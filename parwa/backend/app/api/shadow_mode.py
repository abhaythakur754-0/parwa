"""
Shadow Mode API Router: REST endpoints for Shadow Mode management.

Shadow Mode enables safe variant deployment through the progression:
  SHADOW → SUPERVISED → GRADUATED

Endpoints:
  - POST /api/shadow-mode/enable        — Enable shadow mode for a company
  - POST /api/shadow-mode/disable       — Disable shadow mode
  - GET  /api/shadow-mode/status        — Get current shadow mode status
  - POST /api/shadow-mode/promote       — Manually promote to next phase
  - POST /api/shadow-mode/graduate      — Complete graduation (shadow→live)
  - GET  /api/shadow-mode/comparisons   — Get comparison history
  - GET  /api/shadow-mode/statistics    — Get shadow mode statistics
  - POST /api/shadow-mode/review        — Submit human review (supervised mode)

All endpoints follow BC-001 (company_id scoping), BC-011 (JWT auth),
and BC-012 (structured JSON responses).

Import patterns:
  - Lazy service imports inside endpoint functions to avoid circular imports.
  - Dependencies: require_roles, get_company_id, get_current_user, get_db.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import (
    require_roles,
    get_company_id,
    get_current_user,
)
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/shadow-mode", tags=["shadow-mode"])


# ═══════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS (M-14: Pydantic models)
# ═══════════════════════════════════════════════════════════════════


class EnableShadowModeRequest(BaseModel):
    """Request to enable shadow mode for a company."""
    live_variant: str = Field(
        ..., description="Current live variant (mini_parwa, parwa)",
    )
    shadow_variant: str = Field(
        ..., description="Variant to test in shadow (parwa, parwa_high)",
    )
    sample_rate: float = Field(
        1.0, ge=0.01, le=1.0,
        description="Fraction of messages to shadow-process (0.01-1.0)",
    )
    auto_graduation_threshold: float = Field(
        0.95, ge=0.5, le=1.0,
        description="Quality threshold for auto-graduation",
    )
    auto_graduation_window: int = Field(
        100, ge=10, le=10000,
        description="Consecutive wins required for auto-graduation",
    )
    supervised_timeout_seconds: int = Field(
        300, ge=30, le=3600,
        description="Timeout before auto-fallback in supervised mode",
    )
    auto_promote_to_supervised: bool = Field(
        True, description="Auto-promote from shadow to supervised",
    )
    auto_promote_to_graduated: bool = Field(
        False, description="Auto-promote from supervised to graduated",
    )
    live_instance_id: Optional[str] = Field(
        None, description="Optional specific live instance ID",
    )
    shadow_instance_id: Optional[str] = Field(
        None, description="Optional specific shadow instance ID",
    )


class DisableShadowModeRequest(BaseModel):
    """Request to disable shadow mode."""
    reason: str = Field("", description="Reason for disabling")


class PromoteShadowModeRequest(BaseModel):
    """Request to manually promote shadow mode to next phase."""
    target_status: Optional[str] = Field(
        None, description="Target status (supervised, graduated). Auto-determined if not set.",
    )


class HumanReviewRequest(BaseModel):
    """Request to submit a human review for a shadow mode result."""
    result_id: str = Field(..., description="Shadow mode result ID")
    verdict: str = Field(
        ..., description="Verdict: shadow_better, live_better, equal, skip",
    )
    notes: str = Field("", description="Optional review notes")


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════


@router.post("/enable")
def enable_shadow_mode(
    body: EnableShadowModeRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Enable shadow mode for the company.

    Starts testing the shadow_variant against the live_variant.
    Both variants will process sampled messages, but only the live
    variant response is sent to customers.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    result = service.enable_shadow_mode(
        company_id=company_id,
        live_variant=body.live_variant,
        shadow_variant=body.shadow_variant,
        sample_rate=body.sample_rate,
        auto_graduation_threshold=body.auto_graduation_threshold,
        auto_graduation_window=body.auto_graduation_window,
        supervised_timeout_seconds=body.supervised_timeout_seconds,
        auto_promote_to_supervised=body.auto_promote_to_supervised,
        auto_promote_to_graduated=body.auto_promote_to_graduated,
        live_instance_id=body.live_instance_id or "",
        shadow_instance_id=body.shadow_instance_id or "",
        user_id=str(user.id) if user else "",
    )

    return {"status": "ok" if result.get("success") else "error", "data": result}


@router.post("/disable")
def disable_shadow_mode(
    body: DisableShadowModeRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Disable shadow mode for the company.

    Stops shadow processing immediately. The live variant continues
    handling all messages normally.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    result = service.disable_shadow_mode(
        company_id=company_id,
        reason=body.reason,
    )

    return {"status": "ok" if result.get("success") else "error", "data": result}


@router.get("/status")
def get_shadow_mode_status(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> dict:
    """Get current shadow mode status for the company.

    Returns the active shadow mode configuration, including
    live/shadow variants, sample rate, and quality statistics.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    status = service.get_status(company_id=company_id)

    return {"status": "ok", "data": status.to_dict()}


@router.post("/promote")
def promote_shadow_mode(
    body: PromoteShadowModeRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Manually promote shadow mode to the next phase.

    Progression: shadow → supervised → graduated
    Optionally specify target_status to skip phases.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    result = service.promote(
        company_id=company_id,
        target_status=body.target_status or "",
    )

    return {"status": "ok" if result.get("success") else "error", "data": result}


@router.post("/graduate")
def complete_graduation(
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin")),
) -> dict:
    """Complete graduation: make shadow variant the new live variant.

    This is the final step. The shadow variant becomes the production
    variant, and shadow mode is disabled.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    result = service.complete_graduation(company_id=company_id)

    return {"status": "ok" if result.get("success") else "error", "data": result}


@router.get("/comparisons")
def get_comparison_history(
    company_id: str = Depends(get_company_id),
    limit: int = Query(50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: User = Depends(get_current_user),
) -> dict:
    """Get shadow mode comparison history.

    Returns a list of comparison results between live and shadow
    variant responses, ordered by most recent first.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    comparisons = service.get_comparison_history(
        company_id=company_id,
        limit=limit,
        offset=offset,
    )

    return {
        "status": "ok",
        "data": {
            "comparisons": comparisons,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/statistics")
def get_shadow_mode_statistics(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
) -> dict:
    """Get shadow mode statistics for the company.

    Returns aggregate metrics including win rate, quality delta,
    latency comparison, and auto-graduation progress.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    stats = service.get_statistics(company_id=company_id)

    return {"status": "ok", "data": stats}


@router.post("/review")
def submit_human_review(
    body: HumanReviewRequest,
    company_id: str = Depends(get_company_id),
    user: User = Depends(require_roles("owner", "admin", "agent")),
) -> dict:
    """Submit a human review for a shadow mode comparison result.

    In supervised mode, human reviewers evaluate shadow variant
    responses before they are delivered to customers.
    """
    from app.services.shadow_mode_service import get_shadow_mode_service

    service = get_shadow_mode_service()
    result = service.record_human_review(
        company_id=company_id,
        result_id=body.result_id,
        verdict=body.verdict,
        reviewer_id=str(user.id) if user else "",
        notes=body.notes,
    )

    return {"status": "ok" if result.get("success") else "error", "data": result}
