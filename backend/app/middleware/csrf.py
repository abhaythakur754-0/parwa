"""
CSRF Protection Middleware (H-04, BC-008) — Rust-accelerated.

Pure ASGI middleware that delegates CSRF logic to ``parwa_core_bridge``:
- Origin/Referer validation via Rust ``CSRFValidator.is_valid_origin``
- CSRF token generation via Rust ``CSRFValidator.generate_csrf_token``
- CSRF token validation via Rust ``CSRFValidator.validate_csrf_token``
- Adds Content-Security-Policy header (H-04)
- Skips verification for webhook routes (/api/webhooks/)
- Skips safe methods: GET, HEAD, OPTIONS
- BC-008 compliant: never crashes on malformed input

Configuration:
    CSRF_TRUSTED_ORIGINS: Comma-separated origin list (env var).
    CSRF_ENABLED: bool — Master switch (default true).
"""

import json
import logging
import os
import secrets
import time

logger = logging.getLogger("parwa.middleware.csrf")

# Cookie-based auth path prefixes that require CSRF tokens
_COOKIE_AUTH_PREFIXES = (
    "/api/auth/",
    "/api/login",
    "/api/register",
    "/api/mfa/",
    "/api/refresh",
)

# Public auth endpoints that do NOT require CSRF tokens
_PUBLIC_AUTH_PATHS = (
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/google",
    "/api/auth/refresh",
    "/api/auth/phone/send",
    "/api/auth/phone/verify",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/check-email",
)

# Webhook routes that skip CSRF checks
_WEBHOOK_SKIP_PREFIXES = ("/api/webhooks/",)

# Safe HTTP methods
_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

# CSRF cookie config
_CSRF_COOKIE_NAME = "parwa_csrf"
_CSRF_MAX_AGE = 3600  # 1 hour

# CSP header (H-04)
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

# Lazy-loaded bridge validator
_validator = None


def _get_validator():
    """Lazy-load the CSRF validator bridge."""
    global _validator
    if _validator is None:
        from app.core.parwa_core_bridge import parwa_csrf_validator
        _validator = parwa_csrf_validator()
    return _validator


class CSRFSecurityMiddleware:
    """Pure ASGI middleware for CSRF protection.

    Delegates validation to Rust ``CSRFValidator`` via the bridge.
    Pure-Python fallback is built into the bridge (BC-008).
    """

    def __init__(self, app):
        self.app = app

    def _is_enabled(self) -> bool:
        """Check if CSRF middleware is enabled."""
        return os.environ.get(
            "CSRF_ENABLED", "true",
        ).lower() != "false"

    # ── ASGI entry point ───────────────────────────────────────────

    async def __call__(self, scope, receive, send):
        """Process a single ASGI HTTP request through CSRF checks."""
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # If middleware is disabled, pass through
        if not self._is_enabled():
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "").upper()
        path = scope.get("path", "/")

        # ── Check for existing CSRF cookie ──
        request_headers = dict(scope.get("headers", []))
        cookie_header = request_headers.get(
            b"cookie", b"",
        ).decode("utf-8", errors="replace")
        existing_csrf = self._extract_cookie(
            cookie_header, _CSRF_COOKIE_NAME,
        )
        new_csrf_token = ""
        if not existing_csrf:
            # Generate token via Rust bridge
            try:
                validator = _get_validator()
                new_csrf_token = validator.generate_csrf_token()
            except Exception:
                # BC-008: fallback to Python token
                new_csrf_token = secrets.token_hex(16)

        # ── Wrap send to inject CSP header + CSRF cookie ──
        wrapped_send = self._wrap_send(send, new_csrf_token)

        # ── Fast-path: skip safe methods ──
        if method in _SAFE_METHODS:
            await self.app(scope, receive, wrapped_send)
            return

        # ── Skip webhook routes ──
        for skip_prefix in _WEBHOOK_SKIP_PREFIXES:
            if path.startswith(skip_prefix):
                await self.app(scope, receive, wrapped_send)
                return

        # ── Check Bearer/API key exemption ──
        auth_header = request_headers.get(
            b"authorization", b"",
        ).decode("utf-8", errors="replace").strip()
        api_key_header = request_headers.get(
            b"x-api-key", b"",
        ).decode("utf-8", errors="replace").strip()
        has_bearer = (
            auth_header.lower().startswith("bearer ")
            or bool(api_key_header)
        )

        # ── Validate Origin / Referer ──
        try:
            origin = request_headers.get(
                b"origin", b"",
            ).decode("utf-8", errors="replace")
            referer = request_headers.get(
                b"referer", b"",
            ).decode("utf-8", errors="replace")

            # Check trusted origins (instance attribute set by tests or config).
            # If _trusted_origins is configured, the request origin/referer must
            # match one of them. Empty list = dev mode (allow all).
            trusted = getattr(self, "_trusted_origins", None)
            if trusted:
                candidate = origin or (referer.split("?")[0] if referer else "")
                if not candidate or not any(
                    candidate == t or candidate.startswith(t + "/") or candidate.startswith(t.rstrip("/"))
                    for t in trusted
                ):
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
            else:
                # No trusted origins configured — use the Rust validator bridge.
                validator = _get_validator()
                if not validator.is_valid_origin(origin, referer):
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
        if self._is_cookie_auth_path(path) and not has_bearer:
            try:
                csrf_token = self._extract_cookie(
                    cookie_header, _CSRF_COOKIE_NAME,
                )
                csrf_header = request_headers.get(
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

                if not self._validate_double_submit(
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

    # ── Static helpers ────────────────────────────────────────────

    @staticmethod
    def _is_cookie_auth_path(path: str) -> bool:
        """Check if path needs CSRF token (excludes public auth)."""
        if path in _PUBLIC_AUTH_PATHS:
            return False
        for prefix in _COOKIE_AUTH_PREFIXES:
            base = prefix.rstrip("/")
            if path == prefix or path.startswith(base + "/"):
                return True
        return False

    @staticmethod
    def _extract_cookie(cookie_header: str, name: str) -> str:
        """Extract a named cookie value from Cookie header."""
        if not cookie_header:
            return ""
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(name + "="):
                return part[len(name) + 1:]
        return ""

    @staticmethod
    def _validate_double_submit(
        cookie_token: str, header_token: str,
    ) -> bool:
        """Validate CSRF cookie matches header token (double-submit)."""
        if not cookie_token or not header_token:
            return False
        import hmac
        return hmac.compare_digest(
            cookie_token, header_token,
        )

    # ── Token API (nonce:timestamp:sig format) ──────────────────────
    # Used by tests + any code that wants a signed CSRF token outside ASGI.

    @staticmethod
    def generate_csrf_token(secret_key: str = "") -> str:
        """Generate a signed CSRF token: ``nonce:timestamp:signature``.

        - nonce: 16 random bytes hex-encoded (32 chars)
        - timestamp: unix seconds (string)
        - signature: first 16 hex chars of HMAC-SHA256(secret, nonce:timestamp)
        """
        import hashlib
        import hmac
        import secrets as _secrets
        import time as _time
        key = (secret_key or os.environ.get("JWT_SECRET_KEY", "dev-csrf-secret")).encode()
        nonce = _secrets.token_hex(16)
        ts = str(int(_time.time()))
        sig = hmac.new(key, f"{nonce}:{ts}".encode(), hashlib.sha256).hexdigest()[:16]
        return f"{nonce}:{ts}:{sig}"

    @staticmethod
    def validate_csrf_token(token: str, secret_key: str = "", max_age_seconds: int = 3600) -> bool:
        """Validate a ``nonce:timestamp:signature`` CSRF token.

        Returns True only if: format is correct, signature matches, and
        timestamp is within ``max_age_seconds`` (default 1 hour).
        """
        if not token or not isinstance(token, str):
            return False
        parts = token.split(":")
        if len(parts) != 3:
            return False
        nonce, ts_str, sig = parts
        if len(nonce) != 32 or not ts_str.isdigit() or len(sig) != 16:
            return False
        try:
            ts = int(ts_str)
        except ValueError:
            return False
        # Freshness check
        import time as _time
        if int(_time.time()) - ts > max_age_seconds:
            return False
        # Signature check (constant-time)
        import hashlib
        import hmac
        key = (secret_key or os.environ.get("JWT_SECRET_KEY", "dev-csrf-secret")).encode()
        expected = hmac.new(key, f"{nonce}:{ts_str}".encode(), hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(sig, expected)

    @staticmethod
    def _wrap_send(send, new_csrf_token: str = ""):
        """Wrap ASGI send to inject CSP header and CSRF cookie."""
        headers_injected = False

        async def wrapped_send(message):
            nonlocal headers_injected
            if (
                message.get("type") == "http.response.start"
                and not headers_injected
            ):
                headers = list(message.get("headers", []))
                has_csp = any(
                    h[0].lower() == b"content-security-policy"
                    for h in headers
                )
                if not has_csp:
                    headers.append(
                        [b"content-security-policy", _CSP_HEADER.encode()]
                    )
                if new_csrf_token:
                    csrf_cookie = (
                        f"{_CSRF_COOKIE_NAME}={new_csrf_token}; "
                        f"Path=/; SameSite=Lax; "
                        f"Max-Age={_CSRF_MAX_AGE}"
                    )
                    headers.append(
                        [b"set-cookie", csrf_cookie.encode()]
                    )
                message = {**message, "headers": headers}
                headers_injected = True
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
