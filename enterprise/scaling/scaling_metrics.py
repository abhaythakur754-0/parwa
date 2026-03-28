"""
Scaling Metrics Module - Week 52, Builder 1
Scaling metrics collection and aggregation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict
import statistics
import logging
import asyncio
import time

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric type enum"""
    GAUGE = "gauge"  # Point-in-time value
    COUNTER = "counter"  # Cumulative value
    HISTOGRAM = "histogram"  # Distribution of values
    RATE = "rate"  # Rate of change


class AggregationType(Enum):
    """Aggregation type enum"""
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    P50 = "p50"
    P95 = "p95"
    P99 = "p99"
    COUNT = "count"
    LAST = "last"


@dataclass
class MetricPoint:
    """Single metric data point"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class MetricSeries:
    """Time series of metric points"""
    name: str
    points: List[MetricPoint] = field(default_factory=list)
    metric_type: MetricType = MetricType.GAUGE
    retention_seconds: int = 3600  # 1 hour default

    def add_point(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a data point to the series"""
        point = MetricPoint(
            name=self.name,
            value=value,
            tags=tags or {},
            metric_type=self.metric_type,
        )
        self.points.append(point)
        self._prune_old_points()

    def _prune_old_points(self) -> None:
        """Remove points older than retention period"""
        cutoff = datetime.utcnow() - timedelta(seconds=self.retention_seconds)
        self.points = [p for p in self.points if p.timestamp > cutoff]

    def get_values(self) -> List[float]:
        """Get all values as a list"""
        return [p.value for p in self.points]

    def get_latest(self) -> Optional[float]:
        """Get the latest value"""
        if self.points:
            return self.points[-1].value
        return None

    def aggregate(self, agg_type: AggregationType) -> Optional[float]:
        """Aggregate values"""
        values = self.get_values()
        if not values:
            return None

        if agg_type == AggregationType.AVG:
            return statistics.mean(values)
        elif agg_type == AggregationType.MIN:
            return min(values)
        elif agg_type == AggregationType.MAX:
            return max(values)
        elif agg_type == AggregationType.SUM:
            return sum(values)
        elif agg_type == AggregationType.P50:
            return statistics.median(values)
        elif agg_type == AggregationType.P95:
            return self._percentile(values, 95)
        elif agg_type == AggregationType.P99:
            return self._percentile(values, 99)
        elif agg_type == AggregationType.COUNT:
            return float(len(values))
        elif agg_type == AggregationType.LAST:
            return values[-1]

        return None

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile"""
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        lower = int(index)
        upper = lower + 1
        if upper >= len(sorted_values):
            return sorted_values[-1]
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


class MetricsCollector:
    """
    Central metrics collection system for scaling decisions.
    """

    def __init__(self, default_retention: int = 3600):
        self.default_retention = default_retention
        self.series: Dict[str, MetricSeries] = {}
        self._collectors: Dict[str, Callable] = {}
        self._last_collection: Dict[str, datetime] = {}
        self._collection_interval: int = 60

    def register_metric(
        self,
        name: str,
        metric_type: MetricType = MetricType.GAUGE,
        retention_seconds: Optional[int] = None,
    ) -> MetricSeries:
        """Register a new metric"""
        series = MetricSeries(
            name=name,
            metric_type=metric_type,
            retention_seconds=retention_seconds or self.default_retention,
        )
        self.series[name] = series
        logger.info(f"Registered metric: {name}")
        return series

    def unregister_metric(self, name: str) -> bool:
        """Unregister a metric"""
        if name in self.series:
            del self.series[name]
            return True
        return False

    def record(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Record a metric value"""
        if name not in self.series:
            self.register_metric(name)

        self.series[name].add_point(value, tags)
        return True

    def record_batch(self, metrics: Dict[str, float]) -> int:
        """Record multiple metrics at once"""
        count = 0
        for name, value in metrics.items():
            self.record(name, value)
            count += 1
        return count

    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series by name"""
        return self.series.get(name)

    def get_latest(self, name: str) -> Optional[float]:
        """Get the latest value for a metric"""
        series = self.get_metric(name)
        return series.get_latest() if series else None

    def get_aggregated(
        self,
        name: str,
        agg_type: AggregationType,
        window_seconds: Optional[int] = None,
    ) -> Optional[float]:
        """Get aggregated value for a metric"""
        series = self.get_metric(name)
        if not series:
            return None

        if window_seconds:
            # Create a temporary series with limited window
            cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
            filtered_series = MetricSeries(
                name=name,
                metric_type=series.metric_type,
            )
            filtered_series.points = [
                p for p in series.points if p.timestamp > cutoff
            ]
            return filtered_series.aggregate(agg_type)

        return series.aggregate(agg_type)

    def register_collector(
        self,
        name: str,
        collector: Callable[[], Dict[str, float]],
    ) -> None:
        """Register a metric collector function"""
        self._collectors[name] = collector
        logger.info(f"Registered collector: {name}")

    def collect_all(self) -> Dict[str, float]:
        """Run all collectors and return collected metrics"""
        all_metrics = {}

        for name, collector in self._collectors.items():
            try:
                metrics = collector()
                all_metrics.update(metrics)
                self._last_collection[name] = datetime.utcnow()
            except Exception as e:
                logger.error(f"Collector {name} failed: {e}")

        # Record all collected metrics
        self.record_batch(all_metrics)
        return all_metrics

    def get_all_latest(self) -> Dict[str, float]:
        """Get latest values for all metrics"""
        return {
            name: series.get_latest()
            for name, series in self.series.items()
            if series.get_latest() is not None
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get collector statistics"""
        return {
            "total_metrics": len(self.series),
            "total_collectors": len(self._collectors),
            "metrics": {
                name: {
                    "points_count": len(series.points),
                    "latest": series.get_latest(),
                    "type": series.metric_type.value,
                }
                for name, series in self.series.items()
            },
            "last_collection": {
                name: dt.isoformat()
                for name, dt in self._last_collection.items()
            },
        }


class ResourceMetrics:
    """
    Resource-specific metrics collector for CPU, memory, etc.
    """

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self._register_default_metrics()

    def _register_default_metrics(self) -> None:
        """Register default resource metrics"""
        self.collector.register_metric("cpu_usage", MetricType.GAUGE)
        self.collector.register_metric("memory_usage", MetricType.GAUGE)
        self.collector.register_metric("disk_usage", MetricType.GAUGE)
        self.collector.register_metric("network_in", MetricType.RATE)
        self.collector.register_metric("network_out", MetricType.RATE)
        self.collector.register_metric("request_count", MetricType.COUNTER)
        self.collector.register_metric("request_latency", MetricType.HISTOGRAM)
        self.collector.register_metric("active_connections", MetricType.GAUGE)

    def record_cpu(self, usage: float, host: Optional[str] = None) -> None:
        """Record CPU usage percentage"""
        tags = {"host": host} if host else None
        self.collector.record("cpu_usage", usage, tags)

    def record_memory(self, usage: float, host: Optional[str] = None) -> None:
        """Record memory usage percentage"""
        tags = {"host": host} if host else None
        self.collector.record("memory_usage", usage, tags)

    def record_disk(self, usage: float, host: Optional[str] = None) -> None:
        """Record disk usage percentage"""
        tags = {"host": host} if host else None
        self.collector.record("disk_usage", usage, tags)

    def record_network(
        self,
        bytes_in: float,
        bytes_out: float,
        host: Optional[str] = None,
    ) -> None:
        """Record network I/O"""
        tags = {"host": host} if host else None
        self.collector.record("network_in", bytes_in, tags)
        self.collector.record("network_out", bytes_out, tags)

    def record_request(
        self,
        latency: float,
        endpoint: Optional[str] = None,
    ) -> None:
        """Record a request with latency"""
        tags = {"endpoint": endpoint} if endpoint else None
        self.collector.record("request_latency", latency, tags)

        # Increment request counter
        current = self.collector.get_latest("request_count") or 0
        self.collector.record("request_count", current + 1, tags)

    def record_connections(self, count: int, host: Optional[str] = None) -> None:
        """Record active connections"""
        tags = {"host": host} if host else None
        self.collector.record("active_connections", count, tags)

    def get_resource_summary(self) -> Dict[str, Any]:
        """Get summary of resource metrics"""
        return {
            "cpu": {
                "current": self.collector.get_latest("cpu_usage"),
                "avg_5m": self.collector.get_aggregated(
                    "cpu_usage", AggregationType.AVG, 300
                ),
                "max_5m": self.collector.get_aggregated(
                    "cpu_usage", AggregationType.MAX, 300
                ),
            },
            "memory": {
                "current": self.collector.get_latest("memory_usage"),
                "avg_5m": self.collector.get_aggregated(
                    "memory_usage", AggregationType.AVG, 300
                ),
                "max_5m": self.collector.get_aggregated(
                    "memory_usage", AggregationType.MAX, 300
                ),
            },
            "disk": {
                "current": self.collector.get_latest("disk_usage"),
            },
            "network": {
                "in_rate": self.collector.get_latest("network_in"),
                "out_rate": self.collector.get_latest("network_out"),
            },
            "requests": {
                "count": self.collector.get_latest("request_count"),
                "latency_avg": self.collector.get_aggregated(
                    "request_latency", AggregationType.AVG, 300
                ),
                "latency_p95": self.collector.get_aggregated(
                    "request_latency", AggregationType.P95, 300
                ),
            },
            "connections": {
                "current": self.collector.get_latest("active_connections"),
            },
        }


class ScalingMetricsAggregator:
    """
    Aggregates metrics for scaling decisions.
    """

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    def calculate_load_score(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Calculate a combined load score from multiple metrics.
        Higher score indicates more load.
        """
        default_weights = {
            "cpu_usage": 0.4,
            "memory_usage": 0.3,
            "request_latency": 0.2,
            "active_connections": 0.1,
        }
        weights = weights or default_weights

        score = 0.0
        total_weight = 0.0

        for metric, weight in weights.items():
            value = self.collector.get_latest(metric)
            if value is not None:
                # Normalize to 0-100 scale
                normalized = min(100, max(0, value))
                score += normalized * weight
                total_weight += weight

        if total_weight > 0:
            score /= total_weight

        return score

    def get_scaling_metrics(self) -> Dict[str, Any]:
        """Get all metrics relevant for scaling decisions"""
        return {
            "current": self.collector.get_all_latest(),
            "load_score": self.calculate_load_score(),
            "cpu_trend": self._calculate_trend("cpu_usage"),
            "memory_trend": self._calculate_trend("memory_usage"),
            "latency_p95": self.collector.get_aggregated(
                "request_latency", AggregationType.P95, 300
            ),
        }

    def _calculate_trend(self, metric_name: str) -> str:
        """Calculate trend direction for a metric"""
        series = self.collector.get_metric(metric_name)
        if not series or len(series.points) < 5:
            return "unknown"

        values = series.get_values()[-10:]  # Last 10 points
        if len(values) < 5:
            return "unknown"

        # Simple trend calculation
        first_half = statistics.mean(values[:len(values)//2])
        second_half = statistics.mean(values[len(values)//2:])

        diff = second_half - first_half
        if diff > 5:
            return "increasing"
        elif diff < -5:
            return "decreasing"
        return "stable"

    def predict_load(self, minutes_ahead: int = 5) -> Optional[float]:
        """Predict future load based on current trends"""
        cpu_trend = self._calculate_trend("cpu_usage")
        mem_trend = self._calculate_trend("memory_usage")

        current_load = self.calculate_load_score()

        # Simple prediction based on trend
        if cpu_trend == "increasing" and mem_trend == "increasing":
            return current_load * (1 + 0.1 * minutes_ahead / 5)
        elif cpu_trend == "decreasing" and mem_trend == "decreasing":
            return current_load * (1 - 0.1 * minutes_ahead / 5)

        return current_load  # Default to current load
