# Notification Engine - Week 48 Builder 1
# Enterprise Notification System - Core Orchestrator

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import asyncio
import uuid
import heapq


class NotificationPriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20


class NotificationStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationChannel(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


@dataclass
class Notification:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    channel: NotificationChannel = NotificationChannel.EMAIL
    priority: NotificationPriority = NotificationPriority.NORMAL
    status: NotificationStatus = NotificationStatus.PENDING
    subject: str = ""
    body: str = ""
    template_id: Optional[str] = None
    template_vars: Dict[str, Any] = field(default_factory=dict)
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __lt__(self, other):
        return self.priority.value > other.priority.value


@dataclass
class NotificationResult:
    notification_id: str
    success: bool
    channel: NotificationChannel
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    delivered_at: Optional[datetime] = None


class NotificationQueue:
    """Priority queue for notifications"""

    def __init__(self):
        self._queue: List[Notification] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, notification: Notification) -> bool:
        async with self._lock:
            notification.status = NotificationStatus.QUEUED
            heapq.heappush(self._queue, notification)
            return True

    async def dequeue(self) -> Optional[Notification]:
        async with self._lock:
            if self._queue:
                return heapq.heappop(self._queue)
            return None

    async def peek(self) -> Optional[Notification]:
        async with self._lock:
            return self._queue[0] if self._queue else None

    async def size(self) -> int:
        async with self._lock:
            return len(self._queue)

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count


class NotificationEngine:
    """Core notification orchestrator for enterprise multi-channel notifications"""

    def __init__(self):
        self.queue = NotificationQueue()
        self._notifications: Dict[str, Notification] = {}
        self._channels: Dict[NotificationChannel, Any] = {}
        self._handlers: Dict[str, List[Notification]] = {}
        self._metrics = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "by_channel": {ch.value: 0 for ch in NotificationChannel}
        }

    def register_channel(self, channel_type: NotificationChannel, handler: Any) -> None:
        """Register a channel handler (email, sms, push, etc.)"""
        self._channels[channel_type] = handler

    def create_notification(
        self,
        tenant_id: str,
        user_id: str,
        channel: NotificationChannel,
        subject: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        template_id: Optional[str] = None,
        template_vars: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """Create a new notification"""
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            channel=channel,
            subject=subject,
            body=body,
            priority=priority,
            template_id=template_id,
            template_vars=template_vars or {},
            scheduled_at=scheduled_at,
            metadata=metadata or {}
        )
        self._notifications[notification.id] = notification
        return notification

    async def queue_notification(self, notification: Notification) -> bool:
        """Add notification to the priority queue"""
        return await self.queue.enqueue(notification)

    async def send_notification(self, notification: Notification) -> NotificationResult:
        """Send a notification through its designated channel"""
        if notification.channel not in self._channels:
            return NotificationResult(
                notification_id=notification.id,
                success=False,
                channel=notification.channel,
                error_message=f"Channel {notification.channel.value} not registered"
            )

        notification.status = NotificationStatus.SENDING
        notification.updated_at = datetime.utcnow()

        try:
            handler = self._channels[notification.channel]
            result = await handler.send(notification)

            if result.success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
                self._metrics["total_sent"] += 1
                self._metrics["by_channel"][notification.channel.value] += 1
            else:
                notification.status = NotificationStatus.FAILED
                self._metrics["total_failed"] += 1

            notification.updated_at = datetime.utcnow()
            return result

        except Exception as e:
            notification.status = NotificationStatus.FAILED
            self._metrics["total_failed"] += 1
            return NotificationResult(
                notification_id=notification.id,
                success=False,
                channel=notification.channel,
                error_message=str(e)
            )

    async def process_queue(self, batch_size: int = 10) -> List[NotificationResult]:
        """Process queued notifications in batch"""
        results = []
        processed = 0

        while processed < batch_size:
            notification = await self.queue.dequeue()
            if notification is None:
                break

            result = await self.send_notification(notification)
            results.append(result)
            processed += 1

        return results

    async def retry_failed(self, notification_id: str) -> NotificationResult:
        """Retry a failed notification"""
        notification = self._notifications.get(notification_id)
        if not notification:
            return NotificationResult(
                notification_id=notification_id,
                success=False,
                channel=NotificationChannel.EMAIL,
                error_message="Notification not found"
            )

        if notification.retry_count >= notification.max_retries:
            return NotificationResult(
                notification_id=notification_id,
                success=False,
                channel=notification.channel,
                error_message="Max retries exceeded"
            )

        notification.retry_count += 1
        notification.status = NotificationStatus.PENDING
        return await self.send_notification(notification)

    def cancel_notification(self, notification_id: str) -> bool:
        """Cancel a pending notification"""
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        if notification.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED]:
            return False

        notification.status = NotificationStatus.CANCELLED
        notification.updated_at = datetime.utcnow()
        return True

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Get notification by ID"""
        return self._notifications.get(notification_id)

    def get_notifications_by_user(self, user_id: str) -> List[Notification]:
        """Get all notifications for a user"""
        return [n for n in self._notifications.values() if n.user_id == user_id]

    def get_notifications_by_tenant(self, tenant_id: str) -> List[Notification]:
        """Get all notifications for a tenant"""
        return [n for n in self._notifications.values() if n.tenant_id == tenant_id]

    def get_pending_notifications(self) -> List[Notification]:
        """Get all pending notifications"""
        return [n for n in self._notifications.values() 
                if n.status == NotificationStatus.PENDING]

    def get_scheduled_notifications(self) -> List[Notification]:
        """Get all scheduled notifications"""
        now = datetime.utcnow()
        return [n for n in self._notifications.values() 
                if n.scheduled_at and n.scheduled_at > now]

    def mark_delivered(self, notification_id: str) -> bool:
        """Mark notification as delivered"""
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        notification.status = NotificationStatus.DELIVERED
        notification.delivered_at = datetime.utcnow()
        notification.updated_at = datetime.utcnow()
        self._metrics["total_delivered"] += 1
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get notification metrics"""
        return {
            **self._metrics,
            "queue_size": asyncio.get_event_loop().run_until_complete(self.queue.size()) if asyncio.get_event_loop().is_running() else 0,
            "total_notifications": len(self._notifications)
        }

    def bulk_create(
        self,
        tenant_id: str,
        user_ids: List[str],
        channel: NotificationChannel,
        subject: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> List[Notification]:
        """Create notifications for multiple users"""
        notifications = []
        for user_id in user_ids:
            notification = self.create_notification(
                tenant_id=tenant_id,
                user_id=user_id,
                channel=channel,
                subject=subject,
                body=body,
                priority=priority
            )
            notifications.append(notification)
        return notifications

    async def schedule_notification(
        self,
        notification: Notification,
        scheduled_at: datetime
    ) -> bool:
        """Schedule a notification for future delivery"""
        notification.scheduled_at = scheduled_at
        notification.status = NotificationStatus.PENDING
        return True
