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
from starlette.responses import JSONResponse

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
        limiter = get_rate_limiter()
        result = limiter.check(company_id=company_id, client_ip=client_ip)

        if not result.allowed:
            # Return 429 WITHOUT calling downstream handler
            # This prevents side effects on rate-limited requests
            error_response = build_error_response(
                status_code=429,
                error_code="RATE_LIMIT_EXCEEDED",
                message="Too many requests. Please retry later.",
                correlation_id=getattr(
                    request.state, "correlation_id", None
                ),
            )
            resp = JSONResponse(
                status_code=429,
                content=error_response.body,
                headers=error_response.headers,
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
        """Extract client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        if request.client:
            return request.client.host

        return ""
