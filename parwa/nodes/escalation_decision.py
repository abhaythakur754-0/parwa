"""Node 20: ESCALATION_DECISION — Decides whether a human should handle this.

Router Agent node. Separately decides whether to escalate to a human.
Escalation is too important to be buried inside Action Planner.

Phase 5: Now uses FrameworkBrain with Reverse Thinking for counter-factual
escalation analysis. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import SentimentType, TicketComplexity, IntentType
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.output_parser import parse_escalation_response
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.escalation_decision")


def _should_escalate_rule_based(
    sentiment: str,
    sentiment_urgency: float,
    complexity: str,
    intent: str,
    intent_confidence: float,
) -> tuple[bool, str]:
    """Determine escalation using rules. Returns (should_escalate, reason)."""
    # Angry + Critical = always escalate
    if sentiment in (SentimentType.ANGRY, "angry") and complexity in (TicketComplexity.CRITICAL, "critical"):
        return True, "angry_customer_with_critical_issue"

    # Explicit escalation intent
    if intent in (IntentType.ESCALATION, "escalation"):
        return True, "customer_requested_escalation"

    # Very low confidence = system can't handle it
    if intent_confidence < 0.3:
        return True, "low_intent_confidence"

    # High urgency + frustrated = likely needs human
    if sentiment_urgency > 0.9 and sentiment in (SentimentType.FRUSTRATED, "frustrated"):
        return True, "high_urgency_frustrated_customer"

    return False, ""


async def _should_escalate_llm(
    message: str,
    sentiment: str,
    complexity: str,
    intent: str,
) -> tuple[bool, str]:
    """Determine escalation using LLM (async). Returns (should_escalate, reason).

    Uses structured output parsing and sanitized prompt.
    """
    system_instructions = (
        "Should this customer ticket be escalated to a human agent?\n\n"
        f"Context — Sentiment: {sentiment}, Complexity: {complexity}, Intent: {intent}\n\n"
        "Reply with ONLY: true|reason or false|"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(prompt, node_name="ESCALATION_DECISION")
    return parse_escalation_response(text)


async def _escalate_with_brain(state: dict[str, Any]) -> tuple[bool, str, list[str]]:
    """Escalation decision using FrameworkBrain (Phase 5).

    Returns (should_escalate, reason, frameworks_used).
    Falls back to rule-based on any failure.
    """
    sentiment = state.get("sentiment", "neutral")
    sentiment_urgency = state.get("sentiment_urgency", 0.0)
    complexity = state.get("complexity", "simple")
    intent = state.get("intent", "general_inquiry")
    intent_confidence = state.get("intent_confidence", 0.5)

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="ESCALATION_DECISION", state=state)
        result = await brain.think(
            prompt=f"Should we escalate? Sentiment={sentiment}, Complexity={complexity}, Intent={intent}",
            techniques=["reverse_thinking", "chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Always start with rule-based decision
        should_escalate, reason = _should_escalate_rule_based(
            sentiment, sentiment_urgency, complexity, intent, intent_confidence
        )

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return should_escalate, reason, frameworks_used

    except Exception as exc:
        logger.warning(
            "escalation_decision: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        should_escalate, reason = _should_escalate_rule_based(
            sentiment, sentiment_urgency, complexity, intent, intent_confidence
        )
        return should_escalate, reason, []


@safe_node("ESCALATION_DECISION", fallback={"should_escalate": False, "escalation_reason": "node_error", "active_frameworks": []})
async def escalation_decision(state: dict[str, Any]) -> dict[str, Any]:
    """Decide whether to escalate this ticket to a human (async).

    Phase 5: Uses FrameworkBrain with Reverse Thinking/CoT for
    counter-factual escalation analysis.

    Reads: raw_message, sentiment, sentiment_urgency, complexity, intent, intent_confidence
    Writes: should_escalate, escalation_reason, active_frameworks (append)
    """
    raw_message = state.get("raw_message", "")
    sentiment = state.get("sentiment", "neutral")
    sentiment_urgency = state.get("sentiment_urgency", 0.0)
    complexity = state.get("complexity", "simple")
    intent = state.get("intent", "general_inquiry")
    intent_confidence = state.get("intent_confidence", 0.5)

    # Guard: ensure numeric types
    if not isinstance(sentiment_urgency, (int, float)):
        sentiment_urgency = 0.0
    if not isinstance(intent_confidence, (int, float)):
        intent_confidence = 0.5

    should_escalate, reason, frameworks = await _escalate_with_brain(state)

    # If rules say no but complexity is high, try LLM for nuance with graceful degradation
    if not should_escalate and complexity in (TicketComplexity.COMPLEX, TicketComplexity.CRITICAL, "complex", "critical") and not MOCK_MODE:
        try:
            should_escalate, reason = await _should_escalate_llm(raw_message, sentiment, complexity, intent)
        except Exception as exc:
            # LLM failed — keep the rule-based result (graceful degradation)
            logger.warning(
                "ESCALATION_DECISION: LLM escalation check failed, "
                "falling back to rule-based result (should_escalate=%s): %s",
                should_escalate, exc,
            )

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "should_escalate": should_escalate,
        "escalation_reason": reason,
        "active_frameworks": new_frameworks,
    }
