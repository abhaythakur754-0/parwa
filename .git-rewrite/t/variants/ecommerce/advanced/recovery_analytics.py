"""Recovery Analytics for Cart Abandonment.

Provides analytics for cart recovery:
- Recovery rate tracking
- Revenue attribution
- Channel effectiveness
- Time-to-conversion analysis
- A/B test results
- ROI calculation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import statistics
import logging

logger = logging.getLogger(__name__)


class MetricPeriod(str, Enum):
    """Analytics period."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class RecoveryMetrics:
    """Recovery metrics snapshot."""
    period_start: datetime
    period_end: datetime
    total_abandoned: int
    total_recovered: int
    recovery_rate: float
    revenue_recovered: Decimal
    revenue_lost: Decimal


@dataclass
class ChannelPerformance:
    """Channel performance metrics."""
    channel: str
    messages_sent: int
    messages_opened: int
    open_rate: float
    messages_clicked: int
    click_rate: float
    conversions: int
    conversion_rate: float
    revenue_attributed: Decimal


@dataclass
class ABTestResult:
    """A/B test result."""
    test_name: str
    variant: str
    impressions: int
    conversions: int
    conversion_rate: float
    revenue: Decimal
    statistical_significance: Optional[float] = None


class RecoveryAnalytics:
    """Analytics for cart recovery campaigns."""

    def __init__(self, client_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize analytics.

        Args:
            client_id: Client identifier
            config: Optional configuration
        """
        self.client_id = client_id
        self.config = config or {}
        self._events: List[Dict[str, Any]] = []

    def track_event(
        self,
        event_type: str,
        cart_id: str,
        customer_id: Optional[str] = None,
        channel: Optional[str] = None,
        value: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Track a recovery event (no PII).

        Args:
            event_type: Type of event (abandoned, message_sent, opened, clicked, recovered)
            cart_id: Cart identifier
            customer_id: Customer identifier (anonymized)
            channel: Communication channel
            value: Monetary value if applicable
            metadata: Additional metadata
        """
        event = {
            "event_type": event_type,
            "cart_id": cart_id,
            "customer_id": customer_id,
            "channel": channel,
            "value": float(value) if value else 0,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        self._events.append(event)

        logger.info(
            f"Tracked recovery event: {event_type}",
            extra={
                "client_id": self.client_id,
                "event_type": event_type,
                "cart_id": cart_id
            }
        )

    def get_recovery_metrics(
        self,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> RecoveryMetrics:
        """Get recovery metrics for period.

        Args:
            period: Time period

        Returns:
            Recovery metrics
        """
        now = datetime.utcnow()

        if period == MetricPeriod.DAY:
            start = now - timedelta(days=1)
        elif period == MetricPeriod.WEEK:
            start = now - timedelta(weeks=1)
        else:
            start = now - timedelta(days=30)

        # Filter events in period
        period_events = [
            e for e in self._events
            if datetime.fromisoformat(e["timestamp"]) >= start
        ]

        # Calculate metrics
        abandoned_carts = set(
            e["cart_id"] for e in period_events
            if e["event_type"] == "abandoned"
        )

        recovered_carts = set(
            e["cart_id"] for e in period_events
            if e["event_type"] == "recovered"
        )

        revenue_recovered = sum(
            e["value"] for e in period_events
            if e["event_type"] == "recovered"
        )

        revenue_lost = sum(
            e["value"] for e in period_events
            if e["event_type"] == "abandoned"
            and e["cart_id"] not in recovered_carts
        )

        recovery_rate = (
            len(recovered_carts) / len(abandoned_carts)
            if abandoned_carts else 0
        )

        return RecoveryMetrics(
            period_start=start,
            period_end=now,
            total_abandoned=len(abandoned_carts),
            total_recovered=len(recovered_carts),
            recovery_rate=recovery_rate,
            revenue_recovered=Decimal(str(revenue_recovered)),
            revenue_lost=Decimal(str(revenue_lost))
        )

    def get_channel_performance(
        self,
        channel: str,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> ChannelPerformance:
        """Get performance metrics for a channel.

        Args:
            channel: Channel name
            period: Time period

        Returns:
            Channel performance
        """
        now = datetime.utcnow()

        if period == MetricPeriod.DAY:
            start = now - timedelta(days=1)
        elif period == MetricPeriod.WEEK:
            start = now - timedelta(weeks=1)
        else:
            start = now - timedelta(days=30)

        channel_events = [
            e for e in self._events
            if e.get("channel") == channel
            and datetime.fromisoformat(e["timestamp"]) >= start
        ]

        sent = len([e for e in channel_events if e["event_type"] == "message_sent"])
        opened = len([e for e in channel_events if e["event_type"] == "opened"])
        clicked = len([e for e in channel_events if e["event_type"] == "clicked"])
        conversions = len([e for e in channel_events if e["event_type"] == "recovered"])

        revenue = sum(
            e["value"] for e in channel_events
            if e["event_type"] == "recovered"
        )

        return ChannelPerformance(
            channel=channel,
            messages_sent=sent,
            messages_opened=opened,
            open_rate=opened / sent if sent > 0 else 0,
            messages_clicked=clicked,
            click_rate=clicked / sent if sent > 0 else 0,
            conversions=conversions,
            conversion_rate=conversions / sent if sent > 0 else 0,
            revenue_attributed=Decimal(str(revenue))
        )

    def get_ab_test_results(
        self,
        test_name: str
    ) -> List[ABTestResult]:
        """Get A/B test results.

        Args:
            test_name: Test identifier

        Returns:
            List of variant results
        """
        results = {}

        for event in self._events:
            test = event.get("metadata", {}).get("test_name")
            variant = event.get("metadata", {}).get("variant")

            if test != test_name or not variant:
                continue

            if variant not in results:
                results[variant] = {
                    "impressions": 0,
                    "conversions": 0,
                    "revenue": 0
                }

            if event["event_type"] == "message_sent":
                results[variant]["impressions"] += 1
            elif event["event_type"] == "recovered":
                results[variant]["conversions"] += 1
                results[variant]["revenue"] += event["value"]

        ab_results = []
        for variant, data in results.items():
            conv_rate = (
                data["conversions"] / data["impressions"]
                if data["impressions"] > 0 else 0
            )

            ab_results.append(ABTestResult(
                test_name=test_name,
                variant=variant,
                impressions=data["impressions"],
                conversions=data["conversions"],
                conversion_rate=conv_rate,
                revenue=Decimal(str(data["revenue"]))
            ))

        return ab_results

    def calculate_roi(
        self,
        period: MetricPeriod = MetricPeriod.MONTH
    ) -> Dict[str, Any]:
        """Calculate ROI for recovery campaigns.

        Args:
            period: Time period

        Returns:
            ROI metrics
        """
        metrics = self.get_recovery_metrics(period)

        # Estimate costs (simplified)
        # In production, integrate with actual cost data
        messages_sent = len([
            e for e in self._events
            if e["event_type"] == "message_sent"
        ])

        # Assume $0.01 per email, $0.05 per SMS
        email_cost = messages_sent * 0.01
        sms_cost = messages_sent * 0.01  # Simplified
        total_cost = Decimal(str(email_cost + sms_cost))

        # Calculate ROI
        if total_cost > 0:
            roi = float((metrics.revenue_recovered - total_cost) / total_cost * 100)
        else:
            roi = 0

        return {
            "period": period.value,
            "total_investment": float(total_cost),
            "revenue_recovered": float(metrics.revenue_recovered),
            "net_profit": float(metrics.revenue_recovered - total_cost),
            "roi_percent": roi,
            "cost_per_recovery": float(total_cost / metrics.total_recovered) if metrics.total_recovered > 0 else 0
        }

    def get_time_to_conversion_analysis(
        self,
        period: MetricPeriod = MetricPeriod.WEEK
    ) -> Dict[str, Any]:
        """Analyze time to conversion after recovery message.

        Args:
            period: Time period

        Returns:
            Time to conversion analysis
        """
        now = datetime.utcnow()

        if period == MetricPeriod.DAY:
            start = now - timedelta(days=1)
        elif period == MetricPeriod.WEEK:
            start = now - timedelta(weeks=1)
        else:
            start = now - timedelta(days=30)

        conversion_times = []

        # Group events by cart
        cart_events = {}
        for event in self._events:
            if datetime.fromisoformat(event["timestamp"]) < start:
                continue

            cart_id = event["cart_id"]
            if cart_id not in cart_events:
                cart_events[cart_id] = []

            cart_events[cart_id].append(event)

        # Calculate time between first message and recovery
        for cart_id, events in cart_events.items():
            first_message = None
            recovery = None

            for event in sorted(events, key=lambda x: x["timestamp"]):
                if event["event_type"] == "message_sent" and not first_message:
                    first_message = datetime.fromisoformat(event["timestamp"])
                elif event["event_type"] == "recovered":
                    recovery = datetime.fromisoformat(event["timestamp"])
                    break

            if first_message and recovery:
                delta = (recovery - first_message).total_seconds() / 3600  # hours
                conversion_times.append(delta)

        if conversion_times:
            return {
                "average_hours": statistics.mean(conversion_times),
                "median_hours": statistics.median(conversion_times),
                "min_hours": min(conversion_times),
                "max_hours": max(conversion_times),
                "total_conversions_analyzed": len(conversion_times)
            }

        return {
            "average_hours": 0,
            "median_hours": 0,
            "min_hours": 0,
            "max_hours": 0,
            "total_conversions_analyzed": 0
        }

    def export_analytics(
        self,
        period: MetricPeriod = MetricPeriod.MONTH,
        format: str = "dict"
    ) -> Dict[str, Any]:
        """Export analytics data (no PII).

        Args:
            period: Time period
            format: Export format

        Returns:
            Analytics data
        """
        return {
            "client_id": self.client_id,
            "period": period.value,
            "recovery_metrics": self.get_recovery_metrics(period).__dict__,
            "roi": self.calculate_roi(period),
            "time_to_conversion": self.get_time_to_conversion_analysis(period),
            "channels": {
                "email": self.get_channel_performance("email", period).__dict__,
                "sms": self.get_channel_performance("sms", period).__dict__
            }
        }
