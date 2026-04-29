"""
Bounce & Complaint API Endpoints — Week 13 Day 3 (F-124)

Provides tenant-level bounce/complaint management:
- GET /api/v1/email/bounces — List bounce/complaint events
- POST /api/v1/email/bounces/{id}/whitelist — Whitelist a bounced email
- GET /api/v1/email/bounces/stats — Get deliverability statistics
- GET /api/v1/email/bounces/digest — Get deliverability digest
- GET /api/v1/email/bounces/status/{email} — Check email sendability

BC-001: All endpoints scoped to company_id (via middleware).
BC-003: Webhook endpoints in webhooks.py (already exist).
BC-012: Structured JSON error responses.
"""

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.schemas.bounce_complaint import (
    BounceListResponse,
    WhitelistRequest,
    WhitelistResponse,
    BounceStatsResponse,
    BounceDigestResponse,
)

logger = logging.getLogger("parwa.bounce_api")

router = APIRouter(prefix="/api/v1/email/bounces", tags=["Bounce & Complaint"])


def _get_db(request: Request):
    """Get DB session from request state (injected by middleware)."""
    from database.session import get_db_session
    return get_db_session()


@router.get("", response_model=BounceListResponse)
async def list_bounces(
    request: Request,
    status: str = Query("all", description="Filter: all/soft/hard/complaint"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """List bounce and complaint events for the tenant.

    Returns paginated list of bounce/complaint events ordered by most recent.
    Supports filtering by bounce type.
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
        from app.services.bounce_complaint_service import BounceComplaintService

        service = BounceComplaintService(db)
        result = service.list_bounces(
            company_id=company_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return result
    except Exception as exc:
        logger.error(
            "bounce_list_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list bounces",
                    "details": None,
                }
            },
        )


@router.post("/{bounce_id}/whitelist", response_model=WhitelistResponse)
async def whitelist_bounced_email(
    request: Request,
    bounce_id: str,
    body: WhitelistRequest,
):
    """Whitelist a previously bounced email address.

    Allows sending to the email again. If a new bounce occurs
    after whitelisting, the whitelist is preserved and an alert
    is sent recommending review.
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
        from app.services.bounce_complaint_service import BounceComplaintService
        from database.models.email_bounces import EmailBounce

        service = BounceComplaintService(db)

        # Find the bounce record
        bounce = (
            db.query(EmailBounce)
            .filter(
                EmailBounce.id == bounce_id,
                EmailBounce.company_id == company_id,
            )
            .first()
        )

        if not bounce:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Bounce record {bounce_id} not found",
                        "details": None,
                    }
                },
            )

        # Whitelist the email
        user_id = getattr(request.state, "user_id", None)
        result = service.whitelist_email(
            company_id=company_id,
            email=bounce.customer_email,
            justification=body.justification,
            user_id=user_id,
        )

        return WhitelistResponse(
            status=result["status"],
            bounce_id=bounce_id,
            email=bounce.customer_email,
        )
    except Exception as exc:
        logger.error(
            "whitelist_error",
            extra={
                "company_id": company_id,
                "bounce_id": bounce_id,
                "error": str(exc)[
                    :200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to whitelist email",
                    "details": None,
                }
            },
        )


@router.get("/stats", response_model=BounceStatsResponse)
async def get_bounce_stats(
    request: Request,
    range_days: int = Query(
        7,
        ge=1,
        le=90,
        description="Number of days to look back"),
):
    """Get bounce and complaint statistics for the tenant.

    Returns counts, rates, trend direction, and suppressed email count.
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
        from app.services.bounce_complaint_service import BounceComplaintService

        service = BounceComplaintService(db)
        result = service.get_stats(company_id, range_days)
        return result
    except Exception as exc:
        logger.error(
            "bounce_stats_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get bounce stats",
                    "details": None,
                }
            },
        )


@router.get("/digest", response_model=BounceDigestResponse)
async def get_bounce_digest(request: Request):
    """Get deliverability digest for the tenant.

    Returns critical unacknowledged alerts and a 24h summary
    of bounces and complaints.
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
        from app.services.bounce_complaint_service import BounceComplaintService

        service = BounceComplaintService(db)
        result = service.get_digest(company_id)
        return result
    except Exception as exc:
        logger.error(
            "bounce_digest_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get bounce digest",
                    "details": None,
                }
            },
        )


@router.get("/status/{email:path}")
async def check_email_status(request: Request, email: str):
    """Check if an email address can receive messages.

    Returns the current delivery status, bounce/complaint counts,
    and whether the email is whitelisted or suppressed.
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
        from app.services.bounce_complaint_service import BounceComplaintService

        service = BounceComplaintService(db)
        result = service.get_email_status(company_id, email)
        return result
    except Exception as exc:
        logger.error(
            "email_status_check_error",
            extra={
                "company_id": company_id,
                "email": email,
                "error": str(exc)[
                    :200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to check email status",
                    "details": None,
                }
            },
        )
