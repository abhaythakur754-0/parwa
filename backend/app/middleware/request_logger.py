"""
PARWA Request Logger Middleware (BC-012)

Logs every request with: method, path, status code, response time.
This provides the full request audit trail required by BC-012.

Logs are structured JSON in production, console output in dev/test.
Only non-sensitive information is logged — no passwords, tokens, or PII.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security.utils import get_client_ip
from app.logger import get_logger
from shared.utils.datetime import format_duration

logger = get_logger("request_logger")

# Paths to skip logging (health checks, metrics — too noisy)
SKIP_PATHS = {"/health", "/ready", "/metrics"}

# Paths that are relevant for Jarvis dashboard awareness
DASHBOARD_AWARENESS_PATHS = {
    "/api/tickets": "tickets",
    "/api/billing": "billing",
    "/api/variants": "variants",
    "/api/settings": "settings",
    "/api/knowledge": "knowledge",
    "/api/agents": "agents",
    "/api/dashboard": "dashboard",
    "/api/subscriptions": "subscriptions",
    "/api/shadow-mode": "shadow_mode",
}

# Methods that represent user actions (not just reads)
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every request with method, path, status, timing.

    BC-012: Full request audit trail for compliance and debugging.
    Skips health/ready/metrics endpoints to reduce log noise.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip noisy health endpoints
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        start_time = time.perf_counter()

        # Process the request
        response = await call_next(request)

        # Calculate timing
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Extract correlation ID if available (from ErrorHandlerMiddleware)
        correlation_id = getattr(
            request.state, "correlation_id", "unknown"
        )

        # Log the request
        log_method = (
            logger.warning if response.status_code >= 500 else logger.info
        )
        log_method(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            duration_human=format_duration(duration_ms / 1000),
            correlation_id=correlation_id,
            client_ip=get_client_ip(request),
        )

        # ── Record to Activity Store for Jarvis dashboard awareness ──
        # Mutating requests (POST/PUT/PATCH/DELETE) on dashboard-relevant
        # paths are recorded so Jarvis knows what the user is doing.
        # GET requests are recorded only for page navigation tracking.
        _record_dashboard_activity(request, response)

        return response


def _record_dashboard_activity(request: Request, response: Response) -> None:
    """Record dashboard activity to the Activity Store for Jarvis awareness.

    This is how Jarvis knows what the user is doing in the dashboard.
    Every mutating action (create, update, delete) on ticket, billing,
    variant, settings, knowledge, or agent endpoints is recorded.
    GET requests to dashboard pages are recorded as page views.

    BC-008: Never crashes — recording is wrapped in try/except.
    """
    try:
        path = request.url.path

        # Find matching dashboard awareness path
        matched_category = None
        for prefix, category in DASHBOARD_AWARENESS_PATHS.items():
            if path.startswith(prefix):
                matched_category = category
                break

        if matched_category is None:
            return  # Not a dashboard-relevant path

        # Extract company_id from request state (set by tenant middleware)
        company_id = getattr(request.state, "company_id", None)
        if not company_id:
            return  # Can't record without tenant scope

        # Extract user_id from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)

        # Determine action type
        method = request.method
        is_mutating = method in MUTATING_METHODS

        if is_mutating:
            action = f"api_{method.lower()}_{path.replace('/', '_').strip('_')}"
            severity = "info"
        else:
            # For GET requests, only record page views occasionally
            # (not every API call — too noisy)
            action = f"page_view_{matched_category}"
            severity = "info"

        # Record to Activity Store (fire-and-forget, non-blocking)
        from database.base import SessionLocal
        from app.services.jarvis_activity_store import record_dashboard_event

        db = SessionLocal()
        try:
            record_dashboard_event(
                db=db,
                company_id=company_id,
                action=action,
                actor_id=user_id,
                description=f"API {method} {path} → {response.status_code}",
                context={
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "category": matched_category,
                    "is_mutating": is_mutating,
                    "page": matched_category,
                },
                resource_type=matched_category,
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    except Exception:
        # BC-008: Recording failure is non-fatal
        pass


