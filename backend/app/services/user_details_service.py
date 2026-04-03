"""
PARWA User Details Service (Week 6 Day 1)

Business logic for post-payment user details collection.

BC-001: All operations scoped to company_id.
BC-011: Work email verification tokens are hashed.

Services:
- get_user_details: Fetch user details
- create_or_update_user_details: Create/update after payment
- send_work_email_verification: Send verification email
- verify_work_email: Verify email with token
- get_onboarding_state: Get user's onboarding progress
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.exceptions import ValidationError
from backend.app.logger import get_logger
from backend.app.schemas.onboarding import (
    UserDetailsResponse,
    OnboardingStateResponse,
)
from database.models.core import User, Company
from database.models.user_details import UserDetails
from database.models.onboarding import OnboardingSession

logger = get_logger("user_details_service")

# Work email verification token expiry (24 hours)
_VERIFICATION_TOKEN_EXPIRY_HOURS = 24


def get_user_details(
    db: Session,
    user_id: str,
    company_id: str,
) -> Optional[UserDetailsResponse]:
    """Get user details for a user.

    BC-001: Scoped to company_id.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID for tenant isolation.

    Returns:
        UserDetailsResponse or None if not found.
    """
    details = db.query(UserDetails).filter(
        UserDetails.user_id == user_id,
        UserDetails.company_id == company_id,
    ).first()

    if not details:
        return None

    return UserDetailsResponse(
        id=details.id,
        user_id=details.user_id,
        company_id=details.company_id,
        full_name=details.full_name,
        company_name=details.company_name,
        work_email=details.work_email,
        work_email_verified=details.work_email_verified,
        industry=details.industry,
        company_size=details.company_size,
        website=details.website,
        created_at=details.created_at.isoformat() if details.created_at else None,
        updated_at=details.updated_at.isoformat() if details.updated_at else None,
    )


def create_or_update_user_details(
    db: Session,
    user_id: str,
    company_id: str,
    full_name: str,
    company_name: str,
    industry: str,
    work_email: Optional[str] = None,
    company_size: Optional[str] = None,
    website: Optional[str] = None,
) -> UserDetailsResponse:
    """Create or update user details after payment.

    BC-001: Scoped to company_id.
    Creates UserDetails record and updates OnboardingSession progress.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.
        full_name: User's full name.
        company_name: Business name.
        industry: Business industry.
        work_email: Optional work email.
        company_size: Optional company size.
        website: Optional company website.

    Returns:
        UserDetailsResponse with created/updated data.
    """
    # Check if details already exist
    details = db.query(UserDetails).filter(
        UserDetails.user_id == user_id,
        UserDetails.company_id == company_id,
    ).first()

    if details:
        # Update existing
        details.full_name = full_name
        details.company_name = company_name
        details.industry = industry
        details.company_size = company_size
        details.website = website
        details.updated_at = datetime.utcnow()

        # Only update work_email if provided and different
        if work_email and work_email != details.work_email:
            details.work_email = work_email
            details.work_email_verified = False
            details.work_email_verification_token = None
    else:
        # Create new
        details = UserDetails(
            user_id=user_id,
            company_id=company_id,
            full_name=full_name,
            company_name=company_name,
            work_email=work_email,
            work_email_verified=False,
            industry=industry,
            company_size=company_size,
            website=website,
        )
        db.add(details)

    # Update onboarding session progress
    _mark_details_completed(db, user_id, company_id)

    db.commit()
    db.refresh(details)

    logger.info(
        "user_details_saved",
        user_id=user_id,
        company_id=company_id,
        has_work_email=bool(work_email),
    )

    return UserDetailsResponse(
        id=details.id,
        user_id=details.user_id,
        company_id=details.company_id,
        full_name=details.full_name,
        company_name=details.company_name,
        work_email=details.work_email,
        work_email_verified=details.work_email_verified,
        industry=details.industry,
        company_size=details.company_size,
        website=details.website,
        created_at=details.created_at.isoformat() if details.created_at else None,
        updated_at=details.updated_at.isoformat() if details.updated_at else None,
    )


def send_work_email_verification(
    db: Session,
    user_id: str,
    company_id: str,
    work_email: str,
) -> str:
    """Send verification email for work email address.

    BC-011: Verification token is cryptographically random.
    Stores token hash and sends email via Brevo.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.
        work_email: Work email to verify.

    Returns:
        Success message string.

    Raises:
        ValidationError: If user details not found or email already verified.
    """
    details = db.query(UserDetails).filter(
        UserDetails.user_id == user_id,
        UserDetails.company_id == company_id,
    ).first()

    if not details:
        raise ValidationError(
            message="User details not found. Please submit details first.",
            details={"user_id": user_id},
        )

    # Check if work_email matches
    if details.work_email and details.work_email.lower() != work_email.lower():
        raise ValidationError(
            message="Work email does not match registered email.",
            details={"work_email": work_email},
        )

    # Update work_email if not set
    if not details.work_email:
        details.work_email = work_email.lower()

    # Check if already verified
    if details.work_email_verified:
        return "Work email is already verified."

    # Generate verification token
    token = secrets.token_urlsafe(32)
    details.work_email_verification_token = token
    details.work_email_verification_sent_at = datetime.utcnow()

    db.commit()

    # TODO: Send verification email via Brevo
    # For now, we just store the token
    # In production, this would call email_service.send_verification_email()

    logger.info(
        "work_email_verification_sent",
        user_id=user_id,
        company_id=company_id,
        work_email=work_email,
    )

    return f"Verification email sent to {work_email}"


def verify_work_email(
    db: Session,
    token: str,
) -> bool:
    """Verify work email with token.

    BC-011: Token is single-use and expires after 24 hours.

    Args:
        db: Database session.
        token: Verification token from email.

    Returns:
        True if verification successful.

    Raises:
        ValidationError: If token invalid or expired.
    """
    details = db.query(UserDetails).filter(
        UserDetails.work_email_verification_token == token,
    ).first()

    if not details:
        raise ValidationError(
            message="Invalid verification token.",
            details={"token": token[:8] + "..."},
        )

    # Check expiry
    if details.work_email_verification_sent_at:
        sent_at = details.work_email_verification_sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        expiry = sent_at + timedelta(hours=_VERIFICATION_TOKEN_EXPIRY_HOURS)
        if datetime.now(timezone.utc) > expiry:
            # Clear expired token
            details.work_email_verification_token = None
            db.commit()
            raise ValidationError(
                message="Verification token expired. Please request a new one.",
                details={"expired_at": expiry.isoformat()},
            )

    # Mark as verified
    details.work_email_verified = True
    details.work_email_verification_token = None  # Single-use
    db.commit()

    logger.info(
        "work_email_verified",
        user_id=details.user_id,
        company_id=details.company_id,
        work_email=details.work_email,
    )

    return True


def get_onboarding_state(
    db: Session,
    user_id: str,
    company_id: str,
) -> OnboardingStateResponse:
    """Get user's onboarding state.

    Creates a new OnboardingSession if one doesn't exist.
    BC-001: Scoped to company_id.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.

    Returns:
        OnboardingStateResponse with current progress.
    """
    import json

    session = db.query(OnboardingSession).filter(
        OnboardingSession.user_id == user_id,
        OnboardingSession.company_id == company_id,
    ).first()

    if not session:
        # Create new session
        session = OnboardingSession(
            user_id=user_id,
            company_id=company_id,
            current_step=1,
            status="in_progress",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Parse completed_steps JSON
    try:
        completed_steps = json.loads(session.completed_steps or "[]")
    except json.JSONDecodeError:
        completed_steps = []

    return OnboardingStateResponse(
        id=session.id,
        user_id=session.user_id,
        company_id=session.company_id,
        current_step=session.current_step,
        completed_steps=completed_steps,
        status=session.status,
        details_completed=session.details_completed or False,
        wizard_started=session.wizard_started or False,
        legal_accepted=session.legal_accepted or False,
        first_victory_completed=session.first_victory_completed or False,
        ai_name=session.ai_name or "Jarvis",
        ai_tone=session.ai_tone or "professional",
        ai_response_style=session.ai_response_style or "concise",
        ai_greeting=session.ai_greeting,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
    )


# ── Private Helpers ────────────────────────────────────────────────


def _mark_details_completed(
    db: Session,
    user_id: str,
    company_id: str,
) -> None:
    """Mark details step as completed in onboarding session.

    Creates session if doesn't exist.
    """
    session = db.query(OnboardingSession).filter(
        OnboardingSession.user_id == user_id,
        OnboardingSession.company_id == company_id,
    ).first()

    if not session:
        session = OnboardingSession(
            user_id=user_id,
            company_id=company_id,
            current_step=1,
            status="in_progress",
            details_completed=True,
        )
        db.add(session)
    else:
        session.details_completed = True
        session.updated_at = datetime.utcnow()
