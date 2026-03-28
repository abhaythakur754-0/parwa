"""
Notification Router Module - Week 53, Builder 2
Alert notification routing system
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import asyncio

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Notification channel types"""
    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"
    SMS = "sms"
    TEAMS = "teams"


class NotificationStatus(Enum):
    """Notification status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class NotificationChannel:
    """Notification channel configuration"""
    name: str
    channel_type: ChannelType
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    severity_filter: List[str] = field(default_factory=list)
    rate_limit: int = 60  # seconds between notifications

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.channel_type.value,
            "enabled": self.enabled,
        }


@dataclass
class Notification:
    """Notification data"""
    notification_id: str
    channel: str
    subject: str
    message: str
    severity: str
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    retries: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationRouter:
    """
    Routes alert notifications to appropriate channels.
    """

    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        self._senders: Dict[ChannelType, Callable] = {}
        self._history: List[Notification] = []
        self._last_sent: Dict[str, datetime] = {}
        self.max_history = 10000

    def add_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel"""
        self.channels[channel.name] = channel
        logger.info(f"Added notification channel: {channel.name}")

    def remove_channel(self, name: str) -> bool:
        """Remove a notification channel"""
        if name in self.channels:
            del self.channels[name]
            return True
        return False

    def register_sender(
        self,
        channel_type: ChannelType,
        sender: Callable,
    ) -> None:
        """Register a sender function for a channel type"""
        self._senders[channel_type] = sender

    def _check_rate_limit(self, channel_name: str) -> bool:
        """Check if rate limit allows sending"""
        channel = self.channels.get(channel_name)
        if not channel:
            return False

        last_sent = self._last_sent.get(channel_name)
        if last_sent:
            elapsed = (datetime.utcnow() - last_sent).total_seconds()
            if elapsed < channel.rate_limit:
                return False

        return True

    def _filter_by_severity(
        self,
        channel: NotificationChannel,
        severity: str,
    ) -> bool:
        """Check if severity matches channel filter"""
        if not channel.severity_filter:
            return True
        return severity in channel.severity_filter

    async def send(
        self,
        channel_name: str,
        subject: str,
        message: str,
        severity: str = "warning",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Send a notification"""
        import uuid

        notification = Notification(
            notification_id=str(uuid.uuid4())[:8],
            channel=channel_name,
            subject=subject,
            message=message,
            severity=severity,
            metadata=metadata or {},
        )

        channel = self.channels.get(channel_name)
        if not channel:
            notification.status = NotificationStatus.FAILED
            notification.error = f"Channel not found: {channel_name}"
            self._add_to_history(notification)
            return notification

        if not channel.enabled:
            notification.status = NotificationStatus.FAILED
            notification.error = "Channel disabled"
            self._add_to_history(notification)
            return notification

        if not self._check_rate_limit(channel_name):
            notification.status = NotificationStatus.FAILED
            notification.error = "Rate limited"
            self._add_to_history(notification)
            return notification

        if not self._filter_by_severity(channel, severity):
            notification.status = NotificationStatus.FAILED
            notification.error = "Severity not matched"
            self._add_to_history(notification)
            return notification

        # Send notification
        sender = self._senders.get(channel.channel_type)
        if sender:
            try:
                if asyncio.iscoroutine(sender):
                    await sender(channel, notification)
                else:
                    sender(channel, notification)

                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
                self._last_sent[channel_name] = datetime.utcnow()

            except Exception as e:
                notification.status = NotificationStatus.FAILED
                notification.error = str(e)
                logger.error(f"Notification failed: {e}")
        else:
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            logger.info(f"No sender for {channel.channel_type.value}, marking as sent")

        self._add_to_history(notification)
        return notification

    def _add_to_history(self, notification: Notification) -> None:
        """Add to notification history"""
        self._history.append(notification)
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

    async def broadcast(
        self,
        subject: str,
        message: str,
        severity: str = "warning",
        channels: Optional[List[str]] = None,
    ) -> List[Notification]:
        """Broadcast to multiple channels"""
        target_channels = channels or list(self.channels.keys())
        results = []

        for channel_name in target_channels:
            if channel_name in self.channels:
                result = await self.send(
                    channel_name, subject, message, severity
                )
                results.append(result)

        return results

    def get_history(
        self,
        channel: Optional[str] = None,
        limit: int = 100,
    ) -> List[Notification]:
        """Get notification history"""
        history = self._history
        if channel:
            history = [n for n in history if n.channel == channel]
        return history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics"""
        sent = sum(1 for n in self._history if n.status == NotificationStatus.SENT)
        failed = sum(1 for n in self._history if n.status == NotificationStatus.FAILED)

        return {
            "channels": len(self.channels),
            "total_notifications": len(self._history),
            "sent": sent,
            "failed": failed,
            "success_rate": (sent / len(self._history) * 100) if self._history else 0,
        }

    def retry_failed(self, max_retries: int = 3) -> List[Notification]:
        """Retry failed notifications"""
        failed = [
            n for n in self._history
            if n.status == NotificationStatus.FAILED and n.retries < max_retries
        ]
        # In production, would actually retry
        for n in failed:
            n.retries += 1
        return failed
