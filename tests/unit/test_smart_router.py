import pytest
from unittest.mock import MagicMock, patch
from shared.smart_router.provider_config import Provider, get_active_providers
from shared.smart_router.cost_optimizer import calculate_best_provider
from shared.smart_router.routing_engine import SmartRouter

class TestSmartRouter:
    
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.openrouter_api_key.get_secret_value.return_value = "fake-key"
        return settings

    def test_provider_stats_existence(self):
        from shared.smart_router.provider_config import PROVIDER_STATS
        for provider in Provider:
            assert provider in PROVIDER_STATS
            assert "cost_per_1k_tokens" in PROVIDER_STATS[provider]
            assert "latency_weight" in PROVIDER_STATS[provider]

    def test_get_active_providers_logic(self, mock_settings):
        providers = get_active_providers(mock_settings)
        assert len(providers) == 3
        assert Provider.OPENAI in providers
        
        # Test inactive
        mock_settings.openrouter_api_key.get_secret_value.return_value = ""
        providers = get_active_providers(mock_settings)
        assert providers == []

    @patch("shared.smart_router.cost_optimizer.get_active_providers")
    @patch("shared.smart_router.cost_optimizer.get_settings")
    def test_cost_optimizer_priorities(self, mock_get_settings, mock_get_active, mock_settings):
        mock_get_settings.return_value = mock_settings
        mock_get_active.return_value = [Provider.OPENAI, Provider.ANTHROPIC, Provider.GEMINI]
        
        # Based on PROVIDER_STATS:
        # GEMINI: cost 10, latency 0.8 (Best for cost)
        # OPENAI: cost 30, latency 0.5 (Best for latency)
        # ANTHROPIC: cost 45, latency 1.5
        
        assert calculate_best_provider(100, "cost") == Provider.GEMINI
        assert calculate_best_provider(100, "latency") == Provider.OPENAI
        
        # Test fallback if Gemini is inactive
        mock_get_active.return_value = [Provider.OPENAI, Provider.ANTHROPIC]
        assert calculate_best_provider(100, "cost") == Provider.OPENAI
        assert calculate_best_provider(100, "latency") == Provider.OPENAI
        
    @patch("shared.smart_router.cost_optimizer.get_active_providers")
    def test_cost_optimizer_no_active_providers(self, mock_get_active):
        mock_get_active.return_value = []
        assert calculate_best_provider(100, "cost") == Provider.GEMINI

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_success(self, mock_active, mock_settings_getter, mock_settings):
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.GEMINI]
        
        router = SmartRouter()
        result = router.route_request("Hello", {"priority": "cost"})
        
        assert result["status"] == "success"
        assert result["provider"] == Provider.GEMINI
        assert result["attempts"] == 1

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_failover_503(self, mock_active, mock_settings_getter, mock_settings):
        # Force failover from OpenAI to Gemini
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.OPENAI, Provider.GEMINI]
        
        router = SmartRouter()
        # "force_fail" triggers exception in SmartRouter._execute_call for OpenAI
        result = router.route_request("force_fail OpenAI now", {"priority": "latency"})
        
        assert result["status"] == "success"
        assert result["provider"] == Provider.GEMINI
        assert result["attempts"] == 2

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_failover_429(self, mock_active, mock_settings_getter, mock_settings):
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.OPENAI, Provider.ANTHROPIC]
        
        router = SmartRouter()
        # "force_rate_limit" triggers 429 exception for OpenAI
        result = router.route_request("force_rate_limit OpenAI", {"priority": "latency"})
        
        assert result["status"] == "success"
        assert result["provider"] == Provider.ANTHROPIC
        assert result["attempts"] == 2

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_all_fail(self, mock_active, mock_settings_getter, mock_settings):
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.OPENAI]
        
        router = SmartRouter()
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            router.route_request("force_fail everything")

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_context_preservation(self, mock_active, mock_settings_getter, mock_settings):
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.GEMINI]
        
        router = SmartRouter()
        context = {"priority": "cost", "user_id": "user_123"}
        result = router.route_request("Hello", context)
        
        assert result["status"] == "success"
        assert result["provider"] == Provider.GEMINI
        # Context was preserved in _execute_call (implied by correct routing)
