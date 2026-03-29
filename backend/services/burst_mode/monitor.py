"""
Queue and Performance Monitor for Burst Mode.

Provides real-time monitoring of queue depth, response times,
and system performance metrics with alerting capabilities.

Features:
- Monitor queue depth
- Track response times
- Alert when thresholds exceeded
- Provide real-time metrics
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import deque
import logging
import statistics

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricType(Enum):
    """Types of metrics being monitored."""
    QUEUE_DEPTH = "queue_depth"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"


@dataclass
class MonitorThresholds:
    """Thresholds for monitoring alerts."""
    # Queue depth thresholds
    queue_depth_warning: int = 50
    queue_depth_critical: int = 100
    queue_depth_emergency: int = 200

    # Response time thresholds (milliseconds)
    response_time_warning: float = 200.0
    response_time_critical: float = 500.0
    response_time_emergency: float = 1000.0

    # Throughput thresholds (requests per second)
    throughput_warning: float = 500.0
    throughput_critical: float = 1000.0

    # Error rate thresholds (percentage)
    error_rate_warning: float = 1.0
    error_rate_critical: float = 5.0
    error_rate_emergency: float = 10.0

    # Latency thresholds (milliseconds)
    latency_p95_warning: float = 300.0
    latency_p95_critical: float = 600.0
    latency_p99_warning: float = 500.0
    latency_p99_critical: float = 1000.0


@dataclass
class Alert:
    """Represents a monitoring alert."""
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    metric_type: MetricType
    current_value: float
    threshold: float
    message: str
    acknowledged: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "metric_type": self.metric_type.value,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "message": self.message,
            "acknowledged": self.acknowledged,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class RealtimeMetrics:
    """Current real-time metrics snapshot."""
    timestamp: float = field(default_factory=time.time)

    # Queue metrics
    queue_depth: int = 0
    queue_depth_delta: int = 0  # Change since last measurement
    queue_backlog_seconds: float = 0.0  # Estimated time to clear queue

    # Response time metrics
    response_time_current: float = 0.0  # milliseconds
    response_time_avg_1m: float = 0.0
    response_time_avg_5m: float = 0.0
    response_time_p50: float = 0.0
    response_time_p95: float = 0.0
    response_time_p99: float = 0.0

    # Throughput metrics
    throughput_current: float = 0.0  # requests per second
    throughput_avg_1m: float = 0.0
    throughput_avg_5m: float = 0.0

    # Error metrics
    error_rate: float = 0.0  # percentage
    error_count_total: int = 0
    error_count_recent: int = 0  # Last 5 minutes

    # Health indicators
    health_score: float = 100.0  # 0-100 scale
    is_healthy: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "timestamp": self.timestamp,
            "queue_depth": self.queue_depth,
            "queue_depth_delta": self.queue_depth_delta,
            "queue_backlog_seconds": self.queue_backlog_seconds,
            "response_time_current": self.response_time_current,
            "response_time_avg_1m": self.response_time_avg_1m,
            "response_time_avg_5m": self.response_time_avg_5m,
            "response_time_p50": self.response_time_p50,
            "response_time_p95": self.response_time_p95,
            "response_time_p99": self.response_time_p99,
            "throughput_current": self.throughput_current,
            "throughput_avg_1m": self.throughput_avg_1m,
            "throughput_avg_5m": self.throughput_avg_5m,
            "error_rate": self.error_rate,
            "error_count_total": self.error_count_total,
            "error_count_recent": self.error_count_recent,
            "health_score": self.health_score,
            "is_healthy": self.is_healthy,
        }


class BurstModeMonitor:
    """
    Real-time monitor for burst mode operations.

    Monitors queue depth, response times, throughput, and error rates,
    generating alerts when thresholds are exceeded.
    """

    def __init__(
        self,
        thresholds: Optional[MonitorThresholds] = None,
        burst_mode_service: Optional[Any] = None,
        scaler: Optional[Any] = None,
    ):
        """
        Initialize the burst mode monitor.

        Args:
            thresholds: Custom monitoring thresholds
            burst_mode_service: Reference to burst mode service
            scaler: Reference to resource scaler
        """
        self.thresholds = thresholds or MonitorThresholds()
        self._burst_mode_service = burst_mode_service
        self._scaler = scaler

        # Metrics storage
        self._response_times: deque = deque(maxlen=1000)
        self._throughput_samples: deque = deque(maxlen=300)
        self._error_samples: deque = deque(maxlen=300)
        self._queue_depth_history: deque = deque(maxlen=100)

        # Current state
        self._current_metrics = RealtimeMetrics()
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._max_alert_history = 100

        # Callbacks
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._metrics_callbacks: List[Callable[[RealtimeMetrics], None]] = []

        # Timing
        self._last_queue_depth: int = 0
        self._last_sample_time: float = time.time()
        self._request_count: int = 0
        self._error_count: int = 0
        self._lock = asyncio.Lock()

    @property
    def current_metrics(self) -> RealtimeMetrics:
        """Get current metrics snapshot."""
        return self._current_metrics

    @property
    def active_alerts(self) -> List[Alert]:
        """Get list of active (unacknowledged) alerts."""
        return [a for a in self._active_alerts.values() if not a.acknowledged]

    def add_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Add callback for alert notifications."""
        self._alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Remove an alert callback."""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)

    def add_metrics_callback(self, callback: Callable[[RealtimeMetrics], None]) -> None:
        """Add callback for metrics updates."""
        self._metrics_callbacks.append(callback)

    def remove_metrics_callback(self, callback: Callable[[RealtimeMetrics], None]) -> None:
        """Remove a metrics callback."""
        if callback in self._metrics_callbacks:
            self._metrics_callbacks.remove(callback)

    async def _notify_alert(self, alert: Alert) -> None:
        """Notify all alert callbacks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    async def _notify_metrics(self, metrics: RealtimeMetrics) -> None:
        """Notify all metrics callbacks."""
        for callback in self._metrics_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(metrics)
                else:
                    callback(metrics)
            except Exception as e:
                logger.error(f"Metrics callback error: {e}")

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        return f"alert_{int(time.time() * 1000)}_{len(self._alert_history)}"

    async def record_request(
        self,
        response_time_ms: float,
        is_error: bool = False,
    ) -> None:
        """
        Record a request for monitoring.

        Args:
            response_time_ms: Response time in milliseconds
            is_error: Whether the request resulted in an error
        """
        async with self._lock:
            current_time = time.time()

            self._response_times.append(response_time_ms)
            self._request_count += 1

            if is_error:
                self._error_count += 1
                self._error_samples.append((current_time, 1))

            # Update current response time
            self._current_metrics.response_time_current = response_time_ms

            # Calculate rolling averages
            await self._update_rolling_metrics()

    async def update_queue_depth(self, depth: int) -> None:
        """
        Update queue depth measurement.

        Args:
            depth: Current queue depth
        """
        async with self._lock:
            current_time = time.time()

            # Calculate delta
            delta = depth - self._last_queue_depth
            self._last_queue_depth = depth

            # Store in history
            self._queue_depth_history.append((current_time, depth))

            # Update metrics
            self._current_metrics.queue_depth = depth
            self._current_metrics.queue_depth_delta = delta

            # Estimate backlog time (rough estimate based on recent throughput)
            if self._current_metrics.throughput_current > 0:
                self._current_metrics.queue_backlog_seconds = (
                    depth / self._current_metrics.throughput_current
                )

            # Check thresholds
            await self._check_queue_thresholds(depth)

    async def _update_rolling_metrics(self) -> None:
        """Update rolling average metrics."""
        current_time = time.time()

        # Response time statistics
        if self._response_times:
            times = list(self._response_times)
            self._current_metrics.response_time_avg_1m = statistics.mean(times)
            self._current_metrics.response_time_p50 = statistics.median(times)

            sorted_times = sorted(times)
            count = len(sorted_times)
            self._current_metrics.response_time_p95 = sorted_times[int(count * 0.95)]
            self._current_metrics.response_time_p99 = sorted_times[int(count * 0.99)]

        # Throughput calculation
        time_delta = current_time - self._last_sample_time
        if time_delta >= 1.0:  # Update every second
            self._current_metrics.throughput_current = self._request_count / time_delta
            self._throughput_samples.append((current_time, self._current_metrics.throughput_current))
            self._request_count = 0
            self._last_sample_time = current_time

        # Rolling throughput averages
        one_min_ago = current_time - 60
        five_min_ago = current_time - 300

        recent_throughput = [t for ts, t in self._throughput_samples if ts >= one_min_ago]
        if recent_throughput:
            self._current_metrics.throughput_avg_1m = statistics.mean(recent_throughput)

        older_throughput = [t for ts, t in self._throughput_samples if ts >= five_min_ago]
        if older_throughput:
            self._current_metrics.throughput_avg_5m = statistics.mean(older_throughput)

        # Error rate
        recent_errors = sum(1 for ts, _ in self._error_samples if ts >= five_min_ago)
        self._current_metrics.error_count_recent = recent_errors

        total_requests = len(self._response_times)
        if total_requests > 0:
            error_count = sum(1 for _, e in self._error_samples)
            self._current_metrics.error_rate = (error_count / total_requests) * 100

        # Update health score
        await self._calculate_health_score()

    async def _calculate_health_score(self) -> None:
        """Calculate overall health score (0-100)."""
        score = 100.0
        penalties = []

        # Response time penalty
        if self._current_metrics.response_time_p95 > self.thresholds.response_time_warning:
            penalty = min(30, (
                (self._current_metrics.response_time_p95 - self.thresholds.response_time_warning) /
                self.thresholds.response_time_critical
            ) * 30)
            penalties.append(("response_time", penalty))
            score -= penalty

        # Queue depth penalty
        if self._current_metrics.queue_depth > self.thresholds.queue_depth_warning:
            penalty = min(25, (
                (self._current_metrics.queue_depth - self.thresholds.queue_depth_warning) /
                self.thresholds.queue_depth_critical
            ) * 25)
            penalties.append(("queue_depth", penalty))
            score -= penalty

        # Error rate penalty
        if self._current_metrics.error_rate > self.thresholds.error_rate_warning:
            penalty = min(30, (
                (self._current_metrics.error_rate - self.thresholds.error_rate_warning) /
                self.thresholds.error_rate_critical
            ) * 30)
            penalties.append(("error_rate", penalty))
            score -= penalty

        self._current_metrics.health_score = max(0, score)
        self._current_metrics.is_healthy = score >= 70

    async def _check_queue_thresholds(self, depth: int) -> None:
        """Check queue depth against thresholds."""
        if depth >= self.thresholds.queue_depth_emergency:
            await self._create_alert(
                MetricType.QUEUE_DEPTH,
                AlertSeverity.EMERGENCY,
                depth,
                self.thresholds.queue_depth_emergency,
                f"Queue depth at emergency level: {depth}"
            )
        elif depth >= self.thresholds.queue_depth_critical:
            await self._create_alert(
                MetricType.QUEUE_DEPTH,
                AlertSeverity.CRITICAL,
                depth,
                self.thresholds.queue_depth_critical,
                f"Queue depth at critical level: {depth}"
            )
        elif depth >= self.thresholds.queue_depth_warning:
            await self._create_alert(
                MetricType.QUEUE_DEPTH,
                AlertSeverity.WARNING,
                depth,
                self.thresholds.queue_depth_warning,
                f"Queue depth elevated: {depth}"
            )

    async def _create_alert(
        self,
        metric_type: MetricType,
        severity: AlertSeverity,
        current_value: float,
        threshold: float,
        message: str,
    ) -> Alert:
        """
        Create and register an alert.

        Args:
            metric_type: Type of metric that triggered alert
            severity: Alert severity level
            current_value: Current metric value
            threshold: Threshold that was exceeded
            message: Alert message

        Returns:
            The created alert
        """
        alert = Alert(
            alert_id=self._generate_alert_id(),
            timestamp=datetime.now(),
            severity=severity,
            metric_type=metric_type,
            current_value=current_value,
            threshold=threshold,
            message=message,
        )

        self._active_alerts[f"{metric_type.value}_{severity.value}"] = alert
        self._alert_history.append(alert)

        if len(self._alert_history) > self._max_alert_history:
            self._alert_history.pop(0)

        logger.warning(f"Alert created: [{severity.value}] {message}")
        await self._notify_alert(alert)

        return alert

    async def check_response_time_thresholds(self) -> List[Alert]:
        """
        Check response times against thresholds.

        Returns:
            List of any alerts created
        """
        alerts = []
        p95 = self._current_metrics.response_time_p95
        p99 = self._current_metrics.response_time_p99

        if p99 >= self.thresholds.latency_p99_critical:
            alert = await self._create_alert(
                MetricType.LATENCY_P99,
                AlertSeverity.CRITICAL,
                p99,
                self.thresholds.latency_p99_critical,
                f"P99 latency at critical level: {p99:.1f}ms"
            )
            alerts.append(alert)
        elif p99 >= self.thresholds.latency_p99_warning:
            alert = await self._create_alert(
                MetricType.LATENCY_P99,
                AlertSeverity.WARNING,
                p99,
                self.thresholds.latency_p99_warning,
                f"P99 latency elevated: {p99:.1f}ms"
            )
            alerts.append(alert)

        if p95 >= self.thresholds.latency_p95_critical:
            alert = await self._create_alert(
                MetricType.LATENCY_P95,
                AlertSeverity.CRITICAL,
                p95,
                self.thresholds.latency_p95_critical,
                f"P95 latency at critical level: {p95:.1f}ms"
            )
            alerts.append(alert)
        elif p95 >= self.thresholds.latency_p95_warning:
            alert = await self._create_alert(
                MetricType.LATENCY_P95,
                AlertSeverity.WARNING,
                p95,
                self.thresholds.latency_p95_warning,
                f"P95 latency elevated: {p95:.1f}ms"
            )
            alerts.append(alert)

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an active alert.

        Args:
            alert_id: ID of alert to acknowledge

        Returns:
            True if alert was found and acknowledged
        """
        for key, alert in self._active_alerts.items():
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False

    def resolve_alert(self, alert_key: str) -> bool:
        """
        Resolve an active alert.

        Args:
            alert_key: Key of alert (metric_type_severity)

        Returns:
            True if alert was resolved
        """
        if alert_key in self._active_alerts:
            alert = self._active_alerts.pop(alert_key)
            alert.resolved_at = datetime.now()
            self._alert_history.append(alert)
            logger.info(f"Alert resolved: {alert_key}")
            return True
        return False

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current metrics.

        Returns:
            Dictionary with metrics summary
        """
        return {
            "queue": {
                "depth": self._current_metrics.queue_depth,
                "delta": self._current_metrics.queue_depth_delta,
                "backlog_seconds": self._current_metrics.queue_backlog_seconds,
            },
            "response_time": {
                "current_ms": self._current_metrics.response_time_current,
                "avg_1m_ms": self._current_metrics.response_time_avg_1m,
                "p50_ms": self._current_metrics.response_time_p50,
                "p95_ms": self._current_metrics.response_time_p95,
                "p99_ms": self._current_metrics.response_time_p99,
            },
            "throughput": {
                "current_rps": self._current_metrics.throughput_current,
                "avg_1m_rps": self._current_metrics.throughput_avg_1m,
                "avg_5m_rps": self._current_metrics.throughput_avg_5m,
            },
            "errors": {
                "rate_percent": self._current_metrics.error_rate,
                "count_recent": self._current_metrics.error_count_recent,
            },
            "health": {
                "score": self._current_metrics.health_score,
                "is_healthy": self._current_metrics.is_healthy,
            },
        }

    def get_alert_history(self, limit: int = 20) -> List[Alert]:
        """
        Get alert history.

        Args:
            limit: Maximum alerts to return

        Returns:
            List of historical alerts
        """
        return self._alert_history[-limit:]

    def configure_thresholds(
        self,
        queue_depth_warning: Optional[int] = None,
        queue_depth_critical: Optional[int] = None,
        response_time_warning: Optional[float] = None,
        response_time_critical: Optional[float] = None,
        error_rate_warning: Optional[float] = None,
        error_rate_critical: Optional[float] = None,
        **kwargs
    ) -> None:
        """
        Update monitoring thresholds.

        Args:
            queue_depth_warning: Queue depth warning threshold
            queue_depth_critical: Queue depth critical threshold
            response_time_warning: Response time warning threshold (ms)
            response_time_critical: Response time critical threshold (ms)
            error_rate_warning: Error rate warning threshold (%)
            error_rate_critical: Error rate critical threshold (%)
            **kwargs: Additional threshold options
        """
        if queue_depth_warning is not None:
            self.thresholds.queue_depth_warning = queue_depth_warning
        if queue_depth_critical is not None:
            self.thresholds.queue_depth_critical = queue_depth_critical
        if response_time_warning is not None:
            self.thresholds.response_time_warning = response_time_warning
        if response_time_critical is not None:
            self.thresholds.response_time_critical = response_time_critical
        if error_rate_warning is not None:
            self.thresholds.error_rate_warning = error_rate_warning
        if error_rate_critical is not None:
            self.thresholds.error_rate_critical = error_rate_critical

        for key, value in kwargs.items():
            if hasattr(self.thresholds, key):
                setattr(self.thresholds, key, value)

        logger.info("Monitor thresholds updated")

    def reset(self) -> None:
        """Reset monitor to initial state."""
        self._response_times.clear()
        self._throughput_samples.clear()
        self._error_samples.clear()
        self._queue_depth_history.clear()
        self._current_metrics = RealtimeMetrics()
        self._active_alerts.clear()
        self._alert_history.clear()
        self._request_count = 0
        self._error_count = 0
        logger.info("Burst mode monitor reset")


# Singleton instance
_burst_mode_monitor: Optional[BurstModeMonitor] = None


def get_burst_mode_monitor() -> BurstModeMonitor:
    """Get the singleton burst mode monitor instance."""
    global _burst_mode_monitor
    if _burst_mode_monitor is None:
        _burst_mode_monitor = BurstModeMonitor()
    return _burst_mode_monitor


def reset_burst_mode_monitor() -> None:
    """Reset the singleton burst mode monitor (for testing)."""
    global _burst_mode_monitor
    if _burst_mode_monitor:
        _burst_mode_monitor.reset()
    _burst_mode_monitor = None
