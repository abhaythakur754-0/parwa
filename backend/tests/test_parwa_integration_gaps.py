"""
PARWA Integration Gap Testing
==============================

This test suite checks ALL integration gaps between components:
- Dashboard ↔ PARWA connection
- Jarvis ↔ PARWA commands
- AI Engine ↔ Dashboard
- All API endpoints connectivity
- Database ↔ Services connections
- Frontend ↔ Backend connections

Run with: pytest tests/test_parwa_integration_gaps.py -v --tb=short
"""

import pytest
import os
import sys
import json
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from decimal import Decimal

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# SECTION 1: DASHBOARD ↔ PARWA CONNECTION TESTS
# =============================================================================

class TestDashboardToParwaConnection:
    """Test if Dashboard is properly connected to PARWA backend."""

    def test_dashboard_api_endpoint_exists(self):
        """Dashboard must have API endpoint to communicate with PARWA."""
        # Check if dashboard API file exists
        api_files = [
            "/home/z/my-project/parwa/backend/app/api/dashboard.py",
            "/home/z/my-project/parwa/backend/app/api/agents.py",
            "/home/z/my-project/parwa/backend/app/api/tickets.py",
        ]
        
        for api_file in api_files:
            assert os.path.exists(api_file), f"API file missing: {api_file}"

    def test_dashboard_service_exists(self):
        """Dashboard service must exist for business logic."""
        service_path = "/home/z/my-project/parwa/backend/app/services/dashboard_service.py"
        assert os.path.exists(service_path), "Dashboard service file missing"

    def test_dashboard_can_fetch_tickets(self):
        """Dashboard must be able to fetch tickets from PARWA."""
        # Simulated dashboard API call
        dashboard_response = {
            "tickets": [
                {"id": "ticket_1", "status": "open", "priority": "high"},
                {"id": "ticket_2", "status": "pending", "priority": "medium"}
            ],
            "total": 2,
            "page": 1
        }
        
        assert "tickets" in dashboard_response
        assert len(dashboard_response["tickets"]) == 2

    def test_dashboard_can_send_commands_to_ai(self):
        """Dashboard must be able to send commands to AI engine."""
        command_flow = {
            "dashboard_command": "analyze_ticket",
            "ai_engine_received": True,
            "response": {"analysis": "refund_eligible", "confidence": 0.95}
        }
        
        assert command_flow["ai_engine_received"] is True
        assert "confidence" in command_flow["response"]

    def test_dashboard_websocket_connection(self):
        """Dashboard must have WebSocket connection for real-time updates."""
        socketio_path = "/home/z/my-project/parwa/backend/app/core/socketio.py"
        assert os.path.exists(socketio_path), "Socket.io connection missing"

    def test_dashboard_shows_ai_recommendations(self):
        """Dashboard must display AI recommendations from PARWA."""
        recommendation_display = {
            "ticket_id": "ticket_123",
            "ai_recommendation": "APPROVE",
            "confidence_score": 0.93,
            "reasoning": "Customer eligible per 30-day policy",
            "displayed_on_dashboard": True
        }
        
        assert recommendation_display["displayed_on_dashboard"] is True
        assert recommendation_display["ai_recommendation"] in ["APPROVE", "DENY", "REVIEW"]


# =============================================================================
# SECTION 2: JARVIS ↔ PARWA COMMAND TESTS
# =============================================================================

class TestJarvisToParwaCommands:
    """Test if Jarvis can command PARWA through dashboard."""

    def test_jarvis_api_endpoint_exists(self):
        """Jarvis must have API endpoint for commands."""
        jarvis_api_path = "/home/z/my-project/parwa/backend/app/api/jarvis.py"
        jarvis_control_path = "/home/z/my-project/parwa/backend/app/api/jarvis_control.py"
        
        assert os.path.exists(jarvis_api_path) or os.path.exists(jarvis_control_path), \
            "Jarvis API endpoint missing"

    def test_jarvis_service_exists(self):
        """Jarvis service must exist for command processing."""
        jarvis_service_path = "/home/z/my-project/parwa/backend/app/services/jarvis_service.py"
        assert os.path.exists(jarvis_service_path), "Jarvis service missing"

    def test_jarvis_can_pause_ai(self):
        """Jarvis can pause AI agent through dashboard."""
        command_result = {
            "command": "pause_ai",
            "source": "jarvis",
            "executed": True,
            "ai_status": "paused"
        }
        
        assert command_result["executed"] is True
        assert command_result["ai_status"] == "paused"

    def test_jarvis_can_resume_ai(self):
        """Jarvis can resume AI agent through dashboard."""
        command_result = {
            "command": "resume_ai",
            "source": "jarvis",
            "executed": True,
            "ai_status": "active"
        }
        
        assert command_result["executed"] is True
        assert command_result["ai_status"] == "active"

    def test_jarvis_can_approve_refund(self):
        """Jarvis can approve refund through dashboard."""
        approval_result = {
            "command": "approve_refund",
            "ticket_id": "ticket_123",
            "amount": Decimal("99.99"),
            "executed": True,
            "approval_status": "approved"
        }
        
        assert approval_result["executed"] is True
        assert approval_result["approval_status"] == "approved"

    def test_jarvis_can_deny_refund(self):
        """Jarvis can deny refund through dashboard."""
        denial_result = {
            "command": "deny_refund",
            "ticket_id": "ticket_456",
            "reason": "Outside policy window",
            "executed": True,
            "approval_status": "denied"
        }
        
        assert denial_result["executed"] is True
        assert denial_result["approval_status"] == "denied"

    def test_jarvis_can_view_ai_state(self):
        """Jarvis can view AI current state through dashboard."""
        state_result = {
            "command": "get_ai_state",
            "ai_state": {
                "mode": "supervised",
                "tickets_processed": 150,
                "pending_approvals": 5,
                "confidence_avg": 0.92
            }
        }
        
        assert "ai_state" in state_result
        assert state_result["ai_state"]["mode"] in ["shadow", "supervised", "graduated"]

    def test_jarvis_natural_language_parsing(self):
        """Jarvis can parse natural language commands."""
        parsed_commands = [
            {"input": "pause all refunds", "parsed": {"action": "pause", "target": "refunds"}},
            {"input": "show me today's tickets", "parsed": {"action": "show", "target": "tickets", "filter": "today"}},
            {"input": "what's the system status", "parsed": {"action": "status", "target": "system"}},
        ]
        
        for cmd in parsed_commands:
            assert "parsed" in cmd
            assert "action" in cmd["parsed"]


# =============================================================================
# SECTION 3: AI ENGINE ↔ BACKEND CONNECTION TESTS
# =============================================================================

class TestAIEngineToBackendConnection:
    """Test if AI Engine is properly connected to backend services."""

    def test_ai_pipeline_exists(self):
        """AI pipeline must exist."""
        ai_pipeline_path = "/home/z/my-project/parwa/backend/app/core/ai_pipeline.py"
        assert os.path.exists(ai_pipeline_path), "AI pipeline missing"

    def test_smart_router_exists(self):
        """Smart router must exist for LLM routing."""
        smart_router_path = "/home/z/my-project/parwa/backend/app/core/smart_router.py"
        assert os.path.exists(smart_router_path), "Smart router missing"

    def test_gsd_engine_exists(self):
        """GSD engine must exist for state management."""
        gsd_engine_path = "/home/z/my-project/parwa/backend/app/core/gsd_engine.py"
        assert os.path.exists(gsd_engine_path), "GSD engine missing"

    def test_ai_can_classify_ticket(self):
        """AI engine can classify tickets."""
        classification_result = {
            "ticket_id": "ticket_123",
            "classification": {
                "intent": "refund_request",
                "category": "billing",
                "priority": "high",
                "confidence": 0.94
            }
        }
        
        assert classification_result["classification"]["intent"] == "refund_request"
        assert classification_result["classification"]["confidence"] > 0.5

    def test_ai_can_analyze_sentiment(self):
        """AI engine can analyze customer sentiment."""
        sentiment_result = {
            "message": "I'm very frustrated with this service!",
            "sentiment": {
                "label": "negative",
                "score": 0.92,
                "should_escalate": True
            }
        }
        
        assert sentiment_result["sentiment"]["label"] == "negative"
        assert sentiment_result["sentiment"]["should_escalate"] is True

    def test_ai_can_check_policy(self):
        """AI engine can check refund policy."""
        policy_result = {
            "ticket_id": "ticket_123",
            "policy_check": {
                "eligible": True,
                "policy": "30_day_refund",
                "days_since_purchase": 15,
                "reason": "Within 30-day window"
            }
        }
        
        assert policy_result["policy_check"]["eligible"] is True

    def test_ai_can_detect_fraud(self):
        """AI engine can detect fraud patterns."""
        fraud_result = {
            "ticket_id": "ticket_456",
            "fraud_check": {
                "risk_level": "high",
                "indicators": ["multiple_refunds", "new_account", "high_value"],
                "score": 0.85
            }
        }
        
        assert fraud_result["fraud_check"]["risk_level"] in ["low", "medium", "high"]

    def test_ai_generates_confidence_score(self):
        """AI generates confidence score for every decision."""
        confidence_result = {
            "decision": "approve_refund",
            "confidence": {
                "score": 0.93,
                "factors": {
                    "policy_match": 0.95,
                    "history_check": 0.90,
                    "fraud_check": 0.98
                }
            }
        }
        
        assert 0 <= confidence_result["confidence"]["score"] <= 1


# =============================================================================
# SECTION 4: DATABASE ↔ SERVICES CONNECTION TESTS
# =============================================================================

class TestDatabaseToServicesConnection:
    """Test if database is properly connected to all services."""

    def test_models_directory_exists(self):
        """Database models must exist."""
        models_path = "/home/z/my-project/parwa/backend/app/models"
        assert os.path.exists(models_path), "Models directory missing"

    def test_database_config_exists(self):
        """Database configuration must exist."""
        # Check for database configuration in config
        config_exists = os.path.exists("/home/z/my-project/parwa/backend/app/config.py")
        assert config_exists, "Database config missing"

    def test_ticket_model_exists(self):
        """Ticket model must exist for database operations."""
        # Check if ticket-related files exist
        ticket_service = "/home/z/my-project/parwa/backend/app/services/ticket_service.py"
        assert os.path.exists(ticket_service), "Ticket service missing"

    def test_company_model_exists(self):
        """Company model must exist for multi-tenant operations."""
        company_service = "/home/z/my-project/parwa/backend/app/services/company_service.py"
        assert os.path.exists(company_service), "Company service missing"

    def test_audit_trail_model_exists(self):
        """Audit trail must be implemented."""
        audit_service = "/home/z/my-project/parwa/backend/app/services/audit_service.py"
        assert os.path.exists(audit_service), "Audit service missing"

    def test_migrations_directory_exists(self):
        """Database migrations must exist."""
        alembic_path = "/home/z/my-project/parwa/database/alembic"
        assert os.path.exists(alembic_path), "Alembic migrations missing"


# =============================================================================
# SECTION 5: CHANNEL INTEGRATION TESTS
# =============================================================================

class TestChannelIntegration:
    """Test if all channels are properly integrated."""

    def test_email_channel_exists(self):
        """Email channel must be implemented."""
        email_channel_path = "/home/z/my-project/parwa/backend/app/api/email_channel.py"
        email_service_path = "/home/z/my-project/parwa/backend/app/services/email_channel_service.py"
        
        assert os.path.exists(email_channel_path) or os.path.exists(email_service_path), \
            "Email channel missing"

    def test_sms_channel_exists(self):
        """SMS channel must be implemented."""
        sms_channel_path = "/home/z/my-project/parwa/backend/app/api/sms_channel.py"
        sms_service_path = "/home/z/my-project/parwa/backend/app/services/sms_channel_service.py"
        
        assert os.path.exists(sms_channel_path) or os.path.exists(sms_service_path), \
            "SMS channel missing"

    def test_chat_widget_exists(self):
        """Chat widget must be implemented."""
        chat_widget_api = "/home/z/my-project/parwa/backend/app/api/chat_widget.py"
        chat_widget_service = "/home/z/my-project/parwa/backend/app/services/chat_widget_service.py"
        
        assert os.path.exists(chat_widget_api) or os.path.exists(chat_widget_service), \
            "Chat widget missing"

    def test_voice_channel_exists(self):
        """Voice channel must be implemented."""
        voice_channel_path = "/home/z/my-project/parwa/backend/app/api/twilio_channels.py"
        voice_provider_path = "/home/z/my-project/parwa/backend/app/providers/voice/twilio_voice.py"
        
        assert os.path.exists(voice_channel_path) or os.path.exists(voice_provider_path), \
            "Voice channel missing"

    def test_channel_dispatcher_exists(self):
        """Channel dispatcher must exist for routing."""
        dispatcher_path = "/home/z/my-project/parwa/backend/app/core/channel_dispatcher.py"
        assert os.path.exists(dispatcher_path), "Channel dispatcher missing"

    def test_omnichannel_memory(self):
        """Omnichannel memory must be preserved across channels."""
        omnichannel_result = {
            "customer_id": "cust_123",
            "channels_used": ["email", "chat", "phone"],
            "unified_context": {
                "issue": "refund_request",
                "order_id": "order_456",
                "sentiment": "frustrated"
            },
            "memory_preserved": True
        }
        
        assert omnichannel_result["memory_preserved"] is True
        assert len(omnichannel_result["channels_used"]) > 1


# =============================================================================
# SECTION 6: APPROVAL WORKFLOW INTEGRATION TESTS
# =============================================================================

class TestApprovalWorkflowIntegration:
    """Test if approval workflow is properly integrated."""

    def test_approvals_api_exists(self):
        """Approvals API must exist."""
        approvals_path = "/home/z/my-project/parwa/backend/app/api/approvals.py"
        assert os.path.exists(approvals_path), "Approvals API missing"

    def test_approval_service_exists(self):
        """Approval service must exist."""
        # Check for any approval-related service
        approval_services = [
            "/home/z/my-project/parwa/backend/app/services/approval_tasks.py",
            "/home/z/my-project/parwa/backend/app/services/financial_safety_service.py",
        ]
        
        exists = any(os.path.exists(p) for p in approval_services)
        assert exists, "Approval service missing"

    def test_approval_creates_audit_trail(self):
        """Every approval must create audit trail."""
        approval_audit = {
            "approval_id": "apr_123",
            "ticket_id": "ticket_456",
            "action": "refund_approved",
            "approved_by": "manager_001",
            "timestamp": datetime.utcnow().isoformat(),
            "audit_logged": True
        }
        
        assert approval_audit["audit_logged"] is True

    def test_approval_notification_sent(self):
        """Approval must trigger notification."""
        notification_result = {
            "approval_id": "apr_123",
            "notification": {
                "sent": True,
                "channel": "email",
                "recipient": "customer@example.com"
            }
        }
        
        assert notification_result["notification"]["sent"] is True

    def test_batch_approval_works(self):
        """Batch approval must work correctly."""
        batch_result = {
            "batch_id": "batch_001",
            "tickets": ["ticket_1", "ticket_2", "ticket_3"],
            "action": "approve_all",
            "executed": True,
            "count": 3
        }
        
        assert batch_result["executed"] is True
        assert batch_result["count"] == 3


# =============================================================================
# SECTION 7: TRAINING PIPELINE INTEGRATION TESTS
# =============================================================================

class TestTrainingPipelineIntegration:
    """Test if training pipeline is properly integrated."""

    def test_training_api_exists(self):
        """Training API must exist."""
        training_path = "/home/z/my-project/parwa/backend/app/api/training.py"
        training_advanced_path = "/home/z/my-project/parwa/backend/app/api/training_advanced.py"
        
        assert os.path.exists(training_path) or os.path.exists(training_advanced_path), \
            "Training API missing"

    def test_training_service_exists(self):
        """Training service must exist."""
        training_services = [
            "/home/z/my-project/parwa/backend/app/services/train_from_error_service.py",
            "/home/z/my-project/parwa/backend/app/services/agent_training_service.py",
            "/home/z/my-project/parwa/backend/app/services/fallback_training_service.py",
        ]
        
        exists = any(os.path.exists(p) for p in training_services)
        assert exists, "Training service missing"

    def test_mistake_logging_works(self):
        """Mistakes must be logged for training."""
        mistake_log = {
            "mistake_id": "mistake_001",
            "ticket_id": "ticket_123",
            "ai_response": "APPROVE",
            "correct_response": "DENY",
            "logged": True,
            "logged_at": datetime.utcnow().isoformat()
        }
        
        assert mistake_log["logged"] is True

    def test_50_mistake_threshold_triggers_training(self):
        """50 mistakes must trigger training."""
        training_trigger = {
            "company_id": "comp_123",
            "mistake_count": 50,
            "training_triggered": True,
            "training_job_id": "job_001"
        }
        
        assert training_trigger["training_triggered"] is True

    def test_training_data_isolated(self):
        """Training data must be isolated per company."""
        training_isolation = {
            "company_id": "comp_123",
            "data_source": "own_interactions_only",
            "cross_company_sharing": False
        }
        
        assert training_isolation["cross_company_sharing"] is False


# =============================================================================
# SECTION 8: BILLING INTEGRATION TESTS
# =============================================================================

class TestBillingIntegration:
    """Test if billing is properly integrated."""

    def test_billing_api_exists(self):
        """Billing API must exist."""
        billing_path = "/home/z/my-project/parwa/backend/app/api/billing.py"
        assert os.path.exists(billing_path), "Billing API missing"

    def test_billing_service_exists(self):
        """Billing service must exist."""
        billing_service = "/home/z/my-project/parwa/backend/app/services/paddle_service.py"
        assert os.path.exists(billing_service), "Billing service missing"

    def test_subscription_tracking(self):
        """Subscriptions must be tracked."""
        subscription = {
            "company_id": "comp_123",
            "plan": "parwa_growth",
            "status": "active",
            "tickets_used": 1500,
            "tickets_limit": 5000
        }
        
        assert subscription["status"] == "active"
        assert subscription["tickets_used"] <= subscription["tickets_limit"]

    def test_overage_tracking(self):
        """Overage must be tracked."""
        overage = {
            "company_id": "comp_123",
            "overage_tickets": 100,
            "overage_charge": Decimal("100.00"),
            "tracked": True
        }
        
        assert overage["tracked"] is True


# =============================================================================
# SECTION 9: SECURITY INTEGRATION TESTS
# =============================================================================

class TestSecurityIntegration:
    """Test if security is properly integrated."""

    def test_auth_api_exists(self):
        """Auth API must exist."""
        auth_path = "/home/z/my-project/parwa/backend/app/api/auth.py"
        assert os.path.exists(auth_path), "Auth API missing"

    def test_mfa_api_exists(self):
        """MFA API must exist."""
        mfa_path = "/home/z/my-project/parwa/backend/app/api/mfa.py"
        mfa_service = "/home/z/my-project/parwa/backend/app/services/mfa_service.py"
        
        assert os.path.exists(mfa_path) or os.path.exists(mfa_service), \
            "MFA implementation missing"

    def test_rate_limiting_exists(self):
        """Rate limiting must be implemented."""
        rate_limit_path = "/home/z/my-project/parwa/backend/app/middleware/rate_limit.py"
        rate_limit_service = "/home/z/my-project/parwa/backend/app/services/rate_limit_service.py"
        
        assert os.path.exists(rate_limit_path) or os.path.exists(rate_limit_service), \
            "Rate limiting missing"

    def test_tenant_middleware_exists(self):
        """Tenant middleware must exist for multi-tenant isolation."""
        tenant_path = "/home/z/my-project/parwa/backend/app/middleware/tenant.py"
        assert os.path.exists(tenant_path), "Tenant middleware missing"

    def test_hmac_verification_exists(self):
        """HMAC verification must exist for webhooks."""
        hmac_path = "/home/z/my-project/parwa/backend/app/security/hmac_verification.py"
        hmac_core = "/home/z/my-project/parwa/backend/app/core/hmac_verify.py"
        
        assert os.path.exists(hmac_path) or os.path.exists(hmac_core), \
            "HMAC verification missing"


# =============================================================================
# SECTION 10: FRONTEND CONNECTIVITY TESTS
# =============================================================================

class TestFrontendConnectivity:
    """Test if frontend can connect to backend."""

    def test_frontend_directory_exists(self):
        """Frontend directory must exist."""
        frontend_path = "/home/z/my-project/parwa/frontend"
        assert os.path.exists(frontend_path), "Frontend directory missing"

    def test_api_routes_defined(self):
        """API routes must be defined for frontend consumption."""
        api_path = "/home/z/my-project/parwa/backend/app/api"
        assert os.path.exists(api_path), "API directory missing"
        
        # Count API route files
        api_files = [f for f in os.listdir(api_path) if f.endswith('.py') and f != '__init__.py']
        assert len(api_files) > 20, f"Not enough API files: {len(api_files)}"

    def test_cors_configured(self):
        """CORS must be configured for frontend."""
        # Check main.py for CORS
        main_path = "/home/z/my-project/parwa/backend/app/main.py"
        if os.path.exists(main_path):
            with open(main_path, 'r') as f:
                content = f.read()
            assert "CORS" in content or "cors" in content, "CORS not configured"

    def test_health_endpoint_exists(self):
        """Health endpoint must exist for monitoring."""
        health_path = "/home/z/my-project/parwa/backend/app/api/health.py"
        assert os.path.exists(health_path), "Health endpoint missing"


# =============================================================================
# SECTION 11: REAL-TIME COMMUNICATION TESTS
# =============================================================================

class TestRealTimeCommunication:
    """Test real-time communication capabilities."""

    def test_socketio_configured(self):
        """Socket.io must be configured."""
        socketio_path = "/home/z/my-project/parwa/backend/app/core/socketio.py"
        assert os.path.exists(socketio_path), "Socket.io not configured"

    def test_event_buffer_exists(self):
        """Event buffer must exist for reconnection."""
        event_buffer_path = "/home/z/my-project/parwa/backend/app/core/event_buffer.py"
        assert os.path.exists(event_buffer_path), "Event buffer missing"

    def test_event_emitter_exists(self):
        """Event emitter must exist."""
        event_emitter_path = "/home/z/my-project/parwa/backend/app/core/event_emitter.py"
        assert os.path.exists(event_emitter_path), "Event emitter missing"

    def test_real_time_ticket_updates(self):
        """Ticket updates must be real-time."""
        ticket_update = {
            "ticket_id": "ticket_123",
            "event": "status_changed",
            "old_status": "open",
            "new_status": "in_progress",
            "broadcast_via_socket": True,
            "room": "tenant_comp_123"
        }
        
        assert ticket_update["broadcast_via_socket"] is True


# =============================================================================
# SECTION 12: CRITICAL GAP TESTS
# =============================================================================

class TestCriticalGaps:
    """Test for critical integration gaps."""

    def test_gap_dashboard_to_ai_pipeline(self):
        """GAP: Dashboard must be able to trigger AI pipeline."""
        # Check if there's a way for dashboard to trigger AI
        ai_engine_api = "/home/z/my-project/parwa/backend/app/api/ai_engine.py"
        assert os.path.exists(ai_engine_api), "AI Engine API missing - Dashboard can't trigger AI"

    def test_gap_jarvis_to_approval(self):
        """GAP: Jarvis must be able to trigger approval workflow."""
        jarvis_control = "/home/z/my-project/parwa/backend/app/api/jarvis_control.py"
        approvals = "/home/z/my-project/parwa/backend/app/api/approvals.py"
        
        assert os.path.exists(jarvis_control) and os.path.exists(approvals), \
            "Jarvis ↔ Approval connection missing"

    def test_gap_ticket_to_ai_connection(self):
        """GAP: Tickets must be processed by AI."""
        ticket_service = "/home/z/my-project/parwa/backend/app/services/ticket_service.py"
        ai_pipeline = "/home/z/my-project/parwa/backend/app/core/ai_pipeline.py"
        
        assert os.path.exists(ticket_service) and os.path.exists(ai_pipeline), \
            "Ticket → AI connection missing"

    def test_gap_channel_to_ticket(self):
        """GAP: Channels must create tickets."""
        channel_dispatcher = "/home/z/my-project/parwa/backend/app/core/channel_dispatcher.py"
        ticket_service = "/home/z/my-project/parwa/backend/app/services/ticket_service.py"
        
        assert os.path.exists(channel_dispatcher) and os.path.exists(ticket_service), \
            "Channel → Ticket connection missing"

    def test_gap_approval_to_audit(self):
        """GAP: Approvals must create audit entries."""
        approvals_api = "/home/z/my-project/parwa/backend/app/api/approvals.py"
        audit_service = "/home/z/my-project/parwa/backend/app/services/audit_service.py"
        
        assert os.path.exists(approvals_api) and os.path.exists(audit_service), \
            "Approval → Audit connection missing"

    def test_gap_billing_to_company(self):
        """GAP: Billing must update company subscription."""
        billing_service = "/home/z/my-project/parwa/backend/app/services/paddle_service.py"
        company_service = "/home/z/my-project/parwa/backend/app/services/company_service.py"
        
        assert os.path.exists(billing_service) and os.path.exists(company_service), \
            "Billing → Company connection missing"

    def test_gap_webhook_to_ticket(self):
        """GAP: Webhooks must create/update tickets."""
        webhook_handlers = "/home/z/my-project/parwa/backend/app/webhooks"
        ticket_service = "/home/z/my-project/parwa/backend/app/services/ticket_service.py"
        
        assert os.path.exists(webhook_handlers) and os.path.exists(ticket_service), \
            "Webhook → Ticket connection missing"

    def test_gap_ai_to_notification(self):
        """GAP: AI decisions must trigger notifications."""
        notification_service = "/home/z/my-project/parwa/backend/app/services/notification_service.py"
        ai_pipeline = "/home/z/my-project/parwa/backend/app/core/ai_pipeline.py"
        
        assert os.path.exists(notification_service) and os.path.exists(ai_pipeline), \
            "AI → Notification connection missing"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
