"""
SMS Channel API Endpoints — Week 13 Day 5 (F-123: SMS Channel)

Provides:
- POST /api/v1/sms/send — Send outbound SMS
- GET /api/v1/sms/conversations — List SMS conversations
- GET /api/v1/sms/conversations/{id} — Get conversation detail
- GET /api/v1/sms/conversations/{id}/messages — Get conversation messages
- GET /api/v1/sms/config — Get SMS channel config
- POST /api/v1/sms/config — Create SMS channel config
- PUT /api/v1/sms/config — Update SMS channel config
- DELETE /api/v1/sms/config — Delete SMS channel config
- POST /api/v1/sms/consent/opt-out — Manual opt-out (BC-010)
- POST /api/v1/sms/consent/opt-in — Manual opt-in (BC-010)
- GET /api/v1/sms/consent/{phone} — Get consent status (BC-010)
- POST /api/v1/sms/webhook/status — Twilio status callback (NO JWT — uses HMAC)

BC-001: All endpoints scoped to company_id.
BC-003: Idempotent processing (Twilio MessageSid).
BC-006: Rate limiting on outbound SMS.
BC-010: TCPA opt-out/opt-in compliance.
BC-011: Credentials encrypted at rest. JWT verification on all non-webhook endpoints (R-01 fix).
BC-012: Structured JSON error responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from database.models.core import User
from app.schemas.sms_channel import (
    SMSSendResponse,
    SMSConversationListResponse,
    SMSConversationResponse,
    SMSMessageListResponse,
    SMSConfigResponse,
    SMSConsentStatusResponse,
)

logger = logging.getLogger("parwa.sms_channel_api")

router = APIRouter(prefix="/api/v1/sms", tags=["SMS Channel"])


def _get_db(request: Request):
    """Get DB session from request state (injected by middleware)."""
    try:
        from database.base import get_db
        return next(get_db())
    except Exception:
        from database.base import SessionLocal
        return SessionLocal()


# ═══════════════════════════════════════════════════════════════
# Outbound SMS
# ═══════════════════════════════════════════════════════════════


@router.post("/send", response_model=SMSSendResponse)
async def send_sms(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Send an outbound SMS message.

    Validates opt-out status (BC-010), rate limits (BC-006),
    and sends via Twilio API.

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    if not body.get("to_number") or not body.get("body"):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "to_number and body are required",
                    "details": None,
                }
            },
        )

    sender_id = str(current_user.id)

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        result = service.send_sms(
            company_id=company_id,
            to_number=body["to_number"],
            body=body["body"],
            sender_id=sender_id,
            sender_role=body.get("sender_role", "agent"),
            conversation_id=body.get("conversation_id"),
            ticket_id=body.get("ticket_id"),
        )

        if result.get("status") == "error":
            status_code = 429 if "rate" in result.get("error", "").lower() else 422
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED" if status_code == 429 else "VALIDATION_ERROR",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )

        return result
    except Exception as exc:
        logger.error(
            "sms_send_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to send SMS",
                    "details": None,
                }
            },
        )


# ═══════════════════════════════════════════════════════════════
# Conversation Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/conversations", response_model=SMSConversationListResponse)
async def list_sms_conversations(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    is_opted_out: Optional[bool] = Query(None),
):
    """List SMS conversations with pagination.

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        return service.list_conversations(
            company_id=company_id,
            page=page,
            page_size=page_size,
            is_opted_out=is_opted_out,
        )
    except Exception as exc:
        logger.error(
            "sms_conversations_list_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list SMS conversations",
                    "details": None,
                }
            },
        )


@router.get("/conversations/{conversation_id}", response_model=SMSConversationResponse)
async def get_sms_conversation(
    request: Request,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a single SMS conversation by ID.

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        conv = service.get_conversation(conversation_id, company_id)
        if not conv:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Conversation {conversation_id} not found",
                        "details": None,
                    }
                },
            )
        return conv.to_dict()
    except Exception as exc:
        logger.error(
            "sms_conversation_get_error",
            extra={
                "company_id": company_id,
                "conversation_id": conversation_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve conversation",
                    "details": None,
                }
            },
        )


@router.get("/conversations/{conversation_id}/messages", response_model=SMSMessageListResponse)
async def get_sms_messages(
    request: Request,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get messages for an SMS conversation.

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        return service.get_messages(
            conversation_id=conversation_id,
            company_id=company_id,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.error(
            "sms_messages_get_error",
            extra={
                "company_id": company_id,
                "conversation_id": conversation_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get SMS messages",
                    "details": None,
                }
            },
        )


# ═══════════════════════════════════════════════════════════════
# SMS Config Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/config", response_model=SMSConfigResponse)
async def get_sms_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get SMS channel configuration (secrets redacted).

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        config = service.get_sms_config(company_id)
        if not config:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "SMS channel not configured",
                        "details": None,
                    }
                },
            )
        return config.to_dict()
    except Exception as exc:
        logger.error(
            "sms_config_get_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get SMS config",
                    "details": None,
                }
            },
        )


@router.post("/config", response_model=SMSConfigResponse)
async def create_sms_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Create SMS channel configuration.

    Twilio credentials are encrypted at rest (BC-011).

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id


    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    required_fields = ["twilio_account_sid", "twilio_auth_token", "twilio_phone_number"]
    missing = [f for f in required_fields if not body.get(f)]
    if missing:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Missing required fields: {', '.join(missing)}",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        result = service.create_sms_config(company_id, body)
        if result.get("status") == "error":
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "sms_config_create_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to create SMS config",
                    "details": None,
                }
            },
        )


@router.put("/config", response_model=SMSConfigResponse)
async def update_sms_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Update SMS channel configuration (partial update).

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        result = service.update_sms_config(company_id, body)
        if result.get("status") == "error":
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "sms_config_update_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to update SMS config",
                    "details": None,
                }
            },
        )


@router.delete("/config", response_model=dict)
async def delete_sms_config(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Delete SMS channel configuration.

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        result = service.delete_sms_config(company_id)
        if result.get("status") == "error":
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )
        return result
    except Exception as exc:
        logger.error(
            "sms_config_delete_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to delete SMS config",
                    "details": None,
                }
            },
        )


# ═══════════════════════════════════════════════════════════════
# TCPA Consent Endpoints (BC-010)
# ═══════════════════════════════════════════════════════════════


@router.post("/consent/opt-out", response_model=SMSConsentStatusResponse)
async def manual_opt_out(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Manually opt out a phone number from SMS (BC-010 TCPA).

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    customer_number = body.get("customer_number")
    if not customer_number:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "customer_number is required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        return service.opt_out_number(
            company_id=company_id,
            customer_number=customer_number,
            keyword=body.get("keyword", "manual"),
        )
    except Exception as exc:
        logger.error(
            "sms_opt_out_error",
            extra={
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to opt out number",
                    "details": None,
                }
            },
        )


@router.post("/consent/opt-in", response_model=SMSConsentStatusResponse)
async def manual_opt_in(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Manually opt in a phone number back to SMS (BC-010 TCPA).

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Invalid JSON body",
                    "details": None,
                }
            },
        )

    customer_number = body.get("customer_number")
    if not customer_number:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "customer_number is required",
                    "details": None,
                }
            },
        )

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        return service.opt_in_number(
            company_id=company_id,
            customer_number=customer_number,
        )
    except Exception as exc:
        logger.error(
            "sms_opt_in_error",
            extra={
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to opt in number",
                    "details": None,
                }
            },
        )


@router.get("/consent/{customer_number}", response_model=SMSConsentStatusResponse)
async def get_consent_status(
    request: Request,
    customer_number: str,
    current_user: User = Depends(get_current_user),
):
    """Get TCPA consent status for a phone number (BC-010).

    R-01: Now requires JWT authentication via get_current_user.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        return service.get_consent_status(
            company_id=company_id,
            customer_number=customer_number,
        )
    except Exception as exc:
        logger.error(
            "sms_consent_error",
            extra={
                "company_id": company_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get consent status",
                    "details": None,
                }
            },
        )


# ═══════════════════════════════════════════════════════════════
# Twilio Webhook Receiver (Status Callback)
# NOTE: NO JWT auth — uses Twilio HMAC signature verification (M-16)
# ═══════════════════════════════════════════════════════════════


@router.post("/webhook/status", response_model=dict)
async def twilio_status_callback(request: Request):
    """Receive Twilio SMS delivery status callback.

    Updates message delivery status in the database.

    M-16 FIX: Verifies Twilio webhook signature before processing.
    R-01 NOTE: This endpoint intentionally does NOT use JWT auth —
    it receives callbacks from Twilio, which uses HMAC signature
    verification instead. See M-16 fix for signature check.
    """
    # M-16: Verify Twilio signature before processing
    from app.security.hmac_verification import verify_twilio_signature
    from app.config import get_settings

    settings = get_settings()
    twilio_signature = request.headers.get("x-twilio-signature", "")

    if not settings.TWILIO_AUTH_TOKEN:
        logger.error("sms_status_callback_no_auth_token_configured")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "NOT_CONFIGURED",
                    "message": "SMS webhook not configured — TWILIO_AUTH_TOKEN required",
                    "details": None,
                }
            },
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
            "sms_status_callback_invalid_signature sid=%s",
            payload.get("MessageSid", ""),
        )
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "Invalid Twilio signature",
                    "details": None,
                }
            },
        )

    message_sid = payload.get("MessageSid", "")
    status = payload.get("MessageStatus", "")
    error_code = payload.get("ErrorCode")
    error_message = payload.get("ErrorMessage")

    if not message_sid or not status:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "MessageSid and MessageStatus are required",
                    "details": None,
                }
            },
        )

    # Look up company_id from the message
    try:
        db = _get_db(request)
        from database.models.sms_channel import SMSMessage

        message = (
            db.query(SMSMessage)
            .filter(SMSMessage.twilio_message_sid == message_sid)
            .first()
        )

        if not message:
            return {"status": "not_found"}

        from app.services.sms_channel_service import SMSChannelService
        service = SMSChannelService(db)
        result = service.update_delivery_status(
            company_id=message.company_id,
            message_sid=message_sid,
            status=status,
            error_code=int(error_code) if error_code else None,
            error_message=error_message,
        )
        return result
    except Exception as exc:
        logger.error(
            "sms_status_callback_error sid=%s error=%s",
            message_sid, str(exc)[:200],
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to process status callback",
                    "details": None,
                }
            },
        )
