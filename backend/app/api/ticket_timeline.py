"""
PARWA Ticket Timeline API - Activity Timeline Endpoints (Day 27)

Implements MF04: Activity log/timeline endpoint.

Endpoints:
- GET    /api/v1/tickets/:id/timeline       — Full activity log

Activity types tracked:
- Status changes
- Priority changes
- Category changes
- Assignments
- Tags added/removed
- SLA warning/breach
- Reopens
- Freezes/thaws
- Merges/unmerges
- Messages added
- Internal notes
- Attachments uploaded
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user, get_company_id
from backend.app.services.activity_log_service import ActivityLogService
from backend.app.exceptions import NotFoundError


router = APIRouter(prefix="/tickets", tags=["tickets", "timeline"])


# ── Request/Response Schemas ───────────────────────────────────────────────

class TimelineEvent(BaseModel):
    """Single timeline event."""
    id: str
    type: str
    timestamp: datetime
    actor_id: Optional[str]
    actor_type: str
    old_value: Optional[str]
    new_value: Optional[str]
    reason: Optional[str]
    metadata: Optional[Dict[str, Any]]


class TimelineResponse(BaseModel):
    """Paginated timeline response."""
    events: List[TimelineEvent]
    total: int
    page: int
    page_size: int


class ActivitySummary(BaseModel):
    """Activity summary for a ticket."""
    total_activities: int
    activity_counts: Dict[str, int]
    first_response_at: Optional[str]
    first_assignment_at: Optional[str]
    resolved_at: Optional[str]
    message_count: int
    note_count: int
    status_change_count: int


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/{ticket_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    ticket_id: str,
    include_messages: bool = Query(default=True),
    include_notes: bool = Query(default=True),
    include_internal: bool = Query(default=False),
    activity_types: Optional[str] = Query(
        default=None,
        description="Comma-separated activity types to filter"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Get activity timeline for a ticket.

    Returns a comprehensive timeline of all activities on a ticket:
    - Status changes
    - Assignments
    - Messages
    - Internal notes
    - Attachments
    - Merges
    - SLA events
    """
    service = ActivityLogService(db, company_id)

    # Parse activity types
    types_filter = None
    if activity_types:
        types_filter = [t.strip() for t in activity_types.split(",")]

    try:
        events, total = service.get_timeline(
            ticket_id=ticket_id,
            include_messages=include_messages,
            include_notes=include_notes,
            include_internal=include_internal,
            activity_types=types_filter,
            page=page,
            page_size=page_size,
        )

        return TimelineResponse(
            events=[
                TimelineEvent(
                    id=e["id"],
                    type=e["type"],
                    timestamp=e["timestamp"],
                    actor_id=e.get("actor_id"),
                    actor_type=e.get("actor_type", "human"),
                    old_value=e.get("old_value"),
                    new_value=e.get("new_value"),
                    reason=e.get("reason"),
                    metadata=e.get("metadata"),
                )
                for e in events
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticket_id}/timeline/summary", response_model=ActivitySummary)
async def get_activity_summary(
    ticket_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Get activity summary for a ticket.

    Returns aggregate statistics about ticket activity:
    - Total activities
    - Activity counts by type
    - First response time
    - First assignment time
    - Resolution time
    - Message count
    - Note count
    """
    service = ActivityLogService(db, company_id)

    try:
        summary = service.get_activity_summary(ticket_id)

        return ActivitySummary(**summary)

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticket_id}/timeline/status-changes")
async def get_status_history(
    ticket_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Get status change history for a ticket.

    Returns only status change events.
    """
    service = ActivityLogService(db, company_id)

    try:
        events, total = service.get_timeline(
            ticket_id=ticket_id,
            include_messages=False,
            include_notes=False,
            activity_types=[ActivityLogService.ACTIVITY_STATUS_CHANGE],
            page=page,
            page_size=page_size,
        )

        return TimelineResponse(
            events=[
                TimelineEvent(
                    id=e["id"],
                    type=e["type"],
                    timestamp=e["timestamp"],
                    actor_id=e.get("actor_id"),
                    actor_type=e.get("actor_type", "human"),
                    old_value=e.get("old_value"),
                    new_value=e.get("new_value"),
                    reason=e.get("reason"),
                    metadata=e.get("metadata"),
                )
                for e in events
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticket_id}/timeline/assignments")
async def get_assignment_history(
    ticket_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Get assignment history for a ticket.

    Returns only assignment events.
    """
    service = ActivityLogService(db, company_id)

    try:
        events, total = service.get_timeline(
            ticket_id=ticket_id,
            include_messages=False,
            include_notes=False,
            activity_types=[ActivityLogService.ACTIVITY_ASSIGNED],
            page=page,
            page_size=page_size,
        )

        return TimelineResponse(
            events=[
                TimelineEvent(
                    id=e["id"],
                    type=e["type"],
                    timestamp=e["timestamp"],
                    actor_id=e.get("actor_id"),
                    actor_type=e.get("actor_type", "human"),
                    old_value=e.get("old_value"),
                    new_value=e.get("new_value"),
                    reason=e.get("reason"),
                    metadata=e.get("metadata"),
                )
                for e in events
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{ticket_id}/timeline/sla")
async def get_sla_events(
    ticket_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
    current_user: Dict = Depends(get_current_user),
):
    """Get SLA-related events for a ticket.

    Returns SLA warnings and breach events.
    """
    service = ActivityLogService(db, company_id)

    try:
        events, total = service.get_timeline(
            ticket_id=ticket_id,
            include_messages=False,
            include_notes=False,
            activity_types=[
                ActivityLogService.ACTIVITY_SLA_WARNING,
                ActivityLogService.ACTIVITY_SLA_BREACHED,
            ],
            page=page,
            page_size=page_size,
        )

        return TimelineResponse(
            events=[
                TimelineEvent(
                    id=e["id"],
                    type=e["type"],
                    timestamp=e["timestamp"],
                    actor_id=e.get("actor_id"),
                    actor_type=e.get("actor_type", "system"),
                    old_value=e.get("old_value"),
                    new_value=e.get("new_value"),
                    reason=e.get("reason"),
                    metadata=e.get("metadata"),
                )
                for e in events
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
