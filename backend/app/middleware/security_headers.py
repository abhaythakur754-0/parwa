"""PARWA Security Headers Middleware.

Adds security headers to all responses per BC-011/BC-012:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 0 (modern browsers)
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: camera/mic/geo disabled
- Content-Security-Policy: restrictive default policy (H-04)
- Strict-Transport-Security: in production
- Cache-Control: no-store on auth endpoints (M-11)
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware

# M-11: Paths that must have Cache-Control: no-store
AUTH_PATH_PREFIXES = (
    "/api/auth/",
    "/api/login",
    "/api/register",
    "/api/mfa/",
    "/api/refresh",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        # H-04: Content-Security-Policy header
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; "
            "form-action 'self'"
        )
        # HSTS only in production
        env = os.environ.get("ENVIRONMENT", "development")
        if env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # M-11: Prevent caching of auth responses
        path = request.url.path if hasattr(request, "url") else ""
        for prefix in AUTH_PATH_PREFIXES:
            if path.startswith(prefix):
                response.headers["Cache-Control"] = (
                    "no-store, no-cache, must-revalidate, max-age=0"
                )
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                break

        return response
