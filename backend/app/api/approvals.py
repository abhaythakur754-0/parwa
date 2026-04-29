"""
PARWA Approvals API Bridge

Bridges the frontend approvals page (which calls /api/approvals/*) with
the shadow mode system.  The approvals UI conceptually manages actions
that need human review — this router maps those operations to the
underlying shadow_mode_service.

BC-001: All endpoints scoped by company_id from authenticated user.
BC-011: All endpoints require authentication.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.exceptions import AuthorizationError
from app.logger import get_logger
from database.models.core import User

logger = get_logger("parwa.approvals")

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# ── Pydantic Schemas ──────────────────────────────────────────


class ApproveRejectRequest(BaseModel):
    note: Optional[str] = Field(
        default=None, description="Manager note for the decision"
    )


class EscalateRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Reason for escalation")


class BatchRequest(BaseModel):
    ids: list[str] = Field(..., description="List of shadow log IDs")
    decision: str = Field(..., description="Batch decision: approved or rejected")
    note: Optional[str] = Field(
        default=None, description="Optional note for all entries"
    )


# ── Endpoints ─────────────────────────────────────────────────


@router.get("")
def list_approvals(
    user: User = Depends(get_current_user),
    status: Optional[str] = Query(
        None,
        description="Filter by decision status: approved, rejected, or null for pending",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """
    List approvals (maps to shadow log with pending/approved/rejected statuses).

    This is the main endpoint the frontend approvals page calls.
    It queries the shadow log and returns entries that have gone through
    the shadow mode system.
    """
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()

    # Map 'status' query param to 'decision' filter for the shadow log
    filters: Dict[str, Any] = {}
    if status:
        filters["decision"] = status
    if action_type:
        filters["action_type"] = action_type
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    # Default to showing pending items first
    if not status:
        # Show all, but pending first by default ordering (created_at DESC)
        pass

    result = svc.get_shadow_log(
        company_id=str(company_id),
        filters=filters,
        page=page,
        page_size=page_size,
    )

    # Add pending count for the UI badge
    result["pending_count"] = svc.get_pending_count(str(company_id))

    return result


@router.get("/stats")
def approval_stats(
    user: User = Depends(get_current_user),
):
    """
    Get approval statistics (maps to shadow stats).

    Returns approval rates, risk scores, and distribution data.
    """
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()
    stats = svc.get_shadow_stats(str(company_id))

    return stats


@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
    body: ApproveRejectRequest = ApproveRejectRequest(),
    user: User = Depends(get_current_user),
):
    """Approve a pending action (maps to shadow approve)."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()

    try:
        result = svc.approve_shadow_action(
            shadow_log_id=approval_id,
            manager_id=user.id,
            note=body.note,
        )
    except ShadowModeService.ShadowLogNotFoundError:
        raise HTTPException(status_code=404, detail="Approval not found")
    except ShadowModeService.ShadowModeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Emit real-time approval event
    try:
        from app.core.event_emitter import emit_approval_event
        import asyncio

        asyncio.get_event_loop().create_task(
            emit_approval_event(
                company_id=str(company_id),
                event_type="approval:approved",
                payload={
                    "approval_id": approval_id,
                    "company_id": str(company_id),
                    "action_type": result.get("action_type"),
                    "status": "approved",
                    "approver_id": user.id,
                    "reason": body.note,
                },
            )
        )
    except Exception:
        logger.warning("Failed to emit approval:approved event")

    return result


@router.post("/{approval_id}/reject")
def reject(
    approval_id: str,
    body: ApproveRejectRequest = ApproveRejectRequest(),
    user: User = Depends(get_current_user),
):
    """Reject a pending action (maps to shadow reject)."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()

    try:
        result = svc.reject_shadow_action(
            shadow_log_id=approval_id,
            manager_id=user.id,
            note=body.note,
        )
    except ShadowModeService.ShadowLogNotFoundError:
        raise HTTPException(status_code=404, detail="Approval not found")
    except ShadowModeService.ShadowModeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Emit real-time rejection event
    try:
        from app.core.event_emitter import emit_approval_event
        import asyncio

        asyncio.get_event_loop().create_task(
            emit_approval_event(
                company_id=str(company_id),
                event_type="approval:rejected",
                payload={
                    "approval_id": approval_id,
                    "company_id": str(company_id),
                    "action_type": result.get("action_type"),
                    "status": "rejected",
                    "approver_id": user.id,
                    "reason": body.note,
                },
            )
        )
    except Exception:
        logger.warning("Failed to emit approval:rejected event")

    return result


@router.post("/{approval_id}/escalate")
def escalate(
    approval_id: str,
    body: EscalateRequest = EscalateRequest(),
    user: User = Depends(get_current_user),
):
    """
    Escalate an action — change its mode to shadow (observation only).

    This effectively downgrades the action from whatever mode it was
    in to pure shadow mode, requiring a re-evaluation cycle.
    """
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()

    try:
        result = svc.escalate_shadow_action(
            shadow_log_id=approval_id,
            manager_id=user.id,
            reason=body.reason,
        )
    except ShadowModeService.ShadowLogNotFoundError:
        raise HTTPException(status_code=404, detail="Approval not found")

    return result


@router.post("/batch")
def batch_resolve(
    body: BatchRequest,
    user: User = Depends(get_current_user),
):
    """
    Batch approve or reject multiple pending actions.

    Processes all provided IDs in a single transaction. Items that
    have already been resolved are skipped.
    """
    from app.services.shadow_mode_service import ShadowModeService, VALID_DECISIONS

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    if body.decision not in VALID_DECISIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision: {
                body.decision}. Must be one of: {
                ', '.join(
                    sorted(VALID_DECISIONS))}",
        )

    svc = ShadowModeService()

    result = svc.batch_resolve(
        company_id=str(company_id),
        shadow_log_ids=body.ids,
        decision=body.decision,
        manager_id=user.id,
        note=body.note,
    )

    # Emit batch event
    try:
        from app.core.event_emitter import emit_approval_event
        import asyncio

        asyncio.get_event_loop().create_task(
            emit_approval_event(
                company_id=str(company_id),
                event_type="approval:batch",
                payload={
                    "approval_id": f"batch_{body.decision}",
                    "company_id": str(company_id),
                    "status": body.decision,
                    "approver_id": user.id,
                    "ticket_ids": body.ids,
                    "reason": body.note,
                },
            )
        )
    except Exception:
        logger.warning("Failed to emit approval:batch event")

    return result
