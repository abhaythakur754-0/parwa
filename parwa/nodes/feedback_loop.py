"""Node 22: FEEDBACK_LOOP — Captures customer reaction for continuous improvement.

Proactive Agent node. Records feedback signals from the resolved ticket
to improve future responses. This is what makes PARWA get smarter over time.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.node_base import safe_node


def _generate_feedback_signal(
    intent: str,
    quality_score: float,
    verification_passed: bool,
    recommendation: dict | None,
) -> dict[str, Any]:
    """Generate a feedback signal from the ticket resolution."""
    # Determine if the ticket was resolved
    resolved = verification_passed and quality_score >= 80

    # Determine satisfaction level
    if quality_score >= 90:
        satisfaction = "high"
    elif quality_score >= 70:
        satisfaction = "medium"
    else:
        satisfaction = "low"

    # Identify improvement areas
    improvement_areas = []
    if quality_score < 80:
        improvement_areas.append("response_quality")
    if not verification_passed:
        improvement_areas.append("action_execution")
    if recommendation is not None:
        improvement_areas.append("variant_permission_limitation")

    return {
        "resolved": resolved,
        "satisfaction": satisfaction,
        "improvement_areas": improvement_areas,
        "intent": intent,
        "quality_score": quality_score,
    }


@safe_node("FEEDBACK_LOOP", fallback={"feedback_signal": {"resolved": False, "satisfaction": "low", "improvement_areas": ["node_failed"], "intent": "unknown", "quality_score": 0.0}})
async def feedback_loop(state: dict[str, Any]) -> dict[str, Any]:
    """Capture feedback signal for continuous improvement (async).

    Reads: intent, quality_score, verification_passed, recommendation
    Writes: feedback_signal
    """
    intent = state.get("intent", "general_inquiry")
    quality_score = state.get("quality_score", 0.0)
    verification_passed = state.get("verification_passed", False)
    recommendation = state.get("recommendation")

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(quality_score, (int, float)):
        quality_score = 0.0
    if not isinstance(verification_passed, bool):
        verification_passed = False
    if recommendation is not None and not isinstance(recommendation, dict):
        recommendation = None

    feedback = _generate_feedback_signal(
        intent, quality_score, verification_passed, recommendation
    )

    return {"feedback_signal": feedback}
