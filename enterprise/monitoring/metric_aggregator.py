"""
Metric Aggregator Module - Week 53, Builder 1
Metric aggregation engine for real-time monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import statistics
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class AggregationType(Enum):
    """Aggregation type enum"""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    P50 = "p50"
    P95 = "p95"
    P99 = "p99"
    RATE = "rate"
    DERIVATIVE = "derivative"


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series of metric points"""
    name: str
    points: List[MetricPoint] = field(default_factory=list)
    unit: str = ""
    description: str = ""

    def add_point(
        self,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a data point"""
        point = MetricPoint(
            timestamp=timestamp or datetime.utcnow(),
            value=value,
            labels=labels or {},
        )
        self.points.append(point)

    def get_values(self) -> List[float]:
        """Get all values"""
        return [p.value for p in self.points]

    def get_latest(self) -> Optional[float]:
        """Get latest value"""
        return self.points[-1].value if self.points else None


@dataclass
class AggregatedMetric:
    """Aggregated metric result"""
    name: str
    aggregation: AggregationType
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    window_seconds: int = 60
    sample_count: int = 0
    labels: Dict[str, str] = field(default_factory=dict)


class TimeWindow:
    """
    Manages time-windowed data storage.
    """

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self._data: List[Tuple[datetime, float, Dict]] = []
        self._lock = threading.Lock()

    def add(
        self,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a value to the window"""
        with self._lock:
            ts = timestamp or datetime.utcnow()
            self._data.append((ts, value, labels or {}))
            self._prune()

    def _prune(self) -> None:
        """Remove old entries"""
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_seconds)
        self._data = [(ts, v, l) for ts, v, l in self._data if ts > cutoff]

    def get_values(self) -> List[float]:
        """Get all values in window"""
        with self._lock:
            self._prune()
            return [v for _, v, _ in self._data]

    def get_entries(self) -> List[Tuple[datetime, float, Dict]]:
        """Get all entries in window"""
        with self._lock:
            self._prune()
            return list(self._data)

    def get_count(self) -> int:
        """Get count of entries"""
        with self._lock:
            self._prune()
            return len(self._data)


class MetricAggregator:
    """
    Main metric aggregation engine.
    """

    def __init__(self, default_window: int = 300):
        self.default_window = default_window
        self.series: Dict[str, MetricSeries] = {}
        self.windows: Dict[str, TimeWindow] = {}
        self._lock = threading.Lock()

    def record(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a metric value"""
        with self._lock:
            if name not in self.series:
                self.series[name] = MetricSeries(name=name)
            if name not in self.windows:
                self.windows[name] = TimeWindow(self.default_window)

            self.series[name].add_point(value, labels, timestamp)
            self.windows[name].add(value, labels, timestamp)

    def record_batch(
        self,
        metrics: Dict[str, float],
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record multiple metrics at once"""
        for name, value in metrics.items():
            self.record(name, value, labels)

    def aggregate(
        self,
        name: str,
        agg_type: AggregationType,
        window_seconds: Optional[int] = None,
    ) -> Optional[AggregatedMetric]:
        """Aggregate a metric"""
        if name not in self.series:
            return None

        window = self.windows.get(name)
        if not window:
            return None

        values = window.get_values()
        if not values:
            return None

        # Apply aggregation
        if agg_type == AggregationType.SUM:
            value = sum(values)
        elif agg_type == AggregationType.AVG:
            value = statistics.mean(values)
        elif agg_type == AggregationType.MIN:
            value = min(values)
        elif agg_type == AggregationType.MAX:
            value = max(values)
        elif agg_type == AggregationType.COUNT:
            value = float(len(values))
        elif agg_type == AggregationType.P50:
            value = self._percentile(values, 50)
        elif agg_type == AggregationType.P95:
            value = self._percentile(values, 95)
        elif agg_type == AggregationType.P99:
            value = self._percentile(values, 99)
        elif agg_type == AggregationType.RATE:
            value = self._calculate_rate(window)
        elif agg_type == AggregationType.DERIVATIVE:
            value = self._calculate_derivative(window)
        else:
            value = statistics.mean(values)

        return AggregatedMetric(
            name=name,
            aggregation=agg_type,
            value=value,
            window_seconds=window_seconds or self.default_window,
            sample_count=len(values),
        )

    def _percentile(self, values: List[float], p: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        idx = (p / 100) * (len(sorted_values) - 1)
        lower = int(idx)
        upper = lower + 1
        if upper >= len(sorted_values):
            return sorted_values[-1]
        weight = idx - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    def _calculate_rate(self, window: TimeWindow) -> float:
        """Calculate rate (per second)"""
        entries = window.get_entries()
        if len(entries) < 2:
            return 0.0

        total = sum(v for _, v, _ in entries)
        duration = (entries[-1][0] - entries[0][0]).total_seconds()
        return total / duration if duration > 0 else 0.0

    def _calculate_derivative(self, window: TimeWindow) -> float:
        """Calculate rate of change"""
        entries = window.get_entries()
        if len(entries) < 2:
            return 0.0

        first = entries[0]
        last = entries[-1]
        duration = (last[0] - first[0]).total_seconds()

        return (last[1] - first[1]) / duration if duration > 0 else 0.0

    def get_series(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series"""
        return self.series.get(name)

    def get_all_names(self) -> List[str]:
        """Get all metric names"""
        return list(self.series.keys())

    def get_latest(self, name: str) -> Optional[float]:
        """Get latest value for a metric"""
        series = self.series.get(name)
        return series.get_latest() if series else None

    def get_all_latest(self) -> Dict[str, float]:
        """Get latest values for all metrics"""
        return {
            name: series.get_latest()
            for name, series in self.series.items()
            if series.get_latest() is not None
        }

    def aggregate_all(
        self,
        agg_type: AggregationType,
        window_seconds: Optional[int] = None,
    ) -> Dict[str, AggregatedMetric]:
        """Aggregate all metrics"""
        results = {}
        for name in self.series.keys():
            result = self.aggregate(name, agg_type, window_seconds)
            if result:
                results[name] = result
        return results

    def get_statistics(self, name: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a metric"""
        series = self.series.get(name)
        if not series or not series.points:
            return {}

        values = series.get_values()
        window = self.windows.get(name)

        stats = {
            "name": name,
            "count": len(values),
            "latest": series.get_latest(),
            "min": min(values) if values else 0,
            "max": max(values) if values else 0,
            "avg": statistics.mean(values) if values else 0,
            "std_dev": statistics.stdev(values) if len(values) >= 2 else 0,
            "p50": self._percentile(values, 50),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
            "sum": sum(values),
            "window_count": window.get_count() if window else 0,
        }

        return stats

    def clear(self, name: Optional[str] = None) -> None:
        """Clear metrics"""
        with self._lock:
            if name:
                self.series.pop(name, None)
                self.windows.pop(name, None)
            else:
                self.series.clear()
                self.windows.clear()


class MetricRegistry:
    """
    Registry for metric definitions and aggregation rules.
    """

    def __init__(self):
        self.aggregator = MetricAggregator()
        self._definitions: Dict[str, Dict[str, Any]] = {}
        self._rules: List[Dict[str, Any]] = []

    def define_metric(
        self,
        name: str,
        description: str = "",
        unit: str = "",
        default_aggregation: AggregationType = AggregationType.AVG,
        alert_threshold: Optional[float] = None,
    ) -> None:
        """Define a metric"""
        self._definitions[name] = {
            "name": name,
            "description": description,
            "unit": unit,
            "default_aggregation": default_aggregation,
            "alert_threshold": alert_threshold,
        }

    def add_aggregation_rule(
        self,
        source_metric: str,
        target_metric: str,
        aggregation: AggregationType,
        window_seconds: int,
    ) -> None:
        """Add an aggregation rule"""
        self._rules.append({
            "source": source_metric,
            "target": target_metric,
            "aggregation": aggregation,
            "window": window_seconds,
        })

    def get_definition(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metric definition"""
        return self._definitions.get(name)

    def get_all_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get all metric definitions"""
        return self._definitions.copy()

    def apply_rules(self) -> Dict[str, AggregatedMetric]:
        """Apply all aggregation rules"""
        results = {}
        for rule in self._rules:
            result = self.aggregator.aggregate(
                rule["source"],
                rule["aggregation"],
                rule["window"],
            )
            if result:
                results[rule["target"]] = result
        return results


class MultiMetricAggregator:
    """
    Aggregator for multiple related metrics.
    """

    def __init__(self):
        self.aggregators: Dict[str, MetricAggregator] = {}

    def get_aggregator(self, namespace: str) -> MetricAggregator:
        """Get or create aggregator for namespace"""
        if namespace not in self.aggregators:
            self.aggregators[namespace] = MetricAggregator()
        return self.aggregators[namespace]

    def record(
        self,
        namespace: str,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric in a namespace"""
        agg = self.get_aggregator(namespace)
        agg.record(name, value, labels)

    def get_all_latest(self) -> Dict[str, Dict[str, float]]:
        """Get all latest values across namespaces"""
        return {
            ns: agg.get_all_latest()
            for ns, agg in self.aggregators.items()
        }
