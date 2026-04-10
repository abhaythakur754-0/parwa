"""
PARWA Verification Service (F-012)

Business logic for email verification flow.
- Token generation (256-bit, URL-safe)
- Token validation (exists, not expired, not used)
- Resend with rate limiting (3/email/hour)
- Invalidates previous unused tokens on resend
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.exceptions import RateLimitError
from app.logger import get_logger
from app.services.email_service import (
    send_verification_email,
)
from database.models.core import (
    User,
    VerificationToken,
)

logger = get_logger("verification_service")

# Token expiry: 24 hours (F-012 spec)
TOKEN_EXPIRE_HOURS = 24


def _hash_token(token: str) -> str:
    """Hash a verification token for DB storage (SHA-256)."""
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# Rate limit: 3 resends per email per hour (F-012 spec)
MAX_RESENDS_PER_HOUR = 3
RESEND_WINDOW_SECONDS = 3600


def _generate_token() -> str:
    """Generate a 256-bit URL-safe token."""
    return secrets.token_urlsafe(32)


def create_verification_token(
    db: Session, user: User
) -> str:
    """Create a new verification token for a user.

    Invalidates any previous unused tokens for this user.
    (F-012 spec: requesting new email invalidates old ones)

    Args:
        db: Database session.
        user: User object.

    Returns:
        The raw verification token string (for URL).
    """
    # Invalidate all previous unused tokens for user
    db.query(VerificationToken).filter(
        VerificationToken.user_id == user.id,
        VerificationToken.is_used == False,  # noqa: E712
    ).update({"is_used": True})

    # Create new token
    raw_token = _generate_token()
    token_hash = _hash_token(raw_token)
    token = VerificationToken(
        user_id=user.id,
        company_id=user.company_id,
        token_hash=token_hash,
        purpose="email_verification",
        is_used=False,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(hours=TOKEN_EXPIRE_HOURS)
        ),
    )
    db.add(token)
    db.flush()
    return raw_token


def verify_email(
    db: Session, token: str
) -> dict:
    """Verify an email using a token.

    F-012: Validates token exists, not expired, not used.
    Sets users.email_verified = True on success.

    Args:
        db: Database session.
        token: Raw verification token from URL.

    Returns:
        Dict with status, message, and redirect info.

    Raises:
        ValidationError: If token is invalid/expired.
    """
    token_hash = _hash_token(token)
    stored = db.query(VerificationToken).filter(
        VerificationToken.token_hash == token_hash
    ).first()

    if not stored:
        return {
            "status": "error",
            "message": "Invalid verification link.",
            "error_code": "TOKEN_INVALID",
        }

    # Check if already used
    if stored.is_used:
        return {
            "status": "info",
            "message": "This email is already verified.",
            "redirect_to": "/login",
        }

    # Check expiry
    now = datetime.now(timezone.utc)
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as tz
        expires_at = expires_at.replace(tzinfo=tz.utc)
    if expires_at < now:
        return {
            "status": "error",
            "message": (
                "This verification link has expired."
            ),
            "error_code": "TOKEN_EXPIRED",
            "can_resend": True,
        }

    # Mark token as used
    stored.is_used = True

    # Mark user email as verified
    user = db.query(User).filter(
        User.id == stored.user_id
    ).first()
    if user:
        user.is_verified = True

    # Invalidate all other unused tokens for user
    db.query(VerificationToken).filter(
        VerificationToken.user_id == stored.user_id,
        VerificationToken.is_used == False,  # noqa: E712
    ).update({"is_used": True})

    db.commit()

    logger.info(
        "email_verified",
        user_id=stored.user_id,
        token_id=stored.id,
    )

    return {
        "status": "success",
        "message": (
            "Email verified successfully. "
            "You can now log in."
        ),
        "redirect_to": "/login",
    }


def resend_verification_email(
    db: Session, email: str
) -> dict:
    """Resend a verification email.

    F-012: Rate limited to 3 per email per hour.
    Invalidates previous unused tokens.

    Args:
        db: Database session.
        email: User's email address.

    Returns:
        Dict with status and message.

    Raises:
        ValidationError: If rate limited or email not found.
    """
    # Find user
    user = db.query(User).filter(
        User.email == email.lower().strip()
    ).first()

    if not user:
        # L18: Generic response — don't reveal account existence
        return {
            "status": "success",
            "message": (
                "If an account exists with this email, "
                "a verification link has been sent."
            ),
        }

    # Check already verified
    if user.is_verified:
        # L18: Generic response — don't reveal verification status
        return {
            "status": "success",
            "message": (
                "If an account exists with this email, "
                "a verification link has been sent."
            ),
        }

    # Rate limit check: count tokens created in last hour
    since_utc = datetime.now(timezone.utc) - timedelta(
        seconds=RESEND_WINDOW_SECONDS
    )
    # Handle naive datetimes from SQLite (created_at uses utcnow)
    recent_count = 0
    recent_tokens = db.query(VerificationToken).filter(
        VerificationToken.user_id == user.id,
    ).all()
    for t in recent_tokens:
        t_created = t.created_at
        if t_created.tzinfo is None:
            from datetime import timezone as tz
            t_created = t_created.replace(tzinfo=tz.utc)
        if t_created >= since_utc:
            recent_count += 1

    if recent_count >= MAX_RESENDS_PER_HOUR:
        raise RateLimitError(
            message=(
                "Too many resend requests. "
                "Please wait before trying again."
            ),
            details={
                "retry_after_seconds": RESEND_WINDOW_SECONDS
            },
        )

    # Create new token (invalidates old ones)
    raw_token = create_verification_token(db, user)
    db.commit()

    # Send verification email
    verification_url = (
        f"https://parwa.ai/verify?token={raw_token}"
    )
    sent = send_verification_email(
        user_email=user.email,
        user_name=user.full_name or "User",
        verification_url=verification_url,
    )

    if not sent:
        logger.error(
            "verification_email_failed",
            user_id=user.id,
            email=user.email,
        )

    return {
        "status": "success",
        "message": (
            "Verification email sent. Check your inbox."
        ),
        "retry_after": 60,
    }


def send_verification_on_register(
    db: Session, user: User
) -> None:
    """Send verification email after registration.

    Called by register_user in auth_service.
    Does not raise — email failures are logged.

    Args:
        db: Database session.
        user: Newly registered user.
    """
    raw_token = create_verification_token(db, user)
    db.flush()  # ensure token is saved

    verification_url = (
        f"https://parwa.ai/verify?token={raw_token}"
    )
    sent = send_verification_email(
        user_email=user.email,
        user_name=user.full_name or "User",
        verification_url=verification_url,
    )

    if not sent:
        logger.error(
            "registration_email_failed",
            user_id=user.id,
            email=user.email,
        )
