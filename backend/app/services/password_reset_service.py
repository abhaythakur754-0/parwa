"""
PARWA Password Reset Service (F-014)

Business logic for forgot/reset password flow.
- Token generation (256-bit, URL-safe)
- SHA-256 hashed token in DB (F-014 spec)
- Token validation (single-use, 15-min expiry)
- Generic response to prevent account enumeration
- ALL sessions invalidated on reset (BC-011)
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.exceptions import (
    AuthenticationError,
    NotFoundError,
)
from backend.app.logger import get_logger
from backend.app.services.email_service import (
    send_password_reset_email,
)
from database.models.core import (
    PasswordResetToken,
    RefreshToken,
    User,
)
from shared.utils.security import hash_password

logger = get_logger("password_reset_service")

# Token expiry: 15 minutes (F-014 spec)
TOKEN_EXPIRE_MINUTES = 15

# Rate limit: 3 per email per hour (F-014 spec)
MAX_RESETS_PER_HOUR = 3
RESET_WINDOW_SECONDS = 3600


def _generate_token() -> str:
    """Generate a 256-bit URL-safe token."""
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    """Hash a reset token for DB storage (SHA-256)."""
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def initiate_password_reset(
    db: Session, email: str
) -> dict:
    """Start the password reset flow.

    F-014: Generic response prevents account enumeration.
    Always returns success message, even if email not found.

    Args:
        db: Database session.
        email: User's email address.

    Returns:
        Dict with status message (always generic).
    """
    user = db.query(User).filter(
        User.email == email.lower().strip()
    ).first()

    if not user:
        # F-014: Generic response, no info leakage
        return {
            "status": "success",
            "message": (
                "If an account exists with this email, "
                "a reset link has been sent."
            ),
        }

    # Rate limit check
    since_utc = datetime.now(timezone.utc) - timedelta(
        seconds=RESET_WINDOW_SECONDS
    )
    recent_count = 0
    recent_tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
    ).all()
    for t in recent_tokens:
        t_created = t.created_at
        if t_created.tzinfo is None:
            from datetime import timezone as tz
            t_created = t_created.replace(tzinfo=tz.utc)
        if t_created >= since_utc:
            recent_count += 1

    if recent_count >= MAX_RESETS_PER_HOUR:
        return {
            "status": "error",
            "message": (
                "Too many reset requests. "
                "Please wait before trying again."
            ),
            "retry_after_seconds": RESET_WINDOW_SECONDS,
        }

    # Create reset token
    raw_token = _generate_token()
    token_hash = _hash_token(raw_token)

    reset_token = PasswordResetToken(
        user_id=user.id,
        company_id=user.company_id,
        token_hash=token_hash,
        is_used=False,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
        ),
    )
    db.add(reset_token)

    # Invalidate previous unused tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False,  # noqa: E712
    ).update({"is_used": True})

    db.commit()

    # Send reset email
    reset_url = (
        f"https://parwa.ai/reset-password?"
        f"token={raw_token}"
    )
    sent = send_password_reset_email(
        user_email=user.email,
        user_name=user.full_name or "User",
        reset_url=reset_url,
    )

    if not sent:
        logger.error(
            "reset_email_failed",
            user_id=user.id,
            email=user.email,
        )

    return {
        "status": "success",
        "message": (
            "If an account exists with this email, "
            "a reset link has been sent."
        ),
    }


def reset_password(
    db: Session,
    token: str,
    new_password: str,
) -> dict:
    """Reset a user's password using a valid token.

    F-014: Single-use token, 15-min expiry.
    BC-011: ALL sessions invalidated on reset.
    BC-011: New password hashed with bcrypt.

    Args:
        db: Database session.
        token: Raw reset token from URL.
        new_password: New plaintext password.

    Returns:
        Dict with status message.

    Raises:
        ValidationError: If token invalid/expired/used.
    """
    token_hash = _hash_token(token)
    stored = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()

    if not stored:
        raise NotFoundError(
            message="Invalid reset link.",
        )

    if stored.is_used:
        raise AuthenticationError(
            message="Token already used.",
        )

    # Check expiry
    now = datetime.now(timezone.utc)
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as tz
        expires_at = expires_at.replace(tzinfo=tz.utc)
    if expires_at < now:
        raise AuthenticationError(
            message="Token expired.",
        )

    # Find user
    user = db.query(User).filter(
        User.id == stored.user_id
    ).first()

    if not user or not user.is_active:
        raise NotFoundError(
            message="User not found or disabled.",
        )

    # Mark token as used
    stored.is_used = True

    # Update password (bcrypt cost 12)
    user.password_hash = hash_password(new_password)

    # BC-011: Invalidate ALL sessions for user
    _invalidate_all_sessions(db, user.id)

    # Reset failed login count
    user.failed_login_count = 0
    user.locked_until = None
    user.last_failed_login_at = None

    db.commit()

    logger.info(
        "password_reset",
        user_id=user.id,
        token_id=stored.id,
    )

    return {
        "status": "success",
        "message": "Password reset successfully.",
    }


def _invalidate_all_sessions(
    db: Session, user_id: str
) -> None:
    """BC-011: Delete all refresh tokens for a user.

    Called on password reset to force re-login.
    """
    count = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id
    ).count()
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id
    ).delete()
    logger.info(
        "sessions_invalidated",
        user_id=user_id,
        count=count,
    )
