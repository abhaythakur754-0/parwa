"""
Usage Meter for SaaS Advanced Module.

Provides usage metering including:
- API call tracking
- Storage usage tracking
- Compute time tracking
- User seat counting
- Feature usage tracking
- Real-time meter updates
- Usage aggregation by period
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class UsageType(str, Enum):
    """Types of usage to track."""
    API_CALLS = "api_calls"
    AI_INTERACTIONS = "ai_interactions"
    TICKETS = "tickets"
    VOICE_MINUTES = "voice_minutes"
    STORAGE_GB = "storage_gb"
    COMPUTE_HOURS = "compute_hours"
    TEAM_MEMBERS = "team_members"
    SMS_MESSAGES = "sms_messages"
    EMAILS = "emails"
    WEBHOOKS = "webhooks"


class AggregationPeriod(str, Enum):
    """Aggregation periods for usage."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    BILLING_CYCLE = "billing_cycle"


@dataclass
class UsageRecord:
    """Represents a single usage record."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    usage_type: UsageType = UsageType.API_CALLS
    quantity: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    billed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "usage_type": self.usage_type.value,
            "quantity": self.quantity,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "billed": self.billed,
        }


@dataclass
class UsageSummary:
    """Summary of usage for a period."""
    client_id: str = ""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    usage_by_type: Dict[str, float] = field(default_factory=dict)
    record_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "client_id": self.client_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "usage_by_type": self.usage_by_type,
            "record_count": self.record_count,
        }


# Default usage limits by tier
DEFAULT_LIMITS = {
    "mini": {
        UsageType.API_CALLS: 10000,
        UsageType.AI_INTERACTIONS: 1000,
        UsageType.TICKETS: 500,
        UsageType.VOICE_MINUTES: 100,
        UsageType.STORAGE_GB: 5,
        UsageType.TEAM_MEMBERS: 3,
        UsageType.SMS_MESSAGES: 0,  # Not included
        UsageType.EMAILS: 5000,
    },
    "parwa": {
        UsageType.API_CALLS: 50000,
        UsageType.AI_INTERACTIONS: 5000,
        UsageType.TICKETS: 2000,
        UsageType.VOICE_MINUTES: 500,
        UsageType.STORAGE_GB: 20,
        UsageType.TEAM_MEMBERS: 10,
        UsageType.SMS_MESSAGES: 1000,
        UsageType.EMAILS: 20000,
    },
    "parwa_high": {
        UsageType.API_CALLS: 200000,
        UsageType.AI_INTERACTIONS: 25000,
        UsageType.TICKETS: 10000,
        UsageType.VOICE_MINUTES: 2000,
        UsageType.STORAGE_GB: 100,
        UsageType.TEAM_MEMBERS: 25,
        UsageType.SMS_MESSAGES: 5000,
        UsageType.EMAILS: 100000,
    },
    "enterprise": {
        UsageType.API_CALLS: None,  # Unlimited
        UsageType.AI_INTERACTIONS: None,
        UsageType.TICKETS: None,
        UsageType.VOICE_MINUTES: None,
        UsageType.STORAGE_GB: None,
        UsageType.TEAM_MEMBERS: None,
        UsageType.SMS_MESSAGES: None,
        UsageType.EMAILS: None,
    },
}


class UsageMeter:
    """
    Tracks and manages usage metrics for SaaS clients.

    Features:
    - Track multiple usage types
    - Real-time meter updates
    - Usage aggregation by period
    - Limit checking and alerts
    """

    def __init__(
        self,
        client_id: str = "",
        tier: str = "mini",
        billing_cycle_start: Optional[datetime] = None,
        billing_cycle_end: Optional[datetime] = None
    ):
        """
        Initialize usage meter.

        Args:
            client_id: Client identifier
            tier: Current subscription tier
            billing_cycle_start: Start of billing cycle
            billing_cycle_end: End of billing cycle
        """
        self.client_id = client_id
        self.tier = tier
        self.billing_cycle_start = billing_cycle_start or datetime.now(timezone.utc)
        self.billing_cycle_end = billing_cycle_end or self.billing_cycle_start + timedelta(days=30)

        self._records: List[UsageRecord] = []
        self._aggregated_cache: Dict[str, Dict[str, float]] = {}
        self._limits = DEFAULT_LIMITS.get(tier, DEFAULT_LIMITS["mini"])

    async def track(
        self,
        usage_type: UsageType,
        quantity: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UsageRecord:
        """
        Track a usage event.

        Args:
            usage_type: Type of usage
            quantity: Amount of usage
            metadata: Optional additional data

        Returns:
            UsageRecord created
        """
        record = UsageRecord(
            client_id=self.client_id,
            usage_type=usage_type,
            quantity=quantity,
            metadata=metadata or {},
        )

        self._records.append(record)

        # Invalidate cache
        self._aggregated_cache.clear()

        logger.debug(
            "Usage tracked",
            extra={
                "client_id": self.client_id,
                "usage_type": usage_type.value,
                "quantity": quantity,
            }
        )

        return record

    async def track_api_call(self, endpoint: str = "") -> UsageRecord:
        """Track an API call."""
        return await self.track(
            UsageType.API_CALLS,
            metadata={"endpoint": endpoint}
        )

    async def track_ai_interaction(
        self,
        model: str = "",
        tokens: int = 0
    ) -> UsageRecord:
        """Track an AI interaction."""
        return await self.track(
            UsageType.AI_INTERACTIONS,
            quantity=1.0,
            metadata={"model": model, "tokens": tokens}
        )

    async def track_ticket(self, ticket_id: Optional[str] = None) -> UsageRecord:
        """Track a support ticket."""
        return await self.track(
            UsageType.TICKETS,
            metadata={"ticket_id": ticket_id}
        )

    async def track_voice_minutes(self, minutes: float) -> UsageRecord:
        """Track voice call minutes."""
        return await self.track(UsageType.VOICE_MINUTES, quantity=minutes)

    async def track_storage(self, gb: float) -> UsageRecord:
        """Track storage usage."""
        return await self.track(UsageType.STORAGE_GB, quantity=gb)

    async def get_usage(
        self,
        usage_type: Optional[UsageType] = None,
        period: AggregationPeriod = AggregationPeriod.BILLING_CYCLE
    ) -> Dict[str, Any]:
        """
        Get usage summary for a period.

        Args:
            usage_type: Optional filter by type
            period: Aggregation period

        Returns:
            Dict with usage summary
        """
        period_start, period_end = self._get_period_range(period)

        # Filter records
        filtered = [
            r for r in self._records
            if period_start <= r.timestamp <= period_end
        ]

        if usage_type:
            filtered = [r for r in filtered if r.usage_type == usage_type]

        # Aggregate
        aggregated = defaultdict(float)
        for record in filtered:
            aggregated[record.usage_type.value] += record.quantity

        return {
            "client_id": self.client_id,
            "tier": self.tier,
            "period": period.value,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "usage": dict(aggregated),
            "record_count": len(filtered),
        }

    async def get_usage_by_type(
        self,
        usage_type: UsageType,
        period: AggregationPeriod = AggregationPeriod.BILLING_CYCLE
    ) -> float:
        """
        Get total usage for a specific type.

        Args:
            usage_type: Type of usage
            period: Aggregation period

        Returns:
            Total usage quantity
        """
        usage = await self.get_usage(usage_type, period)
        return usage["usage"].get(usage_type.value, 0.0)

    async def get_usage_summary(self) -> UsageSummary:
        """
        Get comprehensive usage summary for billing cycle.

        Returns:
            UsageSummary with all usage types
        """
        usage = await self.get_usage(period=AggregationPeriod.BILLING_CYCLE)

        return UsageSummary(
            client_id=self.client_id,
            period_start=self.billing_cycle_start,
            period_end=self.billing_cycle_end,
            usage_by_type=usage["usage"],
            record_count=usage["record_count"],
        )

    async def check_limit(
        self,
        usage_type: UsageType
    ) -> Dict[str, Any]:
        """
        Check if usage is within limits.

        Args:
            usage_type: Type of usage to check

        Returns:
            Dict with limit status
        """
        current = await self.get_usage_by_type(usage_type)
        limit = self._limits.get(usage_type)

        if limit is None:
            return {
                "usage_type": usage_type.value,
                "current": current,
                "limit": None,
                "unlimited": True,
                "percentage": 0,
                "at_limit": False,
                "over_limit": False,
            }

        percentage = (current / limit * 100) if limit > 0 else 0

        return {
            "usage_type": usage_type.value,
            "current": current,
            "limit": limit,
            "unlimited": False,
            "percentage": round(percentage, 2),
            "at_limit": current >= limit,
            "over_limit": current > limit,
            "remaining": max(0, limit - current),
        }

    async def check_all_limits(self) -> Dict[str, Any]:
        """
        Check all usage limits.

        Returns:
            Dict with all limit statuses
        """
        results = {}
        for usage_type in self._limits.keys():
            results[usage_type.value] = await self.check_limit(usage_type)

        # Identify critical limits
        critical = [
            ut for ut, status in results.items()
            if not status.get("unlimited") and status.get("percentage", 0) >= 90
        ]

        return {
            "client_id": self.client_id,
            "tier": self.tier,
            "limits": results,
            "critical_limits": critical,
            "any_over_limit": any(
                s.get("over_limit", False) for s in results.values()
            ),
        }

    async def get_usage_trend(
        self,
        usage_type: UsageType,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get usage trend over time.

        Args:
            usage_type: Type of usage
            days: Number of days to analyze

        Returns:
            List of daily usage points
        """
        trend = []
        now = datetime.now(timezone.utc)

        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)

            day_usage = sum(
                r.quantity for r in self._records
                if r.usage_type == usage_type
                and day_start <= r.timestamp < day_end
            )

            trend.append({
                "date": day_start.isoformat(),
                "usage": day_usage,
            })

        return trend

    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """
        Get real-time usage metrics.

        Returns:
            Dict with current usage state
        """
        # Get current billing cycle usage
        current_usage = await self.get_usage(period=AggregationPeriod.BILLING_CYCLE)

        # Calculate projected usage (based on days elapsed)
        days_in_cycle = (self.billing_cycle_end - self.billing_cycle_start).days
        days_elapsed = (datetime.now(timezone.utc) - self.billing_cycle_start).days
        days_elapsed = max(1, min(days_elapsed, days_in_cycle))

        projected = {}
        for usage_type, quantity in current_usage["usage"].items():
            daily_rate = quantity / days_elapsed
            projected[usage_type] = {
                "current": quantity,
                "daily_rate": round(daily_rate, 2),
                "projected": round(daily_rate * days_in_cycle, 2),
            }

        return {
            "client_id": self.client_id,
            "tier": self.tier,
            "billing_cycle": {
                "start": self.billing_cycle_start.isoformat(),
                "end": self.billing_cycle_end.isoformat(),
                "days_total": days_in_cycle,
                "days_elapsed": days_elapsed,
                "days_remaining": days_in_cycle - days_elapsed,
            },
            "current_usage": current_usage["usage"],
            "projected_usage": projected,
            "limits": {ut.value: limit for ut, limit in self._limits.items() if limit is not None},
        }

    def update_tier(self, new_tier: str) -> None:
        """
        Update the subscription tier.

        Args:
            new_tier: New tier value
        """
        self.tier = new_tier
        self._limits = DEFAULT_LIMITS.get(new_tier, DEFAULT_LIMITS["mini"])
        logger.info(
            "Usage meter tier updated",
            extra={"client_id": self.client_id, "new_tier": new_tier}
        )

    def set_billing_cycle(
        self,
        start: datetime,
        end: datetime
    ) -> None:
        """
        Set the billing cycle period.

        Args:
            start: Cycle start date
            end: Cycle end date
        """
        self.billing_cycle_start = start
        self.billing_cycle_end = end
        self._aggregated_cache.clear()

    def _get_period_range(
        self,
        period: AggregationPeriod
    ) -> tuple:
        """Get date range for aggregation period."""
        now = datetime.now(timezone.utc)

        if period == AggregationPeriod.HOURLY:
            start = now.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period == AggregationPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == AggregationPeriod.WEEKLY:
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(days=7)
        elif period == AggregationPeriod.MONTHLY:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end = start.replace(year=now.year + 1, month=1)
            else:
                end = start.replace(month=now.month + 1)
        else:  # BILLING_CYCLE
            start = self.billing_cycle_start
            end = self.billing_cycle_end

        return start, end


# Export for testing
__all__ = [
    "UsageMeter",
    "UsageRecord",
    "UsageSummary",
    "UsageType",
    "AggregationPeriod",
    "DEFAULT_LIMITS",
]
