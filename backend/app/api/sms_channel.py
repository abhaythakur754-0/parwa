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

BC-001: All endpoints scoped to company_id.
BC-003: Idempotent processing (Twilio MessageSid).
BC-006: Rate limiting on outbound SMS.
BC-010: TCPA opt-out/opt-in compliance.
BC-011: Credentials encrypted at rest.
BC-012: Structured JSON error responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

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


@router.post("/send")
async def send_sms(request: Request):
    """Send an outbound SMS message.

    Validates opt-out status (BC-010), rate limits (BC-006),
    and sends via Twilio API.
    """
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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

    sender_id = getattr(request.state, "user_id", None)

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
                        "code": (
                            "RATE_LIMIT_EXCEEDED"
                            if status_code == 429
                            else "VALIDATION_ERROR"
                        ),
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


@router.get("/conversations")
async def list_sms_conversations(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    is_opted_out: Optional[bool] = Query(None),
):
    """List SMS conversations with pagination."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.get("/conversations/{conversation_id}")
async def get_sms_conversation(request: Request, conversation_id: str):
    """Get a single SMS conversation by ID."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.get("/conversations/{conversation_id}/messages")
async def get_sms_messages(
    request: Request,
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get messages for an SMS conversation."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.get("/config")
async def get_sms_config(request: Request):
    """Get SMS channel configuration (secrets redacted)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.post("/config")
async def create_sms_config(request: Request):
    """Create SMS channel configuration.

    Twilio credentials are encrypted at rest (BC-011).
    """
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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
                    "message": f"Missing required fields: {
                        ', '.join(missing)}",
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


@router.put("/config")
async def update_sms_config(request: Request):
    """Update SMS channel configuration (partial update)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.delete("/config")
async def delete_sms_config(request: Request):
    """Delete SMS channel configuration."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.post("/consent/opt-out")
async def manual_opt_out(request: Request):
    """Manually opt out a phone number from SMS (BC-010 TCPA)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.post("/consent/opt-in")
async def manual_opt_in(request: Request):
    """Manually opt in a phone number back to SMS (BC-010 TCPA)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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


@router.get("/consent/{customer_number}")
async def get_consent_status(request: Request, customer_number: str):
    """Get TCPA consent status for a phone number (BC-010)."""
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Tenant identification required",
                    "details": None,
                }
            },
        )

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
# ═══════════════════════════════════════════════════════════════


@router.post("/webhook/status")
async def twilio_status_callback(request: Request):
    """Receive Twilio SMS delivery status callback.

    Updates message delivery status in the database.
    Webhook signature is verified by the generic webhook handler.
    """
    try:
        form_data = await request.form()
        payload = dict(form_data)
    except Exception:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

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
            message_sid,
            str(exc)[:200],
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
