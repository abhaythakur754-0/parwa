"""Node 20: ESCALATION_DECISION — Decides whether a human should handle this.

Router Agent node. Separately decides whether to escalate to a human.
Escalation is too important to be buried inside Action Planner.
"""

from __future__ import annotations

from typing import Any

from parwa.state import SentimentType, TicketComplexity, IntentType
from parwa.utils.llm import MOCK_MODE, get_mock_llm, get_llm
from parwa.utils.node_base import safe_node


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


def _should_escalate_llm(
    message: str,
    sentiment: str,
    complexity: str,
    intent: str,
) -> tuple[bool, str]:
    """Determine escalation using LLM. Returns (should_escalate, reason)."""
    if MOCK_MODE:
        mock = get_mock_llm()
        response = mock.invoke(f"Should escalate? Message: {message}, Sentiment: {sentiment}, Complexity: {complexity}")
        parts = response.split("|")
        should = parts[0].lower() == "true"
        reason = parts[1] if len(parts) > 1 else ""
        return should, reason

    llm = get_llm()
    prompt = (
        f"Should this customer ticket be escalated to a human agent?\n\n"
        f"Message: {message}\n"
        f"Sentiment: {sentiment}\n"
        f"Complexity: {complexity}\n"
        f"Intent: {intent}\n\n"
        f"Reply with ONLY: true|reason or false|"
    )
    response = llm.invoke(prompt)
    text = response.content if hasattr(response, "content") else str(response)
    parts = text.strip().split("|")
    should = parts[0].lower() == "true"
    reason = parts[1] if len(parts) > 1 else ""
    return should, reason


@safe_node("ESCALATION_DECISION")
def escalation_decision(state: dict[str, Any]) -> dict[str, Any]:
    """Decide whether to escalate this ticket to a human.

    Reads: raw_message, sentiment, sentiment_urgency, complexity, intent, intent_confidence
    Writes: should_escalate, escalation_reason
    """
    raw_message = state.get("raw_message", "")
    sentiment = state.get("sentiment", "neutral")
    sentiment_urgency = state.get("sentiment_urgency", 0.0)
    complexity = state.get("complexity", "simple")
    intent = state.get("intent", "general_inquiry")
    intent_confidence = state.get("intent_confidence", 0.5)

    should_escalate, reason = _should_escalate_rule_based(
        sentiment, sentiment_urgency, complexity, intent, intent_confidence
    )

    # If rules say no but complexity is high, try LLM for nuance
    if not should_escalate and complexity in (TicketComplexity.COMPLEX, TicketComplexity.CRITICAL, "complex", "critical") and not MOCK_MODE:
        should_escalate, reason = _should_escalate_llm(raw_message, sentiment, complexity, intent)

    return {
        "should_escalate": should_escalate,
        "escalation_reason": reason,
    }
