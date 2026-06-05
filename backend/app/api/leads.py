"""
PARWA Lead Management API

Exposes lead stats and listing endpoints for the lead_service module.
Wire-up: Task 4.1 — previously the lead_service was orphaned with zero imports.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_current_user
from app.services import lead_service
from database.models.core import User

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("/stats")
async def get_lead_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get aggregate lead statistics.

    Returns counts by status, industry, source, verification rates,
    and total estimated monthly value.
    """
    stats = lead_service.get_lead_stats()
    return {"success": True, "data": stats}


@router.get("/")
async def list_leads(
    request: Request,
    status: str = Query(None, description="Filter by lead status"),
    current_user: User = Depends(get_current_user),
):
    """List all captured leads, optionally filtered by status."""
    if status:
        leads = lead_service.get_leads_by_status(status)
    else:
        leads = lead_service.get_all_leads()
    return {
        "success": True,
        "data": [lead.to_dict() for lead in leads],
        "count": len(leads),
    }


@router.get("/{user_id}")
async def get_lead(
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get lead data for a specific user."""
    lead = lead_service.get_lead(user_id)
    if not lead:
        return {"success": False, "data": None, "message": f"No lead found for user {user_id}"}
    return {"success": True, "data": lead.to_dict()}
