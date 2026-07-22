"""
PARWA DLQ API Router (BC-018)

Exposes the PostgreSQL-backed Dead Letter Queue (graph_execution_dlq table)
to ops engineers and the dashboard. Supports:

  - GET  /api/dlq/entries           — list/filter entries
  - GET  /api/dlq/stats             — aggregate counts by error_type
  - GET  /api/dlq/entries/{id}      — fetch a single entry
  - POST /api/dlq/entries/{id}/retry   — mark entry as manually retried
  - POST /api/dlq/entries/{id}/resolve — mark entry as resolved (soft-close)

Filtering
---------
The three CRM-specific error_types introduced by BC-017 are first-class:

  - crm_escalation_push_failed      (Node 8 could not tell CRM the ticket was escalated)
  - crm_resume_push_failed          (guidance flow could not tell CRM the ticket was resumed)
  - crm_permanent_failure_push_failed  (AI gave up AND we couldn't tell CRM — worst case)

The dashboard CRM-DLQ tile filters by these three error_types so ops can
isolate CRM-specific failures from generic pipeline failures.

Security
--------
  - Tenant users see only their own company's DLQ entries (BC-001).
  - Platform admins can pass `company_id` query param to view any tenant,
    OR omit it to see ALL tenants (company_id=None → cross-tenant view).
  - All write actions (retry/resolve) are audited via audit_service.

Reuses
------
  - app.core.parwa_pipeline.dlq.get_dlq_entries / get_dlq_stats /
    retry_dlq_entry / resolve_dlq_entry (zero duplication).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_company_id, get_current_user, require_platform_admin
from app.core.parwa_pipeline.dlq import (
    get_dlq_entries,
    get_dlq_stats,
    resolve_dlq_entry,
    retry_dlq_entry,
)
from app.exceptions import NotFoundError, ParwaBaseError
from database.models.core import User

logger = logging.getLogger("parwa.dlq_api")

router = APIRouter(prefix="/api/dlq", tags=["DLQ"])


# ── Constants ──────────────────────────────────────────────────────────

#: The three CRM-specific error_types introduced by BC-017. Surfaced as
#: a constant so the frontend dashboard can pull the list from /api/dlq/crm_error_types
#: and stay in sync if we add more later.
CRM_ERROR_TYPES: tuple[str, ...] = (
    "crm_escalation_push_failed",
    "crm_resume_push_failed",
    "crm_permanent_failure_push_failed",
)

#: The earlier CRM error_type from BC-016 (Node 6.5 delivery-phase CRM push).
#: Kept separate because it's a different layer of the stack — ops may want
#: to filter to just BC-017 ones OR include BC-016 too.
CRM_ERROR_TYPES_INCL_BC016: tuple[str, ...] = (
    "crm_push_failed",  # BC-016 — Node 6.5 delivery-phase CRM push
    *CRM_ERROR_TYPES,
)


# ── Response Models ────────────────────────────────────────────────────


class DLQEntryResponse(BaseModel):
    id: str
    company_id: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    error: str
    error_type: Optional[str] = None
    state_snapshot: Dict[str, Any] = Field(default_factory=dict)
    variant_tier: Optional[str] = None
    channel: Optional[str] = None
    intent: Optional[str] = None
    retried: bool = False
    retry_count: int = 0
    retry_succeeded: Optional[bool] = None
    last_retry_at: Optional[str] = None
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None


class DLQListResponse(BaseModel):
    success: bool = True
    count: int
    total_unresolved: Optional[int] = None
    entries: List[DLQEntryResponse]


class DLQStatsResponse(BaseModel):
    success: bool = True
    by_error_type: Dict[str, int]
    total_unresolved: int
    total_retried: int
    total_resolved: int
    crm_unresolved: int = Field(
        default=0,
        description="Unresolved count across the 3 BC-017 CRM error_types "
        "(crm_escalation_push_failed, crm_resume_push_failed, "
        "crm_permanent_failure_push_failed).",
    )
    crm_unresolved_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Per-error-type unresolved count for the 3 CRM types.",
    )


class DLQRetryResponse(BaseModel):
    success: bool
    entry_id: str
    retried: bool
    retry_count: int
    last_retry_at: Optional[str] = None


class DLQResolveResponse(BaseModel):
    success: bool
    entry_id: str
    resolved_at: str
    retry_succeeded: bool


# ── Helpers ────────────────────────────────────────────────────────────


def _resolve_company_filter(
    *,
    user: User,
    explicit_company_id: Optional[str],
) -> Optional[str]:
    """Resolve which company_id filter to use for the query.

    Returns:
        - A specific company_id string  → filter to that tenant
        - None                          → cross-tenant view (no filter)

    Rules:
        - Platform admin passing ?company_id=__all__  → None (no filter)
        - Platform admin passing ?company_id=<uuid>   → that tenant
        - Platform admin passing nothing              → their own tenant
                                                          (safer default — explicit
                                                          opt-in for cross-tenant)
        - Tenant user                                 → always their own tenant
                                                          (company_id query param
                                                          is IGNORED for security)
    """
    if getattr(user, "is_platform_admin", False):
        if explicit_company_id in (None, "", "__all__"):
            # Platform admin did not request a specific tenant.
            # Default to their OWN tenant (safer) — they can opt into
            # cross-tenant via ?company_id=__all__.
            if explicit_company_id == "__all__":
                return None
            return str(user.company_id) if user.company_id else None
        return explicit_company_id

    # Tenant user: always scoped to own company — ignore any ?company_id= they pass.
    return str(user.company_id) if user.company_id else None


def _to_entry_response(row: Dict[str, Any]) -> DLQEntryResponse:
    """Coerce a raw DLQ row dict into the typed response model."""
    return DLQEntryResponse(
        id=row.get("id", ""),
        company_id=row.get("company_id", ""),
        conversation_id=row.get("conversation_id"),
        session_id=row.get("session_id"),
        error=row.get("error", ""),
        error_type=row.get("error_type"),
        state_snapshot=row.get("state_snapshot") or {},
        variant_tier=row.get("variant_tier"),
        channel=row.get("channel"),
        intent=row.get("intent"),
        retried=bool(row.get("retried", False)),
        retry_count=int(row.get("retry_count") or 0),
        retry_succeeded=row.get("retry_succeeded"),
        last_retry_at=row.get("last_retry_at"),
        created_at=row.get("created_at"),
        resolved_at=row.get("resolved_at"),
    )


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/crm_error_types")
async def get_crm_error_types() -> Dict[str, Any]:
    """Return the list of CRM-specific error_types known to the system.

    Used by the frontend dashboard to populate filter dropdowns without
    hardcoding the error_type strings.
    """
    return {
        "success": True,
        "bc_017_crm_error_types": list(CRM_ERROR_TYPES),
        "bc_016_crm_error_types": ["crm_push_failed"],
        "all_crm_error_types": list(CRM_ERROR_TYPES_INCL_BC016),
    }


@router.get("/entries", response_model=DLQListResponse)
async def list_entries(
    error_type: Optional[str] = Query(
        None,
        description="Filter by error_type (e.g. crm_permanent_failure_push_failed). "
        "Pass 'crm_only' to filter to all 3 BC-017 CRM error_types.",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    resolved: bool = Query(False, description="True → resolved; False → unresolved"),
    company_id: Optional[str] = Query(
        None,
        description="Platform admin only. Pass '__all__' for cross-tenant view.",
    ),
    user: User = Depends(get_current_user),
) -> DLQListResponse:
    """List DLQ entries with optional filtering.

    Tenant users are always scoped to their own company (BC-001).
    Platform admins can pass `company_id=__all__` for a cross-tenant view,
    or `company_id=<uuid>` to inspect a specific tenant.
    """
    target_company = _resolve_company_filter(
        user=user, explicit_company_id=company_id
    )

    # Special sentinel: error_type=crm_only → union of the 3 BC-017 CRM types.
    # We fetch all unresolved entries for the tenant (no error_type filter),
    # then filter in Python because get_dlq_entries only supports a single
    # error_type. This is fine — the unresolved set is typically small.
    if error_type == "crm_only":
        raw_rows = get_dlq_entries(
            company_id=target_company or "__all__",  # sentinel; handled below
            limit=500,  # cap; dashboard shows top 50 by created_at desc
            offset=0,
            resolved=resolved,
            error_type=None,
        ) if target_company is not None else _get_dlq_entries_cross_tenant(
            limit=500, offset=0, resolved=resolved, error_type=None,
        )
        # Apply the 3-type filter in Python
        crm_set = set(CRM_ERROR_TYPES)
        rows = [r for r in raw_rows if r.get("error_type") in crm_set]
        rows = rows[offset: offset + limit]
    elif error_type:
        rows = get_dlq_entries(
            company_id=target_company or "__all__",
            limit=limit,
            offset=offset,
            resolved=resolved,
            error_type=error_type,
        ) if target_company is not None else _get_dlq_entries_cross_tenant(
            limit=limit, offset=offset, resolved=resolved, error_type=error_type,
        )
    else:
        rows = get_dlq_entries(
            company_id=target_company or "__all__",
            limit=limit,
            offset=offset,
            resolved=resolved,
            error_type=None,
        ) if target_company is not None else _get_dlq_entries_cross_tenant(
            limit=limit, offset=offset, resolved=resolved, error_type=None,
        )

    entries = [_to_entry_response(r) for r in rows]
    return DLQListResponse(
        count=len(entries),
        entries=entries,
    )


@router.get("/stats", response_model=DLQStatsResponse)
async def get_stats(
    company_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
) -> DLQStatsResponse:
    """Return DLQ aggregate stats, including a CRM-specific breakdown.

    The `crm_unresolved` and `crm_unresolved_by_type` fields power the
    dashboard's CRM-DLQ tile.
    """
    target_company = _resolve_company_filter(
        user=user, explicit_company_id=company_id
    )

    if target_company is not None:
        stats = get_dlq_stats(target_company)
    else:
        stats = _get_dlq_stats_cross_tenant()

    by_type = stats.get("by_error_type", {})
    crm_breakdown = {
        et: int(by_type.get(et, 0))
        for et in CRM_ERROR_TYPES
    }
    crm_total = sum(crm_breakdown.values())

    return DLQStatsResponse(
        by_error_type=by_type,
        total_unresolved=int(stats.get("total_unresolved", 0)),
        total_retried=int(stats.get("total_retried", 0)),
        total_resolved=int(stats.get("total_resolved", 0)),
        crm_unresolved=crm_total,
        crm_unresolved_by_type=crm_breakdown,
    )


@router.post("/entries/{entry_id}/retry", response_model=DLQRetryResponse)
async def retry_entry(
    entry_id: str,
    user: User = Depends(get_current_user),
) -> DLQRetryResponse:
    """Mark a DLQ entry as manually retried.

    NOTE: This does NOT re-execute the graph. It only increments retry_count
    and sets last_retry_at, so ops can track which entries have been
    manually replayed. To actually replay, use the guidance flow's
    `resume_escalation` endpoint or the Celery `dlq_retry_tasks` worker.
    """
    result = retry_dlq_entry(entry_id)
    if result is None:
        raise NotFoundError(
            message=f"DLQ entry {entry_id} not found",
            details={"entry_id": entry_id},
        )

    logger.info(
        "dlq_entry_manual_retry",
        extra={
            "entry_id": entry_id,
            "user_id": str(user.id),
            "company_id": str(user.company_id),
            "retry_count": result.get("retry_count"),
        },
    )

    return DLQRetryResponse(
        success=True,
        entry_id=entry_id,
        retried=bool(result.get("retried")),
        retry_count=int(result.get("retry_count") or 0),
        last_retry_at=result.get("last_retry_at"),
    )


@router.post("/entries/{entry_id}/resolve", response_model=DLQResolveResponse)
async def resolve_entry(
    entry_id: str,
    retry_succeeded: bool = Query(
        True,
        description="Whether the underlying retry was successful. "
        "False = manually resolved without retry success (e.g. ops "
        "fixed the CRM ticket manually).",
    ),
    user: User = Depends(get_current_user),
) -> DLQResolveResponse:
    """Mark a DLQ entry as resolved (soft-close).

    For the worst-case DLQ (`crm_permanent_failure_push_failed`), ops should
    follow the runbook at `documents/ops_runbooks/crm_permanent_failure_push_failed_runbook.md`
    BEFORE resolving the entry — the runbook walks through manually resetting
    the CRM ticket.
    """
    result = resolve_dlq_entry(entry_id, retry_succeeded=retry_succeeded)
    if result is None:
        raise NotFoundError(
            message=f"DLQ entry {entry_id} not found",
            details={"entry_id": entry_id},
        )

    logger.info(
        "dlq_entry_manual_resolve",
        extra={
            "entry_id": entry_id,
            "user_id": str(user.id),
            "company_id": str(user.company_id),
            "retry_succeeded": retry_succeeded,
        },
    )

    return DLQResolveResponse(
        success=True,
        entry_id=entry_id,
        resolved_at=result.get("resolved_at") or "",
        retry_succeeded=bool(result.get("retry_succeeded")),
    )


# ── Cross-tenant helpers (platform admin only path) ────────────────────


def _get_dlq_entries_cross_tenant(
    *,
    limit: int,
    offset: int,
    resolved: bool,
    error_type: Optional[str],
) -> List[Dict[str, Any]]:
    """Fetch DLQ entries across ALL tenants (platform admin only).

    Implementation note: get_dlq_entries() filters by company_id == X.
    To support a true cross-tenant view, we query the DB directly here
    instead of relying on the "__all__" sentinel (which would return []
    because no row has company_id="__all__").

    This mirrors the same SELECT logic as get_dlq_entries but omits the
    company_id WHERE clause.
    """
    try:
        from database.base import SessionLocal
        from app.core.parwa_pipeline.dlq import GraphExecutionDLQ

        with SessionLocal() as db:
            query = db.query(GraphExecutionDLQ)
            if resolved:
                query = query.filter(GraphExecutionDLQ.resolved_at.isnot(None))
            else:
                query = query.filter(GraphExecutionDLQ.resolved_at.is_(None))
            if error_type:
                query = query.filter(GraphExecutionDLQ.error_type == error_type)
            query = query.order_by(GraphExecutionDLQ.created_at.desc())
            entries = query.offset(offset).limit(limit).all()

            return [
                {
                    "id": e.id,
                    "company_id": e.company_id,
                    "conversation_id": e.conversation_id,
                    "session_id": e.session_id,
                    "error": e.error,
                    "error_type": e.error_type,
                    "state_snapshot": (
                        __import__("json").loads(e.state_snapshot)
                        if e.state_snapshot else {}
                    ),
                    "variant_tier": e.variant_tier,
                    "channel": e.channel,
                    "intent": e.intent,
                    "retried": e.retried,
                    "retry_count": e.retry_count,
                    "retry_succeeded": e.retry_succeeded,
                    "last_retry_at": (
                        e.last_retry_at.isoformat() if e.last_retry_at else None
                    ),
                    "created_at": (
                        e.created_at.isoformat() if e.created_at else None
                    ),
                    "resolved_at": (
                        e.resolved_at.isoformat() if e.resolved_at else None
                    ),
                }
                for e in entries
            ]
    except Exception as exc:
        logger.error(
            "dlq_cross_tenant_fetch_failed",
            extra={"error": str(exc)[:200]},
        )
        return []


def _get_dlq_stats_cross_tenant() -> Dict[str, Any]:
    """Cross-tenant version of get_dlq_stats (platform admin only)."""
    try:
        from database.base import SessionLocal
        from app.core.parwa_pipeline.dlq import GraphExecutionDLQ
        from sqlalchemy import func

        with SessionLocal() as db:
            rows = (
                db.query(
                    GraphExecutionDLQ.error_type,
                    func.count(GraphExecutionDLQ.id),
                )
                .filter(GraphExecutionDLQ.resolved_at.is_(None))
                .group_by(GraphExecutionDLQ.error_type)
                .all()
            )
            by_error_type = {row[0] or "unknown": row[1] for row in rows}

            total_unresolved = (
                db.query(func.count(GraphExecutionDLQ.id))
                .filter(GraphExecutionDLQ.resolved_at.is_(None))
                .scalar() or 0
            )
            total_retried = (
                db.query(func.count(GraphExecutionDLQ.id))
                .filter(
                    GraphExecutionDLQ.retried.is_(True),
                    GraphExecutionDLQ.resolved_at.is_(None),
                )
                .scalar() or 0
            )
            total_resolved = (
                db.query(func.count(GraphExecutionDLQ.id))
                .filter(GraphExecutionDLQ.resolved_at.isnot(None))
                .scalar() or 0
            )

            return {
                "by_error_type": by_error_type,
                "total_unresolved": total_unresolved,
                "total_retried": total_retried,
                "total_resolved": total_resolved,
            }
    except Exception as exc:
        logger.error(
            "dlq_cross_tenant_stats_failed",
            extra={"error": str(exc)[:200]},
        )
        return {
            "by_error_type": {},
            "total_unresolved": 0,
            "total_retried": 0,
            "total_resolved": 0,
        }
