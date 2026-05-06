"""
Query Optimizer for PARWA Knowledge Base
Implements query caching, index optimization, and slow query logging.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import defaultdict
from threading import RLock
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Represents an optimized query execution plan."""
    query_hash: str
    original_query: str
    normalized_query: str
    estimated_cost: float
    indexes_used: List[str] = field(default_factory=list)
    cache_key: Optional[str] = None
    execution_time_ms: float = 0.0
    rows_scanned: int = 0
    optimizations_applied: List[str] = field(default_factory=list)


@dataclass
class SlowQueryLog:
    """Log entry for slow queries."""
    query: str
    execution_time_ms: float
    threshold_ms: float
    timestamp: float
    client_id: str
    suggestions: List[str] = field(default_factory=list)


class QueryCache:
    """In-memory cache for query results."""

    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 300):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = RLock()
        self._stats = {"hits": 0, "misses": 0}

    def _hash(self, query: str, params: Dict = None) -> str:
        """Generate cache key from query and params."""
        content = f"{query}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, query: str, params: Dict = None) -> Tuple[Optional[Any], bool]:
        """Get cached result if available and not expired."""
        with self._lock:
            key = self._hash(query, params)
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl_seconds:
                    self._stats["hits"] += 1
                    return value, True
                del self._cache[key]
            self._stats["misses"] += 1
            return None, False

    def set(self, query: str, value: Any, params: Dict = None) -> None:
        """Cache a query result."""
        with self._lock:
            if len(self._cache) >= self.max_entries:
                self._evict_oldest()
            key = self._hash(query, params)
            self._cache[key] = (value, time.time())

    def _evict_oldest(self) -> None:
        """Remove oldest cached entry."""
        if self._cache:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k][1]
            )
            del self._cache[oldest_key]

    def invalidate(self, pattern: str = None) -> int:
        """Invalidate cache entries matching pattern."""
        with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count
            keys_to_remove = [
                k for k in self._cache
                if pattern.lower() in k.lower()
            ]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._stats["hits"] + self._stats["misses"]
        return self._stats["hits"] / total if total > 0 else 0.0


class IndexOptimizer:
    """Manages query indexes for optimization."""

    def __init__(self):
        self._indexes: Dict[str, Dict[str, Any]] = {}
        self._index_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"hits": 0, "misses": 0}
        )

    def create_index(
        self,
        name: str,
        fields: List[str],
        index_type: str = "btree"
    ) -> bool:
        """Create a new index configuration."""
        self._indexes[name] = {
            "fields": fields,
            "type": index_type,
            "created_at": time.time(),
            "size_estimate": len(fields) * 100
        }
        return True

    def drop_index(self, name: str) -> bool:
        """Remove an index."""
        if name in self._indexes:
            del self._indexes[name]
            return True
        return False

    def recommend_indexes(
        self,
        query: str,
        slow_queries: List[SlowQueryLog]
    ) -> List[str]:
        """Recommend indexes based on query patterns."""
        recommendations = []
        query_lower = query.lower()

        if "where" in query_lower and "client_id" in query_lower:
            if "idx_client" not in self._indexes:
                recommendations.append(
                    "CREATE INDEX idx_client ON queries(client_id)"
                )

        if "join" in query_lower:
            if "idx_join" not in self._indexes:
                recommendations.append(
                    "CREATE INDEX idx_join ON queries(foreign_key)"
                )

        frequent_fields = self._analyze_frequent_fields(slow_queries)
        for field in frequent_fields[:3]:
            idx_name = f"idx_{field}"
            if idx_name not in self._indexes:
                recommendations.append(
                    f"CREATE INDEX {idx_name} ON queries({field})"
                )
        return recommendations

    def _analyze_frequent_fields(
        self,
        slow_queries: List[SlowQueryLog]
    ) -> List[str]:
        """Analyze slow queries for frequently accessed fields."""
        field_counts: Dict[str, int] = defaultdict(int)
        for sq in slow_queries:
            words = sq.query.lower().split()
            for word in words:
                if word.isidentifier():
                    field_counts[word] += 1
        return sorted(
            field_counts.keys(),
            key=lambda f: field_counts[f],
            reverse=True
        )

    def get_index_stats(self) -> Dict[str, Any]:
        """Get index usage statistics."""
        return {
            name: {
                **stats,
                "fields": self._indexes[name]["fields"]
            }
            for name, stats in self._index_stats.items()
            if name in self._indexes
        }


class QueryAnalyzer:
    """Analyzes and optimizes query execution."""

    SLOW_QUERY_THRESHOLD_MS = 200

    def __init__(self):
        self._slow_queries: List[SlowQueryLog] = []
        self._query_plans: Dict[str, QueryPlan] = {}
        self._lock = RLock()

    def analyze_query(self, query: str) -> QueryPlan:
        """Analyze query and generate execution plan."""
        normalized = self._normalize_query(query)
        query_hash = hashlib.md5(normalized.encode()).hexdigest()[:12]

        if query_hash in self._query_plans:
            return self._query_plans[query_hash]

        cost = self._estimate_cost(query)
        indexes = self._find_applicable_indexes(query)
        optimizations = self._suggest_optimizations(query, cost)

        plan = QueryPlan(
            query_hash=query_hash,
            original_query=query,
            normalized_query=normalized,
            estimated_cost=cost,
            indexes_used=indexes,
            optimizations_applied=optimizations
        )
        self._query_plans[query_hash] = plan
        return plan

    def _normalize_query(self, query: str) -> str:
        """Normalize query for comparison."""
        normalized = query.lower().strip()
        normalized = " ".join(normalized.split())
        return normalized

    def _estimate_cost(self, query: str) -> float:
        """Estimate query execution cost."""
        cost = 1.0
        query_lower = query.lower()

        complexity_factors = {
            "join": 2.0,
            "group by": 1.5,
            "order by": 1.3,
            "distinct": 1.2,
            "subquery": 2.5,
            "like": 1.4,
            "or": 1.3
        }

        for pattern, factor in complexity_factors.items():
            if pattern in query_lower:
                cost *= factor

        return cost

    def _find_applicable_indexes(self, query: str) -> List[str]:
        """Find indexes that could optimize this query."""
        indexes = []
        query_lower = query.lower()

        if "client_id" in query_lower:
            indexes.append("idx_client")
        if "created_at" in query_lower:
            indexes.append("idx_created")
        if "status" in query_lower:
            indexes.append("idx_status")

        return indexes

    def _suggest_optimizations(
        self,
        query: str,
        cost: float
    ) -> List[str]:
        """Suggest query optimizations."""
        suggestions = []
        query_lower = query.lower()

        if cost > 3.0:
            suggestions.append("Consider adding indexes")

        if "select *" in query_lower:
            suggestions.append("Avoid SELECT * - specify columns")

        if query_lower.count("join") > 2:
            suggestions.append("Reduce number of JOINs")

        if "like '%" in query_lower:
            suggestions.append("Leading wildcard prevents index usage")

        return suggestions

    def log_slow_query(
        self,
        query: str,
        execution_time_ms: float,
        client_id: str,
        threshold: float = None
    ) -> Optional[SlowQueryLog]:
        """Log a slow query for analysis."""
        threshold = threshold or self.SLOW_QUERY_THRESHOLD_MS

        if execution_time_ms <= threshold:
            return None

        plan = self.analyze_query(query)
        log_entry = SlowQueryLog(
            query=query,
            execution_time_ms=execution_time_ms,
            threshold_ms=threshold,
            timestamp=time.time(),
            client_id=client_id,
            suggestions=plan.optimizations_applied
        )

        with self._lock:
            self._slow_queries.append(log_entry)
            if len(self._slow_queries) > 1000:
                self._slow_queries = self._slow_queries[-500:]

        logger.warning(
            f"Slow query detected: {execution_time_ms:.2f}ms "
            f"(threshold: {threshold}ms) - Client: {client_id}"
        )
        return log_entry

    def get_slow_queries(
        self,
        client_id: str = None,
        limit: int = 50
    ) -> List[SlowQueryLog]:
        """Get slow query logs, optionally filtered by client."""
        with self._lock:
            queries = self._slow_queries.copy()

        if client_id:
            queries = [q for q in queries if q.client_id == client_id]

        return sorted(
            queries,
            key=lambda q: q.execution_time_ms,
            reverse=True
        )[:limit]

    def get_query_statistics(self) -> Dict[str, Any]:
        """Get overall query statistics."""
        with self._lock:
            if not self._slow_queries:
                return {
                    "total_slow_queries": 0,
                    "avg_slow_query_time_ms": 0,
                    "max_slow_query_time_ms": 0
                }

            times = [q.execution_time_ms for q in self._slow_queries]
            return {
                "total_slow_queries": len(self._slow_queries),
                "avg_slow_query_time_ms": sum(times) / len(times),
                "max_slow_query_time_ms": max(times),
                "unique_clients": len(set(q.client_id for q in self._slow_queries))
            }


class QueryOptimizer:
    """
    Main query optimizer combining caching, indexing, and analysis.
    """

    def __init__(
        self,
        cache_ttl: int = 300,
        slow_query_threshold_ms: float = 200
    ):
        self.cache = QueryCache(ttl_seconds=cache_ttl)
        self.indexer = IndexOptimizer()
        self.analyzer = QueryAnalyzer()
        self.analyzer.SLOW_QUERY_THRESHOLD_MS = slow_query_threshold_ms
        self._lock = RLock()

    def optimize(
        self,
        query: str,
        params: Dict = None
    ) -> Tuple[QueryPlan, bool]:
        """
        Optimize a query execution.
        Returns (plan, is_cache_hit).
        """
        cached_result, is_cached = self.cache.get(query, params)
        plan = self.analyzer.analyze_query(query)
        plan.cache_key = self.cache._hash(query, params)
        return plan, is_cached

    def execute_with_caching(
        self,
        query: str,
        executor: Callable,
        params: Dict = None,
        client_id: str = "default"
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Execute query with automatic caching.
        Returns (result, metadata).
        """
        start_time = time.time()
        cached_result, is_hit = self.cache.get(query, params)

        if is_hit:
            execution_time = (time.time() - start_time) * 1000
            return cached_result, {
                "cache_hit": True,
                "execution_time_ms": execution_time,
                "from_cache": True
            }

        result = executor()
        execution_time = (time.time() - start_time) * 1000

        self.cache.set(query, result, params)
        self.analyzer.log_slow_query(
            query,
            execution_time,
            client_id
        )

        return result, {
            "cache_hit": False,
            "execution_time_ms": execution_time,
            "from_cache": False
        }

    def get_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report."""
        return {
            "cache_stats": {
                "hit_rate": self.cache.get_hit_rate(),
                "entries": len(self.cache._cache)
            },
            "slow_query_stats": self.analyzer.get_query_statistics(),
            "index_stats": self.indexer.get_index_stats(),
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        hit_rate = self.cache.get_hit_rate()

        if hit_rate < 0.6:
            recommendations.append(
                f"Cache hit rate ({hit_rate:.1%}) below 60% - "
                "consider increasing TTL or cache size"
            )

        slow_stats = self.analyzer.get_query_statistics()
        if slow_stats["total_slow_queries"] > 10:
            recommendations.append(
                f"{slow_stats['total_slow_queries']} slow queries detected - "
                "review query patterns and add indexes"
            )

        return recommendations

    def invalidate_cache(self, pattern: str = None) -> int:
        """Invalidate cache entries."""
        return self.cache.invalidate(pattern)

    def create_index(self, name: str, fields: List[str]) -> bool:
        """Create an index for optimization."""
        return self.indexer.create_index(name, fields)


class TestQueryOptimizer:
    """Test suite for QueryOptimizer."""

    def test_cache_hit(self):
        """Test query cache hit."""
        optimizer = QueryOptimizer()
        optimizer.cache.set("SELECT * FROM test", {"data": "value"})

        cached, hit = optimizer.cache.get("SELECT * FROM test")
        assert hit is True
        assert cached == {"data": "value"}

    def test_cache_miss(self):
        """Test query cache miss."""
        optimizer = QueryOptimizer()
        cached, hit = optimizer.cache.get("unknown query")
        assert hit is False
        assert cached is None

    def test_slow_query_logging(self):
        """Test slow query detection."""
        analyzer = QueryAnalyzer()
        log = analyzer.log_slow_query(
            "SELECT * FROM large_table",
            execution_time_ms=500,
            client_id="test_client"
        )
        assert log is not None
        assert log.execution_time_ms == 500

    def test_query_analysis(self):
        """Test query plan generation."""
        analyzer = QueryAnalyzer()
        plan = analyzer.analyze_query(
            "SELECT * FROM orders WHERE client_id = 1"
        )
        assert plan.estimated_cost > 0
        assert "idx_client" in plan.indexes_used

    def test_index_creation(self):
        """Test index creation."""
        indexer = IndexOptimizer()
        result = indexer.create_index(
            "idx_test",
            ["field1", "field2"]
        )
        assert result is True

    def test_optimization_report(self):
        """Test optimization report generation."""
        optimizer = QueryOptimizer()
        report = optimizer.get_optimization_report()
        assert "cache_stats" in report
        assert "slow_query_stats" in report

    def test_execute_with_caching(self):
        """Test cached execution."""
        optimizer = QueryOptimizer()
        call_count = 0

        def executor():
            nonlocal call_count
            call_count += 1
            return {"result": "data"}

        result1, meta1 = optimizer.execute_with_caching(
            "test query",
            executor,
            client_id="c1"
        )
        result2, meta2 = optimizer.execute_with_caching(
            "test query",
            executor,
            client_id="c1"
        )

        assert call_count == 1  # Only executed once
        assert meta2["cache_hit"] is True

    def test_query_normalization(self):
        """Test query normalization."""
        analyzer = QueryAnalyzer()
        plan = analyzer.analyze_query("  SELECT  *  FROM  test  ")
        assert plan.normalized_query == "select * from test"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
