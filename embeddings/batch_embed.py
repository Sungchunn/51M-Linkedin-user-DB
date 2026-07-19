"""
INSIGHT - Resumable Batch Embedding Generator
Generates 384-d embeddings with checkpointing for 10M+ profiles

Features:
- Resumable with checkpoint table
- 50K batch processing
- Local MPS backend (Apple Silicon) or OpenAI API
- Progress tracking with tqdm
- Automatic retry on failure
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import List, Optional
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import logging
from tqdm.asyncio import tqdm as async_tqdm
from openai import AsyncOpenAI

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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


class EmbeddingBackend:
    """Base class for embedding backends"""

    def __init__(self, model_name: str, dimensions: int = 384):
        self.model_name = model_name
        self.dimensions = dimensions

    async def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings for batch of texts"""
        raise NotImplementedError


class OpenAIBackend(EmbeddingBackend):
    """OpenAI API backend (text-embedding-3-small with 384 dimensions)"""

    def __init__(self, api_key: str, max_concurrent: int = 10):
        super().__init__("text-embedding-3-small", dimensions=384)
        # Tight timeout: the default 600s turns one hung connection into a
        # ~20-min stall of the whole sequential pipeline; failed sub-batches
        # are skipped and can be re-run under a fresh batch name.
        self.client = AsyncOpenAI(api_key=api_key, timeout=30.0, max_retries=5)
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings via OpenAI API"""
        if not texts or len(texts) > 100:
            return None

        async with self.semaphore:
            try:
                response = await self.client.embeddings.create(
                    input=texts,
                    model=self.model_name,
                    dimensions=self.dimensions
                )
                return [item.embedding for item in response.data]

            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                return None


class LocalMPSBackend(EmbeddingBackend):
    """Local Apple Silicon MPS backend (sentence-transformers)"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        super().__init__(model_name, dimensions=384)

        try:
            # torch/sentence-transformers are only needed for this backend —
            # keep them out of module scope so the OpenAI path works without them
            import torch
            from sentence_transformers import SentenceTransformer

            # Check for MPS availability
            if not torch.backends.mps.is_available():
                raise RuntimeError("MPS not available on this device")

            self.device = "mps"
            self.model = SentenceTransformer(model_name, device=self.device)

            logger.info(f"Loaded SentenceTransformer on MPS: {model_name}")

        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize MPS backend: {e}")

    async def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings locally on MPS"""
        if not texts:
            return None

        try:
            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                self.model.encode,
                texts,
                32,  # batch_size
                True,  # show_progress_bar
                True,  # convert_to_numpy
            )

            return embeddings.tolist()

        except Exception as e:
            logger.error(f"MPS embedding error: {e}")
            return None


def get_backend(backend_type: str = "openai") -> EmbeddingBackend:
    """
    Factory function to create embedding backend.

    Args:
        backend_type: "openai" or "mps"

    Returns:
        EmbeddingBackend instance
    """
    if backend_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return OpenAIBackend(api_key)

    elif backend_type == "mps":
        return LocalMPSBackend()

    else:
        raise ValueError(f"Unknown backend: {backend_type}")


async def get_checkpoint(conn: psycopg.Connection, batch_name: str) -> Optional[dict]:
    """Get checkpoint for batch"""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT * FROM embedding_checkpoint
            WHERE batch_name = %s
        """, (batch_name,))
        return cur.fetchone()


def update_checkpoint(
    conn: psycopg.Connection,
    batch_name: str,
    last_processed_id: str,
    rows_processed: int,
    rows_embedded: int,
    rows_skipped: int
):
    """Update checkpoint"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO embedding_checkpoint (
                batch_name, last_processed_id, rows_processed,
                rows_embedded, rows_skipped
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (batch_name) DO UPDATE SET
                last_processed_id = EXCLUDED.last_processed_id,
                rows_processed = EXCLUDED.rows_processed,
                rows_embedded = EXCLUDED.rows_embedded,
                rows_skipped = EXCLUDED.rows_skipped
        """, (batch_name, last_processed_id, rows_processed, rows_embedded, rows_skipped))


def complete_checkpoint(conn: psycopg.Connection, batch_name: str):
    """Mark checkpoint as completed"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE embedding_checkpoint
            SET completed_at = NOW()
            WHERE batch_name = %s
        """, (batch_name,))


async def generate_embeddings_resumable(
    dsn: str,
    backend: EmbeddingBackend,
    batch_name: str,
    # 5K (not 50K): commits gate durability, so smaller batches cap how much
    # work a mid-batch crash or watchdog kill can roll back
    batch_size: int = 5000,
    embed_batch_size: int = 100,
    limit: Optional[int] = None
):
    """
    Generate embeddings with resumable checkpointing.

    Args:
        dsn: Database connection string
        backend: Embedding backend (OpenAI or MPS)
        batch_name: Unique name for this batch run
        batch_size: Database fetch batch size
        embed_batch_size: Embedding API batch size
        limit: Optional limit on total profiles
    """
    with psycopg.connect(dsn) as conn:
        # Get checkpoint
        checkpoint = await get_checkpoint(conn, batch_name)

        if checkpoint and checkpoint.get('completed_at'):
            logger.info(f"Batch '{batch_name}' already completed at {checkpoint['completed_at']}")
            return checkpoint['rows_embedded'], checkpoint['rows_skipped']

        # Resume from checkpoint
        last_id = checkpoint['last_processed_id'] if checkpoint else None
        rows_processed = checkpoint['rows_processed'] if checkpoint else 0
        rows_embedded = checkpoint['rows_embedded'] if checkpoint else 0
        rows_skipped = checkpoint['rows_skipped'] if checkpoint else 0

        if last_id:
            logger.info(f"Resuming from checkpoint: {rows_processed:,} processed, {rows_embedded:,} embedded")

        # Get total count
        with conn.cursor() as cur:
            if last_id:
                cur.execute("""
                    SELECT count(*) FROM profiles_hot
                    WHERE embedding IS NULL
                      AND quality_score >= 0.7
                      AND is_deleted = FALSE
                      AND id > %s::uuid
                """, (last_id,))
            else:
                cur.execute("""
                    SELECT count(*) FROM profiles_hot
                    WHERE embedding IS NULL
                      AND quality_score >= 0.7
                      AND is_deleted = FALSE
                """)

            total_remaining = cur.fetchone()[0]

        if total_remaining == 0:
            logger.info("✅ No profiles need embeddings")
            complete_checkpoint(conn, batch_name)
            return rows_embedded, rows_skipped

        total_to_process = total_remaining if limit is None else min(total_remaining, limit)

        logger.info(f"Processing {total_to_process:,} profiles (backend: {backend.model_name})")

        # Progress bar
        pbar = async_tqdm(
            total=total_to_process,
            initial=0,
            desc="🔮 Embedding",
            unit=" profiles",
            bar_format='{desc}: {percentage:3.0f}%|{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            colour='cyan'
        )

        try:
            offset = 0

            while offset < total_to_process:
                # Fetch batch
                with conn.cursor(row_factory=dict_row) as cur:
                    if last_id:
                        cur.execute("""
                            SELECT id, full_name, job_title, company_name,
                                   industry, headline, top_skills
                            FROM profiles_hot
                            WHERE embedding IS NULL
                              AND quality_score >= 0.7
                              AND is_deleted = FALSE
                              AND id > %s::uuid
                            ORDER BY id
                            LIMIT %s
                        """, (last_id, batch_size))
                    else:
                        cur.execute("""
                            SELECT id, full_name, job_title, company_name,
                                   industry, headline, top_skills
                            FROM profiles_hot
                            WHERE embedding IS NULL
                              AND quality_score >= 0.7
                              AND is_deleted = FALSE
                            ORDER BY id
                            LIMIT %s
                        """, (batch_size,))

                    profiles = cur.fetchall()

                if not profiles:
                    break

                # Process in sub-batches
                for i in range(0, len(profiles), embed_batch_size):
                    sub_batch = profiles[i:i+embed_batch_size]
                    texts = [_build_embedding_text(p) for p in sub_batch]
                    ids = [str(p['id']) for p in sub_batch]

                    # Generate embeddings
                    embeddings = await backend.embed_batch(texts)

                    if embeddings and len(embeddings) == len(ids):
                        # Bulk update
                        with conn.cursor() as cur:
                            update_data = [
                                (emb, pid)
                                for pid, emb in zip(ids, embeddings)
                            ]

                            cur.executemany("""
                                UPDATE profiles_hot
                                SET embedding = %s::vector(384),
                                    embedding_generated_at = NOW()
                                WHERE id = %s::uuid
                            """, update_data)

                        rows_embedded += len(embeddings)
                    else:
                        logger.warning(f"Embedding failed for sub-batch of {len(sub_batch)}")
                        rows_skipped += len(sub_batch)

                    pbar.update(len(sub_batch))

                # Update checkpoint
                last_id = str(profiles[-1]['id'])
                rows_processed += len(profiles)

                update_checkpoint(
                    conn,
                    batch_name,
                    last_id,
                    rows_processed,
                    rows_embedded,
                    rows_skipped
                )
                conn.commit()

                offset += len(profiles)

                # Log progress every 50K
                if rows_processed % 50000 < batch_size:
                    pbar.write(
                        f"\n📊 Checkpoint @ {rows_processed:,}: "
                        f"✅ {rows_embedded:,} | ❌ {rows_skipped:,}\n"
                    )

                if limit and offset >= limit:
                    break

        finally:
            pbar.close()

        # Mark complete
        complete_checkpoint(conn, batch_name)

        logger.info(f"✅ Complete: {rows_embedded:,} embedded, {rows_skipped:,} skipped")
        return rows_embedded, rows_skipped


def _build_embedding_text(profile: dict) -> str:
    """Build text for embedding from profile fields"""
    parts = []

    if profile.get('full_name'):
        parts.append(f"Name: {profile['full_name']}")

    if profile.get('job_title'):
        parts.append(f"Title: {profile['job_title']}")

    if profile.get('company_name'):
        parts.append(f"Company: {profile['company_name']}")

    if profile.get('industry'):
        parts.append(f"Industry: {profile['industry']}")

    if profile.get('headline'):
        parts.append(profile['headline'])

    if profile.get('top_skills'):
        skills_str = ", ".join(profile['top_skills'][:10])
        parts.append(f"Skills: {skills_str}")

    return " | ".join(parts)[:8000]  # Truncate to 8K chars


def main():
    """CLI entry point"""
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python batch_embed.py <batch_name> [--backend openai|mps] [--limit N]")
        sys.exit(1)

    batch_name = sys.argv[1]

    # Parse options
    backend_type = "openai"
    limit = None

    for i, arg in enumerate(sys.argv[2:], start=2):
        if arg == "--backend" and i + 1 < len(sys.argv):
            backend_type = sys.argv[i + 1]
        elif arg == "--limit" and i + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
            except ValueError:
                print(f"Invalid limit: {sys.argv[i + 1]}")
                sys.exit(1)

    # Get DSN
    dsn = os.getenv("PG_DSN")
    if not dsn:
        logger.error("PG_DSN not set")
        sys.exit(1)

    # TCP keepalives so a silently dead connection (e.g. Docker port-forward
    # dropping an idle socket) surfaces as an error within ~a minute instead
    # of blocking a socket read indefinitely
    sep = "&" if "?" in dsn else "?"
    dsn = f"{dsn}{sep}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3"

    try:
        # Initialize backend
        backend = get_backend(backend_type)

        # Run
        embedded, skipped = asyncio.run(
            generate_embeddings_resumable(
                dsn,
                backend,
                batch_name,
                limit=limit
            )
        )

        logger.info(f"🎉 Success! {embedded:,} embeddings, {skipped:,} skipped")
        sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
