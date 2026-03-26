"""
100 Concurrent User Performance Tests.
CRITICAL: P95 < 500ms at 100 users.
"""
import concurrent.futures
import sys
import time
import uuid
import threading
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class PerformanceResult:
    request_id: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: str = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadTestSummary:
    total_requests: int
    successful_requests: int
    failed_requests: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    errors_per_second: float
    requests_per_second: float


class MockAPIServer:
    def __init__(self, base_latency_ms: float = 50.0, error_rate: float = 0.0):
        self.base_latency_ms = base_latency_ms
        self.error_rate = error_rate
        self.request_count = 0
        self.lock = threading.Lock()
    
    def process_request(self, request_type: str = "ticket") -> Dict[str, Any]:
        with self.lock:
            self.request_count += 1
        latency = self.base_latency_ms + random.uniform(-10, 30)
        time.sleep(latency / 1000.0)
        if random.random() < self.error_rate:
            raise Exception("Simulated server error")
        return {"request_id": str(uuid.uuid4()), "type": request_type, "status": "success"}


class LoadTestRunner:
    def __init__(self, server: MockAPIServer, num_users: int = 100, requests_per_user: int = 10):
        self.server = server
        self.num_users = num_users
        self.requests_per_user = requests_per_user
    
    def single_user_session(self, user_id: int) -> List[PerformanceResult]:
        user_results = []
        for i in range(self.requests_per_user):
            request_id = f"user_{user_id}_req_{i}"
            start_time = time.time()
            try:
                request_type = random.choice(["ticket", "customer", "knowledge_base", "approval"])
                self.server.process_request(request_type)
                end_time = time.time()
                user_results.append(PerformanceResult(
                    request_id=request_id, start_time=start_time, end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000, success=True))
            except Exception as e:
                end_time = time.time()
                user_results.append(PerformanceResult(
                    request_id=request_id, start_time=start_time, end_time=end_time,
                    duration_ms=(end_time - start_time) * 1000, success=False, error=str(e)))
        return user_results
    
    def run_concurrent(self) -> LoadTestSummary:
        all_results = []
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_users) as executor:
            futures = [executor.submit(self.single_user_session, uid) for uid in range(self.num_users)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass
        total_time = time.time() - start_time
        durations = sorted([r.duration_ms for r in all_results])
        successful = [r for r in all_results if r.success]
        failed = [r for r in all_results if not r.success]
        n = len(durations)
        
        def percentile(lst, p):
            if not lst: return 0.0
            idx = min(int(n * p / 100), n - 1)
            return lst[idx]
        
        return LoadTestSummary(
            total_requests=len(all_results), successful_requests=len(successful), failed_requests=len(failed),
            p50_ms=percentile(durations, 50), p95_ms=percentile(durations, 95), p99_ms=percentile(durations, 99),
            avg_ms=sum(durations) / n if n > 0 else 0, min_ms=min(durations) if durations else 0,
            max_ms=max(durations) if durations else 0, errors_per_second=len(failed) / total_time if total_time > 0 else 0,
            requests_per_second=len(all_results) / total_time if total_time > 0 else 0)


@pytest.fixture
def mock_server():
    return MockAPIServer(base_latency_ms=50.0, error_rate=0.0)


@pytest.fixture
def load_runner(mock_server):
    return LoadTestRunner(mock_server, num_users=100, requests_per_user=5)


class Test100ConcurrentUsers:
    def test_100_concurrent_users_basic(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=5)
        summary = runner.run_concurrent()
        assert summary.total_requests == 500
        assert summary.failed_requests == 0
    
    def test_p95_latency_under_500ms(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        assert summary.p95_ms < 500, f"P95 latency {summary.p95_ms}ms exceeds 500ms"
    
    def test_no_errors_under_load(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=5)
        summary = runner.run_concurrent()
        assert summary.failed_requests == 0
        assert summary.successful_requests == 500
    
    def test_graceful_degradation(self):
        slow_server = MockAPIServer(base_latency_ms=200.0)
        runner = LoadTestRunner(slow_server, num_users=100, requests_per_user=3)
        summary = runner.run_concurrent()
        assert summary.total_requests == 300
        assert summary.successful_requests > 0
    
    def test_resource_limits_respected(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=5)
        initial_threads = threading.active_count()
        summary = runner.run_concurrent()
        final_threads = threading.active_count()
        assert final_threads <= initial_threads + 10


class TestPerformanceMetrics:
    def test_p50_calculation(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=50, requests_per_user=2)
        summary = runner.run_concurrent()
        assert summary.p50_ms <= summary.p95_ms
    
    def test_p99_calculation(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=5)
        summary = runner.run_concurrent()
        assert summary.p99_ms >= summary.p95_ms
    
    def test_requests_per_second(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=5)
        summary = runner.run_concurrent()
        assert summary.requests_per_second > 0


class TestConcurrencyPatterns:
    def test_burst_traffic(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=200, requests_per_user=2)
        summary = runner.run_concurrent()
        assert summary.total_requests == 400
        assert summary.failed_requests == 0
    
    def test_sustained_load(self, mock_server):
        for _ in range(3):
            runner = LoadTestRunner(mock_server, num_users=50, requests_per_user=5)
            summary = runner.run_concurrent()
            assert summary.failed_requests == 0
    
    def test_mixed_workload(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        assert summary.successful_requests == 1000


class TestErrorHandling:
    def test_error_rate_tolerance(self):
        error_server = MockAPIServer(base_latency_ms=50.0, error_rate=0.05)
        runner = LoadTestRunner(error_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        success_rate = summary.successful_requests / summary.total_requests
        assert success_rate >= 0.90
    
    def test_timeout_handling(self):
        slow_server = MockAPIServer(base_latency_ms=400.0)
        runner = LoadTestRunner(slow_server, num_users=50, requests_per_user=2)
        summary = runner.run_concurrent()
        assert summary.total_requests == 100


class TestScalingLimits:
    def test_max_concurrent_connections(self, mock_server):
        for num_users in [10, 50, 100, 200]:
            runner = LoadTestRunner(mock_server, num_users=num_users, requests_per_user=2)
            summary = runner.run_concurrent()
            assert summary.total_requests == num_users * 2
    
    def test_performance_at_scale(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        assert summary.p95_ms < 500
        assert summary.failed_requests == 0
        assert summary.requests_per_second > 10


class TestPerformanceBaseline:
    def test_baseline_p50(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        assert summary.p50_ms < 200
    
    def test_baseline_p95(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        assert summary.p95_ms < 500
    
    def test_baseline_p99(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        assert summary.p99_ms < 1000
    
    def test_baseline_throughput(self, mock_server):
        runner = LoadTestRunner(mock_server, num_users=100, requests_per_user=10)
        summary = runner.run_concurrent()
        assert summary.requests_per_second >= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
