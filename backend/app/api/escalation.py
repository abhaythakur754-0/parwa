"""
PARWA Escalation API

Exposes the Graceful Escalation Framework via REST endpoints.
Provides active/history listing, acknowledge/resolve lifecycle,
manual escalation creation, statistics, and peer review integration.

BC-001: All endpoints scoped by company_id from authenticated user.
BC-008: Every public method wrapped in try/except — never crash.
BC-011: All endpoints require authentication.
BC-012: All timestamps UTC.
"""

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.exceptions import AuthorizationError
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("parwa.escalation")

router = APIRouter(prefix="/api/escalation", tags=["Escalation"])

# ── Singleton ─────────────────────────────────────────────────────────────

_escalation_manager = None
_manager_lock = threading.Lock()


def _get_manager():
    """Return the singleton GracefulEscalationManager instance."""
    global _escalation_manager
    if _escalation_manager is None:
        with _manager_lock:
            if _escalation_manager is None:
                from app.core.graceful_escalation import GracefulEscalationManager

                _escalation_manager = GracefulEscalationManager()
    return _escalation_manager


# ── Pydantic Schemas ─────────────────────────────────────────────────────


class AcknowledgeRequest(BaseModel):
    note: Optional[str] = Field(
        default=None, description="Optional acknowledgment note"
    )


class ResolveRequest(BaseModel):
    resolution: str = Field(..., description="How the escalation was resolved")
    outcome: str = Field(
        ...,
        description="Resolution outcome: resolved, human_took_over, auto_resolved, dismissed, expired, reassigned",
    )


class ManualEscalationRequest(BaseModel):
    trigger_type: str = Field(
        default="manual_request", description="Trigger type for the manual escalation"
    )
    severity: str = Field(
        default="medium", description="Severity level: low, medium, high, critical"
    )
    description: str = Field(
        ..., description="Human-readable description of the escalation reason"
    )
    ticket_id: Optional[str] = Field(default=None, description="Associated ticket ID")
    customer_id: Optional[str] = Field(
        default=None, description="Associated customer ID"
    )


class PeerReviewSubmitRequest(BaseModel):
    decision: str = Field(
        ..., description="Review decision: approve, request_changes, reject"
    )
    feedback: Optional[str] = Field(
        default=None, description="Feedback for the junior agent"
    )


# ── Helpers ──────────────────────────────────────────────────────────────


def _record_to_dict(record) -> Dict[str, Any]:
    """Convert an EscalationRecord dataclass to a serializable dict."""
    if record is None:
        return {}
    from dataclasses import asdict

    d = asdict(record)
    # Ensure metadata dict is always present
    if not isinstance(d.get("metadata"), dict):
        d["metadata"] = {}
    return d


def _get_company_id(user: User) -> str:
    """Extract company_id from user or raise AuthorizationError."""
    cid = user.company_id
    if not cid:
        raise AuthorizationError(message="User has no associated company")
    return str(cid)


def _peer_review_service(db: Session):
    """Lazy-instantiate PeerReviewService."""
    from app.services.peer_review_service import PeerReviewService

    return PeerReviewService(db)


# ════════════════════════════════════════════════════════════════════════
# Endpoints
# ════════════════════════════════════════════════════════════════════════


@router.get("/active")
def list_active_escalations(
    severity: Optional[str] = Query(
        None, description="Filter by severity: low, medium, high, critical"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
):
    """List active (non-resolved) escalations for the current company.

    Returns paginated list sorted by creation time (most recent first).
    """
    company_id = _get_company_id(user)
    mgr = _get_manager()

    if severity:
        records = mgr.get_escalations_by_severity(company_id, severity)
    else:
        records = mgr.get_active_escalations(company_id)

    total = len(records)
    page = records[offset : offset + limit]

    return {
        "items": [_record_to_dict(r) for r in page],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/history")
def list_resolved_escalations(
    date_from: Optional[str] = Query(None, description="ISO-8601 start date"),
    date_to: Optional[str] = Query(None, description="ISO-8601 end date"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
):
    """List resolved escalation history for the current company.

    Optionally filter by date range. Returns paginated results.
    """
    company_id = _get_company_id(user)
    mgr = _get_manager()

    # Gather all company escalations and filter resolved
    all_records = mgr.get_active_escalations(company_id)
    # get_active_escalations only returns non-resolved, so we need the
    # internal dict directly to also get resolved ones.
    with mgr._lock:
        escalation_ids = mgr._company_escalations.get(company_id, [])
        all_company = [
            mgr._escalations[eid]
            for eid in escalation_ids
            if eid in mgr._escalations and mgr._escalations[eid].status == "resolved"
        ]

    # Date filtering
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            all_company = [
                r
                for r in all_company
                if r.resolved_at and datetime.fromisoformat(r.resolved_at) >= dt_from
            ]
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            all_company = [
                r
                for r in all_company
                if r.resolved_at and datetime.fromisoformat(r.resolved_at) <= dt_to
            ]
        except ValueError:
            pass

    # Sort by resolved_at descending
    all_company.sort(key=lambda r: r.resolved_at or "", reverse=True)

    total = len(all_company)
    page = all_company[offset : offset + limit]

    return {
        "items": [_record_to_dict(r) for r in page],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats")
def escalation_stats(
    user: User = Depends(get_current_user),
):
    """Get escalation statistics for the current company.

    Returns: total_active, total_resolved_24h, by_severity counts,
    by_trigger_type counts, avg_resolution_time.
    """
    company_id = _get_company_id(user)
    mgr = _get_manager()

    stats = mgr.get_statistics(company_id)

    # Compute resolved-in-last-24h
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with mgr._lock:
        escalation_ids = mgr._company_escalations.get(company_id, [])
        resolved_24h = sum(
            1
            for eid in escalation_ids
            if eid in mgr._escalations
            and mgr._escalations[eid].status == "resolved"
            and mgr._escalations[eid].resolved_at
            and mgr._escalations[eid].resolved_at >= cutoff
        )

    return {
        "total_active": stats.get("active_escalations", 0),
        "total_resolved_24h": resolved_24h,
        "by_severity": stats.get("by_severity", {}),
        "by_trigger_type": stats.get("by_trigger", {}),
        "avg_resolution_time_seconds": stats.get("avg_resolution_time_seconds", 0.0),
        "total_escalations": stats.get("total_escalations", 0),
        "resolved_escalations": stats.get("resolved_escalations", 0),
        "by_outcome": stats.get("by_outcome", {}),
    }


@router.post("/{escalation_id}/acknowledge")
def acknowledge_escalation(
    escalation_id: str,
    body: AcknowledgeRequest = AcknowledgeRequest(),
    user: User = Depends(require_roles("owner", "admin", "agent")),
):
    """Acknowledge an active escalation.

    Marks the escalation as acknowledged and assigns it to the current user.
    """
    company_id = _get_company_id(user)
    mgr = _get_manager()

    record = mgr.acknowledge_escalation(
        company_id=company_id,
        escalation_id=escalation_id,
        acknowledged_by=str(user.id),
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Escalation not found")

    result = _record_to_dict(record)
    if body.note:
        result["acknowledgment_note"] = body.note
    return result


@router.post("/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: str,
    body: ResolveRequest,
    user: User = Depends(require_roles("owner", "admin", "agent")),
):
    """Resolve an escalation.

    Marks the escalation as resolved with the given outcome and resolution notes.
    """
    company_id = _get_company_id(user)
    mgr = _get_manager()

    # Validate outcome
    from app.core.graceful_escalation import EscalationOutcome

    valid_outcomes = [o.value for o in EscalationOutcome]
    if body.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome: {
                body.outcome}. Must be one of: {
                ', '.join(
                    sorted(valid_outcomes))}",
        )

    record = mgr.resolve_escalation(
        company_id=company_id,
        escalation_id=escalation_id,
        outcome=body.outcome,
        resolved_by=str(user.id),
        response_message=body.resolution,
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Escalation not found")

    return _record_to_dict(record)


@router.post("/manual")
def create_manual_escalation(
    body: ManualEscalationRequest,
    user: User = Depends(require_roles("owner", "admin", "agent")),
):
    """Create a manual escalation.

    Allows agents/admins to manually escalate an issue.
    """
    company_id = _get_company_id(user)
    mgr = _get_manager()

    # Validate severity
    from app.core.graceful_escalation import EscalationSeverity

    valid_severities = [s.value for s in EscalationSeverity]
    if body.severity not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity: {
                body.severity}. Must be one of: {
                ', '.join(
                    sorted(valid_severities))}",
        )

    from app.core.graceful_escalation import EscalationContext

    ctx = EscalationContext(
        company_id=company_id,
        ticket_id=body.ticket_id or "",
        trigger=body.trigger_type,
        severity=body.severity,
        description=body.description,
        agent_id=str(user.id),
        metadata={
            "source": "manual",
            "customer_id": body.customer_id,
        },
    )

    record = mgr.create_escalation(company_id, ctx)

    if record is None:
        raise HTTPException(
            status_code=429,
            detail="Escalation could not be created (rate limited or max active reached)",
        )

    return _record_to_dict(record)


# ── Peer Review Integration ──────────────────────────────────────────────


@router.get("/peer-review/pending")
def list_pending_peer_reviews(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending peer reviews for the current company.

    Returns the review queue for the current user (as senior reviewer).
    """
    company_id = _get_company_id(user)
    svc = _peer_review_service(db)

    result = svc.get_review_queue(
        company_id=company_id,
        senior_agent_id=str(user.id),
        status="pending",
        limit=limit,
        offset=offset,
    )

    return result


@router.post("/peer-review/{escalation_id}/review")
def submit_peer_review(
    escalation_id: str,
    body: PeerReviewSubmitRequest,
    user: User = Depends(require_roles("owner", "admin", "agent")),
    db: Session = Depends(get_db),
):
    """Submit a peer review for a junior-to-senior escalation.

    Decision can be: approve, request_changes, or reject.
    """
    company_id = _get_company_id(user)
    svc = _peer_review_service(db)

    # Validate decision
    valid_decisions = ("approve", "request_changes", "reject")
    if body.decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision: {
                body.decision}. Must be one of: {
                ', '.join(valid_decisions)}",
        )

    approved = body.decision == "approve"
    reviewed_response = f"Peer review {
        body.decision}d by {
        user.full_name or user.id}"

    result = svc.submit_review(
        company_id=company_id,
        escalation_id=escalation_id,
        senior_agent_id=str(user.id),
        reviewed_response=reviewed_response,
        feedback=body.feedback,
        approved=approved,
    )

    return result
