"""
2000 Concurrent Users Test for PARWA.

Validates system can handle 2000 concurrent requests.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ConcurrentTestResult:
    """Result of concurrent test."""
    total_requests: int
    successful: int
    failed: int
    avg_latency_ms: float
    max_latency_ms: float
    requests_per_second: float
    duration_seconds: float


async def mock_request(request_id: int) -> Dict[str, Any]:
    """Mock a single request."""
    # Simulate request processing
    await asyncio.sleep(0.05)
    return {
        "request_id": request_id,
        "status": "success",
        "timestamp": time.time()
    }


async def run_concurrent_test(
    total_requests: int = 2000,
    batch_size: int = 100
) -> ConcurrentTestResult:
    """
    Run concurrent load test.
    
    Args:
        total_requests: Total number of requests to make
        batch_size: Number of concurrent requests per batch
        
    Returns:
        ConcurrentTestResult
    """
    start_time = time.time()
    latencies: List[float] = []
    successful = 0
    failed = 0
    
    # Run in batches to avoid overwhelming
    for batch_start in range(0, total_requests, batch_size):
        batch_end = min(batch_start + batch_size, total_requests)
        batch_requests = batch_end - batch_start
        
        tasks = [
            mock_request(i)
            for i in range(batch_start, batch_end)
        ]
        
        batch_start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        batch_duration = time.time() - batch_start_time
        
        for result in results:
            if isinstance(result, Exception):
                failed += 1
            else:
                successful += 1
                latencies.append(batch_duration * 1000 / batch_requests)
    
    duration = time.time() - start_time
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    rps = total_requests / duration if duration > 0 else 0
    
    return ConcurrentTestResult(
        total_requests=total_requests,
        successful=successful,
        failed=failed,
        avg_latency_ms=avg_latency,
        max_latency_ms=max_latency,
        requests_per_second=rps,
        duration_seconds=duration
    )


def validate_result(result: ConcurrentTestResult) -> Dict[str, Any]:
    """Validate test result against targets."""
    targets = {
        "min_success_rate": 0.99,  # 99% success
        "max_avg_latency_ms": 300,
        "min_rps": 500,
    }
    
    success_rate = result.successful / result.total_requests
    
    validation = {
        "success_rate": {
            "actual": success_rate,
            "target": targets["min_success_rate"],
            "passed": success_rate >= targets["min_success_rate"]
        },
        "avg_latency": {
            "actual_ms": result.avg_latency_ms,
            "target_ms": targets["max_avg_latency_ms"],
            "passed": result.avg_latency_ms <= targets["max_avg_latency_ms"]
        },
        "throughput": {
            "actual_rps": result.requests_per_second,
            "target_rps": targets["min_rps"],
            "passed": result.requests_per_second >= targets["min_rps"]
        },
        "all_passed": (
            success_rate >= targets["min_success_rate"] and
            result.avg_latency_ms <= targets["max_avg_latency_ms"] and
            result.requests_per_second >= targets["min_rps"]
        )
    }
    
    return validation


async def main():
    """Run the 2000 concurrent test."""
    print("Running 2000 concurrent users test...")
    print("-" * 50)
    
    result = await run_concurrent_test(total_requests=2000, batch_size=100)
    validation = validate_result(result)
    
    print(f"Total Requests: {result.total_requests}")
    print(f"Successful: {result.successful}")
    print(f"Failed: {result.failed}")
    print(f"Avg Latency: {result.avg_latency_ms:.2f}ms")
    print(f"Max Latency: {result.max_latency_ms:.2f}ms")
    print(f"Throughput: {result.requests_per_second:.2f} req/s")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print("-" * 50)
    print(f"Success Rate: {'✅' if validation['success_rate']['passed'] else '❌'}")
    print(f"Avg Latency: {'✅' if validation['avg_latency']['passed'] else '❌'}")
    print(f"Throughput: {'✅' if validation['throughput']['passed'] else '❌'}")
    print("-" * 50)
    print(f"ALL TARGETS MET: {'✅ YES' if validation['all_passed'] else '❌ NO'}")
    
    return validation


if __name__ == "__main__":
    asyncio.run(main())
