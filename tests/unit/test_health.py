"""
Tests for PARWA Health Endpoints (main.py)

BC-012: /health, /ready, /metrics must exist and return 200.
BC-012: 404 must return structured JSON with no stack traces.
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
