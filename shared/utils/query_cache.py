"""
Query Cache for PARWA Performance Optimization.

Week 26 - Builder 3: Redis Cache Deep Optimization
Target: Query cache hit >70%, automatic invalidation, cache warming

Features:
- Cache frequent query results
- TTL: 30 seconds for real-time data, 300 for reference data
- Automatic invalidation on writes
- Cache warming on startup
"""

import hashlib
import json
import time
import logging
from typing import Any, Optional, Dict, List, Set, Callable
from dataclasses import dataclass, field
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class QueryCacheEntry:
    """Cached query result entry."""
    query_hash: str
    result: Any
    table_dependencies: Set[str]
    created_at: float
    ttl: float
    hit_count: int = 0


@dataclass
class QueryCacheStats:
    """Query cache statistics."""
    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    total_queries: int = 0
    cache_warming_hits: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_queries == 0:
            return 0.0
        return self.hits / self.total_queries


class QueryCache:
    """
    Database query result cache.

    Features:
    - Query result caching with TTL
    - Table dependency tracking for invalidation
    - Cache warming for frequently used queries
    - Automatic invalidation on write operations
    """

    # TTL settings by query type
    TTL_REALTIME = 30  # 30 seconds for real-time data
    TTL_SHORT = 60  # 1 minute for frequently changing data
    TTL_MEDIUM = 300  # 5 minutes for moderately changing data
    TTL_REFERENCE = 3600  # 1 hour for reference data

    # Table-based TTL mapping
    TABLE_TTLS: Dict[str, float] = {
        "support_tickets": TTL_REALTIME,
        "sessions": TTL_REALTIME,
        "interactions": TTL_SHORT,
        "audit_logs": TTL_MEDIUM,
        "companies": TTL_MEDIUM,
        "users": TTL_MEDIUM,
        "customers": TTL_SHORT,
        "tenants": TTL_REFERENCE,
        "api_keys": TTL_MEDIUM,
        "human_corrections": TTL_MEDIUM,
        "financial_audit_trail": TTL_MEDIUM,
        "compliance_records": TTL_MEDIUM,
        "fraud_alerts": TTL_REALTIME,
        "complaint_tracking": TTL_SHORT,
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        default_ttl: float = 60,
        max_entries: int = 10000
    ):
        """
        Initialize query cache.

        Args:
            redis_client: Redis client instance.
            default_ttl: Default TTL in seconds.
            max_entries: Maximum local cache entries.
        """
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._cache: Dict[str, QueryCacheEntry] = {}
        self._table_index: Dict[str, Set[str]] = {}  # table -> query hashes
        self._stats = QueryCacheStats()
        self._warm_queries: List[str] = []

    def _hash_query(self, query: str, params: Optional[tuple] = None) -> str:
        """
        Generate a hash for a query and its parameters.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            Query hash string.
        """
        content = query
        if params:
            content += json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _extract_tables(self, query: str) -> Set[str]:
        """
        Extract table names from a query.

        Args:
            query: SQL query string.

        Returns:
            Set of table names.
        """
        tables = set()
        query_upper = query.upper()

        # Extract from FROM clause
        from_idx = query_upper.find("FROM")
        if from_idx != -1:
            from_part = query[from_idx + 4:].split("WHERE")[0]
            from_part = from_part.split("JOIN")[0]
            from_part = from_part.split("GROUP")[0]
            from_part = from_part.split("ORDER")[0]
            from_part = from_part.split("LIMIT")[0]

            # Extract table names
            words = from_part.replace(",", " ").split()
            for word in words:
                word = word.strip("(),")
                if word and not word.upper() in (
                    "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT",
                    "INNER", "OUTER", "ON", "AND", "OR", "AS", "THE"
                ):
                    tables.add(word.lower())

        # Extract from JOIN clauses
        join_keyword = "JOIN"
        join_idx = query_upper.find(join_keyword)
        while join_idx != -1:
            join_part = query[join_idx + 4:].strip()
            table_name = join_part.split()[0] if join_part.split() else ""
            if table_name:
                tables.add(table_name.lower().strip("(),"))
            join_idx = query_upper.find(join_keyword, join_idx + 1)

        return tables

    def get_ttl_for_query(self, query: str, tables: Optional[Set[str]] = None) -> float:
        """
        Determine TTL based on query tables.

        Args:
            query: SQL query string.
            tables: Optional pre-extracted tables.

        Returns:
            TTL in seconds.
        """
        if tables is None:
            tables = self._extract_tables(query)

        # Use shortest TTL among all tables
        min_ttl = self.default_ttl
        for table in tables:
            if table in self.TABLE_TTLS:
                min_ttl = min(min_ttl, self.TABLE_TTLS[table])

        return min_ttl

    async def get(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> Optional[Any]:
        """
        Get cached query result.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            Cached result or None.
        """
        self._stats.total_queries += 1
        query_hash = self._hash_query(query, params)

        # Check local cache
        if query_hash in self._cache:
            entry = self._cache[query_hash]
            if time.time() - entry.created_at < entry.ttl:
                entry.hit_count += 1
                self._stats.hits += 1
                return entry.result
            else:
                # Expired, remove from cache
                del self._cache[query_hash]

        # Check Redis
        if self.redis_client:
            try:
                cached = await self._redis_get(f"query:{query_hash}")
                if cached:
                    result = cached["result"]
                    tables = set(cached.get("tables", []))
                    ttl = cached.get("ttl", self.default_ttl)

                    entry = QueryCacheEntry(
                        query_hash=query_hash,
                        result=result,
                        table_dependencies=tables,
                        created_at=time.time(),
                        ttl=ttl,
                    )
                    self._cache[query_hash] = entry
                    self._stats.hits += 1
                    return result
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")

        self._stats.misses += 1
        return None

    async def set(
        self,
        query: str,
        result: Any,
        params: Optional[tuple] = None,
        ttl: Optional[float] = None,
        tables: Optional[Set[str]] = None
    ) -> None:
        """
        Cache a query result.

        Args:
            query: SQL query string.
            result: Query result to cache.
            params: Query parameters.
            ttl: Optional custom TTL.
            tables: Optional pre-extracted tables.
        """
        query_hash = self._hash_query(query, params)

        if tables is None:
            tables = self._extract_tables(query)

        if ttl is None:
            ttl = self.get_ttl_for_query(query, tables)

        entry = QueryCacheEntry(
            query_hash=query_hash,
            result=result,
            table_dependencies=tables,
            created_at=time.time(),
            ttl=ttl,
        )

        # Store in local cache
        self._cache[query_hash] = entry

        # Update table index
        for table in tables:
            if table not in self._table_index:
                self._table_index[table] = set()
            self._table_index[table].add(query_hash)

        # Store in Redis
        if self.redis_client:
            try:
                await self._redis_set(
                    f"query:{query_hash}",
                    {
                        "result": result,
                        "tables": list(tables),
                        "ttl": ttl,
                    },
                    ttl
                )
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")

        # Evict old entries if needed
        await self._evict_if_needed()

    async def invalidate_table(self, table: str) -> int:
        """
        Invalidate all queries dependent on a table.

        Args:
            table: Table name.

        Returns:
            Number of entries invalidated.
        """
        count = 0
        table = table.lower()

        if table not in self._table_index:
            return 0

        query_hashes = list(self._table_index[table])

        for query_hash in query_hashes:
            if query_hash in self._cache:
                del self._cache[query_hash]
                count += 1

            if self.redis_client:
                try:
                    await self._redis_delete(f"query:{query_hash}")
                except Exception as e:
                    logger.warning(f"Redis delete failed: {e}")

        # Clear table index
        del self._table_index[table]
        self._stats.invalidations += count

        return count

    async def invalidate_on_write(self, query: str) -> int:
        """
        Invalidate cache entries after a write operation.

        Args:
            query: Write query (INSERT, UPDATE, DELETE).

        Returns:
            Number of entries invalidated.
        """
        tables = self._extract_tables(query)
        total_invalidated = 0

        for table in tables:
            total_invalidated += await self.invalidate_table(table)

        return total_invalidated

    def register_warm_query(self, query: str, params: Optional[tuple] = None) -> None:
        """
        Register a query for cache warming.

        Args:
            query: SQL query string.
            params: Query parameters.
        """
        self._warm_queries.append((query, params))

    async def warm_cache(
        self,
        db_execute: Callable[[str, Optional[tuple]], Any]
    ) -> int:
        """
        Warm the cache with pre-registered queries.

        Args:
            db_execute: Database execute function.

        Returns:
            Number of queries warmed.
        """
        count = 0

        for query, params in self._warm_queries:
            try:
                result = await db_execute(query, params)
                await self.set(query, result, params)
                count += 1
            except Exception as e:
                logger.warning(f"Cache warming failed for query: {e}")

        self._stats.cache_warming_hits = count
        return count

    async def _evict_if_needed(self) -> None:
        """Evict old entries if cache is full."""
        if len(self._cache) <= self.max_entries:
            return

        # Sort by hit count and creation time
        entries = sorted(
            self._cache.items(),
            key=lambda x: (x[1].hit_count, x[1].created_at)
        )

        # Remove low-hit, old entries
        to_evict = len(self._cache) - self.max_entries + 100
        for query_hash, _ in entries[:to_evict]:
            entry = self._cache.get(query_hash)
            if entry:
                # Update table index
                for table in entry.table_dependencies:
                    if table in self._table_index:
                        self._table_index[table].discard(query_hash)
            del self._cache[query_hash]

    def get_stats(self) -> QueryCacheStats:
        """Get cache statistics."""
        return self._stats

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._table_index.clear()

    # Redis helper methods
    async def _redis_get(self, key: str) -> Optional[Dict]:
        """Get from Redis."""
        if self.redis_client:
            # Placeholder
            return None
        return None

    async def _redis_set(self, key: str, value: Dict, ttl: float) -> None:
        """Set in Redis with TTL."""
        if self.redis_client:
            # Placeholder
            pass

    async def _redis_delete(self, key: str) -> None:
        """Delete from Redis."""
        if self.redis_client:
            # Placeholder
            pass


def cached_query(ttl: Optional[float] = None) -> Callable:
    """
    Decorator for caching query results.

    Args:
        ttl: Optional custom TTL.

    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract query from args
            query = args[1] if len(args) > 1 else kwargs.get("query")
            params = args[2] if len(args) > 2 else kwargs.get("params")

            if not query:
                return await func(*args, **kwargs)

            cache = get_query_cache()

            # Try cache first
            cached = await cache.get(query, params)
            if cached is not None:
                return cached

            # Execute query
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(query, result, params, ttl)

            return result

        return wrapper
    return decorator


# Global cache instance
_cache: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    """Get the global query cache instance."""
    global _cache
    if _cache is None:
        _cache = QueryCache()
    return _cache


__all__ = [
    "QueryCacheEntry",
    "QueryCacheStats",
    "QueryCache",
    "cached_query",
    "get_query_cache",
]
