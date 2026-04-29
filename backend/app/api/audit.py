"""
PARWA Audit Log API Endpoints

Endpoints for:
- Querying the audit trail with filters and pagination
- Fetching aggregated audit statistics
- Exporting audit trail for compliance (owner/admin only)
- Listing available action types and resource types for UI filters

BC-001: All queries scoped by company_id from authenticated user.
BC-011: All endpoints require authentication.
BC-012: Audit trail is read-only via these endpoints.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from app.api.deps import (
    get_company_id,
    get_current_user,
    get_db,
    require_roles,
)
from app.services.audit_service import (
    AuditAction,
    export_audit_trail,
    get_audit_stats,
    query_audit_trail,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.models.core import User

logger = logging.getLogger("parwa.audit")

router = APIRouter(prefix="/api/audit", tags=["Audit"])


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get("/trail")
async def get_audit_trail(
    actor_type: Optional[str] = Query(
        None, description="Filter by actor type (user, system, api_key)"
    ),
    action: Optional[str] = Query(None, description="Filter by action name"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(
        None, description="Filter by specific resource ID"
    ),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    date_from: Optional[str] = Query(
        None, description="ISO datetime string for start date"
    ),
    date_to: Optional[str] = Query(
        None, description="ISO datetime string for end date"
    ),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: User = Depends(get_current_user),
):
    """Query the audit trail with filters and pagination.

    Returns a paginated list of audit entries sorted by created_at descending.
    All entries are scoped to the authenticated user's company (BC-001).
    """
    parsed_from = None
    parsed_to = None

    if date_from:
        try:
            parsed_from = datetime.fromisoformat(date_from)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date_from format: {date_from}. Use ISO 8601 format.",
            )

    if date_to:
        try:
            parsed_to = datetime.fromisoformat(date_to)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date_to format: {date_to}. Use ISO 8601 format.",
            )

    try:
        items, total = query_audit_trail(
            db=db,
            company_id=company_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            date_from=parsed_from,
            date_to=parsed_to,
            offset=offset,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/stats")
async def get_stats(
    days: int = Query(30, ge=1, le=365, description="Look-back period in days"),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated audit statistics for the company.

    Returns action counts, actor type distribution, most active actors,
    and recent activity metrics.
    """
    try:
        stats = get_audit_stats(db=db, company_id=company_id, days=days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return stats


@router.get("/export")
async def export_audit(
    date_from: Optional[str] = Query(
        None, description="ISO datetime string for start date"
    ),
    date_to: Optional[str] = Query(
        None, description="ISO datetime string for end date"
    ),
    format: str = Query("json", description="Export format (json)"),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    """Export audit trail entries for compliance reporting.

    Only owners and admins can export audit data.
    Returns a JSON file download.
    """
    parsed_from = None
    parsed_to = None

    if date_from:
        try:
            parsed_from = datetime.fromisoformat(date_from)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date_from format: {date_from}. Use ISO 8601 format.",
            )

    if date_to:
        try:
            parsed_to = datetime.fromisoformat(date_to)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date_to format: {date_to}. Use ISO 8601 format.",
            )

    try:
        items = export_audit_trail(
            db=db,
            company_id=company_id,
            date_from=parsed_from,
            date_to=parsed_to,
            format=format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Build JSON response with Content-Disposition header for download
    filename = f"audit-trail-{company_id}-{
        datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    json_content = json.dumps(items, indent=2, default=str)

    return JSONResponse(
        content=json.loads(json_content),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/actions")
async def list_action_types(
    current_user: User = Depends(get_current_user),
):
    """List all available audit action types.

    Returns the list of valid action values from the AuditAction enum
    for populating frontend filter dropdowns.
    """
    actions = [action.value for action in AuditAction]
    return {
        "actions": actions,
    }


@router.get("/resource-types")
async def list_resource_types(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: User = Depends(get_current_user),
):
    """List distinct resource types present in the audit trail for this company.

    Useful for populating the frontend resource type filter dropdown
    with only the types that actually exist for this tenant.
    """
    from database.models.integration import AuditTrail

    rows = (
        db.query(AuditTrail.resource_type)
        .filter(
            AuditTrail.company_id == company_id,
            AuditTrail.resource_type.isnot(None),
        )
        .distinct()
        .all()
    )

    resource_types = sorted([row[0] for row in rows if row[0]])

    return {
        "resource_types": resource_types,
    }
