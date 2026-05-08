"""
PARWA JWT Authentication Service (BC-011)

Token creation, verification, and refresh rotation.
- Access tokens: short-lived (15 min), JWT with HS256
- Refresh tokens: long-lived (7 days), opaque tokens
  stored SHA-256 hashed in DB
- BC-011: JWT_SECRET_KEY from env, never hardcoded
- BC-011: Max 5 sessions per user
- M-10: jti claim for token blacklisting support
- L-02: JWT key rotation via JWT_PREVIOUS_KEYS support
"""

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings
from app.exceptions import AuthenticationError


# JWT algorithm — HS256 is industry standard for symmetric keys
JWT_ALGORITHM = "HS256"

# L-02: JWT key rotation support.
# When rotating keys, set JWT_PREVIOUS_KEYS to a JSON array of old keys.
# Tokens signed with old keys will still be verified until they expire,
# but new tokens will always be signed with JWT_SECRET_KEY.
_JWT_PREVIOUS_KEYS: list[str] = []
_raw_previous = os.environ.get("JWT_PREVIOUS_KEYS", "")
if _raw_previous:
    try:
        _parsed = json.loads(_raw_previous)
        if isinstance(_parsed, list):
            _JWT_PREVIOUS_KEYS = [
                str(k) for k in _parsed
            ]
    except (json.JSONDecodeError, TypeError):
        pass

# H3 fix: pepper for refresh-token hashing — prevents rainbow-table
# attacks even if the DB is leaked.
# MUST be set via the REFRESH_TOKEN_PEPPER env-var.
# In production, this will raise an error if not set.
_REFRESH_TOKEN_PEPPER = os.environ.get("REFRESH_TOKEN_PEPPER", "")
if not _REFRESH_TOKEN_PEPPER:
    if os.environ.get("ENVIRONMENT") == "production":
        raise RuntimeError(
            "REFRESH_TOKEN_PEPPER environment variable is required in "
            "production. Generate a strong random value with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )


def create_access_token(
    user_id: str,
    company_id: str,
    email: str,
    role: str,
    plan: str = "starter",
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
        # M-10: Unique token identifier for blacklisting support.
        # Enables individual token revocation via a jti-based blacklist.
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
    )


def verify_access_token(token: str) -> dict:
    """Verify and decode a JWT access token.

    BC-011: Rejects expired tokens, wrong type, invalid signatures.
    L-02: Also tries JWT_PREVIOUS_KEYS for rotated key support.

    Args:
        token: The JWT string from Authorization header.

    Returns:
        Decoded token payload dict.

    Raises:
        AuthenticationError: If token is invalid or expired.
    """
    settings = get_settings()
    # Build list of candidate keys: current + previous
    candidate_keys = [settings.JWT_SECRET_KEY] + _JWT_PREVIOUS_KEYS
    last_error = None
    for key in candidate_keys:
        try:
            payload = jwt.decode(
                token,
                key,
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
        except JWTError as exc:
            last_error = exc
            continue
    raise AuthenticationError(
        message="Invalid or expired token",
    )


def get_token_jti(token: str) -> str | None:
    """Extract jti from a token without full verification.

    M-10: Utility for blacklist checks. Parses the token payload
    without verifying signature (for use after verify_access_token).

    Args:
        token: The JWT string.

    Returns:
        The jti string, or None if not found.
    """
    try:
        payload = jwt.get_unverified_claims(token)
        return payload.get("jti")
    except Exception:
        return None


def get_jwt_previous_keys() -> list[str]:
    """Return the list of previous JWT signing keys.

    L-02: Used by ops tooling to inspect key rotation state.
    """
    return list(_JWT_PREVIOUS_KEYS)


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
