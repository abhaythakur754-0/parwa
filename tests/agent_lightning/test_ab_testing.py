"""
Tests for A/B Testing Framework.

Tests verify:
- Traffic splits correctly
- Experiments run
- Metrics collected
- Statistical analysis works
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from agent_lightning.monitoring.ab_testing.traffic_splitter import (
    TrafficSplitter,
    SplitConfig,
    Variant,
    VariantAssignment,
    get_traffic_splitter
)
from agent_lightning.monitoring.ab_testing.experiment_manager import (
    ExperimentManager,
    Experiment,
    ExperimentStatus,
    ExperimentConfig,
    get_experiment_manager
)
from agent_lightning.monitoring.ab_testing.metrics_collector import (
    MetricsCollector,
    MetricType,
    VariantMetrics,
    get_metrics_collector
)
from agent_lightning.monitoring.ab_testing.statistical_analyzer import (
    StatisticalAnalyzer,
    SignificanceResult,
    ConfidenceLevel,
    get_statistical_analyzer
)


class TestTrafficSplitter:
    """Tests for Traffic Splitter."""

    def test_initialization(self):
        """Test splitter initializes correctly."""
        splitter = TrafficSplitter()

        assert splitter.config.control_percentage == 90.0
        assert splitter.config.treatment_percentage == 10.0

    def test_custom_split(self):
        """Test custom traffic split."""
        config = SplitConfig(
            control_percentage=80.0,
            treatment_percentage=20.0
        )
        splitter = TrafficSplitter(config)

        distribution = splitter.get_variant_distribution()
        assert distribution["control"] == 80.0
        assert distribution["treatment"] == 20.0

    def test_consistent_assignment(self):
        """Test that same user always gets same variant."""
        splitter = TrafficSplitter()

        # Same user should always get same variant
        assignment1 = splitter.assign_variant("user_1", "client_1", "exp_1")
        assignment2 = splitter.assign_variant("user_1", "client_1", "exp_1")

        assert assignment1.variant == assignment2.variant

    def test_different_users_distribution(self):
        """Test distribution across many users."""
        splitter = TrafficSplitter()

        # Assign many users
        assignments = {}
        for i in range(100):
            assignment = splitter.assign_variant(f"user_{i}", "client_1", "exp_1")
            variant = assignment.variant.value
            assignments[variant] = assignments.get(variant, 0) + 1

        # Check rough distribution (allow some variance)
        # With 90/10 split, control should have ~90 users
        assert assignments.get("control", 0) > 70
        assert assignments.get("treatment", 0) > 5

    def test_client_isolation(self):
        """Test that same user in different client gets independent assignment."""
        splitter = TrafficSplitter()

        # Same user, different clients
        assignment1 = splitter.assign_variant("user_1", "client_A", "exp_1")
        assignment2 = splitter.assign_variant("user_1", "client_B", "exp_1")

        # Assignments should be independent (not necessarily different)
        assert assignment1.client_id == "client_A"
        assert assignment2.client_id == "client_B"

    def test_gradual_rollout(self):
        """Test gradual rollout schedule generation."""
        splitter = TrafficSplitter()

        schedule = splitter.gradual_rollout(target_treatment_percentage=50.0, steps=5)

        assert len(schedule) == 5
        assert schedule[-1] == 50.0

    def test_update_distribution(self):
        """Test updating traffic distribution."""
        splitter = TrafficSplitter()

        splitter.update_distribution(control=70.0, treatment=30.0)

        distribution = splitter.get_variant_distribution()
        assert distribution["control"] == 70.0
        assert distribution["treatment"] == 30.0

    def test_invalid_percentages(self):
        """Test that invalid percentages raise error."""
        config = SplitConfig(
            control_percentage=60.0,
            treatment_percentage=50.0  # Total > 100
        )

        with pytest.raises(ValueError):
            TrafficSplitter(config)

    def test_factory_function(self):
        """Test factory function."""
        splitter = get_traffic_splitter(treatment_percentage=25.0)

        assert splitter.config.treatment_percentage == 25.0
        assert splitter.config.control_percentage == 75.0


class TestExperimentManager:
    """Tests for Experiment Manager."""

    def test_initialization(self):
        """Test manager initializes correctly."""
        manager = ExperimentManager()

        assert len(manager.list_experiments()) == 0

    def test_create_experiment(self):
        """Test creating an experiment."""
        manager = ExperimentManager()

        experiment = manager.create_experiment(
            name="Test Experiment",
            config=ExperimentConfig(
                name="Test Experiment",
                traffic_split=0.10
            )
        )

        assert experiment.name == "Test Experiment"
        assert experiment.status == ExperimentStatus.DRAFT
        assert experiment.experiment_id.startswith("exp_")

    def test_start_experiment(self):
        """Test starting an experiment."""
        manager = ExperimentManager()
        experiment = manager.create_experiment(name="Test")

        started = manager.start_experiment(experiment.experiment_id)

        assert started.status == ExperimentStatus.RUNNING
        assert started.started_at is not None
        assert manager.get_active_experiment() == started

    def test_stop_experiment(self):
        """Test stopping an experiment."""
        manager = ExperimentManager()
        experiment = manager.create_experiment(name="Test")
        manager.start_experiment(experiment.experiment_id)

        stopped = manager.stop_experiment(experiment.experiment_id, reason="manual_stop")

        assert stopped.status == ExperimentStatus.STOPPED
        assert stopped.ended_at is not None
        assert stopped.results["stop_reason"] == "manual_stop"

    def test_complete_experiment(self):
        """Test completing an experiment."""
        manager = ExperimentManager()
        experiment = manager.create_experiment(name="Test")
        manager.start_experiment(experiment.experiment_id)

        completed = manager.complete_experiment(
            experiment.experiment_id,
            winner="treatment",
            results={"p_value": 0.01, "improvement": 0.05}
        )

        assert completed.status == ExperimentStatus.COMPLETED
        assert completed.results["winner"] == "treatment"

    def test_pause_resume(self):
        """Test pausing and resuming experiment."""
        manager = ExperimentManager()
        experiment = manager.create_experiment(name="Test")
        manager.start_experiment(experiment.experiment_id)

        paused = manager.pause_experiment(experiment.experiment_id)
        assert paused.status == ExperimentStatus.PAUSED

        resumed = manager.resume_experiment(experiment.experiment_id)
        assert resumed.status == ExperimentStatus.RUNNING

    def test_list_experiments(self):
        """Test listing experiments."""
        manager = ExperimentManager()

        manager.create_experiment(name="Exp1")
        exp2 = manager.create_experiment(name="Exp2")
        manager.start_experiment(exp2.experiment_id)

        all_exps = manager.list_experiments()
        assert len(all_exps) == 2

        running_exps = manager.list_experiments(status=ExperimentStatus.RUNNING)
        assert len(running_exps) == 1

    def test_factory_function(self):
        """Test factory function."""
        manager = get_experiment_manager()
        assert isinstance(manager, ExperimentManager)


class TestMetricsCollector:
    """Tests for Metrics Collector."""

    def test_initialization(self):
        """Test collector initializes correctly."""
        collector = MetricsCollector()

        assert collector.experiment_id == "default"

    def test_record_accuracy(self):
        """Test recording accuracy metrics."""
        collector = MetricsCollector(experiment_id="test_exp")

        collector.record_accuracy("control", is_correct=True)
        collector.record_accuracy("control", is_correct=False)
        collector.record_accuracy("treatment", is_correct=True)

        control_metrics = collector.get_variant_metrics("control")
        treatment_metrics = collector.get_variant_metrics("treatment")

        assert control_metrics.accuracy() == 0.5  # 1/2
        assert treatment_metrics.accuracy() == 1.0  # 1/1

    def test_record_latency(self):
        """Test recording latency metrics."""
        collector = MetricsCollector()

        collector.record_latency("control", 100.0)
        collector.record_latency("control", 200.0)
        collector.record_latency("control", 300.0)

        metrics = collector.get_variant_metrics("control")

        assert metrics.latency_p50() == 200.0
        assert metrics.latency_p95() >= 200.0

    def test_record_satisfaction(self):
        """Test recording satisfaction scores."""
        collector = MetricsCollector()

        collector.record_satisfaction("control", 4.0)
        collector.record_satisfaction("control", 5.0)
        collector.record_satisfaction("control", 3.0)

        metrics = collector.get_variant_metrics("control")

        assert metrics.satisfaction() == 4.0  # Average

    def test_record_errors(self):
        """Test recording errors."""
        collector = MetricsCollector()

        collector.record_latency("control", 100.0)
        collector.record_latency("control", 200.0)
        collector.record_error("control", error_type="timeout")

        metrics = collector.get_variant_metrics("control")

        assert metrics.error_rate() == pytest.approx(1/3, rel=0.1)

    def test_record_resolution(self):
        """Test recording resolution/escalation."""
        collector = MetricsCollector()

        collector.record_resolution("control", resolved=True, escalated=False)
        collector.record_resolution("control", resolved=True, escalated=False)
        collector.record_resolution("control", resolved=False, escalated=True)

        metrics = collector.get_variant_metrics("control")

        assert metrics.resolution_rate() == pytest.approx(2/3, rel=0.1)
        assert metrics.escalation_rate() == pytest.approx(1/3, rel=0.1)

    def test_get_comparison(self):
        """Test getting comparison metrics."""
        collector = MetricsCollector()

        collector.record_accuracy("control", True)
        collector.record_accuracy("treatment", True)
        collector.record_accuracy("treatment", False)

        comparison = collector.get_comparison()

        assert "control" in comparison
        assert "treatment" in comparison
        assert comparison["control"]["accuracy"] == 1.0

    def test_reset(self):
        """Test resetting metrics."""
        collector = MetricsCollector()

        collector.record_accuracy("control", True)
        collector.reset()

        stats = collector.get_stats()
        assert stats["total_samples"] == 0

    def test_factory_function(self):
        """Test factory function."""
        collector = get_metrics_collector(experiment_id="test")
        assert collector.experiment_id == "test"


class TestStatisticalAnalyzer:
    """Tests for Statistical Analyzer."""

    def test_initialization(self):
        """Test analyzer initializes correctly."""
        analyzer = StatisticalAnalyzer()

        assert analyzer.confidence_level == ConfidenceLevel.P95

    def test_significant_result(self):
        """Test detecting significant difference."""
        analyzer = StatisticalAnalyzer()

        # Large difference: 90% vs 80% with good sample size
        result = analyzer.calculate_significance(
            control_successes=800,
            control_total=1000,
            treatment_successes=900,
            treatment_total=1000
        )

        assert result.is_significant
        assert result.p_value < 0.05
        assert result.improvement == pytest.approx(0.10, rel=0.01)  # 10% improvement

    def test_non_significant_result(self):
        """Test detecting non-significant difference."""
        analyzer = StatisticalAnalyzer()

        # Small difference with small sample
        result = analyzer.calculate_significance(
            control_successes=50,
            control_total=100,
            treatment_successes=52,
            treatment_total=100
        )

        assert not result.is_significant

    def test_negative_improvement(self):
        """Test when treatment performs worse."""
        analyzer = StatisticalAnalyzer()

        result = analyzer.calculate_significance(
            control_successes=90,
            control_total=100,
            treatment_successes=80,
            treatment_total=100
        )

        assert result.improvement < 0
        assert "worse" in result.recommendation.lower()

    def test_sample_size_calculation(self):
        """Test sample size calculation."""
        analyzer = StatisticalAnalyzer()

        n = analyzer.calculate_sample_size(
            baseline_rate=0.80,
            minimum_detectable_effect=0.05
        )

        assert n > 0
        assert isinstance(n, int)

    def test_confidence_interval(self):
        """Test confidence interval calculation."""
        analyzer = StatisticalAnalyzer()

        ci = analyzer.calculate_confidence_interval(
            mean=0.85,
            std_dev=0.05,
            sample_size=100
        )

        assert len(ci) == 2
        assert ci[0] < ci[1]
        assert ci[0] < 0.85 < ci[1]

    def test_determine_winner(self):
        """Test winner determination."""
        analyzer = StatisticalAnalyzer()

        winner1 = analyzer.determine_winner(0.80, 0.90, True)
        assert winner1 == "treatment"

        winner2 = analyzer.determine_winner(0.90, 0.80, True)
        assert winner2 == "control"

        winner3 = analyzer.determine_winner(0.85, 0.86, False)
        assert winner3 == "inconclusive"

    def test_different_confidence_levels(self):
        """Test different confidence levels."""
        analyzer_90 = StatisticalAnalyzer(confidence_level=ConfidenceLevel.P90)
        analyzer_99 = StatisticalAnalyzer(confidence_level=ConfidenceLevel.P99)

        # Higher confidence requires stronger evidence
        result_90 = analyzer_90.calculate_significance(80, 100, 90, 100)
        result_99 = analyzer_99.calculate_significance(80, 100, 90, 100)

        # P99 should be more conservative
        assert result_99.p_value >= result_90.p_value

    def test_factory_function(self):
        """Test factory function."""
        analyzer = get_statistical_analyzer(confidence_level=0.99)

        assert analyzer.confidence_level == ConfidenceLevel.P99


class TestABTestingIntegration:
    """Integration tests for A/B testing framework."""

    def test_full_experiment_workflow(self):
        """Test complete A/B testing workflow."""
        # 1. Create experiment
        manager = get_experiment_manager()
        experiment = manager.create_experiment(
            name="Accuracy Test",
            config=ExperimentConfig(
                name="Accuracy Test",
                traffic_split=0.10,
                min_sample_size=100
            )
        )

        # 2. Start experiment
        manager.start_experiment(experiment.experiment_id)

        # 3. Set up traffic splitter
        splitter = get_traffic_splitter(treatment_percentage=10.0)

        # 4. Set up metrics collector
        collector = get_metrics_collector(experiment.experiment_id)

        # 5. Simulate traffic and record metrics
        for i in range(100):
            assignment = splitter.assign_variant(f"user_{i}", "client_1", experiment.experiment_id)
            variant = assignment.variant.value

            # Simulate results (treatment slightly better)
            is_correct = True if variant == "treatment" else (i % 10 != 0)
            collector.record_accuracy(variant, is_correct)
            collector.record_latency(variant, 100.0 + i % 50)

        # 6. Analyze results
        analyzer = get_statistical_analyzer()
        control = collector.get_variant_metrics("control")
        treatment = collector.get_variant_metrics("treatment")

        result = analyzer.calculate_significance(
            control_successes=int(control.accuracy() * control.accuracy_count),
            control_total=control.accuracy_count,
            treatment_successes=int(treatment.accuracy() * treatment.accuracy_count),
            treatment_total=treatment.accuracy_count
        )

        # 7. Complete experiment
        winner = analyzer.determine_winner(
            control.accuracy(),
            treatment.accuracy(),
            result.is_significant
        )

        manager.complete_experiment(
            experiment.experiment_id,
            winner=winner,
            results=result.to_dict()
        )

        # Verify
        completed = manager.get_experiment(experiment.experiment_id)
        assert completed.status == ExperimentStatus.COMPLETED
        assert "winner" in completed.results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
