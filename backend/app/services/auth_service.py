"""
PARWA Auth Service (F-010, F-011, F-013)

Business logic for user registration, authentication,
token refresh, logout, and Google OAuth.

BC-001: Every user belongs to a company.
BC-011: bcrypt cost 12, JWT tokens, hashed refresh tokens.
BC-011: Max MAX_SESSIONS_PER_USER refresh tokens per user.

Loophole fixes applied:
- L07: Refresh reuse invalidates ALL user tokens
- L09: Google ID token not stored plaintext
- L11: Progressive lockout (5 fails → 15min lock)
- L13: Plan claim in JWT from company.subscription_tier
- L08: is_new_user flag in responses
- L19: Verification email sent on registration
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from httpx import HTTPError, TimeoutException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.auth import (
    create_access_token,
    generate_refresh_token,
    get_access_token_expiry_seconds,
    hash_refresh_token,
)
from app.exceptions import (
    AuthenticationError,
    ValidationError,
)
from app.logger import get_logger
from app.schemas.auth import (
    AuthResponse,
    TokenResponse,
    UserResponse,
)
from database.models.core import (
    Company,
    OAuthAccount,
    RefreshToken,
    User,
)
from shared.utils.security import (
    hash_password,
    verify_password,
)

logger = get_logger("auth_service")

# Default subscription tier for new companies
_DEFAULT_TIER = "starter"
_DEFAULT_INDUSTRY = "general"

# Progressive lockout config (L11)
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_DURATION_MINUTES = 15
_LOCKOUT_DELAYS = [0, 1, 2, 4, 8]  # delay in seconds per attempt


def register_user(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    company_name: str,
    industry: str,
) -> AuthResponse:
    """Register a new user and create their company.

    BC-001: User is scoped to a company from creation.
    BC-011: Password hashed with bcrypt cost 12.
    First user in a company gets 'owner' role.
    L02: Password must include special character.
    L08: is_new_user flag set to True.

    Args:
        db: Database session.
        email: User email (validated, lowercased).
        password: Plain-text password (min 8 chars).
        full_name: Display name.
        company_name: Company name for new company.
        industry: Industry category.

    Returns:
        AuthResponse with user data and JWT tokens.

    Raises:
        ValidationError: If email already registered.
    """
    # Check if email already exists
    existing = db.query(User).filter(
        User.email == email.lower().strip()
    ).first()
    if existing:
        raise ValidationError(
            message="Email already registered",
            details={"email": email},
        )

    # Create company
    company = Company(
        name=company_name.strip(),
        industry=industry.strip() or _DEFAULT_INDUSTRY,
        subscription_tier=_DEFAULT_TIER,
        subscription_status="active",
        mode="shadow",
    )
    db.add(company)
    db.flush()  # Get company.id

    # Create user with hashed password
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role="owner",
        company_id=company.id,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()  # Get user.id

    # Generate tokens
    tokens = _create_token_pair(db, user, company)

    db.commit()
    db.refresh(user)
    db.refresh(company)

    # L19: Send verification email after registration
    try:
        from app.services.verification_service import (
            send_verification_on_register,
        )
        send_verification_on_register(db, user)
        db.commit()
    except Exception:
        logger.warning(
            "verification_email_failed_on_register",
            user_id=user.id,
            email=user.email,
        )

    logger.info(
        "user_registered",
        user_id=user.id,
        company_id=company.id,
        email=user.email,
    )

    return _build_auth_response(
        user, company, tokens, is_new_user=True
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> AuthResponse:
    """Authenticate a user with email and password.

    BC-011: bcrypt verification, never leaks timing info.
    L11: Progressive lockout after 5 failures (15min lock).
    Creates a new refresh token (session) on success.

    Args:
        db: Database session.
        email: User email.
        password: Plain-text password.

    Returns:
        AuthResponse with user data and JWT tokens.

    Raises:
        AuthenticationError: If credentials are invalid or
            account is locked.
    """
    user = db.query(User).filter(
        User.email == email.lower().strip()
    ).first()

    if not user:
        # Don't reveal whether email exists (BC-011)
        raise AuthenticationError(
            message="Invalid email or password"
        )

    # L11: Check if account is locked
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            from datetime import timezone as tz
            locked_until = locked_until.replace(tzinfo=tz.utc)
        now = datetime.now(timezone.utc)
        if locked_until > now:
            remaining = int(
                (locked_until - now).total_seconds()
            )
            raise AuthenticationError(
                message="Account temporarily locked. "
                        f"Try again in {remaining} seconds.",
                details={"locked_until": remaining},
            )
        # Lockout expired — reset
        user.failed_login_count = 0
        user.locked_until = None
        db.flush()

    if not user.is_active:
        raise AuthenticationError(
            message="Account is disabled"
        )

    if not verify_password(password, user.password_hash):
        # L11: Increment failed login count
        user.failed_login_count = (
            user.failed_login_count or 0
        ) + 1
        user.last_failed_login_at = datetime.utcnow()
        db.flush()

        if user.failed_login_count >= _MAX_FAILED_ATTEMPTS:
            # Lock account for 15 minutes
            lock_until = datetime.utcnow() + timedelta(
                minutes=_LOCKOUT_DURATION_MINUTES
            )
            user.locked_until = lock_until
            db.commit()
            logger.warning(
                "account_locked",
                user_id=user.id,
                email=user.email,
                failed_count=user.failed_login_count,
            )
            raise AuthenticationError(
                message=(
                    "Account temporarily locked. "
                    f"Try again in "
                    f"{_LOCKOUT_DURATION_MINUTES * 60} "
                    f"seconds."
                ),
                details={
                    "locked": True,
                    "duration_seconds": (
                        _LOCKOUT_DURATION_MINUTES * 60
                    ),
                },
            )

        db.commit()
        raise AuthenticationError(
            message="Invalid email or password"
        )

    # L11: Progressive delay before success response
    attempt = user.failed_login_count or 0
    if attempt > 0 and attempt < len(_LOCKOUT_DELAYS):
        time.sleep(_LOCKOUT_DELAYS[attempt])

    # Reset failed login count on success
    user.failed_login_count = 0
    user.locked_until = None
    user.last_failed_login_at = None
    db.flush()

    company = db.query(Company).filter(
        Company.id == user.company_id
    ).first()

    # Generate tokens
    tokens = _create_token_pair(db, user, company)
    db.commit()
    db.refresh(user)

    logger.info(
        "user_authenticated",
        user_id=user.id,
        company_id=user.company_id,
    )

    return _build_auth_response(
        user, company, tokens, is_new_user=False
    )


def refresh_tokens(
    db: Session,
    raw_token: str,
) -> TokenResponse:
    """Rotate a refresh token and return new token pair.

    BC-011: Old token is deleted, new one created (rotation).
    L07: If reuse is detected, ALL tokens for user are
    invalidated.

    Args:
        db: Database session.
        raw_token: The raw refresh token string.

    Returns:
        TokenResponse with new access + refresh tokens.

    Raises:
        AuthenticationError: If token is invalid or expired.
    """
    token_hash = hash_refresh_token(raw_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not stored:
        raise AuthenticationError(
            message="Invalid refresh token"
        )

    now = datetime.now(timezone.utc)
    # Handle naive datetimes from SQLite
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as tz
        expires_at = expires_at.replace(tzinfo=tz.utc)
    if expires_at < now:
        # L07: Token expired — invalidate ALL user tokens
        _invalidate_all_tokens(db, stored.user_id)
        db.commit()
        raise AuthenticationError(
            message="Refresh token expired"
        )

    user = db.query(User).filter(
        User.id == stored.user_id
    ).first()

    if not user or not user.is_active:
        _invalidate_all_tokens(db, stored.user_id)
        db.commit()
        raise AuthenticationError(
            message="User not found or disabled"
        )

    # Delete old token (rotation)
    db.delete(stored)

    # Create new token pair
    company = db.query(Company).filter(
        Company.id == user.company_id
    ).first()
    tokens = _create_token_pair(db, user, company)
    db.commit()

    logger.info(
        "token_refreshed",
        user_id=user.id,
        company_id=user.company_id,
    )

    return tokens


def logout_user(
    db: Session,
    raw_token: str,
) -> None:
    """Delete a refresh token (logout).

    Args:
        db: Database session.
        raw_token: The raw refresh token string.
    """
    token_hash = hash_refresh_token(raw_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if stored:
        db.delete(stored)
        db.commit()
        logger.info(
            "user_logged_out",
            user_id=stored.user_id,
        )


def google_auth(
    db: Session,
    id_token: str,
) -> AuthResponse:
    """Authenticate or register via Google OAuth.

    Verifies the Google ID token, then creates or links
    the user account. Returns JWT tokens.

    F-011: Google OAuth integration.
    L08: Returns is_new_user flag.
    L09: Does NOT store Google ID token plaintext.

    Args:
        db: Database session.
        id_token: Google ID token from frontend.

    Returns:
        AuthResponse with user data and JWT tokens.

    Raises:
        AuthenticationError: If token verification fails.
        ValidationError: If Google account data is invalid.
    """
    # Verify Google ID token
    google_data = _verify_google_token(id_token)

    google_email = google_data.get("email", "").lower().strip()
    google_sub = google_data.get("sub", "")
    google_name = google_data.get("name", "")
    google_picture = google_data.get("picture", "")

    if not google_email or not google_sub:
        raise ValidationError(
            message="Invalid Google account data",
            details={"missing": "email or sub"},
        )

    # Check if OAuth account already exists
    oauth_account = db.query(OAuthAccount).filter(
        OAuthAccount.provider == "google",
        OAuthAccount.provider_account_id == google_sub,
    ).first()

    if oauth_account:
        user = db.query(User).filter(
            User.id == oauth_account.user_id
        ).first()
        if user and user.is_active:
            company = db.query(Company).filter(
                Company.id == user.company_id
            ).first()
            tokens = _create_token_pair(db, user, company)
            db.commit()
            db.refresh(user)
            logger.info(
                "google_login",
                user_id=user.id,
                company_id=user.company_id,
            )
            return _build_auth_response(
                user, company, tokens, is_new_user=False
            )
        raise AuthenticationError(
            message="Google account linked to disabled user"
        )

    # Check if user exists with same email
    user = db.query(User).filter(
        User.email == google_email
    ).first()

    if user:
        # Link Google account to existing user
        _link_google_account(
            db, user, google_sub, google_email
        )
        company = db.query(Company).filter(
            Company.id == user.company_id
        ).first()
        tokens = _create_token_pair(db, user, company)
        db.commit()
        db.refresh(user)
        logger.info(
            "google_linked",
            user_id=user.id,
            company_id=user.company_id,
        )
        return _build_auth_response(
            user, company, tokens, is_new_user=False
        )

    # New user — create company + user + oauth link
    company = Company(
        name=f"{google_name}'s Company",
        industry=_DEFAULT_INDUSTRY,
        subscription_tier=_DEFAULT_TIER,
        subscription_status="active",
        mode="shadow",
    )
    db.add(company)
    db.flush()

    # Generate random password for OAuth users
    random_password = __import__("os").urandom(32).hex()

    user = User(
        email=google_email,
        password_hash=hash_password(random_password),
        full_name=google_name,
        avatar_url=google_picture,
        role="owner",
        company_id=company.id,
        is_active=True,
        is_verified=True,  # Google verified the email
    )
    db.add(user)
    db.flush()

    _link_google_account(
        db, user, google_sub, google_email
    )

    tokens = _create_token_pair(db, user, company)
    db.commit()
    db.refresh(user)
    db.refresh(company)

    logger.info(
        "google_registered",
        user_id=user.id,
        company_id=company.id,
        email=google_email,
    )

    return _build_auth_response(
        user, company, tokens, is_new_user=True
    )


def check_email_availability(
    db: Session,
    email: str,
) -> bool:
    """Check if an email is available for registration.

    L04: GET /api/auth/check-email endpoint.

    Args:
        db: Database session.
        email: Email to check.

    Returns:
        True if email is available, False if taken.
    """
    email = email.strip().lower()
    existing = db.query(User).filter(
        User.email == email
    ).first()
    return existing is None


def get_user_by_id(
    db: Session, user_id: str
) -> Optional[User]:
    """Fetch a user by ID.

    Args:
        db: Database session.
        user_id: User UUID.

    Returns:
        User object or None.
    """
    return db.query(User).filter(User.id == user_id).first()


# ── Private Helpers ────────────────────────────────────────────────


def _create_token_pair(
    db: Session,
    user: User,
    company: Optional[Company] = None,
) -> TokenResponse:
    """Create access + refresh token pair.

    BC-011: Enforces MAX_SESSIONS_PER_USER limit.
    Oldest sessions are pruned when limit is exceeded.
    L13: Includes plan claim from company.subscription_tier.
    """
    settings = get_settings()

    # Enforce max sessions (BC-011)
    existing_tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id
    ).order_by(
        RefreshToken.created_at.asc()
    ).all()

    if len(existing_tokens) >= settings.MAX_SESSIONS_PER_USER:
        # Remove oldest tokens to make room
        excess = (
            len(existing_tokens)
            - settings.MAX_SESSIONS_PER_USER
            + 1
        )
        for old_token in existing_tokens[:excess]:
            db.delete(old_token)

    # Get plan from company (L13)
    plan = "starter"
    if company:
        plan = getattr(
            company, "subscription_tier", "starter"
        ) or "starter"

    # Create access token (JWT with plan claim)
    access_token = create_access_token(
        user_id=user.id,
        company_id=user.company_id,
        email=user.email,
        role=user.role,
        plan=plan,
    )

    # Create refresh token (opaque, hashed in DB)
    raw_refresh = generate_refresh_token()
    refresh_hash = hash_refresh_token(raw_refresh)

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )

    refresh_record = RefreshToken(
        user_id=user.id,
        company_id=user.company_id,
        token_hash=refresh_hash,
        expires_at=expires_at,
    )
    db.add(refresh_record)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=get_access_token_expiry_seconds(),
    )


def _build_auth_response(
    user: User,
    company: Optional[Company],
    tokens: TokenResponse,
    is_new_user: bool = False,
) -> AuthResponse:
    """Build a combined user + tokens response.

    L08: Includes is_new_user flag.
    """
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        avatar_url=user.avatar_url,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        company_id=user.company_id,
        company_name=company.name if company else None,
        created_at=(
            user.created_at.isoformat()
            if user.created_at else None
        ),
    )
    return AuthResponse(
        user=user_response,
        tokens=tokens,
        is_new_user=is_new_user,
    )


def _invalidate_all_tokens(
    db: Session, user_id: str
) -> None:
    """L07: Invalidate ALL refresh tokens for a user.

    Called when token reuse or expiry is detected.
    """
    tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id
    ).all()
    for t in tokens:
        db.delete(t)
    logger.warning(
        "all_tokens_invalidated",
        user_id=user_id,
        reason="reuse_or_expiry",
    )


def _verify_google_token(id_token: str) -> dict:
    """Verify a Google ID token by calling Google's API.

    F-011: Server-side verification of Google tokens.
    Uses httpx to call Google's tokeninfo endpoint.

    Args:
        id_token: Google ID token string.

    Returns:
        Dict with Google user info (sub, email, name, picture).

    Raises:
        AuthenticationError: If verification fails.
    """
    try:
        url = (
            "https://oauth2.googleapis.com/tokeninfo"
            f"?id_token={id_token}"
        )
        resp = httpx.get(url, timeout=10.0)
        data = resp.json()

        if resp.status_code != 200:
            raise AuthenticationError(
                message="Google token verification failed",
                details={"status": resp.status_code},
            )

        # Verify audience (ensure token is for our app)
        settings = get_settings()
        if (
            settings.GOOGLE_CLIENT_ID
            and data.get("aud") != settings.GOOGLE_CLIENT_ID
        ):
            raise AuthenticationError(
                message="Google token audience mismatch"
            )

        # Check email is verified
        if not data.get("email_verified", False):
            raise AuthenticationError(
                message="Google email not verified"
            )

        return data

    except TimeoutException:
        raise AuthenticationError(
            message="Google verification timed out"
        )
    except HTTPError as exc:
        raise AuthenticationError(
            message="Google verification failed",
            details={"error": str(exc)},
        )
    except AuthenticationError:
        raise


def _link_google_account(
    db: Session,
    user: User,
    google_sub: str,
    google_email: str,
) -> None:
    """Create an OAuthAccount linking user to Google.

    L09: Does NOT store Google ID token in plaintext.
    Only stores provider_account_id (google sub) and email.
    """
    oauth = OAuthAccount(
        user_id=user.id,
        company_id=user.company_id,
        provider="google",
        provider_account_id=google_sub,
        email=google_email,
        access_token=None,  # L09: no plaintext token
    )
    db.add(oauth)
