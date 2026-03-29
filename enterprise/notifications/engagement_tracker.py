# Engagement Tracker - Week 48 Builder 5
# Open and click tracking for notifications

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class EngagementType(Enum):
    OPEN = "open"
    CLICK = "click"
    UNSUBSCRIBE = "unsubscribe"
    FORWARD = "forward"
    REPLY = "reply"


class EngagementDevice(Enum):
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    UNKNOWN = "unknown"


@dataclass
class EngagementEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    notification_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    engagement_type: EngagementType = EngagementType.OPEN
    device: EngagementDevice = EngagementDevice.UNKNOWN
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    url: Optional[str] = None  # For clicks
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserEngagement:
    user_id: str = ""
    tenant_id: str = ""
    total_opens: int = 0
    total_clicks: int = 0
    first_open: Optional[datetime] = None
    last_open: Optional[datetime] = None
    first_click: Optional[datetime] = None
    last_click: Optional[datetime] = None
    devices_used: List[str] = field(default_factory=list)
    clicked_urls: List[str] = field(default_factory=list)


@dataclass
class NotificationEngagement:
    notification_id: str = ""
    tenant_id: str = ""
    total_opens: int = 0
    unique_opens: int = 0
    total_clicks: int = 0
    unique_clicks: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    click_to_open_rate: float = 0.0
    first_open: Optional[datetime] = None
    last_open: Optional[datetime] = None
    device_breakdown: Dict[str, int] = field(default_factory=dict)


class EngagementTracker:
    """Tracks notification engagement events"""

    def __init__(self):
        self._events: List[EngagementEvent] = []
        self._user_engagement: Dict[str, UserEngagement] = {}
        self._notification_engagement: Dict[str, NotificationEngagement] = {}
        self._metrics = {
            "total_opens": 0,
            "total_clicks": 0,
            "total_unsubscribes": 0,
            "unique_users_engaged": 0
        }

    def record_open(
        self,
        notification_id: str,
        tenant_id: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> EngagementEvent:
        """Record an open event"""
        device = self._detect_device(user_agent)

        event = EngagementEvent(
            notification_id=notification_id,
            tenant_id=tenant_id,
            user_id=user_id,
            engagement_type=EngagementType.OPEN,
            device=device,
            ip_address=ip_address,
            user_agent=user_agent
        )

        self._events.append(event)
        self._update_user_engagement(event)
        self._update_notification_engagement(event)
        self._metrics["total_opens"] += 1

        return event

    def record_click(
        self,
        notification_id: str,
        tenant_id: str,
        user_id: str,
        url: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> EngagementEvent:
        """Record a click event"""
        device = self._detect_device(user_agent)

        event = EngagementEvent(
            notification_id=notification_id,
            tenant_id=tenant_id,
            user_id=user_id,
            engagement_type=EngagementType.CLICK,
            device=device,
            ip_address=ip_address,
            user_agent=user_agent,
            url=url
        )

        self._events.append(event)
        self._update_user_engagement(event)
        self._update_notification_engagement(event)
        self._metrics["total_clicks"] += 1

        return event

    def record_unsubscribe(
        self,
        notification_id: str,
        tenant_id: str,
        user_id: str
    ) -> EngagementEvent:
        """Record an unsubscribe event"""
        event = EngagementEvent(
            notification_id=notification_id,
            tenant_id=tenant_id,
            user_id=user_id,
            engagement_type=EngagementType.UNSUBSCRIBE
        )

        self._events.append(event)
        self._metrics["total_unsubscribes"] += 1

        return event

    def _detect_device(self, user_agent: Optional[str]) -> EngagementDevice:
        """Detect device type from user agent"""
        if not user_agent:
            return EngagementDevice.UNKNOWN

        user_agent = user_agent.lower()

        if "mobile" in user_agent or "android" in user_agent or "iphone" in user_agent:
            return EngagementDevice.MOBILE
        elif "tablet" in user_agent or "ipad" in user_agent:
            return EngagementDevice.TABLET
        elif "windows" in user_agent or "macintosh" in user_agent or "linux" in user_agent:
            return EngagementDevice.DESKTOP

        return EngagementDevice.UNKNOWN

    def _update_user_engagement(self, event: EngagementEvent) -> None:
        """Update user engagement stats"""
        key = f"{event.tenant_id}:{event.user_id}"

        if key not in self._user_engagement:
            self._user_engagement[key] = UserEngagement(
                user_id=event.user_id,
                tenant_id=event.tenant_id
            )
            self._metrics["unique_users_engaged"] += 1

        user_eng = self._user_engagement[key]

        if event.engagement_type == EngagementType.OPEN:
            user_eng.total_opens += 1
            if user_eng.first_open is None:
                user_eng.first_open = event.timestamp
            user_eng.last_open = event.timestamp

        elif event.engagement_type == EngagementType.CLICK:
            user_eng.total_clicks += 1
            if user_eng.first_click is None:
                user_eng.first_click = event.timestamp
            user_eng.last_click = event.timestamp
            if event.url and event.url not in user_eng.clicked_urls:
                user_eng.clicked_urls.append(event.url)

        if event.device.value not in user_eng.devices_used:
            user_eng.devices_used.append(event.device.value)

    def _update_notification_engagement(self, event: EngagementEvent) -> None:
        """Update notification engagement stats"""
        key = event.notification_id

        if key not in self._notification_engagement:
            self._notification_engagement[key] = NotificationEngagement(
                notification_id=event.notification_id,
                tenant_id=event.tenant_id
            )

        notif_eng = self._notification_engagement[key]

        if event.engagement_type == EngagementType.OPEN:
            notif_eng.total_opens += 1
            if notif_eng.first_open is None:
                notif_eng.first_open = event.timestamp
            notif_eng.last_open = event.timestamp

        elif event.engagement_type == EngagementType.CLICK:
            notif_eng.total_clicks += 1

        # Update device breakdown
        device_key = event.device.value
        notif_eng.device_breakdown[device_key] = notif_eng.device_breakdown.get(device_key, 0) + 1

    def get_user_engagement(self, user_id: str, tenant_id: str) -> Optional[UserEngagement]:
        """Get engagement stats for a user"""
        key = f"{tenant_id}:{user_id}"
        return self._user_engagement.get(key)

    def get_notification_engagement(self, notification_id: str) -> Optional[NotificationEngagement]:
        """Get engagement stats for a notification"""
        return self._notification_engagement.get(notification_id)

    def calculate_unique_opens(self, notification_id: str) -> int:
        """Calculate unique opens for a notification"""
        events = [
            e for e in self._events
            if e.notification_id == notification_id
            and e.engagement_type == EngagementType.OPEN
        ]
        unique_users = set(e.user_id for e in events)
        return len(unique_users)

    def calculate_unique_clicks(self, notification_id: str) -> int:
        """Calculate unique clicks for a notification"""
        events = [
            e for e in self._events
            if e.notification_id == notification_id
            and e.engagement_type == EngagementType.CLICK
        ]
        unique_users = set(e.user_id for e in events)
        return len(unique_users)

    def get_engagement_timeline(
        self,
        notification_id: str,
        hours: int = 72
    ) -> List[Dict[str, Any]]:
        """Get engagement timeline for a notification"""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=hours)

        events = [
            e for e in self._events
            if e.notification_id == notification_id
            and e.timestamp >= cutoff
        ]

        # Group by hour
        timeline = []
        for i in range(hours):
            hour_start = now - timedelta(hours=i+1)
            hour_end = now - timedelta(hours=i)

            hour_events = [
                e for e in events
                if hour_start <= e.timestamp < hour_end
            ]

            timeline.append({
                "hour": hour_start.strftime("%Y-%m-%d %H:00"),
                "opens": len([e for e in hour_events if e.engagement_type == EngagementType.OPEN]),
                "clicks": len([e for e in hour_events if e.engagement_type == EngagementType.CLICK])
            })

        return list(reversed(timeline))

    def get_top_clicked_urls(
        self,
        tenant_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get most clicked URLs for a tenant"""
        url_clicks: Dict[str, int] = {}

        for event in self._events:
            if (
                event.tenant_id == tenant_id
                and event.engagement_type == EngagementType.CLICK
                and event.url
            ):
                url_clicks[event.url] = url_clicks.get(event.url, 0) + 1

        sorted_urls = sorted(url_clicks.items(), key=lambda x: x[1], reverse=True)[:limit]

        return [{"url": url, "clicks": count} for url, count in sorted_urls]

    def get_engagement_by_device(
        self,
        tenant_id: str
    ) -> Dict[str, int]:
        """Get engagement breakdown by device"""
        device_counts: Dict[str, int] = {}

        for event in self._events:
            if event.tenant_id == tenant_id:
                device_key = event.device.value
                device_counts[device_key] = device_counts.get(device_key, 0) + 1

        return device_counts

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics"""
        return {
            **self._metrics,
            "total_events": len(self._events),
            "total_users_tracked": len(self._user_engagement),
            "total_notifications_tracked": len(self._notification_engagement)
        }

    def cleanup_old_events(self, days: int = 90) -> int:
        """Remove old events"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        initial_count = len(self._events)
        self._events = [e for e in self._events if e.timestamp >= cutoff]
        return initial_count - len(self._events)
