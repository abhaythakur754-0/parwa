"""
Load Tester Module - Week 52, Builder 4
Load testing framework for performance validation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple
import asyncio
import logging
import random
import statistics
import time
import uuid

logger = logging.getLogger(__name__)


class LoadTestStatus(Enum):
    """Load test status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LoadPattern(Enum):
    """Load pattern type"""
    CONSTANT = "constant"
    RAMP_UP = "ramp_up"
    SPIKE = "spike"
    WAVE = "wave"
    RANDOM = "random"


@dataclass
class LoadTestConfig:
    """Load test configuration"""
    name: str
    target_url: str
    duration_seconds: int = 60
    concurrent_users: int = 10
    ramp_up_seconds: int = 10
    pattern: LoadPattern = LoadPattern.CONSTANT
    request_timeout: float = 30.0
    think_time_min: float = 0.0
    think_time_max: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    method: str = "GET"


@dataclass
class RequestResult:
    """Single request result"""
    request_id: str
    timestamp: datetime
    duration_ms: float
    status_code: int
    success: bool
    error: Optional[str] = None
    response_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadTestMetrics:
    """Aggregated load test metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    requests_per_second: float = 0.0
    errors_per_second: float = 0.0
    total_bytes: int = 0
    bytes_per_second: float = 0.0
    error_rate: float = 0.0


@dataclass
class LoadTestResult:
    """Complete load test result"""
    test_id: str
    config: LoadTestConfig
    status: LoadTestStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metrics: LoadTestMetrics = field(default_factory=LoadTestMetrics)
    requests: List[RequestResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class RequestGenerator:
    """
    Generates requests based on load pattern.
    """

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self._current_users = 0

    def get_current_load(self, elapsed_seconds: float) -> int:
        """Calculate current load based on pattern and elapsed time"""
        if elapsed_seconds < self.config.ramp_up_seconds:
            # During ramp-up
            progress = elapsed_seconds / self.config.ramp_up_seconds
            base_load = int(self.config.concurrent_users * progress)
        else:
            base_load = self.config.concurrent_users

        if self.config.pattern == LoadPattern.CONSTANT:
            return base_load

        elif self.config.pattern == LoadPattern.RAMP_UP:
            # Continuous ramp-up throughout test
            progress = elapsed_seconds / self.config.duration_seconds
            return int(self.config.concurrent_users * progress)

        elif self.config.pattern == LoadPattern.SPIKE:
            # Spike at the middle
            midpoint = self.config.duration_seconds / 2
            spike_window = self.config.duration_seconds / 10
            if abs(elapsed_seconds - midpoint) < spike_window:
                return base_load * 3  # Triple load during spike
            return base_load

        elif self.config.pattern == LoadPattern.WAVE:
            # Sinusoidal wave pattern
            import math
            wave = math.sin(elapsed_seconds * 2 * math.pi / self.config.duration_seconds)
            return int(base_load * (0.5 + 0.5 * wave))

        elif self.config.pattern == LoadPattern.RANDOM:
            # Random fluctuation
            variation = random.uniform(0.5, 1.5)
            return int(base_load * variation)

        return base_load

    def get_think_time(self) -> float:
        """Get random think time between requests"""
        if self.config.think_time_min >= self.config.think_time_max:
            return self.config.think_time_min
        return random.uniform(self.config.think_time_min, self.config.think_time_max)


class MetricsAggregator:
    """
    Aggregates metrics from request results.
    """

    def __init__(self):
        self.results: List[RequestResult] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None

    def add_result(self, result: RequestResult) -> None:
        """Add a request result"""
        self.results.append(result)
        if self._start_time is None or result.timestamp < self._start_time:
            self._start_time = result.timestamp
        if self._end_time is None or result.timestamp > self._end_time:
            self._end_time = result.timestamp

    def get_metrics(self) -> LoadTestMetrics:
        """Calculate aggregated metrics"""
        if not self.results:
            return LoadTestMetrics()

        durations = [r.duration_ms for r in self.results]
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        total_bytes = sum(r.response_size for r in self.results)

        # Calculate duration in seconds
        duration_seconds = 0
        if self._start_time and self._end_time:
            duration_seconds = (self._end_time - self._start_time).total_seconds()

        metrics = LoadTestMetrics(
            total_requests=len(self.results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            avg_latency_ms=statistics.mean(durations) if durations else 0,
            min_latency_ms=min(durations) if durations else 0,
            max_latency_ms=max(durations) if durations else 0,
            p50_latency_ms=self._percentile(durations, 50),
            p95_latency_ms=self._percentile(durations, 95),
            p99_latency_ms=self._percentile(durations, 99),
            requests_per_second=len(self.results) / duration_seconds if duration_seconds > 0 else 0,
            errors_per_second=len(failed) / duration_seconds if duration_seconds > 0 else 0,
            total_bytes=total_bytes,
            bytes_per_second=total_bytes / duration_seconds if duration_seconds > 0 else 0,
            error_rate=len(failed) / len(self.results) * 100 if self.results else 0,
        )

        return metrics

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        lower = int(index)
        upper = lower + 1
        if upper >= len(sorted_values):
            return sorted_values[-1]
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


class LoadTester:
    """
    Main load testing engine.
    """

    def __init__(self):
        self.tests: Dict[str, LoadTestResult] = {}
        self._running_tests: Dict[str, bool] = {}

    async def run_test(
        self,
        config: LoadTestConfig,
        request_handler: Optional[Callable] = None,
    ) -> LoadTestResult:
        """Run a load test"""
        test_id = str(uuid.uuid4())[:8]
        result = LoadTestResult(
            test_id=test_id,
            config=config,
            status=LoadTestStatus.PENDING,
        )
        self.tests[test_id] = result
        self._running_tests[test_id] = True

        generator = RequestGenerator(config)
        aggregator = MetricsAggregator()

        result.status = LoadTestStatus.RUNNING
        result.start_time = datetime.utcnow()

        try:
            # Create virtual users
            tasks = []
            start_time = time.time()

            async def virtual_user(user_id: int):
                """Simulate a virtual user"""
                while self._running_tests.get(test_id, False):
                    elapsed = time.time() - start_time
                    if elapsed >= config.duration_seconds:
                        break

                    # Check if this user should be active based on load pattern
                    current_load = generator.get_current_load(elapsed)
                    if user_id >= current_load:
                        await asyncio.sleep(0.1)
                        continue

                    # Make request
                    request_id = f"{test_id}-{user_id}-{time.time()}"
                    request_start = time.time()

                    try:
                        if request_handler:
                            # Use custom handler
                            response = await request_handler(config)
                            status_code = response.get("status_code", 200)
                            success = response.get("success", True)
                            error = response.get("error")
                            response_size = response.get("size", 0)
                        else:
                            # Simulate request
                            await asyncio.sleep(random.uniform(0.01, 0.1))
                            status_code = random.choices([200, 500], weights=[95, 5])[0]
                            success = status_code == 200
                            error = None if success else "Simulated error"
                            response_size = random.randint(100, 1000)

                        duration_ms = (time.time() - request_start) * 1000

                        req_result = RequestResult(
                            request_id=request_id,
                            timestamp=datetime.utcnow(),
                            duration_ms=duration_ms,
                            status_code=status_code,
                            success=success,
                            error=error,
                            response_size=response_size,
                        )
                        aggregator.add_result(req_result)

                    except Exception as e:
                        req_result = RequestResult(
                            request_id=request_id,
                            timestamp=datetime.utcnow(),
                            duration_ms=(time.time() - request_start) * 1000,
                            status_code=0,
                            success=False,
                            error=str(e),
                        )
                        aggregator.add_result(req_result)
                        result.errors.append(str(e))

                    # Think time
                    think_time = generator.get_think_time()
                    if think_time > 0:
                        await asyncio.sleep(think_time)

            # Start virtual users
            for i in range(config.concurrent_users):
                tasks.append(asyncio.create_task(virtual_user(i)))

            # Wait for test completion
            await asyncio.gather(*tasks, return_exceptions=True)

            result.status = LoadTestStatus.COMPLETED

        except Exception as e:
            result.status = LoadTestStatus.FAILED
            result.errors.append(str(e))
            logger.error(f"Load test {test_id} failed: {e}")

        finally:
            result.end_time = datetime.utcnow()
            result.metrics = aggregator.get_metrics()
            result.requests = aggregator.results
            self._running_tests[test_id] = False

        return result

    def stop_test(self, test_id: str) -> bool:
        """Stop a running test"""
        if test_id in self._running_tests:
            self._running_tests[test_id] = False
            return True
        return False

    def get_test(self, test_id: str) -> Optional[LoadTestResult]:
        """Get test result by ID"""
        return self.tests.get(test_id)

    def get_all_tests(self) -> List[LoadTestResult]:
        """Get all test results"""
        return list(self.tests.values())

    def delete_test(self, test_id: str) -> bool:
        """Delete a test result"""
        if test_id in self.tests:
            del self.tests[test_id]
            if test_id in self._running_tests:
                del self._running_tests[test_id]
            return True
        return False


class LoadTestScenario:
    """
    Predefined load test scenarios.
    """

    @staticmethod
    def smoke_test(target_url: str) -> LoadTestConfig:
        """Basic smoke test"""
        return LoadTestConfig(
            name="Smoke Test",
            target_url=target_url,
            duration_seconds=30,
            concurrent_users=5,
            ramp_up_seconds=5,
        )

    @staticmethod
    def load_test(target_url: str) -> LoadTestConfig:
        """Standard load test"""
        return LoadTestConfig(
            name="Load Test",
            target_url=target_url,
            duration_seconds=300,
            concurrent_users=50,
            ramp_up_seconds=30,
        )

    @staticmethod
    def stress_test(target_url: str) -> LoadTestConfig:
        """Stress test"""
        return LoadTestConfig(
            name="Stress Test",
            target_url=target_url,
            duration_seconds=600,
            concurrent_users=200,
            ramp_up_seconds=60,
            pattern=LoadPattern.RAMP_UP,
        )

    @staticmethod
    def spike_test(target_url: str) -> LoadTestConfig:
        """Spike test"""
        return LoadTestConfig(
            name="Spike Test",
            target_url=target_url,
            duration_seconds=300,
            concurrent_users=50,
            ramp_up_seconds=10,
            pattern=LoadPattern.SPIKE,
        )

    @staticmethod
    def soak_test(target_url: str) -> LoadTestConfig:
        """Soak/endurance test"""
        return LoadTestConfig(
            name="Soak Test",
            target_url=target_url,
            duration_seconds=3600,  # 1 hour
            concurrent_users=30,
            ramp_up_seconds=60,
        )
