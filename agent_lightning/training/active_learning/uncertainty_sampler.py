"""
Uncertainty Sampler for Active Learning.

Identifies low-confidence predictions for human review.
Sampling strategies:
- Entropy-based sampling
- Margin sampling
- Query-by-committee
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import math
import logging

logger = logging.getLogger(__name__)


class SamplingStrategy(Enum):
    """Available uncertainty sampling strategies."""
    ENTROPY = "entropy"
    MARGIN = "margin"
    LEAST_CONFIDENT = "least_confident"
    QUERY_BY_COMMITTEE = "query_by_committee"


@dataclass
class UncertaintyResult:
    """Result of uncertainty sampling analysis."""
    sample_id: str
    query: str
    prediction: str
    confidence: float
    uncertainty_score: float
    strategy: SamplingStrategy
    probabilities: Dict[str, float] = field(default_factory=dict)
    committee_disagreement: Optional[float] = None
    selected: bool = False

    @property
    def is_uncertain(self) -> bool:
        """Check if sample is below confidence threshold."""
        return self.confidence < 0.70  # <70% confidence threshold


class UncertaintySampler:
    """
    Identifies samples where the model is most uncertain.

    Used to prioritize which samples should be reviewed by humans
    for active learning improvement.
    """

    UNCERTAINTY_THRESHOLD: float = 0.70
    MIN_SAMPLES_FOR_COMMITTEE: int = 3

    def __init__(
        self,
        strategy: SamplingStrategy = SamplingStrategy.ENTROPY,
        threshold: float = 0.70,
        committee_size: int = 3
    ):
        """
        Initialize the uncertainty sampler.

        Args:
            strategy: Sampling strategy to use
            threshold: Confidence threshold below which samples are uncertain
            committee_size: Number of models for query-by-committee
        """
        self.strategy = strategy
        self.threshold = threshold
        self.committee_size = committee_size
        self._sampled_count = 0

    def calculate_uncertainty(
        self,
        query: str,
        prediction: str,
        probabilities: Dict[str, float],
        committee_predictions: Optional[List[str]] = None
    ) -> UncertaintyResult:
        """
        Calculate uncertainty score for a prediction.

        Args:
            query: The input query
            prediction: The model's prediction
            probabilities: Probability distribution over all classes
            committee_predictions: Predictions from committee members (optional)

        Returns:
            UncertaintyResult with uncertainty metrics
        """
        confidence = probabilities.get(prediction, 0.0)

        if self.strategy == SamplingStrategy.ENTROPY:
            uncertainty_score = self._entropy_score(probabilities)
        elif self.strategy == SamplingStrategy.MARGIN:
            uncertainty_score = self._margin_score(probabilities)
        elif self.strategy == SamplingStrategy.LEAST_CONFIDENT:
            uncertainty_score = 1.0 - confidence
        elif self.strategy == SamplingStrategy.QUERY_BY_COMMITTEE:
            uncertainty_score = self._committee_score(
                probabilities, committee_predictions
            )
        else:
            uncertainty_score = 1.0 - confidence

        return UncertaintyResult(
            sample_id=f"sample_{self._sampled_count}",
            query=query,
            prediction=prediction,
            confidence=confidence,
            uncertainty_score=uncertainty_score,
            strategy=self.strategy,
            probabilities=probabilities,
            committee_disagreement=(
                self._calculate_disagreement(committee_predictions)
                if committee_predictions else None
            ),
            selected=False
        )

    def _entropy_score(self, probabilities: Dict[str, float]) -> float:
        """Calculate entropy-based uncertainty score."""
        entropy = 0.0
        for prob in probabilities.values():
            if prob > 0:
                entropy -= prob * math.log2(prob)
        # Normalize to [0, 1]
        max_entropy = math.log2(len(probabilities)) if len(probabilities) > 1 else 1
        return entropy / max_entropy if max_entropy > 0 else 0.0

    def _margin_score(self, probabilities: Dict[str, float]) -> float:
        """Calculate margin-based uncertainty (1 - margin)."""
        sorted_probs = sorted(probabilities.values(), reverse=True)
        if len(sorted_probs) >= 2:
            margin = sorted_probs[0] - sorted_probs[1]
            return 1.0 - margin
        return 1.0

    def _committee_score(
        self,
        probabilities: Dict[str, float],
        committee_predictions: Optional[List[str]] = None
    ) -> float:
        """Calculate query-by-committee uncertainty."""
        if not committee_predictions or len(committee_predictions) < 2:
            # Fall back to entropy if no committee
            return self._entropy_score(probabilities)

        # Count votes for each prediction
        vote_counts: Dict[str, int] = {}
        for pred in committee_predictions:
            vote_counts[pred] = vote_counts.get(pred, 0) + 1

        # Uncertainty is based on disagreement
        max_votes = max(vote_counts.values())
        agreement_rate = max_votes / len(committee_predictions)
        return 1.0 - agreement_rate

    def _calculate_disagreement(
        self,
        committee_predictions: Optional[List[str]] = None
    ) -> Optional[float]:
        """Calculate disagreement level among committee."""
        if not committee_predictions or len(committee_predictions) < 2:
            return None

        unique_predictions = set(committee_predictions)
        disagreement = (len(unique_predictions) - 1) / (len(committee_predictions) - 1)
        return disagreement

    def select_uncertain_samples(
        self,
        predictions: List[Dict[str, Any]],
        budget: int = 10
    ) -> List[UncertaintyResult]:
        """
        Select the most uncertain samples for human review.

        Args:
            predictions: List of prediction dicts with query, prediction, probabilities
            budget: Maximum number of samples to select

        Returns:
            List of selected UncertaintyResults sorted by uncertainty
        """
        results = []

        for pred in predictions:
            result = self.calculate_uncertainty(
                query=pred.get("query", ""),
                prediction=pred.get("prediction", ""),
                probabilities=pred.get("probabilities", {}),
                committee_predictions=pred.get("committee_predictions")
            )
            results.append(result)
            self._sampled_count += 1

        # Sort by uncertainty score (descending)
        results.sort(key=lambda x: x.uncertainty_score, reverse=True)

        # Select top uncertain samples
        selected = []
        for result in results[:budget]:
            if result.confidence < self.threshold:
                result.selected = True
                selected.append(result)

        logger.info(
            f"Selected {len(selected)} uncertain samples from {len(predictions)} "
            f"predictions using {self.strategy.value} strategy"
        )

        return selected

    def get_sampling_stats(self) -> Dict[str, Any]:
        """Get sampling statistics."""
        return {
            "strategy": self.strategy.value,
            "threshold": self.threshold,
            "total_sampled": self._sampled_count,
            "committee_size": self.committee_size
        }


def get_uncertainty_sampler(
    strategy: str = "entropy",
    threshold: float = 0.70
) -> UncertaintySampler:
    """
    Factory function to create an uncertainty sampler.

    Args:
        strategy: Sampling strategy name
        threshold: Confidence threshold

    Returns:
        Configured UncertaintySampler instance
    """
    strategy_enum = SamplingStrategy(strategy)
    return UncertaintySampler(strategy=strategy_enum, threshold=threshold)
