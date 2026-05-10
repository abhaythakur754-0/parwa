"""
CSRF Protection Middleware (H-04, BC-008)

Pure ASGI middleware that provides CSRF defense for PARWA.
- Primary defense: Origin/Referer header validation (Bearer-token API)
- Secondary defense: CSRF token generation/validation for cookie paths
- Adds Content-Security-Policy header (H-04 gap fix)
- Skips verification for webhook routes (/api/webhooks/)
- Skips safe methods: GET, HEAD, OPTIONS
- Logs all CSRF failures with correlation IDs
- BC-008 compliant: never crashes on malformed input

Configuration:
    CSRF_TRUSTED_ORIGINS: Comma-separated origin list (env var).
        Falls back to CORS_ORIGINS if not set.
    CSRF_ENABLED: bool — Master switch (default true).
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from urllib.parse import urlparse

logger = logging.getLogger("parwa.middleware.csrf")

# ── Configuration ──────────────────────────────────────────────────────

# Cookie-based auth path prefixes that require CSRF tokens
_COOKIE_AUTH_PREFIXES = (
    "/api/auth/",
    "/api/login",
    "/api/register",
    "/api/mfa/",
    "/api/refresh",
)

# Webhook routes that skip CSRF checks (have their own HMAC verification)
_WEBHOOK_SKIP_PREFIXES = ("/api/webhooks/",)

# Safe HTTP methods that skip CSRF checks
_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

# CSRF cookie name and token TTL
_CSRF_COOKIE_NAME = "parwa_csrf"
_CSRF_MAX_AGE = 3600  # 1 hour

# Content-Security-Policy header value (H-04)
_CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def _parse_trusted_origins() -> list:
    """Parse trusted origins from environment variable.

    Reads CSRF_TRUSTED_ORIGINS first, falls back to CORS_ORIGINS,
    then falls back to an empty list (effectively disabling CSRF
    in local development where no origins are configured).
    """
    raw = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
    if not raw:
        raw = os.environ.get("CORS_ORIGINS", "")
    if not raw:
        return []
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if origins:
        logger.info(
            "csrf_trusted_origins_configured count=%d",
            len(origins),
        )
    return origins


class CSRFSecurityMiddleware:
    """Pure ASGI middleware for CSRF protection.

    Defence-in-depth strategy:
        1. Origin / Referer header validation (primary — for
           Bearer-token API endpoints).
        2. CSRF token cookie validation (secondary — for any
           cookie-based auth endpoints).

    The middleware never raises; all errors result in a 403 JSON
    response (BC-008).
    """

    def __init__(self, app):
        self.app = app
        self._trusted_origins = _parse_trusted_origins()

    def _is_enabled(self) -> bool:
        """Check if CSRF middleware is enabled."""
        return os.environ.get(
            "CSRF_ENABLED", "true",
        ).lower() != "false"

    # ── ASGI entry point ───────────────────────────────────────────

    async def __call__(self, scope, receive, send):
        """Process a single ASGI HTTP request through CSRF checks."""
        # Pass non-HTTP scopes through unchanged
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # If middleware is disabled, pass through
        if not self._is_enabled():
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        path = scope.get("path", "/")

        # ── Add CSP header to all responses ──
        wrapped_send = self._wrap_send(send)

        # ── Fast-path: skip safe methods ──
        if method in _SAFE_METHODS:
            await self.app(scope, receive, wrapped_send)
            return

        # ── Skip webhook routes (have own HMAC verification) ──
        for skip_prefix in _WEBHOOK_SKIP_PREFIXES:
            if path.startswith(skip_prefix):
                await self.app(scope, receive, wrapped_send)
                return

        # ── Validate Origin / Referer ──
        try:
            headers = dict(scope.get("headers", []))
            origin = headers.get(b"origin", b"").decode(
                "utf-8", errors="replace",
            )
            referer = headers.get(b"referer", b"").decode(
                "utf-8", errors="replace",
            )

            if not self._is_valid_origin(origin, referer):
                correlation_id = secrets.token_hex(8)
                logger.warning(
                    "csrf_rejected method=%s path=%s "
                    "origin=%s referer=%s correlation_id=%s",
                    method, path,
                    origin or "(none)",
                    referer or "(none)",
                    correlation_id,
                )
                await self._send_forbidden(
                    scope, send,
                    "CSRF validation failed: invalid origin",
                    correlation_id,
                )
                return

        except Exception as exc:
            # BC-008: Never crash — reject on unexpected errors
            logger.error(
                "csrf_internal_error path=%s error=%s",
                path, exc,
            )
            await self._send_forbidden(
                scope, send,
                "CSRF validation failed",
            )
            return

        # ── For cookie-based auth paths, verify CSRF token ──
        if self._is_cookie_auth_path(path):
            try:
                headers = dict(scope.get("headers", []))
                cookie_header = headers.get(b"cookie", b"").decode(
                    "utf-8", errors="replace",
                )
                csrf_token = self._extract_cookie(
                    cookie_header, _CSRF_COOKIE_NAME,
                )
                csrf_header = headers.get(
                    b"x-csrf-token", b"",
                ).decode("utf-8", errors="replace")

                if not csrf_token or not csrf_header:
                    correlation_id = secrets.token_hex(8)
                    logger.warning(
                        "csrf_token_missing path=%s "
                        "correlation_id=%s",
                        path, correlation_id,
                    )
                    await self._send_forbidden(
                        scope, send,
                        "CSRF token missing",
                        correlation_id,
                    )
                    return

                if not self._validate_csrf_token(
                    csrf_token, csrf_header,
                ):
                    correlation_id = secrets.token_hex(8)
                    logger.warning(
                        "csrf_token_invalid path=%s "
                        "correlation_id=%s",
                        path, correlation_id,
                    )
                    await self._send_forbidden(
                        scope, send,
                        "CSRF token invalid",
                        correlation_id,
                    )
                    return

            except Exception as exc:
                logger.error(
                    "csrf_token_error path=%s error=%s",
                    path, exc,
                )
                await self._send_forbidden(
                    scope, send,
                    "CSRF validation failed",
                )
                return

        await self.app(scope, receive, wrapped_send)

    # ── Origin validation ──────────────────────────────────────────

    def _is_valid_origin(
        self, origin: str, referer: str,
    ) -> bool:
        """Validate Origin and/or Referer against trusted origins.

        - If Origin is present, it must match a trusted origin.
        - If Origin is absent but Referer is present, the Referer
          origin must match.
        - If both are absent, reject (no origin information).
        - If no trusted origins are configured, allow (local dev).
        """
        # No trusted origins configured — allow (local dev)
        if not self._trusted_origins:
            return True

        # Prefer Origin header
        check_origin = origin
        if not check_origin and referer:
            # Extract origin from Referer URL
            try:
                parsed = urlparse(referer)
                check_origin = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                return False

        if not check_origin:
            return False

        # Check against trusted origins
        for trusted in self._trusted_origins:
            if check_origin == trusted or check_origin.startswith(trusted + "/"):
                return True

        return False

    # ── CSRF token helpers ─────────────────────────────────────────

    @staticmethod
    def _is_cookie_auth_path(path: str) -> bool:
        """Check if path is a cookie-based auth endpoint."""
        for prefix in _COOKIE_AUTH_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return True
        return False

    @staticmethod
    def _extract_cookie(
        cookie_header: str, name: str,
    ) -> str:
        """Extract a named cookie value from a Cookie header."""
        if not cookie_header:
            return ""
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(name + "="):
                return part[len(name) + 1:]
        return ""

    @staticmethod
    def generate_csrf_token(secret_key: str = "") -> str:
        """Generate a new CSRF token.

        The token is a random nonce combined with an HMAC using the
        server secret, making tokens unforgeable without the secret.

        Args:
            secret_key: Server secret for HMAC. Falls back to
                SECRET_KEY env var.

        Returns:
            Hex-encoded CSRF token string.
        """
        if not secret_key:
            secret_key = os.environ.get(
                "SECRET_KEY", "parwa-csrf-fallback",
            )
        nonce = secrets.token_hex(16)
        timestamp = str(int(time.time()))
        msg = f"{nonce}:{timestamp}"
        sig = hmac.new(
            secret_key.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16]
        return f"{nonce}:{timestamp}:{sig}"

    @staticmethod
    def validate_csrf_token(
        token: str,
        secret_key: str = "",
    ) -> bool:
        """Validate a CSRF token.

        Checks:
            1. Token format (nonce:timestamp:sig)
            2. Timestamp freshness (within _CSRF_MAX_AGE seconds)
            3. HMAC signature validity

        Args:
            token: The CSRF token string to validate.
            secret_key: Server secret for HMAC verification.

        Returns:
            True if token is valid, False otherwise.
        """
        if not token:
            return False
        try:
            if not secret_key:
                secret_key = os.environ.get(
                    "SECRET_KEY", "parwa-csrf-fallback",
                )
            parts = token.split(":")
            if len(parts) != 3:
                return False
            nonce, timestamp_str, sig = parts
            # Check timestamp freshness
            try:
                ts = int(timestamp_str)
                age = abs(time.time() - ts)
                if age > _CSRF_MAX_AGE:
                    return False
            except (ValueError, TypeError):
                return False
            # Verify HMAC signature
            msg = f"{nonce}:{timestamp_str}"
            expected = hmac.new(
                secret_key.encode("utf-8"),
                msg.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()[:16]
            return hmac.compare_digest(sig, expected)
        except Exception:
            return False

    @staticmethod
    def _validate_csrf_token(
        cookie_token: str, header_token: str,
    ) -> bool:
        """Validate that the CSRF cookie matches the header token.

        The header token is the CSRF token; the cookie contains
        the same token (double-submit cookie pattern).
        """
        if not cookie_token or not header_token:
            return False
        # Tokens must match exactly (double-submit pattern)
        return hmac.compare_digest(cookie_token, header_token)

    # ── Response helpers ───────────────────────────────────────────

    @staticmethod
    def _wrap_send(send):
        """Wrap the ASGI send callable to inject CSP header."""
        csp_injected = False

        async def wrapped_send(message):
            nonlocal csp_injected
            if (
                message.get("type") == "http.response.start"
                and not csp_injected
            ):
                headers = list(message.get("headers", []))
                # Add CSP header if not already present
                has_csp = any(
                    h[0].lower() == b"content-security-policy"
                    for h in headers
                )
                if not has_csp:
                    headers.append(
                        [b"content-security-policy", _CSP_HEADER.encode()]
                    )
                message = {**message, "headers": headers}
                csp_injected = True
            await send(message)

        return wrapped_send

    @staticmethod
    async def _send_forbidden(
        scope, send,
        message: str,
        correlation_id: str = "",
    ):
        """Send a 403 JSON response (BC-012)."""
        error_body = {
            "error": {
                "code": "FORBIDDEN",
                "message": message,
                "details": None,
            }
        }
        if correlation_id:
            error_body["correlation_id"] = correlation_id

        body = json.dumps(error_body).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                [b"content-type", b"application/json"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": body,
        })
