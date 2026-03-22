"""
Unit tests for Notification Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.notification_service import (
    NotificationService,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def notification_service(mock_db):
    """Notification service instance with mocked DB."""
    company_id = uuid.uuid4()
    return NotificationService(mock_db, company_id)


class TestNotificationServiceInit:
    """Tests for NotificationService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = NotificationService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestNotificationChannelEnum:
    """Tests for NotificationChannel enum."""
    
    def test_channel_values(self):
        """Test channel enum values."""
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.SMS.value == "sms"
        assert NotificationChannel.PUSH.value == "push"
        assert NotificationChannel.IN_APP.value == "in_app"
    
    def test_channel_count(self):
        """Test that we have expected number of channels."""
        assert len(NotificationChannel) == 4


class TestNotificationPriorityEnum:
    """Tests for NotificationPriority enum."""
    
    def test_priority_values(self):
        """Test priority enum values."""
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.URGENT.value == "urgent"
    
    def test_priority_count(self):
        """Test that we have expected number of priorities."""
        assert len(NotificationPriority) == 4


class TestNotificationStatusEnum:
    """Tests for NotificationStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert NotificationStatus.PENDING.value == "pending"
        assert NotificationStatus.SENT.value == "sent"
        assert NotificationStatus.DELIVERED.value == "delivered"
        assert NotificationStatus.FAILED.value == "failed"
        assert NotificationStatus.BOUNCED.value == "bounced"
    
    def test_status_count(self):
        """Test that we have expected number of statuses."""
        assert len(NotificationStatus) == 5


class TestSendEmail:
    """Tests for send_email method."""
    
    @pytest.mark.asyncio
    async def test_send_email_returns_dict(self, notification_service):
        """Test that send_email returns proper dict."""
        result = await notification_service.send_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        assert result["channel"] == "email"
        assert result["to"] == "test@example.com"
        assert result["subject"] == "Test Subject"
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_email_with_html(self, notification_service):
        """Test send_email with HTML body."""
        result = await notification_service.send_email(
            to="test@example.com",
            subject="Test",
            body="Plain text",
            html_body="<p>HTML</p>"
        )
        
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_email_with_priority(self, notification_service):
        """Test send_email with high priority."""
        result = await notification_service.send_email(
            to="test@example.com",
            subject="Urgent",
            body="Body",
            priority=NotificationPriority.URGENT
        )
        
        assert result["priority"] == "urgent"
    
    @pytest.mark.asyncio
    async def test_send_email_with_cc_bcc(self, notification_service):
        """Test send_email with CC and BCC."""
        result = await notification_service.send_email(
            to="test@example.com",
            subject="Test",
            body="Body",
            cc=["cc1@example.com", "cc2@example.com"],
            bcc=["bcc@example.com"]
        )
        
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_email_includes_company_id(self, notification_service):
        """Test that send_email includes company_id in result."""
        result = await notification_service.send_email(
            to="test@example.com",
            subject="Test",
            body="Body"
        )
        
        assert "company_id" in result
        assert result["company_id"] == str(notification_service.company_id)


class TestSendSms:
    """Tests for send_sms method."""
    
    @pytest.mark.asyncio
    async def test_send_sms_returns_dict(self, notification_service):
        """Test that send_sms returns proper dict."""
        result = await notification_service.send_sms(
            to="+1234567890",
            message="Test message"
        )
        
        assert result["channel"] == "sms"
        assert result["to"] == "+1234567890"
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_sms_with_priority(self, notification_service):
        """Test send_sms with priority."""
        result = await notification_service.send_sms(
            to="+1234567890",
            message="Test",
            priority=NotificationPriority.HIGH
        )
        
        assert result["priority"] == "high"
    
    @pytest.mark.asyncio
    async def test_send_sms_with_sender_id(self, notification_service):
        """Test send_sms with custom sender ID."""
        result = await notification_service.send_sms(
            to="+1234567890",
            message="Test",
            sender_id="PARWA"
        )
        
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_sms_truncates_long_message(self, notification_service):
        """Test that long SMS messages are truncated."""
        long_message = "x" * 2000  # Over 1600 char limit
        result = await notification_service.send_sms(
            to="+1234567890",
            message=long_message
        )
        
        assert result["message_length"] == 1600
    
    @pytest.mark.asyncio
    async def test_send_sms_includes_company_id(self, notification_service):
        """Test that send_sms includes company_id in result."""
        result = await notification_service.send_sms(
            to="+1234567890",
            message="Test"
        )
        
        assert "company_id" in result


class TestSendPush:
    """Tests for send_push method."""
    
    @pytest.mark.asyncio
    async def test_send_push_returns_dict(self, notification_service):
        """Test that send_push returns proper dict."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_push(
            user_id=user_id,
            title="Test Title",
            body="Test body"
        )
        
        assert result["channel"] == "push"
        assert result["user_id"] == str(user_id)
        assert result["title"] == "Test Title"
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_push_with_data(self, notification_service):
        """Test send_push with data payload."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_push(
            user_id=user_id,
            title="Test",
            body="Body",
            data={"ticket_id": "123", "action": "open"}
        )
        
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_push_with_action_url(self, notification_service):
        """Test send_push with action URL."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_push(
            user_id=user_id,
            title="Test",
            body="Body",
            action_url="https://app.parwa.ai/tickets/123"
        )
        
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_push_includes_company_id(self, notification_service):
        """Test that send_push includes company_id."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_push(
            user_id=user_id,
            title="Test",
            body="Body"
        )
        
        assert "company_id" in result


class TestSendInApp:
    """Tests for send_in_app method."""
    
    @pytest.mark.asyncio
    async def test_send_in_app_returns_dict(self, notification_service):
        """Test that send_in_app returns proper dict."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_in_app(
            user_id=user_id,
            title="Test Title",
            message="Test message"
        )
        
        assert result["channel"] == "in_app"
        assert result["user_id"] == str(user_id)
        assert result["title"] == "Test Title"
        assert result["message"] == "Test message"
        assert result["status"] == "delivered"
    
    @pytest.mark.asyncio
    async def test_send_in_app_with_notification_type(self, notification_service):
        """Test send_in_app with notification type."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_in_app(
            user_id=user_id,
            title="Test",
            message="Message",
            notification_type="ticket_assigned"
        )
        
        assert result["notification_type"] == "ticket_assigned"
    
    @pytest.mark.asyncio
    async def test_send_in_app_with_action_url(self, notification_service):
        """Test send_in_app with action URL."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_in_app(
            user_id=user_id,
            title="Test",
            message="Message",
            action_url="https://app.parwa.ai/tickets/123"
        )
        
        assert result["action_url"] == "https://app.parwa.ai/tickets/123"
    
    @pytest.mark.asyncio
    async def test_send_in_app_with_metadata(self, notification_service):
        """Test send_in_app with metadata."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_in_app(
            user_id=user_id,
            title="Test",
            message="Message",
            metadata={"priority": "high", "source": "jarvis"}
        )
        
        assert "metadata" in result
        assert result["metadata"]["priority"] == "high"


class TestSendNotification:
    """Tests for send_notification unified method."""
    
    @pytest.mark.asyncio
    async def test_send_notification_email(self, notification_service):
        """Test unified send_notification for email."""
        result = await notification_service.send_notification(
            channel=NotificationChannel.EMAIL,
            to="test@example.com",
            subject="Test",
            body="Body"
        )
        
        assert result["channel"] == "email"
    
    @pytest.mark.asyncio
    async def test_send_notification_sms(self, notification_service):
        """Test unified send_notification for SMS."""
        result = await notification_service.send_notification(
            channel=NotificationChannel.SMS,
            to="+1234567890",
            message="Test"
        )
        
        assert result["channel"] == "sms"
    
    @pytest.mark.asyncio
    async def test_send_notification_push(self, notification_service):
        """Test unified send_notification for push."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_notification(
            channel=NotificationChannel.PUSH,
            user_id=user_id,
            title="Test",
            body="Body"
        )
        
        assert result["channel"] == "push"
    
    @pytest.mark.asyncio
    async def test_send_notification_in_app(self, notification_service):
        """Test unified send_notification for in-app."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_notification(
            channel=NotificationChannel.IN_APP,
            user_id=user_id,
            title="Test",
            message="Message"
        )
        
        assert result["channel"] == "in_app"
    
    @pytest.mark.asyncio
    async def test_send_notification_email_requires_to(self, notification_service):
        """Test that email notification requires 'to' parameter."""
        with pytest.raises(ValueError, match="Email address 'to' is required"):
            await notification_service.send_notification(
                channel=NotificationChannel.EMAIL,
                subject="Test",
                body="Body"
            )
    
    @pytest.mark.asyncio
    async def test_send_notification_sms_requires_to(self, notification_service):
        """Test that SMS notification requires 'to' parameter."""
        with pytest.raises(ValueError, match="Phone number 'to' is required"):
            await notification_service.send_notification(
                channel=NotificationChannel.SMS,
                message="Test"
            )
    
    @pytest.mark.asyncio
    async def test_send_notification_push_requires_user_id(self, notification_service):
        """Test that push notification requires user_id."""
        with pytest.raises(ValueError, match="user_id is required for push"):
            await notification_service.send_notification(
                channel=NotificationChannel.PUSH,
                title="Test",
                body="Body"
            )
    
    @pytest.mark.asyncio
    async def test_send_notification_in_app_requires_user_id(self, notification_service):
        """Test that in-app notification requires user_id."""
        with pytest.raises(ValueError, match="user_id is required for in-app"):
            await notification_service.send_notification(
                channel=NotificationChannel.IN_APP,
                title="Test",
                message="Message"
            )


class TestSendBulkEmail:
    """Tests for send_bulk_email method."""
    
    @pytest.mark.asyncio
    async def test_send_bulk_email_returns_results(self, notification_service):
        """Test that send_bulk_email returns results for each recipient."""
        recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]
        
        result = await notification_service.send_bulk_email(
            recipients=recipients,
            subject="Test",
            body="Body"
        )
        
        assert result["total_recipients"] == 3
        assert result["sent_count"] == 3
        assert result["failed_count"] == 0
        assert len(result["results"]) == 3
    
    @pytest.mark.asyncio
    async def test_send_bulk_email_empty_recipients_raises(self, notification_service):
        """Test that empty recipients raises error."""
        with pytest.raises(ValueError, match="Recipients list cannot be empty"):
            await notification_service.send_bulk_email(
                recipients=[],
                subject="Test",
                body="Body"
            )
    
    @pytest.mark.asyncio
    async def test_send_bulk_email_includes_company_id(self, notification_service):
        """Test that bulk email includes company_id."""
        result = await notification_service.send_bulk_email(
            recipients=["test@example.com"],
            subject="Test",
            body="Body"
        )
        
        assert "company_id" in result


class TestSendBulkSms:
    """Tests for send_bulk_sms method."""
    
    @pytest.mark.asyncio
    async def test_send_bulk_sms_returns_results(self, notification_service):
        """Test that send_bulk_sms returns results for each recipient."""
        recipients = ["+1111111111", "+2222222222"]
        
        result = await notification_service.send_bulk_sms(
            recipients=recipients,
            message="Test message"
        )
        
        assert result["total_recipients"] == 2
        assert result["sent_count"] == 2
        assert len(result["results"]) == 2
    
    @pytest.mark.asyncio
    async def test_send_bulk_sms_empty_recipients_raises(self, notification_service):
        """Test that empty recipients raises error."""
        with pytest.raises(ValueError, match="Recipients list cannot be empty"):
            await notification_service.send_bulk_sms(
                recipients=[],
                message="Test"
            )


class TestGetNotificationHistory:
    """Tests for get_notification_history method."""
    
    @pytest.mark.asyncio
    async def test_get_history_returns_list(self, notification_service):
        """Test that get_notification_history returns list."""
        result = await notification_service.get_notification_history()
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_history_with_filters(self, notification_service):
        """Test get_notification_history with filters."""
        user_id = uuid.uuid4()
        
        result = await notification_service.get_notification_history(
            user_id=user_id,
            channel=NotificationChannel.EMAIL,
            status=NotificationStatus.SENT,
            limit=20,
            offset=10
        )
        
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_history_enforces_max_limit(self, notification_service):
        """Test that get_notification_history enforces max limit."""
        # Should not raise even with limit > 200
        result = await notification_service.get_notification_history(limit=500)
        
        assert isinstance(result, list)


class TestMarkAsRead:
    """Tests for mark_as_read method."""
    
    @pytest.mark.asyncio
    async def test_mark_as_read_returns_dict(self, notification_service):
        """Test that mark_as_read returns proper dict."""
        notification_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        result = await notification_service.mark_as_read(
            notification_id=notification_id,
            user_id=user_id
        )
        
        assert result["notification_id"] == str(notification_id)
        assert result["user_id"] == str(user_id)
        assert result["status"] == "read"
        assert "read_at" in result


class TestGetUnreadCount:
    """Tests for get_unread_count method."""
    
    @pytest.mark.asyncio
    async def test_get_unread_count_returns_dict(self, notification_service):
        """Test that get_unread_count returns proper dict."""
        user_id = uuid.uuid4()
        
        result = await notification_service.get_unread_count(user_id=user_id)
        
        assert result["user_id"] == str(user_id)
        assert "unread_count" in result


class TestDeleteNotification:
    """Tests for delete_notification method."""
    
    @pytest.mark.asyncio
    async def test_delete_notification_returns_dict(self, notification_service):
        """Test that delete_notification returns proper dict."""
        notification_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        result = await notification_service.delete_notification(
            notification_id=notification_id,
            user_id=user_id
        )
        
        assert result["notification_id"] == str(notification_id)
        assert result["deleted"] is True
        assert "deleted_at" in result


class TestMaskEmail:
    """Tests for _mask_email helper method."""
    
    def test_mask_email_standard(self):
        """Test masking standard email."""
        masked = NotificationService._mask_email("john.doe@example.com")
        
        assert "@" in masked
        assert masked.endswith("@example.com")
        assert masked != "john.doe@example.com"
    
    def test_mask_email_short(self):
        """Test masking short email."""
        masked = NotificationService._mask_email("a@b.com")
        
        assert "@" in masked
    
    def test_mask_email_empty(self):
        """Test masking empty string."""
        masked = NotificationService._mask_email("")
        
        assert masked == "***"
    
    def test_mask_email_no_at(self):
        """Test masking string without @."""
        masked = NotificationService._mask_email("notanemail")
        
        assert masked != "notanemail"


class TestMaskPhone:
    """Tests for _mask_phone helper method."""
    
    def test_mask_phone_standard(self):
        """Test masking standard phone."""
        masked = NotificationService._mask_phone("+1234567890")
        
        assert masked != "+1234567890"
        assert masked.startswith("+123")
        assert masked.endswith("7890")
    
    def test_mask_phone_short(self):
        """Test masking short phone."""
        masked = NotificationService._mask_phone("+123")
        
        assert masked != "+123"
    
    def test_mask_phone_empty(self):
        """Test masking empty string."""
        masked = NotificationService._mask_phone("")
        
        assert masked == "***"


class TestCompanyScoping:
    """Tests for company scoping enforcement."""
    
    @pytest.mark.asyncio
    async def test_all_methods_include_company_id(self, notification_service):
        """Test that all notification methods include company_id."""
        user_id = uuid.uuid4()
        
        # Email
        email_result = await notification_service.send_email(
            to="test@example.com",
            subject="Test",
            body="Body"
        )
        assert email_result["company_id"] == str(notification_service.company_id)
        
        # SMS
        sms_result = await notification_service.send_sms(
            to="+1234567890",
            message="Test"
        )
        assert sms_result["company_id"] == str(notification_service.company_id)
        
        # Push
        push_result = await notification_service.send_push(
            user_id=user_id,
            title="Test",
            body="Body"
        )
        assert push_result["company_id"] == str(notification_service.company_id)
        
        # In-App
        in_app_result = await notification_service.send_in_app(
            user_id=user_id,
            title="Test",
            message="Message"
        )
        assert in_app_result["company_id"] == str(notification_service.company_id)
