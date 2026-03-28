"""
Category-Level Validator for Agent Lightning.

Provides per-category validation with:
- Per-category accuracy metrics
- Confusion matrix generation
- Per-class precision, recall, F1
- Category-level thresholds

Author: Builder 3 - Week 36
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict
import asyncio

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class CategoryType(str, Enum):
    """Standard category types."""
    FAQ = "faq"
    REFUNDS = "refunds"
    ESCALATIONS = "escalations"
    BILLING = "billing"
    SHIPPING = "shipping"
    RETURNS = "returns"
    ACCOUNT = "account"
    TECHNICAL = "technical"
    COMPLAINTS = "complaints"
    ORDER_STATUS = "order_status"
    PRODUCT_INFO = "product_info"
    APPOINTMENT = "appointment"
    FRAUD = "fraud"
    GENERAL = "general"


@dataclass
class ClassMetrics:
    """Metrics for a single class within a category."""
    class_name: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    support: int = 0  # Number of actual instances

    def calculate_metrics(self) -> None:
        """Calculate precision, recall, and F1."""
        if self.true_positives + self.false_positives > 0:
            self.precision = self.true_positives / (self.true_positives + self.false_positives)

        if self.true_positives + self.false_negatives > 0:
            self.recall = self.true_positives / (self.true_positives + self.false_negatives)

        if self.precision + self.recall > 0:
            self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "class_name": self.class_name,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "support": self.support,
        }


@dataclass
class ConfusionMatrix:
    """Confusion matrix for classification."""
    matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    classes: List[str] = field(default_factory=list)
    total_samples: int = 0
    correct_predictions: int = 0

    def get(self, actual: str, predicted: str) -> int:
        """Get count for actual vs predicted."""
        return self.matrix.get(actual, {}).get(predicted, 0)

    def set(self, actual: str, predicted: str, count: int) -> None:
        """Set count for actual vs predicted."""
        if actual not in self.matrix:
            self.matrix[actual] = {}
        self.matrix[actual][predicted] = count

    def increment(self, actual: str, predicted: str) -> None:
        """Increment count for actual vs predicted."""
        if actual not in self.matrix:
            self.matrix[actual] = {}
        self.matrix[actual][predicted] = self.matrix[actual].get(predicted, 0) + 1

    @property
    def accuracy(self) -> float:
        """Calculate overall accuracy."""
        return self.correct_predictions / self.total_samples if self.total_samples > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "matrix": self.matrix,
            "classes": self.classes,
            "total_samples": self.total_samples,
            "correct_predictions": self.correct_predictions,
            "accuracy": self.accuracy,
        }

    def to_table(self) -> str:
        """Generate ASCII table representation."""
        if not self.classes:
            return "Empty confusion matrix"

        # Determine column widths
        max_class_len = max(len(c) for c in self.classes)
        col_width = max(6, max_class_len)

        lines = []
        header = " " * (col_width + 2) + "Predicted".center(len(self.classes) * (col_width + 1))
        lines.append(header)
        lines.append("-" * len(header))

        # Column headers
        col_header = " " * (col_width + 2) + " ".join(c.center(col_width) for c in self.classes)
        lines.append(col_header)
        lines.append("-" * len(header))

        # Rows
        for actual in self.classes:
            row = f"{actual:>:{col_width}} |"
            for predicted in self.classes:
                count = self.get(actual, predicted)
                row += f"{count:>{col_width}} "
            lines.append(row)

        return "\n".join(lines)


@dataclass
class CategoryValidationResult:
    """Validation result for a single category."""
    category: str
    accuracy: float
    threshold: float
    passed: bool
    total_samples: int
    correct_predictions: int
    class_metrics: Dict[str, ClassMetrics] = field(default_factory=dict)
    confusion_matrix: Optional[ConfusionMatrix] = None
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0
    weighted_precision: float = 0.0
    weighted_recall: float = 0.0
    weighted_f1: float = 0.0
    validated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "accuracy": self.accuracy,
            "threshold": self.threshold,
            "passed": self.passed,
            "total_samples": self.total_samples,
            "correct_predictions": self.correct_predictions,
            "class_metrics": {k: v.to_dict() for k, v in self.class_metrics.items()},
            "confusion_matrix": self.confusion_matrix.to_dict() if self.confusion_matrix else None,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "weighted_precision": self.weighted_precision,
            "weighted_recall": self.weighted_recall,
            "weighted_f1": self.weighted_f1,
            "validated_at": self.validated_at,
        }


@dataclass
class CategoryValidatorReport:
    """Complete category validation report."""
    validation_id: str
    overall_accuracy: float
    overall_passed: bool
    category_results: Dict[str, CategoryValidationResult]
    total_categories: int
    passed_categories: int
    total_samples: int
    global_confusion_matrix: Optional[ConfusionMatrix] = None
    validated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "overall_accuracy": self.overall_accuracy,
            "overall_passed": self.overall_passed,
            "category_results": {k: v.to_dict() for k, v in self.category_results.items()},
            "total_categories": self.total_categories,
            "passed_categories": self.passed_categories,
            "total_samples": self.total_samples,
            "global_confusion_matrix": self.global_confusion_matrix.to_dict() if self.global_confusion_matrix else None,
            "validated_at": self.validated_at,
        }


class CategoryValidator:
    """
    Per-Category Validator for Agent Lightning.
    
    Provides detailed validation at the category level with:
    - Per-category accuracy metrics
    - Confusion matrix generation
    - Per-class precision, recall, F1 scores
    - Configurable category-level thresholds
    
    Example:
        validator = CategoryValidator()
        result = await validator.validate(predictions)
        print(validator.generate_report(result))
    """

    # Default thresholds per category type
    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "faq": 0.95,
        "refunds": 0.92,
        "escalations": 0.95,  # High threshold for escalations
        "billing": 0.93,
        "shipping": 0.92,
        "returns": 0.91,
        "account": 0.93,
        "technical": 0.90,
        "complaints": 0.90,
        "order_status": 0.94,
        "product_info": 0.93,
        "appointment": 0.94,
        "fraud": 0.96,  # High threshold for fraud
        "general": 0.90,
    }

    def __init__(
        self,
        category_thresholds: Optional[Dict[str, float]] = None,
        default_threshold: float = 0.92
    ):
        """
        Initialize the category validator.
        
        Args:
            category_thresholds: Custom thresholds per category
            default_threshold: Default threshold for unspecified categories
        """
        self.category_thresholds = {**self.DEFAULT_THRESHOLDS}
        if category_thresholds:
            self.category_thresholds.update(category_thresholds)
        self.default_threshold = default_threshold
        self._validation_counter = 0

    def get_threshold(self, category: str) -> float:
        """Get threshold for a category."""
        return self.category_thresholds.get(category, self.default_threshold)

    async def validate(
        self,
        predictions: List[Dict[str, Any]],
        categories: Optional[List[str]] = None
    ) -> CategoryValidatorReport:
        """
        Validate predictions with per-category analysis.
        
        Args:
            predictions: List of predictions with 'prediction', 'expected', 'category'
            categories: Optional list of categories to validate (all if None)
            
        Returns:
            CategoryValidatorReport with detailed metrics
        """
        self._validation_counter += 1
        validation_id = f"cat_val_{self._validation_counter}"

        if not predictions:
            return CategoryValidatorReport(
                validation_id=validation_id,
                overall_accuracy=0.0,
                overall_passed=False,
                category_results={},
                total_categories=0,
                passed_categories=0,
                total_samples=0,
            )

        # Group predictions by category
        category_predictions: Dict[str, List[Dict]] = defaultdict(list)
        for pred in predictions:
            category = pred.get("category", "general")
            if categories is None or category in categories:
                category_predictions[category].append(pred)

        # Validate each category
        category_results: Dict[str, CategoryValidationResult] = {}
        total_correct = 0
        total_samples = 0

        for category, preds in category_predictions.items():
            result = self._validate_category(category, preds)
            category_results[category] = result
            total_correct += result.correct_predictions
            total_samples += result.total_samples

        # Build global confusion matrix
        global_cm = self._build_confusion_matrix(predictions)

        # Calculate overall metrics
        overall_accuracy = total_correct / total_samples if total_samples > 0 else 0
        passed_categories = sum(1 for r in category_results.values() if r.passed)
        overall_passed = passed_categories == len(category_results)

        report = CategoryValidatorReport(
            validation_id=validation_id,
            overall_accuracy=overall_accuracy,
            overall_passed=overall_passed,
            category_results=category_results,
            total_categories=len(category_results),
            passed_categories=passed_categories,
            total_samples=total_samples,
            global_confusion_matrix=global_cm,
        )

        logger.info({
            "event": "category_validation_complete",
            "validation_id": validation_id,
            "overall_accuracy": overall_accuracy,
            "passed_categories": passed_categories,
            "total_categories": len(category_results),
        })

        return report

    def _validate_category(
        self,
        category: str,
        predictions: List[Dict[str, Any]]
    ) -> CategoryValidationResult:
        """
        Validate a single category.
        
        Args:
            category: Category name
            predictions: Predictions for this category
            
        Returns:
            CategoryValidationResult
        """
        threshold = self.get_threshold(category)

        # Build confusion matrix for this category
        confusion_matrix = self._build_confusion_matrix(predictions)

        # Calculate per-class metrics
        class_metrics = self._calculate_class_metrics(predictions)

        # Calculate macro and weighted averages
        macro_p, macro_r, macro_f1 = self._calculate_macro_averages(class_metrics)
        weighted_p, weighted_r, weighted_f1 = self._calculate_weighted_averages(class_metrics)

        # Calculate accuracy
        correct = confusion_matrix.correct_predictions
        total = confusion_matrix.total_samples
        accuracy = correct / total if total > 0 else 0

        return CategoryValidationResult(
            category=category,
            accuracy=accuracy,
            threshold=threshold,
            passed=accuracy >= threshold,
            total_samples=total,
            correct_predictions=correct,
            class_metrics=class_metrics,
            confusion_matrix=confusion_matrix,
            macro_precision=macro_p,
            macro_recall=macro_r,
            macro_f1=macro_f1,
            weighted_precision=weighted_p,
            weighted_recall=weighted_r,
            weighted_f1=weighted_f1,
        )

    def _build_confusion_matrix(
        self,
        predictions: List[Dict[str, Any]]
    ) -> ConfusionMatrix:
        """
        Build confusion matrix from predictions.
        
        Args:
            predictions: List of predictions
            
        Returns:
            ConfusionMatrix
        """
        cm = ConfusionMatrix()
        classes_set = set()

        for pred in predictions:
            actual = pred.get("expected", "unknown")
            predicted = pred.get("prediction", "unknown")

            classes_set.add(actual)
            classes_set.add(predicted)

            cm.increment(actual, predicted)
            cm.total_samples += 1

            if actual == predicted:
                cm.correct_predictions += 1

        cm.classes = sorted(list(classes_set))
        return cm

    def _calculate_class_metrics(
        self,
        predictions: List[Dict[str, Any]]
    ) -> Dict[str, ClassMetrics]:
        """
        Calculate precision, recall, F1 for each class.
        
        Args:
            predictions: List of predictions
            
        Returns:
            Dictionary of class metrics
        """
        # Count TP, FP, FN for each class
        metrics: Dict[str, ClassMetrics] = defaultdict(lambda: ClassMetrics(class_name=""))
        all_classes = set()

        for pred in predictions:
            actual = pred.get("expected", "unknown")
            predicted = pred.get("prediction", "unknown")
            all_classes.add(actual)
            all_classes.add(predicted)

        # Initialize metrics for all classes
        for cls in all_classes:
            metrics[cls] = ClassMetrics(class_name=cls)

        # Calculate TP, FP, FN
        for pred in predictions:
            actual = pred.get("expected", "unknown")
            predicted = pred.get("prediction", "unknown")

            # Support (actual instances)
            metrics[actual].support += 1

            if actual == predicted:
                # True positive for this class
                metrics[actual].true_positives += 1
            else:
                # False positive for predicted class
                metrics[predicted].false_positives += 1
                # False negative for actual class
                metrics[actual].false_negatives += 1

        # Calculate TN for each class (samples not in this class, predicted as not this class)
        total = len(predictions)
        for cls in all_classes:
            tp = metrics[cls].true_positives
            fp = metrics[cls].false_positives
            fn = metrics[cls].false_negatives
            metrics[cls].true_negatives = total - tp - fp - fn

        # Calculate precision, recall, F1
        for cls in all_classes:
            metrics[cls].calculate_metrics()

        return dict(metrics)

    def _calculate_macro_averages(
        self,
        class_metrics: Dict[str, ClassMetrics]
    ) -> Tuple[float, float, float]:
        """Calculate macro-averaged metrics."""
        if not class_metrics:
            return 0.0, 0.0, 0.0

        n = len(class_metrics)
        precision = sum(m.precision for m in class_metrics.values()) / n
        recall = sum(m.recall for m in class_metrics.values()) / n
        f1 = sum(m.f1_score for m in class_metrics.values()) / n

        return precision, recall, f1

    def _calculate_weighted_averages(
        self,
        class_metrics: Dict[str, ClassMetrics]
    ) -> Tuple[float, float, float]:
        """Calculate weighted-averaged metrics by support."""
        if not class_metrics:
            return 0.0, 0.0, 0.0

        total_support = sum(m.support for m in class_metrics.values())
        if total_support == 0:
            return 0.0, 0.0, 0.0

        precision = sum(m.precision * m.support for m in class_metrics.values()) / total_support
        recall = sum(m.recall * m.support for m in class_metrics.values()) / total_support
        f1 = sum(m.f1_score * m.support for m in class_metrics.values()) / total_support

        return precision, recall, f1

    def generate_report(self, result: CategoryValidatorReport) -> str:
        """
        Generate detailed validation report.
        
        Args:
            result: Validation result
            
        Returns:
            Formatted report string
        """
        lines = [
            "=" * 70,
            "CATEGORY-LEVEL VALIDATION REPORT",
            "=" * 70,
            "",
            f"Validation ID: {result.validation_id}",
            f"Validated At: {result.validated_at}",
            "",
            f"Overall Accuracy: {result.overall_accuracy:.4f} ({result.overall_accuracy:.2%})",
            f"Categories: {result.passed_categories}/{result.total_categories} passed",
            f"Overall Status: {'PASSED ✓' if result.overall_passed else 'FAILED ✗'}",
            "",
        ]

        # Per-category summary
        lines.append("-" * 70)
        lines.append("CATEGORY SUMMARY")
        lines.append("-" * 70)
        lines.append("")
        lines.append(f"{'Category':<15} {'Accuracy':>10} {'Threshold':>10} {'Status':>8} {'Samples':>8}")
        lines.append("-" * 55)

        for cat_name, cat_result in sorted(result.category_results.items()):
            status = "PASS" if cat_result.passed else "FAIL"
            lines.append(
                f"{cat_name:<15} {cat_result.accuracy:>10.2%} "
                f"{cat_result.threshold:>10.2%} {status:>8} {cat_result.total_samples:>8}"
            )

        # Detailed category results
        for cat_name, cat_result in sorted(result.category_results.items()):
            lines.extend([
                "",
                "=" * 70,
                f"CATEGORY: {cat_name.upper()}",
                "=" * 70,
                "",
                f"Accuracy: {cat_result.accuracy:.4f} ({cat_result.accuracy:.2%})",
                f"Threshold: {cat_result.threshold:.2%}",
                f"Status: {'PASSED ✓' if cat_result.passed else 'FAILED ✗'}",
                "",
                f"Macro Precision: {cat_result.macro_precision:.4f}",
                f"Macro Recall: {cat_result.macro_recall:.4f}",
                f"Macro F1: {cat_result.macro_f1:.4f}",
                "",
                f"Weighted Precision: {cat_result.weighted_precision:.4f}",
                f"Weighted Recall: {cat_result.weighted_recall:.4f}",
                f"Weighted F1: {cat_result.weighted_f1:.4f}",
            ])

            # Class-level metrics
            if cat_result.class_metrics:
                lines.extend([
                    "",
                    "Per-Class Metrics:",
                    "-" * 50,
                    f"{'Class':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>8}",
                    "-" * 50,
                ])
                for cls_name, cls_metrics in sorted(cat_result.class_metrics.items()):
                    lines.append(
                        f"{cls_name:<15} {cls_metrics.precision:>10.4f} "
                        f"{cls_metrics.recall:>10.4f} {cls_metrics.f1_score:>10.4f} "
                        f"{cls_metrics.support:>8}"
                    )

            # Confusion matrix
            if cat_result.confusion_matrix:
                lines.extend([
                    "",
                    "Confusion Matrix:",
                    "-" * 50,
                    cat_result.confusion_matrix.to_table(),
                ])

        # Global confusion matrix
        if result.global_confusion_matrix:
            lines.extend([
                "",
                "=" * 70,
                "GLOBAL CONFUSION MATRIX",
                "=" * 70,
                "",
                result.global_confusion_matrix.to_table(),
            ])

        lines.extend([
            "",
            "=" * 70,
            "END OF REPORT",
            "=" * 70,
        ])

        return "\n".join(lines)

    async def validate_by_category_type(
        self,
        predictions: List[Dict[str, Any]],
        category_type: CategoryType
    ) -> CategoryValidationResult:
        """
        Validate predictions for a specific category type.
        
        Args:
            predictions: All predictions
            category_type: Category type to filter
            
        Returns:
            CategoryValidationResult for the specific category
        """
        filtered = [p for p in predictions if p.get("category") == category_type.value]
        return self._validate_category(category_type.value, filtered)


def get_category_validator(
    category_thresholds: Optional[Dict[str, float]] = None
) -> CategoryValidator:
    """
    Factory function to create a category validator.
    
    Args:
        category_thresholds: Custom thresholds per category
        
    Returns:
        Configured CategoryValidator instance
    """
    return CategoryValidator(category_thresholds=category_thresholds)
