"""
Security Headers Middleware — Unit Tests

Tests for SecurityHeadersMiddleware (Starlette BaseHTTPMiddleware).
No database connection required.

Run: cd /home/z/my-project/parwa && python -m pytest backend/tests/unit/test_security_headers.py -v
"""

import os
import sys

import pytest

# Ensure backend/app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    AUTH_PATH_PREFIXES,
)


# ── Helpers ────────────────────────────────────────────────────────


def _create_app():
    """Create a minimal FastAPI/Starlette app with security headers."""
    from starlette.applications import Starlette
    from starlette.routing import Route

    async def homepage(request):
        return Response(content='{"ok": true}', media_type="application/json")

    async def auth_endpoint(request):
        return Response(content='{"token": "abc"}', media_type="application/json")

    async def login_endpoint(request):
        return Response(content='{"logged_in": true}', media_type="application/json")

    app = Starlette(
        routes=[
            Route("/", homepage),
            Route("/api/auth/token", auth_endpoint),
            Route("/api/login", login_endpoint),
            Route("/api/register", login_endpoint),
            Route("/api/mfa/setup", login_endpoint),
            Route("/api/refresh", login_endpoint),
            Route("/api/v1/tickets", homepage),
        ],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    return app


# ═══════════════════════════════════════════════════════════════════
# All security headers are set
# ═══════════════════════════════════════════════════════════════════


class TestSecurityHeadersPresent:
    """Verify all required security headers are present."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")

    def test_x_content_type_options(self):
        """X-Content-Type-Options should be nosniff."""
        client = TestClient(_create_app())
        resp = client.get("/")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self):
        """X-Frame-Options should be DENY."""
        client = TestClient(_create_app())
        resp = client.get("/")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection(self):
        """X-XSS-Protection should be 0 (modern browsers)."""
        client = TestClient(_create_app())
        resp = client.get("/")
        assert resp.headers["X-XSS-Protection"] == "0"

    def test_referrer_policy(self):
        """Referrer-Policy should be strict-origin-when-cross-origin."""
        client = TestClient(_create_app())
        resp = client.get("/")
        assert resp.headers["Referrer-Policy"] == (
            "strict-origin-when-cross-origin"
        )

    def test_permissions_policy(self):
        """Permissions-Policy should disable camera/mic/geo."""
        client = TestClient(_create_app())
        resp = client.get("/")
        pp = resp.headers["Permissions-Policy"]
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp


# ═══════════════════════════════════════════════════════════════════
# CSP header
# ═══════════════════════════════════════════════════════════════════


class TestCSPHeader:
    """Verify Content-Security-Policy header is present (H-04)."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")

    def test_csp_header_present(self):
        """Content-Security-Policy header should be set on all responses."""
        client = TestClient(_create_app())
        resp = client.get("/")
        assert "Content-Security-Policy" in resp.headers

    def test_csp_default_src_self(self):
        """CSP should have default-src 'self'."""
        client = TestClient(_create_app())
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp

    def test_csp_frame_ancestors_none(self):
        """CSP should have frame-ancestors 'none'."""
        client = TestClient(_create_app())
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    def test_csp_form_action_self(self):
        """CSP should have form-action 'self'."""
        client = TestClient(_create_app())
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "form-action 'self'" in csp

    def test_csp_base_uri_self(self):
        """CSP should have base-uri 'self'."""
        client = TestClient(_create_app())
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "base-uri 'self'" in csp

    def test_csp_script_src_self(self):
        """CSP should have script-src 'self'."""
        client = TestClient(_create_app())
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "script-src 'self'" in csp

    def test_csp_connect_src_self(self):
        """CSP should have connect-src 'self'."""
        client = TestClient(_create_app())
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "connect-src 'self'" in csp

    def test_csp_img_src_allows_data(self):
        """CSP should allow img-src 'self' data: blob:."""
        client = TestClient(_create_app())
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "img-src 'self' data: blob:" in csp


# ═══════════════════════════════════════════════════════════════════
# Cache-Control on auth paths (M-11)
# ═══════════════════════════════════════════════════════════════════


class TestCacheControlAuthPaths:
    """Verify Cache-Control: no-store on auth endpoints (M-11)."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")

    @pytest.mark.parametrize(
        "path",
        [
            "/api/auth/token",
            "/api/login",
            "/api/register",
            "/api/mfa/setup",
            "/api/refresh",
        ],
    )
    def test_no_store_on_auth_paths(self, path):
        """Auth endpoints should have Cache-Control: no-store."""
        client = TestClient(_create_app())
        resp = client.get(path)
        assert "Cache-Control" in resp.headers
        assert "no-store" in resp.headers["Cache-Control"]

    @pytest.mark.parametrize(
        "path",
        ["/api/auth/token", "/api/login", "/api/refresh"],
    )
    def test_pragma_no_cache_on_auth(self, path):
        """Auth endpoints should have Pragma: no-cache."""
        client = TestClient(_create_app())
        resp = client.get(path)
        assert resp.headers.get("Pragma") == "no-cache"

    @pytest.mark.parametrize(
        "path",
        ["/api/auth/token", "/api/login", "/api/refresh"],
    )
    def test_expires_zero_on_auth(self, path):
        """Auth endpoints should have Expires: 0."""
        client = TestClient(_create_app())
        resp = client.get(path)
        assert resp.headers.get("Expires") == "0"

    def test_no_cache_control_on_non_auth(self):
        """Non-auth endpoints should NOT have Cache-Control forced."""
        client = TestClient(_create_app())
        resp = client.get("/")
        # Should not have Cache-Control header
        assert "Cache-Control" not in resp.headers


# ═══════════════════════════════════════════════════════════════════
# HSTS only in production
# ═══════════════════════════════════════════════════════════════════


class TestHSTSProduction:
    """Verify HSTS is only set in production environment."""

    def test_no_hsts_in_development(self, monkeypatch):
        """HSTS should NOT be present in development."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        client = TestClient(_create_app())
        resp = client.get("/")
        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_in_production(self, monkeypatch):
        """HSTS should be present in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        client = TestClient(_create_app())
        resp = client.get("/")
        assert "Strict-Transport-Security" in resp.headers
        hsts = resp.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_no_hsts_in_staging(self, monkeypatch):
        """HSTS should NOT be present in staging."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        client = TestClient(_create_app())
        resp = client.get("/")
        assert "Strict-Transport-Security" not in resp.headers


# ═══════════════════════════════════════════════════════════════════
# Auth path configuration
# ═══════════════════════════════════════════════════════════════════


class TestAuthPathConfig:
    """Verify auth path prefix configuration."""

    def test_auth_prefixes_include_expected(self):
        """AUTH_PATH_PREFIXES should include expected auth paths."""
        assert "/api/auth/" in AUTH_PATH_PREFIXES
        assert "/api/login" in AUTH_PATH_PREFIXES
        assert "/api/register" in AUTH_PATH_PREFIXES
        assert "/api/mfa/" in AUTH_PATH_PREFIXES
        assert "/api/refresh" in AUTH_PATH_PREFIXES

    def test_auth_prefixes_is_tuple(self):
        """AUTH_PATH_PREFIXES should be a tuple (immutable)."""
        assert isinstance(AUTH_PATH_PREFIXES, tuple)
