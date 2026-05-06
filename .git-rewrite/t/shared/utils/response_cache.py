"""
Response Cache for PARWA Performance Optimization.

Week 26 - Builder 3: Redis Cache Deep Optimization
Target: Response cache hit >80%, TTL management, stale-while-revalidate

Features:
- Cache API responses by endpoint + params
- TTL: 60 seconds for dynamic, 300 for static
- Cache keys with client_id for isolation
- Stale-while-revalidate pattern
- Bypass for non-GET requests
"""

import hashlib
import json
import time
import logging
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached response entry."""
    key: str
    value: Any
    created_at: float
    ttl: float
    expires_at: float
    etag: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    hit_count: int = 0


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    total_requests: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests


class ResponseCache:
    """
    API Response cache with Redis backend.

    Features:
    - Endpoint-based caching with TTL
    - Client isolation via cache keys
    - Stale-while-revalidate pattern
    - ETag support for conditional requests
    """

    # Default TTL settings (in seconds)
    DEFAULT_DYNAMIC_TTL = 60  # 1 minute for dynamic data
    DEFAULT_STATIC_TTL = 300  # 5 minutes for static data

    # Endpoints that should not be cached
    BYPASS_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    # Endpoints with custom TTLs
    ENDPOINT_TTLS: Dict[str, float] = {
        "/api/v1/dashboard": 30,  # Dashboard: 30 seconds
        "/api/v1/tickets": 60,  # Tickets list: 1 minute
        "/api/v1/approvals": 30,  # Approvals: 30 seconds
        "/api/v1/analytics": 300,  # Analytics: 5 minutes
        "/api/v1/settings": 300,  # Settings: 5 minutes
        "/api/v1/faq": 3600,  # FAQ: 1 hour
        "/api/v1/kb": 3600,  # Knowledge base: 1 hour
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        default_ttl: float = 60,
        max_stale_age: float = 300
    ):
        """
        Initialize response cache.

        Args:
            redis_client: Redis client instance.
            default_ttl: Default TTL in seconds.
            max_stale_age: Maximum age for stale data.
        """
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.max_stale_age = max_stale_age
        self._local_cache: Dict[str, CacheEntry] = {}
        self._stats = CacheStats()

    def _generate_cache_key(
        self,
        endpoint: str,
        client_id: str,
        params: Optional[Dict] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Generate a unique cache key.

        Args:
            endpoint: API endpoint path.
            client_id: Client/tenant ID for isolation.
            params: Request parameters.
            user_id: Optional user ID for user-specific caching.

        Returns:
            Cache key string.
        """
        # Build key components
        key_parts = [
            "parwa",
            "cache",
            "response",
            f"client:{client_id}",
            f"endpoint:{endpoint}",
        ]

        # Add params hash if present
        if params:
            params_hash = hashlib.md5(
                json.dumps(params, sort_keys=True).encode()
            ).hexdigest()[:8]
            key_parts.append(f"params:{params_hash}")

        # Add user ID for user-specific data
        if user_id:
            key_parts.append(f"user:{user_id}")

        return ":".join(key_parts)

    def _generate_etag(self, data: Any) -> str:
        """
        Generate ETag for cached data.

        Args:
            data: Data to generate ETag for.

        Returns:
            ETag string.
        """
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    def get_ttl_for_endpoint(self, endpoint: str) -> float:
        """
        Get TTL for a specific endpoint.

        Args:
            endpoint: API endpoint path.

        Returns:
            TTL in seconds.
        """
        # Check for exact match
        if endpoint in self.ENDPOINT_TTLS:
            return self.ENDPOINT_TTLS[endpoint]

        # Check for prefix match
        for path, ttl in self.ENDPOINT_TTLS.items():
            if endpoint.startswith(path):
                return ttl

        return self.default_ttl

    async def get(
        self,
        endpoint: str,
        client_id: str,
        params: Optional[Dict] = None,
        user_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get cached response.

        Args:
            endpoint: API endpoint path.
            client_id: Client/tenant ID.
            params: Request parameters.
            user_id: Optional user ID.

        Returns:
            Cached response dict or None.
        """
        self._stats.total_requests += 1
        key = self._generate_cache_key(endpoint, client_id, params, user_id)

        # Check local cache first (L1)
        if key in self._local_cache:
            entry = self._local_cache[key]
            current_time = time.time()

            # Check if entry is fresh or stale-but-usable
            if current_time < entry.expires_at:
                entry.hit_count += 1
                self._stats.hits += 1
                return {"data": entry.value, "etag": entry.etag, "fresh": True}

            # Stale-while-revalidate: return stale data if within max_stale_age
            if current_time - entry.expires_at < self.max_stale_age:
                entry.hit_count += 1
                self._stats.hits += 1
                return {"data": entry.value, "etag": entry.etag, "fresh": False}

        # Check Redis (L2)
        if self.redis_client:
            try:
                cached = await self._redis_get(key)
                if cached:
                    entry = CacheEntry(
                        key=key,
                        value=cached["data"],
                        created_at=cached["created_at"],
                        ttl=cached["ttl"],
                        expires_at=cached["created_at"] + cached["ttl"],
                        etag=cached.get("etag"),
                    )
                    self._local_cache[key] = entry
                    self._stats.hits += 1
                    return {"data": entry.value, "etag": entry.etag, "fresh": True}
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        self._stats.misses += 1
        return None

    async def set(
        self,
        endpoint: str,
        client_id: str,
        data: Any,
        params: Optional[Dict] = None,
        user_id: Optional[str] = None,
        ttl: Optional[float] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Cache a response.

        Args:
            endpoint: API endpoint path.
            client_id: Client/tenant ID.
            data: Response data to cache.
            params: Request parameters.
            user_id: Optional user ID.
            ttl: Optional custom TTL.
            tags: Optional tags for group invalidation.

        Returns:
            ETag for the cached response.
        """
        key = self._generate_cache_key(endpoint, client_id, params, user_id)
        if ttl is None:
            ttl = self.get_ttl_for_endpoint(endpoint)

        current_time = time.time()
        etag = self._generate_etag(data)

        entry = CacheEntry(
            key=key,
            value=data,
            created_at=current_time,
            ttl=ttl,
            expires_at=current_time + ttl,
            etag=etag,
            tags=tags or [],
        )

        # Store in local cache (L1)
        self._local_cache[key] = entry

        # Store in Redis (L2)
        if self.redis_client:
            try:
                await self._redis_set(key, {
                    "data": data,
                    "created_at": current_time,
                    "ttl": ttl,
                    "etag": etag,
                    "tags": tags or [],
                }, ttl)
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

        self._stats.sets += 1
        return etag

    async def delete(
        self,
        endpoint: str,
        client_id: str,
        params: Optional[Dict] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Delete a cached response.

        Args:
            endpoint: API endpoint path.
            client_id: Client/tenant ID.
            params: Request parameters.
            user_id: Optional user ID.

        Returns:
            True if deleted, False otherwise.
        """
        key = self._generate_cache_key(endpoint, client_id, params, user_id)

        # Remove from local cache
        if key in self._local_cache:
            del self._local_cache[key]

        # Remove from Redis
        if self.redis_client:
            try:
                await self._redis_delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")

        self._stats.deletes += 1
        return True

    async def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate all cache entries with a specific tag.

        Args:
            tag: Tag to invalidate.

        Returns:
            Number of entries invalidated.
        """
        count = 0

        # Check local cache
        keys_to_delete = []
        for key, entry in self._local_cache.items():
            if tag in entry.tags:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._local_cache[key]
            count += 1

        # Check Redis (would need to track tags separately in production)
        # This is a simplified version

        self._stats.evictions += count
        return count

    async def invalidate_client(self, client_id: str) -> int:
        """
        Invalidate all cache entries for a client.

        Args:
            client_id: Client/tenant ID.

        Returns:
            Number of entries invalidated.
        """
        count = 0
        prefix = f"parwa:cache:response:client:{client_id}:"

        # Check local cache
        keys_to_delete = [
            key for key in self._local_cache
            if key.startswith(prefix)
        ]

        for key in keys_to_delete:
            del self._local_cache[key]
            count += 1

        # Check Redis
        if self.redis_client:
            try:
                count += await self._redis_delete_pattern(f"{prefix}*")
            except Exception as e:
                logger.warning(f"Redis pattern delete failed: {e}")

        self._stats.evictions += count
        return count

    def should_cache(self, method: str, endpoint: str, status_code: int) -> bool:
        """
        Determine if a response should be cached.

        Args:
            method: HTTP method.
            endpoint: API endpoint path.
            status_code: HTTP status code.

        Returns:
            True if response should be cached.
        """
        # Only cache GET requests
        if method.upper() in self.BYPASS_METHODS:
            return False

        # Only cache successful responses
        if status_code != 200:
            return False

        # Skip certain endpoints
        skip_endpoints = ["/api/v1/health", "/api/v1/metrics", "/api/v1/auth"]
        for skip in skip_endpoints:
            if endpoint.startswith(skip):
                return False

        return True

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    def clear_local_cache(self) -> None:
        """Clear local cache."""
        self._local_cache.clear()

    # Redis helper methods (to be implemented with actual Redis client)
    async def _redis_get(self, key: str) -> Optional[Dict]:
        """Get from Redis."""
        if self.redis_client:
            # Placeholder - implement with actual Redis client
            return None
        return None

    async def _redis_set(self, key: str, value: Dict, ttl: float) -> None:
        """Set in Redis with TTL."""
        if self.redis_client:
            # Placeholder - implement with actual Redis client
            pass

    async def _redis_delete(self, key: str) -> None:
        """Delete from Redis."""
        if self.redis_client:
            # Placeholder - implement with actual Redis client
            pass

    async def _redis_delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern from Redis."""
        if self.redis_client:
            # Placeholder - implement with actual Redis client
            return 0
        return 0


def cached_response(
    endpoint: str,
    ttl: Optional[float] = None,
    user_specific: bool = False
) -> Callable:
    """
    Decorator for caching API responses.

    Args:
        endpoint: API endpoint path.
        ttl: Optional custom TTL.
        user_specific: Whether cache should be user-specific.

    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract client_id from args or kwargs
            client_id = kwargs.get("client_id", "default")
            user_id = kwargs.get("user_id") if user_specific else None
            params = kwargs.get("params")

            # Try to get from cache
            cache = get_response_cache()
            cached = await cache.get(endpoint, client_id, params, user_id)

            if cached and cached.get("fresh"):
                return cached["data"]

            # Execute function
            result = await func(*args, **kwargs)

            # Cache the result
            if isinstance(result, dict) and result.get("status_code", 200) == 200:
                await cache.set(
                    endpoint, client_id, result, params, user_id, ttl
                )

            return result

        return wrapper
    return decorator


# Global cache instance
_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get the global response cache instance."""
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache


__all__ = [
    "CacheEntry",
    "CacheStats",
    "ResponseCache",
    "cached_response",
    "get_response_cache",
]
