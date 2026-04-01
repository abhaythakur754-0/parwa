"""
PARWA Rate Limit Middleware (BC-012)

Wraps incoming requests with rate limiting checks.
Returns 429 Too Many Requests when limit is exceeded.
Sets X-RateLimit-* headers on every response (BC-012).

BC-001: Rate limiting is per-company_id.
BC-011: Redis failure -> fail-open (allow requests).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.middleware.error_handler import build_error_response
from security.rate_limiter import RateLimiter, DEFAULT_REQUESTS_PER_WINDOW

# Shared rate limiter instance (per-process, in-memory)
_rate_limiter = RateLimiter(
    requests_per_window=DEFAULT_REQUESTS_PER_WINDOW,
    window_seconds=60,
)


def get_rate_limiter() -> RateLimiter:
    """Get the shared rate limiter instance."""
    return _rate_limiter


# Paths that skip rate limiting (health, metrics)
SKIP_PATHS = {"/health", "/ready", "/metrics"}
SKIP_PREFIXES = ("/api/public/",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limiting on all API requests.

    - Checks rate limit BEFORE processing request (no side effects on 429)
    - Checks company_id from request state (set by TenantMiddleware)
    - Applies sliding window rate limiting per company_id (BC-001)
    - Progressive lockout for repeated violations (BC-011)
    - Sets X-RateLimit-* headers on every response (BC-012)
    - Skips health/ready/metrics and public API endpoints
    """

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health endpoints
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        # Skip rate limiting for public API prefixes
        for prefix in SKIP_PREFIXES:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        # Get company_id from request state (set by TenantMiddleware)
        company_id = getattr(request.state, "company_id", None)
        if not company_id:
            # No company_id -> skip rate limiting (will be caught by
            # TenantMiddleware with 403 if required)
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit BEFORE processing request
        # BC-011: Fail-open — if limiter crashes, allow request
        limiter = get_rate_limiter()
        try:
            result = limiter.check(
                company_id=company_id, client_ip=client_ip
            )
        except Exception:
            # BC-011: Fail-open on rate limiter failure
            return await call_next(request)

        if not result.allowed:
            # Return 429 WITHOUT calling downstream handler
            # This prevents side effects on rate-limited requests
            # BC-012: Structured error response with correlation ID
            correlation_id = getattr(
                request.state, "correlation_id", None
            )
            resp = build_error_response(
                status_code=429,
                error_code="RATE_LIMIT_EXCEEDED",
                message="Too many requests. Please retry later.",
                correlation_id=correlation_id,
            )
            # Apply rate limit headers to error response
            for header, value in result.to_headers().items():
                resp.headers[header] = value
            return resp

        # Request is allowed - process it
        response = await call_next(request)
        # Set rate limit headers on successful response
        for header, value in result.to_headers().items():
            response.headers[header] = value
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request.

        Prefers the direct connection IP (request.client.host) set by
        the ASGI server from the TCP connection, which cannot be spoofed.
        Falls back to X-Real-IP, then X-Forwarded-For only if no
        direct connection IP is available.

        BC-011: IP must not be client-controllable for rate limiting.
        """
        # Primary: direct TCP connection IP (set by ASGI server)
        if request.client:
            return request.client.host

        # Fallback: X-Real-IP (set by trusted reverse proxy)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Last resort: X-Forwarded-For (only if no direct connection)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        return ""
