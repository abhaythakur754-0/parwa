"""Tests for security headers middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)


@pytest.fixture
def app_with_headers():
    """Create a minimal FastAPI app with security headers."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def test_route():
        return {"status": "ok"}

    return app


def test_security_headers_present(app_with_headers):
    """Security headers must be present on all responses."""
    client = TestClient(app_with_headers)
    response = client.get("/test")
    assert response.status_code == 200
    assert (
        response.headers["X-Content-Type-Options"] == "nosniff"
    )
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "0"
    assert "Referrer-Policy" in response.headers


def test_hsts_not_in_development(app_with_headers):
    """HSTS should NOT be set in development environment."""
    client = TestClient(app_with_headers)
    response = client.get("/test")
    assert "Strict-Transport-Security" not in response.headers


def test_permissions_policy_set(app_with_headers):
    """Permissions-Policy should restrict camera/mic/geo."""
    client = TestClient(app_with_headers)
    response = client.get("/test")
    pp = response.headers.get("Permissions-Policy", "")
    assert "camera=()" in pp
    assert "microphone=()" in pp
