"""
Bottleneck Detector Module - Week 52, Builder 5
Bottleneck detection and analysis for performance optimization
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import logging
import statistics

logger = logging.getLogger(__name__)


class BottleneckType(Enum):
    """Type of bottleneck"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK = "network"
    DATABASE = "database"
    CONNECTION_POOL = "connection_pool"
    THREAD_POOL = "thread_pool"
    QUEUE = "queue"
    LOCK_CONTENTION = "lock_contention"
    GC = "garbage_collection"


class BottleneckSeverity(Enum):
    """Bottleneck severity level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceMetric:
    """Resource utilization metric"""
    resource_type: str
    utilization_percent: float
    capacity: float
    used: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Bottleneck:
    """Detected bottleneck"""
    bottleneck_type: BottleneckType
    severity: BottleneckSeverity
    location: str
    description: str
    impact: str
    current_value: float
    threshold_value: float
    detected_at: datetime = field(default_factory=datetime.utcnow)
    root_causes: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    related_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.bottleneck_type.value,
            "severity": self.severity.value,
            "location": self.location,
            "description": self.description,
            "impact": self.impact,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "detected_at": self.detected_at.isoformat(),
            "root_causes": self.root_causes,
            "recommendations": self.recommendations,
        }


@dataclass
class CorrelationResult:
    """Result of correlation analysis"""
    metric1: str
    metric2: str
    correlation_coefficient: float
    relationship: str  # positive, negative, none


class ResourceCollector:
    """
    Collects resource utilization data.
    """

    def __init__(self):
        self.metrics: Dict[str, List[ResourceMetric]] = {}

    def record(
        self,
        resource_type: str,
        utilization_percent: float,
        capacity: float,
        used: float,
    ) -> None:
        """Record resource metric"""
        metric = ResourceMetric(
            resource_type=resource_type,
            utilization_percent=utilization_percent,
            capacity=capacity,
            used=used,
        )

        if resource_type not in self.metrics:
            self.metrics[resource_type] = []
        self.metrics[resource_type].append(metric)

    def get_latest(self, resource_type: str) -> Optional[ResourceMetric]:
        """Get latest metric for a resource"""
        metrics = self.metrics.get(resource_type, [])
        return metrics[-1] if metrics else None

    def get_average(self, resource_type: str, window: int = 10) -> float:
        """Get average utilization"""
        metrics = self.metrics.get(resource_type, [])
        if not metrics:
            return 0.0
        values = [m.utilization_percent for m in metrics[-window:]]
        return statistics.mean(values) if values else 0.0


class BottleneckDetector:
    """
    Main bottleneck detection engine.
    """

    def __init__(self):
        self.collector = ResourceCollector()
        self.thresholds: Dict[str, Dict[str, float]] = {}
        self.detected_bottlenecks: List[Bottleneck] = []
        self._detection_rules: List[Dict[str, Any]] = []
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Setup default detection rules"""
        # CPU bottleneck
        self._detection_rules.append({
            "type": BottleneckType.CPU,
            "resource": "cpu",
            "warning_threshold": 70,
            "critical_threshold": 90,
            "check_sustained": True,
            "sustained_window": 5,
        })

        # Memory bottleneck
        self._detection_rules.append({
            "type": BottleneckType.MEMORY,
            "resource": "memory",
            "warning_threshold": 75,
            "critical_threshold": 90,
            "check_sustained": True,
            "sustained_window": 3,
        })

        # Disk I/O bottleneck
        self._detection_rules.append({
            "type": BottleneckType.DISK_IO,
            "resource": "disk_io",
            "warning_threshold": 80,
            "critical_threshold": 95,
        })

        # Network bottleneck
        self._detection_rules.append({
            "type": BottleneckType.NETWORK,
            "resource": "network",
            "warning_threshold": 80,
            "critical_threshold": 95,
        })

        # Connection pool bottleneck
        self._detection_rules.append({
            "type": BottleneckType.CONNECTION_POOL,
            "resource": "connections",
            "warning_threshold": 80,
            "critical_threshold": 95,
        })

    def set_custom_threshold(
        self,
        resource: str,
        warning: float,
        critical: float,
    ) -> None:
        """Set custom thresholds for a resource"""
        self.thresholds[resource] = {
            "warning": warning,
            "critical": critical,
        }

    def record_resource(
        self,
        resource_type: str,
        utilization_percent: float,
        capacity: float = 100,
        used: float = None,
    ) -> None:
        """Record resource utilization"""
        used = used if used is not None else utilization_percent
        self.collector.record(resource_type, utilization_percent, capacity, used)

    def detect(self) -> List[Bottleneck]:
        """Run bottleneck detection"""
        detected = []

        for rule in self._detection_rules:
            bottleneck = self._apply_rule(rule)
            if bottleneck:
                detected.append(bottleneck)
                self.detected_bottlenecks.append(bottleneck)

        return detected

    def _apply_rule(self, rule: Dict[str, Any]) -> Optional[Bottleneck]:
        """Apply a detection rule"""
        resource = rule["resource"]
        latest = self.collector.get_latest(resource)

        if not latest:
            return None

        # Check sustained if required
        if rule.get("check_sustained"):
            window = rule.get("sustained_window", 5)
            avg = self.collector.get_average(resource, window)
            if avg < rule["warning_threshold"]:
                return None
            current_value = avg
        else:
            current_value = latest.utilization_percent

        # Determine severity
        severity = None
        if current_value >= rule["critical_threshold"]:
            severity = BottleneckSeverity.CRITICAL
        elif current_value >= rule["warning_threshold"]:
            severity = BottleneckSeverity.HIGH

        if not severity:
            return None

        # Create bottleneck
        bottleneck = Bottleneck(
            bottleneck_type=rule["type"],
            severity=severity,
            location=f"{resource}_subsystem",
            description=f"{resource.upper()} utilization at {current_value:.1f}%",
            impact=f"Performance degradation due to {resource} bottleneck",
            current_value=current_value,
            threshold_value=rule["warning_threshold"],
            root_causes=self._identify_root_causes(rule["type"], current_value),
            recommendations=self._get_recommendations(rule["type"], severity),
        )

        return bottleneck

    def _identify_root_causes(
        self,
        bottleneck_type: BottleneckType,
        value: float,
    ) -> List[str]:
        """Identify potential root causes"""
        causes = []

        if bottleneck_type == BottleneckType.CPU:
            causes = [
                "High computational workload",
                "Inefficient algorithms",
                "Excessive context switching",
                "Insufficient CPU resources",
            ]
        elif bottleneck_type == BottleneckType.MEMORY:
            causes = [
                "Memory leaks",
                "Large object allocations",
                "Insufficient heap size",
                "Excessive caching",
            ]
        elif bottleneck_type == BottleneckType.DISK_IO:
            causes = [
                "High read/write operations",
                "Slow storage device",
                "Inefficient queries",
                "Missing indexes",
            ]
        elif bottleneck_type == BottleneckType.NETWORK:
            causes = [
                "Bandwidth saturation",
                "High latency connections",
                "Network congestion",
                "Inefficient protocols",
            ]
        elif bottleneck_type == BottleneckType.CONNECTION_POOL:
            causes = [
                "Connection leaks",
                "Insufficient pool size",
                "Long-running transactions",
                "Blocking operations",
            ]

        return causes

    def _get_recommendations(
        self,
        bottleneck_type: BottleneckType,
        severity: BottleneckSeverity,
    ) -> List[str]:
        """Get recommendations for bottleneck"""
        recommendations = []

        if bottleneck_type == BottleneckType.CPU:
            recommendations = [
                "Optimize CPU-intensive algorithms",
                "Consider horizontal scaling",
                "Profile application for hotspots",
                "Enable CPU autoscaling",
            ]
        elif bottleneck_type == BottleneckType.MEMORY:
            recommendations = [
                "Investigate memory leaks",
                "Optimize data structures",
                "Increase memory allocation",
                "Implement object pooling",
            ]
        elif bottleneck_type == BottleneckType.DISK_IO:
            recommendations = [
                "Optimize database queries",
                "Add appropriate indexes",
                "Consider SSD storage",
                "Implement caching layer",
            ]
        elif bottleneck_type == BottleneckType.NETWORK:
            recommendations = [
                "Optimize data transfer size",
                "Enable compression",
                "Use connection pooling",
                "Consider CDN for static content",
            ]
        elif bottleneck_type == BottleneckType.CONNECTION_POOL:
            recommendations = [
                "Increase connection pool size",
                "Optimize connection lifecycle",
                "Check for connection leaks",
                "Implement connection timeout",
            ]

        if severity == BottleneckSeverity.CRITICAL:
            recommendations.insert(0, "IMMEDIATE ACTION REQUIRED")

        return recommendations

    def analyze_correlations(
        self,
        metric1: str,
        metric2: str,
    ) -> CorrelationResult:
        """Analyze correlation between two metrics"""
        metrics1 = self.collector.metrics.get(metric1, [])
        metrics2 = self.collector.metrics.get(metric2, [])

        if not metrics1 or not metrics2:
            return CorrelationResult(
                metric1=metric1,
                metric2=metric2,
                correlation_coefficient=0,
                relationship="none",
            )

        # Get aligned values
        values1 = [m.utilization_percent for m in metrics1]
        values2 = [m.utilization_percent for m in metrics2]

        # Ensure same length
        min_len = min(len(values1), len(values2))
        values1 = values1[-min_len:]
        values2 = values2[-min_len:]

        if min_len < 2:
            return CorrelationResult(
                metric1=metric1,
                metric2=metric2,
                correlation_coefficient=0,
                relationship="none",
            )

        # Calculate Pearson correlation
        n = len(values1)
        sum_x = sum(values1)
        sum_y = sum(values2)
        sum_xy = sum(x * y for x, y in zip(values1, values2))
        sum_x2 = sum(x * x for x in values1)
        sum_y2 = sum(y * y for y in values2)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)) ** 0.5

        if denominator == 0:
            correlation = 0
        else:
            correlation = numerator / denominator

        # Determine relationship
        if correlation > 0.7:
            relationship = "positive"
        elif correlation < -0.7:
            relationship = "negative"
        else:
            relationship = "none"

        return CorrelationResult(
            metric1=metric1,
            metric2=metric2,
            correlation_coefficient=correlation,
            relationship=relationship,
        )

    def get_bottleneck_summary(self) -> Dict[str, Any]:
        """Get summary of detected bottlenecks"""
        summary = {
            "total_detected": len(self.detected_bottlenecks),
            "by_severity": {},
            "by_type": {},
            "recent": [],
        }

        # Count by severity
        for severity in BottleneckSeverity:
            count = sum(
                1 for b in self.detected_bottlenecks
                if b.severity == severity
            )
            summary["by_severity"][severity.value] = count

        # Count by type
        for btype in BottleneckType:
            count = sum(
                1 for b in self.detected_bottlenecks
                if b.bottleneck_type == btype
            )
            summary["by_type"][btype.value] = count

        # Recent bottlenecks
        summary["recent"] = [b.to_dict() for b in self.detected_bottlenecks[-10:]]

        return summary

    def clear_history(self) -> None:
        """Clear detection history"""
        self.detected_bottlenecks.clear()


class BottleneckPredictor:
    """
    Predicts future bottlenecks based on trends.
    """

    def __init__(self, detector: BottleneckDetector):
        self.detector = detector

    def predict_bottleneck(
        self,
        resource: str,
        minutes_ahead: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """Predict if a bottleneck will occur"""
        metrics = self.detector.collector.metrics.get(resource, [])

        if len(metrics) < 10:
            return None

        values = [m.utilization_percent for m in metrics]

        # Calculate trend
        n = len(values)
        x = list(range(n))
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(xi * yi for xi, yi in zip(x, values))
        sum_x2 = sum(xi * xi for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0

        # Project future value
        current = values[-1]
        future_value = current + slope * minutes_ahead

        if future_value >= 90:
            return {
                "resource": resource,
                "predicted_value": future_value,
                "current_value": current,
                "minutes_ahead": minutes_ahead,
                "severity": "critical",
                "message": f"{resource} predicted to reach {future_value:.1f}% in {minutes_ahead} minutes",
            }
        elif future_value >= 70:
            return {
                "resource": resource,
                "predicted_value": future_value,
                "current_value": current,
                "minutes_ahead": minutes_ahead,
                "severity": "warning",
                "message": f"{resource} predicted to reach {future_value:.1f}% in {minutes_ahead} minutes",
            }

        return None
