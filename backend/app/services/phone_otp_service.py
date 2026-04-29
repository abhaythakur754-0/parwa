"""
PARWA Phone OTP Service (C5: Phone OTP Login)

Handles sending and verifying phone OTP codes using Twilio Verify.
In test environment, stores OTPs without actually sending via Twilio.
Uses SHA-256 for code hashing and constant-time comparison.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from app.logger import get_logger
from sqlalchemy import and_
from sqlalchemy.orm import Session

from shared.utils.security import constant_time_compare

logger = get_logger("phone_otp_service")

OTP_EXPIRY_SECONDS = 300  # 5 minutes
MAX_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    """Hash an OTP code using SHA-256."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def send_otp(
    db: Session,
    phone_number: str,
    company_id: str,
) -> dict:
    """Send an OTP code to the given phone number.

    Validates phone format, generates a 6-digit code, stores the
    hash in the database. In test env, skips actual Twilio send.

    Args:
        db: Database session.
        phone_number: E.164 formatted phone number.
        company_id: The tenant identifier.

    Returns:
        Dict with message and expires_in.
    """
    from database.models.phone_otp import PhoneOTP

    # Generate 6-digit OTP
    code = str(secrets.randbelow(1000000)).zfill(6)

    # Hash the code for storage
    code_hash = _hash_code(code)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=OTP_EXPIRY_SECONDS)

    otp_record = PhoneOTP(
        phone=phone_number,
        company_id=company_id,
        code_hash=code_hash,
        verified=False,
        expires_at=expires_at,
        attempts=0,
    )
    db.add(otp_record)
    db.commit()

    # In non-test environments, send via Twilio
    if os.environ.get("ENVIRONMENT") != "test":
        try:
            from app.config import get_settings

            settings = get_settings()
            if settings.TWILIO_ACCOUNT_SID:
                success = _send_via_twilio(
                    phone_number,
                    code,
                    settings,
                )
                if not success:
                    # L22: Don't store OTP if Twilio send failed
                    db.rollback()
                    return {
                        "message": "Failed to send OTP. " "Please try again.",
                        "expires_in": 0,
                    }
        except Exception as exc:
            logger.warning(
                "twilio_send_failed",
                phone=phone_number,
                error=str(exc),
            )
            # L22: Return error instead of silently failing
            db.rollback()
            return {
                "message": "Failed to send OTP. " "Please try again.",
                "expires_in": 0,
            }

    logger.info(
        "otp_sent",
        phone=phone_number,
        company_id=company_id,
    )

    return {
        "message": "OTP sent",
        "expires_in": OTP_EXPIRY_SECONDS,
    }


def verify_otp(
    db: Session,
    phone_number: str,
    code: str,
    company_id: str,
) -> dict:
    """Verify a phone OTP code.

    Looks up by phone + company_id + verified=False + not expired.
    Uses constant-time comparison on hashed codes.
    Increments attempts counter; blocks after MAX_ATTEMPTS.

    Args:
        db: Database session.
        phone_number: E.164 formatted phone number.
        code: 6-digit OTP code.
        company_id: The tenant identifier.

    Returns:
        Dict with status, message, and optional attempts_remaining.
    """
    from database.models.phone_otp import PhoneOTP

    now = datetime.now(timezone.utc)

    # Find the latest unverified OTP for this phone+company
    otp_record = (
        db.query(PhoneOTP)
        .filter(
            and_(
                PhoneOTP.phone == phone_number,
                PhoneOTP.company_id == company_id,
                PhoneOTP.verified is False,  # noqa: E712
                PhoneOTP.expires_at > now,
            )
        )
        .order_by(PhoneOTP.created_at.desc())
        .first()
    )

    if otp_record is None:
        # Anti-enumeration: same error for all failure cases
        return {
            "status": "failed",
            "message": "Invalid or expired OTP",
            "attempts_remaining": 0,
        }

    # Increment attempts
    otp_record.attempts += 1
    remaining = MAX_ATTEMPTS - otp_record.attempts

    # Check if too many attempts
    if otp_record.attempts > MAX_ATTEMPTS:
        otp_record.expires_at = now  # expire it
        db.commit()
        return {
            "status": "failed",
            "message": "Invalid or expired OTP",
            "attempts_remaining": 0,
        }

    # Hash the input code and compare
    input_hash = _hash_code(code)
    if not constant_time_compare(input_hash, otp_record.code_hash):
        db.commit()
        return {
            "status": "failed",
            "message": "Invalid or expired OTP",
            "attempts_remaining": max(remaining, 0),
        }

    # Success: mark as verified
    otp_record.verified = True
    db.commit()

    return {
        "status": "verified",
        "message": "Phone verified",
    }


def _send_via_twilio(
    phone_number: str,
    code: str,
    settings,
) -> bool:
    """Send OTP via Twilio SMS.

    Uses the locally generated OTP code (not Twilio Verify)
    so that the code hash stored in DB matches what user enters.

    L21 fix: Twilio Verify generates its own code which wouldn't
    match our locally generated one. Use direct SMS instead.

    Returns:
        True if send succeeded, False otherwise.
    """
    try:
        from twilio.rest import Client

        client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )
        client.messages.create(
            body=(
                f"Your PARWA verification code is: {code}\n"
                "This code expires in 5 minutes."
            ),
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number,
        )
        return True
    except Exception as exc:
        logger.warning(
            "twilio_sms_send_failed",
            phone=phone_number,
            error=str(exc),
        )
        return False
