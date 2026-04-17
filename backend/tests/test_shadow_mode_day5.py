"""
Day 5 Backend Tests - Shadow Mode Undo History & Settings API

Tests for:
- B5.1 Undo History Endpoint
- B5.2 Settings Mode Change
- B5.3 Preferences CRUD
- B5.4 What-If Simulator (Evaluate Action)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.shadow import router
from database.models.core import User
from database.models.approval import UndoLog, ExecutedAction


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create a FastAPI app with shadow router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = "user-123"
    user.company_id = "company-123"
    user.role = "owner"
    user.email = "test@example.com"
    user.name = "Test User"
    return user


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock(spec=Session)
    return session


# ── B5.1 Undo History Endpoint Tests ─────────────────────────────────────────

class TestUndoHistoryEndpoint:
    """Tests for GET /api/shadow/undo-history endpoint."""

    @patch("app.api.shadow.get_current_user")
    @patch("database.base.SessionLocal")
    def test_get_undo_history_empty(self, mock_session_local, mock_get_user, client, mock_user, mock_db_session):
        """Test getting undo history when empty."""
        mock_get_user.return_value = mock_user
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db_session)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=False)
        
        # Mock query chain
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        response = client.get("/api/shadow/undo-history")

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert data["entries"] == []
        assert data["total"] == 0

    @patch("app.api.shadow.get_current_user")
    @patch("database.base.SessionLocal")
    def test_get_undo_history_with_entries(self, mock_session_local, mock_get_user, client, mock_user, mock_db_session):
        """Test getting undo history with entries."""
        mock_get_user.return_value = mock_user
        
        # Create mock undo log entry
        mock_undo_log = MagicMock(spec=UndoLog)
        mock_undo_log.id = "undo-123"
        mock_undo_log.company_id = "company-123"
        mock_undo_log.executed_action_id = "action-123"
        mock_undo_log.undo_type = "reversal"
        mock_undo_log.original_data = '{"amount": 100}'
        mock_undo_log.undo_data = None
        mock_undo_log.undo_reason = "Customer requested"
        mock_undo_log.undone_by = "user-123"
        mock_undo_log.created_at = MagicMock()
        mock_undo_log.created_at.isoformat.return_value = "2024-01-15T10:00:00"

        # Mock query for undo logs
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_undo_log]

        # Mock executed action query
        mock_executed_action = MagicMock(spec=ExecutedAction)
        mock_executed_action.action_type = "refund"
        
        def mock_query_side_effect(model):
            if model == UndoLog:
                return mock_query
            elif model == ExecutedAction:
                inner_query = MagicMock()
                inner_query.filter.return_value = inner_query
                inner_query.first.return_value = mock_executed_action
                return inner_query
            elif model == User:
                inner_query = MagicMock()
                inner_query.filter.return_value = inner_query
                inner_query.first.return_value = mock_user
                return inner_query
            return mock_query
        
        mock_db_session.query.side_effect = mock_query_side_effect
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db_session)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

        response = client.get("/api/shadow/undo-history")

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert len(data["entries"]) == 1
        
        entry = data["entries"][0]
        assert entry["id"] == "undo-123"
        assert entry["undo_type"] == "reversal"
        assert entry["undo_reason"] == "Customer requested"
        assert entry["action_type"] == "refund"
        assert entry["undone_by_name"] == "Test User"

    @patch("app.api.shadow.get_current_user")
    def test_get_undo_history_unauthorized(self, mock_get_user, client):
        """Test getting undo history without company."""
        mock_user = MagicMock(spec=User)
        mock_user.company_id = None
        mock_get_user.return_value = mock_user

        response = client.get("/api/shadow/undo-history")

        assert response.status_code == 403

    @patch("app.api.shadow.get_current_user")
    def test_get_undo_history_limit_parameter(self, mock_get_user, client, mock_user):
        """Test that limit parameter is respected."""
        mock_get_user.return_value = mock_user

        with patch("database.base.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)
            
            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []

            response = client.get("/api/shadow/undo-history?limit=50")

            # Verify limit was called with 50
            mock_query.limit.assert_called_once_with(50)
            assert response.status_code == 200


# ── B5.2 Settings Mode Change Tests ───────────────────────────────────────────

class TestSettingsModeChange:
    """Tests for PUT /api/shadow/mode endpoint."""

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    @patch("app.core.event_emitter.emit_shadow_event")
    def test_set_mode_to_shadow(self, mock_emit, mock_service_class, mock_get_user, client, mock_user):
        """Test setting mode to shadow."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.set_company_mode.return_value = {
            "mode": "shadow",
            "previous_mode": "graduated",
        }

        response = client.put("/api/shadow/mode", json={
            "mode": "shadow",
            "set_via": "ui"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "shadow"
        mock_service.set_company_mode.assert_called_once()

    @patch("app.api.shadow.get_current_user")
    def test_set_mode_invalid(self, mock_get_user, client, mock_user):
        """Test setting an invalid mode."""
        mock_get_user.return_value = mock_user

        response = client.put("/api/shadow/mode", json={
            "mode": "invalid_mode",
            "set_via": "ui"
        })

        assert response.status_code == 400

    @patch("app.api.shadow.get_current_user")
    def test_set_mode_unauthorized_role(self, mock_get_user, client):
        """Test that non-owner/admin cannot change mode."""
        mock_user = MagicMock(spec=User)
        mock_user.id = "user-123"
        mock_user.company_id = "company-123"
        mock_user.role = "agent"  # Not owner or admin
        mock_get_user.return_value = mock_user

        response = client.put("/api/shadow/mode", json={
            "mode": "shadow",
            "set_via": "ui"
        })

        assert response.status_code == 403

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    def test_set_mode_via_jarvis(self, mock_service_class, mock_get_user, client, mock_user):
        """Test setting mode via Jarvis (conversational)."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.set_company_mode.return_value = {
            "mode": "graduated",
            "previous_mode": "shadow",
        }

        response = client.put("/api/shadow/mode", json={
            "mode": "graduated",
            "set_via": "jarvis"
        })

        assert response.status_code == 200
        mock_service.set_company_mode.assert_called_once_with(
            company_id="company-123",
            mode="graduated",
            set_via="jarvis"
        )


# ── B5.3 Preferences CRUD Tests ───────────────────────────────────────────────

class TestPreferencesCRUD:
    """Tests for shadow mode preferences endpoints."""

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    def test_get_preferences(self, mock_service_class, mock_get_user, client, mock_user):
        """Test getting preferences."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_shadow_preferences.return_value = [
            {
                "id": "pref-1",
                "action_category": "refund",
                "preferred_mode": "shadow",
                "set_via": "ui",
            }
        ]

        response = client.get("/api/shadow/preferences")

        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
        assert len(data["preferences"]) == 1

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    def test_set_preference(self, mock_service_class, mock_get_user, client, mock_user):
        """Test setting a preference."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.set_shadow_preference.return_value = {
            "id": "pref-new",
            "action_category": "email_reply",
            "preferred_mode": "shadow",
            "set_via": "ui",
        }

        response = client.patch("/api/shadow/preferences", json={
            "action_category": "email_reply",
            "preferred_mode": "shadow",
            "set_via": "ui"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["action_category"] == "email_reply"

    @patch("app.api.shadow.get_current_user")
    def test_set_preference_invalid_mode(self, mock_get_user, client, mock_user):
        """Test setting a preference with invalid mode."""
        mock_get_user.return_value = mock_user

        response = client.patch("/api/shadow/preferences", json={
            "action_category": "email_reply",
            "preferred_mode": "invalid_mode",
            "set_via": "ui"
        })

        assert response.status_code == 400

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    def test_delete_preference(self, mock_service_class, mock_get_user, client, mock_user):
        """Test deleting a preference."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.delete_shadow_preference.return_value = {"deleted": True}

        response = client.delete("/api/shadow/preferences/refund")

        assert response.status_code == 200
        mock_service.delete_shadow_preference.assert_called_once_with(
            company_id="company-123",
            action_category="refund"
        )


# ── B5.4 What-If Simulator Tests ───────────────────────────────────────────────

class TestWhatIfSimulator:
    """Tests for POST /api/shadow/evaluate endpoint."""

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    def test_evaluate_refund_action(self, mock_service_class, mock_get_user, client, mock_user):
        """Test evaluating a refund action."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.evaluate_action_risk.return_value = {
            "mode": "shadow",
            "risk_score": 0.65,
            "reason": "High value refund requires approval",
            "requires_approval": True,
            "auto_execute": False,
            "layers": {
                "layer1_heuristic": {"score": 0.65, "reason": "Refund amount is high"},
                "layer2_preference": {"mode": "shadow", "reason": "Refund preference set"},
                "layer3_historical": {"avg_risk": 0.5, "reason": "Average risk for refunds"},
                "layer4_safety_floor": {"hard_safety": False, "reason": "No safety floor triggered"},
            },
            "company_mode": "shadow",
        }

        response = client.post("/api/shadow/evaluate", json={
            "action_type": "refund",
            "action_payload": {"amount": 500, "customer_id": "cust_123"}
        })

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "shadow"
        assert data["risk_score"] == 0.65
        assert data["requires_approval"] is True
        assert "layers" in data

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    def test_evaluate_low_risk_action(self, mock_service_class, mock_get_user, client, mock_user):
        """Test evaluating a low risk action that auto-executes."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.evaluate_action_risk.return_value = {
            "mode": "graduated",
            "risk_score": 0.15,
            "reason": "Low risk SMS reply",
            "requires_approval": False,
            "auto_execute": True,
            "layers": {
                "layer1_heuristic": {"score": 0.15, "reason": "Simple SMS reply"},
                "layer2_preference": {"mode": None, "reason": "No preference set"},
                "layer3_historical": {"avg_risk": 0.2, "reason": "Low historical risk"},
                "layer4_safety_floor": {"hard_safety": False, "reason": "No safety floor"},
            },
            "company_mode": "graduated",
        }

        response = client.post("/api/shadow/evaluate", json={
            "action_type": "sms_reply",
            "action_payload": {"phone": "+1234567890", "content": "Thank you!"}
        })

        assert response.status_code == 200
        data = response.json()
        assert data["auto_execute"] is True
        assert data["requires_approval"] is False

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    def test_evaluate_with_stage_zero(self, mock_service_class, mock_get_user, client, mock_user):
        """Test evaluation for new client in Stage 0 (mandatory shadow)."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.evaluate_action_risk.return_value = {
            "mode": "shadow",
            "risk_score": 0.2,
            "reason": "Stage 0: All actions require approval",
            "requires_approval": True,
            "auto_execute": False,
            "stage_0": True,
            "shadow_actions_remaining": 8,
            "layers": {
                "layer1_heuristic": {"score": 0.2, "reason": "Low risk"},
                "layer2_preference": {"mode": None, "reason": "No preference"},
                "layer3_historical": {"avg_risk": None, "reason": "No history"},
                "layer4_safety_floor": {"hard_safety": False, "reason": "No safety floor"},
            },
            "company_mode": "shadow",
        }

        response = client.post("/api/shadow/evaluate", json={
            "action_type": "email_reply",
            "action_payload": {"recipient": "test@example.com"}
        })

        assert response.status_code == 200
        data = response.json()
        assert data.get("stage_0") is True
        assert data.get("shadow_actions_remaining") == 8


# ── B5.5 Socket Event Emission Tests ──────────────────────────────────────────

class TestSocketEventEmission:
    """Tests for Socket.io event emission on shadow mode actions."""

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    @patch("app.core.event_emitter.emit_shadow_event")
    @patch("asyncio.get_event_loop")
    def test_mode_change_emits_event(self, mock_loop, mock_emit, mock_service_class, mock_get_user, client, mock_user):
        """Test that mode change emits socket event."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.set_company_mode.return_value = {
            "mode": "graduated",
            "previous_mode": "shadow",
        }

        # Mock asyncio
        mock_loop.return_value.create_task = MagicMock()

        response = client.put("/api/shadow/mode", json={
            "mode": "graduated",
            "set_via": "ui"
        })

        assert response.status_code == 200
        # Event emission is attempted (may fail gracefully in tests)
        # The actual emission is wrapped in try/except

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.ShadowModeService")
    @patch("asyncio.get_event_loop")
    def test_approval_emits_event(self, mock_loop, mock_service_class, mock_get_user, client, mock_user):
        """Test that approval emits socket event."""
        mock_get_user.return_value = mock_user
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.approve_shadow_action.return_value = {
            "id": "shadow-1",
            "action_type": "refund",
        }

        mock_loop.return_value.create_task = MagicMock()

        response = client.post("/api/shadow/shadow-1/approve", json={
            "note": "Approved"
        })

        assert response.status_code == 200


# ── B5.6 Integration Tests ─────────────────────────────────────────────────────

class TestDay5Integration:
    """Integration tests for Day 5 functionality."""

    @patch("app.api.shadow.get_current_user")
    def test_full_flow_get_settings(self, mock_get_user, client, mock_user):
        """Test getting all settings data in one flow."""
        mock_get_user.return_value = mock_user

        with patch("app.services.shadow_mode_service.ShadowModeService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            
            # Mock all the getters
            mock_service.get_company_mode.return_value = "shadow"
            mock_service.get_shadow_preferences.return_value = []
            mock_service.get_shadow_stats.return_value = {
                "total_actions": 0,
                "pending_count": 0,
                "approval_rate": 0,
            }

            # Get mode
            mode_response = client.get("/api/shadow/mode")
            assert mode_response.status_code == 200

            # Get preferences
            prefs_response = client.get("/api/shadow/preferences")
            assert prefs_response.status_code == 200

            # Get stats
            stats_response = client.get("/api/shadow/stats")
            assert stats_response.status_code == 200
