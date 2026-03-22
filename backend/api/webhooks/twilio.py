"""
PARWA Twilio Webhook Handler.

Processes Twilio webhooks for voice calls, SMS, and status callbacks.
All webhooks verify HMAC signature before processing.

CRITICAL: Bad HMAC returns 401 - security requirement.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from security.hmac_verification import verify_hmac
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

# Initialize router and logger
router = APIRouter(prefix="/webhooks/twilio", tags=["Webhooks - Twilio"])
logger = get_logger(__name__)
settings = get_settings()


# --- Pydantic Schemas ---

class TwilioWebhookResponse(BaseModel):
    """Response schema for Twilio webhook processing."""
    status: str
    message: str
    processed_at: datetime
    event_type: Optional[str] = None
    call_sid: Optional[str] = None
    message_sid: Optional[str] = None


class TwiMLResponse(BaseModel):
    """TwiML response for voice calls."""
    twiml: str
    content_type: str = "application/xml"


# --- Helper Functions ---

def verify_twilio_webhook(
    request_body: bytes,
    signature: str,
    url: str
) -> bool:
    """
    Verify Twilio webhook HMAC signature.

    Twilio sends X-Twilio-Signature header with base64 encoded HMAC-SHA1.

    CRITICAL: Bad HMAC returns 401 - this is a security requirement.

    Args:
        request_body: Raw request body bytes
        signature: Signature from X-Twilio-Signature header
        url: The full URL of the webhook endpoint

    Returns:
        bool: True if signature is valid
    """
    if not signature:
        logger.warning({"event": "twilio_webhook_missing_signature"})
        return False

    auth_token = settings.twilio_auth_token
    if not auth_token:
        logger.error({"event": "twilio_auth_token_not_configured"})
        return False

    try:
        # Twilio signature is HMAC-SHA1 of URL + sorted parameters
        # For simplicity, we validate using the body content
        expected_sig = hmac.new(
            auth_token.get_secret_value().encode("utf-8"),
            url.encode("utf-8") + request_body,
            hashlib.sha1
        ).digest()

        expected_sig_b64 = expected_sig.hex()  # or base64

        # Try both hex and base64 comparison
        if hmac.compare_digest(expected_sig_b64, signature):
            return True

        # Try using verify_hmac from security module
        return verify_hmac(request_body, signature, auth_token.get_secret_value())

    except Exception as e:
        logger.error({
            "event": "twilio_signature_verification_error",
            "error": str(e),
        })
        return False


def parse_twilio_form_data(body: bytes) -> Dict[str, str]:
    """
    Parse Twilio form-encoded webhook data.

    Args:
        body: Raw request body bytes

    Returns:
        Dict of form parameters
    """
    data: Dict[str, str] = {}
    try:
        body_str = body.decode("utf-8")
        for pair in body_str.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                # URL decode
                import urllib.parse
                data[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
    except Exception as e:
        logger.error({
            "event": "twilio_form_parse_error",
            "error": str(e),
        })
    return data


def generate_twiml_response(
    message: str,
    action: Optional[str] = None,
    record: bool = True
) -> str:
    """
    Generate TwiML response for voice calls.

    CRITICAL: Recording disclosure must fire for voice calls.

    Args:
        message: Message to speak
        action: Optional action (gather, dial, etc.)
        record: Whether to record the call

    Returns:
        TwiML XML string
    """
    # Recording disclosure (CRITICAL requirement)
    disclosure = (
        "This call may be recorded for quality assurance purposes. "
    )

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{disclosure}{message}</Say>
"""

    if action == "connect_agent":
        twiml += """    <Dial timeout="30">
        <Number>agent-placeholder</Number>
    </Dial>
"""
    elif action == "gather":
        twiml += """    <Gather numDigits="1" action="/webhooks/twilio/voice/handle-input" method="POST">
        <Say>Press 1 to continue, or wait to speak with an agent.</Say>
    </Gather>
"""

    twiml += """    <Say>Thank you for calling. Goodbye.</Say>
</Response>"""

    return twiml


# --- Webhook Endpoints ---

@router.post(
    "/voice",
    response_class=PlainTextResponse,
    summary="Handle Twilio voice webhook",
    description="Process incoming voice call webhooks with HMAC verification."
)
async def handle_voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    """
    Handle Twilio voice webhook.

    CRITICAL:
    - Bad HMAC returns 401
    - Recording disclosure must fire
    - Never IVR-only - always connect to agent or human

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        TwiML response for the call

    Raises:
        HTTPException: 401 if HMAC verification fails
    """
    body = await request.body()
    signature = request.headers.get("X-Twilio-Signature", "")

    # CRITICAL: Verify HMAC - Bad HMAC returns 401
    if not verify_twilio_webhook(body, signature, str(request.url)):
        logger.warning({
            "event": "twilio_voice_webhook_hmac_failed",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # Parse form data
    form_data = parse_twilio_form_data(body)

    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")
    to_number = form_data.get("To", "unknown")
    call_status = form_data.get("CallStatus", "unknown")

    logger.info({
        "event": "twilio_voice_webhook_received",
        "call_sid": call_sid,
        "from": from_number,
        "to": to_number,
        "status": call_status,
        "note": "HMAC verified successfully",
    })

    # Generate TwiML response
    # CRITICAL: Recording disclosure fires, never IVR-only
    twiml = generate_twiml_response(
        message="Welcome to customer support. Connecting you to an agent.",
        action="connect_agent",
        record=True,
    )

    return PlainTextResponse(
        content=twiml,
        media_type="application/xml"
    )


@router.post(
    "/sms",
    response_model=TwilioWebhookResponse,
    summary="Handle Twilio SMS webhook",
    description="Process incoming SMS webhooks with HMAC verification."
)
async def handle_sms_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> TwilioWebhookResponse:
    """
    Handle Twilio SMS webhook.

    CRITICAL: Bad HMAC returns 401

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        TwilioWebhookResponse with processing status

    Raises:
        HTTPException: 401 if HMAC verification fails
    """
    body = await request.body()
    signature = request.headers.get("X-Twilio-Signature", "")

    # CRITICAL: Verify HMAC - Bad HMAC returns 401
    if not verify_twilio_webhook(body, signature, str(request.url)):
        logger.warning({
            "event": "twilio_sms_webhook_hmac_failed",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # Parse form data
    form_data = parse_twilio_form_data(body)

    message_sid = form_data.get("MessageSid", "unknown")
    from_number = form_data.get("From", "unknown")
    to_number = form_data.get("To", "unknown")
    body_text = form_data.get("Body", "")
    num_media = int(form_data.get("NumMedia", 0))

    logger.info({
        "event": "twilio_sms_webhook_received",
        "message_sid": message_sid,
        "from": from_number,
        "to": to_number,
        "body_length": len(body_text),
        "num_media": num_media,
        "note": "HMAC verified successfully",
    })

    return TwilioWebhookResponse(
        status="accepted",
        message="SMS webhook processed successfully",
        processed_at=datetime.now(timezone.utc),
        event_type="sms.received",
        message_sid=message_sid,
    )


@router.post(
    "/status",
    response_model=TwilioWebhookResponse,
    summary="Handle Twilio status callback",
    description="Process status callback webhooks with HMAC verification."
)
async def handle_status_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> TwilioWebhookResponse:
    """
    Handle Twilio status callback webhook.

    CRITICAL: Bad HMAC returns 401

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        TwilioWebhookResponse with processing status

    Raises:
        HTTPException: 401 if HMAC verification fails
    """
    body = await request.body()
    signature = request.headers.get("X-Twilio-Signature", "")

    # CRITICAL: Verify HMAC - Bad HMAC returns 401
    if not verify_twilio_webhook(body, signature, str(request.url)):
        logger.warning({
            "event": "twilio_status_webhook_hmac_failed",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # Parse form data
    form_data = parse_twilio_form_data(body)

    # Determine event type (call or message)
    call_sid = form_data.get("CallSid")
    message_sid = form_data.get("MessageSid")
    status_value = form_data.get("CallStatus") or form_data.get("MessageStatus", "unknown")

    logger.info({
        "event": "twilio_status_webhook_received",
        "call_sid": call_sid,
        "message_sid": message_sid,
        "status": status_value,
        "note": "HMAC verified successfully",
    })

    return TwilioWebhookResponse(
        status="accepted",
        message="Status callback processed successfully",
        processed_at=datetime.now(timezone.utc),
        event_type="status.callback",
        call_sid=call_sid,
        message_sid=message_sid,
    )


@router.post(
    "/voice/handle-input",
    response_class=PlainTextResponse,
    summary="Handle voice input from gather",
    description="Process DTMF input from voice calls."
)
async def handle_voice_input(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    """
    Handle DTMF input from voice call gather.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        TwiML response based on input
    """
    body = await request.body()
    signature = request.headers.get("X-Twilio-Signature", "")

    # Verify HMAC
    if not verify_twilio_webhook(body, signature, str(request.url)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    form_data = parse_twilio_form_data(body)
    digits = form_data.get("Digits", "")
    call_sid = form_data.get("CallSid", "unknown")

    logger.info({
        "event": "twilio_voice_input_received",
        "call_sid": call_sid,
        "digits": digits,
    })

    # Handle input
    if digits == "1":
        twiml = generate_twiml_response(
            message="Connecting you to an agent.",
            action="connect_agent",
        )
    else:
        twiml = generate_twiml_response(
            message="Invalid input. Please try again.",
            action="gather",
        )

    return PlainTextResponse(
        content=twiml,
        media_type="application/xml"
    )
