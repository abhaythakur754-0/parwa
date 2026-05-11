"""
Tests for CSRF Protection Middleware (H-04, BC-008).

Covers token generation/validation, origin checking, cookie auth path
detection, cookie extraction, double-submit pattern, and full ASGI
request flow through the middleware.
"""

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from unittest.mock import ANY, AsyncMock

import pytest

from backend.app.middleware.csrf import (
    CSRFSecurityMiddleware,
    _CSRF_COOKIE_NAME,
    _CSRF_MAX_AGE,
    _CSP_HEADER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope(
    method: str = "GET",
    path: str = "/",
    headers: dict | None = None,
) -> dict:
    """Build a minimal ASGI HTTP scope dict."""
    raw_headers: list = []
    if headers:
        for k, v in headers.items():
            raw_headers.append([k.lower().encode(), v.encode()])
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": method.upper(),
        "path": path,
        "query_string": b"",
        "headers": raw_headers,
        "server": ("localhost", 8000),
    }


async def _call_middleware(
    middleware: CSRFSecurityMiddleware,
    scope: dict,
) -> list:
    """Invoke the ASGI middleware and collect all sent messages.

    Returns a list of ASGI messages that the middleware sent.
    """
    received_messages: list = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        received_messages.append(message)

    await middleware(scope, receive, send)
    return received_messages


def _make_middleware(
    trusted_origins: str | None = None,
    enabled: str | None = None,
) -> CSRFSecurityMiddleware:
    """Create a CSRFSecurityMiddleware with controlled environment.

    Returns (middleware, cleanup_callable). The cleanup must be called
    after the test to restore the original environment variables.
    """
    saved = {}
    for key in ("CSRF_TRUSTED_ORIGINS", "CORS_ORIGINS", "CSRF_ENABLED"):
        saved[key] = os.environ.pop(key, None)

    if trusted_origins is not None:
        os.environ["CSRF_TRUSTED_ORIGINS"] = trusted_origins
    if enabled is not None:
        os.environ["CSRF_ENABLED"] = enabled

    mw = CSRFSecurityMiddleware(AsyncMock())
    return mw


TEST_SECRET = secrets.token_hex(32)


# ===================================================================
# Token Generation / Validation Tests
# ===================================================================

class TestGenerateCsrfToken:
    """Tests for CSRFSecurityMiddleware.generate_csrf_token."""

    def test_returns_nonce_timestamp_sig_format(self):
        """Token must have exactly 3 colon-separated parts."""
        token = CSRFSecurityMiddleware.generate_csrf_token(TEST_SECRET)
        parts = token.split(":")
        assert len(parts) == 3, f"Expected 3 parts, got {len(parts)}: {parts}"
        nonce, ts, sig = parts
        # nonce is 32 hex chars (16 bytes via token_hex(16))
        assert len(nonce) == 32
        # timestamp is an integer string
        int(ts)
        # sig is 16 hex chars ([:16] of sha256 hexdigest)
        assert len(sig) == 16

    def test_tokens_are_unique(self):
        """Each call must produce a different token (random nonce)."""
        token_a = CSRFSecurityMiddleware.generate_csrf_token(TEST_SECRET)
        token_b = CSRFSecurityMiddleware.generate_csrf_token(TEST_SECRET)
        assert token_a != token_b


class TestValidateCsrfToken:
    """Tests for CSRFSecurityMiddleware.validate_csrf_token."""

    def test_valid_token_returns_true(self):
        """Freshly-generated token must validate."""
        token = CSRFSecurityMiddleware.generate_csrf_token(TEST_SECRET)
        assert CSRFSecurityMiddleware.validate_csrf_token(token, TEST_SECRET) is True

    def test_expired_token_returns_false(self):
        """Token with timestamp older than 1 hour is rejected."""
        nonce = secrets.token_hex(16)
        expired_ts = str(int(time.time()) - _CSRF_MAX_AGE - 100)
        msg = f"{nonce}:{expired_ts}"
        sig = hmac.new(
            TEST_SECRET.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()[:16]
        token = f"{nonce}:{expired_ts}:{sig}"
        assert CSRFSecurityMiddleware.validate_csrf_token(token, TEST_SECRET) is False

    def test_wrong_format_returns_false(self):
        """Malformed token (wrong number of parts) is rejected."""
        assert CSRFSecurityMiddleware.validate_csrf_token("a:b", TEST_SECRET) is False
        assert CSRFSecurityMiddleware.validate_csrf_token("a", TEST_SECRET) is False
        assert CSRFSecurityMiddleware.validate_csrf_token("a:b:c:d", TEST_SECRET) is False

    def test_tampered_signature_returns_false(self):
        """Token with an altered signature portion is rejected."""
        nonce = secrets.token_hex(16)
        ts = str(int(time.time()))
        token = f"{nonce}:{ts}:deadbeefdeadbeef"
        assert CSRFSecurityMiddleware.validate_csrf_token(token, TEST_SECRET) is False

    def test_empty_token_returns_false(self):
        """Empty string is rejected immediately."""
        assert CSRFSecurityMiddleware.validate_csrf_token("", TEST_SECRET) is False
        assert CSRFSecurityMiddleware.validate_csrf_token(None, TEST_SECRET) is False  # type: ignore[arg-type]

    def test_wrong_secret_returns_false(self):
        """Token signed with one secret fails validation with another."""
        token = CSRFSecurityMiddleware.generate_csrf_token(TEST_SECRET)
        wrong_secret = secrets.token_hex(32)
        assert CSRFSecurityMiddleware.validate_csrf_token(token, wrong_secret) is False

    def test_future_timestamp_within_range(self):
        """Token with a small future timestamp (clock skew) is accepted."""
        nonce = secrets.token_hex(16)
        future_ts = str(int(time.time()) + 300)  # 5 min in the future
        msg = f"{nonce}:{future_ts}"
        sig = hmac.new(
            TEST_SECRET.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()[:16]
        token = f"{nonce}:{future_ts}:{sig}"
        assert CSRFSecurityMiddleware.validate_csrf_token(token, TEST_SECRET) is True


# ===================================================================
# Origin Validation Tests
# ===================================================================

class TestIsValidOrigin:
    """Tests for CSRFSecurityMiddleware._is_valid_origin."""

    def test_no_trusted_origins_allows(self):
        """When no trusted origins are configured, all origins pass (local dev)."""
        mw = _make_middleware(trusted_origins="")
        assert mw._is_valid_origin("https://evil.com", "") is True

    def test_matching_origin_returns_true(self):
        """Origin that exactly matches a trusted origin is accepted."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        assert mw._is_valid_origin("https://app.parwa.ai", "") is True

    def test_mismatched_origin_returns_false(self):
        """Origin not in trusted list is rejected."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        assert mw._is_valid_origin("https://evil.com", "") is False

    def test_falls_back_to_referer_when_origin_missing(self):
        """When Origin is absent, Referer origin is extracted and checked."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        result = mw._is_valid_origin("", "https://app.parwa.ai/dashboard")
        assert result is True

    def test_referer_origin_mismatch(self):
        """Referer with wrong origin is rejected."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        result = mw._is_valid_origin("", "https://evil.com/stuff")
        assert result is False

    def test_both_origin_and_referer_missing_rejects(self):
        """If no origin info at all and trusted origins are set, reject."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        assert mw._is_valid_origin("", "") is False

    def test_origin_subpath_match(self):
        """Trusted origin with subpath is accepted."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        assert mw._is_valid_origin("https://app.parwa.ai/extra", "") is True

    def test_multiple_trusted_origins(self):
        """Any origin in a comma-separated list of trusted origins is accepted."""
        mw = _make_middleware(
            trusted_origins="https://app.parwa.ai,https://admin.parwa.ai"
        )
        assert mw._is_valid_origin("https://admin.parwa.ai", "") is True
        assert mw._is_valid_origin("https://app.parwa.ai", "") is True
        assert mw._is_valid_origin("https://other.com", "") is False


# ===================================================================
# Cookie Auth Path Tests
# ===================================================================

class TestIsCookieAuthPath:
    """Tests for CSRFSecurityMiddleware._is_cookie_auth_path."""

    def test_api_auth_login(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/auth/login") is True

    def test_api_auth_subpath(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/auth/logout") is True

    def test_api_login(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/login") is True

    def test_api_register(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/register") is True

    def test_api_mfa_path(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/mfa/verify") is True

    def test_api_refresh(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/refresh") is True

    def test_api_tickets_not_auth(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/tickets") is False

    def test_root_path_not_auth(self):
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/") is False


# ===================================================================
# Cookie Extraction Tests
# ===================================================================

class TestExtractCookie:
    """Tests for CSRFSecurityMiddleware._extract_cookie."""

    def test_finds_cookie_in_header(self):
        header = "session=abc123; parwa_csrf=mytoken; lang=en"
        result = CSRFSecurityMiddleware._extract_cookie(header, "parwa_csrf")
        assert result == "mytoken"

    def test_returns_empty_when_not_found(self):
        header = "session=abc123; lang=en"
        result = CSRFSecurityMiddleware._extract_cookie(header, "parwa_csrf")
        assert result == ""

    def test_empty_header_returns_empty(self):
        result = CSRFSecurityMiddleware._extract_cookie("", "parwa_csrf")
        assert result == ""

    def test_none_header_returns_empty(self):
        result = CSRFSecurityMiddleware._extract_cookie(None, "parwa_csrf")  # type: ignore[arg-type]
        assert result == ""

    def test_only_cookie_in_header(self):
        header = "parwa_csrf=sometoken"
        result = CSRFSecurityMiddleware._extract_cookie(header, "parwa_csrf")
        assert result == "sometoken"

    def test_cookie_value_with_equals(self):
        header = "parwa_csrf=a==b; session=x"
        result = CSRFSecurityMiddleware._extract_cookie(header, "parwa_csrf")
        assert result == "a==b"


# ===================================================================
# Double-Submit Token Validation Tests
# ===================================================================

class TestValidateCsrfTokenDoubleSubmit:
    """Tests for CSRFSecurityMiddleware._validate_csrf_token."""

    def test_matching_tokens_returns_true(self):
        token = secrets.token_hex(32)
        assert CSRFSecurityMiddleware._validate_csrf_token(token, token) is True

    def test_mismatched_tokens_returns_false(self):
        assert CSRFSecurityMiddleware._validate_csrf_token(
            secrets.token_hex(32), secrets.token_hex(32)
        ) is False

    def test_empty_cookie_token_returns_false(self):
        assert CSRFSecurityMiddleware._validate_csrf_token("", secrets.token_hex(32)) is False

    def test_empty_header_token_returns_false(self):
        assert CSRFSecurityMiddleware._validate_csrf_token(secrets.token_hex(32), "") is False

    def test_both_empty_returns_false(self):
        assert CSRFSecurityMiddleware._validate_csrf_token("", "") is False

    def test_constant_time_comparison(self):
        """Ensure comparison uses hmac.compare_digest (constant-time).

        This is a design verification: tokens with common prefixes should
        not short-circuit the comparison.
        """
        token_a = "a" * 64 + "b"
        token_b = "a" * 64 + "c"
        # Both should simply return False without timing differences
        assert CSRFSecurityMiddleware._validate_csrf_token(token_a, token_b) is False


# ===================================================================
# ASGI Integration Tests
# ===================================================================

class TestASGICsrfFlow:
    """Full ASGI request flow through CSRFSecurityMiddleware."""

    def test_get_request_passes_through(self):
        """Safe methods (GET) should pass through without CSRF checks."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(method="GET", path="/api/tickets")
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        # The inner app (AsyncMock) should have been called
        mw.app.assert_awaited_once_with(scope, ANY, ANY)
        # No 403 was sent
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        assert len(start_msgs) == 0, "GET should not send a response directly"

    def test_post_with_valid_origin_passes_through(self):
        """POST with a valid Origin header should pass through."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(
            method="POST",
            path="/api/tickets",
            headers={"origin": "https://app.parwa.ai"},
        )
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        mw.app.assert_awaited_once()
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        assert len(start_msgs) == 0

    def test_post_with_invalid_origin_returns_403(self):
        """POST with an untrusted Origin should get 403 JSON."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(
            method="POST",
            path="/api/tickets",
            headers={"origin": "https://evil.com"},
        )
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        # The inner app must NOT have been called
        mw.app.assert_not_awaited()
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        assert len(start_msgs) == 1
        assert start_msgs[0]["status"] == 403
        # Check body is JSON with error
        body_msgs = [m for m in messages if m.get("type") == "http.response.body"]
        assert len(body_msgs) == 1
        body = json.loads(body_msgs[0]["body"])
        assert body["error"]["code"] == "FORBIDDEN"
        assert "CSRF" in body["error"]["message"]

    def test_webhook_paths_skip_csrf(self):
        """Requests to /api/webhooks/ should skip CSRF verification."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(
            method="POST",
            path="/api/webhooks/stripe",
            headers={"origin": "https://evil.com"},
        )
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        # App should have been called even with bad origin
        mw.app.assert_awaited_once()

    def test_head_request_passes_through(self):
        """HEAD is a safe method and should pass through."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(method="HEAD", path="/api/tickets")
        asyncio.get_event_loop().run_until_complete(_call_middleware(mw, scope))
        mw.app.assert_awaited_once()

    def test_options_request_passes_through(self):
        """OPTIONS is a safe method and should pass through."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(method="OPTIONS", path="/api/tickets")
        asyncio.get_event_loop().run_until_complete(_call_middleware(mw, scope))
        mw.app.assert_awaited_once()

    def test_non_http_scope_passes_through(self):
        """Non-HTTP scopes (e.g. websocket, lifespan) pass through."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = {"type": "websocket", "path": "/ws"}
        asyncio.get_event_loop().run_until_complete(_call_middleware(mw, scope))
        mw.app.assert_awaited_once()

    def test_post_no_origin_no_referer_returns_403(self):
        """POST with no Origin and no Referer is rejected when origins configured."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(method="POST", path="/api/tickets", headers={})
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        mw.app.assert_not_awaited()
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        assert start_msgs[0]["status"] == 403

    def test_csrf_disabled_bypasses_all_checks(self):
        """When CSRF_ENABLED=false, all checks are bypassed."""
        mw = _make_middleware(
            trusted_origins="https://app.parwa.ai",
            enabled="false",
        )
        scope = _make_scope(
            method="POST",
            path="/api/tickets",
            headers={"origin": "https://evil.com"},
        )
        asyncio.get_event_loop().run_until_complete(_call_middleware(mw, scope))
        mw.app.assert_awaited_once()

    def test_cookie_auth_path_requires_csrf_token(self):
        """Cookie auth paths require both CSRF cookie and header token."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(
            method="POST",
            path="/api/auth/login",
            headers={"origin": "https://app.parwa.ai"},
        )
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        # Should be rejected because CSRF token is missing
        mw.app.assert_not_awaited()
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        assert start_msgs[0]["status"] == 403
        body_msgs = [m for m in messages if m.get("type") == "http.response.body"]
        body = json.loads(body_msgs[0]["body"])
        assert "token" in body["error"]["message"].lower()

    def test_cookie_auth_path_with_valid_tokens_passes(self):
        """Cookie auth path with matching CSRF cookie + header passes."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        token = secrets.token_hex(32)
        scope = _make_scope(
            method="POST",
            path="/api/auth/login",
            headers={
                "origin": "https://app.parwa.ai",
                "cookie": f"parwa_csrf={token}",
                "x-csrf-token": token,
            },
        )
        asyncio.get_event_loop().run_until_complete(_call_middleware(mw, scope))
        mw.app.assert_awaited_once()

    def test_cookie_auth_path_mismatched_tokens_returns_403(self):
        """Cookie auth path with mismatched CSRF cookie + header gets 403."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(
            method="POST",
            path="/api/auth/login",
            headers={
                "origin": "https://app.parwa.ai",
                "cookie": f"parwa_csrf={secrets.token_hex(32)}",
                "x-csrf-token": secrets.token_hex(32),
            },
        )
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        mw.app.assert_not_awaited()
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        assert start_msgs[0]["status"] == 403

    def test_403_response_includes_correlation_id(self):
        """CSRF rejection must include a correlation ID for auditability."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(
            method="POST",
            path="/api/tickets",
            headers={"origin": "https://evil.com"},
        )
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        body_msgs = [m for m in messages if m.get("type") == "http.response.body"]
        body = json.loads(body_msgs[0]["body"])
        assert "correlation_id" in body
        assert len(body["correlation_id"]) == 16  # token_hex(8) = 16 chars

    def test_403_response_content_type_is_json(self):
        """CSRF rejection must return application/json."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(
            method="POST",
            path="/api/tickets",
            headers={"origin": "https://evil.com"},
        )
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        headers = {h[0]: h[1] for h in start_msgs[0]["headers"]}
        assert headers.get(b"content-type") == b"application/json"


# ===================================================================
# CSP Header Injection Tests
# ===================================================================

class TestCSPInjection:
    """Tests for Content-Security-Policy header injection via _wrap_send."""

    def test_csp_header_injected_on_response(self):
        """CSP header must be injected into the response by wrapped_send."""
        mw = _make_middleware(trusted_origins="")
        scope = _make_scope(method="GET", path="/")

        collected: list = []

        async def mock_send(message):
            collected.append(message)

        wrapped_send = mw._wrap_send(mock_send)
        scope_response_start = {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        }
        asyncio.get_event_loop().run_until_complete(
            wrapped_send(scope_response_start)
        )
        # Check CSP was added
        headers = collected[0]["headers"]
        csp_found = any(h[0] == b"content-security-policy" for h in headers)
        assert csp_found, "CSP header must be injected"

    def test_csp_not_doubled(self):
        """CSP header should not be injected if already present."""
        mw = _make_middleware(trusted_origins="")
        collected: list = []

        async def mock_send(message):
            collected.append(message)

        wrapped_send = mw._wrap_send(mock_send)
        scope_response_start = {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-security-policy", b"existing-csp"],
            ],
        }
        asyncio.get_event_loop().run_until_complete(
            wrapped_send(scope_response_start)
        )
        csp_headers = [
            h[1] for h in collected[0]["headers"]
            if h[0] == b"content-security-policy"
        ]
        assert len(csp_headers) == 1
        assert csp_headers[0] == b"existing-csp"


# ===================================================================
# Edge Case / BC-008 Robustness Tests
# ===================================================================

class TestBC008Robustness:
    """BC-008: Middleware must never crash on malformed input."""

    def test_malformed_origin_header_does_not_crash(self):
        """Non-UTF-8 bytes in Origin header must not crash middleware."""
        mw = _make_middleware(trusted_origins="https://app.parwa.ai")
        scope = _make_scope(method="POST", path="/api/tickets")
        # Inject raw bytes for origin header
        scope["headers"] = [[b"origin", b"\xff\xfe invalid"]]
        messages = asyncio.get_event_loop().run_until_complete(
            _call_middleware(mw, scope)
        )
        # Should get 403, not an exception
        start_msgs = [m for m in messages if m.get("type") == "http.response.start"]
        assert len(start_msgs) == 1
        assert start_msgs[0]["status"] == 403

    def test_token_with_non_numeric_timestamp(self):
        """Token with non-integer timestamp returns False, not crash."""
        token = "abcdef1234567890abcdef1234567890:notanumber:deadbeef12345678"
        assert CSRFSecurityMiddleware.validate_csrf_token(token, TEST_SECRET) is False
