"""
Accuracy Validator for Week 28.

Validates ≥90% accuracy with:
- Overall accuracy validation
- Per-category accuracy breakdown
- Per-client accuracy breakdown
- Confidence calibration
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import logging
import random
import math

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status of validation."""
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class CategoryValidation:
    """Validation result for a category."""
    category: str
    accuracy: float
    sample_size: int
    correct_predictions: int
    threshold: float = 0.88  # 88% minimum per category
    passed: bool = False

    def __post_init__(self):
        self.passed = self.accuracy >= self.threshold


@dataclass
class ClientValidation:
    """Validation result for a client."""
    client_id: str
    accuracy: float
    sample_size: int
    improvement: float  # Improvement from baseline
    passed: bool = False


@dataclass
class ValidationResult:
    """Overall validation result."""
    validation_id: str
    status: ValidationStatus
    overall_accuracy: float
    threshold: float
    category_validations: Dict[str, CategoryValidation] = field(default_factory=dict)
    client_validations: Dict[str, ClientValidation] = field(default_factory=dict)
    confidence_calibration: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if validation passed."""
        return self.overall_accuracy >= self.threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "status": self.status.value,
            "overall_accuracy": self.overall_accuracy,
            "threshold": self.threshold,
            "passed": self.passed,
            "category_validations": {
                k: {"accuracy": v.accuracy, "passed": v.passed}
                for k, v in self.category_validations.items()
            },
            "client_validations": {
                k: {"accuracy": v.accuracy, "improvement": v.improvement}
                for k, v in self.client_validations.items()
            },
            "confidence_calibration": self.confidence_calibration,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class AccuracyValidatorWeek28:
    """
    Validates Agent Lightning accuracy for Week 28.
    
    Targets:
    - Overall accuracy ≥90%
    - Per-category accuracy >88%
    - All 20 clients show improvement
    """

    OVERALL_THRESHOLD: float = 0.90
    CATEGORY_THRESHOLD: float = 0.88
    MIN_IMPROVEMENT: float = 0.01  # 1% minimum improvement

    def __init__(
        self,
        overall_threshold: float = 0.90,
        category_threshold: float = 0.88,
        min_improvement: float = 0.01
    ):
        """
        Initialize the accuracy validator.

        Args:
            overall_threshold: Overall accuracy threshold
            category_threshold: Per-category accuracy threshold
            min_improvement: Minimum improvement for clients
        """
        self.overall_threshold = overall_threshold
        self.category_threshold = category_threshold
        self.min_improvement = min_improvement
        self._validation_counter = 0
        self._validation_history: List[ValidationResult] = []

    def validate_overall_accuracy(
        self,
        predictions: List[Dict[str, Any]]
    ) -> Tuple[float, bool]:
        """
        Validate overall accuracy.

        Args:
            predictions: List of predictions with 'correct' field

        Returns:
            Tuple of (accuracy, passed)
        """
        if not predictions:
            return 0.0, False

        correct = sum(1 for p in predictions if p.get("correct", False))
        accuracy = correct / len(predictions)
        passed = accuracy >= self.overall_threshold

        logger.info(
            f"Overall accuracy: {accuracy:.2%} "
            f"({'PASSED' if passed else 'FAILED'}, threshold: {self.overall_threshold:.0%})"
        )

        return accuracy, passed

    def validate_by_category(
        self,
        predictions: List[Dict[str, Any]]
    ) -> Dict[str, CategoryValidation]:
        """
        Validate accuracy per category.

        Args:
            predictions: List of predictions with 'category' and 'correct' fields

        Returns:
            Dictionary of category validations
        """
        categories: Dict[str, List[Dict]] = {}
        
        for pred in predictions:
            category = pred.get("category", "unknown")
            if category not in categories:
                categories[category] = []
            categories[category].append(pred)

        validations = {}
        for category, preds in categories.items():
            correct = sum(1 for p in preds if p.get("correct", False))
            accuracy = correct / len(preds) if preds else 0.0

            validations[category] = CategoryValidation(
                category=category,
                accuracy=accuracy,
                sample_size=len(preds),
                correct_predictions=correct,
                threshold=self.category_threshold,
            )

            logger.info(
                f"Category {category}: {accuracy:.2%} "
                f"({'PASSED' if validations[category].passed else 'FAILED'})"
            )

        return validations

    def validate_by_client(
        self,
        predictions: List[Dict[str, Any]],
        baselines: Optional[Dict[str, float]] = None
    ) -> Dict[str, ClientValidation]:
        """
        Validate accuracy per client.

        Args:
            predictions: List of predictions with 'client_id' and 'correct' fields
            baselines: Baseline accuracies per client

        Returns:
            Dictionary of client validations
        """
        clients: Dict[str, List[Dict]] = {}
        
        for pred in predictions:
            client_id = pred.get("client_id", "unknown")
            if client_id not in clients:
                clients[client_id] = []
            clients[client_id].append(pred)

        validations = {}
        baselines = baselines or {}

        for client_id, preds in clients.items():
            correct = sum(1 for p in preds if p.get("correct", False))
            accuracy = correct / len(preds) if preds else 0.0
            baseline = baselines.get(client_id, 0.85)  # Default baseline
            improvement = accuracy - baseline

            validations[client_id] = ClientValidation(
                client_id=client_id,
                accuracy=accuracy,
                sample_size=len(preds),
                improvement=improvement,
                passed=improvement >= self.min_improvement,
            )

        return validations

    def calibrate_confidence(
        self,
        predictions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calibrate confidence scores.

        Args:
            predictions: Predictions with 'confidence' and 'correct' fields

        Returns:
            Calibration metrics
        """
        if not predictions:
            return {"calibration_error": 0.0, "confidence_accuracy_correlation": 0.0}

        # Bin predictions by confidence
        bins = {
            "0.0-0.2": [],
            "0.2-0.4": [],
            "0.4-0.6": [],
            "0.6-0.8": [],
            "0.8-1.0": [],
        }

        for pred in predictions:
            conf = pred.get("confidence", 0.5)
            if conf < 0.2:
                bins["0.0-0.2"].append(pred)
            elif conf < 0.4:
                bins["0.2-0.4"].append(pred)
            elif conf < 0.6:
                bins["0.4-0.6"].append(pred)
            elif conf < 0.8:
                bins["0.6-0.8"].append(pred)
            else:
                bins["0.8-1.0"].append(pred)

        calibration = {}
        total_error = 0.0

        for bin_name, bin_preds in bins.items():
            if bin_preds:
                avg_conf = sum(p.get("confidence", 0.5) for p in bin_preds) / len(bin_preds)
                accuracy = sum(1 for p in bin_preds if p.get("correct", False)) / len(bin_preds)
                calibration[bin_name] = {
                    "avg_confidence": avg_conf,
                    "actual_accuracy": accuracy,
                    "error": abs(avg_conf - accuracy),
                }
                total_error += abs(avg_conf - accuracy)

        # Calculate Expected Calibration Error (ECE)
        ece = total_error / len(bins)

        return {
            "expected_calibration_error": ece,
            "bins": calibration,
        }

    def validate(
        self,
        predictions: List[Dict[str, Any]],
        client_baselines: Optional[Dict[str, float]] = None
    ) -> ValidationResult:
        """
        Run full validation.

        Args:
            predictions: All predictions to validate
            client_baselines: Baseline accuracies per client

        Returns:
            ValidationResult with full validation details
        """
        self._validation_counter += 1
        validation_id = f"val_{self._validation_counter}"

        # Overall accuracy
        overall_accuracy, overall_passed = self.validate_overall_accuracy(predictions)

        # Category validations
        category_validations = self.validate_by_category(predictions)
        all_categories_passed = all(v.passed for v in category_validations.values())

        # Client validations
        client_validations = self.validate_by_client(predictions, client_baselines)
        all_clients_improved = all(v.passed for v in client_validations.values())

        # Confidence calibration
        calibration = self.calibrate_confidence(predictions)

        # Determine status
        status = ValidationStatus.PASSED if (
            overall_passed and
            all_categories_passed and
            all_clients_improved
        ) else ValidationStatus.FAILED

        result = ValidationResult(
            validation_id=validation_id,
            status=status,
            overall_accuracy=overall_accuracy,
            threshold=self.overall_threshold,
            category_validations=category_validations,
            client_validations=client_validations,
            confidence_calibration=calibration,
            details={
                "total_predictions": len(predictions),
                "categories_passed": sum(1 for v in category_validations.values() if v.passed),
                "clients_improved": sum(1 for v in client_validations.values() if v.passed),
            }
        )

        self._validation_history.append(result)

        logger.info(
            f"Validation {validation_id}: {status.value} "
            f"(accuracy: {overall_accuracy:.2%}, threshold: {self.overall_threshold:.0%})"
        )

        return result

    def get_validation_history(self) -> List[ValidationResult]:
        """Get validation history."""
        return self._validation_history

    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics."""
        return {
            "total_validations": len(self._validation_history),
            "passed_validations": sum(1 for v in self._validation_history if v.passed),
            "thresholds": {
                "overall": self.overall_threshold,
                "category": self.category_threshold,
                "min_improvement": self.min_improvement,
            }
        }


def get_accuracy_validator_week28(
    overall_threshold: float = 0.90
) -> AccuracyValidatorWeek28:
    """
    Factory function to create a Week 28 accuracy validator.

    Args:
        overall_threshold: Overall accuracy threshold

    Returns:
        Configured AccuracyValidatorWeek28 instance
    """
    return AccuracyValidatorWeek28(overall_threshold=overall_threshold)
