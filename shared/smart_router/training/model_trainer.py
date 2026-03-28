"""
PARWA Smart Router Training Module.

Provides training, validation, and hyperparameter tuning for ML classifier.
"""
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime, timezone

from shared.core_functions.logger import get_logger
from shared.smart_router.ml_classifier import MLClassifier, EnsembleClassifier

logger = get_logger(__name__)


class ModelTrainer:
    """
    Train and validate ML classifier models.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize trainer.

        Args:
            output_dir: Directory to save trained models
        """
        self.output_dir = output_dir or Path(__file__).parent.parent / "models"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_training_data(
        self,
        data_path: Optional[Path] = None
    ) -> Tuple[List[str], List[int]]:
        """
        Load labeled training data.

        Args:
            data_path: Path to labeled queries JSON

        Returns:
            Tuple of (queries, labels)
        """
        data_path = data_path or Path(__file__).parent / "data" / "labeled_queries.json"

        with open(data_path, 'r') as f:
            data = json.load(f)

        queries = []
        labels = []

        for item in data["queries"]:
            queries.append(item["text"])
            labels.append(item["label"])

        logger.info({
            "event": "training_data_loaded",
            "path": str(data_path),
            "samples": len(queries)
        })

        return queries, labels

    def train(
        self,
        model_type: str = "random_forest",
        data_path: Optional[Path] = None,
        save_model: bool = True
    ) -> Dict[str, Any]:
        """
        Train a new model.

        Args:
            model_type: Type of model to train
            data_path: Path to training data
            save_model: Whether to save trained model

        Returns:
            Training metrics
        """
        # Load data
        queries, labels = self.load_training_data(data_path)

        # Create and train classifier
        classifier = MLClassifier(model_type=model_type)
        metrics = classifier.train(queries, labels, validate=True)

        # Save model
        if save_model:
            model_path = self.output_dir / f"{model_type}_model.pkl"
            classifier.save(model_path)
            metrics["model_path"] = str(model_path)

        return metrics

    def train_ensemble(
        self,
        data_path: Optional[Path] = None,
        save_model: bool = True
    ) -> Dict[str, Any]:
        """
        Train ensemble classifier.

        Args:
            data_path: Path to training data
            save_model: Whether to save trained model

        Returns:
            Training metrics
        """
        # Load data
        queries, labels = self.load_training_data(data_path)

        # Create and train ensemble
        classifier = EnsembleClassifier()
        metrics = classifier.train(queries, labels, validate=True)

        if save_model:
            model_path = self.output_dir / "ensemble_model.pkl"
            classifier.save(model_path)
            metrics["model_path"] = str(model_path)

        return metrics


class ModelValidator:
    """
    Validate ML classifier accuracy and performance.
    """

    def __init__(self, test_data_path: Optional[Path] = None):
        """
        Initialize validator.

        Args:
            test_data_path: Path to test data
        """
        self.test_data_path = test_data_path

    def validate(
        self,
        classifier: MLClassifier,
        test_queries: Optional[List[str]] = None,
        test_labels: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Validate classifier accuracy.

        Args:
            classifier: Trained MLClassifier
            test_queries: Test queries (optional)
            test_labels: Test labels (optional)

        Returns:
            Validation metrics
        """
        # Load test data if not provided
        if test_queries is None or test_labels is None:
            test_queries, test_labels = self._load_test_data()

        metrics = classifier.validate(test_queries, test_labels)

        logger.info({
            "event": "validation_complete",
            "accuracy": metrics.get("accuracy"),
            "meets_threshold": metrics.get("meets_threshold")
        })

        return metrics

    def _load_test_data(self) -> Tuple[List[str], List[int]]:
        """Load test data from file."""
        if self.test_data_path and self.test_data_path.exists():
            with open(self.test_data_path, 'r') as f:
                data = json.load(f)
            queries = [item["text"] for item in data["queries"]]
            labels = [item["label"] for item in data["queries"]]
            return queries, labels

        # Use subset of training data for testing
        data_path = Path(__file__).parent / "data" / "labeled_queries.json"
        with open(data_path, 'r') as f:
            data = json.load(f)

        # Use last 100 samples for testing
        queries = [item["text"] for item in data["queries"][-100:]]
        labels = [item["label"] for item in data["queries"][-100:]]
        return queries, labels


class AccuracyTracker:
    """
    Track classifier accuracy over time.
    """

    def __init__(self, history_path: Optional[Path] = None):
        """
        Initialize accuracy tracker.

        Args:
            history_path: Path to accuracy history file
        """
        self.history_path = history_path or Path(__file__).parent / "accuracy_history.json"
        self.history = self._load_history()

    def record(
        self,
        model_type: str,
        accuracy: float,
        metrics: Dict[str, Any]
    ) -> None:
        """
        Record accuracy measurement.

        Args:
            model_type: Type of model
            accuracy: Accuracy score
            metrics: Full metrics dict
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_type": model_type,
            "accuracy": accuracy,
            "metrics": metrics
        }

        self.history.append(entry)
        self._save_history()

    def get_latest(self, model_type: str) -> Optional[Dict[str, Any]]:
        """Get latest accuracy for model type."""
        for entry in reversed(self.history):
            if entry["model_type"] == model_type:
                return entry
        return None

    def get_trend(self, model_type: str, limit: int = 10) -> List[float]:
        """Get accuracy trend for model type."""
        accuracies = [
            entry["accuracy"] for entry in self.history
            if entry["model_type"] == model_type
        ]
        return accuracies[-limit:]

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load history from file."""
        if self.history_path.exists():
            with open(self.history_path, 'r') as f:
                return json.load(f)
        return []

    def _save_history(self) -> None:
        """Save history to file."""
        with open(self.history_path, 'w') as f:
            json.dump(self.history, f, indent=2)


def train_and_validate(
    model_type: str = "random_forest",
    accuracy_threshold: float = 0.92
) -> Dict[str, Any]:
    """
    Train and validate a model in one function.

    Args:
        model_type: Type of model to train
        accuracy_threshold: Minimum required accuracy

    Returns:
        Training and validation results
    """
    trainer = ModelTrainer()
    validator = ModelValidator()

    # Train
    train_metrics = trainer.train(model_type=model_type)

    # Load classifier
    model_path = Path(train_metrics.get("model_path", ""))
    classifier = MLClassifier(model_type=model_type, model_path=model_path)

    # Validate
    val_metrics = validator.validate(classifier)

    result = {
        "training": train_metrics,
        "validation": val_metrics,
        "meets_threshold": val_metrics.get("accuracy", 0) >= accuracy_threshold
    }

    return result
