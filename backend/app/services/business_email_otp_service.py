"""
PARWA Business Email OTP Service (Week 6 Day 10-11)

Handles sending and verifying OTP codes for business email verification.
This is used in the onboarding flow to verify user's business email.

Flow:
1. User enters business email
2. System generates 6-digit OTP
3. Email sent via Brevo with the OTP code
4. User enters OTP code
5. System verifies against hash

Features:
- Rate limiting (max 3 requests per hour per email)
- OTP expires in 10 minutes
- Max 5 verification attempts
- SHA-256 hashing for security
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.logger import get_logger
from app.exceptions import ValidationError, RateLimitError
from app.services.email_service import send_email
from app.core.email_renderer import render_email_template
from shared.utils.security import constant_time_compare
from database.models.business_email_otp import BusinessEmailOTP

logger = get_logger("business_email_otp_service")

# OTP Configuration
OTP_EXPIRY_MINUTES = 10  # OTP valid for 10 minutes
MAX_VERIFICATION_ATTEMPTS = 5  # Max 5 attempts to verify
MAX_REQUESTS_PER_HOUR = 3  # Max 3 OTP requests per hour per email
OTP_LENGTH = 6  # 6-digit OTP


def _hash_otp(otp: str) -> str:
    """Hash an OTP code using SHA-256."""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    """Generate a random 6-digit OTP."""
    # Use cryptographically secure random number
    return ''.join([str(secrets.randbelow(10)) for _ in range(OTP_LENGTH)])


def _is_valid_business_email(email: str) -> bool:
    """Check if email looks like a business email (not free providers)."""
    if not email or '@' not in email:
        return False

    # Common free email providers to reject
    free_providers = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'aol.com', 'icloud.com', 'mail.com', 'protonmail.com',
        'zoho.com', 'yandex.com', 'qq.com', '163.com',
    ]

    domain = email.split('@')[-1].lower()
    return domain not in free_providers


def send_business_email_otp(
    db: Session,
    email: str,
    user_id: str,
    company_id: str,
    user_name: Optional[str] = None,
) -> dict:
    """Send an OTP code to the business email.

    Args:
        db: Database session.
        email: Business email to verify.
        user_id: User requesting verification.
        company_id: Company context.
        user_name: User's name for email personalization.

    Returns:
        Dict with message and expires_in.

    Raises:
        ValidationError: If email is invalid.
        RateLimitError: If rate limited.
    """
    # Normalize email
    email = email.lower().strip()

    # Validate email format
    if not email or '@' not in email:
        raise ValidationError(
            message="Invalid email address.",
            details={"email": email},
        )

    # Check if it's a business email
    if not _is_valid_business_email(email):
        raise ValidationError(
            message="Please use your business email address. Free email providers (Gmail, Yahoo, etc.) are not accepted.",
            details={
                "email": email},
        )

    # Rate limit check: count OTPs created in last hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_otps = db.query(BusinessEmailOTP).filter(
        BusinessEmailOTP.email == email,
        BusinessEmailOTP.company_id == company_id,
        BusinessEmailOTP.created_at >= one_hour_ago,
    ).count()

    if recent_otps >= MAX_REQUESTS_PER_HOUR:
        raise RateLimitError(
            message="Too many OTP requests. Please wait before requesting another code.",
            details={
                "retry_after_seconds": 3600},
        )

    # Invalidate any previous unverified OTPs for this email
    db.query(BusinessEmailOTP).filter(
        BusinessEmailOTP.email == email,
        BusinessEmailOTP.company_id == company_id,
        BusinessEmailOTP.verified is False,  # noqa: E712
    ).update({"expires_at": datetime.now(timezone.utc)})  # Expire them

    # Generate new OTP
    otp_code = _generate_otp()
    otp_hash = _hash_otp(otp_code)

    # Calculate expiry
    expires_at = datetime.now(timezone.utc) + \
        timedelta(minutes=OTP_EXPIRY_MINUTES)

    # Store OTP
    otp_record = BusinessEmailOTP(
        email=email,
        company_id=company_id,
        user_id=user_id,
        code_hash=otp_hash,
        verified=False,
        expires_at=expires_at,
        attempts=0,
    )
    db.add(otp_record)
    db.commit()

    # Send OTP via email
    html_content = render_email_template(
        "business_email_otp.html",
        {
            "user_name": user_name or "User",
            "otp_code": otp_code,
            "expires_minutes": OTP_EXPIRY_MINUTES,
        },
    )

    sent = send_email(
        to=email,
        subject="Your PARWA Verification Code",
        html_content=html_content,
    )

    if not sent:
        logger.warning(
            "business_email_otp_send_failed",
            email=email,
            user_id=user_id,
        )
        # Still return success - don't reveal email sending status
        # User will see "check your email" message

    logger.info(
        "business_email_otp_sent",
        email=email,
        user_id=user_id,
        company_id=company_id,
    )

    return {
        "message": f"Verification code sent to {email}",
        "expires_in": OTP_EXPIRY_MINUTES * 60,  # seconds
        "email": email,
    }


def verify_business_email_otp(
    db: Session,
    email: str,
    otp_code: str,
    company_id: str,
) -> dict:
    """Verify the OTP code for a business email.

    Args:
        db: Database session.
        email: Business email being verified.
        otp_code: 6-digit OTP code entered by user.
        company_id: Company context.

    Returns:
        Dict with status and message.

    Raises:
        ValidationError: If OTP is invalid/expired.
    """
    # Normalize inputs
    email = email.lower().strip()
    otp_code = otp_code.strip()

    # Basic validation
    if not email or '@' not in email:
        raise ValidationError(
            message="Invalid email address.",
            details={"email": email},
        )

    if not otp_code or len(otp_code) != OTP_LENGTH or not otp_code.isdigit():
        raise ValidationError(
            message=f"Please enter a valid {OTP_LENGTH}-digit code.",
            details={"otp_code": "Invalid format"},
        )

    now = datetime.now(timezone.utc)

    # Find the latest unverified OTP for this email+company
    otp_record = (
        db.query(BusinessEmailOTP)
        .filter(
            and_(
                BusinessEmailOTP.email == email,
                BusinessEmailOTP.company_id == company_id,
                BusinessEmailOTP.verified is False,  # noqa: E712
                BusinessEmailOTP.expires_at > now,
            )
        )
        .order_by(BusinessEmailOTP.created_at.desc())
        .first()
    )

    if otp_record is None:
        # Anti-enumeration: same error for all failure cases
        raise ValidationError(
            message="Invalid or expired verification code. Please request a new code.",
            details={
                "error": "not_found_or_expired"},
        )

    # Check if too many attempts
    if otp_record.attempts >= MAX_VERIFICATION_ATTEMPTS:
        # Expire the OTP
        otp_record.expires_at = now
        db.commit()
        raise ValidationError(
            message="Too many failed attempts. Please request a new code.",
            details={"attempts": otp_record.attempts},
        )

    # Increment attempts
    otp_record.attempts += 1
    db.commit()

    # Hash the input OTP and compare
    input_hash = _hash_otp(otp_code)
    if not constant_time_compare(input_hash, otp_record.code_hash):
        remaining = MAX_VERIFICATION_ATTEMPTS - otp_record.attempts
        raise ValidationError(
            message=f"Invalid verification code. {remaining} attempt(s) remaining.",
            details={
                "attempts_remaining": max(
                    remaining,
                    0),
            },
        )

    # Success: mark as verified
    otp_record.verified = True
    otp_record.verified_at = now
    db.commit()

    logger.info(
        "business_email_otp_verified",
        email=email,
        company_id=company_id,
        user_id=otp_record.user_id,
    )

    return {
        "status": "verified",
        "message": "Business email verified successfully!",
        "email": email,
    }


def check_business_email_verified(
    db: Session,
    email: str,
    company_id: str,
) -> bool:
    """Check if a business email has been verified.

    Args:
        db: Database session.
        email: Business email to check.
        company_id: Company context.

    Returns:
        True if verified, False otherwise.
    """
    email = email.lower().strip()

    verified_otp = db.query(BusinessEmailOTP).filter(
        BusinessEmailOTP.email == email,
        BusinessEmailOTP.company_id == company_id,
        BusinessEmailOTP.verified is True,  # noqa: E712
    ).first()

    return verified_otp is not None
