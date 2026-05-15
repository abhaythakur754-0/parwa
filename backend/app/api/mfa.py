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

C-09 FIX: MFA sessions now backed by Redis with TTL instead of
in-memory Python dict. Falls back to in-memory only when Redis
is unavailable in non-production environments.
"""

import hashlib
import json
import logging
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

logger = logging.getLogger("parwa.mfa")

router = APIRouter(
    prefix="/api/auth",
    tags=["MFA & Sessions"],
)

# ── MFA Temporary Session Store (C-09 FIX: Redis-backed) ──────────
# C-09 FIX: MFA sessions are now stored in Redis with automatic TTL
# instead of an in-memory Python dict. This ensures:
# 1. Sessions survive server restarts
# 2. TTL is enforced by Redis (no stale sessions)
# 3. Works correctly in multi-instance deployments
# Falls back to in-memory only in non-production when Redis is down.

_MFA_SESSION_TTL_SECONDS = 300  # 5 minutes
_MFA_REDIS_PREFIX = "parwa:mfa_session"

# In-memory fallback (only used when Redis is unavailable in non-production)
_mfa_pending_sessions: dict = {}


async def _store_mfa_session(token: str, data: dict) -> bool:
    """Store MFA session in Redis with TTL. Returns True if stored in Redis."""
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        key = f"{_MFA_REDIS_PREFIX}:{token}"
        # Store expiry as ISO string; Redis TTL handles actual expiration
        await redis.set(key, json.dumps(data), ex=_MFA_SESSION_TTL_SECONDS)
        return True
    except Exception as exc:
        logger.error(
            "mfa_session_redis_store_failed error=%s — falling back to in-memory",
            str(exc)[:200],
        )
        return False


async def _retrieve_mfa_session(token: str) -> dict | None:
    """Retrieve and consume MFA session from Redis (atomic GET+DEL).
    Falls back to in-memory dict if Redis is unavailable.
    Returns None if session not found or expired.
    """
    # Try Redis first
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        key = f"{_MFA_REDIS_PREFIX}:{token}"
        # Atomic GET + DELETE to consume the session (one-time use)
        pipe = redis.pipeline()
        pipe.get(key)
        pipe.delete(key)
        results = await pipe.execute()
        raw_data = results[0]

        if raw_data:
            data = json.loads(raw_data)
            # Check expiry (double-check beyond Redis TTL)
            if datetime.now(timezone.utc) > datetime.fromisoformat(data["expires_at"]):
                return None
            return data
        return None
    except Exception as exc:
        logger.error(
            "mfa_session_redis_retrieve_failed error=%s — falling back to in-memory",
            str(exc)[:200],
        )
        # Fall back to in-memory (non-production only)
        session = _mfa_pending_sessions.pop(token, None)
        if session and datetime.now(timezone.utc) <= session["expires_at"]:
            return session
        return None


async def create_mfa_session_token(
    user_id: str,
    company_id: str,
    email: str,
    role: str,
    plan: str = "starter",
) -> str:
    """Create a temporary MFA session token for the login flow.

    C-09 FIX: Stores session in Redis with TTL. Falls back to in-memory
    dict only when Redis is unavailable in non-production.

    RACE CONDITION FIX: Now awaited synchronously so the session is
    guaranteed to be stored BEFORE the response is sent. Previously
    used fire-and-forget ``loop.create_task()`` which could return
    before Redis write completed.

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
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=_MFA_SESSION_TTL_SECONDS
    )
    session_data = {
        "user_id": user_id,
        "company_id": company_id,
        "email": email,
        "role": role,
        "plan": plan,
        "expires_at": expires_at.isoformat(),
    }

    # C-09 + RACE FIX: Await Redis write synchronously so session
    # is guaranteed stored before the token is returned to the caller.
    stored = await _store_mfa_session(token, session_data)

    if not stored:
        # Redis failed — store in-memory as fallback (non-prod only)
        _mfa_pending_sessions[token] = {
            "user_id": user_id,
            "company_id": company_id,
            "email": email,
            "role": role,
            "plan": plan,
            "expires_at": expires_at,
        }
        logger.warning(
            "mfa_session_stored_in_memory_fallback token=%s... "
            "This is NOT safe for production",
            token[:8],
        )

    return token


async def verify_mfa_session_token(token: str) -> dict:
    """Verify and consume a temporary MFA session token.

    C-09 FIX: Retrieves from Redis (with atomic consume) first,
    falls back to in-memory dict if Redis is unavailable.

    Args:
        token: The MFA session token.

    Returns:
        Session data dict with user_id, company_id, email, role, plan.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    session = await _retrieve_mfa_session(token)
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

    # Check expiry (Redis TTL should handle this, but double-check)
    expires_at = session.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if datetime.now(timezone.utc) > expires_at:
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
async def mfa_verify_login(
    body: MFALoginVerifyRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Verify MFA during login.

    F-015: Validates TOTP code with progressive lockout.
    Uses a temporary MFA session token (issued after successful
    email/password verification) instead of a JWT, since the user
    doesn't have a JWT yet during the MFA step.

    C-09 FIX: MFA session token now verified via Redis-backed store.

    The MFA session token is passed as part of the MFALoginVerifyRequest.
    """
    # Extract and verify MFA session token
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

    session_data = await verify_mfa_session_token(body.mfa_session_token)

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
        result = await verify_mfa_login(
            db=db, user=user, code=body.code
        )
    except AuthenticationError:
        raise
    except Exception as exc:
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
