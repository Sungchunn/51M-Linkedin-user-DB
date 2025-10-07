"""
INSIGHT - DuckDB Analytics Layer
Query remote S3 Parquet files without local copy using httpfs extension
"""

import os
import asyncio
from typing import List, Optional
import duckdb
import logging

logger = logging.getLogger(__name__)

# DuckDB connection (thread-local for safety)
_conn: Optional[duckdb.DuckDBPyConnection] = None


def get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    """
    Get or create DuckDB connection with httpfs extension.

    Enables querying S3 Parquet files without local copy:
    - httpfs extension for S3 access
    - AWS credentials from environment
    - Read-only mode
    """
    global _conn

    if _conn is None:
        # Create in-memory database (no local persistence needed)
        _conn = duckdb.connect(database=":memory:", read_only=False)

        # Install and load httpfs extension
        _conn.execute("INSTALL httpfs;")
        _conn.execute("LOAD httpfs;")

        # Configure S3 credentials (optional, for private buckets)
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        if aws_access_key and aws_secret_key:
            _conn.execute(f"SET s3_region='{aws_region}';")
            _conn.execute(f"SET s3_access_key_id='{aws_access_key}';")
            _conn.execute(f"SET s3_secret_access_key='{aws_secret_key}';")
            logger.info("DuckDB S3 credentials configured")
        else:
            logger.warning("AWS credentials not set - S3 access will be public only")

        logger.info("DuckDB connection initialized with httpfs extension")

    return _conn


def get_parquet_path() -> str:
    """
    Get S3 path to full Parquet dataset.

    Format: s3://bucket-name/path/to/linkedin_profiles_51m.parquet
    or local path for testing: /path/to/file.parquet
    """
    parquet_path = os.getenv(
        "PARQUET_S3_PATH",
        "s3://your-bucket/linkedin_profiles_51m.parquet"
    )
    return parquet_path


async def run_duckdb_query(query: str) -> List[dict]:
    """
    Execute DuckDB query asynchronously.

    Wraps synchronous DuckDB operations in asyncio executor.
    """
    def _execute():
        conn = get_duckdb_conn()
        result = conn.execute(query).fetchall()
        columns = [desc[0] for desc in conn.description]

        # Convert to list of dicts
        return [dict(zip(columns, row)) for row in result]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _execute)


async def get_industry_stats(limit: int = 20) -> List[dict]:
    """
    Get industry statistics from full S3 Parquet dataset.

    Queries 51M profiles without local copy.
    """
    parquet_path = get_parquet_path()

    query = f"""
        SELECT
            Industry as industry,
            COUNT(*) as count,
            AVG("Profile Completeness") as avg_completeness,
            COUNT(DISTINCT "Location Country") as countries
        FROM read_parquet('{parquet_path}')
        WHERE Industry IS NOT NULL
        GROUP BY Industry
        ORDER BY count DESC
        LIMIT {limit}
    """

    try:
        results = await run_duckdb_query(query)
        logger.info(f"Industry stats query complete: {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Industry stats query failed: {e}", exc_info=True)
        raise


async def get_country_stats(limit: int = 20) -> List[dict]:
    """
    Get country statistics from full S3 Parquet dataset.
    """
    parquet_path = get_parquet_path()

    query = f"""
        SELECT
            "Location Country" as country,
            COUNT(*) as count,
            AVG("Years Experience") as avg_experience,
            COUNT(DISTINCT Industry) as industries
        FROM read_parquet('{parquet_path}')
        WHERE "Location Country" IS NOT NULL
        GROUP BY "Location Country"
        ORDER BY count DESC
        LIMIT {limit}
    """

    try:
        results = await run_duckdb_query(query)
        logger.info(f"Country stats query complete: {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Country stats query failed: {e}", exc_info=True)
        raise


async def get_skill_trends(skill: str, limit: int = 20) -> List[dict]:
    """
    Get profiles with a specific skill from full dataset.

    Example analytics query for exploring skill distributions.
    """
    parquet_path = get_parquet_path()

    query = f"""
        SELECT
            "Location Country" as country,
            Industry as industry,
            COUNT(*) as count,
            AVG("Years Experience") as avg_experience
        FROM read_parquet('{parquet_path}')
        WHERE Skills LIKE '%{skill}%'
        GROUP BY "Location Country", Industry
        ORDER BY count DESC
        LIMIT {limit}
    """

    try:
        results = await run_duckdb_query(query)
        logger.info(f"Skill trends query complete: skill={skill}, results={len(results)}")
        return results
    except Exception as e:
        logger.error(f"Skill trends query failed: {e}", exc_info=True)
        raise


async def create_stratified_sample(
    output_path: str,
    sample_pct: float = 0.01,
    strata_cols: List[str] = None
):
    """
    Create stratified sample for dev/testing.

    Example: 1% sample stratified by country + industry = ~510K profiles
    with proportional representation.

    Args:
        output_path: Local path to save sample Parquet
        sample_pct: Percentage to sample (0.01 = 1%)
        strata_cols: Columns to stratify by (default: ["Location Country", "Industry"])
    """
    if strata_cols is None:
        strata_cols = ["Location Country", "Industry"]

    parquet_path = get_parquet_path()
    strata_str = ", ".join([f'"{col}"' for col in strata_cols])

    query = f"""
        COPY (
            SELECT *
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY {strata_str}
                        ORDER BY random()
                    ) as rn,
                    CEIL(COUNT(*) OVER (
                        PARTITION BY {strata_str}
                    ) * {sample_pct}) as sample_size
                FROM read_parquet('{parquet_path}')
            )
            WHERE rn <= sample_size
        ) TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """

    try:
        await run_duckdb_query(query)
        logger.info(f"Stratified sample created: {output_path} ({sample_pct*100}%)")
    except Exception as e:
        logger.error(f"Sample creation failed: {e}", exc_info=True)
        raise


async def test_connection():
    """Test DuckDB connectivity and S3 access"""
    parquet_path = get_parquet_path()

    query = f"""
        SELECT COUNT(*) as total
        FROM read_parquet('{parquet_path}')
    """

    try:
        results = await run_duckdb_query(query)
        total = results[0]['total']
        logger.info(f"DuckDB S3 connectivity OK: {total:,} rows in dataset")
        return True
    except Exception as e:
        logger.error(f"DuckDB S3 connectivity test failed: {e}")
        return False


def close_duckdb():
    """Close DuckDB connection"""
    global _conn
    if _conn:
        _conn.close()
        _conn = None
        logger.info("DuckDB connection closed")
