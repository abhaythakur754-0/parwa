"""
Metrics Collector for A/B Testing.

Collects and aggregates metrics per variant:
- Accuracy per variant
- Latency per variant
- User satisfaction
- Error rates
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from collections import defaultdict
import logging
import statistics

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected."""
    ACCURACY = "accuracy"
    LATENCY = "latency"
    SATISFACTION = "satisfaction"
    ERROR_RATE = "error_rate"
    RESOLUTION_RATE = "resolution_rate"
    ESCALATION_RATE = "escalation_rate"


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    metric_type: MetricType
    variant: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VariantMetrics:
    """Aggregated metrics for a variant."""
    variant: str
    sample_size: int = 0

    # Accuracy metrics
    accuracy_sum: float = 0.0
    accuracy_count: int = 0

    # Latency metrics
    latency_values: List[float] = field(default_factory=list)

    # Satisfaction metrics
    satisfaction_sum: float = 0.0
    satisfaction_count: int = 0

    # Error metrics
    error_count: int = 0
    total_requests: int = 0

    # Resolution metrics
    resolved_count: int = 0
    escalation_count: int = 0

    def accuracy(self) -> float:
        """Calculate accuracy."""
        if self.accuracy_count == 0:
            return 0.0
        return self.accuracy_sum / self.accuracy_count

    def latency_p50(self) -> float:
        """Calculate p50 latency."""
        if not self.latency_values:
            return 0.0
        return statistics.median(self.latency_values)

    def latency_p95(self) -> float:
        """Calculate p95 latency."""
        if not self.latency_values:
            return 0.0
        sorted_values = sorted(self.latency_values)
        index = int(len(sorted_values) * 0.95)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def latency_p99(self) -> float:
        """Calculate p99 latency."""
        if not self.latency_values:
            return 0.0
        sorted_values = sorted(self.latency_values)
        index = int(len(sorted_values) * 0.99)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def satisfaction(self) -> float:
        """Calculate satisfaction score."""
        if self.satisfaction_count == 0:
            return 0.0
        return self.satisfaction_sum / self.satisfaction_count

    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests

    def resolution_rate(self) -> float:
        """Calculate resolution rate."""
        total = self.resolved_count + self.escalation_count
        if total == 0:
            return 0.0
        return self.resolved_count / total

    def escalation_rate(self) -> float:
        """Calculate escalation rate."""
        total = self.resolved_count + self.escalation_count
        if total == 0:
            return 0.0
        return self.escalation_count / total

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "variant": self.variant,
            "sample_size": self.sample_size,
            "accuracy": self.accuracy(),
            "latency_p50": self.latency_p50(),
            "latency_p95": self.latency_p95(),
            "latency_p99": self.latency_p99(),
            "satisfaction": self.satisfaction(),
            "error_rate": self.error_rate(),
            "resolution_rate": self.resolution_rate(),
            "escalation_rate": self.escalation_rate(),
        }


class MetricsCollector:
    """
    Collects and aggregates metrics for A/B testing.

    Features:
    - Collect accuracy per variant
    - Collect latency per variant
    - Real-time metrics aggregation
    - Error rate tracking
    """

    def __init__(self, experiment_id: str = "default"):
        """
        Initialize the metrics collector.

        Args:
            experiment_id: Associated experiment ID
        """
        self.experiment_id = experiment_id
        self._metrics: Dict[str, VariantMetrics] = defaultdict(
            lambda: VariantMetrics(variant="unknown")
        )
        self._raw_metrics: List[MetricPoint] = []

    def record_accuracy(
        self,
        variant: str,
        is_correct: bool,
        confidence: Optional[float] = None
    ):
        """
        Record accuracy metric.

        Args:
            variant: Variant name
            is_correct: Whether prediction was correct
            confidence: Model confidence (optional)
        """
        metrics = self._metrics[variant]
        metrics.variant = variant
        metrics.accuracy_sum += 1.0 if is_correct else 0.0
        metrics.accuracy_count += 1
        metrics.sample_size += 1

        self._raw_metrics.append(MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.ACCURACY,
            variant=variant,
            value=1.0 if is_correct else 0.0,
            metadata={"confidence": confidence} if confidence else {}
        ))

    def record_latency(
        self,
        variant: str,
        latency_ms: float,
        query_type: Optional[str] = None
    ):
        """
        Record latency metric.

        Args:
            variant: Variant name
            latency_ms: Latency in milliseconds
            query_type: Type of query (optional)
        """
        metrics = self._metrics[variant]
        metrics.variant = variant
        metrics.latency_values.append(latency_ms)
        metrics.total_requests += 1

        self._raw_metrics.append(MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.LATENCY,
            variant=variant,
            value=latency_ms,
            metadata={"query_type": query_type} if query_type else {}
        ))

    def record_satisfaction(
        self,
        variant: str,
        score: float,  # 1-5 scale
        feedback: Optional[str] = None
    ):
        """
        Record user satisfaction.

        Args:
            variant: Variant name
            score: Satisfaction score (1-5)
            feedback: Optional feedback text
        """
        metrics = self._metrics[variant]
        metrics.variant = variant
        metrics.satisfaction_sum += score
        metrics.satisfaction_count += 1

        self._raw_metrics.append(MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.SATISFACTION,
            variant=variant,
            value=score,
            metadata={"feedback": feedback} if feedback else {}
        ))

    def record_error(
        self,
        variant: str,
        error_type: str,
        error_message: Optional[str] = None
    ):
        """
        Record an error.

        Args:
            variant: Variant name
            error_type: Type of error
            error_message: Error message (optional)
        """
        metrics = self._metrics[variant]
        metrics.variant = variant
        metrics.error_count += 1
        metrics.total_requests += 1

        self._raw_metrics.append(MetricPoint(
            timestamp=datetime.now(),
            metric_type=MetricType.ERROR_RATE,
            variant=variant,
            value=1.0,
            metadata={"error_type": error_type, "error_message": error_message}
        ))

    def record_resolution(
        self,
        variant: str,
        resolved: bool,
        escalated: bool = False
    ):
        """
        Record resolution/escalation.

        Args:
            variant: Variant name
            resolved: Whether issue was resolved
            escalated: Whether issue was escalated
        """
        metrics = self._metrics[variant]
        metrics.variant = variant

        if resolved:
            metrics.resolved_count += 1
        if escalated:
            metrics.escalation_count += 1

    def get_variant_metrics(self, variant: str) -> VariantMetrics:
        """Get metrics for a specific variant."""
        return self._metrics.get(variant, VariantMetrics(variant=variant))

    def get_all_metrics(self) -> Dict[str, VariantMetrics]:
        """Get metrics for all variants."""
        return dict(self._metrics)

    def get_comparison(self) -> Dict[str, Dict[str, Any]]:
        """Get comparison metrics between variants."""
        return {
            variant: metrics.to_dict()
            for variant, metrics in self._metrics.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            "experiment_id": self.experiment_id,
            "variants": list(self._metrics.keys()),
            "total_samples": sum(m.sample_size for m in self._metrics.values()),
            "total_metrics": len(self._raw_metrics),
        }

    def reset(self):
        """Reset all metrics."""
        self._metrics.clear()
        self._raw_metrics.clear()


def get_metrics_collector(experiment_id: str = "default") -> MetricsCollector:
    """Factory function to create a metrics collector."""
    return MetricsCollector(experiment_id=experiment_id)
