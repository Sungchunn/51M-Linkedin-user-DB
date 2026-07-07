"""
Lightweight token-bucket rate limiter with Redis fallback.

Environment:
- RATE_REDIS_HOST, RATE_REDIS_PORT, RATE_REDIS_DB, RATE_REDIS_PASSWORD (optional)
Defaults to in-memory per-process store if Redis unavailable.
"""

from __future__ import annotations

import os
import time
from typing import Optional

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore


class RateLimiter:
    def __init__(self) -> None:
        self._mem = {}
        self._r = None
        if redis is not None and os.getenv("RATE_REDIS_HOST"):
            try:
                self._r = redis.Redis(
                    host=os.getenv("RATE_REDIS_HOST"),
                    port=int(os.getenv("RATE_REDIS_PORT", "6379")),
                    db=int(os.getenv("RATE_REDIS_DB", "0")),
                    password=os.getenv("RATE_REDIS_PASSWORD") or None,
                    decode_responses=True,
                )
                # Test
                self._r.ping()
            except Exception:
                self._r = None

    def allow(self, key: str, rate_per_minute: int, burst: int) -> bool:
        now = int(time.time())
        window = now // 60
        if self._r:
            # Redis scriptless simple counter with TTL
            k = f"rl:{key}:{window}"
            try:
                current = self._r.incr(k)
                if current == 1:
                    self._r.expire(k, 65)
                # Allow up to burst in a window, otherwise proportional to rate_per_minute
                limit = max(rate_per_minute, burst)
                return current <= limit
            except Exception:
                pass

        # In-memory fallback per-process
        bucket_key = (key, window)
        current = self._mem.get(bucket_key, 0) + 1
        self._mem[bucket_key] = current
        limit = max(rate_per_minute, burst)
        return current <= limit

limiter = RateLimiter()
