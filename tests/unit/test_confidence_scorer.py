"""
Unit tests for PARWA Confidence Scorer Module.

Tests confidence thresholds (GRADUATE=95%, ESCALATE=70%)
and weighted average scoring (40%+30%+20%+10%=100%).
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.confidence.thresholds import (
    ConfidenceThresholds,
    ConfidenceAction,
    get_confidence_action,
    should_escalate,
    can_graduate,
)
from shared.confidence.scorer import (
    ConfidenceScorer,
    ConfidenceBreakdown,
    ConfidenceResult,
    WEIGHTS,
    calculate_confidence,
)


class TestConfidenceThresholds:
    """Tests for confidence thresholds."""

    def test_graduate_threshold_is_95_percent(self):
        """Test that GRADUATE threshold is exactly 95%."""
        assert ConfidenceThresholds.GRADUATE_THRESHOLD == 0.95

    def test_escalate_threshold_is_70_percent(self):
        """Test that ESCALATE threshold is exactly 70%."""
        assert ConfidenceThresholds.ESCALATE_THRESHOLD == 0.70

    def test_graduate_threshold_percent_string(self):
        """Test GRADUATE threshold in config shows 95%."""
        config = ConfidenceThresholds.get_threshold_config()
        assert config["graduate_percent"] == "95%"

    def test_escalate_threshold_percent_string(self):
        """Test ESCALATE threshold in config shows 70%."""
        config = ConfidenceThresholds.get_threshold_config()
        assert config["escalate_percent"] == "70%"

    def test_get_action_graduate_at_95_percent(self):
        """Test that 95% confidence returns GRADUATE action."""
        action = ConfidenceThresholds.get_action(0.95)
        assert action == ConfidenceAction.GRADUATE

    def test_get_action_graduate_above_95_percent(self):
        """Test that >95% confidence returns GRADUATE action."""
        action = ConfidenceThresholds.get_action(0.96)
        assert action == ConfidenceAction.GRADUATE

    def test_get_action_continue_at_70_percent(self):
        """Test that 70% confidence returns CONTINUE action."""
        action = ConfidenceThresholds.get_action(0.70)
        assert action == ConfidenceAction.CONTINUE

    def test_get_action_continue_between_70_and_95(self):
        """Test that 70-95% confidence returns CONTINUE action."""
        action = ConfidenceThresholds.get_action(0.80)
        assert action == ConfidenceAction.CONTINUE

    def test_get_action_escalate_below_70(self):
        """Test that <70% confidence returns ESCALATE action."""
        action = ConfidenceThresholds.get_action(0.69)
        assert action == ConfidenceAction.ESCALATE

    def test_get_action_escalate_at_zero(self):
        """Test that 0% confidence returns ESCALATE action."""
        action = ConfidenceThresholds.get_action(0.0)
        assert action == ConfidenceAction.ESCALATE

    def test_get_action_rejects_negative(self):
        """Test that negative confidence raises ValueError."""
        with pytest.raises(ValueError):
            ConfidenceThresholds.get_action(-0.1)

    def test_get_action_rejects_above_one(self):
        """Test that >1.0 confidence raises ValueError."""
        with pytest.raises(ValueError):
            ConfidenceThresholds.get_action(1.1)

    def test_should_escalate_below_70(self):
        """Test should_escalate returns True below 70%."""
        assert should_escalate(0.69) is True
        assert should_escalate(0.50) is True
        assert should_escalate(0.0) is True

    def test_should_escalate_at_or_above_70(self):
        """Test should_escalate returns False at/above 70%."""
        assert should_escalate(0.70) is False
        assert should_escalate(0.80) is False
        assert should_escalate(0.95) is False

    def test_can_graduate_at_95(self):
        """Test can_graduate returns True at 95%."""
        assert can_graduate(0.95) is True

    def test_can_graduate_above_95(self):
        """Test can_graduate returns True above 95%."""
        assert can_graduate(0.96) is True
        assert can_graduate(1.0) is True

    def test_can_graduate_below_95(self):
        """Test can_graduate returns False below 95%."""
        assert can_graduate(0.94) is False
        assert can_graduate(0.80) is False

    def test_validate_thresholds_passes(self):
        """Test that default thresholds are valid."""
        assert ConfidenceThresholds.validate_thresholds() is True


class TestConfidenceWeights:
    """Tests for weight configuration."""

    def test_weights_sum_to_100_percent(self):
        """Test that weights sum to exactly 100% (1.0)."""
        total = sum(WEIGHTS.values())
        assert total == 1.0

    def test_response_quality_weight_is_40_percent(self):
        """Test response_quality weight is 40%."""
        assert WEIGHTS["response_quality"] == 0.40

    def test_knowledge_match_weight_is_30_percent(self):
        """Test knowledge_match weight is 30%."""
        assert WEIGHTS["knowledge_match"] == 0.30

    def test_context_coherence_weight_is_20_percent(self):
        """Test context_coherence weight is 20%."""
        assert WEIGHTS["context_coherence"] == 0.20

    def test_safety_score_weight_is_10_percent(self):
        """Test safety_score weight is 10%."""
        assert WEIGHTS["safety_score"] == 0.10

    def test_weights_sum_formula(self):
        """Test explicit formula: 40+30+20+10=100."""
        expected_sum = 0.40 + 0.30 + 0.20 + 0.10
        assert sum(WEIGHTS.values()) == pytest.approx(expected_sum)
        assert expected_sum == pytest.approx(1.0)


class TestConfidenceScorer:
    """Tests for ConfidenceScorer class."""

    def test_scorer_initialization(self):
        """Test scorer initializes with default weights."""
        scorer = ConfidenceScorer()
        assert scorer.weights == WEIGHTS

    def test_scorer_custom_weights(self):
        """Test scorer can use custom weights."""
        custom = {
            "response_quality": 0.25,
            "knowledge_match": 0.25,
            "context_coherence": 0.25,
            "safety_score": 0.25,
        }
        scorer = ConfidenceScorer(custom_weights=custom)
        assert scorer.weights == custom

    def test_scorer_rejects_invalid_weights_sum(self):
        """Test scorer rejects weights that don't sum to 1.0."""
        invalid = {
            "response_quality": 0.50,
            "knowledge_match": 0.30,
            "context_coherence": 0.10,
            "safety_score": 0.05,  # Sum = 0.95
        }
        with pytest.raises(ValueError):
            ConfidenceScorer(custom_weights=invalid)

    def test_scorer_rejects_missing_weight_keys(self):
        """Test scorer rejects weights missing required keys."""
        invalid = {
            "response_quality": 0.40,
            "knowledge_match": 0.30,
            "context_coherence": 0.30,
            # Missing safety_score
        }
        with pytest.raises(ValueError):
            ConfidenceScorer(custom_weights=invalid)

    def test_score_basic(self):
        """Test basic scoring calculation."""
        scorer = ConfidenceScorer()
        result = scorer.score(
            response_quality=1.0,
            knowledge_match=1.0,
            context_coherence=1.0,
            safety_score=1.0
        )

        assert result.overall_score == pytest.approx(1.0)
        assert result.action == ConfidenceAction.GRADUATE

    def test_score_weighted_average(self):
        """Test that score is correctly weighted average."""
        scorer = ConfidenceScorer()
        # All scores = 1.0 should give 1.0
        result = scorer.score(1.0, 1.0, 1.0, 1.0)
        assert result.overall_score == pytest.approx(1.0)

        # All scores = 0.0 should give 0.0
        result = scorer.score(0.0, 0.0, 0.0, 0.0)
        assert result.overall_score == pytest.approx(0.0)

    def test_score_weighted_calculation(self):
        """Test explicit weighted calculation."""
        scorer = ConfidenceScorer()
        # Set each component to 1.0 individually, others to 0
        # Only response_quality = 1.0 -> 0.40
        result = scorer.score(1.0, 0.0, 0.0, 0.0)
        assert result.overall_score == pytest.approx(0.40)

        # Only knowledge_match = 1.0 -> 0.30
        result = scorer.score(0.0, 1.0, 0.0, 0.0)
        assert result.overall_score == pytest.approx(0.30)

        # Only context_coherence = 1.0 -> 0.20
        result = scorer.score(0.0, 0.0, 1.0, 0.0)
        assert result.overall_score == pytest.approx(0.20)

        # Only safety_score = 1.0 -> 0.10
        result = scorer.score(0.0, 0.0, 0.0, 1.0)
        assert result.overall_score == pytest.approx(0.10)

    def test_score_combined_calculation(self):
        """Test combined weighted calculation."""
        scorer = ConfidenceScorer()
        # 0.8*0.4 + 0.9*0.3 + 0.7*0.2 + 1.0*0.1 = 0.32 + 0.27 + 0.14 + 0.10 = 0.83
        result = scorer.score(0.8, 0.9, 0.7, 1.0)
        expected = 0.8 * 0.4 + 0.9 * 0.3 + 0.7 * 0.2 + 1.0 * 0.1
        assert abs(result.overall_score - expected) < 0.001

    def test_score_returns_graduate_at_95(self):
        """Test score returns GRADUATE action at 95%+."""
        scorer = ConfidenceScorer()
        # 1.0 * 0.4 + 1.0 * 0.3 + 1.0 * 0.2 + 0.5 * 0.1 = 0.95
        result = scorer.score(1.0, 1.0, 1.0, 0.5)
        assert result.overall_score == pytest.approx(0.95)
        assert result.action == ConfidenceAction.GRADUATE

    def test_score_returns_escalate_below_70(self):
        """Test score returns ESCALATE action below 70%."""
        scorer = ConfidenceScorer()
        # All 0.5 -> 0.5 (below 70%)
        result = scorer.score(0.5, 0.5, 0.5, 0.5)
        assert result.overall_score == pytest.approx(0.5)
        assert result.action == ConfidenceAction.ESCALATE

    def test_score_returns_continue_at_70_to_94(self):
        """Test score returns CONTINUE action at 70-94%."""
        scorer = ConfidenceScorer()
        # Mix that gives ~0.80
        result = scorer.score(0.8, 0.8, 0.8, 0.8)
        assert result.action == ConfidenceAction.CONTINUE

    def test_score_rejects_invalid_scores(self):
        """Test scorer rejects scores outside 0-1 range."""
        scorer = ConfidenceScorer()

        with pytest.raises(ValueError):
            scorer.score(-0.1, 0.5, 0.5, 0.5)

        with pytest.raises(ValueError):
            scorer.score(1.1, 0.5, 0.5, 0.5)

    def test_score_from_dict(self):
        """Test scoring from dictionary input."""
        scorer = ConfidenceScorer()
        result = scorer.score_from_dict({
            "response_quality": 0.9,
            "knowledge_match": 0.8,
            "context_coherence": 0.7,
            "safety_score": 1.0,
        })
        assert 0.0 <= result.overall_score <= 1.0

    def test_quick_score(self):
        """Test quick scoring with defaults."""
        scorer = ConfidenceScorer()
        result = scorer.quick_score(quality=0.9, match=0.8)
        # response_quality=0.9, knowledge_match=0.8, context_coherence=0.8, safety_score=1.0
        expected = 0.9 * 0.4 + 0.8 * 0.3 + 0.8 * 0.2 + 1.0 * 0.1
        assert abs(result.overall_score - expected) < 0.001

    def test_get_weights(self):
        """Test getting current weights."""
        scorer = ConfidenceScorer()
        weights = scorer.get_weights()
        assert weights == WEIGHTS

    def test_get_weight_percentages(self):
        """Test getting weights as percentage strings."""
        scorer = ConfidenceScorer()
        percentages = scorer.get_weight_percentages()
        assert percentages["response_quality"] == "40%"
        assert percentages["knowledge_match"] == "30%"
        assert percentages["context_coherence"] == "20%"
        assert percentages["safety_score"] == "10%"


class TestConfidenceResult:
    """Tests for ConfidenceResult model."""

    def test_result_has_overall_score(self):
        """Test result contains overall score."""
        scorer = ConfidenceScorer()
        result = scorer.score(0.8, 0.8, 0.8, 0.8)
        assert hasattr(result, "overall_score")
        assert 0.0 <= result.overall_score <= 1.0

    def test_result_has_breakdown(self):
        """Test result contains breakdown."""
        scorer = ConfidenceScorer()
        result = scorer.score(0.8, 0.8, 0.8, 0.8)
        assert hasattr(result, "breakdown")
        assert isinstance(result.breakdown, ConfidenceBreakdown)

    def test_result_has_action(self):
        """Test result contains action."""
        scorer = ConfidenceScorer()
        result = scorer.score(0.8, 0.8, 0.8, 0.8)
        assert hasattr(result, "action")
        assert isinstance(result.action, ConfidenceAction)

    def test_result_has_weights(self):
        """Test result contains weights."""
        scorer = ConfidenceScorer()
        result = scorer.score(0.8, 0.8, 0.8, 0.8)
        assert hasattr(result, "weights")
        assert result.weights == WEIGHTS

    def test_breakdown_stores_individual_scores(self):
        """Test breakdown stores individual component scores."""
        scorer = ConfidenceScorer()
        result = scorer.score(0.9, 0.8, 0.7, 1.0)

        assert result.breakdown.response_quality == 0.9
        assert result.breakdown.knowledge_match == 0.8
        assert result.breakdown.context_coherence == 0.7
        assert result.breakdown.safety_score == 1.0


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_calculate_confidence(self):
        """Test calculate_confidence convenience function."""
        score = calculate_confidence(1.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0)

        score = calculate_confidence(0.0, 0.0, 0.0, 0.0)
        assert score == pytest.approx(0.0)

    def test_get_confidence_action_convenience(self):
        """Test get_confidence_action convenience function."""
        action = get_confidence_action(0.95)
        assert action == ConfidenceAction.GRADUATE

        action = get_confidence_action(0.69)
        assert action == ConfidenceAction.ESCALATE


class TestIntegration:
    """Integration tests for confidence module."""

    def test_full_confidence_workflow(self):
        """Test complete confidence scoring workflow."""
        scorer = ConfidenceScorer()

        # Simulate a high-quality response
        result = scorer.score(
            response_quality=0.95,
            knowledge_match=0.90,
            context_coherence=0.88,
            safety_score=1.0
        )

        # Should graduate (score ~0.93)
        assert result.overall_score > 0.90
        assert result.action in [ConfidenceAction.GRADUATE, ConfidenceAction.CONTINUE]

        # Check should_escalate
        assert should_escalate(result.overall_score) is False

    def test_low_confidence_workflow(self):
        """Test low confidence workflow requires escalation."""
        scorer = ConfidenceScorer()

        # Simulate a poor response
        result = scorer.score(
            response_quality=0.50,
            knowledge_match=0.40,
            context_coherence=0.60,
            safety_score=0.90
        )

        # Should escalate (score ~0.53)
        assert result.overall_score < 0.70
        assert result.action == ConfidenceAction.ESCALATE
        assert should_escalate(result.overall_score) is True

    def test_boundary_conditions(self):
        """Test boundary conditions for actions."""
        scorer = ConfidenceScorer()

        # Test exact 95% boundary
        result = scorer.score(1.0, 1.0, 1.0, 0.5)  # = 0.95
        assert result.overall_score == 0.95
        assert result.action == ConfidenceAction.GRADUATE

        # Test exact 70% boundary
        # Need: x*0.4 + y*0.3 + z*0.2 + w*0.1 = 0.70
        # Use: 0.7*0.4 + 0.7*0.3 + 0.7*0.2 + 0.7*0.1 = 0.70
        result = scorer.score(0.7, 0.7, 0.7, 0.7)
        assert result.overall_score == 0.70
        assert result.action == ConfidenceAction.CONTINUE
