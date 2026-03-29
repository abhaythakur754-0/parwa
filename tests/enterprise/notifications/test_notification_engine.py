# Tests for Notification Engine - Week 48 Builder 1

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from enterprise.notifications.notification_engine import (
    NotificationEngine,
    Notification,
    NotificationQueue,
    NotificationPriority,
    NotificationStatus,
    NotificationChannel,
    NotificationResult
)


class TestNotification:
    """Test Notification dataclass"""

    def test_create_notification(self):
        notification = Notification(
            tenant_id="tenant1",
            user_id="user1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Test body"
        )
        assert notification.id is not None
        assert notification.tenant_id == "tenant1"
        assert notification.status == NotificationStatus.PENDING

    def test_notification_priority_comparison(self):
        low = Notification(priority=NotificationPriority.LOW)
        high = Notification(priority=NotificationPriority.HIGH)
        urgent = Notification(priority=NotificationPriority.URGENT)

        assert urgent < high
        assert high < low

    def test_notification_default_values(self):
        notification = Notification()
        assert notification.retry_count == 0
        assert notification.max_retries == 3
        assert notification.metadata == {}
        assert notification.template_vars == {}


class TestNotificationQueue:
    """Test NotificationQueue"""

    @pytest.mark.asyncio
    async def test_enqueue(self):
        queue = NotificationQueue()
        notification = Notification(
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        result = await queue.enqueue(notification)
        assert result is True
        assert notification.status == NotificationStatus.QUEUED

    @pytest.mark.asyncio
    async def test_dequeue(self):
        queue = NotificationQueue()
        notification = Notification(
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        await queue.enqueue(notification)
        result = await queue.dequeue()
        assert result.id == notification.id

    @pytest.mark.asyncio
    async def test_dequeue_empty(self):
        queue = NotificationQueue()
        result = await queue.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_priority_order(self):
        queue = NotificationQueue()
        
        low = Notification(priority=NotificationPriority.LOW, subject="low")
        urgent = Notification(priority=NotificationPriority.URGENT, subject="urgent")
        normal = Notification(priority=NotificationPriority.NORMAL, subject="normal")

        await queue.enqueue(low)
        await queue.enqueue(urgent)
        await queue.enqueue(normal)

        first = await queue.dequeue()
        assert first.priority == NotificationPriority.URGENT

    @pytest.mark.asyncio
    async def test_peek(self):
        queue = NotificationQueue()
        notification = Notification(subject="test")
        await queue.enqueue(notification)
        result = await queue.peek()
        assert result.id == notification.id
        assert await queue.size() == 1

    @pytest.mark.asyncio
    async def test_size(self):
        queue = NotificationQueue()
        assert await queue.size() == 0
        await queue.enqueue(Notification())
        assert await queue.size() == 1

    @pytest.mark.asyncio
    async def test_clear(self):
        queue = NotificationQueue()
        await queue.enqueue(Notification())
        await queue.enqueue(Notification())
        count = await queue.clear()
        assert count == 2
        assert await queue.size() == 0


class TestNotificationEngine:
    """Test NotificationEngine"""

    def test_create_notification(self):
        engine = NotificationEngine()
        notification = engine.create_notification(
            tenant_id="tenant1",
            user_id="user1",
            channel=NotificationChannel.EMAIL,
            subject="Test Subject",
            body="Test Body"
        )
        assert notification.tenant_id == "tenant1"
        assert notification.user_id == "user1"
        assert notification.channel == NotificationChannel.EMAIL

    def test_create_notification_with_template(self):
        engine = NotificationEngine()
        notification = engine.create_notification(
            tenant_id="tenant1",
            user_id="user1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body",
            template_id="welcome_email",
            template_vars={"name": "John"}
        )
        assert notification.template_id == "welcome_email"
        assert notification.template_vars == {"name": "John"}

    def test_register_channel(self):
        engine = NotificationEngine()
        handler = MagicMock()
        engine.register_channel(NotificationChannel.EMAIL, handler)
        assert NotificationChannel.EMAIL in engine._channels

    @pytest.mark.asyncio
    async def test_queue_notification(self):
        engine = NotificationEngine()
        notification = Notification(
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        result = await engine.queue_notification(notification)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        engine = NotificationEngine()
        
        mock_handler = AsyncMock()
        mock_handler.send.return_value = NotificationResult(
            notification_id="test-id",
            success=True,
            channel=NotificationChannel.EMAIL
        )
        engine.register_channel(NotificationChannel.EMAIL, mock_handler)

        notification = Notification(
            id="test-id",
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        engine._notifications["test-id"] = notification

        result = await engine.send_notification(notification)
        assert result.success is True
        assert notification.status == NotificationStatus.SENT

    @pytest.mark.asyncio
    async def test_send_notification_channel_not_registered(self):
        engine = NotificationEngine()
        notification = Notification(
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.SMS,
            subject="Test",
            body="Body"
        )
        result = await engine.send_notification(notification)
        assert result.success is False
        assert "not registered" in result.error_message

    @pytest.mark.asyncio
    async def test_process_queue(self):
        engine = NotificationEngine()
        
        mock_handler = AsyncMock()
        mock_handler.send.return_value = NotificationResult(
            notification_id="test-id",
            success=True,
            channel=NotificationChannel.EMAIL
        )
        engine.register_channel(NotificationChannel.EMAIL, mock_handler)

        notification = Notification(
            id="test-id",
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        engine._notifications["test-id"] = notification
        await engine.queue_notification(notification)

        results = await engine.process_queue(batch_size=1)
        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_retry_failed_notification(self):
        engine = NotificationEngine()
        
        mock_handler = AsyncMock()
        mock_handler.send.return_value = NotificationResult(
            notification_id="test-id",
            success=True,
            channel=NotificationChannel.EMAIL
        )
        engine.register_channel(NotificationChannel.EMAIL, mock_handler)

        notification = Notification(
            id="test-id",
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body",
            status=NotificationStatus.FAILED
        )
        engine._notifications["test-id"] = notification

        result = await engine.retry_failed("test-id")
        assert result.success is True
        assert notification.retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_exceeds_max(self):
        engine = NotificationEngine()
        notification = Notification(
            id="test-id",
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body",
            status=NotificationStatus.FAILED,
            retry_count=3
        )
        engine._notifications["test-id"] = notification

        result = await engine.retry_failed("test-id")
        assert result.success is False
        assert "Max retries exceeded" in result.error_message

    def test_cancel_notification(self):
        engine = NotificationEngine()
        notification = Notification(
            id="test-id",
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        engine._notifications["test-id"] = notification

        result = engine.cancel_notification("test-id")
        assert result is True
        assert notification.status == NotificationStatus.CANCELLED

    def test_cancel_sent_notification(self):
        engine = NotificationEngine()
        notification = Notification(
            id="test-id",
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body",
            status=NotificationStatus.SENT
        )
        engine._notifications["test-id"] = notification

        result = engine.cancel_notification("test-id")
        assert result is False

    def test_get_notification(self):
        engine = NotificationEngine()
        notification = engine.create_notification(
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        result = engine.get_notification(notification.id)
        assert result.id == notification.id

    def test_get_notifications_by_user(self):
        engine = NotificationEngine()
        engine.create_notification("t1", "user1", NotificationChannel.EMAIL, "Test1", "Body1")
        engine.create_notification("t1", "user1", NotificationChannel.SMS, "Test2", "Body2")
        engine.create_notification("t1", "user2", NotificationChannel.EMAIL, "Test3", "Body3")

        results = engine.get_notifications_by_user("user1")
        assert len(results) == 2

    def test_get_notifications_by_tenant(self):
        engine = NotificationEngine()
        engine.create_notification("tenant1", "u1", NotificationChannel.EMAIL, "Test", "Body")
        engine.create_notification("tenant2", "u2", NotificationChannel.EMAIL, "Test", "Body")

        results = engine.get_notifications_by_tenant("tenant1")
        assert len(results) == 1

    def test_get_pending_notifications(self):
        engine = NotificationEngine()
        n1 = engine.create_notification("t1", "u1", NotificationChannel.EMAIL, "Test", "Body")
        n2 = engine.create_notification("t1", "u2", NotificationChannel.EMAIL, "Test", "Body")
        n2.status = NotificationStatus.SENT

        results = engine.get_pending_notifications()
        assert len(results) == 1

    def test_get_scheduled_notifications(self):
        engine = NotificationEngine()
        n1 = engine.create_notification("t1", "u1", NotificationChannel.EMAIL, "Test", "Body")
        n1.scheduled_at = datetime.utcnow() + timedelta(hours=1)
        
        n2 = engine.create_notification("t1", "u2", NotificationChannel.EMAIL, "Test", "Body")
        n2.scheduled_at = datetime.utcnow() - timedelta(hours=1)

        results = engine.get_scheduled_notifications()
        assert len(results) == 1

    def test_mark_delivered(self):
        engine = NotificationEngine()
        notification = engine.create_notification(
            "t1", "u1", NotificationChannel.EMAIL, "Test", "Body"
        )
        notification.status = NotificationStatus.SENT
        result = engine.mark_delivered(notification.id)
        assert result is True
        assert notification.status == NotificationStatus.DELIVERED

    def test_bulk_create(self):
        engine = NotificationEngine()
        notifications = engine.bulk_create(
            tenant_id="t1",
            user_ids=["u1", "u2", "u3"],
            channel=NotificationChannel.EMAIL,
            subject="Bulk Test",
            body="Bulk Body"
        )
        assert len(notifications) == 3

    @pytest.mark.asyncio
    async def test_schedule_notification(self):
        engine = NotificationEngine()
        notification = Notification(
            tenant_id="t1",
            user_id="u1",
            channel=NotificationChannel.EMAIL,
            subject="Test",
            body="Body"
        )
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        result = await engine.schedule_notification(notification, scheduled_time)
        assert result is True
        assert notification.scheduled_at == scheduled_time
