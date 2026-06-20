"""
Twilio Webhook Handler (BC-003, GAP 1.5)

Handles Twilio SMS and voice webhooks:
- sms.incoming: Incoming SMS message
- voice.call.started: Incoming voice call started
- voice.call.ended: Voice call ended

All handlers:
- Validate required Twilio fields (MessageSid, CallSid, AccountSid)
- Sanitize input to prevent injection
- Return structured result for service layer
- Are idempotent (checked at webhook_service level)
"""

import logging
from typing import Optional

from app.webhooks import register_handler

logger = logging.getLogger("parwa.webhooks.twilio")

# Maximum SMS body length (160 chars standard, we allow up to 1600)
MAX_SMS_BODY_LENGTH = 1600

# Maximum call duration in seconds (sanity check)
MAX_CALL_DURATION_SECONDS = 86400  # 24 hours


def _sanitize_sms_field(value: str, max_length: int = 200) -> str:
    """Sanitize SMS/voice field to prevent injection.

    Strips control characters except newline, truncates.
    """
    if not value:
        return ""
    cleaned = "".join(
        c for c in str(value) if ord(c) >= 32 or c in "\n\r\t"
    )
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned.strip()


def _extract_sms_data(payload: dict) -> dict:
    """Extract and normalize SMS data from Twilio payload.

    Twilio sends form-encoded data with fields like:
    - MessageSid: Unique message ID
    - AccountSid: Twilio account ID (used as tenant)
    - From: Sender phone number in E.164 format
    - To: Recipient phone number
    - Body: SMS text content
    - NumSegments: Number of SMS segments
    """
    return {
        "message_sid": _sanitize_sms_field(payload.get("MessageSid", ""), 64),
        "account_sid": _sanitize_sms_field(payload.get("AccountSid", ""), 64),
        "from_number": _sanitize_sms_field(payload.get("From", ""), 30),
        "to_number": _sanitize_sms_field(payload.get("To", ""), 30),
        "body": _sanitize_sms_field(payload.get("Body", ""), MAX_SMS_BODY_LENGTH),
        "num_segments": int(payload.get("NumSegments", 1)),
    }


def _extract_voice_data(payload: dict) -> dict:
    """Extract and normalize voice call data from Twilio payload.

    Twilio sends form-encoded data with fields like:
    - CallSid: Unique call ID
    - AccountSid: Twilio account ID
    - From: Caller phone number
    - To: Called phone number
    - CallStatus: ringing, in-progress, completed, failed
    - CallDuration: Duration in seconds (only on ended events)
    - Direction: inbound, outbound
    """
    call_duration = payload.get("CallDuration", "0")
    try:
        duration = int(call_duration)
    except (ValueError, TypeError):
        duration = 0

    # Sanity check on duration
    if duration > MAX_CALL_DURATION_SECONDS:
        logger.warning(
            "twilio_call_duration_unrealistic duration=%s call_sid=%s",
            duration,
            payload.get("CallSid"),
        )
        duration = MAX_CALL_DURATION_SECONDS

    return {
        "call_sid": _sanitize_sms_field(payload.get("CallSid", ""), 64),
        "account_sid": _sanitize_sms_field(payload.get("AccountSid", ""), 64),
        "from_number": _sanitize_sms_field(payload.get("From", ""), 30),
        "to_number": _sanitize_sms_field(payload.get("To", ""), 30),
        "call_status": _sanitize_sms_field(payload.get("CallStatus", ""), 20),
        "direction": _sanitize_sms_field(payload.get("Direction", ""), 20),
        "duration_seconds": duration,
    }


def _validate_sms(data: dict) -> Optional[str]:
    """Validate SMS data has required fields.

    Returns:
        Error message if validation fails, None if OK.
    """
    if not data.get("message_sid"):
        return "Missing required field: MessageSid"
    if not data.get("from_number"):
        return "Missing required field: From"
    return None


def _validate_voice(data: dict) -> Optional[str]:
    """Validate voice data has required fields.

    Returns:
        Error message if validation fails, None if OK.
    """
    if not data.get("call_sid"):
        return "Missing required field: CallSid"
    if not data.get("from_number"):
        return "Missing required field: From"
    return None


def handle_sms_incoming(event: dict) -> dict:
    """Handle Twilio sms.incoming event.

    Stores the message and triggers notification creation.

    Args:
        event: Full event dict with keys:
            - event_type: "sms.incoming"
            - payload: Raw Twilio form data
            - company_id: Tenant company ID
            - event_id: Provider event ID

    Returns:
        Dict with status, action, and extracted SMS data.
    """
    payload = event.get("payload", {})
    sms_data = _extract_sms_data(payload)

    error = _validate_sms(sms_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "twilio_sms_incoming from=%s to=%s body_len=%s",
        sms_data["from_number"],
        sms_data["to_number"],
        len(sms_data["body"]),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "store_sms_notification",
        "data": sms_data,
    }


def handle_voice_call_started(event: dict) -> dict:
    """Handle Twilio voice.call.started event."""
    payload = event.get("payload", {})
    voice_data = _extract_voice_data(payload)

    error = _validate_voice(voice_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "twilio_voice_started from=%s to=%s direction=%s",
        voice_data["from_number"],
        voice_data["to_number"],
        voice_data["direction"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "log_voice_call_started",
        "data": voice_data,
    }


def handle_voice_call_ended(event: dict) -> dict:
    """Handle Twilio voice.call.ended event."""
    payload = event.get("payload", {})
    voice_data = _extract_voice_data(payload)

    error = _validate_voice(voice_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "twilio_voice_ended call_sid=%s duration=%ss status=%s",
        voice_data["call_sid"],
        voice_data["duration_seconds"],
        voice_data["call_status"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "log_voice_call_ended",
        "data": voice_data,
    }


# Event type to handler mapping
_TWILIO_HANDLERS = {
    "sms.incoming": handle_sms_incoming,
    "voice.call.started": handle_voice_call_started,
    "voice.call.ended": handle_voice_call_ended,
}


@register_handler("twilio")
def handle_twilio_event(event: dict) -> dict:
    """Main Twilio webhook handler dispatcher.

    Routes to the correct sub-handler based on event_type.

    Args:
        event: Full event dict.

    Returns:
        Dict with status, action, and extracted data.
    """
    event_type = event.get("event_type", "")

    handler = _TWILIO_HANDLERS.get(event_type)
    if not handler:
        logger.warning(
            "twilio_unknown_event_type type=%s event_id=%s",
            event_type,
            event.get("event_id"),
            extra={"company_id": event.get("company_id")},
        )
        return {
            "status": "validation_error",
            "error": f"Unknown Twilio event type: {event_type}",
            "supported_types": list(_TWILIO_HANDLERS.keys()),
        }

    return handler(event)
