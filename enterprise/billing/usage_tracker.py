"""
Enterprise Billing - Usage Tracker
Track enterprise usage for billing
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from collections import defaultdict


class UsageType(str, Enum):
    API_CALLS = "api_calls"
    TICKETS = "tickets"
    STORAGE = "storage_gb"
    USERS = "users"
    AI_QUERIES = "ai_queries"


class UsageRecord(BaseModel):
    """Usage record"""
    record_id: str
    client_id: str
    usage_type: UsageType
    quantity: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class UsageSummary(BaseModel):
    """Usage summary"""
    client_id: str
    period_start: datetime
    period_end: datetime
    usage: Dict[str, float] = Field(default_factory=dict)
    overage: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict()


class UsageTracker:
    """
    Track enterprise usage for billing.
    """

    def __init__(self):
        self.records: Dict[str, List[UsageRecord]] = defaultdict(list)
        self.limits: Dict[str, Dict[UsageType, float]] = {}

    def set_limit(self, client_id: str, usage_type: UsageType, limit: float) -> None:
        """Set usage limit for a client"""
        if client_id not in self.limits:
            self.limits[client_id] = {}
        self.limits[client_id][usage_type] = limit

    def record_usage(
        self,
        client_id: str,
        usage_type: UsageType,
        quantity: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UsageRecord:
        """Record usage"""
        import uuid
        record = UsageRecord(
            record_id=f"rec_{uuid.uuid4().hex[:8]}",
            client_id=client_id,
            usage_type=usage_type,
            quantity=quantity,
            metadata=metadata or {}
        )
        self.records[client_id].append(record)
        return record

    def get_usage(
        self,
        client_id: str,
        usage_type: Optional[UsageType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[UsageRecord]:
        """Get usage records"""
        records = self.records.get(client_id, [])

        if usage_type:
            records = [r for r in records if r.usage_type == usage_type]

        if start_date:
            records = [r for r in records if r.timestamp >= start_date]

        if end_date:
            records = [r for r in records if r.timestamp <= end_date]

        return records

    def get_summary(
        self,
        client_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> UsageSummary:
        """Get usage summary for a period"""
        records = self.get_usage(client_id, start_date=period_start, end_date=period_end)

        usage: Dict[str, float] = defaultdict(float)
        for record in records:
            usage[record.usage_type.value] += record.quantity

        # Calculate overage
        overage: Dict[str, float] = {}
        limits = self.limits.get(client_id, {})
        for usage_type, total in usage.items():
            limit = limits.get(UsageType(usage_type), float('inf'))
            if total > limit:
                overage[usage_type] = total - limit

        return UsageSummary(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            usage=dict(usage),
            overage=overage
        )

    def check_limit(self, client_id: str, usage_type: UsageType) -> Dict[str, Any]:
        """Check if client is within limits"""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        summary = self.get_summary(client_id, month_start, now)
        current = summary.usage.get(usage_type.value, 0)
        limit = self.limits.get(client_id, {}).get(usage_type, float('inf'))

        return {
            "current": current,
            "limit": limit,
            "remaining": max(0, limit - current),
            "percentage": (current / limit * 100) if limit > 0 else 0
        }
