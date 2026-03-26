"""
Latency Tracker for Cross-Region Replication.

Tracks latency metrics:
- Track cross-region latency
- P50/P95/P99 latency metrics
- Latency alerts
- Historical tracking
- Prometheus export
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import logging
import statistics

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


@dataclass
class LatencyConfig:
    """Configuration for latency tracking."""
    alert_threshold_ms: int = 500
    sample_window_minutes: int = 5
    max_samples: int = 10000
    export_interval_seconds: int = 60


@dataclass
class LatencySample:
    """Single latency sample."""
    source_region: Region
    target_region: Region
    latency_ms: int
    operation: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "latency_ms": self.latency_ms,
            "operation": self.operation,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success
        }


@dataclass
class LatencyMetrics:
    """Aggregated latency metrics."""
    source_region: Region
    target_region: Region
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    sample_count: int
    window_start: datetime
    window_end: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "avg_ms": self.avg_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "sample_count": self.sample_count,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat()
        }


@dataclass
class LatencyAlert:
    """Latency alert."""
    alert_id: str
    source_region: Region
    target_region: Region
    latency_ms: int
    threshold_ms: int
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "latency_ms": self.latency_ms,
            "threshold_ms": self.threshold_ms,
            "timestamp": self.timestamp.isoformat()
        }


class LatencyTracker:
    """
    Tracks cross-region latency.

    Features:
    - Track cross-region latency
    - P50/P95/P99 latency metrics
    - Latency alerts
    - Historical tracking
    - Prometheus export
    """

    def __init__(
        self,
        config: Optional[LatencyConfig] = None
    ):
        """
        Initialize the latency tracker.

        Args:
            config: Latency configuration
        """
        self.config = config or LatencyConfig()
        self._samples: List[LatencySample] = []
        self._alerts: List[LatencyAlert] = []
        self._metrics_history: List[LatencyMetrics] = []

    def record(
        self,
        source_region: Region,
        target_region: Region,
        latency_ms: int,
        operation: str = "replication",
        success: bool = True
    ) -> LatencySample:
        """
        Record a latency sample.

        Args:
            source_region: Source region
            target_region: Target region
            latency_ms: Latency in milliseconds
            operation: Operation type
            success: Whether operation succeeded

        Returns:
            LatencySample that was recorded
        """
        sample = LatencySample(
            source_region=source_region,
            target_region=target_region,
            latency_ms=latency_ms,
            operation=operation,
            success=success
        )

        self._samples.append(sample)

        # Trim if over max samples
        if len(self._samples) > self.config.max_samples:
            self._samples = self._samples[-self.config.max_samples:]

        # Check for alert
        if latency_ms > self.config.alert_threshold_ms:
            self._create_alert(sample)

        return sample

    def _create_alert(self, sample: LatencySample) -> None:
        """Create a latency alert."""
        alert_id = f"latency-alert-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        alert = LatencyAlert(
            alert_id=alert_id,
            source_region=sample.source_region,
            target_region=sample.target_region,
            latency_ms=sample.latency_ms,
            threshold_ms=self.config.alert_threshold_ms
        )

        self._alerts.append(alert)

        logger.warning(
            f"LATENCY ALERT: {sample.source_region.value} -> {sample.target_region.value} "
            f"latency {sample.latency_ms}ms exceeds threshold {self.config.alert_threshold_ms}ms"
        )

    def get_metrics(
        self,
        source_region: Optional[Region] = None,
        target_region: Optional[Region] = None,
        window_minutes: Optional[int] = None
    ) -> Optional[LatencyMetrics]:
        """
        Get aggregated latency metrics.

        Args:
            source_region: Filter by source region
            target_region: Filter by target region
            window_minutes: Time window in minutes

        Returns:
            LatencyMetrics or None if no samples
        """
        window = window_minutes or self.config.sample_window_minutes
        cutoff = datetime.now() - timedelta(minutes=window)

        samples = [
            s for s in self._samples
            if s.timestamp >= cutoff and s.success
        ]

        if source_region:
            samples = [s for s in samples if s.source_region == source_region]

        if target_region:
            samples = [s for s in samples if s.target_region == target_region]

        if not samples:
            return None

        latencies = [s.latency_ms for s in samples]
        latencies_sorted = sorted(latencies)

        n = len(latencies_sorted)
        p50_idx = int(n * 0.50)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)

        metrics = LatencyMetrics(
            source_region=source_region or samples[0].source_region,
            target_region=target_region or samples[0].target_region,
            p50_ms=latencies_sorted[min(p50_idx, n - 1)],
            p95_ms=latencies_sorted[min(p95_idx, n - 1)],
            p99_ms=latencies_sorted[min(p99_idx, n - 1)],
            avg_ms=statistics.mean(latencies),
            min_ms=min(latencies),
            max_ms=max(latencies),
            sample_count=n,
            window_start=cutoff,
            window_end=datetime.now()
        )

        return metrics

    def get_all_region_metrics(self) -> Dict[str, LatencyMetrics]:
        """Get metrics for all region pairs."""
        metrics = {}

        for source in Region:
            for target in Region:
                if source != target:
                    key = f"{source.value}->{target.value}"
                    m = self.get_metrics(source, target)
                    if m:
                        metrics[key] = m

        return metrics

    def get_alerts(self, limit: int = 100) -> List[LatencyAlert]:
        """Get recent latency alerts."""
        return self._alerts[-limit:]

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus formatted metrics string
        """
        lines = []
        lines.append("# HELP replication_latency_ms Replication latency in milliseconds")
        lines.append("# TYPE replication_latency_ms gauge")

        all_metrics = self.get_all_region_metrics()

        for key, metrics in all_metrics.items():
            source, target = key.split("->")
            labels = f'source="{source}",target="{target}"'

            lines.append(f'replication_latency_p50_ms{{{labels}}} {metrics.p50_ms}')
            lines.append(f'replication_latency_p95_ms{{{labels}}} {metrics.p95_ms}')
            lines.append(f'replication_latency_p99_ms{{{labels}}} {metrics.p99_ms}')
            lines.append(f'replication_latency_avg_ms{{{labels}}} {metrics.avg_ms}')

        # Add alert count
        lines.append("# HELP replication_latency_alerts_total Total latency alerts")
        lines.append("# TYPE replication_latency_alerts_total counter")
        lines.append(f"replication_latency_alerts_total {len(self._alerts)}")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        total_samples = len(self._samples)
        successful = len([s for s in self._samples if s.success])

        return {
            "total_samples": total_samples,
            "successful_samples": successful,
            "failed_samples": total_samples - successful,
            "total_alerts": len(self._alerts),
            "samples_by_region": {
                region.value: len([s for s in self._samples if s.source_region == region])
                for region in Region
            }
        }

    def clear_old_samples(self, max_age_hours: int = 24) -> int:
        """
        Clear samples older than specified age.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of samples cleared
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        initial_count = len(self._samples)
        self._samples = [s for s in self._samples if s.timestamp >= cutoff]
        return initial_count - len(self._samples)


def get_latency_tracker() -> LatencyTracker:
    """Factory function to create a latency tracker."""
    return LatencyTracker()
