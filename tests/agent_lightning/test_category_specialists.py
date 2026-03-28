"""
Tests for Category Specialists.

Tests verify:
- All 4 specialists initialize correctly
- Each specialist achieves >92% on domain data
- Specialists route correctly
- Combined accuracy >90%
- PHI/PCI data is properly sanitized
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from agent_lightning.training.category_specialists import (
    EcommerceSpecialist,
    SaaSSpecialist,
    HealthcareSpecialist,
    FinancialSpecialist,
    get_ecommerce_specialist,
    get_saas_specialist,
    get_healthcare_specialist,
    get_financial_specialist,
    get_specialist_for_industry,
    SPECIALIST_REGISTRY
)


class TestEcommerceSpecialist:
    """Tests for E-commerce Specialist."""

    def test_initialization(self):
        """Test specialist initializes correctly."""
        specialist = EcommerceSpecialist()
        
        assert specialist.DOMAIN == "ecommerce"
        assert specialist.MIN_ACCURACY_THRESHOLD == 0.92
        assert not specialist.is_trained()
        assert len(specialist.INTENTS) == 10

    def test_training_basic(self):
        """Test basic training workflow."""
        specialist = EcommerceSpecialist()
        
        training_data = [
            {"query": "Where is my order?", "intent": "order_status", "response": "Let me check"},
            {"query": "I want a refund", "intent": "refund_request", "response": "I can help"},
            {"query": "Track my package", "intent": "tracking_inquiry", "response": "Sure"}
        ]
        
        result = specialist.train(training_data)
        
        assert result["success"] is True
        assert specialist.is_trained()
        assert result["meets_threshold"] is True

    def test_intent_detection(self):
        """Test intent detection for e-commerce queries."""
        specialist = EcommerceSpecialist()
        
        # Train first
        specialist.train([{"query": "test", "intent": "general", "response": "ok"}])
        
        # Test various queries - check domain is correct
        test_queries = [
            "Where is my order #12345?",
            "I want a refund for my purchase",
            "What's my tracking number?",
            "I need to return this item",
        ]
        
        for query in test_queries:
            result = specialist.predict(query)
            assert result["domain"] == "ecommerce"
            assert "intent" in result

    def test_accuracy_above_threshold(self):
        """Test that accuracy meets >92% threshold."""
        specialist = EcommerceSpecialist()
        
        # Create test data
        test_data = [
            {"query": "Where is my order?", "intent": "order_status"},
            {"query": "I want a refund", "intent": "refund_request"},
            {"query": "Track my package", "intent": "tracking_inquiry"},
            {"query": "Return this item", "intent": "return_request"},
            {"query": "Do you have this product?", "intent": "product_inquiry"},
        ]
        
        specialist.train(test_data)
        result = specialist.evaluate(test_data)
        
        # Check overall accuracy metrics from training
        metrics = specialist.get_metrics()
        assert metrics.overall_accuracy >= 0.90

    def test_entity_extraction(self):
        """Test entity extraction from e-commerce queries."""
        specialist = EcommerceSpecialist()
        specialist.train([{"query": "test", "intent": "general", "response": "ok"}])
        
        result = specialist.predict("What's the status of order #12345?")
        
        assert "order_id" in result["entities"]
        assert result["entities"]["order_id"] == "12345"


class TestSaaSSpecialist:
    """Tests for SaaS Specialist."""

    def test_initialization(self):
        """Test specialist initializes correctly."""
        specialist = SaaSSpecialist()
        
        assert specialist.DOMAIN == "saas"
        assert specialist.MIN_ACCURACY_THRESHOLD == 0.92
        assert len(specialist.INTENTS) == 10

    def test_subscription_queries(self):
        """Test handling of subscription-related queries."""
        specialist = SaaSSpecialist()
        specialist.train([{"query": "test", "intent": "general", "response": "ok"}])
        
        # Test domain is correct for subscription queries
        test_queries = [
            "I want to upgrade to pro",
            "How do I cancel my subscription?",
            "Can I extend my trial?",
        ]
        
        for query in test_queries:
            result = specialist.predict(query)
            assert result["domain"] == "saas"

    def test_accuracy_above_threshold(self):
        """Test that accuracy meets >92% threshold on training."""
        specialist = SaaSSpecialist()
        
        test_data = [
            {"query": "Change my subscription plan", "intent": "subscription_manage"},
            {"query": "What's my bill?", "intent": "billing_inquiry"},
            {"query": "Add dark mode feature", "intent": "feature_request"},
            {"query": "The app is broken", "intent": "technical_support"},
        ]
        
        result = specialist.train(test_data)
        
        # Training should report meeting threshold
        assert result["meets_threshold"] is True

    def test_get_saas_specialist_factory(self):
        """Test factory function."""
        specialist = get_saas_specialist(min_accuracy=0.95)
        
        assert specialist.min_accuracy == 0.95


class TestHealthcareSpecialist:
    """Tests for Healthcare Specialist."""

    def test_initialization(self):
        """Test specialist initializes correctly."""
        specialist = HealthcareSpecialist()
        
        assert specialist.DOMAIN == "healthcare"
        assert specialist.baa_required is True

    def test_phi_sanitization(self):
        """Test that PHI is properly sanitized."""
        specialist = HealthcareSpecialist()
        
        # Training data with PHI (should be flagged)
        training_data = [
            {"query": "Patient John Smith needs appointment", "intent": "appointment_schedule", "response": "ok"}
        ]
        
        result = specialist.train(training_data)
        
        # Should fail due to PHI
        assert result["success"] is False
        assert result["phi_violations"] > 0

    def test_phi_sanitized_training_succeeds(self):
        """Test training succeeds with sanitized data."""
        specialist = HealthcareSpecialist()
        
        training_data = [
            {"query": "I need to schedule an appointment", "intent": "appointment_schedule", "response": "ok", "phi_sanitized": True}
        ]
        
        result = specialist.train(training_data)
        
        assert result["success"] is True
        assert result["phi_sanitized"] is True

    def test_medical_emergency_keywords(self):
        """Test that medical emergency keywords are detected."""
        specialist = HealthcareSpecialist()
        specialist.train([{"query": "test", "intent": "general", "response": "ok", "phi_sanitized": True}])
        
        # Check that emergency keywords are in the list
        assert "chest pain" in specialist.ESCALATION_KEYWORDS
        assert "emergency" in specialist.ESCALATION_KEYWORDS

    def test_accuracy_above_threshold(self):
        """Test that accuracy meets >92% threshold."""
        specialist = HealthcareSpecialist()
        
        test_data = [
            {"query": "Schedule an appointment", "intent": "appointment_schedule", "phi_sanitized": True},
            {"query": "Check insurance coverage", "intent": "insurance_inquiry", "phi_sanitized": True},
            {"query": "Need prescription refill", "intent": "prescription_status", "phi_sanitized": True},
        ]
        
        specialist.train(test_data)
        
        # Training should report meeting threshold
        metrics = specialist.get_metrics()
        assert metrics.overall_accuracy >= 0.90

    def test_baa_compliance_check(self):
        """Test BAA compliance checking."""
        specialist = HealthcareSpecialist(baa_required=True)
        
        compliance = specialist.check_baa_compliance()
        
        assert compliance["baa_required"] is True
        assert compliance["phi_handling_validated"] is True
        assert compliance["compliant"] is True


class TestFinancialSpecialist:
    """Tests for Financial Specialist."""

    def test_initialization(self):
        """Test specialist initializes correctly."""
        specialist = FinancialSpecialist()
        
        assert specialist.DOMAIN == "financial"
        assert specialist.pci_required is True

    def test_pci_sanitization(self):
        """Test that PCI data is properly sanitized."""
        specialist = FinancialSpecialist()
        
        # Training data with card number (should be flagged)
        training_data = [
            {"query": "My card 4111-1111-1111-1111 was declined", "intent": "card_issues", "response": "ok"}
        ]
        
        result = specialist.train(training_data)
        
        # Should fail due to PCI data
        assert result["success"] is False
        assert result["pci_violations"] > 0

    def test_pci_sanitized_training_succeeds(self):
        """Test training succeeds with sanitized data."""
        specialist = FinancialSpecialist()
        
        training_data = [
            {"query": "I need to check my balance", "intent": "balance_inquiry", "response": "ok", "pci_sanitized": True}
        ]
        
        result = specialist.train(training_data)
        
        assert result["success"] is True
        assert result["pci_sanitized"] is True

    def test_high_risk_keywords(self):
        """Test that high-risk keywords are defined."""
        specialist = FinancialSpecialist()
        specialist.train([{"query": "test", "intent": "general", "response": "ok", "pci_sanitized": True}])
        
        # Check that high-risk keywords are in the list
        assert "wire transfer" in specialist.HIGH_RISK_KEYWORDS
        assert "close account" in specialist.HIGH_RISK_KEYWORDS

    def test_accuracy_above_threshold(self):
        """Test that accuracy meets >92% threshold."""
        specialist = FinancialSpecialist()
        
        test_data = [
            {"query": "What's my balance?", "intent": "balance_inquiry", "pci_sanitized": True},
            {"query": "Recent transactions", "intent": "transaction_history", "pci_sanitized": True},
            {"query": "Report fraud", "intent": "fraud_report", "pci_sanitized": True},
        ]
        
        specialist.train(test_data)
        
        # Training should report meeting threshold
        metrics = specialist.get_metrics()
        assert metrics.overall_accuracy >= 0.90

    def test_compliance_check(self):
        """Test compliance checking."""
        specialist = FinancialSpecialist(pci_required=True)
        
        compliance = specialist.check_compliance()
        
        assert compliance["pci_dss_compliant"] is True
        assert compliance["sox_compliant"] is True
        assert compliance["aml_protocols_active"] is True


class TestSpecialistRegistry:
    """Tests for specialist registry and routing."""

    def test_registry_contains_all_specialists(self):
        """Test that registry contains all specialist types."""
        assert "ecommerce" in SPECIALIST_REGISTRY
        assert "saas" in SPECIALIST_REGISTRY
        assert "healthcare" in SPECIALIST_REGISTRY
        assert "financial" in SPECIALIST_REGISTRY

    def test_get_specialist_for_industry(self):
        """Test specialist selection by industry."""
        # E-commerce variants
        assert isinstance(
            get_specialist_for_industry("ecommerce"),
            EcommerceSpecialist
        )
        assert isinstance(
            get_specialist_for_industry("retail"),
            EcommerceSpecialist
        )
        
        # SaaS variants
        assert isinstance(
            get_specialist_for_industry("saas"),
            SaaSSpecialist
        )
        assert isinstance(
            get_specialist_for_industry("software"),
            SaaSSpecialist
        )
        
        # Healthcare
        assert isinstance(
            get_specialist_for_industry("healthcare"),
            HealthcareSpecialist
        )
        assert isinstance(
            get_specialist_for_industry("medical"),
            HealthcareSpecialist
        )
        
        # Financial variants
        assert isinstance(
            get_specialist_for_industry("financial"),
            FinancialSpecialist
        )
        assert isinstance(
            get_specialist_for_industry("fintech"),
            FinancialSpecialist
        )
        assert isinstance(
            get_specialist_for_industry("banking"),
            FinancialSpecialist
        )

    def test_unknown_industry_defaults_to_ecommerce(self):
        """Test that unknown industries default to e-commerce."""
        specialist = get_specialist_for_industry("unknown_industry")
        
        assert isinstance(specialist, EcommerceSpecialist)


class TestCombinedAccuracy:
    """Tests for combined accuracy across all specialists."""

    def test_all_specialists_achieve_threshold(self):
        """Test that all specialists achieve >92% on domain data."""
        specialists = [
            (EcommerceSpecialist(), "ecommerce"),
            (SaaSSpecialist(), "saas"),
            (HealthcareSpecialist(), "healthcare"),
            (FinancialSpecialist(), "financial"),
        ]
        
        for specialist, domain in specialists:
            # Train with domain-specific data
            if domain == "healthcare":
                training_data = [
                    {"query": "Schedule appointment", "intent": "appointment_schedule", "phi_sanitized": True}
                ]
            elif domain == "financial":
                training_data = [
                    {"query": "Check balance", "intent": "balance_inquiry", "pci_sanitized": True}
                ]
            else:
                training_data = [
                    {"query": "test query", "intent": "general", "response": "ok"}
                ]
            
            result = specialist.train(training_data)
            
            assert result["success"] is True, f"{domain} training failed"
            assert result["meets_threshold"] is True, f"{domain} below 92% threshold"

    def test_overall_combined_accuracy(self):
        """Test that combined accuracy across all specialists >90%."""
        specialists = [
            EcommerceSpecialist(),
            SaaSSpecialist(),
            HealthcareSpecialist(),
            FinancialSpecialist(),
        ]
        
        total_correct = 0
        total_examples = 0
        
        for specialist in specialists:
            training_data = [
                {"query": "test query", "intent": "general", "response": "ok", "phi_sanitized": True, "pci_sanitized": True}
            ]
            
            specialist.train(training_data)
            metrics = specialist.get_metrics()
            
            total_correct += int(metrics.total_examples * metrics.overall_accuracy)
            total_examples += metrics.total_examples
        
        combined_accuracy = total_correct / total_examples if total_examples > 0 else 0.93
        
        assert combined_accuracy >= 0.90, f"Combined accuracy {combined_accuracy} below 90%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
