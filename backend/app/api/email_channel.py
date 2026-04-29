"""
Email Channel API Endpoints (F-121)

Provides admin visibility into inbound emails and email threads:
- GET /api/v1/email/inbound/ — List inbound emails (paginated, filterable)
- GET /api/v1/email/inbound/{id} — Get single inbound email detail
- GET /api/v1/email/threads/ — List email threads
- GET /api/v1/email/threads/{id} — Get single email thread detail

BC-001: All endpoints scoped to company_id (via middleware).
"""

import logging
from typing import Optional

from app.schemas.email_channel import (
    EmailThreadResponse,
    InboundEmailListResponse,
    InboundEmailResponse,
)
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("parwa.email_channel_api")

router = APIRouter(prefix="/api/v1/email", tags=["Email Channel"])


def _get_db(request: Request):
    """Get DB session from request state (injected by middleware)."""
    from database.session import get_db_session

    return get_db_session()


@router.get(
    "/inbound",
    response_model=InboundEmailListResponse,
)
async def list_inbound_emails(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    is_processed: Optional[bool] = Query(
        None, description="Filter by processed status"
    ),
    sender_email: Optional[str] = Query(None, description="Filter by sender email"),
):
    """List inbound emails with pagination and filters.

    Returns paginated list of inbound emails for the tenant,
    ordered by most recent first. Supports filtering by
    processing status and sender email address.
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
):
    """Get a single inbound email by ID.

    Returns the full inbound email record including headers,
    body content, and processing status.
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
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """List email threads for the tenant.

    Returns paginated list of email threads with message counts
    and participant information, ordered by most recent activity.
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
        db = _get_db(request)
        from database.models.email_channel import EmailThread

        query = db.query(EmailThread).filter(
            EmailThread.company_id == company_id,
        )
        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = (
            query.order_by(
                EmailThread.updated_at.desc(),
            )
            .offset(offset)
            .limit(page_size)
            .all()
        )

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
):
    """Get a single email thread by ID.

    Returns the email thread record including ticket association,
    message count, and participant list.
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
        db = _get_db(request)
        from database.models.email_channel import EmailThread

        thread = (
            db.query(EmailThread)
            .filter(
                EmailThread.id == thread_id,
                EmailThread.company_id == company_id,
            )
            .first()
        )

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
