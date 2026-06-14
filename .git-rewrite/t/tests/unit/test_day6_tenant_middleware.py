"""
Comprehensive Tenant Middleware Tests (Day 6 - BC-001, BC-012)

Tests cover:
- PUBLIC_PATHS: /health, /ready, /metrics, /docs, /redoc, /openapi.json bypass tenant
- PUBLIC_PREFIXES: /api/auth/, /api/public/, /api/api-keys, /api/mfa/, /api/client/,
                   /api/webhooks/, /api/jarvis/, /test/ bypass tenant
- Missing company_id → 403
- Empty/whitespace company_id → 403
- company_id > 128 chars → 400
- company_id with control characters → 400
- Valid company_id passes through (200)
- company_id is stripped before use
- set_tenant_context called on success
- clear_tenant_context called in finally (even on error)
- /api/billing/ and /api/admin/ are NOT public (require tenant → 403)
- Structured error response format (BC-012)
"""

import os
import sys

# Add backend to path for nested app imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

# MUST be set BEFORE importing any backend module
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from unittest import mock

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from backend.app.middleware.tenant import (  # noqa: E402
    MAX_COMPANY_ID_LENGTH,
    TenantMiddleware,
)


# ── Helpers ───────────────────────────────────────────────────


def _make_test_app(company_id: str = None):
    """Create a FastAPI app with TenantMiddleware.

    Optionally injects an http middleware that sets company_id
    on request.state BEFORE TenantMiddleware runs (simulating JWT auth).
    """
    app = FastAPI()
    app.add_middleware(TenantMiddleware)

    @app.get("/api/protected")
    async def protected():
        return {"ok": True}

    @app.get("/api/public/signup")
    async def public_signup():
        return {"public": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics():
        return {"metrics": True}

    @app.get("/api/billing/subscription")
    async def billing():
        return {"billing": True}

    @app.get("/api/admin/users")
    async def admin():
        return {"admin": True}

    # If company_id is provided, add a middleware that sets it on state
    if company_id is not None:

        @app.middleware("http")
        async def inject_company_id(request: Request, call_next):
            request.state.company_id = company_id
            resp = await call_next(request)
            resp.headers["X-Test-Company-ID"] = getattr(
                request.state, "company_id", "NOT_SET"
            )
            return resp

    return app


@pytest.fixture
def no_auth_client():
    """TestClient with tenant middleware but no company_id injection."""
    return TestClient(_make_test_app())


@pytest.fixture
def auth_client():
    """TestClient with tenant middleware + company_id = 'acme'."""
    return TestClient(_make_test_app(company_id="acme"))


# ── PUBLIC_PATHS Tests ────────────────────────────────────────


class TestPublicPaths:
    """PUBLIC_PATHS bypass tenant check entirely."""

    def test_health_passes_through(self, no_auth_client):
        """GET /health → 200 without company_id."""
        resp = no_auth_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_ready_passes_through(self, no_auth_client):
        """GET /ready → 200 without company_id."""
        resp = no_auth_client.get("/ready")
        assert resp.status_code == 200

    def test_metrics_passes_through(self, no_auth_client):
        """GET /metrics → 200 without company_id."""
        resp = no_auth_client.get("/metrics")
        assert resp.status_code == 200

    def test_docs_passes_through(self, no_auth_client):
        """GET /docs bypasses tenant middleware (may 404 but NOT 403)."""
        resp = no_auth_client.get("/docs")
        assert resp.status_code != 403

    def test_redoc_passes_through(self, no_auth_client):
        """GET /redoc bypasses tenant middleware."""
        resp = no_auth_client.get("/redoc")
        assert resp.status_code != 403

    def test_openapi_json_passes_through(self, no_auth_client):
        """GET /openapi.json bypasses tenant middleware."""
        resp = no_auth_client.get("/openapi.json")
        assert resp.status_code != 403


# ── PUBLIC_PREFIXES Tests ─────────────────────────────────────


class TestPublicPrefixes:
    """PUBLIC_PREFIXES bypass tenant check."""

    def test_api_auth_prefix(self, no_auth_client):
        """/api/auth/* bypasses tenant middleware."""
        app = _make_test_app()

        @app.get("/api/auth/login")
        async def auth_login():
            return {"auth": True}

        client = TestClient(app)
        resp = client.get("/api/auth/login")
        assert resp.status_code == 200

    def test_api_public_prefix(self, no_auth_client):
        """/api/public/* bypasses tenant middleware."""
        resp = no_auth_client.get("/api/public/signup")
        assert resp.status_code == 200
        assert resp.json()["public"] is True

    def test_api_api_keys_prefix(self):
        """/api/api-keys bypasses tenant middleware."""
        app = _make_test_app()

        @app.get("/api/api-keys/verify")
        async def api_keys():
            return {"verified": True}

        client = TestClient(app)
        resp = client.get("/api/api-keys/verify")
        assert resp.status_code == 200

    def test_api_mfa_prefix(self):
        """/api/mfa/* bypasses tenant middleware."""
        app = _make_test_app()

        @app.get("/api/mfa/setup")
        async def mfa_setup():
            return {"mfa": True}

        client = TestClient(app)
        resp = client.get("/api/mfa/setup")
        assert resp.status_code == 200

    def test_api_client_prefix(self):
        """/api/client/* bypasses tenant middleware."""
        app = _make_test_app()

        @app.get("/api/client/info")
        async def client_info():
            return {"info": True}

        client = TestClient(app)
        resp = client.get("/api/client/info")
        assert resp.status_code == 200

    def test_api_webhooks_prefix(self):
        """/api/webhooks/* bypasses tenant middleware."""
        app = _make_test_app()

        @app.get("/api/webhooks/paddle")
        async def webhook_paddle():
            return {"webhook": True}

        client = TestClient(app)
        resp = client.get("/api/webhooks/paddle")
        assert resp.status_code == 200

    def test_api_jarvis_prefix(self):
        """/api/jarvis/* bypasses tenant middleware."""
        app = _make_test_app()

        @app.get("/api/jarvis/chat")
        async def jarvis_chat():
            return {"chat": True}

        client = TestClient(app)
        resp = client.get("/api/jarvis/chat")
        assert resp.status_code == 200

    def test_test_prefix(self):
        """/test/* bypasses tenant middleware."""
        app = _make_test_app()

        @app.get("/test/something")
        async def test_route():
            return {"test": True}

        client = TestClient(app)
        resp = client.get("/test/something")
        assert resp.status_code == 200


# ── Missing / Empty company_id Tests ──────────────────────────


class TestMissingCompanyID:
    """Missing or empty company_id → 403 (BC-001)."""

    def test_missing_company_id_returns_403(self, no_auth_client):
        """No company_id in request.state → 403."""
        resp = no_auth_client.get("/api/protected")
        assert resp.status_code == 403

    def test_empty_string_company_id_returns_403(self):
        """company_id = '' → 403."""
        client = TestClient(_make_test_app(company_id=""))
        resp = client.get("/api/protected")
        assert resp.status_code == 403

    def test_whitespace_only_company_id_returns_403(self):
        """company_id = '   ' → 403."""
        client = TestClient(_make_test_app(company_id="   \t  "))
        resp = client.get("/api/protected")
        assert resp.status_code == 403

    def test_403_structured_error_format(self, no_auth_client):
        """403 response follows BC-012 structured format."""
        resp = no_auth_client.get("/api/protected")
        assert resp.status_code == 403
        data = resp.json()
        assert "error" in data
        error = data["error"]
        assert error["code"] == "AUTHORIZATION_ERROR"
        assert error["message"] == "Tenant identification required"
        assert error["details"] is None


# ── company_id Validation Tests ───────────────────────────────


class TestCompanyIDValidation:
    """BC-001: company_id length and format validation."""

    def test_valid_company_id_passes_through(self, auth_client):
        """Valid company_id 'acme' → 200."""
        resp = auth_client.get("/api/protected")
        assert resp.status_code == 200

    def test_company_id_is_stripped(self):
        """company_id '  acme  ' is stripped to 'acme' before use."""
        client = TestClient(_make_test_app(company_id="  acme  "))
        resp = client.get("/api/protected")
        assert resp.status_code == 200
        # Verify stripped value is in state
        assert resp.headers["X-Test-Company-ID"] == "acme"

    def test_long_company_id_returns_400(self):
        """company_id > 128 chars → 400."""
        long_id = "x" * (MAX_COMPANY_ID_LENGTH + 1)
        client = TestClient(_make_test_app(company_id=long_id))
        resp = client.get("/api/protected")
        assert resp.status_code == 400

    def test_max_length_company_id_passes(self):
        """company_id = exactly 128 chars → 200."""
        max_id = "x" * MAX_COMPANY_ID_LENGTH
        client = TestClient(_make_test_app(company_id=max_id))
        resp = client.get("/api/protected")
        assert resp.status_code == 200

    def test_control_characters_returns_400(self):
        """company_id with control chars (null byte, tab, newline) → 400."""
        for bad_id in ["acme\x00corp", "acme\tcorp", "acme\ncorp"]:
            client = TestClient(_make_test_app(company_id=bad_id))
            resp = client.get("/api/protected")
            assert resp.status_code == 400, (
                f"company_id with control char should return 400: {repr(bad_id)}"
            )

    def test_400_structured_error_too_long(self):
        """400 for too-long company_id follows BC-012 format."""
        long_id = "x" * 500
        client = TestClient(_make_test_app(company_id=long_id))
        resp = client.get("/api/protected")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "BAD_REQUEST"
        assert data["error"]["message"] == "Tenant ID too long"

    def test_400_structured_error_invalid_format(self):
        """400 for control chars follows BC-012 format."""
        client = TestClient(_make_test_app(company_id="acme\x00corp"))
        resp = client.get("/api/protected")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "BAD_REQUEST"
        assert data["error"]["message"] == "Invalid tenant ID format"


# ── Tenant Context Propagation Tests ──────────────────────────


class TestTenantContextPropagation:
    """Day 20: set_tenant_context/clear_tenant_context called correctly."""

    def test_set_tenant_context_called_on_success(self):
        """set_tenant_context('acme') is called when company_id is valid."""
        with mock.patch(
            "backend.app.middleware.tenant.set_tenant_context"
        ) as mock_set, mock.patch(
            "backend.app.middleware.tenant.clear_tenant_context"
        ) as mock_clear:
            client = TestClient(_make_test_app(company_id="acme"))
            resp = client.get("/api/protected")
            assert resp.status_code == 200
            mock_set.assert_called_once_with("acme")
            mock_clear.assert_called_once()

    def test_clear_tenant_context_called_in_finally(self):
        """clear_tenant_context is called even if the downstream handler raises."""
        app = FastAPI()
        app.add_middleware(TenantMiddleware)

        @app.middleware("http")
        async def inject_company_id(request: Request, call_next):
            request.state.company_id = "acme"
            return await call_next(request)

        @app.get("/api/error")
        async def error_route():
            raise RuntimeError("intentional error")

        with mock.patch(
            "backend.app.middleware.tenant.set_tenant_context"
        ) as mock_set, mock.patch(
            "backend.app.middleware.tenant.clear_tenant_context"
        ) as mock_clear:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/error")
            # Handler errors → 500, but context must still be cleared
            mock_clear.assert_called_once()

    def test_context_not_set_for_public_paths(self):
        """set_tenant_context is NOT called for public paths."""
        with mock.patch(
            "backend.app.middleware.tenant.set_tenant_context"
        ) as mock_set:
            client = TestClient(_make_test_app(company_id=None))
            client.get("/health")
            mock_set.assert_not_called()

    def test_context_not_set_when_company_id_missing(self):
        """set_tenant_context is NOT called when company_id is missing."""
        with mock.patch(
            "backend.app.middleware.tenant.set_tenant_context"
        ) as mock_set:
            client = TestClient(_make_test_app(company_id=None))
            client.get("/api/protected")
            mock_set.assert_not_called()


# ── Non-Public Paths Require Tenant ───────────────────────────


class TestNonPublicPathsRequireTenant:
    """SECURITY: /api/billing/ and /api/admin/ require tenant."""

    def test_api_billing_requires_tenant(self, no_auth_client):
        """/api/billing/* is NOT in PUBLIC_PREFIXES → requires company_id."""
        resp = no_auth_client.get("/api/billing/subscription")
        assert resp.status_code == 403

    def test_api_admin_requires_tenant(self, no_auth_client):
        """/api/admin/* is NOT in PUBLIC_PREFIXES → requires company_id."""
        resp = no_auth_client.get("/api/admin/users")
        assert resp.status_code == 403

    def test_api_billing_works_with_company_id(self, auth_client):
        """/api/billing/* works when company_id is present."""
        resp = auth_client.get("/api/billing/subscription")
        assert resp.status_code == 200

    def test_api_admin_works_with_company_id(self, auth_client):
        """/api/admin/* works when company_id is present."""
        resp = auth_client.get("/api/admin/users")
        assert resp.status_code == 200


# ── PUBLIC_PATHS Constants Tests ──────────────────────────────


class TestPublicPathsConstants:
    """Verify PUBLIC_PATHS and PUBLIC_PREFIXES are correct."""

    def test_public_paths_set(self):
        """PUBLIC_PATHS is a set of expected paths."""
        expected = {
            "/health", "/ready", "/metrics",
            "/docs", "/redoc", "/openapi.json",
        }
        assert TenantMiddleware.PUBLIC_PATHS == expected

    def test_public_prefixes_tuple(self):
        """PUBLIC_PREFIXES is a tuple of expected prefixes."""
        prefixes = TenantMiddleware.PUBLIC_PREFIXES
        assert isinstance(prefixes, tuple)
        assert "/api/auth/" in prefixes
        assert "/api/public/" in prefixes
        assert "/api/api-keys" in prefixes
        assert "/api/mfa/" in prefixes
        assert "/api/client/" in prefixes
        assert "/api/webhooks/" in prefixes
        assert "/api/jarvis/" in prefixes
        assert "/test/" in prefixes

    def test_billing_not_in_public_prefixes(self):
        """/api/billing/ must NOT be in PUBLIC_PREFIXES."""
        assert "/api/billing/" not in TenantMiddleware.PUBLIC_PREFIXES

    def test_admin_not_in_public_prefixes(self):
        """/api/admin/ must NOT be in PUBLIC_PREFIXES."""
        assert "/api/admin/" not in TenantMiddleware.PUBLIC_PREFIXES

    def test_max_company_id_length(self):
        """MAX_COMPANY_ID_LENGTH is 128."""
        assert MAX_COMPANY_ID_LENGTH == 128
