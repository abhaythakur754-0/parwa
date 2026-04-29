"""
SMS Channel Service Tests — Week 13 Day 5 (F-123)

Tests for:
- Inbound SMS processing with idempotency (BC-003)
- Outbound SMS sending with rate limits (BC-006)
- TCPA opt-out/opt-in handling (BC-010)
- Conversation threading
- Delivery status updates
- Config management
- Phone number normalization
"""

import sys
import os
from unittest.mock import MagicMock, patch
import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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
def sms_service(mock_db):
    """Provide SMSChannelService with mocked dependencies."""
    from app.services.sms_channel_service import SMSChannelService
    service = SMSChannelService(mock_db)
    service._emit_sms_event = MagicMock()
    service._send_sms_via_twilio = MagicMock(return_value={
        "success": True, "message_sid": "SM-twilio-001", "status": "sent",
    })
    return service


def _mock_config(**overrides):
    """Create a mock SMS config."""
    config = {
        "is_enabled": True,
        "auto_create_ticket": True,
        "char_limit": 1600,
        "max_outbound_per_hour": 5,
        "max_outbound_per_day": 50,
        "opt_out_keywords": "STOP,STOPALL,UNSUBSCRIBE,CANCEL,QUIT,END",
        "opt_in_keywords": "START,YES,UNSTOP,CONTINUE",
        "opt_out_response": "You have been opted out. Reply START to resume.",
        "auto_reply_enabled": False,
        "auto_reply_message": "Thanks!",
        "auto_reply_delay_seconds": 10,
        "twilio_account_sid": "AC123",
        "twilio_auth_token_encrypted": "dGVzdA==",
        "twilio_phone_number": "+1234567890",
        "after_hours_message": None,
        "business_hours_json": "{}",
    }
    config.update(overrides)
    mock = MagicMock()
    for k, v in config.items():
        setattr(mock, k, v)
    return mock


def _mock_conversation(**overrides):
    """Create a mock SMS conversation."""
    conv = {
        "id": "conv-001",
        "company_id": "test-company-123",
        "customer_number": "+15551234567",
        "twilio_number": "+1234567890",
        "ticket_id": None,
        "customer_id": None,
        "message_count": 0,
        "last_message_at": None,
        "is_opted_out": False,
        "opt_out_keyword": None,
        "opt_out_at": None,
    }
    conv.update(overrides)
    mock = MagicMock()
    for k, v in conv.items():
        setattr(mock, k, v)
    return mock


# ═══════════════════════════════════════════════════════════
# Inbound SMS Tests
# ═══════════════════════════════════════════════════════════

class TestProcessInboundSMS:
    """Tests for inbound SMS processing."""

    def test_inbound_sms_success(self, sms_service, mock_db, company_id):
        """Test successful inbound SMS processing."""
        config = _mock_config()
        conv = _mock_conversation()

        mock_message = MagicMock()
        mock_message.id = "sms-msg-001"

        def _refresh(obj):
            obj.id = "sms-msg-001"

        mock_db.refresh = MagicMock(side_effect=_refresh)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
                patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
                patch.object(sms_service, "_check_inbound_rate_limit", return_value=None), \
                patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
                patch.object(sms_service, "_link_to_ticket", return_value=None), \
                patch("app.services.sms_channel_service.SMSMessage", return_value=mock_message), \
                patch.object(sms_service, "_schedule_auto_reply", return_value=None):

            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-inbound-001",
                "account_sid": "AC123",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "Hello, I need help",
                "num_segments": 1,
            })

        assert result["status"] == "processed"
        assert result["message_id"] == "sms-msg-001"

    def test_inbound_sms_no_config(self, sms_service, company_id):
        """Test inbound SMS when channel not configured."""
        with patch.object(sms_service, "get_sms_config", return_value=None):
            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-001",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "Hello",
            })

        assert result["status"] == "error"
        assert "not configured" in result["error"]

    def test_inbound_sms_disabled(self, sms_service, company_id):
        """Test inbound SMS when channel is disabled."""
        config = _mock_config(is_enabled=False)

        with patch.object(sms_service, "get_sms_config", return_value=config):
            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-001",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "Hello",
            })

        assert result["status"] == "error"
        assert "disabled" in result["error"]

    def test_inbound_sms_idempotency(self, sms_service, company_id):
        """Test BC-003: duplicate MessageSid is skipped."""
        config = _mock_config()
        conv = _mock_conversation()
        existing_msg = MagicMock()
        existing_msg.id = "sms-msg-000"
        existing_msg.conversation_id = "conv-001"
        existing_msg.ticket_id = "ticket-001"

        with patch.object(sms_service, "get_sms_config", return_value=config), \
            patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
            patch.object(sms_service, "_get_message_by_twilio_sid",
                         return_value=existing_msg):

            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-duplicate-001",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "Hello again",
            })

        assert result["status"] == "skipped_duplicate"
        assert result["message_id"] == "sms-msg-000"

    def test_inbound_sms_already_opted_out(self, sms_service, company_id):
        """Test BC-010: message from opted-out number."""
        config = _mock_config()
        conv = _mock_conversation(is_opted_out=True)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
                patch.object(sms_service, "_get_or_create_conversation", return_value=conv):

            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-optout-001",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "Please help",
            })

        assert result["status"] == "opted_out_ignored"


class TestOptOutOptIn:
    """Tests for TCPA opt-out/opt-in keyword handling (BC-010)."""

    def test_inbound_opt_out_keyword(self, sms_service, mock_db, company_id):
        """Test STOP keyword triggers opt-out."""
        config = _mock_config()
        conv = _mock_conversation(is_opted_out=False)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
                patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
                patch.object(sms_service, "_send_sms_via_twilio") as mock_twilio:

            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-stop-001",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "STOP",
            })

        assert result["status"] == "opted_out"
        assert conv.is_opted_out is True
        assert conv.opt_out_keyword == "stop"
        assert conv.opt_out_at is not None
        mock_twilio.assert_called_once()

    def test_inbound_opt_in_after_opt_out(
            self, sms_service, mock_db, company_id):
        """Test START keyword opts back in."""
        config = _mock_config()
        conv = _mock_conversation(is_opted_out=True)

        with patch.object(sms_service, "get_sms_config", return_value=config), \
                patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
                patch.object(sms_service, "_send_opt_in_confirmation") as mock_confirm:

            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-start-001",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "START",
            })

        assert result["status"] == "opted_in"
        assert conv.is_opted_out is False
        mock_confirm.assert_called_once()

    def test_inbound_rate_limited(self, sms_service, company_id):
        """Test BC-006 inbound rate limit."""
        config = _mock_config()
        conv = _mock_conversation()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
            patch.object(sms_service, "_get_or_create_conversation", return_value=conv), \
            patch.object(sms_service, "_get_message_by_twilio_sid", return_value=None), \
            patch.object(sms_service, "_check_inbound_rate_limit",
                         return_value="BC-006: Inbound rate limit exceeded"):

            result = sms_service.process_inbound_sms(company_id, {
                "message_sid": "SM-rate-001",
                "from_number": "+15551234567",
                "to_number": "+1234567890",
                "body": "Spam",
            })

        assert result["status"] == "rate_limited"


# ═══════════════════════════════════════════════════════════
# Outbound SMS Tests
# ═══════════════════════════════════════════════════════════

class TestSendSMS:
    """Tests for outbound SMS sending."""

    def test_send_sms_success(self, sms_service, mock_db, company_id):
        """Test successful outbound SMS."""
        config = _mock_config()
        conv = _mock_conversation()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
                patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
                patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
                patch.object(sms_service, "_check_outbound_rate_limit", return_value=None):

            mock_message = MagicMock()
            mock_message.id = "sms-out-001"
            sms_service.SMSMessage = MagicMock(return_value=mock_message)

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello from agent",
            )

        assert result["status"] == "sent"
        assert result["twilio_status"] == "sent"

    def test_send_sms_no_config(self, sms_service, company_id):
        """Test sending when no config exists."""
        with patch.object(sms_service, "get_sms_config", return_value=None):
            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "not configured" in result["error"]

    def test_send_sms_opted_out(self, sms_service, company_id):
        """Test BC-010: sending to opted-out number."""
        config = _mock_config()
        conv = _mock_conversation(is_opted_out=True)

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

    def test_send_sms_rate_limited(self, sms_service, company_id):
        """Test BC-006 outbound rate limit."""
        config = _mock_config()
        conv = _mock_conversation()

        with patch.object(sms_service, "get_sms_config", return_value=config), \
            patch.object(sms_service, "_normalize_phone", return_value="+15551234567"), \
            patch.object(sms_service, "_get_conversation_by_numbers", return_value=conv), \
            patch.object(sms_service, "_check_outbound_rate_limit",
                         return_value="BC-006: Hourly limit exceeded"):

            result = sms_service.send_sms(
                company_id=company_id,
                to_number="+15551234567",
                body="Hello",
            )

        assert result["status"] == "error"
        assert "BC-006" in result["error"]


# ═══════════════════════════════════════════════════════════
# Delivery Status Tests
# ═══════════════════════════════════════════════════════════

class TestDeliveryStatus:
    """Tests for delivery status updates."""

    def test_update_delivery_status_delivered(
            self, sms_service, mock_db, company_id):
        """Test successful delivery status update."""
        mock_message = MagicMock()
        mock_message.twilio_status = "sent"

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_message)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.update_delivery_status(
            company_id=company_id,
            message_sid="SM-status-001",
            status="delivered",
        )

        assert result["status"] == "updated"
        assert mock_message.twilio_status == "delivered"
        assert mock_message.delivered_at is not None

    def test_update_delivery_status_not_found(
            self, sms_service, mock_db, company_id):
        """Test status update for unknown message."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.update_delivery_status(
            company_id=company_id,
            message_sid="SM-unknown",
            status="delivered",
        )

        assert result["status"] == "not_found"


# ═══════════════════════════════════════════════════════════
# Config Management Tests
# ═══════════════════════════════════════════════════════════

class TestSMSConfig:
    """Tests for SMS config management."""

    def test_create_sms_config_success(self, sms_service, mock_db, company_id):
        """Test creating SMS config."""
        with patch.object(sms_service, "get_sms_config", return_value=None), \
                patch.object(sms_service, "_encrypt_credential", return_value="encrypted"):

            mock_config = MagicMock()
            mock_config.to_dict.return_value = {"id": "cfg-001"}
            sms_service.SMSChannelConfig = MagicMock(return_value=mock_config)

            result = sms_service.create_sms_config(company_id, {
                "twilio_account_sid": "AC123",
                "twilio_auth_token": "token123",
                "twilio_phone_number": "+1234567890",
            })

        assert result["status"] == "created"

    def test_create_sms_config_already_exists(self, sms_service, company_id):
        """Test creating config when one already exists."""
        with patch.object(sms_service, "get_sms_config",
                          return_value=MagicMock()):
            result = sms_service.create_sms_config(company_id, {
                "twilio_account_sid": "AC123",
                "twilio_auth_token": "token123",
                "twilio_phone_number": "+1234567890",
            })

        assert result["status"] == "error"
        assert "already exists" in result["error"]

    def test_update_sms_config(self, sms_service, mock_db, company_id):
        """Test updating SMS config."""
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {"max_outbound_per_hour": 10}

        with patch.object(sms_service, "get_sms_config", return_value=mock_config):
            result = sms_service.update_sms_config(
                company_id, {"max_outbound_per_hour": 10},
            )

        assert result["status"] == "updated"
        assert mock_config.max_outbound_per_hour == 10

    def test_delete_sms_config(self, sms_service, mock_db, company_id):
        """Test deleting SMS config."""
        mock_config = MagicMock()

        with patch.object(sms_service, "get_sms_config", return_value=mock_config):
            result = sms_service.delete_sms_config(company_id)

        assert result["status"] == "deleted"
        mock_db.delete.assert_called_once()


# ═══════════════════════════════════════════════════════════
# TCPA Consent Tests (BC-010)
# ═══════════════════════════════════════════════════════════

class TestTCPAConsent:
    """Tests for TCPA consent management."""

    def test_manual_opt_out(self, sms_service, mock_db, company_id):
        """Test manual opt-out by agent."""
        mock_conv = MagicMock()
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_conv])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.opt_out_number(
            company_id, "+15551234567", keyword="agent_manual",
        )

        assert result["status"] == "opted_out"
        assert result["conversations_affected"] == 1
        assert mock_conv.is_opted_out is True

    def test_manual_opt_in(self, sms_service, mock_db, company_id):
        """Test manual opt-in by agent."""
        mock_conv = MagicMock()
        mock_conv.is_opted_out = True
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_conv])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.opt_in_number(company_id, "+15551234567")

        assert result["status"] == "opted_in"
        assert mock_conv.is_opted_out is False

    def test_get_consent_status(self, sms_service, mock_db, company_id):
        """Test getting consent status."""
        mock_conv = _mock_conversation(
            is_opted_out=True, opt_out_keyword="stop")
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_conv])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_consent_status(company_id, "+15551234567")

        assert result["status"] == "opted_out"
        assert result["is_opted_out"] is True

    def test_get_consent_status_unknown(
            self, sms_service, mock_db, company_id):
        """Test consent status for unknown number."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query = MagicMock(return_value=mock_query)

        result = sms_service.get_consent_status(company_id, "+19999999999")

        assert result["status"] == "unknown"


# ═══════════════════════════════════════════════════════════
# Phone Normalization Tests
# ═══════════════════════════════════════════════════════════

class TestPhoneNormalization:
    """Tests for phone number normalization."""

    def test_normalize_e164(self, sms_service):
        """Test E.164 format normalization."""
        result = sms_service._normalize_phone("+15551234567")
        assert result == "+15551234567"

    def test_normalize_with_spaces(self, sms_service):
        """Test phone with spaces and dashes."""
        result = sms_service._normalize_phone("+1 (555) 123-4567")
        assert result == "+15551234567"

    def test_normalize_10digit_us(self, sms_service):
        """Test 10-digit US number gets +1 prefix."""
        result = sms_service._normalize_phone("5551234567")
        assert result == "+15551234567"

    def test_normalize_11digit_us(self, sms_service):
        """Test 11-digit US number with leading 1."""
        result = sms_service._normalize_phone("15551234567")
        assert result == "+15551234567"

    def test_normalize_empty(self, sms_service):
        """Test empty string."""
        result = sms_service._normalize_phone("")
        assert result == ""


# ═══════════════════════════════════════════════════════════
# Credential Encryption Tests (BC-011)
# ═══════════════════════════════════════════════════════════

class TestCredentialEncryption:
    """Tests for credential encryption at rest (BC-011)."""

    def test_encrypt_decrypt_roundtrip(self, sms_service):
        """Test encrypt then decrypt returns original value."""
        original = "my-secret-token-123"
        encrypted = sms_service._encrypt_credential(original)
        decrypted = sms_service._decrypt_credential(encrypted)
        assert decrypted == original

    def test_encrypt_returns_string(self, sms_service):
        """Test encryption returns a string."""
        result = sms_service._encrypt_credential("test-token")
        assert isinstance(result, str)
        assert len(result) > 0
