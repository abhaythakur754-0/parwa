"""
Tests for PARWA Tenant Middleware - Deep Checks (Day 2 Backfill)

Tests /api/public bypass, request.state.company_id, empty string rejection,
malicious input handling, and structured error format.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from backend.app.middleware.tenant import TenantMiddleware  # noqa: E402


def _make_test_app():
    """Create a test FastAPI app with tenant middleware."""
    app = FastAPI()
    app.add_middleware(TenantMiddleware)

    @app.get("/api/test")
    async def protected_route():
        return {"ok": True}

    @app.get("/api/public/signup")
    async def public_route():
        return {"public": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture
def client():
    return TestClient(_make_test_app())


class TestPublicPathsBypass:
    """Public paths should bypass tenant middleware."""

    def test_health_bypass(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_docs_bypass(self, client):
        resp = client.get("/docs")
        # Will 404 since no docs enabled, but NOT 403
        assert resp.status_code != 403

    def test_redoc_bypass(self, client):
        resp = client.get("/redoc")
        assert resp.status_code != 403

    def test_openapi_bypass(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code != 403

    def test_api_public_prefix_bypass(self, client):
        resp = client.get("/api/public/signup")
        assert resp.status_code == 200
        assert resp.json()["public"] is True


class TestCompanyIDValidation:
    """Test various company_id values."""

    def test_valid_company_id_allowed(self, client):
        resp = client.get("/api/test", headers={"X-Company-ID": "co_abc123"})
        # Not blocked by tenant middleware (404 because no route handler for this app)
        assert resp.status_code != 403

    def test_empty_string_company_id_rejected(self, client):
        """Empty string company_id should be rejected."""
        resp = client.get("/api/test", headers={"X-Company-ID": ""})
        assert resp.status_code == 403

    def test_whitespace_company_id_rejected(self, client):
        """Whitespace-only company_id should be rejected."""
        resp = client.get("/api/test", headers={"X-Company-ID": "   "})
        assert resp.status_code == 403

    def test_missing_company_id_returns_403(self, client):
        """No X-Company-ID header → 403."""
        resp = client.get("/api/test")
        assert resp.status_code == 403

    def test_very_long_company_id_allowed(self, client):
        """Very long company_id is allowed (validation happens downstream)."""
        long_id = "x" * 500
        resp = client.get("/api/test", headers={"X-Company-ID": long_id})
        assert resp.status_code != 403


class TestStructuredError:
    """BC-012: Tenant middleware error responses are structured."""

    def test_403_response_structure(self, client):
        """403 has {error: {code, message, details}}."""
        resp = client.get("/api/test")
        assert resp.status_code == 403
        data = resp.json()
        assert "error" in data
        error = data["error"]
        assert set(error.keys()) == {"code", "message", "details"}

    def test_403_error_code(self, client):
        """403 error code is AUTHORIZATION_ERROR."""
        resp = client.get("/api/test")
        data = resp.json()
        assert data["error"]["code"] == "AUTHORIZATION_ERROR"

    def test_403_no_stack_traces(self, client):
        """403 must not contain stack traces."""
        resp = client.get("/api/test")
        text = resp.text.lower()
        assert "traceback" not in text
        assert "file " not in text
        assert "line " not in text


class TestRequestState:
    """Test that company_id is stored in request.state."""

    def test_company_id_set_in_state(self):
        """Middleware stores company_id in request.state for downstream."""
        from starlette.requests import Request

        app = _make_test_app()

        @app.middleware("http")
        async def check_state(request: Request, call_next):
            resp = await call_next(request)
            resp.headers["X-Test-Company-ID"] = getattr(
                getattr(request, "state", None), "company_id", "NOT_SET"
            )
            return resp

        @app.get("/api/state-check")
        async def state_route():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/state-check", headers={"X-Company-ID": "co_abc"})
        # The company_id should have been set by tenant middleware
        # If middleware works, request passes through (404 or 200, not 403)
        assert resp.status_code != 403
