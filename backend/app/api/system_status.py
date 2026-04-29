"""
PARWA System Status API (F-088)

Provides /api/system/status endpoint for frontend health strip.
Wraps the core health check system and reformats for the dashboard.

The frontend SystemHealthStrip.tsx polls this endpoint every 30s.
"""

from fastapi import APIRouter
from app.logger import get_logger

logger = get_logger("system_status_api")

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status():
    """Get system status formatted for frontend dashboard health strip.

    Returns per-service health status with latency information.
    Maps backend subsystem names to frontend-expected service keys.

    Frontend expects:
    {
        "status": "healthy" | "degraded" | "down",
        "services": {
            "llm": {"status": "healthy"},
            "redis": {"status": "healthy", "latency_ms": 2},
            "postgres": {"status": "healthy", "latency_ms": 8},
            "email": {"status": "healthy"},
            "sms": {"status": "healthy"},
            "chat": {"status": "healthy"},
            "voice": {"status": "healthy"},
            "celery": {"status": "healthy", "latency_ms": 12},
            "socketio": {"status": "healthy"},
        },
        "message": "All systems operational"
    }
    """
    try:
        from app.core.health import run_health_checks, HealthStatus

        result = await run_health_checks(use_cache=True)

        # Map frontend service keys to backend subsystem names.
        # If a backend subsystem is not monitored, we default to healthy.
        service_map = {
            "llm": None,  # No dedicated health check
            "postgres": "postgresql",
            "redis": "redis",
            "email": "external_brevo",
            "sms": "external_twilio",
            "chat": None,  # No dedicated health check
            "voice": None,  # No dedicated health check
            "celery": "celery",
            "socketio": "socketio",
        }

        services = {}
        any_degraded = False
        any_down = False

        for frontend_key, backend_key in service_map.items():
            if backend_key:
                sub = result.subsystems.get(backend_key)
                if sub:
                    svc: dict = {"status": sub.status}
                    if sub.latency_ms is not None:
                        svc["latency_ms"] = sub.latency_ms
                    services[frontend_key] = svc

                    if sub.status not in (
                        HealthStatus.HEALTHY.value,
                        HealthStatus.HEALTHY.value,
                    ):
                        any_degraded = True
                        if sub.status == HealthStatus.UNHEALTHY.value:
                            any_down = True
                else:
                    # Backend subsystem not found — default healthy
                    services[frontend_key] = {"status": "healthy"}
            else:
                # Service not monitored by health system — assume healthy
                services[frontend_key] = {"status": "healthy"}

        if any_down:
            overall = "down"
            message = "System issues detected"
        elif any_degraded:
            overall = "degraded"
            message = "System degraded"
        else:
            overall = "healthy"
            message = "All systems operational"

        return {
            "status": overall,
            "services": services,
            "message": message,
        }

    except Exception as exc:
        logger.error("system_status_error", error=str(exc))
        return {
            "status": "degraded",
            "services": {},
            "message": "Unable to check system status",
        }
