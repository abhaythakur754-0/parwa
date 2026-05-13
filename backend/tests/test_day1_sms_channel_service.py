"""
Comprehensive Unit Tests for SMS Channel Service — Day 1 (F-123)

Covers the full SMS channel lifecycle with all Building Code compliance:
- BC-001: Multi-tenant isolation (company_id scoping)
- BC-003: Idempotent webhook processing (Twilio MessageSid)
- BC-006: Rate limiting (hourly/daily/inbound flood)
- BC-010: TCPA compliance (opt-out/STOP keywords, consent tracking)
- BC-011: Twilio credentials encrypted at rest
- BC-012: Structured error responses

All DB queries and Twilio calls are mocked. No external dependencies.
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock, call
import pytest

# Ensure project root on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Provide mock DB session with fluent query interface."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.delete = MagicMock()
    db.refresh = MagicMock()

    # Default query chain: db.query(Model).filter(...).first() / .all() / .count() / .scalar()
    _query = MagicMock()
    _query.filter = MagicMock(return_value=_query)
    _query.order_by = MagicMock(return_value=_query)
    _query.offset = MagicMock(return_value=_query)
    _query.limit = MagicMock(return_value=_query)
    _query.first = MagicMock(return_value=None)
    _query.all = MagicMock(return_value=[])
    _query.count = MagicMock(return_value=0)
    _query.scalar = MagicMock(return_value=0)
    db.query = MagicMock(return_value=_query)

    return db


@pytest.fixture
def company_id():
    return "comp-sms-day1-001"


@pytest.fixture
def sms_service(mock_db):
    """Provide SMSChannelService with mocked Twilio and event emission."""
    from app.services.sms_channel_service import SMSChannelService
    service = SMSChannelService(mock_db)
    # Mock external calls by default
    service._send_sms_via_twilio = MagicMock(return_value={
        "success": True, "message_sid": "SM-twilio-mock-001", "status": "sent",
    })
    service._send_opt_in_confirmation = MagicMock()
    service._schedule_auto_reply = MagicMock()
    service._emit_sms_event = MagicMock()
    return service


# ── Helper factories ────────────────────────────────────────────────

def _make_config(**overrides):
    """Create a mock SMSChannelConfig with sensible defaults."""
    defaults = {
        "id": "cfg-001",
        "company_id": "comp-sms-day1-001",
        "is_enabled": True,
        "auto_create_ticket": True,
        "char_limit": 1600,
        "max_outbound_per_hour": 5,
        "max_outbound_per_day": 50,
        "opt_out_keywords": "STOP,STOPALL,UNSUBSCRIBE,CANCEL,QUIT,END",
        "opt_in_keywords": "START,YES,UNSTOP,CONTINUE",
        "opt_out_response": "You have been opted out. Reply START to resume.",
        "auto_reply_enabled": False,
        "auto_reply_message": "Thanks for your message!",
        "auto_reply_delay_seconds": 10,
        "twilio_account_sid": "ACtest123",
        "twilio_auth_token_encrypted": "dGVzdC1hdXRoLXRva2Vu",
        "twilio_phone_number": "+12345678901",
        "after_hours_message": None,
        "business_hours_json": "{}",
    }
    defaults.update(overrides)
    cfg = MagicMock()
    for k, v in defaults.items():
        setattr(cfg, k, v)
    cfg.to_dict = MagicMock(return_value=defaults)
    return cfg


def _make_conversation(**overrides):
    """Create a mock SMSConversation with sensible defaults."""
    defaults = {
        "id": "conv-001",
        "company_id": "comp-sms-day1-001",
        "customer_number": "+15551234567",
        "twilio_number": "+12345678901",
        "ticket_id": None,
        "customer_id": None,
        "message_count": 0,
        "last_message_at": None,
        "is_opted_out": False,
        "opt_out_keyword": None,
        "opt_out_at": None,
    }
    defaults.update(overrides)
    conv = MagicMock()
    for k, v in defaults.items():
        setattr(conv, k, v)
    conv.to_dict = MagicMock(return_value=defaults)
    return conv


def _make_message(**overrides):
    """Create a mock SMSMessage with sensible defaults."""
    defaults = {
        "id": "msg-001",
        "company_id": "comp-sms-day1-001",
        "conversation_id": "conv-001",
        "direction": "inbound",
        "from_number": "+15551234567",
        "to_number": "+12345678901",
        "body": "Hello",
        "num_segments": 1,
        "char_count": 5,
        "twilio_message_sid": "SM-msg-001",
        "twilio_account_sid": "ACtest123",
        "twilio_status": "receiving",
        "twilio_error_code": None,
        "twilio_error_message": None,
        "ticket_id": None,
        "sender_id": None,
        "sender_role": "visitor",
        "delivered_at": None,
        "created_at": datetime.utcnow(),
    }
    defaults.update(overrides)
    msg = MagicMock()
    for k, v in defaults.items():
        setattr(msg, k, v)
    msg.to_dict = MagicMock(return_value=defaults)
    return msg


def _inbound_sms_data(**overrides):
    """Create a typical inbound SMS data dict."""
    defaults = {
        "message_sid": "SM-inbound-001",
        "account_sid": "ACtest123",
        "from_number": "+15551234567",
        "to_number": "+12345678901",
        "body": "I need help with my order",
        "num_segments": 1,
    }
    defaults.update(overrides)
    return defaults


# ═══════════════════════════════════════════════════════════════════════
# 1. TestProcessInboundSMS
# ═══════════════════════════════════════════════════════════════════════

class TestProcessInboundSMS:
    """Full pipeline tests for inbound SMS processing."""

    def test_full_pipeline_success(self, sms_service, mock_db, company_id):
        """Full pipeline: config → conversation → TCPA → idempotency → store → ticket."""
        config = _make_config()
        conv = _make_conversation()
        msg = _make_message()

        def _refresh(obj):
            obj.id = "msg-new-001"

        mock_db.refresh = MagicMock(side_effect=_refresh)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value="ticket-001"), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg), \
             patch.object(sms_service, "_schedule_auto_reply"):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert result["status"] == "processed"
        assert result["message_id"] == "msg-new-001"
        assert result["conversation_id"] == "conv-001"
        assert result["ticket_id"] == "ticket-001"
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_returns_error_when_no_sms_config(self, sms_service, company_id):
        """Returns error when no SMS config exists for company."""
        with patch.object(sms_service, "get_sms_config", return_value=None):
            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert result["status"] == "error"
        assert "not configured" in result["error"]

    def test_returns_error_when_sms_disabled(self, sms_service, company_id):
        """Returns error when SMS channel is disabled."""
        config = _make_config(is_enabled=False)

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert result["status"] == "error"
        assert "disabled" in result["error"]

    def test_returns_error_for_invalid_from_number(self, sms_service, company_id):
        """Returns error when from_number cannot be normalized."""
        config = _make_config()

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(from_number="NOT_A_PHONE"),
            )

        assert result["status"] == "error"
        assert "Invalid phone number" in result["error"]

    def test_returns_error_for_invalid_to_number(self, sms_service, company_id):
        """Returns error when to_number cannot be normalized."""
        config = _make_config()

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(to_number="xyz"),
            )

        assert result["status"] == "error"
        assert "Invalid phone number" in result["error"]

    def test_creates_conversation_when_none_exists(self, sms_service, mock_db, company_id):
        """Creates a new conversation if no existing one is found."""
        config = _make_config()
        new_conv = _make_conversation(id="conv-new-001")
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=new_conv) as mock_get_or_create, \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

            assert result["status"] == "processed"
            mock_get_or_create.assert_called_once_with(
                company_id=company_id,
                customer_number="+15551234567",
                twilio_number="+12345678901",
            )

    def test_ignores_messages_from_opted_out_number(self, sms_service, company_id):
        """BC-010: Messages from opted-out numbers are silently ignored."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=True)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="Please help me"),
            )

        assert result["status"] == "opted_out_ignored"
        assert result["conversation_id"] == "conv-001"

    def test_handles_opt_in_keyword_from_opted_out_number(self, sms_service, mock_db, company_id):
        """BC-010: START keyword from opted-out number opts them back in."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=True)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_send_opt_in_confirmation") as mock_confirm:

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="START"),
            )

        assert result["status"] == "opted_in"
        assert conv.is_opted_out is False
        assert conv.opt_out_keyword is None
        assert conv.opt_out_at is None
        mock_db.commit.assert_called()
        mock_confirm.assert_called_once()

    def test_handles_unstop_keyword_opt_in(self, sms_service, mock_db, company_id):
        """BC-010: UNSTOP keyword also opts back in from opted-out state."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=True)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_send_opt_in_confirmation"):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="UNSTOP"),
            )

        assert result["status"] == "opted_in"
        assert conv.is_opted_out is False

    def test_handles_opt_out_keyword_stop(self, sms_service, mock_db, company_id):
        """BC-010: STOP keyword marks conversation as opted_out."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=False)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_send_sms_via_twilio") as mock_twilio:

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="STOP"),
            )

        assert result["status"] == "opted_out"
        assert conv.is_opted_out is True
        assert conv.opt_out_keyword == "stop"
        assert conv.opt_out_at is not None
        mock_db.commit.assert_called()
        # TCPA requires sending opt-out confirmation
        mock_twilio.assert_called_once_with(
            config=config,
            to_number="+15551234567",
            body=config.opt_out_response,
        )

    def test_handles_opt_out_keyword_cancel(self, sms_service, mock_db, company_id):
        """BC-010: CANCEL keyword triggers opt-out."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=False)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_send_sms_via_twilio"):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="CANCEL"),
            )

        assert result["status"] == "opted_out"
        assert conv.opt_out_keyword == "cancel"

    def test_handles_opt_out_keyword_end(self, sms_service, mock_db, company_id):
        """BC-010: END keyword triggers opt-out."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=False)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_send_sms_via_twilio"):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="END"),
            )

        assert result["status"] == "opted_out"
        assert conv.opt_out_keyword == "end"

    def test_opt_out_keyword_case_insensitive(self, sms_service, mock_db, company_id):
        """BC-010: Opt-out keywords are case-insensitive."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=False)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_send_sms_via_twilio"):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="Unsubscribe"),
            )

        assert result["status"] == "opted_out"
        assert conv.opt_out_keyword == "unsubscribe"

    def test_already_opted_in_keyword_when_not_opted_out(self, sms_service, company_id):
        """START keyword from non-opted-out number returns already_opted_in."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=False)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="START"),
            )

        assert result["status"] == "already_opted_in"
        assert result["conversation_id"] == "conv-001"

    def test_idempotency_check_via_twilio_message_sid(self, sms_service, company_id):
        """BC-003: Duplicate Twilio MessageSid is skipped."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=False)
        existing_msg = _make_message(
            id="msg-existing-001",
            conversation_id="conv-001",
            ticket_id="ticket-existing-001",
        )

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=existing_msg):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(message_sid="SM-duplicate-sid"),
            )

        assert result["status"] == "skipped_duplicate"
        assert result["message_id"] == "msg-existing-001"
        assert result["conversation_id"] == "conv-001"
        assert result["ticket_id"] == "ticket-existing-001"

    def test_idempotency_not_triggered_when_no_message_sid(self, sms_service, company_id):
        """BC-003: No MessageSid → no idempotency check, process normally."""
        config = _make_config()
        conv = _make_conversation()
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(message_sid=""),
            )

        assert result["status"] == "processed"

    def test_rate_limit_check_for_inbound(self, sms_service, company_id):
        """BC-006: Inbound flood protection triggers rate_limited status."""
        config = _make_config()
        conv = _make_conversation()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit",
                         return_value="BC-006: Inbound rate limit exceeded (100/100 per hour)"):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert result["status"] == "rate_limited"
        assert "BC-006" in result["error"]

    def test_stores_sms_message_with_correct_fields(self, sms_service, mock_db, company_id):
        """Stored SMSMessage has correct direction, from/to, twilio_status, etc."""
        config = _make_config()
        conv = _make_conversation()
        captured_kwargs = {}

        # Intercept SMSMessage constructor
        def capture_sms_message(**kwargs):
            captured_kwargs.update(kwargs)
            msg = _make_message()
            for k, v in kwargs.items():
                setattr(msg, k, v)
            return msg

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage",
                   side_effect=capture_sms_message):

            sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert captured_kwargs["direction"] == "inbound"
        assert captured_kwargs["from_number"] == "+15551234567"
        assert captured_kwargs["to_number"] == "+12345678901"
        assert captured_kwargs["twilio_message_sid"] == "SM-inbound-001"
        assert captured_kwargs["twilio_status"] == "receiving"
        assert captured_kwargs["sender_role"] == "visitor"
        assert captured_kwargs["company_id"] == company_id

    def test_links_to_existing_ticket(self, sms_service, mock_db, company_id):
        """If conversation has ticket_id, links to existing ticket."""
        config = _make_config()
        conv = _make_conversation(ticket_id="ticket-existing-001")
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value="ticket-existing-001"), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert result["ticket_id"] == "ticket-existing-001"

    def test_creates_new_ticket_when_none_exists(self, sms_service, mock_db, company_id):
        """If no ticket and auto_create_ticket=True, creates new ticket."""
        config = _make_config(auto_create_ticket=True)
        conv = _make_conversation(ticket_id=None)
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value="ticket-new-001"), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert result["ticket_id"] == "ticket-new-001"

    def test_no_ticket_when_auto_create_disabled(self, sms_service, mock_db, company_id):
        """If auto_create_ticket=False and no existing ticket, ticket_id is None."""
        config = _make_config(auto_create_ticket=False)
        conv = _make_conversation(ticket_id=None)
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert result["ticket_id"] is None

    def test_schedules_auto_reply_if_configured(self, sms_service, mock_db, company_id):
        """Schedules auto-reply when auto_reply_enabled and no ticket exists."""
        config = _make_config(auto_reply_enabled=True)
        conv = _make_conversation(ticket_id=None)
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg), \
             patch.object(sms_service, "_schedule_auto_reply") as mock_schedule:

            sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        mock_schedule.assert_called_once()

    def test_no_auto_reply_when_ticket_exists(self, sms_service, mock_db, company_id):
        """No auto-reply when a ticket is linked (agent will respond)."""
        config = _make_config(auto_reply_enabled=True)
        conv = _make_conversation(ticket_id="ticket-001")
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value="ticket-001"), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg), \
             patch.object(sms_service, "_schedule_auto_reply") as mock_schedule:

            sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        mock_schedule.assert_not_called()

    def test_body_truncated_to_char_limit(self, sms_service, mock_db, company_id):
        """Inbound body is truncated when exceeding char_limit."""
        config = _make_config(char_limit=10)
        conv = _make_conversation()
        captured_kwargs = {}

        def capture_sms_message(**kwargs):
            captured_kwargs.update(kwargs)
            return _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage",
                   side_effect=capture_sms_message):

            sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(body="A" * 50),
            )

        assert len(captured_kwargs["body"]) == 10
        assert captured_kwargs["char_count"] == 10

    def test_conversation_message_count_incremented(self, sms_service, mock_db, company_id):
        """Conversation message_count is incremented after processing."""
        config = _make_config()
        conv = _make_conversation(message_count=5)
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
             patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
             patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_link_to_ticket", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            sms_service.process_inbound_sms(
                company_id, _inbound_sms_data(),
            )

        assert conv.message_count == 6


# ═══════════════════════════════════════════════════════════════════════
# 2. TestSendSMS
# ═══════════════════════════════════════════════════════════════════════

class TestSendSMS:
    """Tests for outbound SMS sending via Twilio."""

    def test_sends_outbound_sms_via_twilio(self, sms_service, mock_db, company_id):
        """Successfully sends outbound SMS and stores in DB."""
        config = _make_config()
        conv = _make_conversation()
        msg = _make_message(direction="outbound")

        def _refresh(obj):
            obj.id = "msg-out-001"

        mock_db.refresh = MagicMock(side_effect=_refresh)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
             patch.object(sms_service, "_check_outbound_rate_limit", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello from support",
                sender_id="agent-001",
                sender_role="agent",
            )

        assert result["status"] == "sent"
        assert result["twilio_message_sid"] == "SM-twilio-mock-001"
        assert result["direction"] == "outbound"
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_returns_error_when_no_config(self, sms_service, company_id):
        """Returns error when no SMS config exists."""
        with patch.object(sms_service, "get_sms_config", return_value=None):
            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "not configured" in result["error"]

    def test_returns_error_when_disabled(self, sms_service, company_id):
        """Returns error when SMS channel is disabled."""
        config = _make_config(is_enabled=False)

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "disabled" in result["error"]

    def test_validates_phone_number_format(self, sms_service, company_id):
        """Returns error for invalid recipient phone number."""
        config = _make_config()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value=""):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="invalid-phone",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "Invalid recipient phone number" in result["error"]

    def test_respects_opt_out_status_tcpa(self, sms_service, company_id):
        """BC-010: Cannot send to opted-out recipient."""
        config = _make_config()
        conv = _make_conversation(is_opted_out=True)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "opted out" in result["error"]
        assert "BC-010" in result["error"]

    def test_rate_limit_hourly(self, sms_service, company_id):
        """BC-006: Hourly outbound rate limit is enforced."""
        config = _make_config()
        conv = _make_conversation()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
             patch.object(sms_service, "_check_outbound_rate_limit",
                         return_value="BC-006: Hourly outbound limit exceeded (5/5)"):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "BC-006" in result["error"]

    def test_rate_limit_daily(self, sms_service, company_id):
        """BC-006: Daily outbound rate limit is enforced."""
        config = _make_config()
        conv = _make_conversation()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
             patch.object(sms_service, "_check_outbound_rate_limit",
                         return_value="BC-006: Daily outbound limit exceeded (50/50)"):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "Daily" in result["error"]

    def test_truncates_body_to_char_limit(self, sms_service, mock_db, company_id):
        """Body is truncated when exceeding char_limit."""
        config = _make_config(char_limit=20)
        conv = _make_conversation()
        captured_kwargs = {}

        def capture_sms_message(**kwargs):
            captured_kwargs.update(kwargs)
            return _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
             patch.object(sms_service, "_check_outbound_rate_limit", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage",
                   side_effect=capture_sms_message):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="A" * 100,
            )

        assert result["status"] == "sent"
        assert len(result["body"]) == 20
        assert captured_kwargs["char_count"] == 20

    def test_stores_outbound_message_in_db(self, sms_service, mock_db, company_id):
        """Outbound message is stored in DB with correct fields."""
        config = _make_config()
        conv = _make_conversation()
        captured_kwargs = {}

        def capture_sms_message(**kwargs):
            captured_kwargs.update(kwargs)
            return _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
             patch.object(sms_service, "_check_outbound_rate_limit", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage",
                   side_effect=capture_sms_message):

            sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
                sender_id="agent-007",
                sender_role="agent",
                ticket_id="ticket-001",
            )

        assert captured_kwargs["direction"] == "outbound"
        assert captured_kwargs["from_number"] == config.twilio_phone_number
        assert captured_kwargs["to_number"] == "+15551234567"
        assert captured_kwargs["twilio_status"] == "sent"
        assert captured_kwargs["sender_id"] == "agent-007"
        assert captured_kwargs["sender_role"] == "agent"
        assert captured_kwargs["ticket_id"] == "ticket-001"
        mock_db.add.assert_called()

    def test_returns_twilio_message_sid(self, sms_service, mock_db, company_id):
        """Returns twilio_message_sid from Twilio response."""
        config = _make_config()
        conv = _make_conversation()
        msg = _make_message()

        sms_service._send_sms_via_twilio = MagicMock(return_value={
            "success": True, "message_sid": "SM-unique-sid-999", "status": "sent",
        })

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
             patch.object(sms_service, "_check_outbound_rate_limit", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["twilio_message_sid"] == "SM-unique-sid-999"

    def test_twilio_send_failure_returns_error(self, sms_service, company_id):
        """Returns error when Twilio send fails."""
        config = _make_config()
        conv = _make_conversation()

        sms_service._send_sms_via_twilio = MagicMock(return_value={
            "success": False, "error": "Twilio API error: 21211",
        })

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
             patch.object(sms_service, "_check_outbound_rate_limit", return_value=None):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "Twilio API error" in result["error"]

    def test_creates_conversation_if_none_exists(self, sms_service, mock_db, company_id):
        """If no conversation found, creates one for outbound."""
        config = _make_config()
        new_conv = _make_conversation(id="conv-new-002")
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "_get_conversation_by_numbers", return_value=None), \
             patch.object(sms_service, "_check_outbound_rate_limit", return_value=None), \
             patch.object(sms_service, "_get_or_create_conversation", return_value=new_conv) as mock_get_or_create, \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

            assert result["status"] == "sent"
            mock_get_or_create.assert_called_once()

    def test_uses_conversation_id_when_provided(self, sms_service, mock_db, company_id):
        """When conversation_id is provided, uses get_conversation instead."""
        config = _make_config()
        conv = _make_conversation(id="conv-specific-001")
        msg = _make_message()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
             patch.object(sms_service, "get_conversation", return_value=conv) as mock_get_conv, \
             patch.object(sms_service, "_check_outbound_rate_limit", return_value=None), \
             patch("app.services.sms_channel_service.SMSMessage", return_value=msg):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
                conversation_id="conv-specific-001",
            )

            assert result["status"] == "sent"
            mock_get_conv.assert_called_once_with(
                "conv-specific-001", company_id,
            )


# ═══════════════════════════════════════════════════════════════════════
# 3. TestUpdateDeliveryStatus
# ═══════════════════════════════════════════════════════════════════════

class TestUpdateDeliveryStatus:
    """Tests for Twilio delivery status callbacks."""

    def test_updates_twilio_status(self, sms_service, mock_db, company_id):
        """Updates twilio_status field on message."""
        mock_msg = _make_message(twilio_status="sent")

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_msg)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.update_delivery_status(
            company_id=company_id,
            message_sid="SM-msg-001",
            status="delivered",
        )

        assert result["status"] == "updated"
        assert mock_msg.twilio_status == "delivered"
        mock_db.commit.assert_called()

    def test_sets_delivered_at_when_status_delivered(self, sms_service, mock_db, company_id):
        """Sets delivered_at timestamp when status is 'delivered'."""
        mock_msg = _make_message(twilio_status="sent", delivered_at=None)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_msg)
        mock_db.query = MagicMock(return_value=mock_query)

        sms_service.update_delivery_status(
            company_id=company_id,
            message_sid="SM-msg-001",
            status="delivered",
        )

        assert mock_msg.delivered_at is not None
        assert isinstance(mock_msg.delivered_at, datetime)

    def test_does_not_set_delivered_at_for_other_status(self, sms_service, mock_db, company_id):
        """Does not set delivered_at for non-delivered status."""
        mock_msg = _make_message(twilio_status="sent", delivered_at=None)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_msg)
        mock_db.query = MagicMock(return_value=mock_query)

        sms_service.update_delivery_status(
            company_id=company_id,
            message_sid="SM-msg-001",
            status="undelivered",
        )

        assert mock_msg.delivered_at is None

    def test_sets_error_code_and_message_on_failure(self, sms_service, mock_db, company_id):
        """Sets error_code and error_message on failed delivery."""
        mock_msg = _make_message()

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_msg)
        mock_db.query = MagicMock(return_value=mock_query)

        sms_service.update_delivery_status(
            company_id=company_id,
            message_sid="SM-msg-001",
            status="failed",
            error_code=21211,
            error_message="Invalid 'To' phone number",
        )

        assert mock_msg.twilio_error_code == 21211
        assert mock_msg.twilio_error_message == "Invalid 'To' phone number"

    def test_returns_not_found_for_unknown_message_sid(self, sms_service, mock_db, company_id):
        """Returns not_found when no message matches the sid."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.update_delivery_status(
            company_id=company_id,
            message_sid="SM-nonexistent",
            status="delivered",
        )

        assert result["status"] == "not_found"


# ═══════════════════════════════════════════════════════════════════════
# 4. TestConversationManagement
# ═══════════════════════════════════════════════════════════════════════

class TestConversationManagement:
    """Tests for conversation retrieval and listing."""

    def test_get_conversation_with_company_id_isolation(self, sms_service, mock_db, company_id):
        """BC-001: get_conversation filters by both id and company_id."""
        conv = _make_conversation()
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=conv)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_conversation("conv-001", company_id)

        assert result is conv
        # Verify filter was called (company_id isolation)
        mock_db.query.assert_called_once()
        mock_query.filter.assert_called()

    def test_get_conversation_returns_none_for_wrong_company(self, sms_service, mock_db):
        """BC-001: get_conversation returns None if company_id doesn't match."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_conversation("conv-001", "different-company-id")

        assert result is None

    def test_list_conversations_with_pagination(self, sms_service, mock_db, company_id):
        """list_conversations returns paginated results."""
        from database.models.sms_channel import SMSConversation as SMSConvModel
        conv1 = _make_conversation(id="conv-001")
        conv2 = _make_conversation(id="conv-002")

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.count = MagicMock(return_value=25)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.offset = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[conv1, conv2])
        mock_db.query = MagicMock(return_value=mock_query)

        # Ensure SMSConversation.updated_at has a .desc() method for order_by
        SMSConvModel.updated_at = MagicMock()
        SMSConvModel.updated_at.desc = MagicMock(return_value="updated_at_desc")

        result = sms_service.list_conversations(
            company_id=company_id, page=2, page_size=10,
        )

        assert result["total"] == 25
        assert result["page"] == 2
        assert result["page_size"] == 10
        assert result["total_pages"] == 3  # ceil(25/10)
        assert len(result["items"]) == 2

    def test_list_conversations_filter_by_is_opted_out(self, sms_service, mock_db, company_id):
        """list_conversations filters by is_opted_out when specified."""
        from database.models.sms_channel import SMSConversation as SMSConvModel
        conv = _make_conversation(is_opted_out=True)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.count = MagicMock(return_value=1)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.offset = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[conv])
        mock_db.query = MagicMock(return_value=mock_query)

        # Ensure SMSConversation.updated_at has a .desc() method for order_by
        SMSConvModel.updated_at = MagicMock()
        SMSConvModel.updated_at.desc = MagicMock(return_value="updated_at_desc")

        result = sms_service.list_conversations(
            company_id=company_id, is_opted_out=True,
        )

        assert result["total"] == 1
        # filter should have been called twice (company_id + is_opted_out)
        assert mock_query.filter.call_count == 2

    def test_list_conversations_no_opt_out_filter(self, sms_service, mock_db, company_id):
        """list_conversations without is_opted_out filter returns all."""
        from database.models.sms_channel import SMSConversation as SMSConvModel
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.count = MagicMock(return_value=10)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.offset = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query = MagicMock(return_value=mock_query)

        # Ensure SMSConversation.updated_at has a .desc() method for order_by
        SMSConvModel.updated_at = MagicMock()
        SMSConvModel.updated_at.desc = MagicMock(return_value="updated_at_desc")

        result = sms_service.list_conversations(
            company_id=company_id, is_opted_out=None,
        )

        # Only one filter call (company_id)
        assert mock_query.filter.call_count == 1


# ═══════════════════════════════════════════════════════════════════════
# 5. TestSMSConfigManagement
# ═══════════════════════════════════════════════════════════════════════

class TestSMSConfigManagement:
    """Tests for SMS channel configuration CRUD."""

    def test_get_sms_config_returns_config_for_company(self, sms_service, mock_db, company_id):
        """get_sms_config returns the config for the given company_id."""
        config = _make_config()

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=config)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_sms_config(company_id)

        assert result is config
        mock_db.query.assert_called_once()

    def test_get_sms_config_returns_none_when_not_found(self, sms_service, mock_db, company_id):
        """get_sms_config returns None when no config exists."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_sms_config(company_id)

        assert result is None

    def test_create_sms_config_encrypts_auth_token(self, sms_service, mock_db, company_id):
        """BC-011: create_sms_config encrypts the auth_token."""
        with patch.object(sms_service, "get_sms_config", return_value=None), \
             patch.object(sms_service, "_encrypt_credential",
                         return_value="ENC:encrypted_token") as mock_encrypt, \
             patch("app.services.sms_channel_service.SMSChannelConfig") as MockConfig:

            mock_config_instance = MagicMock()
            mock_config_instance.to_dict.return_value = {"id": "cfg-new"}
            MockConfig.return_value = mock_config_instance

            result = sms_service.create_sms_config(company_id, {
                "twilio_account_sid": "ACnew123",
                "twilio_auth_token": "my-plaintext-token",
                "twilio_phone_number": "+19876543210",
            })

        assert result["status"] == "created"
        mock_encrypt.assert_called_once_with("my-plaintext-token")
        # Verify encrypted token passed to model constructor
        call_kwargs = MockConfig.call_args[1]
        assert call_kwargs["twilio_auth_token_encrypted"] == "ENC:encrypted_token"

    def test_create_sms_config_returns_error_if_already_exists(self, sms_service, company_id):
        """Cannot create config if one already exists for the company."""
        with patch.object(sms_service, "get_sms_config",
                         return_value=_make_config()):
            result = sms_service.create_sms_config(company_id, {
                "twilio_account_sid": "AC123",
                "twilio_auth_token": "tok",
                "twilio_phone_number": "+12345678901",
            })

        assert result["status"] == "error"
        assert "already exists" in result["error"]

    def test_update_sms_config_partial_update(self, sms_service, mock_db, company_id):
        """update_sms_config applies partial updates to allowed fields."""
        config = _make_config(char_limit=1600, max_outbound_per_hour=5)

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.update_sms_config(
                company_id, {"char_limit": 320, "max_outbound_per_hour": 10},
            )

        assert result["status"] == "updated"
        assert config.char_limit == 320
        assert config.max_outbound_per_hour == 10
        # Other fields unchanged
        assert config.is_enabled is True
        mock_db.commit.assert_called()

    def test_update_sms_config_encrypts_new_auth_token(self, sms_service, mock_db, company_id):
        """BC-011: update_sms_config encrypts new auth_token if provided."""
        config = _make_config()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
             patch.object(sms_service, "_encrypt_credential",
                         return_value="ENC:new-encrypted") as mock_encrypt:

            result = sms_service.update_sms_config(
                company_id, {"twilio_auth_token": "new-plain-token"},
            )

        assert result["status"] == "updated"
        mock_encrypt.assert_called_once_with("new-plain-token")
        assert config.twilio_auth_token_encrypted == "ENC:new-encrypted"

    def test_update_sms_config_ignores_none_values(self, sms_service, mock_db, company_id):
        """update_sms_config ignores fields with None values."""
        config = _make_config(char_limit=1600)

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.update_sms_config(
                company_id, {"char_limit": None, "max_outbound_per_hour": 20},
            )

        assert result["status"] == "updated"
        # char_limit should NOT have been changed to None
        assert config.char_limit == 1600
        assert config.max_outbound_per_hour == 20

    def test_update_sms_config_not_found(self, sms_service, company_id):
        """update_sms_config returns error when config not found."""
        with patch.object(sms_service, "get_sms_config", return_value=None):
            result = sms_service.update_sms_config(
                company_id, {"char_limit": 320},
            )

        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_delete_sms_config(self, sms_service, mock_db, company_id):
        """delete_sms_config removes config from DB."""
        config = _make_config()

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.delete_sms_config(company_id)

        assert result["status"] == "deleted"
        mock_db.delete.assert_called_once_with(config)
        mock_db.commit.assert_called()

    def test_delete_sms_config_not_found(self, sms_service, company_id):
        """delete_sms_config returns error when config not found."""
        with patch.object(sms_service, "get_sms_config", return_value=None):
            result = sms_service.delete_sms_config(company_id)

        assert result["status"] == "error"
        assert "not found" in result["error"]


# ═══════════════════════════════════════════════════════════════════════
# 6. TestTCPAConsentManagement (BC-010)
# ═══════════════════════════════════════════════════════════════════════

class TestTCPAConsentManagement:
    """Tests for TCPA compliance consent management (BC-010)."""

    def test_opt_out_number_marks_all_conversations(self, sms_service, mock_db, company_id):
        """opt_out_number marks all conversations for that number as opted_out."""
        conv1 = _make_conversation(id="conv-001", is_opted_out=False)
        conv2 = _make_conversation(id="conv-002", is_opted_out=False)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[conv1, conv2])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.opt_out_number(
            company_id, "+15551234567", keyword="agent_manual",
        )

        assert result["status"] == "opted_out"
        assert result["conversations_affected"] == 2
        assert conv1.is_opted_out is True
        assert conv2.is_opted_out is True
        assert conv1.opt_out_keyword == "agent_manual"
        assert conv1.opt_out_at is not None
        mock_db.commit.assert_called()

    def test_opt_out_number_no_conversations(self, sms_service, mock_db, company_id):
        """opt_out_number with no matching conversations returns count 0."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.opt_out_number(
            company_id, "+15559999999",
        )

        assert result["status"] == "opted_out"
        assert result["conversations_affected"] == 0
        mock_db.commit.assert_not_called()

    def test_opt_in_number_clears_opt_out_status(self, sms_service, mock_db, company_id):
        """opt_in_number clears is_opted_out, opt_out_keyword, opt_out_at."""
        conv1 = _make_conversation(id="conv-001", is_opted_out=True, opt_out_keyword="stop", opt_out_at=datetime.utcnow())
        conv2 = _make_conversation(id="conv-002", is_opted_out=True, opt_out_keyword="cancel", opt_out_at=datetime.utcnow())

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[conv1, conv2])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.opt_in_number(company_id, "+15551234567")

        assert result["status"] == "opted_in"
        assert result["conversations_affected"] == 2
        assert conv1.is_opted_out is False
        assert conv1.opt_out_keyword is None
        assert conv1.opt_out_at is None
        assert conv2.is_opted_out is False
        mock_db.commit.assert_called()

    def test_opt_in_number_only_affects_opted_out(self, sms_service, mock_db, company_id):
        """opt_in_number only queries conversations where is_opted_out=True."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.opt_in_number(company_id, "+15551234567")

        assert result["conversations_affected"] == 0

    def test_get_consent_status_opted_in(self, sms_service, mock_db, company_id):
        """get_consent_status returns opted_in when no conversations opted out."""
        conv = _make_conversation(is_opted_out=False, opt_out_at=None)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[conv])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_consent_status(company_id, "+15551234567")

        assert result["status"] == "opted_in"
        assert result["is_opted_out"] is False
        assert result["conversation_count"] == 1

    def test_get_consent_status_opted_out(self, sms_service, mock_db, company_id):
        """get_consent_status returns opted_out when conversations are opted out."""
        opt_out_time = datetime(2025, 1, 15, 10, 30, 0)
        conv = _make_conversation(is_opted_out=True, opt_out_keyword="stop", opt_out_at=opt_out_time)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[conv])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_consent_status(company_id, "+15551234567")

        assert result["status"] == "opted_out"
        assert result["is_opted_out"] is True
        assert result["last_opt_out"] is not None
        assert result["last_opt_out"]["keyword"] == "stop"

    def test_get_consent_status_unknown_number(self, sms_service, mock_db, company_id):
        """get_consent_status returns 'unknown' for number with no conversations."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_consent_status(company_id, "+15550000000")

        assert result["status"] == "unknown"
        assert result["is_opted_out"] is False
        assert result["customer_number"] == "+15550000000"


# ═══════════════════════════════════════════════════════════════════════
# 7. TestPhoneNormalization
# ═══════════════════════════════════════════════════════════════════════

class TestPhoneNormalization:
    """Tests for E.164 phone number normalization."""

    def test_valid_e164_format(self, sms_service):
        """Valid E.164 format passes through unchanged."""
        assert sms_service._normalize_phone("+15551234567") == "+15551234567"

    def test_valid_e164_international(self, sms_service):
        """International E.164 format is preserved."""
        assert sms_service._normalize_phone("+447911123456") == "+447911123456"

    def test_us_number_normalization_10_digit(self, sms_service):
        """10-digit US number gets +1 prefix."""
        assert sms_service._normalize_phone("5551234567") == "+15551234567"

    def test_us_number_normalization_11_digit(self, sms_service):
        """11-digit US number with leading 1 gets + prefix."""
        assert sms_service._normalize_phone("15551234567") == "+15551234567"

    def test_strips_spaces(self, sms_service):
        """Spaces are stripped from phone numbers."""
        assert sms_service._normalize_phone("+1 555 123 4567") == "+15551234567"

    def test_strips_dashes(self, sms_service):
        """Dashes are stripped from phone numbers."""
        assert sms_service._normalize_phone("+1-555-123-4567") == "+15551234567"

    def test_strips_parens(self, sms_service):
        """Parentheses are stripped from phone numbers."""
        assert sms_service._normalize_phone("+1 (555) 123-4567") == "+15551234567"

    def test_strips_dots(self, sms_service):
        """Dots are stripped from phone numbers."""
        assert sms_service._normalize_phone("+1.555.123.4567") == "+15551234567"

    def test_strips_all_formatting(self, sms_service):
        """All formatting characters stripped simultaneously."""
        assert sms_service._normalize_phone("+1 (555) 123-45.67") == "+15551234567"

    def test_invalid_numbers_return_empty_string(self, sms_service):
        """Invalid phone numbers that can't be normalized return empty string."""
        result = sms_service._normalize_phone("abc123def")
        assert result == ""

    def test_too_short_number_returns_empty(self, sms_service):
        """Too-short digit-only number returns empty string."""
        result = sms_service._normalize_phone("12345")
        assert result == ""

    def test_empty_string_returns_empty(self, sms_service):
        """Empty string returns empty string."""
        assert sms_service._normalize_phone("") == ""

    def test_none_like_empty(self, sms_service):
        """Falsy input returns empty string."""
        assert sms_service._normalize_phone("") == ""

    def test_e164_plus_with_short_digits(self, sms_service):
        """E.164 with + prefix but too short may still pass if format matches."""
        # The pattern is ^\+[1-9]\d{1,14}$ — so +12 should match (2 digits total after +)
        result = sms_service._normalize_phone("+12")
        assert result == "+12"  # valid E.164 (minimum length)

    def test_e164_plus_zero_start_invalid(self, sms_service):
        """E.164 with +0 prefix is not valid E.164 but service fallback returns it.

        The service code's E164_PATTERN requires +[1-9], so +0... fails regex.
        However, the fallback `return cleaned if cleaned.startswith('+') else ''`
        still returns the +0 number. This test documents the current behavior.
        """
        result = sms_service._normalize_phone("+0123456789")
        # Current behavior: returns the cleaned string because it starts with '+',
        # even though it's not valid E.164. This is a known edge case.
        assert result == "+0123456789"


# ═══════════════════════════════════════════════════════════════════════
# 8. TestRateLimiting (BC-006)
# ═══════════════════════════════════════════════════════════════════════

class TestRateLimiting:
    """Tests for BC-006 rate limiting on outbound and inbound SMS."""

    def test_hourly_outbound_limit_ok(self, sms_service, mock_db, company_id):
        """Hourly outbound count below limit returns None (no error)."""
        config = _make_config(max_outbound_per_hour=5)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.scalar = MagicMock(return_value=3)  # below hourly limit
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_outbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is None

    def test_hourly_outbound_limit_exceeded(self, sms_service, mock_db, company_id):
        """Hourly outbound count at limit returns error message."""
        config = _make_config(max_outbound_per_hour=5)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.scalar = MagicMock(return_value=5)  # at hourly limit
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_outbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is not None
        assert "BC-006" in result
        assert "Hourly" in result
        assert "5/5" in result

    def test_daily_outbound_limit_ok(self, sms_service, mock_db, company_id):
        """Daily outbound count below limit returns None."""
        config = _make_config(max_outbound_per_day=50)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        # First call: hourly count, second call: daily count
        mock_query.scalar = MagicMock(side_effect=[3, 30])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_outbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is None

    def test_daily_outbound_limit_exceeded(self, sms_service, mock_db, company_id):
        """Daily outbound count at limit returns error message."""
        config = _make_config(max_outbound_per_day=50)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        # hourly passes (3), daily exceeds (50)
        mock_query.scalar = MagicMock(side_effect=[3, 50])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_outbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is not None
        assert "BC-006" in result
        assert "Daily" in result
        assert "50/50" in result

    def test_hourly_checked_before_daily(self, sms_service, mock_db, company_id):
        """Hourly limit is checked first; if exceeded, daily is not checked."""
        config = _make_config(max_outbound_per_hour=5, max_outbound_per_day=50)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.scalar = MagicMock(return_value=5)  # hourly exceeded
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_outbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert "Hourly" in result
        # scalar should only have been called once (hourly check)
        assert mock_query.scalar.call_count == 1

    def test_inbound_rate_limit_ok(self, sms_service, mock_db, company_id):
        """Inbound count below 100/hour returns None."""
        config = _make_config()

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.scalar = MagicMock(return_value=50)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_inbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is None

    def test_inbound_rate_limit_exceeded(self, sms_service, mock_db, company_id):
        """Inbound count at 100/hour returns rate limit error."""
        config = _make_config()

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.scalar = MagicMock(return_value=100)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_inbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is not None
        assert "BC-006" in result
        assert "Inbound" in result
        assert "100/100" in result

    def test_inbound_rate_limit_scalar_returns_none(self, sms_service, mock_db, company_id):
        """Handles case where scalar() returns None (no messages found)."""
        config = _make_config()

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.scalar = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_inbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is None  # None from scalar treated as 0

    def test_outbound_rate_limit_scalar_returns_none(self, sms_service, mock_db, company_id):
        """Handles case where scalar() returns None for outbound check."""
        config = _make_config(max_outbound_per_hour=5, max_outbound_per_day=50)

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.scalar = MagicMock(side_effect=[None, None])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._check_outbound_rate_limit(
            company_id, "+15551234567", config,
        )

        assert result is None  # None treated as 0 for both checks


# ═══════════════════════════════════════════════════════════════════════
# 9. TestKeywordParsing
# ═══════════════════════════════════════════════════════════════════════

class TestKeywordParsing:
    """Tests for _parse_keywords helper method."""

    def test_parse_comma_separated_keywords(self, sms_service):
        """Comma-separated keywords are parsed to lowercase list."""
        result = sms_service._parse_keywords("STOP,CANCEL,QUIT")
        assert result == ["stop", "cancel", "quit"]

    def test_parse_keywords_with_spaces(self, sms_service):
        """Keywords with spaces around commas are trimmed."""
        result = sms_service._parse_keywords("STOP , CANCEL , QUIT")
        assert result == ["stop", "cancel", "quit"]

    def test_parse_keywords_empty_string(self, sms_service):
        """Empty string returns empty list."""
        result = sms_service._parse_keywords("")
        assert result == []

    def test_parse_keywords_none(self, sms_service):
        """None returns empty list."""
        result = sms_service._parse_keywords(None)
        assert result == []

    def test_parse_keywords_single(self, sms_service):
        """Single keyword returns list with one element."""
        result = sms_service._parse_keywords("STOP")
        assert result == ["stop"]

    def test_parse_keywords_strips_empty_entries(self, sms_service):
        """Trailing commas don't create empty entries."""
        result = sms_service._parse_keywords("STOP,,CANCEL,")
        assert result == ["stop", "cancel"]


# ═══════════════════════════════════════════════════════════════════════
# 10. TestCredentialEncryption (BC-011)
# ═══════════════════════════════════════════════════════════════════════

class TestCredentialEncryption:
    """Tests for BC-011 credential encryption at rest."""

    def test_encrypt_returns_string(self, sms_service):
        """Encryption returns a non-empty string."""
        result = sms_service._encrypt_credential("my-secret-token")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_encrypt_decrypt_roundtrip(self, sms_service):
        """Encrypt then decrypt returns original value."""
        original = "my-twilio-auth-token-12345"
        encrypted = sms_service._encrypt_credential(original)
        decrypted = sms_service._decrypt_credential(encrypted)
        assert decrypted == original

    def test_encrypt_empty_string(self, sms_service):
        """Encrypting empty string still works."""
        encrypted = sms_service._encrypt_credential("")
        decrypted = sms_service._decrypt_credential(encrypted)
        assert decrypted == ""

    def test_encrypt_different_inputs_different_outputs(self, sms_service):
        """Different inputs produce different encrypted outputs."""
        enc1 = sms_service._encrypt_credential("token-alpha")
        enc2 = sms_service._encrypt_credential("token-beta")
        assert enc1 != enc2

    def test_encrypted_value_not_equal_to_plaintext(self, sms_service):
        """Encrypted value is not equal to plaintext (obvious but important)."""
        plaintext = "super-secret-auth-token"
        encrypted = sms_service._encrypt_credential(plaintext)
        assert encrypted != plaintext


# ═══════════════════════════════════════════════════════════════════════
# 11. TestGetOrCreateConversation
# ═══════════════════════════════════════════════════════════════════════

class TestGetOrCreateConversation:
    """Tests for _get_or_create_conversation private method."""

    def test_returns_existing_conversation(self, sms_service, mock_db, company_id):
        """Returns existing conversation if found by phone pair."""
        existing_conv = _make_conversation()

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=existing_conv)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._get_or_create_conversation(
            company_id, "+15551234567", "+12345678901",
        )

        assert result is existing_conv
        mock_db.add.assert_not_called()  # no new conversation created

    def test_creates_new_conversation_when_none(self, sms_service, mock_db, company_id):
        """Creates new conversation when no match found."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        with patch("app.services.sms_channel_service.SMSConversation") as MockConv:
            new_conv = _make_conversation(id="conv-fresh")
            MockConv.return_value = new_conv

            result = sms_service._get_or_create_conversation(
                company_id, "+15551234567", "+12345678901",
            )

        assert result is new_conv
        mock_db.add.assert_called()
        mock_db.flush.assert_called()


# ═══════════════════════════════════════════════════════════════════════
# 12. TestGetMessageByTwilioSid
# ═══════════════════════════════════════════════════════════════════════

class TestGetMessageByTwilioSid:
    """Tests for _get_message_by_twilio_sid private method."""

    def test_returns_message_when_found(self, sms_service, mock_db):
        """Returns SMSMessage when sid matches."""
        msg = _make_message()

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=msg)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._get_message_by_twilio_sid("SM-found-001")

        assert result is msg

    def test_returns_none_when_not_found(self, sms_service, mock_db):
        """Returns None when no message matches the sid."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service._get_message_by_twilio_sid("SM-not-found")

        assert result is None

    def test_returns_none_for_empty_sid(self, sms_service, mock_db):
        """Returns None immediately for empty message_sid."""
        result = sms_service._get_message_by_twilio_sid("")

        assert result is None
        mock_db.query.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# 13. TestConstants
# ═══════════════════════════════════════════════════════════════════════

class TestConstants:
    """Verify service-level constants are correct."""

    def test_max_sms_body_length(self):
        """MAX_SMS_BODY_LENGTH should be 1600 (Twilio concat limit)."""
        from app.services.sms_channel_service import MAX_SMS_BODY_LENGTH
        assert MAX_SMS_BODY_LENGTH == 1600

    def test_default_opt_out_keywords(self):
        """Default opt-out keywords include STOP, CANCEL, etc."""
        from app.services.sms_channel_service import DEFAULT_OPT_OUT_KEYWORDS
        assert "stop" in DEFAULT_OPT_OUT_KEYWORDS
        assert "cancel" in DEFAULT_OPT_OUT_KEYWORDS
        assert "quit" in DEFAULT_OPT_OUT_KEYWORDS
        assert "end" in DEFAULT_OPT_OUT_KEYWORDS

    def test_default_opt_in_keywords(self):
        """Default opt-in keywords include START, YES, etc."""
        from app.services.sms_channel_service import DEFAULT_OPT_IN_KEYWORDS
        assert "start" in DEFAULT_OPT_IN_KEYWORDS
        assert "yes" in DEFAULT_OPT_IN_KEYWORDS
        assert "unstop" in DEFAULT_OPT_IN_KEYWORDS

    def test_rate_limit_windows(self):
        """Rate limit windows are 60 min (hourly) and 1440 min (daily)."""
        from app.services.sms_channel_service import RATE_LIMIT_HOUR_WINDOW, RATE_LIMIT_DAY_WINDOW
        assert RATE_LIMIT_HOUR_WINDOW == 60
        assert RATE_LIMIT_DAY_WINDOW == 1440
