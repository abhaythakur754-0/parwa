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

import asyncio
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

        # Emit Socket.io call:outgoing event to the tenant room
        try:
            from app.core.socketio import emit_to_tenant
            asyncio.create_task(emit_to_tenant(
                company_id=company_id,
                event_type="call:outgoing",
                payload={
                    "call_id": result.get("call_id"),
                    "conversation_id": result.get("conversation_id"),
                    "twilio_call_sid": result.get("twilio_call_sid"),
                    "direction": "outbound",
                    "from_number": result.get("from_number"),
                    "to_number": result.get("to_number"),
                    "status": "queued",
                    "variant_tier": result.get("variant_tier"),
                },
            ))
        except Exception as sio_exc:
            logger.warning("voice_outgoing_socket_emit_failed error=%s", str(sio_exc)[:200])

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

    # BYO (2026-02): the tenant's own provider credentials are ALWAYS
    # required. "parwa_provided" is retired — Parwa never provisions
    # numbers and never pays for telecom.
    if body.get("number_source") == "parwa_provided":
        return _error_response(
            "VALIDATION_ERROR",
            "Parwa no longer provides phone numbers. Connect your own "
            "calling provider account (bring_own) — you pay the provider "
            "directly, not Parwa.",
            422,
        )
    required_fields = ["twilio_account_sid", "twilio_auth_token", "twilio_phone_number"]
    missing = [f for f in required_fields if not body.get(f)]
    if missing:
        return _error_response(
            "VALIDATION_ERROR",
            f"Missing required provider credential fields: {', '.join(missing)}",
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
async def voice_status_callback(request: Request):
    """Receive call status callback from the tenant's voice provider (BYO).

    Updates call status; on completion triggers the post-call pipeline
    (transcript summary + ticket creation) as a background task.

    R-01 NOTE: No JWT auth — providers authenticate via their own HMAC
    signature, verified with the TENANT's stored credentials (BYO).
    """
    from app.config import get_settings

    try:
        form_data = await request.form()
        payload = dict(form_data)
    except Exception:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

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

    # Look up company from the call record if not in query params
    call_row = None
    if not company_id:
        try:
            db = _get_db(request)
            from database.models.voice_channel import VoiceCall
            call_row = (
                db.query(VoiceCall)
                .filter(VoiceCall.twilio_call_sid == call_sid)
                .first()
            )
            if call_row:
                company_id = call_row.company_id
        except Exception:
            pass

    if not company_id:
        return {"status": "no_company_id"}

    # BYO signature verification: use the TENANT's provider credentials,
    # not any global Parwa telecom account.
    try:
        db = _get_db(request)
        from database.models.voice_channel import (
            VoiceCall as VoiceCallModel,
            VoiceChannelConfig,
        )
        from app.core.providers.voice.base_voice_provider import get_voice_provider

        if call_row is None:
            call_row = (
                db.query(VoiceCallModel)
                .filter(VoiceCallModel.twilio_call_sid == call_sid)
                .first()
            )

        config = (
            db.query(VoiceChannelConfig)
            .filter(VoiceChannelConfig.company_id == company_id)
            .first()
        )
        if config and call_row:
            from app.services.voice_channel_service import VoiceChannelService
            provider = get_voice_provider(config.provider)
            service_tmp = VoiceChannelService(db)
            tenant_token = service_tmp._decrypt_credential_or_empty(
                config.twilio_auth_token_encrypted,
            )
            if not provider.verify_signature(
                str(request.url),
                payload,
                dict(request.headers),
                tenant_token or "",
            ):
                logger.warning(
                    "voice_status_callback_invalid_signature sid=%s provider=%s",
                    call_sid, config.provider,
                )
                return _error_response(
                    "AUTHENTICATION_ERROR", "Invalid provider signature", 401,
                )
    except Exception as exc:
        logger.warning(
            "voice_status_signature_check_skipped error=%s", str(exc)[:200],
        )

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

        # Emit Socket.io call:status event to the tenant room
        try:
            from app.core.socketio import emit_to_tenant
            event_type = (
                "call:ended"
                if call_status in ("completed", "failed", "busy", "no-answer", "canceled")
                else "call:status"
            )
            asyncio.create_task(emit_to_tenant(
                company_id=company_id,
                event_type=event_type,
                payload={
                    "call_sid": call_sid,
                    "status": call_status,
                    "duration": int(duration) if duration else None,
                    "recording_url": recording_url,
                    "recording_sid": recording_sid,
                },
            ))
        except Exception as sio_exc:
            logger.warning("voice_status_socket_emit_failed error=%s", str(sio_exc)[:200])

        # Call finished → run the post-call pipeline (summary + ticket)
        # in the background so the provider callback returns instantly.
        if call_status == "completed":
            asyncio.create_task(_finish_call_background(company_id, call_sid, int(duration) if duration else 0))

        return result
    except Exception as exc:
        logger.error(
            "voice_status_callback_error sid=%s error=%s",
            call_sid, str(exc)[:200],
        )
        return _error_response("INTERNAL_ERROR", "Failed to process status callback", 500)


async def _finish_call_background(
    company_id: str, call_sid: str, duration_seconds: int,
) -> None:
    """Post-call pipeline in its own DB session (summary + ticket)."""
    try:
        from database.base import SessionLocal
        from app.services.voice_conversation_engine import VoiceConversationEngine

        db = SessionLocal()
        try:
            engine = VoiceConversationEngine(db)
            result = await engine.afinish_call(
                company_id=company_id,
                call_sid=call_sid,
                end_reason="completed",
                duration_seconds=duration_seconds,
            )
            logger.info(
                "voice_finish_call_done company=%s ticket=%s turns=%s",
                company_id, result.get("ticket_id"), result.get("turns"),
            )
        finally:
            db.close()
    except Exception as exc:
        logger.error(
            "voice_finish_call_failed company=%s sid=%s error=%s",
            company_id, call_sid, str(exc)[:300],
        )


@router.post("/webhook/voice")
async def voice_inbound_webhook(request: Request):
    """Receive inbound call webhook from the tenant's voice provider (BYO).

    Starts the AI conversation: greeting turn + live Gather action that
    points at /webhook/gather — that's where the actual problem-solving
    happens, turn by turn.

    R-01 NOTE: No JWT auth — provider HMAC signature is verified with
    the TENANT's stored credentials (BYO).
    """
    from app.config import get_settings

    try:
        form_data = await request.form()
        payload = dict(form_data)
    except Exception:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    call_sid = payload.get("CallSid", "")
    from_number = payload.get("From", "")
    to_number = payload.get("To", "")

    # Look up the tenant by the number they connected (BYO)
    company_id = None
    config = None
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

    if not company_id or not config:
        # Unknown number — nobody's tenant owns it, hang up politely.
        from fastapi.responses import Response as RawResponse
        twiml = (
            '<Response>'
            '<Say>We are unable to process your call at this time.</Say>'
            '<Hangup/>'
            '</Response>'
        )
        return RawResponse(content=twiml, media_type="application/xml")

    # BYO signature verification with the tenant's own credentials
    try:
        from app.core.providers.voice.base_voice_provider import get_voice_provider
        from app.services.voice_channel_service import VoiceChannelService

        provider = get_voice_provider(config.provider)
        service_tmp = VoiceChannelService(_get_db(request))
        tenant_token = service_tmp._decrypt_credential_or_empty(
            config.twilio_auth_token_encrypted,
        )
        if not provider.verify_signature(
            str(request.url),
            payload,
            dict(request.headers),
            tenant_token or "",
        ):
            logger.warning(
                "voice_webhook_invalid_signature from=%s provider=%s",
                from_number, config.provider,
            )
            from app.config import get_settings as _gs
            if _gs().is_production:
                return _error_response(
                    "AUTHENTICATION_ERROR", "Invalid provider signature", 401,
                )
    except Exception as exc:
        logger.warning(
            "voice_webhook_signature_check_skipped error=%s", str(exc)[:200],
        )

    # Process the inbound call (creates records + opens the AI conversation)
    try:
        db = _get_db(request)
        from app.services.voice_channel_service import VoiceChannelService
        service = VoiceChannelService(db)
        result = service.process_inbound_call(
            company_id=company_id,
            call_data={
                "call_sid": call_sid,
                "account_sid": payload.get("AccountSid", ""),
                "from_number": from_number,
                "to_number": to_number,
                "call_status": payload.get("CallStatus", "ringing"),
            },
        )

        # Emit Socket.io call:incoming event to the tenant room
        try:
            from app.core.socketio import emit_to_tenant
            asyncio.create_task(emit_to_tenant(
                company_id=company_id,
                event_type="call:incoming",
                payload={
                    "call_id": result.get("call_id"),
                    "conversation_id": result.get("conversation_id"),
                    "provider_call_sid": call_sid,
                    "direction": "inbound",
                    "from_number": from_number,
                    "to_number": to_number,
                    "status": "ringing",
                },
            ))
        except Exception as sio_exc:
            logger.warning("voice_incoming_socket_emit_failed error=%s", str(sio_exc)[:200])

        from fastapi.responses import Response as RawResponse
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
        from fastapi.responses import Response as RawResponse
        twiml = (
            '<Response>'
            '<Say>An error occurred. Please try again later.</Say>'
            '<Hangup/>'
            '</Response>'
        )
        return RawResponse(content=twiml, media_type="application/xml")


@router.post("/webhook/gather")
async def voice_gather_webhook(request: Request):
    """Receive ONE TURN of the live conversation (customer speech).

    This is the heartbeat of the AI voice agent:
      customer speech → engine (LLM decision + SuperGlue tool if needed)
      → reply text → spoken back, and the call keeps listening.

    The Gather action URL in the call script points here with the
    tenant's company_id as a query param.
    """
    from fastapi.responses import Response as RawResponse
    from app.config import get_settings
    from app.core.providers.voice.base_voice_provider import get_voice_provider

    try:
        form_data = await request.form()
        payload = dict(form_data)
    except Exception:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    company_id = request.query_params.get("company_id", "")
    if not company_id:
        return RawResponse(
            content=(
                '<Response><Say>Call configuration error.</Say><Hangup/></Response>'
            ),
            media_type="application/xml",
        )

    try:
        db = _get_db(request)
        from database.models.voice_channel import VoiceChannelConfig
        from app.services.voice_conversation_engine import VoiceConversationEngine

        config = (
            db.query(VoiceChannelConfig)
            .filter(VoiceChannelConfig.company_id == company_id)
            .first()
        )
        if not config:
            return RawResponse(
                content=(
                    '<Response><Say>Call configuration error.</Say>'
                    '<Hangup/></Response>'
                ),
                media_type="application/xml",
            )

        provider = get_voice_provider(config.provider)
        event = provider.parse_webhook(payload)

        # BYO signature verification with the tenant's own credentials
        from app.services.voice_channel_service import VoiceChannelService
        service_tmp = VoiceChannelService(db)
        tenant_token = service_tmp._decrypt_credential_or_empty(
            config.twilio_auth_token_encrypted,
        )
        if not provider.verify_signature(
            str(request.url),
            payload,
            dict(request.headers),
            tenant_token or "",
        ):
            logger.warning(
                "voice_gather_invalid_signature company=%s provider=%s",
                company_id, config.provider,
            )
            if get_settings().is_production:
                return _error_response(
                    "AUTHENTICATION_ERROR", "Invalid provider signature", 401,
                )

        gather_url = request.url.__str__()
        # Rebuild the gather URL WITHOUT volatile query pollution: keep
        # only company_id so the loop stays stable across turns.
        from urllib.parse import urlencode
        gather_url = f"{str(request.base_url).rstrip('/')}/api/v1/voice/webhook/gather?{urlencode({'company_id': company_id})}"

        customer_text = (event.speech_text or "").strip()
        digits = (event.digits or "").strip()
        if digits and not customer_text:
            customer_text = f"[pressed {digits}]"

        engine = VoiceConversationEngine(db)

        if not customer_text:
            # Silence / empty gather ping — nudge, don't hang up.
            twiml = provider.build_conversation_twiml(
                say_text="Are you still there?",
                gather_action_url=gather_url,
                language=config.speech_language,
                voice=config.tts_voice,
            )
            return RawResponse(content=twiml, media_type="application/xml")

        # ── The AI turn ──────────────────────────────────────────
        result = await engine.handle_turn(
            company_id=company_id,
            call_sid=event.call_sid,
            customer_text=customer_text,
            from_number=event.from_number,
            to_number=event.to_number,
        )

        if result.action == "transfer" and config.transfer_number:
            twiml = provider.build_transfer_twiml(
                say_text=result.say or "Transferring you to a colleague now.",
                transfer_number=config.transfer_number,
                language=config.speech_language,
                voice=config.tts_voice,
            )
            asyncio.create_task(
                _finish_call_background(company_id, event.call_sid, 0)
            )
        elif result.action == "end":
            twiml = provider.build_end_twiml(
                say_text=result.say or "Goodbye.",
                language=config.speech_language,
                voice=config.tts_voice,
            )
            if result.end_reason != "opt_out":
                asyncio.create_task(
                    _finish_call_background(company_id, event.call_sid, 0)
                )
        else:
            twiml = provider.build_conversation_twiml(
                say_text=result.say or "I'm sorry, could you repeat that?",
                gather_action_url=gather_url,
                language=config.speech_language,
                voice=config.tts_voice,
            )

        return RawResponse(content=twiml, media_type="application/xml")
    except Exception as exc:
        logger.error(
            "voice_gather_error company=%s error=%s",
            company_id, str(exc)[:300],
        )
        return RawResponse(
            content=(
                '<Response>'
                '<Say>I am sorry, something went wrong on our side. '
                'Please try again later. Goodbye.</Say>'
                '<Hangup/>'
                '</Response>'
            ),
            media_type="application/xml",
        )
