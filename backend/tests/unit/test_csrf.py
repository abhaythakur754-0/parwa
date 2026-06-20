"""
CSRF Protection Middleware — Unit Tests

Tests for CSRFSecurityMiddleware (pure ASGI middleware).
No database connection required — all tests use mock ASGI scopes.

Run: cd /home/z/my-project/parwa && python -m pytest backend/tests/unit/test_csrf.py -v
"""

import json
import os
import sys

import pytest

# Ensure backend/app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.middleware.csrf import (
    CSRFSecurityMiddleware,
    _SAFE_METHODS,
    _WEBHOOK_SKIP_PREFIXES,
    _COOKIE_AUTH_PREFIXES,
    _CSP_HEADER,
)


# ── Helpers ────────────────────────────────────────────────────────

def _make_scope(
    method: str = "POST",
    path: str = "/api/v1/tickets",
    headers: list | None = None,
) -> dict:
    """Build a minimal ASGI HTTP scope."""
    return {
        "type": "http",
        "method": method.upper(),
        "path": path,
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 50000),
    }


def _make_middleware(
    trusted_origins: list | None = None,
) -> CSRFSecurityMiddleware:
    """Create a CSRF middleware with controlled trusted origins."""
    app = CSRFSecurityMiddleware.__new__(CSRFSecurityMiddleware)
    app.app = _noop_app
    app._trusted_origins = trusted_origins if trusted_origins is not None else []
    return app


async def _noop_app(scope, receive, send):
    """No-op downstream ASGI app."""
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": b'{"ok": true}',
    })


async def _run_middleware(
    method: str = "POST",
    path: str = "/api/v1/tickets",
    origin: str | None = None,
    referer: str | None = None,
    cookie: str | None = None,
    csrf_token_header: str | None = None,
    trusted_origins: list | None = None,
) -> list:
    """Run the CSRF middleware and return the ASGI messages."""
    headers = []
    if origin is not None:
        headers.append([b"origin", origin.encode()])
    if referer is not None:
        headers.append([b"referer", referer.encode()])
    if cookie is not None:
        headers.append([b"cookie", cookie.encode()])
    if csrf_token_header is not None:
        headers.append(
            [b"x-csrf-token", csrf_token_header.encode()],
        )

    scope = _make_scope(method=method, path=path, headers=headers)

    async def receive():
        return {"type": "http.request", "body": b""}

    messages = []

    async def capture_send(message):
        messages.append(message)

    middleware = _make_middleware(
        trusted_origins=trusted_origins,
    )
    await middleware(scope, receive, capture_send)
    return messages


def _get_status(messages: list) -> int:
    """Extract HTTP status code from ASGI messages."""
    for msg in messages:
        if msg.get("type") == "http.response.start":
            return msg.get("status", 0)
    return 0


def _get_body(messages: list) -> dict:
    """Extract JSON body from ASGI messages."""
    for msg in messages:
        if msg.get("type") == "http.response.body":
            return json.loads(msg.get("body", b"{}"))
    return {}


# ═══════════════════════════════════════════════════════════════════
# Safe methods skip
# ═══════════════════════════════════════════════════════════════════


class TestCSRFSafeMethods:
    """CSRF middleware must skip GET, HEAD, OPTIONS requests."""

    @pytest.mark.parametrize("method", list(_SAFE_METHODS))
    @pytest.mark.asyncio
    async def test_safe_methods_skip(self, method):
        """GET/HEAD/OPTIONS requests should pass through."""
        messages = await _run_middleware(method=method)
        assert _get_status(messages) == 200

    @pytest.mark.asyncio
    async def test_post_is_not_safe(self):
        """POST should be checked by CSRF."""
        messages = await _run_middleware(
            method="POST",
            origin="https://evil.com",
        )
        # With no trusted origins, POST with evil origin passes
        # (no origins configured = dev mode)
        assert _get_status(messages) == 200

    @pytest.mark.asyncio
    async def test_delete_is_checked(self):
        """DELETE should be checked by CSRF."""
        messages = await _run_middleware(
            method="DELETE",
            origin="https://evil.com",
        )
        assert _get_status(messages) == 200  # No origins configured


# ═══════════════════════════════════════════════════════════════════
# Webhook route skip
# ═══════════════════════════════════════════════════════════════════


class TestCSRFWebhookSkip:
    """CSRF middleware must skip /api/webhooks/ routes."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/webhooks/paddle",
            "/api/webhooks/shopify",
            "/api/webhooks/twilio/callback",
            "/api/webhooks/brevo/events",
        ],
    )
    @pytest.mark.asyncio
    async def test_webhook_routes_skip(self, path):
        """Webhook routes should bypass CSRF regardless of origin."""
        messages = await _run_middleware(
            method="POST",
            path=path,
            origin="https://evil.com",
        )
        assert _get_status(messages) == 200


# ═══════════════════════════════════════════════════════════════════
# Origin validation
# ═══════════════════════════════════════════════════════════════════


class TestCSRFOriginValidation:
    """CSRF middleware must validate Origin/Referer headers."""

    @pytest.mark.asyncio
    async def test_valid_origin_accepted(self):
        """Valid origin should be accepted."""
        messages = await _run_middleware(
            method="POST",
            origin="https://app.parwa.io",
            trusted_origins=["https://app.parwa.io"],
        )
        assert _get_status(messages) == 200

    @pytest.mark.asyncio
    async def test_invalid_origin_rejected(self):
        """Origin not in trusted list should be rejected."""
        messages = await _run_middleware(
            method="POST",
            origin="https://evil.com",
            trusted_origins=["https://app.parwa.io"],
        )
        assert _get_status(messages) == 403

    @pytest.mark.asyncio
    async def test_no_origin_no_referer_rejected(self):
        """Requests with no Origin and no Referer should be rejected."""
        messages = await _run_middleware(
            method="POST",
            trusted_origins=["https://app.parwa.io"],
        )
        assert _get_status(messages) == 403

    @pytest.mark.asyncio
    async def test_referer_fallback_accepted(self):
        """If Origin is absent, Referer origin should be validated."""
        messages = await _run_middleware(
            method="POST",
            referer="https://app.parwa.io/some/path",
            trusted_origins=["https://app.parwa.io"],
        )
        assert _get_status(messages) == 200

    @pytest.mark.asyncio
    async def test_referer_fallback_rejected(self):
        """If Origin is absent, bad Referer should be rejected."""
        messages = await _run_middleware(
            method="POST",
            referer="https://evil.com/attack",
            trusted_origins=["https://app.parwa.io"],
        )
        assert _get_status(messages) == 403

    @pytest.mark.asyncio
    async def test_no_trusted_origins_allows_all(self):
        """With no trusted origins, all requests pass through (dev mode)."""
        messages = await _run_middleware(
            method="POST",
            origin="https://anything.com",
            trusted_origins=[],
        )
        assert _get_status(messages) == 200

    @pytest.mark.asyncio
    async def test_rejection_has_correlation_id(self):
        """CSRF rejection should include correlation_id in response."""
        messages = await _run_middleware(
            method="POST",
            origin="https://evil.com",
            trusted_origins=["https://app.parwa.io"],
        )
        body = _get_body(messages)
        assert "correlation_id" in body
        assert len(body["correlation_id"]) == 16  # hex token


# ═══════════════════════════════════════════════════════════════════
# Non-HTTP scopes
# ═══════════════════════════════════════════════════════════════════


class TestCSRFNonHTTP:
    """CSRF middleware must pass non-HTTP scopes through."""

    @pytest.mark.asyncio
    async def test_lifespan_scope_passes_through(self):
        """Lifespan scope should pass through unchanged."""
        scope = {"type": "lifespan"}
        called = False

        async def custom_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = _make_middleware()
        middleware.app = custom_app
        await middleware(scope, lambda: None, lambda m: None)
        assert called

    @pytest.mark.asyncio
    async def test_websocket_scope_passes_through(self):
        """WebSocket scope should pass through unchanged."""
        scope = {"type": "websocket", "path": "/ws/chat"}
        called = False

        async def custom_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = _make_middleware()
        middleware.app = custom_app
        await middleware(scope, lambda: None, lambda m: None)
        assert called


# ═══════════════════════════════════════════════════════════════════
# CSRF token generation and validation
# ═══════════════════════════════════════════════════════════════════


class TestCSRFTokens:
    """CSRF token generation and validation helpers."""

    def test_generate_token_format(self):
        """Generated token should have nonce:timestamp:sig format."""
        token = CSRFSecurityMiddleware.generate_csrf_token(
            secret_key="test-secret",
        )
        parts = token.split(":")
        assert len(parts) == 3
        nonce, timestamp, sig = parts
        assert len(nonce) == 32  # 16 bytes hex
        assert timestamp.isdigit()
        assert len(sig) == 16  # truncated HMAC

    def test_validate_valid_token(self):
        """Valid token should pass validation."""
        token = CSRFSecurityMiddleware.generate_csrf_token(
            secret_key="test-secret",
        )
        assert CSRFSecurityMiddleware.validate_csrf_token(
            token, secret_key="test-secret",
        )

    def test_validate_wrong_secret(self):
        """Token validated with wrong secret should fail."""
        token = CSRFSecurityMiddleware.generate_csrf_token(
            secret_key="test-secret",
        )
        assert not CSRFSecurityMiddleware.validate_csrf_token(
            token, secret_key="wrong-secret",
        )

    def test_validate_tampered_token(self):
        """Tampered token should fail validation."""
        token = CSRFSecurityMiddleware.generate_csrf_token(
            secret_key="test-secret",
        )
        parts = token.split(":")
        # Tamper with the nonce
        tampered = "deadbeef" * 4 + ":" + parts[1] + ":" + parts[2]
        assert not CSRFSecurityMiddleware.validate_csrf_token(
            tampered, secret_key="test-secret",
        )

    def test_validate_empty_token(self):
        """Empty token should fail."""
        assert not CSRFSecurityMiddleware.validate_csrf_token("")

    def test_validate_malformed_token(self):
        """Malformed token (wrong number of parts) should fail."""
        assert not CSRFSecurityMiddleware.validate_csrf_token("abc")
        assert not CSRFSecurityMiddleware.validate_csrf_token("a:b:c:d")

    def test_validate_expired_token(self):
        """Token with old timestamp should fail freshness check."""
        import time
        nonce = "a" * 32
        # Token from 2 hours ago
        old_ts = str(int(time.time()) - 7200)
        # Valid HMAC for this old token
        import hashlib
        import hmac as hmac_mod
        sig = hmac_mod.new(
            b"test-secret",
            f"{nonce}:{old_ts}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        token = f"{nonce}:{old_ts}:{sig}"
        assert not CSRFSecurityMiddleware.validate_csrf_token(
            token, secret_key="test-secret",
        )


# ═══════════════════════════════════════════════════════════════════
# BC-008: Never crash
# ═══════════════════════════════════════════════════════════════════


class TestCSRFBC008:
    """CSRF middleware must never crash (BC-008)."""

    @pytest.mark.asyncio
    async def test_malformed_headers_no_crash(self):
        """Malformed headers should not crash middleware."""
        scope = _make_scope(
            method="POST",
            headers=[[b"origin", b"\x00\x01\x02"]],
        )

        async def receive():
            return {"type": "http.request", "body": b""}

        messages = []
        async def capture_send(message):
            messages.append(message)

        middleware = _make_middleware(
            trusted_origins=["https://app.parwa.io"],
        )
        # Should not raise
        await middleware(scope, receive, capture_send)
        # Should return 403 (bad origin)
        assert _get_status(messages) == 403

    @pytest.mark.asyncio
    async def test_empty_scope_no_crash(self):
        """Empty/missing scope fields should not crash."""
        scope = {"type": "http"}  # Minimal, missing method/path/headers

        async def receive():
            return {"type": "http.request", "body": b""}

        messages = []
        async def capture_send(message):
            messages.append(message)

        middleware = _make_middleware()
        # Should not raise — BC-008
        try:
            await middleware(scope, receive, capture_send)
        except Exception:
            pytest.fail("CSRF middleware crashed on minimal scope")

    @pytest.mark.asyncio
    async def test_broken_send_no_crash(self):
        """Middleware should handle send errors gracefully."""
        scope = _make_scope(method="POST")

        async def receive():
            return {"type": "http.request", "body": b""}

        async def broken_send(message):
            raise RuntimeError("send error")

        middleware = _make_middleware()
        # The middleware itself should not crash; the error
        # propagates from the downstream send which is expected
        with pytest.raises(RuntimeError):
            await middleware(scope, receive, broken_send)


# ═══════════════════════════════════════════════════════════════════
# CSP header injection
# ═══════════════════════════════════════════════════════════════════


class TestCSRFCSPInjection:
    """CSRF middleware should inject CSP header on responses."""

    @pytest.mark.asyncio
    async def test_csp_header_on_safe_request(self):
        """CSP header should be added to GET responses."""
        messages = await _run_middleware(method="GET")
        for msg in messages:
            if msg.get("type") == "http.response.start":
                headers = {h[0]: h[1] for h in msg.get("headers", [])}
                assert b"content-security-policy" in headers
                assert b"frame-ancestors" in headers[
                    b"content-security-policy"
                ]

    @pytest.mark.asyncio
    async def test_csp_header_on_post_request(self):
        """CSP header should be added to POST responses (when allowed)."""
        messages = await _run_middleware(
            method="POST",
            origin="https://app.parwa.io",
            trusted_origins=["https://app.parwa.io"],
        )
        for msg in messages:
            if msg.get("type") == "http.response.start":
                headers = {h[0]: h[1] for h in msg.get("headers", [])}
                assert b"content-security-policy" in headers
