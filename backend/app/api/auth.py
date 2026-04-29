"""
PARWA Auth Router (F-010, F-011, F-012, F-013, F-014, C5)

Endpoints for user registration, login, token refresh,
logout, profile, email check, Google OAuth,
email verification, password reset, and phone OTP login.

All public endpoints (no JWT required):
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/refresh
- POST /api/auth/google
- GET  /api/auth/check-email
- GET  /api/auth/verify
- POST /api/auth/resend-verification
- POST /api/auth/forgot-password
- POST /api/auth/reset-password
- POST /api/auth/phone/send
- POST /api/auth/phone/verify

Protected endpoints (JWT required):
- POST /api/auth/logout
- GET  /api/auth/me
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.schemas.auth import (
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
from app.schemas.email import (
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
)
from app.schemas.phone_otp import (
    SendOTPRequest,
    SendOTPResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.services.auth_service import (
    authenticate_user,
    check_email_availability,
    google_auth,
    logout_user,
    refresh_tokens,
    register_user,
)
from app.services.password_reset_service import (
    initiate_password_reset,
    reset_password,
)
from app.services.verification_service import (
    resend_verification_email,
    verify_email,
)
from app.services.phone_otp_service import (
    send_otp,
    verify_otp,
)
from database.base import get_db
from database.models.core import Company, User

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

    Creates both a Company (with 'mini_parwa' tier) and a User
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
    BC-011: bcrypt verification.
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
    L07: Reuse detection invalidates ALL user tokens.
    L12: Also updates HTTP-only cookies.
    """
    result = refresh_tokens(db=db, raw_token=body.refresh_token)
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


# ── C5: Phone OTP Login ──────────────────────────────────────────


@router.post(
    "/phone/send",
    response_model=SendOTPResponse,
    status_code=200,
)
def phone_send_otp(
    body: SendOTPRequest,
    db: Session = Depends(get_db),
) -> SendOTPResponse:
    """Send a 6-digit OTP to a phone number.

    C5: Phone OTP Login via Twilio Verify.
    Validates E.164 format, generates OTP, stores hash in DB.
    """
    # Verify company exists (BC-001)
    company = (
        db.query(Company)
        .filter(
            Company.id == body.company_id,
        )
        .first()
    )
    if not company:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    result = send_otp(
        db=db,
        phone_number=body.phone,
        company_id=body.company_id,
    )
    return SendOTPResponse(**result)


@router.post(
    "/phone/verify",
    response_model=VerifyOTPResponse,
)
def phone_verify_otp(
    body: VerifyOTPRequest,
    db: Session = Depends(get_db),
) -> VerifyOTPResponse:
    """Verify a phone OTP code.

    C5: Constant-time comparison, max 5 attempts,
    5-minute expiry, anti-enumeration error messages.
    L23: Validate company exists for consistency with send.
    """
    # L23: Verify company exists (BC-001)
    company = (
        db.query(Company)
        .filter(
            Company.id == body.company_id,
        )
        .first()
    )
    if not company:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    result = verify_otp(
        db=db,
        phone_number=body.phone,
        code=body.code,
        company_id=body.company_id,
    )
    return VerifyOTPResponse(**result)


# ── F-012: Email Verification ──────────────────────────────────────


@router.get("/verify")
def verify_email_endpoint(
    token: str = Query(
        ...,
        min_length=32,
        max_length=64,
        description="Verification token (URL-safe)",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Verify an email address with a token.

    F-012: Validates token (exists, not expired, not used).
    Sets users.email_verified = True on success.
    L27: Token length validated (32-64 chars).
    """
    return verify_email(db=db, token=token)


@router.post("/resend-verification")
def resend_verification(
    body: ResendVerificationRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Resend a verification email.

    F-012: Rate limited to 3 per email per hour.
    Invalidates previous unused tokens.
    """
    return resend_verification_email(db=db, email=body.email)


# ── F-014: Password Reset ──────────────────────────────────────────


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Initiate password reset flow.

    F-014: Generic response (no account enumeration).
    Rate limited to 3 per email per hour.
    """
    return initiate_password_reset(db=db, email=body.email)


@router.post("/reset-password")
def reset_password_endpoint(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Reset password using a valid token.

    F-014: Single-use, 15-min expiry.
    BC-011: ALL sessions invalidated on reset.
    """
    return reset_password(
        db=db,
        token=body.token,
        new_password=body.new_password,
    )


# ── Protected Endpoints ────────────────────────────────────────────


@router.post("/logout", response_model=MessageResponse)
def logout(
    body: RefreshRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Revoke a refresh token (logout).

    Deletes the refresh token from the database.
    L12: Clears HTTP-only cookies.
    """
    logout_user(db=db, raw_token=body.refresh_token)
    _clear_token_cookies(response)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Get the current authenticated user's profile.

    BC-001: User is always scoped to a company.
    D8-3: Derives onboarding_completed from OnboardingSession
    so the frontend auth guard can redirect completed users.
    """
    # D8-3: Check onboarding session to derive completion status
    onboarding_completed = False
    try:
        from database.models.onboarding import OnboardingSession

        session = (
            db.query(OnboardingSession)
            .filter(
                OnboardingSession.user_id == user.id,
                OnboardingSession.company_id == user.company_id,
            )
            .first()
        )
        if (
            session
            and session.status == "completed"
            and session.first_victory_completed
        ):
            onboarding_completed = True
    except Exception:
        pass  # Non-critical — default to False

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
        onboarding_completed=onboarding_completed,
        created_at=(user.created_at.isoformat() if user.created_at else None),
    )


# ── Cookie Helpers (L12) ──────────────────────────────────────────


def _set_token_cookies(response: Response, tokens: TokenResponse) -> None:
    """L12: Set HTTP-only, Secure, SameSite=Strict cookies."""
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
    response.delete_cookie(key="parwa_access", path="/")
    response.delete_cookie(key="parwa_refresh", path="/")
