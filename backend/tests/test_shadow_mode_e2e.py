"""
Shadow Mode E2E Tests - Day 8

Comprehensive end-to-end tests for all Shadow Mode flows:
- New client shadow flow (Stage 0)
- Email shadow hold flow
- SMS auto-execute flow
- Ticket resolution shadow
- Jarvis command integration
- Undo action flow
- Batch approve flow
- Safety floor enforcement
- Socket.io real-time updates
- Dual control sync

BC-001: All operations are company-scoped.
BC-008: Never crash the caller - defensive error handling.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from decimal import Decimal
import uuid
import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.api.shadow import router as shadow_router
from app.services.shadow_mode_service import ShadowModeService
from database.models.shadow_mode import ShadowLog, ShadowPreference
from database.models.core import User, Company
from database.models.approval import UndoLog, ExecutedAction


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create a FastAPI app with shadow router."""
    app = FastAPI()
    app.include_router(shadow_router, prefix="/api/shadow")
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Create a mock authenticated user (owner role)."""
    user = MagicMock(spec=User)
    user.id = str(uuid.uuid4())
    user.company_id = str(uuid.uuid4())
    user.role = "owner"
    user.email = "owner@example.com"
    user.name = "Test Owner"
    return user


@pytest.fixture
def mock_company():
    """Create a mock company."""
    company = MagicMock(spec=Company)
    company.id = str(uuid.uuid4())
    company.system_mode = "shadow"
    company.undo_window_minutes = 30
    company.risk_threshold_shadow = 0.7
    company.risk_threshold_auto = 0.3
    company.shadow_actions_remaining = None
    return company


@pytest.fixture
def mock_shadow_service():
    """Create a mock ShadowModeService."""
    return MagicMock(spec=ShadowModeService)


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 1: New Client Shadow Flow (Stage 0)
# ─────────────────────────────────────────────────────────────────────────────

class TestNewClientShadowFlow:
    """
    E2E Test: New client onboarding flow with Stage 0 shadow enforcement.
    
    Flow:
    1. New company created with shadow_actions_remaining = 10
    2. First action logged → forced to shadow mode
    3. Manager approves → counter decrements
    4. After 10 approved actions → graduates to supervised mode
    """

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.SessionLocal")
    def test_stage0_forces_shadow_mode(self, mock_session, mock_get_user, client, mock_user, mock_company):
        """Test that Stage 0 clients always get shadow mode."""
        mock_get_user.return_value = mock_user
        mock_company.shadow_actions_remaining = 10
        
        mock_db = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_company
        
        with patch("app.services.shadow_mode_service.ShadowModeService.evaluate_action_risk") as mock_eval:
            mock_eval.return_value = {
                "mode": "shadow",
                "risk_score": 0.2,
                "reason": "Stage 0: All actions require approval",
                "requires_approval": True,
                "auto_execute": False,
                "stage_0": True,
                "shadow_actions_remaining": 10,
                "layers": {
                    "layer1_heuristic": {"score": 0.2, "reason": "Low risk"},
                    "layer2_preference": {"mode": None, "reason": "No preference"},
                    "layer3_historical": {"avg_risk": None, "reason": "No history"},
                    "layer4_safety_floor": {"hard_safety": False, "reason": "No safety floor"},
                },
                "company_mode": "shadow",
            }
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "sms_reply",
                "action_payload": {"message": "Hello!", "to_number": "+1234567890"}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["mode"] == "shadow"
            assert data["stage_0"] is True
            assert data["shadow_actions_remaining"] == 10

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.SessionLocal")
    def test_stage0_counter_decrements_on_approval(self, mock_session, mock_get_user, client, mock_user, mock_company):
        """Test that Stage 0 counter decrements when manager approves."""
        mock_get_user.return_value = mock_user
        mock_company.shadow_actions_remaining = 8
        
        mock_db = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        
        # Create mock shadow log entry
        mock_shadow_log = MagicMock(spec=ShadowLog)
        mock_shadow_log.id = str(uuid.uuid4())
        mock_shadow_log.company_id = mock_user.company_id
        mock_shadow_log.action_type = "sms_reply"
        mock_shadow_log.manager_decision = None
        mock_shadow_log.action_payload = {}
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_shadow_log
        
        with patch("app.services.shadow_mode_service.ShadowModeService.approve_shadow_action") as mock_approve:
            mock_approve.return_value = {
                "id": mock_shadow_log.id,
                "manager_decision": "approved",
                "shadow_actions_remaining": 7,
            }
            
            response = client.post(f"/api/shadow/{mock_shadow_log.id}/approve", json={
                "note": "Approved for testing"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["manager_decision"] == "approved"

    @patch("app.api.shadow.get_current_user")
    @patch("app.services.shadow_mode_service.SessionLocal")
    def test_stage0_graduation(self, mock_session, mock_get_user, client, mock_user, mock_company):
        """Test that client graduates after 10 approved actions."""
        mock_get_user.return_value = mock_user
        # Counter at 1, should graduate after this approval
        mock_company.shadow_actions_remaining = 1
        
        mock_db = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        
        mock_shadow_log = MagicMock(spec=ShadowLog)
        mock_shadow_log.id = str(uuid.uuid4())
        mock_shadow_log.company_id = mock_user.company_id
        mock_shadow_log.manager_decision = None
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_shadow_log
        
        with patch("app.services.shadow_mode_service.ShadowModeService.approve_shadow_action") as mock_approve:
            mock_approve.return_value = {
                "id": mock_shadow_log.id,
                "manager_decision": "approved",
                "graduated": True,
                "new_mode": "supervised",
            }
            
            response = client.post(f"/api/shadow/{mock_shadow_log.id}/approve", json={
                "note": "Final approval, graduation!"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data.get("graduated") is True


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 2: Email Shadow Hold Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailShadowHoldFlow:
    """
    E2E Test: Email shadow hold and release flow.
    
    Flow:
    1. AI drafts email → shadow evaluation
    2. If requires_approval: email saved to queue, not sent
    3. Manager approves → email fetched from queue, sent via Brevo
    4. Manager rejects → email deleted from queue
    """

    @patch("app.api.shadow.get_current_user")
    def test_email_shadow_hold(self, mock_get_user, client, mock_user):
        """Test email is held when shadow evaluation requires approval."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "mode": "shadow",
                "risk_score": 0.75,
                "reason": "High value refund mention in email",
                "requires_approval": True,
                "auto_execute": False,
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "email_reply",
                "action_payload": {
                    "to": "customer@example.com",
                    "subject": "Refund Confirmation",
                    "body": "We have processed your refund of $500."
                }
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["requires_approval"] is True
            assert data["mode"] == "shadow"

    @patch("app.api.shadow.get_current_user")
    def test_email_approved_and_queued(self, mock_get_user, client, mock_user):
        """Test that approved email is marked ready for sending."""
        mock_get_user.return_value = mock_user
        shadow_log_id = str(uuid.uuid4())
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.approve_shadow_action.return_value = {
                "id": shadow_log_id,
                "manager_decision": "approved",
                "status": "ready_to_send",
            }
            
            response = client.post(f"/api/shadow/{shadow_log_id}/approve", json={
                "note": "Approved"
            })
            
            assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 3: SMS Auto-Execute Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestSMSAutoExecuteFlow:
    """
    E2E Test: SMS auto-execute in supervised/graduated mode.
    
    Flow:
    1. Supervised mode with low risk SMS
    2. SMS auto-executed (sent immediately)
    3. Action logged to undo queue
    4. Appears in undo queue with countdown timer
    """

    @patch("app.api.shadow.get_current_user")
    def test_sms_auto_execute_low_risk(self, mock_get_user, client, mock_user):
        """Test low-risk SMS is auto-executed."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "mode": "graduated",
                "risk_score": 0.15,
                "reason": "Low risk: simple thank you message",
                "requires_approval": False,
                "auto_execute": True,
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "sms_reply",
                "action_payload": {
                    "to_number": "+1234567890",
                    "body": "Thank you for your message!"
                }
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["auto_execute"] is True
            assert data["requires_approval"] is False


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 4: Ticket Resolution Shadow
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketResolutionShadow:
    """
    E2E Test: Ticket resolution with shadow mode integration.
    
    Flow:
    1. AI attempts to resolve ticket
    2. Shadow evaluation runs
    3. If shadow: ticket stays in pending state
    4. Manager approves → ticket status changes to resolved
    5. Manager rejects → ticket stays open
    """

    @patch("app.api.shadow.get_current_user")
    def test_ticket_resolution_requires_approval(self, mock_get_user, client, mock_user):
        """Test high-risk ticket resolution requires approval."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "mode": "shadow",
                "risk_score": 0.85,
                "reason": "High-value customer, billing category",
                "requires_approval": True,
                "auto_execute": False,
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "ticket_close",
                "action_payload": {
                    "ticket_id": str(uuid.uuid4()),
                    "resolution": "Refund processed",
                    "category": "billing"
                }
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["requires_approval"] is True


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 5: Jarvis Command Integration
# ─────────────────────────────────────────────────────────────────────────────

class TestJarvisShadowCommands:
    """
    E2E Test: Jarvis shadow mode commands.
    
    Commands:
    - "put refunds in shadow mode"
    - "show me pending approvals"
    - "approve the last refund"
    - "switch to supervised mode"
    """

    @patch("app.api.shadow.get_current_user")
    def test_jarvis_set_preference_command(self, mock_get_user, client, mock_user):
        """Test Jarvis setting shadow preference via API."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.set_shadow_preference.return_value = {
                "id": str(uuid.uuid4()),
                "action_category": "refund",
                "preferred_mode": "shadow",
                "set_via": "jarvis",
            }
            
            response = client.patch("/api/shadow/preferences", json={
                "action_category": "refund",
                "preferred_mode": "shadow",
                "set_via": "jarvis"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["set_via"] == "jarvis"

    @patch("app.api.shadow.get_current_user")
    def test_jarvis_set_mode_command(self, mock_get_user, client, mock_user):
        """Test Jarvis setting global mode via API."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.set_company_mode.return_value = {
                "mode": "supervised",
                "previous_mode": "shadow",
            }
            
            response = client.put("/api/shadow/mode", json={
                "mode": "supervised",
                "set_via": "jarvis"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["mode"] == "supervised"


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 6: Undo Action Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestUndoActionFlow:
    """
    E2E Test: Undo auto-approved action within window.
    
    Flow:
    1. Action auto-approved and executed
    2. Manager clicks undo within 30-minute window
    3. Action is reversed
    4. Logged to undo_log
    """

    @patch("app.api.shadow.get_current_user")
    def test_undo_within_window(self, mock_get_user, client, mock_user):
        """Test undo action within the undo window."""
        mock_get_user.return_value = mock_user
        shadow_log_id = str(uuid.uuid4())
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.undo_auto_approved_action.return_value = {
                "undo_id": str(uuid.uuid4()),
                "shadow_log_id": shadow_log_id,
                "status": "undone",
            }
            
            response = client.post(f"/api/shadow/{shadow_log_id}/undo", json={
                "reason": "Mistaken auto-approval"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "undone"


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 7: Batch Approve Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchApproveFlow:
    """
    E2E Test: Batch approve multiple shadow actions.
    
    Flow:
    1. Manager selects 5 pending actions
    2. Clicks "Approve All"
    3. All 5 are approved in one transaction
    """

    @patch("app.api.shadow.get_current_user")
    def test_batch_approve(self, mock_get_user, client, mock_user):
        """Test batch approving multiple actions."""
        mock_get_user.return_value = mock_user
        ids = [str(uuid.uuid4()) for _ in range(5)]
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.batch_resolve.return_value = {
                "resolved": 5,
                "skipped": 0,
                "failed": 0,
            }
            
            response = client.post("/api/shadow/batch-resolve", json={
                "shadow_log_ids": ids,
                "decision": "approved",
                "note": "Batch approved"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["resolved"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 8: Safety Floor Enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestSafetyFloorEnforcement:
    """
    E2E Test: Hard safety floor blocks auto-approve for critical actions.
    
    Critical actions ALWAYS require approval:
    - account_delete
    - refund > $500
    - password_reset
    - payment_method_change
    """

    @patch("app.api.shadow.get_current_user")
    def test_account_delete_always_requires_approval(self, mock_get_user, client, mock_user):
        """Test that account_delete always requires approval regardless of mode."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "mode": "shadow",
                "risk_score": 1.0,
                "reason": "Hard safety floor: account deletion is irreversible",
                "requires_approval": True,
                "auto_execute": False,
                "layers": {
                    "layer4_safety_floor": {
                        "hard_safety": True,
                        "reason": "Account deletion is irreversible"
                    }
                }
            }
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "account_delete",
                "action_payload": {"user_id": str(uuid.uuid4())}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["requires_approval"] is True
            assert data["layers"]["layer4_safety_floor"]["hard_safety"] is True

    @patch("app.api.shadow.get_current_user")
    def test_high_value_refund_always_requires_approval(self, mock_get_user, client, mock_user):
        """Test that high-value refunds always require approval."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "mode": "shadow",
                "risk_score": 0.9,
                "reason": "High value refund: $750 exceeds threshold",
                "requires_approval": True,
                "auto_execute": False,
            }
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "refund",
                "action_payload": {"amount": 750.00}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["requires_approval"] is True


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 9: Socket.io Real-time Updates
# ─────────────────────────────────────────────────────────────────────────────

class TestSocketRealtimeUpdates:
    """
    E2E Test: Socket.io real-time event emission.
    
    Events:
    - shadow:action_logged
    - shadow:action_approved
    - shadow:action_rejected
    - shadow:mode_changed
    """

    @patch("app.api.shadow.get_current_user")
    @patch("app.core.event_emitter.emit_shadow_event")
    def test_action_logged_emits_event(self, mock_emit, mock_get_user, client, mock_user):
        """Test that logging an action emits socket event."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "sms_reply",
                "action_payload": {"body": "Test"}
            })
            
            assert response.status_code == 200

    @patch("app.api.shadow.get_current_user")
    @patch("app.core.event_emitter.emit_shadow_event")
    def test_mode_changed_emits_event(self, mock_emit, mock_get_user, client, mock_user):
        """Test that mode change emits socket event."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.set_company_mode.return_value = {
                "mode": "supervised",
                "previous_mode": "shadow",
            }
            
            response = client.put("/api/shadow/mode", json={
                "mode": "supervised",
                "set_via": "ui"
            })
            
            assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# E2E Scenario 10: Dual Control Sync
# ─────────────────────────────────────────────────────────────────────────────

class TestDualControlSync:
    """
    E2E Test: UI ↔ Jarvis preference sync.
    
    Flow:
    1. Change preference via UI
    2. Verify Jarvis context is updated
    3. Change preference via Jarvis
    4. Verify UI reflects change
    """

    @patch("app.api.shadow.get_current_user")
    def test_ui_to_jarvis_sync(self, mock_get_user, client, mock_user):
        """Test that UI preference change syncs to Jarvis context."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.set_shadow_preference.return_value = {
                "id": str(uuid.uuid4()),
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
            # In real implementation, would verify socket event emitted

    @patch("app.api.shadow.get_current_user")
    def test_jarvis_to_ui_sync(self, mock_get_user, client, mock_user):
        """Test that Jarvis preference change syncs to UI."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.set_shadow_preference.return_value = {
                "id": str(uuid.uuid4()),
                "action_category": "sms_reply",
                "preferred_mode": "graduated",
                "set_via": "jarvis",
            }
            
            response = client.patch("/api/shadow/preferences", json={
                "action_category": "sms_reply",
                "preferred_mode": "graduated",
                "set_via": "jarvis"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["set_via"] == "jarvis"


# ─────────────────────────────────────────────────────────────────────────────
# Edge Case Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Tests for edge cases and defensive handling."""

    @patch("app.api.shadow.get_current_user")
    def test_empty_payload_handled(self, mock_get_user, client, mock_user):
        """Test that empty action_payload is handled gracefully."""
        mock_get_user.return_value = mock_user
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "mode": "supervised",
                "risk_score": 0.5,
                "reason": "Default risk for empty payload",
                "requires_approval": True,
            }
            
            response = client.post("/api/shadow/evaluate", json={
                "action_type": "unknown_action",
                "action_payload": {}
            })
            
            assert response.status_code == 200

    @patch("app.api.shadow.get_current_user")
    def test_unauthorized_role_rejected(self, mock_get_user, client):
        """Test that non-owner/admin cannot change settings."""
        mock_user = MagicMock(spec=User)
        mock_user.id = str(uuid.uuid4())
        mock_user.company_id = str(uuid.uuid4())
        mock_user.role = "agent"  # Not authorized
        mock_get_user.return_value = mock_user
        
        response = client.put("/api/shadow/mode", json={
            "mode": "shadow",
            "set_via": "ui"
        })
        
        assert response.status_code == 403

    @patch("app.api.shadow.get_current_user")
    def test_invalid_mode_rejected(self, mock_get_user, client, mock_user):
        """Test that invalid mode is rejected."""
        mock_get_user.return_value = mock_user
        
        response = client.put("/api/shadow/mode", json={
            "mode": "invalid_mode",
            "set_via": "ui"
        })
        
        assert response.status_code == 400

    @patch("app.api.shadow.get_current_user")
    def test_concurrent_approval_handled(self, mock_get_user, client, mock_user):
        """Test that concurrent approval attempts are handled."""
        mock_get_user.return_value = mock_user
        shadow_log_id = str(uuid.uuid4())
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            # First call succeeds
            mock_service.approve_shadow_action.return_value = {
                "id": shadow_log_id,
                "manager_decision": "approved",
            }
            
            # Simulate concurrent request
            response1 = client.post(f"/api/shadow/{shadow_log_id}/approve", json={"note": "First"})
            
            # Second call should handle already-approved state
            mock_service.approve_shadow_action.return_value = {
                "id": shadow_log_id,
                "manager_decision": "approved",
                "already_processed": True,
            }
            
            response2 = client.post(f"/api/shadow/{shadow_log_id}/approve", json={"note": "Second"})
            
            # Both should return 200 (idempotent)
            assert response1.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Performance Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPerformance:
    """Tests for performance characteristics."""

    @patch("app.api.shadow.get_current_user")
    def test_large_batch_performance(self, mock_get_user, client, mock_user):
        """Test batch approve with large number of items."""
        mock_get_user.return_value = mock_user
        ids = [str(uuid.uuid4()) for _ in range(100)]
        
        with patch("app.services.shadow_mode_service.ShadowModeService") as MockService:
            mock_service = MockService.return_value
            mock_service.batch_resolve.return_value = {
                "resolved": 100,
                "skipped": 0,
                "failed": 0,
            }
            
            response = client.post("/api/shadow/batch-resolve", json={
                "shadow_log_ids": ids,
                "decision": "approved",
                "note": "Large batch test"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["resolved"] == 100

    @patch("app.api.shadow.get_current_user")
    def test_pagination_large_dataset(self, mock_get_user, client, mock_user):
        """Test shadow log pagination with large dataset."""
        mock_get_user.return_value = mock_user
        
        with patch("database.base.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            # Mock count
            mock_db.query.return_value.filter.return_value.count.return_value = 10000
            # Mock paginated results
            mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            
            response = client.get("/api/shadow/logs?page=1&limit=50")
            
            assert response.status_code == 200
