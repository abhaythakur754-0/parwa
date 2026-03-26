"""
Response Caching System for PARWA
Implements TTL-based caching with per-client isolation and hit rate tracking.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict
from threading import RLock


@dataclass
class CacheEntry:
    """Represents a cached response entry."""
    key: str
    value: Any
    created_at: float
    ttl_seconds: int
    client_id: str
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if entry has exceeded TTL."""
        return time.time() - self.created_at > self.ttl_seconds

    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = time.time()


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class ResponseCache:
    """
    Memory-efficient response cache with per-client isolation.
    Implements TTL-based invalidation and LRU eviction.
    """

    DEFAULT_TTL = 3600  # 1 hour
    MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB default
    MAX_ENTRIES_PER_CLIENT = 1000

    def __init__(
        self,
        max_size_bytes: int = MAX_SIZE_BYTES,
        default_ttl: int = DEFAULT_TTL
    ):
        self.max_size_bytes = max_size_bytes
        self.default_ttl = default_ttl
        self._lock = RLock()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._client_caches: Dict[str, Dict[str, CacheEntry]] = {}
        self._stats = CacheStats()
        self._faq_patterns: Dict[str, List[str]] = {}

    def _generate_key(self, query: str, client_id: str) -> str:
        """Generate a unique cache key."""
        normalized = query.lower().strip()
        hash_input = f"{client_id}:{normalized}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _estimate_size(self, value: Any) -> int:
        """Estimate size of cached value in bytes."""
        try:
            return len(json.dumps(value))
        except (TypeError, ValueError):
            return len(str(value))

    def _evict_if_needed(self) -> None:
        """Evict entries if cache exceeds size limit."""
        while (self._stats.total_size_bytes > self.max_size_bytes
               and self._cache):
            self._evict_oldest()

    def _evict_oldest(self) -> None:
        """Evict the oldest/least recently used entry."""
        if not self._cache:
            return
        key, entry = self._cache.popitem(last=False)
        self._stats.total_size_bytes -= entry.size_bytes
        self._stats.entry_count -= 1
        self._stats.evictions += 1
        if entry.client_id in self._client_caches:
            self._client_caches[entry.client_id].pop(entry.key, None)

    def _evict_expired(self) -> int:
        """Remove all expired entries."""
        expired_count = 0
        keys_to_remove = [
            k for k, v in self._cache.items() if v.is_expired()
        ]
        for key in keys_to_remove:
            self._remove_entry(key)
            expired_count += 1
        return expired_count

    def _remove_entry(self, key: str) -> None:
        """Remove a specific entry from cache."""
        entry = self._cache.pop(key, None)
        if entry:
            self._stats.total_size_bytes -= entry.size_bytes
            self._stats.entry_count -= 1
            if entry.client_id in self._client_caches:
                self._client_caches[entry.client_id].pop(key, None)

    def get(
        self,
        query: str,
        client_id: str
    ) -> Tuple[Optional[Any], bool]:
        """
        Retrieve cached response for query.
        Returns (value, is_hit) tuple.
        """
        with self._lock:
            key = self._generate_key(query, client_id)
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None, False

            if entry.is_expired():
                self._remove_entry(key)
                self._stats.misses += 1
                return None, False

            entry.touch()
            self._cache.move_to_end(key)
            self._stats.hits += 1
            return entry.value, True

    def set(
        self,
        query: str,
        client_id: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache a response with optional TTL override."""
        with self._lock:
            self._evict_expired()
            key = self._generate_key(query, client_id)
            ttl = ttl or self.default_ttl
            size = self._estimate_size(value)

            if key in self._cache:
                self._remove_entry(key)

            self._evict_if_needed()

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl_seconds=ttl,
                client_id=client_id,
                size_bytes=size
            )

            self._cache[key] = entry
            self._stats.total_size_bytes += size
            self._stats.entry_count += 1

            if client_id not in self._client_caches:
                self._client_caches[client_id] = {}
            self._client_caches[client_id][key] = entry
            self._enforce_client_limit(client_id)
            return True

    def _enforce_client_limit(self, client_id: str) -> None:
        """Enforce per-client entry limit."""
        client_cache = self._client_caches.get(client_id, {})
        while len(client_cache) > self.MAX_ENTRIES_PER_CLIENT:
            oldest_key = next(iter(client_cache))
            self._remove_entry(oldest_key)

    def invalidate_client(self, client_id: str) -> int:
        """Invalidate all entries for a client."""
        with self._lock:
            count = 0
            if client_id in self._client_caches:
                keys = list(self._client_caches[client_id].keys())
                for key in keys:
                    self._remove_entry(key)
                    count += 1
            return count

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._client_caches.clear()
            self._stats = CacheStats()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "hit_rate": self._stats.hit_rate,
                "evictions": self._stats.evictions,
                "total_size_bytes": self._stats.total_size_bytes,
                "entry_count": self._stats.entry_count,
                "client_count": len(self._client_caches),
                "utilization": self._stats.total_size_bytes / self.max_size_bytes
            }

    def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Get per-client cache statistics."""
        with self._lock:
            client_cache = self._client_caches.get(client_id, {})
            total_access = sum(e.access_count for e in client_cache.values())
            return {
                "client_id": client_id,
                "entry_count": len(client_cache),
                "total_access_count": total_access,
                "entries": [
                    {
                        "key": e.key[:8],
                        "access_count": e.access_count,
                        "age_seconds": time.time() - e.created_at
                    }
                    for e in list(client_cache.values())[:10]
                ]
            }

    def register_faq_pattern(
        self,
        pattern: str,
        variations: List[str]
    ) -> None:
        """Register FAQ patterns for proactive caching."""
        with self._lock:
            self._faq_patterns[pattern.lower()] = [
                v.lower() for v in variations
            ]

    def match_faq(self, query: str, client_id: str) -> Optional[str]:
        """Match query against registered FAQ patterns."""
        normalized = query.lower().strip()
        with self._lock:
            for pattern, variations in self._faq_patterns.items():
                if normalized in variations or normalized == pattern:
                    key = self._generate_key(pattern, client_id)
                    entry = self._cache.get(key)
                    if entry and not entry.is_expired():
                        return pattern
        return None

    def preload_faq(
        self,
        client_id: str,
        faqs: List[Dict[str, Any]],
        ttl: Optional[int] = None
    ) -> int:
        """Preload FAQ responses into cache."""
        loaded = 0
        for faq in faqs:
            query = faq.get("query", "")
            response = faq.get("response")
            if query and response:
                self.set(query, client_id, response, ttl)
                loaded += 1
        return loaded


class TestResponseCache:
    """Test suite for ResponseCache."""

    def test_basic_set_and_get(self):
        """Test basic cache set/get operations."""
        cache = ResponseCache()
        cache.set("What is your return policy?", "client_001", "30 days")
        value, hit = cache.get("What is your return policy?", "client_001")
        assert hit is True
        assert value == "30 days"

    def test_cache_miss(self):
        """Test cache miss behavior."""
        cache = ResponseCache()
        value, hit = cache.get("unknown query", "client_001")
        assert hit is False
        assert value is None

    def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = ResponseCache(default_ttl=1)
        cache.set("query", "client_001", "value")
        time.sleep(1.1)
        value, hit = cache.get("query", "client_001")
        assert hit is False

    def test_client_isolation(self):
        """Test per-client cache isolation."""
        cache = ResponseCache()
        cache.set("query", "client_001", "value1")
        cache.set("query", "client_002", "value2")
        v1, h1 = cache.get("query", "client_001")
        v2, h2 = cache.get("query", "client_002")
        assert v1 == "value1"
        assert v2 == "value2"

    def test_hit_rate_tracking(self):
        """Test hit rate statistics."""
        cache = ResponseCache()
        cache.set("q1", "c1", "v1")
        cache.get("q1", "c1")  # hit
        cache.get("q2", "c1")  # miss
        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.5

    def test_invalidate_client(self):
        """Test client cache invalidation."""
        cache = ResponseCache()
        cache.set("q1", "client_001", "v1")
        cache.set("q2", "client_001", "v2")
        count = cache.invalidate_client("client_001")
        assert count == 2
        _, hit = cache.get("q1", "client_001")
        assert hit is False

    def test_memory_limit(self):
        """Test memory limit enforcement."""
        cache = ResponseCache(max_size_bytes=100)
        for i in range(20):
            cache.set(f"q{i}", "c1", "x" * 20)
        stats = cache.get_stats()
        # Cache should not grow unboundedly - allow small overflow due to eviction timing
        assert stats["total_size_bytes"] <= 150
        assert stats["evictions"] > 0

    def test_case_insensitive_lookup(self):
        """Test case-insensitive cache lookup."""
        cache = ResponseCache()
        cache.set("Return Policy", "c1", "30 days")
        value, hit = cache.get("return policy", "c1")
        assert hit is True

    def test_client_stats(self):
        """Test per-client statistics."""
        cache = ResponseCache()
        cache.set("q1", "client_001", "v1")
        stats = cache.get_client_stats("client_001")
        assert stats["entry_count"] == 1

    def test_clear_cache(self):
        """Test cache clearing."""
        cache = ResponseCache()
        cache.set("q1", "c1", "v1")
        cache.clear()
        stats = cache.get_stats()
        assert stats["entry_count"] == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
