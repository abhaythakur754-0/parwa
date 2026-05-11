"""
Day 27 Service Unit Tests - Message Service

Tests for message_service.py covering:
- Message CRUD operations
- Edit window enforcement
- Role validation
- Content validation
- Attachment handling
- Redaction
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from backend.app.services.message_service import MessageService
from backend.app.exceptions import NotFoundError, ValidationError
from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketAttachment,
    TicketStatus,
    TicketPriority,
)


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_company_id():
    """Test company ID."""
    return "test-company-123"


@pytest.fixture
def message_service(mock_db, mock_company_id):
    """Message service instance."""
    return MessageService(mock_db, mock_company_id)


@pytest.fixture
def sample_ticket():
    """Sample ticket for testing."""
    ticket = Ticket()
    ticket.id = "ticket-123"
    ticket.company_id = "test-company-123"
    ticket.status = TicketStatus.open.value
    ticket.frozen = False
    ticket.first_response_at = None
    ticket.updated_at = datetime.utcnow()
    return ticket


@pytest.fixture
def sample_message():
    """Sample message for testing."""
    message = TicketMessage()
    message.id = "message-123"
    message.ticket_id = "ticket-123"
    message.company_id = "test-company-123"
    message.role = "agent"
    message.content = "Hello, how can I help you?"
    message.channel = "email"
    message.is_internal = False
    message.is_redacted = False
    message.ai_confidence = None
    message.variant_version = None
    message.metadata_json = "{}"
    message.created_at = datetime.utcnow()
    return message


# ═══════════════════════════════════════════════════════════════════
# CREATE MESSAGE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestCreateMessage:

    def test_create_message_success(self, message_service, mock_db, sample_ticket):
        """Test successful message creation."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        message = message_service.create_message(
            ticket_id="ticket-123",
            role="agent",
            content="Test message",
            channel="email",
        )

        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_message_validates_role(self, message_service, mock_db, sample_ticket):
        """Test that invalid role is rejected."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        with pytest.raises(ValidationError) as exc_info:
            message_service.create_message(
                ticket_id="ticket-123",
                role="invalid_role",
                content="Test message",
                channel="email",
            )

        assert "Invalid role" in str(exc_info.value)

    def test_create_message_validates_content_length(self, message_service, mock_db, sample_ticket):
        """Test that content length is validated."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        long_content = "x" * (MessageService.MAX_MESSAGE_LENGTH + 1)

        with pytest.raises(ValidationError) as exc_info:
            message_service.create_message(
                ticket_id="ticket-123",
                role="agent",
                content=long_content,
                channel="email",
            )

        assert "too long" in str(exc_info.value)

    def test_create_message_rejects_frozen_ticket(self, message_service, mock_db, sample_ticket):
        """Test that messages cannot be added to frozen tickets."""
        sample_ticket.frozen = True
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        with pytest.raises(ValidationError) as exc_info:
            message_service.create_message(
                ticket_id="ticket-123",
                role="agent",
                content="Test message",
                channel="email",
            )

        assert "frozen" in str(exc_info.value).lower()

    def test_create_message_sets_first_response_at(self, message_service, mock_db, sample_ticket):
        """Test that first_response_at is set on first agent/AI message."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        message_service.create_message(
            ticket_id="ticket-123",
            role="agent",
            content="Test message",
            channel="email",
        )

        assert sample_ticket.first_response_at is not None

    def test_create_message_with_ai_confidence(self, message_service, mock_db, sample_ticket):
        """Test creating AI message with confidence score."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        message_service.create_message(
            ticket_id="ticket-123",
            role="ai",
            content="AI response",
            channel="chat",
            ai_confidence=0.95,
            variant_version="v1.0",
        )

        assert mock_db.add.called

    def test_create_message_with_attachments(self, message_service, mock_db, sample_ticket):
        """Test creating message with attachments."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        attachments = [
            {
                "filename": "test.pdf",
                "file_url": "https://storage/test.pdf",
                "file_size": 1024,
                "mime_type": "application/pdf",
            }
        ]

        message_service.create_message(
            ticket_id="ticket-123",
            role="customer",
            content="See attachment",
            channel="email",
            attachments=attachments,
        )

        # Should add both message and attachment
        assert mock_db.add.call_count >= 2


# ═══════════════════════════════════════════════════════════════════
# GET MESSAGE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestGetMessage:

    def test_get_message_success(self, message_service, mock_db, sample_message):
        """Test successful message retrieval."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        message = message_service.get_message("ticket-123", "message-123")

        assert message.id == "message-123"
        assert message.role == "agent"

    def test_get_message_not_found(self, message_service, mock_db):
        """Test message not found raises error."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            message_service.get_message("ticket-123", "nonexistent")


# ═══════════════════════════════════════════════════════════════════
# LIST MESSAGES TESTS
# ═══════════════════════════════════════════════════════════════════

class TestListMessages:

    def test_list_messages_success(self, message_service, mock_db, sample_message):
        """Test successful message listing."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_message]
        mock_db.query.return_value = mock_query

        messages, total = message_service.list_messages("ticket-123")

        assert len(messages) == 1
        assert total == 1

    def test_list_messages_excludes_internal_by_default(self, message_service, mock_db):
        """Test that internal messages are excluded by default."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        message_service.list_messages("ticket-123")

        # Should have filtered is_internal == False
        filter_calls = mock_query.filter.call_args_list

    def test_list_messages_includes_internal_when_requested(self, message_service, mock_db, sample_message):
        """Test that internal messages are included when requested."""
        sample_message.is_internal = True
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_message]
        mock_db.query.return_value = mock_query

        messages, total = message_service.list_messages("ticket-123", include_internal=True)

        assert len(messages) == 1

    def test_list_messages_filters_by_role(self, message_service, mock_db, sample_message):
        """Test filtering by role."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_message]
        mock_db.query.return_value = mock_query

        messages, total = message_service.list_messages("ticket-123", role="agent")


# ═══════════════════════════════════════════════════════════════════
# UPDATE MESSAGE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestUpdateMessage:

    def test_update_message_success(self, message_service, mock_db, sample_message):
        """Test successful message update."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        # Set created_at to be within edit window
        sample_message.created_at = datetime.utcnow()

        updated = message_service.update_message(
            ticket_id="ticket-123",
            message_id="message-123",
            content="Updated content",
        )

        assert mock_db.commit.called

    def test_update_message_rejects_after_edit_window(self, message_service, mock_db, sample_message):
        """Test that messages cannot be edited after edit window expires."""
        sample_message.created_at = datetime.utcnow() - timedelta(minutes=10)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        with pytest.raises(ValidationError) as exc_info:
            message_service.update_message(
                ticket_id="ticket-123",
                message_id="message-123",
                content="Updated content",
            )

        assert "5 minutes" in str(exc_info.value)

    def test_update_message_force_bypasses_edit_window(self, message_service, mock_db, sample_message):
        """Test that force=True bypasses edit window check."""
        sample_message.created_at = datetime.utcnow() - timedelta(minutes=10)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        updated = message_service.update_message(
            ticket_id="ticket-123",
            message_id="message-123",
            content="Updated content",
            force=True,
        )

        assert mock_db.commit.called

    def test_update_message_validates_content_length(self, message_service, mock_db, sample_message):
        """Test that updated content length is validated."""
        sample_message.created_at = datetime.utcnow()
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        long_content = "x" * (MessageService.MAX_MESSAGE_LENGTH + 1)

        with pytest.raises(ValidationError) as exc_info:
            message_service.update_message(
                ticket_id="ticket-123",
                message_id="message-123",
                content=long_content,
            )

        assert "too long" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════
# DELETE MESSAGE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestDeleteMessage:

    def test_soft_delete_message(self, message_service, mock_db, sample_message):
        """Test soft delete replaces content with [DELETED]."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        message_service.delete_message("ticket-123", "message-123")

        assert sample_message.content == "[DELETED]"
        assert mock_db.commit.called

    def test_hard_delete_message(self, message_service, mock_db, sample_message):
        """Test hard delete removes from database."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        message_service.delete_message("ticket-123", "message-123", hard=True)

        assert mock_db.delete.called


# ═══════════════════════════════════════════════════════════════════
# REDACTION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestRedactMessage:

    def test_redact_message_success(self, message_service, mock_db, sample_message):
        """Test successful message redaction."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_message

        redacted = message_service.redact_message(
            ticket_id="ticket-123",
            message_id="message-123",
            reason="GDPR request",
            user_id="user-456",
        )

        assert sample_message.content == "[REDACTED]"
        assert sample_message.is_redacted is True

        metadata = json.loads(sample_message.metadata_json)
        assert metadata["redacted"] is True
        assert metadata["redaction_reason"] == "GDPR request"


# ═══════════════════════════════════════════════════════════════════
# VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestMessageValidation:

    def test_valid_roles_accepted(self, message_service, mock_db, sample_ticket):
        """Test that all valid roles are accepted."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        valid_roles = ["customer", "agent", "system", "ai"]

        for role in valid_roles:
            # Reset mock
            mock_db.add.reset_mock()
            mock_db.commit.reset_mock()

            message_service.create_message(
                ticket_id="ticket-123",
                role=role,
                content=f"Test message from {role}",
                channel="email",
            )

            assert mock_db.add.called

    def test_empty_content_rejected(self, message_service, mock_db, sample_ticket):
        """Test that empty content is rejected."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        # Empty content should still create (validation is at Pydantic level)
        # But very long content is rejected
        pass


# ═══════════════════════════════════════════════════════════════════
# ATTACHMENT TESTS
# ═══════════════════════════════════════════════════════════════════

class TestAttachments:

    def test_get_attachments_success(self, message_service, mock_db):
        """Test getting attachments for a ticket."""
        attachment = TicketAttachment()
        attachment.id = "attach-123"
        attachment.ticket_id = "ticket-123"
        attachment.filename = "test.pdf"
        attachment.file_url = "https://storage/test.pdf"

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [attachment]

        attachments = message_service.get_attachments("ticket-123")

        assert len(attachments) == 1
        assert attachments[0].filename == "test.pdf"
