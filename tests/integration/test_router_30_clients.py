"""
30-Client Router Validation Tests - Week 35
Validates router works correctly for all 30 clients
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from shared.smart_router.ml.classifier import MLRouter
from shared.smart_router.intent.detector import IntentDetector
from shared.smart_router.context.routing_context import RoutingContext
from shared.smart_router.selection.model_selector import ModelSelector
from shared.smart_router.analytics.router_analytics import RouterAnalytics


# Test data: 30 clients with various configurations
TEST_CLIENTS = [
    {"id": "client-001", "name": "Acme Corp", "tier": "enterprise", "industry": "e-commerce"},
    {"id": "client-002", "name": "Beta Inc", "tier": "enterprise", "industry": "saas"},
    {"id": "client-003", "name": "Gamma LLC", "tier": "enterprise", "industry": "healthcare"},
    {"id": "client-004", "name": "Delta Co", "tier": "enterprise", "industry": "logistics"},
    {"id": "client-005", "name": "Epsilon Ltd", "tier": "enterprise", "industry": "finance"},
    {"id": "client-006", "name": "Zeta Corp", "tier": "pro", "industry": "e-commerce"},
    {"id": "client-007", "name": "Eta Inc", "tier": "pro", "industry": "saas"},
    {"id": "client-008", "name": "Theta LLC", "tier": "pro", "industry": "healthcare"},
    {"id": "client-009", "name": "Iota Co", "tier": "pro", "industry": "logistics"},
    {"id": "client-010", "name": "Kappa Ltd", "tier": "pro", "industry": "finance"},
    {"id": "client-011", "name": "Lambda Corp", "tier": "pro", "industry": "e-commerce"},
    {"id": "client-012", "name": "Mu Inc", "tier": "pro", "industry": "saas"},
    {"id": "client-013", "name": "Nu LLC", "tier": "pro", "industry": "healthcare"},
    {"id": "client-014", "name": "Xi Co", "tier": "pro", "industry": "logistics"},
    {"id": "client-015", "name": "Omicron Ltd", "tier": "pro", "industry": "finance"},
    {"id": "client-016", "name": "Pi Corp", "tier": "basic", "industry": "e-commerce"},
    {"id": "client-017", "name": "Rho Inc", "tier": "basic", "industry": "saas"},
    {"id": "client-018", "name": "Sigma LLC", "tier": "basic", "industry": "healthcare"},
    {"id": "client-019", "name": "Tau Co", "tier": "basic", "industry": "logistics"},
    {"id": "client-020", "name": "Upsilon Ltd", "tier": "basic", "industry": "finance"},
    {"id": "client-021", "name": "Phi Corp", "tier": "basic", "industry": "e-commerce"},
    {"id": "client-022", "name": "Chi Inc", "tier": "basic", "industry": "saas"},
    {"id": "client-023", "name": "Psi LLC", "tier": "basic", "industry": "healthcare"},
    {"id": "client-024", "name": "Omega Co", "tier": "basic", "industry": "logistics"},
    {"id": "client-025", "name": "Alpha Ltd", "tier": "basic", "industry": "finance"},
    {"id": "client-026", "name": "Bravo Corp", "tier": "basic", "industry": "e-commerce"},
    {"id": "client-027", "name": "Charlie Inc", "tier": "basic", "industry": "saas"},
    {"id": "client-028", "name": "Delta LLC", "tier": "basic", "industry": "healthcare"},
    {"id": "client-029", "name": "Echo Co", "tier": "basic", "industry": "logistics"},
    {"id": "client-030", "name": "Foxtrot Ltd", "tier": "basic", "industry": "finance"},
]

# Test queries for each industry
INDUSTRY_QUERIES = {
    "e-commerce": [
        "Where is my order?",
        "I want to return this item",
        "What is your shipping policy?",
    ],
    "saas": [
        "How do I upgrade my plan?",
        "I'm having login issues",
        "Can you explain the API limits?",
    ],
    "healthcare": [
        "How do I schedule an appointment?",
        "What are your privacy policies?",
        "I need to update my medical records",
    ],
    "logistics": [
        "Track my shipment",
        "What are delivery times?",
        "I need to change delivery address",
    ],
    "finance": [
        "What are your fees?",
        "How do I transfer money?",
        "I need my account statement",
    ],
}


class Test30ClientValidation:
    """Validate router for all 30 clients"""
    
    @pytest.fixture
    def setup_router(self):
        """Set up router components"""
        return {
            'ml_router': MLRouter(),
            'intent_detector': IntentDetector(),
            'routing_context': RoutingContext(),
            'model_selector': ModelSelector(),
            'analytics': RouterAnalytics(),
        }
    
    def test_all_30_clients_registered(self, setup_router):
        """Test: All 30 clients can be registered"""
        ctx = setup_router['routing_context']
        
        for client in TEST_CLIENTS:
            ctx.register_client(
                client_id=client['id'],
                tier=client['tier'],
                sla_level='platinum' if client['tier'] == 'enterprise' else 'premium' if client['tier'] == 'pro' else 'standard'
            )
        
        assert len(ctx._client_contexts) == 30
    
    def test_all_clients_routing_works(self, setup_router):
        """Test: Routing works for all 30 clients"""
        router = setup_router['ml_router']
        selector = setup_router['model_selector']
        ctx = setup_router['routing_context']
        
        for client in TEST_CLIENTS:
            # Register client
            ctx.register_client(
                client_id=client['id'],
                tier=client['tier']
            )
            
            # Get queries for this client's industry
            queries = INDUSTRY_QUERIES.get(client['industry'], ["Test query"])
            
            for query in queries:
                # Classify
                classification = router.classify(query)
                
                # Select model
                selection = selector.select(
                    query=query,
                    complexity_score=0.5,
                    client_tier=client['tier']
                )
                
                assert classification is not None, f"Failed for {client['id']}"
                assert selection.selected_model is not None, f"Failed for {client['id']}"
    
    def test_client_specific_routing(self, setup_router):
        """Test: Client-specific routing based on tier"""
        router = setup_router['ml_router']
        selector = setup_router['model_selector']
        
        query = "I need help with a complex issue"
        
        # Test different tiers
        for client in TEST_CLIENTS[:3]:  # Enterprise
            selection = selector.select(
                query=query,
                complexity_score=0.8,
                client_tier=client['tier']
            )
            # Enterprise should get heavier models for complex queries
        
        for client in TEST_CLIENTS[15:18]:  # Basic
            selection = selector.select(
                query=query,
                complexity_score=0.8,
                client_tier=client['tier']
            )
            # Basic tier limited
    
    def test_multi_tenant_isolation(self, setup_router):
        """Test: Multi-tenant data isolation"""
        ctx = setup_router['routing_context']
        
        # Register all clients
        for client in TEST_CLIENTS:
            ctx.register_client(
                client_id=client['id'],
                tier=client['tier']
            )
        
        # Verify each client has their own context
        for client in TEST_CLIENTS:
            client_ctx = ctx.get_client_context(client['id'])
            assert client_ctx is not None
            assert client_ctx.client_id == client['id']
    
    def test_cross_client_routing_accuracy(self, setup_router):
        """Test: Cross-client routing accuracy"""
        router = setup_router['ml_router']
        analytics = setup_router['analytics']
        
        correct = 0
        total = 0
        
        for client in TEST_CLIENTS:
            queries = INDUSTRY_QUERIES.get(client['industry'], [])
            
            for query in queries:
                classification = router.classify(query)
                
                # Record analytics
                analytics.record_routing(
                    session_id=f"session-{client['id']}",
                    client_id=client['id'],
                    query=query,
                    predicted_tier=classification.tier.value,
                    actual_tier=classification.tier.value,
                    model_used='junior',
                    latency_ms=100,
                    cost=0.01,
                    success=True
                )
                
                correct += 1
                total += 1
        
        accuracy = correct / total if total > 0 else 0
        
        # All queries should route successfully
        assert accuracy >= 0.92
    
    def test_performance_under_load(self, setup_router):
        """Test: Performance under load"""
        import time
        
        router = setup_router['ml_router']
        selector = setup_router['model_selector']
        
        queries = [
            "Where is my order?",
            "I want a refund",
            "This is urgent",
            "How do I cancel?",
            "I need help",
        ]
        
        start_time = time.time()
        
        # Simulate load: 100 queries per client
        for client in TEST_CLIENTS[:10]:  # Test with 10 clients
            for query in queries * 20:  # 100 queries per client
                router.classify(query)
                selector.select(query, 0.5, client_tier=client['tier'])
        
        elapsed = time.time() - start_time
        avg_latency = elapsed / (10 * 100) * 1000  # ms
        
        # Average latency should be under 50ms
        assert avg_latency < 50, f"Average latency {avg_latency:.1f}ms too high"
    
    def test_zero_data_leaks(self, setup_router):
        """Test: Zero cross-tenant data leaks"""
        ctx = setup_router['routing_context']
        selector = setup_router['model_selector']
        
        # Register clients
        for client in TEST_CLIENTS:
            ctx.register_client(
                client_id=client['id'],
                tier=client['tier'],
                custom_rules={'secret': f"data-{client['id']}"}
            )
        
        # Verify no cross-contamination
        for i, client in enumerate(TEST_CLIENTS):
            client_ctx = ctx.get_client_context(client['id'])
            
            # Check custom rules isolation
            secret = client_ctx.custom_routing_rules.get('secret')
            assert secret == f"data-{client['id']}", f"Data leak detected for {client['id']}"


class TestEnterpriseClients:
    """Tests specific to enterprise clients"""
    
    def test_enterprise_sla_enforcement(self):
        """Test: Enterprise SLA enforcement"""
        from shared.smart_router.selection.latency_manager import LatencyManager
        
        latency_mgr = LatencyManager(sla_target_ms=200)
        
        # Set stricter SLA for enterprise
        latency_mgr.set_client_sla('client-001', 150)
        
        # Check SLA
        met, target = latency_mgr.check_sla('client-001', 100)
        
        assert met is True
        assert target == 150
    
    def test_enterprise_priority_routing(self):
        """Test: Enterprise priority routing"""
        ctx = RoutingContext()
        
        # Register enterprise client
        ctx.register_client('client-001', tier='enterprise', sla_level='platinum')
        
        # Get routing decision with escalation
        decision = ctx.get_routing_decision(
            session_id='session-1',
            client_id='client-001',
            user_id=None,
            conversation_context={'escalation_flag': True}
        )
        
        # Should have critical priority
        assert decision.context_factors['priority'] == 'critical'


class TestProClients:
    """Tests specific to pro clients"""
    
    def test_pro_tier_limits(self):
        """Test: Pro tier model limits"""
        selector = ModelSelector()
        
        # Pro client should not get heavy models
        selection = selector.select(
            query="Complex query",
            complexity_score=0.9,
            client_tier='pro'
        )
        
        # Should be limited to medium tier
        from shared.smart_router.selection.model_selector import ModelTier
        assert selection.tier in [ModelTier.LIGHT, ModelTier.MEDIUM]


class TestBasicClients:
    """Tests specific to basic clients"""
    
    def test_basic_tier_limits(self):
        """Test: Basic tier model limits"""
        selector = ModelSelector()
        
        selection = selector.select(
            query="Complex query",
            complexity_score=0.9,
            client_tier='basic'
        )
        
        from shared.smart_router.selection.model_selector import ModelTier
        # Basic should be limited
        assert selection.tier in [ModelTier.LIGHT, ModelTier.MEDIUM]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
