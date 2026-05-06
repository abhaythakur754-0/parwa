"""
Tests for Active Learning System.

Tests verify:
- Uncertainty sampler identifies uncertain samples
- Sample selector prioritizes valuable samples
- Feedback collector gathers feedback
- Model updater improves model
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from agent_lightning.training.active_learning.uncertainty_sampler import (
    UncertaintySampler,
    SamplingStrategy,
    UncertaintyResult,
    get_uncertainty_sampler
)
from agent_lightning.training.active_learning.sample_selector import (
    SampleSelector,
    SelectionConfig,
    SelectedSample,
    get_sample_selector
)
from agent_lightning.training.active_learning.feedback_collector import (
    FeedbackCollector,
    FeedbackItem,
    FeedbackPriority,
    FeedbackQuality,
    get_feedback_collector
)
from agent_lightning.training.active_learning.model_updater import (
    ModelUpdater,
    UpdateConfig,
    UpdateResult,
    get_model_updater
)


class TestUncertaintySampler:
    """Tests for Uncertainty Sampler."""

    def test_initialization(self):
        """Test sampler initializes correctly."""
        sampler = UncertaintySampler()

        assert sampler.strategy == SamplingStrategy.ENTROPY
        assert sampler.threshold == 0.70
        assert sampler.committee_size == 3

    def test_entropy_sampling(self):
        """Test entropy-based uncertainty calculation."""
        sampler = UncertaintySampler(strategy=SamplingStrategy.ENTROPY)

        # High uncertainty (uniform distribution)
        result = sampler.calculate_uncertainty(
            query="Test query",
            prediction="A",
            probabilities={"A": 0.33, "B": 0.33, "C": 0.34}
        )

        assert result.uncertainty_score > 0.9  # High entropy
        assert result.is_uncertain

    def test_margin_sampling(self):
        """Test margin-based uncertainty calculation."""
        sampler = UncertaintySampler(strategy=SamplingStrategy.MARGIN)

        # Small margin (high uncertainty)
        result = sampler.calculate_uncertainty(
            query="Test query",
            prediction="A",
            probabilities={"A": 0.51, "B": 0.49}
        )

        assert result.uncertainty_score > 0.9  # Small margin

        # Large margin (low uncertainty)
        result2 = sampler.calculate_uncertainty(
            query="Test query",
            prediction="A",
            probabilities={"A": 0.95, "B": 0.05}
        )

        assert result2.uncertainty_score < 0.2  # Large margin

    def test_least_confident_sampling(self):
        """Test least confident sampling strategy."""
        sampler = UncertaintySampler(strategy=SamplingStrategy.LEAST_CONFIDENT)

        result = sampler.calculate_uncertainty(
            query="Test query",
            prediction="A",
            probabilities={"A": 0.60, "B": 0.40}
        )

        # Uncertainty = 1 - confidence
        assert result.uncertainty_score == 0.40

    def test_query_by_committee(self):
        """Test query-by-committee strategy."""
        sampler = UncertaintySampler(strategy=SamplingStrategy.QUERY_BY_COMMITTEE)

        # High disagreement
        result = sampler.calculate_uncertainty(
            query="Test query",
            prediction="A",
            probabilities={"A": 0.40, "B": 0.35, "C": 0.25},
            committee_predictions=["A", "B", "C"]
        )

        assert result.committee_disagreement is not None
        assert result.uncertainty_score > 0.5

    def test_select_uncertain_samples(self):
        """Test selection of uncertain samples."""
        sampler = UncertaintySampler()

        predictions = [
            {"query": "Q1", "prediction": "A", "probabilities": {"A": 0.95, "B": 0.05}},
            {"query": "Q2", "prediction": "A", "probabilities": {"A": 0.55, "B": 0.45}},
            {"query": "Q3", "prediction": "B", "probabilities": {"A": 0.40, "B": 0.60}},
        ]

        selected = sampler.select_uncertain_samples(predictions, budget=2)

        assert len(selected) <= 2
        # Q2 should be selected (lowest confidence)
        queries = [s.query for s in selected]
        assert "Q2" in queries

    def test_factory_function(self):
        """Test factory function."""
        sampler = get_uncertainty_sampler(strategy="margin", threshold=0.8)

        assert sampler.strategy == SamplingStrategy.MARGIN
        assert sampler.threshold == 0.8


class TestSampleSelector:
    """Tests for Sample Selector."""

    def test_initialization(self):
        """Test selector initializes correctly."""
        selector = SampleSelector()

        assert selector.config.budget == 10
        assert selector.config.diversity_weight == 0.3

    def test_diversity_calculation(self):
        """Test diversity score calculation."""
        selector = SampleSelector()

        # First sample has max diversity
        diversity = selector.calculate_diversity(
            {"query": "New query", "intent": "A"},
            []
        )
        assert diversity == 1.0

        # Same intent/words has lower diversity
        selected = [SelectedSample(
            sample_id="1",
            query="New query",
            intent="A"
        )]
        diversity = selector.calculate_diversity(
            {"query": "New query", "intent": "A"},
            selected
        )
        assert diversity < 1.0

    def test_representativeness_calculation(self):
        """Test representativeness score calculation."""
        selector = SampleSelector()

        all_samples = [
            {"query": "Q1", "intent": "A"},
            {"query": "Q2", "intent": "A"},
            {"query": "Q3", "intent": "B"},
        ]

        rep = selector.calculate_representativeness(
            {"query": "Q", "intent": "A"},
            all_samples
        )
        assert 0 <= rep <= 1

    def test_sample_selection(self):
        """Test sample selection process."""
        selector = SampleSelector(config=SelectionConfig(budget=5))

        candidates = [
            {"id": "1", "query": "Q1", "intent": "A", "uncertainty_score": 0.9},
            {"id": "2", "query": "Q2", "intent": "A", "uncertainty_score": 0.8},
            {"id": "3", "query": "Q3", "intent": "B", "uncertainty_score": 0.7},
            {"id": "4", "query": "Q4", "intent": "C", "uncertainty_score": 0.6},
            {"id": "5", "query": "Q5", "intent": "D", "uncertainty_score": 0.5},
        ]

        selected = selector.select_samples(candidates)

        assert len(selected) <= 5
        # Should prioritize high uncertainty
        assert selected[0].uncertainty_score >= selected[-1].uncertainty_score

    def test_class_balance(self):
        """Test class balance in selection."""
        selector = SampleSelector(config=SelectionConfig(
            budget=6,
            min_per_class=1,
            max_per_class=2
        ))

        candidates = [
            {"id": str(i), "query": f"Q{i}", "intent": "A", "uncertainty_score": 0.9}
            for i in range(10)
        ]

        selected = selector.select_samples(candidates)

        # Should have class balance
        intent_counts = {}
        for s in selected:
            intent_counts[s.intent] = intent_counts.get(s.intent, 0) + 1

        # Max per class should be respected
        for count in intent_counts.values():
            assert count <= selector.config.max_per_class

    def test_factory_function(self):
        """Test factory function."""
        selector = get_sample_selector(budget=20, diversity_weight=0.5)

        assert selector.config.budget == 20
        assert selector.config.diversity_weight == 0.5


class TestFeedbackCollector:
    """Tests for Feedback Collector."""

    def test_initialization(self):
        """Test collector initializes correctly."""
        collector = FeedbackCollector()

        assert collector.max_queue_size == 1000
        assert collector.auto_label_threshold == 0.95

    def test_add_feedback(self):
        """Test adding feedback."""
        collector = FeedbackCollector()

        feedback = collector.add_feedback(
            sample_id="sample_1",
            query="Test query",
            original_prediction="A",
            corrected_label="B",
            source="manager"
        )

        assert feedback.feedback_id == "fb_0"
        assert feedback.priority == FeedbackPriority.MEDIUM
        assert feedback.quality == FeedbackQuality.MEDIUM

    def test_priority_queue(self):
        """Test priority ordering."""
        collector = FeedbackCollector()

        # Add in reverse priority order
        collector.add_feedback("1", "Q1", "A", "B", priority=FeedbackPriority.LOW)
        collector.add_feedback("2", "Q2", "A", "B", priority=FeedbackPriority.CRITICAL)
        collector.add_feedback("3", "Q3", "A", "B", priority=FeedbackPriority.HIGH)

        pending = collector.get_pending_feedback()

        # CRITICAL should be first
        assert pending[0].priority == FeedbackPriority.CRITICAL

    def test_auto_label_suggestions(self):
        """Test auto-labeling suggestions."""
        collector = FeedbackCollector(auto_label_threshold=0.90)

        predictions = [
            {"sample_id": "1", "query": "Q1", "prediction": "A", "confidence": 0.95},
            {"sample_id": "2", "query": "Q2", "prediction": "B", "confidence": 0.85},
            {"sample_id": "3", "query": "Q3", "prediction": "C", "confidence": 0.88},
        ]

        suggestions = collector.suggest_auto_labels(predictions)

        # Only high confidence should not need review
        high_conf = [s for s in suggestions if not s["needs_review"]]
        assert len(high_conf) == 1
        assert high_conf[0]["sample_id"] == "1"

    def test_manager_corrections_aggregation(self):
        """Test aggregation of manager corrections."""
        collector = FeedbackCollector()

        corrections = [
            {"sample_id": "1", "query": "Q1", "original_prediction": "A", "corrected_label": "B"},
            {"sample_id": "2", "query": "Q2", "original_prediction": "A", "corrected_label": "C"},
        ]

        count = collector.aggregate_manager_corrections("manager_1", corrections)

        assert count == 2
        stats = collector.get_feedback_stats()
        assert "manager_manager_1" in stats["by_source"]

    def test_quality_score(self):
        """Test feedback quality score calculation."""
        collector = FeedbackCollector()

        collector.add_feedback("1", "Q1", "A", "B", quality=FeedbackQuality.HIGH)
        collector.add_feedback("2", "Q2", "A", "B", quality=FeedbackQuality.HIGH)
        collector.add_feedback("3", "Q3", "A", "B", quality=FeedbackQuality.LOW)

        score = collector.calculate_feedback_quality_score()

        # Average of 1.0, 1.0, 0.4
        assert 0.7 < score < 0.9

    def test_export_feedback(self):
        """Test feedback export."""
        collector = FeedbackCollector()

        collector.add_feedback("1", "Q1", "A", "B")
        collector.add_feedback("2", "Q2", "A", "C")

        exported = collector.export_feedback()

        assert len(exported) == 2
        assert all("feedback_id" in item for item in exported)

    def test_factory_function(self):
        """Test factory function."""
        collector = get_feedback_collector(max_queue_size=500)

        assert collector.max_queue_size == 500


class TestModelUpdater:
    """Tests for Model Updater."""

    def test_initialization(self):
        """Test updater initializes correctly."""
        updater = ModelUpdater()

        assert updater.config.min_samples == 10
        assert updater.config.accuracy_threshold == 0.90

    def test_version_increment(self):
        """Test version incrementing."""
        updater = ModelUpdater()

        assert updater.get_current_version() == "v0.0.0"

        # Apply update to increment version
        samples = [{"query": f"Q{i}", "intent": "A"} for i in range(15)]
        result = updater.apply_update(samples)

        assert result.version != "v0.0.0"

    def test_apply_update_success(self):
        """Test successful model update."""
        updater = ModelUpdater(config=UpdateConfig(min_samples=5))

        samples = [{"query": f"Q{i}", "intent": "A"} for i in range(10)]
        result = updater.apply_update(samples)

        assert result.success
        assert result.samples_used == 10
        assert result.accuracy_after >= result.accuracy_before

    def test_update_validation(self):
        """Test update validation."""
        updater = ModelUpdater(config=UpdateConfig(min_samples=10))

        # Too few samples
        samples = [{"query": f"Q{i}", "intent": "A"} for i in range(5)]
        result = updater.apply_update(samples)

        assert not result.success
        assert "Need at least" in result.metrics.get("error", "")

    def test_version_history(self):
        """Test version history tracking."""
        updater = ModelUpdater(config=UpdateConfig(min_samples=5))

        # Apply multiple updates
        for i in range(3):
            samples = [{"query": f"Q{j}", "intent": "A"} for j in range(10)]
            updater.apply_update(samples)

        history = updater.get_version_history()

        assert len(history) == 3

    def test_rollback(self):
        """Test model rollback."""
        updater = ModelUpdater(config=UpdateConfig(min_samples=5))

        # Apply initial update
        samples = [{"query": f"Q{i}", "intent": "A"} for i in range(10)]
        result1 = updater.apply_update(samples)
        version_after_update = result1.version

        # Apply another update
        result2 = updater.apply_update(samples)

        # Rollback
        success = updater.rollback()

        assert success
        assert updater.get_current_version() == version_after_update

    def test_performance_trend(self):
        """Test performance trend tracking."""
        updater = ModelUpdater(config=UpdateConfig(min_samples=5))

        # Apply multiple updates
        for i in range(3):
            samples = [{"query": f"Q{j}", "intent": "A"} for j in range(10)]
            updater.apply_update(samples)

        trend = updater.get_performance_trend()

        assert len(trend) == 3
        # Accuracy should generally increase
        accuracies = [t[1] for t in trend]
        assert accuracies[-1] >= accuracies[0]

    def test_factory_function(self):
        """Test factory function."""
        updater = get_model_updater(min_samples=20, accuracy_threshold=0.95)

        assert updater.config.min_samples == 20
        assert updater.config.accuracy_threshold == 0.95


class TestActiveLearningIntegration:
    """Integration tests for the full active learning pipeline."""

    def test_full_pipeline(self):
        """Test complete active learning workflow."""
        # 1. Uncertainty sampling
        sampler = get_uncertainty_sampler(strategy="entropy")

        predictions = [
            {"query": f"Query {i}", "prediction": "A", "probabilities": {"A": 0.5 + i*0.05, "B": 0.5 - i*0.05}}
            for i in range(10)
        ]

        uncertain = sampler.select_uncertain_samples(predictions, budget=5)

        # 2. Sample selection
        selector = get_sample_selector(budget=3)

        candidates = [
            {"id": s.sample_id, "query": s.query, "intent": "A", "uncertainty_score": s.uncertainty_score}
            for s in uncertain
        ]

        selected = selector.select_samples(candidates)

        # 3. Feedback collection
        collector = get_feedback_collector()

        for sample in selected:
            collector.add_feedback(
                sample_id=sample.sample_id,
                query=sample.query,
                original_prediction="A",
                corrected_label="B",
                source="manager"
            )

        stats = collector.get_feedback_stats()
        assert stats["total_feedback"] == len(selected)

        # 4. Model update
        updater = get_model_updater(min_samples=3)

        feedback = collector.export_feedback()
        training_samples = [
            {"query": f["query"], "intent": f["corrected_label"]}
            for f in feedback
        ]

        result = updater.apply_update(training_samples)

        assert result.success or not training_samples  # May fail if too few samples


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
