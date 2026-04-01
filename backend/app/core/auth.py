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
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from backend.app.config import get_settings
from backend.app.exceptions import AuthenticationError


# JWT algorithm — HS256 is industry standard for symmetric keys
JWT_ALGORITHM = "HS256"


def create_access_token(
    user_id: str,
    company_id: str,
    email: str,
    role: str,
) -> str:
    """Create a short-lived JWT access token.

    BC-011: Token contains user_id, company_id, email, role.
    BC-011: Expiry from JWT_ACCESS_TOKEN_EXPIRE_MINUTES.

    Args:
        user_id: The user's UUID.
        company_id: The user's company UUID.
        email: The user's email address.
        role: The user's role (owner, admin, agent, viewer).

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
        "type": "access",
        "exp": expire,
        "iat": now,
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
    except JWTError as exc:
        raise AuthenticationError(
            message="Invalid or expired token",
            details={"reason": str(exc)},
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
    Uses SHA-256 (consistent with API key hashing).

    Args:
        token: Raw refresh token string.

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def get_access_token_expiry_seconds() -> int:
    """Get access token expiry in seconds.

    Returns:
        Expiry time in seconds from config.
    """
    settings = get_settings()
    return settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
