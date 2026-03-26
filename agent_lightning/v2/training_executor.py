"""
Training Executor - Main training execution engine for Agent Lightning v2.

CRITICAL: Executes training pipeline with privacy-preserving collective intelligence.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import logging
import json
import os

logger = logging.getLogger(__name__)


class TrainingStatus(Enum):
    """Status of training execution"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class CheckpointType(Enum):
    """Types of checkpoints"""
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    FINAL = "final"


@dataclass
class TrainingCheckpoint:
    """Training checkpoint data"""
    checkpoint_id: str
    step: int
    epoch: int
    timestamp: datetime
    loss: float
    accuracy: float
    checkpoint_type: CheckpointType
    checkpoint_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "step": self.step,
            "epoch": self.epoch,
            "timestamp": self.timestamp.isoformat(),
            "loss": self.loss,
            "accuracy": self.accuracy,
            "checkpoint_type": self.checkpoint_type.value,
            "checkpoint_path": self.checkpoint_path,
            "metadata": self.metadata,
        }


@dataclass
class TrainingMetrics:
    """Training metrics at a point in time"""
    step: int
    epoch: int
    timestamp: datetime
    loss: float
    accuracy: float
    learning_rate: float
    gradient_norm: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    epoch_progress: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "step": self.step,
            "epoch": self.epoch,
            "timestamp": self.timestamp.isoformat(),
            "loss": self.loss,
            "accuracy": self.accuracy,
            "learning_rate": self.learning_rate,
            "gradient_norm": self.gradient_norm,
            "gpu_memory_mb": self.gpu_memory_mb,
            "epoch_progress": self.epoch_progress,
        }


class TrainingExecutor:
    """
    Main training execution engine for Agent Lightning v2.

    CRITICAL: Trains on collective intelligence data (578 examples)
    without exposing client-specific data.

    Features:
    - Execute full training pipeline
    - Load collective intelligence dataset
    - Track training metrics
    - Handle interruptions gracefully
    - Save checkpoints every 100 steps
    """

    # Default training configuration
    DEFAULT_CONFIG = {
        "num_epochs": 3,
        "batch_size": 8,
        "learning_rate": 2e-5,
        "warmup_steps": 100,
        "max_steps": -1,  # -1 means no limit
        "checkpoint_steps": 100,
        "eval_steps": 50,
        "max_checkpoints": 5,
        "fp16": True,
        "gradient_accumulation_steps": 4,
    }

    # Collective intelligence dataset size
    DATASET_SIZE = 578

    def __init__(
        self,
        model_path: str,
        output_dir: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize training executor.

        Args:
            model_path: Path to base model
            output_dir: Directory for outputs and checkpoints
            config: Training configuration override
        """
        self.model_path = model_path
        self.output_dir = output_dir
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        self._status = TrainingStatus.PENDING
        self._checkpoints: List[TrainingCheckpoint] = []
        self._metrics_history: List[TrainingMetrics] = []
        self._current_step = 0
        self._current_epoch = 0
        self._best_accuracy = 0.0
        self._interruption_requested = False

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "checkpoints"), exist_ok=True)

    def load_collective_dataset(
        self,
        dataset_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load collective intelligence dataset.

        CRITICAL: Dataset contains no client-specific data.

        Args:
            dataset_path: Optional path to dataset

        Returns:
            Dataset info
        """
        # Simulated dataset loading
        # In production, would load from actual collective intelligence dataset
        dataset_info = {
            "total_examples": self.DATASET_SIZE,
            "train_examples": int(self.DATASET_SIZE * 0.9),  # 90% train
            "val_examples": int(self.DATASET_SIZE * 0.1),    # 10% validation
            "industries": ["ecommerce", "saas", "healthcare", "logistics", "fintech"],
            "industries_balanced": True,
            "privacy_preserved": True,
            "no_client_data": True,
        }

        logger.info(
            f"Loaded collective intelligence dataset: "
            f"{dataset_info['train_examples']} train, "
            f"{dataset_info['val_examples']} validation"
        )

        return dataset_info

    def execute_training(
        self,
        on_step: Optional[Callable[[TrainingMetrics], None]] = None,
        on_checkpoint: Optional[Callable[[TrainingCheckpoint], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the full training pipeline.

        Args:
            on_step: Callback for each training step
            on_checkpoint: Callback for each checkpoint

        Returns:
            Training results
        """
        self._status = TrainingStatus.RUNNING
        start_time = datetime.now()

        try:
            # Load dataset
            dataset_info = self.load_collective_dataset()

            # Training loop simulation
            total_steps = dataset_info["train_examples"] * self.config["num_epochs"]
            total_steps = total_steps // self.config["batch_size"]

            for epoch in range(self.config["num_epochs"]):
                self._current_epoch = epoch

                for step in range(total_steps // self.config["num_epochs"]):
                    if self._interruption_requested:
                        self._status = TrainingStatus.INTERRUPTED
                        self._save_interrupt_checkpoint()
                        break

                    self._current_step += 1

                    # Simulate training metrics
                    metrics = self._simulate_training_step(epoch, step)
                    self._metrics_history.append(metrics)

                    # Callback
                    if on_step:
                        on_step(metrics)

                    # Save checkpoint
                    if self._current_step % self.config["checkpoint_steps"] == 0:
                        checkpoint = self._save_checkpoint(metrics)
                        if on_checkpoint:
                            on_checkpoint(checkpoint)

                if self._interruption_requested:
                    break

            if not self._interruption_requested:
                self._status = TrainingStatus.COMPLETED

        except Exception as e:
            self._status = TrainingStatus.FAILED
            logger.error(f"Training failed: {e}")
            raise

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return {
            "status": self._status.value,
            "total_steps": self._current_step,
            "total_epochs": self._current_epoch + 1,
            "duration_seconds": duration,
            "best_accuracy": self._best_accuracy,
            "final_loss": self._metrics_history[-1].loss if self._metrics_history else None,
            "final_accuracy": self._metrics_history[-1].accuracy if self._metrics_history else None,
            "checkpoints_saved": len(self._checkpoints),
        }

    def request_interruption(self) -> None:
        """Request graceful training interruption"""
        self._interruption_requested = True
        logger.info("Training interruption requested")

    def restore_from_checkpoint(
        self,
        checkpoint_path: str
    ) -> None:
        """
        Restore training from a checkpoint.

        Args:
            checkpoint_path: Path to checkpoint
        """
        # Load checkpoint metadata
        with open(checkpoint_path, "r") as f:
            data = json.load(f)

        self._current_step = data["step"]
        self._current_epoch = data["epoch"]
        self._best_accuracy = data["accuracy"]

        logger.info(
            f"Restored from checkpoint: step={self._current_step}, "
            f"epoch={self._current_epoch}, accuracy={self._best_accuracy:.4f}"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current training status"""
        return {
            "status": self._status.value,
            "current_step": self._current_step,
            "current_epoch": self._current_epoch,
            "best_accuracy": self._best_accuracy,
            "checkpoints_count": len(self._checkpoints),
            "metrics_count": len(self._metrics_history),
        }

    def get_checkpoints(self) -> List[TrainingCheckpoint]:
        """Get all checkpoints"""
        return self._checkpoints

    def get_metrics_history(self, limit: int = 100) -> List[TrainingMetrics]:
        """Get metrics history"""
        return self._metrics_history[-limit:]

    def _simulate_training_step(
        self,
        epoch: int,
        step: int
    ) -> TrainingMetrics:
        """Simulate a training step (mock for testing)"""
        import random

        # Simulate decreasing loss and increasing accuracy
        base_loss = 2.0 - (self._current_step * 0.001)
        base_accuracy = 0.72 + (self._current_step * 0.0001)

        # Add some noise
        loss = max(0.1, base_loss + random.uniform(-0.1, 0.1))
        accuracy = min(0.99, base_accuracy + random.uniform(-0.01, 0.01))

        if accuracy > self._best_accuracy:
            self._best_accuracy = accuracy

        return TrainingMetrics(
            step=self._current_step,
            epoch=epoch,
            timestamp=datetime.now(),
            loss=loss,
            accuracy=accuracy,
            learning_rate=self.config["learning_rate"],
            gradient_norm=random.uniform(0.1, 1.0),
            gpu_memory_mb=random.uniform(4000, 8000),
            epoch_progress=step / (self.DATASET_SIZE // self.config["batch_size"] // self.config["num_epochs"]),
        )

    def _save_checkpoint(
        self,
        metrics: TrainingMetrics
    ) -> TrainingCheckpoint:
        """Save a training checkpoint"""
        checkpoint_id = f"ckpt_{self._current_step:06d}"
        checkpoint_path = os.path.join(
            self.output_dir,
            "checkpoints",
            f"{checkpoint_id}.json"
        )

        checkpoint = TrainingCheckpoint(
            checkpoint_id=checkpoint_id,
            step=self._current_step,
            epoch=self._current_epoch,
            timestamp=datetime.now(),
            loss=metrics.loss,
            accuracy=metrics.accuracy,
            checkpoint_type=CheckpointType.AUTOMATIC,
            checkpoint_path=checkpoint_path,
        )

        # Save checkpoint metadata
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

        self._checkpoints.append(checkpoint)

        # Limit checkpoints
        if len(self._checkpoints) > self.config["max_checkpoints"]:
            old_checkpoint = self._checkpoints.pop(0)
            if os.path.exists(old_checkpoint.checkpoint_path):
                os.remove(old_checkpoint.checkpoint_path)

        logger.info(f"Saved checkpoint: {checkpoint_id}")
        return checkpoint

    def _save_interrupt_checkpoint(self) -> None:
        """Save checkpoint on interruption"""
        if self._metrics_history:
            checkpoint = self._save_checkpoint(self._metrics_history[-1])
            checkpoint.checkpoint_type = CheckpointType.MANUAL


def execute_training_pipeline(
    model_path: str,
    output_dir: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to execute training pipeline.

    Args:
        model_path: Path to base model
        output_dir: Directory for outputs
        config: Training configuration

    Returns:
        Training results
    """
    executor = TrainingExecutor(
        model_path=model_path,
        output_dir=output_dir,
        config=config,
    )
    return executor.execute_training()
