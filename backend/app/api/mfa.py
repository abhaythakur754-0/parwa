"""
PARWA MFA & Session Router (F-015, F-016, F-017)

Endpoints for MFA setup/verification, backup codes,
and session management.

MFA endpoints (authenticated):
- POST /api/auth/mfa/setup/initiate
- POST /api/auth/mfa/setup/verify
- GET  /api/auth/mfa/backup-codes (remaining count)
- POST /api/auth/mfa/backup-codes/regenerate
- POST /api/auth/mfa/backup-codes/use (during login)

MFA endpoints (pre-auth — temporary session token):
- POST /api/mfa/verify (during login — uses MFA session token)

Session endpoints (authenticated):
- GET    /api/auth/sessions
- DELETE /api/auth/sessions/{session_id}/revoke
- DELETE /api/auth/sessions/revoke-others
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, optional_user
from app.core.auth import (
    create_access_token,
    hash_refresh_token,
)
from app.exceptions import AuthenticationError
from app.schemas.mfa import (
    BackupCodeRegenerateRequest,
    BackupCodeUseRequest,
    BackupCodesResponse,
    MFASetupInitiateRequest,
    MFASetupResponse,
    MFASetupVerifyRequest,
    MFAVerifyResponse,
    MFALoginVerifyRequest,
    RevokeOthersResponse,
    SessionListResponse,
    SessionRevokeResponse,
)
from app.services.mfa_service import (
    get_remaining_backup_codes,
    initiate_mfa_setup,
    regenerate_backup_codes,
    use_backup_code,
    verify_mfa_login,
    verify_mfa_setup,
)
from app.services.session_service import (
    list_sessions,
    revoke_other_sessions,
    revoke_session,
)
from database.base import get_db
from database.models.core import User

router = APIRouter(
    prefix="/api/auth",
    tags=["MFA & Sessions"],
)

# ── MFA Temporary Session Store ────────────────────────────────────
# Stores pending MFA sessions: {mfa_session_token -> {user_id, company_id, email, role, plan, expires_at}}
# In production, this should be backed by Redis with TTL.
_mfa_pending_sessions: dict = {}
_MFA_SESSION_TTL_SECONDS = 300  # 5 minutes


def create_mfa_session_token(
    user_id: str,
    company_id: str,
    email: str,
    role: str,
    plan: str = "starter",
) -> str:
    """Create a temporary MFA session token for the login flow.

    This token is issued after successful email/password verification
    but before MFA code verification. It allows the MFA verify endpoint
    to identify the user without a full JWT (which hasn't been issued yet).

    Args:
        user_id: The user's UUID.
        company_id: The user's company UUID.
        email: The user's email.
        role: The user's role.
        plan: Subscription tier.

    Returns:
        Temporary MFA session token string.
    """
    token = secrets.token_urlsafe(32)
    _mfa_pending_sessions[token] = {
        "user_id": user_id,
        "company_id": company_id,
        "email": email,
        "role": role,
        "plan": plan,
        "expires_at": datetime.now(timezone.utc) + timedelta(
            seconds=_MFA_SESSION_TTL_SECONDS
        ),
    }
    return token


def verify_mfa_session_token(token: str) -> dict:
    """Verify and consume a temporary MFA session token.

    Args:
        token: The MFA session token.

    Returns:
        Session data dict with user_id, company_id, email, role, plan.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    session = _mfa_pending_sessions.pop(token, None)
    if not session:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "MFA_SESSION_INVALID",
                    "message": "Invalid or expired MFA session. Please log in again.",
                    "details": None,
                }
            },
        )

    if datetime.now(timezone.utc) > session["expires_at"]:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "MFA_SESSION_EXPIRED",
                    "message": "MFA session expired. Please log in again.",
                    "details": None,
                }
            },
        )

    return session


# ── F-015: MFA Setup ──────────────────────────────────────────────


@router.post(
    "/mfa/setup/initiate",
    response_model=MFASetupResponse,
)
def mfa_setup_initiate(
    body: MFASetupInitiateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFASetupResponse:
    """Initiate MFA setup — returns QR code + backup codes.

    F-015: Generates TOTP secret, QR code, and 10 backup codes.
    """
    result = initiate_mfa_setup(db=db, user=user)
    return MFASetupResponse(**result)


@router.post(
    "/mfa/setup/verify",
    response_model=MFAVerifyResponse,
)
def mfa_setup_verify(
    body: MFASetupVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFAVerifyResponse:
    """Verify MFA setup with TOTP code.

    F-015: Validates code and activates MFA.
    """
    result = verify_mfa_setup(
        db=db,
        user=user,
        code=body.code,
        temp_secret=body.temp_secret,
    )
    return MFAVerifyResponse(**result)


@router.post("/mfa/verify")
def mfa_verify_login(
    body: MFALoginVerifyRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Verify MFA during login.

    F-015: Validates TOTP code with progressive lockout.
    Uses a temporary MFA session token (issued after successful
    email/password verification) instead of a JWT, since the user
    doesn't have a JWT yet during the MFA step.

    The MFA session token is passed in the Authorization header
    as: Bearer mfa_<token>
    """
    # Extract and verify MFA session token from Authorization header
    from fastapi import Header
    # We read the raw token from the request to avoid circular deps
    # The session token is sent as part of the MFALoginVerifyRequest
    if not body.mfa_session_token:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "MFA session token required",
                    "details": None,
                }
            },
        )

    session_data = verify_mfa_session_token(body.mfa_session_token)

    # Look up user from session data
    user = db.query(User).filter(
        User.id == session_data["user_id"]
    ).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": "User not found or inactive",
                    "details": None,
                }
            },
        )

    # M-09: Wrap service call to catch any raw Exception and
    # convert to proper AuthenticationError for consistent error handling.
    try:
        result = verify_mfa_login(
            db=db, user=user, code=body.code
        )
    except AuthenticationError:
        raise
    except Exception as exc:
        logger = __import__("logging").getLogger("parwa.mfa")
        logger.error(
            "mfa_verify_unexpected_error user_id=%s error=%s",
            session_data.get("user_id", ""),
            str(exc)[:200],
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "MFA verification failed. Please try again.",
                    "details": None,
                }
            },
        )

    # On successful MFA verification, issue real JWT tokens
    if result.get("verified"):
        from app.core.auth import generate_refresh_token
        from app.services.auth_service import create_session

        access_token = create_access_token(
            user_id=user.id,
            company_id=session_data["company_id"],
            email=session_data["email"],
            role=session_data["role"],
            plan=session_data["plan"],
        )
        refresh_token_raw = generate_refresh_token()

        # Create session in DB
        create_session(
            db=db,
            user_id=user.id,
            company_id=session_data["company_id"],
            token_hash=hash_refresh_token(refresh_token_raw),
            device_info="mfa-login",
        )

        result["access_token"] = access_token
        result["refresh_token"] = refresh_token_raw

    return result


# ── F-016: Backup Codes ───────────────────────────────────────────


@router.get("/mfa/backup-codes")
def get_backup_codes_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get remaining backup codes count.

    F-016: Returns count of unused backup codes.
    """
    remaining = get_remaining_backup_codes(
        db=db, user=user
    )
    return {
        "remaining": remaining,
        "warning": remaining < 3,
    }


@router.post(
    "/mfa/backup-codes/regenerate",
    response_model=BackupCodesResponse,
)
def regenerate_codes(
    body: BackupCodeRegenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BackupCodesResponse:
    """Regenerate all backup codes.

    F-016: Requires valid TOTP code. Invalidates old codes.
    """
    result = regenerate_backup_codes(
        db=db,
        user=user,
        mfa_code=body.mfa_code,
    )
    return BackupCodesResponse(**result)


@router.post("/mfa/backup-codes/use")
def use_backup_code_endpoint(
    body: BackupCodeUseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Use a backup code for authentication.

    F-016: Single-use, returns remaining count.
    """
    result = use_backup_code(
        db=db, user=user, code=body.code
    )
    return result


# ── F-017: Session Management ─────────────────────────────────────


@router.get(
    "/sessions",
    response_model=SessionListResponse,
)
def get_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    """List all active sessions.

    F-017: Shows device info, masked IP, last active.
    """
    # Get current token hash for marking current session
    current_hash = None
    refresh_token = request.cookies.get("parwa_refresh")
    if refresh_token:
        current_hash = hash_refresh_token(refresh_token)

    sessions = list_sessions(
        db=db,
        user_id=user.id,
        current_token_hash=current_hash,
    )
    return SessionListResponse(sessions=sessions)


@router.delete(
    "/sessions/{session_id}/revoke",
    response_model=SessionRevokeResponse,
)
def revoke_session_endpoint(
    session_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionRevokeResponse:
    """Revoke a specific session.

    F-017: Cannot revoke own current session.
    """
    current_hash = None
    refresh_token = request.cookies.get("parwa_refresh")
    if refresh_token:
        current_hash = hash_refresh_token(refresh_token)

    result = revoke_session(
        db=db,
        user_id=user.id,
        session_id=session_id,
        current_token_hash=current_hash,
    )
    return SessionRevokeResponse(**result)


@router.delete(
    "/sessions/revoke-others",
    response_model=RevokeOthersResponse,
)
def revoke_others_endpoint(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevokeOthersResponse:
    """Revoke all sessions except current.

    F-017: Keeps current session active.
    """
    refresh_token = request.cookies.get("parwa_refresh")
    if not refresh_token:
        raise AuthenticationError(
            message="No active session found",
        )

    current_hash = hash_refresh_token(refresh_token)

    result = revoke_other_sessions(
        db=db,
        user_id=user.id,
        current_token_hash=current_hash,
    )
    return RevokeOthersResponse(**result)
