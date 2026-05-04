"""
PARWA Collision API - Concurrent Editing Detection Endpoints (Day 33: MF11)

Endpoints for tracking ticket viewers and collision detection.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.exceptions import NotFoundError, ValidationError
from app.services.collision_service import CollisionService
from database.models.core import User


router = APIRouter(prefix="/tickets", tags=["Collisions"])


# ── Schemas ────────────────────────────────────────────────────────────────


class StartViewingRequest(BaseModel):
    session_id: Optional[str] = None


class ViewerResponse(BaseModel):
    user_id: str
    name: str
    email: Optional[str]


class CollisionStatusResponse(BaseModel):
    ticket_id: str
    user_id: Optional[str]
    is_viewing: bool
    has_collision: Optional[bool] = None
    current_viewers: list
    viewer_count: int


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/{ticket_id}/viewing", response_model=CollisionStatusResponse)
def start_viewing(
    ticket_id: str,
    data: StartViewingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark the current user as viewing a ticket."""
    service = CollisionService(db, current_user.company_id)

    try:
        result = service.start_viewing(
            ticket_id=ticket_id,
            user_id=current_user.id,
            session_id=data.session_id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return CollisionStatusResponse(
        ticket_id=result["ticket_id"],
        user_id=result["user_id"],
        is_viewing=result["is_viewing"],
        has_collision=result.get("has_collision"),
        current_viewers=result["current_viewers"],
        viewer_count=result["viewer_count"],
    )


@router.delete("/{ticket_id}/viewing", response_model=CollisionStatusResponse)
def stop_viewing(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the current user from ticket viewers."""
    service = CollisionService(db, current_user.company_id)

    try:
        result = service.stop_viewing(
            ticket_id=ticket_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return CollisionStatusResponse(
        ticket_id=result["ticket_id"],
        user_id=result["user_id"],
        is_viewing=result["is_viewing"],
        current_viewers=result["current_viewers"],
        viewer_count=result["viewer_count"],
    )


@router.get("/{ticket_id}/viewers")
def get_viewers(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current viewers of a ticket."""
    service = CollisionService(db, current_user.company_id)

    result = service.get_viewers(ticket_id)

    return result


@router.post("/{ticket_id}/viewing/heartbeat")
def heartbeat(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Refresh viewer session (extend TTL)."""
    service = CollisionService(db, current_user.company_id)

    try:
        result = service.heartbeat(
            ticket_id=ticket_id,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@router.get("/{ticket_id}/collisions/history")
def get_collision_history(
    ticket_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get collision history for a ticket."""
    service = CollisionService(db, current_user.company_id)

    result = service.get_collision_history(
        ticket_id=ticket_id,
        page=page,
        page_size=page_size,
    )

    return result
