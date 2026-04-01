"""
PARWA Auth Router (F-010, F-011, F-013)

Endpoints for user registration, login, token refresh,
logout, profile, email check, and Google OAuth.

All public endpoints (no JWT required):
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/refresh
- POST /api/auth/google
- GET  /api/auth/check-email

Protected endpoints (JWT required):
- POST /api/auth/logout
- GET  /api/auth/me
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.schemas.auth import (
    AuthResponse,
    EmailCheckResponse,
    GoogleAuthRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.services.auth_service import (
    authenticate_user,
    check_email_availability,
    google_auth,
    logout_user,
    refresh_tokens,
    register_user,
)
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ── Public Endpoints ───────────────────────────────────────────────


@router.get("/check-email", response_model=EmailCheckResponse)
def check_email(
    email: str = Query(..., min_length=1, max_length=254),
    db: Session = Depends(get_db),
) -> EmailCheckResponse:
    """Check if an email is available for registration.

    L04: F-010 spec requires email availability check.
    Rate limited by middleware (20/IP/min).
    """
    available = check_email_availability(db=db, email=email)
    return EmailCheckResponse(
        email=email.strip().lower(),
        available=available,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
)
def register(
    body: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Register a new user and create their company.

    Creates both a Company (with 'starter' tier) and a User
    with 'owner' role. Returns JWT tokens for immediate use.

    F-010: User registration.
    BC-001: User scoped to company from creation.
    L01: confirm_password must match password.
    L02: Password must include special character.
    L12: Also sets HTTP-only cookies for tokens.
    """
    result = register_user(
        db=db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        company_name=body.company_name,
        industry=body.industry,
    )
    _set_token_cookies(response, result.tokens)
    return result


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Authenticate with email and password.

    F-010: Email/password login.
    BC-011: bcrypt verification, constant-time comparison.
    L11: Progressive lockout after 5 failures.
    L12: Also sets HTTP-only cookies for tokens.
    """
    result = authenticate_user(
        db=db,
        email=body.email,
        password=body.password,
    )
    _set_token_cookies(response, result.tokens)
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Refresh an expired access token.

    F-013: Token refresh with rotation.
    BC-011: Old refresh token is deleted, new one created.
    L07: Reuse detection invalidates ALL user tokens.
    L12: Also updates HTTP-only cookies.
    """
    result = refresh_tokens(
        db=db, raw_token=body.refresh_token
    )
    _set_token_cookies(response, result)
    return result


@router.post("/google", response_model=AuthResponse)
def google_login(
    body: GoogleAuthRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Authenticate or register via Google OAuth.

    F-011: Google OAuth sign-in.
    L08: Returns is_new_user flag.
    L12: Also sets HTTP-only cookies for tokens.
    """
    result = google_auth(db=db, id_token=body.id_token)
    _set_token_cookies(response, result.tokens)
    return result


# ── Protected Endpoints ────────────────────────────────────────────


@router.post("/logout", response_model=MessageResponse)
def logout(
    body: RefreshRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Revoke a refresh token (logout).

    Deletes the refresh token from the database so it
    cannot be used again. The access token will expire
    naturally within 15 minutes.
    L12: Clears HTTP-only cookies.
    """
    logout_user(db=db, raw_token=body.refresh_token)
    _clear_token_cookies(response)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user's profile.

    Returns user data including company info.
    BC-001: User is always scoped to a company.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        company_id=user.company_id,
        created_at=(
            user.created_at.isoformat()
            if user.created_at else None
        ),
    )


# ── Cookie Helpers (L12) ──────────────────────────────────────────


def _set_token_cookies(
    response: Response, tokens: TokenResponse
) -> None:
    """L12: Set HTTP-only, Secure, SameSite=Strict cookies.

    F-013 spec: parwa_access + parwa_refresh cookies.
    """
    response.set_cookie(
        key="parwa_access",
        value=tokens.access_token,
        max_age=tokens.expires_in,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key="parwa_refresh",
        value=tokens.refresh_token,
        max_age=7 * 24 * 60 * 60,  # 7 days
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


def _clear_token_cookies(response: Response) -> None:
    """L12: Clear auth cookies on logout."""
    response.delete_cookie(
        key="parwa_access", path="/"
    )
    response.delete_cookie(
        key="parwa_refresh", path="/"
    )
