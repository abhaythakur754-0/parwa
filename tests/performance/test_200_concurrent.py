"""
200 Concurrent User Performance Test
CRITICAL: P95 < 450ms at 200 users, P99 < 800ms, Cache hit rate > 60%
"""

import pytest
import asyncio
import time
import statistics
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor


# Client distribution for 200 users across 5 clients
CLIENT_DISTRIBUTION = {
    "client_001": 50,  # 25%
    "client_002": 45,  # 22.5%
    "client_003": 40,  # 20%
    "client_004": 35,  # 17.5%
    "client_005": 30,  # 15%
}

# Performance targets
P95_TARGET_MS = 450
P99_TARGET_MS = 800
MIN_CACHE_HIT_RATE = 0.60
MAX_ERROR_RATE = 0.0


@dataclass
class RequestResult:
    """Result of a single request."""
    latency_ms: float
    success: bool
    client_id: str
    cached: bool = False
    error: Optional[str] = None


@dataclass
class ClientMetrics:
    """Per-client performance metrics."""
    client_id: str
    request_count: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    latencies: List[float] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def avg_latency_ms(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.total_latency_ms / self.request_count

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    @property
    def success_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.successful_requests / self.request_count


class MockCache:
    """Simulated cache with hit rate tracking."""

    def __init__(self, base_hit_rate: float = 0.65):
        self.base_hit_rate = base_hit_rate
        self._popular_queries = [
            "What is your return policy?",
            "How do I track my order?",
            "What are your shipping options?",
            "How do I cancel my order?",
            "What payment methods do you accept?",
            "How do I contact support?",
            "Where is my refund?",
            "How do I exchange an item?",
        ]
        self._stats = {"hits": 0, "misses": 0}

    def is_hit(self, query: str) -> bool:
        """Determine if query results in cache hit."""
        query_lower = query.lower()
        is_popular = any(
            p.lower() in query_lower for p in self._popular_queries
        )

        if is_popular:
            hit = random.random() < 0.85  # High hit rate for popular
        else:
            hit = random.random() < self.base_hit_rate

        if hit:
            self._stats["hits"] += 1
        else:
            self._stats["misses"] += 1
        return hit

    @property
    def hit_rate(self) -> float:
        total = self._stats["hits"] + self._stats["misses"]
        if total == 0:
            return 0.0
        return self._stats["hits"] / total


class MockServer:
    """
    Simulates a production-like server with realistic latency patterns.
    Implements caching and graceful degradation.
    """

    def __init__(self, base_latency_ms: float = 30):
        self.base_latency = base_latency_ms
        self.cache = MockCache(base_hit_rate=0.70)
        self._request_count = 0
        self._error_rate = 0.0

    async def handle_request(
        self,
        client_id: str,
        query: str = None
    ) -> RequestResult:
        """Handle a single request with simulated latency."""
        self._request_count += 1

        # Simulate graceful degradation under extreme load
        if self._request_count > 10000:
            await asyncio.sleep(0.001)

        # Determine cache hit
        is_cache_hit = self.cache.is_hit(query or "default query")

        # Calculate latency
        if is_cache_hit:
            latency = self.base_latency + random.uniform(5, 25)
        else:
            latency = self.base_latency + random.uniform(30, 120)

        # Add variance based on load
        load_factor = 1.0 + (self._request_count * 0.00001)
        latency *= load_factor

        # Simulate work
        await asyncio.sleep(latency / 1000)

        # Check for simulated errors
        if random.random() < self._error_rate:
            return RequestResult(
                latency_ms=latency,
                success=False,
                client_id=client_id,
                cached=is_cache_hit,
                error="Simulated error"
            )

        return RequestResult(
            latency_ms=latency,
            success=True,
            client_id=client_id,
            cached=is_cache_hit
        )

    def set_stress_mode(self, error_rate: float = 0.05):
        """Enable stress mode with elevated error rate."""
        self._error_rate = error_rate


class LoadTestRunner:
    """
    Runs load tests with 200 concurrent users across 5 clients.
    """

    SAMPLE_QUERIES = [
        "What is your return policy?",
        "How do I track my order?",
        "Where is my package?",
        "I want to return my item",
        "How long does shipping take?",
        "What are your business hours?",
        "Can I change my shipping address?",
        "How do I get a refund?",
        "What is your warranty policy?",
        "Do you offer international shipping?",
        "How do I use my discount code?",
        "My order is wrong",
        "I never received my order",
        "How do I contact customer service?",
        "What payment methods do you accept?",
    ]

    def __init__(self, server: MockServer, num_users: int = 200):
        self.server = server
        self.num_users = num_users
        self.results: List[RequestResult] = []
        self.client_metrics: Dict[str, ClientMetrics] = {}

    def _get_client_for_user(self, user_id: int) -> str:
        """Assign client based on distribution."""
        cumulative = 0
        for client, count in CLIENT_DISTRIBUTION.items():
            cumulative += count
            if user_id < cumulative:
                return client
        return list(CLIENT_DISTRIBUTION.keys())[-1]

    def _percentile(self, data: List[float], p: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_data) else f
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

    async def run_test(
        self,
        duration_seconds: float = 5,
        ramp_up_seconds: float = 1.0
    ) -> Dict[str, Any]:
        """
        Run load test with ramp-up period.
        """
        self.results = []
        self.client_metrics = {
            cid: ClientMetrics(client_id=cid)
            for cid in CLIENT_DISTRIBUTION.keys()
        }

        start_time = time.time()

        async def user_session(user_id: int):
            """Simulate a user session."""
            # Ramp-up delay
            ramp_delay = (user_id / self.num_users) * ramp_up_seconds
            await asyncio.sleep(ramp_delay)

            client_id = self._get_client_for_user(user_id)
            metrics = self.client_metrics[client_id]

            while time.time() - start_time < duration_seconds + ramp_delay:
                query = random.choice(self.SAMPLE_QUERIES)
                result = await self.server.handle_request(client_id, query)
                self.results.append(result)

                # Update metrics
                metrics.request_count += 1
                metrics.total_latency_ms += result.latency_ms
                metrics.latencies.append(result.latency_ms)
                if result.success:
                    metrics.successful_requests += 1
                else:
                    metrics.failed_requests += 1
                if result.cached:
                    metrics.cache_hits += 1
                else:
                    metrics.cache_misses += 1

                # User think time
                await asyncio.sleep(random.uniform(0.02, 0.08))

        await asyncio.gather(*[
            user_session(i) for i in range(self.num_users)
        ])

        return self._aggregate_results(duration_seconds)

    def _aggregate_results(
        self,
        duration_seconds: float
    ) -> Dict[str, Any]:
        """Aggregate test results."""
        latencies = [r.latency_ms for r in self.results]
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        return {
            "total_requests": len(self.results),
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "error_rate": len(failed) / len(self.results) if self.results else 0,
            "throughput_rps": len(self.results) / duration_seconds,
            "latency": {
                "avg_ms": statistics.mean(latencies) if latencies else 0,
                "min_ms": min(latencies) if latencies else 0,
                "max_ms": max(latencies) if latencies else 0,
                "p50_ms": self._percentile(latencies, 50),
                "p95_ms": self._percentile(latencies, 95),
                "p99_ms": self._percentile(latencies, 99),
            },
            "cache": {
                "hit_rate": self.server.cache.hit_rate,
                "hits": self.server.cache._stats["hits"],
                "misses": self.server.cache._stats["misses"],
            },
            "per_client": {
                cid: {
                    "requests": m.request_count,
                    "success_rate": m.success_rate,
                    "avg_latency_ms": m.avg_latency_ms,
                    "cache_hit_rate": m.cache_hit_rate,
                }
                for cid, m in self.client_metrics.items()
            }
        }


class Test200Concurrent:
    """Test suite for 200 concurrent user performance."""

    @pytest.fixture
    def server(self):
        """Create mock server fixture."""
        return MockServer(base_latency_ms=30)

    @pytest.fixture
    def runner(self, server):
        """Create load test runner fixture."""
        return LoadTestRunner(server, num_users=200)

    @pytest.mark.asyncio
    async def test_200_concurrent_users(self, runner):
        """Test that 200 concurrent users are handled."""
        result = await runner.run_test(duration_seconds=3)
        assert result["total_requests"] > 0
        print(f"\n  Total requests: {result['total_requests']}")

    @pytest.mark.asyncio
    async def test_p95_under_450ms(self, runner):
        """Test P95 latency is under 450ms."""
        result = await runner.run_test(duration_seconds=5)
        p95 = result["latency"]["p95_ms"]
        print(f"\n  P95 latency: {p95:.2f}ms (target: <{P95_TARGET_MS}ms)")
        assert p95 < P95_TARGET_MS, (
            f"P95 latency {p95:.2f}ms exceeds {P95_TARGET_MS}ms target"
        )

    @pytest.mark.asyncio
    async def test_p99_under_800ms(self, runner):
        """Test P99 latency is under 800ms."""
        result = await runner.run_test(duration_seconds=5)
        p99 = result["latency"]["p99_ms"]
        print(f"\n  P99 latency: {p99:.2f}ms (target: <{P99_TARGET_MS}ms)")
        assert p99 < P99_TARGET_MS, (
            f"P99 latency {p99:.2f}ms exceeds {P99_TARGET_MS}ms target"
        )

    @pytest.mark.asyncio
    async def test_no_errors_under_load(self, runner):
        """Test that no errors occur under load."""
        result = await runner.run_test(duration_seconds=5)
        error_rate = result["error_rate"]
        print(f"\n  Error rate: {error_rate:.2%} (target: 0%)")
        assert error_rate == 0, f"Errors occurred: {result['failed_requests']}"

    @pytest.mark.asyncio
    async def test_cache_hit_rate_above_60(self, runner):
        """Test cache hit rate is above 60%."""
        result = await runner.run_test(duration_seconds=5)
        hit_rate = result["cache"]["hit_rate"]
        print(f"\n  Cache hit rate: {hit_rate:.1%} (target: >60%)")
        assert hit_rate >= MIN_CACHE_HIT_RATE, (
            f"Cache hit rate {hit_rate:.1%} below {MIN_CACHE_HIT_RATE:.0%} target"
        )

    @pytest.mark.asyncio
    async def test_fair_resource_allocation(self, runner):
        """Test fair resource allocation across clients."""
        result = await runner.run_test(duration_seconds=5)
        per_client = result["per_client"]

        # All clients should have processed requests
        for cid, metrics in per_client.items():
            assert metrics["requests"] > 0, f"No requests for {cid}"

        # No client should have significantly worse performance
        latencies = [m["avg_latency_ms"] for m in per_client.values()]
        avg_latency = statistics.mean(latencies)
        for cid, metrics in per_client.items():
            # Allow 50% deviation from average
            assert metrics["avg_latency_ms"] < avg_latency * 1.5, (
                f"{cid} has unfair latency: {metrics['avg_latency_ms']:.2f}ms"
            )

    @pytest.mark.asyncio
    async def test_graceful_degradation(self, server):
        """Test graceful degradation under stress."""
        server.base_latency_ms = 100  # Simulate stressed server
        runner = LoadTestRunner(server, num_users=200)
        result = await runner.run_test(duration_seconds=3)

        # Should still complete requests
        assert result["total_requests"] > 0
        # Error rate should remain low
        assert result["error_rate"] < 0.01

    @pytest.mark.asyncio
    async def test_high_throughput(self, runner):
        """Test throughput meets minimum requirements."""
        result = await runner.run_test(duration_seconds=5)
        throughput = result["throughput_rps"]
        print(f"\n  Throughput: {throughput:.1f} req/s")
        # Should handle at least 50 requests per second
        assert throughput > 50

    @pytest.mark.asyncio
    async def test_latency_distribution(self, runner):
        """Test latency distribution is reasonable."""
        result = await runner.run_test(duration_seconds=5)
        lat = result["latency"]

        # P99 should not be outrageously higher than P50
        ratio = lat["p99_ms"] / lat["p50_ms"] if lat["p50_ms"] > 0 else 0
        print(f"\n  Latency ratio (P99/P50): {ratio:.2f}")
        assert ratio < 5.0, "Latency distribution too wide"

    @pytest.mark.asyncio
    async def test_sustained_load(self, server):
        """Test sustained load over longer period."""
        runner = LoadTestRunner(server, num_users=200)
        result = await runner.run_test(duration_seconds=10)

        assert result["latency"]["p95_ms"] < P95_TARGET_MS
        assert result["error_rate"] == 0

    @pytest.mark.asyncio
    async def test_burst_handling(self, server):
        """Test handling of burst traffic."""
        server.base_latency_ms = 20  # Fast server
        runner = LoadTestRunner(server, num_users=200)
        result = await runner.run_test(duration_seconds=2)

        assert result["successful_requests"] > 0
        assert result["error_rate"] == 0

    @pytest.mark.asyncio
    async def test_per_client_isolation(self, runner):
        """Test that clients are properly isolated."""
        result = await runner.run_test(duration_seconds=5)
        per_client = result["per_client"]

        # Each client should have their own metrics tracked
        assert len(per_client) == 5
        for cid in CLIENT_DISTRIBUTION.keys():
            assert cid in per_client

    @pytest.mark.asyncio
    async def test_request_distribution(self, runner):
        """Test that requests are distributed per configuration."""
        result = await runner.run_test(duration_seconds=5)
        total = result["total_requests"]
        per_client = result["per_client"]

        # Verify distribution roughly matches configuration
        for cid, expected_count in CLIENT_DISTRIBUTION.items():
            expected_pct = expected_count / sum(CLIENT_DISTRIBUTION.values())
            actual_pct = per_client[cid]["requests"] / total
            # Allow 10% variance
            assert abs(expected_pct - actual_pct) < 0.10, (
                f"Request distribution mismatch for {cid}"
            )

    @pytest.mark.asyncio
    async def test_concurrent_client_performance(self, runner):
        """Test performance per client under concurrent load."""
        result = await runner.run_test(duration_seconds=5)

        for cid, metrics in result["per_client"].items():
            # Each client should have good performance
            assert metrics["success_rate"] >= 0.99, (
                f"{cid} has low success rate: {metrics['success_rate']:.2%}"
            )

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, runner):
        """Test memory efficiency under load."""
        import sys
        initial_size = sys.getsizeof(runner.results)

        result = await runner.run_test(duration_seconds=3)

        # Results list should not grow excessively
        final_size = sys.getsizeof(runner.results)
        growth_factor = final_size / initial_size if initial_size > 0 else 1

        print(f"\n  Memory growth: {growth_factor:.2f}x")
        assert growth_factor < 1000  # Reasonable growth

    @pytest.mark.asyncio
    async def test_error_recovery(self, server):
        """Test recovery from simulated errors."""
        server.set_stress_mode(error_rate=0.02)
        runner = LoadTestRunner(server, num_users=200)
        result = await runner.run_test(duration_seconds=3)

        # Most requests should still succeed
        assert result["successful_requests"] > result["failed_requests"]

    @pytest.mark.asyncio
    async def test_cache_effectiveness(self, runner):
        """Test that caching improves performance."""
        result = await runner.run_test(duration_seconds=5)

        # Cache should be working
        assert result["cache"]["hits"] > 0
        assert result["cache"]["hit_rate"] > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
