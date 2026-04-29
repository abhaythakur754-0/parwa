"""
OOO Detection API Endpoints — Week 13 Day 3 (F-122)

Provides tenant-level OOO detection management:
- POST /api/v1/email/ooo/check — Check if an email is OOO
- GET /api/v1/email/ooo/rules — List detection rules
- POST /api/v1/email/ooo/rules — Create a detection rule
- PUT /api/v1/email/ooo/rules/{id} — Update a detection rule
- DELETE /api/v1/email/ooo/rules/{id} — Delete a detection rule
- GET /api/v1/email/ooo/stats — Get detection statistics
- GET /api/v1/email/ooo/status/{email} — Check customer OOO status

BC-001: All endpoints scoped to company_id (via middleware).
BC-012: Structured JSON error responses.
"""

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.schemas.ooo_detection import (
    OOOCheckRequest,
    OOOCheckResponse,
    OOORuleCreate,
    OOORuleUpdate,
    OOORuleActionResponse,
    OOORulesListResponse,
    OOOStatsResponse,
)

logger = logging.getLogger("parwa.ooo_api")

router = APIRouter(prefix="/api/v1/email/ooo", tags=["OOO Detection"])


def _get_db(request: Request):
    """Get DB session from request state (injected by middleware)."""
    from database.session import get_db_session
    return get_db_session()


@router.post("/check", response_model=OOOCheckResponse)
async def check_ooo(request: Request, body: OOOCheckRequest):
    """Check if an email is an out-of-office or auto-reply.

    Analyzes email headers, subject, and body content against
    OOO detection patterns and custom tenant rules.
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
        from app.services.ooo_detection_service import OOODetectionService

        service = OOODetectionService(db)

        email_data = {
            "headers_json": body.email_headers or {},
            "subject": body.subject or "",
            "body_text": body.body_text or "",
            "body_html": body.body_html or "",
            "sender_email": body.sender_email or "",
        }

        result = service.detect_ooo(email_data, company_id)

        return OOOCheckResponse(
            is_auto_reply=result.get("is_auto_reply", False),
            type=result.get("type"),
            confidence=result.get("confidence"),
            detection_source=result.get("detection_source"),
            detected_signals=result.get("detected_signals", []),
            reason=result.get("reason"),
            ooo_until=result.get("ooo_until"),
            rule_ids_matched=result.get("rule_ids_matched", []),
        )
    except Exception as exc:
        logger.error(
            "ooo_check_error",
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
                    "message": "OOO check failed",
                    "details": None,
                }
            },
        )


@router.get("/rules", response_model=OOORulesListResponse)
async def list_ooo_rules(request: Request):
    """List OOO detection rules for the tenant.

    Returns both tenant-specific custom rules and the count of
    global rules available to all tenants.
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
        from app.services.ooo_detection_service import OOODetectionService

        service = OOODetectionService(db)
        result = service.list_rules(company_id)
        return result
    except Exception as exc:
        logger.error(
            "ooo_list_rules_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to list OOO rules",
                    "details": None,
                }
            },
        )


@router.post("/rules", response_model=OOORuleActionResponse)
async def create_ooo_rule(request: Request, body: OOORuleCreate):
    """Create a custom OOO detection rule for the tenant.

    Rules are evaluated in order after built-in patterns.
    Supported pattern types: regex, substring, contains.
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
        from app.services.ooo_detection_service import OOODetectionService

        service = OOODetectionService(db)
        result = service.create_rule(
            company_id=company_id,
            pattern=body.pattern,
            pattern_type=body.pattern_type,
            rule_type=body.rule_type,
            classification=body.classification,
            active=body.active,
        )
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
        return OOORuleActionResponse(
            rule_id=result.get("rule_id"),
            status="created",
        )
    except Exception as exc:
        logger.error(
            "ooo_create_rule_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to create OOO rule",
                    "details": None,
                }
            },
        )


@router.put("/rules/{rule_id}", response_model=OOORuleActionResponse)
async def update_ooo_rule(request: Request, rule_id: str, body: OOORuleUpdate):
    """Update an existing OOO detection rule."""
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
        from app.services.ooo_detection_service import OOODetectionService

        service = OOODetectionService(db)

        updates = body.model_dump(exclude_none=True)
        result = service.update_rule(company_id, rule_id, updates)

        if result.get("status") == "error":
            return JSONResponse(
                status_code=404 if "not found" in result["error"] else 422,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": result["error"],
                        "details": None,
                    }
                },
            )

        return OOORuleActionResponse(
            rule_id=result.get("rule_id"),
            status="updated",
        )
    except Exception as exc:
        logger.error(
            "ooo_update_rule_error",
            extra={
                "company_id": company_id,
                "rule_id": rule_id,
                "error": str(exc)[
                    :200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to update OOO rule",
                    "details": None,
                }
            },
        )


@router.delete("/rules/{rule_id}", response_model=OOORuleActionResponse)
async def delete_ooo_rule(request: Request, rule_id: str):
    """Delete a custom OOO detection rule."""
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
        from app.services.ooo_detection_service import OOODetectionService

        service = OOODetectionService(db)
        result = service.delete_rule(company_id, rule_id)

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

        return OOORuleActionResponse(
            rule_id=rule_id,
            status="deleted",
        )
    except Exception as exc:
        logger.error(
            "ooo_delete_rule_error",
            extra={
                "company_id": company_id,
                "rule_id": rule_id,
                "error": str(exc)[
                    :200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to delete OOO rule",
                    "details": None,
                }
            },
        )


@router.get("/stats", response_model=OOOStatsResponse)
async def get_ooo_stats(request: Request, range_days: int = Query(
        7, ge=1, le=90, description="Number of days to look back"), ):
    """Get OOO detection statistics for the tenant.

    Returns detection counts, breakdown by type, and top senders.
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
        from app.services.ooo_detection_service import OOODetectionService

        service = OOODetectionService(db)
        result = service.get_stats(company_id, range_days)
        return result
    except Exception as exc:
        logger.error(
            "ooo_stats_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to get OOO stats",
                    "details": None,
                }
            },
        )


@router.get("/status/{email:path}")
async def check_sender_ooo_status(request: Request, email: str):
    """Check if a customer currently has an active OOO status.

    Returns the OOO profile details if active, or null if not.
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
        from app.services.ooo_detection_service import OOODetectionService

        service = OOODetectionService(db)
        result = service.is_customer_ooo(company_id, email)

        if result:
            return result
        return {"is_ooo": False}
    except Exception as exc:
        logger.error(
            "ooo_status_check_error",
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
                    "message": "Failed to check OOO status",
                    "details": None,
                }
            },
        )
