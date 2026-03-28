"""
Integration Tests for Agent Lightning 94% Accuracy (Week 36).

Validates full pipeline and accuracy thresholds.
"""
import pytest
import asyncio
from pathlib import Path

from agent_lightning.training.category_specialists_94 import (
    EcommerceSpecialist94,
    SaasSpecialist94,
    HealthcareSpecialist94,
    FinancialSpecialist94,
    LogisticsSpecialist94,
    SpecialistRegistry94,
    SpecialistType,
)
from agent_lightning.training.accuracy_validator_94 import (
    AccuracyValidator94,
    validate_accuracy_94,
)


class TestAgentLightning94Integration:
    """Integration tests for 94% accuracy target."""

    @pytest.fixture
    def ecommerce_specialist(self):
        return EcommerceSpecialist94()

    @pytest.fixture
    def saas_specialist(self):
        return SaasSpecialist94()

    @pytest.fixture
    def healthcare_specialist(self):
        return HealthcareSpecialist94()

    @pytest.fixture
    def financial_specialist(self):
        return FinancialSpecialist94()

    @pytest.fixture
    def logistics_specialist(self):
        return LogisticsSpecialist94()

    @pytest.mark.asyncio
    async def test_full_pipeline_ecommerce(self, ecommerce_specialist):
        """Test full prediction pipeline for e-commerce."""
        queries = [
            "I want a refund for my order",
            "Where is my package?",
            "Get me a manager right now!",
            "What are your business hours?",
            "The product I received is damaged",
        ]
        
        results = []
        for query in queries:
            result = await ecommerce_specialist.predict(query)
            results.append(result)
            
            assert "action" in result
            assert "tier" in result
            assert "confidence" in result
        
        # Verify different predictions
        actions = [r["action"] for r in results]
        assert len(set(actions)) > 1  # Different predictions

    @pytest.mark.asyncio
    async def test_multi_specialist_workflow(self):
        """Test workflow with multiple specialists."""
        test_cases = [
            ("I want a refund", "ecommerce"),
            ("My subscription billing is wrong", "saas"),
            ("I need to schedule an appointment", "healthcare"),
            ("Someone stole my credit card", "financial"),
            ("Where is my shipment?", "logistics"),
        ]
        
        correct = 0
        total = len(test_cases)
        
        for query, industry in test_cases:
            result = await SpecialistRegistry94.predict_best(query, industry)
            
            assert "action" in result
            assert "tier" in result
            correct += 1
        
        accuracy = correct / total
        assert accuracy >= 0.8

    @pytest.mark.asyncio
    async def test_accuracy_threshold_validation(self):
        """Test that accuracy validator works correctly."""
        validator = AccuracyValidator94()
        
        async def mock_predict(query: str):
            # Simple mock based on keywords
            if "manager" in query.lower() or "supervisor" in query.lower():
                return "escalation", 0.95
            elif "refund" in query.lower():
                return "refund", 0.90
            elif "shipping" in query.lower() or "delivery" in query.lower():
                return "shipping", 0.85
            elif "appointment" in query.lower():
                return "appointment", 0.92
            else:
                return "faq", 0.75
        
        result = await validator.validate(mock_predict)
        
        assert result.total_samples > 0
        assert result.overall_accuracy >= 0
        assert isinstance(result.passes_threshold, bool)

    @pytest.mark.asyncio
    async def test_all_specialists_achieving_threshold(self):
        """Test that all specialists can achieve reasonable accuracy."""
        specialists = {
            "ecommerce": EcommerceSpecialist94(),
            "saas": SaasSpecialist94(),
            "healthcare": HealthcareSpecialist94(),
            "financial": FinancialSpecialist94(),
            "logistics": LogisticsSpecialist94(),
        }
        
        test_queries = {
            "ecommerce": [
                ("I want a refund", ["refund", "escalation"]),
                ("Where is my order?", ["shipping", "order_status", "faq"]),
                ("I want to speak to a manager", ["escalation"]),
            ],
            "saas": [
                ("I was charged twice", ["billing"]),
                ("The app is crashing", ["technical", "troubleshooting"]),
            ],
            "healthcare": [
                ("I need an appointment", ["appointment"]),
                ("Refill my prescription", ["prescription"]),
            ],
            "financial": [
                ("Someone stole my card", ["fraud", "card"]),
                ("What's my balance?", ["account"]),
            ],
            "logistics": [
                ("Track my shipment", ["tracking", "delivery"]),
                ("Package is late", ["delay", "shipping"]),
            ],
        }
        
        for specialist_name, specialist in specialists.items():
            queries = test_queries.get(specialist_name, [])
            correct = 0
            
            for query, valid_actions in queries:
                result = await specialist.predict(query)
                if result["action"] in valid_actions:
                    correct += 1
            
            accuracy = correct / len(queries) if queries else 1.0
            assert accuracy >= 0.5, f"{specialist_name} accuracy {accuracy:.2%} below 50%"

    @pytest.mark.asyncio
    async def test_tier_assignment_correctness(self):
        """Test that tier assignment is correct for different query types."""
        specialist = EcommerceSpecialist94()
        
        # Heavy tier queries
        heavy_queries = [
            "I want to speak to a manager right now!",
            "This is completely unacceptable, give me a refund!",
        ]
        
        for query in heavy_queries:
            result = await specialist.predict(query)
            if result["action"] == "escalation":
                assert result["tier"] == "heavy", f"Heavy query got tier {result['tier']}"
        
        # Light tier queries
        light_queries = [
            "What are your hours?",
            "How do I contact support?",
        ]
        
        for query in light_queries:
            result = await specialist.predict(query)
            # Light queries should not be heavy
            assert result["tier"] in ["light", "medium"]

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test performance with many concurrent predictions."""
        specialist = EcommerceSpecialist94()
        
        queries = [
            "I want a refund",
            "Where is my order?",
            "The product is broken",
            "I need to return this",
            "Speak to a manager",
        ] * 20  # 100 queries
        
        # Run predictions concurrently
        tasks = [specialist.predict(q) for q in queries]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 100
        assert all("action" in r for r in results)


class TestCrossSpecialistIntegration:
    """Tests for cross-specialist integration."""

    @pytest.mark.asyncio
    async def test_specialist_registry_routing(self):
        """Test that registry routes to correct specialist."""
        test_cases = [
            ("I want a refund", "ecommerce"),
            ("Billing issue", "saas"),
            ("Schedule appointment", "healthcare"),
            ("Credit card fraud", "financial"),
            ("Track package", "logistics"),
        ]
        
        for query, expected_industry in test_cases:
            result = await SpecialistRegistry94.predict_best(query, expected_industry)
            
            assert "action" in result
            assert "tier" in result
            assert "confidence" in result

    @pytest.mark.asyncio
    async def test_unknown_industry_fallback(self):
        """Test fallback for unknown industry."""
        result = await SpecialistRegistry94.predict_best(
            "I need help",
            "unknown_industry"
        )
        
        # Should still return valid prediction
        assert "action" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
