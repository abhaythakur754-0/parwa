"""
PARWA Redis Connection Layer (BC-001)

Provides a managed Redis connection pool with tenant-scoped key namespacing.
Every Redis key MUST include company_id in the namespace: parwa:{company_id}:*

BC-001: No global keys — all keys are tenant-isolated.
BC-011: Redis URL loaded from environment, never hardcoded.
BC-012: Redis failure -> fail-open (consistent with rate_limiter design).

Day 20: Added key validation enforcement:
- validate_tenant_key() checks key follows parwa:{company_id}:* pattern
- validate_tenant_keys() filters to only keys matching current tenant
- safe_get() / safe_mget() validate tenant key prefix before operating
- Warning logged for raw key access attempts

Usage:
    from app.core.redis import get_redis, make_key

    redis = get_redis()
    await redis.set(make_key("session", company_id, session_id), "data")
    value = await redis.get(make_key("session", company_id, session_id))
"""

import asyncio
import json
import re
import threading
import time
from typing import Any, List, Optional

import redis.asyncio as aioredis

from app.config import get_settings
from app.logger import get_logger

logger = get_logger("redis")

# Module-level redis client singleton
_redis_client: Optional[aioredis.Redis] = None

# H1 fix: Thread-safety for sync contexts.
# _redis_init_lock protects the async path (get_redis).
# _redis_thread_lock is available for any future sync get_redis_sync() function
# or background thread that accesses _redis_client.  Currently there is no
# sync accessor, so this lock is a defensive placeholder.
_redis_thread_lock = threading.Lock()
_redis_init_lock = asyncio.Lock()

# NOTE: No sync get_redis() or get_redis_sync() exists in this module.
# If one is added in the future, it MUST acquire _redis_thread_lock
# before reading/writing _redis_client to prevent cross-thread races.

# Key namespace prefix — BC-001: all keys scoped by tenant
NAMESPACE_PREFIX = "parwa"

# Pattern for validating tenant-scoped keys: parwa:{company_id}:*
_TENANT_KEY_PATTERN = re.compile(r"^parwa:[^:]+:.+$")

# Pattern for raw (non-tenant) keys that should trigger warnings
_RAW_KEY_PATTERN = re.compile(r"^(?!parwa:)")


def make_key(company_id: str, *parts: str) -> str:
    """Build a tenant-scoped Redis key.

    Every key follows the format: parwa:{company_id}:{part1}:{part2}:...

    BC-001: company_id is ALWAYS the first segment after the prefix.
    This prevents any possibility of cross-tenant key collision.

    Args:
        company_id: The tenant identifier (required, no default).
        *parts: Additional key segments (e.g., "session", "abc123").

    Returns:
        Namespaced Redis key string.

    Raises:
        ValueError: If company_id is empty or contains control characters.

    Examples:
        >>> make_key("acme", "session", "sess_123")
        'parwa:acme:session:sess_123'
        >>> make_key("acme", "rate_limit")
        'parwa:acme:rate_limit'
    """
    if not company_id or not isinstance(company_id, str):
        raise ValueError(
            "company_id is required and must be a non-empty string (BC-001)"
        )
    if not company_id.strip():
        raise ValueError("company_id must not be whitespace-only (BC-001)")
    # Reject control characters (same guard as tenant middleware)
    if any(ord(c) < 32 for c in company_id):
        raise ValueError("Invalid company_id: contains control characters")
    # Sanitize: strip whitespace
    company_id = company_id.strip()
    # Build the namespaced key
    segments = [NAMESPACE_PREFIX, company_id] + list(parts)
    return ":".join(segments)


def validate_tenant_key(key: str) -> bool:
    """Check if a Redis key follows the tenant-scoped pattern.

    Valid keys must match: parwa:{company_id}:*

    Args:
        key: The Redis key to validate.

    Returns:
        True if the key is properly tenant-scoped, False otherwise.
    """
    if not key or not isinstance(key, str):
        return False
    return bool(_TENANT_KEY_PATTERN.match(key))


def validate_tenant_keys(keys: list) -> list:
    """Filter a list of keys to only include those matching the current tenant.

    Reads the current company_id from tenant_context and filters keys
    to only those starting with parwa:{company_id}:.

    Keys that don't match the pattern are logged as potential cross-tenant
    access attempts.

    Args:
        keys: List of Redis key strings.

    Returns:
        Filtered list containing only keys matching the current tenant.
    """
    from app.core.tenant_context import get_tenant_context

    company_id = get_tenant_context()
    if not company_id:
        logger.warning(
            "validate_tenant_keys_no_context",
            extra={"key_count": len(keys)},
        )
        # Without context, can't validate — return empty for safety
        return []

    prefix = f"parwa:{company_id}:"
    valid_keys = []
    rejected_keys = []

    for key in keys:
        if isinstance(key, str) and key.startswith(prefix):
            valid_keys.append(key)
        else:
            rejected_keys.append(key)

    if rejected_keys:
        logger.warning(
            "tenant_key_rejection",
            extra={
                "company_id": company_id,
                "rejected_count": len(rejected_keys),
                "rejected_keys_sample": rejected_keys[:5],
            },
        )

    return valid_keys


async def safe_get(key: str, default: Any = None) -> Any:
    """Safely get a Redis key with tenant validation.

    Validates that the key follows the parwa:{company_id}:* pattern
    before performing the operation. Keys that don't match are rejected
    with a warning log.

    Args:
        key: The Redis key to retrieve.
        default: Value to return if key is invalid or not found.

    Returns:
        The cached value, default, or None.
    """
    if not validate_tenant_key(key):
        logger.warning(
            "safe_get_rejected_non_tenant_key",
            extra={"key": key[:100]},
        )
        return default

    try:
        client = await get_redis()
        value = await client.get(key)
        if value is not None:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return default
    except Exception:
        return default


async def safe_mget(keys: List[str]) -> List[Any]:
    """Safely get multiple Redis keys with tenant validation.

    Filters keys through validate_tenant_keys() to ensure only
    keys belonging to the current tenant are accessed.

    Args:
        keys: List of Redis keys to retrieve.

    Returns:
        List of values (None for missing/invalid keys).
    """
    valid_keys = validate_tenant_keys(keys)

    if not valid_keys:
        return [None] * len(keys)

    try:
        client = await get_redis()
        # Get values only for valid keys
        valid_values = await client.mget(valid_keys)
        # Build result: valid key → value, invalid key → None
        valid_set = set(valid_keys)
        result = []
        valid_idx = 0
        for key in keys:
            if key in valid_set:
                val = valid_values[valid_idx]
                if val is not None:
                    try:
                        result.append(json.loads(val))
                    except (json.JSONDecodeError, TypeError):
                        result.append(val)
                else:
                    result.append(None)
                valid_idx += 1
            else:
                result.append(None)
        return result
    except Exception:
        return [None] * len(keys)


def _log_raw_key_access(key: str, operation: str) -> None:
    """Log a warning when a raw (non-tenant-scoped) key is accessed.

    Args:
        key: The raw key being accessed.
        operation: The operation being performed (e.g., 'get', 'set').
    """
    logger.warning(
        "raw_key_access_attempt",
        extra={
            "key": key[:100],
            "operation": operation,
            "warning": (
                "Redis key does not follow tenant-scoped pattern "
                "parwa:{company_id}:*. Use make_key() or safe_* wrappers."
            ),
        },
    )


async def get_redis() -> aioredis.Redis:
    """Get or create the Redis connection pool singleton.

    Uses connection pooling for efficient connection reuse.
    Redis URL is loaded from REDIS_URL environment variable (BC-011).

    Returns:
        Async Redis client connected to the pool.

    Raises:
        Exception: If Redis is unreachable (callers should handle
                   with fail-open per BC-012).
    """
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        async with _redis_init_lock:
            if _redis_client is None:  # double-check pattern
                settings = get_settings()
                _redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                logger.info(
                    "redis_connected",
                    url=settings.REDIS_URL.split("@")[-1]
                    if "@" in settings.REDIS_URL else "localhost",
                )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool gracefully.

    Must be called during application shutdown to prevent connection leaks.
    Safe to call multiple times (idempotent).
    """
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
            logger.info("redis_disconnected")
        except Exception as exc:
            logger.warning("redis_disconnect_error", error=str(exc))
        finally:
            _redis_client = None


async def redis_health_check() -> dict:
    """Check Redis connectivity and return health status.

    Used by the /health endpoint (BC-012) to detect Redis failures.

    Returns:
        Dict with 'status' ('healthy' or 'unhealthy'), 'latency_ms',
        and optional 'error'.
    """
    start = time.monotonic()
    try:
        client = await get_redis()
        await client.ping()
        latency = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency}
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        logger.warning("redis_health_check_failed", error=str(exc))
        return {
            "status": "unhealthy",
            "latency_ms": latency,
            "error": str(exc),
        }


async def cache_get(
    company_id: str, key: str, default: Any = None
) -> Any:
    """Get a cached value by tenant-scoped key.

    Args:
        company_id: Tenant identifier (BC-001).
        key: Cache key suffix (appended after company_id).
        default: Value to return if key not found.

    Returns:
        Cached value or default.
    """
    try:
        client = await get_redis()
        value = await client.get(make_key(company_id, "cache", key))
        if value is not None:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return default
    except Exception:
        return default


async def cache_set(
    company_id: str,
    key: str,
    value: Any,
    ttl_seconds: int = 300,
) -> bool:
    """Set a cached value with tenant-scoped key and TTL.

    Args:
        company_id: Tenant identifier (BC-001).
        key: Cache key suffix.
        value: Value to cache (will be JSON-serialized if not string).
        ttl_seconds: Time-to-live in seconds (default 5 minutes).

    Returns:
        True if set succeeded, False otherwise.
    """
    try:
        client = await get_redis()
        serialized = value if isinstance(value, str) else json.dumps(value)
        await client.set(
            make_key(company_id, "cache", key),
            serialized,
            ex=ttl_seconds,
        )
        return True
    except Exception:
        return False


async def cache_delete(company_id: str, key: str) -> bool:
    """Delete a cached value by tenant-scoped key.

    Args:
        company_id: Tenant identifier (BC-001).
        key: Cache key suffix to delete.

    Returns:
        True if delete succeeded, False otherwise.
    """
    try:
        client = await get_redis()
        await client.delete(make_key(company_id, "cache", key))
        return True
    except Exception:
        return False
