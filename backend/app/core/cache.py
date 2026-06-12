"""
PARWA Phase 3 — Smart Cache with Redis + In-Memory Fallback

Provides a unified caching interface that prefers Redis but transparently
falls back to an in-memory dict when Redis is unavailable.  TTL
presets implement the D12 data-freshness strategy.

BC-008 compliance: every operation is wrapped in try/except so the cache
never crashes the host application.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# D12 TTL strategy presets (seconds)
# ------------------------------------------------------------------
TTL_PRESETS: Dict[str, int] = {
    "real_time": 300,       # 5 minutes  — e.g. API rate-limit counters
    "semi_static": 900,     # 15 minutes — e.g. CRM contact lists
    "rarely_changing": 3600,  # 60 minutes — e.g. integration configs
}


class _InMemoryBucket:
    """Simple TTL-aware dict entry."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class SmartCache:
    """Dual-backend cache: Redis primary, in-memory fallback.

    Parameters
    ----------
    redis_url:
        Redis connection URL.  If the connection fails the cache
        silently degrades to in-memory storage.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._memory: Dict[str, _InMemoryBucket] = {}
        self._redis_available: bool = False
        self._company_key_prefix: str = "parwa:cache:company:"

        self._init_redis()

    # ------------------------------------------------------------------
    # Redis initialisation
    # ------------------------------------------------------------------

    def _init_redis(self) -> None:
        """Attempt to connect to Redis; degrade gracefully on failure."""
        try:
            import redis  # type: ignore[import-untyped]

            self._redis = redis.from_url(self._redis_url, socket_timeout=3)
            self._redis.ping()
            self._redis_available = True
            logger.info("Redis connected at %s", self._redis_url)
        except Exception as exc:
            self._redis_available = False
            self._redis = None
            logger.warning(
                "Redis unavailable (%s) — falling back to in-memory cache", exc
            )

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize(value: Any) -> str:
        """Convert *value* to a JSON string."""
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            logger.error("Serialization failed: %s", exc)
            raise

    @staticmethod
    def _deserialize(data: str) -> Any:
        """Parse a JSON string back to a Python object."""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Deserialization failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a cached value by *key*.

        Returns ``None`` if the key does not exist or has expired.
        """
        try:
            if self._redis_available:
                return self._get_redis(key)
            return self._get_memory(key)
        except Exception as exc:
            logger.error("Cache GET failed for key=%s: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store *value* under *key* with the given TTL."""
        try:
            if self._redis_available:
                self._set_redis(key, value, ttl_seconds)
            else:
                self._set_memory(key, value, ttl_seconds)
        except Exception as exc:
            logger.error("Cache SET failed for key=%s: %s", key, exc)
            # Fall back to memory if Redis write fails
            try:
                self._set_memory(key, value, ttl_seconds)
            except Exception as mem_exc:
                logger.error("In-memory SET also failed for key=%s: %s", key, mem_exc)

    def delete(self, key: str) -> None:
        """Remove *key* from the cache."""
        try:
            if self._redis_available:
                self._redis.delete(key)
            if key in self._memory:
                del self._memory[key]
        except Exception as exc:
            logger.error("Cache DELETE failed for key=%s: %s", key, exc)

    def invalidate_company(self, company_id: str) -> None:
        """Delete all cache entries belonging to *company_id*.

        Keys are expected to follow the pattern
        ``parwa:cache:company:{company_id}:*``.
        """
        try:
            pattern = f"{self._company_key_prefix}{company_id}:*"

            if self._redis_available:
                try:
                    cursor = 0
                    while True:
                        cursor, keys = self._redis.scan(
                            cursor=cursor, match=pattern, count=200
                        )
                        if keys:
                            self._redis.delete(*keys)
                        if cursor == 0:
                            break
                except Exception as exc:
                    logger.error(
                        "Redis SCAN/DELETE failed for company_id=%s: %s",
                        company_id,
                        exc,
                    )

            # Also purge in-memory entries
            prefix = f"{self._company_key_prefix}{company_id}:"
            expired_keys = [
                k for k in self._memory if k.startswith(prefix)
            ]
            for k in expired_keys:
                del self._memory[k]

            logger.info(
                "Invalidated %d cache entries for company_id=%s",
                len(expired_keys) if not self._redis_available else 0,
                company_id,
            )
        except Exception as exc:
            logger.error(
                "invalidate_company failed for company_id=%s: %s", company_id, exc
            )

    # ------------------------------------------------------------------
    # Redis backend
    # ------------------------------------------------------------------

    def _get_redis(self, key: str) -> Optional[Any]:
        """Fetch from Redis, falling back to memory on error."""
        try:
            data = self._redis.get(key)
            if data is None:
                return None
            return self._deserialize(data)
        except Exception as exc:
            logger.warning("Redis GET error for key=%s: %s — trying memory", key, exc)
            self._redis_available = False
            return self._get_memory(key)

    def _set_redis(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Write to Redis, also mirroring to memory."""
        try:
            serialized = self._serialize(value)
            self._redis.setex(key, ttl_seconds, serialized)
            # Mirror to memory as a warm standby
            self._set_memory(key, value, ttl_seconds)
        except Exception as exc:
            logger.warning(
                "Redis SET error for key=%s: %s — falling back to memory", key, exc
            )
            self._redis_available = False
            self._set_memory(key, value, ttl_seconds)

    # ------------------------------------------------------------------
    # In-memory backend
    # ------------------------------------------------------------------

    def _get_memory(self, key: str) -> Optional[Any]:
        """Fetch from the in-memory dict."""
        bucket = self._memory.get(key)
        if bucket is None:
            return None
        if bucket.is_expired():
            del self._memory[key]
            return None
        return bucket.value

    def _set_memory(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store in the in-memory dict with monotonic-clock expiry."""
        expires_at = time.monotonic() + ttl_seconds
        self._memory[key] = _InMemoryBucket(value=value, expires_at=expires_at)

        # Periodic cleanup — evict ~10% of expired entries each write
        if len(self._memory) > 1000:
            self._evict_expired()

    def _evict_expired(self) -> None:
        """Remove all expired entries from the in-memory dict."""
        now = time.monotonic()
        expired_keys = [
            k for k, v in self._memory.items() if v.expires_at <= now
        ]
        for k in expired_keys:
            del self._memory[k]
        if expired_keys:
            logger.debug("Evicted %d expired in-memory cache entries", len(expired_keys))
