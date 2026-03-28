# Edge Cache - Week 51 Builder 2
# Edge caching strategies

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import hashlib


class EdgeLocation(Enum):
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    APAC = "apac"
    GLOBAL = "global"


class CacheStatus(Enum):
    HIT = "hit"
    MISS = "miss"
    STALE = "stale"
    BYPASSED = "bypassed"


@dataclass
class EdgeCacheEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = ""
    value: Any = None
    content_type: str = "application/json"
    size_bytes: int = 0
    location: EdgeLocation = EdgeLocation.GLOBAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    etag: str = ""
    hit_count: int = 0


@dataclass
class CachePolicy:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    default_ttl: int = 3600
    max_ttl: int = 86400
    stale_while_revalidate: int = 300
    stale_if_error: int = 600
    must_revalidate: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


class EdgeCache:
    """Edge caching with multiple locations"""

    def __init__(self):
        self._entries: Dict[str, EdgeCacheEntry] = {}
        self._policies: Dict[str, CachePolicy] = {}
        self._location_caches: Dict[EdgeLocation, List[str]] = {
            loc: [] for loc in EdgeLocation
        }
        self._metrics = {
            "total_entries": 0,
            "total_size_bytes": 0,
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "by_location": {}
        }

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
        location: EdgeLocation = EdgeLocation.GLOBAL,
        content_type: str = "application/json"
    ) -> EdgeCacheEntry:
        """Store a value in edge cache"""
        # Generate ETag
        etag = hashlib.md5(str(value).encode()).hexdigest()

        entry = EdgeCacheEntry(
            key=key,
            value=value,
            content_type=content_type,
            location=location,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
            etag=etag
        )

        # Calculate size
        entry.size_bytes = len(str(value).encode())

        self._entries[key] = entry
        self._location_caches[location].append(key)
        self._metrics["total_entries"] = len(self._entries)
        self._metrics["total_size_bytes"] += entry.size_bytes

        loc_key = location.value
        self._metrics["by_location"][loc_key] = \
            self._metrics["by_location"].get(loc_key, 0) + 1

        return entry

    def get(
        self,
        key: str,
        location: Optional[EdgeLocation] = None
    ) -> Optional[Any]:
        """Get a value from edge cache"""
        entry = self._entries.get(key)

        if not entry:
            self._metrics["misses"] += 1
            return None

        # Check if entry is expired
        if entry.expires_at and datetime.utcnow() > entry.expires_at:
            self._metrics["misses"] += 1
            return None

        # Check location if specified
        if location and entry.location != location and entry.location != EdgeLocation.GLOBAL:
            self._metrics["misses"] += 1
            return None

        entry.hit_count += 1
        self._metrics["hits"] += 1
        return entry.value

    def get_status(self, key: str) -> CacheStatus:
        """Get cache status for a key"""
        entry = self._entries.get(key)

        if not entry:
            return CacheStatus.MISS

        if entry.expires_at:
            if datetime.utcnow() > entry.expires_at:
                return CacheStatus.STALE

        return CacheStatus.HIT

    def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry"""
        entry = self._entries.get(key)
        if not entry:
            return False

        # Remove from location cache
        if key in self._location_caches[entry.location]:
            self._location_caches[entry.location].remove(key)

        self._metrics["total_size_bytes"] -= entry.size_bytes
        del self._entries[key]
        self._metrics["total_entries"] = len(self._entries)
        self._metrics["evictions"] += 1

        return True

    def invalidate_by_location(self, location: EdgeLocation) -> int:
        """Invalidate all entries in a location"""
        keys = self._location_caches[location].copy()
        count = 0

        for key in keys:
            if self.invalidate(key):
                count += 1

        return count

    def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate entries matching a pattern"""
        import fnmatch
        count = 0

        for key in list(self._entries.keys()):
            if fnmatch.fnmatch(key, pattern):
                if self.invalidate(key):
                    count += 1

        return count

    def create_policy(
        self,
        name: str,
        default_ttl: int = 3600,
        max_ttl: int = 86400
    ) -> CachePolicy:
        """Create a cache policy"""
        policy = CachePolicy(
            name=name,
            default_ttl=default_ttl,
            max_ttl=max_ttl
        )
        self._policies[policy.id] = policy
        return policy

    def get_policy(self, policy_id: str) -> Optional[CachePolicy]:
        """Get a cache policy"""
        return self._policies.get(policy_id)

    def get_entry(self, key: str) -> Optional[EdgeCacheEntry]:
        """Get cache entry details"""
        return self._entries.get(key)

    def get_entries_by_location(self, location: EdgeLocation) -> List[EdgeCacheEntry]:
        """Get all entries in a location"""
        keys = self._location_caches.get(location, [])
        return [self._entries[k] for k in keys if k in self._entries]

    def get_expired_entries(self) -> List[EdgeCacheEntry]:
        """Get all expired entries"""
        now = datetime.utcnow()
        return [
            e for e in self._entries.values()
            if e.expires_at and e.expires_at < now
        ]

    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        expired = self.get_expired_entries()
        count = 0

        for entry in expired:
            if self.invalidate(entry.key):
                count += 1

        return count

    def get_hit_rate(self) -> float:
        """Calculate hit rate"""
        total = self._metrics["hits"] + self._metrics["misses"]
        if total == 0:
            return 0.0
        return (self._metrics["hits"] / total) * 100

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        return {
            **self._metrics,
            "hit_rate": round(self.get_hit_rate(), 2)
        }

    def clear_all(self) -> int:
        """Clear all cache entries"""
        count = len(self._entries)
        self._entries.clear()
        for loc in self._location_caches:
            self._location_caches[loc].clear()
        self._metrics["total_entries"] = 0
        self._metrics["total_size_bytes"] = 0
        return count
