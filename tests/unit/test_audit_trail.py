"""
Unit tests for the audit trail logging mechanism module.

Tests cover:
- Financial action logging
- Agent decision logging
- Edge cases and validation
- Audit trail immutability requirements
"""
import os
import time
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.core_functions.audit_trail import log_financial_action, log_agent_decision


class TestLogFinancialAction:
    """Tests for financial action audit logging."""

    def test_log_financial_action_success(self):
        """Test proper formatting of a financial audit log."""
        action = log_financial_action(
            action_type="refund",
            amount=15.50,
            target_id="txn_123",
            user_id="user_456"
        )

        assert action["event"] == "financial_audit"
        assert action["audit_type"] == "transaction"
        assert action["context"]["action"] == "refund"
        assert action["context"]["amount"] == 15.50
        assert action["context"]["target_id"] == "txn_123"
        assert action["context"]["user_id"] == "user_456"
        assert "timestamp_utc" in action["context"]

    def test_log_financial_action_negative_amount(self):
        """Test that negative financial amounts are rejected."""
        with pytest.raises(ValueError, match="Amount must be positive"):
            log_financial_action(
                action_type="refund",
                amount=-10.0,
                target_id="txn_123",
                user_id="user_456"
            )

    def test_log_financial_action_missing_fields(self):
        """Test that missing critical fields trigger an error."""
        with pytest.raises(ValueError, match="Missing required fields"):
            log_financial_action(
                action_type="",  # Empty action
                amount=10.0,
                target_id="txn_123",
                user_id="user_456"
            )

    def test_log_financial_action_with_metadata(self):
        """Test financial action with optional metadata."""
        metadata = {
            "reason": "Customer request",
            "approved_by": "manager_001",
            "ticket_id": "TKT-12345"
        }
        action = log_financial_action(
            action_type="refund",
            amount=99.99,
            target_id="txn_789",
            user_id="user_123",
            metadata=metadata
        )

        assert action["context"]["metadata"] == metadata
        assert action["context"]["metadata"]["reason"] == "Customer request"

    def test_log_financial_action_zero_amount(self):
        """Test that zero amount is accepted (could represent void)."""
        action = log_financial_action(
            action_type="void",
            amount=0.0,
            target_id="txn_void",
            user_id="user_789"
        )
        assert action["context"]["amount"] == 0.0

    def test_log_financial_action_large_amount(self):
        """Test logging large financial amounts."""
        action = log_financial_action(
            action_type="charge",
            amount=999999.99,
            target_id="txn_large",
            user_id="user_big"
        )
        assert action["context"]["amount"] == 999999.99

    def test_log_financial_action_various_types(self):
        """Test logging various financial action types."""
        action_types = ["refund", "charge", "discount", "credit", "void", "adjustment"]

        for action_type in action_types:
            action = log_financial_action(
                action_type=action_type,
                amount=10.0,
                target_id=f"txn_{action_type}",
                user_id="user_test"
            )
            assert action["context"]["action"] == action_type

    def test_log_financial_action_timestamp_is_float(self):
        """Test that timestamp is a float (Unix timestamp)."""
        action = log_financial_action(
            action_type="refund",
            amount=10.0,
            target_id="txn_time",
            user_id="user_time"
        )

        assert isinstance(action["context"]["timestamp_utc"], float)
        # Timestamp should be recent (within last minute)
        assert time.time() - action["context"]["timestamp_utc"] < 60


class TestLogAgentDecision:
    """Tests for agent decision audit logging."""

    def test_log_agent_decision_success(self):
        """Test proper formatting of an agent logic audit log."""
        decision = log_agent_decision(
            prompt_hash="1a2b3c",
            selected_action="escalate_to_human",
            confidence_score=0.95
        )

        assert decision["event"] == "agent_decision_audit"
        assert decision["audit_type"] == "ai_logic"
        assert decision["context"]["prompt_hash"] == "1a2b3c"
        assert decision["context"]["selected_action"] == "escalate_to_human"
        assert decision["context"]["confidence_score"] == 0.95
        assert decision["context"]["agent_id"] == "primary_router"
        assert "timestamp_utc" in decision["context"]

    def test_log_agent_decision_invalid_confidence(self):
        """Test that out-of-bounds confidence scores are rejected."""
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            log_agent_decision(
                prompt_hash="hash",
                selected_action="route",
                confidence_score=1.5  # Invalid
            )

        with pytest.raises(ValueError):
            log_agent_decision(
                prompt_hash="hash",
                selected_action="route",
                confidence_score=-0.1  # Invalid
            )

    def test_log_agent_decision_missing_fields(self):
        """Test that missing required decision fields trigger an error."""
        with pytest.raises(ValueError, match="Missing required fields"):
            log_agent_decision(
                prompt_hash="",
                selected_action="execute",
                confidence_score=0.8
            )

    def test_log_agent_decision_custom_agent_id(self):
        """Test agent decision with custom agent ID."""
        decision = log_agent_decision(
            prompt_hash="custom_hash",
            selected_action="route_to_tier2",
            confidence_score=0.88,
            agent_id="secondary_router"
        )

        assert decision["context"]["agent_id"] == "secondary_router"

    def test_log_agent_decision_confidence_boundaries(self):
        """Test confidence score at boundaries."""
        # Test 0.0
        decision = log_agent_decision(
            prompt_hash="hash_zero",
            selected_action="escalate",
            confidence_score=0.0
        )
        assert decision["context"]["confidence_score"] == 0.0

        # Test 1.0
        decision = log_agent_decision(
            prompt_hash="hash_one",
            selected_action="proceed",
            confidence_score=1.0
        )
        assert decision["context"]["confidence_score"] == 1.0

    def test_log_agent_decision_various_actions(self):
        """Test logging various agent action types."""
        actions = [
            "escalate_to_human",
            "route_to_light_tier",
            "route_to_medium_tier",
            "route_to_heavy_tier",
            "apply_refund",
            "send_response",
            "request_clarification"
        ]

        for action in actions:
            decision = log_agent_decision(
                prompt_hash=f"hash_{action}",
                selected_action=action,
                confidence_score=0.85
            )
            assert decision["context"]["selected_action"] == action

    def test_log_agent_decision_timestamp_is_float(self):
        """Test that timestamp is a float (Unix timestamp)."""
        decision = log_agent_decision(
            prompt_hash="time_test",
            selected_action="proceed",
            confidence_score=0.9
        )

        assert isinstance(decision["context"]["timestamp_utc"], float)
        # Timestamp should be recent (within last minute)
        assert time.time() - decision["context"]["timestamp_utc"] < 60


class TestAuditTrailIntegration:
    """Integration tests for audit trail module."""

    def test_financial_and_agent_audit_together(self):
        """Test that both audit types can be logged in sequence."""
        # Agent decides to refund
        agent_decision = log_agent_decision(
            prompt_hash="refund_decision_123",
            selected_action="apply_refund",
            confidence_score=0.92
        )

        # Financial action executed
        financial_action = log_financial_action(
            action_type="refund",
            amount=49.99,
            target_id="txn_refund_123",
            user_id="user_refund_test",
            metadata={"agent_decision_id": agent_decision["context"]["prompt_hash"]}
        )

        assert agent_decision["context"]["selected_action"] == "apply_refund"
        assert financial_action["context"]["action"] == "refund"
        assert financial_action["context"]["metadata"]["agent_decision_id"] == "refund_decision_123"

    def test_audit_trail_immutability_structure(self):
        """Test that audit records have immutable structure."""
        action = log_financial_action(
            action_type="test",
            amount=1.0,
            target_id="test_id",
            user_id="test_user"
        )

        # Required fields should be present
        required_keys = ["event", "audit_type", "context"]
        for key in required_keys:
            assert key in action

        # Context should have required fields
        required_context = ["action", "amount", "target_id", "user_id", "timestamp_utc"]
        for key in required_context:
            assert key in action["context"]

    def test_audit_event_types_distinct(self):
        """Test that financial and agent audits have distinct event types."""
        financial = log_financial_action(
            action_type="test",
            amount=1.0,
            target_id="test",
            user_id="test"
        )

        agent = log_agent_decision(
            prompt_hash="test",
            selected_action="test",
            confidence_score=0.5
        )

        assert financial["event"] == "financial_audit"
        assert agent["event"] == "agent_decision_audit"
        assert financial["audit_type"] == "transaction"
        assert agent["audit_type"] == "ai_logic"


class TestAuditTrailEdgeCases:
    """Edge case tests for audit trail module."""

    def test_financial_action_with_empty_metadata(self):
        """Test financial action with empty metadata dict."""
        action = log_financial_action(
            action_type="test",
            amount=1.0,
            target_id="test",
            user_id="test",
            metadata={}
        )
        assert action["context"]["metadata"] == {}

    def test_financial_action_without_metadata(self):
        """Test financial action without metadata parameter."""
        action = log_financial_action(
            action_type="test",
            amount=1.0,
            target_id="test",
            user_id="test"
        )
        assert action["context"]["metadata"] == {}

    def test_agent_decision_with_long_hash(self):
        """Test agent decision with long prompt hash."""
        long_hash = "a" * 1000  # SHA512-like hash
        decision = log_agent_decision(
            prompt_hash=long_hash,
            selected_action="test",
            confidence_score=0.75
        )
        assert decision["context"]["prompt_hash"] == long_hash

    def test_financial_action_precision(self):
        """Test financial action with precise amounts."""
        action = log_financial_action(
            action_type="test",
            amount=123.456789,
            target_id="precision_test",
            user_id="test"
        )
        # Should preserve precision
        assert action["context"]["amount"] == 123.456789
