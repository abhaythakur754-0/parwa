"""
Unit Tests for Agent Lightning Training Pipeline.

Tests for:
- Trainer initialization and configuration
- Unsloth optimizer settings
- Model deployment
- Model rollback

CRITICAL Tests:
- Trainer initializes correctly with Colab FREE config
- Unsloth optimizer applies correctly
- Model deployed to registry
- Rollback restores previous version
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import os
import json
import tempfile
import asyncio


# Import the modules under test
from agent_lightning.training.trainer import (
    Trainer,
    TrainingConfig,
    TrainingStatus,
    TrainingMetrics,
    get_trainer
)
from agent_lightning.training.unsloth_optimizer import (
    UnslothOptimizer,
    UnslothConfig,
    OptimizationLevel,
    MemoryProfile,
    get_unsloth_optimizer
)
from agent_lightning.deployment.deploy_model import (
    ModelDeployer,
    DeploymentStatus,
    Environment,
    get_model_deployer
)
from agent_lightning.deployment.rollback import (
    ModelRollback,
    RollbackStatus,
    get_model_rollback
)


class TestTrainer:
    """Tests for Agent Lightning Trainer."""

    def test_trainer_initializes_correctly(self):
        """Test that trainer initializes with default config."""
        trainer = Trainer()

        assert trainer.status == TrainingStatus.PENDING
        assert trainer.config is not None
        assert trainer.config.model_name == "unsloth/mistral-7b-instruct-v0.2"

    def test_trainer_with_custom_config(self):
        """Test trainer with custom configuration."""
        custom_config = TrainingConfig(
            model_name="custom-model",
            epochs=5,
            batch_size=4,
            learning_rate=1e-4
        )

        trainer = Trainer(config=custom_config)

        assert trainer.config.model_name == "custom-model"
        assert trainer.config.epochs == 5
        assert trainer.config.batch_size == 4
        assert trainer.config.learning_rate == 1e-4

    def test_get_training_config(self):
        """Test getting training configuration."""
        trainer = Trainer()
        config = trainer.get_training_config()

        assert "model_name" in config
        assert "epochs" in config
        assert "batch_size" in config
        assert "lora_r" in config
        assert config["colab_free_optimized"] is True

    def test_colab_free_config(self):
        """Test Colab FREE tier configuration is optimized."""
        trainer = Trainer()
        config = trainer.get_training_config()

        # Verify Colab FREE optimizations
        assert config["load_in_4bit"] is True  # Memory efficient
        assert config["gradient_checkpointing"] is True
        assert config["batch_size"] <= 4  # Conservative batch size
        assert config["max_seq_length"] <= 4096  # Manageable context

    @pytest.mark.asyncio
    async def test_train_validates_dataset(self):
        """Test that trainer validates dataset format."""
        trainer = Trainer()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            # Write valid JSONL entries
            for i in range(5):
                json.dump({"instruction": f"test {i}", "output": f"result {i}"}, f)
                f.write("\n")
            dataset_path = f.name

        try:
            result = await trainer.train(dataset_path)

            assert result["success"] is True
            assert "accuracy" in result
            assert "model_path" in result

        finally:
            os.unlink(dataset_path)

    @pytest.mark.asyncio
    async def test_train_handles_missing_dataset(self):
        """Test that trainer handles missing dataset."""
        trainer = Trainer()

        result = await trainer.train("/nonexistent/path/dataset.jsonl")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_evaluate_model(self):
        """Test model evaluation."""
        trainer = Trainer()

        result = await trainer.evaluate("/models/test_model")

        assert result["success"] is True
        assert "metrics" in result
        assert "accuracy" in result["metrics"]
        assert "passes_threshold" in result

    @pytest.mark.asyncio
    async def test_evaluate_accuracy_threshold(self):
        """Test that evaluation checks 90% threshold."""
        trainer = Trainer()

        result = await trainer.evaluate("/models/test_model")

        # The simulated accuracy is 0.92, should pass threshold
        assert result["metrics"]["accuracy"] >= 0.90
        assert result["passes_threshold"] is True

    def test_get_status(self):
        """Test getting trainer status."""
        trainer = Trainer()
        status = trainer.get_status()

        assert "status" in status
        assert "config" in status
        assert "metrics" in status


class TestUnslothOptimizer:
    """Tests for Unsloth Optimizer."""

    def test_optimizer_initializes_correctly(self):
        """Test that optimizer initializes with default level."""
        optimizer = UnslothOptimizer()

        assert optimizer.optimization_level == OptimizationLevel.COLAB_FREE
        assert optimizer._config.load_in_4bit is True

    def test_optimizer_with_custom_level(self):
        """Test optimizer with custom optimization level."""
        optimizer = UnslothOptimizer(
            optimization_level=OptimizationLevel.AGGRESSIVE
        )

        assert optimizer.optimization_level == OptimizationLevel.AGGRESSIVE

    def test_apply_optimizations(self):
        """Test applying optimizations to model config."""
        optimizer = UnslothOptimizer()
        model_config = {"model_name": "test-model"}

        optimized = optimizer.apply_optimizations(model_config)

        assert optimized["load_in_4bit"] is True
        assert optimized["gradient_checkpointing"] is True
        assert "lora_r" in optimized
        assert "target_modules" in optimized

    def test_get_memory_footprint(self):
        """Test memory footprint calculation."""
        optimizer = UnslothOptimizer()

        footprint = optimizer.get_memory_footprint()

        assert footprint > 0
        assert footprint < 16  # Should fit in Colab FREE tier

    def test_optimize_for_colab_free(self):
        """Test Colab FREE optimization settings."""
        optimizer = UnslothOptimizer()

        config = optimizer.optimize_for_colab_free()

        assert config["load_in_4bit"] is True
        assert config["gradient_checkpointing"] is True
        assert config["optim"] == "adamw_8bit"
        assert config["batch_size"] == 2
        assert config["colab_free_optimized"] is True

    def test_check_memory_available(self):
        """Test memory availability check."""
        optimizer = UnslothOptimizer()
        optimizer.get_memory_footprint()  # Calculate first

        result = optimizer.check_memory_available(10.0)

        assert "fits" in result
        assert "recommendation" in result

    def test_get_recommended_batch_size(self):
        """Test batch size recommendations."""
        optimizer = UnslothOptimizer()

        # Short sequence - should allow larger batch
        assert optimizer.get_recommended_batch_size(1024) == 4

        # Medium sequence
        assert optimizer.get_recommended_batch_size(2048) == 2

        # Long sequence
        assert optimizer.get_recommended_batch_size(4096) == 1

    def test_get_memory_profile(self):
        """Test getting detailed memory profile."""
        optimizer = UnslothOptimizer()

        profile = optimizer.get_memory_profile()

        assert isinstance(profile, MemoryProfile)
        assert profile.total_vram_gb > 0
        assert "model_memory_gb" in profile.to_dict()

    def test_get_status(self):
        """Test getting optimizer status."""
        optimizer = UnslothOptimizer()

        status = optimizer.get_status()

        assert "optimization_level" in status
        assert "config" in status
        assert "memory_profile" in status
        assert status["colab_free_compatible"] is True


class TestModelDeployer:
    """Tests for Model Deployer."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_deploy_model(self, temp_registry):
        """Test deploying a model."""
        deployer = ModelDeployer(registry_path=temp_registry)

        result = await deployer.deploy(
            model_path="/models/test",
            version="v1.0.0",
            accuracy=0.92,
            environment=Environment.STAGING
        )

        assert result["success"] is True
        assert result["model_version"] == "v1.0.0"
        assert result["status"] == DeploymentStatus.DEPLOYED.value

    @pytest.mark.asyncio
    async def test_deploy_blocks_low_accuracy(self, temp_registry):
        """CRITICAL: Test that deployment blocks at <90% accuracy."""
        deployer = ModelDeployer(registry_path=temp_registry)

        result = await deployer.deploy(
            model_path="/models/test",
            version="v1.0.0",
            accuracy=0.85,  # Below threshold
            environment=Environment.STAGING
        )

        assert result["success"] is False
        assert "below threshold" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_deploy_allows_high_accuracy(self, temp_registry):
        """CRITICAL: Test that deployment allows at 91%+ accuracy."""
        deployer = ModelDeployer(registry_path=temp_registry)

        result = await deployer.deploy(
            model_path="/models/test",
            version="v1.0.0",
            accuracy=0.91,  # Above threshold
            environment=Environment.STAGING
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_verify_deployment(self, temp_registry):
        """Test deployment verification."""
        deployer = ModelDeployer(registry_path=temp_registry)

        # Deploy first
        await deployer.deploy(
            model_path="/models/test",
            version="v1.0.0",
            accuracy=0.92,
            environment=Environment.STAGING
        )

        # Verify
        is_valid = await deployer.verify_deployment("v1.0.0")

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_promote_to_production(self, temp_registry):
        """Test promoting staging to production."""
        deployer = ModelDeployer(registry_path=temp_registry)

        # Deploy to staging
        await deployer.deploy(
            model_path="/models/test",
            version="v1.0.0",
            accuracy=0.92,
            environment=Environment.STAGING
        )

        # Promote to production
        result = await deployer.promote_to_production("v1.0.0")

        assert result["success"] is True
        assert deployer.get_current_model(Environment.PRODUCTION) == "v1.0.0"

    def test_get_deployment_history(self, temp_registry):
        """Test getting deployment history."""
        deployer = ModelDeployer(registry_path=temp_registry)

        history = deployer.get_deployment_history()

        assert isinstance(history, list)

    def test_get_status(self, temp_registry):
        """Test getting deployer status."""
        deployer = ModelDeployer(registry_path=temp_registry)

        status = deployer.get_status()

        assert "registry_path" in status
        assert "accuracy_threshold" in status
        assert status["accuracy_threshold"] == 0.90


class TestModelRollback:
    """Tests for Model Rollback."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_rollback_to_version(self, temp_registry):
        """Test rolling back to a specific version."""
        rollback = ModelRollback(registry_path=temp_registry)

        # Set up versions
        rollback.set_current_version("v2.0.0")

        # Create mock version directories
        v1_path = os.path.join(temp_registry, "v1.0.0")
        os.makedirs(v1_path, exist_ok=True)
        with open(os.path.join(v1_path, "metadata.json"), "w") as f:
            json.dump({"version": "v1.0.0"}, f)

        result = await rollback.rollback("v1.0.0", reason="Test rollback")

        assert result["success"] is True
        assert result["to_version"] == "v1.0.0"

    @pytest.mark.asyncio
    async def test_get_previous_version(self, temp_registry):
        """Test getting previous stable version."""
        rollback = ModelRollback(registry_path=temp_registry)

        # Set up history
        rollback.set_current_version("v2.0.0")
        rollback.set_current_version("v3.0.0")

        result = await rollback.get_previous_version()

        assert result["success"] is True
        assert result["previous_version"] == "v2.0.0"

    @pytest.mark.asyncio
    async def test_verify_rollback(self, temp_registry):
        """Test verifying rollback success."""
        rollback = ModelRollback(registry_path=temp_registry)

        # Set up version
        rollback.set_current_version("v1.0.0")

        v1_path = os.path.join(temp_registry, "v1.0.0")
        os.makedirs(v1_path, exist_ok=True)
        with open(os.path.join(v1_path, "metadata.json"), "w") as f:
            json.dump({"version": "v1.0.0"}, f)

        is_valid = await rollback.verify_rollback("v1.0.0")

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_version(self, temp_registry):
        """Test rolling back to nonexistent version."""
        rollback = ModelRollback(registry_path=temp_registry)
        rollback.set_current_version("v2.0.0")

        result = await rollback.rollback("v99.0.0", reason="Invalid rollback")

        assert result["success"] is False
        assert "error" in result

    def test_get_rollback_history(self, temp_registry):
        """Test getting rollback history."""
        rollback = ModelRollback(registry_path=temp_registry)

        history = rollback.get_rollback_history()

        assert isinstance(history, list)

    def test_get_available_versions(self, temp_registry):
        """Test getting available versions."""
        rollback = ModelRollback(registry_path=temp_registry)

        # Create some version directories
        for version in ["v1.0.0", "v2.0.0", "v3.0.0"]:
            v_path = os.path.join(temp_registry, version)
            os.makedirs(v_path, exist_ok=True)
            with open(os.path.join(v_path, "metadata.json"), "w") as f:
                json.dump({"version": version}, f)

        versions = rollback.get_available_versions()

        assert "v1.0.0" in versions
        assert "v2.0.0" in versions
        assert "v3.0.0" in versions

    def test_get_status(self, temp_registry):
        """Test getting rollback status."""
        rollback = ModelRollback(registry_path=temp_registry)

        status = rollback.get_status()

        assert "registry_path" in status
        assert "current_version" in status
        assert "available_versions" in status


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_trainer(self):
        """Test get_trainer factory."""
        trainer = get_trainer()

        assert isinstance(trainer, Trainer)

    def test_get_unsloth_optimizer(self):
        """Test get_unsloth_optimizer factory."""
        optimizer = get_unsloth_optimizer()

        assert isinstance(optimizer, UnslothOptimizer)

    def test_get_model_deployer(self):
        """Test get_model_deployer factory."""
        deployer = get_model_deployer()

        assert isinstance(deployer, ModelDeployer)

    def test_get_model_rollback(self):
        """Test get_model_rollback factory."""
        rollback = get_model_rollback()

        assert isinstance(rollback, ModelRollback)


class TestIntegration:
    """Integration tests for training pipeline."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_full_training_to_deployment_flow(self, temp_registry):
        """Test complete flow from training to deployment."""
        # 1. Create optimizer and get config
        optimizer = get_unsloth_optimizer()
        config = optimizer.optimize_for_colab_free()

        # 2. Create trainer
        trainer = get_trainer()

        # 3. Create training dataset
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for i in range(50):  # 50 entries
                json.dump({
                    "instruction": f"Test instruction {i}",
                    "output": f"Expected output {i}"
                }, f)
                f.write("\n")
            dataset_path = f.name

        try:
            # 4. Train model
            train_result = await trainer.train(dataset_path)

            assert train_result["success"] is True

            # 5. Evaluate model
            eval_result = await trainer.evaluate(train_result["model_path"])

            assert eval_result["success"] is True

            # 6. Deploy model
            deployer = get_model_deployer(registry_path=temp_registry)

            deploy_result = await deployer.deploy(
                model_path=train_result["model_path"],
                version="v1.0.0",
                accuracy=eval_result["metrics"]["accuracy"],
                environment=Environment.PRODUCTION
            )

            # Check deployment based on accuracy
            if eval_result["metrics"]["accuracy"] >= 0.90:
                assert deploy_result["success"] is True
            else:
                assert deploy_result["success"] is False

        finally:
            os.unlink(dataset_path)

    @pytest.mark.asyncio
    async def test_deployment_rollback_flow(self, temp_registry):
        """Test deployment and rollback flow."""
        # Setup
        deployer = get_model_deployer(registry_path=temp_registry)
        rollback = get_model_rollback(registry_path=temp_registry)

        # Create version directories
        for version in ["v1.0.0", "v2.0.0"]:
            v_path = os.path.join(temp_registry, version)
            os.makedirs(v_path, exist_ok=True)
            with open(os.path.join(v_path, "metadata.json"), "w") as f:
                json.dump({"version": version}, f)

        # Deploy v1
        await deployer.deploy(
            model_path="/models/v1",
            version="v1.0.0",
            accuracy=0.92,
            environment=Environment.PRODUCTION
        )

        # Deploy v2 (replaces v1)
        await deployer.deploy(
            model_path="/models/v2",
            version="v2.0.0",
            accuracy=0.93,
            environment=Environment.PRODUCTION
        )

        # Rollback to v1
        rollback.set_current_version("v2.0.0")
        result = await rollback.rollback("v1.0.0", reason="Issues with v2")

        assert result["success"] is True
        assert result["to_version"] == "v1.0.0"

        # Verify rollback
        is_valid = await rollback.verify_rollback("v1.0.0")
        assert is_valid is True
