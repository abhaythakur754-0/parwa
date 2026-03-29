# Tests for Week 48 Builder 3 - SMS & Push Notifications
# Unit tests for sms_channel.py, push_channel.py, mobile_notifier.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from enterprise.notifications.sms_channel import (
    SMSChannel,
    SMSMessage,
    SMSConfig,
    SMSProvider,
    SMSStatus,
    SendResult
)

from enterprise.notifications.push_channel import (
    PushChannel,
    PushNotification,
    PushConfig,
    PushProvider,
    PushPriority,
    PushStatus,
    PushResult
)

from enterprise.notifications.mobile_notifier import (
    MobileNotifier,
    MobileDevice,
    MobileNotification,
    NotificationFallback
)


# ============== SMS CHANNEL TESTS ==============

class TestSMSChannel:
    def test_create_message(self):
        channel = SMSChannel()
        message = channel.create_message(
            tenant_id="t1",
            to_number="+1234567890",
            body="Test message"
        )
        assert message.tenant_id == "t1"
        assert message.to_number == "+1234567890"
        assert message.body == "Test message"

    def test_normalize_number(self):
        channel = SMSChannel()
        # Number with country code
        assert channel._normalize_number("+1234567890") == "+1234567890"
        # Number without country code
        assert channel._normalize_number("2345678901") == "+12345678901"

    def test_calculate_segments(self):
        channel = SMSChannel()
        # Single segment
        assert channel._calculate_segments("Short message") == 1
        # Multi segment
        long_message = "x" * 200
        assert channel._calculate_segments(long_message) == 2

    def test_get_message(self):
        channel = SMSChannel()
        message = channel.create_message("t1", "+1234567890", "Test")
        result = channel.get_message(message.id)
        assert result.id == message.id

    def test_get_messages_by_tenant(self):
        channel = SMSChannel()
        channel.create_message("t1", "+1111111111", "Test1")
        channel.create_message("t1", "+2222222222", "Test2")
        channel.create_message("t2", "+3333333333", "Test3")

        results = channel.get_messages_by_tenant("t1")
        assert len(results) == 2

    def test_mark_delivered(self):
        channel = SMSChannel()
        message = channel.create_message("t1", "+1234567890", "Test")
        message.status = SMSStatus.SENT
        result = channel.mark_delivered(message.id)
        assert result is True
        assert message.status == SMSStatus.DELIVERED

    def test_get_pending_messages(self):
        channel = SMSChannel()
        m1 = channel.create_message("t1", "+1111111111", "Test")
        m2 = channel.create_message("t1", "+2222222222", "Test")
        m2.status = SMSStatus.SENT

        pending = channel.get_pending_messages()
        assert len(pending) == 1

    def test_get_failed_messages(self):
        channel = SMSChannel()
        m1 = channel.create_message("t1", "+1111111111", "Test")
        m2 = channel.create_message("t1", "+2222222222", "Test")
        m2.status = SMSStatus.FAILED

        failed = channel.get_failed_messages()
        assert len(failed) == 1

    def test_estimate_cost(self):
        channel = SMSChannel()
        cost = channel.estimate_cost("Short message")
        assert cost > 0

    def test_get_metrics(self):
        channel = SMSChannel()
        metrics = channel.get_metrics()
        assert "total_sent" in metrics
        assert "total_failed" in metrics

    @pytest.mark.asyncio
    async def test_send_message_mock(self):
        channel = SMSChannel()
        message = channel.create_message("t1", "+1234567890", "Test")

        # Mock Twilio response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "sid": "SM123",
            "num_segments": "1",
            "price": "0.0075"
        }

        with patch.object(channel, '_send_twilio', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SendResult(
                message_id=message.id,
                success=True,
                external_id="SM123",
                segments=1,
                cost=0.0075
            )
            result = await channel.send(message)

        assert result.success is True
        assert message.status == SMSStatus.SENT


# ============== PUSH CHANNEL TESTS ==============

class TestPushChannel:
    def test_create_notification(self):
        channel = PushChannel()
        notification = channel.create_notification(
            tenant_id="t1",
            device_token="abc123token",
            title="Test Title",
            body="Test body"
        )
        assert notification.tenant_id == "t1"
        assert notification.title == "Test Title"

    def test_create_notification_with_data(self):
        channel = PushChannel()
        notification = channel.create_notification(
            tenant_id="t1",
            device_token="token123",
            title="Test",
            body="Body",
            data={"order_id": "12345"},
            badge=5
        )
        assert notification.data == {"order_id": "12345"}
        assert notification.badge == 5

    def test_detect_device_type_android(self):
        channel = PushChannel()
        # FCM token (not 64 hex chars)
        device_type = channel._detect_device_type("fcm_token_abc123")
        assert device_type == "android"

    def test_detect_device_type_ios(self):
        channel = PushChannel()
        # APNs token (64 hex chars)
        device_type = channel._detect_device_type("a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")
        assert device_type == "ios"

    def test_register_device(self):
        channel = PushChannel()
        channel.register_device(
            tenant_id="t1",
            user_id="u1",
            device_token="token123",
            device_type="android"
        )
        devices = channel.get_user_devices("u1")
        assert len(devices) == 1

    def test_unregister_device(self):
        channel = PushChannel()
        channel.register_device("t1", "u1", "token123")
        result = channel.unregister_device("token123")
        assert result is True
        devices = channel.get_user_devices("u1")
        assert len(devices) == 0

    def test_get_notification(self):
        channel = PushChannel()
        notification = channel.create_notification("t1", "token", "Test", "Body")
        result = channel.get_notification(notification.id)
        assert result.id == notification.id

    def test_mark_delivered(self):
        channel = PushChannel()
        notification = channel.create_notification("t1", "token", "Test", "Body")
        notification.status = PushStatus.SENT
        result = channel.mark_delivered(notification.id)
        assert result is True
        assert notification.status == PushStatus.DELIVERED

    def test_get_metrics(self):
        channel = PushChannel()
        metrics = channel.get_metrics()
        assert "total_sent" in metrics
        assert "total_failed" in metrics
        assert "by_device_type" in metrics

    @pytest.mark.asyncio
    async def test_send_notification_mock(self):
        channel = PushChannel()
        notification = channel.create_notification(
            tenant_id="t1",
            device_token="token123",
            title="Test",
            body="Body"
        )

        with patch.object(channel, '_send_fcm', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = PushResult(
                notification_id=notification.id,
                success=True,
                external_id="msg123"
            )
            result = await channel.send(notification)

        assert result.success is True
        assert notification.status == PushStatus.SENT


# ============== MOBILE NOTIFIER TESTS ==============

class TestMobileNotifier:
    def test_register_device(self):
        notifier = MobileNotifier()
        device = notifier.register_device(
            user_id="u1",
            tenant_id="t1",
            device_token="token123",
            device_type="android"
        )
        assert device.user_id == "u1"
        assert device.device_token == "token123"

    def test_register_device_with_phone(self):
        notifier = MobileNotifier()
        device = notifier.register_device(
            user_id="u1",
            tenant_id="t1",
            device_token="token123",
            phone_number="+1234567890"
        )
        assert device.phone_number == "+1234567890"

    def test_update_device(self):
        notifier = MobileNotifier()
        device = notifier.register_device("u1", "t1", "token123")
        updated = notifier.update_device(
            device.device_id,
            push_enabled=False
        )
        assert updated.push_enabled is False

    def test_unregister_device(self):
        notifier = MobileNotifier()
        device = notifier.register_device("u1", "t1", "token123")
        result = notifier.unregister_device(device.device_id)
        assert result is True
        assert notifier.get_device(device.device_id) is None

    def test_get_user_devices(self):
        notifier = MobileNotifier()
        notifier.register_device("u1", "t1", "token1")
        notifier.register_device("u1", "t1", "token2")
        notifier.register_device("u2", "t1", "token3")

        devices = notifier.get_user_devices("u1")
        assert len(devices) == 2

    def test_create_notification(self):
        notifier = MobileNotifier()
        notification = notifier.create_notification(
            user_id="u1",
            tenant_id="t1",
            title="Test",
            body="Body"
        )
        assert notification.user_id == "u1"
        assert notification.title == "Test"

    def test_create_notification_with_fallback(self):
        notifier = MobileNotifier()
        notification = notifier.create_notification(
            user_id="u1",
            tenant_id="t1",
            title="Test",
            body="Body",
            fallback=NotificationFallback.PUSH_TO_SMS
        )
        assert notification.fallback == NotificationFallback.PUSH_TO_SMS

    def test_get_device(self):
        notifier = MobileNotifier()
        device = notifier.register_device("u1", "t1", "token123")
        result = notifier.get_device(device.device_id)
        assert result.device_id == device.device_id

    def test_get_notification(self):
        notifier = MobileNotifier()
        notification = notifier.create_notification("u1", "t1", "Test", "Body")
        result = notifier.get_notification(notification.id)
        assert result.id == notification.id

    def test_get_metrics(self):
        notifier = MobileNotifier()
        notifier.register_device("u1", "t1", "token1")
        notifier.create_notification("u1", "t1", "Test", "Body")
        metrics = notifier.get_metrics()
        assert metrics["total_devices"] == 1
        assert metrics["total_notifications"] == 1

    def test_get_devices_by_tenant(self):
        notifier = MobileNotifier()
        notifier.register_device("u1", "t1", "token1")
        notifier.register_device("u2", "t1", "token2")
        notifier.register_device("u3", "t2", "token3")

        devices = notifier.get_devices_by_tenant("t1")
        assert len(devices) == 2

    def test_quiet_hours_check(self):
        notifier = MobileNotifier()
        device = notifier.register_device("u1", "t1", "token123")
        device.quiet_hours_start = "22:00"
        device.quiet_hours_end = "08:00"

        # Test quiet hours logic
        is_quiet = notifier._is_quiet_hours(device)
        # Result depends on current time
        assert isinstance(is_quiet, bool)

    @pytest.mark.asyncio
    async def test_send_notification(self):
        notifier = MobileNotifier()
        device = notifier.register_device(
            user_id="u1",
            tenant_id="t1",
            device_token="token123",
            push_enabled=True
        )
        notification = notifier.create_notification("u1", "t1", "Test", "Body")

        # Mock push channel send
        with patch.object(notifier.push_channel, 'send', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = PushResult(
                notification_id="test",
                success=True
            )
            result = await notifier.send_notification(notification)

        assert "devices_notified" in result

    @pytest.mark.asyncio
    async def test_broadcast(self):
        notifier = MobileNotifier()
        notifier.register_device("u1", "t1", "token1")
        notifier.register_device("u2", "t1", "token2")
        notifier.register_device("u3", "t2", "token3")

        with patch.object(notifier.push_channel, 'send', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = PushResult(notification_id="test", success=True)
            result = await notifier.broadcast("t1", "Alert", "Test broadcast")

        assert result["total_devices"] == 2
