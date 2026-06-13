"""
Tests for Security Headers Middleware (BC-011/BC-012, H-04, M-11).

Verifies that all required security headers are set on every response,
HSTS is only present in production, and auth paths receive cache-control
directives.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.app.middleware.security_headers import (
    AUTH_PATH_PREFIXES,
    SecurityHeadersMiddleware,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_request(path: str = "/") -> Request:
    """Create a mock Starlette Request with a given path."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [],
        "server": ("localhost", 8000),
        "asgi": {"version": "3.0"},
    }
    request = Request(scope)
    return request


def _make_middleware(app: ASGIApp | None = None) -> SecurityHeadersMiddleware:
    """Create a SecurityHeadersMiddleware with a mock app."""
    if app is None:
        app = AsyncMock()
    return SecurityHeadersMiddleware(app)


async def _call_dispatch(
    middleware: SecurityHeadersMiddleware,
    path: str = "/",
    env: str = "development",
) -> Response:
    """Invoke dispatch() and return the resulting Response."""
    with patch.dict(os.environ, {"ENVIRONMENT": env}):
        request = _make_mock_request(path)

        async def call_next(req):
            return Response(content='{"ok":true}', media_type="application/json")

        return await middleware.dispatch(request, call_next)


# ===================================================================
# Required Security Headers Tests
# ===================================================================

class TestRequiredSecurityHeaders:
    """BC-011/BC-012: Required security headers on all responses."""

    @pytest.mark.asyncio
    async def test_x_content_type_options_nosniff(self):
        """X-Content-Type-Options must be 'nosniff'."""
        mw = _make_middleware()
        response = await _call_dispatch(mw)
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_x_frame_options_deny(self):
        """X-Frame-Options must be 'DENY'."""
        mw = _make_middleware()
        response = await _call_dispatch(mw)
        assert response.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_referrer_policy_strict_origin(self):
        """Referrer-Policy must be 'strict-origin-when-cross-origin'."""
        mw = _make_middleware()
        response = await _call_dispatch(mw)
        assert (
            response.headers["Referrer-Policy"]
            == "strict-origin-when-cross-origin"
        )

    @pytest.mark.asyncio
    async def test_permissions_policy_disables_camera_mic_geo(self):
        """Permissions-Policy must disable camera, microphone, geolocation."""
        mw = _make_middleware()
        response = await _call_dispatch(mw)
        pp = response.headers["Permissions-Policy"]
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp

    @pytest.mark.asyncio
    async def test_content_security_policy_present(self):
        """Content-Security-Policy header must be present (H-04)."""
        mw = _make_middleware()
        response = await _call_dispatch(mw)
        csp = response.headers.get("Content-Security-Policy", "")
        assert len(csp) > 0, "CSP header must be present"
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "form-action 'self'" in csp

    @pytest.mark.asyncio
    async def test_x_xss_protection_zero(self):
        """X-XSS-Protection must be '0' (modern browsers)."""
        mw = _make_middleware()
        response = await _call_dispatch(mw)
        assert response.headers["X-XSS-Protection"] == "0"


# ===================================================================
# HSTS Tests
# ===================================================================

class TestHSTS:
    """HSTS should only be set in production."""

    @pytest.mark.asyncio
    async def test_no_hsts_in_development(self):
        """Strict-Transport-Security must NOT be present in development."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, env="development")
        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_no_hsts_in_test(self):
        """Strict-Transport-Security must NOT be present in test environment."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, env="test")
        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_hsts_present_in_production(self):
        """Strict-Transport-Security must be set in production."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, env="production")
        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    @pytest.mark.asyncio
    async def test_hsts_max_age_value(self):
        """HSTS max-age must be exactly 1 year in seconds."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, env="production")
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts


# ===================================================================
# Cache-Control on Auth Paths (M-11)
# ===================================================================

class TestAuthPathCacheControl:
    """M-11: Auth endpoints must have Cache-Control: no-store."""

    @pytest.mark.asyncio
    async def test_cache_control_on_auth_path(self):
        """Cache-Control: no-store must be set on /api/auth/ paths."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/auth/login")
        cc = response.headers.get("Cache-Control", "")
        assert "no-store" in cc

    @pytest.mark.asyncio
    async def test_pragma_no_cache_on_auth_path(self):
        """Pragma: no-cache must be set on auth paths."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/auth/login")
        assert response.headers.get("Pragma") == "no-cache"

    @pytest.mark.asyncio
    async def test_expires_zero_on_auth_path(self):
        """Expires: 0 must be set on auth paths."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/auth/login")
        assert response.headers.get("Expires") == "0"

    @pytest.mark.asyncio
    async def test_cache_control_on_login_path(self):
        """Cache-Control: no-store must be set on /api/login."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/login")
        cc = response.headers.get("Cache-Control", "")
        assert "no-store" in cc

    @pytest.mark.asyncio
    async def test_cache_control_on_mfa_path(self):
        """Cache-Control: no-store must be set on /api/mfa/ paths."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/mfa/verify")
        cc = response.headers.get("Cache-Control", "")
        assert "no-store" in cc

    @pytest.mark.asyncio
    async def test_cache_control_on_refresh_path(self):
        """Cache-Control: no-store must be set on /api/refresh."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/refresh")
        cc = response.headers.get("Cache-Control", "")
        assert "no-store" in cc

    @pytest.mark.asyncio
    async def test_no_cache_control_on_non_auth_path(self):
        """Cache-Control must NOT be set on non-auth paths."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/tickets")
        assert "Cache-Control" not in response.headers

    @pytest.mark.asyncio
    async def test_no_pragma_on_non_auth_path(self):
        """Pragma must NOT be set on non-auth paths."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/tickets")
        assert "Pragma" not in response.headers

    @pytest.mark.asyncio
    async def test_cache_control_full_value_on_auth(self):
        """Cache-Control on auth paths must include no-cache, must-revalidate."""
        mw = _make_middleware()
        response = await _call_dispatch(mw, path="/api/auth/logout")
        cc = response.headers.get("Cache-Control", "")
        assert "no-cache" in cc
        assert "must-revalidate" in cc
        assert "max-age=0" in cc


# ===================================================================
# BaseHTTPMiddleware Integration Tests
# ===================================================================

class TestMiddlewareIntegration:
    """Integration tests using a real FastAPI app + TestClient."""

    def test_all_headers_via_test_client(self):
        """Full round-trip: all security headers present on response."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test-endpoint")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test-endpoint")

        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "0"
        assert "Referrer-Policy" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

    def test_auth_endpoint_has_cache_headers(self):
        """Auth endpoint should have Cache-Control and Pragma headers."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.post("/api/auth/login")
        async def login():
            return {"token": "test"}

        client = TestClient(app)
        response = client.post("/api/auth/login")

        assert "Cache-Control" in response.headers
        assert "no-store" in response.headers["Cache-Control"]
        assert response.headers["Pragma"] == "no-cache"
