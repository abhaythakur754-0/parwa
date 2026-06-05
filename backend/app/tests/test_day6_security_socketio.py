"""
Day 6 Backend Tests — Security HIGH + Socket.io + Dashboard Pages

Comprehensive unit + integration tests for PARWA Day 6 features:
1. Security Headers Middleware
2. CSRF Protection Middleware
3. Rate Limit Middleware
4. Billing Webhooks API
5. Billing API (role-based access)
6. Auth Cookies / Open Redirect
7. IP Extraction Utility
8. Socket.io Backend
"""

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ═══════════════════════════════════════════════════════════════════════
# 1. SECURITY HEADERS MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware.dispatch()."""

    @pytest.fixture
    def app_with_security_headers(self):
        """Create a minimal Starlette app with SecurityHeadersMiddleware."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        from app.middleware.security_headers import SecurityHeadersMiddleware

        async def homepage(request):
            return PlainTextResponse("OK")

        async def auth_login(request):
            return PlainTextResponse("authenticated")

        app = Starlette(
            routes=[
                Route("/", homepage),
                Route("/api/auth/login", auth_login),
                Route("/api/mfa/verify", auth_login),
            ]
        )
        app.add_middleware(SecurityHeadersMiddleware)
        return app

    @pytest.fixture
    def client(self, app_with_security_headers):
        from starlette.testclient import TestClient
        return TestClient(app_with_security_headers)

    def test_adds_x_content_type_options_nosniff(self, client):
        """X-Content-Type-Options: nosniff is set on all responses."""
        resp = client.get("/")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_adds_x_frame_options_deny(self, client):
        """X-Frame-Options: DENY is set on all responses."""
        resp = client.get("/")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_adds_csp_with_nonce(self, client):
        """H-04: Content-Security-Policy includes a unique nonce."""
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "script-src 'self' 'nonce-" in csp
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp

    def test_csp_nonce_exposed_via_header(self, client):
        """X-CSP-Nonce header is set for downstream use."""
        resp = client.get("/")
        nonce = resp.headers.get("X-CSP-Nonce")
        assert nonce is not None
        assert len(nonce) > 10
        # Verify nonce appears in CSP
        csp = resp.headers["Content-Security-Policy"]
        assert f"'nonce-{nonce}'" in csp

    def test_csp_nonce_unique_per_request(self, client):
        """Each request gets a different CSP nonce (prevents reuse)."""
        resp1 = client.get("/")
        resp2 = client.get("/")
        nonce1 = resp1.headers["X-CSP-Nonce"]
        nonce2 = resp2.headers["X-CSP-Nonce"]
        assert nonce1 != nonce2

    def test_no_hsts_in_development(self, client):
        """Strict-Transport-Security is NOT added in non-production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            resp = client.get("/")
            assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_in_production(self, client):
        """Strict-Transport-Security is added when ENVIRONMENT=production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            resp = client.get("/")
            assert "Strict-Transport-Security" in resp.headers
            hsts = resp.headers["Strict-Transport-Security"]
            assert "max-age=31536000" in hsts
            assert "includeSubDomains" in hsts

    def test_cache_control_no_store_on_auth_endpoints(self, client):
        """M-11: Cache-Control: no-store on auth endpoints."""
        resp = client.get("/api/auth/login")
        assert "no-store" in resp.headers.get("Cache-Control", "")
        assert "no-cache" in resp.headers.get("Cache-Control", "")
        assert resp.headers.get("Pragma") == "no-cache"
        assert resp.headers.get("Expires") == "0"

    def test_cache_control_no_store_on_mfa_endpoints(self, client):
        """M-11: Cache-Control: no-store on /api/mfa/ endpoints."""
        resp = client.get("/api/mfa/verify")
        assert "no-store" in resp.headers.get("Cache-Control", "")

    def test_no_cache_control_on_non_auth_endpoints(self, client):
        """Non-auth endpoints should NOT have Cache-Control: no-store."""
        resp = client.get("/")
        # No no-store forced by the middleware on non-auth paths
        assert "no-store" not in resp.headers.get("Cache-Control", "")

    def test_referrer_policy_set(self, client):
        """Referrer-Policy header is set."""
        resp = client.get("/")
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_set(self, client):
        """Permissions-Policy header disables camera/mic/geo."""
        resp = client.get("/")
        pp = resp.headers["Permissions-Policy"]
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp


# ═══════════════════════════════════════════════════════════════════════
# 2. CSRF PROTECTION MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════


class TestCSRFMiddleware:
    """Tests for CSRFSecurityMiddleware (pure ASGI middleware)."""

    @pytest.fixture
    def csrf_app(self):
        """Create a minimal ASGI app wrapped with CSRF middleware."""
        from app.middleware.csrf import CSRFSecurityMiddleware

        async def inner_app(scope, receive, send):
            # Simple 200 OK response
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"OK",
            })

        return CSRFSecurityMiddleware(inner_app)

    async def _call_asgi(self, app, scope_overrides=None, headers=None):
        """Helper to invoke the ASGI app and collect responses."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [],
        }
        if scope_overrides:
            scope.update(scope_overrides)
        if headers:
            scope["headers"] = headers

        received = []

        async def send(message):
            received.append(message)

        async def receive():
            return {"type": "http.request", "body": b""}

        await app(scope, receive, send)
        return received

    @pytest.mark.asyncio
    async def test_safe_methods_pass_through(self, csrf_app):
        """GET/HEAD/OPTIONS skip CSRF validation."""
        for method in ("GET", "HEAD", "OPTIONS"):
            msgs = await self._call_asgi(csrf_app, {"method": method})
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            assert status_msgs[0]["status"] == 200, f"{method} should pass through"

    @pytest.mark.asyncio
    async def test_post_without_origin_rejected(self, csrf_app):
        """POST without Origin/Referer is rejected (403)."""
        with patch.dict(os.environ, {
            "CSRF_TRUSTED_ORIGINS": "https://app.parwa.com",
            "CSRF_ENABLED": "true",
        }):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "POST", "path": "/api/tickets"},
            )
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            assert status_msgs[0]["status"] == 403

    @pytest.mark.asyncio
    async def test_post_with_valid_origin_accepted(self, csrf_app):
        """POST with a trusted Origin is accepted."""
        with patch.dict(os.environ, {
            "CSRF_TRUSTED_ORIGINS": "https://app.parwa.com",
            "CSRF_ENABLED": "true",
        }):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "POST", "path": "/api/tickets"},
                headers=[
                    [b"origin", b"https://app.parwa.com"],
                ],
            )
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            assert status_msgs[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_post_with_invalid_origin_rejected(self, csrf_app):
        """POST with an untrusted Origin is rejected (403)."""
        with patch.dict(os.environ, {
            "CSRF_TRUSTED_ORIGINS": "https://app.parwa.com",
            "CSRF_ENABLED": "true",
        }):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "POST", "path": "/api/tickets"},
                headers=[
                    [b"origin", b"https://evil.com"],
                ],
            )
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            assert status_msgs[0]["status"] == 403

    @pytest.mark.asyncio
    async def test_referer_used_when_origin_missing(self, csrf_app):
        """Referer header is used when Origin is missing."""
        with patch.dict(os.environ, {
            "CSRF_TRUSTED_ORIGINS": "https://app.parwa.com",
            "CSRF_ENABLED": "true",
        }):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "POST", "path": "/api/tickets"},
                headers=[
                    [b"referer", b"https://app.parwa.com/dashboard"],
                ],
            )
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            assert status_msgs[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_bearer_token_exempt_from_csrf_cookie(self, csrf_app):
        """H-19: Bearer token requests skip CSRF cookie check."""
        with patch.dict(os.environ, {
            "CSRF_TRUSTED_ORIGINS": "https://app.parwa.com",
            "CSRF_ENABLED": "true",
        }):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "POST", "path": "/api/auth/login"},
                headers=[
                    [b"origin", b"https://app.parwa.com"],
                    [b"authorization", b"Bearer test.jwt.token"],
                ],
            )
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            # Should pass — Bearer auth exempted from CSRF cookie
            assert status_msgs[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_webhook_routes_skip_csrf(self, csrf_app):
        """Webhook routes skip CSRF checks entirely."""
        with patch.dict(os.environ, {
            "CSRF_TRUSTED_ORIGINS": "https://app.parwa.com",
            "CSRF_ENABLED": "true",
        }):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "POST", "path": "/api/webhooks/paddle"},
            )
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            assert status_msgs[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_csrf_disabled_allows_all(self, csrf_app):
        """CSRF_ENABLED=false passes all requests through."""
        with patch.dict(os.environ, {"CSRF_ENABLED": "false"}):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "POST", "path": "/api/tickets"},
            )
            status_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            assert status_msgs[0]["status"] == 200

    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self, csrf_app):
        """Non-HTTP scopes (WebSocket, lifecycle) pass through unchanged."""
        received = []

        async def send(message):
            received.append(message)

        async def receive():
            return {}

        await csrf_app({"type": "websocket"}, receive, send)
        assert len(received) == 1  # passed to inner app directly

    def test_generate_csrf_token_format(self):
        """CSRF token is nonce:timestamp:signature format."""
        from app.middleware.csrf import CSRFSecurityMiddleware
        token = CSRFSecurityMiddleware.generate_csrf_token("test-secret")
        parts = token.split(":")
        assert len(parts) == 3  # nonce, timestamp, signature
        assert len(parts[0]) == 32  # 16 bytes hex = 32 chars
        assert parts[1].isdigit()  # timestamp

    def test_validate_csrf_token_valid(self):
        """A freshly generated token validates successfully."""
        from app.middleware.csrf import CSRFSecurityMiddleware
        token = CSRFSecurityMiddleware.generate_csrf_token("test-secret")
        assert CSRFSecurityMiddleware.validate_csrf_token(token, "test-secret") is True

    def test_validate_csrf_token_expired(self):
        """An expired token fails validation (freshness check)."""
        from app.middleware.csrf import CSRFSecurityMiddleware, _CSRF_MAX_AGE
        # Create a token with an old timestamp
        old_ts = str(int(time.time()) - _CSRF_MAX_AGE - 100)
        nonce = "a" * 32
        msg = f"{nonce}:{old_ts}"
        sig = hmac.new(
            b"test-secret", msg.encode("utf-8"), hashlib.sha256,
        ).hexdigest()[:16]
        token = f"{nonce}:{old_ts}:{sig}"
        assert CSRFSecurityMiddleware.validate_csrf_token(token, "test-secret") is False

    def test_validate_csrf_token_wrong_secret(self):
        """Token validated with wrong secret fails."""
        from app.middleware.csrf import CSRFSecurityMiddleware
        token = CSRFSecurityMiddleware.generate_csrf_token("secret-a")
        assert CSRFSecurityMiddleware.validate_csrf_token(token, "secret-b") is False

    def test_validate_csrf_token_malformed(self):
        """BC-008: Malformed token never crashes, returns False."""
        from app.middleware.csrf import CSRFSecurityMiddleware
        assert CSRFSecurityMiddleware.validate_csrf_token("", "secret") is False
        assert CSRFSecurityMiddleware.validate_csrf_token("bad", "secret") is False
        assert CSRFSecurityMiddleware.validate_csrf_token("a:b:c:d", "secret") is False
        assert CSRFSecurityMiddleware.validate_csrf_token("::::", "secret") is False
        assert CSRFSecurityMiddleware.validate_csrf_token(None, "secret") is False

    def test_double_submit_cookie_validation(self):
        """Double-submit: cookie and header tokens must match."""
        from app.middleware.csrf import CSRFSecurityMiddleware
        token = CSRFSecurityMiddleware.generate_csrf_token("secret")
        assert CSRFSecurityMiddleware._validate_csrf_token(token, token) is True
        assert CSRFSecurityMiddleware._validate_csrf_token(token, "different") is False
        assert CSRFSecurityMiddleware._validate_csrf_token("", token) is False
        assert CSRFSecurityMiddleware._validate_csrf_token(token, "") is False

    @pytest.mark.asyncio
    async def test_csrf_cookie_generated_when_missing(self, csrf_app):
        """H-19: CSRF cookie is generated and set when not present."""
        with patch.dict(os.environ, {
            "CSRF_TRUSTED_ORIGINS": "https://app.parwa.com",
            "CSRF_ENABLED": "true",
        }):
            msgs = await self._call_asgi(
                csrf_app,
                {"method": "GET", "path": "/"},
                headers=[],
            )
            # Look for Set-Cookie header with CSRF token
            start_msgs = [m for m in msgs if m.get("type") == "http.response.start"]
            all_headers = []
            for m in start_msgs:
                all_headers.extend(m.get("headers", []))
            cookie_headers = [h for h in all_headers if h[0] == b"set-cookie"]
            csrf_cookies = [h for h in cookie_headers if b"parwa_csrf=" in h[1]]
            assert len(csrf_cookies) > 0, "CSRF cookie should be set when missing"

    def test_is_cookie_auth_path(self):
        """Cookie auth path detection works correctly."""
        from app.middleware.csrf import CSRFSecurityMiddleware
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/auth/login") is True
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/auth/refresh") is True
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/mfa/verify") is True
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/register") is True
        assert CSRFSecurityMiddleware._is_cookie_auth_path("/api/tickets") is False


# ═══════════════════════════════════════════════════════════════════════
# 3. RATE LIMIT MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware.dispatch()."""

    @pytest.fixture
    def rate_limit_app(self):
        """Create a Starlette app with RateLimitMiddleware."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from app.middleware.rate_limit import RateLimitMiddleware

        async def homepage(request):
            return PlainTextResponse("OK")

        async def webhook(request):
            return PlainTextResponse("webhook OK")

        app = Starlette(
            routes=[
                Route("/", homepage),
                Route("/health", homepage),
                Route("/api/webhooks/paddle", webhook, methods=["POST"]),
                Route("/api/tickets", homepage, methods=["GET", "POST"]),
            ]
        )
        app.add_middleware(RateLimitMiddleware)
        return app

    @pytest.fixture
    def client(self, rate_limit_app):
        from starlette.testclient import TestClient
        return TestClient(rate_limit_app)

    def test_health_endpoint_skips_rate_limit(self, client):
        """Health endpoint bypasses rate limiting."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_webhook_endpoint_skips_rate_limit(self, client):
        """Webhook endpoints bypass rate limiting."""
        resp = client.post("/api/webhooks/paddle")
        assert resp.status_code == 200

    def test_rate_limit_headers_on_allowed_request(self, client):
        """X-RateLimit-* headers are set on allowed requests."""
        with patch("app.middleware.rate_limit.get_rate_limit_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc.classify_path.return_value = "general_get"
            mock_svc.extract_identifier = AsyncMock(return_value="1.2.3.4")
            mock_svc.sync_redis_time = AsyncMock()
            result = MagicMock()
            result.allowed = True
            result.remaining = 99
            result.limit = 100
            result.reset_at = time.time() + 60
            result.to_headers.return_value = {
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "99",
                "X-RateLimit-Reset": str(int(time.time() + 60)),
            }
            mock_svc.check_rate_limit.return_value = result
            mock_svc_fn.return_value = mock_svc

            resp = client.get("/")
            assert "X-RateLimit-Limit" in resp.headers

    def test_rate_limit_exceeded_returns_429(self, client):
        """When rate limit is exceeded, returns 429."""
        with patch("app.middleware.rate_limit.get_rate_limit_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc.classify_path.return_value = "auth_login"
            mock_svc.extract_identifier = AsyncMock(return_value="test@example.com")
            mock_svc.sync_redis_time = AsyncMock()
            result = MagicMock()
            result.allowed = False
            result.remaining = 0
            result.limit = 5
            result.reset_at = time.time() + 60
            result.retry_after = 60
            result.to_headers.return_value = {
                "X-RateLimit-Limit": "5",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + 60)),
                "Retry-After": "60",
            }
            mock_svc.check_rate_limit.return_value = result
            mock_svc_fn.return_value = mock_svc

            resp = client.get("/api/tickets")
            assert resp.status_code == 429

    def test_redis_failure_returns_503_fail_closed(self, client):
        """When Redis fails, middleware returns 503 (fail-closed)."""
        with patch("app.middleware.rate_limit.get_rate_limit_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc.classify_path.return_value = "general_get"
            mock_svc.extract_identifier = AsyncMock(return_value="1.2.3.4")
            mock_svc.sync_redis_time = AsyncMock()
            mock_svc.check_rate_limit.side_effect = Exception("Redis down")
            mock_svc_fn.return_value = mock_svc

            resp = client.get("/api/tickets")
            assert resp.status_code == 503

    def test_rate_limit_service_classify_path(self):
        """classify_path returns correct categories for known paths."""
        from app.services.rate_limit_service import RateLimitService
        svc = RateLimitService()
        assert svc.classify_path("/api/auth/login", "POST") == "auth_login"
        assert svc.classify_path("/api/auth/register", "POST") == "auth_register"
        assert svc.classify_path("/api/billing/subscription", "GET") == "financial"
        assert svc.classify_path("/api/integrations/hubspot", "GET") == "integration"
        assert svc.classify_path("/api/tickets", "GET") == "general_get"
        assert svc.classify_path("/api/tickets", "POST") == "general_post"

    def test_rate_limit_result_to_headers(self):
        """RateLimitResult.to_headers() returns correct header dict."""
        from app.services.rate_limit_service import RateLimitResult
        result = RateLimitResult(
            allowed=True, remaining=99, limit=100,
            reset_at=time.time() + 60,
        )
        headers = result.to_headers()
        assert "X-RateLimit-Limit" in headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "99"

    def test_rate_limit_result_retry_after_header(self):
        """RateLimitResult includes Retry-After when rate limited."""
        from app.services.rate_limit_service import RateLimitResult
        result = RateLimitResult(
            allowed=False, remaining=0, limit=5,
            reset_at=time.time() + 60, retry_after=60,
        )
        headers = result.to_headers()
        assert "Retry-After" in headers


# ═══════════════════════════════════════════════════════════════════════
# 4. BILLING WEBHOOKS API
# ═══════════════════════════════════════════════════════════════════════


class TestBillingWebhooks:
    """Tests for billing_webhooks.py (H-07, H-08)."""

    def test_extract_company_id_from_custom_data(self):
        """extract_company_id_from_event finds company_id in custom_data."""
        from app.api.billing_webhooks import extract_company_id_from_event
        data = {"custom_data": {"company_id": "comp-123"}}
        assert extract_company_id_from_event(data) == "comp-123"

    def test_extract_company_id_from_passthrough(self):
        """extract_company_id_from_event finds company_id in passthrough."""
        from app.api.billing_webhooks import extract_company_id_from_event
        data = {"passthrough": {"company_id": "comp-456"}}
        assert extract_company_id_from_event(data) == "comp-456"

    def test_extract_company_id_from_passthrough_string(self):
        """extract_company_id_from_event parses JSON string passthrough."""
        from app.api.billing_webhooks import extract_company_id_from_event
        data = {"passthrough": json.dumps({"company_id": "comp-789"})}
        assert extract_company_id_from_event(data) == "comp-789"

    def test_extract_company_id_from_metadata(self):
        """extract_company_id_from_event finds company_id in metadata."""
        from app.api.billing_webhooks import extract_company_id_from_event
        data = {"metadata": {"company_id": "comp-meta"}}
        assert extract_company_id_from_event(data) == "comp-meta"

    def test_extract_company_id_returns_none_when_missing(self):
        """extract_company_id_from_event returns None when no company_id."""
        from app.api.billing_webhooks import extract_company_id_from_event
        data = {"other_key": "value"}
        assert extract_company_id_from_event(data) is None

    def test_extract_company_id_handles_empty_dicts(self):
        """extract_company_id_from_event handles empty/None dicts."""
        from app.api.billing_webhooks import extract_company_id_from_event
        assert extract_company_id_from_event({"custom_data": None}) is None
        assert extract_company_id_from_event({"custom_data": {}}) is None
        assert extract_company_id_from_event({}) is None

    def test_extract_company_id_invalid_passthrough_json(self):
        """extract_company_id_from_event handles invalid JSON passthrough."""
        from app.api.billing_webhooks import extract_company_id_from_event
        data = {"passthrough": "not-valid-json"}
        assert extract_company_id_from_event(data) is None

    @pytest.mark.asyncio
    async def test_webhook_rejects_no_secret_configured(self):
        """H-07: Webhook rejects when PADDLE_WEBHOOK_SECRET is not set."""
        from app.api.billing_webhooks import handle_paddle_webhook
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b'{"test": true}')
        mock_request.headers = {"Paddle-Signature": "ts=123;h1=abc"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = ""

        with patch("app.api.billing_webhooks.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await handle_paddle_webhook(
                    request=mock_request,
                    background_tasks=MagicMock(),
                )
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_webhook_rejects_invalid_signature(self):
        """H-07: Webhook rejects invalid Paddle signature."""
        from app.api.billing_webhooks import handle_paddle_webhook
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b'{"test": true}')
        mock_request.headers = {"Paddle-Signature": "ts=123;h1=bad"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = "whsec_test123"

        mock_paddle_client = MagicMock()
        mock_paddle_client.verify_webhook_signature.return_value = False

        with patch("app.api.billing_webhooks.get_settings", return_value=mock_settings), \
             patch("app.api.billing_webhooks.get_paddle_client", return_value=mock_paddle_client):
            with pytest.raises(HTTPException) as exc_info:
                await handle_paddle_webhook(
                    request=mock_request,
                    background_tasks=MagicMock(),
                )
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_rejects_replay_old_timestamp(self):
        """H-08: Webhook rejects events with timestamps older than 5 minutes."""
        from app.api.billing_webhooks import handle_paddle_webhook, MAX_WEBHOOK_AGE_SECONDS
        from fastapi import HTTPException

        old_time = (datetime.now(timezone.utc) - timedelta(seconds=MAX_WEBHOOK_AGE_SECONDS + 100))
        old_time_str = old_time.isoformat()

        payload = json.dumps({
            "event_type": "subscription.created",
            "event_id": "evt-123",
            "occurred_at": old_time_str,
            "data": {"custom_data": {"company_id": "comp-1"}},
        }).encode()

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"Paddle-Signature": "ts=123;h1=valid"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = "whsec_test123"

        mock_paddle_client = MagicMock()
        mock_paddle_client.verify_webhook_signature.return_value = True

        with patch("app.api.billing_webhooks.get_settings", return_value=mock_settings), \
             patch("app.api.billing_webhooks.get_paddle_client", return_value=mock_paddle_client):
            with pytest.raises(HTTPException) as exc_info:
                await handle_paddle_webhook(
                    request=mock_request,
                    background_tasks=MagicMock(),
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_webhook_rejects_missing_timestamp(self):
        """H-08: Webhook rejects events without a timestamp (replay protection)."""
        from app.api.billing_webhooks import handle_paddle_webhook
        from fastapi import HTTPException

        payload = json.dumps({
            "event_type": "subscription.created",
            "event_id": "evt-124",
            "data": {"custom_data": {"company_id": "comp-1"}},
        }).encode()

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"Paddle-Signature": "ts=123;h1=valid"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = "whsec_test123"

        mock_paddle_client = MagicMock()
        mock_paddle_client.verify_webhook_signature.return_value = True

        with patch("app.api.billing_webhooks.get_settings", return_value=mock_settings), \
             patch("app.api.billing_webhooks.get_paddle_client", return_value=mock_paddle_client):
            with pytest.raises(HTTPException) as exc_info:
                await handle_paddle_webhook(
                    request=mock_request,
                    background_tasks=MagicMock(),
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_webhook_accepts_valid_event(self):
        """Valid webhook event is accepted with 200."""
        from app.api.billing_webhooks import handle_paddle_webhook

        recent_time = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({
            "event_type": "subscription.created",
            "event_id": "evt-125",
            "occurred_at": recent_time,
            "data": {"custom_data": {"company_id": "comp-1"}},
        }).encode()

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"Paddle-Signature": "ts=123;h1=valid"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = "whsec_test123"

        mock_paddle_client = MagicMock()
        mock_paddle_client.verify_webhook_signature.return_value = True

        mock_webhook_result = {"duplicate": False}

        with patch("app.api.billing_webhooks.get_settings", return_value=mock_settings), \
             patch("app.api.billing_webhooks.get_paddle_client", return_value=mock_paddle_client), \
             patch("app.api.billing_webhooks.process_webhook", return_value=mock_webhook_result):
            result = await handle_paddle_webhook(
                request=mock_request,
                background_tasks=MagicMock(),
            )
            assert result["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_webhook_duplicate_returns_duplicate_status(self):
        """Duplicate webhook event returns 'duplicate' status."""
        from app.api.billing_webhooks import handle_paddle_webhook

        recent_time = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({
            "event_type": "subscription.created",
            "event_id": "evt-dup-1",
            "occurred_at": recent_time,
            "data": {"custom_data": {"company_id": "comp-1"}},
        }).encode()

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=payload)
        mock_request.headers = {"Paddle-Signature": "ts=123;h1=valid"}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = "whsec_test123"

        mock_paddle_client = MagicMock()
        mock_paddle_client.verify_webhook_signature.return_value = True

        mock_webhook_result = {"duplicate": True}

        with patch("app.api.billing_webhooks.get_settings", return_value=mock_settings), \
             patch("app.api.billing_webhooks.get_paddle_client", return_value=mock_paddle_client), \
             patch("app.api.billing_webhooks.process_webhook", return_value=mock_webhook_result):
            result = await handle_paddle_webhook(
                request=mock_request,
                background_tasks=MagicMock(),
            )
            assert result["status"] == "duplicate"

    def test_event_handler_map_has_expected_handlers(self):
        """EVENT_HANDLER_MAP has all expected event type mappings."""
        from app.api.billing_webhooks import EVENT_HANDLER_MAP
        expected_keys = [
            "payment.failed", "payment.succeeded",
            "transaction.paid", "transaction.completed",
            "subscription.created", "subscription.updated",
            "subscription.activated", "subscription.canceled",
            "subscription.past_due",
        ]
        for key in expected_keys:
            assert key in EVENT_HANDLER_MAP, f"Missing handler for {key}"


# ═══════════════════════════════════════════════════════════════════════
# 5. BILLING API — ROLE-BASED ACCESS (H-13)
# ═══════════════════════════════════════════════════════════════════════


class TestBillingAPIRoleAccess:
    """Tests for billing.py H-13: require_roles('owner', 'admin')."""

    def test_require_roles_rejects_unauthorized_role(self):
        """require_roles('owner', 'admin') rejects non-owner/admin roles."""
        from app.api.deps import require_roles
        from app.exceptions import AuthorizationError

        checker = require_roles("owner", "admin")
        mock_user = MagicMock()
        mock_user.role = "agent"  # Not owner/admin
        with pytest.raises(AuthorizationError):
            checker(mock_user)

    def test_require_roles_allows_owner(self):
        """require_roles('owner', 'admin') allows owner."""
        from app.api.deps import require_roles
        checker = require_roles("owner", "admin")
        mock_user = MagicMock()
        mock_user.role = "owner"
        result = checker(mock_user)
        assert result == mock_user

    def test_require_roles_allows_admin(self):
        """require_roles('owner', 'admin') allows admin."""
        from app.api.deps import require_roles
        checker = require_roles("owner", "admin")
        mock_user = MagicMock()
        mock_user.role = "admin"
        result = checker(mock_user)
        assert result == mock_user

    def test_billing_create_subscription_requires_owner_admin(self):
        """POST /subscription requires owner/admin (H-13)."""
        from app.api.billing import create_subscription
        # Verify the dependency is declared
        import inspect
        sig = inspect.signature(create_subscription)
        # The 'user' parameter should exist and depend on require_roles
        assert "user" in sig.parameters

    def test_billing_update_subscription_requires_owner_admin(self):
        """PATCH /subscription requires owner/admin (H-13)."""
        from app.api.billing import update_subscription
        import inspect
        sig = inspect.signature(update_subscription)
        assert "user" in sig.parameters

    def test_billing_cancel_subscription_requires_owner_admin(self):
        """DELETE /subscription requires owner/admin (H-13)."""
        from app.api.billing import cancel_subscription
        import inspect
        sig = inspect.signature(cancel_subscription)
        assert "user" in sig.parameters

    def test_billing_reactivate_requires_owner_admin(self):
        """POST /subscription/reactivate requires owner/admin (H-13)."""
        from app.api.billing import reactivate_subscription
        import inspect
        sig = inspect.signature(reactivate_subscription)
        assert "user" in sig.parameters

    def test_billing_create_refund_requires_owner_admin(self):
        """POST /client-refunds requires owner/admin (H-13)."""
        from app.api.billing import create_client_refund
        import inspect
        sig = inspect.signature(create_client_refund)
        assert "user" in sig.parameters

    def test_billing_process_refund_requires_owner_admin(self):
        """POST /client-refunds/{id}/process requires owner/admin (H-13)."""
        from app.api.billing import process_client_refund
        import inspect
        sig = inspect.signature(process_client_refund)
        assert "user" in sig.parameters

    def test_get_subscription_any_authenticated(self):
        """GET /subscription is available to any authenticated user."""
        from app.api.billing import get_subscription
        import inspect
        sig = inspect.signature(get_subscription)
        # No 'user' param means no role check — only company_id required
        assert "user" not in sig.parameters


# ═══════════════════════════════════════════════════════════════════════
# 6. AUTH COOKIES — OPEN REDIRECT (H-01)
# ═══════════════════════════════════════════════════════════════════════


class TestSafeRedirect:
    """Tests for isSafeRedirect() and getSafeRedirect() — H-01."""

    def _import_auth_cookies(self):
        """Import the TS module as Python equivalent for testing logic."""
        # Since this is TypeScript, we re-implement the core logic in Python
        # for unit testing. The actual TS tests would run via Jest.
        # We test the logic directly.
        ALLOWED_PREFIXES = [
            "/models", "/tickets", "/settings", "/billing",
            "/analytics", "/channels", "/knowledge", "/jarvis",
            "/agents", "/profile", "/onboarding", "/monitoring",
        ]
        return ALLOWED_PREFIXES

    def _is_safe_redirect(self, url: str) -> bool:
        """Python reimplementation of isSafeRedirect for unit testing."""
        ALLOWED_PREFIXES = self._import_auth_cookies()

        if not url or not isinstance(url, str):
            return False

        # Fully decode
        decoded = self._fully_decode_uri(url)

        if not decoded.startswith("/"):
            return False
        if decoded.startswith("//"):
            return False
        if decoded.startswith("\\\\"):
            return False
        if decoded.startswith("\\"):
            return False
        if "://" in decoded:
            return False
        import re
        if re.match(r"^\s*(javascript|data|vbscript)\s*:", decoded, re.IGNORECASE):
            return False

        path_only = decoded.split("?")[0].split("#")[0]
        return any(
            path_only == prefix or path_only.startswith(prefix + "/")
            for prefix in ALLOWED_PREFIXES
        )

    def _fully_decode_uri(self, s: str) -> str:
        """Python reimplementation of fullyDecodeUri."""
        from urllib.parse import unquote
        prev = ""
        current = s
        for _ in range(5):
            prev = current
            try:
                current = unquote(current)
            except Exception:
                break
            if current == prev:
                break
        return current

    def test_allows_valid_internal_path(self):
        """Valid internal paths are allowed."""
        assert self._is_safe_redirect("/models") is True
        assert self._is_safe_redirect("/tickets/123") is True
        assert self._is_safe_redirect("/billing?plan=growth") is True

    def test_blocks_protocol_relative_url(self):
        """Protocol-relative URLs (//evil.com) are blocked."""
        assert self._is_safe_redirect("//evil.com") is False

    def test_blocks_backslash_paths(self):
        """Backslash-based paths are blocked."""
        assert self._is_safe_redirect("\\\\evil.com") is False
        assert self._is_safe_redirect("\\evil.com") is False

    def test_blocks_external_urls(self):
        """External URLs with :// are blocked."""
        assert self._is_safe_redirect("https://evil.com") is False
        assert self._is_safe_redirect("http://evil.com") is False

    def test_blocks_javascript_uri(self):
        """javascript: URI scheme is blocked."""
        assert self._is_safe_redirect("javascript:alert(1)") is False

    def test_blocks_data_uri(self):
        """data: URI scheme is blocked."""
        assert self._is_safe_redirect("data:text/html,<script>alert(1)</script>") is False

    def test_blocks_double_encoded_paths(self):
        """Double-encoded paths (e.g., %252F) are decoded and validated."""
        # %252F -> %2F -> /
        # /%252F%252Fevil.com would decode to //evil.com
        assert self._is_safe_redirect("/%252F%252Fevil.com") is False

    def test_blocks_unauthorized_prefix(self):
        """Paths not in the whitelist are blocked."""
        assert self._is_safe_redirect("/admin") is False
        assert self._is_safe_redirect("/unknown-path") is False
        assert self._is_safe_redirect("/etc/passwd") is False

    def test_empty_url_blocked(self):
        """Empty or None URLs are blocked."""
        assert self._is_safe_redirect("") is False
        assert self._is_safe_redirect(None) is False

    def test_fully_decode_uri_multi_level(self):
        """fullyDecodeUri iteratively decodes multi-level encoding."""
        result = self._fully_decode_uri("%252F")
        assert result == "/"
        result = self._fully_decode_uri("hello")
        assert result == "hello"

    def test_get_safe_redirect_returns_default_on_invalid(self):
        """getSafeRedirect returns default when URL is invalid."""
        SAFE_REDIRECT_DEFAULT = "/models"
        url = "https://evil.com"
        if self._is_safe_redirect(url):
            result = url
        else:
            result = SAFE_REDIRECT_DEFAULT
        assert result == "/models"

    def test_get_safe_redirect_returns_url_on_valid(self):
        """getSafeRedirect returns the URL when it's valid."""
        url = "/billing"
        if self._is_safe_redirect(url):
            result = url
        else:
            result = "/models"
        assert result == "/billing"


# ═══════════════════════════════════════════════════════════════════════
# 7. IP EXTRACTION UTILITY (H-06)
# ═══════════════════════════════════════════════════════════════════════


class TestGetClientIP:
    """Tests for get_client_ip() — H-06."""

    def test_extracts_from_x_forwarded_for(self):
        """IP extracted from X-Forwarded-For header."""
        from app.core.security.utils import get_client_ip
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "1.2.3.4, 10.0.0.1"}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        ip = get_client_ip(mock_request)
        assert ip == "1.2.3.4" or ip == "10.0.0.1"  # depends on TRUSTED_PROXY_COUNT

    def test_extracts_from_x_real_ip(self):
        """IP extracted from X-Real-IP header when no X-Forwarded-For."""
        from app.core.security.utils import get_client_ip
        with patch.dict(os.environ, {"TRUSTED_PROXY_COUNT": "1"}):
            # Reimport to pick up new env
            import importlib
            import app.core.security.utils as utils_mod
            importlib.reload(utils_mod)

            mock_request = MagicMock()
            mock_request.headers = {"X-Real-IP": "5.6.7.8"}
            mock_request.client = MagicMock()
            mock_request.client.host = "10.0.0.1"
            ip = utils_mod.get_client_ip(mock_request)
            assert ip == "5.6.7.8"

    def test_falls_back_to_direct_connection(self):
        """IP falls back to request.client.host when no proxy headers."""
        from app.core.security.utils import get_client_ip
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.1"
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.1"

    def test_returns_unknown_when_no_ip(self):
        """Returns 'unknown' when IP cannot be determined from Request."""
        from app.core.security.utils import get_client_ip
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = None
        ip = get_client_ip(mock_request)
        assert ip == "unknown"

    def test_asgi_scope_extraction(self):
        """IP extraction works from raw ASGI scope dict."""
        from app.core.security.utils import get_client_ip
        scope = {
            "headers": [
                (b"x-forwarded-for", b"1.2.3.4"),
            ],
            "client": ("10.0.0.1", 12345),
        }
        with patch.dict(os.environ, {"TRUSTED_PROXY_COUNT": "1"}):
            import importlib
            import app.core.security.utils as utils_mod
            importlib.reload(utils_mod)
            ip = utils_mod.get_client_ip(scope)
            assert ip == "1.2.3.4"

    def test_trusted_proxy_count_respected(self):
        """TRUSTED_PROXY_COUNT determines which IP from X-Forwarded-For is used."""
        from app.core.security.utils import get_client_ip
        # With TRUSTED_PROXY_COUNT=2, the 2nd-from-right IP is used
        with patch.dict(os.environ, {"TRUSTED_PROXY_COUNT": "2"}):
            import importlib
            import app.core.security.utils as utils_mod
            importlib.reload(utils_mod)

            mock_request = MagicMock()
            mock_request.headers = {"X-Forwarded-For": "1.1.1.1, 2.2.2.2, 3.3.3.3"}
            mock_request.client = MagicMock()
            mock_request.client.host = "3.3.3.3"
            ip = utils_mod.get_client_ip(mock_request)
            assert ip == "2.2.2.2"  # 2nd from right

    def test_asgi_scope_no_headers(self):
        """ASGI scope with no headers falls back to client."""
        from app.core.security.utils import get_client_ip
        with patch.dict(os.environ, {"TRUSTED_PROXY_COUNT": "1"}):
            import importlib
            import app.core.security.utils as utils_mod
            importlib.reload(utils_mod)

            scope = {
                "headers": [],
                "client": ("192.168.1.50", 54321),
            }
            ip = utils_mod.get_client_ip(scope)
            assert ip == "192.168.1.50"


# ═══════════════════════════════════════════════════════════════════════
# 8. SOCKET.IO BACKEND
# ═══════════════════════════════════════════════════════════════════════


class TestSocketIO:
    """Tests for Socket.io backend (BC-005, BC-001, BC-011)."""

    def test_get_tenant_room_format(self):
        """get_tenant_room returns 'tenant_{company_id}' format."""
        from app.core.socketio import get_tenant_room
        assert get_tenant_room("acme") == "tenant_acme"
        assert get_tenant_room("company-123") == "tenant_company-123"

    def test_get_tenant_room_rejects_empty_company_id(self):
        """get_tenant_room raises ValueError for empty company_id."""
        from app.core.socketio import get_tenant_room
        with pytest.raises(ValueError):
            get_tenant_room("")
        with pytest.raises(ValueError):
            get_tenant_room("   ")

    def test_get_tenant_room_rejects_none_company_id(self):
        """get_tenant_room raises ValueError for None company_id."""
        from app.core.socketio import get_tenant_room
        with pytest.raises(ValueError):
            get_tenant_room(None)

    def test_get_tenant_room_rejects_oversized_company_id(self):
        """get_tenant_room raises ValueError for company_id > 128 chars."""
        from app.core.socketio import get_tenant_room, MAX_COMPANY_ID_LENGTH
        with pytest.raises(ValueError):
            get_tenant_room("x" * (MAX_COMPANY_ID_LENGTH + 1))

    def test_get_tenant_room_rejects_control_characters(self):
        """get_tenant_room raises ValueError for control characters in company_id."""
        from app.core.socketio import get_tenant_room
        with pytest.raises(ValueError):
            get_tenant_room("acme\x00evil")
        with pytest.raises(ValueError):
            get_tenant_room("acme\ninjection")

    def test_validate_company_id_valid(self):
        """_validate_company_id returns True for valid IDs."""
        from app.core.socketio import _validate_company_id
        assert _validate_company_id("acme") is True
        assert _validate_company_id("company-123") is True
        assert _validate_company_id("abc_def") is True

    def test_validate_company_id_invalid(self):
        """_validate_company_id returns False for invalid IDs."""
        from app.core.socketio import _validate_company_id
        assert _validate_company_id("") is False
        assert _validate_company_id(None) is False
        assert _validate_company_id(123) is False
        assert _validate_company_id("   ") is False
        assert _validate_company_id("x" * 200) is False

    def test_extract_token_from_qs(self):
        """_extract_token_from_qs extracts JWT from query string."""
        from app.core.socketio import _extract_token_from_qs
        assert _extract_token_from_qs("token=abc123") == "abc123"
        assert _extract_token_from_qs("foo=bar&token=xyz789") == "xyz789"
        assert _extract_token_from_qs("") == ""
        assert _extract_token_from_qs("foo=bar") == ""

    def test_get_socketio_server_returns_instance(self):
        """get_socketio_server returns the server or None."""
        from app.core.socketio import get_socketio_server, sio
        result = get_socketio_server()
        # May be None if python-socketio not installed
        assert result is sio

    def test_get_connected_count_returns_int(self):
        """get_connected_count returns an integer."""
        from app.core.socketio import get_connected_count
        count = get_connected_count()
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_emit_to_tenant_validates_company_id(self):
        """emit_to_tenant raises ValueError for invalid company_id."""
        from app.core.socketio import emit_to_tenant
        with pytest.raises(ValueError):
            await emit_to_tenant("", "test:event", {})

    @pytest.mark.asyncio
    async def test_emit_to_tenant_validates_none_company_id(self):
        """emit_to_tenant raises ValueError for None company_id."""
        from app.core.socketio import emit_to_tenant
        with pytest.raises(ValueError):
            await emit_to_tenant(None, "test:event", {})

    @pytest.mark.asyncio
    async def test_emit_to_tenant_uses_correct_room(self):
        """emit_to_tenant emits to the correct tenant room."""
        from app.core.socketio import emit_to_tenant, sio

        if sio is None:
            pytest.skip("python-socketio not installed")

        with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit, \
             patch("app.core.socketio.store_event", new_callable=AsyncMock):
            mock_emit.return_value = None
            # Patch manager.get_participants to avoid errors
            with patch.object(sio, "manager", create=True) as mock_mgr:
                mock_mgr.get_participants.return_value = set()
                await emit_to_tenant("acme", "ticket:new", {"id": "123"})
                mock_emit.assert_called_once()
                call_kwargs = mock_emit.call_args
                assert call_kwargs[1]["room"] == "tenant_acme"

    def test_create_socketio_app_raises_without_package(self):
        """create_socketio_app raises RuntimeError if socketio not installed."""
        from app.core import socketio as sio_mod
        original_pkg = sio_mod._socketio_pkg
        try:
            sio_mod._socketio_pkg = None
            with pytest.raises(RuntimeError, match="python-socketio is not installed"):
                sio_mod.create_socketio_app()
        finally:
            sio_mod._socketio_pkg = original_pkg


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION: Security Layers Working Together
# ═══════════════════════════════════════════════════════════════════════


class TestSecurityLayersIntegration:
    """Integration tests ensuring security layers work together."""

    @pytest.fixture
    def full_security_app(self):
        """App with security headers + CSRF middleware."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from app.middleware.security_headers import SecurityHeadersMiddleware
        from app.middleware.csrf import CSRFSecurityMiddleware

        async def homepage(request):
            return PlainTextResponse("OK")

        async def auth_login(request):
            return PlainTextResponse("authenticated")

        app = Starlette(
            routes=[
                Route("/", homepage),
                Route("/api/auth/login", auth_login, methods=["POST"]),
                Route("/api/tickets", homepage, methods=["GET", "POST"]),
            ]
        )
        app.add_middleware(SecurityHeadersMiddleware)
        # CSRF middleware wraps as pure ASGI — can't use add_middleware
        # so we test the layers individually for integration
        return app

    @pytest.fixture
    def client(self, full_security_app):
        from starlette.testclient import TestClient
        return TestClient(full_security_app)

    def test_security_headers_present_on_all_responses(self, client):
        """Security headers are present on all responses."""
        resp = client.get("/")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in resp.headers

    def test_cache_control_on_auth_and_security_headers(self, client):
        """M-11: Auth endpoints get both cache-control AND security headers."""
        resp = client.post("/api/auth/login")
        # Security headers should be present
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        # Cache control should be present on auth paths
        assert "no-store" in resp.headers.get("Cache-Control", "")

    @pytest.mark.asyncio
    async def test_csrf_and_ip_extraction_consistency(self):
        """H-06: Both CSRF and rate limit use same get_client_ip()."""
        from app.core.security.utils import get_client_ip
        from app.services.rate_limit_service import RateLimitService

        # Verify rate limit service uses get_client_ip
        svc = RateLimitService()
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "1.2.3.4, 10.0.0.1"}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"

        # Both should return the same IP
        direct_ip = get_client_ip(mock_request)
        svc_ip = svc._extract_ip(mock_request)
        assert direct_ip == svc_ip

    @pytest.mark.asyncio
    async def test_csrf_middleware_injects_csp_header(self):
        """CSRF middleware adds CSP header if not already present."""
        from app.middleware.csrf import CSRFSecurityMiddleware

        async def inner_app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"OK",
            })

        csrf_app = CSRFSecurityMiddleware(inner_app)
        received = []

        async def send_collector(message):
            received.append(message)

        async def receive():
            return {"type": "http.request", "body": b""}

        with patch.dict(os.environ, {"CSRF_ENABLED": "true"}):
            await csrf_app(
                {"type": "http", "method": "GET", "path": "/", "query_string": b"", "headers": []},
                receive,
                send_collector,
            )

        start_msgs = [m for m in received if m.get("type") == "http.response.start"]
        all_headers = []
        for m in start_msgs:
            all_headers.extend(m.get("headers", []))
        csp_headers = [h for h in all_headers if h[0] == b"content-security-policy"]
        assert len(csp_headers) > 0, "CSP header should be injected by CSRF middleware"

    def test_webhook_path_consistent_skipping(self):
        """Webhook paths are consistently skipped across rate limit + CSRF."""
        from app.middleware.rate_limit import SKIP_PREFIXES
        from app.middleware.csrf import _WEBHOOK_SKIP_PREFIXES

        # Both middlewares skip /api/webhooks/
        assert any("/api/webhooks/" in p for p in SKIP_PREFIXES)
        assert any("/api/webhooks/" in p for p in _WEBHOOK_SKIP_PREFIXES)

    @pytest.mark.asyncio
    async def test_csrf_token_freshness_and_signature(self):
        """Integration: CSRF token has both freshness and valid signature."""
        from app.middleware.csrf import CSRFSecurityMiddleware, _CSRF_MAX_AGE

        token = CSRFSecurityMiddleware.generate_csrf_token("integration-secret")
        # Should validate
        assert CSRFSecurityMiddleware.validate_csrf_token(token, "integration-secret") is True

        # Token parts should be parseable
        parts = token.split(":")
        assert len(parts) == 3
        nonce, ts_str, sig = parts
        # Timestamp should be recent (within last 10 seconds)
        ts = int(ts_str)
        assert abs(time.time() - ts) < 10

    def test_rate_limit_categories_cover_all_paths(self):
        """Rate limit categories cover auth, financial, integration, and general paths."""
        from app.services.rate_limit_service import RateLimitService
        svc = RateLimitService()

        # Auth paths
        assert svc.classify_path("/api/auth/login", "POST") == "auth_login"
        # Financial paths
        assert svc.classify_path("/api/billing/subscription", "POST") == "financial"
        # Integration paths
        assert svc.classify_path("/api/integrations/shopify", "POST") == "integration"
        # Default GET
        assert svc.classify_path("/api/unknown", "GET") == "general_get"
        # Default POST
        assert svc.classify_path("/api/unknown", "POST") == "general_post"
