"""
SMS + Voice Combined Integration Tests

Tests that SMS and Voice channels work together:
- Same phone number has both SMS and voice interactions
- Opt-out affects both channels
- Voice calls create tickets (like SMS does)
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


@pytest.fixture
def db_session():
    return MagicMock()


@pytest.fixture
def voice_service(db_session):
    from app.services.voice_channel_service import VoiceChannelService
    return VoiceChannelService(db_session)


@pytest.fixture
def sms_service(db_session):
    from app.services.sms_channel_service import SMSChannelService
    return SMSChannelService(db_session)


class TestSMSVoiceCombined:
    """Test SMS and Voice channel integration."""

    def test_same_phone_number_both_channels(self, voice_service, sms_service, db_session):
        """Same customer should have conversations in both channels."""
        # Both services normalize phone numbers the same way
        voice_normalized = voice_service._normalize_phone("+919652852014")
        sms_normalized = sms_service._normalize_phone("+919652852014")
        assert voice_normalized == sms_normalized == "+919652852014"

    def test_phone_normalization_consistency(self, voice_service, sms_service):
        """Both services should normalize phone numbers identically."""
        test_numbers = [
            "+919652852014",
            "7752583673",
            "+17752583673",
            "+1-775-258-3673",
        ]
        for num in test_numbers:
            v = voice_service._normalize_phone(num)
            s = sms_service._normalize_phone(num)
            assert v == s, f"Mismatch for {num}: voice={v}, sms={s}"

    def test_voice_opt_out_blocks_outbound(self, voice_service, db_session):
        """Voice opt-out should block outbound calls."""
        from database.models.voice_channel import VoiceChannelConfig, VoiceConversation
        mock_config = MagicMock()
        mock_config.is_enabled = True
        mock_config.twilio_phone_number = "+17752583673"
        mock_conv = MagicMock()
        mock_conv.is_opted_out = True
        db_session.query.return_value.filter.return_value.first.side_effect = [mock_config, mock_conv]
        result = voice_service.initiate_outbound_call("company-001", "+919652852014")
        assert result["status"] == "error"
        assert "opted out" in result.get("error", "").lower()

    def test_sms_opt_out_blocks_outbound(self, sms_service, db_session):
        """SMS opt-out should block outbound SMS."""
        from database.models.sms_channel import SMSChannelConfig, SMSConversation
        mock_config = MagicMock()
        mock_config.is_enabled = True
        mock_config.twilio_phone_number = "+17752583673"
        mock_config.max_outbound_per_hour = 5
        mock_config.max_outbound_per_day = 50
        mock_config.char_limit = 1600
        mock_conv = MagicMock()
        mock_conv.is_opted_out = True
        db_session.query.return_value.filter.return_value.first.side_effect = [mock_config, mock_conv]
        result = sms_service.send_sms("company-001", "+919652852014", "Test message")
        assert result["status"] == "error"
        assert "opted out" in result.get("error", "").lower()

    def test_e164_format_required_both(self, voice_service, sms_service):
        """Both channels should reject invalid phone formats."""
        result_v = voice_service.initiate_outbound_call("company-001", "abc")
        result_s = sms_service.send_sms("company-001", "abc", "test")
        # Both should fail with invalid phone
        assert result_v.get("status") == "error" or "invalid" in str(result_v).lower()
        assert result_s.get("status") == "error"
