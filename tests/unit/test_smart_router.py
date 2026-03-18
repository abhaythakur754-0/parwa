"""
Unit tests for Smart Router components.

Tests for:
- TierConfig
- FailoverManager
- ComplexityScorer
- SmartRouter
"""
import os
import pytest
from unittest.mock import MagicMock, patch

# Set test environment variables before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.smart_router.provider_config import Provider, get_active_providers
from shared.smart_router.cost_optimizer import calculate_best_provider
from shared.smart_router.routing_engine import SmartRouter as LegacySmartRouter


class TestTierConfig:
    """Tests for Tier Config."""

    def test_ai_tier_enum(self):
        """Test AITier enum values."""
        from shared.smart_router.tier_config import AITier

        assert AITier.LIGHT.value == "light"
        assert AITier.MEDIUM.value == "medium"
        assert AITier.HEAVY.value == "heavy"

    def test_get_model(self):
        """Test getting model for tier."""
        from shared.smart_router.tier_config import TierConfig, AITier

        config = TierConfig()
        model = config.get_model(AITier.LIGHT)

        assert isinstance(model, str)
        assert len(model) > 0

    def test_get_model_different_providers(self):
        """Test getting model for different providers."""
        from shared.smart_router.tier_config import TierConfig, AITier

        google_config = TierConfig(provider="google")
        google_model = google_config.get_model(AITier.LIGHT)

        cerebras_config = TierConfig(provider="cerebras")
        cerebras_model = cerebras_config.get_model(AITier.LIGHT)

        # Different providers should have different models
        assert google_model != cerebras_model

    def test_get_cost(self):
        """Test getting tier cost."""
        from shared.smart_router.tier_config import TierConfig, AITier

        config = TierConfig()
        light_cost = config.get_cost(AITier.LIGHT)
        heavy_cost = config.get_cost(AITier.HEAVY)

        assert light_cost > 0
        assert heavy_cost > 0
        assert heavy_cost > light_cost  # Heavy should cost more

    def test_get_token_limit(self):
        """Test getting token limits."""
        from shared.smart_router.tier_config import TierConfig, AITier

        config = TierConfig()
        light_limit = config.get_token_limit(AITier.LIGHT)
        heavy_limit = config.get_token_limit(AITier.HEAVY)

        assert light_limit > 0
        assert heavy_limit > light_limit

    def test_get_tier_config(self):
        """Test getting full tier configuration."""
        from shared.smart_router.tier_config import TierConfig, AITier

        config = TierConfig()
        full_config = config.get_tier_config(AITier.MEDIUM)

        assert "tier" in full_config
        assert "provider" in full_config
        assert "model" in full_config
        assert "cost_per_1m_tokens" in full_config
        assert "token_limit" in full_config

    def test_validate_tier_id(self):
        """Test tier ID validation."""
        from shared.smart_router.tier_config import TierConfig

        config = TierConfig()

        assert config.validate_tier_id("light") is True
        assert config.validate_tier_id("medium") is True
        assert config.validate_tier_id("heavy") is True
        assert config.validate_tier_id("invalid") is False
        assert config.validate_tier_id("LIGHT") is False  # Case sensitive


class TestFailoverManager:
    """Tests for Failover Manager."""

    @patch("shared.smart_router.failover.get_settings")
    def test_get_provider(self, mock_get_settings):
        """Test getting provider."""
        from shared.smart_router.failover import FailoverManager

        mock_settings = MagicMock()
        mock_settings.llm_primary_provider = "google"
        mock_settings.llm_fallback_provider = "groq"
        mock_get_settings.return_value = mock_settings

        manager = FailoverManager()
        provider = manager.get_provider()

        assert provider is not None
        assert isinstance(provider, str)

    @patch("shared.smart_router.failover.get_settings")
    def test_record_success(self, mock_get_settings):
        """Test recording success."""
        from shared.smart_router.failover import FailoverManager, ProviderStatus

        mock_settings = MagicMock()
        mock_settings.llm_primary_provider = "google"
        mock_settings.llm_fallback_provider = "groq"
        mock_get_settings.return_value = mock_settings

        manager = FailoverManager()
        manager.record_success("google")

        status = manager.get_status()
        assert status["primary"]["status"] == ProviderStatus.HEALTHY.value

    @patch("shared.smart_router.failover.get_settings")
    def test_record_error_triggers_degraded(self, mock_get_settings):
        """Test that error recording triggers degraded status."""
        from shared.smart_router.failover import FailoverManager, ProviderStatus

        mock_settings = MagicMock()
        mock_settings.llm_primary_provider = "google"
        mock_settings.llm_fallback_provider = "groq"
        mock_get_settings.return_value = mock_settings

        manager = FailoverManager()

        # Record a single error
        manager.record_error("google", "test_error")

        status = manager.get_status()
        assert status["primary"]["status"] == ProviderStatus.DEGRADED.value

    @patch("shared.smart_router.failover.get_settings")
    def test_record_error_triggers_unhealthy(self, mock_get_settings):
        """Test that errors up to threshold trigger unhealthy status."""
        from shared.smart_router.failover import FailoverManager, ProviderStatus

        mock_settings = MagicMock()
        mock_settings.llm_primary_provider = "google"
        mock_settings.llm_fallback_provider = "groq"
        mock_get_settings.return_value = mock_settings

        manager = FailoverManager()

        # Record errors up to threshold
        for i in range(manager.ERROR_THRESHOLD):
            manager.record_error("google", "test_error")

        status = manager.get_status()
        assert status["primary"]["status"] == ProviderStatus.UNHEALTHY.value

    @patch("shared.smart_router.failover.get_settings")
    def test_rate_limit_recording(self, mock_get_settings):
        """Test rate limit recording."""
        from shared.smart_router.failover import FailoverManager, ProviderStatus

        mock_settings = MagicMock()
        mock_settings.llm_primary_provider = "google"
        mock_settings.llm_fallback_provider = "groq"
        mock_get_settings.return_value = mock_settings

        manager = FailoverManager()
        manager.record_rate_limit("google")

        status = manager.get_status()
        assert status["primary"]["status"] == ProviderStatus.DEGRADED.value

    @patch("shared.smart_router.failover.get_settings")
    def test_reset_provider(self, mock_get_settings):
        """Test resetting provider status."""
        from shared.smart_router.failover import FailoverManager, ProviderStatus

        mock_settings = MagicMock()
        mock_settings.llm_primary_provider = "google"
        mock_settings.llm_fallback_provider = "groq"
        mock_get_settings.return_value = mock_settings

        manager = FailoverManager()

        # Record errors to make unhealthy
        for i in range(manager.ERROR_THRESHOLD):
            manager.record_error("google", "test_error")

        # Reset
        manager.reset_provider("google")

        status = manager.get_status()
        assert status["primary"]["status"] == ProviderStatus.HEALTHY.value


class TestComplexityScorer:
    """Tests for Complexity Scorer."""

    def test_simple_query_score(self):
        """Test simple query scores 0-2."""
        from shared.smart_router.complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()
        score = scorer.score("What are your hours?")

        assert 0 <= score <= 2

    def test_medium_query_score(self):
        """Test medium query scores 3-6."""
        from shared.smart_router.complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()
        score = scorer.score("I have a problem with my order and it's not working correctly")

        assert 3 <= score <= 6

    def test_complex_query_score(self):
        """Test complex query scores 7+."""
        from shared.smart_router.complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()
        score = scorer.score("I want a refund and I need to speak to a manager about this terrible issue")

        assert score >= 7

    def test_escalation_detection(self):
        """Test escalation auto-scores 10."""
        from shared.smart_router.complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()
        score = scorer.score("I need to speak to a human agent right now!")

        assert score == 10

    def test_empty_query(self):
        """Test empty query returns 0."""
        from shared.smart_router.complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()
        score = scorer.score("")

        assert score == 0

    def test_get_tier_for_score(self):
        """Test tier mapping for scores."""
        from shared.smart_router.complexity_scorer import ComplexityScorer, AITier

        scorer = ComplexityScorer()

        assert scorer.get_tier_for_score(0) == AITier.LIGHT
        assert scorer.get_tier_for_score(1) == AITier.LIGHT
        assert scorer.get_tier_for_score(2) == AITier.LIGHT
        assert scorer.get_tier_for_score(3) == AITier.MEDIUM
        assert scorer.get_tier_for_score(5) == AITier.MEDIUM
        assert scorer.get_tier_for_score(6) == AITier.MEDIUM
        assert scorer.get_tier_for_score(7) == AITier.HEAVY
        assert scorer.get_tier_for_score(9) == AITier.HEAVY
        assert scorer.get_tier_for_score(10) == AITier.HEAVY

    def test_analyze(self):
        """Test full analysis."""
        from shared.smart_router.complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()
        analysis = scorer.analyze("I need a refund for my order")

        assert "query" in analysis
        assert "complexity_score" in analysis
        assert "recommended_tier" in analysis
        assert "word_count" in analysis
        assert "has_escalation_indicators" in analysis

    def test_long_query_adjustment(self):
        """Test that long queries get higher scores."""
        from shared.smart_router.complexity_scorer import ComplexityScorer

        scorer = ComplexityScorer()

        short_score = scorer.score("What are your hours?")
        long_query = "What are your hours? " * 20  # Make it long
        long_score = scorer.score(long_query)

        # Long query should have higher or equal score
        assert long_score >= short_score


class TestSmartRouter:
    """Tests for the new Smart Router."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.openrouter_api_key.get_secret_value.return_value = "fake-key"
        settings.llm_primary_provider = "google"
        settings.llm_fallback_provider = "groq"
        return settings

    @patch("shared.smart_router.router.get_settings")
    def test_route_basic(self, mock_get_settings, mock_settings):
        """Test basic routing."""
        from shared.smart_router.router import SmartRouter

        mock_get_settings.return_value = mock_settings

        router = SmartRouter()
        tier, metadata = router.route("What are your hours?")

        assert tier is not None
        assert "complexity_score" in metadata
        assert "selected_tier" in metadata
        assert "provider" in metadata

    @patch("shared.smart_router.router.get_settings")
    def test_route_complex_query(self, mock_get_settings, mock_settings):
        """Test routing complex query to heavy tier."""
        from shared.smart_router.router import SmartRouter, AITier

        mock_get_settings.return_value = mock_settings

        router = SmartRouter()
        tier, metadata = router.route("I want to speak to a human agent about my refund!")

        assert tier == AITier.HEAVY

    @patch("shared.smart_router.router.get_settings")
    def test_route_simple_query(self, mock_get_settings, mock_settings):
        """Test routing simple query to light tier."""
        from shared.smart_router.router import SmartRouter, AITier

        mock_get_settings.return_value = mock_settings

        router = SmartRouter()
        tier, metadata = router.route("What is your price?")

        assert tier == AITier.LIGHT

    @patch("shared.smart_router.router.get_settings")
    def test_budget_downgrade(self, mock_get_settings, mock_settings):
        """Test budget-based downgrade."""
        from shared.smart_router.router import SmartRouter, AITier

        mock_get_settings.return_value = mock_settings

        router = SmartRouter()

        # Complex query but critical budget
        tier, metadata = router.route(
            "I want a refund for my terrible order!",
            budget_remaining=0.50
        )

        assert tier == AITier.LIGHT
        assert metadata.get("budget_downgrade") is True

    @patch("shared.smart_router.router.get_settings")
    def test_estimate_cost(self, mock_get_settings, mock_settings):
        """Test cost estimation."""
        from shared.smart_router.router import SmartRouter

        mock_get_settings.return_value = mock_settings

        router = SmartRouter()
        cost = router.estimate_cost("What are your hours?")

        assert cost >= 0
        assert isinstance(cost, float)

    @patch("shared.smart_router.router.get_settings")
    def test_record_success_error(self, mock_get_settings, mock_settings):
        """Test recording success and error."""
        from shared.smart_router.router import SmartRouter

        mock_get_settings.return_value = mock_settings

        router = SmartRouter()

        # Should not raise
        router.record_success("google")
        router.record_error("google", "test_error")

    @patch("shared.smart_router.router.get_settings")
    def test_get_routing_stats(self, mock_get_settings, mock_settings):
        """Test getting routing stats."""
        from shared.smart_router.router import SmartRouter

        mock_get_settings.return_value = mock_settings

        router = SmartRouter()
        stats = router.get_routing_stats()

        assert "provider_status" in stats


class TestLegacySmartRouter:
    """Tests for legacy Smart Router (routing_engine.py)."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.openrouter_api_key.get_secret_value.return_value = "fake-key"
        return settings

    def test_provider_stats_existence(self):
        """Test provider stats exist for all providers."""
        from shared.smart_router.provider_config import PROVIDER_STATS

        for provider in Provider:
            assert provider in PROVIDER_STATS
            assert "cost_per_1k_tokens" in PROVIDER_STATS[provider]
            assert "latency_weight" in PROVIDER_STATS[provider]

    def test_get_active_providers_logic(self, mock_settings):
        """Test getting active providers."""
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
        """Test cost optimizer with different priorities."""
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
        """Test cost optimizer with no active providers."""
        mock_get_active.return_value = []
        assert calculate_best_provider(100, "cost") == Provider.GEMINI

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_success(self, mock_active, mock_settings_getter, mock_settings):
        """Test successful routing."""
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.GEMINI]

        router = LegacySmartRouter()
        result = router.route_request("Hello", {"priority": "cost"})

        assert result["status"] == "success"
        assert result["provider"] == Provider.GEMINI
        assert result["attempts"] == 1

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_failover_503(self, mock_active, mock_settings_getter, mock_settings):
        """Test failover on 503 error."""
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.OPENAI, Provider.GEMINI]

        router = LegacySmartRouter()
        # "force_fail" triggers exception in SmartRouter._execute_call for OpenAI
        result = router.route_request("force_fail OpenAI now", {"priority": "latency"})

        assert result["status"] == "success"
        assert result["provider"] == Provider.GEMINI
        assert result["attempts"] == 2

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_failover_429(self, mock_active, mock_settings_getter, mock_settings):
        """Test failover on rate limit."""
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.OPENAI, Provider.ANTHROPIC]

        router = LegacySmartRouter()
        # "force_rate_limit" triggers 429 exception for OpenAI
        result = router.route_request("force_rate_limit OpenAI", {"priority": "latency"})

        assert result["status"] == "success"
        assert result["provider"] == Provider.ANTHROPIC
        assert result["attempts"] == 2

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_smart_router_all_fail(self, mock_active, mock_settings_getter, mock_settings):
        """Test all providers failing."""
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.OPENAI]

        router = LegacySmartRouter()
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            router.route_request("force_fail everything")

    @patch("shared.smart_router.routing_engine.get_settings")
    @patch("shared.smart_router.routing_engine.get_active_providers")
    def test_context_preservation(self, mock_active, mock_settings_getter, mock_settings):
        """Test context preservation during routing."""
        mock_settings_getter.return_value = mock_settings
        mock_active.return_value = [Provider.GEMINI]

        router = LegacySmartRouter()
        context = {"priority": "cost", "user_id": "user_123"}
        result = router.route_request("Hello", context)

        assert result["status"] == "success"
        assert result["provider"] == Provider.GEMINI
