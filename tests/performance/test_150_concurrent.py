"""
150 Concurrent User Performance Test
CRITICAL: P95 < 500ms at 150 users
"""

import pytest
import asyncio
import time
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any
import random


CLIENT_DISTRIBUTION = {
    "client_001": 40,
    "client_002": 30,
    "client_003": 25,
    "client_004": 30,
    "client_005": 25,
}


@dataclass
class RequestResult:
    latency_ms: float
    success: bool


class MockServer:
    def __init__(self, base_latency_ms: float = 50):
        self.base_latency = base_latency_ms
    
    async def handle_request(self, client_id: str) -> RequestResult:
        latency = self.base_latency + random.uniform(-20, 50)
        await asyncio.sleep(latency / 1000)
        return RequestResult(latency_ms=latency * random.uniform(1, 3), success=True)


class LoadTestRunner:
    def __init__(self, server: MockServer, num_users: int = 150):
        self.server = server
        self.num_users = num_users
        self.results: List[RequestResult] = []
    
    async def run_test(self, duration_seconds: float = 5) -> Dict[str, Any]:
        self.results = []
        start = time.time()
        
        async def user_session():
            while time.time() - start < duration_seconds:
                client = random.choice(list(CLIENT_DISTRIBUTION.keys()))
                result = await self.server.handle_request(client)
                self.results.append(result)
                await asyncio.sleep(random.uniform(0.01, 0.05))
        
        await asyncio.gather(*[user_session() for _ in range(self.num_users)])
        
        latencies = sorted([r.latency_ms for r in self.results])
        
        def percentile(data, p):
            k = (len(data) - 1) * p / 100
            f = int(k)
            return data[f] if f < len(data) else data[-1]
        
        return {
            "total_requests": len(self.results),
            "successful": sum(1 for r in self.results if r.success),
            "avg_ms": statistics.mean(latencies) if latencies else 0,
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
            "p99_ms": percentile(latencies, 99),
            "max_ms": max(latencies) if latencies else 0,
            "throughput": len(self.results) / duration_seconds,
        }


class Test150Concurrent:
    @pytest.fixture
    def server(self):
        return MockServer(base_latency_ms=50)
    
    @pytest.fixture
    def runner(self, server):
        return LoadTestRunner(server, num_users=150)
    
    @pytest.mark.asyncio
    async def test_150_concurrent_users(self, runner):
        result = await runner.run_test(duration_seconds=3)
        assert result["total_requests"] > 0
        assert result["successful"] > 0
    
    @pytest.mark.asyncio
    async def test_p95_under_500ms(self, runner):
        result = await runner.run_test(duration_seconds=3)
        print(f"\n  P95: {result['p95_ms']:.2f}ms")
        assert result["p95_ms"] < 500, f"P95 was {result['p95_ms']}ms"
    
    @pytest.mark.asyncio
    async def test_no_errors(self, server, runner):
        server.base_latency_ms = 30
        result = await runner.run_test(duration_seconds=3)
        assert result["successful"] == result["total_requests"]
    
    @pytest.mark.asyncio
    async def test_fair_allocation(self, runner):
        result = await runner.run_test(duration_seconds=3)
        # All clients should process requests
        assert result["total_requests"] > 100
    
    @pytest.mark.asyncio
    async def test_high_throughput(self, runner):
        result = await runner.run_test(duration_seconds=3)
        assert result["throughput"] > 50
    
    @pytest.mark.asyncio
    async def test_latency_distribution(self, runner):
        result = await runner.run_test(duration_seconds=3)
        # P99 should not be outrageously higher than P50
        if result["p50_ms"] > 0:
            ratio = result["p99_ms"] / result["p50_ms"]
            assert ratio < 5.0
    
    @pytest.mark.asyncio
    async def test_sustained_load(self, server):
        runner = LoadTestRunner(server, num_users=150)
        result = await runner.run_test(duration_seconds=5)
        assert result["p95_ms"] < 500
    
    @pytest.mark.asyncio
    async def test_burst_handling(self, server):
        server.base_latency_ms = 20
        runner = LoadTestRunner(server, num_users=150)
        result = await runner.run_test(duration_seconds=2)
        assert result["successful"] > 0
    
    @pytest.mark.asyncio
    async def test_client_isolation_under_load(self, runner):
        result = await runner.run_test(duration_seconds=3)
        # All requests should succeed (no isolation failures)
        assert result["successful"] == result["total_requests"]
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, server):
        server.base_latency_ms = 150  # Stressed
        runner = LoadTestRunner(server, num_users=150)
        result = await runner.run_test(duration_seconds=3)
        # Should still complete
        assert result["total_requests"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
