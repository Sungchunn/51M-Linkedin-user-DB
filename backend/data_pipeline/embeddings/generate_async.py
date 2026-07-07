"""
INSIGHT - Async Parallel Embedding Generation
Uses asyncio to parallelize OpenAI API calls for 5-10x speed improvement

Optimizations:
- Parallel API calls (10 concurrent requests)
- Async batch processing
- Rate limit handling
- Bulk database updates
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import List, Tuple, Optional
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import logging
from tqdm.asyncio import tqdm as async_tqdm
from openai import AsyncOpenAI

# Import modules
from backend.data_pipeline.ingestion import transformers as tf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose logs
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


class AsyncEmbeddingGenerator:
    """Async embedding generator with parallel API calls"""

    def __init__(self, api_key: str, max_concurrent: int = 10):
        """
        Initialize async generator.

        Args:
            api_key: OpenAI API key
            max_concurrent: Maximum concurrent API calls
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def embed_batch_async(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Generate embeddings with rate limiting.

        Args:
            texts: List of texts (max 100)

        Returns:
            List of embeddings or None
        """
        if not texts or len(texts) > 100:
            return None

        async with self.semaphore:
            try:
                response = await self.client.embeddings.create(
                    input=texts,
                    model=self.model
                )
                return [item.embedding for item in response.data]

            except Exception as e:
                logger.error(f"API error: {e}")
                return None

    async def process_batch(
        self,
        profiles: List[dict],
        batch_size: int = 100
    ) -> Tuple[List[str], List[List[float]]]:
        """
        Process profiles in parallel sub-batches.

        Args:
            profiles: List of profile dicts
            batch_size: Profiles per API call

        Returns:
            Tuple of (profile_ids, embeddings)
        """
        tasks = []
        all_ids = []
        batch_info = []

        # Create tasks for parallel execution
        for i in range(0, len(profiles), batch_size):
            sub_batch = profiles[i:i+batch_size]
            texts = [tf.build_content_for_embedding(p) for p in sub_batch]
            ids = [p['id'] for p in sub_batch]

            tasks.append(self.embed_batch_async(texts))
            all_ids.extend(ids)
            batch_info.append((i, len(texts)))

        # Execute all API calls in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful embeddings
        all_embeddings = []
        successful_ids = []

        for (start_idx, count), result in zip(batch_info, results):
            if isinstance(result, list) and result:
                # Get corresponding IDs
                batch_ids = all_ids[start_idx:start_idx+count]
                all_embeddings.extend(result)
                successful_ids.extend(batch_ids)

        return successful_ids, all_embeddings


def update_profiles_bulk_sync(
    conn: psycopg.Connection,
    profile_ids: List[str],
    embeddings: List[List[float]]
) -> int:
    """Bulk update profiles (synchronous for psycopg)"""
    try:
        with conn.cursor() as cur:
            update_data = [
                (emb, pid)
                for pid, emb in zip(profile_ids, embeddings)
            ]

            cur.executemany("""
                UPDATE profiles
                SET embedding = %s::vector,
                    updated_at = NOW()
                WHERE id = %s
            """, update_data)

            return cur.rowcount

    except Exception as e:
        logger.error(f"Bulk update failed: {e}")
        return 0


async def generate_embeddings_async(
    dsn: str,
    min_quality_score: float = 0.7,
    batch_size: int = 5000,
    limit: Optional[int] = None
):
    """
    Generate embeddings with async parallel processing.

    Args:
        dsn: Database connection string
        min_quality_score: Minimum quality threshold
        batch_size: Profiles per database fetch
        limit: Optional limit on total profiles
    """
    # Initialize
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    generator = AsyncEmbeddingGenerator(api_key, max_concurrent=10)

    # Connect to database
    with psycopg.connect(dsn) as conn:
        # Get total count
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*) FROM profiles
                WHERE embedding IS NULL
                  AND content_quality_score >= %s
                  AND is_deleted = FALSE
            """, (min_quality_score,))

            total_eligible = cur.fetchone()[0]

        if total_eligible == 0:
            logger.info("✅ No profiles need embeddings")
            return 0, 0

        total_to_process = total_eligible if limit is None else min(total_eligible, limit)

        logger.info(f"Found {total_eligible:,} eligible profiles (processing {total_to_process:,})")

        total_success = 0
        total_failed = 0
        offset = 0

        # Progress bar
        pbar = async_tqdm(
            total=total_to_process,
            desc="🚀 Embedding (async)",
            unit=" profiles",
            bar_format='{desc}: {percentage:3.0f}%|{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            colour='magenta'
        )

        try:
            while offset < total_to_process:
                # Fetch batch
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("""
                        SELECT id, job_title, company_name, industry, location, skills
                        FROM profiles
                        WHERE embedding IS NULL
                          AND content_quality_score >= %s
                          AND is_deleted = FALSE
                        ORDER BY created_at
                        LIMIT %s OFFSET %s
                    """, (min_quality_score, batch_size, offset))

                    profiles = cur.fetchall()

                if not profiles:
                    break

                # Process in parallel
                profile_ids, embeddings = await generator.process_batch(profiles, batch_size=100)

                # Bulk update database
                if profile_ids and embeddings:
                    success_count = update_profiles_bulk_sync(conn, profile_ids, embeddings)
                    conn.commit()

                    total_success += success_count
                    total_failed += (len(profiles) - success_count)

                pbar.update(len(profiles))
                offset += len(profiles)

                # Checkpoint every 50K
                if total_success % 50000 < batch_size:
                    pbar.write(
                        f"\n📊 Checkpoint @ {total_success:,}: "
                        f"✅ {total_success:,} | ❌ {total_failed:,}\n"
                    )

                if limit and offset >= limit:
                    break

        finally:
            pbar.close()

        logger.info(f"✅ Complete: {total_success:,} generated, {total_failed:,} failed")
        return total_success, total_failed


def main():
    """CLI entry point"""
    load_dotenv()

    dsn = os.getenv('PG_DSN')
    if not dsn:
        logger.error("PG_DSN not set")
        sys.exit(1)

    # Optional limit
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid limit: {sys.argv[1]}")
            sys.exit(1)

    # Run async
    try:
        success, failed = asyncio.run(
            generate_embeddings_async(dsn, limit=limit)
        )

        logger.info(f"🎉 Success! {success:,} embeddings, {failed:,} failed")
        sys.exit(0 if failed == 0 else 1)

    except Exception as e:
        logger.error(f"❌ Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
