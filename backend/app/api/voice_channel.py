"""
Voice Channel API Endpoints — Voice Call API

Provides:
- POST /api/v1/voice/call           — Initiate outbound call
- GET  /api/v1/voice/calls          — List voice calls (paginated)
- GET  /api/v1/voice/calls/{id}     — Get call detail
- POST /api/v1/voice/calls/{id}/end — End active call
- POST /api/v1/voice/calls/{id}/transfer — Transfer call
- GET  /api/v1/voice/conversations  — List conversations
- GET  /api/v1/voice/conversations/{id} — Get conversation detail
- GET  /api/v1/voice/config         — Get voice config
- POST /api/v1/voice/config         — Create voice config
- PUT  /api/v1/voice/config         — Update voice config
- DELETE /api/v1/voice/config       — Delete voice config
- POST /api/v1/voice/webhook/status — Twilio status callback (NO JWT)
- POST /api/v1/voice/webhook/voice  — Twilio voice webhook (NO JWT)
- GET  /api/v1/voice/history        — Call history
- POST /api/v1/voice/test-call      — Test call (rate limited)

BC-001: All endpoints scoped to company_id.
BC-003: Idempotent processing (Twilio CallSid).
BC-006: Rate limiting on outbound calls.
BC-010: TCPA opt-out compliance.
BC-011: Credentials encrypted at rest.
BC-012: Structured JSON error responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from app.api.deps import get_current_user
from database.models.core import User

logger = logging.getLogger("parwa.voice_channel_api")

router = APIRouter(prefix="/api/v1/voice", tags=["Voice Channel"])


def _get_db(request: Request):
    """Get DB session from request state (injected by middleware)."""
    try:
        from database.base import get_db
        return next(get_db())
    except Exception:
        from database.base import SessionLocal
        return SessionLocal()


def _error_response(code: str, message: str, status_code: int = 422) -> JSONResponse:
    """Build a structured JSON error response (BC-012)."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": None,
            }
        },
    )


# ═══════════════════════════════════════════════════════════════
# Outbound Call
# ═══════════════════════════════════════════════════════════════


@router.post("/call")
async def initiate_outbound_call(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Initiate an outbound voice call.

    Validates opt-out status (BC-010), rate limits (BC-006),
    and sends via Twilio API.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        return _error_response("BAD_REQUEST", "Invalid JSON body", 400)

    if not body.get("to_number"):
        return _error_response("VALIDATION_ERROR", "to_number is required")

    sender_id = str(current_user.id)

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.initiate_outbound_call(
            company_id=company_id,
            to_number=body["to_number"],
            variant_tier=body.get("variant_tier", "parwa"),
            message=body.get("message"),
            sender_id=sender_id,
            sender_role=body.get("sender_role", "agent"),
            ticket_id=body.get("ticket_id"),
            enable_recording=body.get("enable_recording"),
        )

        if result.get("status") == "error":
            status_code = 429 if "rate" in result.get("error", "").lower() else 422
            code = "RATE_LIMIT_EXCEEDED" if status_code == 429 else "VALIDATION_ERROR"
            return _error_response(code, result["error"], status_code)

        return result
    except Exception as exc:
        logger.error(
            "voice_call_initiate_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to initiate call", 500)


# ═══════════════════════════════════════════════════════════════
# Call Management Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/calls")
async def list_voice_calls(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List voice calls with pagination.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        return service.list_calls(
            company_id=company_id,
            page=page,
            page_size=page_size,
            direction=direction,
            status=status,
        )
    except Exception as exc:
        logger.error(
            "voice_calls_list_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to list voice calls", 500)


@router.get("/calls/{call_id}")
async def get_voice_call(
    request: Request,
    call_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a single voice call by ID.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        call = service.get_call(call_id, company_id)
        if not call:
            return _error_response("NOT_FOUND", f"Call {call_id} not found", 404)
        return call.to_dict()
    except Exception as exc:
        logger.error(
            "voice_call_get_error",
            extra={
                "company_id": company_id,
                "call_id": call_id,
                "error": str(exc)[:200],
            },
        )
        return _error_response("INTERNAL_ERROR", "Failed to retrieve call", 500)


@router.post("/calls/{call_id}/end")
async def end_voice_call(
    request: Request,
    call_id: str,
    current_user: User = Depends(get_current_user),
):
    """End an active voice call.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)

        # Find the call to get the twilio_call_sid
        call = service.get_call(call_id, company_id)
        if not call:
            return _error_response("NOT_FOUND", f"Call {call_id} not found", 404)

        if not call.twilio_call_sid:
            return _error_response("VALIDATION_ERROR", "Call has no Twilio SID")

        result = service.end_call(company_id, call.twilio_call_sid)
        if result.get("status") == "error":
            return _error_response("VALIDATION_ERROR", result["error"])

        return result
    except Exception as exc:
        logger.error(
            "voice_call_end_error",
            extra={
                "company_id": company_id,
                "call_id": call_id,
                "error": str(exc)[:200],
            },
        )
        return _error_response("INTERNAL_ERROR", "Failed to end call", 500)


@router.post("/calls/{call_id}/transfer")
async def transfer_voice_call(
    request: Request,
    call_id: str,
    current_user: User = Depends(get_current_user),
):
    """Transfer an active voice call to another number.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        return _error_response("BAD_REQUEST", "Invalid JSON body", 400)

    to_number = body.get("to_number")
    if not to_number:
        return _error_response("VALIDATION_ERROR", "to_number is required")

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)

        # Find the call to get the twilio_call_sid
        call = service.get_call(call_id, company_id)
        if not call:
            return _error_response("NOT_FOUND", f"Call {call_id} not found", 404)

        if not call.twilio_call_sid:
            return _error_response("VALIDATION_ERROR", "Call has no Twilio SID")

        result = service.transfer_call(
            company_id, call.twilio_call_sid, to_number,
        )
        if result.get("status") == "error":
            return _error_response("VALIDATION_ERROR", result["error"])

        return result
    except Exception as exc:
        logger.error(
            "voice_call_transfer_error",
            extra={
                "company_id": company_id,
                "call_id": call_id,
                "error": str(exc)[:200],
            },
        )
        return _error_response("INTERNAL_ERROR", "Failed to transfer call", 500)


# ═══════════════════════════════════════════════════════════════
# Conversation Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/conversations")
async def list_voice_conversations(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    is_opted_out: Optional[bool] = Query(None),
):
    """List voice conversations with pagination.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        return service.list_conversations(
            company_id=company_id,
            page=page,
            page_size=page_size,
            is_opted_out=is_opted_out,
        )
    except Exception as exc:
        logger.error(
            "voice_conversations_list_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to list conversations", 500)


@router.get("/conversations/{conversation_id}")
async def get_voice_conversation(
    request: Request,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a single voice conversation by ID.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        conv = service.get_conversation(conversation_id, company_id)
        if not conv:
            return _error_response(
                "NOT_FOUND",
                f"Conversation {conversation_id} not found",
                404,
            )
        return conv.to_dict()
    except Exception as exc:
        logger.error(
            "voice_conversation_get_error",
            extra={
                "company_id": company_id,
                "conversation_id": conversation_id,
                "error": str(exc)[:200],
            },
        )
        return _error_response("INTERNAL_ERROR", "Failed to retrieve conversation", 500)


# ═══════════════════════════════════════════════════════════════
# Voice Config Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/config")
async def get_voice_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get voice channel configuration (secrets redacted).

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        config = service.get_voice_config(company_id)
        if not config:
            return _error_response(
                "NOT_FOUND", "Voice channel not configured", 404,
            )
        return config.to_dict()
    except Exception as exc:
        logger.error(
            "voice_config_get_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to get voice config", 500)


@router.post("/config")
async def create_voice_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Create voice channel configuration.

    Twilio credentials are encrypted at rest (BC-011).

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        return _error_response("BAD_REQUEST", "Invalid JSON body", 400)

    required_fields = ["twilio_account_sid", "twilio_auth_token", "twilio_phone_number"]
    missing = [f for f in required_fields if not body.get(f)]
    if missing:
        return _error_response(
            "VALIDATION_ERROR",
            f"Missing required fields: {', '.join(missing)}",
        )

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.create_voice_config(company_id, body)
        if result.get("status") == "error":
            return _error_response("VALIDATION_ERROR", result["error"])
        return result
    except Exception as exc:
        logger.error(
            "voice_config_create_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to create voice config", 500)


@router.put("/config")
async def update_voice_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Update voice channel configuration (partial update).

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.update_voice_config(company_id, body)
        if result.get("status") == "error":
            return _error_response("NOT_FOUND", result["error"], 404)
        return result
    except Exception as exc:
        logger.error(
            "voice_config_update_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to update voice config", 500)


@router.delete("/config")
async def delete_voice_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Delete voice channel configuration.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.delete_voice_config(company_id)
        if result.get("status") == "error":
            return _error_response("NOT_FOUND", result["error"], 404)
        return result
    except Exception as exc:
        logger.error(
            "voice_config_delete_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to delete voice config", 500)


# ═══════════════════════════════════════════════════════════════
# Call History
# ═══════════════════════════════════════════════════════════════


@router.get("/history")
async def get_call_history(
    request: Request,
    current_user: User = Depends(get_current_user),
    phone_number: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get call history with optional filters.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        return service.get_call_history(
            company_id=company_id,
            phone_number=phone_number,
            direction=direction,
            status=status,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.error(
            "voice_history_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to get call history", 500)


# ═══════════════════════════════════════════════════════════════
# Test Call (Rate Limited)
# ═══════════════════════════════════════════════════════════════


@router.post("/test-call")
async def test_call(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Make a test call to a specified number.

    Rate limited to 1 test call per hour per company.

    R-01: Requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        return _error_response("BAD_REQUEST", "Invalid JSON body", 400)

    to_number = body.get("to_number")
    if not to_number:
        return _error_response("VALIDATION_ERROR", "to_number is required")

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.initiate_outbound_call(
            company_id=company_id,
            to_number=to_number,
            variant_tier="parwa",
            message="This is a test call from Parwa voice system.",
            sender_id=str(current_user.id),
            sender_role="agent",
        )

        if result.get("status") == "error":
            status_code = 429 if "rate" in result.get("error", "").lower() else 422
            code = "RATE_LIMIT_EXCEEDED" if status_code == 429 else "VALIDATION_ERROR"
            return _error_response(code, result["error"], status_code)

        return result
    except Exception as exc:
        logger.error(
            "voice_test_call_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return _error_response("INTERNAL_ERROR", "Failed to make test call", 500)


# ═══════════════════════════════════════════════════════════════
# Twilio Webhook Receivers (NO JWT — uses HMAC signature)
# ═══════════════════════════════════════════════════════════════


@router.post("/webhook/status")
async def twilio_status_callback(request: Request):
    """Receive Twilio voice call status callback.

    Updates call status in the database.

    M-16 FIX: Verifies Twilio webhook signature before processing.
    R-01 NOTE: This endpoint intentionally does NOT use JWT auth —
    it receives callbacks from Twilio, which uses HMAC signature
    verification instead.
    """
    from app.security.hmac_verification import verify_twilio_signature
    from app.config import get_settings

    settings = get_settings()
    twilio_signature = request.headers.get("x-twilio-signature", "")

    if not settings.TWILIO_AUTH_TOKEN:
        logger.error("voice_status_callback_no_auth_token_configured")
        return _error_response(
            "NOT_CONFIGURED",
            "Voice webhook not configured — TWILIO_AUTH_TOKEN required",
            500,
        )

    try:
        form_data = await request.form()
        payload = dict(form_data)
    except Exception:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    if not verify_twilio_signature(
        str(request.url),
        payload,
        twilio_signature,
        settings.TWILIO_AUTH_TOKEN,
    ):
        logger.warning(
            "voice_status_callback_invalid_signature sid=%s",
            payload.get("CallSid", ""),
        )
        return _error_response("AUTHENTICATION_ERROR", "Invalid Twilio signature", 401)

    call_sid = payload.get("CallSid", "")
    call_status = payload.get("CallStatus", "")
    duration = payload.get("CallDuration")
    recording_url = payload.get("RecordingUrl")
    recording_sid = payload.get("RecordingSid")
    company_id = payload.get("company_id", "")

    if not call_sid or not call_status:
        return _error_response(
            "VALIDATION_ERROR", "CallSid and CallStatus are required",
        )

    # Look up company_id from the call if not provided
    if not company_id:
        try:
            db = _get_db(request)
            from database.models.voice_channel import VoiceCall
            call = (
                db.query(VoiceCall)
                .filter(VoiceCall.twilio_call_sid == call_sid)
                .first()
            )
            if call:
                company_id = call.company_id
        except Exception:
            pass

    if not company_id:
        return {"status": "no_company_id"}

    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.update_call_status(
            company_id=company_id,
            call_sid=call_sid,
            status=call_status,
            duration=int(duration) if duration else None,
            recording_url=recording_url,
            recording_sid=recording_sid,
        )
        return result
    except Exception as exc:
        logger.error(
            "voice_status_callback_error sid=%s error=%s",
            call_sid, str(exc)[:200],
        )
        return _error_response("INTERNAL_ERROR", "Failed to process status callback", 500)


@router.post("/webhook/voice")
async def twilio_voice_webhook(request: Request):
    """Receive Twilio inbound voice call webhook.

    Generates TwiML response for the call.

    R-01 NOTE: This endpoint intentionally does NOT use JWT auth —
    it receives callbacks from Twilio, which uses HMAC signature
    verification instead.
    """
    from app.security.hmac_verification import verify_twilio_signature
    from app.config import get_settings
    from fastapi.responses import Response as RawResponse

    settings = get_settings()
    twilio_signature = request.headers.get("x-twilio-signature", "")

    # Try to parse form data first (Twilio sends form-encoded)
    try:
        form_data = await request.form()
        payload = dict(form_data)
    except Exception:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    # Verify Twilio signature (allow in dev mode for testing)
    if settings.TWILIO_AUTH_TOKEN and twilio_signature:
        if not verify_twilio_signature(
            str(request.url),
            payload,
            twilio_signature,
            settings.TWILIO_AUTH_TOKEN,
        ):
            logger.warning(
                "voice_webhook_invalid_signature from=%s",
                payload.get("From", ""),
            )
            # In dev mode, continue anyway; in prod, reject
            if settings.is_production:
                return _error_response("AUTHENTICATION_ERROR", "Invalid Twilio signature", 401)

    call_sid = payload.get("CallSid", "")
    from_number = payload.get("From", "")
    to_number = payload.get("To", "")
    account_sid = payload.get("AccountSid", "")

    # Look up company by Twilio phone number
    company_id = None
    try:
        db = _get_db(request)
        from database.models.voice_channel import VoiceChannelConfig
        config = (
            db.query(VoiceChannelConfig)
            .filter(VoiceChannelConfig.twilio_phone_number == to_number)
            .first()
        )
        if config:
            company_id = config.company_id
    except Exception as exc:
        logger.error(
            "voice_webhook_lookup_error error=%s",
            str(exc)[:200],
        )

    if not company_id:
        # Fallback to settings-level config
        twiml = (
            '<Response>'
            '<Say>We are unable to process your call at this time.</Say>'
            '<Hangup/>'
            '</Response>'
        )
        return RawResponse(content=twiml, media_type="application/xml")

    # Process the inbound call
    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.process_inbound_call(
            company_id=company_id,
            call_data={
                "call_sid": call_sid,
                "account_sid": account_sid,
                "from_number": from_number,
                "to_number": to_number,
                "call_status": "ringing",
            },
        )

        # Return TwiML as XML response
        twiml = result.get("twiml", (
            '<Response>'
            '<Say>Thank you for calling.</Say>'
            '<Hangup/>'
            '</Response>'
        ))
        return RawResponse(content=twiml, media_type="application/xml")
    except Exception as exc:
        logger.error(
            "voice_webhook_error call_sid=%s error=%s",
            call_sid, str(exc)[:200],
        )
        twiml = (
            '<Response>'
            '<Say>An error occurred. Please try again later.</Say>'
            '<Hangup/>'
            '</Response>'
        )
        return RawResponse(content=twiml, media_type="application/xml")
