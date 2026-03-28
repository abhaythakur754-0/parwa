"""
Stress Tester Module - Week 52, Builder 4
Stress testing engine for breaking point analysis
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import asyncio
import logging
import random
import time
import uuid

logger = logging.getLogger(__name__)


class StressTestType(Enum):
    """Type of stress test"""
    BREAKPOINT = "breakpoint"  # Find breaking point
    SATURATION = "saturation"  # Find saturation point
    ENDURANCE = "endurance"  # Long-running stress
    MEMORY = "memory"  # Memory stress
    CPU = "cpu"  # CPU stress
    CONNECTION = "connection"  # Connection limit stress


class StressTestStatus(Enum):
    """Stress test status"""
    PENDING = "pending"
    WARMUP = "warmup"
    STRESSING = "stressing"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StressTestConfig:
    """Stress test configuration"""
    name: str
    test_type: StressTestType
    target: str
    initial_load: int = 10
    max_load: int = 1000
    increment: int = 10
    increment_interval: int = 30  # seconds
    failure_threshold: float = 5.0  # error rate %
    recovery_timeout: int = 60  # seconds
    warmup_duration: int = 60  # seconds
    cooldown_duration: int = 30  # seconds


@dataclass
class StressPoint:
    """Single stress test data point"""
    timestamp: datetime
    load_level: int
    error_rate: float
    avg_latency_ms: float
    throughput: float
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BreakingPoint:
    """Detected breaking point"""
    load_level: int
    error_rate: float
    latency_ms: float
    timestamp: datetime
    recovery_time: Optional[float] = None


@dataclass
class StressTestResult:
    """Complete stress test result"""
    test_id: str
    config: StressTestConfig
    status: StressTestStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    data_points: List[StressPoint] = field(default_factory=list)
    breaking_point: Optional[BreakingPoint] = None
    saturation_point: Optional[BreakingPoint] = None
    max_sustained_load: int = 0
    total_errors: int = 0
    recovery_successful: bool = False


class SystemMonitor:
    """
    Monitors system metrics during stress test.
    """

    def __init__(self):
        self.metrics: Dict[str, List[float]] = {
            "cpu": [],
            "memory": [],
            "connections": [],
            "latency": [],
        }

    def record(self, metric: str, value: float) -> None:
        """Record a metric value"""
        if metric in self.metrics:
            self.metrics[metric].append(value)

    def get_average(self, metric: str, window: int = 10) -> float:
        """Get average of recent values"""
        values = self.metrics.get(metric, [])
        if not values:
            return 0.0
        recent = values[-window:]
        return sum(recent) / len(recent)

    def get_trend(self, metric: str) -> str:
        """Get trend direction"""
        values = self.metrics.get(metric, [])
        if len(values) < 5:
            return "unknown"

        first_half = sum(values[:len(values)//2]) / (len(values)//2)
        second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

        if second_half > first_half * 1.1:
            return "increasing"
        elif second_half < first_half * 0.9:
            return "decreasing"
        return "stable"


class StressTester:
    """
    Main stress testing engine.
    """

    def __init__(self):
        self.tests: Dict[str, StressTestResult] = {}
        self._running_tests: Dict[str, bool] = {}
        self.monitor = SystemMonitor()

    async def run_test(
        self,
        config: StressTestConfig,
        load_handler: Optional[Callable] = None,
    ) -> StressTestResult:
        """Run a stress test"""
        test_id = str(uuid.uuid4())[:8]
        result = StressTestResult(
            test_id=test_id,
            config=config,
            status=StressTestStatus.PENDING,
        )
        self.tests[test_id] = result
        self._running_tests[test_id] = True

        result.start_time = datetime.utcnow()

        try:
            # Warmup phase
            result.status = StressTestStatus.WARMUP
            await self._run_phase(
                test_id, config, result, config.initial_load,
                config.warmup_duration, load_handler
            )

            if not self._running_tests.get(test_id, False):
                result.status = StressTestStatus.FAILED
                return result

            # Stress phase - gradually increase load
            result.status = StressTestStatus.STRESSING
            current_load = config.initial_load

            while current_load <= config.max_load:
                if not self._running_tests.get(test_id, False):
                    break

                # Run at current load level
                error_rate, avg_latency, throughput = await self._run_phase(
                    test_id, config, result, current_load,
                    config.increment_interval, load_handler
                )

                # Record data point
                point = StressPoint(
                    timestamp=datetime.utcnow(),
                    load_level=current_load,
                    error_rate=error_rate,
                    avg_latency_ms=avg_latency,
                    throughput=throughput,
                    success=error_rate < config.failure_threshold,
                )
                result.data_points.append(point)

                # Check for breaking point
                if error_rate >= config.failure_threshold:
                    result.breaking_point = BreakingPoint(
                        load_level=current_load,
                        error_rate=error_rate,
                        latency_ms=avg_latency,
                        timestamp=datetime.utcnow(),
                    )
                    logger.info(f"Breaking point detected at load {current_load}")
                    break

                # Check for saturation (throughput stops increasing)
                if len(result.data_points) > 1:
                    prev_point = result.data_points[-2]
                    if throughput <= prev_point.throughput * 1.01:
                        if result.saturation_point is None:
                            result.saturation_point = BreakingPoint(
                                load_level=current_load,
                                error_rate=error_rate,
                                latency_ms=avg_latency,
                                timestamp=datetime.utcnow(),
                            )
                            logger.info(f"Saturation point detected at load {current_load}")

                result.max_sustained_load = current_load
                current_load += config.increment

            # Cooldown/Recovery phase
            result.status = StressTestStatus.RECOVERING
            await self._run_phase(
                test_id, config, result, config.initial_load,
                config.cooldown_duration, load_handler
            )
            result.recovery_successful = True

            result.status = StressTestStatus.COMPLETED

        except Exception as e:
            result.status = StressTestStatus.FAILED
            logger.error(f"Stress test {test_id} failed: {e}")

        finally:
            result.end_time = datetime.utcnow()
            self._running_tests[test_id] = False

        return result

    async def _run_phase(
        self,
        test_id: str,
        config: StressTestConfig,
        result: StressTestResult,
        load_level: int,
        duration: int,
        load_handler: Optional[Callable],
    ) -> tuple:
        """Run a phase of the stress test"""
        errors = 0
        total_requests = 0
        latencies = []
        start_time = time.time()

        async def make_request():
            nonlocal errors, total_requests
            request_start = time.time()

            try:
                if load_handler:
                    response = await load_handler(config.target, load_level)
                    success = response.get("success", True)
                else:
                    # Simulate request with increasing error rate at high load
                    await asyncio.sleep(random.uniform(0.01, 0.05))
                    error_probability = min(0.5, load_level / config.max_load * 0.3)
                    success = random.random() > error_probability

                latency = (time.time() - request_start) * 1000
                latencies.append(latency)
                total_requests += 1

                if not success:
                    errors += 1
                    result.total_errors += 1

            except Exception as e:
                errors += 1
                result.total_errors += 1
                latencies.append((time.time() - request_start) * 1000)

        # Run requests for the duration
        while time.time() - start_time < duration:
            if not self._running_tests.get(test_id, False):
                break

            # Create concurrent requests based on load level
            tasks = []
            batch_size = min(load_level, 50)  # Limit concurrent tasks

            for _ in range(batch_size):
                tasks.append(asyncio.create_task(make_request()))

            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0.1)  # Small delay between batches

        # Calculate metrics
        error_rate = (errors / total_requests * 100) if total_requests > 0 else 0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        throughput = total_requests / duration if duration > 0 else 0

        return error_rate, avg_latency, throughput

    def stop_test(self, test_id: str) -> bool:
        """Stop a running test"""
        if test_id in self._running_tests:
            self._running_tests[test_id] = False
            return True
        return False

    def get_test(self, test_id: str) -> Optional[StressTestResult]:
        """Get test result by ID"""
        return self.tests.get(test_id)

    def get_all_tests(self) -> List[StressTestResult]:
        """Get all test results"""
        return list(self.tests.values())


class ResourceStressTester:
    """
    Specialized resource stress tester.
    """

    def __init__(self):
        self.tests: Dict[str, Dict[str, Any]] = {}

    async def stress_memory(
        self,
        target_mb: int,
        duration_seconds: int,
    ) -> Dict[str, Any]:
        """Perform memory stress test"""
        test_id = str(uuid.uuid4())[:8]
        result = {
            "test_id": test_id,
            "type": "memory",
            "target_mb": target_mb,
            "duration_seconds": duration_seconds,
            "status": "running",
            "peak_usage_mb": 0,
        }
        self.tests[test_id] = result

        try:
            # Simulate memory allocation
            allocated = []
            chunk_size = 1024 * 1024  # 1MB chunks

            for _ in range(target_mb):
                # Allocate memory
                allocated.append(bytearray(chunk_size))
                result["peak_usage_mb"] = len(allocated)

                if len(allocated) % 100 == 0:
                    await asyncio.sleep(0)  # Yield

            # Hold for duration
            await asyncio.sleep(duration_seconds)

            result["status"] = "completed"
            result["success"] = True

        except MemoryError:
            result["status"] = "failed"
            result["success"] = False
            result["error"] = "Out of memory"

        finally:
            # Release memory
            allocated.clear()

        return result

    async def stress_cpu(
        self,
        threads: int,
        duration_seconds: int,
    ) -> Dict[str, Any]:
        """Perform CPU stress test"""
        test_id = str(uuid.uuid4())[:8]
        result = {
            "test_id": test_id,
            "type": "cpu",
            "threads": threads,
            "duration_seconds": duration_seconds,
            "status": "running",
            "operations": 0,
        }
        self.tests[test_id] = result

        async def cpu_worker():
            """CPU-intensive worker"""
            count = 0
            start = time.time()
            while time.time() - start < duration_seconds:
                # CPU-intensive calculation
                _ = sum(i * i for i in range(10000))
                count += 1
                if count % 100 == 0:
                    await asyncio.sleep(0)  # Yield
            return count

        try:
            # Run workers
            tasks = [asyncio.create_task(cpu_worker()) for _ in range(threads)]
            counts = await asyncio.gather(*tasks)
            result["operations"] = sum(counts)
            result["status"] = "completed"
            result["success"] = True

        except Exception as e:
            result["status"] = "failed"
            result["success"] = False
            result["error"] = str(e)

        return result

    async def stress_connections(
        self,
        target: str,
        connection_count: int,
        duration_seconds: int,
    ) -> Dict[str, Any]:
        """Perform connection stress test"""
        test_id = str(uuid.uuid4())[:8]
        result = {
            "test_id": test_id,
            "type": "connection",
            "target": target,
            "connection_count": connection_count,
            "duration_seconds": duration_seconds,
            "status": "running",
            "active_connections": 0,
            "failed_connections": 0,
        }
        self.tests[test_id] = result

        async def hold_connection():
            """Simulate holding a connection"""
            try:
                # Simulate connection
                await asyncio.sleep(duration_seconds)
                return True
            except Exception:
                return False

        try:
            # Create connections
            tasks = [
                asyncio.create_task(hold_connection())
                for _ in range(connection_count)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            result["active_connections"] = sum(1 for r in results if r is True)
            result["failed_connections"] = sum(1 for r in results if r is not True)
            result["status"] = "completed"
            result["success"] = result["failed_connections"] < connection_count * 0.5

        except Exception as e:
            result["status"] = "failed"
            result["success"] = False
            result["error"] = str(e)

        return result


class StressTestScenarios:
    """
    Predefined stress test scenarios.
    """

    @staticmethod
    def find_breaking_point(target: str) -> StressTestConfig:
        """Find system breaking point"""
        return StressTestConfig(
            name="Breaking Point Test",
            test_type=StressTestType.BREAKPOINT,
            target=target,
            initial_load=10,
            max_load=1000,
            increment=20,
            increment_interval=30,
            failure_threshold=5.0,
        )

    @staticmethod
    def find_saturation_point(target: str) -> StressTestConfig:
        """Find system saturation point"""
        return StressTestConfig(
            name="Saturation Point Test",
            test_type=StressTestType.SATURATION,
            target=target,
            initial_load=10,
            max_load=500,
            increment=10,
            increment_interval=60,
            failure_threshold=10.0,
        )

    @staticmethod
    def endurance_test(target: str) -> StressTestConfig:
        """Long-running endurance test"""
        return StressTestConfig(
            name="Endurance Test",
            test_type=StressTestType.ENDURANCE,
            target=target,
            initial_load=100,
            max_load=100,  # Constant load
            increment=0,
            increment_interval=3600,  # 1 hour intervals
            warmup_duration=300,
        )
