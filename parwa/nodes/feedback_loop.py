"""Node 22: FEEDBACK_LOOP — Captures customer reaction for continuous improvement.

Proactive Agent node. Records feedback signals from the resolved ticket
to improve future responses. This is what makes PARWA get smarter over time.

Phase 4: Now uses FrameworkBrain with ThoT (Thread of Thought) to maintain
a continuous learning thread across tickets.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.feedback_loop")


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


async def _feedback_with_brain(state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Feedback with FrameworkBrain + ThoT (Phase 4).

    Returns (feedback_signal, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    quality_score = state.get("quality_score", 0.0)
    verification_passed = state.get("verification_passed", False)
    recommendation = state.get("recommendation")

    # Guard types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(quality_score, (int, float)):
        quality_score = 0.0
    if not isinstance(verification_passed, bool):
        verification_passed = False
    if recommendation is not None and not isinstance(recommendation, dict):
        recommendation = None

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="FEEDBACK_LOOP", state=state)
        result = await brain.think(
            prompt=intent,
            techniques=["thread_of_thought", "dynamic_context"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Generate the feedback signal (rule-based + brain enhancement)
        feedback = _generate_feedback_signal(
            intent, quality_score, verification_passed, recommendation
        )

        # Enhance with ThoT insights
        if result.metadata.get("thread_length", 0) > 0:
            feedback["thought_thread_entries"] = result.metadata.get("thread_length", 0)
            feedback["brain_enhanced"] = True

        return feedback, result.frameworks_used if result.frameworks_used else []

    except Exception as exc:
        logger.warning(
            "feedback_loop: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        feedback = _generate_feedback_signal(
            intent, quality_score, verification_passed, recommendation
        )
        return feedback, []


@safe_node("FEEDBACK_LOOP", fallback={"feedback_signal": {"resolved": False, "satisfaction": "low", "improvement_areas": ["node_failed"], "intent": "unknown", "quality_score": 0.0}, "active_frameworks": []})
async def feedback_loop(state: dict[str, Any]) -> dict[str, Any]:
    """Capture feedback signal for continuous improvement (async).

    Phase 4: Uses FrameworkBrain with ThoT to maintain a continuous
    learning thread across tickets. Falls back to rule-based on failure.

    Reads: intent, quality_score, verification_passed, recommendation
    Writes: feedback_signal, active_frameworks (append)
    """
    # Try FrameworkBrain first (Phase 4)
    feedback, frameworks = await _feedback_with_brain(state)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "feedback_signal": feedback,
        "active_frameworks": new_frameworks,
    }
