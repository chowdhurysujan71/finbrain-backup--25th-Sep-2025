# utils/ttl_store.py
"""
Lightweight TTL store with Redis preference and safe in-memory fallback
Handles rate limiting, daily caps, and anti-repeat functionality
"""

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class InProcTTL:
    """Thread-safe in-memory TTL store for fallback when Redis unavailable"""
    
    def __init__(self):
        self._d = {}
        self._lock = threading.Lock()

    def _purge(self):
        """Remove expired entries"""
        now = time.time()
        drop = [k for k, (_, exp) in self._d.items() if exp and exp < now]
        for k in drop:
            self._d.pop(k, None)

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        """Increment key by 1, optionally setting TTL"""
        with self._lock:
            self._purge()
            val, exp = self._d.get(key, (0, 0))
            val += 1
            if ttl_seconds:
                exp = time.time() + ttl_seconds
            self._d[key] = (val, exp)
            return val

    def get(self, key: str) -> int | None:
        """Get value for key"""
        with self._lock:
            self._purge()
            itm = self._d.get(key)
            return itm[0] if itm else None

    def setex(self, key: str, ttl_seconds: int, value: int = 1) -> None:
        """Set key to value with TTL"""
        with self._lock:
            self._purge()
            self._d[key] = (value, time.time() + ttl_seconds)

    def exists(self, key: str) -> bool:
        """Check if key exists and not expired"""
        with self._lock:
            self._purge()
            return key in self._d


class RedisTTL:
    """Redis-backed TTL store"""
    
    def __init__(self, client):
        self.client = client

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        """Increment key by 1, optionally setting TTL"""
        p = self.client.pipeline()
        p.incr(key)
        if ttl_seconds and (self.client.ttl(key) is None or self.client.ttl(key) < 0):
            p.expire(key, ttl_seconds)
        return p.execute()[0]

    def get(self, key: str) -> int | None:
        """Get value for key"""
        v = self.client.get(key)
        return int(v) if v else None

    def setex(self, key: str, ttl_seconds: int, value: int = 1) -> None:
        """Set key to value with TTL"""
        self.client.setex(key, ttl_seconds, value)

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        return bool(self.client.exists(key))


def get_store():
    """
    Get TTL store instance - prefers Redis if available, falls back to in-memory
    Safe Redis import with graceful fallback
    """
    url = os.getenv("REDIS_URL")
    if not url:
        logger.info("TTL Store: Using in-memory fallback (no REDIS_URL)")
        return InProcTTL()
    
    try:
        import redis
        client = redis.Redis.from_url(url)
        # Test connection
        client.ping()
        logger.info("TTL Store: Using Redis backend")
        return RedisTTL(client)
    except ImportError:
        logger.warning("TTL Store: Redis package not available, using in-memory fallback")
        return InProcTTL()
    except Exception as e:
        logger.warning(f"TTL Store: Redis connection failed ({e}), using in-memory fallback")
        return InProcTTL()