"""
Performance Monitor for Auto-Rollback.

Monitors real-time performance:
- Accuracy tracking
- Latency percentiles
- Error rate monitoring
- Anomaly detection
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import logging
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MetricBaseline:
    """Baseline for a metric."""
    name: str
    value: float
    std_dev: float
    sample_size: int
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceAlert:
    """A performance alert."""
    metric_name: str
    current_value: float
    baseline_value: float
    deviation: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    is_critical: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "baseline_value": self.baseline_value,
            "deviation": self.deviation,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "is_critical": self.is_critical,
        }


class PerformanceMonitor:
    """
    Monitors model performance in real-time.

    Features:
    - Real-time accuracy tracking
    - Latency percentile tracking
    - Error rate monitoring
    - Comparison against baseline
    """

    DEFAULT_WINDOW_SIZE: int = 1000
    ALERT_THRESHOLD_ACCURACY: float = 0.05  # 5% deviation
    ALERT_THRESHOLD_LATENCY: float = 0.30  # 30% deviation
    ALERT_THRESHOLD_ERROR_RATE: float = 0.10  # 10% error rate

    def __init__(
        self,
        window_size: int = 1000,
        accuracy_alert_threshold: float = 0.05,
        latency_alert_threshold: float = 0.30
    ):
        """
        Initialize the performance monitor.

        Args:
            window_size: Rolling window size for metrics
            accuracy_alert_threshold: Alert threshold for accuracy deviation
            latency_alert_threshold: Alert threshold for latency deviation
        """
        self.window_size = window_size
        self.accuracy_alert_threshold = accuracy_alert_threshold
        self.latency_alert_threshold = latency_alert_threshold

        # Metric windows
        self._accuracy_window: deque = deque(maxlen=window_size)
        self._latency_window: deque = deque(maxlen=window_size)
        self._error_window: deque = deque(maxlen=window_size)

        # Baselines
        self._baselines: Dict[str, MetricBaseline] = {}

        # Alert history
        self._alerts: List[PerformanceAlert] = []

    def set_baseline(
        self,
        metric_name: str,
        value: float,
        std_dev: float = 0.0,
        sample_size: int = 100
    ):
        """
        Set baseline for a metric.

        Args:
            metric_name: Name of the metric
            value: Baseline value
            std_dev: Standard deviation
            sample_size: Sample size for baseline
        """
        self._baselines[metric_name] = MetricBaseline(
            name=metric_name,
            value=value,
            std_dev=std_dev,
            sample_size=sample_size
        )

        logger.info(f"Set baseline for {metric_name}: {value:.4f}")

    def record_accuracy(self, is_correct: bool, confidence: Optional[float] = None):
        """
        Record an accuracy measurement.

        Args:
            is_correct: Whether prediction was correct
            confidence: Model confidence (optional)
        """
        self._accuracy_window.append({
            "value": 1.0 if is_correct else 0.0,
            "confidence": confidence,
            "timestamp": datetime.now()
        })

    def record_latency(self, latency_ms: float, query_type: Optional[str] = None):
        """
        Record a latency measurement.

        Args:
            latency_ms: Latency in milliseconds
            query_type: Type of query (optional)
        """
        self._latency_window.append({
            "value": latency_ms,
            "query_type": query_type,
            "timestamp": datetime.now()
        })

    def record_error(self, error_type: str, error_message: Optional[str] = None):
        """
        Record an error.

        Args:
            error_type: Type of error
            error_message: Error message (optional)
        """
        self._error_window.append({
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.now()
        })

    def get_current_accuracy(self) -> float:
        """Get current accuracy from rolling window."""
        if not self._accuracy_window:
            return 0.0
        return sum(item["value"] for item in self._accuracy_window) / len(self._accuracy_window)

    def get_latency_percentiles(self) -> Dict[str, float]:
        """Get latency percentiles."""
        if not self._latency_window:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        values = sorted(item["value"] for item in self._latency_window)
        n = len(values)

        return {
            "p50": values[int(n * 0.50)],
            "p95": values[int(n * 0.95)],
            "p99": values[int(n * 0.99)],
        }

    def get_error_rate(self) -> float:
        """Get current error rate."""
        if not self._error_window:
            return 0.0
        # Assuming errors are per request
        total_requests = len(self._accuracy_window) + len(self._latency_window)
        if total_requests == 0:
            return 0.0
        return len(self._error_window) / total_requests

    def check_accuracy_deviation(self) -> Optional[PerformanceAlert]:
        """
        Check for accuracy deviation from baseline.

        Returns:
            PerformanceAlert if deviation detected, None otherwise
        """
        if "accuracy" not in self._baselines:
            return None

        baseline = self._baselines["accuracy"]
        current = self.get_current_accuracy()

        deviation = baseline.value - current  # Negative = improvement

        if deviation > self.accuracy_alert_threshold:
            alert = PerformanceAlert(
                metric_name="accuracy",
                current_value=current,
                baseline_value=baseline.value,
                deviation=deviation,
                threshold=self.accuracy_alert_threshold,
                is_critical=deviation > self.accuracy_alert_threshold * 2
            )
            self._alerts.append(alert)
            return alert

        return None

    def check_latency_deviation(self) -> Optional[PerformanceAlert]:
        """
        Check for latency degradation from baseline.

        Returns:
            PerformanceAlert if degradation detected, None otherwise
        """
        if "latency_p95" not in self._baselines:
            return None

        baseline = self._baselines["latency_p95"]
        current = self.get_latency_percentiles()["p95"]

        deviation = (current - baseline.value) / baseline.value if baseline.value > 0 else 0

        if deviation > self.latency_alert_threshold:
            alert = PerformanceAlert(
                metric_name="latency_p95",
                current_value=current,
                baseline_value=baseline.value,
                deviation=deviation,
                threshold=self.latency_alert_threshold,
                is_critical=deviation > self.latency_alert_threshold * 2
            )
            self._alerts.append(alert)
            return alert

        return None

    def check_all_metrics(self) -> List[PerformanceAlert]:
        """
        Check all metrics for deviations.

        Returns:
            List of PerformanceAlerts
        """
        alerts = []

        accuracy_alert = self.check_accuracy_deviation()
        if accuracy_alert:
            alerts.append(accuracy_alert)

        latency_alert = self.check_latency_deviation()
        if latency_alert:
            alerts.append(latency_alert)

        return alerts

    def has_critical_alert(self) -> bool:
        """Check if there's a critical alert."""
        return any(alert.is_critical for alert in self._alerts)

    def get_recent_alerts(self, limit: int = 10) -> List[PerformanceAlert]:
        """Get recent alerts."""
        return self._alerts[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get monitor statistics."""
        return {
            "window_size": self.window_size,
            "samples": {
                "accuracy": len(self._accuracy_window),
                "latency": len(self._latency_window),
                "errors": len(self._error_window),
            },
            "current_metrics": {
                "accuracy": self.get_current_accuracy(),
                "latency": self.get_latency_percentiles(),
                "error_rate": self.get_error_rate(),
            },
            "baselines": {
                name: {"value": b.value, "std_dev": b.std_dev}
                for name, b in self._baselines.items()
            },
            "alert_count": len(self._alerts),
            "has_critical": self.has_critical_alert(),
        }


def get_performance_monitor(window_size: int = 1000) -> PerformanceMonitor:
    """Factory function to create a performance monitor."""
    return PerformanceMonitor(window_size=window_size)
