"""
Cross-Tenant Analytics Module

Provides analytics across tenants while preserving privacy.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    PERCENTAGE = "percentage"


class AggregationType(str, Enum):
    """Aggregation methods"""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE = "percentile"


@dataclass
class MetricPoint:
    """A single metric data point"""
    tenant_id: str
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    """An aggregated metric result"""
    metric_name: str
    aggregation: AggregationType
    value: float
    tenant_count: int
    period_start: datetime
    period_end: datetime
    percentiles: Optional[Dict[str, float]] = None


class CrossTenantAnalytics:
    """
    Provides analytics across tenants with privacy preservation.

    Features:
    - Anonymous aggregation
    - Percentile calculations
    - Trend analysis
    - Privacy-preserving queries
    """

    def __init__(self, min_tenant_threshold: int = 5):
        """
        Initialize analytics engine.

        Args:
            min_tenant_threshold: Minimum tenants for aggregation (privacy)
        """
        self.min_tenant_threshold = min_tenant_threshold

        # Metric storage
        self._metrics: List[MetricPoint] = []

        # Pre-computed aggregations
        self._aggregations: Dict[str, AggregatedMetric] = {}

        # Metrics
        self._stats = {
            "total_points": 0,
            "queries_served": 0
        }

    def record(
        self,
        tenant_id: str,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> MetricPoint:
        """Record a metric data point"""
        point = MetricPoint(
            tenant_id=tenant_id,
            metric_name=metric_name,
            value=value,
            tags=tags or {}
        )

        self._metrics.append(point)
        self._stats["total_points"] += 1

        return point

    def aggregate(
        self,
        metric_name: str,
        aggregation: AggregationType,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Optional[AggregatedMetric]:
        """
        Aggregate metrics across tenants.

        Args:
            metric_name: Name of metric to aggregate
            aggregation: Aggregation method
            start_time: Start of time range
            end_time: End of time range
            tags: Optional tag filters

        Returns:
            AggregatedMetric or None if insufficient data
        """
        # Filter metrics
        points = [p for p in self._metrics if p.metric_name == metric_name]

        if start_time:
            points = [p for p in points if p.timestamp >= start_time]
        if end_time:
            points = [p for p in points if p.timestamp <= end_time]

        if tags:
            for key, value in tags.items():
                points = [p for p in points if p.tags.get(key) == value]

        # Check privacy threshold
        unique_tenants = set(p.tenant_id for p in points)
        if len(unique_tenants) < self.min_tenant_threshold:
            logger.warning(
                f"Insufficient tenants ({len(unique_tenants)}) for aggregation, "
                f"minimum is {self.min_tenant_threshold}"
            )
            return None

        # Aggregate values
        values = [p.value for p in points]

        if aggregation == AggregationType.SUM:
            result = sum(values)
        elif aggregation == AggregationType.AVG:
            result = sum(values) / len(values)
        elif aggregation == AggregationType.MIN:
            result = min(values)
        elif aggregation == AggregationType.MAX:
            result = max(values)
        elif aggregation == AggregationType.COUNT:
            result = float(len(values))
        elif aggregation == AggregationType.PERCENTILE:
            result = sum(values) / len(values)  # Default to avg
        else:
            result = 0

        # Calculate percentiles
        percentiles = None
        if aggregation == AggregationType.PERCENTILE or True:
            sorted_values = sorted(values)
            percentiles = {
                "p50": self._percentile(sorted_values, 50),
                "p90": self._percentile(sorted_values, 90),
                "p95": self._percentile(sorted_values, 95),
                "p99": self._percentile(sorted_values, 99)
            }

        self._stats["queries_served"] += 1

        return AggregatedMetric(
            metric_name=metric_name,
            aggregation=aggregation,
            value=result,
            tenant_count=len(unique_tenants),
            period_start=start_time or min(p.timestamp for p in points),
            period_end=end_time or max(p.timestamp for p in points),
            percentiles=percentiles
        )

    def _percentile(self, sorted_values: List[float], p: int) -> float:
        """Calculate percentile value"""
        if not sorted_values:
            return 0

        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_values) else f

        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    def get_tenant_ranking(
        self,
        metric_name: str,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a tenant's ranking for a metric (privacy-preserving)"""
        points = [p for p in self._metrics if p.metric_name == metric_name]

        if start_time:
            points = [p for p in points if p.timestamp >= start_time]
        if end_time:
            points = [p for p in points if p.timestamp <= end_time]

        # Aggregate by tenant
        tenant_values: Dict[str, List[float]] = defaultdict(list)
        for p in points:
            tenant_values[p.tenant_id].append(p.value)

        # Calculate averages
        tenant_avgs = {
            tid: sum(vals) / len(vals)
            for tid, vals in tenant_values.items()
        }

        if tenant_id not in tenant_avgs:
            return None

        # Sort and find rank (anonymized)
        sorted_tenants = sorted(tenant_avgs.items(), key=lambda x: x[1], reverse=True)

        for rank, (tid, val) in enumerate(sorted_tenants, 1):
            if tid == tenant_id:
                return {
                    "tenant_id": tenant_id,
                    "metric_name": metric_name,
                    "value": tenant_avgs[tenant_id],
                    "rank": rank,
                    "total_tenants": len(sorted_tenants),
                    "percentile": round((1 - (rank - 1) / len(sorted_tenants)) * 100, 1)
                }

        return None

    def get_distribution(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        buckets: int = 10
    ) -> Dict[str, Any]:
        """Get distribution of a metric across tenants"""
        points = [p for p in self._metrics if p.metric_name == metric_name]

        if start_time:
            points = [p for p in points if p.timestamp >= start_time]
        if end_time:
            points = [p for p in points if p.timestamp <= end_time]

        values = [p.value for p in points]

        if not values:
            return {"buckets": [], "total": 0}

        min_val = min(values)
        max_val = max(values)
        bucket_size = (max_val - min_val) / buckets if max_val > min_val else 1

        distribution = [0] * buckets

        for v in values:
            bucket_idx = min(int((v - min_val) / bucket_size), buckets - 1)
            distribution[bucket_idx] += 1

        return {
            "metric_name": metric_name,
            "min": min_val,
            "max": max_val,
            "avg": sum(values) / len(values),
            "buckets": [
                {
                    "range_start": min_val + i * bucket_size,
                    "range_end": min_val + (i + 1) * bucket_size,
                    "count": distribution[i]
                }
                for i in range(buckets)
            ],
            "total": len(values)
        }

    def compare_tenant_to_average(
        self,
        tenant_id: str,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """Compare a tenant to the average (anonymized)"""
        tenant_points = [
            p for p in self._metrics
            if p.tenant_id == tenant_id and p.metric_name == metric_name
        ]

        if not tenant_points:
            return None

        tenant_avg = sum(p.value for p in tenant_points) / len(tenant_points)

        # Get aggregated (anonymous) average
        agg = self.aggregate(metric_name, AggregationType.AVG, start_time, end_time)

        if not agg:
            return None

        diff = tenant_avg - agg.value
        diff_percent = (diff / agg.value * 100) if agg.value != 0 else 0

        return {
            "tenant_id": tenant_id,
            "metric_name": metric_name,
            "tenant_value": tenant_avg,
            "cross_tenant_average": agg.value,
            "difference": diff,
            "difference_percent": round(diff_percent, 2),
            "comparison": "above" if diff > 0 else "below" if diff < 0 else "equal"
        }

    def get_trend(
        self,
        metric_name: str,
        period_days: int = 7,
        aggregation: AggregationType = AggregationType.AVG
    ) -> List[Dict[str, Any]]:
        """Get metric trend over time"""
        trend = []
        now = datetime.utcnow()

        for i in range(period_days):
            day_end = now - timedelta(days=i)
            day_start = day_end - timedelta(days=1)

            agg = self.aggregate(
                metric_name=metric_name,
                aggregation=aggregation,
                start_time=day_start,
                end_time=day_end
            )

            trend.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "value": agg.value if agg else None,
                "tenant_count": agg.tenant_count if agg else 0
            })

        return list(reversed(trend))

    def get_metrics(self) -> Dict[str, Any]:
        """Get analytics metrics"""
        return {
            **self._stats,
            "stored_points": len(self._metrics),
            "unique_metrics": len(set(p.metric_name for p in self._metrics))
        }

    def clear_old_metrics(self, days: int = 90) -> int:
        """Clear metrics older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        initial_count = len(self._metrics)
        self._metrics = [p for p in self._metrics if p.timestamp >= cutoff]

        return initial_count - len(self._metrics)
