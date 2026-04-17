"""
PARWA Shadow Mode API Endpoints

Dual-control system endpoints for managing AI action execution modes.
Provides shadow/supervised/graduated mode management, risk evaluation,
action logging, manager approval/rejection, and statistics.

BC-001: All endpoints scoped by company_id from authenticated user.
BC-011: All endpoints require authentication.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.exceptions import AuthorizationError
from app.logger import get_logger
from database.models.core import User

logger = get_logger("parwa.shadow")

router = APIRouter(prefix="/api/shadow", tags=["shadow"])


# ── Pydantic Schemas ──────────────────────────────────────────


class SetModeRequest(BaseModel):
    mode: str = Field(..., description="New system mode: shadow, supervised, graduated")
    set_via: str = Field(default="ui", description="How this was set: ui or jarvis")


class SetPreferenceRequest(BaseModel):
    action_category: str = Field(..., description="Action category: refund, sms, email_reply, etc.")
    preferred_mode: str = Field(..., description="Preferred mode: shadow, supervised, graduated")
    set_via: str = Field(default="ui", description="How this was set: ui or jarvis")


class EvaluateActionRequest(BaseModel):
    action_type: str = Field(..., description="Type of action to evaluate")
    action_payload: Dict[str, Any] = Field(default_factory=dict, description="Action payload data")


class ResolveActionRequest(BaseModel):
    note: Optional[str] = Field(default=None, description="Manager note for the decision")


class UndoActionRequest(BaseModel):
    reason: str = Field(..., description="Reason for undoing the action")


class BatchResolveRequest(BaseModel):
    ids: list[str] = Field(..., description="List of shadow log IDs to resolve")
    decision: str = Field(..., description="Batch decision: approved or rejected")
    note: Optional[str] = Field(default=None, description="Optional note for all entries")


# ── Endpoints ─────────────────────────────────────────────────


@router.get("/mode")
def get_mode(
    user: User = Depends(get_current_user),
):
    """Get the current shadow mode for the authenticated company."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()
    mode = svc.get_company_mode(str(company_id))

    return {
        "company_id": company_id,
        "mode": mode,
    }


@router.put("/mode")
def set_mode(
    body: SetModeRequest,
    user: User = Depends(get_current_user),
):
    """Change the system mode (shadow/supervised/graduated)."""
    from app.services.shadow_mode_service import ShadowModeService, VALID_MODES

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    if body.mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {body.mode}. Must be one of: {', '.join(sorted(VALID_MODES))}",
        )

    svc = ShadowModeService()

    # Only owners/admins can change system mode
    if user.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only owners and admins can change system mode",
        )

    result = svc.set_company_mode(
        company_id=str(company_id),
        mode=body.mode,
        set_via=body.set_via,
    )

    # Emit real-time event
    try:
        from app.core.event_emitter import emit_shadow_event
        import asyncio

        asyncio.get_event_loop().create_task(
            emit_shadow_event(
                company_id=str(company_id),
                event_type="shadow:mode_changed",
                payload={
                    "company_id": str(company_id),
                    "mode": body.mode,
                    "previous_mode": result.get("previous_mode"),
                    "set_via": body.set_via,
                },
            )
        )
    except Exception:
        logger.warning("Failed to emit shadow mode change event")

    return result


@router.get("/preferences")
def get_preferences(
    user: User = Depends(get_current_user),
):
    """List all shadow mode preferences for the company."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()
    preferences = svc.get_shadow_preferences(str(company_id))

    return {
        "company_id": company_id,
        "preferences": preferences,
    }


@router.patch("/preferences")
def set_preference(
    body: SetPreferenceRequest,
    user: User = Depends(get_current_user),
):
    """Set or update a shadow mode preference for an action category."""
    from app.services.shadow_mode_service import ShadowModeService, VALID_MODES

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    if body.preferred_mode not in VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {body.preferred_mode}. Must be one of: {', '.join(sorted(VALID_MODES))}",
        )

    svc = ShadowModeService()
    preference = svc.set_shadow_preference(
        company_id=str(company_id),
        action_category=body.action_category,
        preferred_mode=body.preferred_mode,
        set_via=body.set_via,
    )

    return preference


@router.delete("/preferences/{category}")
def delete_preference(
    category: str,
    user: User = Depends(get_current_user),
):
    """Remove a preference (reset to default)."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()
    result = svc.delete_shadow_preference(
        company_id=str(company_id),
        action_category=category,
    )

    return result


@router.get("/log")
def get_shadow_log(
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action_type: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Get paginated shadow log for the company."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    filters = {}
    if action_type:
        filters["action_type"] = action_type
    if mode:
        filters["mode"] = mode
    if decision:
        filters["decision"] = decision
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    svc = ShadowModeService()
    result = svc.get_shadow_log(
        company_id=str(company_id),
        filters=filters,
        page=page,
        page_size=page_size,
    )

    return result


@router.get("/stats")
def get_stats(
    user: User = Depends(get_current_user),
):
    """Get shadow mode statistics for the company."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()
    stats = svc.get_shadow_stats(str(company_id))

    return stats


@router.post("/evaluate")
def evaluate_action(
    body: EvaluateActionRequest,
    user: User = Depends(get_current_user),
):
    """Evaluate the risk of an AI action using the 4-layer decision system."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()
    result = svc.evaluate_action_risk(
        company_id=str(company_id),
        action_type=body.action_type,
        action_payload=body.action_payload,
    )

    return result


@router.post("/{shadow_id}/approve")
def approve_action(
    shadow_id: str,
    body: ResolveActionRequest = ResolveActionRequest(),
    user: User = Depends(get_current_user),
):
    """Approve a pending shadow action."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()

    try:
        result = svc.approve_shadow_action(
            shadow_log_id=shadow_id,
            manager_id=user.id,
            note=body.note,
        )
    except ShadowModeService.ShadowLogNotFoundError:
        raise HTTPException(status_code=404, detail="Shadow log entry not found")
    except ShadowModeService.ShadowModeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Emit approval event
    try:
        from app.core.event_emitter import emit_shadow_event
        import asyncio

        asyncio.get_event_loop().create_task(
            emit_shadow_event(
                company_id=str(company_id),
                event_type="shadow:action_resolved",
                payload={
                    "company_id": str(company_id),
                    "shadow_log_id": shadow_id,
                    "action_type": result.get("action_type"),
                    "decision": "approved",
                    "manager_id": user.id,
                    "reason": body.note,
                },
            )
        )
    except Exception:
        logger.warning("Failed to emit approval event")

    return result


@router.post("/{shadow_id}/reject")
def reject_action(
    shadow_id: str,
    body: ResolveActionRequest = ResolveActionRequest(),
    user: User = Depends(get_current_user),
):
    """Reject a pending shadow action."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()

    try:
        result = svc.reject_shadow_action(
            shadow_log_id=shadow_id,
            manager_id=user.id,
            note=body.note,
        )
    except ShadowModeService.ShadowLogNotFoundError:
        raise HTTPException(status_code=404, detail="Shadow log entry not found")
    except ShadowModeService.ShadowModeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Emit rejection event
    try:
        from app.core.event_emitter import emit_shadow_event
        import asyncio

        asyncio.get_event_loop().create_task(
            emit_shadow_event(
                company_id=str(company_id),
                event_type="shadow:action_resolved",
                payload={
                    "company_id": str(company_id),
                    "shadow_log_id": shadow_id,
                    "action_type": result.get("action_type"),
                    "decision": "rejected",
                    "manager_id": user.id,
                    "reason": body.note,
                },
            )
        )
    except Exception:
        logger.warning("Failed to emit rejection event")

    return result


@router.post("/{shadow_id}/undo")
def undo_action(
    shadow_id: str,
    body: UndoActionRequest,
    user: User = Depends(get_current_user),
):
    """Undo an auto-approved action."""
    from app.services.shadow_mode_service import ShadowModeService

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    svc = ShadowModeService()

    try:
        result = svc.undo_auto_approved_action(
            shadow_log_id=shadow_id,
            reason=body.reason,
            manager_id=user.id,
        )
    except ShadowModeService.ShadowLogNotFoundError:
        raise HTTPException(status_code=404, detail="Shadow log entry not found")
    except ShadowModeService.ShadowModeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.get("/undo-history")
def get_undo_history(
    user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    """Get the undo history for the company.

    Returns a list of actions that have been undone, including
    the original action data, undo reason, and who performed the undo.
    """
    from sqlalchemy import desc
    from database.base import SessionLocal
    from database.models.approval import UndoLog, ExecutedAction

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    with SessionLocal() as db:
        undo_logs = (
            db.query(UndoLog)
            .filter(UndoLog.company_id == str(company_id))
            .order_by(desc(UndoLog.created_at))
            .limit(limit)
            .all()
        )

        entries = []
        for log in undo_logs:
            # Get the associated executed action for action type
            executed_action = (
                db.query(ExecutedAction)
                .filter(ExecutedAction.id == log.executed_action_id)
                .first()
            )

            # Get the user who undid the action
            undone_by_name = None
            if log.undone_by:
                undo_user = db.query(User).filter(User.id == log.undone_by).first()
                if undo_user:
                    undone_by_name = undo_user.name or undo_user.email

            entries.append({
                "id": log.id,
                "company_id": log.company_id,
                "executed_action_id": log.executed_action_id,
                "undo_type": log.undo_type,
                "original_data": log.original_data,
                "undo_data": log.undo_data,
                "undo_reason": log.undo_reason,
                "undone_by": log.undone_by,
                "undone_by_name": undone_by_name,
                "action_type": executed_action.action_type if executed_action else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        return {
            "entries": entries,
            "total": len(entries),
        }


class JarvisCommandRequest(BaseModel):
    message: str = Field(..., description="The user's message containing a shadow mode command")


@router.post("/jarvis-command")
def jarvis_shadow_command(
    body: JarvisCommandRequest,
    user: User = Depends(get_current_user),
):
    """Process a shadow mode conversational command from Jarvis chat.

    Parses natural language commands like:
    - "put refunds in shadow mode"
    - "switch to graduated mode"
    - "show me pending approvals"
    - "approve the last refund"
    - "undo the last action"

    Returns the command result for Jarvis to relay to the user.
    """
    from app.services.jarvis_service import process_shadow_mode_command

    company_id = user.company_id
    if not company_id:
        raise AuthorizationError(message="User has no associated company")

    result = process_shadow_mode_command(
        message=body.message,
        company_id=str(company_id),
        user_id=user.id,
    )

    if result is None:
        return {
            "command_matched": False,
            "message": None,
        }

    return {
        "command_matched": True,
        "success": result.get("success", False),
        "message": result.get("message", ""),
        "data": {k: v for k, v in result.items() if k not in ("success", "message")},
    }
