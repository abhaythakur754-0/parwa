"""
P95 Latency Benchmark Test for PARWA.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from dataclasses import dataclass, field
import statistics


@dataclass
class LatencyResult:
    """Latency test result."""
    endpoint: str
    latencies: List[float] = field(default_factory=list)
    
    def p50(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0
    
    def p95(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]
    
    def p99(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]


class P95LatencyBenchmark:
    """
    Benchmark for P95 latency measurement.
    
    Target: P95 < 300ms for all critical endpoints.
    """
    
    TARGET_P95_MS = 300
    
    def __init__(self):
        self.results: Dict[str, LatencyResult] = {}
    
    async def measure_endpoint(
        self,
        name: str,
        request_func,
        iterations: int = 100
    ) -> LatencyResult:
        """
        Measure latency for an endpoint.
        
        Args:
            name: Endpoint name
            request_func: Async function that makes the request
            iterations: Number of iterations
            
        Returns:
            LatencyResult
        """
        result = LatencyResult(endpoint=name)
        
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                await request_func()
            except Exception:
                pass  # Ignore errors for latency test
            elapsed_ms = (time.perf_counter() - start) * 1000
            result.latencies.append(elapsed_ms)
        
        self.results[name] = result
        return result
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate benchmark report."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_p95_ms": self.TARGET_P95_MS,
            "endpoints": {}
        }
        
        all_pass = True
        for name, result in self.results.items():
            p95 = result.p95()
            passed = p95 < self.TARGET_P95_MS
            if not passed:
                all_pass = False
            
            report["endpoints"][name] = {
                "p50_ms": round(result.p50(), 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(result.p99(), 2),
                "samples": len(result.latencies),
                "target_met": passed
            }
        
        report["all_targets_met"] = all_pass
        return report


async def run_latency_benchmark():
    """Run the full latency benchmark suite."""
    benchmark = P95LatencyBenchmark()
    
    # Mock request functions for testing
    async def mock_ticket_create():
        await asyncio.sleep(0.05)  # 50ms mock latency
    
    async def mock_ticket_list():
        await asyncio.sleep(0.03)
    
    async def mock_refund_request():
        await asyncio.sleep(0.08)
    
    async def mock_kb_search():
        await asyncio.sleep(0.04)
    
    async def mock_analytics_query():
        await asyncio.sleep(0.10)
    
    # Run benchmarks
    await benchmark.measure_endpoint("ticket_create", mock_ticket_create)
    await benchmark.measure_endpoint("ticket_list", mock_ticket_list)
    await benchmark.measure_endpoint("refund_request", mock_refund_request)
    await benchmark.measure_endpoint("kb_search", mock_kb_search)
    await benchmark.measure_endpoint("analytics_query", mock_analytics_query)
    
    return benchmark.generate_report()


if __name__ == "__main__":
    report = asyncio.run(run_latency_benchmark())
    print(f"Target P95: {report['target_p95_ms']}ms")
    print(f"All targets met: {report['all_targets_met']}")
    for endpoint, stats in report["endpoints"].items():
        print(f"  {endpoint}: P95={stats['p95_ms']}ms ({'✅' if stats['target_met'] else '❌'})")
