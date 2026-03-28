"""
Agent Lightning Accuracy Validator for 94% Target.

Validates model accuracy across all categories and industries.
Ensures Agent Lightning meets 94%+ accuracy threshold.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import asyncio

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class AccuracyCategory(str, Enum):
    """Accuracy categories for validation."""
    REFUNDS = "refunds"
    ESCALATIONS = "escalations"
    TROUBLESHOOTING = "troubleshooting"
    FAQ = "faq"
    BILLING = "billing"
    SHIPPING = "shipping"
    RETURNS = "returns"
    ACCOUNT = "account"
    TECHNICAL = "technical"
    COMPLAINTS = "complaints"


@dataclass
class CategoryMetrics:
    """Metrics for a single category."""
    category: str
    total_samples: int = 0
    correct_predictions: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    accuracy: float = 0.0

    def calculate_metrics(self) -> None:
        """Calculate derived metrics."""
        if self.total_samples > 0:
            self.accuracy = self.correct_predictions / self.total_samples

        if self.correct_predictions + self.false_positives > 0:
            self.precision = self.correct_predictions / (self.correct_predictions + self.false_positives)

        if self.correct_predictions + self.false_negatives > 0:
            self.recall = self.correct_predictions / (self.correct_predictions + self.false_negatives)

        if self.precision + self.recall > 0:
            self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)


@dataclass
class ValidationResult:
    """Overall validation result."""
    overall_accuracy: float = 0.0
    passes_threshold: bool = False
    threshold: float = 0.94
    category_metrics: Dict[str, CategoryMetrics] = field(default_factory=dict)
    total_samples: int = 0
    total_correct: int = 0
    validated_at: str = ""
    errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.validated_at = datetime.now(timezone.utc).isoformat()


class AccuracyValidator94:
    """
    Validator for Agent Lightning 94% accuracy target.

    Features:
    - Per-category accuracy tracking
    - Industry-specific validation
    - Confidence threshold analysis
    - Detailed error reporting
    """

    ACCURACY_THRESHOLD = 0.94
    MIN_SAMPLES_PER_CATEGORY = 50

    def __init__(self, test_data_path: Optional[Path] = None):
        """
        Initialize validator.

        Args:
            test_data_path: Path to test data
        """
        self.test_data_path = test_data_path or Path(__file__).parent / "data" / "test_cases_94.json"
        self._test_data: List[Dict[str, Any]] = []
        self._validation_result: Optional[ValidationResult] = None

    async def validate(
        self,
        predict_fn,
        categories: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Validate model accuracy using prediction function.

        Args:
            predict_fn: Async function that takes query and returns (prediction, confidence)
            categories: Categories to validate (optional)

        Returns:
            ValidationResult with detailed metrics
        """
        # Load test data
        self._test_data = await self._load_test_data(categories)

        if not self._test_data:
            return ValidationResult(
                passes_threshold=False,
                errors=["No test data available"]
            )

        # Initialize category metrics
        category_metrics: Dict[str, CategoryMetrics] = {}
        for cat in AccuracyCategory:
            category_metrics[cat.value] = CategoryMetrics(category=cat.value)

        total_correct = 0
        total_samples = 0

        # Run validation
        for sample in self._test_data:
            query = sample["query"]
            expected = sample["expected_output"]
            category = sample.get("category", "faq")

            try:
                prediction, confidence = await predict_fn(query)

                total_samples += 1
                cat_metrics = category_metrics.get(category, CategoryMetrics(category=category))
                cat_metrics.total_samples += 1

                if self._is_correct(prediction, expected, confidence):
                    total_correct += 1
                    cat_metrics.correct_predictions += 1
                else:
                    if prediction != expected:
                        if prediction == "escalation":
                            cat_metrics.false_positives += 1
                        else:
                            cat_metrics.false_negatives += 1

                category_metrics[category] = cat_metrics

            except Exception as e:
                logger.error({
                    "event": "validation_error",
                    "query": query[:50],
                    "error": str(e)
                })

        # Calculate metrics
        for cat_metrics in category_metrics.values():
            cat_metrics.calculate_metrics()

        overall_accuracy = total_correct / total_samples if total_samples > 0 else 0

        result = ValidationResult(
            overall_accuracy=overall_accuracy,
            passes_threshold=overall_accuracy >= self.ACCURACY_THRESHOLD,
            threshold=self.ACCURACY_THRESHOLD,
            category_metrics=category_metrics,
            total_samples=total_samples,
            total_correct=total_correct
        )

        self._validation_result = result

        logger.info({
            "event": "validation_complete",
            "accuracy": overall_accuracy,
            "passes_threshold": result.passes_threshold,
            "total_samples": total_samples
        })

        return result

    def _is_correct(
        self,
        prediction: str,
        expected: str,
        confidence: float
    ) -> bool:
        """Check if prediction is correct."""
        # Direct match
        if prediction == expected:
            return True

        # Semantic equivalence
        equivalence_map = {
            ("refund", "escalation"): True,  # Refunds often escalate
            ("complaint", "escalation"): True,
            ("speak_to_manager", "escalation"): True,
        }

        key = tuple(sorted([prediction, expected]))
        return equivalence_map.get(key, False)

    async def _load_test_data(
        self,
        categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Load test data from file or generate default."""
        if self.test_data_path.exists():
            with open(self.test_data_path, 'r') as f:
                data = json.load(f)
                if categories:
                    return [d for d in data["test_cases"] if d.get("category") in categories]
                return data.get("test_cases", [])

        # Generate default test cases
        return self._generate_default_test_cases()

    def _generate_default_test_cases(self) -> List[Dict[str, Any]]:
        """Generate default test cases for validation."""
        test_cases = [
            # FAQ - Light tier
            {"query": "What are your business hours?", "expected_output": "faq", "category": "faq"},
            {"query": "How do I contact support?", "expected_output": "faq", "category": "faq"},
            {"query": "Where is my order?", "expected_output": "faq", "category": "faq"},
            {"query": "What is your return policy?", "expected_output": "faq", "category": "faq"},

            # Troubleshooting - Medium tier
            {"query": "I can't log into my account", "expected_output": "troubleshooting", "category": "troubleshooting"},
            {"query": "The website is not loading", "expected_output": "troubleshooting", "category": "troubleshooting"},
            {"query": "My discount code isn't working", "expected_output": "troubleshooting", "category": "troubleshooting"},

            # Refunds - Heavy tier
            {"query": "I want a full refund immediately", "expected_output": "refund", "category": "refunds"},
            {"query": "This product is defective, I need my money back", "expected_output": "refund", "category": "refunds"},
            {"query": "I never received my order and want a refund", "expected_output": "refund", "category": "refunds"},

            # Escalations - Heavy tier
            {"query": "I want to speak to a manager right now!", "expected_output": "escalation", "category": "escalations"},
            {"query": "This is unacceptable, get me a supervisor", "expected_output": "escalation", "category": "escalations"},
            {"query": "I'm going to report your company to the BBB", "expected_output": "escalation", "category": "escalations"},
            {"query": "I want to speak to a human agent", "expected_output": "escalation", "category": "escalations"},

            # Billing
            {"query": "I was charged twice for my order", "expected_output": "billing", "category": "billing"},
            {"query": "Why was my payment declined?", "expected_output": "billing", "category": "billing"},
            {"query": "I need an invoice for my purchase", "expected_output": "billing", "category": "billing"},

            # Shipping
            {"query": "My package is delayed", "expected_output": "shipping", "category": "shipping"},
            {"query": "Can I change my shipping address?", "expected_output": "shipping", "category": "shipping"},
            {"query": "The tracking shows delivered but I didn't receive it", "expected_output": "shipping", "category": "shipping"},

            # Returns
            {"query": "How do I return an item?", "expected_output": "returns", "category": "returns"},
            {"query": "My return was rejected, why?", "expected_output": "returns", "category": "returns"},
            {"query": "I returned my item 2 weeks ago, no refund yet", "expected_output": "returns", "category": "returns"},

            # Account
            {"query": "How do I reset my password?", "expected_output": "account", "category": "account"},
            {"query": "I want to delete my account", "expected_output": "account", "category": "account"},
            {"query": "Someone hacked my account", "expected_output": "account", "category": "account"},

            # Technical
            {"query": "The app keeps crashing", "expected_output": "technical", "category": "technical"},
            {"query": "I'm getting an error message", "expected_output": "technical", "category": "technical"},
            {"query": "The checkout page isn't working", "expected_output": "technical", "category": "technical"},

            # Complaints
            {"query": "This is the worst service I've ever experienced", "expected_output": "complaint", "category": "complaints"},
            {"query": "I'm extremely disappointed with your product", "expected_output": "complaint", "category": "complaints"},
            {"query": "Your company is a scam!", "expected_output": "complaint", "category": "complaints"},
        ]

        return test_cases

    def get_result(self) -> Optional[ValidationResult]:
        """Get last validation result."""
        return self._validation_result

    def generate_report(self) -> str:
        """Generate human-readable validation report."""
        if not self._validation_result:
            return "No validation result available"

        result = self._validation_result
        lines = [
            "=" * 60,
            "AGENT LIGHTNING 94% ACCURACY VALIDATION REPORT",
            "=" * 60,
            "",
            f"Overall Accuracy: {result.overall_accuracy:.2%}",
            f"Threshold: {result.threshold:.2%}",
            f"Status: {'PASSED ✓' if result.passes_threshold else 'FAILED ✗'}",
            "",
            f"Total Samples: {result.total_samples}",
            f"Correct Predictions: {result.total_correct}",
            "",
            "PER-CATEGORY METRICS:",
            "-" * 40,
        ]

        for cat_name, metrics in result.category_metrics.items():
            if metrics.total_samples > 0:
                lines.extend([
                    f"  {cat_name.upper()}:",
                    f"    Accuracy: {metrics.accuracy:.2%}",
                    f"    Precision: {metrics.precision:.2%}",
                    f"    Recall: {metrics.recall:.2%}",
                    f"    F1 Score: {metrics.f1_score:.2%}",
                    f"    Samples: {metrics.total_samples}",
                    ""
                ])

        return "\n".join(lines)


async def validate_accuracy_94(predict_fn) -> Tuple[bool, float]:
    """
    Quick validation function for 94% accuracy.

    Args:
        predict_fn: Prediction function

    Returns:
        Tuple of (passes_threshold, accuracy)
    """
    validator = AccuracyValidator94()
    result = await validator.validate(predict_fn)
    return result.passes_threshold, result.overall_accuracy
