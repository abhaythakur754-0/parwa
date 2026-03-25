"""
Unit tests for Financial Services Tools and Workflows.

Tests cover:
- Account tools with audit logging
- Transaction tools (read-only)
- Compliance workflow orchestration
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from variants.financial_services.tools.account_tools import (
    get_account_summary,
    verify_account_status,
    request_statement,
    check_account_eligibility,
)
from variants.financial_services.tools.transaction_tools import (
    get_transaction_status,
    search_transactions,
    verify_payment,
    get_transfer_status,
)
from variants.financial_services.workflows.compliance_workflow import (
    ComplianceWorkflow,
    WorkflowResult,
    WorkflowStatus,
    WorkflowStep,
)


class TestAccountTools:
    """Tests for account tools."""

    def test_get_account_summary(self):
        """Test account summary retrieval."""
        result = get_account_summary(
            customer_id="CUST-001",
            account_id="ACC-001234",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "masked_account_number" in result
        assert "audit_id" in result

    def test_account_number_masked(self):
        """Test that account numbers are masked."""
        result = get_account_summary(
            customer_id="CUST-001",
            account_id="1234567890",
            actor="user@example.com"
        )

        masked = result["masked_account_number"]
        assert "XXXX" in masked
        assert "7890" in masked  # Last 4 digits visible

    def test_verify_account_status(self):
        """Test account status verification."""
        result = verify_account_status(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "verified" in result
        assert "audit_id" in result

    def test_request_statement_valid_period(self):
        """Test statement request with valid period."""
        result = request_statement(
            customer_id="CUST-001",
            account_id="ACC-001",
            statement_period="2024-01",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "request_id" in result

    def test_request_statement_invalid_period(self):
        """Test statement request with invalid period."""
        result = request_statement(
            customer_id="CUST-001",
            account_id="ACC-001",
            statement_period="invalid",
            actor="user@example.com"
        )

        assert result["success"] is False

    def test_check_account_eligibility(self):
        """Test eligibility check."""
        result = check_account_eligibility(
            customer_id="CUST-001",
            account_id="ACC-001",
            feature="balance_inquiry",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "eligible" in result

    def test_account_tools_create_audit_trail(self):
        """Test that account tools create audit trail."""
        results = []

        results.append(get_account_summary(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        ))

        results.append(verify_account_status(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        ))

        # All results should have audit_id
        for result in results:
            assert "audit_id" in result
            assert result["audit_id"].startswith("AUD-")


class TestTransactionTools:
    """Tests for transaction tools."""

    def test_get_transaction_status(self):
        """Test transaction status inquiry."""
        result = get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "status" in result
        assert "audit_id" in result

    def test_transaction_amount_masked(self):
        """Test that transaction amounts are shown as ranges."""
        result = get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com"
        )

        # Amount should be a range
        assert "amount_range" in result
        assert "$" in result["amount_range"]

    def test_search_transactions(self):
        """Test transaction search."""
        result = search_transactions(
            customer_id="CUST-001",
            account_id="ACC-001",
            date_from="2024-01-01",
            date_to="2024-01-31",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "transactions" in result

    def test_search_transactions_invalid_date_range(self):
        """Test that invalid date range is rejected."""
        result = search_transactions(
            customer_id="CUST-001",
            account_id="ACC-001",
            date_from="2024-01-01",
            date_to="2024-05-01",  # More than 90 days
            actor="user@example.com"
        )

        assert result["success"] is False

    def test_verify_payment(self):
        """Test payment verification."""
        result = verify_payment(
            customer_id="CUST-001",
            payment_id="PAY-001",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "verified" in result

    def test_get_transfer_status(self):
        """Test transfer status inquiry."""
        result = get_transfer_status(
            customer_id="CUST-001",
            transfer_id="TRF-001",
            actor="user@example.com"
        )

        assert result["success"] is True
        assert "status" in result

    def test_no_transaction_initiation_tools(self):
        """Test that there are no transaction initiation tools."""
        # Verify no initiation functions exist
        import variants.financial_services.tools.transaction_tools as txn_tools

        assert not hasattr(txn_tools, 'create_transaction')
        assert not hasattr(txn_tools, 'initiate_transfer')
        assert not hasattr(txn_tools, 'send_payment')

    def test_transaction_tools_create_audit_trail(self):
        """Test that transaction tools create audit trail."""
        result = get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com"
        )

        assert "audit_id" in result
        assert result["audit_id"].startswith("AUD-")


class TestComplianceWorkflow:
    """Tests for compliance workflow."""

    def test_workflow_initializes(self):
        """Test workflow initialization."""
        workflow = ComplianceWorkflow()

        assert workflow is not None
        assert workflow.compliance_agent is not None

    def test_execute_sync_workflow(self):
        """Test synchronous workflow execution."""
        workflow = ComplianceWorkflow()

        result = workflow.execute_sync(
            action_type="payment",
            customer_id="CUST-001",
            amount=50.00,
            actor="user@example.com",
            actor_role="agent"
        )

        assert result.workflow_id.startswith("WF-")
        assert result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]
        assert result.pre_check_result is not None

    def test_workflow_with_large_amount(self):
        """Test workflow with large amount."""
        workflow = ComplianceWorkflow()

        result = workflow.execute_sync(
            action_type="refund_request",
            customer_id="CUST-001",
            amount=500.00,  # Above threshold
            actor="user@example.com",
            actor_role="agent"
        )

        # Should have recommendations for approval
        assert result.pre_check_result is not None

    def test_workflow_with_action(self):
        """Test workflow with action execution."""
        workflow = ComplianceWorkflow()

        action_called = []

        def mock_action():
            action_called.append(True)
            return {"action": "completed"}

        result = workflow.execute_sync(
            action_type="payment",
            customer_id="CUST-001",
            amount=50.00,
            actor="user@example.com",
            actor_role="agent",
            action_callable=mock_action
        )

        assert len(action_called) == 1
        assert result.audit_id.startswith("AUD-")

    def test_workflow_creates_audit_trail(self):
        """Test that workflow creates audit trail."""
        workflow = ComplianceWorkflow()

        workflow.execute_sync(
            action_type="payment",
            customer_id="CUST-001",
            amount=50.00,
            actor="user@example.com",
            actor_role="agent"
        )

        log = workflow.get_workflow_log()
        assert len(log) > 0
        assert log[0]["action_type"] == "payment"

    def test_workflow_summary(self):
        """Test workflow summary."""
        workflow = ComplianceWorkflow()

        # Execute a few workflows
        for i in range(3):
            workflow.execute_sync(
                action_type="payment",
                customer_id=f"CUST-{i:03d}",
                amount=50.00,
                actor="user@example.com",
                actor_role="agent"
            )

        summary = workflow.get_workflow_summary()

        assert summary["total_workflows"] == 3
        assert "pass_rate" in summary

    def test_workflow_log_filter_by_customer(self):
        """Test workflow log filtering."""
        workflow = ComplianceWorkflow()

        # Execute for multiple customers
        workflow.execute_sync(
            action_type="payment",
            customer_id="CUST-001",
            amount=50.00,
            actor="user@example.com",
            actor_role="agent"
        )

        workflow.execute_sync(
            action_type="payment",
            customer_id="CUST-002",
            amount=50.00,
            actor="user@example.com",
            actor_role="agent"
        )

        log = workflow.get_workflow_log(customer_id="CUST-001")

        assert len(log) == 1
        assert log[0]["customer_id"] == "CUST-001"


class TestToolsIntegration:
    """Integration tests for tools and workflows."""

    def test_tools_use_same_config(self):
        """Test that tools use the same config."""
        from variants.financial_services.config import FinancialServicesConfig

        config = FinancialServicesConfig()

        result1 = get_account_summary(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com",
            config=config
        )

        result2 = get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com",
            config=config
        )

        assert result1["success"] is True
        assert result2["success"] is True

    def test_workflow_uses_tools(self):
        """Test that workflow can use tools."""
        workflow = ComplianceWorkflow()

        # Define action that uses account tools
        def check_account():
            return get_account_summary(
                customer_id="CUST-001",
                account_id="ACC-001",
                actor="workflow"
            )

        result = workflow.execute_sync(
            action_type="account_check",
            customer_id="CUST-001",
            amount=0.00,
            actor="user@example.com",
            actor_role="agent",
            action_callable=check_account
        )

        assert result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]

    def test_all_tools_return_audit_id(self):
        """Test that all tools return audit_id."""
        results = []

        results.append(get_account_summary(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        ))

        results.append(verify_account_status(
            customer_id="CUST-001",
            account_id="ACC-001",
            actor="user@example.com"
        ))

        results.append(get_transaction_status(
            customer_id="CUST-001",
            transaction_id="TXN-001",
            actor="user@example.com"
        ))

        results.append(verify_payment(
            customer_id="CUST-001",
            payment_id="PAY-001",
            actor="user@example.com"
        ))

        for result in results:
            assert "audit_id" in result, f"Missing audit_id in {result}"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
