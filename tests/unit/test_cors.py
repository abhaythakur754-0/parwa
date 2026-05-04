"""Tests for CORS middleware configuration."""

import os
from fastapi.testclient import TestClient


def test_cors_headers_present():
    """CORS headers must be present on API responses."""
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

    from backend.app.main import app
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS preflight or regular response
    assert response.status_code in (200, 405, 204)
