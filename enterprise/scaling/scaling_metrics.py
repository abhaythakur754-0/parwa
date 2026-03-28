# Scaling Metrics - Week 52 Builder 1
# Scaling metrics collection

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class MetricAggregation(Enum):
    AVERAGE = "average"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    SUM = "sum"
    COUNT = "count"


class MetricPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MetricDataPoint:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""
    dimensions: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MetricDefinition:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    display_name: str = ""
    unit: str = ""
    aggregation: MetricAggregation = MetricAggregation.AVERAGE
    priority: MetricPriority = MetricPriority.NORMAL
    collection_interval: int = 60
    retention_days: int = 30
    created_at: datetime = field(default_factory=datetime.utcnow)


class ScalingMetrics:
    """Collects and manages scaling metrics"""

    def __init__(self):
        self._definitions: Dict[str, MetricDefinition] = {}
        self._data_points: Dict[str, List[MetricDataPoint]] = {}
        self._metrics = {
            "total_definitions": 0,
            "total_data_points": 0,
            "by_priority": {},
            "by_aggregation": {}
        }

    def register_metric(
        self,
        name: str,
        display_name: str = "",
        unit: str = "",
        aggregation: MetricAggregation = MetricAggregation.AVERAGE,
        priority: MetricPriority = MetricPriority.NORMAL,
        collection_interval: int = 60,
        retention_days: int = 30
    ) -> MetricDefinition:
        """Register a metric definition"""
        definition = MetricDefinition(
            name=name,
            display_name=display_name or name,
            unit=unit,
            aggregation=aggregation,
            priority=priority,
            collection_interval=collection_interval,
            retention_days=retention_days
        )
        self._definitions[definition.id] = definition
        self._data_points[name] = []
        self._metrics["total_definitions"] += 1

        priority_key = priority.value
        self._metrics["by_priority"][priority_key] = \
            self._metrics["by_priority"].get(priority_key, 0) + 1

        agg_key = aggregation.value
        self._metrics["by_aggregation"][agg_key] = \
            self._metrics["by_aggregation"].get(agg_key, 0) + 1

        return definition

    def record_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "",
        dimensions: Optional[Dict[str, str]] = None
    ) -> Optional[MetricDataPoint]:
        """Record a metric data point"""
        if metric_name not in self._data_points:
            return None

        data_point = MetricDataPoint(
            metric_name=metric_name,
            value=value,
            unit=unit,
            dimensions=dimensions or {}
        )

        self._data_points[metric_name].append(data_point)
        self._metrics["total_data_points"] += 1
        return data_point

    def get_metric_definition(self, definition_id: str) -> Optional[MetricDefinition]:
        """Get metric definition by ID"""
        return self._definitions.get(definition_id)

    def get_metric_definition_by_name(self, name: str) -> Optional[MetricDefinition]:
        """Get metric definition by name"""
        for definition in self._definitions.values():
            if definition.name == name:
                return definition
        return None

    def get_data_points(
        self,
        metric_name: str,
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[MetricDataPoint]:
        """Get data points for a metric"""
        points = self._data_points.get(metric_name, [])

        if since:
            points = [p for p in points if p.timestamp >= since]

        return points[-limit:]

    def get_aggregated_value(
        self,
        metric_name: str,
        aggregation: Optional[MetricAggregation] = None,
        since: Optional[datetime] = None,
        minutes: int = 5
    ) -> Optional[float]:
        """Get aggregated metric value"""
        if since is None:
            since = datetime.utcnow() - timedelta(minutes=minutes)

        points = self.get_data_points(metric_name, since)
        if not points:
            return None

        # Get aggregation type
        definition = self.get_metric_definition_by_name(metric_name)
        if aggregation is None and definition:
            aggregation = definition.aggregation
        elif aggregation is None:
            aggregation = MetricAggregation.AVERAGE

        values = [p.value for p in points]

        if aggregation == MetricAggregation.AVERAGE:
            return sum(values) / len(values)
        elif aggregation == MetricAggregation.MAXIMUM:
            return max(values)
        elif aggregation == MetricAggregation.MINIMUM:
            return min(values)
        elif aggregation == MetricAggregation.SUM:
            return sum(values)
        elif aggregation == MetricAggregation.COUNT:
            return float(len(values))

        return None

    def get_statistics(
        self,
        metric_name: str,
        minutes: int = 5
    ) -> Dict[str, float]:
        """Get metric statistics"""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        points = self.get_data_points(metric_name, since)

        if not points:
            return {
                "count": 0,
                "average": 0.0,
                "minimum": 0.0,
                "maximum": 0.0,
                "sum": 0.0,
                "std_dev": 0.0
            }

        values = [p.value for p in points]
        avg = sum(values) / len(values)
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        std_dev = variance ** 0.5

        return {
            "count": len(values),
            "average": avg,
            "minimum": min(values),
            "maximum": max(values),
            "sum": sum(values),
            "std_dev": std_dev
        }

    def get_percentile(
        self,
        metric_name: str,
        percentile: float,
        minutes: int = 5
    ) -> Optional[float]:
        """Get metric percentile"""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        points = self.get_data_points(metric_name, since)

        if not points:
            return None

        values = sorted([p.value for p in points])
        index = int(len(values) * percentile / 100)
        return values[min(index, len(values) - 1)]

    def get_rate(
        self,
        metric_name: str,
        minutes: int = 5
    ) -> float:
        """Get rate of change per minute"""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        points = self.get_data_points(metric_name, since)

        if len(points) < 2:
            return 0.0

        sorted_points = sorted(points, key=lambda p: p.timestamp)
        first = sorted_points[0]
        last = sorted_points[-1]

        time_diff = (last.timestamp - first.timestamp).total_seconds() / 60
        if time_diff == 0:
            return 0.0

        return (last.value - first.value) / time_diff

    def cleanup_old_data(self, hours: int = 24) -> int:
        """Remove old data points"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        total_removed = 0

        for metric_name in self._data_points:
            initial = len(self._data_points[metric_name])
            self._data_points[metric_name] = [
                p for p in self._data_points[metric_name]
                if p.timestamp >= cutoff
            ]
            removed = initial - len(self._data_points[metric_name])
            total_removed += removed
            self._metrics["total_data_points"] -= removed

        return total_removed

    def get_metrics_by_priority(
        self,
        priority: MetricPriority
    ) -> List[MetricDefinition]:
        """Get all metrics of a priority"""
        return [d for d in self._definitions.values() if d.priority == priority]

    def get_all_definitions(self) -> List[MetricDefinition]:
        """Get all metric definitions"""
        return list(self._definitions.values())

    def delete_metric(self, metric_name: str) -> bool:
        """Delete a metric"""
        if metric_name in self._data_points:
            count = len(self._data_points[metric_name])
            self._metrics["total_data_points"] -= count
            del self._data_points[metric_name]
            return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics collection stats"""
        return {
            **self._metrics,
            "unique_metrics": len(self._data_points)
        }
