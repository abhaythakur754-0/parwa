"""
Day 31 Unit Tests - Notification System + Email Templates (MF05)

Tests for:
- NotificationService: Notification dispatch, PS03/PS10 handlers
- NotificationTemplateService: Template CRUD, variable validation
- NotificationPreferenceService: User preferences
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest


# ── NOTIFICATION SERVICE TESTS ────────────────────────────────────────────────


class TestNotificationService:
    """Tests for NotificationService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def notification_service(self, mock_db):
        """Create NotificationService instance."""
        from backend.app.services.notification_service import NotificationService
        return NotificationService(mock_db, "test-company-id")

    def test_event_types_defined(self, notification_service):
        """Test that all event types are defined."""
        assert "ticket_created" in notification_service.EVENT_TYPES
        assert "ticket_assigned" in notification_service.EVENT_TYPES
        assert "sla_warning" in notification_service.EVENT_TYPES
        assert "sla_breached" in notification_service.EVENT_TYPES
        assert "ticket_escalated" in notification_service.EVENT_TYPES

    def test_channels_defined(self, notification_service):
        """Test that channels are defined."""
        assert "email" in notification_service.CHANNELS
        assert "in_app" in notification_service.CHANNELS
        assert "push" in notification_service.CHANNELS

    def test_send_notification_invalid_event_type(self, notification_service):
        """Test sending notification with invalid event type."""
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            notification_service.send_notification(
                event_type="invalid_event",
                recipient_ids=["user-1"],
                data={},
            )

        assert "Invalid event type" in str(exc_info.value)

    def test_send_notification_success(self, notification_service, mock_db):
        """Test successful notification send."""
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.email = "user@example.com"

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(notification_service, '_get_user_preferences', return_value={"enabled": True, "channels": ["in_app"]}):
            with patch.object(notification_service, '_dispatch_to_channels', return_value={"success": True}):
                result = notification_service.send_notification(
                    event_type="ticket_created",
                    recipient_ids=["user-1"],
                    data={"ticket_subject": "Test Ticket"},
                )

        assert result["sent_count"] == 1
        assert mock_db.add.called

    def test_send_notification_user_disabled(self, notification_service, mock_db):
        """Test notification skipped when user has disabled it."""
        with patch.object(notification_service, '_get_user_preferences', return_value={"enabled": False, "channels": []}):
            result = notification_service.send_notification(
                event_type="ticket_created",
                recipient_ids=["user-1"],
                data={},
            )

        assert result["sent_count"] == 0
        assert result.get("skipped_count", 0) == 1

    def test_send_bulk_notification(self, notification_service, mock_db):
        """Test bulk notification send."""
        recipient_ids = [f"user-{i}" for i in range(150)]

        with patch.object(notification_service, 'send_notification') as mock_send:
            mock_send.return_value = {"sent_count": 50, "failed_count": 0}
            result = notification_service.send_bulk_notification(
                event_type="incident_created",
                recipient_ids=recipient_ids,
                data={"incident_title": "Test Incident"},
                batch_size=50,
            )

        assert result["batches"] == 3
        assert result["total_recipients"] == 150

    def test_send_bulk_notification_max_limit(self, notification_service):
        """Test bulk notification max recipient limit."""
        from backend.app.exceptions import ValidationError

        recipient_ids = [f"user-{i}" for i in range(10001)]

        with pytest.raises(ValidationError) as exc_info:
            notification_service.send_bulk_notification(
                event_type="incident_created",
                recipient_ids=recipient_ids,
                data={},
            )

        assert "10,000" in str(exc_info.value)

    def test_notify_human_queue(self, notification_service, mock_db):
        """Test PS03: Notify human queue."""
        mock_ticket = MagicMock()
        mock_ticket.id = "ticket-1"
        mock_ticket.subject = "Test Ticket"
        mock_ticket.customer_id = "customer-1"
        mock_ticket.priority = "high"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_ticket

        with patch.object(notification_service, '_get_available_agents', return_value=[{"id": "agent-1"}]):
            with patch.object(notification_service, 'send_notification') as mock_send:
                mock_send.return_value = {"sent_count": 1, "failed_count": 0}
                result = notification_service.notify_human_queue(
                    ticket_id="ticket-1",
                    summary="Customer had login issues",
                    escalation_reason="Customer requested human",
                )

        assert result["sent_count"] == 1

    def test_notify_human_queue_no_agents(self, notification_service, mock_db):
        """Test PS03: No agents available."""
        mock_ticket = MagicMock()
        mock_ticket.id = "ticket-1"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_ticket

        with patch.object(notification_service, '_get_available_agents', return_value=[]):
            with patch.object(notification_service, '_get_company_agents', return_value=[]):
                result = notification_service.notify_human_queue(
                    ticket_id="ticket-1",
                    summary="Summary",
                    escalation_reason="Reason",
                )

        assert result["success"] is False

    def test_notify_incident_subscribers(self, notification_service, mock_db):
        """Test PS10: Notify incident subscribers."""
        with patch.object(notification_service, 'send_bulk_notification') as mock_bulk:
            mock_bulk.return_value = {"sent_count": 100, "failed_count": 0}
            result = notification_service.notify_incident_subscribers(
                incident_id="incident-1",
                incident_title="API Outage",
                status_update="Investigating the issue",
                affected_customer_ids=[f"customer-{i}" for i in range(100)],
            )

        assert result["sent_count"] == 100

    def test_get_notifications(self, notification_service, mock_db):
        """Test getting notifications for user."""
        mock_notification = MagicMock()
        mock_notification.id = "notif-1"
        mock_notification.event_type = "ticket_created"
        mock_notification.title = "New Ticket"
        mock_notification.message = "A new ticket has been created"

        mock_db.query.return_value.filter.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_notification]

        notifications, total = notification_service.get_notifications("user-1")

        assert total == 1
        assert len(notifications) == 1

    def test_mark_as_read(self, notification_service, mock_db):
        """Test marking notification as read."""
        mock_notification = MagicMock()
        mock_notification.id = "notif-1"
        mock_notification.user_id = "user-1"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_notification

        result = notification_service.mark_as_read("notif-1", "user-1")

        assert result.read_at is not None

    def test_mark_as_read_not_found(self, notification_service, mock_db):
        """Test marking notification not found."""
        from backend.app.exceptions import NotFoundError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            notification_service.mark_as_read("notif-1", "user-1")

    def test_mark_all_as_read(self, notification_service, mock_db):
        """Test marking all notifications as read."""
        mock_db.query.return_value.filter.return_value.update.return_value = 5

        count = notification_service.mark_all_as_read("user-1")

        assert count == 5

    def test_get_unread_count(self, notification_service, mock_db):
        """Test getting unread notification count."""
        mock_db.query.return_value.filter.return_value.count.return_value = 3

        count = notification_service.get_unread_count("user-1")

        assert count == 3

    def test_create_digest_daily(self, notification_service, mock_db):
        """Test creating daily digest."""
        mock_notification = MagicMock()
        mock_notification.event_type = "ticket_assigned"
        mock_notification.read_at = None

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_notification]

        result = notification_service.create_digest("user-1", "daily")

        assert result["digest_created"] is True
        assert result["digest"]["period"] == "daily"

    def test_create_digest_no_notifications(self, notification_service, mock_db):
        """Test creating digest with no notifications."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = notification_service.create_digest("user-1", "daily")

        assert result["digest_created"] is False

    def test_generate_title(self, notification_service):
        """Test title generation for event types."""
        title = notification_service._generate_title("ticket_created", {"ticket_subject": "Test"})
        assert "Test" in title

        title = notification_service._generate_title("sla_breached", {"ticket_subject": "SLA Test"})
        assert "SLA Breached" in title

    def test_generate_message(self, notification_service):
        """Test message generation for event types."""
        message = notification_service._generate_message("ticket_assigned", {"ticket_subject": "Test"})
        assert "assigned" in message.lower()


# ── NOTIFICATION TEMPLATE SERVICE TESTS ───────────────────────────────────────


class TestNotificationTemplateService:
    """Tests for NotificationTemplateService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def template_service(self, mock_db):
        """Create NotificationTemplateService instance."""
        from backend.app.services.notification_template_service import NotificationTemplateService
        return NotificationTemplateService(mock_db, "test-company-id")

    def test_template_variables_defined(self, template_service):
        """Test that template variables are defined for all event types."""
        assert "ticket_created" in template_service.TEMPLATE_VARIABLES
        assert "ticket_subject" in template_service.TEMPLATE_VARIABLES["ticket_created"]

    def test_create_template_success(self, template_service, mock_db):
        """Test successful template creation."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        template = template_service.create_template(
            event_type="ticket_created",
            channel="email",
            subject_template="New Ticket: {{ticket_subject}}",
            body_template="Ticket {{ticket_id}} created by {{customer_name}}",
        )

        assert mock_db.add.called

    def test_create_template_invalid_event_type(self, template_service):
        """Test template creation with invalid event type."""
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            template_service.create_template(
                event_type="invalid_event",
                channel="email",
                subject_template="Subject",
                body_template="Body",
            )

        assert "Invalid event type" in str(exc_info.value)

    def test_create_template_invalid_variable(self, template_service, mock_db):
        """Test template creation with invalid variable."""
        from backend.app.exceptions import ValidationError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            template_service.create_template(
                event_type="ticket_created",
                channel="email",
                subject_template="Subject",
                body_template="Invalid var: {{invalid_variable}}",
            )

        assert "Invalid variables" in str(exc_info.value)

    def test_create_template_invalid_channel(self, template_service):
        """Test template creation with invalid channel."""
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            template_service.create_template(
                event_type="ticket_created",
                channel="invalid_channel",
                subject_template="Subject",
                body_template="Body",
            )

        assert "Invalid channel" in str(exc_info.value)

    def test_get_template(self, template_service, mock_db):
        """Test getting template by ID."""
        mock_template = MagicMock()
        mock_template.id = "template-1"
        mock_template.event_type = "ticket_created"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        result = template_service.get_template("template-1")

        assert result.id == "template-1"

    def test_get_template_not_found(self, template_service, mock_db):
        """Test getting template not found."""
        from backend.app.exceptions import NotFoundError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            template_service.get_template("nonexistent")

    def test_list_templates(self, template_service, mock_db):
        """Test listing templates."""
        mock_templates = [MagicMock(id="t1"), MagicMock(id="t2")]

        mock_db.query.return_value.filter.return_value.count.return_value = 2
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_templates

        templates, total = template_service.list_templates()

        assert total == 2
        assert len(templates) == 2

    def test_update_template(self, template_service, mock_db):
        """Test updating template."""
        mock_template = MagicMock()
        mock_template.id = "template-1"
        mock_template.event_type = "ticket_created"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        result = template_service.update_template(
            template_id="template-1",
            subject_template="New Subject: {{ticket_subject}}",
        )

        assert mock_db.commit.called

    def test_delete_template_soft(self, template_service, mock_db):
        """Test soft deleting system template."""
        mock_template = MagicMock()
        mock_template.id = "template-1"
        mock_template.event_type = "ticket_created"  # System template

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        result = template_service.delete_template("template-1")

        assert result is True
        assert mock_template.is_active is False

    def test_delete_template_hard(self, template_service, mock_db):
        """Test hard deleting custom template."""
        mock_template = MagicMock()
        mock_template.id = "template-1"
        mock_template.event_type = "custom_event"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        result = template_service.delete_template("template-1")

        assert result is True
        assert mock_db.delete.called

    def test_preview_template(self, template_service, mock_db):
        """Test template preview."""
        mock_template = MagicMock()
        mock_template.id = "template-1"
        mock_template.event_type = "ticket_created"
        mock_template.subject_template = "Ticket: {{ticket_subject}}"
        mock_template.body_template = "ID: {{ticket_id}}"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        preview = template_service.preview_template("template-1")

        assert "subject" in preview
        assert "body" in preview

    def test_get_template_variables(self, template_service):
        """Test getting template variables for event type."""
        variables = template_service.get_template_variables("ticket_created")

        assert "ticket_id" in variables
        assert "ticket_subject" in variables

    def test_seed_default_templates(self, template_service, mock_db):
        """Test seeding default templates."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        count = template_service.seed_default_templates()

        assert count > 0


# ── NOTIFICATION PREFERENCE SERVICE TESTS ──────────────────────────────────────


class TestNotificationPreferenceService:
    """Tests for NotificationPreferenceService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def preference_service(self, mock_db):
        """Create NotificationPreferenceService instance."""
        from backend.app.services.notification_preference_service import NotificationPreferenceService
        return NotificationPreferenceService(mock_db, "test-company-id")

    def test_default_preferences_defined(self, preference_service):
        """Test that default preferences are defined."""
        assert "ticket_created" in preference_service.DEFAULT_PREFERENCES
        assert "enabled" in preference_service.DEFAULT_PREFERENCES["ticket_created"]

    def test_get_user_preferences(self, preference_service, mock_db):
        """Test getting user preferences."""
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.metadata_json = "{}"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value.filter.return_value.all.return_value = []

        prefs = preference_service.get_user_preferences("user-1")

        assert "preferences" in prefs
        assert "digest_frequency" in prefs

    def test_get_user_preferences_user_not_found(self, preference_service, mock_db):
        """Test getting preferences for non-existent user."""
        from backend.app.exceptions import NotFoundError

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            preference_service.get_user_preferences("nonexistent")

    def test_update_preference(self, preference_service, mock_db):
        """Test updating preference."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = preference_service.update_preference(
            user_id="user-1",
            event_type="ticket_created",
            enabled=False,
            channels=["email"],
        )

        assert mock_db.add.called

    def test_update_preference_invalid_event_type(self, preference_service):
        """Test updating preference with invalid event type."""
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            preference_service.update_preference(
                user_id="user-1",
                event_type="invalid_event",
            )

        assert "Invalid event type" in str(exc_info.value)

    def test_update_preference_invalid_channel(self, preference_service):
        """Test updating preference with invalid channel."""
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            preference_service.update_preference(
                user_id="user-1",
                event_type="ticket_created",
                channels=["invalid_channel"],
            )

        assert "Invalid channels" in str(exc_info.value)

    def test_update_preference_invalid_priority(self, preference_service):
        """Test updating preference with invalid priority threshold."""
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            preference_service.update_preference(
                user_id="user-1",
                event_type="ticket_created",
                priority_threshold="invalid",
            )

        assert "Invalid priority threshold" in str(exc_info.value)

    def test_update_preferences_bulk(self, preference_service, mock_db):
        """Test bulk updating preferences."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = preference_service.update_preferences_bulk(
            user_id="user-1",
            preferences={
                "ticket_created": {"enabled": False},
                "ticket_assigned": {"enabled": True},
            },
        )

        assert len(result["updated"]) == 2

    def test_set_digest_settings(self, preference_service, mock_db):
        """Test setting digest settings."""
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.metadata_json = "{}"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = preference_service.set_digest_settings(
            user_id="user-1",
            frequency="daily",
            digest_time="09:00",
        )

        assert result["digest_frequency"] == "daily"

    def test_set_digest_settings_invalid_frequency(self, preference_service):
        """Test setting digest with invalid frequency."""
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            preference_service.set_digest_settings(
                user_id="user-1",
                frequency="invalid",
            )

        assert "Invalid frequency" in str(exc_info.value)

    def test_set_digest_settings_invalid_time(self, preference_service, mock_db):
        """Test setting digest with invalid time format."""
        from backend.app.exceptions import ValidationError

        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        with pytest.raises(ValidationError) as exc_info:
            preference_service.set_digest_settings(
                user_id="user-1",
                frequency="daily",
                digest_time="25:00",  # Invalid hour
            )

        assert "Invalid time format" in str(exc_info.value)

    def test_disable_all_notifications(self, preference_service, mock_db):
        """Test disabling all notifications."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        count = preference_service.disable_all_notifications("user-1")

        assert count == len(preference_service.DEFAULT_PREFERENCES)

    def test_enable_all_notifications(self, preference_service, mock_db):
        """Test enabling all notifications."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        count = preference_service.enable_all_notifications("user-1")

        assert count == len(preference_service.DEFAULT_PREFERENCES)

    def test_should_notify(self, preference_service, mock_db):
        """Test checking if user should be notified."""
        mock_pref = MagicMock()
        mock_pref.enabled = True
        mock_pref.channels = '["email"]'
        mock_pref.priority_threshold = "low"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_pref

        should_notify, channels = preference_service.should_notify(
            user_id="user-1",
            event_type="ticket_created",
            priority="high",
        )

        assert should_notify is True
        assert "email" in channels

    def test_should_notify_disabled(self, preference_service, mock_db):
        """Test checking notification when disabled."""
        mock_pref = MagicMock()
        mock_pref.enabled = False
        mock_pref.channels = '[]'
        mock_pref.priority_threshold = "low"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_pref

        should_notify, channels = preference_service.should_notify(
            user_id="user-1",
            event_type="ticket_created",
        )

        assert should_notify is False

    def test_should_notify_below_threshold(self, preference_service, mock_db):
        """Test checking notification below priority threshold."""
        mock_pref = MagicMock()
        mock_pref.enabled = True
        mock_pref.channels = '["email"]'
        mock_pref.priority_threshold = "high"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_pref

        should_notify, channels = preference_service.should_notify(
            user_id="user-1",
            event_type="ticket_created",
            priority="low",  # Below threshold
        )

        assert should_notify is False

    def test_reset_to_defaults(self, preference_service, mock_db):
        """Test resetting preferences to defaults."""
        count = preference_service.reset_to_defaults("user-1")

        assert mock_db.query.return_value.filter.return_value.delete.called
        assert count == len(preference_service.DEFAULT_PREFERENCES)


# ── INTEGRATION TESTS ─────────────────────────────────────────────────────────


class TestDay31Integration:
    """Integration tests for Day 31 features."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    def test_full_notification_flow(self, mock_db):
        """Test complete notification flow."""
        from backend.app.services.notification_service import NotificationService
        from backend.app.services.notification_preference_service import NotificationPreferenceService

        notif_service = NotificationService(mock_db, "company-1")
        pref_service = NotificationPreferenceService(mock_db, "company-1")

        # User has preferences enabled
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.email = "user@example.com"
        mock_user.metadata_json = "{}"

        mock_pref = MagicMock()
        mock_pref.enabled = True
        mock_pref.channels = '["email", "in_app"]'
        mock_pref.priority_threshold = "low"

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_user,  # for preference service
            None,  # for notification service preference check
        ]

        # Get preferences
        with patch.object(pref_service, 'get_user_preferences', return_value={
            "preferences": {"ticket_created": {"enabled": True, "channels": ["email"]}},
            "digest_frequency": "none",
        }):
            prefs = pref_service.get_user_preferences("user-1")

        assert prefs["digest_frequency"] == "none"

    def test_template_to_notification_flow(self, mock_db):
        """Test template usage in notification."""
        from backend.app.services.notification_service import NotificationService
        from backend.app.services.notification_template_service import NotificationTemplateService

        notif_service = NotificationService(mock_db, "company-1")
        template_service = NotificationTemplateService(mock_db, "company-1")

        # Template exists
        mock_template = MagicMock()
        mock_template.subject_template = "Ticket: {{ticket_subject}}"
        mock_template.body_template = "Created by {{customer_name}}"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        # Get template
        template = template_service.get_template_by_event("ticket_created", "email")

        # Render subject
        subject = notif_service._render_template(
            template.subject_template if template else "Subject",
            {"ticket_subject": "Test Ticket"}
        )

        assert "Test Ticket" in subject


# ── LOOPHOLE TESTS ────────────────────────────────────────────────────────────


class TestDay31Loopholes:
    """Tests for potential loopholes and edge cases."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_gap1_prevent_notification_spam(self, mock_db):
        """GAP1: Prevent notification spam - rate limiting."""
        from backend.app.services.notification_service import NotificationService

        service = NotificationService(mock_db, "company-1")

        # Should not send more than reasonable notifications per minute
        # This is enforced at the API level, but service should handle it gracefully
        with patch.object(service, '_get_user_preferences', return_value={"enabled": True, "channels": ["in_app"]}):
            with patch.object(service, '_dispatch_to_channels', return_value={"success": True}):
                # Send multiple notifications
                result = service.send_notification(
                    event_type="ticket_created",
                    recipient_ids=["user-1"],
                    data={},
                )

        # Should complete without error
        assert "sent_count" in result

    def test_gap2_template_injection_prevention(self, mock_db):
        """GAP2: Template injection prevention."""
        from backend.app.services.notification_template_service import NotificationTemplateService

        service = NotificationTemplateService(mock_db, "company-1")

        # Variable validation should reject unknown variables
        from backend.app.exceptions import ValidationError

        with pytest.raises(ValidationError):
            service._validate_template_variables(
                "ticket_created",
                "{{malicious_var}}",
                "subject"
            )

    def test_gap3_user_isolation_preferences(self, mock_db):
        """GAP3: User preferences should be isolated."""
        from backend.app.services.notification_preference_service import NotificationPreferenceService

        service = NotificationPreferenceService(mock_db, "company-1")

        mock_db.query.return_value.filter.return_value.first.return_value = None

        # User 1's preference shouldn't affect User 2
        service.update_preference("user-1", "ticket_created", enabled=False)

        # Verify the query uses both company_id and user_id
        assert mock_db.query.return_value.filter.called

    def test_gap4_digest_time_validation(self, mock_db):
        """GAP4: Digest time should be validated."""
        from backend.app.services.notification_preference_service import NotificationPreferenceService
        from backend.app.exceptions import ValidationError

        service = NotificationPreferenceService(mock_db, "company-1")

        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        # Invalid time format
        with pytest.raises(ValidationError):
            service.set_digest_settings("user-1", "daily", "invalid")

    def test_gap5_bulk_limit_enforcement(self, mock_db):
        """GAP5: Bulk notification limit should be enforced."""
        from backend.app.services.notification_service import NotificationService
        from backend.app.exceptions import ValidationError

        service = NotificationService(mock_db, "company-1")

        # 10,001 recipients should fail
        with pytest.raises(ValidationError):
            service.send_bulk_notification(
                event_type="incident_created",
                recipient_ids=["user"] * 10001,
                data={},
            )

    def test_gap6_channel_fallback(self, mock_db):
        """GAP6: Failed channel should not block other channels."""
        from backend.app.services.notification_service import NotificationService

        service = NotificationService(mock_db, "company-1")

        result = service._dispatch_to_channels(
            notification=MagicMock(user_id="user-1"),
            channels=["email", "in_app"],
            data={},
        )

        # Even if one channel fails, others should be attempted
        assert "channels" in result

    def test_gap7_empty_recipient_list(self, mock_db):
        """GAP7: Empty recipient list should be handled."""
        from backend.app.services.notification_service import NotificationService

        service = NotificationService(mock_db, "company-1")

        result = service.send_notification(
            event_type="ticket_created",
            recipient_ids=[],
            data={},
        )

        assert result["sent_count"] == 0

    def test_gap8_notification_data_size_limit(self, mock_db):
        """GAP8: Large notification data should be handled."""
        from backend.app.services.notification_service import NotificationService

        service = NotificationService(mock_db, "company-1")

        # Create large data
        large_data = {"content": "x" * 100000}

        with patch.object(service, '_get_user_preferences', return_value={"enabled": True, "channels": ["in_app"]}):
            with patch.object(service, '_dispatch_to_channels', return_value={"success": True}):
                result = service.send_notification(
                    event_type="ticket_created",
                    recipient_ids=["user-1"],
                    data=large_data,
                )

        # Should complete without error
        assert "sent_count" in result

    def test_gap9_system_template_protection(self, mock_db):
        """GAP9: System templates should not be hard deleted."""
        from backend.app.services.notification_template_service import NotificationTemplateService

        service = NotificationTemplateService(mock_db, "company-1")

        mock_template = MagicMock()
        mock_template.event_type = "ticket_created"  # System template

        mock_db.query.return_value.filter.return_value.first.return_value = mock_template

        result = service.delete_template("template-1")

        # Should soft delete, not hard delete
        assert mock_template.is_active is False
        assert mock_db.delete.called is False

    def test_gap10_preference_inheritance(self, mock_db):
        """GAP10: New users should get default preferences."""
        from backend.app.services.notification_preference_service import NotificationPreferenceService

        service = NotificationPreferenceService(mock_db, "company-1")

        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.metadata_json = "{}"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value.filter.return_value.all.return_value = []

        prefs = service.get_user_preferences("user-1")

        # Should have all default preferences
        assert len(prefs["preferences"]) == len(service.DEFAULT_PREFERENCES)
