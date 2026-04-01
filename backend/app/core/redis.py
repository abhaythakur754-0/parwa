"""
PARWA Redis Connection Layer (BC-001)

Provides a managed Redis connection pool with tenant-scoped key namespacing.
Every Redis key MUST include company_id in the namespace: parwa:{company_id}:*

BC-001: No global keys — all keys are tenant-isolated.
BC-011: Redis URL loaded from environment, never hardcoded.
BC-012: Redis failure -> fail-open (consistent with rate_limiter design).

Usage:
    from backend.app.core.redis import get_redis, make_key

    redis = get_redis()
    await redis.set(make_key("session", company_id, session_id), "data")
    value = await redis.get(make_key("session", company_id, session_id))
"""

import json
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from backend.app.config import get_settings
from backend.app.logger import get_logger

logger = get_logger("redis")

# Module-level redis client singleton
_redis_client: Optional[aioredis.Redis] = None

# Key namespace prefix — BC-001: all keys scoped by tenant
NAMESPACE_PREFIX = "parwa"


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
