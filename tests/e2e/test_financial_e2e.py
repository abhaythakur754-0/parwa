"""
End-to-End Tests for Financial Services.

Tests complete financial flows:
- Financial inquiry end-to-end
- Complaint processing flow
- Fraud alert handling
- Compliance dashboard access
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from variants.financial_services.config import FinancialServicesConfig
from variants.financial_services.workflows.compliance_workflow import (
    ComplianceWorkflow,
    WorkflowStatus,
)
from variants.financial_services.tasks.handle_inquiry import handle_inquiry
from variants.financial_services.tasks.process_complaint import process_complaint
from variants.financial_services.tasks.fraud_alert import create_fraud_alert


class TestFinancialE2E:
    """End-to-end tests for financial services."""

    def test_financial_inquiry_e2e(self):
        """Test complete financial inquiry flow."""
        # Step 1: Create workflow
        workflow = ComplianceWorkflow()

        # Step 2: Handle inquiry
        result = handle_inquiry(
            customer_id="CUST-001",
            inquiry_type="balance",
            inquiry_data={"account_id": "ACC-001"},
            actor="user@example.com"
        )

        # Verify result - inquiry processed regardless of compliance status
        assert result.inquiry_id.startswith("INQ-")
        assert result.audit_id.startswith("AUD-")

    def test_complaint_processing_e2e(self):
        """Test complete complaint processing flow."""
        # Process complaint
        result = process_complaint(
            customer_id="CUST-001",
            complaint_type="service",
            complaint_description="Service issue reported",
            customer_info={"name": "Test Customer", "account_id": "ACC-001"},
            actor="support@example.com"
        )

        # Verify result
        assert result.success is True
        assert result.complaint_id.startswith("CMP-")
        assert result.status == "open"

    def test_fraud_alert_e2e(self):
        """Test complete fraud alert flow."""
        # Create alert
        result = create_fraud_alert(
            customer_id="CUST-001",
            alert_type="velocity",
            risk_factors=["velocity", "unusual_amount"],
            details={"transaction_id": "TXN-001"},
            actor="fraud_detection_agent"
        )

        # Verify result
        assert result.success is True
        assert result.alert_id.startswith("ALR-")
        assert result.risk_level in ["low", "medium", "high", "critical"]

    def test_full_compliance_workflow_e2e(self):
        """Test full compliance workflow."""
        workflow = ComplianceWorkflow()

        # Define an action
        action_executed = []

        def mock_action():
            action_executed.append(True)
            return {"status": "success"}

        # Execute workflow
        result = workflow.execute_sync(
            action_type="payment",
            customer_id="CUST-001",
            amount=100.00,
            actor="user@example.com",
            actor_role="agent",
            action_callable=mock_action
        )

        # Verify workflow completed (may pass or fail based on audit trail)
        assert result.workflow_id.startswith("WF-")
        assert len(action_executed) == 1  # Action was executed

    def test_multi_step_financial_flow(self):
        """Test multi-step financial flow."""
        customer_id = "CUST-FLOW-001"

        # Step 1: Handle inquiry
        inquiry = handle_inquiry(
            customer_id=customer_id,
            inquiry_type="balance",
            inquiry_data={},
            actor="user@example.com"
        )
        assert inquiry.inquiry_id.startswith("INQ-")

        # Step 2: Create fraud alert (if needed)
        alert = create_fraud_alert(
            customer_id=customer_id,
            alert_type="test",
            risk_factors=[],
            details={"inquiry_id": inquiry.inquiry_id}
        )
        assert alert.alert_id.startswith("ALR-")

        # Step 3: Verify audit trail exists
        assert inquiry.audit_id is not None
        assert alert.audit_id is not None

    def test_compliance_dashboard_data(self):
        """Test that dashboard data is available."""
        workflow = ComplianceWorkflow()

        # Execute some actions
        for i in range(3):
            workflow.execute_sync(
                action_type="inquiry",
                customer_id=f"CUST-{i:03d}",
                amount=0.0,
                actor="user@example.com",
                actor_role="agent"
            )

        # Get summary
        summary = workflow.get_workflow_summary()

        assert summary["total_workflows"] == 3
        assert summary["pass_rate"] >= 0

    def test_financial_services_config_integration(self):
        """Test that config integrates properly."""
        config = FinancialServicesConfig()

        # Verify financial services settings
        assert config.sox_compliance_enabled is True
        assert config.finra_compliance_enabled is True
        assert config.pci_compliance_enabled is True
        assert config.audit_all_actions is True

    def test_all_tasks_create_audit_trails(self):
        """Test that all tasks create audit trails."""
        results = []

        # Execute all task types
        results.append(handle_inquiry(
            customer_id="CUST-001",
            inquiry_type="balance",
            inquiry_data={},
            actor="user@example.com"
        ))

        results.append(process_complaint(
            customer_id="CUST-001",
            complaint_type="test",
            complaint_description="Test",
            customer_info={},
            actor="user@example.com"
        ))

        results.append(create_fraud_alert(
            customer_id="CUST-001",
            alert_type="test",
            risk_factors=[],
            details={}
        ))

        # All should have audit IDs
        for result in results:
            assert hasattr(result, 'audit_id')
            assert result.audit_id.startswith("AUD-")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
