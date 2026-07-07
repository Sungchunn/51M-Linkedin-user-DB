"""
INSIGHT - Database Connection Management
AsyncPG connection pooling with psycopg for complex queries
"""

import os
from typing import Optional
import psycopg_pool
import logging

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[psycopg_pool.AsyncConnectionPool] = None


async def get_db_pool() -> psycopg_pool.AsyncConnectionPool:
    """
    Get or create async connection pool.

    Settings optimized for M2 MacBook Air:
    - min_size=5, max_size=20 (reasonable for local dev)
    - timeout=30s
    - max_lifetime=3600s (1 hour)
    """
    global _pool

    if _pool is None:
        dsn = os.getenv("PG_DSN")
        if not dsn:
            raise ValueError("PG_DSN environment variable not set")

        min_size = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
        max_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))

        _pool = psycopg_pool.AsyncConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=30,
            max_lifetime=3600,
            open=True
        )

        logger.info(
            f"Database pool initialized: min={min_size}, max={max_size}"
        )

    return _pool


async def close_db_pool():
    """Close database connection pool"""
    global _pool

    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def execute_query(query: str, params: tuple = None, fetch: str = "all"):
    """
    Execute query with connection from pool.

    Args:
        query: SQL query string
        params: Query parameters tuple
        fetch: "all", "one", or "none"

    Returns:
        Query results based on fetch mode
    """
    pool = await get_db_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)

            if fetch == "all":
                return await cur.fetchall()
            elif fetch == "one":
                return await cur.fetchone()
            else:
                return None


async def execute_query_dict(query: str, params: tuple = None, fetch: str = "all"):
    """
    Execute query and return results as dicts.

    Uses psycopg dict_row factory.
    """
    from psycopg.rows import dict_row

    pool = await get_db_pool()

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)

            if fetch == "all":
                return await cur.fetchall()
            elif fetch == "one":
                return await cur.fetchone()
            else:
                return None


# Database settings optimized for M2 MacBook Air
# Applied via docker-compose.yml command flags:
#
# shared_buffers = 2GB              # 25% of Docker RAM (8GB)
# effective_cache_size = 8GB        # 50% of Docker RAM
# maintenance_work_mem = 2GB        # For index builds
# work_mem = 64MB                   # Per operation
# max_wal_size = 4GB
# wal_compression = on
# random_page_cost = 1.1            # SSD
# effective_io_concurrency = 200    # SSD
# max_worker_processes = 8
# max_parallel_workers_per_gather = 4
# max_parallel_workers = 8
# checkpoint_timeout = 15min
# checkpoint_completion_target = 0.9
# min_wal_size = 1GB
#
# Query-time settings (set per session):
# SET hnsw.ef_search = 100;         # Higher = better recall for vector search
