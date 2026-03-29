"""
Response Cache System for AI Optimization.

This module provides a high-performance response caching system with LRU eviction
policy, TTL support, and comprehensive cache statistics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Generic, Hashable, List, Optional, TypeVar
from collections import OrderedDict
import threading
import hashlib
import json
import time


K = TypeVar('K', bound=Hashable)
V = TypeVar('V')


@dataclass
class CacheEntry(Generic[K, V]):
    """Represents a single cache entry with metadata."""
    
    key: K
    value: V
    ttl: Optional[float] = None  # Time-to-live in seconds
    timestamp: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl is None:
            return False
        expiry_time = self.timestamp + timedelta(seconds=self.ttl)
        return datetime.now() > expiry_time
    
    def touch(self) -> None:
        """Update access metadata when entry is accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize entry to dictionary."""
        return {
            'key': str(self.key),
            'value': self.value,
            'ttl': self.ttl,
            'timestamp': self.timestamp.isoformat(),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat(),
            'metadata': self.metadata,
        }


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_entries: int = 0
    total_size_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize stats to dictionary."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'expirations': self.expirations,
            'total_entries': self.total_entries,
            'total_size_bytes': self.total_size_bytes,
            'hit_rate': self.hit_rate,
            'miss_rate': self.miss_rate,
        }


class ResponseCache(Generic[K, V]):
    """
    A thread-safe response cache with LRU eviction policy.
    
    Features:
    - LRU (Least Recently Used) eviction
    - TTL (Time-To-Live) support for automatic expiration
    - Thread-safe operations
    - Cache statistics tracking
    - Bulk operations support
    - Key pattern matching for invalidation
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
        enable_stats: bool = True,
    ):
        """
        Initialize the response cache.
        
        Args:
            max_size: Maximum number of entries in the cache
            default_ttl: Default TTL in seconds (None = no expiration)
            enable_stats: Whether to track cache statistics
        """
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._enable_stats = enable_stats
        
        # Use OrderedDict for LRU implementation
        self._cache: OrderedDict[K, CacheEntry[K, V]] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
    
    def get(self, key: K) -> Optional[V]:
        """
        Retrieve a value from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            The cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._record_miss()
                return None
            
            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self._stats.expirations += 1
                self._stats.total_entries -= 1
                self._record_miss()
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            
            self._record_hit()
            return entry.value
    
    def set(
        self,
        key: K,
        value: V,
        ttl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store a value in the cache.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
            metadata: Optional metadata to store with the entry
        """
        with self._lock:
            # Check if key already exists
            if key in self._cache:
                # Update existing entry
                old_entry = self._cache[key]
                entry = CacheEntry(
                    key=key,
                    value=value,
                    ttl=ttl if ttl is not None else self._default_ttl,
                    timestamp=datetime.now(),
                    access_count=old_entry.access_count,
                    metadata=metadata or {},
                )
                self._cache[key] = entry
                self._cache.move_to_end(key)
            else:
                # Evict if at capacity
                while len(self._cache) >= self._max_size:
                    self._evict_lru()
                
                # Create new entry
                entry = CacheEntry(
                    key=key,
                    value=value,
                    ttl=ttl if ttl is not None else self._default_ttl,
                    timestamp=datetime.now(),
                    metadata=metadata or {},
                )
                self._cache[key] = entry
                self._stats.total_entries += 1
            
            # Update size estimate
            self._update_size_estimate()
    
    def invalidate(self, key: K) -> bool:
        """
        Remove a specific entry from the cache.
        
        Args:
            key: The cache key to invalidate
            
        Returns:
            True if the key was found and removed, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.total_entries -= 1
                self._update_size_estimate()
                return True
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: Pattern to match (supports * as wildcard)
            
        Returns:
            Number of entries invalidated
        """
        import fnmatch
        
        with self._lock:
            keys_to_remove = []
            for key in self._cache.keys():
                if fnmatch.fnmatch(str(key), pattern):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
            
            self._stats.total_entries -= len(keys_to_remove)
            self._update_size_estimate()
            return len(keys_to_remove)
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()
            self._stats.total_entries = 0
            self._stats.total_size_bytes = 0
    
    def get_or_set(
        self,
        key: K,
        factory: callable,
        ttl: Optional[float] = None,
    ) -> V:
        """
        Get a value from cache or compute and cache it.
        
        Args:
            key: The cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds
            
        Returns:
            The cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        value = factory()
        self.set(key, value, ttl)
        return value
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expirations=self._stats.expirations,
                total_entries=self._stats.total_entries,
                total_size_bytes=self._stats.total_size_bytes,
            )
    
    def get_entry(self, key: K) -> Optional[CacheEntry[K, V]]:
        """Get the full cache entry including metadata."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired():
                return None
            return entry
    
    def keys(self) -> List[K]:
        """Get all cache keys."""
        with self._lock:
            return list(self._cache.keys())
    
    def values(self) -> List[V]:
        """Get all cache values."""
        with self._lock:
            return [entry.value for entry in self._cache.values() if not entry.is_expired()]
    
    def items(self) -> List[tuple]:
        """Get all key-value pairs."""
        with self._lock:
            return [(key, entry.value) for key, entry in self._cache.items() if not entry.is_expired()]
    
    def __len__(self) -> int:
        """Get the number of entries in the cache."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: K) -> bool:
        """Check if a key exists in the cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                return False
            return True
    
    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._cache:
            # OrderedDict: first item is LRU
            self._cache.popitem(last=False)
            self._stats.evictions += 1
            self._stats.total_entries -= 1
    
    def _record_hit(self) -> None:
        """Record a cache hit."""
        if self._enable_stats:
            self._stats.hits += 1
    
    def _record_miss(self) -> None:
        """Record a cache miss."""
        if self._enable_stats:
            self._stats.misses += 1
    
    def _update_size_estimate(self) -> None:
        """Update the size estimate for cache entries."""
        try:
            total_size = 0
            for entry in self._cache.values():
                # Rough estimate of entry size
                entry_json = json.dumps(entry.to_dict(), default=str)
                total_size += len(entry_json.encode('utf-8'))
            self._stats.total_size_bytes = total_size
        except Exception:
            # If we can't estimate size, keep previous value
            pass
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            keys_to_remove = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
            
            self._stats.expirations += len(keys_to_remove)
            self._stats.total_entries -= len(keys_to_remove)
            self._update_size_estimate()
            return len(keys_to_remove)
    
    @staticmethod
    def generate_key(*args, **kwargs) -> str:
        """
        Generate a cache key from arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            A hash-based cache key
        """
        key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()
