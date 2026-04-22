"""
PARWA GDPR API Endpoints (E3)

Provides data privacy endpoints for GDPR compliance:
- POST /api/gdpr/erase  — Cascade-delete all data for authenticated user
- GET  /api/gdpr/export — Export all user data as JSON

Both endpoints require authentication via get_current_user.

ERASURE covers all related records across tables:
  - User profile (anonymized, not hard-deleted, to preserve FK refs)
  - Refresh tokens
  - Backup codes
  - OAuth accounts
  - MFA secrets
  - Verification tokens
  - Password reset tokens
  - Notification preferences

EXPORT returns a comprehensive JSON payload with all user data
structured by category for easy data portability.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from database.base import get_db
from database.models.core import (
    User,
    Company,
    RefreshToken,
    BackupCode,
    OAuthAccount,
    APIKey,
    UserNotificationPreference,
    VerificationToken,
    PasswordResetToken,
    MFASecret,
)

logger = logging.getLogger("parwa.gdpr")

router = APIRouter(
    prefix="/api/gdpr",
    tags=["GDPR"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)

# ── Helpers ──────────────────────────────────────────────────────


def _serialize_model(obj, allowed_fields: list[str]) -> dict:
    """Serialize selected fields from a SQLAlchemy model instance."""
    if obj is None:
        return None
    result = {}
    for field in allowed_fields:
        val = getattr(obj, field, None)
        if isinstance(val, datetime):
            val = val.isoformat() if val else None
        result[field] = val
    return result


def _collect_user_data(db: Session, user: User) -> dict:
    """Gather all data related to a user for GDPR export."""
    # Company info
    company = db.query(Company).filter(
        Company.id == user.company_id,
    ).first()
    company_data = _serialize_model(
        company,
        ["id", "name", "industry", "subscription_tier",
         "subscription_status", "created_at", "updated_at"],
    ) if company else None

    # API keys (metadata only — never export the secret hash)
    api_keys = db.query(APIKey).filter(
        APIKey.created_by == user.id,
    ).all()
    api_keys_data = [
        _serialize_model(k, [
            "id", "name", "key_prefix", "scope", "scopes",
            "is_active", "revoked", "last_used_at",
            "expires_at", "created_at",
        ])
        for k in api_keys
    ]

    # Notification preferences
    notif_prefs = db.query(UserNotificationPreference).filter(
        UserNotificationPreference.user_id == user.id,
    ).all()
    notif_prefs_data = [
        _serialize_model(p, [
            "channel", "event_type", "enabled", "updated_at",
        ])
        for p in notif_prefs
    ]

    # OAuth accounts (never export tokens)
    oauth_accounts = db.query(OAuthAccount).filter(
        OAuthAccount.user_id == user.id,
    ).all()
    oauth_accounts_data = [
        _serialize_model(o, [
            "provider", "provider_account_id", "email",
            "created_at",
        ])
        for o in oauth_accounts
    ]

    # Refresh tokens (active sessions — metadata only)
    refresh_tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
    ).all()
    refresh_tokens_data = [
        _serialize_model(t, [
            "id", "device_info", "ip_address",
            "expires_at", "created_at",
        ])
        for t in refresh_tokens
    ]

    return {
        "user": _serialize_model(
            user,
            ["id", "email", "full_name", "phone", "avatar_url",
             "role", "is_active", "is_verified", "mfa_enabled",
             "company_id", "created_at", "updated_at"],
        ),
        "company": company_data,
        "api_keys": api_keys_data,
        "notification_preferences": notif_prefs_data,
        "oauth_accounts": oauth_accounts_data,
        "active_sessions": refresh_tokens_data,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def _cascade_delete_user_data(db: Session, user: User) -> None:
    """Delete all user-related records from the database.

    This performs a cascading deletion of all PII-bearing records
    linked to the user. The User row itself is anonymized (not
    hard-deleted) to preserve referential integrity for any
    audit trails that reference user IDs.
    """
    user_id = user.id
    company_id = user.company_id

    # 1. Delete refresh tokens (ends all active sessions)
    deleted = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d refresh_tokens for user=%s",
            deleted, user_id,
        )

    # 2. Delete backup codes
    deleted = db.query(BackupCode).filter(
        BackupCode.user_id == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d backup_codes for user=%s",
            deleted, user_id,
        )

    # 3. Delete OAuth accounts (revokes third-party access)
    deleted = db.query(OAuthAccount).filter(
        OAuthAccount.user_id == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d oauth_accounts for user=%s",
            deleted, user_id,
        )

    # 4. Delete MFA secret (disables MFA enrollment)
    deleted = db.query(MFASecret).filter(
        MFASecret.user_id == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d mfa_secrets for user=%s",
            deleted, user_id,
        )

    # 5. Delete verification tokens (invalidate pending emails)
    deleted = db.query(VerificationToken).filter(
        VerificationToken.user_id == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d verification_tokens for user=%s",
            deleted, user_id,
        )

    # 6. Delete password reset tokens
    deleted = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d password_reset_tokens for user=%s",
            deleted, user_id,
        )

    # 7. Delete notification preferences
    deleted = db.query(UserNotificationPreference).filter(
        UserNotificationPreference.user_id == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d notif_prefs for user=%s",
            deleted, user_id,
        )

    # 8. Revoke API keys created by this user
    deleted = db.query(APIKey).filter(
        APIKey.created_by == user_id,
    ).delete(synchronize_session=False)
    if deleted:
        logger.info(
            "gdpr_erase: deleted %d api_keys for user=%s",
            deleted, user_id,
        )

    # 9. Anonymize user record (preserve FK integrity, scrub PII)
    user.email = f"gdpr_erased_{user_id[:8]}@erased.local"
    user.full_name = None
    user.phone = None
    user.avatar_url = None
    user.password_hash = "GDPR_ERASED"
    user.mfa_secret = None
    user.mfa_enabled = False
    user.is_active = False
    user.is_verified = False
    user.failed_login_count = 0
    user.locked_until = None
    user.last_failed_login_at = None
    user.updated_at = datetime.utcnow()

    db.commit()
    logger.info(
        "gdpr_erase: user=%s anonymized, all related records deleted",
        user_id,
    )


# ── Endpoints ───────────────────────────────────────────────────


@router.post("/erase")
def erase_user_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete all data for the authenticated user (GDPR right to erasure).

    Performs cascade deletion of all user-related records:
      - Ends all active sessions (refresh tokens)
      - Revokes all API keys
      - Removes MFA enrollment
      - Deletes OAuth account links
      - Removes verification and password-reset tokens
      - Anonymizes the User record (preserves FK integrity)

    Returns 200 with the user_id and a confirmation message.
    """
    logger.info(
        "gdpr_erase_requested user_id=%s company_id=%s",
        user.id,
        user.company_id,
    )

    try:
        _cascade_delete_user_data(db, user)
    except Exception as exc:
        db.rollback()
        logger.error(
            "gdpr_erase_failed user_id=%s error=%s",
            user.id, exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Data erasure failed. Please try again later.",
        ) from exc

    return JSONResponse(
        status_code=200,
        content={
            "status": "completed",
            "message": (
                "All your personal data has been permanently "
                "deleted in accordance with GDPR Article 17 "
                "(Right to Erasure). Your account has been "
                "deactivated and anonymized."
            ),
            "user_id": user.id,
        },
    )


@router.get("/export")
def export_user_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all user data as JSON (GDPR right to data portability).

    Returns a comprehensive JSON payload containing:
      - User profile (name, email, role, timestamps)
      - Company information
      - API keys (metadata only, no secrets)
      - Notification preferences
      - OAuth account links (no tokens)
      - Active sessions (metadata only)
    """
    logger.info(
        "gdpr_export_requested user_id=%s company_id=%s",
        user.id,
        user.company_id,
    )

    try:
        data = _collect_user_data(db, user)
    except Exception as exc:
        logger.error(
            "gdpr_export_failed user_id=%s error=%s",
            user.id, exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Data export failed. Please try again later.",
        ) from exc

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Data export generated (GDPR Article 20).",
            "user_id": user.id,
            **data,
        },
    )
