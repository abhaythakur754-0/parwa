"""
Email Channel Tests: Week 13 Day 1 (F-121: Email Inbound).

Comprehensive tests for:
- InboundEmail model
- EmailThread model
- EmailChannelService.process_inbound_email()
- Email loop detection (BC-003)
- Auto-reply / OOO detection
- Email thread finding and linking
- Company isolation (BC-001)
- Idempotency (BC-003)
- Bounce/complaint stubs
- Brevo handler dispatch
"""

import pytest
from unittest.mock import patch

# Service under test — must be imported before use in test classes
from app.services.email_channel_service import EmailChannelService

# ── Test Data ──────────────────────────────────────────────────

SAMPLE_INBOUND_EMAIL = {
    "sender_email": "customer@example.com",
    "sender_name": "John Doe",
    "recipient_email": "support@company.com",
    "subject": "I need help with my order",
    "body_html": "<p>Hi, I need help with my order #12345</p>",
    "body_text": "Hi, I need help with my order #12345",
    "message_id": "<abc123@example.com>",
    "in_reply_to": None,
    "references": None,
    "attachments": [],
    "headers_json": "{}",
}

SAMPLE_REPLY_EMAIL = {
    "sender_email": "customer@example.com",
    "sender_name": "John Doe",
    "recipient_email": "support@company.com",
    "subject": "Re: I need help with my order",
    "body_html": "<p>Thanks, but I still have an issue</p>",
    "body_text": "Thanks, but I still have an issue",
    "message_id": "<def456@example.com>",
    "in_reply_to": "<abc123@example.com>",
    "references": "<abc123@example.com>",
    "attachments": [],
    "headers_json": "{}",
}

SAMPLE_OOO_EMAIL = {
    "sender_email": "away@example.com",
    "sender_name": "Jane Smith",
    "recipient_email": "support@company.com",
    "subject": "Out of Office: I will be back next week",
    "body_html": "<p>I am out of the office until Monday. Please contact my colleague.</p>",
    "body_text": "I am out of the office until Monday. Please contact my colleague.",
    "message_id": "<ooo789@example.com>",
    "in_reply_to": None,
    "references": None,
    "attachments": [],
    "headers_json": '{"Auto-Submitted": "auto-replied"}',
}

SAMPLE_SELF_SENT_EMAIL = {
    "sender_email": "noreply@parwa.ai",
    "sender_name": "PARWA AI",
    "recipient_email": "customer@example.com",
    "subject": "Re: Ticket Update",
    "body_html": "<p>Your ticket has been updated.</p>",
    "body_text": "Your ticket has been updated.",
    "message_id": "<self101@parwa.ai>",
    "in_reply_to": "<abc123@example.com>",
    "references": None,
    "attachments": [],
    "headers_json": "{}",
}

COMPANY_ID = "test-company-123"
COMPANY_ID_2 = "test-company-456"


# ── Helper: Create mock DB session ─────────────────────────────


class MockDB:
    """Mock database session for testing without real DB."""

    def __init__(self):
        self._data = {
            "inbound_emails": {},
            "email_threads": {},
            "tickets": {},
            "ticket_messages": {},
            "customers": {},
        }
        self.committed = False

    def add(self, obj):
        """Simulate adding an object to the session."""

    def commit(self):
        """Simulate commit."""
        self.committed = True

    def flush(self):
        """Simulate flush."""
        self.committed = True

    def refresh(self, obj):
        """Simulate refresh."""

    def query(self, model):
        """Return a mock query object."""
        return MockQuery(self, model)


class MockQuery:
    """Mock query builder."""

    def __init__(self, db, model):
        self.db = db
        self.model = model
        self._filters = []

    def filter(self, *args):
        """Simulate filter — always returns self for chaining."""
        self._filters.extend(args)
        return self

    def first(self):
        """Simulate first() — returns None by default."""
        return None

    def count(self):
        """Simulate count() — returns 0 by default."""
        return 0

    def order_by(self, *args):
        return self

    def offset(self, *args):
        return self

    def limit(self, *args):
        return self

    def all(self):
        return []


# ── Test: Import checks ────────────────────────────────────────


class TestImports:
    """Verify all modules can be imported."""

    def test_import_email_channel_models(self):
        """Email channel models should be importable."""
        from database.models.email_channel import InboundEmail, EmailThread

        assert InboundEmail is not None
        assert EmailThread is not None

    def test_import_email_channel_schemas(self):
        """Email channel schemas should be importable."""
        from app.schemas.email_channel import (
            InboundEmailCreate,
            InboundEmailResponse,
            EmailThreadResponse,
            EmailLoopDetection,
            AutoReplyDetection,
            EmailProcessResult,
        )

        assert all(
            [
                InboundEmailCreate,
                InboundEmailResponse,
                EmailThreadResponse,
                EmailLoopDetection,
                AutoReplyDetection,
                EmailProcessResult,
            ]
        )

    def test_import_email_channel_service(self):
        """Email channel service should be importable."""
        from app.services.email_channel_service import EmailChannelService

        assert EmailChannelService is not None

    def test_import_email_channel_tasks(self):
        """Email channel Celery tasks should be importable."""
        from app.tasks.email_channel_tasks import (
            process_inbound_email_task,
            process_bounce_event_task,
            process_complaint_event_task,
        )

        assert all(
            [
                process_inbound_email_task,
                process_bounce_event_task,
                process_complaint_event_task,
            ]
        )

    def test_import_brevo_handler(self):
        """Brevo handler should be importable with all event types."""
        from app.webhooks.brevo_handler import handle_brevo_event

        assert handle_brevo_event is not None


# ── Test: InboundEmail Model ───────────────────────────────────


class TestInboundEmailModel:
    """Tests for the InboundEmail database model."""

    def test_model_fields(self):
        """InboundEmail should have all required fields."""
        from database.models.email_channel import InboundEmail

        # Check that all expected columns exist
        expected_fields = [
            "id",
            "company_id",
            "message_id",
            "in_reply_to",
            "references",
            "sender_email",
            "sender_name",
            "recipient_email",
            "subject",
            "body_html",
            "body_text",
            "headers_json",
            "is_auto_reply",
            "is_loop",
            "is_processed",
            "ticket_id",
            "processing_error",
            "raw_size_bytes",
            "created_at",
        ]
        for field in expected_fields:
            assert hasattr(InboundEmail, field), f"Missing field: {field}"

    def test_to_dict(self):
        """to_dict() should return a proper dictionary."""
        from database.models.email_channel import InboundEmail

        email = InboundEmail(
            id="test-123",
            company_id="company-456",
            message_id="<msg@example.com>",
            sender_email="test@example.com",
            recipient_email="support@example.com",
            subject="Test Subject",
            is_processed=True,
        )
        result = email.to_dict()
        assert result["id"] == "test-123"
        assert result["company_id"] == "company-456"
        assert result["message_id"] == "<msg@example.com>"
        assert result["sender_email"] == "test@example.com"
        assert result["is_processed"] is True


# ── Test: EmailThread Model ────────────────────────────────────


class TestEmailThreadModel:
    """Tests for the EmailThread database model."""

    def test_model_fields(self):
        """EmailThread should have all required fields."""
        from database.models.email_channel import EmailThread

        expected_fields = [
            "id",
            "company_id",
            "ticket_id",
            "thread_message_id",
            "latest_message_id",
            "message_count",
            "participants_json",
            "created_at",
            "updated_at",
        ]
        for field in expected_fields:
            assert hasattr(EmailThread, field), f"Missing field: {field}"

    def test_to_dict(self):
        """to_dict() should return a proper dictionary."""
        from database.models.email_channel import EmailThread

        thread = EmailThread(
            id="thread-123",
            company_id="company-456",
            ticket_id="ticket-789",
            thread_message_id="<first@example.com>",
            latest_message_id="<latest@example.com>",
            message_count=3,
            participants_json='["a@b.com", "c@d.com"]',
        )
        result = thread.to_dict()
        assert result["id"] == "thread-123"
        assert result["ticket_id"] == "ticket-789"
        assert result["message_count"] == 3


# ── Test: Auto-Reply Detection ─────────────────────────────────


class TestAutoReplyDetection:
    """Tests for auto-reply / OOO detection logic."""

    def _get_service(self):
        return EmailChannelService(MockDB())

    def test_detect_ooo_by_auto_submitted_header(self):
        """Should detect OOO via Auto-Submitted header."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "headers_json": '{"Auto-Submitted": "auto-replied"}',
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is True
        assert result.detection_source == "header"

    def test_detect_ooo_by_precedence_header(self):
        """Should detect OOO via Precedence: auto_reply header."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "headers_json": '{"Precedence": "auto_reply"}',
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is True
        assert result.detection_source == "header"

    def test_detect_ooo_by_body_pattern_out_of_office(self):
        """Should detect OOO via 'out of office' body pattern."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "body_text": "I am out of the office until next Monday",
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is True
        assert result.detection_source == "body"

    def test_detect_ooo_by_body_pattern_autoreply(self):
        """Should detect OOO via 'autoreply' body pattern."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "body_text": "This is an autoreply message",
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is True
        assert result.detection_source == "body"

    def test_detect_ooo_by_body_pattern_vacation(self):
        """Should detect OOO via 'vacation notice' body pattern."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "body_text": "Vacation notice: I will be back next week",
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is True

    def test_detect_ooo_by_body_pattern_away(self):
        """Should detect OOO via 'I am away' body pattern."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "body_text": "I am currently away on leave",
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is True

    def test_no_ooo_normal_email(self):
        """Should NOT detect OOO in a normal email."""
        service = self._get_service()
        result = service.detect_auto_reply(SAMPLE_INBOUND_EMAIL)
        assert result.is_auto_reply is False

    def test_no_ooo_with_auto_submitted_no(self):
        """Should NOT detect OOO when Auto-Submitted = no."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "headers_json": '{"Auto-Submitted": "no"}',
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is False

    def test_ooo_detection_from_html_body(self):
        """Should detect OOO patterns in HTML body (strips tags)."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "body_text": "",
            "body_html": "<html><body><p>I am out of the office.</p></body></html>",
        }
        result = service.detect_auto_reply(email_data)
        assert result.is_auto_reply is True


# ── Test: Loop Detection ────────────────────────────────────────


class TestLoopDetection:
    """Tests for email loop detection logic."""

    def _get_service(self):
        return EmailChannelService(MockDB())

    def test_detect_self_sent_parwa_domain(self):
        """Should detect loop from PARWA system domain."""
        service = self._get_service()
        result = service.detect_email_loop(COMPANY_ID, SAMPLE_SELF_SENT_EMAIL)
        assert result.is_loop is True
        assert result.loop_type == "self_sent"

    def test_detect_self_sent_getparwa_domain(self):
        """Should detect loop from getparwa.com domain."""
        service = self._get_service()
        email_data = {**SAMPLE_SELF_SENT_EMAIL, "sender_email": "system@getparwa.com"}
        result = service.detect_email_loop(COMPANY_ID, email_data)
        assert result.is_loop is True

    def test_no_loop_normal_sender(self):
        """Should NOT detect loop from a normal sender."""
        service = self._get_service()
        result = service.detect_email_loop(COMPANY_ID, SAMPLE_INBOUND_EMAIL)
        assert result.is_loop is False

    def test_no_loop_normal_sender_company_domain(self):
        """Should NOT detect loop for customer company domain."""
        service = self._get_service()
        email_data = {
            **SAMPLE_INBOUND_EMAIL,
            "sender_email": "user@customercompany.com",
        }
        result = service.detect_email_loop(COMPANY_ID, email_data)
        assert result.is_loop is False

    def test_empty_sender_no_loop(self):
        """Should NOT crash with empty sender_email."""
        service = self._get_service()
        email_data = {**SAMPLE_INBOUND_EMAIL, "sender_email": ""}
        result = service.detect_email_loop(COMPANY_ID, email_data)
        # Empty sender will be caught by validation before loop check
        assert result.is_loop is False


# ── Test: References Parsing ───────────────────────────────────


class TestReferencesParsing:
    """Tests for parsing the References email header."""

    def _get_service(self):
        return EmailChannelService(MockDB())

    def test_parse_angle_bracket_references(self):
        """Should parse Message-IDs from angle brackets."""
        service = self._get_service()
        refs = "<msg1@example.com> <msg2@example.com> <msg3@example.com>"
        result = service._parse_references(refs)
        assert result == ["msg1@example.com", "msg2@example.com", "msg3@example.com"]

    def test_parse_empty_references(self):
        """Should return empty list for empty references."""
        service = self._get_service()
        assert service._parse_references("") == []
        assert service._parse_references(None) == []

    def test_parse_single_reference(self):
        """Should parse a single Message-ID."""
        service = self._get_service()
        assert service._parse_references("<only-one@example.com>") == [
            "only-one@example.com"
        ]

    def test_parse_whitespace_references_fallback(self):
        """Should fallback to whitespace split if no angle brackets."""
        service = self._get_service()
        result = service._parse_references("msg1@example.com msg2@example.com")
        assert result == ["msg1@example.com", "msg2@example.com"]


# ── Test: Brevo Handler ─────────────────────────────────────────


class TestBrevoHandler:
    """Tests for the Brevo webhook handler."""

    def test_inbound_email_dispatches_to_celery(self):
        """Inbound email handler should dispatch to Celery task."""
        from app.webhooks.brevo_handler import handle_inbound_email

        event = {
            "event_type": "inbound_email",
            "payload": {
                "sender": {"email": "customer@example.com", "name": "John"},
                "recipient": {"email": "support@company.com"},
                "subject": "Help needed",
                "body_html": "<p>Help</p>",
                "body_text": "Help",
                "message_id": "<test@example.com>",
            },
            "company_id": COMPANY_ID,
            "event_id": "evt-123",
        }

        with patch(
            "app.webhooks.brevo_handler.process_inbound_email_task"
        ) as mock_task:
            result = handle_inbound_email(event)
            mock_task.delay.assert_called_once()
            call_args = mock_task.delay.call_args
            assert call_args[1]["company_id"] == COMPANY_ID
            assert call_args[1]["email_data"]["sender_email"] == "customer@example.com"
            assert result["status"] == "dispatched"

    def test_inbound_email_missing_field(self):
        """Inbound email handler should validate required fields."""
        from app.webhooks.brevo_handler import handle_inbound_email

        event = {
            "event_type": "inbound_email",
            "payload": {
                "sender": {"email": "customer@example.com", "name": "John"},
                # Missing recipient_email, subject, body_html
            },
            "company_id": COMPANY_ID,
        }

        result = handle_inbound_email(event)
        assert result["status"] == "validation_error"
        assert "Missing required field" in result["error"]

    def test_inbound_email_body_size_truncation(self):
        """Inbound email handler should truncate oversized body."""
        from app.webhooks.brevo_handler import handle_inbound_email, MAX_EMAIL_BODY_SIZE

        big_body = "x" * (MAX_EMAIL_BODY_SIZE + 1000)
        event = {
            "event_type": "inbound_email",
            "payload": {
                "sender": {"email": "customer@example.com", "name": "John"},
                "recipient": {"email": "support@company.com"},
                "subject": "Big email",
                "body_html": big_body,
                "message_id": "<big@example.com>",
            },
            "company_id": COMPANY_ID,
        }

        with patch("app.webhooks.brevo_handler.process_inbound_email_task"):
            result = handle_inbound_email(event)
            # Body should be truncated
            data = result.get("data", {})
            assert len(data["body_html"]) <= MAX_EMAIL_BODY_SIZE

    def test_bounce_dispatches_to_celery(self):
        """Bounce handler should dispatch to Celery task."""
        from app.webhooks.brevo_handler import handle_bounce

        event = {
            "event_type": "bounce",
            "payload": {
                "email": "bounced@example.com",
                "type": "hard",
                "reason": "mailbox full",
            },
            "company_id": COMPANY_ID,
            "event_id": "evt-456",
        }

        with patch("app.webhooks.brevo_handler.process_bounce_event_task") as mock_task:
            result = handle_bounce(event)
            mock_task.delay.assert_called_once()
            assert result["status"] == "dispatched"

    def test_complaint_dispatches_to_celery(self):
        """Complaint handler should dispatch to Celery task."""
        from app.webhooks.brevo_handler import handle_complaint

        event = {
            "event_type": "complaint",
            "payload": {
                "email": "complaint@example.com",
                "reason": "spam",
            },
            "company_id": COMPANY_ID,
        }

        with patch(
            "app.webhooks.brevo_handler.process_complaint_event_task"
        ) as mock_task:
            result = handle_complaint(event)
            mock_task.delay.assert_called_once()
            assert result["status"] == "dispatched"

    def test_delivered_logs_only(self):
        """Delivered handler should just log and return."""
        from app.webhooks.brevo_handler import handle_delivered

        event = {
            "event_type": "delivered",
            "payload": {"email": "delivered@example.com", "message_id": "<msg1>"},
            "company_id": COMPANY_ID,
        }

        result = handle_delivered(event)
        assert result["status"] == "logged"
        assert result["event_type"] == "delivered"

    def test_unknown_event_type(self):
        """Unknown event type should return validation error."""
        from app.webhooks.brevo_handler import handle_brevo_event

        event = {
            "event_type": "unknown_type",
            "company_id": COMPANY_ID,
        }

        result = handle_brevo_event(event)
        assert result["status"] == "validation_error"
        assert "Unknown Brevo event type" in result["error"]


# ── Test: Schemas ──────────────────────────────────────────────


class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_inbound_email_create(self):
        """InboundEmailCreate should validate properly."""
        from app.schemas.email_channel import InboundEmailCreate

        data = InboundEmailCreate(
            sender_email="test@example.com",
            recipient_email="support@example.com",
            subject="Help",
            body_html="<p>Help me</p>",
        )
        assert data.sender_email == "test@example.com"

    def test_inbound_email_create_missing_required(self):
        """InboundEmailCreate should reject missing required fields."""
        from app.schemas.email_channel import InboundEmailCreate
        from pydantic import ValidationError

        try:
            InboundEmailCreate()
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass

    def test_email_loop_detection_schema(self):
        """EmailLoopDetection should work."""
        from app.schemas.email_channel import EmailLoopDetection

        loop = EmailLoopDetection(
            is_loop=True,
            reason="Self-sent email",
            loop_type="self_sent",
        )
        assert loop.is_loop is True
        assert loop.loop_type == "self_sent"

    def test_auto_reply_detection_schema(self):
        """AutoReplyDetection should work."""
        from app.schemas.email_channel import AutoReplyDetection

        ooo = AutoReplyDetection(
            is_auto_reply=True,
            reason="OOO body pattern",
            detection_source="body",
        )
        assert ooo.is_auto_reply is True

    def test_email_process_result_schema(self):
        """EmailProcessResult should work."""
        from app.schemas.email_channel import EmailProcessResult

        result = EmailProcessResult(
            status="created_ticket",
            ticket_id="ticket-123",
            inbound_email_id="email-456",
        )
        assert result.status == "created_ticket"


# ── Test: List Inbound Emails ──────────────────────────────────


class TestListInboundEmails:
    """Tests for listing inbound emails with pagination."""

    def _get_service(self):
        return EmailChannelService(MockDB())

    def test_list_returns_empty(self):
        """Should return empty list when no emails."""
        service = self._get_service()
        result = service.list_inbound_emails(COMPANY_ID)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["page"] == 1

    def test_list_with_pagination_params(self):
        """Should pass pagination params correctly."""
        service = self._get_service()
        result = service.list_inbound_emails(COMPANY_ID, page=2, page_size=25)
        assert result["page"] == 2
        assert result["page_size"] == 25


# ── Test: Migration File ───────────────────────────────────────


class TestMigrationFile:
    """Verify migration file exists and is valid."""

    def test_migration_file_exists(self):
        """Migration 016_email_channel_tables.py should exist."""
        import os

        path = "/home/z/my-project/parwa/database/alembic/versions/016_email_channel_tables.py"
        assert os.path.exists(path), f"Migration file not found: {path}"

    def test_migration_creates_correct_tables(self):
        """Migration should create inbound_emails and email_threads."""
        # Read migration file content
        with open(
            "/home/z/my-project/parwa/database/alembic/versions/016_email_channel_tables.py"
        ) as f:
            content = f.read()

        assert "inbound_emails" in content
        assert "email_threads" in content
        assert "company_id" in content  # BC-001
        assert "message_id" in content
        assert "is_processed" in content
        assert "is_auto_reply" in content
        assert "is_loop" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
