# Tests for Week 48 Builder 2 - Email Channel
# Unit tests for email_channel.py, email_templates.py, email_tracker.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from enterprise.notifications.email_channel import (
    EmailChannel,
    EmailMessage,
    EmailConfig,
    EmailProvider,
    EmailStatus,
    EmailAddress,
    SendResult
)

from enterprise.notifications.email_templates import (
    EmailTemplateProcessor,
    EmailTemplate,
    TemplateType,
    RenderedTemplate
)

from enterprise.notifications.email_tracker import (
    EmailTracker,
    TrackingEvent,
    TrackingEventType,
    EmailTrackingData,
    EngagementStats
)


# ============== EMAIL CHANNEL TESTS ==============

class TestEmailAddress:
    def test_email_only(self):
        addr = EmailAddress(email="test@example.com")
        assert addr.to_string() == "test@example.com"

    def test_email_with_name(self):
        addr = EmailAddress(email="test@example.com", name="John Doe")
        assert addr.to_string() == "John Doe <test@example.com>"


class TestEmailChannel:
    def test_create_message(self):
        channel = EmailChannel()
        message = channel.create_message(
            tenant_id="t1",
            to_addresses=["user@example.com"],
            subject="Test Subject",
            body_text="Test body"
        )
        assert message.tenant_id == "t1"
        assert message.subject == "Test Subject"
        assert len(message.to_addresses) == 1

    def test_create_message_with_cc_bcc(self):
        channel = EmailChannel()
        message = channel.create_message(
            tenant_id="t1",
            to_addresses=["to@example.com"],
            subject="Test",
            body_text="Body",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"]
        )
        assert len(message.cc_addresses) == 1
        assert len(message.bcc_addresses) == 1

    def test_create_message_with_template(self):
        channel = EmailChannel()
        message = channel.create_message(
            tenant_id="t1",
            to_addresses=["user@example.com"],
            subject="Test",
            body_text="Body",
            template_id="welcome_email",
            template_vars={"name": "John"}
        )
        assert message.template_id == "welcome_email"
        assert message.template_vars == {"name": "John"}

    def test_get_message(self):
        channel = EmailChannel()
        message = channel.create_message(
            tenant_id="t1",
            to_addresses=["user@example.com"],
            subject="Test",
            body_text="Body"
        )
        result = channel.get_message(message.id)
        assert result.id == message.id

    def test_get_messages_by_tenant(self):
        channel = EmailChannel()
        channel.create_message("t1", ["u1@example.com"], "Test1", "Body")
        channel.create_message("t1", ["u2@example.com"], "Test2", "Body")
        channel.create_message("t2", ["u3@example.com"], "Test3", "Body")

        results = channel.get_messages_by_tenant("t1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_send_message(self):
        config = EmailConfig(
            provider=EmailProvider.SMTP,
            smtp_host="localhost",
            smtp_port=25
        )
        channel = EmailChannel(config)
        message = channel.create_message(
            tenant_id="t1",
            to_addresses=["user@example.com"],
            subject="Test",
            body_text="Test body"
        )

        # Mock SMTP sending
        with patch.object(channel, '_send_smtp', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SendResult(
                message_id=message.id,
                success=True,
                external_id="ext-123"
            )
            result = await channel.send(message)

        assert result.success is True
        assert message.status == EmailStatus.SENT

    def test_mark_delivered(self):
        channel = EmailChannel()
        message = channel.create_message("t1", ["u@example.com"], "Test", "Body")
        message.status = EmailStatus.SENT
        result = channel.mark_delivered(message.id)
        assert result is True
        assert message.status == EmailStatus.DELIVERED

    def test_mark_bounced(self):
        channel = EmailChannel()
        message = channel.create_message("t1", ["u@example.com"], "Test", "Body")
        result = channel.mark_bounced(message.id)
        assert result is True
        assert message.status == EmailStatus.BOUNCED

    def test_mark_opened(self):
        channel = EmailChannel()
        message = channel.create_message("t1", ["u@example.com"], "Test", "Body")
        message.status = EmailStatus.DELIVERED
        result = channel.mark_opened(message.id)
        assert result is True
        assert message.status == EmailStatus.OPENED

    def test_mark_clicked(self):
        channel = EmailChannel()
        message = channel.create_message("t1", ["u@example.com"], "Test", "Body")
        message.status = EmailStatus.OPENED
        result = channel.mark_clicked(message.id)
        assert result is True
        assert message.status == EmailStatus.CLICKED

    def test_get_pending_messages(self):
        channel = EmailChannel()
        m1 = channel.create_message("t1", ["u1@example.com"], "Test", "Body")
        m2 = channel.create_message("t1", ["u2@example.com"], "Test", "Body")
        m2.status = EmailStatus.SENT

        pending = channel.get_pending_messages()
        assert len(pending) == 1

    def test_get_failed_messages(self):
        channel = EmailChannel()
        m1 = channel.create_message("t1", ["u1@example.com"], "Test", "Body")
        m2 = channel.create_message("t1", ["u2@example.com"], "Test", "Body")
        m2.status = EmailStatus.FAILED

        failed = channel.get_failed_messages()
        assert len(failed) == 1

    def test_get_metrics(self):
        channel = EmailChannel()
        metrics = channel.get_metrics()
        assert "total_sent" in metrics
        assert "total_delivered" in metrics
        assert "total_failed" in metrics


# ============== EMAIL TEMPLATES TESTS ==============

class TestEmailTemplates:
    def test_create_template(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="welcome",
            subject="Welcome {{name}}!",
            body_text="Hello {{name}}, welcome to our service!"
        )
        assert template.tenant_id == "t1"
        assert template.name == "welcome"
        assert "name" in template.variables

    def test_create_template_with_html(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="welcome",
            subject="Welcome",
            body_text="Hello {{name}}",
            body_html="<h1>Hello {{name}}</h1>"
        )
        assert template.body_html is not None
        assert "name" in template.variables

    def test_extract_variables(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Hello {{name}}",
            body_text="Your order {{order_id}} is ready. Total: {{amount}}"
        )
        assert "name" in template.variables
        assert "order_id" in template.variables
        assert "amount" in template.variables

    def test_render_template(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="greeting",
            subject="Hello {{name}}",
            body_text="Welcome {{name}}!"
        )
        rendered = processor.render(template.id, {"name": "John"})
        assert rendered.subject == "Hello John"
        assert rendered.body_text == "Welcome John!"

    def test_render_with_defaults(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Hello {{name}}",
            body_text="Body",
            default_values={"name": "Guest"}
        )
        rendered = processor.render(template.id, {})
        assert rendered.subject == "Hello Guest"

    def test_render_with_missing_required(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Hello {{name}}",
            body_text="Body",
            required_vars=["name"]
        )
        rendered = processor.render(template.id, {})
        assert "name" in rendered.missing_vars

    def test_get_template(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Test",
            body_text="Body"
        )
        result = processor.get_template(template.id)
        assert result.id == template.id

    def test_get_template_by_name(self):
        processor = EmailTemplateProcessor()
        processor.create_template(
            tenant_id="t1",
            name="welcome",
            subject="Welcome",
            body_text="Body"
        )
        result = processor.get_template_by_name("t1", "welcome")
        assert result is not None
        assert result.name == "welcome"

    def test_update_template(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Old Subject",
            body_text="Old Body"
        )
        updated = processor.update_template(
            template.id,
            subject="New Subject"
        )
        assert updated.subject == "New Subject"
        assert updated.version == 2

    def test_delete_template(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Test",
            body_text="Body"
        )
        result = processor.delete_template(template.id)
        assert result is True
        assert processor.get_template(template.id) is None

    def test_get_templates_by_tenant(self):
        processor = EmailTemplateProcessor()
        processor.create_template("t1", "test1", "S1", "B1")
        processor.create_template("t1", "test2", "S2", "B2")
        processor.create_template("t2", "test3", "S3", "B3")
        results = processor.get_templates_by_tenant("t1")
        assert len(results) == 2

    def test_validate_variables(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Hello {{name}}",
            body_text="Order {{order_id}}",
            required_vars=["name"]
        )
        result = processor.validate_variables(template.id, {"name": "John"})
        assert result["valid"] is True

    def test_validate_missing_required(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="test",
            subject="Hello {{name}}",
            body_text="Body",
            required_vars=["name"]
        )
        result = processor.validate_variables(template.id, {})
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_duplicate_template(self):
        processor = EmailTemplateProcessor()
        template = processor.create_template(
            tenant_id="t1",
            name="original",
            subject="Hello {{name}}",
            body_text="Body"
        )
        duplicate = processor.duplicate_template(template.id, "copy")
        assert duplicate.name == "copy"
        assert duplicate.tenant_id == template.tenant_id


# ============== EMAIL TRACKER TESTS ==============

class TestEmailTracker:
    def test_generate_tracking(self):
        tracker = EmailTracker()
        tracking = tracker.generate_tracking(
            message_id="msg1",
            tenant_id="t1",
            links=["https://example.com/page1", "https://example.com/page2"]
        )
        assert tracking.message_id == "msg1"
        assert tracking.tracking_pixel_url is not None
        assert len(tracking.tracking_links) == 2

    def test_generate_tracking_pixel_only(self):
        tracker = EmailTracker()
        tracking = tracker.generate_tracking(
            message_id="msg1",
            tenant_id="t1"
        )
        assert tracking.tracking_pixel_url is not None
        assert len(tracking.tracking_links) == 0

    def test_record_sent_event(self):
        tracker = EmailTracker()
        event = tracker.record_event(
            message_id="msg1",
            tenant_id="t1",
            event_type=TrackingEventType.SENT
        )
        assert event.event_type == TrackingEventType.SENT
        assert tracker._metrics["total_sent"] == 1

    def test_record_delivered_event(self):
        tracker = EmailTracker()
        event = tracker.record_event(
            message_id="msg1",
            tenant_id="t1",
            event_type=TrackingEventType.DELIVERED
        )
        assert event.event_type == TrackingEventType.DELIVERED

    def test_record_open_event(self):
        tracker = EmailTracker()
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)
        tracker.record_event("msg1", "t1", TrackingEventType.DELIVERED)
        event = tracker.record_event(
            message_id="msg1",
            tenant_id="t1",
            event_type=TrackingEventType.OPENED,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        assert event.event_type == TrackingEventType.OPENED
        assert event.ip_address == "192.168.1.1"

    def test_record_click_event(self):
        tracker = EmailTracker()
        event = tracker.record_event(
            message_id="msg1",
            tenant_id="t1",
            event_type=TrackingEventType.CLICKED,
            url="https://example.com/page"
        )
        assert event.url == "https://example.com/page"

    def test_record_bounce_event(self):
        tracker = EmailTracker()
        event = tracker.record_event(
            message_id="msg1",
            tenant_id="t1",
            event_type=TrackingEventType.BOUNCED,
            bounce_reason="User unknown"
        )
        assert event.bounce_reason == "User unknown"

    def test_get_engagement(self):
        tracker = EmailTracker()
        tracker.generate_tracking("msg1", "t1")
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)
        tracker.record_event("msg1", "t1", TrackingEventType.OPENED)
        tracker.record_event("msg1", "t1", TrackingEventType.OPENED)

        engagement = tracker.get_engagement("msg1")
        assert engagement.open_count == 2

    def test_get_events_filtered(self):
        tracker = EmailTracker()
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)
        tracker.record_event("msg1", "t1", TrackingEventType.OPENED)
        tracker.record_event("msg2", "t1", TrackingEventType.SENT)

        events = tracker.get_events(message_id="msg1")
        assert len(events) == 2

        events = tracker.get_events(event_type=TrackingEventType.OPENED)
        assert len(events) == 1

    def test_record_open_helper(self):
        tracker = EmailTracker()
        event = tracker.record_open(
            message_id="msg1",
            tenant_id="t1",
            ip_address="10.0.0.1"
        )
        assert event.event_type == TrackingEventType.OPENED

    def test_record_click_helper(self):
        tracker = EmailTracker()
        event = tracker.record_click(
            message_id="msg1",
            tenant_id="t1",
            url="https://example.com/link"
        )
        assert event.event_type == TrackingEventType.CLICKED
        assert event.url == "https://example.com/link"

    def test_get_open_rate(self):
        tracker = EmailTracker()
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)
        tracker.record_event("msg2", "t1", TrackingEventType.SENT)
        tracker.record_event("msg1", "t1", TrackingEventType.OPENED)

        rate = tracker.get_open_rate("t1")
        assert rate == 50.0

    def test_get_click_rate(self):
        tracker = EmailTracker()
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)
        tracker.record_event("msg1", "t1", TrackingEventType.OPENED)
        tracker.record_event("msg1", "t1", TrackingEventType.CLICKED)

        rate = tracker.get_click_rate("t1")
        assert rate == 100.0

    def test_get_metrics(self):
        tracker = EmailTracker()
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)
        tracker.record_event("msg1", "t1", TrackingEventType.OPENED)
        metrics = tracker.get_metrics()
        assert metrics["total_sent"] == 1
        assert metrics["total_opens"] == 1

    def test_get_tenant_metrics(self):
        tracker = EmailTracker()
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)
        tracker.record_event("msg1", "t1", TrackingEventType.DELIVERED)
        tracker.record_event("msg1", "t1", TrackingEventType.OPENED)
        tracker.record_event("msg1", "t2", TrackingEventType.SENT)

        t1_metrics = tracker.get_tenant_metrics("t1")
        assert t1_metrics["sent"] == 1
        assert t1_metrics["delivered"] == 1

    def test_cleanup_old_events(self):
        tracker = EmailTracker()
        tracker.record_event("msg1", "t1", TrackingEventType.SENT)

        # Add old event manually
        old_event = TrackingEvent(
            message_id="old",
            tenant_id="t1",
            event_type=TrackingEventType.SENT,
            timestamp=datetime.utcnow() - timedelta(days=100)
        )
        tracker._events.append(old_event)

        removed = tracker.cleanup_old_events(days=30)
        assert removed == 1
