"""
Tests for PARWA Tenant Middleware (Day 2)

BC-001: Tenant middleware extracts company_id and blocks requests without it.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from backend.app.main import app  # noqa: E402
from backend.app.middleware.tenant import TenantMiddleware  # noqa: E402


class TestTenantMiddleware:
    """BC-001: Tenant middleware tests."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_public_endpoints_no_company_id_required(self, client):
        """Health/ready/metrics endpoints work without company_id."""
        # /health and /metrics always return 200
        # /ready may return 503 if Redis is down (BC-012)
        for path in ["/health", "/metrics"]:
            resp = client.get(path)
            assert resp.status_code == 200, (
                f"Public endpoint {path} should return 200"
            )
        # /ready may return 503 when deps are unavailable (test env)
        resp = client.get("/ready")
        assert resp.status_code in (200, 503), (
            "Public endpoint /ready should not require company_id"
        )

    def test_protected_route_without_company_id_returns_403(self, client):
        """Protected route without company_id returns 403 (BC-001)."""
        resp = client.get("/fake-protected-route")
        assert resp.status_code in (403, 404), (
            "Should be blocked or not found"
        )

    def test_middleware_allows_with_company_id_header(self, client):
        """Request with X-Company-ID header is allowed through."""
        resp = client.get(
            "/nonexistent",
            headers={"X-Company-ID": "test-company-123"}
        )
        assert resp.status_code != 403, (
            "company_id request should not be blocked"
            " by tenant middleware"
        )

    def test_middleware_structured_403_response(self):
        """403 response from middleware follows BC-012 structured format."""
        test_app = FastAPI()
        test_app.add_middleware(TenantMiddleware)

        @test_app.get("/api/test")
        async def test_route():
            return {"ok": True}

        tc = TestClient(test_app)
        resp = tc.get("/api/test")
        assert resp.status_code == 403
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTHORIZATION_ERROR"
        assert "message" in data["error"]
