"""
Redis Key Namespace Manager (Phase 6: Production Hardening)

Standardizes all Redis keys across PARWA with:
- Consistent namespace pattern: parwa:{namespace}:{company_id}:{key}
- TTL defaults per namespace
- Key validation
- Bulk cleanup utilities
- Key usage metrics

BC-001: company_id is ALWAYS the second segment after the namespace prefix.
BC-008: Never crash — all methods handle errors gracefully.
BC-012: All timestamps UTC.

Existing Key Patterns Found in Codebase (audited):
  Properly namespaced (parwa:{company_id}:*):
    - parwa:{company_id}:cache:{key}
    - parwa:{company_id}:events
    - parwa:{company_id}:jarvis:bridge:{session_id}
    - parwa:{company_id}:jarvis:awareness:{session_id}
    - parwa:{company_id}:jarvis:feedback:{session_id}
    - parwa:{company_id}:pii:{redaction_id}
    - parwa:{company_id}:freshness:{type}:{id}
    - parwa:{company_id}:ticket_viewing:{ticket_id}
    - parwa:{company_id}:guardrails:blocked:{id}
    - parwa:{company_id}:guardrails:stats
    - parwa:{company_id}:escalation_cooldown[:{ticket_id}]
    - parwa:{company_id}:injection_rate:{user_key}
    - parwa:{company_id}:tenant_blocklist
    - parwa:{company_id}:training_data:{variant}:{dataset_id}
    - parwa:{company_id}:recent_searches:{user_id}

  Non-standard patterns (flagged for migration):
    - health:{provider}:{model_id}           (redis_health_tracker — no parwa prefix)
    - health:last_daily_reset                (redis_health_tracker — no parwa prefix)
    - parwa:rl:{hash}                        (rate_limit_service — no company_id)
    - parwa:rl:fail:{hash}                   (rate_limit_service — no company_id)
    - brand_voice:{company_id}               (brand_voice_service — no parwa prefix)
    - migration:{company_id}:{suffix}        (rule_ai_migration — no parwa prefix)
    - {tenant_id}:{feature}                  (rule_to_ai_migration — no parwa prefix)

Usage:
    from app.core.redis_key_manager import build_key, get_ttl, RedisNamespace

    key = build_key(RedisNamespace.CACHE, "BC-001", "query:hello")
    # -> "parwa:cache:BC-001:query:hello"

    ttl = get_ttl(RedisNamespace.CACHE)  # -> 120
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("redis_key_manager")


# ═══════════════════════════════════════════════════════════════════════
# NAMESPACE ENUM
# ═══════════════════════════════════════════════════════════════════════


class RedisNamespace(str, Enum):
    """All valid Redis key namespaces in PARWA."""
    SESSION = "session"
    RATE_LIMIT = "ratelimit"
    HEALTH = "health"
    CACHE = "cache"
    AWARENESS = "awareness"
    JARVIS_BRIDGE = "jarvis:bridge"
    JARVIS_COMMAND = "jarvis:command"
    JARVIS_FEED = "jarvis:feed"
    EVENT_BUFFER = "events"
    SOCKETIO = "socketio"
    TECHNIQUE = "technique"
    KNOWLEDGE = "knowledge"
    BILLING = "billing"
    WEBHOOK = "webhook"
    SLA = "sla"
    TRAINING = "training"
    ANALYTICS = "analytics"
    PII = "pii"
    OTP = "otp"
    API_KEY = "apikey"
    LOCK = "lock"
    GUARDRAILS = "guardrails"
    FRESHNESS = "freshness"
    MIGRATION = "migration"
    BRAND_VOICE = "brand_voice"
    COLLISION = "collision"
    INJECTION_DEFENSE = "injection_defense"


# ═══════════════════════════════════════════════════════════════════════
# TTL DEFAULTS PER NAMESPACE
# ═══════════════════════════════════════════════════════════════════════

NAMESPACE_TTL_DEFAULTS: Dict[RedisNamespace, int] = {
    RedisNamespace.SESSION: 86400,          # 24 hours
    RedisNamespace.RATE_LIMIT: 3600,        # 1 hour
    RedisNamespace.HEALTH: 120,             # 2 minutes
    RedisNamespace.CACHE: 120,              # 2 minutes (general cache)
    RedisNamespace.AWARENESS: 300,          # 5 minutes
    RedisNamespace.JARVIS_BRIDGE: 600,      # 10 minutes
    RedisNamespace.JARVIS_COMMAND: 600,     # 10 minutes
    RedisNamespace.JARVIS_FEED: 300,        # 5 minutes
    RedisNamespace.EVENT_BUFFER: 86400,     # 24 hours
    RedisNamespace.SOCKETIO: 3600,          # 1 hour
    RedisNamespace.TECHNIQUE: 3600,         # 1 hour
    RedisNamespace.KNOWLEDGE: 1800,         # 30 minutes
    RedisNamespace.BILLING: 300,            # 5 minutes
    RedisNamespace.WEBHOOK: 300,            # 5 minutes
    RedisNamespace.SLA: 60,                 # 1 minute
    RedisNamespace.TRAINING: 86400,         # 24 hours
    RedisNamespace.ANALYTICS: 600,          # 10 minutes
    RedisNamespace.PII: 3600,               # 1 hour
    RedisNamespace.OTP: 300,                # 5 minutes
    RedisNamespace.API_KEY: 3600,           # 1 hour
    RedisNamespace.LOCK: 30,                # 30 seconds (distributed lock)
    RedisNamespace.GUARDRAILS: 7776000,     # 90 days
    RedisNamespace.FRESHNESS: 300,          # 5 minutes
    RedisNamespace.MIGRATION: 86400,        # 24 hours
    RedisNamespace.BRAND_VOICE: 3600,       # 1 hour
    RedisNamespace.COLLISION: 300,          # 5 minutes
    RedisNamespace.INJECTION_DEFENSE: 3600, # 1 hour
}

# Global prefix
NAMESPACE_PREFIX = "parwa"

# Pattern for validating keys built by build_key()
_STANDARD_KEY_PATTERN = re.compile(
    r"^parwa:[a-zA-Z0-9_:-]+:[^:]+:.+$"
)

# Pattern for validating individual key segment characters
_SAFE_CHAR_PATTERN = re.compile(r"^[a-zA-Z0-9_\-:]+$")


# ═══════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════


def build_key(
    namespace: RedisNamespace,
    company_id: str,
    key: str,
    suffix: Optional[str] = None,
) -> str:
    """Build a standardized Redis key.

    Pattern: parwa:{namespace}:{company_id}:{key}[:{suffix}]

    This replaces the old make_key() pattern which used
    parwa:{company_id}:{namespace}:{key}. The new pattern places
    namespace BEFORE company_id for better SCAN grouping by namespace.

    For backward compatibility, the old make_key() in redis.py
    continues to work. New code should use build_key().

    Args:
        namespace: Valid RedisNamespace enum value
        company_id: Tenant identifier (BC-001)
        key: Specific key within namespace
        suffix: Optional additional segment

    Returns:
        Standardized Redis key string

    Raises:
        ValueError: If company_id or key contains invalid characters
    """
    # Validate company_id
    if not company_id or not isinstance(company_id, str):
        raise ValueError(
            "company_id is required and must be a non-empty string (BC-001)"
        )
    if not company_id.strip():
        raise ValueError("company_id must not be whitespace-only (BC-001)")
    if any(ord(c) < 32 for c in company_id):
        raise ValueError("Invalid company_id: contains control characters")
    company_id = company_id.strip()

    # Validate key
    if not key or not isinstance(key, str):
        raise ValueError("key is required and must be a non-empty string")
    if not key.strip():
        raise ValueError("key must not be whitespace-only")

    # Build the namespaced key
    segments = [NAMESPACE_PREFIX, namespace.value, company_id, key]
    if suffix is not None:
        if not isinstance(suffix, str) or not suffix.strip():
            raise ValueError("suffix must be a non-empty string if provided")
        segments.append(suffix)

    return ":".join(segments)


def get_ttl(namespace: RedisNamespace, custom_ttl: Optional[int] = None) -> int:
    """Get TTL for a namespace, with optional override.

    Args:
        namespace: Namespace to get TTL for
        custom_ttl: Optional override TTL in seconds

    Returns:
        TTL in seconds (minimum 1 second)
    """
    if custom_ttl is not None and isinstance(custom_ttl, int) and custom_ttl > 0:
        return custom_ttl

    default = NAMESPACE_TTL_DEFAULTS.get(namespace, 300)  # 5 min fallback
    return max(1, default)


def validate_key(key: str) -> bool:
    """Validate a Redis key contains only safe characters.

    Allowed: alphanumeric, hyphens, underscores, colons.

    Args:
        key: The key string to validate.

    Returns:
        True if key is valid, False otherwise.
    """
    if not key or not isinstance(key, str):
        return False
    # Reject control characters
    if any(ord(c) < 32 for c in key):
        return False
    # Allow alphanumeric, hyphens, underscores, colons, periods
    return bool(re.match(r"^[a-zA-Z0-9_\-:.]+$", key))


def parse_key(key: str) -> Optional[Dict[str, str]]:
    """Parse a standardized Redis key into its components.

    Args:
        key: A key built by build_key()

    Returns:
        Dict with 'prefix', 'namespace', 'company_id', 'key', 'suffix'
        or None if the key doesn't match the standard pattern.
    """
    if not key or not isinstance(key, str):
        return None

    parts = key.split(":")
    # Minimum: parwa:{namespace}:{company_id}:{key} = 4 parts
    if len(parts) < 4:
        return None
    if parts[0] != NAMESPACE_PREFIX:
        return None

    # Handle namespaces that contain colons (e.g., "jarvis:bridge")
    # Try to match against known namespaces
    result = {
        "prefix": parts[0],
        "namespace": "",
        "company_id": "",
        "key": "",
        "suffix": "",
    }

    # Try matching namespace from known values
    for ns in RedisNamespace:
        ns_parts = ns.value.split(":")
        candidate = ":".join(parts[1:1 + len(ns_parts)])
        if candidate == ns.value:
            result["namespace"] = ns.value
            remaining = parts[1 + len(ns_parts):]
            if len(remaining) >= 2:
                result["company_id"] = remaining[0]
                result["key"] = remaining[1]
                if len(remaining) > 2:
                    result["suffix"] = ":".join(remaining[2:])
            return result

    # Fallback: assume namespace is a single segment
    if len(parts) >= 4:
        result["namespace"] = parts[1]
        result["company_id"] = parts[2]
        result["key"] = parts[3]
        if len(parts) > 4:
            result["suffix"] = ":".join(parts[4:])
        return result

    return None


def identify_namespace(key: str) -> Optional[RedisNamespace]:
    """Identify which RedisNamespace a key belongs to.

    Works with both old (parwa:{company_id}:{ns}) and new
    (parwa:{ns}:{company_id}) patterns, as well as non-standard keys.

    Args:
        key: Any Redis key string.

    Returns:
        The matching RedisNamespace, or None if unknown.
    """
    if not key or not isinstance(key, str):
        return None

    # Check old pattern: parwa:{company_id}:{namespace_segment}:*
    # And new pattern: parwa:{namespace_segment}:{company_id}:*
    parts = key.split(":")
    if len(parts) < 3:
        return None

    # Try to find a namespace match in the key
    key_lower = key.lower()

    namespace_keywords = {
        RedisNamespace.SESSION: ["session"],
        RedisNamespace.RATE_LIMIT: ["ratelimit", "rl:"],
        RedisNamespace.HEALTH: ["health:"],
        RedisNamespace.CACHE: ["cache:"],
        RedisNamespace.AWARENESS: ["awareness"],
        RedisNamespace.JARVIS_BRIDGE: ["jarvis:bridge", "jarvis:awareness"],
        RedisNamespace.JARVIS_COMMAND: ["jarvis:command"],
        RedisNamespace.JARVIS_FEED: ["jarvis:feed", "jarvis:feedback"],
        RedisNamespace.EVENT_BUFFER: ["events"],
        RedisNamespace.SOCKETIO: ["socketio"],
        RedisNamespace.TECHNIQUE: ["technique"],
        RedisNamespace.KNOWLEDGE: ["knowledge"],
        RedisNamespace.BILLING: ["billing"],
        RedisNamespace.WEBHOOK: ["webhook"],
        RedisNamespace.SLA: ["sla"],
        RedisNamespace.TRAINING: ["training_data", "training:"],
        RedisNamespace.ANALYTICS: ["analytics"],
        RedisNamespace.PII: ["pii"],
        RedisNamespace.OTP: ["otp"],
        RedisNamespace.API_KEY: ["apikey"],
        RedisNamespace.LOCK: ["lock:"],
        RedisNamespace.GUARDRAILS: ["guardrails"],
        RedisNamespace.FRESHNESS: ["freshness"],
        RedisNamespace.MIGRATION: ["migration"],
        RedisNamespace.BRAND_VOICE: ["brand_voice"],
        RedisNamespace.COLLISION: ["ticket_viewing", "collision"],
        RedisNamespace.INJECTION_DEFENSE: ["injection_rate", "tenant_blocklist"],
    }

    for ns, keywords in namespace_keywords.items():
        for kw in keywords:
            if kw in key_lower:
                return ns

    return None


# ═══════════════════════════════════════════════════════════════════════
# ASYNC OPERATIONS (require Redis client)
# ═══════════════════════════════════════════════════════════════════════


async def cleanup_namespace(
    redis_client: Any,
    namespace: RedisNamespace,
    company_id: Optional[str] = None,
) -> int:
    """Clean up all keys in a namespace, optionally filtered by company_id.

    Args:
        redis_client: Async Redis client instance
        namespace: Namespace to clean up
        company_id: Optional company_id filter

    Returns:
        Number of keys deleted
    """
    try:
        # Build scan pattern
        if company_id:
            # New pattern: parwa:{ns}:{company_id}:*
            pattern = f"{NAMESPACE_PREFIX}:{namespace.value}:{company_id}:*"
        else:
            # All keys in this namespace
            pattern = f"{NAMESPACE_PREFIX}:{namespace.value}:*"

        keys = []
        async for key in redis_client.scan_iter(match=pattern, count=500):
            keys.append(key)

        # Also scan old pattern: parwa:{company_id}:{ns_segment}:*
        if company_id:
            old_pattern = f"{NAMESPACE_PREFIX}:{company_id}:{namespace.value}:*"
            async for key in redis_client.scan_iter(match=old_pattern, count=500):
                if key not in keys:
                    keys.append(key)

        if not keys:
            return 0

        deleted = await redis_client.delete(*keys)
        logger.info(
            "cleanup_namespace",
            namespace=namespace.value,
            company_id=company_id,
            keys_deleted=deleted,
        )
        return deleted

    except Exception as exc:
        logger.warning(
            "cleanup_namespace_failed",
            namespace=namespace.value,
            company_id=company_id,
            error=str(exc)[:200],
        )
        return 0


async def get_namespace_metrics(
    redis_client: Any,
    namespace: RedisNamespace,
    company_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get metrics for a namespace: key count, memory usage, TTL distribution.

    Args:
        redis_client: Async Redis client instance
        namespace: Namespace to query
        company_id: Optional company_id filter

    Returns:
        Dict with key_count, memory_estimate_bytes, ttl_distribution,
        oldest_key_age_seconds
    """
    try:
        if company_id:
            pattern = f"{NAMESPACE_PREFIX}:{namespace.value}:{company_id}:*"
        else:
            pattern = f"{NAMESPACE_PREFIX}:{namespace.value}:*"

        keys: List[str] = []
        async for key in redis_client.scan_iter(match=pattern, count=500):
            keys.append(key)

        if not keys:
            return {
                "namespace": namespace.value,
                "company_id": company_id,
                "key_count": 0,
                "memory_estimate_bytes": 0,
                "ttl_distribution": {},
                "sample_keys": [],
            }

        # Sample TTLs (up to 100 keys for performance)
        sample_keys = keys[:100]
        ttl_distribution: Dict[str, int] = {
            "no_ttl": 0,
            "under_1min": 0,
            "under_5min": 0,
            "under_1hr": 0,
            "under_1day": 0,
            "over_1day": 0,
        }

        total_memory = 0
        for key in sample_keys:
            try:
                ttl = await redis_client.ttl(key)
                mem = await redis_client.memory_usage(key) or 0
                total_memory += mem

                if ttl == -1:
                    ttl_distribution["no_ttl"] += 1
                elif ttl == -2:
                    pass  # Key doesn't exist
                elif ttl < 60:
                    ttl_distribution["under_1min"] += 1
                elif ttl < 300:
                    ttl_distribution["under_5min"] += 1
                elif ttl < 3600:
                    ttl_distribution["under_1hr"] += 1
                elif ttl < 86400:
                    ttl_distribution["under_1day"] += 1
                else:
                    ttl_distribution["over_1day"] += 1
            except Exception:
                ttl_distribution["no_ttl"] += 1

        # Scale memory estimate to full key count
        memory_scale = len(keys) / max(len(sample_keys), 1)
        estimated_memory = int(total_memory * memory_scale)

        return {
            "namespace": namespace.value,
            "company_id": company_id,
            "key_count": len(keys),
            "memory_estimate_bytes": estimated_memory,
            "ttl_distribution": ttl_distribution,
            "sample_keys": keys[:10],
        }

    except Exception as exc:
        logger.warning(
            "get_namespace_metrics_failed",
            namespace=namespace.value,
            company_id=company_id,
            error=str(exc)[:200],
        )
        return {
            "namespace": namespace.value,
            "company_id": company_id,
            "key_count": 0,
            "memory_estimate_bytes": 0,
            "ttl_distribution": {},
            "sample_keys": [],
            "error": str(exc)[:200],
        }


async def audit_all_keys(redis_client: Any) -> Dict[str, Any]:
    """Full audit of all Redis keys.

    Returns:
        - total_key_count: Total number of keys in Redis
        - keys_without_ttl: Count of keys with no expiry (potential leaks)
        - keys_by_namespace: Dict of namespace -> key count
        - orphaned_keys: List of keys not matching any known pattern
        - estimated_memory_bytes: Rough memory usage estimate
        - audit_timestamp: ISO-8601 UTC timestamp
    """
    try:
        # Get total key count
        total_key_count = await redis_client.dbsize()

        keys_by_namespace: Dict[str, int] = {}
        orphaned_keys: List[str] = []
        keys_without_ttl = 0
        total_memory = 0
        scanned = 0

        # Scan all keys
        async for key in redis_client.scan_iter(count=500):
            scanned += 1

            # Identify namespace
            ns = identify_namespace(key)

            # Keys without "parwa:" prefix are always orphaned
            # even if we can identify the namespace they belong to
            if not key.startswith("parwa:"):
                orphaned_keys.append(key)
                # Still record the namespace for reporting
                if ns is not None:
                    keys_by_namespace[f"orphaned:{ns.value}"] = (
                        keys_by_namespace.get(f"orphaned:{ns.value}", 0) + 1
                    )
            elif ns is not None:
                ns_name = ns.value
                keys_by_namespace[ns_name] = keys_by_namespace.get(ns_name, 0) + 1
            else:
                # It's a parwa key but we can't identify the namespace
                parts = key.split(":")
                if len(parts) >= 3:
                    ns_segment = parts[1] if parts[1] != "" else "unknown"
                    keys_by_namespace[f"unmapped:{ns_segment}"] = (
                        keys_by_namespace.get(f"unmapped:{ns_segment}", 0) + 1
                    )
                else:
                    orphaned_keys.append(key)

            # Check TTL (sample for performance)
            if scanned <= 500:
                try:
                    ttl = await redis_client.ttl(key)
                    if ttl == -1:
                        keys_without_ttl += 1
                except Exception:
                    pass

                # Memory sampling
                if scanned <= 100:
                    try:
                        mem = await redis_client.memory_usage(key) or 0
                        total_memory += mem
                    except Exception:
                        pass

        # Scale TTL count to full dataset
        if scanned > 0 and scanned > 500:
            ttl_scale = scanned / 500
            keys_without_ttl = int(keys_without_ttl * ttl_scale)

        # Scale memory estimate
        if scanned > 0 and scanned > 100:
            mem_scale = scanned / 100
            total_memory = int(total_memory * mem_scale)

        audit_result = {
            "total_key_count": total_key_count,
            "scanned_key_count": scanned,
            "keys_without_ttl": keys_without_ttl,
            "keys_by_namespace": keys_by_namespace,
            "orphaned_keys": orphaned_keys[:50],  # Cap at 50
            "orphaned_key_count": len(orphaned_keys),
            "estimated_memory_bytes": total_memory,
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "redis_key_audit_complete",
            total_keys=total_key_count,
            scanned_keys=scanned,
            keys_without_ttl=keys_without_ttl,
            orphaned_keys=len(orphaned_keys),
            namespaces_found=len(keys_by_namespace),
        )

        return audit_result

    except Exception as exc:
        logger.warning(
            "redis_key_audit_failed",
            error=str(exc)[:200],
        )
        return {
            "total_key_count": 0,
            "scanned_key_count": 0,
            "keys_without_ttl": 0,
            "keys_by_namespace": {},
            "orphaned_keys": [],
            "orphaned_key_count": 0,
            "estimated_memory_bytes": 0,
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc)[:200],
        }


async def fix_missing_ttls(
    redis_client: Any,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Apply default TTLs to keys that are missing them.

    Scans all keys and applies the namespace-appropriate TTL to any key
    that has no expiry set (TTL = -1).

    Args:
        redis_client: Async Redis client instance
        dry_run: If True, only report what would be changed

    Returns:
        Dict with keys_fixed count and details
    """
    try:
        keys_fixed = 0
        keys_scanned = 0
        details: List[Dict[str, Any]] = []

        async for key in redis_client.scan_iter(count=500):
            keys_scanned += 1
            try:
                ttl = await redis_client.ttl(key)
                if ttl != -1:
                    continue  # Already has TTL

                # Key has no TTL — determine appropriate default
                ns = identify_namespace(key)
                if ns is not None:
                    default_ttl = NAMESPACE_TTL_DEFAULTS.get(ns, 300)
                else:
                    # Unknown namespace — use safe default of 1 hour
                    default_ttl = 3600

                if dry_run:
                    details.append({
                        "key": key[:100],
                        "namespace": ns.value if ns else "unknown",
                        "would_apply_ttl": default_ttl,
                    })
                else:
                    await redis_client.expire(key, default_ttl)
                    details.append({
                        "key": key[:100],
                        "namespace": ns.value if ns else "unknown",
                        "applied_ttl": default_ttl,
                    })

                keys_fixed += 1

                # Cap details list
                if len(details) >= 200:
                    break

            except Exception:
                continue

        result = {
            "dry_run": dry_run,
            "keys_scanned": keys_scanned,
            "keys_fixed": keys_fixed,
            "details": details[:50],  # Cap at 50
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "fix_missing_ttls_complete",
            dry_run=dry_run,
            keys_scanned=keys_scanned,
            keys_fixed=keys_fixed,
        )

        return result

    except Exception as exc:
        logger.warning(
            "fix_missing_ttls_failed",
            dry_run=dry_run,
            error=str(exc)[:200],
        )
        return {
            "dry_run": dry_run,
            "keys_scanned": 0,
            "keys_fixed": 0,
            "details": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc)[:200],
        }


async def startup_audit(redis_client: Any) -> None:
    """Run a startup audit and log results.

    Called during application startup to identify orphaned keys
    and keys missing TTLs.

    Args:
        redis_client: Async Redis client instance
    """
    try:
        logger.info("redis_startup_audit_begin")

        # Full audit
        audit = await audit_all_keys(redis_client)

        logger.info(
            "redis_startup_audit_results",
            total_keys=audit.get("total_key_count", 0),
            keys_without_ttl=audit.get("keys_without_ttl", 0),
            orphaned_keys=audit.get("orphaned_key_count", 0),
            namespaces=audit.get("keys_by_namespace", {}),
        )

        # Alert on orphans
        orphaned = audit.get("orphaned_keys", [])
        if orphaned:
            logger.warning(
                "redis_orphaned_keys_detected",
                count=len(orphaned),
                sample=orphaned[:10],
            )

        # Alert on missing TTLs
        keys_no_ttl = audit.get("keys_without_ttl", 0)
        if keys_no_ttl > 0:
            logger.warning(
                "redis_keys_missing_ttl",
                count=keys_no_ttl,
                recommendation="Run fix_missing_ttls(dry_run=False) to apply defaults",
            )

    except Exception as exc:
        # BC-008: Startup audit failure must not crash the app
        logger.warning(
            "redis_startup_audit_failed",
            error=str(exc)[:200],
        )


# ═══════════════════════════════════════════════════════════════════════
# CONVENIENCE: NAMESPACED CACHE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════


async def namespaced_cache_get(
    company_id: str,
    namespace: RedisNamespace,
    key: str,
    default: Any = None,
) -> Any:
    """Get a cached value using standardized namespaced key.

    Args:
        company_id: Tenant identifier (BC-001)
        namespace: Cache namespace
        key: Cache key
        default: Default value if not found

    Returns:
        Cached value or default
    """
    import json

    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        redis_key = build_key(namespace, company_id, key)
        value = await redis.get(redis_key)

        if value is not None:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return default
    except Exception:
        return default


async def namespaced_cache_set(
    company_id: str,
    namespace: RedisNamespace,
    key: str,
    value: Any,
    ttl_override: Optional[int] = None,
) -> bool:
    """Set a cached value using standardized namespaced key with auto-TTL.

    Args:
        company_id: Tenant identifier (BC-001)
        namespace: Cache namespace
        key: Cache key
        value: Value to cache (JSON-serialized if not string)
        ttl_override: Optional TTL override in seconds

    Returns:
        True if set succeeded, False otherwise
    """
    import json

    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        redis_key = build_key(namespace, company_id, key)
        ttl = get_ttl(namespace, ttl_override)

        serialized = value if isinstance(value, str) else json.dumps(value)
        await redis.set(redis_key, serialized, ex=ttl)
        return True
    except Exception:
        return False


async def namespaced_cache_delete(
    company_id: str,
    namespace: RedisNamespace,
    key: str,
) -> bool:
    """Delete a cached value using standardized namespaced key.

    Args:
        company_id: Tenant identifier (BC-001)
        namespace: Cache namespace
        key: Cache key

    Returns:
        True if delete succeeded, False otherwise
    """
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        redis_key = build_key(namespace, company_id, key)
        await redis.delete(redis_key)
        return True
    except Exception:
        return False
