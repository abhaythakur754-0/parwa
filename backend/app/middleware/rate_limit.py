"""
PARWA Rate Limit Middleware (BC-012 / F-018) — Rust-accelerated.

Uses ``parwa_core_bridge`` to delegate to the Rust ``RateLimiter``
for all rate-limit checks, classification, and failure tracking.
Pure-Python fallback is built into the bridge (BC-008).

Old dependency removed: ``app.services.rate_limit_service``
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security.security_utils import get_client_ip
from app.middleware.error_handler import build_error_response
from app.core.parwa_core_bridge import get_parwa_rate_limiter

logger = logging.getLogger("parwa.middleware.rate_limit")

# Shared bridge instance (per-process)
_bridge = get_parwa_rate_limiter()

# Paths that skip rate limiting (health, metrics)
SKIP_PATHS = {"/health", "/ready", "/metrics"}
SKIP_PREFIXES = ("/api/webhooks/",)


def get_rate_limiter():
    """Get the shared rate limit bridge (compat wrapper)."""
    return _bridge


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces per-category rate limiting.

    All logic delegated to the Rust-backed bridge:
    - Path classification
    - Per-email for auth endpoints (prevent enumeration)
    - Per-IP for general endpoints
    - Progressive backoff on auth failures
    - Sets X-RateLimit-* headers on every response (BC-012)
    - Skips health/ready/metrics and webhook endpoints
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip rate limiting for health endpoints
        if path in SKIP_PATHS:
            return await call_next(request)

        # Skip rate limiting for webhook prefixes
        for prefix in SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Classify the endpoint category
        svc = get_parwa_rate_limiter()
        category = svc.classify_path(path, request.method)

        # Extract identifier based on category
        try:
            identifier = await svc.extract_identifier(
                category, request,
            )
        except Exception:
            logger.debug("rate_limit_identifier_extraction_failed")
            identifier = "unknown"

        # Fallback: use IP if identifier extraction failed
        # Never skip rate limiting (L01: brute-force prevention)
        if identifier == "unknown":
            client_ip = get_client_ip(request)
            if client_ip:
                identifier = client_ip

        # Check rate limit
        try:
            # sync_redis_time is a no-op for Rust backend
            await svc.sync_redis_time()
            result = svc.check_rate_limit(category, identifier)
        except Exception as exc:
            # FAIL-CLOSED: Block request when rate limit check fails
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
