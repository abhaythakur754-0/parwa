"""
PARWA JWT Authentication Service (BC-011)

Token creation, verification, and refresh rotation.
- Access tokens: short-lived (15 min), JWT with HS256
- Refresh tokens: long-lived (7 days), opaque tokens
  stored SHA-256 hashed in DB
- BC-011: JWT_SECRET_KEY from env, never hardcoded
- BC-011: Max 5 sessions per user
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings
from app.exceptions import AuthenticationError


# JWT algorithm — HS256 is industry standard for symmetric keys
JWT_ALGORITHM = "HS256"

# H3 fix: pepper for refresh-token hashing — prevents rainbow-table
# attacks even if the DB is leaked.  MUST be set via the REFRESH_TOKEN_PEPPER
# env-var.  No default is provided — startup will fail if missing.
_REFRESH_TOKEN_PEPPER = os.getenv("REFRESH_TOKEN_PEPPER")

if not _REFRESH_TOKEN_PEPPER:
    raise RuntimeError(
        "REFRESH_TOKEN_PEPPER environment variable is required. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )


def create_access_token(
    user_id: str,
    company_id: str,
    email: str,
    role: str,
    plan: str = "mini_parwa",
) -> str:
    """Create a short-lived JWT access token.

    BC-011: Token contains user_id, company_id, email, role, plan.
    BC-011: Expiry from JWT_ACCESS_TOKEN_EXPIRE_MINUTES.
    L13: Includes subscription plan from company.
    L16: Includes nbf (not-before) claim.

    Args:
        user_id: The user's UUID.
        company_id: The user's company UUID.
        email: The user's email address.
        role: The user's role (owner, admin, agent, viewer).
        plan: Subscription tier (starter, growth, enterprise).

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "email": email,
        "role": role,
        "plan": plan,
        "type": "access",
        "exp": expire,
        "iat": now,
        "nbf": now,
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
    )


def verify_access_token(token: str) -> dict:
    """Verify and decode a JWT access token.

    BC-011: Rejects expired tokens, wrong type, invalid signatures.

    Args:
        token: The JWT string from Authorization header.

    Returns:
        Decoded token payload dict.

    Raises:
        AuthenticationError: If token is invalid or expired.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise AuthenticationError(
                message="Invalid token type",
                details={"expected": "access"},
            )
        return payload
    except AuthenticationError:
        raise
    except JWTError:
        raise AuthenticationError(
            message="Invalid or expired token",
        )


def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token.

    Returns:
        URL-safe random token (43 characters).
    """
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for safe DB storage.

    BC-011: Tokens are never stored in plaintext.
    Uses SHA-256 with a pepper (H3 fix) to prevent rainbow-table
    attacks even if the token hash database is leaked.

    Args:
        token: Raw refresh token string.

    Returns:
        SHA-256 hex digest (peppered).
    """
    assert _REFRESH_TOKEN_PEPPER is not None  # guaranteed by startup check
    return hashlib.sha256(
        f"{_REFRESH_TOKEN_PEPPER}:{token}".encode("utf-8")
    ).hexdigest()


def get_access_token_expiry_seconds() -> int:
    """Get access token expiry in seconds.

    Returns:
        Expiry time in seconds from config.
    """
    settings = get_settings()
    return settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
