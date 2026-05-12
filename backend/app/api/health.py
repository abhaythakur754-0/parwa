"""
PARWA Health API Routes (Day 21, BC-012)

Provides /health, /ready, /health/detail, /metrics endpoints.

All endpoints are publicly accessible (no auth required).
BC-012: No company data is exposed in any health response.
BC-012: No tenant-specific counts in metrics.
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from app.core.health import (
    HealthStatus,
    run_health_checks,
    run_readiness_check,
    clear_health_cache,
)
from app.core.metrics import registry, record_http_request
from app.logger import get_logger

logger = get_logger("health_api")

router = APIRouter(tags=["Health"])

# Track app start time for uptime calculation
_start_time = time.monotonic()
APP_VERSION = "0.3.0"


def _get_uptime_seconds() -> float:
    """Get application uptime in seconds."""
    return round(time.monotonic() - _start_time, 2)


def _subsystem_to_dict(sub) -> dict:
    """Convert SubsystemHealth to JSON-safe dict."""
    result = {
        "status": sub.status,
        "latency_ms": sub.latency_ms,
    }
    if sub.details:
        result["details"] = sub.details
    if sub.error:
        result["error"] = sub.error
    return result


# ── Phase 6: Circuit Breaker & Self-Healing Helpers ────────────────


def _get_circuit_breaker_summary() -> dict:
    """Get circuit breaker health summary for /health endpoint.

    BC-008: Returns empty dict on failure (never crashes).
    BC-012: No company data exposed.
    """
    try:
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
        )
        manager = get_circuit_breaker_manager()
        return manager.get_health_summary()
    except Exception:
        return {"status": "unknown", "total_circuits": 0}


def _get_circuit_breaker_detail() -> dict:
    """Get detailed circuit breaker states for /health/detail endpoint.

    BC-008: Returns empty dict on failure (never crashes).
    BC-012: No company data exposed.
    """
    try:
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
        )
        manager = get_circuit_breaker_manager()
        return manager.get_all_states()
    except Exception:
        return {}


def _get_self_healing_status() -> dict:
    """Get self-healing service status for /health endpoint.

    BC-008: Returns empty dict on failure (never crashes).
    BC-012: No company data exposed.
    """
    try:
        from app.services.self_healing_service import (
            get_self_healing_service,
        )
        service = get_self_healing_service()
        return service.get_status()
    except Exception:
        return {"status": "unknown"}


def _get_self_healing_detail() -> dict:
    """Get self-healing detail with recent actions for /health/detail.

    BC-008: Returns empty dict on failure (never crashes).
    BC-012: No company data exposed.
    """
    try:
        from app.services.self_healing_service import (
            get_self_healing_service,
        )
        service = get_self_healing_service()
        metrics = service.get_healing_metrics()
        recent_history = service.get_healing_history(limit=10)
        return {
            "metrics": metrics,
            "recent_actions": recent_history,
        }
    except Exception:
        return {"metrics": {}, "recent_actions": []}


def _get_sentry_status() -> dict:
    """Get Sentry monitoring status for /health endpoint.

    BC-008: Returns empty dict on failure (never crashes).
    BC-012: No company data or DSN exposed.
    """
    try:
        from app.core.sentry import get_sentry_status
        return get_sentry_status()
    except Exception:
        return {"initialized": False, "status": "unknown"}


@router.get("/health")
async def health_endpoint():
    """Liveness probe — returns aggregate health status.

    BC-012: Returns 200 with status, version, timestamp, and
    subsystem summary. Results cached for 10s to prevent bottleneck.
    No company data exposed.
    """
    start = time.monotonic()
    result = await run_health_checks(use_cache=True)

    subsystems_summary = {}
    for name, sub in result.subsystems.items():
        subsystems_summary[name] = {"status": sub.status}

    duration = round((time.monotonic() - start) * 1000, 2)

    # Phase 6: Circuit breaker health summary
    circuit_breaker_health = _get_circuit_breaker_summary()

    # Phase 6: Self-healing service status
    self_healing_status = _get_self_healing_status()

    # Phase 6: Sentry monitoring status
    sentry_status = _get_sentry_status()

    response_data = {
        "status": result.status,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "version": APP_VERSION,
        "uptime_seconds": _get_uptime_seconds(),
        "subsystems": subsystems_summary,
        "checks_total": result.checks_total,
        "checks_healthy": result.checks_healthy,
        "checks_degraded": result.checks_degraded,
        "checks_unhealthy": result.checks_unhealthy,
        "cached": result.cached,
        "circuit_breakers": circuit_breaker_health,
        "self_healing": self_healing_status,
        "sentry": sentry_status,
    }

    # Record health check duration in metrics
    record_http_request("GET", "/health", 200, duration / 1000)

    return response_data


@router.get("/health/detail")
async def health_detail_endpoint():
    """Detailed health probe — full subsystem breakdown.

    BC-012: Returns full subsystem details including latencies,
    pool stats, queue depths, and error messages.
    No company data exposed.
    """
    start = time.monotonic()

    # Force fresh check (bypass cache) for detail endpoint
    clear_health_cache()
    result = await run_health_checks(use_cache=False)

    subsystems_detail = {}
    for name, sub in result.subsystems.items():
        subsystems_detail[name] = _subsystem_to_dict(sub)

    duration = round((time.monotonic() - start) * 1000, 2)

    # Phase 6: Detailed circuit breaker states
    circuit_breaker_states = _get_circuit_breaker_detail()

    # Phase 6: Self-healing service detail with recent actions
    self_healing_detail = _get_self_healing_detail()

    # Phase 6: Sentry monitoring detail
    sentry_detail = _get_sentry_status()

    response_data = {
        "status": result.status,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "version": APP_VERSION,
        "uptime_seconds": _get_uptime_seconds(),
        "subsystems": subsystems_detail,
        "checks_total": result.checks_total,
        "checks_healthy": result.checks_healthy,
        "checks_degraded": result.checks_degraded,
        "checks_unhealthy": result.checks_unhealthy,
        "circuit_breakers": circuit_breaker_states,
        "self_healing": self_healing_detail,
        "sentry": sentry_detail,
    }

    record_http_request("GET", "/health/detail", 200, duration / 1000)

    return response_data


@router.get("/ready")
async def readiness_endpoint():
    """Readiness probe — 200 if ALL critical subsystems healthy.

    BC-012: Returns 503 if any critical dependency (DB, Redis) is
    unhealthy. Non-critical subsystems (Celery, external services)
    don't affect readiness.
    """
    start = time.monotonic()
    readiness = await run_readiness_check()
    duration = round((time.monotonic() - start) * 1000, 2)

    if readiness["ready"]:
        record_http_request("GET", "/ready", 200, duration / 1000)
        return {
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "uptime_seconds": _get_uptime_seconds(),
            "subsystems": readiness["subsystems"],
        }
    else:
        record_http_request(
            "GET", "/ready", 503, duration / 1000,
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "timestamp": (
                    datetime.now(timezone.utc).isoformat() + "Z"
                ),
                "uptime_seconds": _get_uptime_seconds(),
                "subsystems": readiness["subsystems"],
            },
        )


@router.get("/metrics")
async def metrics_endpoint(
    format: Optional[str] = Query(
        None,
        description="Output format: 'prometheus' (default) or 'json'",
    ),
):
    """Prometheus metrics endpoint.

    BC-012: Returns metrics in Prometheus text format.
    No tenant-specific data exposed (loophole check).
    """
    start = time.monotonic()

    # Gather health status for up/down gauges
    try:
        health = await run_health_checks(use_cache=True)
        subsystem_up = {}
        for name, sub in health.subsystems.items():
            subsystem_up[name] = (
                1 if sub.status == HealthStatus.HEALTHY.value else 0
            )
    except Exception:
        subsystem_up = {}

    # Build Prometheus output
    lines = []

    # Build info (L-13: environment label removed to avoid info leakage)
    lines.append(
        f'# HELP parwa_build_info PARWA build information\n'
        f'# TYPE parwa_build_info gauge\n'
        f'parwa_build_info{{version="{APP_VERSION}"}} 1'
    )

    # Uptime
    uptime = _get_uptime_seconds()
    lines.append(
        f'\n# HELP parwa_uptime_seconds PARWA uptime in seconds\n'
        f'# TYPE parwa_uptime_seconds gauge\n'
        f'parwa_uptime_seconds {uptime}'
    )

    # Health status for each subsystem
    lines.append(
        '\n# HELP parwa_subsystem_up '
        'Subsystem health (1=healthy, 0=unhealthy)\n'
        '# TYPE parwa_subsystem_up gauge'
    )
    for name, up in subsystem_up.items():
        lines.append(f'parwa_subsystem_up{{subsystem="{name}"}} {up}')

    # Health summary
    lines.append(
        '\n# HELP parwa_health_check '
        'Aggregate health (1=healthy, 0=unhealthy)\n'
        '# TYPE parwa_health_check gauge'
    )
    if health:
        aggregate = (
            1 if health.status == HealthStatus.HEALTHY.value else 0
        )
        lines.append(f'parwa_health_check {{status="aggregate"}} {aggregate}')
        lines.append(
            f'parwa_health_check '
            f'{{status="checks_total"}} {health.checks_total}'
        )
        lines.append(
            f'parwa_health_check '
            f'{{status="checks_healthy"}} {health.checks_healthy}'
        )
        lines.append(
            f'parwa_health_check '
            f'{{status="checks_degraded"}} {health.checks_degraded}'
        )
        lines.append(
            f'parwa_health_check '
            f'{{status="checks_unhealthy"}} {health.checks_unhealthy}'
        )

    # Registry metrics (HTTP, Celery, DB, Redis)
    registry_output = registry.render_all()
    if registry_output:
        lines.append(f"\n{registry_output}")

    # Phase 6: Circuit breaker metrics
    try:
        from app.core.circuit_breaker_manager import (
            get_circuit_breaker_manager,
        )
        cb_manager = get_circuit_breaker_manager()
        cb_metrics = cb_manager.get_metrics()
        metrics_text = cb_metrics.get("metrics_text", "")
        if metrics_text:
            lines.append(f"\n{metrics_text}")
    except Exception:
        pass

    content = "\n".join(lines)
    duration = round((time.monotonic() - start) * 1000, 2)

    record_http_request("GET", "/metrics", 200, duration / 1000)

    if format == "json":
        return {"metrics_text": content, "format": "prometheus"}

    return PlainTextResponse(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
