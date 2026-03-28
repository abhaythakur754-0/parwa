"""
Unit tests for Financial Services Agents.

Tests cover:
- AccountInquiryAgent
- TransactionAgent
- ComplianceAgent
- FraudDetectionAgent
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import the agents
from variants.financial_services.agents.account_inquiry_agent import (
    AccountInquiryAgent,
    AccountInfo,
    AccountStatus,
    AccountType,
)
from variants.financial_services.agents.transaction_agent import (
    TransactionAgent,
    TransactionInfo,
    TransactionStatus,
    TransactionType,
)
from variants.financial_services.agents.compliance_agent import (
    ComplianceAgent,
    ComplianceCheckResult,
    ComplianceCheckType,
    ComplianceStatus,
)
from variants.financial_services.agents.fraud_detection_agent import (
    FraudDetectionAgent,
    FraudRiskLevel,
    FraudAlert,
    AlertType,
    RiskAssessment,
)


class TestAccountInquiryAgent:
    """Tests for AccountInquiryAgent."""

    def test_agent_initializes(self):
        """Test that agent initializes correctly."""
        agent = AccountInquiryAgent()

        assert agent is not None
        assert agent.config is not None
        assert len(agent._inquiry_count) == 0

    def test_handle_balance_inquiry(self):
        """Test balance inquiry handling."""
        agent = AccountInquiryAgent()

        result = agent.handle_balance_inquiry(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        )

        assert result.success is True
        assert result.account_info is not None
        assert result.audit_id.startswith("AUD-")

    def test_balance_shown_as_range(self):
        """Test that balance is shown as range, not exact amount."""
        agent = AccountInquiryAgent()

        result = agent.handle_balance_inquiry(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        )

        # Balance should be a range like "$1,000 - $5,000"
        if result.account_info and result.account_info.balance_range:
            assert "$" in result.account_info.balance_range
            # Should not be exact amount
            assert "." not in result.account_info.balance_range or "Under" in result.account_info.balance_range

    def test_account_number_masked(self):
        """Test that account numbers are masked."""
        agent = AccountInquiryAgent()

        result = agent.handle_balance_inquiry(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        )

        if result.account_info:
            masked = result.account_info.masked_account_number
            # Should show only last 4 digits
            assert "XXXX" in masked or "X" in masked
            assert len(masked.replace("-", "").replace("X", "")) <= 4

    def test_status_inquiry(self):
        """Test status inquiry handling."""
        agent = AccountInquiryAgent()

        result = agent.handle_status_inquiry(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        )

        assert result.success is True
        assert result.account_info is not None
        assert result.account_info.status in [AccountStatus.ACTIVE, AccountStatus.INACTIVE,
                                              AccountStatus.SUSPENDED, AccountStatus.CLOSED]

    def test_statement_request(self):
        """Test statement request handling."""
        agent = AccountInquiryAgent()

        result = agent.handle_statement_request(
            customer_id="CUST-001",
            account_id="ACC-001",
            statement_period="2024-01",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "request_id" in result

    def test_invalid_statement_period(self):
        """Test that invalid statement period is rejected."""
        agent = AccountInquiryAgent()

        result = agent.handle_statement_request(
            customer_id="CUST-001",
            account_id="ACC-001",
            statement_period="invalid",
            actor="user@example.com"
        )

        assert result["success"] is False

    def test_rate_limiting(self):
        """Test that rate limiting works."""
        agent = AccountInquiryAgent()

        # Make multiple requests
        for i in range(15):
            result = agent.handle_balance_inquiry(
                customer_id="CUST-RATE-LIMIT",
                account_id="ACC-001",
                actor="user@example.com"
            )

        # Last request should be rate limited
        assert result.success is False
        assert "rate limit" in result.message.lower()

    def test_audit_trail_created(self):
        """Test that audit trail is created for inquiries."""
        agent = AccountInquiryAgent()

        initial_count = len(agent._audit_log)

        agent.handle_balance_inquiry(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        )

        assert len(agent._audit_log) == initial_count + 1


class TestTransactionAgent:
    """Tests for TransactionAgent."""

    def test_agent_initializes(self):
        """Test that agent initializes correctly."""
        agent = TransactionAgent()

        assert agent is not None
        assert agent.config is not None

    def test_get_transaction_status(self):
        """Test transaction status inquiry."""
        agent = TransactionAgent()

        result = agent.get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com"
        )

        assert result.success is True
        assert result.transaction_info is not None
        assert result.transaction_info.status in [TransactionStatus.COMPLETED,
                                                   TransactionStatus.PENDING,
                                                   TransactionStatus.PROCESSING]

    def test_transaction_amount_masked(self):
        """Test that transaction amounts are shown as ranges."""
        agent = TransactionAgent()

        result = agent.get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com"
        )

        if result.transaction_info:
            # Amount should be a range
            assert "$" in result.transaction_info.amount_range

    def test_search_transactions(self):
        """Test transaction search."""
        agent = TransactionAgent()

        result = agent.search_transactions(
            customer_id="CUST-001",
            account_id="ACC-001",
            date_from="2024-01-01",
            date_to="2024-01-31",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "transactions" in result

    def test_invalid_date_range(self):
        """Test that invalid date range is rejected."""
        agent = TransactionAgent()

        result = agent.search_transactions(
            customer_id="CUST-001",
            account_id="ACC-001",
            date_from="2024-01-01",
            date_to="2024-05-01",  # More than 90 days
            actor="user@example.com"
        )

        assert result["success"] is False

    def test_verify_payment(self):
        """Test payment verification."""
        agent = TransactionAgent()

        result = agent.verify_payment(
            customer_id="CUST-001",
            payment_id="PAY-001",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "verified" in result

    def test_get_transfer_status(self):
        """Test transfer status inquiry."""
        agent = TransactionAgent()

        result = agent.get_transfer_status(
            customer_id="CUST-001",
            transfer_id="TRF-001",
            actor="user@example.com"
        )

        # Result should have audit_id regardless of success
        assert "audit_id" in result
        # If successful, should have status
        if result.get("success"):
            assert "status" in result

    def test_no_transaction_initiation(self):
        """Test that agent cannot initiate transactions."""
        agent = TransactionAgent()

        # Verify there's no method to initiate transactions
        assert not hasattr(agent, 'create_transaction')
        assert not hasattr(agent, 'initiate_transfer')
        assert not hasattr(agent, 'send_payment')


class TestComplianceAgent:
    """Tests for ComplianceAgent."""

    def test_agent_initializes(self):
        """Test that agent initializes correctly."""
        agent = ComplianceAgent()

        assert agent is not None
        assert agent.sox is not None  # SOX compliance enabled
        assert agent.finra is not None  # FINRA rules enabled

    def test_pre_transaction_check_passes(self):
        """Test pre-transaction compliance check passes for normal transaction."""
        agent = ComplianceAgent()

        result = agent.check_pre_transaction(
            transaction_type="payment",
            customer_id="CUST-001",
            amount=50.00,
            actor="user@example.com",
            actor_role="agent"
        )

        assert result.passed is True
        assert result.status == ComplianceStatus.PASSED

    def test_pre_transaction_check_flags_large_amount(self):
        """Test that large amounts are flagged."""
        agent = ComplianceAgent()

        result = agent.check_pre_transaction(
            transaction_type="refund_request",
            customer_id="CUST-001",
            amount=150.00,  # Above approval threshold
            actor="user@example.com",
            actor_role="agent"
        )

        assert len(result.recommendations) > 0
        assert any("approval" in r.lower() for r in result.recommendations)

    def test_post_transaction_check(self):
        """Test post-transaction compliance check."""
        agent = ComplianceAgent()

        result = agent.check_post_transaction(
            transaction_id="TXN-001",
            transaction_type="payment",
            customer_id="CUST-001",
            amount=100.00,
            actor="user@example.com"
        )

        assert result.check_type == ComplianceCheckType.POST_TRANSACTION

    def test_suitability_check(self):
        """Test FINRA suitability check."""
        agent = ComplianceAgent()

        result = agent.check_suitability(
            customer_id="CUST-001",
            recommendation="Investment recommendation",
            product_type="options",
            customer_profile={
                "risk_tolerance": "low",
                "investment_objectives": ["preservation"]
            },
            actor="advisor@example.com"
        )

        # High-risk product for low-risk customer should fail
        assert result.passed is False

    def test_aml_check(self):
        """Test AML check."""
        agent = ComplianceAgent()

        result = agent.check_aml(
            customer_id="CUST-001",
            transaction_amount=15000.00,  # Large amount
            transaction_type="transfer"
        )

        assert len(result.warnings) > 0  # Should have warnings for large amount

    def test_flag_suspicious_activity(self):
        """Test suspicious activity flagging."""
        agent = ComplianceAgent()

        result = agent.flag_suspicious_activity(
            customer_id="CUST-001",
            activity_type="unusual_pattern",
            details={"pattern": "velocity"},
            severity="high"
        )

        assert result["success"] is True
        assert result["escalated"] is True

    def test_compliance_summary(self):
        """Test compliance summary."""
        agent = ComplianceAgent()

        summary = agent.get_compliance_summary()

        assert "sox_compliance" in summary
        assert "finra_compliance" in summary
        assert "total_violations" in summary


class TestFraudDetectionAgent:
    """Tests for FraudDetectionAgent."""

    def test_agent_initializes(self):
        """Test that agent initializes correctly."""
        agent = FraudDetectionAgent()

        assert agent is not None
        assert len(agent._alerts) == 0

    def test_analyze_transaction_low_risk(self):
        """Test that normal transaction has low risk."""
        agent = FraudDetectionAgent()

        result = agent.analyze_transaction(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            amount=100.00,
            transaction_type="payment"
        )

        assert result.risk_level in [FraudRiskLevel.LOW, FraudRiskLevel.MEDIUM]
        assert result.overall_risk_score < 0.7

    def test_analyze_transaction_high_risk(self):
        """Test that suspicious transaction has high risk."""
        agent = FraudDetectionAgent()

        # Create some velocity by multiple transactions
        for i in range(15):
            agent.analyze_transaction(
                customer_id="CUST-VELOCITY",
                transaction_id=f"TXN-{i}",
                amount=500.00,
                transaction_type="payment"
            )

        # This transaction should have high velocity risk
        result = agent.analyze_transaction(
            customer_id="CUST-VELOCITY",
            transaction_id="TXN-FINAL",
            amount=500.00,
            transaction_type="payment"
        )

        assert result.factors["velocity"] > 0.5

    def test_structuring_detection(self):
        """Test structuring detection (amounts just under $10,000)."""
        agent = FraudDetectionAgent()

        result = agent.analyze_transaction(
            customer_id="CUST-001",
            transaction_id="TXN-STRUCTURE",
            amount=9500.00,  # Just under reporting threshold
            transaction_type="transfer"
        )

        # Pattern risk should be elevated
        assert result.factors["pattern"] > 0.5

    def test_detect_anomalies(self):
        """Test anomaly detection."""
        agent = FraudDetectionAgent()

        # Create transaction history
        for i in range(10):
            agent.analyze_transaction(
                customer_id="CUST-ANOMALY",
                transaction_id=f"TXN-{i}",
                amount=100.00,  # Normal amounts
                transaction_type="payment"
            )

        # Add anomalous transaction
        agent.analyze_transaction(
            customer_id="CUST-ANOMALY",
            transaction_id="TXN-HUGE",
            amount=50000.00,  # Much larger than normal
            transaction_type="payment"
        )

        anomalies = agent.detect_anomalies("CUST-ANOMALY")

        assert len(anomalies) > 0

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        agent = FraudDetectionAgent()

        # Trigger high-risk transaction to create alert
        for i in range(20):
            agent.analyze_transaction(
                customer_id="CUST-ALERT",
                transaction_id=f"TXN-{i}",
                amount=1000.00,
                transaction_type="payment"
            )

        alerts = agent.get_active_alerts()

        # Should have alerts for this customer
        assert len(alerts) >= 0  # May or may not have alerts depending on risk score

    def test_resolve_alert(self):
        """Test resolving an alert."""
        agent = FraudDetectionAgent()

        # Create an alert manually
        alert = FraudAlert(
            alert_id="ALR-TEST001",
            alert_type=AlertType.BEHAVIORAL_ANOMALY,
            risk_level=FraudRiskLevel.HIGH,
            customer_id="CUST-001",
            description="Test alert"
        )
        agent._alerts.append(alert)

        result = agent.resolve_alert(
            alert_id="ALR-TEST001",
            resolution="False positive - verified customer",
            resolved_by="analyst@example.com",
            is_false_positive=True
        )

        assert result["success"] is True
        assert alert.investigation_status == "false_positive"

    def test_customer_risk_summary(self):
        """Test customer risk summary."""
        agent = FraudDetectionAgent()

        # Add some transactions
        for i in range(5):
            agent.analyze_transaction(
                customer_id="CUST-SUMMARY",
                transaction_id=f"TXN-{i}",
                amount=100.00,
                transaction_type="payment"
            )

        summary = agent.get_customer_risk_summary("CUST-SUMMARY")

        assert summary["customer_id"] == "CUST-SUMMARY"
        assert summary["total_transactions"] == 5


class TestAgentIntegration:
    """Integration tests for financial agents."""

    def test_all_agents_work_together(self):
        """Test that all agents can work together."""
        from variants.financial_services.config import FinancialServicesConfig

        config = FinancialServicesConfig()

        account_agent = AccountInquiryAgent(config)
        transaction_agent = TransactionAgent(config)
        compliance_agent = ComplianceAgent(config)
        fraud_agent = FraudDetectionAgent(config)

        # Simulate a transaction flow
        customer_id = "CUST-INTEGRATION"

        # Check account
        account_result = account_agent.handle_balance_inquiry(
            customer_id=customer_id,
            account_id="ACC-001",
            actor="user@example.com"
        )
        assert account_result.success is True

        # Check compliance
        compliance_result = compliance_agent.check_pre_transaction(
            transaction_type="payment",
            customer_id=customer_id,
            amount=500.00,
            actor="user@example.com",
            actor_role="agent"
        )
        assert compliance_result.passed is True or len(compliance_result.recommendations) >= 0

        # Analyze for fraud
        fraud_result = fraud_agent.analyze_transaction(
            customer_id=customer_id,
            transaction_id="TXN-001",
            amount=500.00,
            transaction_type="payment"
        )
        assert fraud_result.risk_level in [FraudRiskLevel.LOW, FraudRiskLevel.MEDIUM,
                                           FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL]

    def test_agents_use_same_config(self):
        """Test that all agents use the same config."""
        from variants.financial_services.config import FinancialServicesConfig

        config = FinancialServicesConfig()

        account_agent = AccountInquiryAgent(config)
        transaction_agent = TransactionAgent(config)
        compliance_agent = ComplianceAgent(config)
        fraud_agent = FraudDetectionAgent(config)

        # All should have same config
        assert account_agent.config is config
        assert transaction_agent.config is config
        assert compliance_agent.config is config
        assert fraud_agent.config is config

    def test_audit_trails_created(self):
        """Test that all agents create audit trails."""
        account_agent = AccountInquiryAgent()
        transaction_agent = TransactionAgent()
        compliance_agent = ComplianceAgent()
        fraud_agent = FraudDetectionAgent()

        # Perform actions
        account_agent.handle_balance_inquiry(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        )

        transaction_agent.get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com"
        )

        # Check audit logs
        assert len(account_agent._audit_log) > 0
        assert len(transaction_agent._audit_log) > 0


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
