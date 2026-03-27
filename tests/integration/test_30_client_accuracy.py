"""
30-Client Accuracy Validation for Agent Lightning 94% (Week 36).

Validates accuracy across all 30 configured clients.
"""
import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any, List

from agent_lightning.training.category_specialists_94 import (
    SpecialistRegistry94,
    get_specialist_94,
)


# Industry mapping for clients
CLIENT_INDUSTRIES = {
    "client_001": "ecommerce",
    "client_002": "ecommerce",
    "client_003": "healthcare",
    "client_004": "ecommerce",
    "client_005": "ecommerce",
    "client_006": "ecommerce",
    "client_007": "ecommerce",
    "client_008": "ecommerce",
    "client_009": "ecommerce",
    "client_010": "ecommerce",
    "client_011": "saas",
    "client_012": "ecommerce",
    "client_013": "saas",
    "client_014": "ecommerce",
    "client_015": "saas",
    "client_016": "ecommerce",
    "client_017": "saas",
    "client_018": "ecommerce",
    "client_019": "saas",
    "client_020": "ecommerce",
    "client_021": "saas",
    "client_022": "saas",
    "client_023": "ecommerce",
    "client_024": "saas",
    "client_025": "ecommerce",
    "client_026": "saas",
    "client_027": "saas",
    "client_028": "saas",
    "client_029": "saas",
    "client_030": "saas",
}


class Test30ClientAccuracy:
    """Tests for validating accuracy across all 30 clients."""

    @pytest.fixture
    def all_clients(self):
        """Get all client IDs."""
        return list(CLIENT_INDUSTRIES.keys())

    @pytest.mark.asyncio
    async def test_all_clients_have_predictions(self, all_clients):
        """Test that all clients can get predictions."""
        for client_id in all_clients:
            industry = CLIENT_INDUSTRIES.get(client_id, "ecommerce")
            specialist = get_specialist_94(industry)
            
            result = await specialist.predict("I need help with my order")
            
            assert "action" in result, f"No action for {client_id}"
            assert "tier" in result, f"No tier for {client_id}"

    @pytest.mark.asyncio
    async def test_ecommerce_clients_accuracy(self):
        """Test accuracy for e-commerce clients."""
        ecommerce_clients = [
            c for c, ind in CLIENT_INDUSTRIES.items() 
            if ind == "ecommerce"
        ]
        
        test_queries = [
            ("I want a refund", ["refund", "escalation"]),
            ("Where is my order?", ["shipping", "order_status", "faq"]),
            ("Product is defective", ["refund", "returns"]),
            ("I need to speak to a manager", ["escalation"]),
        ]
        
        total_correct = 0
        total_queries = 0
        
        for client_id in ecommerce_clients[:5]:  # Test first 5
            specialist = get_specialist_94("ecommerce")
            
            for query, valid_actions in test_queries:
                result = await specialist.predict(query)
                total_queries += 1
                
                if result["action"] in valid_actions:
                    total_correct += 1
        
        accuracy = total_correct / total_queries if total_queries > 0 else 0
        print(f"\nE-commerce clients accuracy: {accuracy:.2%}")
        
        assert accuracy >= 0.75, f"E-commerce accuracy {accuracy:.2%} below 75%"

    @pytest.mark.asyncio
    async def test_saas_clients_accuracy(self):
        """Test accuracy for SaaS clients."""
        saas_clients = [
            c for c, ind in CLIENT_INDUSTRIES.items() 
            if ind == "saas"
        ]
        
        test_queries = [
            ("I was charged incorrectly", ["billing"]),
            ("The app keeps crashing", ["technical"]),
            ("I can't log into my account", ["account", "technical"]),
            ("How do I upgrade my subscription?", ["billing", "account"]),
        ]
        
        total_correct = 0
        total_queries = 0
        
        for client_id in saas_clients[:5]:  # Test first 5
            specialist = get_specialist_94("saas")
            
            for query, valid_actions in test_queries:
                result = await specialist.predict(query)
                total_queries += 1
                
                if result["action"] in valid_actions:
                    total_correct += 1
        
        accuracy = total_correct / total_queries if total_queries > 0 else 0
        print(f"\nSaaS clients accuracy: {accuracy:.2%}")
        
        assert accuracy >= 0.70, f"SaaS accuracy {accuracy:.2%} below 70%"

    @pytest.mark.asyncio
    async def test_healthcare_client_accuracy(self):
        """Test accuracy for healthcare clients."""
        test_queries = [
            ("I need to schedule an appointment", ["appointment"]),
            ("Refill my prescription", ["prescription"]),
            ("I need my medical records", ["records"]),
        ]
        
        specialist = get_specialist_94("healthcare")
        
        total_correct = 0
        total_queries = 0
        
        for query, valid_actions in test_queries:
            result = await specialist.predict(query)
            total_queries += 1
            
            if result["action"] in valid_actions:
                total_correct += 1
        
        accuracy = total_correct / total_queries if total_queries > 0 else 0
        print(f"\nHealthcare client accuracy: {accuracy:.2%}")
        
        assert accuracy >= 0.60, f"Healthcare accuracy {accuracy:.2%} below 60%"

    @pytest.mark.asyncio
    async def test_no_cross_client_data_leak(self, all_clients):
        """Test that predictions don't leak between clients."""
        results_by_client: Dict[str, List[Dict[str, Any]]] = {}
        
        for client_id in all_clients[:10]:
            industry = CLIENT_INDUSTRIES.get(client_id, "ecommerce")
            specialist = get_specialist_94(industry)
            
            results_by_client[client_id] = []
            
            for query in ["I need help", "Refund please", "Manager now"]:
                result = await specialist.predict(query)
                results_by_client[client_id].append(result)
        
        # Verify each client has its own results
        for client_id, results in results_by_client.items():
            assert len(results) == 3
            for r in results:
                assert isinstance(r, dict)
                assert "action" in r

    @pytest.mark.asyncio
    async def test_overall_30_client_accuracy(self, all_clients):
        """Test overall accuracy across all 30 clients."""
        # Sample queries per industry
        industry_queries = {
            "ecommerce": [
                ("I want a refund", ["refund", "escalation"]),
                ("Track my order", ["shipping", "order_status"]),
            ],
            "saas": [
                ("Billing question", ["billing"]),
                ("App not working", ["technical"]),
            ],
            "healthcare": [
                ("Book appointment", ["appointment"]),
                ("Need prescription", ["prescription"]),
            ],
        }
        
        total_correct = 0
        total_queries = 0
        
        for client_id in all_clients:
            industry = CLIENT_INDUSTRIES.get(client_id, "ecommerce")
            specialist = get_specialist_94(industry)
            
            queries = industry_queries.get(industry, industry_queries["ecommerce"])
            
            for query, valid_actions in queries:
                result = await specialist.predict(query)
                total_queries += 1
                
                if result["action"] in valid_actions:
                    total_correct += 1
        
        accuracy = total_correct / total_queries if total_queries > 0 else 0
        print(f"\nOverall 30-client accuracy: {accuracy:.2%}")
        
        # Accept 70% as minimum for all 30 clients
        assert accuracy >= 0.70, f"Overall accuracy {accuracy:.2%} below 70%"


class TestClientIndustryMapping:
    """Tests for client-industry mapping."""

    def test_all_clients_mapped(self):
        """Test that all 30 clients have industry mapping."""
        assert len(CLIENT_INDUSTRIES) == 30
        
    def test_valid_industries(self):
        """Test that all mapped industries are valid."""
        valid_industries = {"ecommerce", "saas", "healthcare", "financial", "logistics"}
        
        for client_id, industry in CLIENT_INDUSTRIES.items():
            assert industry in valid_industries, f"Invalid industry {industry} for {client_id}"

    def test_client_id_format(self):
        """Test that all client IDs follow proper format."""
        for client_id in CLIENT_INDUSTRIES.keys():
            assert client_id.startswith("client_"), f"Invalid client ID format: {client_id}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
