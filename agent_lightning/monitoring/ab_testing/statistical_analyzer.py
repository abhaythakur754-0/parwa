"""
Statistical Analyzer for A/B Testing.

Performs statistical analysis:
- Significance testing
- Confidence intervals
- Effect size estimation
- Sample size calculation
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import math
import logging

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence levels for statistical tests."""
    P90 = 0.90  # 1.645 z-score
    P95 = 0.95  # 1.96 z-score
    P99 = 0.99  # 2.576 z-score


@dataclass
class SignificanceResult:
    """Result of significance testing."""
    is_significant: bool
    p_value: float
    confidence_level: ConfidenceLevel
    effect_size: float
    control_mean: float
    treatment_mean: float
    improvement: float
    confidence_interval: Tuple[float, float]
    sample_size_control: int
    sample_size_treatment: int
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_significant": self.is_significant,
            "p_value": self.p_value,
            "confidence_level": self.confidence_level.value,
            "effect_size": self.effect_size,
            "control_mean": self.control_mean,
            "treatment_mean": self.treatment_mean,
            "improvement": self.improvement,
            "confidence_interval": list(self.confidence_interval),
            "sample_size_control": self.sample_size_control,
            "sample_size_treatment": self.sample_size_treatment,
            "recommendation": self.recommendation,
        }


class StatisticalAnalyzer:
    """
    Performs statistical analysis for A/B tests.

    Features:
    - Statistical significance testing
    - Confidence interval calculation
    - Effect size estimation
    - Sample size calculation
    """

    # Z-scores for confidence levels
    Z_SCORES = {
        ConfidenceLevel.P90: 1.645,
        ConfidenceLevel.P95: 1.96,
        ConfidenceLevel.P99: 2.576,
    }

    def __init__(
        self,
        confidence_level: ConfidenceLevel = ConfidenceLevel.P95,
        minimum_detectable_effect: float = 0.02
    ):
        """
        Initialize the statistical analyzer.

        Args:
            confidence_level: Confidence level for tests
            minimum_detectable_effect: Minimum effect size to detect
        """
        self.confidence_level = confidence_level
        self.minimum_detectable_effect = minimum_detectable_effect

    def _z_score(self) -> float:
        """Get z-score for current confidence level."""
        return self.Z_SCORES[self.confidence_level]

    def calculate_significance(
        self,
        control_successes: int,
        control_total: int,
        treatment_successes: int,
        treatment_total: int
    ) -> SignificanceResult:
        """
        Calculate statistical significance using two-proportion z-test.

        Args:
            control_successes: Number of successes in control
            control_total: Total samples in control
            treatment_successes: Number of successes in treatment
            treatment_total: Total samples in treatment

        Returns:
            SignificanceResult with test results
        """
        # Calculate proportions
        p_control = control_successes / control_total if control_total > 0 else 0
        p_treatment = treatment_successes / treatment_total if treatment_total > 0 else 0

        # Pooled proportion
        pooled_p = (control_successes + treatment_successes) / (control_total + treatment_total)

        # Standard error
        se = math.sqrt(
            pooled_p * (1 - pooled_p) * (1/control_total + 1/treatment_total)
        ) if pooled_p > 0 and pooled_p < 1 else 0.001

        # Z-statistic
        z = (p_treatment - p_control) / se if se > 0 else 0

        # P-value (two-tailed)
        # Using approximation for standard normal
        p_value = 2 * (1 - self._normal_cdf(abs(z)))

        # Effect size (Cohen's h)
        effect_size = self._cohens_h(p_control, p_treatment)

        # Improvement
        improvement = p_treatment - p_control

        # Confidence interval for difference
        z_score = self._z_score()
        margin = z_score * se
        ci_lower = improvement - margin
        ci_upper = improvement + margin

        # Determine significance
        is_significant = p_value < (1 - self.confidence_level.value)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            is_significant, improvement, p_control, p_treatment
        )

        return SignificanceResult(
            is_significant=is_significant,
            p_value=p_value,
            confidence_level=self.confidence_level,
            effect_size=effect_size,
            control_mean=p_control,
            treatment_mean=p_treatment,
            improvement=improvement,
            confidence_interval=(ci_lower, ci_upper),
            sample_size_control=control_total,
            sample_size_treatment=treatment_total,
            recommendation=recommendation
        )

    def _normal_cdf(self, x: float) -> float:
        """Approximate standard normal CDF."""
        # Approximation using error function
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _cohens_h(self, p1: float, p2: float) -> float:
        """Calculate Cohen's h effect size for proportions."""
        if p1 <= 0 or p1 >= 1 or p2 <= 0 or p2 >= 1:
            return 0.0
        phi1 = 2 * math.asin(math.sqrt(p1))
        phi2 = 2 * math.asin(math.sqrt(p2))
        return phi2 - phi1

    def _generate_recommendation(
        self,
        is_significant: bool,
        improvement: float,
        control: float,
        treatment: float
    ) -> str:
        """Generate recommendation based on results."""
        if not is_significant:
            return "Continue experiment - no significant difference detected"

        if improvement > 0.02:  # >2% improvement
            return "Deploy treatment - significant positive improvement"
        elif improvement > 0:
            return "Consider deployment - small but significant improvement"
        elif improvement < -0.02:
            return "Keep control - treatment performs significantly worse"
        else:
            return "No action needed - marginal difference"

    def calculate_sample_size(
        self,
        baseline_rate: float,
        minimum_detectable_effect: Optional[float] = None,
        power: float = 0.80
    ) -> int:
        """
        Calculate required sample size per variant.

        Args:
            baseline_rate: Expected baseline conversion rate
            minimum_detectable_effect: Minimum effect to detect
            power: Statistical power (1 - beta)

        Returns:
            Required sample size per variant
        """
        mde = minimum_detectable_effect or self.minimum_detectable_effect

        # Expected treatment rate
        treatment_rate = baseline_rate + mde

        # Z-scores
        z_alpha = self._z_score()  # For significance level
        z_beta = 0.84 if power == 0.80 else 1.28 if power == 0.90 else 0.524  # For power

        # Sample size formula for two proportions
        p_pooled = (baseline_rate + treatment_rate) / 2

        numerator = (
            (z_alpha * math.sqrt(2 * p_pooled * (1 - p_pooled)) +
             z_beta * math.sqrt(baseline_rate * (1 - baseline_rate) +
                               treatment_rate * (1 - treatment_rate))) ** 2
        )
        denominator = (treatment_rate - baseline_rate) ** 2

        n = numerator / denominator if denominator > 0 else 1000

        return int(math.ceil(n))

    def calculate_confidence_interval(
        self,
        mean: float,
        std_dev: float,
        sample_size: int
    ) -> Tuple[float, float]:
        """
        Calculate confidence interval for a mean.

        Args:
            mean: Sample mean
            std_dev: Sample standard deviation
            sample_size: Sample size

        Returns:
            Tuple of (lower, upper) bounds
        """
        if sample_size < 2:
            return (mean, mean)

        se = std_dev / math.sqrt(sample_size)
        margin = self._z_score() * se

        return (mean - margin, mean + margin)

    def determine_winner(
        self,
        control_accuracy: float,
        treatment_accuracy: float,
        is_significant: bool
    ) -> str:
        """
        Determine the winning variant.

        Args:
            control_accuracy: Control variant accuracy
            treatment_accuracy: Treatment variant accuracy
            is_significant: Whether difference is significant

        Returns:
            Winner variant name
        """
        if not is_significant:
            return "inconclusive"

        if treatment_accuracy > control_accuracy:
            return "treatment"
        else:
            return "control"

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            "confidence_level": self.confidence_level.value,
            "z_score": self._z_score(),
            "minimum_detectable_effect": self.minimum_detectable_effect,
        }


def get_statistical_analyzer(
    confidence_level: float = 0.95
) -> StatisticalAnalyzer:
    """
    Factory function to create a statistical analyzer.

    Args:
        confidence_level: Confidence level (0.90, 0.95, or 0.99)

    Returns:
        Configured StatisticalAnalyzer instance
    """
    level = ConfidenceLevel(confidence_level)
    return StatisticalAnalyzer(confidence_level=level)
