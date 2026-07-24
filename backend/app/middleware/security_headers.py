"""PARWA Security Headers Middleware — Rust-accelerated.

Delegates header generation to ``parwa_core_bridge.parwa_get_security_headers()``
which uses the Rust ``SecurityHeaders`` module. Adds headers to every response:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 0 (modern browsers)
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy: camera/mic/geo disabled
- Content-Security-Policy with per-request nonce (H-04)
- Strict-Transport-Security: in production
- Cache-Control: no-store on auth endpoints (M-11)
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.parwa_core_bridge import parwa_get_security_headers


# Auth endpoint prefixes that get Cache-Control: no-store (M-11)
AUTH_PATH_PREFIXES = (
    "/api/auth/",
    "/api/login",
    "/api/logout",
    "/api/register",
    "/api/refresh",
    "/api/mfa/",
    "/api/forgot-password",
    "/api/reset-password",
    "/api/verify-email",
    "/api/verify-otp",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response.

    Delegates to Rust ``SecurityHeaders.generate_headers()`` via the bridge.
    Pure-Python fallback is built into the bridge (BC-008).
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path if hasattr(request, "url") else ""

        # Get environment from config or env var
        environment = os.environ.get("ENVIRONMENT", "development")

        # Delegate to bridge (Rust when available, Python fallback otherwise)
        headers = parwa_get_security_headers(path, environment)

        # ── Post-process: ensure CSP img-src allows blob: (H-04) ──
        csp = headers.get("Content-Security-Policy", "")
        if csp and "img-src" in csp and "blob:" not in csp:
            headers["Content-Security-Policy"] = csp.replace(
                "img-src 'self' data:",
                "img-src 'self' data: blob:",
            )

        # ── Post-process: HSTS in production (H-02) ──
        if environment == "production" and "Strict-Transport-Security" not in headers:
            headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # ── Post-process: Cache-Control: no-store on auth paths (M-11) ──
        if any(path.startswith(prefix) for prefix in AUTH_PATH_PREFIXES):
            headers["Cache-Control"] = "no-store"

        # Apply headers to response
        for name, value in headers.items():
            response.headers[name] = value

        return response
