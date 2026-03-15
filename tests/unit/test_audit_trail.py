"""
Unit tests for the audit trail logging mechanism module.
"""
import pytest
from shared.core_functions.audit_trail import log_financial_action, log_agent_decision


def test_log_financial_action_success():
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


def test_log_financial_action_negative_amount():
    """Test that negative financial amounts are rejected."""
    with pytest.raises(ValueError, match="Amount must be positive"):
        log_financial_action(
            action_type="refund",
            amount=-10.0,
            target_id="txn_123",
            user_id="user_456"
        )


def test_log_financial_action_missing_fields():
    """Test that missing critical fields trigger an error."""
    with pytest.raises(ValueError, match="Missing required fields"):
        log_financial_action(
            action_type="",  # Empty action
            amount=10.0,
            target_id="txn_123",
            user_id="user_456"
        )


def test_log_agent_decision_success():
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


def test_log_agent_decision_invalid_confidence():
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


def test_log_agent_decision_missing_fields():
    """Test that missing required decision fields trigger an error."""
    with pytest.raises(ValueError, match="Missing required fields"):
        log_agent_decision(
            prompt_hash="",
            selected_action="execute",
            confidence_score=0.8
        )
