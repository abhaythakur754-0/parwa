"""
Tests for backend/app/middleware/request_logger.py

Tests request logging, client IP extraction, path skipping.
BC-012: Every request should be logged (except health endpoints).
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt")
os.environ.setdefault(
    "DATA_ENCRYPTION_KEY", "12345678901234567890123456789012"
)

from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from backend.app.middleware.request_logger import (  # noqa: E402
    SKIP_PATHS,
    RequestLoggerMiddleware,
    _get_client_ip,
)


class TestSkipPaths:
    """Tests for path skipping configuration."""

    def test_health_skipped(self):
        assert "/health" in SKIP_PATHS

    def test_ready_skipped(self):
        assert "/ready" in SKIP_PATHS

    def test_metrics_skipped(self):
        assert "/metrics" in SKIP_PATHS

    def test_normal_path_not_skipped(self):
        assert "/api/tickets" not in SKIP_PATHS


class TestGetClientIp:
    """Tests for client IP extraction."""

    def test_from_forwarded_for(self):
        scope = {
            "type": "http", "method": "GET",
            "headers": [(b"x-forwarded-for", b"10.0.0.1, 172.16.0.1")],
            "query_string": b"", "path": "/test",
        }
        assert _get_client_ip(Request(scope)) == "10.0.0.1"

    def test_from_real_ip(self):
        scope = {
            "type": "http", "method": "GET",
            "headers": [(b"x-real-ip", b"192.168.1.1")],
            "query_string": b"", "path": "/test",
        }
        assert _get_client_ip(Request(scope)) == "192.168.1.1"

    def test_forwarded_takes_priority(self):
        scope = {
            "type": "http", "method": "GET",
            "headers": [
                (b"x-forwarded-for", b"10.0.0.1"),
                (b"x-real-ip", b"192.168.1.1"),
            ],
            "query_string": b"", "path": "/test",
        }
        assert _get_client_ip(Request(scope)) == "10.0.0.1"

    def test_no_headers_returns_unknown(self):
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
            "client": None,
        }
        assert _get_client_ip(Request(scope)) == "unknown"

    def test_client_host_fallback(self):
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
            "client": ("127.0.0.1", 12345),
        }
        assert _get_client_ip(Request(scope)) == "127.0.0.1"


class TestRequestLoggerMiddleware:
    """Tests for request logger middleware."""

    def test_normal_request_logged(self):
        async def handler(request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/api/test", handler)])
        app.add_middleware(RequestLoggerMiddleware)
        client = TestClient(app)

        response = client.get("/api/test")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_not_logged(self):
        """Health endpoints should be skipped (no logging)."""
        async def handler(request):
            return JSONResponse({"status": "healthy"})

        app = Starlette(routes=[Route("/health", handler)])
        app.add_middleware(RequestLoggerMiddleware)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

    def test_ready_not_logged(self):
        async def handler(request):
            return JSONResponse({"status": "ready"})

        app = Starlette(routes=[Route("/ready", handler)])
        app.add_middleware(RequestLoggerMiddleware)
        client = TestClient(app)

        response = client.get("/ready")
        assert response.status_code == 200

    def test_metrics_not_logged(self):
        async def handler(request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/metrics", handler)])
        app.add_middleware(RequestLoggerMiddleware)
        client = TestClient(app)

        response = client.get("/metrics")
        assert response.status_code == 200

    def test_error_request_still_responds(self):
        """Middleware should not break on errors."""
        async def handler(request):
            raise ValueError("test error")

        app = Starlette(routes=[Route("/api/error", handler)])
        app.add_middleware(RequestLoggerMiddleware)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/error")
        assert response.status_code == 500

    def test_post_request_logged(self):
        async def handler(request):
            return JSONResponse({"status": "created"})

        app = Starlette(routes=[
            Route("/api/create", handler, methods=["POST"])
        ])
        app.add_middleware(RequestLoggerMiddleware)
        client = TestClient(app)

        response = client.post("/api/create", json={"data": "test"})
        assert response.status_code == 200

    def test_with_correlation_id(self):
        """Should work alongside error handler middleware."""
        from backend.app.middleware.error_handler import (  # noqa: E402
            ErrorHandlerMiddleware,
        )

        async def handler(request):
            cid = getattr(request.state, "correlation_id", "none")
            return JSONResponse({"correlation_id": cid})

        app = Starlette(routes=[Route("/api/cid-test", handler)])
        app.add_middleware(ErrorHandlerMiddleware)
        app.add_middleware(RequestLoggerMiddleware)
        client = TestClient(app)

        response = client.get("/api/cid-test")
        assert response.status_code == 200
        data = response.json()
        assert data["correlation_id"] != "none"
