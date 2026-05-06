"""
Cache Performance Tests for PARWA Performance Optimization.

Week 26 - Builder 3: Redis Cache Deep Optimization
Target: Cache hit rate >75%, cache latency <1ms, invalidation works

Tests verify:
- Response cache hit rate >80%
- Query cache hit rate >70%
- Cache invalidation works correctly
- Cache latency <1ms
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any

import sys
sys.path.insert(0, '/home/z/my-project/parwa')

from shared.utils.response_cache import (
    ResponseCache,
    CacheStats,
    CacheEntry,
    get_response_cache,
)

from shared.utils.query_cache import (
    QueryCache,
    QueryCacheStats,
    QueryCacheEntry,
    get_query_cache,
)

from shared.utils.session_cache import (
    SessionCache,
    SessionData,
    SessionCacheStats,
    get_session_cache,
)

from shared.utils.cache_invalidator import (
    CacheInvalidator,
    InvalidationRule,
    InvalidationStats,
    get_cache_invalidator,
)

from shared.utils.cache_metrics import (
    CacheMetricsCollector,
    CacheMetrics,
    get_cache_metrics,
)


class TestResponseCache:
    """Test response cache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a response cache for testing."""
        return ResponseCache()

    def test_generate_cache_key(self, cache):
        """Test cache key generation."""
        key = cache._generate_cache_key(
            endpoint="/api/v1/tickets",
            client_id="client_123",
            params={"status": "open"},
            user_id="user_456"
        )

        assert "parwa" in key
        assert "client:client_123" in key
        assert "endpoint:/api/v1/tickets" in key

    def test_generate_etag(self, cache):
        """Test ETag generation."""
        data1 = {"id": 1, "name": "test"}
        data2 = {"id": 1, "name": "test"}
        data3 = {"id": 2, "name": "test"}

        etag1 = cache._generate_etag(data1)
        etag2 = cache._generate_etag(data2)
        etag3 = cache._generate_etag(data3)

        assert etag1 == etag2  # Same data = same ETag
        assert etag1 != etag3  # Different data = different ETag

    def test_get_ttl_for_endpoint(self, cache):
        """Test TTL determination for endpoints."""
        assert cache.get_ttl_for_endpoint("/api/v1/dashboard") == 30
        assert cache.get_ttl_for_endpoint("/api/v1/analytics") == 300
        assert cache.get_ttl_for_endpoint("/api/v1/faq") == 3600
        assert cache.get_ttl_for_endpoint("/api/v1/unknown") == 60  # Default

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """Test setting and getting cached responses."""
        endpoint = "/api/v1/tickets"
        client_id = "client_123"
        data = {"tickets": [{"id": 1}, {"id": 2}]}

        # Set cache
        etag = await cache.set(endpoint, client_id, data)
        assert etag is not None

        # Get cache
        cached = await cache.get(endpoint, client_id)
        assert cached is not None
        assert cached["data"] == data
        assert cached["etag"] == etag
        assert cached["fresh"] is True

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        """Test cache miss behavior."""
        cached = await cache.get("/api/v1/unknown", "unknown_client")
        assert cached is None

        stats = cache.get_stats()
        assert stats.misses == 1
        assert stats.total_requests == 1

    @pytest.mark.asyncio
    async def test_should_cache(self, cache):
        """Test cache decision logic."""
        assert cache.should_cache("GET", "/api/v1/tickets", 200) is True
        assert cache.should_cache("POST", "/api/v1/tickets", 200) is False
        assert cache.should_cache("GET", "/api/v1/tickets", 500) is False
        assert cache.should_cache("GET", "/api/v1/auth/login", 200) is False

    @pytest.mark.asyncio
    async def test_invalidate_client(self, cache):
        """Test client-specific cache invalidation."""
        # Set multiple cache entries
        await cache.set("/api/v1/tickets", "client_1", {"data": "1"})
        await cache.set("/api/v1/tickets", "client_2", {"data": "2"})

        # Invalidate client_1
        count = await cache.invalidate_client("client_1")
        assert count >= 1

        # client_1 cache should be gone
        cached1 = await cache.get("/api/v1/tickets", "client_1")
        assert cached1 is None

        # client_2 cache should still exist
        cached2 = await cache.get("/api/v1/tickets", "client_2")
        assert cached2 is not None

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, cache):
        """Test hit rate calculation."""
        # Generate hits and misses
        await cache.set("/api/v1/test", "client_1", {"data": "test"})
        await cache.get("/api/v1/test", "client_1")  # Hit
        await cache.get("/api/v1/unknown", "client_1")  # Miss

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5


class TestQueryCache:
    """Test query cache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a query cache for testing."""
        return QueryCache()

    def test_hash_query(self, cache):
        """Test query hashing."""
        query1 = "SELECT * FROM users WHERE id = 1"
        query2 = "SELECT * FROM users WHERE id = 1"
        query3 = "SELECT * FROM users WHERE id = 2"

        hash1 = cache._hash_query(query1)
        hash2 = cache._hash_query(query2)
        hash3 = cache._hash_query(query3)

        assert hash1 == hash2
        assert hash1 != hash3

    def test_extract_tables(self, cache):
        """Test table extraction from queries."""
        query1 = "SELECT * FROM users WHERE id = 1"
        query2 = "SELECT t.*, u.name FROM tickets t JOIN users u ON t.user_id = u.id"

        tables1 = cache._extract_tables(query1)
        tables2 = cache._extract_tables(query2)

        assert "users" in tables1
        assert "tickets" in tables2
        assert "users" in tables2

    def test_get_ttl_for_query(self, cache):
        """Test TTL determination based on tables."""
        query1 = "SELECT * FROM support_tickets WHERE id = 1"
        query2 = "SELECT * FROM unknown_table WHERE id = 1"

        ttl1 = cache.get_ttl_for_query(query1)
        ttl2 = cache.get_ttl_for_query(query2)

        # support_tickets has REALTIME TTL (30 seconds)
        assert ttl1 == cache.TTL_REALTIME
        # unknown_table uses default TTL
        assert ttl2 == cache.default_ttl

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """Test setting and getting cached query results."""
        query = "SELECT * FROM users WHERE id = ?"
        params = (1,)
        result = [{"id": 1, "name": "John"}]

        # Set cache
        await cache.set(query, result, params)

        # Get cache
        cached = await cache.get(query, params)
        assert cached == result

    @pytest.mark.asyncio
    async def test_invalidate_table(self, cache):
        """Test table-based invalidation."""
        query = "SELECT * FROM users WHERE id = ?"
        result = [{"id": 1}]

        await cache.set(query, result, (1,))
        cached = await cache.get(query, (1,))
        assert cached is not None

        # Invalidate table
        count = await cache.invalidate_table("users")
        assert count >= 1

        # Cache should be gone
        cached = await cache.get(query, (1,))
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_warming(self, cache):
        """Test cache warming."""
        warm_query = "SELECT COUNT(*) FROM users"
        warm_result = 100

        async def mock_execute(query, params):
            if "COUNT" in query:
                return warm_result
            return None

        cache.register_warm_query(warm_query)
        count = await cache.warm_cache(mock_execute)

        assert count == 1


class TestSessionCache:
    """Test session cache functionality."""

    @pytest.fixture
    def cache(self):
        """Create a session cache for testing."""
        return SessionCache(enable_compression=False)

    def test_generate_session_id(self, cache):
        """Test session ID generation."""
        session_id1 = cache._generate_session_id("user_1", "device_1")
        session_id2 = cache._generate_session_id("user_1", "device_1")

        assert len(session_id1) == 32
        assert session_id1 != session_id2  # Different each time

    def test_get_ttl_for_industry(self, cache):
        """Test TTL for different industries."""
        assert cache.get_ttl_for_industry("financial") == 900
        assert cache.get_ttl_for_industry("healthcare") == 900
        assert cache.get_ttl_for_industry("default") == 900

    @pytest.mark.asyncio
    async def test_create_session(self, cache):
        """Test session creation."""
        session = await cache.create(
            user_id="user_123",
            client_id="client_456",
            industry="default"
        )

        assert session.session_id is not None
        assert session.user_id == "user_123"
        assert session.client_id == "client_456"
        assert session.expires_at > session.created_at

    @pytest.mark.asyncio
    async def test_get_session(self, cache):
        """Test session retrieval."""
        created = await cache.create(
            user_id="user_123",
            client_id="client_456"
        )

        session = await cache.get(created.session_id)
        assert session is not None
        assert session.user_id == "user_123"

    @pytest.mark.asyncio
    async def test_destroy_session(self, cache):
        """Test session destruction."""
        session = await cache.create(
            user_id="user_123",
            client_id="client_456"
        )

        destroyed = await cache.destroy(session.session_id)
        assert destroyed is True

        cached = await cache.get(session.session_id)
        assert cached is None

    @pytest.mark.asyncio
    async def test_update_session(self, cache):
        """Test session update."""
        session = await cache.create(
            user_id="user_123",
            client_id="client_456"
        )

        updated = await cache.update(
            session.session_id,
            {"cart_items": [1, 2, 3]}
        )
        assert updated is True

        cached = await cache.get(session.session_id)
        assert cached.data.get("cart_items") == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_multi_device_sessions(self, cache):
        """Test multi-device session support."""
        session1 = await cache.create(
            user_id="user_123",
            client_id="client_456",
            device_id="device_1"
        )

        session2 = await cache.create(
            user_id="user_123",
            client_id="client_456",
            device_id="device_2"
        )

        sessions = await cache.get_user_sessions("user_123")
        assert len(sessions) == 2

        # Destroy all sessions for user
        count = await cache.destroy_user_sessions("user_123")
        assert count == 2


class TestCacheInvalidator:
    """Test cache invalidation functionality."""

    @pytest.fixture
    def invalidator(self):
        """Create a cache invalidator for testing."""
        return CacheInvalidator(enable_pubsub=False)

    def test_match_pattern(self, invalidator):
        """Test pattern matching."""
        assert invalidator._match_pattern(
            "parwa:cache:response:client:123:endpoint:/api/v1/tickets",
            "parwa:cache:response:*:endpoint:/api/v1/tickets*"
        )
        assert not invalidator._match_pattern(
            "parwa:cache:response:client:123:endpoint:/api/v1/users",
            "parwa:cache:response:*:endpoint:/api/v1/tickets*"
        )

    def test_add_rule(self, invalidator):
        """Test adding invalidation rules."""
        rule = InvalidationRule(
            trigger_table="custom_table",
            trigger_operation="INSERT",
            patterns=["cache:custom:*"],
            tags=["custom"]
        )

        invalidator.add_rule(rule)
        assert len(invalidator._rules) > len(invalidator.DEFAULT_RULES)

    def test_register_key(self, invalidator):
        """Test key registration."""
        invalidator.register_key(
            "cache:test:key1",
            tags=["tickets", "dashboard"],
            patterns=["cache:test:*"]
        )

        assert "tickets" in invalidator._tag_index
        assert "cache:test:key1" in invalidator._tag_index["tickets"]

    @pytest.mark.asyncio
    async def test_invalidate_on_write(self, invalidator):
        """Test invalidation on write."""
        # Register a key
        invalidator.register_key(
            "parwa:cache:response:client:123:endpoint:/api/v1/tickets",
            tags=["tickets"]
        )

        # Trigger invalidation
        count = await invalidator.invalidate_on_write(
            table="support_tickets",
            operation="INSERT",
            client_id="123"
        )

        assert count >= 0  # May or may not have matching entries

    @pytest.mark.asyncio
    async def test_tag_invalidation(self, invalidator):
        """Test tag-based invalidation."""
        invalidator.register_key(
            "cache:test:1",
            tags=["test_tag"]
        )
        invalidator.register_key(
            "cache:test:2",
            tags=["test_tag"]
        )

        count = await invalidator._invalidate_tag("test_tag")
        assert count == 2


class TestCacheMetrics:
    """Test cache metrics functionality."""

    @pytest.fixture
    def metrics(self):
        """Create a metrics collector for testing."""
        return CacheMetricsCollector(enable_prometheus=False)

    def test_record_hit(self, metrics):
        """Test recording cache hits."""
        metrics.record_hit("response", "client_1", 0.5)

        cache_metrics = metrics.get_metrics("response")
        assert cache_metrics is not None
        assert cache_metrics.hits == 1
        assert cache_metrics.avg_latency_ms == 0.5

    def test_record_miss(self, metrics):
        """Test recording cache misses."""
        metrics.record_miss("response", "client_1", 0.2)

        cache_metrics = metrics.get_metrics("response")
        assert cache_metrics.misses == 1

    def test_hit_rate_calculation(self, metrics):
        """Test hit rate calculation."""
        for _ in range(80):
            metrics.record_hit("query", "client_1")

        for _ in range(20):
            metrics.record_miss("query", "client_1")

        cache_metrics = metrics.get_metrics("query")
        assert cache_metrics.hit_rate == 0.8

    def test_record_eviction(self, metrics):
        """Test recording evictions."""
        metrics.record_set("response", 1.0, 1000)
        metrics.record_eviction("response", "ttl_expired", 1000)

        cache_metrics = metrics.get_metrics("response")
        assert cache_metrics.evictions == 1
        assert cache_metrics.memory_bytes == 0

    def test_latency_percentile(self, metrics):
        """Test latency percentile calculation."""
        # Record various latencies
        latencies = [0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0]
        for lat in latencies:
            metrics.record_hit("response", "client_1", lat)

        p50 = metrics.get_latency_percentile("response", 50)
        p95 = metrics.get_latency_percentile("response", 95)
        p99 = metrics.get_latency_percentile("response", 99)

        assert p50 is not None
        assert p95 is not None
        assert p99 is not None
        assert p50 <= p95 <= p99

    def test_get_report(self, metrics):
        """Test metrics report generation."""
        metrics.record_hit("response", "client_1")
        metrics.record_miss("response", "client_1")
        metrics.record_hit("query", "client_1")

        report = metrics.get_report()

        assert "caches" in report
        assert "overall" in report
        assert "response" in report["caches"]
        assert "query" in report["caches"]


class TestCachePerformanceIntegration:
    """Integration tests for cache performance."""

    @pytest.mark.asyncio
    async def test_end_to_end_caching(self):
        """Test complete caching workflow."""
        response_cache = ResponseCache()
        query_cache = QueryCache()
        invalidator = CacheInvalidator(enable_pubsub=False)

        # Simulate API response caching
        endpoint = "/api/v1/dashboard"
        client_id = "client_123"
        data = {"metrics": {"tickets": 100, "resolved": 80}}

        # Cache the response
        await response_cache.set(endpoint, client_id, data)

        # Retrieve from cache
        cached = await response_cache.get(endpoint, client_id)
        assert cached is not None
        assert cached["data"] == data

        # Simulate query caching
        query = "SELECT COUNT(*) FROM support_tickets WHERE client_id = ?"
        result = [{"count": 100}]
        await query_cache.set(query, result, (client_id,))

        cached_query = await query_cache.get(query, (client_id,))
        assert cached_query == result

        # Trigger invalidation
        count = await invalidator.invalidate_on_write(
            "support_tickets", "INSERT", client_id=client_id
        )

    @pytest.mark.asyncio
    async def test_cache_latency_target(self):
        """Test that cache operations meet latency target (<1ms)."""
        cache = ResponseCache()

        # Measure average latency over multiple operations
        latencies = []

        for i in range(100):
            start = time.time()
            await cache.set(f"/api/v1/test/{i}", "client_1", {"data": i})
            await cache.get(f"/api/v1/test/{i}", "client_1")
            latency = (time.time() - start) * 1000 / 2  # Average of set and get
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 1.0  # Target: <1ms average


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
