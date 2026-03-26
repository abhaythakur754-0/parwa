"""
PARWA Confidence Thresholds Module.

Defines the confidence thresholds for AI response routing decisions.
- GRADUATE: Confidence level at which response can proceed autonomously
- ESCALATE: Confidence level below which human escalation is required
"""
from enum import Enum
from typing import Dict, Any


class ConfidenceAction(str, Enum):
    """
    Actions based on confidence score.

    Actions determine how the system proceeds after evaluating confidence:
    - GRADUATE: High confidence, proceed autonomously
    - CONTINUE: Moderate confidence, proceed with monitoring
    - ESCALATE: Low confidence, require human intervention
    """
    GRADUATE = "graduate"      # >= 95% - autonomous, fully trusted
    CONTINUE = "continue"      # 70-95% - proceed with caution
    ESCALATE = "escalate"      # < 70% - human intervention required


class ConfidenceThresholds:
    """
    Confidence thresholds for routing decisions.

    Thresholds define the boundaries between confidence actions:
    - GRADUATE_THRESHOLD: 95% (0.95) - Auto-proceed without human review
    - ESCALATE_THRESHOLD: 70% (0.70) - Requires human escalation

    These thresholds are calibrated based on:
    - PARWA's quality requirements
    - Risk tolerance for autonomous actions
    - Compliance and safety standards
    """

    # Core thresholds as specified in AGENT_COMMS.md
    GRADUATE_THRESHOLD: float = 0.95  # 95% confidence to proceed autonomously
    ESCALATE_THRESHOLD: float = 0.70  # 70% minimum to avoid escalation

    # Additional thresholds for fine-grained control
    HIGH_CONFIDENCE: float = 0.90     # High confidence zone
    MEDIUM_CONFIDENCE: float = 0.75   # Medium confidence zone
    LOW_CONFIDENCE: float = 0.50      # Low confidence zone

    @classmethod
    def get_action(cls, confidence_score: float) -> ConfidenceAction:
        """
        Determine the action based on confidence score.

        Args:
            confidence_score: Float between 0.0 and 1.0

        Returns:
            ConfidenceAction enum value

        Raises:
            ValueError: If confidence_score is not between 0.0 and 1.0
        """
        if not 0.0 <= confidence_score <= 1.0:
            raise ValueError(
                f"Confidence score must be between 0.0 and 1.0, got {confidence_score}"
            )

        if confidence_score >= cls.GRADUATE_THRESHOLD:
            return ConfidenceAction.GRADUATE
        elif confidence_score >= cls.ESCALATE_THRESHOLD:
            return ConfidenceAction.CONTINUE
        else:
            return ConfidenceAction.ESCALATE

    @classmethod
    def should_escalate(cls, confidence_score: float) -> bool:
        """
        Check if confidence score requires human escalation.

        Args:
            confidence_score: Float between 0.0 and 1.0

        Returns:
            True if escalation is required, False otherwise
        """
        return confidence_score < cls.ESCALATE_THRESHOLD

    @classmethod
    def can_graduate(cls, confidence_score: float) -> bool:
        """
        Check if confidence score allows autonomous graduation.

        Args:
            confidence_score: Float between 0.0 and 1.0

        Returns:
            True if can proceed autonomously, False otherwise
        """
        return confidence_score >= cls.GRADUATE_THRESHOLD

    @classmethod
    def get_threshold_config(cls) -> Dict[str, Any]:
        """
        Get the full threshold configuration.

        Returns:
            Dict with all threshold values and descriptions
        """
        return {
            "graduate_threshold": cls.GRADUATE_THRESHOLD,
            "graduate_percent": f"{cls.GRADUATE_THRESHOLD * 100:.0f}%",
            "escalate_threshold": cls.ESCALATE_THRESHOLD,
            "escalate_percent": f"{cls.ESCALATE_THRESHOLD * 100:.0f}%",
            "high_confidence": cls.HIGH_CONFIDENCE,
            "medium_confidence": cls.MEDIUM_CONFIDENCE,
            "low_confidence": cls.LOW_CONFIDENCE,
            "description": {
                "graduate": "Auto-proceed without human review",
                "continue": "Proceed with monitoring",
                "escalate": "Require human intervention"
            }
        }

    @classmethod
    def validate_thresholds(cls) -> bool:
        """
        Validate that thresholds are properly configured.

        Ensures:
        - GRADUATE > ESCALATE
        - All thresholds are between 0 and 1
        - Thresholds are in logical order

        Returns:
            True if thresholds are valid

        Raises:
            ValueError: If thresholds are misconfigured
        """
        # Check all thresholds are in valid range
        thresholds = [
            cls.GRADUATE_THRESHOLD,
            cls.ESCALATE_THRESHOLD,
            cls.HIGH_CONFIDENCE,
            cls.MEDIUM_CONFIDENCE,
            cls.LOW_CONFIDENCE
        ]

        for t in thresholds:
            if not 0.0 <= t <= 1.0:
                raise ValueError(f"Threshold {t} is not between 0.0 and 1.0")

        # Check logical ordering
        if cls.GRADUATE_THRESHOLD <= cls.ESCALATE_THRESHOLD:
            raise ValueError(
                f"GRADUATE_THRESHOLD ({cls.GRADUATE_THRESHOLD}) must be > "
                f"ESCALATE_THRESHOLD ({cls.ESCALATE_THRESHOLD})"
            )

        return True


# Module-level convenience functions
def get_confidence_action(confidence_score: float) -> ConfidenceAction:
    """
    Convenience function to get action for confidence score.

    Args:
        confidence_score: Float between 0.0 and 1.0

    Returns:
        ConfidenceAction enum value
    """
    return ConfidenceThresholds.get_action(confidence_score)


def should_escalate(confidence_score: float) -> bool:
    """
    Convenience function to check if escalation is needed.

    Args:
        confidence_score: Float between 0.0 and 1.0

    Returns:
        True if escalation required
    """
    return ConfidenceThresholds.should_escalate(confidence_score)


def can_graduate(confidence_score: float) -> bool:
    """
    Convenience function to check if can graduate autonomously.

    Args:
        confidence_score: Float between 0.0 and 1.0

    Returns:
        True if can proceed autonomously
    """
    return ConfidenceThresholds.can_graduate(confidence_score)
