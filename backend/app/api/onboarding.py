"""
PARWA Onboarding Router (Week 6 — F-028, F-029, F-034, F-035)

Endpoints for onboarding wizard progression, legal consent,
AI activation, and first victory celebration.

- POST /api/onboarding/complete-step    — Complete a wizard step
- POST /api/onboarding/legal-consent    — Accept legal consents (Step 2)
- POST /api/onboarding/activate         — Activate AI assistant (Step 5)
- GET  /api/onboarding/prerequisites    — Check AI activation prerequisites
- GET  /api/onboarding/first-victory    — Get first victory status
- POST /api/onboarding/first-victory    — Mark first victory completed

BC-001: All operations scoped to authenticated user's company_id.
"""

from typing import List

from app.api.deps import get_current_user
from app.core.cold_start_service import get_cold_start_service
from app.schemas.onboarding import (
    AIConfigRequest,
    AIConfigResponse,
    LegalConsentRequest,
    LegalConsentResponse,
    MessageResponse,
    StepCompleteResponse,
)
from app.services.onboarding_service import (
    accept_legal_consents,
    activate_ai,
    complete_first_victory,
    complete_step,
    get_first_victory_status,
)
from app.services.user_details_service import check_ai_activation_prerequisites
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


# ── Step Completion ────────────────────────────────────────────────


@router.post(
    "/complete-step",
    response_model=StepCompleteResponse,
)
def api_complete_step(
    step: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StepCompleteResponse:
    """Complete a wizard step with race condition prevention.

    GAP 1 FIX: Uses row-level locking for atomic step transitions.
    Steps must be completed sequentially (no skipping).

    BC-001: Scoped to user's company_id.

    Args:
        step: Step number to complete (1-6).
    """
    result = complete_step(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        step=step,
    )
    return StepCompleteResponse(
        message=f"Step {step} completed successfully.",
        current_step=result["current_step"],
        completed_steps=result["completed_steps"],
    )


# ── Legal Consent (Step 2) ────────────────────────────────────────


@router.post(
    "/legal-consent",
    response_model=LegalConsentResponse,
)
def api_legal_consent(
    body: LegalConsentRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LegalConsentResponse:
    """Accept legal consents (Step 2).

    GAP 5 FIX: Uses server time for consent recording, not client time.
    Validates all three consents are accepted before recording.
    Creates an audit trail with IP and user agent.

    BC-001: Scoped to user's company_id.
    """
    # Extract client info for audit trail
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    result = accept_legal_consents(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        accept_terms=body.accept_terms,
        accept_privacy=body.accept_privacy,
        accept_ai_data=body.accept_ai_data,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return LegalConsentResponse(
        message=result["message"],
        terms_accepted_at=result["terms_accepted_at"],
        privacy_accepted_at=result["privacy_accepted_at"],
        ai_data_accepted_at=result["ai_data_accepted_at"],
    )


# ── AI Activation (Step 5) ────────────────────────────────────────


class PrerequisitesResponse(BaseModel):
    """Response for prerequisite check."""

    can_activate: bool
    missing: List[str] = []


@router.get(
    "/prerequisites",
    response_model=PrerequisitesResponse,
)
def api_get_prerequisites(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PrerequisitesResponse:
    """Check AI activation prerequisites.

    Returns which prerequisites are met and which are missing.
    Used by the frontend to show/hide the activation button.

    BC-001: Scoped to user's company_id.
    """
    prereqs = check_ai_activation_prerequisites(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
    )
    return PrerequisitesResponse(**prereqs)


@router.post(
    "/activate",
    response_model=AIConfigResponse,
)
def api_activate_ai(
    body: AIConfigRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    """Activate AI assistant for the company (Step 5).

    Validates all prerequisites before activation:
    - Legal consents accepted
    - Email verified (if work email provided)
    - At least one integration or KB document

    F-034: AI Activation Gate.

    BC-001: Scoped to user's company_id.
    """
    result = activate_ai(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        ai_name=body.ai_name,
        ai_tone=body.ai_tone,
        ai_response_style=body.ai_response_style,
        ai_greeting=body.ai_greeting,
    )

    return AIConfigResponse(
        ai_name=result["ai_name"],
        ai_tone=result["ai_tone"],
        ai_response_style=result["ai_response_style"],
        ai_greeting=result["ai_greeting"],
    )


class WarmupStatusResponse(BaseModel):
    """Response for warmup status check (P24)."""

    overall_status: str
    models_ready: int = 0
    models_total: int = 0
    fallback_used: bool = False
    message: str = ""


@router.get(
    "/warmup-status",
    response_model=WarmupStatusResponse,
)
def api_get_warmup_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarmupStatusResponse:
    """Check AI warmup progress after activation.

    P24 FIX: Allows the frontend to poll warmup progress and show
    the user when their AI models are fully ready.
    D8-P1 FIX: Handles horizontal scaling — if tenant not found in
    this instance's in-memory state (request routed to a different pod),
    silently triggers recovery warmup instead of returning "cold".
    """
    cold_start = get_cold_start_service()
    tenant_state = cold_start.get_tenant_status(user.company_id)

    if not tenant_state:
        # D8-P1: Tenant activated but this instance doesn't have warmup state.
        # This happens with horizontal scaling (multiple pods behind a LB).
        # Check if the session is actually completed in the DB.
        from database.models.onboarding import OnboardingSession
        from database.models.user_details import UserDetails

        session = (
            db.query(OnboardingSession)
            .filter(
                OnboardingSession.user_id == user.id,
                OnboardingSession.company_id == user.company_id,
            )
            .first()
        )

        if not session or session.status != "completed":
            return WarmupStatusResponse(
                overall_status="cold",
                message="No warmup initiated yet.",
            )

        # Session is completed — trigger recovery warmup on this instance.
        # recover_tenant_warmup() calls warmup_tenant() which is idempotent.
        details = (
            db.query(UserDetails)
            .filter(
                UserDetails.company_id == user.company_id,
            )
            .first()
        )
        variant_type = "mini_parwa"
        if details and details.company_size:
            size_to_variant = {
                "1_10": "mini_parwa",
                "11_50": "parwa",
                "51_200": "parwa",
                "201_500": "high_parwa",
                "501_1000": "high_parwa",
                "1000_plus": "high_parwa",
            }
            variant_type = size_to_variant.get(details.company_size, "mini_parwa")

        # Run warmup in background thread so the poll response isn't blocked
        import threading

        def _recovery_warmup():
            try:
                cold_start.recover_tenant_warmup(user.company_id, variant_type)
            except Exception:
                pass  # Non-blocking — next poll will retry

        threading.Thread(target=_recovery_warmup, daemon=True).start()

        return WarmupStatusResponse(
            overall_status="warming",
            models_ready=0,
            models_total=0,
            fallback_used=False,
            message="Warming up models on this instance...",
        )

    models_total = len(tenant_state.models_warmed)
    models_ready = sum(
        1 for ms in tenant_state.models_warmed.values() if ms.warmup_success
    )

    return WarmupStatusResponse(
        overall_status=tenant_state.overall_status.value,
        models_ready=models_ready,
        models_total=models_total,
        fallback_used=tenant_state.fallback_used,
        message=(
            f"{models_ready}/{models_total} models ready."
            if models_total > 0
            else "Warming up..."
        ),
    )


# ── First Victory (F-035) ─────────────────────────────────────────


@router.get(
    "/first-victory",
)
def api_get_first_victory(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get first victory celebration status.

    F-035: Returns whether the user has seen the celebration
    and their AI config for personalized celebration.

    BC-001: Scoped to user's company_id.
    """
    return get_first_victory_status(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
    )


@router.post(
    "/first-victory",
    response_model=MessageResponse,
)
def api_complete_first_victory(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Mark first victory celebration as completed.

    F-035: Confetti + redirect to dashboard after completion.

    BC-001: Scoped to user's company_id.
    """
    result = complete_first_victory(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
    )
    return MessageResponse(message=result["message"])
