"""
Tests for Agent Lightning v2 Training System.

CRITICAL: All tests verify training works without client data leakage.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
import os
import tempfile

from agent_lightning.v2.training_executor import (
    TrainingExecutor,
    TrainingStatus,
    TrainingCheckpoint,
    TrainingMetrics,
    execute_training_pipeline,
)
from agent_lightning.v2.collective_trainer import (
    CollectiveTrainer,
    CollectiveTrainingConfig,
    TrainingProgress,
    IndustryBatch,
    train_on_collective_data,
)
from agent_lightning.v2.hyperparameter_optimizer import (
    HyperparameterOptimizer,
    HyperparameterConfig,
    HyperparameterRange,
    OptimizationResult,
    OptimizationStrategy,
    optimize_hyperparameters,
)
from agent_lightning.v2.training_monitor import (
    TrainingMonitor,
    TrainingAlert,
    ProgressUpdate,
    AlertLevel,
)
from agent_lightning.v2.training_results import (
    TrainingResults,
    EpochMetrics,
    IndustryMetrics,
    ModelStatus,
    create_training_results,
)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def temp_output_dir():
    """Create temporary output directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def training_executor(temp_output_dir):
    """Create a training executor"""
    return TrainingExecutor(
        model_path="models/base",
        output_dir=temp_output_dir,
    )


@pytest.fixture
def collective_trainer():
    """Create a collective trainer"""
    return CollectiveTrainer()


@pytest.fixture
def hyperparameter_optimizer():
    """Create a hyperparameter optimizer"""
    return HyperparameterOptimizer(n_trials=3)


@pytest.fixture
def training_monitor(temp_output_dir):
    """Create a training monitor"""
    return TrainingMonitor(output_dir=temp_output_dir)


# ==============================================================================
# Training Executor Tests
# ==============================================================================

class TestTrainingExecutor:
    """Tests for TrainingExecutor"""

    def test_executor_initialization(self, training_executor):
        """Test executor initializes correctly"""
        assert training_executor.model_path == "models/base"
        assert training_executor.config["num_epochs"] == 3
        assert training_executor.config["batch_size"] == 8
        assert training_executor._status == TrainingStatus.PENDING

    def test_load_collective_dataset(self, training_executor):
        """Test loading collective intelligence dataset"""
        dataset_info = training_executor.load_collective_dataset()

        assert dataset_info["total_examples"] == 578
        assert dataset_info["privacy_preserved"] is True
        assert dataset_info["no_client_data"] is True
        assert len(dataset_info["industries"]) == 5

    def test_execute_training(self, training_executor):
        """Test executing training pipeline"""
        results = training_executor.execute_training()

        assert training_executor._status == TrainingStatus.COMPLETED
        assert results["status"] == "completed"
        assert results["total_steps"] > 0
        assert results["best_accuracy"] > 0

    def test_checkpoint_saving(self, training_executor):
        """Test checkpoint saving during training"""
        results = training_executor.execute_training()

        checkpoints = training_executor.get_checkpoints()
        assert len(checkpoints) > 0

        checkpoint = checkpoints[0]
        assert checkpoint.checkpoint_id.startswith("ckpt_")
        assert checkpoint.accuracy > 0

    def test_training_interruption(self, training_executor):
        """Test graceful training interruption"""
        training_executor.request_interruption()
        assert training_executor._interruption_requested is True

    def test_get_status(self, training_executor):
        """Test getting training status"""
        status = training_executor.get_status()

        assert "status" in status
        assert "current_step" in status
        assert "best_accuracy" in status

    def test_metrics_history(self, training_executor):
        """Test metrics history tracking"""
        training_executor.execute_training()

        history = training_executor.get_metrics_history()
        assert len(history) > 0

        metrics = history[0]
        assert isinstance(metrics, TrainingMetrics)
        assert metrics.loss > 0
        assert 0 <= metrics.accuracy <= 1

    def test_no_client_data_in_output(self, training_executor):
        """CRITICAL: Verify no client data in training output"""
        results = training_executor.execute_training()

        results_str = str(results).lower()

        # No sensitive patterns
        assert "email" not in results_str
        assert "phone" not in results_str
        assert "ssn" not in results_str
        assert "patient_id" not in results_str


class TestExecuteTrainingPipelineFunction:
    """Tests for convenience function"""

    def test_execute_training_pipeline_function(self, temp_output_dir):
        """Test the convenience pipeline function"""
        results = execute_training_pipeline(
            model_path="models/base",
            output_dir=temp_output_dir,
        )

        assert "status" in results
        assert "total_steps" in results


# ==============================================================================
# Collective Trainer Tests
# ==============================================================================

class TestCollectiveTrainer:
    """Tests for CollectiveTrainer"""

    def test_trainer_initialization(self, collective_trainer):
        """Test trainer initializes correctly"""
        assert len(collective_trainer.INDUSTRIES) == 5
        assert collective_trainer.config.target_accuracy == 0.77

    def test_prepare_industry_batches(self, collective_trainer):
        """Test preparing industry batches"""
        batches = collective_trainer.prepare_industry_batches()

        assert len(batches) == 5
        for batch in batches:
            assert isinstance(batch, IndustryBatch)
            assert batch.privacy_verified is True
            assert len(batch.examples) > 0

    def test_train(self, collective_trainer):
        """Test collective training"""
        results = collective_trainer.train(num_epochs=1)

        assert results["total_steps"] > 0
        assert results["final_accuracy"] > 0
        assert "industry_accuracies" in results

    def test_get_industry_performance(self, collective_trainer):
        """Test getting industry performance"""
        collective_trainer.train(num_epochs=1)

        performance = collective_trainer.get_industry_performance()

        assert len(performance) == 5
        for industry, metrics in performance.items():
            assert "accuracy" in metrics
            assert "improvement" in metrics

    def test_cross_client_generalization(self, collective_trainer):
        """Test cross-client generalization assessment"""
        collective_trainer.train(num_epochs=1)

        generalization = collective_trainer.get_cross_client_generalization()

        assert "average_accuracy" in generalization
        assert "generalization_score" in generalization
        assert "best_industry" in generalization
        assert "worst_industry" in generalization

    def test_privacy_validation(self, collective_trainer):
        """CRITICAL: Test privacy is preserved"""
        privacy = collective_trainer.validate_privacy()

        assert privacy["privacy_preserved"] is True
        assert privacy["no_client_data_exposed"] is True
        assert privacy["collective_intelligence_safe"] is True

    def test_industry_balancing(self, collective_trainer):
        """Test industry balancing"""
        config = CollectiveTrainingConfig(
            balance_industries=True,
            industry_weights={
                "ecommerce": 0.25,
                "saas": 0.25,
                "healthcare": 0.20,
                "logistics": 0.15,
                "fintech": 0.15,
            }
        )
        trainer = CollectiveTrainer(config=config)

        batches = trainer.prepare_industry_batches()

        # Check weights are applied
        total_examples = sum(len(b.examples) for b in batches)
        for batch in batches:
            expected_ratio = config.industry_weights[batch.industry]
            actual_ratio = len(batch.examples) / total_examples
            # Allow some variance due to rounding
            assert abs(actual_ratio - expected_ratio) < 0.05


class TestTrainOnCollectiveDataFunction:
    """Tests for convenience function"""

    def test_train_on_collective_data_function(self):
        """Test the convenience training function"""
        results = train_on_collective_data(num_epochs=1)

        assert "final_accuracy" in results
        assert "industry_accuracies" in results


# ==============================================================================
# Hyperparameter Optimizer Tests
# ==============================================================================

class TestHyperparameterOptimizer:
    """Tests for HyperparameterOptimizer"""

    def test_optimizer_initialization(self, hyperparameter_optimizer):
        """Test optimizer initializes correctly"""
        assert hyperparameter_optimizer.n_trials == 3
        assert hyperparameter_optimizer.target_accuracy == 0.77

    def test_optimize(self, hyperparameter_optimizer):
        """Test hyperparameter optimization"""
        best_config, best_accuracy = hyperparameter_optimizer.optimize()

        assert isinstance(best_config, HyperparameterConfig)
        assert best_accuracy > 0
        assert best_config.learning_rate > 0

    def test_get_learning_rate_schedule(self, hyperparameter_optimizer):
        """Test learning rate schedule generation"""
        # Run optimization first
        hyperparameter_optimizer.optimize()

        schedule = hyperparameter_optimizer.get_learning_rate_schedule(
            total_steps=100,
            warmup_ratio=0.1,
        )

        assert len(schedule) == 100
        # Check warmup
        assert schedule[0] < schedule[10]
        # Check decay
        assert schedule[-1] < schedule[50]

    def test_suggest_batch_size(self, hyperparameter_optimizer):
        """Test batch size suggestion"""
        batch_size = hyperparameter_optimizer.suggest_batch_size(
            available_memory_mb=16000,
            model_size_mb=1500,
        )

        assert 1 <= batch_size <= 32
        # Should be power of 2
        assert batch_size & (batch_size - 1) == 0  # Power of 2 check

    def test_get_early_stopping_config(self, hyperparameter_optimizer):
        """Test early stopping config"""
        config = hyperparameter_optimizer.get_early_stopping_config()

        assert "patience" in config
        assert "min_delta" in config
        assert "restore_best_weights" in config

    def test_get_trials(self, hyperparameter_optimizer):
        """Test getting optimization trials"""
        hyperparameter_optimizer.optimize()

        trials = hyperparameter_optimizer.get_trials()
        assert len(trials) > 0

        trial = trials[0]
        assert isinstance(trial, OptimizationResult)
        assert trial.accuracy > 0

    def test_random_vs_grid_search(self):
        """Test random vs grid search strategies"""
        random_optimizer = HyperparameterOptimizer(
            strategy=OptimizationStrategy.RANDOM_SEARCH,
            n_trials=3,
        )
        grid_optimizer = HyperparameterOptimizer(
            strategy=OptimizationStrategy.GRID_SEARCH,
            n_trials=3,
        )

        random_config, _ = random_optimizer.optimize()
        grid_config, _ = grid_optimizer.optimize()

        assert isinstance(random_config, HyperparameterConfig)
        assert isinstance(grid_config, HyperparameterConfig)


class TestOptimizeHyperparametersFunction:
    """Tests for convenience function"""

    def test_optimize_hyperparameters_function(self):
        """Test the convenience optimization function"""
        config, accuracy = optimize_hyperparameters(n_trials=3)

        assert isinstance(config, HyperparameterConfig)
        assert accuracy > 0


# ==============================================================================
# Training Monitor Tests
# ==============================================================================

class TestTrainingMonitor:
    """Tests for TrainingMonitor"""

    def test_monitor_initialization(self, training_monitor):
        """Test monitor initializes correctly"""
        assert training_monitor._start_time is None
        assert len(training_monitor._loss_history) == 0

    def test_start_stop_monitoring(self, training_monitor):
        """Test starting and stopping monitoring"""
        training_monitor.start_monitoring()
        assert training_monitor._start_time is not None

        summary = training_monitor.stop_monitoring()
        assert "duration_seconds" in summary

    def test_record_step(self, training_monitor):
        """Test recording a training step"""
        training_monitor.start_monitoring()

        update = training_monitor.record_step(
            step=1,
            epoch=0,
            loss=1.5,
            accuracy=0.75,
            learning_rate=2e-5,
            gpu_memory_mb=5000,
        )

        assert isinstance(update, ProgressUpdate)
        assert update.step == 1
        assert update.current_loss == 1.5
        assert update.current_accuracy == 0.75

    def test_get_loss_curve(self, training_monitor):
        """Test getting loss curve"""
        training_monitor.start_monitoring()

        for i in range(5):
            training_monitor.record_step(
                step=i,
                epoch=0,
                loss=2.0 - i * 0.1,
                accuracy=0.72 + i * 0.01,
            )

        curve = training_monitor.get_loss_curve()
        assert len(curve) == 5

    def test_get_accuracy_curve(self, training_monitor):
        """Test getting accuracy curve"""
        training_monitor.start_monitoring()

        for i in range(5):
            training_monitor.record_step(
                step=i,
                epoch=0,
                loss=1.0,
                accuracy=0.72 + i * 0.01,
            )

        curve = training_monitor.get_accuracy_curve()
        assert len(curve) == 5

    def test_alert_generation(self, training_monitor):
        """Test alert generation for issues"""
        training_monitor.start_monitoring()

        # Record initial metrics
        training_monitor.record_step(
            step=1,
            epoch=0,
            loss=1.0,
            accuracy=0.75,
        )

        # Record a loss spike
        training_monitor.record_step(
            step=2,
            epoch=0,
            loss=2.0,  # Big spike
            accuracy=0.75,
        )

        alerts = training_monitor.get_alerts()
        assert len(alerts) > 0

        alert = alerts[0]
        assert isinstance(alert, TrainingAlert)
        assert alert.level in [AlertLevel.WARNING, AlertLevel.ERROR]


# ==============================================================================
# Training Results Tests
# ==============================================================================

class TestTrainingResults:
    """Tests for TrainingResults"""

    def test_results_creation(self):
        """Test creating training results"""
        results = create_training_results(
            training_id="test_001",
            final_accuracy=0.78,
            total_epochs=3,
            total_steps=500,
            training_time_seconds=60.0,
        )

        assert results.training_id == "test_001"
        assert results.final_accuracy == 0.78
        assert results.target_met is True  # 78% > 77%

    def test_results_to_dict(self):
        """Test converting results to dictionary"""
        results = create_training_results(
            training_id="test_001",
            final_accuracy=0.78,
            total_epochs=3,
            total_steps=500,
            training_time_seconds=60.0,
        )

        data = results.to_dict()

        assert "training_id" in data
        assert "final_accuracy" in data
        assert "industry_metrics" in data

    def test_results_save_load(self, temp_output_dir):
        """Test saving and loading results"""
        results = create_training_results(
            training_id="test_001",
            final_accuracy=0.78,
            total_epochs=3,
            total_steps=500,
            training_time_seconds=60.0,
        )

        # Save
        output_path = os.path.join(temp_output_dir, "results.json")
        results.save(output_path)

        # Load
        loaded = TrainingResults.load(output_path)

        assert loaded.training_id == results.training_id
        assert loaded.final_accuracy == results.final_accuracy

    def test_get_summary(self):
        """Test getting results summary"""
        results = create_training_results(
            training_id="test_001",
            final_accuracy=0.78,
            total_epochs=3,
            total_steps=500,
            training_time_seconds=60.0,
        )

        summary = results.get_summary()

        assert "accuracy_improvement" in summary
        assert "target_met" in summary

    def test_compare_to_baseline(self):
        """Test comparing to baseline"""
        results = create_training_results(
            training_id="test_001",
            final_accuracy=0.78,
            total_epochs=3,
            total_steps=500,
            training_time_seconds=60.0,
        )

        comparison = results.compare_to_baseline()

        assert comparison["baseline_accuracy"] == 0.72
        assert comparison["final_accuracy"] == 0.78
        assert comparison["absolute_improvement"] > 0

    def test_industry_metrics(self):
        """Test industry metrics"""
        results = create_training_results(
            training_id="test_001",
            final_accuracy=0.78,
            total_epochs=3,
            total_steps=500,
            training_time_seconds=60.0,
        )

        industry_summary = results.get_industry_summary()

        assert len(industry_summary) == 5
        for industry, metrics in industry_summary.items():
            assert "baseline" in metrics
            assert "final" in metrics
            assert "improvement" in metrics


class TestCreateTrainingResultsFunction:
    """Tests for convenience function"""

    def test_create_training_results_function(self):
        """Test the convenience results function"""
        results = create_training_results(
            training_id="test_001",
            final_accuracy=0.78,
            total_epochs=3,
            total_steps=500,
            training_time_seconds=60.0,
        )

        assert isinstance(results, TrainingResults)
        assert results.training_id == "test_001"


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestTrainingIntegration:
    """Integration tests for complete training workflow"""

    def test_full_training_workflow(self, temp_output_dir):
        """Test complete training workflow"""
        # 1. Initialize components
        executor = TrainingExecutor(
            model_path="models/base",
            output_dir=temp_output_dir,
        )
        monitor = TrainingMonitor(output_dir=temp_output_dir)

        # 2. Start monitoring
        monitor.start_monitoring()

        # 3. Execute training with monitoring
        def on_step(metrics):
            monitor.record_step(
                step=metrics.step,
                epoch=metrics.epoch,
                loss=metrics.loss,
                accuracy=metrics.accuracy,
                learning_rate=metrics.learning_rate,
            )

        results = executor.execute_training(on_step=on_step)

        # 4. Stop monitoring
        monitor_summary = monitor.stop_monitoring()

        # 5. Compile results
        training_results = create_training_results(
            training_id="integration_test",
            final_accuracy=results["best_accuracy"],
            total_epochs=results["total_epochs"],
            total_steps=results["total_steps"],
            training_time_seconds=monitor_summary["duration_seconds"],
        )

        assert training_results.final_accuracy > 0
        assert len(monitor.get_loss_curve()) > 0

    def test_privacy_throughout_workflow(self, temp_output_dir):
        """CRITICAL: Verify privacy throughout workflow"""
        # Train with collective intelligence
        trainer = CollectiveTrainer()
        results = trainer.train(num_epochs=1)

        # Validate privacy
        privacy = trainer.validate_privacy()

        # Check all privacy flags
        assert privacy["privacy_preserved"] is True
        assert privacy["no_client_data_exposed"] is True
        assert privacy["data_minimized"] is True
        assert privacy["patterns_only"] is True
        assert privacy["collective_intelligence_safe"] is True

        # Check results don't contain client data
        results_str = str(results).lower()
        sensitive_patterns = [
            "client_001", "client_002", "client_003",
            "email", "phone", "ssn", "patient_id"
        ]

        for pattern in sensitive_patterns:
            assert pattern not in results_str


# ==============================================================================
# Run Tests
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
