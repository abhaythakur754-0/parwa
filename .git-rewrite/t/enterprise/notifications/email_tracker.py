# Email Tracker - Week 48 Builder 2
# Email delivery and engagement tracking

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class TrackingEventType(Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    COMPLAINED = "complained"


@dataclass
class TrackingEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_id: str = ""
    tenant_id: str = ""
    event_type: TrackingEventType = TrackingEventType.SENT
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    url: Optional[str] = None  # For click tracking
    bounce_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailTrackingData:
    message_id: str = ""
    tenant_id: str = ""
    tracking_pixel_url: Optional[str] = None
    tracking_links: Dict[str, str] = field(default_factory=dict)  # original -> tracked URL
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EngagementStats:
    message_id: str = ""
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    first_open_at: Optional[datetime] = None
    last_open_at: Optional[datetime] = None
    open_count: int = 0
    first_click_at: Optional[datetime] = None
    last_click_at: Optional[datetime] = None
    click_count: int = 0
    clicked_urls: List[str] = field(default_factory=list)


class EmailTracker:
    """Tracks email delivery and engagement"""

    def __init__(self, base_tracking_url: str = "https://track.example.com"):
        self._base_url = base_tracking_url.rstrip("/")
        self._tracking_data: Dict[str, EmailTrackingData] = {}
        self._events: List[TrackingEvent] = []
        self._engagement: Dict[str, EngagementStats] = {}
        self._metrics = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_opens": 0,
            "total_clicks": 0,
            "total_bounces": 0,
            "total_unsubscribes": 0
        }

    def generate_tracking(
        self,
        message_id: str,
        tenant_id: str,
        links: Optional[List[str]] = None
    ) -> EmailTrackingData:
        """Generate tracking data for an email"""
        # Generate tracking pixel URL
        pixel_url = f"{self._base_url}/pixel/{message_id}"

        # Generate tracked links
        tracked_links = {}
        if links:
            for i, original_url in enumerate(links):
                tracked_url = f"{self._base_url}/click/{message_id}/{i}"
                tracked_links[original_url] = tracked_url

        tracking = EmailTrackingData(
            message_id=message_id,
            tenant_id=tenant_id,
            tracking_pixel_url=pixel_url,
            tracking_links=tracked_links
        )

        self._tracking_data[message_id] = tracking
        self._engagement[message_id] = EngagementStats(message_id=message_id)

        return tracking

    def record_event(
        self,
        message_id: str,
        tenant_id: str,
        event_type: TrackingEventType,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        url: Optional[str] = None,
        bounce_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrackingEvent:
        """Record a tracking event"""
        event = TrackingEvent(
            message_id=message_id,
            tenant_id=tenant_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            url=url,
            bounce_reason=bounce_reason,
            metadata=metadata or {}
        )

        self._events.append(event)
        self._update_metrics(event)
        self._update_engagement(event)

        return event

    def _update_metrics(self, event: TrackingEvent) -> None:
        """Update aggregate metrics"""
        if event.event_type == TrackingEventType.SENT:
            self._metrics["total_sent"] += 1
        elif event.event_type == TrackingEventType.DELIVERED:
            self._metrics["total_delivered"] += 1
        elif event.event_type == TrackingEventType.OPENED:
            self._metrics["total_opens"] += 1
        elif event.event_type == TrackingEventType.CLICKED:
            self._metrics["total_clicks"] += 1
        elif event.event_type == TrackingEventType.BOUNCED:
            self._metrics["total_bounces"] += 1
        elif event.event_type == TrackingEventType.UNSUBSCRIBED:
            self._metrics["total_unsubscribes"] += 1

    def _update_engagement(self, event: TrackingEvent) -> None:
        """Update engagement stats for a message"""
        stats = self._engagement.get(event.message_id)
        if not stats:
            stats = EngagementStats(message_id=event.message_id)
            self._engagement[event.message_id] = stats

        if event.event_type == TrackingEventType.SENT:
            stats.sent_at = event.timestamp
        elif event.event_type == TrackingEventType.DELIVERED:
            stats.delivered_at = event.timestamp
        elif event.event_type == TrackingEventType.OPENED:
            if stats.first_open_at is None:
                stats.first_open_at = event.timestamp
            stats.last_open_at = event.timestamp
            stats.open_count += 1
        elif event.event_type == TrackingEventType.CLICKED:
            if stats.first_click_at is None:
                stats.first_click_at = event.timestamp
            stats.last_click_at = event.timestamp
            stats.click_count += 1
            if event.url and event.url not in stats.clicked_urls:
                stats.clicked_urls.append(event.url)

    def get_tracking_data(self, message_id: str) -> Optional[EmailTrackingData]:
        """Get tracking data for a message"""
        return self._tracking_data.get(message_id)

    def get_engagement(self, message_id: str) -> Optional[EngagementStats]:
        """Get engagement stats for a message"""
        return self._engagement.get(message_id)

    def get_events(
        self,
        message_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        event_type: Optional[TrackingEventType] = None,
        since: Optional[datetime] = None
    ) -> List[TrackingEvent]:
        """Get tracking events with filters"""
        events = self._events

        if message_id:
            events = [e for e in events if e.message_id == message_id]
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if since:
            events = [e for e in events if e.timestamp >= since]

        return events

    def resolve_tracked_link(
        self,
        message_id: str,
        link_index: int
    ) -> Optional[str]:
        """Resolve a tracked link to the original URL"""
        tracking = self._tracking_data.get(message_id)
        if not tracking:
            return None

        # Find original URL by index
        for i, (original, tracked) in enumerate(tracking.tracking_links.items()):
            if i == link_index:
                return original

        return None

    def record_open(
        self,
        message_id: str,
        tenant_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TrackingEvent:
        """Record an email open event"""
        return self.record_event(
            message_id=message_id,
            tenant_id=tenant_id,
            event_type=TrackingEventType.OPENED,
            ip_address=ip_address,
            user_agent=user_agent
        )

    def record_click(
        self,
        message_id: str,
        tenant_id: str,
        url: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TrackingEvent:
        """Record a link click event"""
        return self.record_event(
            message_id=message_id,
            tenant_id=tenant_id,
            event_type=TrackingEventType.CLICKED,
            ip_address=ip_address,
            user_agent=user_agent,
            url=url
        )

    def get_open_rate(self, tenant_id: str) -> float:
        """Calculate open rate for a tenant"""
        sent = len([e for e in self._events 
                   if e.tenant_id == tenant_id and e.event_type == TrackingEventType.SENT])
        if sent == 0:
            return 0.0

        opened_messages = set(
            e.message_id for e in self._events
            if e.tenant_id == tenant_id and e.event_type == TrackingEventType.OPENED
        )

        return (len(opened_messages) / sent) * 100

    def get_click_rate(self, tenant_id: str) -> float:
        """Calculate click rate for a tenant"""
        opened = len([e for e in self._events 
                     if e.tenant_id == tenant_id and e.event_type == TrackingEventType.OPENED])
        if opened == 0:
            return 0.0

        clicked_messages = set(
            e.message_id for e in self._events
            if e.tenant_id == tenant_id and e.event_type == TrackingEventType.CLICKED
        )

        return (len(clicked_messages) / opened) * 100

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics"""
        return {
            **self._metrics,
            "total_messages_tracked": len(self._tracking_data)
        }

    def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get metrics for a specific tenant"""
        tenant_events = [e for e in self._events if e.tenant_id == tenant_id]

        return {
            "sent": len([e for e in tenant_events if e.event_type == TrackingEventType.SENT]),
            "delivered": len([e for e in tenant_events if e.event_type == TrackingEventType.DELIVERED]),
            "opens": len([e for e in tenant_events if e.event_type == TrackingEventType.OPENED]),
            "clicks": len([e for e in tenant_events if e.event_type == TrackingEventType.CLICKED]),
            "bounces": len([e for e in tenant_events if e.event_type == TrackingEventType.BOUNCED]),
            "open_rate": self.get_open_rate(tenant_id),
            "click_rate": self.get_click_rate(tenant_id)
        }

    def cleanup_old_events(self, days: int = 90) -> int:
        """Remove events older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        initial_count = len(self._events)
        self._events = [e for e in self._events if e.timestamp >= cutoff]
        return initial_count - len(self._events)
