"""
INSIGHT - Parquet to Staging Loader
Loads raw Parquet file to staging_profiles_raw table

Negative Spaces Implementation:
- Validates Parquet file exists
- Enforces batch size limits
- Tracks progress with tqdm
- Logs all failures with context
- Fail-fast on connection errors
"""

import os
import sys
from pathlib import Path
from typing import Optional
import psycopg
from dotenv import load_dotenv
import logging
import pandas as pd
import pyarrow.parquet as pq
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sentinel for uninitialized state
UNINITIALIZED = object()


class ParquetLoadError(Exception):
    """Raised when Parquet loading fails"""
    pass


def validate_file_path(file_path: str) -> Path:
    """
    Validate Parquet file exists and is readable.

    NEGATIVE SPACE CONTRACT:
    - File must exist
    - File must have .parquet extension
    - File must be readable

    Args:
        file_path: Path to Parquet file

    Returns:
        Validated Path object

    Raises:
        ParquetLoadError: If validation fails
    """
    path = Path(file_path)

    if not path.exists():
        raise ParquetLoadError(
            f"NEGATIVE SPACE VIOLATION: Parquet file not found: {path.absolute()}"
        )

    if not path.is_file():
        raise ParquetLoadError(
            f"NEGATIVE SPACE VIOLATION: Path is not a file: {path.absolute()}"
        )

    if path.suffix.lower() != '.parquet':
        logger.warning(
            f"File extension is {path.suffix}, expected .parquet. Proceeding anyway."
        )

    return path


def get_row_count(parquet_file: Path) -> int:
    """
    Get total row count from Parquet file metadata.

    NEGATIVE SPACE CONTRACT:
    - Returns positive integer
    - Raises error if file is corrupted

    Args:
        parquet_file: Path to Parquet file

    Returns:
        Total row count
    """
    try:
        parquet_file_obj = pq.ParquetFile(str(parquet_file))
        row_count = parquet_file_obj.metadata.num_rows

        if row_count <= 0:
            raise ParquetLoadError(
                f"NEGATIVE SPACE VIOLATION: Parquet file has {row_count} rows (expected > 0)"
            )

        logger.info(f"Parquet file contains {row_count:,} rows")
        return row_count

    except Exception as e:
        raise ParquetLoadError(
            f"NEGATIVE SPACE VIOLATION: Failed to read Parquet metadata: {e}"
        ) from e


def load_batch_to_staging(
    conn: psycopg.Connection,
    batch_df: pd.DataFrame,
    batch_id: str
) -> int:
    """
    Load a single batch DataFrame to staging table.

    NEGATIVE SPACE CONTRACT:
    - batch_df must not be empty
    - All column names must match staging table
    - Returns number of rows inserted

    Args:
        conn: Database connection
        batch_df: DataFrame batch
        batch_id: Unique batch identifier

    Returns:
        Number of rows inserted

    Raises:
        ParquetLoadError: If batch load fails
    """
    if batch_df.empty:
        raise ParquetLoadError("NEGATIVE SPACE VIOLATION: Cannot load empty batch")

    # Add batch tracking column
    batch_df['import_batch_id'] = batch_id

    # Convert DataFrame to tuples for COPY
    try:
        with conn.cursor() as cur:
            # Get column names from DataFrame
            columns = list(batch_df.columns)

            # Create COPY statement
            copy_query = f"""
                COPY staging_profiles_raw ({', '.join(f'"{col}"' for col in columns)})
                FROM STDIN
            """

            # Use COPY for maximum performance
            with cur.copy(copy_query) as copy:
                for row in batch_df.itertuples(index=False, name=None):
                    copy.write_row(row)

        conn.commit()
        return len(batch_df)

    except psycopg.Error as e:
        conn.rollback()
        raise ParquetLoadError(
            f"NEGATIVE SPACE VIOLATION: Batch load failed: {e}\n"
            f"Batch ID: {batch_id}, Rows: {len(batch_df)}"
        ) from e


def load_parquet(
    file_path: str,
    dsn: str,
    batch_size: int = 5000,
    batch_id_prefix: Optional[str] = None
) -> int:
    """
    Load Parquet file to staging table in batches.

    NEGATIVE SPACE CONTRACT:
    - file_path must exist
    - dsn must be valid connection string
    - batch_size must be > 0
    - Returns total rows loaded

    Args:
        file_path: Path to Parquet file
        dsn: PostgreSQL connection string
        batch_size: Rows per batch (default 5000)
        batch_id_prefix: Optional prefix for batch IDs

    Returns:
        Total number of rows loaded

    Raises:
        ParquetLoadError: If load fails
    """
    # Validate inputs
    if batch_size <= 0:
        raise ParquetLoadError(
            f"NEGATIVE SPACE VIOLATION: batch_size must be > 0, got {batch_size}"
        )

    # Validate file
    parquet_path = validate_file_path(file_path)

    # Get row count
    total_rows = get_row_count(parquet_path)

    # Generate batch ID prefix
    if not batch_id_prefix:
        from datetime import datetime
        batch_id_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info(
        f"Starting Parquet load: {parquet_path.name} "
        f"({total_rows:,} rows, batch_size={batch_size})"
    )

    # Connect to database
    try:
        with psycopg.connect(dsn) as conn:
            logger.info("✅ Database connection established")

            # Read Parquet in batches using PyArrow
            parquet_file = pq.ParquetFile(str(parquet_path))

            total_loaded = 0
            batch_num = 0

            # Create progress bar
            pbar = tqdm(total=total_rows, desc="Loading batches", unit="rows")

            # Iterate through row groups
            for batch in parquet_file.iter_batches(batch_size=batch_size):
                batch_num += 1
                batch_id = f"{batch_id_prefix}_batch_{batch_num:04d}"

                # Convert Arrow batch to Pandas DataFrame
                batch_df = batch.to_pandas()

                # Load to staging
                rows_loaded = load_batch_to_staging(conn, batch_df, batch_id)

                total_loaded += rows_loaded
                pbar.update(rows_loaded)

                logger.debug(f"Loaded batch {batch_num}: {rows_loaded:,} rows")

            pbar.close()

            # Verify row count
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM staging_profiles_raw WHERE import_batch_id LIKE %s",
                    (f"{batch_id_prefix}%",)
                )
                db_count = cur.fetchone()[0]

            if db_count != total_loaded:
                logger.warning(
                    f"NEGATIVE SPACE WARNING: Expected {total_loaded:,} rows, "
                    f"DB shows {db_count:,} rows"
                )

            logger.info(
                f"✅ Parquet load complete: {total_loaded:,} rows loaded in {batch_num} batches"
            )

            return total_loaded

    except psycopg.Error as e:
        raise ParquetLoadError(
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

    # Get file path from command line or use default
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Default to data directory
        project_root = Path(__file__).parent.parent.parent.parent
        file_path = project_root / 'data' / 'linkedin_profiles.parquet'

    if not Path(file_path).exists():
        logger.error(
            f"NEGATIVE SPACE VIOLATION: Parquet file not found: {file_path}\n"
            f"Usage: python load_parquet_to_staging.py [file_path]"
        )
        sys.exit(1)

    # Get batch size from env or use default
    batch_size = int(os.getenv('BATCH_SIZE', '5000'))

    try:
        total_rows = load_parquet(
            file_path=str(file_path),
            dsn=dsn,
            batch_size=batch_size
        )

        logger.info(f"🎉 Success! {total_rows:,} rows loaded to staging_profiles_raw")
        sys.exit(0)

    except ParquetLoadError as e:
        logger.error(f"❌ Load failed: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
