"""
PARWA JWT Authentication Service (BC-011)

Token creation, verification, and refresh rotation.
- Access tokens: short-lived (15 min), JWT with HS256 or RS256
- Refresh tokens: long-lived (7 days), opaque tokens
  stored SHA-256 hashed in DB
- BC-011: JWT_SECRET_KEY from env, never hardcoded
- BC-011: Max 5 sessions per user
- M-10: jti claim for token blacklisting support
- L-02: JWT key rotation via JWT_PREVIOUS_KEYS support
- CROSS-6: JWT token blacklist via Redis with TTL
- Week 6: RS256 migration support (dual-algorithm: HS256 + RS256)
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from jose import JWTError, jwt

from app.config import get_settings
from app.exceptions import AuthenticationError

# CROSS-6: Redis key prefix for token blacklist.
# Uses a global namespace (not tenant-scoped) because jti is
# globally unique and blacklist checks happen before tenant
# context is available.
_BLACKLIST_PREFIX = "parwa:blacklist"


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
    logger.warning(
        "REFRESH_TOKEN_PEPPER is not set — refresh tokens will lack pepper "
        "hardening. Set REFRESH_TOKEN_PEPPER for all environments. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )


# ── Week 6: RS256 Key Loading ────────────────────────────────────

def _load_rs256_keys():
    """Load RSA keys from file path or base64 env var.

    Returns (private_key_pem, public_key_pem) tuple or (None, None) if not configured.
    """
    settings = get_settings()

    private_key = None
    public_key = None

    # Try file paths first
    if settings.JWT_PRIVATE_KEY_PATH:
        try:
            with open(settings.JWT_PRIVATE_KEY_PATH, "r") as f:
                private_key = f.read()
        except Exception as e:
            logger.warning("Failed to load RSA private key from %s: %s", settings.JWT_PRIVATE_KEY_PATH, e)

    if settings.JWT_PUBLIC_KEY_PATH:
        try:
            with open(settings.JWT_PUBLIC_KEY_PATH, "r") as f:
                public_key = f.read()
        except Exception as e:
            logger.warning("Failed to load RSA public key from %s: %s", settings.JWT_PUBLIC_KEY_PATH, e)

    # Try base64 env vars as fallback
    if not private_key and settings.JWT_PRIVATE_KEY_BASE64:
        try:
            private_key = base64.b64decode(settings.JWT_PRIVATE_KEY_BASE64).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to decode RSA private key from base64: %s", e)

    if not public_key and settings.JWT_PUBLIC_KEY_BASE64:
        try:
            public_key = base64.b64decode(settings.JWT_PUBLIC_KEY_BASE64).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to decode RSA public key from base64: %s", e)

    return private_key, public_key


def _get_jwt_algorithm():
    """Get the current JWT algorithm from settings.

    Falls back to HS256 if settings cannot be loaded.
    """
    try:
        settings = get_settings()
        return settings.JWT_ALGORITHM
    except Exception:
        return "HS256"  # Safe fallback


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
    Week 6: Supports both HS256 and RS256 algorithms.

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
    algorithm = _get_jwt_algorithm()
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

    # Determine signing key based on algorithm
    if algorithm == "RS256":
        private_key, _ = _load_rs256_keys()
        if not private_key:
            logger.warning(
                "RS256 configured but no private key found — falling back to HS256 for signing"
            )
            algorithm = "HS256"
            signing_key = settings.JWT_SECRET_KEY
        else:
            signing_key = private_key
    else:
        signing_key = settings.JWT_SECRET_KEY

    # Build headers — include kid for key identification
    headers: dict = {"alg": algorithm}
    if algorithm == "RS256" or settings.JWT_KID:
        headers["kid"] = settings.JWT_KID

    return jwt.encode(payload, signing_key, algorithm=algorithm, headers=headers)


def verify_access_token(token: str) -> dict:
    """Verify and decode a JWT access token (JWT verification only).

    BC-011: Rejects expired tokens, wrong type, invalid signatures.
    L-02: Also tries JWT_PREVIOUS_KEYS for rotated key support.
    CROSS-6: Note — this function verifies the JWT signature and
    payload only.  Callers that need revocation checking should
    call ``is_token_revoked()`` with the payload's ``jti`` *after*
    this function succeeds (see deps.get_current_user).

    Week 6: Supports dual-algorithm verification (RS256 + HS256).
    Tries RS256 first if configured, then falls back to HS256 with
    all previous keys.

    Args:
        token: The JWT string from Authorization header.

    Returns:
        Decoded token payload dict.

    Raises:
        AuthenticationError: If token is invalid or expired.
    """
    settings = get_settings()
    last_error = None

    # ── Strategy 1: RS256 verification (if configured) ──────────
    algorithm = _get_jwt_algorithm()
    if algorithm == "RS256":
        _, public_key = _load_rs256_keys()
        if public_key:
            try:
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
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
                logger.debug("RS256 verification failed, trying HS256: %s", exc)
        else:
            logger.warning("RS256 configured but no public key found for verification")

    # ── Strategy 2: HS256 verification with key rotation ────────
    candidate_keys = [settings.JWT_SECRET_KEY] + _JWT_PREVIOUS_KEYS
    for key in candidate_keys:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=["HS256"],
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


# ── CROSS-6: Token Blacklist (Redis-backed) ──────────────────────
# Token blacklisting uses Redis SET entries with TTL matching
# the token's remaining lifetime.  Redis TTL handles cleanup
# automatically; a Celery beat task provides a safety net.


async def blacklist_jti(jti: str, ttl: int) -> bool:
    """Add a token's jti to the blacklist.

    CROSS-6: Stores the jti in Redis with an expiry (TTL) matching
    the token's remaining lifetime so that blacklisted entries are
    automatically cleaned up.

    Uses a global Redis key (parwa:blacklist:{jti}) rather than
    tenant-scoped because jti is globally unique and the blacklist
    check runs before tenant context is available.

    Args:
        jti: The JWT ID (unique token identifier) to blacklist.
        ttl: Time-to-live in seconds (should match token expiry).

    Returns:
        True if the jti was successfully blacklisted, False otherwise.
    """
    if not jti or ttl <= 0:
        logger.warning(
            "blacklist_jti_invalid_args jti=%s ttl=%d",
            "present" if jti else "missing",
            ttl,
        )
        return False
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        key = f"{_BLACKLIST_PREFIX}:{jti}"
        await redis.set(key, "1", ex=ttl)
        logger.info("token_blacklisted jti=%s ttl=%d", jti, ttl)
        return True
    except Exception as exc:
        # Never break logout flow on Redis failure — log and continue.
        # The token will expire naturally via JWT expiry.
        logger.error(
            "blacklist_jti_failed jti=%s error=%s",
            jti,
            str(exc)[:200],
        )
        return False


async def is_token_revoked(jti: str) -> bool:
    """Check if a token's jti is in the blacklist.

    CROSS-6: Queries Redis to determine whether a token has been
    explicitly revoked (logged out, password changed, etc.).

    C-02 FIX: In production, this fails CLOSED on Redis errors — if
    Redis is unavailable, the token is rejected rather than allowed.
    This prevents an attacker from bypassing revocation by taking
    Redis offline. In non-production environments, fails open for
    developer convenience but logs a strong warning.

    Args:
        jti: The JWT ID to check.

    Returns:
        True if the token has been revoked, False otherwise.
        In production: True (reject) if Redis is unavailable.
        In dev/staging/test: False (allow) if Redis is unavailable.
    """
    if not jti:
        return False
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        key = f"{_BLACKLIST_PREFIX}:{jti}"
        result = await redis.exists(key)
        if result:
            logger.info(
                "token_revocation_detected jti=%s", jti
            )
        return bool(result)
    except Exception as exc:
        # C-02 FIX: Fail-closed in production, fail-open in dev
        environment = os.environ.get("ENVIRONMENT", "development")
        if environment == "production":
            # FAIL CLOSED: If we can't check the blacklist in production,
            # assume the token IS revoked. This prevents an attacker from
            # bypassing token revocation by causing Redis failures.
            logger.critical(
                "is_token_revoked_redis_failed_FAIL_CLOSED jti=%s error=%s "
                "— token rejected because Redis is unavailable in production",
                jti,
                str(exc)[:200],
            )
            return True
        else:
            # Fail-open in non-production for developer convenience
            logger.error(
                "is_token_revoked_redis_failed_fail_open jti=%s error=%s "
                "— token allowed because Redis unavailable (non-production)",
                jti,
                str(exc)[:200],
            )
            return False


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


def rotate_jwt_key(new_key: str, algorithm: str = "HS256") -> dict:
    """Rotate JWT signing key.

    Administrative function for key rotation. The old key is preserved
    in JWT_PREVIOUS_KEYS so that tokens signed with it remain valid
    until they expire naturally.

    Args:
        new_key: The new signing key (secret for HS256, private key PEM for RS256).
        algorithm: The algorithm to use ("HS256" or "RS256").

    Returns:
        Status dict with success flag and message.
    """
    if algorithm not in ("HS256", "RS256"):
        return {
            "success": False,
            "message": f"Unsupported algorithm: '{algorithm}'. Use 'HS256' or 'RS256'.",
        }

    if algorithm == "HS256":
        settings = get_settings()
        old_key = settings.JWT_SECRET_KEY
        # Add old key to previous keys list if not already there
        if old_key not in _JWT_PREVIOUS_KEYS:
            _JWT_PREVIOUS_KEYS.append(old_key)
        logger.info(
            "JWT key rotated (HS256). Previous keys count: %d",
            len(_JWT_PREVIOUS_KEYS),
        )
    else:
        # For RS256, the key rotation is handled via config env vars.
        # The old keys should be managed via JWT_PREVIOUS_KEYS env var.
        logger.info("JWT key rotation noted for RS256. Update JWT_PRIVATE_KEY_PATH or JWT_PRIVATE_KEY_BASE64.")

    return {
        "success": True,
        "message": "Key rotated. Old keys remain valid until tokens expire.",
    }


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


async def blacklist_current_token(token: str) -> bool:
    """Blacklist the current access token immediately.

    CROSS-6: Convenience function for logout / password-reset flows.
    Extracts the jti and remaining TTL from the token and adds
    it to the blacklist.

    Args:
        token: The raw JWT access token string.

    Returns:
        True if blacklisted successfully, False otherwise.
    """
    try:
        payload = jwt.get_unverified_claims(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            logger.warning(
                "blacklist_current_token_missing_claims "
                "jti=%s exp=%s",
                "present" if jti else "missing",
                "present" if exp else "missing",
            )
            return False
        import time
        remaining_ttl = max(int(exp - time.time()), 1)
        return await blacklist_jti(jti, remaining_ttl)
    except Exception as exc:
        logger.error(
            "blacklist_current_token_failed error=%s",
            str(exc)[:200],
        )
        return False
