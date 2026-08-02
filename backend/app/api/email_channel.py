"""
Email Channel API Endpoints (F-121)

Provides admin visibility into inbound emails and email threads:
- GET  /api/v1/email/inbound/      — List inbound emails (paginated, filterable)
- GET  /api/v1/email/inbound/{id}  — Get single inbound email detail
- GET  /api/v1/email/threads/      — List email threads
- GET  /api/v1/email/threads/{id}  — Get single email thread detail
- POST /api/v1/email/send          — Send an outbound email via EmailBridge

BC-001: All endpoints scoped to company_id (via middleware).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.email_bridge.email_bridge import EmailBridge
from app.services.integration_service import IntegrationService
from database.base import get_db
from database.models.core import User
from app.schemas.email_channel import (
    InboundEmailListResponse,
    InboundEmailResponse,
    EmailThreadResponse,
)

logger = logging.getLogger("parwa.email_channel_api")

router = APIRouter(prefix="/api/v1/email", tags=["Email Channel"])


def _get_db(request: Request):
    """Get DB session from request state (injected by middleware)."""
    from database.session import get_db_session
    return get_db_session()


# ── Outbound Email ────────────────────────────────────────────────


class SendEmailRequest(BaseModel):
    """Request body for POST /api/v1/email/send.

    Matches the shape src/lib/email.ts sends:
      { to: string[], subject: string, body: string, html_body?: string }
    """

    to: List[str] = Field(..., min_length=1, max_length=50, description="Recipient email addresses")
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(default="", description="Plain-text body")
    html_body: Optional[str] = Field(default=None, description="HTML body (optional)")
    provider: Optional[str] = Field(
        default=None,
        description="Email provider key (brevo, sendgrid, mailgun, ses, postmark). "
                    "Defaults to the tenant's first active email integration.",
    )


class SendEmailResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None


@router.post("/send", response_model=SendEmailResponse)
async def send_email(
    body: SendEmailRequest,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> SendEmailResponse:
    """Send an outbound email via the tenant's configured email provider.

    Resolves the active email integration via IntegrationService, then delegates
    to EmailBridge.send_email which routes through the correct adapter
    (Brevo/SendGrid/Mailgun/SES/Postmark). BC-012: structured errors, no leaks.

    Fix context: src/lib/email.ts was calling this endpoint, but the route didn't
    exist — frontend email send silently 404'd.
    """
    service = IntegrationService(db)
    company_id = str(user.company_id)

    # Resolve provider: explicit request, else first active email integration.
    provider = body.provider
    if not provider:
        # Try the common email providers in priority order.
        for candidate in ("brevo", "sendgrid", "mailgun", "ses", "postmark", "smtp"):
            creds = service.get_credential_config(company_id, candidate)
            if creds and (creds.get("api_key") or creds.get("server_token")
                          or creds.get("access_key_id") or creds.get("smtp_host")):
                provider = candidate
                break
    if not provider:
        return SendEmailResponse(
            success=False,
            error="No email integration is connected. Connect Brevo/SendGrid/Mailgun/SES/Postmark/SMTP in Settings → Integrations.",
        )

    creds = service.get_credential_config(company_id, provider)
    if not creds or not (creds.get("api_key") or creds.get("server_token")
                         or creds.get("access_key_id") or creds.get("smtp_host")):
        return SendEmailResponse(
            success=False,
            error=f"Email provider '{provider}' is connected but credentials are missing. Reconnect it in Settings → Integrations.",
        )

    # Send to each recipient. EmailBridge.send_email takes a single address;
    # we loop so partial failures don't lose the successful sends.
    successes: List[str] = []
    last_error: Optional[str] = None
    for recipient in body.to:
        result = await EmailBridge.send_email(
            provider=provider,
            to_email=recipient,
            subject=body.subject,
            body_text=body.body,
            body_html=body.html_body,
            config=creds,
        )
        if result.get("success"):
            successes.append(recipient)
        else:
            last_error = result.get("error", "unknown error")
            logger.warning(
                "email_send_failed",
                extra={"recipient": recipient, "provider": provider, "error": last_error},
            )

    if not successes:
        return SendEmailResponse(success=False, provider=provider, error=last_error or "All sends failed.")
    if len(successes) < len(body.to):
        return SendEmailResponse(
            success=True,
            provider=provider,
            message_id=f"partial:{len(successes)}/{len(body.to)}",
            error=f"{len(successes)}/{len(body.to)} sent; last error: {last_error}",
        )
    return SendEmailResponse(success=True, provider=provider, message_id=f"sent:{len(successes)}")


@router.get(
    "/inbound",
    response_model=InboundEmailListResponse,
)
async def list_inbound_emails(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    is_processed: Optional[bool] = Query(None, description="Filter by processed status"),
    sender_email: Optional[str] = Query(None, description="Filter by sender email"),
):
    """List inbound emails with pagination and filters.

    Returns paginated list of inbound emails for the tenant,
    ordered by most recent first. Supports filtering by
    processing status and sender email address.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.email_channel_service import EmailChannelService
        service = EmailChannelService(db)
        result = service.list_inbound_emails(
            company_id=company_id,
            page=page,
            page_size=page_size,
            is_processed=is_processed,
            sender_email=sender_email,
        )
        return result
    except Exception as exc:
        logger.error(
            "email_channel_list_error",
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
                    "message": "Failed to list inbound emails",
                    "details": None,
                }
            },
        )


@router.get(
    "/inbound/{inbound_email_id}",
    response_model=InboundEmailResponse,
)
async def get_inbound_email(
    request: Request,
    inbound_email_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a single inbound email by ID.

    Returns the full inbound email record including headers,
    body content, and processing status.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from app.services.email_channel_service import EmailChannelService
        service = EmailChannelService(db)
        email = service.get_inbound_email(inbound_email_id, company_id)
        if not email:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Inbound email {inbound_email_id} not found",
                        "details": None,
                    }
                },
            )
        return email
    except Exception as exc:
        logger.error(
            "email_channel_get_error",
            extra={
                "company_id": company_id,
                "email_id": inbound_email_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve inbound email",
                    "details": None,
                }
            },
        )


@router.get(
    "/threads",
)
async def list_email_threads(
    request: Request,
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """List email threads for the tenant.

    Returns paginated list of email threads with message counts
    and participant information, ordered by most recent activity.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from database.models.email_channel import EmailThread

        query = db.query(EmailThread).filter(
            EmailThread.company_id == company_id,
        )
        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = query.order_by(
            EmailThread.updated_at.desc(),
        ).offset(offset).limit(page_size).all()

        return {
            "items": [
                {
                    "id": t.id,
                    "company_id": t.company_id,
                    "ticket_id": t.ticket_id,
                    "thread_message_id": t.thread_message_id,
                    "latest_message_id": t.latest_message_id,
                    "message_count": t.message_count or 1,
                    "participants": t.participants_json or "[]",
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    except Exception as exc:
        logger.error(
            "email_threads_list_error",
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
                    "message": "Failed to list email threads",
                    "details": None,
                }
            },
        )


@router.get(
    "/threads/{thread_id}",
    response_model=EmailThreadResponse,
)
async def get_email_thread(
    request: Request,
    thread_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a single email thread by ID.

    Returns the email thread record including ticket association,
    message count, and participant list.
    """
    company_id = current_user.company_id

    try:
        db = _get_db(request)
        from database.models.email_channel import EmailThread

        thread = db.query(EmailThread).filter(
            EmailThread.id == thread_id,
            EmailThread.company_id == company_id,
        ).first()

        if not thread:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Email thread {thread_id} not found",
                        "details": None,
                    }
                },
            )
        return thread
    except Exception as exc:
        logger.error(
            "email_thread_get_error",
            extra={
                "company_id": company_id,
                "thread_id": thread_id,
                "error": str(exc)[:200],
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve email thread",
                    "details": None,
                }
            },
        )
