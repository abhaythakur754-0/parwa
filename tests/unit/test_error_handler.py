"""
Tests for backend/app/middleware/error_handler.py

Tests correlation ID generation, structured error responses,
no stack traces to users (BC-012), and error propagation.
"""

import json
import os
import uuid

# Set env BEFORE imports
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

from backend.app.exceptions import (  # noqa: E402
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from backend.app.middleware.error_handler import (  # noqa: E402
    ErrorHandlerMiddleware,
    build_error_response,
    get_correlation_id,
    _status_to_error_code,
)
from starlette.exceptions import (  # noqa: E402
    HTTPException as StarletteHTTPException,
)


class TestGetCorrelationId:
    """Tests for correlation ID extraction/generation."""

    def test_generates_uuid_when_no_header(self):
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        cid = get_correlation_id(request)
        assert cid is not None
        assert len(cid) == 36
        uuid.UUID(cid)  # raises if invalid

    def test_uses_existing_header(self):
        test_id = "test-correlation-123"
        scope = {
            "type": "http", "method": "GET",
            "headers": [(b"x-correlation-id", test_id.encode())],
            "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        assert get_correlation_id(request) == test_id

    def test_generates_new_when_header_too_long(self):
        long_id = "x" * 100
        scope = {
            "type": "http", "method": "GET",
            "headers": [(b"x-correlation-id", long_id.encode())],
            "query_string": b"", "path": "/test",
        }
        cid = get_correlation_id(Request(scope))
        assert cid != long_id
        assert len(cid) == 36

    def test_sanitizes_special_characters(self):
        malicious = "<script>alert(1)</script>"
        scope = {
            "type": "http", "method": "GET",
            "headers": [(b"x-correlation-id", malicious.encode())],
            "query_string": b"", "path": "/test",
        }
        cid = get_correlation_id(Request(scope))
        assert cid != malicious
        assert "<" not in cid

    def test_accepts_alphanumeric_hyphen_underscore(self):
        valid_id = "abc-123_XYZ_456"
        scope = {
            "type": "http", "method": "GET",
            "headers": [(b"x-correlation-id", valid_id.encode())],
            "query_string": b"", "path": "/test",
        }
        assert get_correlation_id(Request(scope)) == valid_id


class TestBuildErrorResponse:
    """Tests for build_error_response() helper."""

    def test_basic_error_structure(self):
        response = build_error_response(404, "NOT_FOUND", "Resource not found")
        assert response.status_code == 404
        data = json.loads(response.body.decode())
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "Resource not found"

    def test_has_error_wrapper(self):
        response = build_error_response(400, "BAD_REQUEST", "Bad request")
        data = json.loads(response.body.decode())
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]

    def test_details_field(self):
        response = build_error_response(
            422, "VALIDATION_ERROR", "Validation failed",
            details={"field": "email", "error": "invalid"},
        )
        data = json.loads(response.body.decode())
        assert data["error"]["details"]["field"] == "email"

    def test_with_correlation_id(self):
        response = build_error_response(
            500, "INTERNAL_ERROR", "Server error",
            correlation_id="test-123",
        )
        data = json.loads(response.body.decode())
        assert data["correlation_id"] == "test-123"

    def test_without_correlation_id(self):
        response = build_error_response(400, "BAD_REQUEST", "Bad")
        data = json.loads(response.body.decode())
        assert "correlation_id" not in data

    def test_details_none(self):
        response = build_error_response(
            404, "NOT_FOUND", "Not found", details=None,
        )
        data = json.loads(response.body.decode())
        assert data["error"]["details"] is None


def _make_app(handler):
    """Create a Starlette app with error handler middleware for testing."""
    app = Starlette(routes=[Route("/test", handler)])
    app.add_middleware(ErrorHandlerMiddleware)
    return app


class TestErrorHandlerMiddleware:
    """Tests for ErrorHandlerMiddleware integration."""

    def test_middleware_sets_correlation_id_on_success(self):
        async def ok_handler(request):
            return JSONResponse({"status": "ok"})
        client = TestClient(_make_app(ok_handler))
        response = client.get("/test")
        assert response.status_code == 200
        assert "x-correlation-id" in response.headers
        assert len(response.headers["x-correlation-id"]) == 36

    def test_middleware_propagates_existing_correlation_id(self):
        async def ok_handler(request):
            return JSONResponse({"status": "ok"})
        client = TestClient(_make_app(ok_handler))
        response = client.get(
            "/test", headers={"X-Correlation-ID": "existing-id"},
        )
        assert response.headers["x-correlation-id"] == "existing-id"

    def test_handles_parwa_error_with_structured_json(self):
        async def error_handler(request):
            raise NotFoundError(
                message="Test not found", details={"id": "abc"},
            )
        client = TestClient(
            _make_app(error_handler),
            raise_server_exceptions=False,
        )
        response = client.get("/test")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "Test not found"
        assert data["error"]["details"]["id"] == "abc"
        assert "correlation_id" in data

    def test_no_stack_trace_in_error_response(self):
        async def crash_handler(request):
            raise ValueError(
                "secret internal error with stack trace info"
            )
        client = TestClient(
            _make_app(crash_handler),
            raise_server_exceptions=False,
        )
        response = client.get("/test")
        assert response.status_code == 500
        data = response.json()
        # BC-012: NO stack trace, NO internal details
        assert data["error"]["message"] == "An internal error occurred"
        assert data["error"]["details"] is None
        assert "stack" not in str(data).lower()
        assert "traceback" not in str(data).lower()
        assert "ValueError" not in str(data)
        assert "secret internal error" not in str(data)

    def test_unexpected_error_has_correlation_id(self):
        async def crash_handler(request):
            raise RuntimeError("unexpected")
        client = TestClient(
            _make_app(crash_handler),
            raise_server_exceptions=False,
        )
        response = client.get("/test")
        data = response.json()
        assert "correlation_id" in data
        assert data["correlation_id"] is not None

    def test_authentication_error_structured(self):
        async def auth_handler(request):
            raise AuthenticationError(
                message="Invalid credentials",
            )
        client = TestClient(
            _make_app(auth_handler),
            raise_server_exceptions=False,
        )
        response = client.get("/test")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"

    def test_rate_limit_error_structured(self):
        async def rate_handler(request):
            raise RateLimitError(
                message="Too many requests",
            )
        client = TestClient(
            _make_app(rate_handler),
            raise_server_exceptions=False,
        )
        response = client.get("/test")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_validation_error_structured(self):
        async def val_handler(request):
            raise ValidationError(
                message="Bad input",
                details=["email required"],
            )
        client = TestClient(
            _make_app(val_handler),
            raise_server_exceptions=False,
        )
        response = client.get("/test")
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["details"] == ["email required"]

    def test_authorization_error_structured(self):
        async def authz_handler(request):
            raise AuthorizationError(
                message="No permission", details={"role": "viewer"},
            )
        client = TestClient(
            _make_app(authz_handler),
            raise_server_exceptions=False,
        )
        response = client.get("/test")
        assert response.status_code == 403
        assert response.json()["error"]["details"]["role"] == "viewer"

    def test_starlette_404_preserved(self):
        """Starlette HTTPException preserved as structured JSON.

        Note: Starlette's ExceptionMiddleware intercepts HTTPException
        before BaseHTTPMiddleware can catch it. We test the handler
        method directly. In FastAPI this will be the app-level
        exception handler.
        """
        mw = ErrorHandlerMiddleware(app=None)
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        exc = StarletteHTTPException(status_code=404, detail="Not Found")
        response = mw._handle_http_exception(request, exc, "test-cid")
        assert response.status_code == 404
        data = json.loads(response.body.decode())
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "Not Found"
        assert data["correlation_id"] == "test-cid"
        assert response.headers["x-correlation-id"] == "test-cid"

    def test_starlette_401_preserved(self):
        mw = ErrorHandlerMiddleware(app=None)
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        exc = StarletteHTTPException(
            status_code=401, detail="Unauthorized",
        )
        response = mw._handle_http_exception(request, exc, "test-cid")
        assert response.status_code == 401
        data = json.loads(response.body.decode())
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"

    def test_starlette_403_preserved(self):
        mw = ErrorHandlerMiddleware(app=None)
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        exc = StarletteHTTPException(
            status_code=403, detail="Forbidden",
        )
        response = mw._handle_http_exception(request, exc, "test-cid")
        assert response.status_code == 403
        resp_data = json.loads(response.body.decode())
        assert resp_data["error"]["code"] == "AUTHORIZATION_ERROR"

    def test_starlette_422_preserved(self):
        mw = ErrorHandlerMiddleware(app=None)
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        exc = StarletteHTTPException(
            status_code=422, detail="Validation Error",
        )
        response = mw._handle_http_exception(request, exc, "test-cid")
        assert response.status_code == 422
        resp_data = json.loads(response.body.decode())
        assert resp_data["error"]["code"] == "VALIDATION_ERROR"

    def test_starlette_429_preserved(self):
        mw = ErrorHandlerMiddleware(app=None)
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        exc = StarletteHTTPException(
            status_code=429, detail="Rate limited",
        )
        response = mw._handle_http_exception(request, exc, "test-cid")
        assert response.status_code == 429
        resp_data = json.loads(response.body.decode())
        assert resp_data["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_starlette_http_exception_has_correlation_header(self):
        mw = ErrorHandlerMiddleware(app=None)
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        exc = StarletteHTTPException(status_code=404, detail="Gone")
        response = mw._handle_http_exception(request, exc, "test-cid")
        assert "x-correlation-id" in response.headers

    def test_starlette_unknown_status_maps_to_http_error(self):
        mw = ErrorHandlerMiddleware(app=None)
        scope = {
            "type": "http", "method": "GET",
            "headers": [], "query_string": b"", "path": "/test",
        }
        request = Request(scope)
        exc = StarletteHTTPException(
            status_code=418, detail="I'm a teapot",
        )
        response = mw._handle_http_exception(request, exc, "test-cid")
        assert response.status_code == 418
        resp_data = json.loads(response.body.decode())
        assert resp_data["error"]["code"] == "HTTP_ERROR"


class TestStatusToErrorCode:
    """Tests for _status_to_error_code() helper."""

    def test_400_maps_to_bad_request(self):
        assert _status_to_error_code(400) == "BAD_REQUEST"

    def test_401_maps_to_authentication_error(self):
        assert _status_to_error_code(401) == "AUTHENTICATION_ERROR"

    def test_403_maps_to_authorization_error(self):
        assert _status_to_error_code(403) == "AUTHORIZATION_ERROR"

    def test_404_maps_to_not_found(self):
        assert _status_to_error_code(404) == "NOT_FOUND"

    def test_405_maps_to_method_not_allowed(self):
        assert _status_to_error_code(405) == "METHOD_NOT_ALLOWED"

    def test_422_maps_to_validation_error(self):
        assert _status_to_error_code(422) == "VALIDATION_ERROR"

    def test_429_maps_to_rate_limit_exceeded(self):
        assert _status_to_error_code(429) == "RATE_LIMIT_EXCEEDED"

    def test_unknown_maps_to_http_error(self):
        assert _status_to_error_code(418) == "HTTP_ERROR"

    def test_500_maps_to_http_error(self):
        assert _status_to_error_code(500) == "HTTP_ERROR"

    def test_200_maps_to_http_error(self):
        assert _status_to_error_code(200) == "HTTP_ERROR"
