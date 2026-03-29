# Metrics Collector - Week 50 Builder 2
# Centralized metrics collection

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class MetricNamespace(Enum):
    SYSTEM = "system"
    APPLICATION = "application"
    BUSINESS = "business"
    CUSTOM = "custom"


@dataclass
class Metric:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    namespace: MetricNamespace = MetricNamespace.APPLICATION
    name: str = ""
    value: float = 0.0
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """Collects and aggregates metrics"""

    def __init__(self):
        self._metrics: List[Metric] = []
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._metrics_meta = {"total_collected": 0, "by_namespace": {}}

    def counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter"""
        key = self._make_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value
        self._record(MetricNamespace.APPLICATION, name, self._counters[key], "count", tags)

    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge value"""
        key = self._make_key(name, tags)
        self._gauges[key] = value
        self._record(MetricNamespace.APPLICATION, name, value, "gauge", tags)

    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record histogram value"""
        key = self._make_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._record(MetricNamespace.APPLICATION, name, value, "histogram", tags)

    def _record(
        self,
        namespace: MetricNamespace,
        name: str,
        value: float,
        unit: str,
        tags: Optional[Dict[str, str]]
    ) -> None:
        """Record a metric"""
        metric = Metric(
            namespace=namespace,
            name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        )
        self._metrics.append(metric)
        self._metrics_meta["total_collected"] += 1
        ns_key = namespace.value
        self._metrics_meta["by_namespace"][ns_key] = self._metrics_meta["by_namespace"].get(ns_key, 0) + 1

    def _make_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Create metric key with tags"""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}:{tag_str}"

    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get counter value"""
        key = self._make_key(name, tags)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get gauge value"""
        key = self._make_key(name, tags)
        return self._gauges.get(key, 0)

    def get_histogram_stats(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get histogram statistics"""
        key = self._make_key(name, tags)
        values = self._histograms.get(key, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p95": 0, "p99": 0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(values) / n,
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)]
        }

    def get_metrics(
        self,
        namespace: Optional[MetricNamespace] = None,
        since: Optional[datetime] = None
    ) -> List[Metric]:
        """Get collected metrics"""
        metrics = self._metrics
        if namespace:
            metrics = [m for m in metrics if m.namespace == namespace]
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        return metrics

    def get_meta(self) -> Dict[str, Any]:
        return self._metrics_meta.copy()

    def clear(self) -> int:
        """Clear all metrics"""
        count = len(self._metrics)
        self._metrics.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        return count
