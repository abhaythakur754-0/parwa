"""
Real-time Monitor Module - Week 53, Builder 1
Real-time system monitoring for enterprise infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import asyncio
import logging
import time
import threading

# Import HealthStatus from health_aggregator to avoid duplication
from enterprise.monitoring.health_aggregator import HealthStatus

logger = logging.getLogger(__name__)


class MonitorStatus(Enum):
    """Monitor status enum"""
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class MetricType(Enum):
    """Metric type enum"""
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricSample:
    """Single metric sample"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorTarget:
    """Monitoring target configuration"""
    name: str
    target_type: str  # "host", "service", "endpoint", "process"
    check_interval: float = 60.0
    timeout: float = 10.0
    enabled: bool = True
    health_endpoint: Optional[str] = None
    thresholds: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorResult:
    """Result of a monitoring check"""
    target: str
    status: HealthStatus
    response_time_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class MetricBuffer:
    """
    Thread-safe buffer for metric samples.
    """

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._buffer: Dict[str, List[MetricSample]] = {}
        self._lock = threading.Lock()

    def add(self, sample: MetricSample) -> None:
        """Add a metric sample"""
        with self._lock:
            if sample.name not in self._buffer:
                self._buffer[sample.name] = []

            self._buffer[sample.name].append(sample)

            # Enforce max size
            if len(self._buffer[sample.name]) > self.max_size:
                self._buffer[sample.name] = self._buffer[sample.name][-self.max_size:]

    def get_samples(
        self,
        name: str,
        limit: int = 100,
    ) -> List[MetricSample]:
        """Get recent samples for a metric"""
        with self._lock:
            samples = self._buffer.get(name, [])
            return samples[-limit:]

    def get_all_names(self) -> List[str]:
        """Get all metric names"""
        with self._lock:
            return list(self._buffer.keys())

    def clear(self, name: Optional[str] = None) -> None:
        """Clear buffer"""
        with self._lock:
            if name:
                self._buffer.pop(name, None)
            else:
                self._buffer.clear()


class RealtimeMonitor:
    """
    Main real-time monitoring engine.
    """

    def __init__(
        self,
        check_interval: float = 60.0,
        max_concurrent: int = 50,
    ):
        self.check_interval = check_interval
        self.max_concurrent = max_concurrent
        self.status = MonitorStatus.STOPPED
        self.targets: Dict[str, MonitorTarget] = {}
        self.results: Dict[str, List[MonitorResult]] = {}
        self.buffer = MetricBuffer()
        self._checkers: Dict[str, Callable] = {}
        self._callbacks: List[Callable] = []
        self._task: Optional[asyncio.Task] = None

    def add_target(self, target: MonitorTarget) -> None:
        """Add a monitoring target"""
        self.targets[target.name] = target
        if target.name not in self.results:
            self.results[target.name] = []
        logger.info(f"Added monitoring target: {target.name}")

    def remove_target(self, name: str) -> bool:
        """Remove a monitoring target"""
        if name in self.targets:
            del self.targets[name]
            self.results.pop(name, None)
            logger.info(f"Removed monitoring target: {name}")
            return True
        return False

    def register_checker(
        self,
        target_type: str,
        checker: Callable[[MonitorTarget], MonitorResult],
    ) -> None:
        """Register a checker function for a target type"""
        self._checkers[target_type] = checker
        logger.info(f"Registered checker for type: {target_type}")

    def add_callback(self, callback: Callable[[MonitorResult], None]) -> None:
        """Add a callback for monitor results"""
        self._callbacks.append(callback)

    async def check_target(self, target: MonitorTarget) -> MonitorResult:
        """Perform a single monitoring check"""
        start_time = time.time()
        status = HealthStatus.HEALTHY
        metrics = {}
        error = None

        try:
            checker = self._checkers.get(target.target_type)

            if checker:
                # Run checker with timeout
                result = await asyncio.wait_for(
                    self._run_checker(checker, target),
                    timeout=target.timeout,
                )
                status = result.status
                metrics = result.metrics
                error = result.error
            else:
                # Default health check
                status = await self._default_check(target)

        except asyncio.TimeoutError:
            status = HealthStatus.UNHEALTHY
            error = f"Timeout after {target.timeout}s"
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            error = str(e)

        response_time = (time.time() - start_time) * 1000

        result = MonitorResult(
            target=target.name,
            status=status,
            response_time_ms=response_time,
            metrics=metrics,
            error=error,
        )

        # Store result
        self.results[target.name].append(result)
        if len(self.results[target.name]) > 100:
            self.results[target.name] = self.results[target.name][-100:]

        # Record metrics
        self.buffer.add(MetricSample(
            name=f"{target.name}.response_time",
            value=response_time,
            metric_type=MetricType.GAUGE,
            labels={"target": target.name},
        ))

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return result

    async def _run_checker(
        self,
        checker: Callable,
        target: MonitorTarget,
    ) -> MonitorResult:
        """Run a checker function"""
        import asyncio
        result = checker(target)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def _default_check(self, target: MonitorTarget) -> HealthStatus:
        """Default health check"""
        # Simulate check - in production would do actual health check
        await asyncio.sleep(0.01)
        return HealthStatus.HEALTHY

    async def run_checks(self) -> Dict[str, MonitorResult]:
        """Run all enabled target checks"""
        results = {}

        enabled_targets = [
            t for t in self.targets.values()
            if t.enabled
        ]

        # Run checks concurrently
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def check_with_semaphore(target: MonitorTarget):
            async with semaphore:
                return target.name, await self.check_target(target)

        tasks = [check_with_semaphore(t) for t in enabled_targets]
        check_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in check_results:
            if isinstance(result, tuple):
                name, monitor_result = result
                results[name] = monitor_result

        return results

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self.status == MonitorStatus.RUNNING:
            try:
                await self.run_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(1)

    def start(self) -> None:
        """Start monitoring"""
        if self.status == MonitorStatus.RUNNING:
            return

        self.status = MonitorStatus.RUNNING
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Monitoring started")

    def stop(self) -> None:
        """Stop monitoring"""
        self.status = MonitorStatus.STOPPED
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Monitoring stopped")

    def pause(self) -> None:
        """Pause monitoring"""
        self.status = MonitorStatus.PAUSED
        logger.info("Monitoring paused")

    def resume(self) -> None:
        """Resume monitoring"""
        if self.status == MonitorStatus.PAUSED:
            self.status = MonitorStatus.RUNNING
            logger.info("Monitoring resumed")

    def get_status(self) -> Dict[str, Any]:
        """Get monitor status summary"""
        healthy = sum(
            1 for results in self.results.values()
            if results and results[-1].status == HealthStatus.HEALTHY
        )
        total = len(self.targets)

        return {
            "status": self.status.value,
            "targets": total,
            "healthy": healthy,
            "unhealthy": total - healthy,
            "health_percent": (healthy / total * 100) if total > 0 else 0,
            "metrics_count": len(self.buffer.get_all_names()),
        }

    def get_target_status(self, name: str) -> Optional[MonitorResult]:
        """Get latest status for a target"""
        results = self.results.get(name, [])
        return results[-1] if results else None

    def get_target_history(
        self,
        name: str,
        limit: int = 100,
    ) -> List[MonitorResult]:
        """Get history for a target"""
        results = self.results.get(name, [])
        return results[-limit:]


class MonitorFactory:
    """
    Factory for creating pre-configured monitors.
    """

    @staticmethod
    def create_system_monitor() -> RealtimeMonitor:
        """Create system resource monitor"""
        monitor = RealtimeMonitor(check_interval=30.0)
        return monitor

    @staticmethod
    def create_service_monitor() -> RealtimeMonitor:
        """Create service health monitor"""
        monitor = RealtimeMonitor(check_interval=60.0)

        # Register service checker
        async def service_checker(target: MonitorTarget) -> MonitorResult:
            # Simulated service check
            return MonitorResult(
                target=target.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=50.0,
            )

        monitor.register_checker("service", service_checker)
        return monitor

    @staticmethod
    def create_endpoint_monitor() -> RealtimeMonitor:
        """Create endpoint monitor"""
        monitor = RealtimeMonitor(check_interval=15.0)

        # Register endpoint checker
        async def endpoint_checker(target: MonitorTarget) -> MonitorResult:
            # Simulated endpoint check
            return MonitorResult(
                target=target.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=100.0,
            )

        monitor.register_checker("endpoint", endpoint_checker)
        return monitor
