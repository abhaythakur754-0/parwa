"""
Performance Analytics Module - Week 52, Builder 5
Performance analytics engine for insights and analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import statistics

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Performance metric type"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK = "network"
    CONNECTIONS = "connections"


class TrendDirection(Enum):
    """Trend direction enum"""
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"
    UNKNOWN = "unknown"


class Severity(Enum):
    """Issue severity"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Single performance metric"""
    name: str
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PerformanceInsight:
    """Performance insight/finding"""
    title: str
    description: str
    severity: Severity
    metric_type: MetricType
    current_value: float
    expected_value: Optional[float]
    trend: TrendDirection
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MetricStats:
    """Statistics for a metric"""
    count: int = 0
    mean: float = 0.0
    min: float = 0.0
    max: float = 0.0
    std_dev: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    last_value: float = 0.0
    trend: TrendDirection = TrendDirection.UNKNOWN


class TimeSeriesStore:
    """
    Stores time series performance data.
    """

    def __init__(self, max_points: int = 10000):
        self.max_points = max_points
        self.data: Dict[str, List[PerformanceMetric]] = {}

    def add(self, metric: PerformanceMetric) -> None:
        """Add a metric data point"""
        key = f"{metric.metric_type.value}:{metric.name}"

        if key not in self.data:
            self.data[key] = []

        self.data[key].append(metric)

        # Enforce max points
        if len(self.data[key]) > self.max_points:
            self.data[key] = self.data[key][-self.max_points:]

    def get_series(
        self,
        metric_type: MetricType,
        name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[PerformanceMetric]:
        """Get metric series for time range"""
        key = f"{metric_type.value}:{name}"
        series = self.data.get(key, [])

        if start:
            series = [m for m in series if m.timestamp >= start]
        if end:
            series = [m for m in series if m.timestamp <= end]

        return series

    def get_latest(self, metric_type: MetricType, name: str) -> Optional[PerformanceMetric]:
        """Get latest metric value"""
        key = f"{metric_type.value}:{name}"
        series = self.data.get(key, [])
        return series[-1] if series else None

    def get_all_types(self) -> List[Tuple[MetricType, str]]:
        """Get all metric type/name combinations"""
        result = []
        for key in self.data.keys():
            parts = key.split(":", 1)
            if len(parts) == 2:
                metric_type = MetricType(parts[0])
                name = parts[1]
                result.append((metric_type, name))
        return result


class MetricsAnalyzer:
    """
    Analyzes performance metrics.
    """

    def __init__(self, store: TimeSeriesStore):
        self.store = store

    def calculate_stats(
        self,
        metric_type: MetricType,
        name: str,
        window: int = 100,
    ) -> MetricStats:
        """Calculate statistics for a metric"""
        series = self.store.get_series(metric_type, name)
        if not series:
            return MetricStats()

        values = [m.value for m in series[-window:]]
        if not values:
            return MetricStats()

        sorted_values = sorted(values)

        def percentile(p: float) -> float:
            if not sorted_values:
                return 0.0
            idx = int(p / 100 * (len(sorted_values) - 1))
            return sorted_values[idx]

        return MetricStats(
            count=len(values),
            mean=statistics.mean(values),
            min=min(values),
            max=max(values),
            std_dev=statistics.stdev(values) if len(values) >= 2 else 0,
            p50=percentile(50),
            p95=percentile(95),
            p99=percentile(99),
            last_value=values[-1],
            trend=self._calculate_trend(values),
        )

    def _calculate_trend(self, values: List[float]) -> TrendDirection:
        """Calculate trend direction"""
        if len(values) < 5:
            return TrendDirection.UNKNOWN

        first_half = statistics.mean(values[:len(values)//2])
        second_half = statistics.mean(values[len(values)//2:])

        if first_half == 0:
            return TrendDirection.STABLE

        change = (second_half - first_half) / first_half

        if change > 0.1:
            return TrendDirection.DEGRADING  # Higher values = worse for most metrics
        elif change < -0.1:
            return TrendDirection.IMPROVING
        return TrendDirection.STABLE

    def compare_periods(
        self,
        metric_type: MetricType,
        name: str,
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime,
    ) -> Dict[str, Any]:
        """Compare metric between two periods"""
        series1 = self.store.get_series(metric_type, name, period1_start, period1_end)
        series2 = self.store.get_series(metric_type, name, period2_start, period2_end)

        values1 = [m.value for m in series1]
        values2 = [m.value for m in series2]

        mean1 = statistics.mean(values1) if values1 else 0
        mean2 = statistics.mean(values2) if values2 else 0

        change = ((mean2 - mean1) / mean1 * 100) if mean1 != 0 else 0

        return {
            "period1_mean": mean1,
            "period2_mean": mean2,
            "change_percent": change,
            "period1_count": len(values1),
            "period2_count": len(values2),
        }


class PerformanceAnalytics:
    """
    Main performance analytics engine.
    """

    def __init__(self):
        self.store = TimeSeriesStore()
        self.analyzer = MetricsAnalyzer(self.store)
        self.thresholds: Dict[str, Dict[str, float]] = {}
        self.insights: List[PerformanceInsight] = []

    def set_threshold(
        self,
        metric_type: MetricType,
        name: str,
        warning: float,
        critical: float,
    ) -> None:
        """Set thresholds for a metric"""
        key = f"{metric_type.value}:{name}"
        self.thresholds[key] = {
            "warning": warning,
            "critical": critical,
        }

    def record(
        self,
        metric_type: MetricType,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a performance metric"""
        metric = PerformanceMetric(
            name=name,
            metric_type=metric_type,
            value=value,
            unit=unit,
            tags=tags or {},
        )
        self.store.add(metric)

        # Check thresholds
        self._check_threshold(metric)

    def _check_threshold(self, metric: PerformanceMetric) -> None:
        """Check if metric exceeds threshold"""
        key = f"{metric.metric_type.value}:{metric.name}"
        thresholds = self.thresholds.get(key)

        if not thresholds:
            return

        severity = None
        if metric.value >= thresholds["critical"]:
            severity = Severity.CRITICAL
        elif metric.value >= thresholds["warning"]:
            severity = Severity.WARNING

        if severity:
            trend = self.analyzer._calculate_trend(
                [m.value for m in self.store.get_series(metric.metric_type, metric.name)[-20:]]
            )
            insight = PerformanceInsight(
                title=f"{metric.name} {severity.value}",
                description=f"{metric.name} is at {metric.value} {metric.unit}",
                severity=severity,
                metric_type=metric.metric_type,
                current_value=metric.value,
                expected_value=thresholds["warning"],
                trend=trend,
                recommendation=f"Investigate {metric.name} and consider optimization",
            )
            self.insights.append(insight)

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for performance dashboard"""
        dashboard = {
            "metrics": {},
            "insights": [],
            "summary": {},
        }

        # Get stats for all metrics
        for metric_type, name in self.store.get_all_types():
            stats = self.analyzer.calculate_stats(metric_type, name)
            key = f"{metric_type.value}:{name}"
            dashboard["metrics"][key] = {
                "mean": stats.mean,
                "min": stats.min,
                "max": stats.max,
                "p95": stats.p95,
                "trend": stats.trend.value,
                "last_value": stats.last_value,
            }

        # Get recent insights
        dashboard["insights"] = [
            {
                "title": i.title,
                "severity": i.severity.value,
                "description": i.description,
                "recommendation": i.recommendation,
            }
            for i in self.insights[-20:]
        ]

        # Summary
        dashboard["summary"] = {
            "total_metrics": len(dashboard["metrics"]),
            "total_insights": len(self.insights),
            "critical_count": sum(1 for i in self.insights if i.severity == Severity.CRITICAL),
            "warning_count": sum(1 for i in self.insights if i.severity == Severity.WARNING),
        }

        return dashboard

    def get_metric_report(
        self,
        metric_type: MetricType,
        name: str,
    ) -> Dict[str, Any]:
        """Get detailed report for a metric"""
        stats = self.analyzer.calculate_stats(metric_type, name)
        series = self.store.get_series(metric_type, name)

        return {
            "metric_type": metric_type.value,
            "name": name,
            "stats": {
                "count": stats.count,
                "mean": stats.mean,
                "min": stats.min,
                "max": stats.max,
                "std_dev": stats.std_dev,
                "p50": stats.p50,
                "p95": stats.p95,
                "p99": stats.p99,
                "trend": stats.trend.value,
            },
            "data_points": [
                {"timestamp": m.timestamp.isoformat(), "value": m.value}
                for m in series[-100:]  # Last 100 points
            ],
        }

    def get_trend_analysis(
        self,
        metric_type: MetricType,
        name: str,
    ) -> Dict[str, Any]:
        """Get trend analysis for a metric"""
        stats = self.analyzer.calculate_stats(metric_type, name)
        series = self.store.get_series(metric_type, name)

        if len(series) < 10:
            return {
                "trend": "insufficient_data",
                "message": "Not enough data points for trend analysis",
            }

        values = [m.value for m in series]

        # Calculate trend line
        n = len(values)
        x = list(range(n))
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(xi * yi for xi, yi in zip(x, values))
        sum_x2 = sum(xi * xi for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0

        return {
            "trend": stats.trend.value,
            "slope": slope,
            "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
            "current": stats.last_value,
            "mean": stats.mean,
            "variability": stats.std_dev / stats.mean if stats.mean != 0 else 0,
        }

    def clear_insights(self) -> None:
        """Clear all insights"""
        self.insights.clear()

    def export_data(self) -> Dict[str, Any]:
        """Export all analytics data"""
        return {
            "exported_at": datetime.utcnow().isoformat(),
            "metrics": {
                key: [m.to_dict() for m in series]
                for key, series in self.store.data.items()
            },
            "insights": [
                {
                    "title": i.title,
                    "severity": i.severity.value,
                    "description": i.description,
                    "recommendation": i.recommendation,
                }
                for i in self.insights
            ],
        }
