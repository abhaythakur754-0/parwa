"""
PARWA Rate Limit Middleware (BC-012 / F-018)

Enhanced middleware using per-endpoint-category rate limits.
Routes requests to correct category based on path pattern.
Uses the new rate_limit_service for advanced per-email,
per-IP, per-API-key, and per-user rate limiting.

Keeps backward compatibility with the old security/rate_limiter
module (the old limiter is still available but not used here).
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security.utils import get_client_ip
from app.middleware.error_handler import build_error_response
from app.services.rate_limit_service import (
    get_rate_limit_service,
)

logger = logging.getLogger("parwa.middleware.rate_limit")

# Shared service instance (per-process)
_rate_limit_svc = get_rate_limit_service()

# Paths that skip rate limiting (health, metrics)
SKIP_PATHS = {"/health", "/ready", "/metrics"}
SKIP_PREFIXES = ("/api/webhooks/",)


def get_rate_limiter():
    """Get the shared rate limit service (compat wrapper)."""
    return _rate_limit_svc


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces per-category rate limiting.

    - Routes to correct endpoint category based on path
    - Per-email for auth endpoints (prevent enumeration)
    - Per-IP for general endpoints
    - Per-API-key for integration endpoints
    - Progressive backoff on auth failures
    - Sets X-RateLimit-* headers on every response (BC-012)
    - Skips health/ready/metrics and public API endpoints
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip rate limiting for health endpoints
        if path in SKIP_PATHS:
            return await call_next(request)

        # Skip rate limiting for public API prefixes
        for prefix in SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Classify the endpoint category
        svc = get_rate_limit_service()
        category = svc.classify_path(path, request.method)

        # Extract identifier based on category
        identifier = await svc.extract_identifier(
            category, request,
        )

        # Fallback: use IP if identifier extraction failed
        # Never skip rate limiting (L01: brute-force prevention)
        if identifier == "unknown":
            client_ip = get_client_ip(request)
            if client_ip:
                identifier = client_ip

        # Check rate limit
        try:
            # F-018: Sync Redis time for consistent timestamps
            await svc.sync_redis_time()
            result = svc.check_rate_limit(
                category, identifier,
            )
        except Exception as exc:
            # FAIL-CLOSED: When Redis is unavailable or rate limit
            # check fails, BLOCK the request with 503.  This prevents
            # brute-force / DDoS from bypassing rate limits when
            # Redis is down.  The in-memory fallback in
            # rate_limit_service is NOT used here by default.
            logger.critical(
                "rate_limit_check_failed_fail_closed path=%s "
                "category=%s identifier=%s error=%s",
                path,
                category,
                identifier[:50] if identifier else "none",
                str(exc)[:200],
                extra={
                    "path": path,
                    "category": category,
                },
            )
            correlation_id = getattr(
                request.state, "correlation_id", None
            )
            return build_error_response(
                status_code=503,
                error_code="SERVICE_UNAVAILABLE",
                message="Rate limiting service is temporarily "
                "unavailable. Please retry later.",
                correlation_id=correlation_id,
            )

        if not result.allowed:
            correlation_id = getattr(
                request.state, "correlation_id", None
            )
            resp = build_error_response(
                status_code=429,
                error_code="RATE_LIMIT_EXCEEDED",
                message="Too many requests. "
                "Please retry later.",
                correlation_id=correlation_id,
            )
            for hdr, val in result.to_headers().items():
                resp.headers[hdr] = val
            return resp

        # Request is allowed
        response = await call_next(request)
        for hdr, val in result.to_headers().items():
            response.headers[hdr] = val
        return response


