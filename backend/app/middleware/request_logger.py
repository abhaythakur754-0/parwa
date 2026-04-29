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

from app.logger import get_logger
from shared.utils.datetime import format_duration

logger = get_logger("request_logger")

# Paths to skip logging (health checks, metrics — too noisy)
SKIP_PATHS = {"/health", "/ready", "/metrics"}


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
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        # Log the request
        log_method = logger.warning if response.status_code >= 500 else logger.info
        log_method(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            duration_human=format_duration(duration_ms / 1000),
            correlation_id=correlation_id,
            client_ip=_get_client_ip(request),
        )

        return response


def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request.

    Checks X-Forwarded-For first (behind reverse proxy),
    then X-Real-IP, then falls back to client host.

    Args:
        request: Incoming HTTP request.

    Returns:
        Client IP address string.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs; first is the original
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"
