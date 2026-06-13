"""Node 22: FEEDBACK_LOOP — Captures customer reaction for continuous improvement.

Proactive Agent node. Records feedback signals from the resolved ticket
to improve future responses. This is what makes PARWA get smarter over time.

Phase 4: Now uses FrameworkBrain with ThoT (Thread of Thought) to maintain
a continuous learning thread across tickets.

P3 UPGRADE: CLOSED FEEDBACK LOOP — The feedback loop now actually ADJUSTS
behavior within the same ticket, not just records signals for future tickets.
It can:
  1. Detect if the current resolution is suboptimal (low quality score)
  2. Generate specific improvement suggestions for downstream nodes
  3. Adjust the response tone based on sentiment mismatch
  4. Feed corrective signals back to the quality scorer

This closes the loop: instead of just "we'll do better next time", the
system can self-correct WITHIN the current ticket.
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


@safe_node("FEEDBACK_LOOP", fallback={"feedback_signal": {"resolved": False, "satisfaction": "low", "improvement_areas": ["node_failed"], "intent": "unknown", "quality_score": 0.0}, "active_frameworks": [], "evidence_chain": [], "feed_forward_signals": []})
async def feedback_loop(state: dict[str, Any]) -> dict[str, Any]:
    """Capture feedback signal for continuous improvement (async).

    Phase 4: Uses FrameworkBrain with ThoT to maintain a continuous
    learning thread across tickets. Falls back to rule-based on failure.

    P3: CLOSED FEEDBACK LOOP — Now generates corrective signals that
    downstream nodes can use to improve the CURRENT ticket's response.
    This closes the loop between problem detection and correction.

    Reads: intent, quality_score, verification_passed, recommendation, sentiment,
           evidence_chain, situation_model, active_frameworks
    Writes: feedback_signal, active_frameworks (append), evidence_chain (append),
            feed_forward_signals (append)
    """
    # Try FrameworkBrain first (Phase 4)
    feedback, frameworks = await _feedback_with_brain(state)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # ─── P3: CLOSED FEEDBACK LOOP ───────────────────────────────────
    # Generate corrective signals that downstream nodes can act on
    corrective_signals = _generate_closed_loop_signals(state, feedback)

    # Build evidence chain entry for feedback
    new_evidence = []
    quality_score = state.get("quality_score", 0.0)
    if isinstance(quality_score, (int, float)):
        new_evidence.append({
            "claim": f"Feedback: {feedback.get('satisfaction', 'unknown')} satisfaction, "
                     f"score={quality_score:.0f}, "
                     f"{'resolved' if feedback.get('resolved') else 'unresolved'}",
            "sources": feedback.get("improvement_areas", []),
            "confidence": 0.75,
            "technique": "feedback_loop",
            "category": "feedback",
            "node": "FEEDBACK_LOOP",
        })

    return {
        "feedback_signal": feedback,
        "active_frameworks": new_frameworks,
        "evidence_chain": new_evidence,
        "feed_forward_signals": corrective_signals,
    }


def _generate_closed_loop_signals(state: dict[str, Any], feedback: dict[str, Any]) -> list[dict[str, Any]]:
    """P3: Generate corrective signals for downstream nodes.

    Instead of just recording "we'll do better next time", these signals
    tell downstream nodes how to improve the CURRENT response.
    """
    signals = []
    quality_score = state.get("quality_score", 0.0)
    sentiment = state.get("sentiment", "neutral")
    intent = state.get("intent", "general_inquiry")
    improvement_areas = feedback.get("improvement_areas", [])

    # Signal 1: If quality is low, tell quality scorer to be stricter
    if isinstance(quality_score, (int, float)) and quality_score < 70:
        signals.append({
            "target_node": "QUALITY_SCORER",
            "signal_type": "strict_mode",
            "detail": f"Low quality score ({quality_score:.0f}) — be extra strict on response quality",
            "priority": "high",
        })

    # Signal 2: If sentiment is negative, tell response formatter to add empathy
    if sentiment in ("angry", "frustrated"):
        signals.append({
            "target_node": "RESPONSE_FORMATTER",
            "signal_type": "add_empathy",
            "detail": f"Customer is {sentiment} — ensure response acknowledges frustration",
            "priority": "high",
        })

    # Signal 3: If action execution failed, tell action planner to try alternative
    if "action_execution" in improvement_areas:
        signals.append({
            "target_node": "ACTION_PLANNER",
            "signal_type": "try_alternative",
            "detail": "Action execution had issues — consider alternative actions",
            "priority": "medium",
        })

    # Signal 4: If response quality is low, tell conversational repair to be aggressive
    if "response_quality" in improvement_areas:
        signals.append({
            "target_node": "CONVERSATIONAL_REPAIR",
            "signal_type": "aggressive_repair",
            "detail": "Response quality was flagged as low — apply aggressive repair",
            "priority": "high",
        })

    # Signal 5: If situation model predicted high risk, ensure response addresses it
    situation = state.get("situation_model", {})
    if isinstance(situation, dict):
        high_risks = [r for r in situation.get("risks", []) if isinstance(r, dict) and r.get("severity") == "high"]
        if high_risks:
            signals.append({
                "target_node": "CONVERSATIONAL_REPAIR",
                "signal_type": "address_risks",
                "detail": f"Situation model flagged high risks — ensure response addresses: {high_risks[0].get('description', '')[:80]}",
                "priority": "high",
            })

    return signals
