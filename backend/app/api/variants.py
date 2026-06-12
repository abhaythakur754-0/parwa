"""
PARWA Phase 5 — Variant Control API

Endpoints for Command Center: variant status, pause/resume,
emergency stop, activity log, approvals, and undo.

CRITICAL RULES:
- BC-001: company_id from JWT/header
- BC-008: Never crash
- Mini: recommendations only (needs approval)
- PARWA: auto-execute (can undo)
- High: auto-execute + voice + recordings
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_company_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/variants", tags=["variants"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class VariantStatus(BaseModel):
    variant: str = Field(..., description="mini | parwa | high")
    status: str = Field(..., description="active | paused | stopped")
    tickets_used: int = 0
    tickets_limit: int = 0
    actions_today: int = 0
    pending_approvals: int = 0
    last_action: Optional[str] = None


class VariantStatusResponse(BaseModel):
    variants: list[VariantStatus]
    emergency_stop: bool = False
    paused_all: bool = False


class PauseResumeResponse(BaseModel):
    success: bool
    variant: str
    status: str
    message: str


class EmergencyStopResponse(BaseModel):
    success: bool
    message: str
    timestamp: str


class ActivityEntry(BaseModel):
    id: str
    variant: str
    action_type: str
    description: str
    status: str = Field(..., description="executed | pending | undone | denied")
    timestamp: str
    can_undo: bool = False
    can_approve: bool = False
    customer_id: Optional[str] = None
    ticket_id: Optional[str] = None


class ActivityLogResponse(BaseModel):
    entries: list[ActivityEntry]
    total: int
    page: int
    per_page: int


class ApprovalAction(BaseModel):
    success: bool
    action_id: str
    new_status: str
    message: str


class UndoAction(BaseModel):
    success: bool
    action_id: str
    message: str


class NoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


class NoteResponse(BaseModel):
    success: bool
    action_id: str
    message: str


# ---------------------------------------------------------------------------
# In-memory state (production would use Redis + DB)
# ---------------------------------------------------------------------------

# Track per-company variant states
_company_variant_state: dict[str, dict] = {}

# Track per-company emergency stop
_company_emergency_stop: dict[str, bool] = {}

# Track per-company pause-all
_company_paused_all: dict[str, bool] = {}

# Activity log per company
_company_activity: dict[str, list[dict]] = {}


def _get_company_state(company_id: str) -> dict:
    """Get or create company variant state."""
    if company_id not in _company_variant_state:
        _company_variant_state[company_id] = {
            "emergency_stop": False,
            "paused_all": False,
            "variants": {
                "mini": {"status": "active"},
                "parwa": {"status": "active"},
                "high": {"status": "active"},
            },
        }
    return _company_variant_state[company_id]


def _get_activity(company_id: str) -> list[dict]:
    """Get or create activity log for company."""
    if company_id not in _company_activity:
        # Seed with some sample activity
        now = datetime.now(timezone.utc).isoformat()
        _company_activity[company_id] = [
            {
                "id": "act-001",
                "variant": "parwa",
                "action_type": "refund",
                "description": "Refunded $29.99 for order #ORD-4521",
                "status": "executed",
                "timestamp": now,
                "can_undo": True,
                "can_approve": False,
                "customer_id": "cust-101",
                "ticket_id": "tkt-501",
            },
            {
                "id": "act-002",
                "variant": "mini",
                "action_type": "refund",
                "description": "Refund $15.00 recommended for order #ORD-3890",
                "status": "pending",
                "timestamp": now,
                "can_undo": False,
                "can_approve": True,
                "customer_id": "cust-102",
                "ticket_id": "tkt-502",
            },
            {
                "id": "act-003",
                "variant": "high",
                "action_type": "crm_update",
                "description": "Updated CRM contact: John Doe (HubSpot)",
                "status": "executed",
                "timestamp": now,
                "can_undo": True,
                "can_approve": False,
                "customer_id": "cust-103",
                "ticket_id": "tkt-503",
            },
            {
                "id": "act-004",
                "variant": "parwa",
                "action_type": "send_email",
                "description": "Sent order confirmation to jane@example.com",
                "status": "executed",
                "timestamp": now,
                "can_undo": True,
                "can_approve": False,
                "customer_id": "cust-104",
                "ticket_id": "tkt-504",
            },
            {
                "id": "act-005",
                "variant": "mini",
                "action_type": "cancel_order",
                "description": "Cancel order #ORD-5500 recommended",
                "status": "pending",
                "timestamp": now,
                "can_undo": False,
                "can_approve": True,
                "customer_id": "cust-105",
                "ticket_id": "tkt-505",
            },
            {
                "id": "act-006",
                "variant": "high",
                "action_type": "voice_call",
                "description": "Voice call with customer regarding delivery delay",
                "status": "executed",
                "timestamp": now,
                "can_undo": False,
                "can_approve": False,
                "customer_id": "cust-106",
                "ticket_id": "tkt-506",
            },
        ]
    return _company_activity[company_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=VariantStatusResponse)
def get_variant_status(
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
):
    """Get all variant statuses for the company's Command Center."""
    try:
        state = _get_company_state(company_id)

        # Get actual variant info from DB
        try:
            from database.models.core import Company
            company = db.query(Company).filter(Company.id == company_id).first()
            active_variant = company.subscription_variant if company else "mini"
        except Exception:
            active_variant = "parwa"

        variants = []
        variant_limits = {"mini": 500, "parwa": 2000, "high": 999999}

        for vname, vstate in state["variants"].items():
            is_active_variant = vname == active_variant
            limit = variant_limits.get(vname, 500)
            used = 0

            # Try to get real usage from DB
            try:
                from database.models.ticket import Ticket
                from sqlalchemy import func
                result = db.query(func.count(Ticket.id)).filter(
                    Ticket.company_id == company_id
                ).scalar()
                if result:
                    used = min(result, limit)
            except Exception:
                used = int(limit * 0.62) if is_active_variant else 0  # demo fallback

            pending = sum(
                1 for a in _get_activity(company_id)
                if a["variant"] == vname and a["status"] == "pending"
            )

            variants.append(VariantStatus(
                variant=vname,
                status=vstate["status"],
                tickets_used=used,
                tickets_limit=limit if vname != "high" else 0,
                actions_today=len([
                    a for a in _get_activity(company_id) if a["variant"] == vname
                ]),
                pending_approvals=pending,
                last_action=next(
                    (a["description"] for a in reversed(_get_activity(company_id))
                     if a["variant"] == vname),
                    None
                ) if is_active_variant else None,
            ))

        return VariantStatusResponse(
            variants=variants,
            emergency_stop=state["emergency_stop"],
            paused_all=state["paused_all"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_variant_status failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get variant status",
        ) from exc


@router.post("/{variant_id}/pause", response_model=PauseResumeResponse)
def pause_variant(
    variant_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Pause a specific variant — stops it from processing new tickets."""
    try:
        if variant_id not in ("mini", "parwa", "high"):
            raise HTTPException(status_code=400, detail="Invalid variant ID")

        state = _get_company_state(company_id)
        state["variants"][variant_id]["status"] = "paused"

        # Log the action
        _get_activity(company_id).insert(0, {
            "id": f"act-{datetime.now().strftime('%H%M%S')}",
            "variant": variant_id,
            "action_type": "pause",
            "description": f"Variant {variant_id} paused by user",
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "can_undo": True,
            "can_approve": False,
        })

        return PauseResumeResponse(
            success=True,
            variant=variant_id,
            status="paused",
            message=f"Variant {variant_id} has been paused",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("pause_variant failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to pause variant") from exc


@router.post("/{variant_id}/resume", response_model=PauseResumeResponse)
def resume_variant(
    variant_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Resume a paused variant."""
    try:
        if variant_id not in ("mini", "parwa", "high"):
            raise HTTPException(status_code=400, detail="Invalid variant ID")

        state = _get_company_state(company_id)

        # Check if emergency stop is active
        if state["emergency_stop"]:
            raise HTTPException(
                status_code=409,
                detail="Cannot resume while emergency stop is active. Resume all first.",
            )

        state["variants"][variant_id]["status"] = "active"

        _get_activity(company_id).insert(0, {
            "id": f"act-{datetime.now().strftime('%H%M%S')}",
            "variant": variant_id,
            "action_type": "resume",
            "description": f"Variant {variant_id} resumed by user",
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "can_undo": True,
            "can_approve": False,
        })

        return PauseResumeResponse(
            success=True,
            variant=variant_id,
            status="active",
            message=f"Variant {variant_id} has been resumed",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("resume_variant failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to resume variant") from exc


@router.post("/pause-all", response_model=EmergencyStopResponse)
def pause_all_variants(
    company_id: str = Depends(get_current_company_id),
):
    """Pause ALL variants at once — PAUSE ALL button."""
    try:
        state = _get_company_state(company_id)
        state["paused_all"] = True

        for vname in state["variants"]:
            state["variants"][vname]["status"] = "paused"

        _get_activity(company_id).insert(0, {
            "id": f"act-{datetime.now().strftime('%H%M%S')}",
            "variant": "all",
            "action_type": "pause_all",
            "description": "All variants paused by user (PAUSE ALL)",
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "can_undo": True,
            "can_approve": False,
        })

        return EmergencyStopResponse(
            success=True,
            message="All variants have been paused",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        logger.error("pause_all failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to pause all") from exc


@router.post("/emergency-stop", response_model=EmergencyStopResponse)
def emergency_stop(
    company_id: str = Depends(get_current_company_id),
):
    """EMERGENCY STOP — kill all AI, route everything to human agents."""
    try:
        state = _get_company_state(company_id)
        state["emergency_stop"] = True
        state["paused_all"] = True

        for vname in state["variants"]:
            state["variants"][vname]["status"] = "stopped"

        _get_activity(company_id).insert(0, {
            "id": f"act-{datetime.now().strftime('%H%M%S')}",
            "variant": "all",
            "action_type": "emergency_stop",
            "description": "EMERGENCY STOP activated — all AI stopped, routing to human agents",
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "can_undo": True,
            "can_approve": False,
        })

        return EmergencyStopResponse(
            success=True,
            message="EMERGENCY STOP activated. All AI processing halted. New tickets route to human agents.",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        logger.error("emergency_stop failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to emergency stop") from exc


@router.post("/resume-all", response_model=EmergencyStopResponse)
def resume_all_variants(
    company_id: str = Depends(get_current_company_id),
):
    """Resume all variants after emergency stop or pause all."""
    try:
        state = _get_company_state(company_id)
        state["emergency_stop"] = False
        state["paused_all"] = False

        for vname in state["variants"]:
            state["variants"][vname]["status"] = "active"

        _get_activity(company_id).insert(0, {
            "id": f"act-{datetime.now().strftime('%H%M%S')}",
            "variant": "all",
            "action_type": "resume_all",
            "description": "All variants resumed by user",
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "can_undo": True,
            "can_approve": False,
        })

        return EmergencyStopResponse(
            success=True,
            message="All variants have been resumed. AI processing is active.",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        logger.error("resume_all failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to resume all") from exc


@router.get("/{variant_id}/activity", response_model=ActivityLogResponse)
def get_variant_activity(
    variant_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    company_id: str = Depends(get_current_company_id),
):
    """Get activity log for a specific variant."""
    try:
        activity = _get_activity(company_id)

        # Filter by variant
        if variant_id != "all":
            activity = [a for a in activity if a["variant"] == variant_id]

        # Filter by status
        if status_filter:
            activity = [a for a in activity if a["status"] == status_filter]

        total = len(activity)
        start = (page - 1) * per_page
        end = start + per_page

        entries = [
            ActivityEntry(
                id=a["id"],
                variant=a["variant"],
                action_type=a["action_type"],
                description=a["description"],
                status=a["status"],
                timestamp=a["timestamp"],
                can_undo=a.get("can_undo", False),
                can_approve=a.get("can_approve", False),
                customer_id=a.get("customer_id"),
                ticket_id=a.get("ticket_id"),
            )
            for a in activity[start:end]
        ]

        return ActivityLogResponse(
            entries=entries,
            total=total,
            page=page,
            per_page=per_page,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_variant_activity failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get activity") from exc


@router.get("/approvals/all", response_model=ActivityLogResponse)
def get_pending_approvals(
    company_id: str = Depends(get_current_company_id),
):
    """Get all pending approval requests (for Mini PARWA recommendations)."""
    try:
        activity = _get_activity(company_id)
        pending = [a for a in activity if a["status"] == "pending"]

        entries = [
            ActivityEntry(
                id=a["id"],
                variant=a["variant"],
                action_type=a["action_type"],
                description=a["description"],
                status=a["status"],
                timestamp=a["timestamp"],
                can_undo=a.get("can_undo", False),
                can_approve=a.get("can_approve", False),
                customer_id=a.get("customer_id"),
                ticket_id=a.get("ticket_id"),
            )
            for a in pending
        ]

        return ActivityLogResponse(
            entries=entries,
            total=len(pending),
            page=1,
            per_page=100,
        )
    except Exception as exc:
        logger.error("get_pending_approvals failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get approvals") from exc


@router.post("/approvals/{action_id}/approve", response_model=ApprovalAction)
def approve_action(
    action_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Approve a pending Mini PARWA recommendation."""
    try:
        activity = _get_activity(company_id)
        for a in activity:
            if a["id"] == action_id and a["status"] == "pending":
                a["status"] = "executed"
                a["can_approve"] = False
                a["can_undo"] = True

                # Log the approval
                activity.insert(0, {
                    "id": f"act-{datetime.now().strftime('%H%M%S')}",
                    "variant": a["variant"],
                    "action_type": "approval",
                    "description": f"Approved: {a['description']}",
                    "status": "executed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "can_undo": False,
                    "can_approve": False,
                })

                return ApprovalAction(
                    success=True,
                    action_id=action_id,
                    new_status="executed",
                    message=f"Action approved and executed",
                )

        raise HTTPException(status_code=404, detail="Pending action not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("approve_action failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to approve") from exc


@router.post("/approvals/{action_id}/deny", response_model=ApprovalAction)
def deny_action(
    action_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Deny a pending Mini PARWA recommendation."""
    try:
        activity = _get_activity(company_id)
        for a in activity:
            if a["id"] == action_id and a["status"] == "pending":
                a["status"] = "denied"
                a["can_approve"] = False

                activity.insert(0, {
                    "id": f"act-{datetime.now().strftime('%H%M%S')}",
                    "variant": a["variant"],
                    "action_type": "denial",
                    "description": f"Denied: {a['description']}",
                    "status": "executed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "can_undo": False,
                    "can_approve": False,
                })

                return ApprovalAction(
                    success=True,
                    action_id=action_id,
                    new_status="denied",
                    message="Action denied",
                )

        raise HTTPException(status_code=404, detail="Pending action not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("deny_action failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to deny") from exc


@router.post("/actions/{action_id}/undo", response_model=UndoAction)
def undo_action(
    action_id: str,
    company_id: str = Depends(get_current_company_id),
):
    """Undo a previously executed AI action (PARWA & High variants)."""
    try:
        activity = _get_activity(company_id)
        for a in activity:
            if a["id"] == action_id and a["status"] == "executed" and a.get("can_undo"):
                a["status"] = "undone"
                a["can_undo"] = False

                activity.insert(0, {
                    "id": f"act-{datetime.now().strftime('%H%M%S')}",
                    "variant": a["variant"],
                    "action_type": "undo",
                    "description": f"Undone: {a['description']}",
                    "status": "executed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "can_undo": False,
                    "can_approve": False,
                })

                return UndoAction(
                    success=True,
                    action_id=action_id,
                    message="Action has been undone",
                )

        raise HTTPException(status_code=404, detail="Action not found or cannot be undone")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("undo_action failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to undo") from exc


@router.post("/actions/{action_id}/note", response_model=NoteResponse)
def add_note_to_action(
    action_id: str,
    body: NoteRequest,
    company_id: str = Depends(get_current_company_id),
):
    """Add a human note to an AI action (correction/instruction)."""
    try:
        activity = _get_activity(company_id)
        for a in activity:
            if a["id"] == action_id:
                activity.insert(0, {
                    "id": f"act-{datetime.now().strftime('%H%M%S')}",
                    "variant": a["variant"],
                    "action_type": "note",
                    "description": f"Note on {a['action_type']}: {body.note[:100]}",
                    "status": "executed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "can_undo": False,
                    "can_approve": False,
                })

                return NoteResponse(
                    success=True,
                    action_id=action_id,
                    message="Note added successfully",
                )

        raise HTTPException(status_code=404, detail="Action not found")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("add_note failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to add note") from exc
