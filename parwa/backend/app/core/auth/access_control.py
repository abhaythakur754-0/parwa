"""
PARWA Phase 1 — Key-Based Access System

- Key generation (pk_live_XXXXXXXXXXXX format)
- Key validation (SHA-256 hash lookup)
- JWT session management (tenant_id + session_id)
- Failed attempt tracking with 15-min lockout
- Rate limiting per key
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger("parwa.auth")


# ── Key Generation ────────────────────────────────────────────

KEY_PREFIX_LIVE = "pk_live_"
KEY_PREFIX_TEST = "pk_test_"


def generate_api_key(key_type: str = "live") -> Tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        (full_key, key_prefix, key_hash)
        - full_key:  "pk_live_abc123..." — shown ONCE to the user
        - key_prefix: "pk_live_abc1"    — stored for display/search
        - key_hash:   SHA-256 hash      — stored in DB, full key never stored
    """
    prefix = KEY_PREFIX_LIVE if key_type == "live" else KEY_PREFIX_TEST
    random_part = secrets.token_urlsafe(32)  # 43 chars, URL-safe
    full_key = f"{prefix}{random_part}"
    key_prefix = full_key[:16]  # first 16 chars for display
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    return full_key, key_prefix, key_hash


# ── Key Validation ────────────────────────────────────────────

def hash_api_key(full_key: str) -> str:
    """Hash an API key for DB lookup."""
    return hashlib.sha256(full_key.encode()).hexdigest()


def verify_key_hash(provided_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of key hash (prevents timing attacks)."""
    computed = hashlib.sha256(provided_key.encode()).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


# ── JWT Session Management ────────────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET", "parwa-phase1-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def create_jwt_session(
    tenant_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a JWT token with tenant_id + session_id.

    Uses a simple HMAC-based implementation (no external dep needed).
    For production, swap to PyJWT or python-jose.
    """
    import base64

    now = int(time.time())
    sid = session_id or str(uuid4())

    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_id": sid,
        "iat": now,
        "exp": now + (JWT_EXPIRY_HOURS * 3600),
    }
    if extra_claims:
        payload.update(extra_claims)

    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")

    # Header
    header = {"alg": "HS256", "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":"))
    header_b64 = base64.urlsafe_b64encode(header_json.encode()).decode().rstrip("=")

    # Signature
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_jwt_session(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token.

    Returns None if invalid/expired.
    """
    import base64

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        # Pad base64
        header_b64 += "=" * (4 - len(header_b64) % 4)
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        signature_b64 += "=" * (4 - len(signature_b64) % 4)

        # Verify signature
        signing_input = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(
            JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        actual_sig = base64.urlsafe_b64decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("JWT signature mismatch")
            return None

        # Decode payload
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        # Check expiry
        if payload.get("exp", 0) < int(time.time()):
            logger.warning("JWT expired for tenant %s", payload.get("tenant_id"))
            return None

        return payload

    except Exception as e:
        logger.warning("JWT verification failed: %s", e)
        return None


# ── Failed Attempt Tracking & Lockout ─────────────────────────

# In-memory store for Phase 1. Production uses the failed_auth_attempts table.
_failed_attempts: Dict[str, Dict[str, Any]] = {}  # identifier -> {count, locked_until}

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes


def check_lockout(identifier: str) -> Tuple[bool, Optional[float]]:
    """Check if an identifier is locked out.

    Returns:
        (is_locked, seconds_remaining)
    """
    record = _failed_attempts.get(identifier)
    if not record:
        return False, None

    if record["locked_until"] and record["locked_until"] > time.time():
        remaining = record["locked_until"] - time.time()
        return True, remaining

    # Lockout expired, reset
    if record["locked_until"] and record["locked_until"] <= time.time():
        del _failed_attempts[identifier]
        return False, None

    return False, None


def record_failed_attempt(identifier: str) -> Tuple[int, bool, Optional[float]]:
    """Record a failed auth attempt.

    Returns:
        (total_attempts, is_now_locked, lockout_seconds_remaining)
    """
    record = _failed_attempts.get(identifier, {"count": 0, "locked_until": None})
    record["count"] += 1

    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = time.time() + LOCKOUT_DURATION_SECONDS
        _failed_attempts[identifier] = record
        return record["count"], True, LOCKOUT_DURATION_SECONDS

    _failed_attempts[identifier] = record
    return record["count"], False, None


def reset_failed_attempts(identifier: str) -> None:
    """Clear failed attempts on successful auth."""
    _failed_attempts.pop(identifier, None)


# ── Rate Limiting ─────────────────────────────────────────────

# In-memory sliding window. Production uses Redis.
_rate_limit_windows: Dict[str, list] = {}  # key_id -> [timestamp, ...]
DEFAULT_RATE_LIMIT_RPM = 40


def check_rate_limit(
    key_id: str, rpm_limit: int = DEFAULT_RATE_LIMIT_RPM
) -> Tuple[bool, int, int]:
    """Sliding window rate limit check.

    Returns:
        (allowed, remaining_requests, reset_seconds)
    """
    now = time.time()
    window_start = now - 60  # 60-second sliding window

    if key_id not in _rate_limit_windows:
        _rate_limit_windows[key_id] = []

    # Remove old entries outside the window
    _rate_limit_windows[key_id] = [
        ts for ts in _rate_limit_windows[key_id] if ts > window_start
    ]

    current_count = len(_rate_limit_windows[key_id])

    if current_count >= rpm_limit:
        oldest = _rate_limit_windows[key_id][0]
        reset_seconds = int(oldest - window_start) + 1
        return False, 0, reset_seconds

    _rate_limit_windows[key_id].append(now)
    remaining = rpm_limit - current_count - 1
    return True, remaining, 0


# ── Auth Middleware Logic ─────────────────────────────────────

async def validate_request(
    api_key: Optional[str] = None,
    jwt_token: Optional[str] = None,
    client_ip: str = "unknown",
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Validate an incoming request by API key or JWT.

    Args:
        api_key: The full API key from Authorization header
        jwt_token: Bearer JWT token
        client_ip: Client IP for lockout tracking

    Returns:
        (is_valid, context, error_message)
        context contains: tenant_id, user_id, session_id, key_id, etc.
    """
    identifier = client_ip

    # Check lockout first
    is_locked, lockout_remaining = check_lockout(identifier)
    if is_locked:
        return False, None, f"Locked out. Try again in {int(lockout_remaining)}s."

    # Try JWT first (session-based)
    if jwt_token:
        payload = verify_jwt_session(jwt_token)
        if payload:
            return True, {
                "tenant_id": payload["tenant_id"],
                "user_id": payload.get("user_id"),
                "session_id": payload.get("session_id"),
                "auth_method": "jwt",
            }, ""
        else:
            count, locked, _ = record_failed_attempt(identifier)
            return False, None, f"Invalid JWT (attempt {count}/{MAX_FAILED_ATTEMPTS})"

    # Try API key
    if api_key:
        key_hash = hash_api_key(api_key)
        # In production: DB lookup by key_hash
        # Phase 1: validate against known test keys
        valid, context = _validate_key_against_store(api_key, key_hash)
        if valid:
            reset_failed_attempts(identifier)
            return True, context, ""
        else:
            count, locked, remaining = record_failed_attempt(identifier)
            if locked:
                return False, None, f"Too many failures. Locked for {remaining}s."
            return False, None, f"Invalid API key (attempt {count}/{MAX_FAILED_ATTEMPTS})"

    return False, None, "No authentication provided. Supply API key or JWT."


def _validate_key_against_store(
    full_key: str, key_hash: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Look up a key hash against the key store.

    Phase 1: In-memory store. Production: DB lookup.
    Returns (is_valid, context_dict).
    """
    # Check in-memory registered keys
    for kid, kdata in _registered_keys.items():
        if verify_key_hash(full_key, kdata["key_hash"]):
            # Check expiry
            if kdata.get("expires_at") and kdata["expires_at"] < time.time():
                logger.warning("Expired key used: %s", kid)
                return False, None
            # Check active
            if not kdata.get("is_active", True):
                logger.warning("Inactive key used: %s", kid)
                return False, None
            # Rate limit check
            allowed, remaining, reset = check_rate_limit(
                kid, kdata.get("rate_limit_rpm", DEFAULT_RATE_LIMIT_RPM)
            )
            if not allowed:
                logger.warning("Rate limit exceeded for key %s", kid)
                return False, None

            return True, {
                "tenant_id": kdata["tenant_id"],
                "user_id": kdata.get("user_id"),
                "key_id": kid,
                "key_prefix": kdata["key_prefix"],
                "auth_method": "api_key",
                "rate_limit_remaining": remaining,
            }

    return False, None


# ── Key Registration (in-memory for Phase 1) ──────────────────

# Production: keys stored in access_keys table
# Phase 1: in-memory dict for testing
_registered_keys: Dict[str, Dict[str, Any]] = {}


def register_key(
    tenant_id: str,
    key_type: str = "live",
    name: str = "Default Key",
    user_id: Optional[str] = None,
    rate_limit_rpm: int = DEFAULT_RATE_LIMIT_RPM,
    expires_hours: Optional[int] = None,
) -> Dict[str, str]:
    """Generate and register a new API key.

    Returns dict with full_key (shown ONCE), key_prefix, key_id.
    """
    full_key, key_prefix, key_hash = generate_api_key(key_type)
    key_id = str(uuid4())

    expires_at = None
    if expires_hours:
        expires_at = time.time() + (expires_hours * 3600)

    _registered_keys[key_id] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "key_type": key_type,
        "name": name,
        "is_active": True,
        "rate_limit_rpm": rate_limit_rpm,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Key registered: id=%s prefix=%s tenant=%s type=%s",
        key_id, key_prefix, tenant_id, key_type,
    )

    return {
        "key_id": key_id,
        "full_key": full_key,       # Show ONCE, never stored in plain text
        "key_prefix": key_prefix,   # Safe to display
    }


def list_keys(tenant_id: str) -> list:
    """List all keys for a tenant (safe info only, no full keys)."""
    results = []
    for kid, kdata in _registered_keys.items():
        if kdata["tenant_id"] == tenant_id:
            results.append({
                "key_id": kid,
                "key_prefix": kdata["key_prefix"],
                "name": kdata["name"],
                "key_type": kdata["key_type"],
                "is_active": kdata["is_active"],
                "rate_limit_rpm": kdata["rate_limit_rpm"],
                "created_at": kdata["created_at"],
            })
    return results


def revoke_key(key_id: str) -> bool:
    """Revoke (deactivate) a key."""
    if key_id in _registered_keys:
        _registered_keys[key_id]["is_active"] = False
        logger.info("Key revoked: %s", key_id)
        return True
    return False


# ── Tenant Context (set on every request) ─────────────────────

_current_tenant_context: Optional[Dict[str, Any]] = None


def set_tenant_context(context: Dict[str, Any]) -> None:
    """Set the tenant context for the current request.

    Equivalent to PostgreSQL: SELECT set_tenant_context(tenant_id)
    """
    global _current_tenant_context
    _current_tenant_context = context


def get_tenant_context() -> Optional[Dict[str, Any]]:
    """Get the current tenant context."""
    return _current_tenant_context


def clear_tenant_context() -> None:
    """Clear tenant context at end of request."""
    global _current_tenant_context
    _current_tenant_context = None


def require_tenant_id() -> str:
    """Get tenant_id or raise if no context set.

    Use this in every database query to enforce tenant isolation.
    """
    ctx = _current_tenant_context
    if not ctx or "tenant_id" not in ctx:
        raise PermissionError("No tenant context. Authentication required.")
    return ctx["tenant_id"]