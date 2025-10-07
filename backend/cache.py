"""
INSIGHT - Redis Caching Layer
Read-through cache for search results and profile details
"""

import os
import json
from typing import Optional, Any
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """Async Redis cache wrapper"""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.enabled = os.getenv("REDIS_ENABLED", "true").lower() == "true"

    async def _get_client(self) -> aioredis.Redis:
        """Get or create Redis client"""
        if self.redis is None:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))

            self.redis = await aioredis.from_url(
                f"redis://{redis_host}:{redis_port}",
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )

            logger.info(f"Redis client initialized: {redis_host}:{redis_port}")

        return self.redis

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        if not self.enabled:
            return None

        try:
            client = await self._get_client()
            return await client.get(key)
        except Exception as e:
            logger.warning(f"Cache GET failed for key={key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 300):
        """Set value in cache with TTL (seconds)"""
        if not self.enabled:
            return

        try:
            client = await self._get_client()
            await client.setex(key, ttl, value)
        except Exception as e:
            logger.warning(f"Cache SET failed for key={key}: {e}")

    async def delete(self, key: str):
        """Delete key from cache"""
        if not self.enabled:
            return

        try:
            client = await self._get_client()
            await client.delete(key)
        except Exception as e:
            logger.warning(f"Cache DELETE failed for key={key}: {e}")

    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from cache"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in cache for key={key}")
                return None
        return None

    async def set_json(self, key: str, value: dict, ttl: int = 300):
        """Set JSON value in cache"""
        await self.set(key, json.dumps(value), ttl=ttl)

    async def get_search_results(self, query_hash: str) -> Optional[dict]:
        """Get cached search results"""
        return await self.get_json(f"search:{query_hash}")

    async def set_search_results(self, query_hash: str, results: dict, ttl: int = 300):
        """Cache search results"""
        await self.set_json(f"search:{query_hash}", results, ttl=ttl)

    async def get_profile(self, profile_id: str) -> Optional[dict]:
        """Get cached profile details"""
        return await self.get_json(f"profile:{profile_id}")

    async def set_profile(self, profile_id: str, profile: dict, ttl: int = 600):
        """Cache profile details"""
        await self.set_json(f"profile:{profile_id}", profile, ttl=ttl)

    async def invalidate_profile(self, profile_id: str):
        """Invalidate cached profile (e.g., after update)"""
        await self.delete(f"profile:{profile_id}")

    async def ping(self) -> bool:
        """Check Redis connectivity"""
        if not self.enabled:
            return False

        try:
            client = await self._get_client()
            return await client.ping()
        except Exception as e:
            logger.error(f"Redis PING failed: {e}")
            return False

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")


# Global cache instance
cache = RedisCache()
