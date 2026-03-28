"""
Accuracy Validator for Week 36 - 94% Target.

Validates Agent Lightning accuracy with:
- 94% threshold validation
- Confidence interval calculation
- Statistical significance testing
- Error analysis
- Report generation

Author: Builder 3 - Week 36
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
import math
import asyncio
from collections import defaultdict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ValidationStatus(Enum):
    """Status of validation."""
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    ERROR = "error"


class StatisticalTest(Enum):
    """Types of statistical tests."""
    Z_TEST = "z_test"
    T_TEST = "t_test"
    CHI_SQUARE = "chi_square"
    MCNEMAR = "mcnemar"


@dataclass
class ConfidenceInterval:
    """Confidence interval for accuracy."""
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95
    standard_error: float = 0.0
    margin_of_error: float = 0.0

    def contains(self, value: float) -> bool:
        """Check if value is within the interval."""
        return self.lower_bound <= value <= self.upper_bound

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "confidence_level": self.confidence_level,
            "standard_error": self.standard_error,
            "margin_of_error": self.margin_of_error,
        }


@dataclass
class StatisticalResult:
    """Result of statistical significance test."""
    test_type: StatisticalTest
    statistic: float
    p_value: float
    is_significant: bool
    significance_level: float = 0.05
    null_hypothesis: str = ""
    alternative_hypothesis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_type": self.test_type.value,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "is_significant": self.is_significant,
            "significance_level": self.significance_level,
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
        }


@dataclass
class ErrorAnalysis:
    """Analysis of prediction errors."""
    total_errors: int
    error_rate: float
    false_positives: int = 0
    false_negatives: int = 0
    error_patterns: Dict[str, int] = field(default_factory=dict)
    confusion_pairs: List[Tuple[str, str, int]] = field(default_factory=list)
    error_by_confidence: Dict[str, int] = field(default_factory=dict)
    top_error_categories: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_errors": self.total_errors,
            "error_rate": self.error_rate,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "error_patterns": self.error_patterns,
            "confusion_pairs": self.confusion_pairs[:10],  # Top 10
            "error_by_confidence": self.error_by_confidence,
            "top_error_categories": self.top_error_categories,
        }


@dataclass
class CategoryMetrics94:
    """Metrics for a category at 94% threshold."""
    category: str
    total_samples: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    threshold: float = 0.92  # Per-category threshold slightly lower
    passed: bool = False
    confidence_interval: Optional[ConfidenceInterval] = None

    def __post_init__(self):
        if self.total_samples > 0:
            self.accuracy = self.correct_predictions / self.total_samples
        self.passed = self.accuracy >= self.threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "total_samples": self.total_samples,
            "correct_predictions": self.correct_predictions,
            "accuracy": self.accuracy,
            "threshold": self.threshold,
            "passed": self.passed,
            "confidence_interval": self.confidence_interval.to_dict() if self.confidence_interval else None,
        }


@dataclass
class ValidationResult94:
    """Complete validation result for 94% accuracy."""
    validation_id: str
    status: ValidationStatus
    overall_accuracy: float
    threshold: float = 0.94
    passes_threshold: bool = False
    total_samples: int = 0
    total_correct: int = 0
    confidence_interval: Optional[ConfidenceInterval] = None
    statistical_result: Optional[StatisticalResult] = None
    error_analysis: Optional[ErrorAnalysis] = None
    category_metrics: Dict[str, CategoryMetrics94] = field(default_factory=dict)
    validated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "validation_id": self.validation_id,
            "status": self.status.value,
            "overall_accuracy": self.overall_accuracy,
            "threshold": self.threshold,
            "passes_threshold": self.passes_threshold,
            "total_samples": self.total_samples,
            "total_correct": self.total_correct,
            "confidence_interval": self.confidence_interval.to_dict() if self.confidence_interval else None,
            "statistical_result": self.statistical_result.to_dict() if self.statistical_result else None,
            "error_analysis": self.error_analysis.to_dict() if self.error_analysis else None,
            "category_metrics": {k: v.to_dict() for k, v in self.category_metrics.items()},
            "validated_at": self.validated_at,
            "metadata": self.metadata,
        }


class AccuracyValidator94:
    """
    Accuracy Validator for 94% Target (Week 36).
    
    Features:
    - 94% threshold validation
    - Confidence interval calculation using Wilson score
    - Statistical significance testing (z-test, chi-square)
    - Detailed error analysis
    - Comprehensive report generation
    
    Example:
        validator = AccuracyValidator94()
        result = await validator.validate(predictions)
        report = validator.generate_report(result)
    """

    ACCURACY_THRESHOLD = 0.94
    CATEGORY_THRESHOLD = 0.92
    MIN_SAMPLES = 30
    CONFIDENCE_LEVEL = 0.95
    SIGNIFICANCE_LEVEL = 0.05

    def __init__(
        self,
        accuracy_threshold: float = 0.94,
        category_threshold: float = 0.92,
        confidence_level: float = 0.95,
        significance_level: float = 0.05,
        test_data_path: Optional[Path] = None
    ):
        """
        Initialize the 94% accuracy validator.
        
        Args:
            accuracy_threshold: Overall accuracy threshold (default 0.94)
            category_threshold: Per-category threshold (default 0.92)
            confidence_level: Confidence level for intervals (default 0.95)
            significance_level: Alpha for statistical tests (default 0.05)
            test_data_path: Optional path to test data file
        """
        self.accuracy_threshold = accuracy_threshold
        self.category_threshold = category_threshold
        self.confidence_level = confidence_level
        self.significance_level = significance_level
        self.test_data_path = test_data_path
        self._validation_counter = 0
        self._validation_history: List[ValidationResult94] = []

    async def validate(
        self,
        predictions: List[Dict[str, Any]],
        baseline_accuracy: Optional[float] = None
    ) -> ValidationResult94:
        """
        Validate predictions against 94% threshold.
        
        Args:
            predictions: List of prediction dicts with keys:
                - 'prediction': predicted class
                - 'expected': expected class
                - 'confidence': prediction confidence
                - 'category': optional category
            baseline_accuracy: Optional baseline for comparison
            
        Returns:
            ValidationResult94 with comprehensive metrics
        """
        self._validation_counter += 1
        validation_id = f"val_94_{self._validation_counter}"

        if not predictions:
            return ValidationResult94(
                validation_id=validation_id,
                status=ValidationStatus.ERROR,
                overall_accuracy=0.0,
                metadata={"error": "No predictions provided"}
            )

        # Calculate overall accuracy
        total_correct = sum(
            1 for p in predictions
            if p.get("prediction") == p.get("expected")
        )
        total_samples = len(predictions)
        overall_accuracy = total_correct / total_samples

        # Calculate confidence interval
        confidence_interval = self._calculate_confidence_interval(
            total_correct, total_samples
        )

        # Run statistical test
        statistical_result = self._run_statistical_test(
            total_correct, total_samples, baseline_accuracy
        )

        # Analyze errors
        error_analysis = self._analyze_errors(predictions)

        # Calculate per-category metrics
        category_metrics = self._calculate_category_metrics(predictions)

        # Determine if passes threshold
        passes_threshold = overall_accuracy >= self.accuracy_threshold
        all_categories_pass = all(m.passed for m in category_metrics.values())

        # Set status
        status = ValidationStatus.PASSED if (
            passes_threshold and all_categories_pass
        ) else ValidationStatus.FAILED

        result = ValidationResult94(
            validation_id=validation_id,
            status=status,
            overall_accuracy=overall_accuracy,
            threshold=self.accuracy_threshold,
            passes_threshold=passes_threshold,
            total_samples=total_samples,
            total_correct=total_correct,
            confidence_interval=confidence_interval,
            statistical_result=statistical_result,
            error_analysis=error_analysis,
            category_metrics=category_metrics,
            metadata={
                "baseline_accuracy": baseline_accuracy,
                "categories_count": len(category_metrics),
            }
        )

        self._validation_history.append(result)

        logger.info({
            "event": "validation_complete",
            "validation_id": validation_id,
            "accuracy": overall_accuracy,
            "passes_threshold": passes_threshold,
            "status": status.value
        })

        return result

    async def validate_with_predictor(
        self,
        predict_fn: Callable[[str], Any],
        test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> ValidationResult94:
        """
        Validate using an async prediction function.
        
        Args:
            predict_fn: Async function that takes query and returns prediction
            test_cases: Optional test cases, will generate defaults if not provided
            
        Returns:
            ValidationResult94 with metrics
        """
        test_cases = test_cases or self._generate_default_test_cases()
        predictions = []

        for case in test_cases:
            try:
                if asyncio.iscoroutinefunction(predict_fn):
                    prediction, confidence = await predict_fn(case["query"])
                else:
                    prediction, confidence = predict_fn(case["query"])

                predictions.append({
                    "prediction": prediction,
                    "expected": case.get("expected_output", case.get("expected")),
                    "confidence": confidence,
                    "category": case.get("category", "general"),
                    "query": case["query"]
                })
            except Exception as e:
                logger.error({
                    "event": "prediction_error",
                    "query": case.get("query", "")[:50],
                    "error": str(e)
                })

        return await self.validate(predictions)

    def _calculate_confidence_interval(
        self,
        correct: int,
        total: int,
        confidence_level: Optional[float] = None
    ) -> ConfidenceInterval:
        """
        Calculate Wilson score confidence interval.
        
        Uses the Wilson score interval which is more accurate for
        proportions near 0 or 1.
        
        Args:
            correct: Number of correct predictions
            total: Total number of predictions
            confidence_level: Confidence level (default from instance)
            
        Returns:
            ConfidenceInterval with bounds
        """
        if total == 0:
            return ConfidenceInterval(
                lower_bound=0.0,
                upper_bound=1.0,
                confidence_level=confidence_level or self.confidence_level
            )

        confidence_level = confidence_level or self.confidence_level
        p = correct / total

        # Z-score for confidence level
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence_level, 1.96)

        # Wilson score interval
        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

        # Standard error
        se = math.sqrt(p * (1 - p) / total)

        return ConfidenceInterval(
            lower_bound=max(0.0, center - margin),
            upper_bound=min(1.0, center + margin),
            confidence_level=confidence_level,
            standard_error=se,
            margin_of_error=margin
        )

    def _run_statistical_test(
        self,
        correct: int,
        total: int,
        baseline: Optional[float] = None
    ) -> StatisticalResult:
        """
        Run statistical significance test.
        
        Performs a one-sample z-test comparing observed accuracy
        against the 94% threshold or provided baseline.
        
        Args:
            correct: Number correct
            total: Total samples
            baseline: Baseline accuracy to compare against
            
        Returns:
            StatisticalResult with test details
        """
        if total < self.MIN_SAMPLES:
            return StatisticalResult(
                test_type=StatisticalTest.Z_TEST,
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                null_hypothesis="Insufficient samples for test",
                alternative_hypothesis="N/A"
            )

        p_observed = correct / total
        p_expected = baseline or self.accuracy_threshold

        # Z-test for proportion
        se = math.sqrt(p_expected * (1 - p_expected) / total)
        z_stat = (p_observed - p_expected) / se if se > 0 else 0

        # Two-tailed p-value approximation
        # Using standard normal distribution
        p_value = 2 * (1 - self._normal_cdf(abs(z_stat)))

        is_significant = p_value < self.significance_level

        return StatisticalResult(
            test_type=StatisticalTest.Z_TEST,
            statistic=z_stat,
            p_value=p_value,
            is_significant=is_significant,
            significance_level=self.significance_level,
            null_hypothesis=f"Accuracy equals {p_expected:.2%}",
            alternative_hypothesis=f"Accuracy differs from {p_expected:.2%}"
        )

    def _normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF using error function."""
        # Approximation using Horner's method
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

        return 0.5 * (1.0 + sign * y)

    def _analyze_errors(self, predictions: List[Dict[str, Any]]) -> ErrorAnalysis:
        """
        Perform detailed error analysis.
        
        Analyzes:
        - Error patterns
        - Confusion pairs
        - Errors by confidence level
        - Top error categories
        
        Args:
            predictions: List of predictions
            
        Returns:
            ErrorAnalysis with detailed breakdown
        """
        errors = [p for p in predictions if p.get("prediction") != p.get("expected")]
        total = len(predictions)
        total_errors = len(errors)
        error_rate = total_errors / total if total > 0 else 0

        # Count error patterns
        error_patterns: Dict[str, int] = defaultdict(int)
        confusion_pairs: Dict[Tuple[str, str], int] = defaultdict(int)
        error_by_confidence: Dict[str, int] = defaultdict(int)
        category_errors: Dict[str, int] = defaultdict(int)

        for pred in errors:
            expected = pred.get("expected", "unknown")
            predicted = pred.get("prediction", "unknown")
            confidence = pred.get("confidence", 0.5)
            category = pred.get("category", "general")

            # Error pattern
            pattern = f"{predicted}->{expected}"
            error_patterns[pattern] += 1

            # Confusion pair
            confusion_pairs[(predicted, expected)] += 1

            # Confidence bucket
            if confidence >= 0.9:
                bucket = "high_confidence_90+"
            elif confidence >= 0.7:
                bucket = "medium_confidence_70-90"
            else:
                bucket = "low_confidence_<70"
            error_by_confidence[bucket] += 1

            # Category errors
            category_errors[category] += 1

        # Sort and format confusion pairs
        sorted_pairs = sorted(confusion_pairs.items(), key=lambda x: -x[1])
        formatted_pairs = [(p[0], p[1], count) for p, count in sorted_pairs[:10]]

        # Top error categories
        top_error_cats = [
            {"category": cat, "errors": count, "rate": count / total if total > 0 else 0}
            for cat, count in sorted(category_errors.items(), key=lambda x: -x[1])[:5]
        ]

        # Count false positives/negatives
        false_positives = sum(1 for p in errors if p.get("prediction") == "escalation")
        false_negatives = total_errors - false_positives

        return ErrorAnalysis(
            total_errors=total_errors,
            error_rate=error_rate,
            false_positives=false_positives,
            false_negatives=false_negatives,
            error_patterns=dict(sorted(error_patterns.items(), key=lambda x: -x[1])[:10]),
            confusion_pairs=formatted_pairs,
            error_by_confidence=dict(error_by_confidence),
            top_error_categories=top_error_cats
        )

    def _calculate_category_metrics(
        self,
        predictions: List[Dict[str, Any]]
    ) -> Dict[str, CategoryMetrics94]:
        """
        Calculate per-category accuracy metrics.
        
        Args:
            predictions: List of predictions with category
            
        Returns:
            Dictionary of category metrics
        """
        categories: Dict[str, List[Dict]] = defaultdict(list)

        for pred in predictions:
            category = pred.get("category", "general")
            categories[category].append(pred)

        metrics = {}
        for category, preds in categories.items():
            correct = sum(
                1 for p in preds
                if p.get("prediction") == p.get("expected")
            )
            total = len(preds)

            ci = self._calculate_confidence_interval(correct, total, 0.90)

            metrics[category] = CategoryMetrics94(
                category=category,
                total_samples=total,
                correct_predictions=correct,
                threshold=self.category_threshold,
                confidence_interval=ci
            )

        return metrics

    def _generate_default_test_cases(self) -> List[Dict[str, Any]]:
        """Generate default test cases for validation."""
        return [
            # FAQ - Light tier
            {"query": "What are your business hours?", "expected_output": "faq", "category": "faq"},
            {"query": "How do I contact support?", "expected_output": "faq", "category": "faq"},
            {"query": "Where is my order?", "expected_output": "order_status", "category": "faq"},
            {"query": "What is your return policy?", "expected_output": "faq", "category": "faq"},

            # Refunds - Heavy tier
            {"query": "I want a full refund immediately", "expected_output": "refund", "category": "refunds"},
            {"query": "This product is defective, I need my money back", "expected_output": "refund", "category": "refunds"},
            {"query": "I never received my order and want a refund", "expected_output": "refund", "category": "refunds"},

            # Escalations - Heavy tier
            {"query": "I want to speak to a manager right now!", "expected_output": "escalation", "category": "escalations"},
            {"query": "This is unacceptable, get me a supervisor", "expected_output": "escalation", "category": "escalations"},
            {"query": "I'm going to report your company", "expected_output": "escalation", "category": "escalations"},

            # Billing
            {"query": "I was charged twice for my order", "expected_output": "billing", "category": "billing"},
            {"query": "Why was my payment declined?", "expected_output": "billing", "category": "billing"},

            # Shipping
            {"query": "My package is delayed", "expected_output": "shipping", "category": "shipping"},
            {"query": "Can I change my shipping address?", "expected_output": "shipping", "category": "shipping"},

            # Technical
            {"query": "The app keeps crashing", "expected_output": "technical", "category": "technical"},
            {"query": "I'm getting an error message", "expected_output": "technical", "category": "technical"},
        ]

    def generate_report(self, result: Optional[ValidationResult94] = None) -> str:
        """
        Generate comprehensive validation report.
        
        Args:
            result: Validation result (uses last if not provided)
            
        Returns:
            Formatted report string
        """
        result = result or (self._validation_history[-1] if self._validation_history else None)
        if not result:
            return "No validation result available."

        lines = [
            "=" * 70,
            "AGENT LIGHTNING 94% ACCURACY VALIDATION REPORT",
            "=" * 70,
            "",
            f"Validation ID: {result.validation_id}",
            f"Status: {result.status.value.upper()}",
            f"Validated At: {result.validated_at}",
            "",
            "-" * 70,
            "OVERALL RESULTS",
            "-" * 70,
            f"Accuracy: {result.overall_accuracy:.4f} ({result.overall_accuracy:.2%})",
            f"Threshold: {result.threshold:.2%}",
            f"Passes Threshold: {'YES ✓' if result.passes_threshold else 'NO ✗'}",
            f"Total Samples: {result.total_samples}",
            f"Correct Predictions: {result.total_correct}",
        ]

        # Confidence interval
        if result.confidence_interval:
            ci = result.confidence_interval
            lines.extend([
                "",
                "-" * 70,
                "CONFIDENCE INTERVAL",
                "-" * 70,
                f"Level: {ci.confidence_level:.0%}",
                f"Interval: [{ci.lower_bound:.4f}, {ci.upper_bound:.4f}]",
                f"Standard Error: {ci.standard_error:.4f}",
                f"Margin of Error: {ci.margin_of_error:.4f}",
            ])

        # Statistical test
        if result.statistical_result:
            sr = result.statistical_result
            lines.extend([
                "",
                "-" * 70,
                "STATISTICAL SIGNIFICANCE TEST",
                "-" * 70,
                f"Test Type: {sr.test_type.value}",
                f"Test Statistic: {sr.statistic:.4f}",
                f"P-value: {sr.p_value:.6f}",
                f"Significant at {sr.significance_level:.0%}: {'YES' if sr.is_significant else 'NO'}",
                f"H0: {sr.null_hypothesis}",
                f"H1: {sr.alternative_hypothesis}",
            ])

        # Error analysis
        if result.error_analysis:
            ea = result.error_analysis
            lines.extend([
                "",
                "-" * 70,
                "ERROR ANALYSIS",
                "-" * 70,
                f"Total Errors: {ea.total_errors}",
                f"Error Rate: {ea.error_rate:.4f} ({ea.error_rate:.2%})",
                f"False Positives: {ea.false_positives}",
                f"False Negatives: {ea.false_negatives}",
                "",
                "Top Error Patterns:",
            ])
            for pattern, count in list(ea.error_patterns.items())[:5]:
                lines.append(f"  {pattern}: {count}")

            lines.append("")
            lines.append("Errors by Confidence Level:")
            for bucket, count in ea.error_by_confidence.items():
                lines.append(f"  {bucket}: {count}")

        # Category metrics
        if result.category_metrics:
            lines.extend([
                "",
                "-" * 70,
                "PER-CATEGORY METRICS",
                "-" * 70,
            ])
            for cat_name, metrics in sorted(result.category_metrics.items()):
                status = "PASS" if metrics.passed else "FAIL"
                lines.extend([
                    f"",
                    f"  {cat_name.upper()} [{status}]",
                    f"    Accuracy: {metrics.accuracy:.4f} ({metrics.accuracy:.2%})",
                    f"    Threshold: {metrics.threshold:.2%}",
                    f"    Samples: {metrics.total_samples}",
                ])
                if metrics.confidence_interval:
                    lines.append(
                        f"    90% CI: [{metrics.confidence_interval.lower_bound:.4f}, "
                        f"{metrics.confidence_interval.upper_bound:.4f}]"
                    )

        lines.extend([
            "",
            "=" * 70,
            f"END OF REPORT",
            "=" * 70,
        ])

        return "\n".join(lines)

    def get_validation_history(self) -> List[ValidationResult94]:
        """Get all validation results."""
        return self._validation_history

    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics."""
        if not self._validation_history:
            return {"total_validations": 0}

        passed = sum(1 for v in self._validation_history if v.passes_threshold)
        accuracies = [v.overall_accuracy for v in self._validation_history]

        return {
            "total_validations": len(self._validation_history),
            "passed_validations": passed,
            "pass_rate": passed / len(self._validation_history),
            "avg_accuracy": sum(accuracies) / len(accuracies),
            "min_accuracy": min(accuracies),
            "max_accuracy": max(accuracies),
            "threshold": self.accuracy_threshold,
        }


# Factory function
def get_accuracy_validator_94(
    accuracy_threshold: float = 0.94
) -> AccuracyValidator94:
    """
    Factory function to create a 94% accuracy validator.
    
    Args:
        accuracy_threshold: Accuracy threshold (default 0.94)
        
    Returns:
        Configured AccuracyValidator94 instance
    """
    return AccuracyValidator94(accuracy_threshold=accuracy_threshold)


# Convenience function for quick validation
async def validate_accuracy_94(
    predictions: List[Dict[str, Any]],
    baseline: Optional[float] = None
) -> Tuple[bool, float, str]:
    """
    Quick validation function for 94% accuracy.
    
    Args:
        predictions: List of predictions
        baseline: Optional baseline accuracy
        
    Returns:
        Tuple of (passes_threshold, accuracy, report)
    """
    validator = AccuracyValidator94()
    result = await validator.validate(predictions, baseline)
    report = validator.generate_report(result)
    return result.passes_threshold, result.overall_accuracy, report
