"""Tests for Twilio webhook handler."""

import backend.app.webhooks.twilio_handler  # noqa: F401
from backend.app.webhooks.twilio_handler import (
    handle_twilio_event,
    handle_sms_incoming,
    handle_voice_call_started,
    handle_voice_call_ended,
    _extract_sms_data,
    _extract_voice_data,
    MAX_SMS_BODY_LENGTH,
    MAX_CALL_DURATION_SECONDS,
)

SAMPLE_SMS_EVENT = {
    "event_type": "sms.incoming",
    "payload": {
        "MessageSid": "SM123abc",
        "AccountSid": "AC123xyz",
        "From": "+1234567890",
        "To": "+0987654321",
        "Body": "Hello, I need help",
        "NumSegments": "2",
    },
    "company_id": "comp_1",
    "event_id": "evt_sms_1",
}

SAMPLE_VOICE_STARTED_EVENT = {
    "event_type": "voice.call.started",
    "payload": {
        "CallSid": "CA123abc",
        "AccountSid": "AC123xyz",
        "From": "+1234567890",
        "To": "+0987654321",
        "CallStatus": "ringing",
        "Direction": "inbound",
    },
    "company_id": "comp_1",
    "event_id": "evt_voice_1",
}

SAMPLE_VOICE_ENDED_EVENT = {
    "event_type": "voice.call.ended",
    "payload": {
        "CallSid": "CA123abc",
        "AccountSid": "AC123xyz",
        "From": "+1234567890",
        "To": "+0987654321",
        "CallStatus": "completed",
        "Direction": "inbound",
        "CallDuration": "125",
    },
    "company_id": "comp_1",
    "event_id": "evt_voice_2",
}


class TestHandleTwilioEvent:
    def test_dispatches_sms_incoming(self):
        result = handle_twilio_event(SAMPLE_SMS_EVENT)
        assert result["status"] == "processed"
        assert result["action"] == "store_sms_notification"

    def test_dispatches_voice_call_started(self):
        result = handle_twilio_event(SAMPLE_VOICE_STARTED_EVENT)
        assert result["action"] == "log_voice_call_started"

    def test_dispatches_voice_call_ended(self):
        result = handle_twilio_event(SAMPLE_VOICE_ENDED_EVENT)
        assert result["action"] == "log_voice_call_ended"

    def test_unknown_event_type_returns_error(self):
        event = {**SAMPLE_SMS_EVENT, "event_type": "unknown"}
        result = handle_twilio_event(event)
        assert result["status"] == "validation_error"
        assert "Unknown Twilio event type" in result["error"]

    def test_unknown_event_includes_supported_types(self):
        event = {**SAMPLE_SMS_EVENT, "event_type": "unknown"}
        result = handle_twilio_event(event)
        assert "supported_types" in result
        assert len(result["supported_types"]) == 3


class TestHandleSmsIncoming:
    def test_returns_processed_status(self):
        result = handle_sms_incoming(SAMPLE_SMS_EVENT)
        assert result["status"] == "processed"

    def test_extracts_message_sid(self):
        result = handle_sms_incoming(SAMPLE_SMS_EVENT)
        assert result["data"]["message_sid"] == "SM123abc"

    def test_extracts_account_sid(self):
        result = handle_sms_incoming(SAMPLE_SMS_EVENT)
        assert result["data"]["account_sid"] == "AC123xyz"

    def test_extracts_from_number(self):
        result = handle_sms_incoming(SAMPLE_SMS_EVENT)
        assert result["data"]["from_number"] == "+1234567890"

    def test_extracts_to_number(self):
        result = handle_sms_incoming(SAMPLE_SMS_EVENT)
        assert result["data"]["to_number"] == "+0987654321"

    def test_extracts_body(self):
        result = handle_sms_incoming(SAMPLE_SMS_EVENT)
        assert result["data"]["body"] == "Hello, I need help"

    def test_extracts_num_segments(self):
        result = handle_sms_incoming(SAMPLE_SMS_EVENT)
        assert result["data"]["num_segments"] == 2

    def test_missing_message_sid_returns_error(self):
        event = {**SAMPLE_SMS_EVENT, "payload": {**SAMPLE_SMS_EVENT["payload"], "MessageSid": ""}}
        result = handle_sms_incoming(event)
        assert result["status"] == "validation_error"

    def test_missing_from_returns_error(self):
        event = {**SAMPLE_SMS_EVENT, "payload": {**SAMPLE_SMS_EVENT["payload"], "From": ""}}
        result = handle_sms_incoming(event)
        assert result["status"] == "validation_error"

    def test_body_truncated_to_max_length(self):
        event = {
            **SAMPLE_SMS_EVENT,
            "payload": {**SAMPLE_SMS_EVENT["payload"], "Body": "x" * 2000},
        }
        result = handle_sms_incoming(event)
        assert len(result["data"]["body"]) <= MAX_SMS_BODY_LENGTH


class TestHandleVoiceCallStarted:
    def test_returns_processed_status(self):
        result = handle_voice_call_started(SAMPLE_VOICE_STARTED_EVENT)
        assert result["status"] == "processed"

    def test_extracts_call_sid(self):
        result = handle_voice_call_started(SAMPLE_VOICE_STARTED_EVENT)
        assert result["data"]["call_sid"] == "CA123abc"

    def test_extracts_direction(self):
        result = handle_voice_call_started(SAMPLE_VOICE_STARTED_EVENT)
        assert result["data"]["direction"] == "inbound"

    def test_extracts_call_status(self):
        result = handle_voice_call_started(SAMPLE_VOICE_STARTED_EVENT)
        assert result["data"]["call_status"] == "ringing"

    def test_missing_call_sid_returns_error(self):
        event = {**SAMPLE_VOICE_STARTED_EVENT, "payload": {**SAMPLE_VOICE_STARTED_EVENT["payload"], "CallSid": ""}}
        result = handle_voice_call_started(event)
        assert result["status"] == "validation_error"

    def test_duration_is_zero_on_start(self):
        result = handle_voice_call_started(SAMPLE_VOICE_STARTED_EVENT)
        assert result["data"]["duration_seconds"] == 0


class TestHandleVoiceCallEnded:
    def test_returns_processed_status(self):
        result = handle_voice_call_ended(SAMPLE_VOICE_ENDED_EVENT)
        assert result["status"] == "processed"

    def test_extracts_duration(self):
        result = handle_voice_call_ended(SAMPLE_VOICE_ENDED_EVENT)
        assert result["data"]["duration_seconds"] == 125

    def test_extracts_call_status(self):
        result = handle_voice_call_ended(SAMPLE_VOICE_ENDED_EVENT)
        assert result["data"]["call_status"] == "completed"

    def test_missing_call_sid_returns_error(self):
        event = {**SAMPLE_VOICE_ENDED_EVENT, "payload": {**SAMPLE_VOICE_ENDED_EVENT["payload"], "CallSid": ""}}
        result = handle_voice_call_ended(event)
        assert result["status"] == "validation_error"

    def test_unrealistic_duration_capped(self):
        event = {
            **SAMPLE_VOICE_ENDED_EVENT,
            "payload": {**SAMPLE_VOICE_ENDED_EVENT["payload"], "CallDuration": "999999"},
        }
        result = handle_voice_call_ended(event)
        assert result["data"]["duration_seconds"] == MAX_CALL_DURATION_SECONDS

    def test_invalid_duration_defaults_to_zero(self):
        event = {
            **SAMPLE_VOICE_ENDED_EVENT,
            "payload": {**SAMPLE_VOICE_ENDED_EVENT["payload"], "CallDuration": "invalid"},
        }
        result = handle_voice_call_ended(event)
        assert result["data"]["duration_seconds"] == 0


class TestConstants:
    def test_max_sms_body_length(self):
        assert MAX_SMS_BODY_LENGTH == 1600

    def test_max_call_duration(self):
        assert MAX_CALL_DURATION_SECONDS == 86400
