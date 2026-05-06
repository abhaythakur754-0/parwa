# Performance Monitor - Week 50 Builder 1
# System performance monitoring and metrics

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import time


class MetricType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricSample:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric_type: MetricType = MetricType.CPU
    value: float = 0.0
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PerformanceAlert:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric_type: MetricType = MetricType.CPU
    level: AlertLevel = AlertLevel.WARNING
    threshold: float = 0.0
    actual_value: float = 0.0
    message: str = ""
    triggered_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False


class PerformanceMonitor:
    """Monitors system performance metrics"""

    def __init__(self):
        self._samples: List[MetricSample] = []
        self._alerts: List[PerformanceAlert] = []
        self._thresholds: Dict[MetricType, Dict[str, float]] = {
            MetricType.CPU: {"warning": 70.0, "critical": 90.0},
            MetricType.MEMORY: {"warning": 80.0, "critical": 95.0},
            MetricType.LATENCY: {"warning": 500.0, "critical": 1000.0},
            MetricType.ERROR_RATE: {"warning": 1.0, "critical": 5.0}
        }
        self._metrics = {
            "total_samples": 0,
            "total_alerts": 0,
            "by_type": {}
        }

    def record_sample(
        self,
        metric_type: MetricType,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None
    ) -> MetricSample:
        """Record a performance sample"""
        sample = MetricSample(
            metric_type=metric_type,
            value=value,
            unit=unit,
            tags=tags or {}
        )

        self._samples.append(sample)
        self._metrics["total_samples"] += 1

        type_key = metric_type.value
        self._metrics["by_type"][type_key] = self._metrics["by_type"].get(type_key, 0) + 1

        # Check thresholds
        self._check_threshold(sample)

        return sample

    def _check_threshold(self, sample: MetricSample) -> None:
        """Check if sample exceeds thresholds"""
        thresholds = self._thresholds.get(sample.metric_type, {})
        
        critical_threshold = thresholds.get("critical", float('inf'))
        warning_threshold = thresholds.get("warning", float('inf'))

        if sample.value >= critical_threshold:
            alert = PerformanceAlert(
                metric_type=sample.metric_type,
                level=AlertLevel.CRITICAL,
                threshold=critical_threshold,
                actual_value=sample.value,
                message=f"Critical: {sample.metric_type.value} at {sample.value}{sample.unit}"
            )
            self._alerts.append(alert)
            self._metrics["total_alerts"] += 1

        elif sample.value >= warning_threshold:
            alert = PerformanceAlert(
                metric_type=sample.metric_type,
                level=AlertLevel.WARNING,
                threshold=warning_threshold,
                actual_value=sample.value,
                message=f"Warning: {sample.metric_type.value} at {sample.value}{sample.unit}"
            )
            self._alerts.append(alert)
            self._metrics["total_alerts"] += 1

    def set_threshold(
        self,
        metric_type: MetricType,
        warning: float,
        critical: float
    ) -> None:
        """Set thresholds for a metric"""
        self._thresholds[metric_type] = {"warning": warning, "critical": critical}

    def get_average(
        self,
        metric_type: MetricType,
        minutes: int = 5
    ) -> float:
        """Get average value for a metric"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        samples = [
            s for s in self._samples
            if s.metric_type == metric_type
            and s.timestamp >= cutoff
        ]

        if not samples:
            return 0.0

        return sum(s.value for s in samples) / len(samples)

    def get_percentile(
        self,
        metric_type: MetricType,
        percentile: int,
        minutes: int = 5
    ) -> float:
        """Get percentile value for a metric"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        samples = [
            s.value for s in self._samples
            if s.metric_type == metric_type
            and s.timestamp >= cutoff
        ]

        if not samples:
            return 0.0

        samples.sort()
        index = int(len(samples) * percentile / 100)
        return samples[min(index, len(samples) - 1)]

    def get_trend(
        self,
        metric_type: MetricType,
        minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get trend data for a metric"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        samples = [
            s for s in self._samples
            if s.metric_type == metric_type
            and s.timestamp >= cutoff
        ]

        return [
            {"timestamp": s.timestamp.isoformat(), "value": s.value}
            for s in sorted(samples, key=lambda x: x.timestamp)
        ]

    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get all unacknowledged alerts"""
        return [a for a in self._alerts if not a.acknowledged]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get monitor metrics"""
        return {
            **self._metrics,
            "total_alerts_active": len(self.get_active_alerts())
        }

    def cleanup_old_samples(self, hours: int = 24) -> int:
        """Remove old samples"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        initial = len(self._samples)
        self._samples = [s for s in self._samples if s.timestamp >= cutoff]
        return initial - len(self._samples)
