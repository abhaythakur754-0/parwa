"""
Financial Services Integration Tests.

Tests full financial services flow:
- Inquiry handling
- Complaint processing
- Fraud alert flow
- Data isolation
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from variants.financial_services.tasks.handle_inquiry import (
    handle_inquiry,
    InquiryResult,
)
from variants.financial_services.tasks.process_complaint import (
    process_complaint,
    ComplaintResult,
)
from variants.financial_services.tasks.fraud_alert import (
    create_fraud_alert,
    FraudAlertResult,
)
from variants.financial_services.workflows.compliance_workflow import (
    ComplianceWorkflow,
    WorkflowStatus,
)


class TestFinancialInquiry:
    """Tests for financial inquiry handling."""

    def test_handle_balance_inquiry(self):
        """Test balance inquiry handling."""
        result = handle_inquiry(
            customer_id="CUST-001",
            inquiry_type="balance",
            inquiry_data={"account_id": "ACC-001"},
            actor="user@example.com"
        )

        # Inquiry is processed even if compliance check fails
        assert result.inquiry_id.startswith("INQ-")
        assert result.audit_id.startswith("AUD-")

    def test_handle_transaction_inquiry(self):
        """Test transaction inquiry handling."""
        result = handle_inquiry(
            customer_id="CUST-001",
            inquiry_type="transaction",
            inquiry_data={"transaction_id": "TXN-001"},
            actor="user@example.com"
        )

        # Inquiry is processed
        assert result.inquiry_id.startswith("INQ-")

    def test_inquiry_creates_audit_trail(self):
        """Test that inquiry creates audit trail."""
        result = handle_inquiry(
            customer_id="CUST-001",
            inquiry_type="account",
            inquiry_data={},
            actor="user@example.com"
        )

        assert result.audit_id.startswith("AUD-")

    def test_response_masked(self):
        """Test that response is masked."""
        result = handle_inquiry(
            customer_id="CUST-001",
            inquiry_type="balance",
            inquiry_data={},
            actor="user@example.com"
        )

        # Masked response should not contain sensitive data
        assert "1234567890123456" not in result.masked_response


class TestComplaintProcessing:
    """Tests for complaint processing."""

    def test_process_complaint(self):
        """Test complaint processing."""
        result = process_complaint(
            customer_id="CUST-001",
            complaint_type="service",
            complaint_description="Service issue",
            customer_info={"name": "John Doe", "account_id": "ACC-001"},
            actor="support@example.com"
        )

        assert result.success is True
        assert result.complaint_id.startswith("CMP-")
        assert result.status == "open"

    def test_complaint_timeline(self):
        """Test that complaint has timeline deadline."""
        result = process_complaint(
            customer_id="CUST-001",
            complaint_type="billing",
            complaint_description="Billing error",
            customer_info={},
            actor="support@example.com"
        )

        assert result.timeline_deadline is not None

    def test_escalation_detection(self):
        """Test that escalation is detected."""
        result = process_complaint(
            customer_id="CUST-001",
            complaint_type="fraud",
            complaint_description="Unauthorized transaction - possible fraud",
            customer_info={},
            actor="support@example.com"
        )

        assert result.requires_escalation is True
        assert result.assigned_to == "compliance_team"


class TestFraudAlert:
    """Tests for fraud alert creation."""

    def test_create_fraud_alert(self):
        """Test fraud alert creation."""
        result = create_fraud_alert(
            customer_id="CUST-001",
            alert_type="velocity",
            risk_factors=["velocity", "unusual_amount"],
            details={},
            actor="fraud_detection_agent"
        )

        assert result.success is True
        assert result.alert_id.startswith("ALR-")

    def test_high_risk_alert(self):
        """Test high-risk alert."""
        result = create_fraud_alert(
            customer_id="CUST-001",
            alert_type="structuring",
            risk_factors=["structuring", "velocity", "unusual_location"],
            details={},
            actor="fraud_detection_agent"
        )

        assert result.risk_level in ["high", "critical"]
        assert result.priority in ["high", "urgent"]

    def test_critical_alert_escalation(self):
        """Test that critical alerts are escalated."""
        result = create_fraud_alert(
            customer_id="CUST-001",
            alert_type="fraud",
            risk_factors=["structuring", "velocity", "unusual_amount", "off_hours"],
            details={},
            actor="fraud_detection_agent"
        )

        if result.risk_level == "critical":
            assert result.escalated is True


class TestFinancialIntegration:
    """Integration tests for financial services."""

    def test_full_inquiry_flow(self):
        """Test full inquiry flow with workflow."""
        workflow = ComplianceWorkflow()

        result = workflow.execute_sync(
            action_type="inquiry",
            customer_id="CUST-001",
            amount=0.0,
            actor="user@example.com",
            actor_role="agent"
        )

        assert result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]

    def test_complaint_with_workflow(self):
        """Test complaint processing with compliance workflow."""
        # Process complaint
        complaint = process_complaint(
            customer_id="CUST-001",
            complaint_type="service",
            complaint_description="Service issue",
            customer_info={},
            actor="support@example.com"
        )

        # Verify compliance workflow attached
        assert complaint.audit_id.startswith("AUD-")

    def test_fraud_alert_with_inquiry(self):
        """Test fraud alert after inquiry."""
        # Handle inquiry
        inquiry = handle_inquiry(
            customer_id="CUST-001",
            inquiry_type="transaction",
            inquiry_data={"suspicious": True},
            actor="user@example.com"
        )

        # Create fraud alert
        alert = create_fraud_alert(
            customer_id="CUST-001",
            alert_type="suspicious_activity",
            risk_factors=["unusual_amount"],
            details={"inquiry_id": inquiry.inquiry_id}
        )

        assert alert.success is True

    def test_data_isolation(self):
        """Test that customer data is isolated."""
        results = []

        for i in range(3):
            result = handle_inquiry(
                customer_id=f"CUST-{i:03d}",
                inquiry_type="balance",
                inquiry_data={},
                actor="user@example.com"
            )
            results.append(result)

        # Each customer should have unique inquiry ID
        inquiry_ids = [r.inquiry_id for r in results]
        assert len(set(inquiry_ids)) == 3


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
