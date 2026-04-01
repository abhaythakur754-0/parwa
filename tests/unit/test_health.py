"""
Tests for PARWA Health Endpoints (main.py)

BC-012: /health, /ready, /metrics must exist and return 200.
BC-012: 404 must return structured JSON with no stack traces.
BC-011: OpenAPI schema must be hidden when DEBUG=False.
BC-012: 500 handler must never expose stack traces.
"""


class TestHealthEndpoints:
    """BC-012: Health endpoints mandatory."""

    def test_health_returns_200(self, client):
        """GET /health returns 200 with healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data

    def test_ready_returns_200(self, client):
        """GET /ready returns 200 with ready status."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_metrics_returns_200(self, client):
        """GET /metrics returns 200 with Prometheus-style text."""
        response = client.get("/metrics")
        assert response.status_code == 200
        content = response.text
        assert "parwa_build_info" in content
        assert "parwa_health_check" in content
        assert 'version="0.1.0"' in content


class TestErrorResponses:
    """BC-012: Structured JSON errors, no stack traces to users."""

    def test_404_returns_structured_json(self, client):
        """Unknown path returns structured 404 JSON (BC-012)."""
        response = client.get("/nonexistent_path_that_does_not_exist")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "message" in data["error"]

    def test_404_no_stack_traces(self, client):
        """404 response must NEVER contain stack traces (BC-012)."""
        response = client.get("/another_fake_path_xyz")
        data = response.json()
        text = response.text.lower()
        # Must not leak stack traces
        assert "traceback" not in text
        assert "stacktrace" not in text
        assert "exception" not in text
        assert "file " not in text
        assert "line " not in text
        # Must be structured
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"

    def test_error_response_has_code_message_details(self, client):
        """All error responses follow structured format."""
        response = client.get("/bad_route_12345")
        data = response.json()
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "details" in error


class TestParwaBaseExceptionHandler:
    """BC-012: ParwaBaseError subclasses handled with structured JSON."""

    def test_not_found_error_returns_404(self, client):
        """NotFoundError → 404 with structured JSON."""
        response = client.get("/test/raise/not-found")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "Test resource not found"
        assert data["error"]["details"] == {"id": "123"}

    def test_validation_error_returns_422(self, client):
        """ValidationError → 422 with structured JSON."""
        response = client.get("/test/raise/validation")
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "Test validation"
        assert data["error"]["details"] == ["field x invalid"]

    def test_authentication_error_returns_401(self, client):
        """AuthenticationError → 401 with structured JSON."""
        response = client.get("/test/raise/authentication")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"
        assert data["error"]["details"] == {"reason": "bad token"}

    def test_authorization_error_returns_403(self, client):
        """AuthorizationError → 403 with structured JSON."""
        response = client.get("/test/raise/authorization")
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "AUTHORIZATION_ERROR"
        assert data["error"]["details"] == {"required": "admin"}

    def test_rate_limit_error_returns_429(self, client):
        """RateLimitError → 429 with structured JSON."""
        response = client.get("/test/raise/rate-limit")
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert data["error"]["details"] == {"retry_after": 60}


class TestInternalErrorHandler:
    """BC-012: 500 handler must NEVER expose internal details."""

    def test_unhandled_error_returns_500(self, client_no_raise):
        """Unexpected exception (ValueError) → 500."""
        response = client_no_raise.get("/test/raise/internal")
        assert response.status_code == 500

    def test_500_has_structured_json(self, client_no_raise):
        """500 response follows structured format."""
        response = client_no_raise.get("/test/raise/internal")
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INTERNAL_ERROR"
        assert data["error"]["message"] == "An internal error occurred"
        assert data["error"]["details"] is None

    def test_500_no_stack_trace(self, client_no_raise):
        """500 must NEVER contain stack traces or error details."""
        response = client_no_raise.get("/test/raise/internal")
        text = response.text.lower()
        assert "traceback" not in text
        assert "stacktrace" not in text
        assert "valueerror" not in text  # the actual exception type
        assert "simulates" not in text  # internal error message
        assert "file " not in text
        assert "line " not in text

    def test_500_generic_message_only(self, client_no_raise):
        """500 shows generic message, never the real error."""
        response = client_no_raise.get("/test/raise/internal")
        data = response.json()
        assert data["error"]["message"] == "An internal error occurred"
        # The real error ("This simulates...") must NOT appear
        assert "simulates" not in response.text


class TestOpenAPISecurity:
    """BC-011: OpenAPI schema must be hidden when DEBUG=False."""

    def test_openapi_hidden_by_default(self, client):
        """DEBUG=False (default) → OpenAPI endpoints return 404."""
        response = client.get("/openapi.json")
        assert response.status_code == 404

    def test_docs_hidden_by_default(self, client):
        """DEBUG=False → /docs returns 404."""
        response = client.get("/docs")
        assert response.status_code == 404

    def test_redoc_hidden_by_default(self, client):
        """DEBUG=False → /redoc returns 404."""
        response = client.get("/redoc")
        assert response.status_code == 404
