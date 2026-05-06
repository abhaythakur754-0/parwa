"""
Unit tests for PARWA Sentiment Analysis.

Tests sentiment analyzer and routing rules.
"""
import os
import pytest
from datetime import datetime, timezone

# Set test environment variables
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.sentiment.analyzer import (
    SentimentAnalyzer,
    SentimentResult,
    SentimentAnalyzerConfig,
    SentimentType,
    SentimentIntensity,
)
from shared.sentiment.routing_rules import (
    SentimentRouter,
    RoutingDecision,
    SentimentRoutingConfig,
    RoutingPathway,
    RoutingThresholds,
    create_sentiment_router,
)


class TestSentimentAnalyzer:
    """Tests for Sentiment Analyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initializes correctly."""
        analyzer = SentimentAnalyzer()

        assert analyzer.config is not None
        assert analyzer.config.anger_threshold == 50.0
        assert analyzer.config.enable_logging is True

    def test_analyze_neutral_text(self):
        """Test analyzing neutral text."""
        analyzer = SentimentAnalyzer()

        result = analyzer.analyze("What are your hours?")

        assert isinstance(result, SentimentResult)
        assert result.primary_sentiment in [
            SentimentType.NEUTRAL.value,
            SentimentType.CONFUSION.value,
        ]

    def test_analyze_angry_text(self):
        """Test analyzing angry text."""
        analyzer = SentimentAnalyzer()

        result = analyzer.analyze(
            "I am absolutely furious with your terrible service! "
            "This is unacceptable and I want to speak to a manager immediately!"
        )

        assert isinstance(result, SentimentResult)
        assert result.primary_sentiment == SentimentType.ANGER.value
        # Anger score should be high
        assert result.sentiment_scores.get(SentimentType.ANGER.value, 0) > 50

    def test_analyze_frustrated_text(self):
        """Test analyzing frustrated text."""
        analyzer = SentimentAnalyzer()

        result = analyzer.analyze(
            "I've been waiting for hours and nothing is working. "
            "This is so frustrating!"
        )

        assert isinstance(result, SentimentResult)
        # Should detect frustration
        assert result.sentiment_scores.get(SentimentType.FRUSTRATION.value, 0) > 0

    def test_analyze_urgent_text(self):
        """Test analyzing urgent text."""
        analyzer = SentimentAnalyzer()

        result = analyzer.analyze(
            "This is urgent! I need help immediately! It's an emergency!"
        )

        assert isinstance(result, SentimentResult)
        assert result.sentiment_scores.get(SentimentType.URGENCY.value, 0) > 0

    def test_analyze_happy_text(self):
        """Test analyzing happy text."""
        analyzer = SentimentAnalyzer()

        result = analyzer.analyze(
            "Thank you so much! You've been incredibly helpful. "
            "I'm so happy with the service!"
        )

        assert isinstance(result, SentimentResult)
        # Should detect happiness or gratitude
        positive_score = (
            result.sentiment_scores.get(SentimentType.HAPPINESS.value, 0) +
            result.sentiment_scores.get(SentimentType.GRATITUDE.value, 0)
        )
        assert positive_score > 0

    def test_analyze_empty_text_raises(self):
        """Test analyzing empty text raises error."""
        analyzer = SentimentAnalyzer()

        with pytest.raises(ValueError):
            analyzer.analyze("")

    def test_analyze_batch(self):
        """Test batch analysis."""
        analyzer = SentimentAnalyzer()

        texts = [
            "Hello there!",
            "I'm angry about this!",
            "Thanks for your help!",
        ]

        results = analyzer.analyze_batch(texts)

        assert len(results) == 3
        assert all(isinstance(r, SentimentResult) for r in results)

    def test_requires_attention_high_anger(self):
        """Test attention flag for high anger."""
        analyzer = SentimentAnalyzer(
            config=SentimentAnalyzerConfig(anger_threshold=30.0)
        )

        result = analyzer.analyze(
            "I am absolutely furious! This is the worst service ever! "
            "I hate this company and will never use you again!"
        )

        assert result.requires_attention is True

    def test_routing_pathway_high_anger(self):
        """Test routing pathway for high anger."""
        analyzer = SentimentAnalyzer()

        result = analyzer.analyze(
            "I am so angry! This is ridiculous! I want a refund now!"
        )

        # High anger should route to high or escalation
        assert result.routing_pathway in ["high", "escalation", "elevated"]

    def test_routing_pathway_urgency(self):
        """Test routing pathway for urgency."""
        analyzer = SentimentAnalyzer()

        result = analyzer.analyze(
            "This is urgent! I need immediate help right now!"
        )

        # Urgency should route to priority
        assert result.routing_pathway in ["priority", "elevated"]

    def test_get_stats(self):
        """Test getting analyzer stats."""
        analyzer = SentimentAnalyzer()

        analyzer.analyze("Test query 1")
        analyzer.analyze("Test query 2")

        stats = analyzer.get_stats()

        assert "analyses_performed" in stats
        assert stats["analyses_performed"] == 2

    def test_confidence_calculation(self):
        """Test confidence calculation."""
        analyzer = SentimentAnalyzer()

        # Longer text with clear sentiment should have higher confidence
        long_result = analyzer.analyze(
            "I am extremely frustrated and angry about this terrible service. "
            "I have been waiting for hours and nothing works. This is unacceptable!"
        )

        # Very short text
        short_result = analyzer.analyze("ok")

        assert isinstance(long_result.confidence, float)
        assert isinstance(short_result.confidence, float)


class TestSentimentRouter:
    """Tests for Sentiment Router."""

    def test_router_initialization(self):
        """Test router initializes correctly."""
        router = SentimentRouter()

        assert router.analyzer is not None
        assert router.config is not None

    def test_route_standard_query(self):
        """Test routing standard query."""
        router = SentimentRouter()

        decision = router.route("What are your business hours?")

        assert isinstance(decision, RoutingDecision)
        assert decision.pathway in [
            RoutingPathway.STANDARD.value,
            RoutingPathway.GUIDED.value,
        ]

    def test_route_angry_query_to_high(self):
        """Test routing angry query to high pathway."""
        router = SentimentRouter()

        decision = router.route(
            "I am absolutely furious! This is the worst experience ever! "
            "I want to speak to a manager right now!"
        )

        # High anger should route to high or escalation
        assert decision.pathway in [
            RoutingPathway.HIGH.value,
            RoutingPathway.ESCALATION.value,
            RoutingPathway.ELEVATED.value,
        ]

    def test_route_urgent_to_priority(self):
        """Test routing urgent query to priority."""
        router = SentimentRouter()

        decision = router.route(
            "URGENT! This is an emergency! I need immediate help right now! "
            "CRITICAL priority! This cannot wait! ASAP!"
        )

        # High urgency should route to priority or elevated
        assert decision.pathway in [
            RoutingPathway.PRIORITY.value,
            RoutingPathway.ELEVATED.value,
        ]

    def test_route_confused_to_guided(self):
        """Test routing confused query to guided."""
        router = SentimentRouter()

        decision = router.route(
            "I don't understand how this works. Can you explain it to me?"
        )

        assert decision.pathway in [
            RoutingPathway.GUIDED.value,
            RoutingPathway.STANDARD.value,
        ]

    def test_human_escalation_required(self):
        """Test human escalation for critical cases."""
        router = SentimentRouter()

        decision = router.route(
            "I am going to sue your company! This is fraud! "
            "I want to speak to your lawyer immediately! I'll call the BBB!"
        )

        assert decision.requires_human is True

    def test_routing_decision_has_sentiment(self):
        """Test routing decision includes sentiment."""
        router = SentimentRouter()

        decision = router.route("I'm happy with the service!")

        assert decision.sentiment_result is not None
        assert isinstance(decision.sentiment_result, SentimentResult)

    def test_routing_with_context(self):
        """Test routing with additional context."""
        router = SentimentRouter()

        decision = router.route(
            "I need help",
            context={"previous_issues": 5, "customer_tier": "premium"}
        )

        assert isinstance(decision, RoutingDecision)
        assert decision.sentiment_result is not None

    def test_routing_with_budget_constraints(self):
        """Test routing with budget constraints."""
        router = SentimentRouter()

        decision = router.route(
            "I'm having a complex issue that needs detailed help",
            budget_remaining=0.5  # Critical budget
        )

        # Should use lighter tier due to budget
        assert decision.tier in ["light", "medium"]

    def test_routing_reasons_provided(self):
        """Test that routing reasons are provided."""
        router = SentimentRouter()

        decision = router.route(
            "I am very angry and frustrated with this service!"
        )

        assert len(decision.routing_reasons) > 0

    def test_recommended_actions_provided(self):
        """Test that recommended actions are provided."""
        router = SentimentRouter()

        decision = router.route(
            "I'm confused, can you help me understand?"
        )

        assert isinstance(decision.recommended_actions, list)

    def test_get_stats(self):
        """Test getting router stats."""
        router = SentimentRouter()

        router.route("Test 1")
        router.route("Test 2")

        stats = router.get_stats()

        assert "routing_decisions" in stats
        assert stats["routing_decisions"] == 2


class TestRoutingThresholds:
    """Tests for Routing Thresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = RoutingThresholds()

        assert thresholds.ANGER_ESCALATION_THRESHOLD == 75.0
        assert thresholds.CRITICAL_INTENSITY_THRESHOLD == 80.0

    def test_thresholds_are_class_attrs(self):
        """Test that thresholds are class attributes."""
        # Verify thresholds are accessible
        assert hasattr(RoutingThresholds, 'ANGER_ESCALATION_THRESHOLD')
        assert hasattr(RoutingThresholds, 'ESCALATION_COMBINED_THRESHOLD')


class TestSentimentRoutingConfig:
    """Tests for Sentiment Routing Config."""

    def test_default_config(self):
        """Test default configuration."""
        config = SentimentRoutingConfig()

        assert config.enable_sentiment_routing is True
        assert config.escalate_on_anger is True
        assert config.anger_threshold == RoutingThresholds.ANGER_ESCALATION_THRESHOLD

    def test_custom_config(self):
        """Test custom configuration."""
        config = SentimentRoutingConfig(
            anger_threshold=60.0,
            escalate_on_anger=False
        )

        assert config.anger_threshold == 60.0
        assert config.escalate_on_anger is False


class TestIntegration:
    """Integration tests for sentiment module."""

    def test_full_sentiment_workflow(self):
        """Test full sentiment analysis workflow."""
        analyzer = SentimentAnalyzer()
        router = SentimentRouter(analyzer=analyzer)

        # Analyze angry customer
        decision = router.route(
            "I've been waiting for 3 hours! This is absolutely ridiculous! "
            "I want my money back and I'm never using your service again!"
        )

        assert decision.pathway in [
            RoutingPathway.HIGH.value,
            RoutingPathway.ESCALATION.value,
            RoutingPathway.ELEVATED.value,
        ]
        assert len(decision.routing_reasons) > 0

    def test_positive_sentiment_flow(self):
        """Test positive sentiment handling."""
        router = create_sentiment_router()

        decision = router.route(
            "Thank you so much for your help! You've been amazing!"
        )

        assert decision.pathway == RoutingPathway.STANDARD.value
        assert decision.requires_human is False

    def test_mixed_emotions_handling(self):
        """Test handling of mixed emotions."""
        router = SentimentRouter()

        decision = router.route(
            "I'm frustrated but I really need this fixed urgently. "
            "Please help me resolve this issue."
        )

        # Should handle mixed emotions appropriately
        assert decision.sentiment_result is not None
        # Should have urgency due to 'urgently' keyword
        urgency_score = decision.sentiment_result.sentiment_scores.get(
            SentimentType.URGENCY.value, 0
        )
        assert urgency_score > 0
