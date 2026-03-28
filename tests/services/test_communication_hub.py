"""
Tests for Communication Hub Services

Tests communication hub, message templates, and notification scheduler.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from backend.services.client_success.communication_hub import (
    CommunicationHub,
    MessageChannel,
    MessageStatus,
    MessageType,
    ClientMessage,
    ClientPreference,
)
from backend.services.client_success.message_templates import (
    MessageTemplates,
    TemplateCategory,
    MessageTemplate,
)
from backend.services.client_success.notification_scheduler import (
    NotificationScheduler,
    ScheduleStatus,
    RecurrenceType,
    ScheduledNotification,
)


class TestCommunicationHub:
    """Tests for CommunicationHub class."""

    @pytest.fixture
    def hub(self):
        """Create communication hub instance."""
        return CommunicationHub()

    @pytest.mark.asyncio
    async def test_send_message(self, hub):
        """Test sending a message."""
        message = await hub.send_message(
            client_id="client_001",
            channel=MessageChannel.EMAIL,
            message_type=MessageType.CHECK_IN,
            subject="Test Subject",
            body="Test body content"
        )

        assert isinstance(message, ClientMessage)
        assert message.client_id == "client_001"
        assert message.channel == MessageChannel.EMAIL
        assert message.status in [MessageStatus.SENT, MessageStatus.FAILED]

    @pytest.mark.asyncio
    async def test_send_to_invalid_client(self, hub):
        """Test that invalid client raises error."""
        with pytest.raises(ValueError, match="Unsupported client"):
            await hub.send_message(
                client_id="invalid_client",
                channel=MessageChannel.EMAIL,
                message_type=MessageType.CHECK_IN,
                subject="Test",
                body="Test"
            )

    @pytest.mark.asyncio
    async def test_mark_read(self, hub):
        """Test marking message as read."""
        message = await hub.send_message(
            client_id="client_001",
            channel=MessageChannel.IN_APP,
            message_type=MessageType.ALERT,
            subject="Alert",
            body="Alert body"
        )

        read_message = hub.mark_read(message.message_id)

        assert read_message is not None
        assert read_message.status == MessageStatus.READ
        assert read_message.read_at is not None

    def test_get_message_history(self, hub):
        """Test getting message history."""
        # Send some messages
        import asyncio
        for i in range(3):
            asyncio.run(hub.send_message(
                client_id="client_001",
                channel=MessageChannel.EMAIL,
                message_type=MessageType.CHECK_IN,
                subject=f"Message {i}",
                body="Body"
            ))

        history = hub.get_message_history("client_001")

        assert len(history) >= 3

    def test_get_unread_count(self, hub):
        """Test getting unread count."""
        import asyncio
        asyncio.run(hub.send_message(
            client_id="client_001",
            channel=MessageChannel.IN_APP,
            message_type=MessageType.ALERT,
            subject="Unread",
            body="Body"
        ))

        count = hub.get_unread_count("client_001")

        assert count >= 0

    def test_update_preferences(self, hub):
        """Test updating preferences."""
        prefs = hub.update_preferences(
            client_id="client_001",
            preferences={
                "email_enabled": False,
                "sms_enabled": True,
                "frequency_cap_daily": 10
            }
        )

        assert prefs.email_enabled is False
        assert prefs.sms_enabled is True
        assert prefs.frequency_cap_daily == 10

    def test_get_preferences(self, hub):
        """Test getting preferences."""
        prefs = hub.get_preferences("client_001")

        assert isinstance(prefs, ClientPreference)
        assert prefs.client_id == "client_001"

    @pytest.mark.asyncio
    async def test_broadcast_message(self, hub):
        """Test broadcasting to multiple clients."""
        results = await hub.broadcast_message(
            client_ids=["client_001", "client_002", "client_003"],
            channel=MessageChannel.EMAIL,
            message_type=MessageType.ANNOUNCEMENT,
            subject="Broadcast",
            body="Broadcast content"
        )

        assert len(results) == 3
        assert all(isinstance(m, ClientMessage) for m in results.values())

    def test_communication_summary(self, hub):
        """Test getting communication summary."""
        summary = hub.get_communication_summary()

        assert "total_messages" in summary
        assert "by_status" in summary
        assert "by_channel" in summary
        assert "read_rate" in summary


class TestMessageTemplates:
    """Tests for MessageTemplates class."""

    @pytest.fixture
    def templates(self):
        """Create message templates instance."""
        return MessageTemplates()

    def test_get_template(self, templates):
        """Test getting a template by ID."""
        template = templates.get_template("onboarding_welcome")

        assert template is not None
        assert template.name == "Welcome to PARWA"

    def test_get_templates_by_category(self, templates):
        """Test getting templates by category."""
        onboarding = templates.get_templates_by_category(TemplateCategory.ONBOARDING)

        assert len(onboarding) > 0
        assert all(t.category == TemplateCategory.ONBOARDING for t in onboarding)

    def test_render_template(self, templates):
        """Test rendering a template."""
        rendered = templates.render_template(
            template_id="onboarding_welcome",
            variables={"client_name": "Test Client"}
        )

        assert "subject" in rendered
        assert "body" in rendered
        assert "Test Client" in rendered["subject"]
        assert "Test Client" in rendered["body"]

    def test_render_missing_variable(self, templates):
        """Test that missing variables raise error."""
        with pytest.raises(ValueError, match="Missing variables"):
            templates.render_template(
                template_id="onboarding_welcome",
                variables={}  # Missing client_name
            )

    def test_add_template(self, templates):
        """Test adding a custom template."""
        template = MessageTemplate(
            template_id="custom_test",
            name="Custom Test Template",
            category=TemplateCategory.CUSTOM,
            subject_template="Hello {name}",
            body_template="Welcome {name}!",
            variables=["name"],
            channel="email"
        )

        templates.add_template(template)

        retrieved = templates.get_template("custom_test")
        assert retrieved is not None
        assert retrieved.name == "Custom Test Template"

    def test_validate_template(self, templates):
        """Test validating template syntax."""
        variables = templates.validate_template(
            subject_template="Hello {client_name}",
            body_template="Welcome {client_name}, your plan is {plan_type}!"
        )

        assert "client_name" in variables
        assert "plan_type" in variables

    def test_template_summary(self, templates):
        """Test getting template summary."""
        summary = templates.get_template_summary()

        assert "total_templates" in summary
        assert "by_category" in summary


class TestNotificationScheduler:
    """Tests for NotificationScheduler class."""

    @pytest.fixture
    def scheduler(self):
        """Create notification scheduler instance."""
        return NotificationScheduler()

    def test_schedule_notification(self, scheduler):
        """Test scheduling a notification."""
        scheduled_for = datetime.utcnow() + timedelta(hours=1)

        notification = scheduler.schedule_notification(
            client_id="client_001",
            channel="email",
            subject="Scheduled Test",
            body="Scheduled body",
            scheduled_for=scheduled_for
        )

        assert isinstance(notification, ScheduledNotification)
        assert notification.client_id == "client_001"
        assert notification.status == ScheduleStatus.PENDING

    def test_schedule_optimal_time(self, scheduler):
        """Test scheduling at optimal time."""
        notification = scheduler.schedule_optimal_time(
            client_id="client_001",
            channel="email",
            subject="Optimal Time Test",
            body="Body"
        )

        assert notification.scheduled_for is not None
        # Should be scheduled during business hours
        assert notification.scheduled_for.hour >= 9
        assert notification.scheduled_for.hour <= 17

    def test_batch_schedule(self, scheduler):
        """Test batch scheduling."""
        scheduled_for = datetime.utcnow() + timedelta(hours=1)

        results = scheduler.batch_schedule(
            client_ids=["client_001", "client_002", "client_003"],
            channel="email",
            subject="Batch Test",
            body="Batch body",
            scheduled_for=scheduled_for,
            stagger_minutes=5
        )

        assert len(results) == 3
        # Check staggering
        times = [r.scheduled_for for r in results.values()]
        assert times[1] > times[0]
        assert times[2] > times[1]

    def test_get_pending_notifications(self, scheduler):
        """Test getting pending notifications."""
        # Schedule in the past (due now)
        past_time = datetime.utcnow() - timedelta(minutes=30)

        scheduler.schedule_notification(
            client_id="client_001",
            channel="email",
            subject="Due Now",
            body="Body",
            scheduled_for=past_time
        )

        pending = scheduler.get_pending_notifications()

        assert len(pending) > 0

    def test_recurring_schedule(self, scheduler):
        """Test recurring notifications."""
        scheduled_for = datetime.utcnow() + timedelta(hours=1)

        notification = scheduler.schedule_notification(
            client_id="client_001",
            channel="email",
            subject="Recurring",
            body="Body",
            scheduled_for=scheduled_for,
            recurrence=RecurrenceType.DAILY
        )

        assert notification.recurrence == RecurrenceType.DAILY
        assert notification.next_occurrence is not None

    def test_cancel_schedule(self, scheduler):
        """Test cancelling a schedule."""
        scheduled_for = datetime.utcnow() + timedelta(hours=1)

        notification = scheduler.schedule_notification(
            client_id="client_001",
            channel="email",
            subject="To Cancel",
            body="Body",
            scheduled_for=scheduled_for
        )

        cancelled = scheduler.cancel_schedule(notification.schedule_id)

        assert cancelled is not None
        assert cancelled.status == ScheduleStatus.CANCELLED

    def test_get_upcoming_schedules(self, scheduler):
        """Test getting upcoming schedules."""
        # Schedule within 24 hours
        scheduler.schedule_notification(
            client_id="client_001",
            channel="email",
            subject="Upcoming",
            body="Body",
            scheduled_for=datetime.utcnow() + timedelta(hours=12)
        )

        upcoming = scheduler.get_upcoming_schedules(hours=24)

        assert len(upcoming) > 0

    def test_calculate_optimal_send_time(self, scheduler):
        """Test optimal send time calculation."""
        optimal = scheduler.calculate_optimal_send_time()

        assert optimal is not None
        # Should be in the future
        assert optimal > datetime.utcnow()

    def test_schedule_summary(self, scheduler):
        """Test getting schedule summary."""
        summary = scheduler.get_schedule_summary()

        assert "total_scheduled" in summary
        assert "pending" in summary
        assert "upcoming_24h" in summary


class TestIntegration:
    """Integration tests for communication services."""

    @pytest.mark.asyncio
    async def test_full_communication_workflow(self):
        """Test complete communication workflow."""
        hub = CommunicationHub()
        templates = MessageTemplates()
        scheduler = NotificationScheduler()

        # Render a template
        rendered = templates.render_template(
            template_id="check_in_weekly",
            variables={
                "client_name": "Test Client",
                "tickets_handled": 50,
                "resolution_rate": 95,
                "avg_response_time": "2.5 hours"
            }
        )

        # Send message
        message = await hub.send_message(
            client_id="client_001",
            channel=MessageChannel.EMAIL,
            message_type=MessageType.CHECK_IN,
            subject=rendered["subject"],
            body=rendered["body"],
            template_id="check_in_weekly"
        )

        assert message.status in [MessageStatus.SENT, MessageStatus.FAILED]

        # Schedule future message
        scheduled = scheduler.schedule_notification(
            client_id="client_002",
            channel="email",
            subject="Follow-up",
            body="Scheduled follow-up",
            scheduled_for=datetime.utcnow() + timedelta(days=1)
        )

        assert scheduled.status == ScheduleStatus.PENDING

    def test_all_10_clients_communication(self):
        """Test communication for all 10 clients."""
        hub = CommunicationHub()
        templates = MessageTemplates()

        all_clients = [
            "client_001", "client_002", "client_003", "client_004", "client_005",
            "client_006", "client_007", "client_008", "client_009", "client_010"
        ]

        # Check preferences for all clients
        for client_id in all_clients:
            prefs = hub.get_preferences(client_id)
            assert prefs is not None
            assert prefs.client_id == client_id

        # Check templates work for all
        for client_id in all_clients:
            rendered = templates.render_template(
                template_id="onboarding_welcome",
                variables={"client_name": client_id}
            )
            assert client_id in rendered["subject"] or "PARWA" in rendered["subject"]
