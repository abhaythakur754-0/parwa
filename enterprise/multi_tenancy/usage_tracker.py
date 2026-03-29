"""
Usage Tracker

Tracks resource usage in real-time for multi-tenant environments.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import logging
import threading
from collections import defaultdict

from .quota_manager import ResourceType

logger = logging.getLogger(__name__)


class AggregationPeriod(str, Enum):
    """Periods for usage aggregation"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class UsageRecord:
    """A single usage record"""
    record_id: str
    tenant_id: str
    resource_type: ResourceType
    amount: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageAggregation:
    """Aggregated usage data"""
    tenant_id: str
    resource_type: ResourceType
    period: AggregationPeriod
    period_start: datetime
    period_end: datetime
    total: int
    count: int
    average: float
    peak: int
    min_value: int


class UsageTracker:
    """
    Tracks resource usage in real-time.

    Features:
    - Real-time usage tracking
    - Historical data storage
    - Aggregation by period
    - Usage analytics
    """

    def __init__(
        self,
        retention_days: int = 90,
        aggregation_enabled: bool = True
    ):
        self.retention_days = retention_days
        self.aggregation_enabled = aggregation_enabled

        # Real-time tracking
        self._current_usage: Dict[str, Dict[ResourceType, int]] = defaultdict(lambda: defaultdict(int))
        self._usage_lock = threading.Lock()

        # Historical records
        self._records: List[UsageRecord] = []

        # Aggregations cache
        self._aggregations: Dict[str, UsageAggregation] = {}

        # Metrics
        self._metrics = {
            "total_records": 0,
            "records_by_type": defaultdict(int),
            "last_record_time": None
        }

    def track(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> UsageRecord:
        """
        Track resource usage.

        Args:
            tenant_id: Tenant ID
            resource_type: Type of resource
            amount: Amount used
            source: Source of usage (e.g., "api", "webhook")
            metadata: Additional metadata

        Returns:
            UsageRecord
        """
        record_id = f"rec_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(self._records)}"

        record = UsageRecord(
            record_id=record_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            amount=amount,
            source=source,
            metadata=metadata or {}
        )

        # Store record
        self._records.append(record)

        # Update current usage
        with self._usage_lock:
            self._current_usage[tenant_id][resource_type] += amount

        # Update metrics
        self._metrics["total_records"] += 1
        self._metrics["records_by_type"][resource_type] += 1
        self._metrics["last_record_time"] = datetime.utcnow()

        logger.debug(f"Tracked usage: {tenant_id} {resource_type.value} +{amount}")

        return record

    def get_current_usage(
        self,
        tenant_id: str,
        resource_type: Optional[ResourceType] = None
    ) -> Dict[str, int]:
        """Get current usage for tenant"""
        with self._usage_lock:
            if resource_type:
                return {resource_type.value: self._current_usage[tenant_id][resource_type]}
            return {k.value: v for k, v in self._current_usage[tenant_id].items()}

    def get_usage_history(
        self,
        tenant_id: str,
        resource_type: Optional[ResourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[UsageRecord]:
        """Get usage history for tenant"""
        records = [r for r in self._records if r.tenant_id == tenant_id]

        if resource_type:
            records = [r for r in records if r.resource_type == resource_type]

        if start_time:
            records = [r for r in records if r.timestamp >= start_time]

        if end_time:
            records = [r for r in records if r.timestamp <= end_time]

        return sorted(records, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_usage_summary(
        self,
        tenant_id: str,
        period: AggregationPeriod = AggregationPeriod.DAY,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get usage summary for tenant"""
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=30)
        if not end_time:
            end_time = datetime.utcnow()

        records = self.get_usage_history(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            limit=100000
        )

        # Group by resource type
        by_resource: Dict[str, List[int]] = defaultdict(list)
        for record in records:
            by_resource[record.resource_type.value].append(record.amount)

        summary = {
            "tenant_id": tenant_id,
            "period": period.value,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_records": len(records),
            "by_resource": {}
        }

        for resource, amounts in by_resource.items():
            summary["by_resource"][resource] = {
                "total": sum(amounts),
                "count": len(amounts),
                "average": sum(amounts) / len(amounts) if amounts else 0,
                "peak": max(amounts) if amounts else 0,
                "min": min(amounts) if amounts else 0
            }

        return summary

    def get_trend(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        periods: int = 7,
        period: AggregationPeriod = AggregationPeriod.DAY
    ) -> List[Dict[str, Any]]:
        """Get usage trend over time"""
        trend = []
        now = datetime.utcnow()

        for i in range(periods):
            period_end = now - timedelta(days=i)
            period_start = period_end - timedelta(days=1)

            records = [
                r for r in self._records
                if r.tenant_id == tenant_id
                and r.resource_type == resource_type
                and period_start <= r.timestamp < period_end
            ]

            amounts = [r.amount for r in records]

            trend.append({
                "date": period_start.strftime("%Y-%m-%d"),
                "total": sum(amounts),
                "count": len(amounts),
                "average": sum(amounts) / len(amounts) if amounts else 0
            })

        return list(reversed(trend))

    def get_peak_usage(
        self,
        tenant_id: str,
        resource_type: ResourceType
    ) -> Dict[str, Any]:
        """Get peak usage info for tenant/resource"""
        records = [
            r for r in self._records
            if r.tenant_id == tenant_id and r.resource_type == resource_type
        ]

        if not records:
            return {"peak": 0, "timestamp": None}

        peak_record = max(records, key=lambda x: x.amount)

        return {
            "peak": peak_record.amount,
            "timestamp": peak_record.timestamp.isoformat(),
            "record_id": peak_record.record_id
        }

    def compare_periods(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        period1_start: datetime,
        period1_end: datetime,
        period2_start: datetime,
        period2_end: datetime
    ) -> Dict[str, Any]:
        """Compare usage between two periods"""
        period1_records = [
            r for r in self._records
            if r.tenant_id == tenant_id
            and r.resource_type == resource_type
            and period1_start <= r.timestamp < period1_end
        ]

        period2_records = [
            r for r in self._records
            if r.tenant_id == tenant_id
            and r.resource_type == resource_type
            and period2_start <= r.timestamp < period2_end
        ]

        period1_total = sum(r.amount for r in period1_records)
        period2_total = sum(r.amount for r in period2_records)

        change = period2_total - period1_total
        change_percent = (change / period1_total * 100) if period1_total > 0 else 0

        return {
            "period1": {
                "start": period1_start.isoformat(),
                "end": period1_end.isoformat(),
                "total": period1_total,
                "count": len(period1_records)
            },
            "period2": {
                "start": period2_start.isoformat(),
                "end": period2_end.isoformat(),
                "total": period2_total,
                "count": len(period2_records)
            },
            "change": change,
            "change_percent": round(change_percent, 2)
        }

    def reset_current_usage(self, tenant_id: str) -> None:
        """Reset current usage counter for tenant"""
        with self._usage_lock:
            self._current_usage[tenant_id].clear()

    def cleanup_old_records(self) -> int:
        """Remove records older than retention period"""
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)

        initial_count = len(self._records)
        self._records = [r for r in self._records if r.timestamp >= cutoff]
        removed = initial_count - len(self._records)

        logger.info(f"Cleaned up {removed} old usage records")
        return removed

    def get_metrics(self) -> Dict[str, Any]:
        """Get tracker metrics"""
        return {
            "total_records": self._metrics["total_records"],
            "records_by_type": dict(self._metrics["records_by_type"]),
            "last_record_time": self._metrics["last_record_time"].isoformat() if self._metrics["last_record_time"] else None,
            "active_tenants": len(self._current_usage),
            "storage_size": len(self._records)
        }

    def export_usage(
        self,
        tenant_id: str,
        format: str = "json"
    ) -> str:
        """Export usage data for tenant"""
        records = self.get_usage_history(tenant_id, limit=10000)

        if format == "json":
            import json
            data = [
                {
                    "record_id": r.record_id,
                    "resource": r.resource_type.value,
                    "amount": r.amount,
                    "timestamp": r.timestamp.isoformat(),
                    "source": r.source
                }
                for r in records
            ]
            return json.dumps(data, indent=2)

        raise ValueError(f"Unsupported format: {format}")
