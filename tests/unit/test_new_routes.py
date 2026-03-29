"""
Unit tests for new API routes: cold_start, undo, burst.

Tests:
- POST /cold-start returns 200
- POST /undo returns 200
- GET /burst/status returns state
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.cold_start import router as cold_start_router
from backend.api.routes.undo import router as undo_router
from backend.api.routes.burst import router as burst_router
from backend.services.cold_start import (
    ColdStartService,
    BootstrapStatus,
    BootstrapResult,
    IndustryAnalysis,
)
from backend.services.undo_manager import (
    UndoManager,
    Snapshot,
    SnapshotStatus,
    SnapshotType,
    RestoreResult,
)
from backend.services.burst_mode import (
    BurstModeService,
    BurstState,
    BurstSession,
    TriggerType,
)


# --- Fixtures ---

@pytest.fixture
def app():
    """Create a FastAPI app with all routers."""
    app = FastAPI()
    app.include_router(cold_start_router)
    app.include_router(undo_router)
    app.include_router(burst_router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


# --- Cold Start Tests ---

class TestColdStartRoutes:
    """Tests for cold start API routes."""

    def test_post_cold_start_returns_200(self, client):
        """Test: POST /cold-start returns 200."""
        response = client.post(
            "/cold-start",
            json={
                "client_name": "Test Company",
                "industry": "ecommerce",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "client_id" in data
        assert data["status"] in ["pending", "in_progress", "completed", "failed"]
        assert data["knowledge_base_ready"] in [True, False]
        assert data["configuration_applied"] in [True, False]

    def test_post_cold_start_with_custom_config(self, client):
        """Test POST /cold-start with custom configuration."""
        response = client.post(
            "/cold-start",
            json={
                "client_name": "Custom Company",
                "industry": "saas",
                "custom_config": {
                    "features": ["api_access", "webhooks"],
                    "timezone": "UTC",
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["industry"] == "saas"

    def test_post_cold_start_auto_industry_detection(self, client):
        """Test POST /cold-start without industry (auto-detect)."""
        response = client.post(
            "/cold-start",
            json={
                "client_name": "Shop Store",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "client_id" in data

    def test_get_cold_start_status_returns_200(self, client):
        """Test GET /cold-start/{client_id}/status returns 200."""
        # First create a client
        create_response = client.post(
            "/cold-start",
            json={
                "client_name": "Status Test Company",
                "industry": "healthcare",
            }
        )
        client_id = create_response.json()["client_id"]

        # Then get status
        response = client.get(f"/cold-start/{client_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == client_id
        assert data["status"] == "completed"
        assert data["industry"] == "healthcare"

    def test_get_cold_start_status_not_found(self, client):
        """Test GET /cold-start/{client_id}/status with invalid ID returns 404."""
        response = client.get("/cold-start/nonexistent_client/status")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_post_cold_start_analyze_returns_200(self, client):
        """Test POST /cold-start/{client_id}/analyze returns 200."""
        response = client.post(
            "/cold-start/test_client_123/analyze",
            json={
                "client_name": "Healthcare Clinic",
                "description": "We provide medical appointments and patient care",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == "test_client_123"
        assert "detected_industry" in data
        assert "confidence_score" in data
        assert "keywords_found" in data
        assert "recommended_config" in data


# --- Undo Tests ---

class TestUndoRoutes:
    """Tests for undo API routes."""

    def test_post_undo_returns_200(self, client):
        """Test: POST /undo returns 200."""
        response = client.post(
            "/undo",
            json={
                "client_id": "client_001",
                "snapshot_type": "configuration",
                "state_data": {
                    "setting1": "value1",
                    "setting2": "value2",
                },
                "description": "Test snapshot",
                "created_by": "test_user",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "snapshot_id" in data
        assert data["client_id"] == "client_001"
        assert data["snapshot_type"] == "configuration"
        assert data["status"] == "active"
        assert "created_at" in data

    def test_post_undo_with_all_fields(self, client):
        """Test POST /undo with all fields."""
        response = client.post(
            "/undo",
            json={
                "client_id": "client_002",
                "snapshot_type": "knowledge_base",
                "state_data": {
                    "entries": ["entry1", "entry2"],
                    "version": "1.0",
                },
                "description": "KB backup before update",
                "created_by": "admin_user",
                "ttl_hours": 48,
                "metadata": {
                    "reason": "Scheduled maintenance",
                    "ticket_id": "TICKET-123",
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_type"] == "knowledge_base"
        assert data["ttl_hours"] == 48

    def test_post_undo_invalid_type_returns_400(self, client):
        """Test POST /undo with invalid snapshot type returns 400."""
        response = client.post(
            "/undo",
            json={
                "client_id": "client_003",
                "snapshot_type": "invalid_type",
                "state_data": {"key": "value"},
            }
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_post_undo_restore_returns_200(self, client):
        """Test POST /undo/{snapshot_id}/restore returns 200."""
        # First create a snapshot
        create_response = client.post(
            "/undo",
            json={
                "client_id": "client_004",
                "snapshot_type": "client_settings",
                "state_data": {
                    "theme": "dark",
                    "notifications": True,
                },
                "description": "Settings backup",
            }
        )
        snapshot_id = create_response.json()["snapshot_id"]

        # Then restore it
        response = client.post(f"/undo/{snapshot_id}/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["snapshot_id"] == snapshot_id
        assert "restored_at" in data
        assert "restored_state" in data

    def test_post_undo_restore_not_found_returns_404(self, client):
        """Test POST /undo/{snapshot_id}/restore with invalid ID returns 404."""
        response = client.post("/undo/nonexistent_snapshot/restore")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_undo_history_returns_200(self, client):
        """Test GET /undo/{client_id}/history returns 200."""
        # Create some snapshots
        client_id = "client_history_test"
        for i in range(3):
            client.post(
                "/undo",
                json={
                    "client_id": client_id,
                    "snapshot_type": "configuration",
                    "state_data": {"version": i},
                    "description": f"Snapshot {i}",
                }
            )

        # Get history
        response = client.get(f"/undo/{client_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == client_id
        assert "snapshots" in data
        assert "total" in data

    def test_get_undo_history_with_type_filter(self, client):
        """Test GET /undo/{client_id}/history with type filter."""
        client_id = "client_filter_test"
        # Create different types
        client.post(
            "/undo",
            json={
                "client_id": client_id,
                "snapshot_type": "configuration",
                "state_data": {"a": 1},
            }
        )
        client.post(
            "/undo",
            json={
                "client_id": client_id,
                "snapshot_type": "workflow",
                "state_data": {"b": 2},
            }
        )

        response = client.get(
            f"/undo/{client_id}/history",
            params={"snapshot_type": "configuration"}
        )

        assert response.status_code == 200
        data = response.json()
        # All returned snapshots should be configuration type
        for snapshot in data["snapshots"]:
            assert snapshot["snapshot_type"] == "configuration"


# --- Burst Mode Tests ---

class TestBurstRoutes:
    """Tests for burst mode API routes."""

    def test_get_burst_status_returns_state(self, client):
        """Test: GET /burst/status returns state."""
        response = client.get("/burst/status")

        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert data["state"] in ["inactive", "active", "cooldown", "throttled"]
        assert "is_active" in data
        assert "metrics" in data
        assert "activation_count" in data

    def test_get_burst_status_initial_state(self, client):
        """Test GET /burst/status returns inactive initially."""
        response = client.get("/burst/status")

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "inactive"
        assert data["is_active"] is False
        assert data["current_session"] is None

    def test_post_burst_activate_returns_200(self, client):
        """Test POST /burst/activate returns 200."""
        response = client.post(
            "/burst/activate",
            json={
                "trigger_type": "manual",
                "options": {
                    "reason": "Expected traffic spike",
                    "duration_minutes": 30,
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["state"] == "active"
        assert "session_id" in data
        assert data["trigger_type"] == "manual"

    def test_post_burst_activate_when_already_active(self, client):
        """Test POST /burst/activate when already active returns failure."""
        # First activation
        client.post("/burst/activate", json={"trigger_type": "manual"})

        # Second activation attempt
        response = client.post("/burst/activate", json={"trigger_type": "manual"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "already active" in data["message"].lower()

    def test_post_burst_deactivate_returns_200(self, client):
        """Test POST /burst/deactivate returns 200."""
        # First activate
        client.post("/burst/activate", json={"trigger_type": "manual"})

        # Then deactivate
        response = client.post("/burst/deactivate?reason=Testing")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["state"] == "cooldown"
        assert data["cooldown_duration_seconds"] is not None

    def test_post_burst_deactivate_when_not_active(self, client):
        """Test POST /burst/deactivate when not active returns failure."""
        # Try to deactivate without activating first (fresh service instance)
        response = client.post("/burst/deactivate")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not active" in data["message"].lower()

    def test_get_burst_metrics_returns_200(self, client):
        """Test GET /burst/metrics returns 200."""
        response = client.get("/burst/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "current_metrics" in data
        assert "current_state" in data
        assert "statistics" in data
        assert "thresholds" in data
        assert "triggers_breakdown" in data
        assert "recent_sessions" in data

    def test_get_burst_metrics_includes_thresholds(self, client):
        """Test GET /burst/metrics includes thresholds."""
        response = client.get("/burst/metrics")

        assert response.status_code == 200
        data = response.json()
        thresholds = data["thresholds"]

        assert "auto_activate_rps" in thresholds
        assert "auto_activate_queue" in thresholds
        assert "auto_activate_latency_ms" in thresholds
        assert "max_burst_duration_seconds" in thresholds
        assert "cooldown_duration_seconds" in thresholds


# --- Integration Tests ---

class TestRoutesIntegration:
    """Integration tests for route interactions."""

    def test_cold_start_full_flow(self, client):
        """Test full cold start flow: create, check status, analyze."""
        # Create
        create_response = client.post(
            "/cold-start",
            json={
                "client_name": "Integration Test Company",
            }
        )
        assert create_response.status_code == 200
        client_id = create_response.json()["client_id"]

        # Check status
        status_response = client.get(f"/cold-start/{client_id}/status")
        assert status_response.status_code == 200

        # Analyze
        analyze_response = client.post(
            f"/cold-start/{client_id}/analyze",
            json={
                "client_name": "Integration Test Company",
                "description": "An online store with shopping cart",
            }
        )
        assert analyze_response.status_code == 200

    def test_undo_snapshot_restore_flow(self, client):
        """Test undo snapshot and restore flow."""
        # Create snapshot
        create_response = client.post(
            "/undo",
            json={
                "client_id": "integration_client",
                "snapshot_type": "configuration",
                "state_data": {"setting": "original_value"},
                "description": "Before change",
            }
        )
        assert create_response.status_code == 200
        snapshot_id = create_response.json()["snapshot_id"]

        # Restore snapshot
        restore_response = client.post(f"/undo/{snapshot_id}/restore")
        assert restore_response.status_code == 200
        assert restore_response.json()["success"] is True

        # Check history
        history_response = client.get("/undo/integration_client/history")
        assert history_response.status_code == 200
        assert history_response.json()["total"] >= 1

    def test_burst_mode_lifecycle(self, client):
        """Test burst mode activation and deactivation lifecycle."""
        # Check initial status
        initial_status = client.get("/burst/status")
        assert initial_status.status_code == 200

        # Activate
        activate_response = client.post(
            "/burst/activate",
            json={"trigger_type": "manual"}
        )
        assert activate_response.status_code == 200

        # Check active status
        active_status = client.get("/burst/status")
        assert active_status.status_code == 200

        # Deactivate
        deactivate_response = client.post("/burst/deactivate")
        assert deactivate_response.status_code == 200

        # Check metrics
        metrics_response = client.get("/burst/metrics")
        assert metrics_response.status_code == 200
        assert metrics_response.json()["statistics"]["total_activations"] >= 1


# --- Edge Case Tests ---

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_cold_start_empty_client_name(self, client):
        """Test cold start with empty client name."""
        response = client.post(
            "/cold-start",
            json={"client_name": ""}
        )
        # Should still work (validation not strict)
        assert response.status_code == 200

    def test_undo_empty_state_data(self, client):
        """Test undo with empty state data."""
        response = client.post(
            "/undo",
            json={
                "client_id": "edge_case_client",
                "snapshot_type": "configuration",
                "state_data": {},
            }
        )
        assert response.status_code == 200

    def test_burst_activate_with_scheduled_trigger(self, client):
        """Test burst activate with scheduled trigger type."""
        response = client.post(
            "/burst/activate",
            json={
                "trigger_type": "scheduled",
                "options": {"scheduled_time": "2024-01-01T00:00:00Z"}
            }
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_undo_history_empty_client(self, client):
        """Test undo history for client with no snapshots."""
        response = client.get("/undo/nonexistent_client_history/history")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_cold_start_analyze_with_keywords(self, client):
        """Test analyze with keywords list."""
        response = client.post(
            "/cold-start/test_analyze/analyze",
            json={
                "client_name": "Keyword Test",
                "keywords": ["patient", "appointment", "medical", "healthcare"],
            }
        )
        assert response.status_code == 200
        data = response.json()
        # Should detect healthcare based on keywords
        assert data["detected_industry"] == "healthcare"
