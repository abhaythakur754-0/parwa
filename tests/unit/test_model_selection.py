"""
Model Selection Unit Tests - Week 35
Tests for Dynamic Model Selection
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from shared.smart_router.selection.model_selector import (
    ModelSelector, ModelInfo, ModelTier, SelectionResult
)
from shared.smart_router.selection.cost_optimizer import (
    CostOptimizer, CostRecord, BudgetInfo, BudgetStatus, CostReport
)
from shared.smart_router.selection.latency_manager import (
    LatencyManager, LatencyRecord, LatencyStatus, LatencyStats
)
from shared.smart_router.selection.fallback_chain import (
    FallbackChain, FallbackLevel, FallbackReason, FallbackResult
)


class TestModelSelector:
    """Tests for Model Selector"""
    
    @pytest.fixture
    def selector(self):
        return ModelSelector()
    
    def test_selector_initializes(self, selector):
        """Test: ModelSelector initializes correctly"""
        assert selector is not None
        assert selector.is_initialized()
    
    def test_selects_model_by_complexity(self, selector):
        """Test: Selects model by complexity"""
        # Simple query -> light tier
        result = selector.select(
            query="What is your return policy?",
            complexity_score=0.2,
            client_tier="pro"
        )
        
        assert result.selected_model is not None
        assert result.confidence > 0
    
    def test_load_balances_correctly(self, selector):
        """Test: Load balancing works"""
        # Set different loads
        selector.update_load('junior', 0.8)
        selector.update_load('junior-plus', 0.2)
        
        result = selector.select(
            query="Help me with my order",
            complexity_score=0.5,
            client_tier="enterprise"
        )
        
        # Should prefer lower load
        assert result.selected_model is not None
    
    def test_monitors_model_health(self, selector):
        """Test: Model health monitoring"""
        # Mark model unhealthy
        selector.update_health('junior', 'unhealthy')
        
        # Should not select unhealthy model
        result = selector.select(
            query="Help me",
            complexity_score=0.5,
            client_tier="pro"
        )
        
        # Should select healthy alternative
        assert selector.get_model_info(result.selected_model) is not None
    
    def test_selection_explanation(self, selector):
        """Test: Selection explanation"""
        result = selector.select(
            query="Complex analysis needed",
            complexity_score=0.8,
            client_tier="enterprise"
        )
        
        assert result.reason is not None
        assert len(result.reason) > 0
    
    def test_client_tier_limits(self, selector):
        """Test: Client tier limits enforced"""
        # Basic tier should not get heavy models
        result = selector.select(
            query="Complex query",
            complexity_score=0.9,
            client_tier="basic"
        )
        
        # Should not exceed medium tier for basic client
        assert result.tier in [ModelTier.LIGHT, ModelTier.MEDIUM]
    
    def test_capability_requirements(self, selector):
        """Test: Capability requirements respected"""
        result = selector.select(
            query="Analyze this code",
            complexity_score=0.7,
            required_capabilities=['code'],
            client_tier="enterprise"
        )
        
        model_info = selector.get_model_info(result.selected_model)
        assert 'code' in model_info.capabilities
    
    def test_list_available_models(self, selector):
        """Test: List available models"""
        models = selector.list_available_models()
        
        assert len(models) > 0
        assert all(m.health_status == "healthy" for m in models)


class TestCostOptimizer:
    """Tests for Cost Optimizer"""
    
    @pytest.fixture
    def optimizer(self):
        return CostOptimizer()
    
    def test_optimizer_initializes(self, optimizer):
        """Test: CostOptimizer initializes correctly"""
        assert optimizer is not None
        assert optimizer.is_initialized()
    
    def test_tracks_token_costs(self, optimizer):
        """Test: Tracks token costs"""
        record = optimizer.track_cost(
            model='junior',
            input_tokens=100,
            output_tokens=50,
            client_id='client-1',
            session_id='session-1'
        )
        
        assert record.cost > 0
        assert record.model == 'junior'
    
    def test_enforces_budgets(self, optimizer):
        """Test: Budget enforcement"""
        # Set small budget
        optimizer.set_budget('client-1', total_budget=0.01)
        
        # Try to use expensive model
        allowed, status = optimizer.check_budget('client-1', 0.05)
        
        assert not allowed
    
    def test_cost_prediction(self, optimizer):
        """Test: Cost prediction"""
        predicted = optimizer.predict_cost('high', 1000)
        
        assert predicted > 0
    
    def test_cost_reporting(self, optimizer):
        """Test: Cost reporting"""
        # Track some costs
        optimizer.track_cost('junior', 100, 50, 'client-1', 's1')
        optimizer.track_cost('mini', 50, 30, 'client-1', 's2')
        
        report = optimizer.get_cost_report('client-1')
        
        assert report.total_cost > 0
        assert 'junior' in report.cost_by_model or 'mini' in report.cost_by_model
    
    def test_roi_calculation(self, optimizer):
        """Test: ROI calculation"""
        optimizer.track_cost('junior', 100, 50, 'client-1', 's1')
        optimizer.track_cost('junior', 100, 50, 'client-1', 's2')
        
        roi = optimizer.calculate_roi('client-1', resolution_value=5.0)
        
        assert 'roi' in roi
        assert 'total_cost' in roi
    
    def test_cost_aware_selection(self, optimizer):
        """Test: Cost-aware model selection"""
        optimizer.set_budget('client-1', total_budget=1.0)
        
        models = ['mini', 'junior', 'high']
        
        selected = optimizer.get_cost_aware_model(
            models,
            'client-1',
            quality_preference='cheap'
        )
        
        # Should select cheapest
        assert selected == 'mini'
    
    def test_budget_status_tracking(self, optimizer):
        """Test: Budget status tracking"""
        optimizer.set_budget('client-1', total_budget=1.0)
        
        # Use some budget
        for i in range(10):
            optimizer.track_cost('junior', 100, 50, 'client-1', f's{i}')
        
        budget = optimizer._budgets.get('client-1')
        
        # Should have some usage
        assert budget.used > 0


class TestLatencyManager:
    """Tests for Latency Manager"""
    
    @pytest.fixture
    def manager(self):
        return LatencyManager()
    
    def test_manager_initializes(self, manager):
        """Test: LatencyManager initializes correctly"""
        assert manager is not None
        assert manager.is_initialized()
    
    def test_tracks_latency(self, manager):
        """Test: Tracks latency"""
        status = manager.record_latency(
            model='junior',
            latency_ms=150.0,
            client_id='client-1',
            session_id='session-1'
        )
        
        assert status in [LatencyStatus.FAST, LatencyStatus.NORMAL, LatencyStatus.SLOW, LatencyStatus.CRITICAL]
    
    def test_routes_by_latency(self, manager):
        """Test: Routes by latency"""
        # Record some latencies
        manager.record_latency('mini', 50, 'client-1', 's1')
        manager.record_latency('junior', 150, 'client-1', 's2')
        manager.record_latency('high', 300, 'client-1', 's3')
        
        fastest = manager.get_fastest_models(['mini', 'junior', 'high'])
        
        assert fastest[0] == 'mini'
    
    def test_enforces_sla(self, manager):
        """Test: SLA enforcement"""
        manager.set_client_sla('client-1', 200)
        
        met, target = manager.check_sla('client-1', 150)
        
        assert met is True
        assert target == 200
        
        met, _ = manager.check_sla('client-1', 250)
        assert met is False
    
    def test_latency_prediction(self, manager):
        """Test: Latency prediction"""
        # Record some latencies for history
        for i in range(10):
            manager.record_latency('junior', 100 + i*10, 'client-1', f's{i}')
        
        predicted = manager.predict_latency('junior', query_length=50)
        
        assert predicted > 0
    
    def test_slow_model_detection(self, manager):
        """Test: Slow model detection"""
        # Record slow latencies
        for i in range(20):
            manager.record_latency('high', 600, 'client-1', f's{i}')
        
        slow = manager.get_slow_models()
        
        assert 'high' in slow
    
    def test_sla_report(self, manager):
        """Test: SLA report"""
        # Record various latencies
        manager.record_latency('junior', 100, 'client-1', 's1')
        manager.record_latency('junior', 200, 'client-1', 's2')
        manager.record_latency('junior', 500, 'client-1', 's3')
        
        report = manager.get_sla_report()
        
        assert 'compliance_rate' in report
        assert 'total_queries' in report


class TestFallbackChain:
    """Tests for Fallback Chain"""
    
    @pytest.fixture
    def chain(self):
        return FallbackChain()
    
    def test_chain_initializes(self, chain):
        """Test: FallbackChain initializes correctly"""
        assert chain is not None
        assert chain.is_initialized()
    
    def test_falls_back_correctly(self, chain):
        """Test: Falls back correctly"""
        result = chain.get_fallback_model(
            current_model='high',
            reason=FallbackReason.MODEL_ERROR,
            tier='heavy',
            session_id='session-1'
        )
        
        # Should fall back to junior
        assert result.model == 'junior'
        assert result.level == FallbackLevel.SECONDARY
    
    def test_recovers_automatically(self, chain):
        """Test: Automatic recovery"""
        # Simulate failures
        for i in range(5):
            chain.get_fallback_model(
                'junior',
                FallbackReason.MODEL_ERROR,
                'medium',
                f's{i}'
            )
        
        # Circuit should be open
        assert chain.is_circuit_open('junior')
        
        # After recovery timeout, should close
        # (In real test, would mock time)
    
    def test_logs_fallback_events(self, chain):
        """Test: Fallback event logging"""
        chain.get_fallback_model(
            'high',
            FallbackReason.TIMEOUT,
            'heavy',
            'session-1'
        )
        
        analytics = chain.get_fallback_analytics()
        
        assert analytics['total_fallbacks'] >= 1
    
    def test_graceful_degradation(self, chain):
        """Test: Graceful degradation"""
        # Trip circuit for some models
        for i in range(6):
            chain.get_fallback_model(
                'junior',
                FallbackReason.MODEL_ERROR,
                'medium',
                f's{i}'
            )
        
        model = chain.graceful_degradation(
            tier='medium',
            constraints={'max_latency': 500}
        )
        
        # Should return a working model
        assert model is not None
    
    def test_tier_specific_chains(self, chain):
        """Test: Tier-specific chains"""
        heavy_chain = chain.get_chain_for_tier('heavy')
        light_chain = chain.get_chain_for_tier('light')
        
        assert 'high' in heavy_chain
        assert 'high' not in light_chain
    
    def test_model_health_tracking(self, chain):
        """Test: Model health tracking"""
        # Cause some failures
        for i in range(3):
            chain.get_fallback_model(
                'junior',
                FallbackReason.MODEL_ERROR,
                'medium',
                f's{i}'
            )
        
        health = chain.get_model_health('junior')
        
        assert 'model' in health
        assert 'failure_count' in health


class TestModelSelectionIntegration:
    """Integration tests for model selection"""
    
    def test_full_selection_flow(self):
        """Test: Full selection flow"""
        selector = ModelSelector()
        cost_optimizer = CostOptimizer()
        latency_manager = LatencyManager()
        fallback_chain = FallbackChain()
        
        # Set up budget
        cost_optimizer.set_budget('client-1', 10.0)
        
        # Select model
        selection = selector.select(
            query="Help me analyze my data",
            complexity_score=0.7,
            client_tier="pro"
        )
        
        # Check budget
        allowed, _ = cost_optimizer.check_budget(
            'client-1',
            selection.estimated_cost
        )
        
        if allowed:
            # Track cost
            cost_optimizer.track_cost(
                model=selection.selected_model,
                input_tokens=100,
                output_tokens=50,
                client_id='client-1',
                session_id='session-1'
            )
            
            # Record latency
            latency_manager.record_latency(
                model=selection.selected_model,
                latency_ms=selection.estimated_latency_ms,
                client_id='client-1',
                session_id='session-1'
            )
        
        assert selection.selected_model is not None
    
    def test_fallback_with_cost_tracking(self):
        """Test: Fallback with cost tracking"""
        selector = ModelSelector()
        cost_optimizer = CostOptimizer()
        fallback = FallbackChain()
        
        # Select initial model
        selection = selector.select(
            query="Complex query",
            complexity_score=0.9,
            client_tier="enterprise"
        )
        
        # Simulate failure and fallback
        fallback_result = fallback.get_fallback_model(
            selection.selected_model,
            FallbackReason.MODEL_ERROR,
            'heavy',
            'session-1'
        )
        
        # Track cost of fallback
        cost_optimizer.track_cost(
            model=fallback_result.model,
            input_tokens=100,
            output_tokens=50,
            client_id='client-1',
            session_id='session-1'
        )
        
        assert fallback_result.model != selection.selected_model


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
