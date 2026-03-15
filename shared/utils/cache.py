"""
Redis cache utility wrapper for PARWA.
Provides simple async set/get/delete operations.
"""
import json
from typing import Any, Optional
import redis.asyncio as redis
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

class Cache:
    """
    Async Redis cache client.
    Handles connection pooling and JSON serialization.
    """
    def __init__(self):
        self.settings = get_settings()
        self._redis: Optional[redis.Redis] = None

    async def _get_conn(self) -> redis.Redis:
        """Initialize or return the Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                str(self.settings.redis_url),
                decode_responses=True,
                encoding="utf-8"
            )
        return self._redis

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set a value in cache with an expiration time (seconds)."""
        try:
            conn = await self._get_conn()
            serialized = json.dumps(value)
            await conn.set(key, serialized, ex=expire)
            return True
        except Exception as e:
            logger.error("cache_set_failed", extra={"context": {"key": key, "error": str(e)}})
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize a value from cache."""
        try:
            conn = await self._get_conn()
            value = await conn.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("cache_get_failed", extra={"context": {"key": key, "error": str(e)}})
            return None

    async def delete(self, key: str) -> bool:
        """Remove a key from cache."""
        try:
            conn = await self._get_conn()
            await conn.delete(key)
            return True
        except Exception as e:
            logger.error("cache_delete_failed", extra={"context": {"key": key, "error": str(e)}})
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        try:
            conn = await self._get_conn()
            return await conn.exists(key) > 0
        except Exception as e:
            logger.error("cache_exists_failed", extra={"context": {"key": key, "error": str(e)}})
            return False

    async def close(self):
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
