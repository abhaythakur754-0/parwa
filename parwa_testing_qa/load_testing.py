"""
Week 59 - Builder 4: Load Testing Module
Load generator, stress tester, and capacity testing
"""

import time
import threading
import random
import statistics
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class LoadPattern(Enum):
    """Load patterns"""
    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    SPIKE = "spike"
    WAVE = "wave"
    RANDOM = "random"


class TestState(Enum):
    """Test state"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class VirtualUser:
    """Virtual user representation"""
    id: int
    state: str = "idle"
    iterations: int = 0
    errors: int = 0
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)


@dataclass
class LoadTestResult:
    """Load test result"""
    test_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0
    p95_latency_ms: float = 0
    p99_latency_ms: float = 0
    requests_per_second: float = 0
    duration_seconds: float = 0
    state: TestState = TestState.IDLE
    errors: List[str] = field(default_factory=list)


@dataclass
class StressTestResult:
    """Stress test result"""
    test_id: str
    breaking_point: int = 0
    max_concurrent: int = 0
    error_rate_at_break: float = 0
    latency_at_break: float = 0
    duration_seconds: float = 0
    state: TestState = TestState.IDLE


class LoadGenerator:
    """
    Load generator with virtual users, ramp-up, and patterns
    """

    def __init__(self):
        self.virtual_users: Dict[int, VirtualUser] = {}
        self.results: Dict[str, LoadTestResult] = {}
        self.state = TestState.IDLE
        self.lock = threading.Lock()
        self.latencies: List[float] = []
        self.current_vus = 0
        self.target_vus = 0
        self.stop_flag = False

    def create_virtual_users(self, count: int) -> List[VirtualUser]:
        """Create virtual users"""
        users = []
        with self.lock:
            for i in range(count):
                user_id = len(self.virtual_users) + i + 1
                user = VirtualUser(id=user_id)
                self.virtual_users[user_id] = user
                users.append(user)
        return users

    def set_load_pattern(self, pattern: LoadPattern,
                         duration_seconds: int = 60,
                         max_users: int = 100) -> None:
        """Set load pattern parameters"""
        self.pattern = pattern
        self.pattern_duration = duration_seconds
        self.max_users = max_users

    def _calculate_vus_for_time(self, elapsed: float) -> int:
        """Calculate VUs for current time based on pattern"""
        if self.pattern == LoadPattern.CONSTANT:
            return self.max_users

        elif self.pattern == LoadPattern.RAMP_UP:
            progress = min(1.0, elapsed / self.pattern_duration)
            return int(self.max_users * progress)

        elif self.pattern == LoadPattern.SPIKE:
            if elapsed < self.pattern_duration * 0.3:
                return self.max_users
            elif elapsed < self.pattern_duration * 0.5:
                return self.max_users * 3
            else:
                return self.max_users

        elif self.pattern == LoadPattern.WAVE:
            wave = math.sin(elapsed * 2 * math.pi / self.pattern_duration)
            return int(self.max_users * (0.5 + 0.5 * wave))

        else:  # RANDOM
            return random.randint(1, self.max_users)

    def run_test(self, test_func: Callable,
                 duration_seconds: int = 60,
                 target_rps: int = 100) -> LoadTestResult:
        """Run a load test"""
        test_id = f"load-{int(time.time())}"
        result = LoadTestResult(test_id=test_id, state=TestState.RUNNING)

        self.stop_flag = False
        start_time = time.time()
        latencies = []
        requests = 0
        errors = 0

        def worker():
            nonlocal requests, errors
            while not self.stop_flag and (time.time() - start_time) < duration_seconds:
                try:
                    req_start = time.perf_counter()
                    test_func()
                    req_end = time.perf_counter()
                    latencies.append((req_end - req_start) * 1000)
                    requests += 1
                except Exception as e:
                    errors += 1
                    result.errors.append(str(e))

        # Start worker threads
        threads = []
        for _ in range(min(target_rps, 100)):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        # Run for duration
        time.sleep(duration_seconds)
        self.stop_flag = True

        for t in threads:
            t.join(timeout=1)

        # Calculate results
        actual_duration = time.time() - start_time
        result.total_requests = requests
        result.successful_requests = requests - errors
        result.failed_requests = errors
        result.duration_seconds = actual_duration

        if latencies:
            sorted_latencies = sorted(latencies)
            result.avg_latency_ms = statistics.mean(latencies)
            result.p95_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            result.p99_latency_ms = sorted_latencies[int(len(sorted_latencies) * 0.99)]

        if actual_duration > 0:
            result.requests_per_second = requests / actual_duration

        result.state = TestState.COMPLETED

        with self.lock:
            self.results[test_id] = result
            self.latencies = latencies

        return result

    def stop_test(self) -> None:
        """Stop running test"""
        self.stop_flag = True

    def get_result(self, test_id: str) -> Optional[LoadTestResult]:
        """Get test result"""
        return self.results.get(test_id)


class StressTester:
    """
    Stress tester for finding breaking points
    """

    def __init__(self):
        self.results: Dict[str, StressTestResult] = {}
        self.lock = threading.Lock()

    def run_stress_test(self, test_func: Callable,
                        initial_load: int = 10,
                        increment: int = 10,
                        max_load: int = 1000,
                        duration_per_step: int = 30) -> StressTestResult:
        """Run stress test to find breaking point"""
        test_id = f"stress-{int(time.time())}"
        result = StressTestResult(test_id=test_id, state=TestState.RUNNING)

        current_load = initial_load
        breaking_point = 0
        max_successful = 0

        while current_load <= max_load:
            errors = 0
            latencies = []
            stop_flag = threading.Event()

            def worker():
                while not stop_flag.is_set():
                    try:
                        start = time.perf_counter()
                        test_func()
                        latencies.append((time.perf_counter() - start) * 1000)
                    except Exception:
                        nonlocal errors
                        errors += 1

            threads = []
            for _ in range(current_load):
                t = threading.Thread(target=worker, daemon=True)
                t.start()
                threads.append(t)

            time.sleep(duration_per_step)
            stop_flag.set()

            for t in threads:
                t.join(timeout=1)

            error_rate = errors / (errors + len(latencies)) if latencies else 1

            if error_rate < 0.1:  # Less than 10% errors
                max_successful = current_load
            else:
                breaking_point = current_load
                result.error_rate_at_break = error_rate
                if latencies:
                    result.latency_at_break = statistics.mean(latencies)
                break

            current_load += increment

        result.breaking_point = breaking_point
        result.max_concurrent = max_successful
        result.duration_seconds = duration_per_step * ((current_load - initial_load) // increment)
        result.state = TestState.COMPLETED

        with self.lock:
            self.results[test_id] = result

        return result

    def get_result(self, test_id: str) -> Optional[StressTestResult]:
        """Get stress test result"""
        return self.results.get(test_id)


class CapacityTester:
    """
    Capacity tester for limits and scaling
    """

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def test_capacity(self, test_func: Callable,
                      target_rps: int,
                      duration_seconds: int = 60,
                      sla_latency_ms: float = 500,
                      sla_error_rate: float = 0.01) -> Dict[str, Any]:
        """Test capacity against SLA"""
        test_id = f"capacity-{int(time.time())}"

        latencies = []
        errors = 0
        successes = 0
        stop_flag = threading.Event()

        def worker():
            nonlocal errors, successes
            while not stop_flag.is_set():
                try:
                    start = time.perf_counter()
                    test_func()
                    latencies.append((time.perf_counter() - start) * 1000)
                    successes += 1
                except Exception:
                    errors += 1

        threads = []
        for _ in range(min(target_rps, 200)):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        time.sleep(duration_seconds)
        stop_flag.set()

        for t in threads:
            t.join(timeout=1)

        # Calculate metrics
        total = successes + errors
        actual_rps = total / duration_seconds if duration_seconds > 0 else 0
        error_rate = errors / total if total > 0 else 1
        avg_latency = statistics.mean(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        result = {
            "test_id": test_id,
            "target_rps": target_rps,
            "actual_rps": actual_rps,
            "total_requests": total,
            "errors": errors,
            "error_rate": error_rate,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "sla_met": error_rate <= sla_error_rate and p95_latency <= sla_latency_ms,
            "sla_latency_ms": sla_latency_ms,
            "sla_error_rate": sla_error_rate,
            "duration_seconds": duration_seconds
        }

        with self.lock:
            self.results[test_id] = result

        return result

    def find_max_capacity(self, test_func: Callable,
                          start_rps: int = 10,
                          max_rps: int = 1000,
                          step: int = 50,
                          sla_latency_ms: float = 500,
                          sla_error_rate: float = 0.01) -> Dict[str, Any]:
        """Find maximum capacity that meets SLA"""
        current_rps = start_rps
        last_successful = start_rps
        last_successful_result = None

        while current_rps <= max_rps:
            result = self.test_capacity(
                test_func,
                current_rps,
                duration_seconds=30,
                sla_latency_ms=sla_latency_ms,
                sla_error_rate=sla_error_rate
            )

            if result["sla_met"]:
                last_successful = current_rps
                last_successful_result = result
                current_rps += step
            else:
                break

        return {
            "max_capacity_rps": last_successful,
            "result": last_successful_result
        }

    def get_result(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get capacity test result"""
        return self.results.get(test_id)


import math
