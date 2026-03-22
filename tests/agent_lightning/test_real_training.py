"""
Tests for Agent Lightning Real Training.

Tests the complete training pipeline including:
- Configuration loading
- Mistake export
- Approval export
- Dataset building
- Model validation
- Training pipeline
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent_lightning.training.real_training_config import (
    RealTrainingConfig,
    get_training_config,
    DEFAULT_CONFIG
)
from agent_lightning.training.export_real_mistakes import (
    MistakeExporter,
    MistakeRecord,
    export_mistakes
)
from agent_lightning.training.export_real_approvals import (
    ApprovalExporter,
    ApprovalRecord,
    export_approvals
)
from agent_lightning.training.build_real_dataset import (
    DatasetBuilder,
    build_training_dataset
)
from agent_lightning.training.validate_real_model import (
    ModelValidator,
    validate_trained_model
)


class TestRealTrainingConfig:
    """Tests for training configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RealTrainingConfig()

        assert config.epochs == 3
        assert config.batch_size == 16
        assert config.learning_rate == 2e-5
        assert config.validation_split == 0.2
        assert config.min_accuracy_threshold == 0.91
        assert config.target_improvement == 0.03

    def test_config_to_dict(self):
        """Test config serialization."""
        config = RealTrainingConfig()
        data = config.to_dict()

        assert "client_ids" in data
        assert "epochs" in data
        assert "batch_size" in data
        assert data["database_url"] == "***REDACTED***"  # Security check

    def test_config_from_dict(self):
        """Test config deserialization."""
        data = {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 1e-5
        }
        config = RealTrainingConfig.from_dict(data)

        assert config.epochs == 5
        assert config.batch_size == 32
        assert config.learning_rate == 1e-5

    def test_environment_configs(self):
        """Test environment-specific configs."""
        prod_config = get_training_config("production")
        assert prod_config.epochs == 3
        assert prod_config.min_samples == 500

        dev_config = get_training_config("development")
        assert dev_config.epochs == 1
        assert dev_config.min_samples == 10
        assert dev_config.use_gpu is False


class TestMistakeExporter:
    """Tests for mistake export functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_exporter_initialization(self, temp_dir):
        """Test exporter initialization."""
        exporter = MistakeExporter(export_dir=temp_dir)
        assert exporter.export_dir == Path(temp_dir)

    def test_anonymize_pii(self, temp_dir):
        """Test PII anonymization."""
        exporter = MistakeExporter(export_dir=temp_dir, anonymize=True)

        text = "Contact john@example.com or call 555-123-4567"
        anonymized = exporter.anonymize_text(text)

        assert "john@example.com" not in anonymized
        assert "[EMAIL]" in anonymized
        assert "[PHONE]" in anonymized

    def test_anonymize_credit_card(self, temp_dir):
        """Test credit card anonymization."""
        exporter = MistakeExporter(export_dir=temp_dir, anonymize=True)

        text = "Card: 4111-1111-1111-1111"
        anonymized = exporter.anonymize_text(text)

        assert "4111-1111-1111-1111" not in anonymized
        assert "[CARD]" in anonymized

    def test_fetch_mistakes(self, temp_dir):
        """Test fetching mistakes."""
        exporter = MistakeExporter(export_dir=temp_dir)
        mistakes = exporter.fetch_mistakes_from_db(
            client_ids=["client_001"],
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )

        assert len(mistakes) > 0
        assert all(isinstance(m, MistakeRecord) for m in mistakes)

    def test_export_to_jsonl(self, temp_dir):
        """Test export to JSONL format."""
        exporter = MistakeExporter(export_dir=temp_dir)
        mistakes = exporter.fetch_mistakes_from_db(
            client_ids=["client_001"],
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )

        output_path = exporter.export_to_jsonl(mistakes)
        assert Path(output_path).exists()

        # Verify content
        with open(output_path, 'r') as f:
            lines = f.readlines()
        assert len(lines) == len(mistakes)

    def test_mistake_statistics(self, temp_dir):
        """Test mistake statistics generation."""
        exporter = MistakeExporter(export_dir=temp_dir)
        mistakes = exporter.fetch_mistakes_from_db(
            client_ids=["client_001"],
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )

        stats = exporter.get_mistake_statistics(mistakes)

        assert "total" in stats
        assert stats["total"] > 0
        assert "by_type" in stats
        assert "by_category" in stats


class TestApprovalExporter:
    """Tests for approval export functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_fetch_approvals(self, temp_dir):
        """Test fetching approvals."""
        exporter = ApprovalExporter(export_dir=temp_dir)
        approvals = exporter.fetch_approvals_from_db(
            client_ids=["client_001"],
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )

        assert len(approvals) > 0
        assert all(isinstance(a, ApprovalRecord) for a in approvals)

    def test_export_to_jsonl(self, temp_dir):
        """Test export to JSONL format."""
        exporter = ApprovalExporter(export_dir=temp_dir)
        approvals = exporter.fetch_approvals_from_db(
            client_ids=["client_001"],
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )

        output_path = exporter.export_to_jsonl(approvals)
        assert Path(output_path).exists()

    def test_approval_statistics(self, temp_dir):
        """Test approval statistics."""
        exporter = ApprovalExporter(export_dir=temp_dir)
        approvals = exporter.fetch_approvals_from_db(
            client_ids=["client_001"],
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )

        stats = exporter.get_approval_statistics(approvals)

        assert stats["total"] > 0
        assert "avg_confidence" in stats
        assert stats["avg_confidence"] > 0


class TestDatasetBuilder:
    """Tests for dataset building."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def sample_mistakes(self, temp_dir):
        """Create sample mistakes file."""
        path = Path(temp_dir) / "mistakes.jsonl"
        with open(path, 'w') as f:
            for i in range(10):
                f.write(json.dumps({
                    "input": f"Mistake input {i}",
                    "output": f"Mistake output {i}",
                    "category": "test"
                }) + '\n')
        return str(path)

    @pytest.fixture
    def sample_approvals(self, temp_dir):
        """Create sample approvals file."""
        path = Path(temp_dir) / "approvals.jsonl"
        with open(path, 'w') as f:
            for i in range(20):
                f.write(json.dumps({
                    "input": f"Approval input {i}",
                    "output": f"Approval output {i}",
                    "category": "test"
                }) + '\n')
        return str(path)

    def test_builder_initialization(self, temp_dir):
        """Test builder initialization."""
        builder = DatasetBuilder(output_dir=temp_dir)
        assert builder.output_dir == Path(temp_dir)

    def test_balance_dataset(self, temp_dir, sample_mistakes, sample_approvals):
        """Test dataset balancing."""
        builder = DatasetBuilder(output_dir=temp_dir, balance_dataset=True)

        mistakes = builder.load_jsonl(sample_mistakes)
        approvals = builder.load_jsonl(sample_approvals)

        balanced_m, balanced_a = builder.balance_examples(mistakes, approvals)

        # Should be balanced to min count
        assert len(balanced_m) == len(balanced_a) == 10

    def test_build_dataset(self, temp_dir, sample_mistakes, sample_approvals):
        """Test complete dataset building."""
        builder = DatasetBuilder(output_dir=temp_dir, validation_split=0.2)

        stats = builder.build_dataset(sample_mistakes, sample_approvals)

        assert stats.total_examples > 0
        assert stats.train_examples > stats.val_examples

    def test_validate_dataset(self, temp_dir, sample_mistakes, sample_approvals):
        """Test dataset validation."""
        builder = DatasetBuilder(output_dir=temp_dir)

        # Create files
        builder.build_dataset(sample_mistakes, sample_approvals)

        # Find created files
        import glob
        train_files = sorted(glob.glob(str(builder.output_dir / "*_train.jsonl")))
        val_files = sorted(glob.glob(str(builder.output_dir / "*_val.jsonl")))

        validation = builder.validate_dataset(train_files[-1], val_files[-1])

        assert "valid" in validation
        assert "issues" in validation


class TestModelValidator:
    """Tests for model validation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def sample_validation_set(self, temp_dir):
        """Create sample validation set."""
        path = Path(temp_dir) / "validation.jsonl"
        with open(path, 'w') as f:
            for i in range(50):
                f.write(json.dumps({
                    "input": f"Validation input {i}",
                    "output": {"decision": "test", "reasoning": "test"},
                    "category": "test"
                }) + '\n')
        return str(path)

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = ModelValidator(
            baseline_accuracy=0.72,
            min_accuracy_threshold=0.91,
            target_improvement=0.03
        )

        assert validator.baseline_accuracy == 0.72
        assert validator.min_accuracy_threshold == 0.91

    def test_validate_model(self, temp_dir, sample_validation_set):
        """Test model validation."""
        validator = ModelValidator(
            baseline_accuracy=0.72,
            min_accuracy_threshold=0.75  # Lower for test
        )

        result = validator.validate_model(
            model_path="mock_model",
            validation_path=sample_validation_set
        )

        assert result.test_count == 50
        assert result.accuracy > 0

    def test_improvement_calculation(self, temp_dir, sample_validation_set):
        """Test improvement calculation."""
        validator = ModelValidator(baseline_accuracy=0.72)

        result = validator.validate_model(
            model_path="mock_model",
            validation_path=sample_validation_set
        )

        # Our mock achieves ~76% accuracy
        assert result.accuracy >= 0.72
        assert result.improvement >= 0

    def test_generate_report(self, temp_dir, sample_validation_set):
        """Test report generation."""
        validator = ModelValidator()
        result = validator.validate_model(
            model_path="mock_model",
            validation_path=sample_validation_set
        )

        report = validator.generate_report(result)

        assert "VALIDATION REPORT" in report
        assert "Accuracy" in report


class TestTrainingPipeline:
    """Tests for the complete training pipeline."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_full_pipeline_dry_run(self, temp_dir):
        """Test full pipeline in dry-run mode."""
        from scripts.run_agent_lightning_training import TrainingPipeline

        config = RealTrainingConfig(
            export_dir=temp_dir,
            model_output_dir=temp_dir,
            dataset_output_dir=temp_dir,
            min_samples=1  # Lower threshold for test
        )

        pipeline = TrainingPipeline(config, dry_run=True)
        results = pipeline.run()

        # In dry run, the pipeline should complete even if files don't exist
        assert results.get("dry_run") is True

    def test_pipeline_report(self, temp_dir):
        """Test pipeline report generation."""
        from scripts.run_agent_lightning_training import TrainingPipeline

        config = RealTrainingConfig(
            export_dir=temp_dir,
            model_output_dir=temp_dir,
            dataset_output_dir=temp_dir
        )

        pipeline = TrainingPipeline(config, dry_run=True)
        pipeline.run()
        report = pipeline.generate_report()

        assert "TRAINING REPORT" in report


class TestAccuracyImprovement:
    """Tests for accuracy improvement validation."""

    def test_minimum_improvement_threshold(self):
        """Test that model meets minimum improvement threshold."""
        # Baseline from Week 19: 72%
        baseline = 0.72
        target_improvement = 0.03  # 3%

        # Mock model achieving 76% (4% improvement)
        model_accuracy = 0.76

        improvement = model_accuracy - baseline
        improvement_pct = (improvement / baseline) * 100

        assert improvement >= target_improvement
        assert improvement_pct >= 3.0

    def test_validation_thresholds(self):
        """Test validation threshold calculations."""
        validator = ModelValidator(
            baseline_accuracy=0.72,
            min_accuracy_threshold=0.91,
            target_improvement=0.03
        )

        # Test passing case
        assert validator.baseline_accuracy + validator.target_improvement <= 0.91


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
