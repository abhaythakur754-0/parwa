# Cache Manager - Week 50 Builder 1
# Intelligent caching system

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import hashlib


class CachePolicy(Enum):
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"


@dataclass
class CacheEntry:
    key: str = ""
    value: Any = None
    ttl_seconds: int = 3600
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    hit_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CacheStats:
    total_entries: int = 0
    total_hits: int = 0
    total_misses: int = 0
    hit_rate: float = 0.0
    total_size_bytes: int = 0


class CacheManager:
    """Intelligent cache management"""

    def __init__(self, max_size: int = 10000, policy: CachePolicy = CachePolicy.LRU):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._policy = policy
        self._stats = CacheStats()
        self._metrics = {"evictions": 0, "expirations": 0}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        entry = self._cache.get(key)
        if not entry:
            self._stats.total_misses += 1
            return None

        # Check expiration
        if entry.expires_at and datetime.utcnow() > entry.expires_at:
            del self._cache[key]
            self._stats.total_misses += 1
            self._metrics["expirations"] += 1
            return None

        entry.hit_count += 1
        entry.last_accessed = datetime.utcnow()
        self._stats.total_hits += 1
        self._update_hit_rate()
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600
    ) -> None:
        """Set value in cache"""
        # Evict if at capacity
        while len(self._cache) >= self._max_size:
            self._evict()

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds)
        )
        self._cache[key] = entry
        self._stats.total_entries = len(self._cache)

    def delete(self, key: str) -> bool:
        """Delete from cache"""
        if key in self._cache:
            del self._cache[key]
            self._stats.total_entries = len(self._cache)
            return True
        return False

    def _evict(self) -> None:
        """Evict based on policy"""
        if not self._cache:
            return

        if self._policy == CachePolicy.LRU:
            key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        elif self._policy == CachePolicy.LFU:
            key = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)
        else:  # FIFO
            key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)

        del self._cache[key]
        self._metrics["evictions"] += 1
        self._stats.total_entries = len(self._cache)

    def _update_hit_rate(self) -> None:
        """Update hit rate"""
        total = self._stats.total_hits + self._stats.total_misses
        self._stats.hit_rate = (self._stats.total_hits / total * 100) if total > 0 else 0

    def clear(self) -> int:
        """Clear cache"""
        count = len(self._cache)
        self._cache.clear()
        self._stats.total_entries = 0
        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        now = datetime.utcnow()
        to_remove = [
            k for k, v in self._cache.items()
            if v.expires_at and v.expires_at < now
        ]
        for key in to_remove:
            del self._cache[key]
        self._metrics["expirations"] += len(to_remove)
        self._stats.total_entries = len(self._cache)
        return len(to_remove)

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        return self._stats

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        return {
            "entries": self._stats.total_entries,
            "hits": self._stats.total_hits,
            "misses": self._stats.total_misses,
            "hit_rate": round(self._stats.hit_rate, 2),
            "evictions": self._metrics["evictions"],
            "expirations": self._metrics["expirations"]
        }
