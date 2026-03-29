# Notification Analytics - Week 48 Builder 5
# Delivery metrics and analytics for notifications

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import statistics
import uuid


class MetricPeriod(Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class NotificationChannel(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


@dataclass
class MetricPoint:
    timestamp: datetime
    value: float


@dataclass
class ChannelMetrics:
    channel: NotificationChannel = NotificationChannel.EMAIL
    total_sent: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    total_opened: int = 0
    total_clicked: int = 0
    total_bounced: int = 0

    @property
    def delivery_rate(self) -> float:
        if self.total_sent == 0:
            return 0.0
        return (self.total_delivered / self.total_sent) * 100

    @property
    def open_rate(self) -> float:
        if self.total_delivered == 0:
            return 0.0
        return (self.total_opened / self.total_delivered) * 100

    @property
    def click_rate(self) -> float:
        if self.total_opened == 0:
            return 0.0
        return (self.total_clicked / self.total_opened) * 100

    @property
    def bounce_rate(self) -> float:
        if self.total_sent == 0:
            return 0.0
        return (self.total_bounced / self.total_sent) * 100


@dataclass
class NotificationMetrics:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    period: MetricPeriod = MetricPeriod.DAY
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    channels: Dict[str, ChannelMetrics] = field(default_factory=dict)
    total_cost: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


class NotificationAnalytics:
    """Analytics engine for notification delivery metrics"""

    def __init__(self):
        self._metrics: Dict[str, NotificationMetrics] = {}
        self._events: List[Dict[str, Any]] = []
        self._tenant_metrics: Dict[str, List[str]] = {}

    def record_event(
        self,
        tenant_id: str,
        channel: NotificationChannel,
        event_type: str,
        notification_id: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a notification event"""
        event = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "channel": channel.value,
            "event_type": event_type,
            "notification_id": notification_id,
            "timestamp": timestamp or datetime.utcnow(),
            "metadata": metadata or {}
        }
        self._events.append(event)

    def get_channel_metrics(
        self,
        tenant_id: str,
        channel: NotificationChannel,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> ChannelMetrics:
        """Get metrics for a specific channel"""
        events = self._filter_events(tenant_id, start_time, end_time)
        channel_events = [e for e in events if e["channel"] == channel.value]

        metrics = ChannelMetrics(channel=channel)
        metrics.total_sent = len([e for e in channel_events if e["event_type"] == "sent"])
        metrics.total_delivered = len([e for e in channel_events if e["event_type"] == "delivered"])
        metrics.total_failed = len([e for e in channel_events if e["event_type"] == "failed"])
        metrics.total_opened = len([e for e in channel_events if e["event_type"] == "opened"])
        metrics.total_clicked = len([e for e in channel_events if e["event_type"] == "clicked"])
        metrics.total_bounced = len([e for e in channel_events if e["event_type"] == "bounced"])

        return metrics

    def get_all_channel_metrics(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, ChannelMetrics]:
        """Get metrics for all channels"""
        result = {}
        for channel in NotificationChannel:
            result[channel.value] = self.get_channel_metrics(
                tenant_id, channel, start_time, end_time
            )
        return result

    def _filter_events(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Filter events by tenant and time range"""
        events = [e for e in self._events if e["tenant_id"] == tenant_id]
        if start_time:
            events = [e for e in events if e["timestamp"] >= start_time]
        if end_time:
            events = [e for e in events if e["timestamp"] <= end_time]
        return events

    def get_metrics_over_time(
        self,
        tenant_id: str,
        metric_name: str,
        period: MetricPeriod = MetricPeriod.DAY,
        periods: int = 7
    ) -> List[MetricPoint]:
        """Get metric values over time"""
        now = datetime.utcnow()
        points = []

        for i in range(periods):
            if period == MetricPeriod.HOUR:
                start = now - timedelta(hours=i+1)
                end = now - timedelta(hours=i)
            elif period == MetricPeriod.DAY:
                start = (now - timedelta(days=i+1)).replace(hour=0, minute=0, second=0)
                end = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0)
            elif period == MetricPeriod.WEEK:
                start = now - timedelta(weeks=i+1)
                end = now - timedelta(weeks=i)
            else:  # MONTH
                start = now - timedelta(days=30*(i+1))
                end = now - timedelta(days=30*i)

            events = self._filter_events(tenant_id, start, end)
            value = len([e for e in events if e["event_type"] == metric_name])

            points.append(MetricPoint(timestamp=start, value=value))

        return list(reversed(points))

    def get_delivery_trends(
        self,
        tenant_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get delivery trends over time"""
        now = datetime.utcnow()
        start = now - timedelta(days=days)

        events = self._filter_events(tenant_id, start, now)

        daily_stats = []
        for i in range(days):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0)
            day_end = day_start + timedelta(days=1)

            day_events = [e for e in events if day_start <= e["timestamp"] < day_end]

            daily_stats.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "sent": len([e for e in day_events if e["event_type"] == "sent"]),
                "delivered": len([e for e in day_events if e["event_type"] == "delivered"]),
                "failed": len([e for e in day_events if e["event_type"] == "failed"])
            })

        return {
            "period_days": days,
            "daily_stats": list(reversed(daily_stats)),
            "total_sent": sum(d["sent"] for d in daily_stats),
            "total_delivered": sum(d["delivered"] for d in daily_stats)
        }

    def get_best_performing_channel(
        self,
        tenant_id: str,
        metric: str = "delivery_rate"
    ) -> Optional[NotificationChannel]:
        """Get the best performing channel"""
        metrics = self.get_all_channel_metrics(tenant_id)

        best_channel = None
        best_value = -1

        for channel, channel_metrics in metrics.items():
            if metric == "delivery_rate":
                value = channel_metrics.delivery_rate
            elif metric == "open_rate":
                value = channel_metrics.open_rate
            elif metric == "click_rate":
                value = channel_metrics.click_rate
            else:
                continue

            if value > best_value:
                best_value = value
                best_channel = NotificationChannel(channel)

        return best_channel

    def get_summary(
        self,
        tenant_id: str,
        period: MetricPeriod = MetricPeriod.DAY
    ) -> Dict[str, Any]:
        """Get summary metrics"""
        now = datetime.utcnow()
        if period == MetricPeriod.HOUR:
            start = now - timedelta(hours=1)
        elif period == MetricPeriod.DAY:
            start = now - timedelta(days=1)
        elif period == MetricPeriod.WEEK:
            start = now - timedelta(weeks=1)
        else:
            start = now - timedelta(days=30)

        channel_metrics = self.get_all_channel_metrics(tenant_id, start, now)

        total_sent = sum(m.total_sent for m in channel_metrics.values())
        total_delivered = sum(m.total_delivered for m in channel_metrics.values())
        total_failed = sum(m.total_failed for m in channel_metrics.values())

        return {
            "period": period.value,
            "start_time": start.isoformat(),
            "end_time": now.isoformat(),
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_failed": total_failed,
            "overall_delivery_rate": (total_delivered / total_sent * 100) if total_sent > 0 else 0,
            "by_channel": {
                ch: {
                    "sent": m.total_sent,
                    "delivered": m.total_delivered,
                    "delivery_rate": m.delivery_rate,
                    "open_rate": m.open_rate,
                    "click_rate": m.click_rate
                }
                for ch, m in channel_metrics.items()
            }
        }

    def cleanup_old_events(self, days: int = 90) -> int:
        """Remove events older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        initial_count = len(self._events)
        self._events = [e for e in self._events if e["timestamp"] >= cutoff]
        return initial_count - len(self._events)
