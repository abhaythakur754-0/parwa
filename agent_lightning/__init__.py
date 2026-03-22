"""
PARWA Agent Lightning Module.

Agent Lightning provides the training pipeline for fine-tuning models
based on collected mistakes and approvals. Uses Unsloth + Colab FREE tier
for cost-effective training.

Components:
- data: Export training data (mistakes, approvals, dataset builder)
- deployment: Model registry and deployment
- training: Training pipeline (Unsloth, fine-tuning)
- monitoring: Drift detection, accuracy tracking

Key Features:
- Export mistakes from DB for training
- Export approval decisions with reasoning
- Build JSONL datasets (50+ entries)
- Model version registry
- Training with Unsloth + Colab FREE tier
- Validation blocks deployment at <90% accuracy
- Validation allows deployment at 91%+ accuracy

CRITICAL Requirements:
- Uses Unsloth + Colab FREE tier for cost-effective training
- validate.py: BLOCKS deployment at <90% accuracy
- validate.py: ALLOWS deployment at 91%+ accuracy
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
import json


class TrainingStatus(str, Enum):
    """Training job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelStatus(str, Enum):
    """Model deployment status."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class MistakeType(str, Enum):
    """Types of training mistakes."""
    INCORRECT_CLASSIFICATION = "incorrect_classification"
    WRONG_REFUND_DECISION = "wrong_refund_decision"
    POOR_RESPONSE = "poor_response"
    ESCALATION_ERROR = "escalation_error"
    COMPLIANCE_VIOLATION = "compliance_violation"


class ApprovalDecision(str, Enum):
    """Approval decision types."""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    ESCALATED = "escalated"


# Module version
__version__ = "1.0.0"


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


def get_training_config() -> Dict[str, Any]:
    """
    Get default training configuration for Agent Lightning.

    Returns:
        Dict with training configuration
    """
    return {
        "model": {
            "base_model": "unsloth/mistral-7b-instruct-v0.2",
            "max_seq_length": 2048,
            "load_in_4bit": True,
        },
        "training": {
            "epochs": 3,
            "batch_size": 4,
            "learning_rate": 2e-4,
            "warmup_steps": 50,
            "weight_decay": 0.01,
        },
        "unsloth": {
            "use_fast_inference": True,
            "use_gradient_checkpointing": True,
            "optimize_for_colab_free": True,
        },
        "validation": {
            "accuracy_threshold": 0.90,  # CRITICAL: 90% minimum
            "test_split": 0.2,
        }
    }


def validate_jsonl_entry(entry: Dict[str, Any]) -> bool:
    """
    Validate a JSONL training entry.

    Args:
        entry: Training entry to validate

    Returns:
        True if valid
    """
    required_fields = ["messages"]

    for field in required_fields:
        if field not in entry:
            return False

    # Validate messages format
    messages = entry.get("messages", [])
    if not isinstance(messages, list):
        return False

    if len(messages) < 2:
        return False

    for msg in messages:
        if "role" not in msg or "content" not in msg:
            return False

        if msg["role"] not in ["system", "user", "assistant"]:
            return False

    return True


def format_training_prompt(
    instruction: str,
    input_text: str,
    output_text: str
) -> Dict[str, Any]:
    """
    Format a training prompt in messages format.

    Args:
        instruction: Task instruction
        input_text: Input text
        output_text: Expected output

    Returns:
        Formatted training entry
    """
    return {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful customer support agent for PARWA."
            },
            {
                "role": "user",
                "content": f"{instruction}\n\nInput: {input_text}"
            },
            {
                "role": "assistant",
                "content": output_text
            }
        ]
    }


__all__ = [
    "TrainingStatus",
    "ModelStatus",
    "MistakeType",
    "ApprovalDecision",
    "TrainingConfig",
    "ModelVersion",
    "TrainingResult",
    "get_training_config",
    "validate_jsonl_entry",
    "format_training_prompt",
]
