"""
Agent Lightning Module.

Fine-tuning and training pipeline for PARWA agents using Unsloth + Colab FREE tier.

Key Components:
- Data Export: Export training data (mistakes, approvals)
- Training: Unsloth-optimized training pipeline
- Deployment: Model registry and deployment
- Monitoring: Drift detection and accuracy tracking

CRITICAL Requirements:
- Uses Unsloth + Colab FREE tier for cost-effective training
- validate.py: BLOCKS deployment at <90% accuracy
- validate.py: ALLOWS deployment at 91%+ accuracy
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


__version__ = "1.0.0"
__all__ = [
    "TrainingConfig",
    "ModelVersion",
    "TrainingResult",
]


class TrainingConfig:
    """Default training configuration."""

    # Unsloth + Colab FREE tier settings
    MODEL_NAME = "unsloth/mistral-7b-instruct-v0.2"
    MAX_SEQ_LENGTH = 2048
    DTYPE = None  # Auto-detect
    LOAD_IN_4BIT = True  # Use 4bit quantization for memory efficiency

    # Training hyperparameters
    EPOCHS = 3
    BATCH_SIZE = 2
    GRADIENT_ACCUMULATION_STEPS = 4
    LEARNING_RATE = 2e-4
    WARMUP_STEPS = 5

    # LoRA settings
    LORA_R = 16
    LORA_ALPHA = 16
    LORA_DROPOUT = 0
    TARGET_MODULES = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ]

    # Output settings
    OUTPUT_DIR = "./models/agent_lightning"


class ModelVersion:
    """Model version information."""

    def __init__(
        self,
        version: str,
        accuracy: float,
        created_at: Optional[datetime] = None,
        is_active: bool = False,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """Initialize model version."""
        self.version = version
        self.accuracy = accuracy
        self.created_at = created_at or datetime.now(timezone.utc)
        self.is_active = is_active
        self.metrics = metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "accuracy": self.accuracy,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "metrics": self.metrics
        }


class TrainingResult:
    """Training result container."""

    def __init__(
        self,
        success: bool,
        model_path: Optional[str] = None,
        accuracy: float = 0.0,
        loss: float = 0.0,
        epochs_completed: int = 0,
        training_time_seconds: float = 0.0,
        error: Optional[str] = None
    ):
        """Initialize training result."""
        self.success = success
        self.model_path = model_path
        self.accuracy = accuracy
        self.loss = loss
        self.epochs_completed = epochs_completed
        self.training_time_seconds = training_time_seconds
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "model_path": self.model_path,
            "accuracy": self.accuracy,
            "loss": self.loss,
            "epochs_completed": self.epochs_completed,
            "training_time_seconds": self.training_time_seconds,
            "error": self.error
        }
