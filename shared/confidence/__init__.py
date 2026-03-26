"""
PARWA Confidence Module.

Provides confidence scoring, thresholds, and routing decisions
for AI-generated responses.

Components:
- ConfidenceThresholds: GRADUATE=95%, ESCALATE=70% thresholds
- ConfidenceScorer: Weighted avg scoring (40%+30%+20%+10%=100%)
- ConfidenceAction: Actions based on confidence (GRADUATE, CONTINUE, ESCALATE)
"""

from shared.confidence.thresholds import (
    ConfidenceThresholds,
    ConfidenceAction,
    get_confidence_action,
    should_escalate,
    can_graduate,
)
from shared.confidence.scorer import (
    ConfidenceScorer,
    ConfidenceBreakdown,
    ConfidenceResult,
    WEIGHTS,
    calculate_confidence,
)

__all__ = [
    # Thresholds
    "ConfidenceThresholds",
    "ConfidenceAction",
    "get_confidence_action",
    "should_escalate",
    "can_graduate",
    # Scorer
    "ConfidenceScorer",
    "ConfidenceBreakdown",
    "ConfidenceResult",
    "WEIGHTS",
    "calculate_confidence",
]
