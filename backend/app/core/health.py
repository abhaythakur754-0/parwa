"""
PARWA Health Check Orchestrator (Day 21, BC-012)

Aggregates health checks for all subsystems with:
- 9 subsystem checks (PostgreSQL, Redis, Celery, Socket.io,
  Paddle, Brevo, Twilio, Disk)
- Dependency graph: if a critical dep is down,
  dependents show "degraded"
- Three-state status: healthy / degraded / unhealthy
- 10-second cache to prevent health checks from becoming a bottleneck
- No company data exposed in health responses (BC-012)
- External checks are connectivity-only probes (never send real data)
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("health")


class HealthStatus(str, Enum):
    """Health status levels for subsystem checks."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class SubsystemHealth:
    """Health result for a single subsystem.

    Attributes:
        name: Subsystem identifier (e.g., 'postgresql', 'redis').
        status: Current health status (healthy/degraded/unhealthy).
        latency_ms: Response latency in milliseconds.
        details: Optional dict with subsystem-specific metrics.
        error: Error message if check failed.
        is_critical: Whether this subsystem is required for readiness.
    """
    name: str
    status: str = HealthStatus.UNKNOWN.value
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    is_critical: bool = True


@dataclass
class HealthCheckResult:
    """Aggregate health check result for all subsystems.

    Attributes:
        status: Overall system status (healthy if all critical healthy,
                degraded if any non-critical or dependent unhealthy,
                unhealthy if any critical unhealthy).
        subsystems: Dict of subsystem name -> SubsystemHealth.
        checks_total: Total number of subsystem checks.
        checks_healthy: Number of healthy checks.
        checks_degraded: Number of degraded checks.
        checks_unhealthy: Number of unhealthy checks.
        cached: Whether this result was served from cache.
    """
    status: str = HealthStatus.UNKNOWN.value
    subsystems: Dict[str, SubsystemHealth] = field(
        default_factory=dict,
    )
    checks_total: int = 0
    checks_healthy: int = 0
    checks_degraded: int = 0
    checks_unhealthy: int = 0
    cached: bool = False


# ── Cache (10-second TTL per loophole check requirement) ───────────

_health_cache: Optional[HealthCheckResult] = None
_health_cache_timestamp: float = 0.0
_HEALTH_CACHE_TTL = 10.0  # seconds


def _get_cached_result() -> Optional[HealthCheckResult]:
    """Return cached health result if still valid (within TTL)."""
    now = time.monotonic()
    if (
        _health_cache is not None
        and (now - _health_cache_timestamp) < _HEALTH_CACHE_TTL
    ):
        cached = HealthCheckResult(
            status=_health_cache.status,
            subsystems=_health_cache.subsystems,
            checks_total=_health_cache.checks_total,
            checks_healthy=_health_cache.checks_healthy,
            checks_degraded=_health_cache.checks_degraded,
            checks_unhealthy=_health_cache.checks_unhealthy,
            cached=True,
        )
        return cached
    return None


def _set_cache(result: HealthCheckResult) -> None:
    """Store health result in cache with current timestamp."""
    global _health_cache, _health_cache_timestamp
    _health_cache = result
    _health_cache_timestamp = time.monotonic()


def clear_health_cache() -> None:
    """Clear the health check cache. Used in tests."""
    global _health_cache, _health_cache_timestamp
    _health_cache = None
    _health_cache_timestamp = 0.0


# ── Dependency Graph ───────────────────────────────────────────────

# Maps subsystem -> list of subsystems it depends on.
# If a dependency is unhealthy, dependents are forced to "degraded".
DEPENDENCY_GRAPH: Dict[str, List[str]] = {
    "celery": ["postgresql", "redis"],
    "celery_queues": ["celery"],
    "socketio": ["redis"],
    # External services have no internal dependencies
    "external_paddle": [],
    "external_brevo": [],
    "external_twilio": [],
    "disk_space": [],
}


# ── Individual Subsystem Checks ────────────────────────────────────


async def check_postgresql() -> SubsystemHealth:
    """Check PostgreSQL connectivity and pool stats.

    Returns healthy if SELECT 1 succeeds and pool < 80% used.
    Returns degraded if pool > 80% used.
    Returns unhealthy if connection fails.
    """
    start = time.monotonic()
    try:
        from database.base import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))

        latency = round((time.monotonic() - start) * 1000, 2)

        # Pool stats
        pool_used = 0
        pool_max = 0
        try:
            pool = engine.pool
            pool_used = pool.checkedout()
            pool_max = pool.size()
        except Exception:
            pass

        pool_pct = (pool_used / pool_max * 100) if pool_max > 0 else 0
        status = HealthStatus.HEALTHY.value
        if pool_pct > 80:
            status = HealthStatus.DEGRADED.value

        return SubsystemHealth(
            name="postgresql",
            status=status,
            latency_ms=latency,
            details={
                "pool_used": pool_used,
                "pool_max": pool_max,
                "pool_percent": round(pool_pct, 1),
            },
            is_critical=True,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name="postgresql",
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error=str(exc)[:200],
            is_critical=True,
        )


async def check_redis() -> SubsystemHealth:
    """Check Redis connectivity and memory usage.

    Returns healthy if PING succeeds and memory < 80% max.
    Returns degraded if memory > 80%.
    Returns unhealthy if PING fails.
    """
    start = time.monotonic()
    try:
        from app.core.redis import get_redis
        client = await get_redis()
        await client.ping()

        latency = round((time.monotonic() - start) * 1000, 2)

        # Memory info
        memory_used_mb = 0
        memory_max_mb = 0
        try:
            info = await client.info("memory")
            memory_used_mb = round(
                info.get("used_memory", 0) / (1024 * 1024), 2,
            )
            maxmemory = info.get("maxmemory", 0)
            if maxmemory > 0:
                memory_max_mb = round(
                    maxmemory / (1024 * 1024), 2,
                )
        except Exception:
            pass

        mem_pct = 0.0
        if memory_max_mb > 0:
            mem_pct = memory_used_mb / memory_max_mb * 100

        status = HealthStatus.HEALTHY.value
        if mem_pct > 80:
            status = HealthStatus.DEGRADED.value

        details: Dict[str, Any] = {
            "memory_used_mb": memory_used_mb,
        }
        if memory_max_mb > 0:
            details["memory_max_mb"] = memory_max_mb
            details["memory_percent"] = round(mem_pct, 1)

        return SubsystemHealth(
            name="redis",
            status=status,
            latency_ms=latency,
            details=details,
            is_critical=True,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name="redis",
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error=str(exc)[:200],
            is_critical=True,
        )


async def check_celery() -> SubsystemHealth:
    """Check Celery broker connectivity and worker count.

    Returns healthy if broker reachable and workers > 0.
    Returns degraded if no workers (queue > 1000 also degraded).
    Returns unhealthy if broker unreachable.
    """
    start = time.monotonic()
    try:
        from app.tasks.celery_health import (
            celery_health_check,
            get_active_workers,
        )
        broker_info = await celery_health_check()
        latency = round((time.monotonic() - start) * 1000, 2)

        if broker_info["status"] != "healthy":
            return SubsystemHealth(
                name="celery",
                status=HealthStatus.UNHEALTHY.value,
                latency_ms=latency,
                error=broker_info.get("error", "broker unreachable"),
                is_critical=False,
            )

        workers_info = await get_active_workers()
        worker_count = workers_info.get("worker_count", 0)

        status = HealthStatus.HEALTHY.value
        if worker_count == 0:
            status = HealthStatus.DEGRADED.value

        return SubsystemHealth(
            name="celery",
            status=status,
            latency_ms=latency,
            details={
                "workers": worker_count,
                "broker_latency_ms": broker_info.get("latency_ms", 0),
            },
            is_critical=False,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name="celery",
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error=str(exc)[:200],
            is_critical=False,
        )


async def check_celery_queues() -> SubsystemHealth:
    """Check per-queue depths for all 7 defined Celery queues.

    Queues: default, ai_heavy, ai_light, email, webhook, analytics, training.
    Returns healthy if all queues < 500.
    Returns degraded if any queue > 500.
    Returns unhealthy if any queue > 5000.
    """
    start = time.monotonic()
    queue_names = [
        "default", "ai_heavy", "ai_light", "email",
        "webhook", "analytics", "training",
    ]

    try:
        from app.tasks.celery_app import app as celery_app
        inspect = celery_app.control.inspect(timeout=3)

        queue_depths: Dict[str, int] = {q: 0 for q in queue_names}
        total_depth = 0

        try:
            # Get reserved + active task counts per queue
            reserved = inspect.reserved() or {}
            active = inspect.active() or {}
            for worker_name, tasks in reserved.items():
                for task in (tasks or []):
                    q_name = task.get("delivery_info", {}).get(
                        "routing_key", "default"
                    )
                    if q_name in queue_depths:
                        queue_depths[q_name] += 1
                    total_depth += 1
            for worker_name, tasks in active.items():
                for task in (tasks or []):
                    q_name = task.get("delivery_info", {}).get(
                        "routing_key", "default"
                    )
                    if q_name in queue_depths:
                        queue_depths[q_name] += 1
                    total_depth += 1
        except Exception:
            pass

        latency = round((time.monotonic() - start) * 1000, 2)

        max_depth = max(queue_depths.values()) if queue_depths else 0
        status = HealthStatus.HEALTHY.value
        if max_depth > 5000:
            status = HealthStatus.UNHEALTHY.value
        elif (max_depth > 500 or total_depth > 1000):
            status = HealthStatus.DEGRADED.value

        return SubsystemHealth(
            name="celery_queues",
            status=status,
            latency_ms=latency,
            details={
                "queues": queue_depths,
                "total_depth": total_depth,
            },
            is_critical=False,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name="celery_queues",
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error=str(exc)[:200],
            is_critical=False,
        )


async def check_socketio() -> SubsystemHealth:
    """Check Socket.io server status.

    Returns healthy if server is accessible.
    Returns unhealthy if server check fails.
    """
    start = time.monotonic()
    try:
        # Check if socketio module is available
        from app.core.socketio import get_socketio_manager

        manager = get_socketio_manager()
        connected = manager.get_connected_count() if manager else 0

        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name="socketio",
            status=HealthStatus.HEALTHY.value,
            latency_ms=latency,
            details={
                "connected_clients": connected,
            },
            is_critical=False,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name="socketio",
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error=str(exc)[:200],
            is_critical=False,
        )


async def check_external_service(
    name: str, url: str,
    degraded_timeout: float = 2.0,
    unhealthy_timeout: float = 5.0,
) -> SubsystemHealth:
    """Check external service connectivity (HTTPS probe only).

    NEVER sends real data -- only a HEAD/GET to the root URL to verify
    connectivity and measure latency. This is a loophole protection:
    external health checks must be pure connectivity probes.

    Args:
        name: Subsystem name (e.g., 'external_paddle').
        url: Base URL of the external service.
        degraded_timeout: Latency threshold for degraded state.
        unhealthy_timeout: Latency threshold for unhealthy state.

    Returns:
        SubsystemHealth with connectivity status and latency.
    """
    start = time.monotonic()
    try:
        import aiohttp

        # Use a very short timeout — we only care about connectivity
        timeout = aiohttp.ClientTimeout(total=unhealthy_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # HEAD request — no data sent, just connectivity check
            async with session.head(url, allow_redirects=False):
                # Any response (even 4xx) means the service is reachable
                latency = round((time.monotonic() - start) * 1000, 2)

                status = HealthStatus.HEALTHY.value
                if latency > unhealthy_timeout * 1000:
                    status = HealthStatus.UNHEALTHY.value
                elif latency > degraded_timeout * 1000:
                    status = HealthStatus.DEGRADED.value

                return SubsystemHealth(
                    name=name,
                    status=status,
                    latency_ms=latency,
                    is_critical=False,
                )
    except asyncio.TimeoutError:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name=name,
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error="connection timeout",
            is_critical=False,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name=name,
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error=str(exc)[:200],
            is_critical=False,
        )


async def check_disk_space() -> SubsystemHealth:
    """Check disk space using os.statvfs().

    Returns healthy if > 20% free.
    Returns degraded if < 20% free.
    Returns unhealthy if < 5% free.
    """
    start = time.monotonic()
    try:
        stat = os.statvfs("/")
        total_blocks = stat.f_blocks
        free_blocks = stat.f_bavail
        block_size = stat.f_frsize

        total_gb = round(
            (total_blocks * block_size) / (1024 ** 3), 2,
        )
        free_gb = round(
            (free_blocks * block_size) / (1024 ** 3), 2,
        )
        free_pct = round(
            (free_blocks / total_blocks) * 100, 2,
        ) if total_blocks > 0 else 0

        latency = round((time.monotonic() - start) * 1000, 2)

        status = HealthStatus.HEALTHY.value
        if free_pct < 5:
            status = HealthStatus.UNHEALTHY.value
        elif free_pct < 20:
            status = HealthStatus.DEGRADED.value

        return SubsystemHealth(
            name="disk_space",
            status=status,
            latency_ms=latency,
            details={
                "total_gb": total_gb,
                "free_gb": free_gb,
                "free_percent": free_pct,
            },
            is_critical=False,
        )
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return SubsystemHealth(
            name="disk_space",
            status=HealthStatus.UNHEALTHY.value,
            latency_ms=latency,
            error=str(exc)[:200],
            is_critical=False,
        )


# ── Orchestrator ───────────────────────────────────────────────────

# Registry of all subsystem check functions
_CHECK_REGISTRY: Dict[str, Callable] = {
    "postgresql": check_postgresql,
    "redis": check_redis,
    "celery": check_celery,
    "celery_queues": check_celery_queues,
    "socketio": check_socketio,
    "disk_space": check_disk_space,
}


async def run_health_checks(
    use_cache: bool = True,
    include_external: bool = True,
    external_urls: Optional[Dict[str, str]] = None,
) -> HealthCheckResult:
    """Run all subsystem health checks and aggregate results.

    Applies dependency graph: if a dependency is unhealthy,
    dependent subsystems are forced to "degraded".

    Results are cached for 10 seconds to prevent health endpoint
    from becoming a bottleneck (loophole check requirement).

    Args:
        use_cache: Whether to use cached results (default True).
        include_external: Whether to check external services (default True).
        external_urls: Override external service URLs for testing.

    Returns:
        HealthCheckResult with aggregate status and all subsystem details.
    """
    # Check cache first
    if use_cache:
        cached = _get_cached_result()
        if cached is not None:
            return cached

    subsystems: Dict[str, SubsystemHealth] = {}
    tasks = []

    # Schedule all internal checks concurrently
    for name, check_fn in _CHECK_REGISTRY.items():
        tasks.append((name, check_fn()))

    # Schedule external checks concurrently
    ext_urls = external_urls or {}
    if include_external:
        if not ext_urls:
            try:
                from app.config import get_settings
                get_settings()  # noqa: F841 — verify config is valid
                ext_urls = {
                    "external_paddle": "https://vendors.paddle.com",
                    "external_brevo": "https://api.brevo.com",
                    "external_twilio": "https://api.twilio.com",
                }
            except Exception:
                ext_urls = {
                    "external_paddle": "https://vendors.paddle.com",
                    "external_brevo": "https://api.brevo.com",
                    "external_twilio": "https://api.twilio.com",
                }

        for name, url in ext_urls.items():
            tasks.append((
                name,
                check_external_service(name, url),
            ))

    # Await all checks concurrently
    for name, coro in tasks:
        try:
            result = await asyncio.wait_for(coro, timeout=10.0)
            subsystems[name] = result
        except asyncio.TimeoutError:
            subsystems[name] = SubsystemHealth(
                name=name,
                status=HealthStatus.UNHEALTHY.value,
                error="check timed out",
                is_critical=False,
            )
        except Exception as exc:
            logger.warning(
                "health_check_error",
                extra={"subsystem": name, "error": str(exc)},
            )
            subsystems[name] = SubsystemHealth(
                name=name,
                status=HealthStatus.UNHEALTHY.value,
                error="check failed",
                is_critical=False,
            )

    # Apply dependency graph
    for name, deps in DEPENDENCY_GRAPH.items():
        if name not in subsystems:
            continue
        current = subsystems[name]
        if current.status == HealthStatus.UNHEALTHY.value:
            continue

        # Check if any dependency is unhealthy
        for dep in deps:
            dep_health = subsystems.get(dep)
            if (dep_health and
                    dep_health.status == HealthStatus.UNHEALTHY.value):
                # Force dependent to degraded (not unhealthy — the
                # subsystem itself may be fine, just its dependency is down)
                subsystems[name] = SubsystemHealth(
                    name=current.name,
                    status=HealthStatus.DEGRADED.value,
                    latency_ms=current.latency_ms,
                    details=current.details,
                    error=(
                        f"dependency '{dep}' is unhealthy"
                    ),
                    is_critical=current.is_critical,
                )
                break

    # Calculate aggregate status
    healthy = 0
    degraded = 0
    unhealthy = 0
    critical_unhealthy = False

    for sub in subsystems.values():
        if sub.status == HealthStatus.HEALTHY.value:
            healthy += 1
        elif sub.status == HealthStatus.DEGRADED.value:
            degraded += 1
        else:
            unhealthy += 1
            if sub.is_critical:
                critical_unhealthy = True

    total = len(subsystems)

    # Overall status determination
    if critical_unhealthy or unhealthy > 0:
        overall = HealthStatus.UNHEALTHY.value
    elif degraded > 0:
        overall = HealthStatus.DEGRADED.value
    else:
        overall = HealthStatus.HEALTHY.value

    # Special case: no critical subsystems unhealthy = degraded, not unhealthy
    if not critical_unhealthy and unhealthy > 0:
        overall = HealthStatus.DEGRADED.value

    result = HealthCheckResult(
        status=overall,
        subsystems=subsystems,
        checks_total=total,
        checks_healthy=healthy,
        checks_degraded=degraded,
        checks_unhealthy=unhealthy,
    )

    # Cache the result
    _set_cache(result)

    return result


async def run_readiness_check() -> Dict[str, Any]:
    """Run readiness check -- only critical subsystems matter.

    Returns 200-ready if ALL critical subsystems are healthy.
    Returns 503-not_ready if any critical subsystem is unhealthy.

    Returns:
        Dict with 'ready' bool and 'subsystems' breakdown.
    """
    result = await run_health_checks(use_cache=True)

    all_critical_healthy = True
    subsystem_breakdown = {}

    for name, sub in result.subsystems.items():
        is_ready = sub.status == HealthStatus.HEALTHY.value
        subsystem_breakdown[name] = {
            "status": "ready" if is_ready else "unhealthy",
        }
        if sub.is_critical and not is_ready:
            all_critical_healthy = False

    return {
        "ready": all_critical_healthy,
        "subsystems": subsystem_breakdown,
    }
