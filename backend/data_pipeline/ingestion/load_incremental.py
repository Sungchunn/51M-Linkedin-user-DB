"""
INSIGHT - Incremental Data Loader
Loads data from Parquet files with automatic deduplication

Negative Spaces Implementation:
- Deduplicates against existing database records
- Idempotent (safe to re-run with same data)
- Progress tracking with resume capability
- Comprehensive logging and statistics

Usage:
    python -m backend.data_pipeline.ingestion.load_incremental <parquet_file> [--limit N]
"""

import os
import sys
from pathlib import Path
from typing import Optional
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import logging
from tqdm import tqdm
import pyarrow.parquet as pf

# Import modules
from backend.data_pipeline.ingestion import transformers as tf
from backend.data_pipeline.ingestion import validators as val
from backend.data_pipeline.ingestion import deduplication as dedup
from backend.data_pipeline.ingestion.load_to_core import (
    transform_staging_row,
    insert_profile,
    insert_profiles_bulk
)

# Configure logging - suppress warnings to show progress bar
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose warnings from transformers and deduplication
logging.getLogger('backend.data_pipeline.ingestion.transformers').setLevel(logging.ERROR)
logging.getLogger('backend.data_pipeline.ingestion.deduplication').setLevel(logging.WARNING)
logging.getLogger('backend.data_pipeline.ingestion.load_to_core').setLevel(logging.WARNING)


class IncrementalLoadError(Exception):
    """Raised when incremental load fails"""
    pass


def load_parquet_batch_to_profiles(
    conn: psycopg.Connection,
    parquet_file: str,
    batch_size: int = 10000,
    limit: Optional[int] = None
) -> dict:
    """
    Load Parquet data directly to profiles table with deduplication.

    NEGATIVE SPACE CONTRACT:
    - Skips existing profiles (by linkedin_username or content hash)
    - Returns statistics dict
    - Commits in batches
    - Idempotent (safe to re-run)

    Args:
        conn: Database connection
        parquet_file: Path to Parquet file
        batch_size: Rows to process per batch
        limit: Optional limit on total rows to process

    Returns:
        Dict with statistics (loaded, duplicates, failed)
    """
    if not os.path.exists(parquet_file):
        raise IncrementalLoadError(f"File not found: {parquet_file}")

    logger.info(f"Loading data from: {parquet_file}")

    # Open Parquet file with streaming reader (memory efficient)
    parquet_file_obj = pf.ParquetFile(parquet_file)
    total_rows = parquet_file_obj.metadata.num_rows

    if limit:
        total_rows = min(total_rows, limit)
        logger.info(f"Limiting to {limit:,} rows")

    logger.info(f"Total rows to process: {total_rows:,}")

    # Statistics
    stats = {
        'total_processed': 0,
        'loaded': 0,
        'duplicates': 0,
        'failed_transform': 0,
        'failed_validation': 0,
        'failed_insert': 0
    }

    # Cache existing usernames/hashes ONCE (huge performance boost)
    logger.info("Loading existing profiles for deduplication...")
    existing_usernames = dedup.get_existing_linkedin_usernames(conn)
    existing_hashes = dedup.get_existing_profile_hashes(conn)
    logger.info(f"Cached {len(existing_usernames):,} usernames and {len(existing_hashes):,} hashes")

    # Process in batches using streaming reader
    rows_processed = 0
    with tqdm(total=total_rows, desc="Loading profiles", unit=" rows",
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
        # Iterate through Parquet file in batches
        for batch_table in parquet_file_obj.iter_batches(batch_size=batch_size):
            # Stop if we've hit the limit
            if rows_processed >= total_rows:
                break

            # Convert batch to pandas (only this batch, not whole file)
            batch_df = batch_table.to_pandas()

            # Trim if this batch exceeds the limit
            if limit and rows_processed + len(batch_df) > limit:
                remaining = limit - rows_processed
                batch_df = batch_df.iloc[:remaining]

            # Convert to list of dicts
            staging_rows = batch_df.to_dict('records')

            # Transform and filter in one pass
            profiles_to_insert = []
            for staging_row in staging_rows:
                try:
                    # Transform
                    core_row = transform_staging_row(staging_row)
                    if not core_row:
                        stats['failed_transform'] += 1
                        continue

                    # Check duplicate (using cached sets)
                    is_dup, _ = dedup.is_duplicate_profile(core_row, existing_usernames, existing_hashes)
                    if is_dup:
                        stats['duplicates'] += 1
                        continue

                    # Validate quality
                    quality_score = val.calculate_quality_score(core_row)
                    core_row['content_quality_score'] = quality_score

                    if quality_score < 0.5:
                        stats['failed_validation'] += 1
                        continue

                    # Add to batch insert
                    profiles_to_insert.append(core_row)

                    # Update cache (for within-batch deduplication)
                    if core_row.get('linkedin_username'):
                        existing_usernames.add(core_row['linkedin_username'].lower())
                    existing_hashes.add(dedup.generate_profile_hash(core_row))

                except Exception as e:
                    logger.debug(f"Transform error: {e}")
                    stats['failed_transform'] += 1

            # Bulk insert all profiles at once (MUCH faster)
            if profiles_to_insert:
                try:
                    success_count, failure_count = insert_profiles_bulk(conn, profiles_to_insert)
                    stats['loaded'] += success_count
                    stats['failed_insert'] += failure_count

                    # Commit batch at once
                    conn.commit()

                except Exception as e:
                    logger.warning(f"Bulk insert failed: {e}")
                    stats['failed_insert'] += len(profiles_to_insert)
                    conn.rollback()

            stats['total_processed'] += len(staging_rows)
            rows_processed += len(staging_rows)

            # Update progress bar with detailed stats
            pbar.set_postfix({
                'loaded': f"{stats['loaded']:,}",
                'dups': f"{stats['duplicates']:,}",
                'failed': f"{stats['failed_insert']:,}"
            })
            pbar.update(len(staging_rows))

            # Log progress every 50K rows
            if stats['total_processed'] % 50000 == 0:
                logger.info(
                    f"Progress: {stats['total_processed']:,} processed, "
                    f"{stats['loaded']:,} loaded, "
                    f"{stats['duplicates']:,} duplicates, "
                    f"{stats['failed_insert']:,} failed"
                )

    return stats


def main():
    """
    Main entry point for CLI execution.
    """
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m backend.data_pipeline.ingestion.load_incremental <parquet_file> [--limit N]")
        sys.exit(1)

    parquet_file = sys.argv[1]

    # Parse optional limit
    limit = None
    if len(sys.argv) > 2 and sys.argv[2] == '--limit':
        if len(sys.argv) < 4:
            print("Error: --limit requires a number")
            sys.exit(1)
        try:
            limit = int(sys.argv[3])
        except ValueError:
            print(f"Error: Invalid limit value: {sys.argv[3]}")
            sys.exit(1)

    # Get database connection
    dsn = os.getenv('PG_DSN')
    if not dsn:
        logger.error("PG_DSN environment variable not set")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("INSIGHT - Incremental Data Loader")
    logger.info("=" * 60)
    logger.info(f"File: {parquet_file}")
    if limit:
        logger.info(f"Limit: {limit:,} rows")
    logger.info("")

    try:
        with psycopg.connect(dsn) as conn:
            # Get initial stats
            initial_stats = dedup.get_import_statistics(conn)
            logger.info(f"Before: {initial_stats['total_profiles']:,} profiles in database")
            logger.info("")

            # Load data
            stats = load_parquet_batch_to_profiles(conn, parquet_file, limit=limit)

            # Get final stats
            final_stats = dedup.get_import_statistics(conn)

            logger.info("")
            logger.info("=" * 60)
            logger.info("Load Summary")
            logger.info("=" * 60)
            logger.info(f"Total processed:     {stats['total_processed']:,}")
            logger.info(f"✅ Loaded:           {stats['loaded']:,}")
            logger.info(f"⏭️  Duplicates:       {stats['duplicates']:,}")
            logger.info(f"❌ Failed transform: {stats['failed_transform']:,}")
            logger.info(f"❌ Failed validation: {stats['failed_validation']:,}")
            logger.info(f"❌ Failed insert:    {stats['failed_insert']:,}")
            logger.info("")
            logger.info(f"Database totals:")
            logger.info(f"  Total profiles:    {final_stats['total_profiles']:,}")
            logger.info(f"  With embeddings:   {final_stats['with_embeddings']:,}")
            logger.info(f"  Avg quality:       {final_stats['avg_quality']}")
            logger.info(f"  High quality:      {final_stats['high_quality']:,} (≥0.7)")
            logger.info("")

            if stats['loaded'] > 0:
                logger.info("✅ Incremental load completed successfully!")
                sys.exit(0)
            elif stats['duplicates'] == stats['total_processed']:
                logger.info("ℹ️  All profiles were duplicates (already in database)")
                sys.exit(0)
            else:
                logger.warning("⚠️  No profiles loaded (check validation rules)")
                sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Load failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
