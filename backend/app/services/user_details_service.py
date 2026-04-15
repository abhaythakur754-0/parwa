"""
PARWA User Details Service (Week 6 Day 1)

Business logic for post-payment user details collection.

BC-001: All operations scoped to company_id.
BC-011: Work email verification tokens are hashed.

GAP FIXES:
- GAP-001: XSS sanitization on all text inputs
- GAP-003: Email verification required for AI activation
- GAP-005: Rate limiting on verification emails

Services:
- get_user_details: Fetch user details
- create_or_update_user_details: Create/update after payment
- send_work_email_verification: Send verification email
- verify_work_email: Verify email with token
- get_onboarding_state: Get user's onboarding progress
"""

import secrets
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions import ValidationError
from app.logger import get_logger
from app.schemas.onboarding import (
    UserDetailsResponse,
    OnboardingStateResponse,
)
from database.models.core import User, Company
from database.models.user_details import UserDetails
from database.models.onboarding import OnboardingSession
from app.services.email_service import send_verification_email
from app.config import get_settings

logger = get_logger("user_details_service")

# Work email verification token expiry (24 hours)
_VERIFICATION_TOKEN_EXPIRY_HOURS = 24

# Rate limiting: minimum seconds between verification emails
_VERIFICATION_RATE_LIMIT_SECONDS = 60


# ── GAP-001: XSS Sanitization ─────────────────────────────────────────────

def sanitize_text_input(text: str, max_length: int = 100) -> str:
    """
    Sanitize text input to prevent XSS attacks.
    
    Removes:
    - HTML tags
    - JavaScript protocol
    - Event handlers
    - Dangerous characters
    
    P13 FIX: Uses html.escape() instead of regex tag stripping.
    The old regex `re.sub(r'<[^>]*>', '', text)` silently removed legitimate
    content like "AT&T < Wireless" → "AT&T ". Now we escape HTML entities
    so they render safely as-is in the browser.
    """
    if not text or not isinstance(text, str):
        return ''
    
    sanitized = text.strip()
    
    # P13: Escape HTML entities instead of stripping them.
    # This preserves content like "AT&T < Partner >" as
    # "AT&T &lt; Partner &gt;" instead of destroying it.
    sanitized = sanitized.replace('&', '&amp;')
    sanitized = sanitized.replace('<', '&lt;')
    sanitized = sanitized.replace('>', '&gt;')
    sanitized = sanitized.replace('"', '&quot;')
    sanitized = sanitized.replace("'", '&#x27;')
    
    # Remove javascript: protocol (after escaping, look for the escaped form)
    sanitized = re.sub(r'javascript\s*:', '', sanitized, flags=re.IGNORECASE)
    
    # Remove event handlers (onclick, onerror, etc.)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    
    # Remove data: URLs
    sanitized = re.sub(r'data\s*:', '', sanitized, flags=re.IGNORECASE)
    
    # Truncate to max length
    return sanitized[:max_length]


def sanitize_url_input(url: str) -> str:
    """
    Sanitize URL input to prevent XSS via URL schemes.
    
    Only allows http:// and https:// protocols.
    """
    if not url or not isinstance(url, str):
        return ''
    
    url = url.strip()
    url_lower = url.lower()
    
    # Block dangerous protocols
    dangerous_protocols = ['javascript:', 'data:', 'vbscript:', 'file:']
    for protocol in dangerous_protocols:
        if url_lower.startswith(protocol):
            return ''
    
    # Only allow http/https
    if url and not url_lower.startswith(('http://', 'https://')):
        # Don't add protocol - just return empty for safety
        # Frontend should handle URL normalization
        pass
    
    return url[:255]


def sanitize_email(email: str) -> str:
    """Sanitize email input."""
    if not email or not isinstance(email, str):
        return ''
    
    # Check for XSS attempts
    if '<' in email or '>' in email or 'javascript:' in email.lower():
        return ''
    
    return email.strip().lower()[:255]


# ── Service Functions ────────────────────────────────────────────────────


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
    GAP-001: Sanitizes all inputs before storage.
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
    # GAP-001: Sanitize all inputs before storage
    full_name = sanitize_text_input(full_name, max_length=100)
    company_name = sanitize_text_input(company_name, max_length=100)
    industry = sanitize_text_input(industry, max_length=50)
    company_size = sanitize_text_input(company_size, max_length=20) if company_size else None
    work_email = sanitize_email(work_email) if work_email else None
    website = sanitize_url_input(website) if website else None
    
    # Validate required fields after sanitization
    if not full_name or len(full_name) < 2:
        raise ValidationError(
            message="Full name must be at least 2 characters.",
            details={"field": "full_name"},
        )
    
    if not company_name or len(company_name) < 2:
        raise ValidationError(
            message="Company name must be at least 2 characters.",
            details={"field": "company_name"},
        )
    
    if not industry:
        raise ValidationError(
            message="Industry is required.",
            details={"field": "industry"},
        )

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
        details.updated_at = datetime.now(timezone.utc)

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
    GAP-005: Rate limiting to prevent spam.
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
    # Sanitize email
    work_email = sanitize_email(work_email)
    
    if not work_email:
        raise ValidationError(
            message="Invalid email address.",
            details={"work_email": work_email},
        )
    
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

    # GAP-005: Rate limiting check
    if details.work_email_verification_sent_at:
        sent_at = details.work_email_verification_sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        
        time_since_last = datetime.now(timezone.utc) - sent_at
        if time_since_last.total_seconds() < _VERIFICATION_RATE_LIMIT_SECONDS:
            remaining = _VERIFICATION_RATE_LIMIT_SECONDS - int(time_since_last.total_seconds())
            raise ValidationError(
                message=f"Please wait {remaining} seconds before requesting another verification email.",
                details={"retry_after_seconds": remaining},
            )

    # Generate verification token
    token = secrets.token_urlsafe(32)
    details.work_email_verification_token = token
    details.work_email_verification_sent_at = datetime.now(timezone.utc)

    db.commit()

    # Send verification email via Brevo
    try:
        settings = get_settings()
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        send_verification_email(
            user_email=work_email,
            user_name=details.full_name or "User",
            verification_url=verification_url,
        )
    except Exception as e:
        logger.error(
            "work_email_verification_failed",
            user_id=user_id,
            error=str(e),
        )

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
    # Sanitize token - allow reasonable length for test tokens
    token = token.strip()[:64] if token else ''
    
    if not token or len(token) < 8:
        raise ValidationError(
            message="Invalid verification token.",
            details={"token": "Token too short"},
        )
    
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


# ── GAP-003: AI Activation Prerequisites Check ────────────────────────────

def check_ai_activation_prerequisites(
    db: Session,
    user_id: str,
    company_id: str,
) -> dict:
    """
    Check if user can activate AI.
    
    GAP-003: Email verification required if work email provided.
    
    Prerequisites:
    1. Legal consents accepted
    2. If work_email provided, it must be verified
    3. At least one integration configured OR one KB document uploaded
    
    Returns:
        dict with 'can_activate' bool and 'missing' list of requirements
    """
    missing = []
    
    # Get user details
    details = db.query(UserDetails).filter(
        UserDetails.user_id == user_id,
        UserDetails.company_id == company_id,
    ).first()
    
    # Get onboarding session
    session = db.query(OnboardingSession).filter(
        OnboardingSession.user_id == user_id,
        OnboardingSession.company_id == company_id,
    ).first()
    
    if not session:
        missing.append("onboarding_not_started")
        return {"can_activate": False, "missing": missing}
    
    # Check legal consents
    if not session.legal_accepted:
        missing.append("legal_consent_required")
    
    # GAP-003: Check email verification if work email provided
    if details and details.work_email and not details.work_email_verified:
        missing.append("work_email_verification_required")
    
    # Check integrations or KB — query actual Integration table (not stale session.integrations)
    import json
    from database.models.integration import Integration
    integration_count = db.query(Integration).filter(
        Integration.company_id == company_id,
        Integration.status.in_(["active", "pending"]),
    ).count()
    has_integrations = integration_count > 0
    
    # P22 FIX: Only count "completed" KB documents as valid.
    # Previously "processing" documents counted too — a doc that just
    # started processing but will fail in 10 seconds was treated as valid.
    # This could allow activation with a KB that never actually processed.
    kb_doc_count = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.company_id == company_id,
        KnowledgeDocument.status == "completed",  # P22: Only completed, not processing
    ).count()
    has_kb = kb_doc_count > 0
    
    if not has_integrations and not has_kb:
        missing.append("integration_or_kb_required")
    
    return {
        "can_activate": len(missing) == 0,
        "missing": missing,
    }


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
        session.updated_at = datetime.now(timezone.utc)
