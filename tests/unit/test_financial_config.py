"""
Unit tests for Financial Services Configuration and Compliance.

Tests cover:
- FinancialServicesConfig
- SOX Compliance
- FINRA Rules
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import the modules under test
from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
    DataClassification,
    EncryptionLevel,
    AuditLogLevel,
)
from variants.financial_services.compliance.sox_compliance import (
    SOXCompliance,
    SOXViolation,
    SOXSection,
    SOXViolationType,
    SOXSeverity,
    AuditEntry,
)
from variants.financial_services.compliance.finra_rules import (
    FINRARules,
    FINRAViolation,
    FINRARule,
    FINRAViolationType,
    FINRASeverity,
    CustomerComplaint,
    SupervisoryReview,
)


class TestFinancialServicesConfig:
    """Tests for FinancialServicesConfig."""

    def test_config_loads_with_defaults(self):
        """Test that config loads with default values."""
        config = FinancialServicesConfig()

        assert config.refund_limit == 500.0
        assert config.approval_threshold == 100.0
        assert config.session_timeout_minutes == 15
        assert config.max_concurrent_sessions == 1
        assert config.data_retention_years == 7
        assert config.audit_all_actions is True

    def test_config_has_regulatory_settings(self):
        """Test that config has required regulatory settings."""
        config = FinancialServicesConfig()

        # SOX compliance
        assert config.sox_compliance_enabled is True
        assert config.audit_log_retention_days == 2555  # 7 years

        # FINRA compliance
        assert config.finra_compliance_enabled is True
        assert config.communication_retention_years == 7

        # PCI compliance
        assert config.pci_compliance_enabled is True
        assert config.pii_masking_enabled is True
        assert config.pci_masking_enabled is True

    def test_higher_refund_limit(self):
        """Test that financial services has higher refund limit."""
        config = FinancialServicesConfig()

        # Financial services has $500 limit vs $50 for Mini
        assert config.refund_limit == 500.0
        assert config.refund_limit > 50.0  # Higher than Mini

    def test_stricter_approval_threshold(self):
        """Test that approval threshold is appropriate."""
        config = FinancialServicesConfig()

        # Amounts >= $100 require approval
        assert config.approval_threshold == 100.0
        assert config.requires_approval(99.99) is False
        assert config.requires_approval(100.00) is True
        assert config.requires_approval(500.00) is True

    def test_dual_approval_threshold(self):
        """Test dual approval requirements."""
        config = FinancialServicesConfig()

        # Amounts >= $500 require dual approval
        assert config.dual_approval_threshold == 500.0
        assert config.requires_dual_approval(499.99) is False
        assert config.requires_dual_approval(500.00) is True

    def test_account_number_masking(self):
        """Test account number masking."""
        config = FinancialServicesConfig()

        # Mask account numbers showing only last 4 digits
        assert config.mask_account_number("1234567890") == "XXXXXX7890"
        assert config.mask_account_number("1234567890123456") == "XXXXXXXXXXXX3456"
        assert config.mask_account_number("1234") == "1234"  # Short numbers not masked

    def test_card_number_masking(self):
        """Test payment card number masking per PCI DSS."""
        config = FinancialServicesConfig()

        # Mask card numbers showing only last 4 digits
        masked = config.mask_card_number("4111111111111234")
        assert masked == "XXXX-XXXX-XXXX-1234"

        # Test with spaces/dashes
        masked = config.mask_card_number("4111-1111-1111-1234")
        assert masked == "XXXX-XXXX-XXXX-1234"

    def test_encryption_settings(self):
        """Test encryption requirements."""
        config = FinancialServicesConfig()

        # Financial services requires enhanced encryption
        assert config.encryption_at_rest == EncryptionLevel.FINANCIAL
        assert config.encryption_in_transit == EncryptionLevel.ENHANCED

    def test_session_security_settings(self):
        """Test session security settings."""
        config = FinancialServicesConfig()

        # Regulatory requirements for session security
        assert config.session_timeout_minutes == 15
        assert config.max_concurrent_sessions == 1
        assert config.idle_timeout_minutes == 5

    def test_get_compliance_requirements(self):
        """Test compliance requirements summary."""
        config = FinancialServicesConfig()
        requirements = config.get_compliance_requirements()

        assert "sox" in requirements
        assert requirements["sox"]["enabled"] is True
        assert requirements["sox"]["data_retention_years"] == 7

        assert "finra" in requirements
        assert requirements["finra"]["enabled"] is True

        assert "pci_dss" in requirements
        assert requirements["pci_dss"]["enabled"] is True

    def test_get_variant_info(self):
        """Test variant identification."""
        config = FinancialServicesConfig()

        assert config.get_variant_name() == "Financial Services PARWA"
        assert config.get_variant_id() == "financial_services"

    def test_singleton_config(self):
        """Test get_financial_services_config returns consistent instance."""
        config1 = get_financial_services_config()
        config2 = get_financial_services_config()

        assert config1 is config2


class TestSOXCompliance:
    """Tests for SOX compliance module."""

    def test_sox_compliance_initializes(self):
        """Test SOX compliance checker initializes."""
        sox = SOXCompliance()

        assert sox is not None
        assert len(sox._audit_log) == 0
        assert len(sox._violations) == 0

    def test_check_action_compliant(self):
        """Test checking compliant action."""
        sox = SOXCompliance()

        result = sox.check_action(
            action_type="refund_request",
            actor="user@example.com",
            actor_role="agent",
            amount=50.00
        )

        # Small amount should be compliant
        assert result["compliant"] is True
        assert result["action_type"] == "refund_request"

    def test_check_action_requires_approval(self):
        """Test that large amounts require approval."""
        sox = SOXCompliance()

        result = sox.check_action(
            action_type="refund_request",
            actor="user@example.com",
            actor_role="agent",
            amount=150.00
        )

        # Large amount should have violations
        assert result["compliant"] is False
        assert len(result["violations"]) > 0

    def test_duty_segregation_check(self):
        """Test segregation of duties enforcement."""
        sox = SOXCompliance()

        # User requests refund
        sox.check_action(
            action_type="refund_request",
            actor="user@example.com",
            actor_role="agent"
        )

        # Same user tries to approve - should violate segregation
        result = sox.check_action(
            action_type="refund_approve",
            actor="user@example.com",
            actor_role="agent"
        )

        # Should have segregation violation
        assert result["compliant"] is False
        assert any(
            v.violation_type == SOXViolationType.DUTY_SEGREGATION
            for v in result["violations"]
        )

    def test_create_audit_entry(self):
        """Test creating SOX-compliant audit entry."""
        sox = SOXCompliance()

        entry = sox.create_audit_entry(
            action_type="refund_request",
            actor="user@example.com",
            actor_role="agent",
            resource_type="refund",
            resource_id="REF-123",
            justification="Customer complaint resolution"
        )

        assert entry.action_type == "refund_request"
        assert entry.actor == "user@example.com"
        assert entry.entry_hash != ""  # Has integrity hash
        assert len(sox._audit_log) == 1

    def test_audit_entry_integrity(self):
        """Test audit entry integrity hash."""
        sox = SOXCompliance()

        entry = sox.create_audit_entry(
            action_type="test_action",
            actor="test@example.com",
            actor_role="admin",
            resource_type="test",
            resource_id="TEST-1",
            justification="Test justification"
        )

        # Verify integrity
        result = sox.verify_audit_integrity()
        assert result["valid"] is True
        assert result["entries_checked"] == 1

    def test_get_compliance_summary(self):
        """Test SOX compliance summary."""
        sox = SOXCompliance()

        summary = sox.get_compliance_summary()

        assert "total_audit_entries" in summary
        assert "total_violations" in summary
        assert "compliance_status" in summary

    def test_violation_severity_levels(self):
        """Test violation severity classification."""
        sox = SOXCompliance()

        # Trigger a violation with large amount
        result = sox.check_action(
            action_type="refund_request",
            actor="user@example.com",
            actor_role="agent",
            amount=600.00  # Above dual approval threshold
        )

        if result["violations"]:
            violation = result["violations"][0]
            assert violation.severity in [SOXSeverity.LOW, SOXSeverity.MEDIUM,
                                          SOXSeverity.HIGH, SOXSeverity.CRITICAL]


class TestFINRARules:
    """Tests for FINRA rules module."""

    def test_finra_rules_initializes(self):
        """Test FINRA rules checker initializes."""
        finra = FINRARules()

        assert finra is not None
        assert len(finra._complaints) == 0
        assert len(finra._violations) == 0

    def test_create_complaint(self):
        """Test creating customer complaint record."""
        finra = FINRARules()

        complaint = finra.create_complaint(
            customer_name="John Doe",
            customer_account="ACC-12345",
            description="Unauthorized transaction",
            complaint_type="written"
        )

        assert complaint.complaint_id.startswith("CMP-")
        assert complaint.customer_name == "John Doe"
        assert complaint.status == "open"
        assert len(finra._complaints) == 1

    def test_process_complaint(self):
        """Test processing customer complaint."""
        finra = FINRARules()

        # Create complaint
        complaint = finra.create_complaint(
            customer_name="Jane Doe",
            customer_account="ACC-67890",
            description="Billing error",
            complaint_type="electronic"
        )

        # Process complaint
        result = finra.process_complaint(
            complaint_id=complaint.complaint_id,
            resolution_description="Refund processed",
            supervisor="supervisor@example.com"
        )

        assert result["success"] is True
        assert result["timeline_compliant"] is True

        # Check complaint is resolved
        updated = next(c for c in finra._complaints
                       if c.complaint_id == complaint.complaint_id)
        assert updated.status == "resolved"

    def test_supervisory_review(self):
        """Test creating supervisory review."""
        finra = FINRARules()

        review = finra.create_supervisory_review(
            review_type="transaction",
            reviewer="supervisor@example.com",
            items_reviewed=["TXN-1", "TXN-2", "TXN-3"],
            findings=["No issues found"],
            actions_taken=["Approved all transactions"]
        )

        assert review.review_id.startswith("REV-")
        assert review.review_type == "transaction"
        assert len(finra._supervisory_reviews) == 1

    def test_customer_info_check(self):
        """Test customer account information check."""
        finra = FINRARules()

        # Complete customer info
        complete_info = {
            "customer_name": "John Doe",
            "customer_address": "123 Main St",
            "customer_tax_id": "XXX-XX-1234",
            "customer_dob": "1980-01-01",
            "customer_occupation": "Engineer",
            "customer_employer": "Tech Corp",
            "investment_objectives": ["growth"],
            "risk_tolerance": "moderate",
            "account_type": "individual",
        }

        result = finra.check_customer_info(complete_info)
        assert result["compliant"] is True
        assert len(result["missing_fields"]) == 0

    def test_customer_info_missing_fields(self):
        """Test detection of missing customer info."""
        finra = FINRARules()

        # Incomplete customer info
        incomplete_info = {
            "customer_name": "Jane Doe",
            "customer_address": "456 Oak Ave",
            # Missing required fields
        }

        result = finra.check_customer_info(incomplete_info)
        assert result["compliant"] is False
        assert len(result["missing_fields"]) > 0

    def test_suitability_check(self):
        """Test recommendation suitability check."""
        finra = FINRARules()

        # Conservative customer
        conservative_profile = {
            "risk_tolerance": "low",
            "investment_objectives": ["income", "preservation"],
        }

        # High-risk product should be flagged
        result = finra.check_suitability(
            recommendation="Options trading strategy",
            customer_profile=conservative_profile,
            product_type="options"
        )

        assert result["suitable"] is False
        assert len(result["issues"]) > 0

    def test_get_pending_complaints(self):
        """Test getting pending complaints."""
        finra = FINRARules()

        # Create complaints
        finra.create_complaint(
            customer_name="Customer 1",
            customer_account="ACC-1",
            description="Issue 1",
            complaint_type="written"
        )
        finra.create_complaint(
            customer_name="Customer 2",
            customer_account="ACC-2",
            description="Issue 2",
            complaint_type="electronic"
        )

        pending = finra.get_pending_complaints()
        assert len(pending) == 2

    def test_compliance_summary(self):
        """Test FINRA compliance summary."""
        finra = FINRARules()

        summary = finra.get_compliance_summary()

        assert "total_complaints" in summary
        assert "open_complaints" in summary
        assert "total_violations" in summary
        assert "compliance_status" in summary


class TestIntegration:
    """Integration tests for financial services compliance."""

    def test_config_and_sox_integration(self):
        """Test config integrates with SOX compliance."""
        config = FinancialServicesConfig()
        sox = SOXCompliance()

        # Check that SOX uses config settings
        assert config.sox_compliance_enabled is True
        assert config.audit_all_actions is True

        # Create audit entry
        entry = sox.create_audit_entry(
            action_type="financial_transaction",
            actor="user@example.com",
            actor_role="agent",
            resource_type="refund",
            resource_id="REF-1",
            justification="Customer request"
        )

        assert entry is not None

    def test_config_and_finra_integration(self):
        """Test config integrates with FINRA rules."""
        config = FinancialServicesConfig()
        finra = FINRARules()

        # Check that FINRA uses config settings
        assert config.finra_compliance_enabled is True
        assert config.complaint_retention_years == 7

        # Create complaint
        complaint = finra.create_complaint(
            customer_name="Test Customer",
            customer_account="ACC-TEST",
            description="Test complaint",
            complaint_type="written"
        )

        assert complaint is not None

    def test_masking_integration(self):
        """Test PII/PCI masking integration."""
        config = FinancialServicesConfig()

        # Verify masking is enabled
        assert config.pii_masking_enabled is True
        assert config.pci_masking_enabled is True
        assert config.account_number_masking is True

        # Test masking functions
        assert "7890" in config.mask_account_number("1234567890")
        assert "1234" in config.mask_card_number("4111111111111234")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
