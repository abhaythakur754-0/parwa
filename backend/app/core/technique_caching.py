"""
Technique Result Caching Layer (Week 10 Day 3)

TTL-based cache with LRU eviction for technique execution results:
- TTL-based cache with configurable expiry per technique
- LRU eviction with configurable max_size
- Cache key: hash of (technique_id, query_hash, signals_hash, company_id)
- Per-company cache isolation
- Cache hit/miss statistics
- Cache warming/preloading support
- Cache invalidation by company, technique, or pattern
- Cache size monitoring
- Thread-safe with threading.Lock
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.technique_router import (
    TechniqueID,
    TECHNIQUE_REGISTRY,
)


# ── Default TTLs per technique tier (seconds) ────────────────────

DEFAULT_TTL_BY_TIER: Dict[str, int] = {
    "tier_1": 300,   # 5 minutes
    "tier_2": 600,   # 10 minutes
    "tier_3": 1200,  # 20 minutes
}

DEFAULT_TTL_SECONDS: int = 600  # 10 minutes
DEFAULT_MAX_SIZE: int = 1000


# ── Data Structures ────────────────────────────────────────────────


@dataclass
class CacheEntry:
    """Single cache entry with TTL and access tracking."""

    key: str
    technique_id: str
    company_id: str
    result: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl_seconds: float = DEFAULT_TTL_SECONDS
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        return (
            time.time() - self.created_at > self.ttl_seconds
        )

    @property
    def age_seconds(self) -> float:
        """Get the age of this entry in seconds."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update last accessed time and increment counter."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache hit/miss and size statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = DEFAULT_MAX_SIZE
    expired_cleanups: int = 0
    company_counts: Dict[str, int] = field(
        default_factory=dict,
    )
    technique_counts: Dict[str, int] = field(
        default_factory=dict,
    )

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def miss_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.misses / self.total_requests

    @property
    def utilization(self) -> float:
        if self.max_size == 0:
            return 0.0
        return self.size / self.max_size


# ── Technique Cache ────────────────────────────────────────────────


class TechniqueCache:
    """
    Thread-safe LRU cache with TTL for technique results.

    Cache keys are derived from (technique_id, query_hash,
    signals_hash, company_id). Supports per-company isolation,
    hit/miss statistics, cache warming, and invalidation.
    """

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        default_ttl: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._lock = threading.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl

        # OrderedDict for LRU ordering
        # Key: cache_key -> CacheEntry
        self._cache: OrderedDict[str, CacheEntry] = (
            OrderedDict()
        )

        # Stats
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        self._expired_cleanups: int = 0

        # Per-technique TTL overrides
        self._technique_ttls: Dict[str, int] = {}

    # ── Key Generation ────────────────────────────────────────────

    @staticmethod
    def make_cache_key(
        technique_id: str,
        query_hash: str,
        signals_hash: str,
        company_id: str,
    ) -> str:
        """
        Generate a deterministic cache key.

        Args:
            technique_id: Technique identifier
            query_hash: Hash of the query text
            signals_hash: Hash of query signals
            company_id: Tenant company identifier

        Returns:
            SHA-256 hex digest cache key
        """
        raw = (
            f"{technique_id}:{query_hash}:"
            f"{signals_hash}:{company_id}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── Get / Set ─────────────────────────────────────────────────

    def get(
        self,
        technique_id: str,
        query_hash: str,
        signals_hash: str,
        company_id: str,
    ) -> Optional[Any]:
        """
        Retrieve a cached result.

        Returns None on cache miss or expired entry.
        """
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value

        cache_key = self.make_cache_key(
            technique_id, query_hash, signals_hash, company_id,
        )

        with self._lock:
            entry = self._cache.get(cache_key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                # Remove expired entry
                del self._cache[cache_key]
                self._expired_cleanups += 1
                self._misses += 1
                return None

            # Cache hit — move to end for LRU
            self._cache.move_to_end(cache_key)
            entry.touch()
            self._hits += 1
            return entry.result

    def set(
        self,
        technique_id: str,
        query_hash: str,
        signals_hash: str,
        company_id: str,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Store a result in the cache.

        Args:
            technique_id: Technique identifier
            query_hash: Hash of the query text
            signals_hash: Hash of query signals
            company_id: Tenant company identifier
            result: The result to cache
            ttl_seconds: TTL override (None = auto-detect)

        Returns:
            True if stored successfully
        """
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value

        cache_key = self.make_cache_key(
            technique_id, query_hash, signals_hash, company_id,
        )

        ttl = self._resolve_ttl(technique_id, ttl_seconds)

        with self._lock:
            # If key already exists, remove it first
            if cache_key in self._cache:
                del self._cache[cache_key]

            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._evict_lru()

            entry = CacheEntry(
                key=cache_key,
                technique_id=technique_id,
                company_id=company_id,
                result=result,
                ttl_seconds=ttl,
            )
            self._cache[cache_key] = entry
            self._cache.move_to_end(cache_key)

            return True

    # ── Invalidation ──────────────────────────────────────────────

    def invalidate(
        self,
        technique_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            technique_id: If set, invalidate entries for this
                technique only
            company_id: If set, invalidate entries for this
                company only

        Returns:
            Number of entries invalidated
        """
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value

        with self._lock:
            if technique_id is None and company_id is None:
                count = len(self._cache)
                self._cache.clear()
                return count

            keys_to_remove: List[str] = []
            for key, entry in self._cache.items():
                if technique_id is not None:
                    if entry.technique_id != technique_id:
                        continue
                if company_id is not None:
                    if entry.company_id != company_id:
                        continue
                keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._cache[key]

            return len(keys_to_remove)

    def invalidate_pattern(
        self,
        company_id: str,
        technique_prefix: Optional[str] = None,
    ) -> int:
        """
        Invalidate by company with optional technique prefix
        matching.

        Args:
            company_id: Company to invalidate
            technique_prefix: If set, only invalidate techniques
                starting with this prefix

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_remove: List[str] = []
            for key, entry in self._cache.items():
                if entry.company_id != company_id:
                    continue
                if (
                    technique_prefix is not None
                    and not entry.technique_id.startswith(
                        technique_prefix,
                    )
                ):
                    continue
                keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._cache[key]

            return len(keys_to_remove)

    # ── Cache Warming ─────────────────────────────────────────────

    def warm(
        self,
        technique_id: str,
        company_id: str,
        entries: List[Dict[str, Any]],
    ) -> int:
        """
        Preload cache entries (cache warming).

        Args:
            technique_id: Technique identifier
            company_id: Company to warm for
            entries: List of dicts with keys:
                'query_hash', 'signals_hash', 'result',
                'ttl_seconds' (optional)

        Returns:
            Number of entries loaded
        """
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value

        loaded = 0
        for entry_data in entries:
            query_hash = entry_data.get("query_hash", "")
            signals_hash = entry_data.get("signals_hash", "")
            result = entry_data.get("result")
            ttl = entry_data.get("ttl_seconds")

            if result is None:
                continue

            success = self.set(
                technique_id=technique_id,
                query_hash=query_hash,
                signals_hash=signals_hash,
                company_id=company_id,
                result=result,
                ttl_seconds=ttl,
            )
            if success:
                loaded += 1

        return loaded

    # ── Stats ─────────────────────────────────────────────────────

    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        with self._lock:
            company_counts: Dict[str, int] = {}
            technique_counts: Dict[str, int] = {}

            for entry in self._cache.values():
                company_counts[entry.company_id] = (
                    company_counts.get(entry.company_id, 0) + 1
                )
                technique_counts[entry.technique_id] = (
                    technique_counts.get(
                        entry.technique_id, 0,
                    ) + 1
                )

            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                size=len(self._cache),
                max_size=self._max_size,
                expired_cleanups=self._expired_cleanups,
                company_counts=company_counts,
                technique_counts=technique_counts,
            )

    def reset_stats(self) -> None:
        """Reset hit/miss/eviction counters."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._expired_cleanups = 0

    # ── Maintenance ───────────────────────────────────────────────

    def cleanup(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            keys_to_remove: List[str] = []
            for key, entry in self._cache.items():
                if entry.is_expired:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._cache[key]
                self._expired_cleanups += 1

            return len(keys_to_remove)

    def resize(self, max_size: int) -> int:
        """
        Change max cache size, evicting if necessary.

        Args:
            max_size: New maximum cache size

        Returns:
            Number of entries evicted
        """
        if max_size < 1:
            max_size = 1

        with self._lock:
            self._max_size = max_size
            evicted = 0

            while len(self._cache) > self._max_size:
                self._evict_lru()
                evicted += 1

            return evicted

    def clear(self) -> None:
        """Clear all cache entries and reset stats."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._expired_cleanups = 0

    # ── TTL Configuration ─────────────────────────────────────────

    def set_technique_ttl(
        self, technique_id: str, ttl_seconds: int,
    ) -> None:
        """Set a custom TTL for a specific technique."""
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value
        with self._lock:
            self._technique_ttls[technique_id] = ttl_seconds

    def get_technique_ttl(
        self, technique_id: str,
    ) -> Optional[int]:
        """Get custom TTL for a technique, if set."""
        if isinstance(technique_id, TechniqueID):
            technique_id = technique_id.value
        with self._lock:
            return self._technique_ttls.get(technique_id)

    def _resolve_ttl(
        self,
        technique_id: str,
        override: Optional[int],
    ) -> int:
        """Resolve the effective TTL for a technique."""
        if override is not None:
            return override

        # Check per-technique override
        if technique_id in self._technique_ttls:
            return self._technique_ttls[technique_id]

        # Check technique tier
        info = TECHNIQUE_REGISTRY.get(TechniqueID(technique_id))
        if info is not None:
            tier_key = info.tier.value
            return DEFAULT_TTL_BY_TIER.get(
                tier_key, self._default_ttl,
            )

        return self._default_ttl

    # ── LRU Eviction ──────────────────────────────────────────────

    def _evict_lru(self) -> Optional[str]:
        """Evict the least recently used entry."""
        if not self._cache:
            return None

        # First item in OrderedDict is the LRU
        key, _ = self._cache.popitem(last=False)
        self._evictions += 1
        return key

    # ── Monitoring ────────────────────────────────────────────────

    def get_size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def get_max_size(self) -> int:
        """Get maximum cache size."""
        return self._max_size

    def get_entry_count_by_company(
        self, company_id: str,
    ) -> int:
        """Count cache entries for a company."""
        with self._lock:
            return sum(
                1
                for e in self._cache.values()
                if e.company_id == company_id
            )

    def get_oldest_entry_age(self) -> Optional[float]:
        """Get age of the oldest cache entry."""
        with self._lock:
            if not self._cache:
                return None
            oldest = min(
                self._cache.values(),
                key=lambda e: e.created_at,
            )
            return time.time() - oldest.created_at

    def get_newest_entry_age(self) -> Optional[float]:
        """Get age of the newest cache entry."""
        with self._lock:
            if not self._cache:
                return None
            newest = max(
                self._cache.values(),
                key=lambda e: e.created_at,
            )
            return time.time() - newest.created_at
