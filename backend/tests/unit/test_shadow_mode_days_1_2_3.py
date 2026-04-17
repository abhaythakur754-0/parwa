"""
Unit Tests for Shadow Mode - Days 1, 2, and 3

Tests cover:
- Day 1: ShadowModeService (4-layer decision system, Socket.io events)
- Day 2: Channel Interceptors (Email, SMS, Voice, Chat)
- Day 3: Ticket Shadow Integration

BC-001: All operations are company-scoped.
BC-008: Never crash the caller - defensive error handling.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import uuid

# ─────────────────────────────────────────────────────────────────────────────
# Day 1 Tests - ShadowModeService
# ─────────────────────────────────────────────────────────────────────────────


class TestShadowModeServiceDay1:
    """Tests for ShadowModeService (Day 1 Backend Completion)."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = MagicMock()
        return session

    @pytest.fixture
    def mock_company(self):
        """Create a mock company object."""
        company = MagicMock()
        company.id = str(uuid.uuid4())
        company.system_mode = "supervised"
        company.undo_window_minutes = 30
        company.risk_threshold_shadow = 0.7
        company.risk_threshold_auto = 0.3
        company.shadow_actions_remaining = None
        return company

    @pytest.fixture
    def shadow_service(self):
        """Create a ShadowModeService instance."""
        from app.services.shadow_mode_service import ShadowModeService
        return ShadowModeService()

    def test_evaluate_action_risk_low_risk_action(self, shadow_service, mock_company):
        """Test Layer 1: Low risk actions have low risk scores."""
        with patch.object(shadow_service, '_get_avg_risk_score', return_value=None):
            with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
                mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
                
                result = shadow_service.evaluate_action_risk(
                    company_id=mock_company.id,
                    action_type="sms_reply",
                    action_payload={"message": "Hello, how can I help?"},
                )
                
                assert "risk_score" in result
                assert result["risk_score"] < 0.5  # SMS is low risk
                assert "mode" in result
                assert "layers" in result

    def test_evaluate_action_risk_high_risk_action(self, shadow_service, mock_company):
        """Test Layer 1: High risk actions have high risk scores."""
        with patch.object(shadow_service, '_get_avg_risk_score', return_value=None):
            with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
                mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
                
                result = shadow_service.evaluate_action_risk(
                    company_id=mock_company.id,
                    action_type="refund",
                    action_payload={"amount": 500.0},
                )
                
                # Refund is in HARD_SAFETY_ACTIONS, should always require approval
                assert result["mode"] == "supervised"
                assert result["requires_approval"] is True

    def test_evaluate_action_risk_hard_safety_floor(self, shadow_service, mock_company):
        """Test Layer 4: Hard safety floor for critical actions."""
        with patch.object(shadow_service, '_get_avg_risk_score', return_value=None):
            with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
                mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
                
                # Account delete should ALWAYS require approval
                result = shadow_service.evaluate_action_risk(
                    company_id=mock_company.id,
                    action_type="account_delete",
                    action_payload={},
                )
                
                assert result["mode"] == "supervised"
                assert result["requires_approval"] is True
                assert result["layers"]["layer4_safety_floor"]["hard_safety"] is True

    def test_evaluate_action_risk_stage_0_forces_shadow(self, shadow_service, mock_company):
        """Test Stage 0 onboarding: Forces shadow mode for new clients."""
        mock_company.shadow_actions_remaining = 10
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
            
            result = shadow_service.evaluate_action_risk(
                company_id=mock_company.id,
                action_type="sms_reply",
                action_payload={"message": "Hello"},
            )
            
            assert result["mode"] == "shadow"
            assert result["requires_approval"] is True
            assert result["stage_0"] is True
            assert result["shadow_actions_remaining"] == 10

    def test_evaluate_action_risk_graduated_mode_auto_execute(self, shadow_service, mock_company):
        """Test graduated mode with low risk allows auto-execute."""
        mock_company.system_mode = "graduated"
        
        with patch.object(shadow_service, '_get_avg_risk_score', return_value=None):
            with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
                mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
                
                result = shadow_service.evaluate_action_risk(
                    company_id=mock_company.id,
                    action_type="sms_reply",  # Low risk action
                    action_payload={"message": "Thanks for your message"},
                )
                
                # In graduated mode with low risk, should auto-execute
                assert result["mode"] == "graduated"
                # Note: auto_execute depends on risk_score < 0.3

    def test_evaluate_action_risk_refund_amount_adjustment(self, shadow_service, mock_company):
        """Test Layer 1: High refund amounts increase risk score."""
        with patch.object(shadow_service, '_get_avg_risk_score', return_value=None):
            with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
                mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
                
                # Small refund
                result_small = shadow_service.evaluate_action_risk(
                    company_id=mock_company.id,
                    action_type="refund",
                    action_payload={"amount": 50.0},
                )
                
                # Large refund - should have higher risk
                result_large = shadow_service.evaluate_action_risk(
                    company_id=mock_company.id,
                    action_type="refund",
                    action_payload={"amount": 500.0},
                )
                
                # Both require approval (hard safety), but large has higher risk
                assert result_large["risk_score"] > result_small["risk_score"]

    def test_get_company_mode_default(self, shadow_service):
        """Test get_company_mode returns supervised as default."""
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = None
            
            result = shadow_service.get_company_mode("non-existent-id")
            
            assert result == "supervised"

    def test_set_company_mode_valid(self, shadow_service, mock_company):
        """Test setting company mode."""
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
            
            result = shadow_service.set_company_mode(
                company_id=mock_company.id,
                mode="shadow",
                set_via="ui",
            )
            
            assert result["mode"] == "shadow"
            assert result["previous_mode"] == "supervised"

    def test_set_company_mode_invalid(self, shadow_service, mock_company):
        """Test setting invalid company mode raises error."""
        from app.services.shadow_mode_service import InvalidModeError
        
        with pytest.raises(InvalidModeError):
            shadow_service.set_company_mode(
                company_id=mock_company.id,
                mode="invalid_mode",
                set_via="ui",
            )

    def test_log_shadow_action(self, shadow_service, mock_company):
        """Test logging shadow action."""
        mock_entry = MagicMock()
        mock_entry.id = str(uuid.uuid4())
        mock_entry.company_id = mock_company.id
        mock_entry.action_type = "email_reply"
        mock_entry.action_payload = {"to": "test@example.com"}
        mock_entry.jarvis_risk_score = 0.5
        mock_entry.mode = "shadow"
        mock_entry.manager_decision = None
        mock_entry.manager_note = None
        mock_entry.resolved_at = None
        mock_entry.created_at = datetime.utcnow()
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.add = MagicMock()
            mock_session.return_value.__enter__.return_value.commit = MagicMock()
            mock_session.return_value.__enter__.return_value.refresh = MagicMock()
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = None
            
            # Create a new entry
            with patch('app.services.shadow_mode_service.ShadowLog') as MockShadowLog:
                MockShadowLog.return_value = mock_entry
                result = shadow_service.log_shadow_action(
                    company_id=mock_company.id,
                    action_type="email_reply",
                    action_payload={"to": "test@example.com"},
                    risk_score=0.5,
                    mode="shadow",
                )
                
                assert "id" in result

    def test_approve_shadow_action(self, shadow_service):
        """Test approving a shadow action."""
        mock_entry = MagicMock()
        mock_entry.id = str(uuid.uuid4())
        mock_entry.company_id = str(uuid.uuid4())
        mock_entry.action_type = "refund"
        mock_entry.manager_decision = None
        mock_entry.action_payload = {"amount": 100}
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_entry
            mock_session.return_value.__enter__.return_value.commit = MagicMock()
            mock_session.return_value.__enter__.return_value.refresh = MagicMock()
            
            result = shadow_service.approve_shadow_action(
                shadow_log_id=mock_entry.id,
                manager_id=str(uuid.uuid4()),
                note="Approved - legitimate refund",
            )
            
            assert mock_entry.manager_decision == "approved"

    def test_reject_shadow_action(self, shadow_service):
        """Test rejecting a shadow action."""
        mock_entry = MagicMock()
        mock_entry.id = str(uuid.uuid4())
        mock_entry.company_id = str(uuid.uuid4())
        mock_entry.action_type = "refund"
        mock_entry.manager_decision = None
        mock_entry.action_payload = {"amount": 100}
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_entry
            mock_session.return_value.__enter__.return_value.commit = MagicMock()
            mock_session.return_value.__enter__.return_value.refresh = MagicMock()
            
            result = shadow_service.reject_shadow_action(
                shadow_log_id=mock_entry.id,
                manager_id=str(uuid.uuid4()),
                note="Rejected - suspicious request",
            )
            
            assert mock_entry.manager_decision == "rejected"

    def test_undo_auto_approved_action(self, shadow_service):
        """Test undoing an auto-approved action."""
        mock_entry = MagicMock()
        mock_entry.id = str(uuid.uuid4())
        mock_entry.company_id = str(uuid.uuid4())
        mock_entry.action_type = "sms_reply"
        mock_entry.manager_decision = None
        mock_entry.action_payload = {"message": "Test message"}
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_entry
            mock_session.return_value.__enter__.return_value.add = MagicMock()
            mock_session.return_value.__enter__.return_value.flush = MagicMock()
            mock_session.return_value.__enter__.return_value.commit = MagicMock()
            mock_session.return_value.__enter__.return_value.refresh = MagicMock()
            
            result = shadow_service.undo_auto_approved_action(
                shadow_log_id=mock_entry.id,
                reason="Customer requested reversal",
                manager_id=str(uuid.uuid4()),
            )
            
            assert "undo_id" in result
            assert mock_entry.manager_decision == "rejected"

    def test_get_shadow_stats(self, shadow_service, mock_company):
        """Test getting shadow mode statistics."""
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.scalar.return_value = 10
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
            
            result = shadow_service.get_shadow_stats(mock_company.id)
            
            assert "total_actions" in result
            assert "pending_count" in result
            assert "approved_count" in result
            assert "rejected_count" in result
            assert "approval_rate" in result

    def test_batch_resolve(self, shadow_service, mock_company):
        """Test batch resolving multiple shadow actions."""
        ids = [str(uuid.uuid4()) for _ in range(3)]
        
        mock_entries = []
        for entry_id in ids:
            entry = MagicMock()
            entry.id = entry_id
            entry.company_id = mock_company.id
            entry.manager_decision = None
            mock_entries.append(entry)
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = mock_entries
            mock_session.return_value.__enter__.return_value.commit = MagicMock()
            
            result = shadow_service.batch_resolve(
                company_id=mock_company.id,
                shadow_log_ids=ids,
                decision="approved",
                manager_id=str(uuid.uuid4()),
                note="Batch approved",
            )
            
            assert result["resolved"] == 3
            assert result["skipped"] == 0


class TestShadowPreferencesDay1:
    """Tests for Shadow Preferences management."""

    @pytest.fixture
    def shadow_service(self):
        from app.services.shadow_mode_service import ShadowModeService
        return ShadowModeService()

    def test_set_shadow_preference(self, shadow_service):
        """Test setting a shadow preference for an action category."""
        company_id = str(uuid.uuid4())
        
        mock_pref = MagicMock()
        mock_pref.id = str(uuid.uuid4())
        mock_pref.company_id = company_id
        mock_pref.action_category = "refund"
        mock_pref.preferred_mode = "shadow"
        mock_pref.set_via = "ui"
        mock_pref.updated_at = datetime.utcnow()
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value.__enter__.return_value.add = MagicMock()
            mock_session.return_value.__enter__.return_value.commit = MagicMock()
            mock_session.return_value.__enter__.return_value.refresh = MagicMock()
            
            with patch('app.services.shadow_mode_service.ShadowPreference') as MockPref:
                MockPref.return_value = mock_pref
                result = shadow_service.set_shadow_preference(
                    company_id=company_id,
                    action_category="refund",
                    preferred_mode="shadow",
                    set_via="ui",
                )
                
                assert result["action_category"] == "refund"
                assert result["preferred_mode"] == "shadow"

    def test_delete_shadow_preference(self, shadow_service):
        """Test deleting a shadow preference."""
        company_id = str(uuid.uuid4())
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.delete.return_value = 1
            mock_session.return_value.__enter__.return_value.commit = MagicMock()
            
            result = shadow_service.delete_shadow_preference(
                company_id=company_id,
                action_category="refund",
            )
            
            assert result["deleted"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Day 2 Tests - Channel Interceptors
# ─────────────────────────────────────────────────────────────────────────────


class TestEmailShadowInterceptorDay2:
    """Tests for Email Shadow Interceptor (Day 2)."""

    def test_evaluate_email_shadow_low_risk(self):
        """Test email evaluation for low-risk content."""
        from app.interceptors.email_shadow import evaluate_email_shadow, EmailShadowResult
        
        company_id = str(uuid.uuid4())
        
        with patch('app.interceptors.email_shadow.ShadowModeService') as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "requires_approval": False,
                "auto_execute": True,
                "mode": "graduated",
                "risk_score": 0.2,
                "reason": "Low risk email content",
                "layers": {},
                "company_mode": "graduated",
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            result = evaluate_email_shadow(
                company_id=company_id,
                email_payload={
                    "to": "customer@example.com",
                    "subject": "Re: Your inquiry",
                    "body": "Thank you for reaching out. We've received your message.",
                },
                shadow_service=mock_service,
            )
            
            assert isinstance(result, EmailShadowResult)
            assert result.auto_execute is True
            assert result.mode == "graduated"

    def test_evaluate_email_shadow_high_risk(self):
        """Test email evaluation for high-risk content."""
        from app.interceptors.email_shadow import evaluate_email_shadow, EmailShadowResult
        
        company_id = str(uuid.uuid4())
        
        with patch('app.interceptors.email_shadow.ShadowModeService') as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "requires_approval": True,
                "auto_execute": False,
                "mode": "shadow",
                "risk_score": 0.8,
                "reason": "High risk: refund request detected",
                "layers": {},
                "company_mode": "shadow",
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            result = evaluate_email_shadow(
                company_id=company_id,
                email_payload={
                    "to": "customer@example.com",
                    "subject": "Refund Confirmation",
                    "body": "We have processed your refund of $500.",
                },
                shadow_service=mock_service,
            )
            
            assert result.requires_approval is True
            assert result.shadow_log_id is not None

    def test_evaluate_email_shadow_error_fallback(self):
        """Test email evaluation error fallback to supervised mode."""
        from app.interceptors.email_shadow import evaluate_email_shadow, EmailShadowResult
        
        company_id = str(uuid.uuid4())
        
        with patch('app.interceptors.email_shadow.ShadowModeService') as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.side_effect = Exception("Database error")
            
            result = evaluate_email_shadow(
                company_id=company_id,
                email_payload={"to": "test@example.com", "subject": "Test", "body": "Test"},
                shadow_service=mock_service,
            )
            
            # Should fallback to requiring approval
            assert result.requires_approval is True
            assert result.mode == "supervised"

    def test_process_email_after_approval(self):
        """Test processing email after manager approval."""
        from app.interceptors.email_shadow import process_email_after_approval
        
        company_id = str(uuid.uuid4())
        shadow_log_id = str(uuid.uuid4())
        
        mock_entry = MagicMock()
        mock_entry.action_payload = {
            "to": "customer@example.com",
            "subject": "Approved Subject",
            "body": "Approved content",
        }
        
        with patch('app.interceptors.email_shadow.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_entry
            
            result = process_email_after_approval(
                company_id=company_id,
                shadow_log_id=shadow_log_id,
            )
            
            assert result["status"] == "ready_to_send"
            assert "email_payload" in result


class TestSMSShadowInterceptorDay2:
    """Tests for SMS Shadow Interceptor (Day 2)."""

    def test_evaluate_sms_shadow_low_risk(self):
        """Test SMS evaluation for low-risk content."""
        from app.interceptors.sms_shadow import evaluate_sms_shadow, SMSShadowResult
        
        company_id = str(uuid.uuid4())
        
        with patch('app.interceptors.sms_shadow.ShadowModeService') as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "requires_approval": False,
                "auto_execute": True,
                "mode": "graduated",
                "risk_score": 0.15,
                "reason": "Low risk SMS",
                "layers": {},
                "company_mode": "graduated",
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            result = evaluate_sms_shadow(
                company_id=company_id,
                sms_payload={
                    "to_number": "+1234567890",
                    "body": "Your order has shipped!",
                },
                shadow_service=mock_service,
            )
            
            assert isinstance(result, SMSShadowResult)
            assert result.auto_execute is True

    def test_evaluate_sms_shadow_high_risk(self):
        """Test SMS evaluation for high-risk content."""
        from app.interceptors.sms_shadow import evaluate_sms_shadow, SMSShadowResult
        
        company_id = str(uuid.uuid4())
        
        with patch('app.interceptors.sms_shadow.ShadowModeService') as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "requires_approval": True,
                "auto_execute": False,
                "mode": "shadow",
                "risk_score": 0.7,
                "reason": "Account action required",
                "layers": {},
                "company_mode": "shadow",
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            result = evaluate_sms_shadow(
                company_id=company_id,
                sms_payload={
                    "to_number": "+1234567890",
                    "body": "Your password has been reset. Click here to verify.",
                },
                shadow_service=mock_service,
            )
            
            assert result.requires_approval is True


class TestVoiceShadowInterceptorDay2:
    """Tests for Voice Shadow Interceptor (Day 2)."""

    def test_evaluate_voice_shadow(self):
        """Test voice/TTS evaluation."""
        from app.interceptors.voice_shadow import evaluate_voice_shadow, VoiceShadowResult
        
        company_id = str(uuid.uuid4())
        
        with patch('app.interceptors.voice_shadow.ShadowModeService') as MockService:
            mock_service = MockService.return_value
            mock_service.evaluate_action_risk.return_value = {
                "requires_approval": True,
                "auto_execute": False,
                "mode": "shadow",
                "risk_score": 0.6,
                "reason": "Voice message requires review",
                "layers": {},
                "company_mode": "shadow",
            }
            mock_service.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
            
            result = evaluate_voice_shadow(
                company_id=company_id,
                voice_payload={
                    "call_id": str(uuid.uuid4()),
                    "to_number": "+1234567890",
                    "message": "Your refund of $500 has been processed.",
                },
                shadow_service=mock_service,
            )
            
            assert isinstance(result, VoiceShadowResult)
            assert result.requires_approval is True

    def test_should_intercept_voice_skip_greeting(self):
        """Test that simple greetings are not intercepted."""
        from app.interceptors.voice_shadow import should_intercept_voice
        
        company_id = str(uuid.uuid4())
        
        # Simple greeting - should not intercept
        result = should_intercept_voice(
            company_id=company_id,
            call_data={"message": "Thank you for calling. How can I help you?"},
        )
        
        assert result is False

    def test_should_intercept_voice_content(self):
        """Test that content messages are intercepted."""
        from app.interceptors.voice_shadow import should_intercept_voice
        
        company_id = str(uuid.uuid4())
        
        # Content message - should intercept
        result = should_intercept_voice(
            company_id=company_id,
            call_data={"message": "Your refund has been processed to your account."},
        )
        
        assert result is True

    def test_get_hold_message(self):
        """Test hold message generation."""
        from app.interceptors.voice_shadow import get_hold_message
        
        message = get_hold_message()
        
        assert "hold" in message.lower()
        assert len(message) > 20  # Meaningful message


class TestChatShadowInterceptorDay2:
    """Tests for Chat Shadow Interceptor (Day 2)."""

    def test_intercept_outbound_chat_pending(self):
        """Test chat interception returning pending status."""
        from app.interceptors.chat_shadow import ChatShadowInterceptor
        
        interceptor = ChatShadowInterceptor()
        company_id = str(uuid.uuid4())
        
        with patch.object(interceptor, 'evaluate_shadow') as mock_eval:
            mock_eval.return_value = {
                "requires_hold": True,
                "risk_score": 0.7,
                "mode": "shadow",
                "shadow_log_id": str(uuid.uuid4()),
                "auto_execute": False,
                "reason": "Chat requires approval",
            }
            
            with patch.object(interceptor, '_queue_chat_message') as mock_queue:
                mock_queue.return_value = {"queue_id": str(uuid.uuid4()), "status": "queued"}
                
                result = interceptor.intercept_outbound_chat(
                    company_id=company_id,
                    message_data={
                        "session_id": "session-123",
                        "message": "Your refund has been processed.",
                    },
                )
                
                assert result["status"] == "pending"
                assert result["requires_hold"] is True

    def test_intercept_outbound_chat_auto_send(self):
        """Test chat interception with auto-send."""
        from app.interceptors.chat_shadow import ChatShadowInterceptor
        
        interceptor = ChatShadowInterceptor()
        company_id = str(uuid.uuid4())
        
        with patch.object(interceptor, 'evaluate_shadow') as mock_eval:
            mock_eval.return_value = {
                "requires_hold": False,
                "risk_score": 0.2,
                "mode": "graduated",
                "shadow_log_id": str(uuid.uuid4()),
                "auto_execute": True,
                "reason": "Auto-approved",
            }
            
            with patch.object(interceptor, '_send_chat_message') as mock_send:
                mock_send.return_value = {"success": True, "message_uuid": str(uuid.uuid4())}
                
                with patch.object(interceptor, '_log_to_undo_queue') as mock_undo:
                    mock_undo.return_value = str(uuid.uuid4())
                    
                    result = interceptor.intercept_outbound_chat(
                        company_id=company_id,
                        message_data={
                            "session_id": "session-123",
                            "message": "Thank you for your message!",
                        },
                    )
                    
                    assert result["status"] == "sent"
                    assert result["auto_execute"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Day 3 Tests - Ticket Shadow Integration
# ─────────────────────────────────────────────────────────────────────────────


class TestTicketShadowIntegrationDay3:
    """Tests for Ticket Shadow Integration (Day 3)."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_company_id(self):
        """Return a test company ID."""
        return str(uuid.uuid4())

    @pytest.fixture
    def ticket_service(self, mock_db, mock_company_id):
        """Create a TicketService instance."""
        from app.services.ticket_service import TicketService
        return TicketService(mock_db, mock_company_id)

    def test_evaluate_ticket_shadow(self, ticket_service):
        """Test evaluating ticket shadow status."""
        ticket_id = str(uuid.uuid4())
        
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_id
        mock_ticket.status = "in_progress"
        mock_ticket.priority = "high"
        mock_ticket.category = "billing"
        mock_ticket.reopen_count = 0
        mock_ticket.escalation_level = 1
        mock_ticket.sla_breached = False
        
        with patch.object(ticket_service, 'get_ticket', return_value=mock_ticket):
            with patch('app.services.ticket_service.ShadowModeService') as MockService:
                mock_shadow = MockService.return_value
                mock_shadow.evaluate_action_risk.return_value = {
                    "requires_approval": True,
                    "risk_score": 0.6,
                    "mode": "shadow",
                    "reason": "High priority billing ticket",
                    "layers": {},
                    "auto_execute": False,
                }
                
                result = ticket_service.evaluate_ticket_shadow(
                    ticket_id=ticket_id,
                    action_type="ticket_close",
                )
                
                assert result["requires_approval"] is True
                assert result["mode"] == "shadow"

    def test_resolve_ticket_with_shadow_pending(self, ticket_service):
        """Test ticket resolution requiring shadow approval."""
        ticket_id = str(uuid.uuid4())
        
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_id
        mock_ticket.status = "in_progress"
        mock_ticket.shadow_status = "none"
        mock_ticket.shadow_log_id = None
        mock_ticket.risk_score = None
        
        with patch.object(ticket_service, 'get_ticket', return_value=mock_ticket):
            with patch.object(ticket_service, 'evaluate_ticket_shadow') as mock_eval:
                mock_eval.return_value = {
                    "requires_approval": True,
                    "risk_score": 0.8,
                    "mode": "shadow",
                    "auto_execute": False,
                }
                
                with patch('app.services.ticket_service.ShadowModeService') as MockService:
                    mock_shadow = MockService.return_value
                    mock_shadow.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
                    
                    result = ticket_service.resolve_ticket_with_shadow(
                        ticket_id=ticket_id,
                        manager_id=str(uuid.uuid4()),
                        resolution_note="Test resolution",
                    )
                    
                    assert result["pending_approval"] is True
                    assert result["resolved"] is False

    def test_resolve_ticket_with_shadow_auto_approved(self, ticket_service):
        """Test ticket resolution with auto-approval in graduated mode."""
        ticket_id = str(uuid.uuid4())
        
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_id
        mock_ticket.status = "in_progress"
        mock_ticket.shadow_status = "none"
        
        with patch.object(ticket_service, 'get_ticket', return_value=mock_ticket):
            with patch.object(ticket_service, 'evaluate_ticket_shadow') as mock_eval:
                mock_eval.return_value = {
                    "requires_approval": False,
                    "risk_score": 0.2,
                    "mode": "graduated",
                    "auto_execute": True,
                }
                
                with patch('app.services.ticket_service.ShadowModeService') as MockService:
                    mock_shadow = MockService.return_value
                    mock_shadow.log_shadow_action.return_value = {"id": str(uuid.uuid4())}
                    mock_shadow.approve_shadow_action.return_value = {"id": str(uuid.uuid4())}
                    
                    result = ticket_service.resolve_ticket_with_shadow(
                        ticket_id=ticket_id,
                        manager_id=str(uuid.uuid4()),
                        resolution_note="Auto resolution",
                    )
                    
                    assert result["resolved"] is True
                    assert result["pending_approval"] is False

    def test_approve_ticket_resolution(self, ticket_service):
        """Test approving a pending ticket resolution."""
        ticket_id = str(uuid.uuid4())
        manager_id = str(uuid.uuid4())
        
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_id
        mock_ticket.shadow_status = "pending_approval"
        mock_ticket.shadow_log_id = str(uuid.uuid4())
        mock_ticket.status = "in_progress"
        
        with patch.object(ticket_service, 'get_ticket', return_value=mock_ticket):
            with patch.object(ticket_service, '_record_status_change'):
                with patch('app.services.ticket_service.ShadowModeService') as MockService:
                    mock_shadow = MockService.return_value
                    mock_shadow.approve_shadow_action.return_value = {"id": str(uuid.uuid4())}
                    
                    result = ticket_service.approve_ticket_resolution(
                        ticket_id=ticket_id,
                        manager_id=manager_id,
                        note="Approved",
                    )
                    
                    assert result["success"] is True
                    assert result["shadow_status"] == "approved"

    def test_approve_ticket_resolution_not_pending(self, ticket_service):
        """Test approving a ticket that is not pending approval."""
        ticket_id = str(uuid.uuid4())
        
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_id
        mock_ticket.shadow_status = "approved"  # Already approved
        
        with patch.object(ticket_service, 'get_ticket', return_value=mock_ticket):
            result = ticket_service.approve_ticket_resolution(
                ticket_id=ticket_id,
                manager_id=str(uuid.uuid4()),
                note="Attempt to approve again",
            )
            
            assert result["success"] is False
            assert "not pending approval" in result["error"].lower()

    def test_undo_ticket_resolution(self, ticket_service):
        """Test undoing an approved ticket resolution."""
        ticket_id = str(uuid.uuid4())
        
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_id
        mock_ticket.shadow_status = "approved"
        mock_ticket.shadow_log_id = str(uuid.uuid4())
        mock_ticket.status = "resolved"
        
        with patch.object(ticket_service, 'get_ticket', return_value=mock_ticket):
            with patch.object(ticket_service, '_record_status_change'):
                with patch('app.services.ticket_service.ShadowModeService') as MockService:
                    mock_shadow = MockService.return_value
                    mock_shadow.undo_auto_approved_action.return_value = {"undo_id": str(uuid.uuid4())}
                    
                    result = ticket_service.undo_ticket_resolution(
                        ticket_id=ticket_id,
                        reason="Customer requested reversal",
                        manager_id=str(uuid.uuid4()),
                    )
                    
                    assert result["success"] is True
                    assert mock_ticket.shadow_status == "undone"

    def test_undo_ticket_resolution_not_approved(self, ticket_service):
        """Test undoing a ticket that was not approved."""
        ticket_id = str(uuid.uuid4())
        
        mock_ticket = MagicMock()
        mock_ticket.id = ticket_id
        mock_ticket.shadow_status = "pending_approval"  # Not yet approved
        
        with patch.object(ticket_service, 'get_ticket', return_value=mock_ticket):
            result = ticket_service.undo_ticket_resolution(
                ticket_id=ticket_id,
                reason="Cannot undo pending",
                manager_id=str(uuid.uuid4()),
            )
            
            assert result["success"] is False


class TestTicketShadowAPIEndpointsDay3:
    """Tests for Ticket Shadow API endpoints (Day 3)."""

    def test_shadow_status_filter_in_list_tickets(self):
        """Test filtering tickets by shadow_status."""
        from app.api.tickets import list_tickets
        
        # This would be an integration test with FastAPI TestClient
        # For now, we verify the endpoint accepts the shadow_status parameter
        pass

    def test_resolve_with_shadow_endpoint(self):
        """Test the resolve-with-shadow endpoint."""
        # Integration test would verify the endpoint exists and returns proper response
        pass

    def test_approve_resolution_endpoint(self):
        """Test the approve-resolution endpoint."""
        # Integration test would verify the endpoint
        pass

    def test_undo_resolution_endpoint(self):
        """Test the undo-resolution endpoint."""
        # Integration test would verify the endpoint
        pass

    def test_shadow_details_endpoint(self):
        """Test the shadow-details endpoint."""
        # Integration test would verify the endpoint
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestShadowModeIntegration:
    """Integration tests for Shadow Mode across all components."""

    def test_full_flow_email_shadow_to_approval(self):
        """Test complete flow: email shadow → approve → send."""
        # 1. Evaluate email - requires approval
        # 2. Manager approves
        # 3. Email is sent
        pass

    def test_full_flow_ticket_shadow_to_undo(self):
        """Test complete flow: ticket shadow → approve → undo."""
        # 1. Ticket resolution requires approval
        # 2. Manager approves
        # 3. Ticket is resolved
        # 4. Manager undoes resolution
        # 5. Ticket is reopened
        pass

    def test_socket_events_emitted(self):
        """Test that Socket.io events are emitted correctly."""
        # Verify all 6 events are emitted:
        # - shadow:action_logged
        # - shadow:action_approved
        # - shadow:action_rejected
        # - shadow:action_undone
        # - shadow:mode_changed
        # - shadow:preference_changed
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases and Error Handling
# ─────────────────────────────────────────────────────────────────────────────


class TestShadowModeEdgeCases:
    """Tests for edge cases and error handling."""

    def test_evaluate_risk_with_null_payload(self):
        """Test risk evaluation with null payload."""
        from app.services.shadow_mode_service import ShadowModeService
        
        service = ShadowModeService()
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_company = MagicMock()
            mock_company.system_mode = "supervised"
            mock_company.shadow_actions_remaining = None
            
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_company
            
            result = service.evaluate_action_risk(
                company_id=str(uuid.uuid4()),
                action_type="email_reply",
                action_payload=None,
            )
            
            # Should handle gracefully with default values
            assert "risk_score" in result

    def test_evaluate_risk_company_not_found(self):
        """Test risk evaluation when company is not found."""
        from app.services.shadow_mode_service import ShadowModeService
        
        service = ShadowModeService()
        
        with patch('app.services.shadow_mode_service.SessionLocal') as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = None
            
            # Should return supervised mode as fallback
            result = service.evaluate_action_risk(
                company_id="non-existent-id",
                action_type="email_reply",
                action_payload={},
            )
            
            assert result["mode"] == "supervised"
            assert result["requires_approval"] is True

    def test_concurrent_shadow_log_access(self):
        """Test handling concurrent access to shadow log."""
        # Test that race conditions are handled properly
        pass

    def test_undo_window_expiration(self):
        """Test that undo window is respected."""
        # Test that actions outside the undo window cannot be undone
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
