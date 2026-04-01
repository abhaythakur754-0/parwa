"""
PARWA Auth Router (F-010, F-011, F-013)

Endpoints for user registration, login, token refresh,
logout, profile, and Google OAuth.

All public endpoints (no JWT required):
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/refresh
- POST /api/auth/google

Protected endpoints (JWT required):
- POST /api/auth/logout
- GET  /api/auth/me
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.schemas.auth import (
    AuthResponse,
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
    google_auth,
    logout_user,
    refresh_tokens,
    register_user,
)
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ── Public Endpoints ───────────────────────────────────────────────


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Register a new user and create their company.

    Creates both a Company (with 'starter' tier) and a User
    with 'owner' role. Returns JWT tokens for immediate use.

    F-010: User registration.
    BC-001: User scoped to company from creation.
    """
    return register_user(
        db=db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        company_name=body.company_name,
        industry=body.industry,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Authenticate with email and password.

    F-010: Email/password login.
    BC-011: bcrypt verification, constant-time comparison.
    Creates a new refresh token (session) on success.
    """
    return authenticate_user(
        db=db,
        email=body.email,
        password=body.password,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Refresh an expired access token.

    F-013: Token refresh with rotation.
    BC-011: Old refresh token is deleted, new one created.
    """
    return refresh_tokens(db=db, raw_token=body.refresh_token)


@router.post("/google", response_model=AuthResponse)
def google_login(
    body: GoogleAuthRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Authenticate or register via Google OAuth.

    F-011: Google OAuth sign-in.
    Verifies the Google ID token server-side, then creates
    or links the user account. New users get a company auto-created.
    """
    return google_auth(db=db, id_token=body.id_token)


# ── Protected Endpoints ────────────────────────────────────────────


@router.post("/logout", response_model=MessageResponse)
def logout(
    body: RefreshRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Revoke a refresh token (logout).

    Deletes the refresh token from the database so it
    cannot be used again. The access token will expire
    naturally within 15 minutes.
    """
    logout_user(db=db, raw_token=body.refresh_token)
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
