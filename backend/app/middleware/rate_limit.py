"""
PARWA Rate Limit Middleware (BC-012 / F-018)

Enhanced middleware using per-endpoint-category rate limits.
Routes requests to correct category based on path pattern.
Uses the new rate_limit_service for advanced per-email,
per-IP, per-API-key, and per-user rate limiting.

Keeps backward compatibility with the old security/rate_limiter
module (the old limiter is still available but not used here).
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.middleware.error_handler import build_error_response
from app.services.rate_limit_service import (
    get_rate_limit_service,
)

# Shared service instance (per-process)
_rate_limit_svc = get_rate_limit_service()

# Number of trusted reverse-proxy layers in front of the app.
# Only the rightmost N addresses in X-Forwarded-For are trusted.
_TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))

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
            client_ip = self._get_client_ip(request)
            if client_ip:
                identifier = client_ip

        # Check rate limit
        try:
            # F-018: Sync Redis time for consistent timestamps
            await svc.sync_redis_time()
            result = svc.check_rate_limit(
                category, identifier,
            )
        except Exception:
            # BC-011: Fail-open on rate limiter failure
            # TODO(B5): For authentication-critical endpoints (login, register,
            # password-reset, OTP), consider fail-closed behavior: if the rate
            # limiter cannot check Redis, reject the request with 429 instead
            # of allowing it through. This prevents brute-force attacks when
            # Redis is down. Implement by checking path category here:
            #   if category in ("auth", "otp"):
            #       return build_error_response(status_code=429, ...)
            return await call_next(request)

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

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, honouring trusted proxy configuration.

        Reads ``X-Forwarded-For`` only when ``TRUSTED_PROXY_COUNT > 0``
        and returns the rightmost trusted address (i.e. the client-side
        IP closest to the outermost trusted proxy).

        Falls back to ``request.client.host`` when the header is absent
        or no trusted proxies are configured.
        """
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded and _TRUSTED_PROXY_COUNT > 0:
            ips = [ip.strip() for ip in forwarded.split(",")]
            if len(ips) >= _TRUSTED_PROXY_COUNT:
                return ips[-_TRUSTED_PROXY_COUNT]
        return request.client.host if request.client else "unknown"
