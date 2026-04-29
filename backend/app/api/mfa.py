"""
PARWA MFA & Session Router (F-015, F-016, F-017)

Endpoints for MFA setup/verification, backup codes,
and session management.

MFA endpoints (authenticated):
- POST /api/auth/mfa/setup/initiate
- POST /api/auth/mfa/setup/verify
- POST /api/auth/mfa/verify (during login)
- GET  /api/auth/mfa/backup-codes (remaining count)
- POST /api/auth/mfa/backup-codes/regenerate
- POST /api/auth/mfa/backup-codes/use (during login)

Session endpoints (authenticated):
- GET    /api/auth/sessions
- DELETE /api/auth/sessions/{session_id}/revoke
- DELETE /api/auth/sessions/revoke-others
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.auth import hash_refresh_token
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Verify MFA during login.

    F-015: Validates TOTP code with progressive lockout.
    """
    result = verify_mfa_login(db=db, user=user, code=body.code)
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
    remaining = get_remaining_backup_codes(db=db, user=user)
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
    result = use_backup_code(db=db, user=user, code=body.code)
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
        from app.exceptions import AuthenticationError

        raise AuthenticationError(
            message="No refresh token found. " "Please re-authenticate.",
        )

    current_hash = hash_refresh_token(refresh_token)

    result = revoke_other_sessions(
        db=db,
        user_id=user.id,
        current_token_hash=current_hash,
    )
    return RevokeOthersResponse(**result)
