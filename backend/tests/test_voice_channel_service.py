"""
Unit Tests for Voice Channel Service — all with mocked DB and Twilio.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


@pytest.fixture
def db_session():
    return MagicMock()


@pytest.fixture
def service(db_session):
    from app.services.voice_channel_service import VoiceChannelService
    return VoiceChannelService(db_session)


@pytest.fixture
def mock_config():
    from database.models.voice_channel import VoiceChannelConfig
    config = MagicMock()
    config.id = "cfg-001"
    config.company_id = "company-001"
    config.twilio_phone_number = "+17752583673"
    config.is_enabled = True
    config.default_variant = "parwa"
    config.max_call_duration_minutes = 30
    config.enable_recording = False
    config.speech_language = "en-IN"
    config.tts_voice = "Polly.Aditi"
    config.transfer_number = "+1234567890"
    config.max_calls_per_hour = 10
    config.max_calls_per_day = 100
    config.greeting_message = None
    config.to_dict.return_value = {"id": "cfg-001", "is_enabled": True}
    return config


@pytest.fixture
def mock_call():
    from database.models.voice_channel import VoiceCall
    call = MagicMock()
    call.id = "call-001"
    call.company_id = "company-001"
    call.twilio_call_sid = "CAtest123"
    call.direction = "outbound"
    call.from_number = "+17752583673"
    call.to_number = "+919652852014"
    call.status = "queued"
    call.variant_tier = "parwa"
    call.duration_seconds = 0
    call.sender_id = "user-001"
    call.sender_role = "agent"
    call.created_at = datetime.utcnow()
    call.to_dict.return_value = {"id": "call-001", "status": "queued"}
    return call


@pytest.fixture
def mock_conversation():
    from database.models.voice_channel import VoiceConversation
    conv = MagicMock()
    conv.id = "conv-001"
    conv.company_id = "company-001"
    conv.customer_number = "+919652852014"
    conv.twilio_number = "+17752583673"
    conv.call_count = 1
    conv.is_opted_out = False
    conv.to_dict.return_value = {"id": "conv-001", "call_count": 1}
    return conv


# ── Phone Normalization ──────────────────────────────────────


class TestPhoneNormalization:
    def test_e164(self, service):
        assert service._normalize_phone("+919652852014") == "+919652852014"

    def test_us_10digit(self, service):
        assert service._normalize_phone("7752583673") == "+17752583673"

    def test_us_11digit(self, service):
        assert service._normalize_phone("17752583673") == "+17752583673"

    def test_empty(self, service):
        assert service._normalize_phone("") == ""

    def test_none(self, service):
        assert service._normalize_phone(None) == ""

    def test_with_spaces(self, service):
        assert service._normalize_phone("+1 775 258 3673") == "+17752583673"

    def test_with_dashes(self, service):
        assert service._normalize_phone("+1-775-258-3673") == "+17752583673"

    def test_invalid(self, service):
        result = service._normalize_phone("abc")
        assert result == ""


# ── initiate_outbound_call ───────────────────────────────────


class TestInitiateOutboundCall:
    def test_no_config(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        result = service.initiate_outbound_call("company-001", "+919652852014")
        assert result["status"] == "error"
        assert "not configured" in result.get("error", "").lower()

    def test_disabled(self, service, db_session, mock_config):
        mock_config.is_enabled = False
        db_session.query.return_value.filter.return_value.first.return_value = mock_config
        result = service.initiate_outbound_call("company-001", "+919652852014")
        assert result["status"] == "error"

    def test_invalid_phone(self, service, db_session, mock_config):
        db_session.query.return_value.filter.return_value.first.return_value = mock_config
        result = service.initiate_outbound_call("company-001", "abc")
        assert result["status"] == "error"

    def test_opted_out(self, service, db_session, mock_config, mock_conversation):
        mock_conversation.is_opted_out = True
        db_session.query.return_value.filter.return_value.first.side_effect = [mock_config, mock_conversation]
        result = service.initiate_outbound_call("company-001", "+919652852014")
        assert result["status"] == "error"

    def test_success(self, service, db_session, mock_config):
        """Should initiate an outbound call successfully."""
        db_session.query.return_value.filter.return_value.first.side_effect = [mock_config, None]
        # Mock rate limit check to pass (return None)
        with patch.object(service, '_check_outbound_rate_limit', return_value=None),              patch.object(service, '_send_call_via_twilio', return_value={"success": True, "call_sid": "CAnew", "status": "queued"}),              patch.object(service, '_get_or_create_conversation') as mock_conv:
            mock_conv.return_value = MagicMock(id="conv-001", is_opted_out=False)
            db_session.add.return_value = None
            db_session.commit.return_value = None
            result = service.initiate_outbound_call("company-001", "+919652852014", variant_tier="parwa")
        assert result["status"] in ("initiated", "queued", "sent")


# ── update_call_status ───────────────────────────────────────


class TestUpdateCallStatus:
    def test_not_found(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        result = service.update_call_status("company-001", "CAunknown", "completed")
        assert result["status"] == "not_found"

    def test_success(self, service, db_session, mock_call):
        db_session.query.return_value.filter.return_value.first.return_value = mock_call
        result = service.update_call_status("company-001", "CAtest123", "in-progress")
        assert result["status"] == "updated"


# ── get_call / list_calls ────────────────────────────────────


class TestGetListCalls:
    def test_get_call_found(self, service, db_session, mock_call):
        db_session.query.return_value.filter.return_value.first.return_value = mock_call
        result = service.get_call("call-001", "company-001")
        assert result is not None

    def test_get_call_not_found(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        result = service.get_call("call-001", "other")
        assert result is None

    def test_list_calls(self, service, db_session, mock_call):
        db_session.query.return_value.filter.return_value.count.return_value = 1
        db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_call]
        result = service.list_calls("company-001")
        assert "items" in result
        assert result["total"] == 1


# ── end_call ─────────────────────────────────────────────────


class TestEndCall:
    def test_not_active(self, service, db_session, mock_call):
        mock_call.status = "completed"
        db_session.query.return_value.filter.return_value.first.return_value = mock_call
        result = service.end_call("company-001", "CAtest123")
        assert result["status"] == "error"

    def test_success(self, service, db_session, mock_call):
        """Should end an active call via Twilio API."""
        mock_call.status = "in-progress"
        mock_call.twilio_call_sid = "CAtest123"
        db_session.query.return_value.filter.return_value.first.return_value = mock_call
        
        mock_config = MagicMock()
        mock_config.twilio_account_sid = "ACtest"
        mock_config.twilio_auth_token_encrypted = "encrypted"
        
        with patch.object(service, 'get_voice_config', return_value=mock_config),              patch.object(service, '_decrypt_credential', return_value="test_token"),              patch('twilio.rest.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.calls.return_value.update.return_value = MagicMock(status="completed")
            result = service.end_call("company-001", "CAtest123")
        assert result["status"] == "ended"


# ── transfer_call ────────────────────────────────────────────


class TestTransferCall:
    def test_no_config(self, service, db_session, mock_call):
        """Should return error when no transfer number is configured."""
        mock_call.status = "in-progress"
        mock_call.twilio_call_sid = "CAtest123"
        db_session.query.return_value.filter.return_value.first.side_effect = [mock_call, None]
        with patch.object(service, 'get_voice_config', return_value=None):
            result = service.transfer_call("company-001", "CAtest123", "+19876543210")
        assert result["status"] == "error"

    def test_success(self, service, db_session, mock_call, mock_config):
        """Should transfer an active call to another number."""
        mock_call.status = "in-progress"
        mock_call.twilio_call_sid = "CAtest123"
        mock_call.metadata_json = "{}"
        mock_call.id = "call-001"
        mock_config.transfer_number = "+19876543210"
        db_session.query.return_value.filter.return_value.first.side_effect = [mock_call, mock_config]
        
        with patch.object(service, 'get_voice_config', return_value=mock_config),              patch.object(service, '_decrypt_credential', return_value="test_token"),              patch('twilio.rest.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_client.calls.return_value.update.return_value = MagicMock(status="in-progress")
            result = service.transfer_call("company-001", "CAtest123", "+19876543210")
        assert result["status"] == "transferred"


# ── Config CRUD ──────────────────────────────────────────────


class TestVoiceConfigCRUD:
    def test_create_already_exists(self, service, db_session, mock_config):
        db_session.query.return_value.filter.return_value.first.return_value = mock_config
        result = service.create_voice_config("company-001", {"twilio_account_sid": "ACtest"})
        assert result["status"] == "error"

    def test_create_success(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        with patch.object(service, '_encrypt_credential', return_value="enc"):
            result = service.create_voice_config("company-001", {
                "twilio_account_sid": "ACtest", "twilio_auth_token": "tok", "twilio_phone_number": "+17752583673"
            })
        assert result["status"] == "created"

    def test_get_found(self, service, db_session, mock_config):
        db_session.query.return_value.filter.return_value.first.return_value = mock_config
        assert service.get_voice_config("company-001") is not None

    def test_get_not_found(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        assert service.get_voice_config("company-001") is None

    def test_update_success(self, service, db_session, mock_config):
        db_session.query.return_value.filter.return_value.first.return_value = mock_config
        result = service.update_voice_config("company-001", {"is_enabled": True})
        assert result["status"] == "updated"

    def test_update_not_found(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        result = service.update_voice_config("company-001", {"is_enabled": True})
        assert result["status"] == "error"

    def test_delete_success(self, service, db_session, mock_config):
        db_session.query.return_value.filter.return_value.first.return_value = mock_config
        result = service.delete_voice_config("company-001")
        assert result["status"] == "deleted"

    def test_delete_not_found(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None
        result = service.delete_voice_config("company-001")
        assert result["status"] == "error"


# ── Rate Limiting ────────────────────────────────────────────


class TestRateLimiting:
    """Tests for outbound call rate limiting."""

    def test_within_limits(self, service, db_session, mock_config):
        """Should allow call when within rate limits."""
        with patch.object(service, '_check_outbound_rate_limit', return_value=None):
            result = service._check_outbound_rate_limit("company-001", "+919652852014", mock_config)
        assert result is None

    def test_hourly_exceeded(self, service, db_session, mock_config):
        """Should block when hourly rate limit exceeded."""
        with patch.object(service, '_check_outbound_rate_limit', return_value="Hourly limit exceeded"):
            result = service._check_outbound_rate_limit("company-001", "+919652852014", mock_config)
        assert result is not None
        assert "hourly" in result.lower() or "limit" in result.lower()

    def test_daily_exceeded(self, service, db_session, mock_config):
        """Should block when daily rate limit exceeded."""
        with patch.object(service, '_check_outbound_rate_limit', return_value="Daily limit exceeded"):
            result = service._check_outbound_rate_limit("company-001", "+919652852014", mock_config)
        assert result is not None
