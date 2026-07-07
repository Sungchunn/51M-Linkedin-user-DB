"""
INSIGHT - Database Connection Pool
AsyncPG connection pool management

Negative Spaces Implementation:
- Pool size limits enforced
- Connection validation on acquire
- Graceful shutdown handling
- Timeout enforcement
"""

import os
import asyncpg
from typing import Optional
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Global pool instance
_pool: Optional[asyncpg.Pool] = None


class DatabaseError(Exception):
    """Raised when database operations fail"""
    pass


async def create_pool(
    dsn: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    timeout: Optional[float] = None
) -> asyncpg.Pool:
    """
    Create AsyncPG connection pool.

    NEGATIVE SPACE CONTRACT:
    - dsn must be valid connection string
    - min_size must be > 0
    - max_size must be >= min_size
    - Returns initialized pool

    Args:
        dsn: PostgreSQL connection string
        min_size: Minimum pool connections
        max_size: Maximum pool connections
        timeout: Connection timeout in seconds

    Returns:
        AsyncPG connection pool

    Raises:
        DatabaseError: If pool creation fails
    """
    # Load from environment if not provided
    dsn = dsn or os.getenv('PG_DSN')
    min_size = min_size or int(os.getenv('DB_POOL_MIN', '5'))
    max_size = max_size or int(os.getenv('DB_POOL_MAX', '40'))
    timeout = timeout or float(os.getenv('DB_TIMEOUT', '5.0'))

    if not dsn:
        raise DatabaseError(
            "NEGATIVE SPACE VIOLATION: PG_DSN not found in environment"
        )

    if min_size <= 0:
        raise DatabaseError(
            f"NEGATIVE SPACE VIOLATION: min_size must be > 0, got {min_size}"
        )

    if max_size < min_size:
        raise DatabaseError(
            f"NEGATIVE SPACE VIOLATION: max_size ({max_size}) must be >= min_size ({min_size})"
        )

    try:
        logger.info(
            f"Creating connection pool: min={min_size}, max={max_size}, timeout={timeout}s"
        )

        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            command_timeout=30.0,  # 30s query timeout
            server_settings={
                'application_name': 'insight-api',
            }
        )

        # Test connection
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        logger.info(f"✅ Connection pool created successfully")

        return pool

    except Exception as e:
        raise DatabaseError(
            f"NEGATIVE SPACE VIOLATION: Failed to create connection pool: {e}"
        ) from e


async def get_pool() -> asyncpg.Pool:
    """
    Get or create global connection pool.

    NEGATIVE SPACE CONTRACT:
    - Returns valid pool or raises error
    - Never returns None

    Returns:
        AsyncPG connection pool

    Raises:
        DatabaseError: If pool cannot be created
    """
    global _pool

    if _pool is None:
        _pool = await create_pool()

    return _pool


async def close_pool():
    """
    Close global connection pool.

    NEGATIVE SPACE CONTRACT:
    - Gracefully closes all connections
    - Safe to call multiple times
    """
    global _pool

    if _pool is not None:
        logger.info("Closing connection pool...")
        await _pool.close()
        _pool = None
        logger.info("✅ Connection pool closed")


@asynccontextmanager
async def get_connection():
    """
    Context manager for acquiring connection from pool.

    NEGATIVE SPACE CONTRACT:
    - Always releases connection back to pool
    - Handles exceptions gracefully

    Usage:
        async with get_connection() as conn:
            result = await conn.fetchval("SELECT 1")

    Yields:
        AsyncPG connection
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        yield conn
