"""
PARWA Confidence Scorer Module.

Provides weighted average scoring for AI responses based on multiple factors.
Weights: 40% + 30% + 20% + 10% = 100%

Scoring Components:
1. Response Quality (40%): Completeness, relevance, clarity
2. Knowledge Match (30%): How well response matches knowledge base
3. Context Coherence (20%): Consistency with conversation context
4. Safety Score (10%): Compliance with safety guidelines
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.confidence.thresholds import (
    ConfidenceThresholds,
    ConfidenceAction,
)

logger = get_logger(__name__)


# Weight configuration (must sum to 1.0 / 100%)
WEIGHTS = {
    "response_quality": 0.40,     # 40% - Quality of the response content
    "knowledge_match": 0.30,      # 30% - Match with knowledge base
    "context_coherence": 0.20,    # 20% - Contextual consistency
    "safety_score": 0.10,         # 10% - Safety compliance
}


class ConfidenceBreakdown(BaseModel):
    """
    Breakdown of individual confidence components.

    Each score is between 0.0 and 1.0.
    """
    model_config = ConfigDict()

    response_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    knowledge_match: float = Field(default=0.0, ge=0.0, le=1.0)
    context_coherence: float = Field(default=0.0, ge=0.0, le=1.0)
    safety_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ConfidenceResult(BaseModel):
    """
    Complete confidence scoring result.

    Contains the overall score, breakdown, and recommended action.
    """
    model_config = ConfigDict()

    overall_score: float = Field(ge=0.0, le=1.0)
    breakdown: ConfidenceBreakdown
    action: ConfidenceAction
    weights: Dict[str, float] = Field(default_factory=lambda: WEIGHTS.copy())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfidenceScorer:
    """
    Confidence Scorer for AI-generated responses.

    Calculates a weighted average confidence score based on:
    - Response Quality (40%): Content completeness and relevance
    - Knowledge Match (30%): Alignment with knowledge base
    - Context Coherence (20%): Conversation consistency
    - Safety Score (10%): Compliance with safety rules

    Total weights: 0.40 + 0.30 + 0.20 + 0.10 = 1.0 (100%)
    """

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None) -> None:
        """
        Initialize the Confidence Scorer.

        Args:
            custom_weights: Optional custom weights dict. Must sum to 1.0
        """
        if custom_weights:
            self._validate_weights(custom_weights)
            self.weights = custom_weights
        else:
            self.weights = WEIGHTS.copy()

    def _validate_weights(self, weights: Dict[str, float]) -> None:
        """
        Validate that weights are properly configured.

        Args:
            weights: Dictionary of component weights

        Raises:
            ValueError: If weights are invalid
        """
        required_keys = {"response_quality", "knowledge_match",
                         "context_coherence", "safety_score"}

        if set(weights.keys()) != required_keys:
            raise ValueError(
                f"Weights must have keys: {required_keys}, got {set(weights.keys())}"
            )

        total = sum(weights.values())
        if not (0.99 <= total <= 1.01):  # Allow small floating point errors
            raise ValueError(
                f"Weights must sum to 1.0, got {total}"
            )

        for key, value in weights.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"Weight {key} must be between 0.0 and 1.0, got {value}"
                )

    def score(
        self,
        response_quality: float,
        knowledge_match: float,
        context_coherence: float,
        safety_score: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConfidenceResult:
        """
        Calculate weighted confidence score.

        Args:
            response_quality: Quality score (0.0-1.0), weight 40%
            knowledge_match: Knowledge match score (0.0-1.0), weight 30%
            context_coherence: Context coherence score (0.0-1.0), weight 20%
            safety_score: Safety score (0.0-1.0), weight 10%
            metadata: Optional additional metadata

        Returns:
            ConfidenceResult with overall score and breakdown

        Raises:
            ValueError: If any score is not between 0.0 and 1.0
        """
        # Validate all scores
        scores = {
            "response_quality": response_quality,
            "knowledge_match": knowledge_match,
            "context_coherence": context_coherence,
            "safety_score": safety_score,
        }

        for name, score in scores.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"{name} must be between 0.0 and 1.0, got {score}"
                )

        # Calculate weighted average
        overall_score = (
            response_quality * self.weights["response_quality"] +
            knowledge_match * self.weights["knowledge_match"] +
            context_coherence * self.weights["context_coherence"] +
            safety_score * self.weights["safety_score"]
        )

        # Clamp to handle floating point precision
        overall_score = max(0.0, min(1.0, overall_score))

        # Determine action
        action = ConfidenceThresholds.get_action(overall_score)

        # Create breakdown
        breakdown = ConfidenceBreakdown(
            response_quality=response_quality,
            knowledge_match=knowledge_match,
            context_coherence=context_coherence,
            safety_score=safety_score,
        )

        result = ConfidenceResult(
            overall_score=overall_score,
            breakdown=breakdown,
            action=action,
            weights=self.weights.copy(),
            metadata=metadata or {}
        )

        logger.info({
            "event": "confidence_scored",
            "overall_score": overall_score,
            "action": action.value,
            "breakdown": {
                "response_quality": response_quality,
                "knowledge_match": knowledge_match,
                "context_coherence": context_coherence,
                "safety_score": safety_score,
            }
        })

        return result

    def score_from_dict(
        self,
        scores: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConfidenceResult:
        """
        Calculate confidence from a dictionary of scores.

        Args:
            scores: Dict with keys: response_quality, knowledge_match,
                    context_coherence, safety_score
            metadata: Optional additional metadata

        Returns:
            ConfidenceResult with overall score and breakdown
        """
        return self.score(
            response_quality=scores.get("response_quality", 0.0),
            knowledge_match=scores.get("knowledge_match", 0.0),
            context_coherence=scores.get("context_coherence", 0.0),
            safety_score=scores.get("safety_score", 0.0),
            metadata=metadata
        )

    def quick_score(self, quality: float, match: float = 1.0) -> ConfidenceResult:
        """
        Quick scoring with default values for less critical scores.

        Provides sensible defaults for context_coherence (0.8) and safety_score (1.0).

        Args:
            quality: Response quality score (0.0-1.0)
            match: Knowledge match score (0.0-1.0), defaults to 1.0

        Returns:
            ConfidenceResult with calculated score
        """
        return self.score(
            response_quality=quality,
            knowledge_match=match,
            context_coherence=0.8,  # Default good coherence
            safety_score=1.0,       # Default safe
        )

    def get_weights(self) -> Dict[str, float]:
        """
        Get the current weight configuration.

        Returns:
            Dict of component weights
        """
        return self.weights.copy()

    def get_weight_percentages(self) -> Dict[str, str]:
        """
        Get weights as percentage strings.

        Returns:
            Dict with weights as percentage strings (e.g., "40%")
        """
        return {k: f"{v * 100:.0f}%" for k, v in self.weights.items()}

    @staticmethod
    def validate_weights_sum(weights: Dict[str, float]) -> bool:
        """
        Static method to validate weights sum to 100%.

        Args:
            weights: Dictionary of weights

        Returns:
            True if weights sum to approximately 1.0 (100%)
        """
        total = sum(weights.values())
        return 0.99 <= total <= 1.01


def calculate_confidence(
    response_quality: float,
    knowledge_match: float,
    context_coherence: float,
    safety_score: float,
) -> float:
    """
    Convenience function to calculate confidence score.

    Uses default weights: 40% + 30% + 20% + 10% = 100%

    Args:
        response_quality: Quality score (40% weight)
        knowledge_match: Knowledge match score (30% weight)
        context_coherence: Context coherence score (20% weight)
        safety_score: Safety score (10% weight)

    Returns:
        Weighted average confidence score (0.0-1.0)
    """
    scorer = ConfidenceScorer()
    result = scorer.score(
        response_quality=response_quality,
        knowledge_match=knowledge_match,
        context_coherence=context_coherence,
        safety_score=safety_score
    )
    return result.overall_score
