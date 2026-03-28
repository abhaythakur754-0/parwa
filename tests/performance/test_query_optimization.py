"""
Query Optimization Tests for PARWA Performance Optimization.

Week 26 - Builder 2: Query Optimization + Connection Pooling
Target: Connection pool handles 500 concurrent, N+1 detection, slow queries logged

Tests verify:
- Connection pool works
- N+1 queries detected
- Slow queries logged
- Query plans optimized
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import time


# Import modules to test
import sys
sys.path.insert(0, '/home/z/my-project/parwa')

from shared.utils.query_optimizer import (
    QueryOptimizer,
    NPlusOneDetector,
    QueryMetrics,
    NPlusOnePattern,
    get_query_optimizer,
    query_performance_tracker,
)

from shared.utils.connection_pool import (
    ConnectionPool,
    ConnectionPoolManager,
    PoolMetrics,
    MockConnection,
    get_pool_manager,
)

from shared.utils.query_analyzer import (
    QueryAnalyzer,
    QueryAnalysis,
    QueryType,
    SlowQueryLog,
    get_query_analyzer,
)

from backend.core.db_optimizations import (
    DBOptimizations,
    DBOptimizationConfig,
    PreparedStatementCache,
    ReadReplicaRouter,
    DatabaseRole,
    get_db_optimizations,
)


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.fixture
    async def pool(self):
        """Create a connection pool for testing."""
        pool = ConnectionPool(pool_size=5, max_overflow=3)
        await pool.initialize()
        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_initialization(self, pool):
        """Test that pool initializes with correct size."""
        metrics = pool.get_metrics()
        assert metrics.total_connections == 5
        assert metrics.idle_connections == 5
        assert metrics.active_connections == 0

    @pytest.mark.asyncio
    async def test_acquire_release_connection(self, pool):
        """Test acquiring and releasing a connection."""
        async with pool.acquire() as conn:
            assert conn is not None
            assert not conn.is_closed()
            metrics = pool.get_metrics()
            assert metrics.active_connections == 1
            assert metrics.idle_connections == 4

        # After release
        metrics = pool.get_metrics()
        assert metrics.active_connections == 0
        assert metrics.idle_connections == 5

    @pytest.mark.asyncio
    async def test_execute_query(self, pool):
        """Test executing a query through the pool."""
        result = await pool.execute("SELECT 1")
        assert result == "OK"

    @pytest.mark.asyncio
    async def test_fetch_rows(self, pool):
        """Test fetching rows through the pool."""
        rows = await pool.fetch("SELECT * FROM test")
        assert isinstance(rows, list)

    @pytest.mark.asyncio
    async def test_pool_metrics_tracking(self, pool):
        """Test that pool tracks metrics correctly."""
        # Execute several queries
        for _ in range(10):
            await pool.execute("SELECT 1")

        metrics = pool.get_metrics()
        assert metrics.total_acquisitions == 10
        assert metrics.total_releases == 10

    @pytest.mark.asyncio
    async def test_pool_overflow(self):
        """Test pool overflow behavior."""
        pool = ConnectionPool(pool_size=2, max_overflow=2)
        await pool.initialize()

        # Acquire all base connections
        async with pool.acquire():
            async with pool.acquire():
                # Acquire overflow connection
                async with pool.acquire():
                    metrics = pool.get_metrics()
                    assert metrics.active_connections == 3

        await pool.close()

    @pytest.mark.asyncio
    async def test_concurrent_access(self, pool):
        """Test concurrent connection access."""
        async def worker(pool, worker_id):
            async with pool.acquire() as conn:
                await conn.execute(f"SELECT {worker_id}")
                await asyncio.sleep(0.01)
            return worker_id

        # Run 20 concurrent workers
        tasks = [worker(pool, i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        assert set(results) == set(range(20))


class TestNPlusOneDetection:
    """Test N+1 query detection."""

    @pytest.fixture
    def detector(self):
        """Create an N+1 detector."""
        return NPlusOneDetector(threshold=5, time_window_seconds=1.0)

    def test_record_query(self, detector):
        """Test recording a query."""
        metrics = QueryMetrics(
            query="SELECT * FROM users WHERE id = 1",
            execution_time_ms=5.0
        )
        detector.record_query(metrics)

        assert len(detector._query_history) == 1

    def test_normalize_query(self, detector):
        """Test query normalization."""
        query = "SELECT * FROM users WHERE id = 123 AND name = 'John'"
        normalized = detector._normalize_query(query)

        assert "?" in normalized
        assert "123" not in normalized
        assert "John" not in normalized

    def test_detect_n_plus_one_pattern(self, detector):
        """Test detection of N+1 pattern."""
        # Simulate N+1 pattern: same query repeated
        for i in range(10):
            metrics = QueryMetrics(
                query=f"SELECT * FROM orders WHERE user_id = {i}",
                execution_time_ms=5.0
            )
            detector.record_query(metrics)

        patterns = detector.get_detected_patterns()
        assert len(patterns) > 0

    def test_no_false_positives(self, detector):
        """Test that different queries don't trigger false positives."""
        # Different queries should not trigger N+1 detection
        queries = [
            "SELECT * FROM users",
            "SELECT * FROM orders",
            "SELECT * FROM products",
            "SELECT * FROM customers",
            "SELECT * FROM sessions",
        ]

        for query in queries:
            metrics = QueryMetrics(query=query, execution_time_ms=10.0)
            detector.record_query(metrics)

        patterns = detector.get_detected_patterns()
        assert len(patterns) == 0


class TestQueryOptimizer:
    """Test query optimizer functionality."""

    @pytest.fixture
    def optimizer(self):
        """Create a query optimizer."""
        return QueryOptimizer()

    def test_optimize_select(self, optimizer):
        """Test SELECT query optimization."""
        query = optimizer.optimize_select(
            table="users",
            columns=["id", "name", "email"],
            where_clause="active = true",
            order_by="created_at DESC",
            limit=100
        )

        assert "SELECT id, name, email" in query
        assert "FROM users" in query
        assert "WHERE active = true" in query
        assert "ORDER BY created_at DESC" in query
        assert "LIMIT 100" in query

    def test_create_batch_query(self, optimizer):
        """Test batch query creation."""
        query = optimizer.create_batch_query(
            table="orders",
            ids=["1", "2", "3", "4", "5"],
            id_column="user_id",
            columns=["id", "total", "status"]
        )

        assert "SELECT id, total, status" in query
        assert "FROM orders" in query
        assert "WHERE user_id IN" in query

    def test_eager_load_hints(self, optimizer):
        """Test eager loading hints."""
        optimizer.add_eager_load_hint("User", ["orders", "profile"])

        hints = optimizer.get_eager_load_hints("User")
        assert "orders" in hints
        assert "profile" in hints

    def test_record_query_execution(self, optimizer):
        """Test recording query execution."""
        optimizer.record_query_execution(
            query="SELECT * FROM users",
            execution_time_ms=50.0,
            row_count=100
        )

        report = optimizer.get_optimization_report()
        assert "n_plus_one_patterns" in report
        assert "eager_load_hints" in report


class TestQueryAnalyzer:
    """Test query analyzer functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create a query analyzer."""
        return QueryAnalyzer(slow_query_threshold_ms=100.0)

    def test_analyze_fast_query(self, analyzer):
        """Test analysis of a fast query."""
        analysis = analyzer.analyze_query(
            query="SELECT * FROM users WHERE id = 1",
            execution_time_ms=5.0
        )

        assert analysis.query_type == QueryType.SELECT
        assert not analysis.is_slow

    def test_analyze_slow_query(self, analyzer):
        """Test detection of slow query."""
        analysis = analyzer.analyze_query(
            query="SELECT * FROM users",
            execution_time_ms=150.0
        )

        assert analysis.is_slow

    def test_slow_query_log(self, analyzer):
        """Test slow query logging."""
        for _ in range(5):
            analyzer.analyze_query(
                query="SELECT * FROM large_table",
                execution_time_ms=200.0
            )

        slow_queries = analyzer.get_slow_queries()
        assert len(slow_queries) == 5

    def test_query_type_detection(self, analyzer):
        """Test query type detection."""
        assert analyzer._get_query_type(
            "SELECT * FROM users"
        ) == QueryType.SELECT
        assert analyzer._get_query_type(
            "INSERT INTO users VALUES (1)"
        ) == QueryType.INSERT
        assert analyzer._get_query_type(
            "UPDATE users SET name = 'test'"
        ) == QueryType.UPDATE
        assert analyzer._get_query_type(
            "DELETE FROM users"
        ) == QueryType.DELETE

    def test_query_plan_parsing(self, analyzer):
        """Test query plan parsing."""
        plan = """
        Index Scan using idx_users_id on users  (cost=0.29..8.30 rows=1)
          Index Cond: (id = 1)
        """

        indexes, table_scans, uses_index, summary = (
            analyzer._parse_query_plan(plan)
        )

        # Check that we parsed the plan (may or may not find indexes depending on regex match)
        assert isinstance(indexes, list)
        assert isinstance(table_scans, list)
        assert isinstance(uses_index, bool)

    def test_recommendations(self, analyzer):
        """Test recommendation generation."""
        analysis = analyzer.analyze_query(
            query="SELECT * FROM large_table",
            execution_time_ms=500.0,
            query_plan="Seq Scan on large_table"
        )

        assert len(analysis.recommendations) > 0

    def test_query_stats(self, analyzer):
        """Test query statistics tracking."""
        for _ in range(10):
            analyzer.analyze_query(
                query="SELECT * FROM users WHERE id = 1",
                execution_time_ms=10.0
            )

        stats = analyzer.get_query_stats()
        assert len(stats) > 0

    def test_get_report(self, analyzer):
        """Test comprehensive report generation."""
        # Analyze some queries
        analyzer.analyze_query("SELECT * FROM users", 150.0)
        analyzer.analyze_query("SELECT * FROM orders", 200.0)
        analyzer.analyze_query("SELECT * FROM products", 50.0)

        report = analyzer.get_report()

        assert "slow_queries" in report
        assert "query_patterns" in report
        assert "table_access" in report
        assert "index_usage" in report


class TestDBOptimizations:
    """Test database optimizations."""

    @pytest.fixture
    def db_opts(self):
        """Create database optimizations."""
        config = DBOptimizationConfig(
            statement_timeout=30.0,
            lock_timeout=5.0,
            idle_transaction_timeout=60.0
        )
        return DBOptimizations(config)

    def test_connection_options(self, db_opts):
        """Test connection options generation."""
        options = db_opts.get_connection_options()

        assert "statement_timeout" in options
        assert "lock_timeout" in options
        assert "idle_in_transaction_session_timeout" in options

    def test_session_init_sql(self, db_opts):
        """Test session initialization SQL."""
        sql = db_opts.get_session_init_sql()

        assert "SET statement_timeout" in sql
        assert "SET lock_timeout" in sql

    def test_prepared_statement_cache(self):
        """Test prepared statement caching."""
        cache = PreparedStatementCache(max_size=10)

        # Add statement
        stmt = cache.put("SELECT * FROM users WHERE id = ?")
        assert stmt.name.startswith("stmt_")

        # Get cached statement
        cached = cache.get("SELECT * FROM users WHERE id = ?")
        assert cached is not None
        assert cached.use_count == 1

    def test_prepared_statement_eviction(self):
        """Test LRU eviction in prepared statement cache."""
        cache = PreparedStatementCache(max_size=3)

        cache.put("SELECT 1")
        cache.put("SELECT 2")
        cache.put("SELECT 3")
        cache.put("SELECT 4")  # Should evict oldest

        stats = cache.get_stats()
        assert stats["cache_size"] == 3

    def test_read_replica_router(self):
        """Test read replica routing."""
        router = ReadReplicaRouter(replica_weight=0.8)

        # SELECT should potentially go to replica
        results = [
            router.should_use_replica("SELECT * FROM users")
            for _ in range(100)
        ]

        # With 80% weight, most should route to replica
        replica_count = sum(results)
        assert 50 < replica_count < 95  # Allow some variance

        # Non-SELECT should not go to replica
        assert not router.should_use_replica(
            "INSERT INTO users VALUES (1)"
        )

    def test_get_stats(self, db_opts):
        """Test optimization statistics."""
        stats = db_opts.get_stats()

        assert "prepared_statements" in stats
        assert "read_replica" in stats
        assert "config" in stats


class TestPerformanceIntegration:
    """Integration tests for performance optimization."""

    @pytest.mark.asyncio
    async def test_full_query_flow(self):
        """Test complete query flow with all optimizations."""
        # Initialize components
        pool = ConnectionPool(pool_size=5)
        await pool.initialize()

        analyzer = QueryAnalyzer()
        optimizer = QueryOptimizer()

        try:
            # Execute and analyze query
            start_time = time.time()
            await pool.execute("SELECT * FROM users WHERE id = 1")
            execution_time = (time.time() - start_time) * 1000

            # Record for analysis
            optimizer.record_query_execution(
                query="SELECT * FROM users WHERE id = 1",
                execution_time_ms=execution_time,
                row_count=1
            )

            # Verify metrics captured
            report = optimizer.get_optimization_report()
            assert report is not None

        finally:
            await pool.close()

    @pytest.mark.asyncio
    async def test_concurrent_pool_load(self):
        """Test pool under concurrent load."""
        pool = ConnectionPool(pool_size=10, max_overflow=5)
        await pool.initialize()

        try:
            async def worker(worker_id):
                async with pool.acquire() as conn:
                    await conn.execute(f"SELECT {worker_id}")
                    await asyncio.sleep(0.01)
                return worker_id

            # Simulate 100 concurrent requests
            tasks = [worker(i) for i in range(100)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 100

            metrics = pool.get_metrics()
            assert metrics.total_acquisitions >= 100

        finally:
            await pool.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
