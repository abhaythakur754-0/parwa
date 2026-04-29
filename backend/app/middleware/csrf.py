"""
PARWA CSRF Protection Middleware (FIX A3)

Implements double-submit cookie pattern:
- On non-GET requests, validates that the X-CSRF-Token header
  matches the parwa_csrf cookie value.
- Safe methods (GET, HEAD, OPTIONS) are exempt.
- API endpoints under /api/webhooks/ are exempt (they use HMAC instead).
- The CSRF cookie is set by the frontend JavaScript (not httpOnly)
  so it can be read and sent as a header.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("parwa.csrf")

# Methods that are safe and don't need CSRF protection
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths that are exempt from CSRF (webhooks use HMAC, public endpoints)
CSRF_EXEMPT_PREFIXES = (
    "/api/webhooks/",
    "/api/public/",
    "/api/pricing/",
    "/api/health",
    "/api/events/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection.

    The frontend generates a random token, stores it in a cookie
    (parwa_csrf), and sends it in the X-CSRF-Token header on every
    mutating request. This middleware compares the two values.

    Why double-submit cookie instead of Synchronizer Token?
    - Simpler to implement (no server-side session storage needed)
    - Works with httpOnly session cookies (the CSRF cookie is separate)
    - Industry standard used by Django, Rails, etc.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip safe methods
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Skip exempt paths
        path = request.url.path
        if any(path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
            return await call_next(request)

        # Skip if no cookies at all (e.g., API key auth)
        if not request.cookies:
            return await call_next(request)

        # Get CSRF token from cookie
        csrf_cookie = request.cookies.get("parwa_csrf")

        # Get CSRF token from header
        csrf_header = request.headers.get("x-csrf-token", "")

        if not csrf_cookie or not csrf_header:
            logger.warning(
                "CSRF missing token: path=%s method=%s has_cookie=%s has_header=%s",
                path,
                request.method,
                bool(csrf_cookie),
                bool(csrf_header),
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "CSRF_FAILED",
                        "message": "CSRF validation failed. Missing token.",
                        "details": None,
                    }
                },
            )

        # Constant-time comparison to prevent timing attacks
        import secrets

        if not secrets.compare_digest(csrf_cookie, csrf_header):
            logger.warning(
                "CSRF token mismatch: path=%s method=%s",
                path, request.method,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "CSRF_FAILED",
                        "message": "CSRF validation failed. Token mismatch.",
                        "details": None,
                    }
                },
            )

        return await call_next(request)
