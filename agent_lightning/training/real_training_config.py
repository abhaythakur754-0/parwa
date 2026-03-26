"""
Real Training Configuration.

Configuration for training Agent Lightning on real production data.
"""
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RealTrainingConfig:
    """Configuration for real Agent Lightning training."""

    # Client scope
    client_ids: List[str] = field(default_factory=lambda: ["client_001", "client_002"])

    # Data source configuration
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://localhost/parwa"))
    training_data_table: str = "training_data"
    approvals_table: str = "approval_decisions"
    mistakes_table: str = "agent_mistakes"

    # Date range for training data
    days_back: int = 30
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Training parameters
    epochs: int = 3
    batch_size: int = 16
    learning_rate: float = 2e-5
    warmup_steps: int = 100
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    # Dataset configuration
    validation_split: float = 0.2
    min_samples: int = 100
    max_samples: int = 10000
    balance_dataset: bool = True

    # Model configuration
    base_model: str = "unsloth/llama-3-8b-bnb-4bit"
    output_model_name: str = "agent_lightning_v1"
    max_sequence_length: int = 2048

    # Accuracy thresholds
    min_accuracy_threshold: float = 0.91  # 91%
    target_improvement: float = 0.03  # 3% improvement required

    # Export paths
    export_dir: Path = field(default_factory=lambda: Path("./agent_lightning/exports"))
    model_output_dir: Path = field(default_factory=lambda: Path("./agent_lightning/models"))
    dataset_output_dir: Path = field(default_factory=lambda: Path("./agent_lightning/datasets"))

    # PII anonymization
    anonymize_pii: bool = True
    pii_fields: List[str] = field(default_factory=lambda: [
        "customer_email", "customer_name", "customer_phone",
        "order_id", "transaction_id", "ip_address"
    ])

    # Training features
    use_gpu: bool = True
    mixed_precision: bool = True
    gradient_checkpointing: bool = True

    # Logging
    log_level: str = "INFO"
    wandb_project: Optional[str] = "parwa-agent-lightning"
    wandb_enabled: bool = False

    # Deployment
    auto_deploy: bool = False
    canary_percentage: int = 5

    def __post_init__(self):
        """Set default dates if not provided."""
        if self.end_date is None:
            self.end_date = datetime.utcnow()
        if self.start_date is None:
            self.start_date = self.end_date - timedelta(days=self.days_back)

        # Ensure paths are Path objects
        self.export_dir = Path(self.export_dir)
        self.model_output_dir = Path(self.model_output_dir)
        self.dataset_output_dir = Path(self.dataset_output_dir)

        # Create directories
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.model_output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_output_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "client_ids": self.client_ids,
            "database_url": "***REDACTED***",  # Don't expose in logs
            "days_back": self.days_back,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "validation_split": self.validation_split,
            "min_accuracy_threshold": self.min_accuracy_threshold,
            "target_improvement": self.target_improvement,
            "base_model": self.base_model,
            "output_model_name": self.output_model_name,
            "anonymize_pii": self.anonymize_pii,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RealTrainingConfig":
        """Create config from dictionary."""
        # Handle date parsing
        if "start_date" in data and isinstance(data["start_date"], str):
            data["start_date"] = datetime.fromisoformat(data["start_date"])
        if "end_date" in data and isinstance(data["end_date"], str):
            data["end_date"] = datetime.fromisoformat(data["end_date"])

        # Handle path parsing
        if "export_dir" in data:
            data["export_dir"] = Path(data["export_dir"])
        if "model_output_dir" in data:
            data["model_output_dir"] = Path(data["model_output_dir"])
        if "dataset_output_dir" in data:
            data["dataset_output_dir"] = Path(data["dataset_output_dir"])

        return cls(**data)

    @classmethod
    def load_from_file(cls, filepath: str) -> "RealTrainingConfig":
        """Load config from JSON file."""
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def save_to_file(self, filepath: str) -> None:
        """Save config to JSON file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


# Default configuration instance
DEFAULT_CONFIG = RealTrainingConfig()


def get_training_config(environment: str = "production") -> RealTrainingConfig:
    """Get training configuration for the specified environment."""
    if environment == "production":
        return RealTrainingConfig(
            epochs=3,
            batch_size=16,
            min_samples=500,
            auto_deploy=False,
        )
    elif environment == "staging":
        return RealTrainingConfig(
            epochs=2,
            batch_size=8,
            min_samples=100,
            auto_deploy=False,
        )
    elif environment == "development":
        return RealTrainingConfig(
            epochs=1,
            batch_size=4,
            min_samples=10,
            auto_deploy=False,
            use_gpu=False,
        )
    else:
        return RealTrainingConfig()
