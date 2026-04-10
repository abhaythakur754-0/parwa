"""
PARWA MFA Service (F-015, F-016)

Business logic for MFA setup, TOTP verification, and backup codes.
- TOTP secret generation (pyotp)
- QR code generation (qrcode)
- Backup code generation (10 codes, SHA-256 hashed)
- MFA verification during login (with progressive lockout)
- Backup code use and regeneration

BC-011: MFA enforced, bcrypt cost 12, tokens hashed.
"""

import base64
import hashlib
import io
import secrets
import time

import pyotp
import qrcode
from sqlalchemy.orm import Session

from app.exceptions import (
    AuthenticationError,
    ValidationError,
)
from app.logger import get_logger
from database.models.core import (
    BackupCode,
    MFASecret,
    User,
)

logger = get_logger("mfa_service")

# Backup code config (F-016)
BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 10
BACKUP_CODE_CHUNKS = 3

# Progressive lockout for MFA (BC-011)
_MFA_MAX_FAILURES = 5
_MFA_LOCKOUT_MINUTES = 15
_MFA_DELAYS = [0, 1, 2, 4, 8]  # delay in seconds


def _generate_backup_codes() -> list[str]:
    """Generate backup codes (10 codes, 3 chunks of chars).

    Returns list of plaintext codes like 'A7K3-M9X2-P4L1'.
    """
    codes = []
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(BACKUP_CODE_COUNT):
        chunks = []
        for _ in range(BACKUP_CODE_CHUNKS):
            chunk = "".join(
                secrets.choice(chars) for _ in range(3)
            )
            chunks.append(chunk)
        codes.append("-".join(chunks))
    return codes


def _hash_backup_code(code: str) -> str:
    """Hash a backup code for DB storage (SHA-256)."""
    return hashlib.sha256(
        code.strip().upper().encode("utf-8")
    ).hexdigest()


def _generate_qr_code_data_url(
    secret: str, email: str
) -> str:
    """Generate a QR code data URL for TOTP setup.

    Args:
        secret: TOTP secret (base32).
        email: User's email for issuer label.

    Returns:
        Data URL string (data:image/png;base64,...).
    """
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=email,
        issuer_name="PARWA"
    )
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def initiate_mfa_setup(
    db: Session, user: User
) -> dict:
    """Initiate MFA setup — generate TOTP secret + backup codes.

    F-015: Returns QR code, secret, and 10 backup codes.
    Secret is stored temporarily; MFA not active until verified.

    Args:
        db: Database session.
        user: Authenticated user.

    Returns:
        Dict with qr_code_data_url, secret_key, backup_codes.
    """
    if user.mfa_enabled:
        raise ValidationError(
            message="MFA is already enabled on this account",
        )

    # L30: Clean up any previous unverified setup
    db.query(MFASecret).filter(
        MFASecret.user_id == user.id,
        MFASecret.is_verified == False,  # noqa: E712
    ).delete()
    db.query(BackupCode).filter(
        BackupCode.user_id == user.id,
        BackupCode.is_used == False,  # noqa: E712
    ).delete()

    # Generate TOTP secret
    secret = pyotp.random_base32()

    # Generate backup codes
    plain_codes = _generate_backup_codes()

    # Generate QR code
    qr_data_url = _generate_qr_code_data_url(
        secret, user.email
    )

    # Store backup codes as hashes
    for code in plain_codes:
        bc = BackupCode(
            user_id=user.id,
            company_id=user.company_id,
            code_hash=_hash_backup_code(code),
            is_used=False,
        )
        db.add(bc)

    # Store temp secret in MFASecret table (not verified yet)
    # Delete any existing temp secret for this user
    db.query(MFASecret).filter(
        MFASecret.user_id == user.id,
        MFASecret.is_verified == False,  # noqa: E712
    ).delete()

    mfa_record = MFASecret(
        user_id=user.id,
        company_id=user.company_id,
        secret_key=secret,
        is_verified=False,
    )
    db.add(mfa_record)
    db.commit()

    logger.info(
        "mfa_setup_initiated",
        user_id=user.id,
    )

    return {
        "qr_code_data_url": qr_data_url,
        "secret_key": secret,
        "backup_codes": plain_codes,
        "message": (
            "Scan QR code with your authenticator app"
        ),
    }


def verify_mfa_setup(
    db: Session, user: User, code: str, temp_secret: str
) -> dict:
    """Verify MFA setup with TOTP code.

    F-015: Validates code, enables MFA, stores permanent secret.
    Accepts codes within ±1 time window (30s tolerance).

    Args:
        db: Database session.
        user: Authenticated user.
        code: 6-digit TOTP code.
        temp_secret: TOTP secret from setup initiation.

    Returns:
        Dict with status and mfa_enabled.

    Raises:
        AuthenticationError: If code is invalid.
    """
    totp = pyotp.TOTP(temp_secret)

    # Check current, previous, and next window (clock drift)
    valid = (
        totp.verify(code, valid_window=1)
    )

    if not valid:
        raise AuthenticationError(
            message="Invalid MFA code. Please try again."
        )

    # Update user's MFA status
    user.mfa_enabled = True

    # Mark MFASecret as verified
    mfa_record = db.query(MFASecret).filter(
        MFASecret.user_id == user.id,
        MFASecret.is_verified == False,  # noqa: E712
    ).first()

    if mfa_record:
        mfa_record.secret_key = temp_secret
        mfa_record.is_verified = True
    else:
        # Create verified record
        mfa_record = MFASecret(
            user_id=user.id,
            company_id=user.company_id,
            secret_key=temp_secret,
            is_verified=True,
        )
        db.add(mfa_record)

    db.commit()

    logger.info(
        "mfa_enabled",
        user_id=user.id,
    )

    return {
        "status": "enabled",
        "mfa_enabled": True,
        "message": "MFA enabled successfully",
    }


def verify_mfa_login(
    db: Session, user: User, code: str
) -> dict:
    """Verify MFA during login.

    BC-011: Progressive lockout (5 fails → 15min lock).
    Accepts TOTP codes within ±1 time window.

    Args:
        db: Database session.
        user: User with MFA enabled.
        code: 6-digit TOTP code.

    Returns:
        Dict with status="verified".

    Raises:
        AuthenticationError: If code invalid or locked.
    """
    # Check lockout
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            from datetime import timezone as tz
            locked_until = locked_until.replace(tzinfo=tz.utc)
        now = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        if locked_until > now:
            remaining = int(
                (locked_until - now).total_seconds()
            )
            raise AuthenticationError(
                message=(
                    "Account temporarily locked. "
                    f"Try again in {remaining} seconds."
                ),
                details={"locked_until": remaining},
            )
        # Lockout expired
        user.failed_login_count = 0
        user.locked_until = None

    # Get verified MFA secret
    mfa_record = db.query(MFASecret).filter(
        MFASecret.user_id == user.id,
        MFASecret.is_verified == True,  # noqa: E712
    ).first()

    if not mfa_record:
        raise AuthenticationError(
            message="MFA not configured"
        )

    totp = pyotp.TOTP(mfa_record.secret_key)
    valid = totp.verify(code, valid_window=1)

    if not valid:
        # Increment failure count
        count = (user.failed_login_count or 0) + 1
        user.failed_login_count = count
        user.last_failed_login_at = (
            __import__("datetime").datetime.utcnow()
        )

        if count >= _MFA_MAX_FAILURES:
            from datetime import timedelta
            user.locked_until = (
                __import__("datetime").datetime.utcnow()
                + timedelta(minutes=_MFA_LOCKOUT_MINUTES)
            )
            db.commit()
            raise AuthenticationError(
                message=(
                    "Too many failed MFA attempts. "
                    f"Account locked for "
                    f"{_MFA_LOCKOUT_MINUTES} minutes."
                ),
                details={"locked": True},
            )

        # Progressive delay
        attempt = min(count - 1, len(_MFA_DELAYS) - 1)
        if _MFA_DELAYS[attempt] > 0:
            time.sleep(_MFA_DELAYS[attempt])

        db.commit()
        raise AuthenticationError(
            message="Invalid MFA code. Please try again."
        )

    # Success — reset failure count
    user.failed_login_count = 0
    user.locked_until = None
    user.last_failed_login_at = None
    db.commit()

    return {
        "status": "verified",
        "message": "MFA verified successfully",
    }


def use_backup_code(
    db: Session, user: User, code: str
) -> dict:
    """Use a backup code for authentication.

    F-016: Single-use, SHA-256 hashed in DB.
    L29: Requires MFA to be enabled on the account.

    Args:
        db: Database session.
        user: User with MFA enabled.
        code: Plaintext backup code.

    Returns:
        Dict with status and remaining count.

    Raises:
        AuthenticationError: If code is invalid or MFA not enabled.
    """
    # L29: Check MFA is enabled
    if not user.mfa_enabled:
        raise AuthenticationError(
            message="MFA is not enabled on this account"
        )

    code_hash = _hash_backup_code(code)

    bc = db.query(BackupCode).filter(
        BackupCode.user_id == user.id,
        BackupCode.code_hash == code_hash,
        BackupCode.is_used == False,  # noqa: E712
    ).first()

    if not bc:
        raise AuthenticationError(
            message="Invalid backup code"
        )

    # Mark as used
    bc.is_used = True
    bc.used_at = __import__("datetime").datetime.utcnow()
    db.flush()

    # Count remaining
    remaining = db.query(BackupCode).filter(
        BackupCode.user_id == user.id,
        BackupCode.is_used == False,  # noqa: E712
    ).count()

    # Reset MFA failure count on successful backup use
    user.failed_login_count = 0
    user.locked_until = None

    db.commit()

    logger.warning(
        "backup_code_used",
        user_id=user.id,
        remaining=remaining,
    )

    return {
        "status": "verified",
        "remaining": remaining,
        "message": "Backup code accepted",
    }


def regenerate_backup_codes(
    db: Session, user: User, mfa_code: str
) -> dict:
    """Regenerate backup codes (requires valid TOTP code).

    F-016: Invalidates ALL existing codes, generates 10 new ones.

    Args:
        db: Database session.
        user: User with MFA enabled.
        mfa_code: Current valid TOTP code for authorization.

    Returns:
        Dict with new backup_codes.

    Raises:
        AuthenticationError: If MFA code is invalid.
        ValidationError: If MFA is not enabled.
    """
    if not user.mfa_enabled:
        raise ValidationError(
            message="MFA must be enabled to regenerate codes"
        )

    # Verify MFA code first
    mfa_record = db.query(MFASecret).filter(
        MFASecret.user_id == user.id,
        MFASecret.is_verified == True,  # noqa: E712
    ).first()

    if not mfa_record:
        raise AuthenticationError(
            message="MFA not configured"
        )

    totp = pyotp.TOTP(mfa_record.secret_key)
    if not totp.verify(mfa_code, valid_window=1):
        raise AuthenticationError(
            message="Invalid MFA code"
        )

    # Invalidate ALL existing backup codes
    db.query(BackupCode).filter(
        BackupCode.user_id == user.id
    ).delete()

    # Generate new codes
    new_codes = _generate_backup_codes()
    for code in new_codes:
        bc = BackupCode(
            user_id=user.id,
            company_id=user.company_id,
            code_hash=_hash_backup_code(code),
            is_used=False,
        )
        db.add(bc)

    db.commit()

    logger.info(
        "backup_codes_regenerated",
        user_id=user.id,
    )

    return {
        "backup_codes": new_codes,
        "message": (
            "New backup codes generated. "
            "Store them securely."
        ),
    }


def get_remaining_backup_codes(
    db: Session, user: User
) -> int:
    """Get count of remaining unused backup codes."""
    return db.query(BackupCode).filter(
        BackupCode.user_id == user.id,
        BackupCode.is_used == False,  # noqa: E712
    ).count()
