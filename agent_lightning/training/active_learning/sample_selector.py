"""
Sample Selector for Active Learning.

Prioritizes high-value samples for training based on:
- Diversity
- Representativeness
- Information gain
- Budget constraints
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
import logging
import random
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class SelectionConfig:
    """Configuration for sample selection."""
    budget: int = 10
    diversity_weight: float = 0.3
    uncertainty_weight: float = 0.4
    representativeness_weight: float = 0.3
    min_per_class: int = 1
    max_per_class: int = 5
    seed: Optional[int] = None


@dataclass
class SelectedSample:
    """A selected training sample."""
    sample_id: str
    query: str
    intent: str
    response: Optional[str] = None
    uncertainty_score: float = 0.0
    diversity_score: float = 0.0
    representativeness_score: float = 0.0
    overall_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SampleSelector:
    """
    Selects high-value samples for active learning.

    Combines multiple selection criteria to maximize
    the information gain from human annotations.
    """

    def __init__(self, config: Optional[SelectionConfig] = None):
        """
        Initialize the sample selector.

        Args:
            config: Selection configuration
        """
        self.config = config or SelectionConfig()
        if self.config.seed is not None:
            random.seed(self.config.seed)
        self._selected_samples: List[SelectedSample] = []
        self._seen_intents: Set[str] = set()

    def calculate_diversity(
        self,
        sample: Dict[str, Any],
        selected: List[SelectedSample]
    ) -> float:
        """
        Calculate diversity score for a sample.

        Higher score for samples different from already selected ones.

        Args:
            sample: Candidate sample
            selected: Already selected samples

        Returns:
            Diversity score in [0, 1]
        """
        if not selected:
            return 1.0

        sample_intent = sample.get("intent", "")
        sample_words = set(sample.get("query", "").lower().split())

        # Check intent diversity
        selected_intents = [s.intent for s in selected]
        intent_diversity = 1.0 if sample_intent not in selected_intents else 0.5

        # Check word overlap diversity
        max_overlap = 0.0
        for sel in selected:
            sel_words = set(sel.query.lower().split())
            if sample_words and sel_words:
                overlap = len(sample_words & sel_words) / len(sample_words | sel_words)
                max_overlap = max(max_overlap, overlap)

        word_diversity = 1.0 - max_overlap

        # Combined diversity
        return 0.5 * intent_diversity + 0.5 * word_diversity

    def calculate_representativeness(
        self,
        sample: Dict[str, Any],
        all_samples: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate how representative a sample is of the distribution.

        Args:
            sample: Candidate sample
            all_samples: All available samples

        Returns:
            Representativeness score in [0, 1]
        """
        if not all_samples:
            return 0.5

        sample_intent = sample.get("intent", "")

        # Count intent distribution
        intent_counts = Counter(s.get("intent", "") for s in all_samples)
        intent_freq = intent_counts.get(sample_intent, 0) / len(all_samples)

        # Samples from common intents are more representative
        # But we also want some coverage of rare intents
        # Optimal is around 0.3-0.5 frequency
        optimal_freq = 0.3
        representativeness = 1.0 - abs(intent_freq - optimal_freq)

        return representativeness

    def score_sample(
        self,
        sample: Dict[str, Any],
        all_samples: List[Dict[str, Any]],
        selected: List[SelectedSample]
    ) -> SelectedSample:
        """
        Calculate overall score for a sample.

        Args:
            sample: Candidate sample
            all_samples: All available samples
            selected: Already selected samples

        Returns:
            SelectedSample with scores
        """
        uncertainty = sample.get("uncertainty_score", 0.5)
        diversity = self.calculate_diversity(sample, selected)
        representativeness = self.calculate_representativeness(sample, all_samples)

        overall = (
            self.config.uncertainty_weight * uncertainty +
            self.config.diversity_weight * diversity +
            self.config.representativeness_weight * representativeness
        )

        return SelectedSample(
            sample_id=sample.get("id", f"sample_{len(selected)}"),
            query=sample.get("query", ""),
            intent=sample.get("intent", ""),
            response=sample.get("response"),
            uncertainty_score=uncertainty,
            diversity_score=diversity,
            representativeness_score=representativeness,
            overall_score=overall,
            metadata=sample.get("metadata", {})
        )

    def select_samples(
        self,
        candidates: List[Dict[str, Any]]
    ) -> List[SelectedSample]:
        """
        Select the best samples for annotation.

        Args:
            candidates: Candidate samples with uncertainty scores

        Returns:
            List of selected samples
        """
        selected: List[SelectedSample] = []
        intent_counts: Dict[str, int] = {}

        # Score all candidates
        scored = [
            self.score_sample(sample, candidates, selected)
            for sample in candidates
        ]

        # Sort by overall score
        scored.sort(key=lambda x: x.overall_score, reverse=True)

        # Select with budget and class balance constraints
        for sample in scored:
            if len(selected) >= self.config.budget:
                break

            intent = sample.intent
            current_count = intent_counts.get(intent, 0)

            # Check class balance constraints
            if current_count >= self.config.max_per_class:
                continue

            # Prefer samples from underrepresented classes
            if len(intent_counts) < len(set(s.get("intent") for s in candidates)):
                if intent in intent_counts and current_count >= self.config.min_per_class:
                    # Skip if we haven't covered all intents yet
                    continue

            selected.append(sample)
            intent_counts[intent] = current_count + 1
            self._seen_intents.add(intent)

        self._selected_samples.extend(selected)

        logger.info(
            f"Selected {len(selected)} samples from {len(candidates)} candidates, "
            f"covering {len(intent_counts)} intents"
        )

        return selected

    def get_selection_stats(self) -> Dict[str, Any]:
        """Get selection statistics."""
        if not self._selected_samples:
            return {"total_selected": 0}

        avg_uncertainty = sum(
            s.uncertainty_score for s in self._selected_samples
        ) / len(self._selected_samples)
        avg_diversity = sum(
            s.diversity_score for s in self._selected_samples
        ) / len(self._selected_samples)

        return {
            "total_selected": len(self._selected_samples),
            "unique_intents": len(self._seen_intents),
            "avg_uncertainty": avg_uncertainty,
            "avg_diversity": avg_diversity,
            "budget": self.config.budget
        }


def get_sample_selector(
    budget: int = 10,
    diversity_weight: float = 0.3,
    uncertainty_weight: float = 0.4
) -> SampleSelector:
    """
    Factory function to create a sample selector.

    Args:
        budget: Maximum samples to select
        diversity_weight: Weight for diversity criterion
        uncertainty_weight: Weight for uncertainty criterion

    Returns:
        Configured SampleSelector instance
    """
    config = SelectionConfig(
        budget=budget,
        diversity_weight=diversity_weight,
        uncertainty_weight=uncertainty_weight
    )
    return SampleSelector(config=config)
