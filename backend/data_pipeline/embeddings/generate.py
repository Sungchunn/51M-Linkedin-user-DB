"""
INSIGHT - Embedding Generation Pipeline
Generates embeddings for profiles that meet quality threshold

Negative Spaces Implementation:
- Quality threshold enforcement (≥0.7)
- Batch size limits (5000 I/O, 100 embed)
- Progress tracking with tqdm
- Skip and log failures
- Transaction safety
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import logging
from tqdm import tqdm

# Import modules
from backend.data_pipeline.ingestion import transformers as tf
from backend.data_pipeline.embeddings import providers

# Configure logging - suppress debug messages for cleaner output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose provider logs
logging.getLogger('backend.data_pipeline.embeddings.providers').setLevel(logging.WARNING)
logging.getLogger('backend.data_pipeline.embeddings.retry').setLevel(logging.WARNING)


class EmbeddingGenerationError(Exception):
    """Raised when embedding generation fails"""
    pass


def get_profiles_needing_embeddings(
    conn: psycopg.Connection,
    min_quality_score: float,
    batch_size: int,
    offset: int
) -> List[dict]:
    """
    Fetch profiles that need embeddings.

    NEGATIVE SPACE CONTRACT:
    - Only returns profiles with quality >= min_quality_score
    - Only returns profiles without embeddings (embedding IS NULL)
    - Returns at most batch_size rows

    Args:
        conn: Database connection
        min_quality_score: Minimum quality threshold
        batch_size: Maximum rows to fetch
        offset: Row offset for pagination

    Returns:
        List of profile dicts
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                id,
                job_title,
                company_name,
                industry,
                location,
                skills
            FROM profiles
            WHERE embedding IS NULL
              AND content_quality_score >= %s
              AND is_deleted = FALSE
            ORDER BY created_at
            LIMIT %s OFFSET %s
        """, (min_quality_score, batch_size, offset))

        return cur.fetchall()


def build_embedding_text(profile: dict) -> str:
    """
    Build text content for embedding.

    Uses the standard template from transformers.

    NEGATIVE SPACE CONTRACT:
    - Always returns non-empty string
    - Truncates to 8000 chars max

    Args:
        profile: Profile dict

    Returns:
        Text string for embedding
    """
    return tf.build_content_for_embedding(profile)


def update_profiles_bulk(
    conn: psycopg.Connection,
    profile_ids: List[str],
    embeddings: List[List[float]]
) -> Tuple[int, int]:
    """
    Bulk update profiles with embeddings (much faster than individual updates).

    NEGATIVE SPACE CONTRACT:
    - embeddings must be 1536 dimensions each
    - len(profile_ids) must equal len(embeddings)
    - Returns (success_count, failure_count)

    Args:
        conn: Database connection
        profile_ids: List of profile UUIDs
        embeddings: List of 1536-dim embedding vectors

    Returns:
        Tuple of (successful_updates, failed_updates)
    """
    if len(profile_ids) != len(embeddings):
        logger.error(
            f"NEGATIVE SPACE: Mismatch - {len(profile_ids)} IDs vs {len(embeddings)} embeddings"
        )
        return 0, len(profile_ids)

    success_count = 0
    failure_count = 0

    try:
        # Use executemany for bulk update (much faster)
        with conn.cursor() as cur:
            # Prepare data for bulk update
            update_data = [
                (embedding, profile_id)
                for profile_id, embedding in zip(profile_ids, embeddings)
            ]

            cur.executemany("""
                UPDATE profiles
                SET embedding = %s::vector,
                    updated_at = NOW()
                WHERE id = %s
            """, update_data)

            success_count = cur.rowcount
            failure_count = len(profile_ids) - success_count

        return success_count, failure_count

    except Exception as e:
        logger.error(f"Bulk update failed: {e}")
        return 0, len(profile_ids)


def generate_embeddings_batch(
    conn: psycopg.Connection,
    profiles: List[dict],
    provider: providers.OpenAIEmbeddingProvider
) -> Tuple[int, int]:
    """
    Generate and store embeddings for a batch of profiles with bulk updates.

    NEGATIVE SPACE CONTRACT:
    - Processes in sub-batches of 100 (OpenAI limit)
    - Uses bulk update for speed
    - Commits after each sub-batch
    - Returns (success_count, failure_count)

    Args:
        conn: Database connection
        profiles: List of profile dicts
        provider: Embedding provider

    Returns:
        Tuple of (successful_embeds, failed_embeds)
    """
    success_count = 0
    failure_count = 0

    # Split into sub-batches of 100 (OpenAI limit)
    embed_batch_size = int(os.getenv('BATCH_SIZE_EMBED', '100'))

    for i in range(0, len(profiles), embed_batch_size):
        sub_batch = profiles[i:i+embed_batch_size]

        # Build texts for embedding
        texts = []
        profile_ids = []

        for profile in sub_batch:
            text = build_embedding_text(profile)
            texts.append(text)
            profile_ids.append(profile['id'])

        # Generate embeddings via OpenAI
        embeddings = provider.embed_batch(texts)

        if embeddings is None:
            logger.error(f"Failed to generate embeddings for sub-batch of {len(texts)}")
            failure_count += len(texts)
            continue

        # Bulk update profiles (much faster than individual updates)
        success, failed = update_profiles_bulk(conn, profile_ids, embeddings)
        success_count += success
        failure_count += failed

        # Commit sub-batch
        conn.commit()

    return success_count, failure_count


def generate_all_embeddings(
    dsn: str,
    min_quality_score: Optional[float] = None,
    batch_size: Optional[int] = None,
    limit: Optional[int] = None
) -> Tuple[int, int]:
    """
    Generate embeddings for all eligible profiles.

    NEGATIVE SPACE CONTRACT:
    - Only processes profiles with quality >= min_quality_score
    - Only processes profiles without embeddings
    - Processes in batches for memory efficiency
    - Returns (total_generated, total_failed)

    Args:
        dsn: PostgreSQL connection string
        min_quality_score: Minimum quality threshold (default from env)
        batch_size: I/O batch size (default from env)
        limit: Optional limit on total profiles to process

    Returns:
        Tuple of (total_generated, total_failed)

    Raises:
        EmbeddingGenerationError: If critical error occurs
    """
    # Load configuration
    min_quality_score = min_quality_score or float(os.getenv('MIN_QUALITY_SCORE', '0.7'))
    batch_size = batch_size or int(os.getenv('BATCH_SIZE_IO', '5000'))

    logger.info(f"Starting embedding generation (min_quality={min_quality_score})")

    # Initialize provider
    try:
        provider = providers.get_provider()
    except providers.EmbeddingProviderError as e:
        raise EmbeddingGenerationError(f"Failed to initialize provider: {e}") from e

    # Connect to database
    try:
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

            # Apply limit if specified
            total_to_process = total_eligible if limit is None else min(total_eligible, limit)

            logger.info(
                f"Found {total_eligible:,} eligible profiles "
                f"(processing {total_to_process:,})"
            )

            total_success = 0
            total_failed = 0

            # Process in batches with enhanced progress bar
            with tqdm(total=total_to_process,
                     desc="🔮 Embedding",
                     unit=" profiles",
                     bar_format='{desc}: {percentage:3.0f}%|{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]',
                     colour='cyan',
                     ncols=120) as pbar:
                offset = 0
                batch_count = 0

                while offset < total_to_process:
                    # Fetch batch
                    profiles = get_profiles_needing_embeddings(
                        conn,
                        min_quality_score,
                        batch_size,
                        offset
                    )

                    if not profiles:
                        break

                    # Generate embeddings
                    success, failed = generate_embeddings_batch(conn, profiles, provider)

                    total_success += success
                    total_failed += failed
                    batch_count += 1

                    pbar.update(len(profiles))

                    # Update stats every 5 batches
                    if batch_count % 5 == 0 or offset + len(profiles) >= total_to_process:
                        success_rate = (total_success / (total_success + total_failed) * 100) if (total_success + total_failed) > 0 else 0
                        pbar.set_postfix_str(
                            f"✅ {total_success:,} | ❌ {total_failed:,} | 📈 {success_rate:.1f}%",
                            refresh=True
                        )

                    offset += len(profiles)

                    # Checkpoint every 50K
                    if total_success % 50000 < batch_size:
                        pbar.write(
                            f"\n📊 Checkpoint @ {total_success:,} embeddings: "
                            f"✅ {total_success:,} success | ❌ {total_failed:,} failed\n"
                        )

                    # Check limit
                    if limit and offset >= limit:
                        break

            logger.info(
                f"✅ Embedding generation complete: "
                f"{total_success:,} generated, {total_failed:,} failed"
            )

            return total_success, total_failed

    except psycopg.Error as e:
        raise EmbeddingGenerationError(
            f"NEGATIVE SPACE VIOLATION: Database error: {e}"
        ) from e


def main():
    """
    Main entry point for CLI execution.
    """
    load_dotenv()

    # Get environment variables
    dsn = os.getenv('PG_DSN')
    if not dsn:
        logger.error("NEGATIVE SPACE VIOLATION: PG_DSN environment variable not set")
        sys.exit(1)

    # Get optional limit from command line
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            logger.info(f"Processing limit: {limit:,} profiles")
        except ValueError:
            logger.error(f"Invalid limit: {sys.argv[1]} (must be integer)")
            sys.exit(1)

    try:
        success, failed = generate_all_embeddings(dsn, limit=limit)

        logger.info(
            f"🎉 Success! {success:,} embeddings generated, {failed:,} failed"
        )

        sys.exit(0 if failed == 0 else 1)

    except EmbeddingGenerationError as e:
        logger.error(f"❌ Embedding generation failed: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
