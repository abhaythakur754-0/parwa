"""
PARWA User Details Router (Week 6 Day 1)

Endpoints for post-payment user details collection.

Public context (after payment, before onboarding):
- GET  /api/onboarding/state - Get onboarding state
- GET  /api/user/details - Get current user details
- POST /api/user/details - Submit user details
- PATCH /api/user/details - Update user details
- POST /api/user/verify-work-email - Send verification
- POST /api/user/verify-work-email/confirm - Confirm with token

BC-001: All operations scoped to authenticated user's company_id.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.schemas.onboarding import (
    UserDetailsRequest,
    UserDetailsResponse,
    WorkEmailVerificationRequest,
    WorkEmailVerificationResponse,
    VerifyWorkEmailRequest,
    OnboardingStateResponse,
    MessageResponse,
)
from app.services.user_details_service import (
    get_user_details,
    create_or_update_user_details,
    send_work_email_verification,
    verify_work_email,
    get_onboarding_state,
)
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api", tags=["Onboarding"])


# ── Onboarding State ────────────────────────────────────────────────


@router.get(
    "/onboarding/state",
    response_model=OnboardingStateResponse,
)
def get_state(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStateResponse:
    """Get the current onboarding state for the user.

    Week 6 Day 1: Returns progress through the onboarding wizard.
    Used to determine which step to show after payment.

    BC-001: Scoped to user's company_id.
    """
    return get_onboarding_state(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
    )


# ── User Details CRUD ────────────────────────────────────────────────


@router.get(
    "/user/details",
    response_model=UserDetailsResponse,
)
def get_details(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDetailsResponse:
    """Get the user details for the authenticated user.

    Week 6 Day 1: Returns post-payment details if submitted.
    Returns 404 if not yet submitted.

    BC-001: Scoped to user's company_id.
    """
    result = get_user_details(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
    )
    if not result:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="User details not found. Please submit details first.",
        )
    return result


@router.post(
    "/user/details",
    response_model=UserDetailsResponse,
    status_code=201,
)
def create_details(
    body: UserDetailsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDetailsResponse:
    """Submit user details after successful payment.

    Week 6 Day 1: Required before user can proceed to onboarding wizard.
    Collects: full_name, company_name, industry, work_email (optional).

    BC-001: Scoped to user's company_id.
    Marks details_completed in onboarding session.
    """
    return create_or_update_user_details(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        full_name=body.full_name,
        company_name=body.company_name,
        industry=body.industry,
        work_email=body.work_email,
        company_size=body.company_size,
        website=body.website,
    )


@router.patch(
    "/user/details",
    response_model=UserDetailsResponse,
)
def update_details(
    body: UserDetailsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDetailsResponse:
    """Update user details.

    Week 6 Day 1: Allows updating details after initial submission.
    If work_email changes, it will need re-verification.

    BC-001: Scoped to user's company_id.
    """
    return create_or_update_user_details(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        full_name=body.full_name,
        company_name=body.company_name,
        industry=body.industry,
        work_email=body.work_email,
        company_size=body.company_size,
        website=body.website,
    )


# ── Work Email Verification ──────────────────────────────────────────


@router.post(
    "/user/verify-work-email",
    response_model=WorkEmailVerificationResponse,
)
def send_verification(
    body: WorkEmailVerificationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkEmailVerificationResponse:
    """Send verification email for work email.

    Week 6 Day 1: Sends a verification email to the work email address.
    Token expires in 24 hours.

    BC-001: Scoped to user's company_id.
    """
    message = send_work_email_verification(
        db=db,
        user_id=user.id,
        company_id=user.company_id,
        work_email=body.work_email,
    )
    return WorkEmailVerificationResponse(
        message=message,
        work_email=body.work_email,
    )


@router.post(
    "/user/verify-work-email/confirm",
    response_model=MessageResponse,
)
def confirm_verification(
    body: VerifyWorkEmailRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Verify work email with token from email link.

    Week 6 Day 1: Public endpoint (no auth required).
    Token is single-use and expires after 24 hours.

    BC-011: Token is cryptographically random.
    """
    verify_work_email(db=db, token=body.token)
    return MessageResponse(
        message="Work email verified successfully."
    )
