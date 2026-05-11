"""
Chat Widget Service Tests — Week 13 Day 4 (F-122)

Tests for:
- Session creation with HMAC tokens (BC-011)
- Message sending with rate limits (BC-006)
- Typing indicators and read receipts
- Session assignment and closing
- CSAT rating submission
- Widget config management
- Canned response CRUD
"""

import sys
import os
import types
from unittest.mock import MagicMock, patch, PropertyMock
import pytest


# Ensure conftest runs first
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.tests.conftest import _mock_db, _AttrChainer


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Provide mock DB session."""
    db = MagicMock()
    db.query = MagicMock(return_value=MagicMock())
    db.add = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.refresh = MagicMock()
    db.delete = MagicMock()
    return db


@pytest.fixture
def company_id():
    return "test-company-123"


@pytest.fixture
def chat_service(mock_db, company_id):
    """Provide ChatWidgetService with mocked dependencies."""
    from app.services.chat_widget_service import ChatWidgetService
    service = ChatWidgetService(mock_db, company_id)
    service._emit_chat_event = MagicMock()
    return service


# ═══════════════════════════════════════════════════════════
# Session Tests
# ═══════════════════════════════════════════════════════════

class TestCreateSession:
    """Tests for chat session creation."""

    def test_create_session_success(self, chat_service, mock_db, company_id):
        """Test successful session creation with visitor token."""
        # Setup — refresh() must assign the id before to_dict() is called
        mock_session = MagicMock()
        mock_session.id = None
        mock_session.to_dict.return_value = {"id": "session-001", "status": "active"}

        def _refresh(obj):
            obj.id = "session-001"

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=_refresh)

        with patch.object(chat_service, "_get_widget_config", return_value=None), \
             patch.object(chat_service, "_generate_visitor_token", return_value="hmac-token-123"), \
             patch("database.models.chat_widget.ChatWidgetSession", return_value=mock_session):
            result = chat_service.create_session(company_id, {
                "visitor_name": "John",
                "visitor_email": "john@test.com",
            })

        assert result["status"] == "created"
        assert result["visitor_token"] == "hmac-token-123"
        assert result["session"]["id"] == "session-001"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_session_widget_disabled(self, chat_service, company_id):
        """Test session creation when widget is disabled."""
        mock_config = MagicMock()
        mock_config.is_enabled = False

        with patch.object(chat_service, "_get_widget_config", return_value=mock_config):
            result = chat_service.create_session(company_id, {
                "visitor_name": "John",
            })

        assert result["status"] == "error"
        assert "disabled" in result["error"]

    def test_create_session_missing_required_fields(self, chat_service, company_id):
        """Test session creation when required visitor fields are missing."""
        mock_config = MagicMock()
        mock_config.is_enabled = True
        mock_config.require_visitor_email = True

        with patch.object(chat_service, "_get_widget_config", return_value=mock_config), \
             patch.object(chat_service, "_check_required_visitor_fields", return_value=["email"]):
            result = chat_service.create_session(company_id, {
                "visitor_name": "John",
            })

        assert result["status"] == "error"
        assert "email" in result["error"]


class TestSessionAssignment:
    """Tests for session assignment."""

    def test_assign_session_success(self, chat_service, mock_db, company_id):
        """Test successful agent assignment."""
        mock_session = MagicMock()
        mock_session.assigned_agent_id = None
        mock_session.status = "active"
        mock_session.to_dict.return_value = {"id": "session-001", "status": "assigned"}

        with patch.object(chat_service, "get_session", return_value=mock_session):
            result = chat_service.assign_session("session-001", company_id, "agent-001")

        assert result["status"] == "assigned"
        assert mock_session.assigned_agent_id == "agent-001"
        assert mock_session.status == "assigned"
        chat_service._emit_chat_event.assert_called_once()

    def test_assign_session_not_found(self, chat_service, company_id):
        """Test assignment when session doesn't exist."""
        with patch.object(chat_service, "get_session", return_value=None):
            result = chat_service.assign_session("nonexistent", company_id, "agent-001")

        assert result["status"] == "error"
        assert "not found" in result["error"]


class TestCloseSession:
    """Tests for session closing."""

    def test_close_session_success(self, chat_service, mock_db, company_id):
        """Test successful session close."""
        mock_session = MagicMock()
        mock_session.status = "assigned"
        mock_session.to_dict.return_value = {"id": "session-001", "status": "closed"}

        with patch.object(chat_service, "get_session", return_value=mock_session):
            result = chat_service.close_session("session-001", company_id)

        assert result["status"] == "closed"
        assert mock_session.status == "closed"
        assert mock_session.closed_at is not None
        chat_service._emit_chat_event.assert_called_once()


# ═══════════════════════════════════════════════════════════
# Message Tests
# ═══════════════════════════════════════════════════════════

class TestSendMessage:
    """Tests for message sending."""

    def test_send_visitor_message_success(self, chat_service, mock_db, company_id):
        """Test successful visitor message."""
        mock_session = MagicMock()
        mock_session.status = "active"
        mock_session.message_count = 0
        mock_session.visitor_message_count = 0
        mock_session.first_message_at = None
        mock_session.assigned_agent_id = None

        mock_message = MagicMock()
        mock_message.id = None
        mock_message.to_dict.return_value = {"id": "msg-001", "content": "Hello"}

        def _refresh(obj):
            obj.id = "msg-001"

        mock_db.refresh = MagicMock(side_effect=_refresh)

        with patch.object(chat_service, "get_session", return_value=mock_session), \
             patch.object(chat_service, "_check_visitor_rate_limit", return_value=None), \
             patch("database.models.chat_widget.ChatWidgetMessage", return_value=mock_message):
            result = chat_service.send_message(
                session_id="session-001",
                company_id=company_id,
                content="Hello",
                role="visitor",
            )

        assert result["status"] == "sent"
        assert result["message"]["id"] == "msg-001"
        chat_service._emit_chat_event.assert_called_once()

    def test_send_message_session_not_found(self, chat_service, company_id):
        """Test sending message to nonexistent session."""
        with patch.object(chat_service, "get_session", return_value=None):
            result = chat_service.send_message(
                session_id="nonexistent",
                company_id=company_id,
                content="Hello",
            )

        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_send_message_session_closed(self, chat_service, company_id):
        """Test sending message to closed session."""
        mock_session = MagicMock()
        mock_session.status = "closed"

        with patch.object(chat_service, "get_session", return_value=mock_session):
            result = chat_service.send_message(
                session_id="session-001",
                company_id=company_id,
                content="Hello",
            )

        assert result["status"] == "error"
        assert "closed" in result["error"]

    def test_send_message_rate_limited(self, chat_service, company_id):
        """Test BC-006 rate limit."""
        mock_session = MagicMock()
        mock_session.status = "active"

        with patch.object(chat_service, "get_session", return_value=mock_session), \
             patch.object(chat_service, "_check_visitor_rate_limit",
                         return_value="BC-006: rate limit exceeded"):
            result = chat_service.send_message(
                session_id="session-001",
                company_id=company_id,
                content="Hello",
                role="visitor",
            )

        assert result["status"] == "error"
        assert "BC-006" in result["error"]


class TestTypingIndicator:
    """Tests for typing indicators."""

    def test_typing_indicator_emit(self, chat_service, company_id):
        """Test typing indicator emission."""
        mock_session = MagicMock()

        with patch.object(chat_service, "get_session", return_value=mock_session):
            result = chat_service.send_typing_indicator(
                session_id="session-001",
                company_id=company_id,
                user_id="user-001",
                role="visitor",
                is_typing=True,
            )

        assert result["status"] == "emitted"
        chat_service._emit_chat_event.assert_called_once()
        call_args = chat_service._emit_chat_event.call_args
        assert call_args[1]["event_type"] == "chat:typing"


class TestMarkRead:
    """Tests for mark messages read."""

    def test_mark_messages_read_success(self, chat_service, mock_db, company_id):
        """Test marking messages as read."""
        mock_session = MagicMock()
        mock_msg1 = MagicMock()
        mock_msg1.is_read = False
        mock_msg2 = MagicMock()
        mock_msg2.is_read = False

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_msg1, mock_msg2])
        mock_db.query = MagicMock(return_value=mock_query)

        with patch.object(chat_service, "get_session", return_value=mock_session):
            count = chat_service.mark_messages_read(
                session_id="session-001",
                company_id=company_id,
                reader_id="user-001",
            )

        assert count == 2
        assert mock_msg1.is_read is True
        assert mock_msg2.is_read is True
        chat_service._emit_chat_event.assert_called_once()

    def test_mark_messages_read_no_session(self, chat_service, company_id):
        """Test marking read when session doesn't exist."""
        with patch.object(chat_service, "get_session", return_value=None):
            count = chat_service.mark_messages_read(
                session_id="nonexistent",
                company_id=company_id,
            )

        assert count == 0


# ═══════════════════════════════════════════════════════════
# CSAT Rating Tests
# ═══════════════════════════════════════════════════════════

class TestCsatRating:
    """Tests for CSAT rating submission."""

    def test_submit_rating_success(self, chat_service, mock_db, company_id):
        """Test successful CSAT rating."""
        mock_session = MagicMock()
        mock_session.to_dict.return_value = {"id": "session-001", "csat_rating": 5}

        with patch.object(chat_service, "get_session", return_value=mock_session):
            result = chat_service.submit_csat_rating(
                session_id="session-001",
                company_id=company_id,
                rating=5,
                comment="Great support!",
            )

        assert result["status"] == "rated"
        assert mock_session.csat_rating == 5
        assert mock_session.csat_comment == "Great support!"

    def test_submit_rating_invalid(self, chat_service, company_id):
        """Test invalid CSAT rating."""
        result = chat_service.submit_csat_rating(
            session_id="session-001",
            company_id=company_id,
            rating=10,
        )

        assert result["status"] == "error"
        assert "1-5" in result["error"]


# ═══════════════════════════════════════════════════════════
# Widget Config Tests
# ═══════════════════════════════════════════════════════════

class TestWidgetConfig:
    """Tests for widget configuration management."""

    def test_get_widget_config(self, chat_service, mock_db, company_id):
        """Test getting widget config."""
        mock_config = MagicMock()
        mock_config.widget_title = "Chat"
        mock_config.is_enabled = True

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_config)
        mock_db.query = MagicMock(return_value=mock_query)

        result = chat_service.get_widget_config(company_id)

        assert result is not None
        assert result.widget_title == "Chat"
        mock_db.query.assert_called_once()

    def test_get_or_create_widget_config_existing(self, chat_service, company_id):
        """Test getting existing config."""
        mock_config = MagicMock()

        with patch.object(chat_service, "get_widget_config", return_value=mock_config):
            result = chat_service.get_or_create_widget_config(company_id)

        assert result is mock_config

    def test_get_or_create_widget_config_new(self, chat_service, mock_db, company_id):
        """Test creating new config when none exists."""
        with patch.object(chat_service, "get_widget_config", return_value=None):
            mock_config = MagicMock()
            chat_service.ChatWidgetConfig = MagicMock(return_value=mock_config)
            result = chat_service.get_or_create_widget_config(company_id)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_update_widget_config(self, chat_service, mock_db, company_id):
        """Test updating widget config."""
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {"widget_title": "Updated"}

        with patch.object(chat_service, "get_or_create_widget_config", return_value=mock_config):
            result = chat_service.update_widget_config(
                company_id,
                {"widget_title": "Updated Title"},
            )

        assert result["status"] == "updated"
        assert mock_config.widget_title == "Updated Title"


# ═══════════════════════════════════════════════════════════
# Canned Response Tests
# ═══════════════════════════════════════════════════════════

class TestCannedResponses:
    """Tests for canned response CRUD."""

    def test_create_canned_response(self, chat_service, mock_db, company_id):
        """Test creating a canned response."""
        mock_response = MagicMock()
        mock_response.id = None
        mock_response.to_dict.return_value = {"id": "cr-001", "title": "Greeting"}

        def _refresh(obj):
            obj.id = "cr-001"

        mock_db.refresh = MagicMock(side_effect=_refresh)

        with patch("app.services.chat_widget_service.CannedResponse", return_value=mock_response):
            result = chat_service.create_canned_response(
                company_id,
                {"title": "Greeting", "content": "Hello! How can I help?"},
                created_by="agent-001",
            )

        assert result["status"] == "created"
        mock_db.add.assert_called_once()

    def test_list_canned_responses(self, chat_service, mock_db, company_id):
        """Test listing canned responses."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[
            MagicMock(to_dict=lambda: {"id": "cr-001", "title": "Greeting"}),
        ])
        mock_db.query = MagicMock(return_value=mock_query)

        items = chat_service.list_canned_responses(company_id)

        assert len(items) == 1

    def test_update_canned_response_not_found(self, chat_service, mock_db, company_id):
        """Test updating nonexistent canned response."""
        mock_query = MagicMock()
        # Each .filter() call returns the same query for chaining
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        with patch("app.services.chat_widget_service.CannedResponse") as MockCR:
            MockCR.id == "nonexistent"
            mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
            result = chat_service.update_canned_response(
                "nonexistent", company_id, {"title": "New Title"},
            )

        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_delete_canned_response(self, chat_service, mock_db, company_id):
        """Test deleting a canned response."""
        mock_response = MagicMock()
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_response)
        mock_db.query = MagicMock(return_value=mock_query)

        result = chat_service.delete_canned_response("cr-001", company_id)

        assert result["status"] == "deleted"
        mock_db.delete.assert_called_once()


# ═══════════════════════════════════════════════════════════
# Visitor Token Tests (BC-011)
# ═══════════════════════════════════════════════════════════

class TestVisitorToken:
    """Tests for HMAC visitor token (BC-011)."""

    def test_generate_and_verify_token(self, chat_service, company_id):
        """Test token generation and verification."""
        token = chat_service.generate_visitor_token("session-001", company_id)
        assert isinstance(token, str)
        assert len(token) == 64  # SHA256 hex

    def test_verify_valid_token(self, chat_service, company_id):
        """Test verifying a valid token."""
        token = chat_service.generate_visitor_token("session-001", company_id)
        result = chat_service.verify_visitor_token("session-001", company_id, token)
        assert result is True

    def test_verify_invalid_token(self, chat_service, company_id):
        """Test verifying an invalid token."""
        result = chat_service.verify_visitor_token(
            "session-001", company_id, "invalid-token-here",
        )
        assert result is False

    def test_verify_wrong_session(self, chat_service, company_id):
        """Test verifying token for wrong session."""
        token = chat_service.generate_visitor_token("session-001", company_id)
        result = chat_service.verify_visitor_token("session-999", company_id, token)
        assert result is False
