"""Node 2: INTENT_CLASSIFIER — Determines what the customer wants.

Router Agent node. Classifies the ticket intent and confidence score.
Also determines the ticket complexity based on confidence.
"""

from __future__ import annotations

from typing import Any

from parwa.state import IntentType, TicketComplexity
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node


# Keyword-based intent mapping for mock/rule-based classification
_INTENT_KEYWORDS: dict[IntentType, list[str]] = {
    IntentType.REFUND_REQUEST: ["refund", "charged twice", "double charge", "money back", "reimburse"],
    IntentType.CANCELLATION: ["cancel", "cancellation", "stop order", "terminate"],
    IntentType.ORDER_STATUS: ["where is my order", "order status", "tracking", "delivery", "shipped"],
    IntentType.BILLING_ISSUE: ["billing", "charge", "invoice", "payment", "overcharged"],
    IntentType.ACCOUNT_MODIFICATION: ["account", "update my", "change my", "modify"],
    IntentType.TECHNICAL_SUPPORT: ["broken", "error", "bug", "not working", "crash"],
    IntentType.COMPLAINT: ["complaint", "unacceptable", "terrible", "worst", "angry"],
    IntentType.ESCALATION: ["manager", "supervisor", "escalate", "speak to someone"],
    IntentType.FAQ_QUESTION: ["how do i", "what is", "can you tell me", "policy"],
}


def _classify_intent_rule_based(message: str) -> tuple[str, float]:
    """Classify intent using keyword matching. Returns (intent, confidence)."""
    message_lower = message.lower()

    best_intent = IntentType.GENERAL_INQUIRY
    best_confidence = 0.5

    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in message_lower:
                # More specific keyword = higher confidence
                confidence = min(0.99, 0.80 + len(kw) * 0.01)
                if confidence > best_confidence:
                    best_intent = intent
                    best_confidence = confidence

    return best_intent, best_confidence


async def _classify_intent_llm(message: str) -> tuple[str, float]:
    """Classify intent using LLM (async). Returns (intent, confidence)."""
    prompt = (
        f"Classify the following customer message into one of these intents: "
        f"order_status, refund_request, cancellation, billing_issue, "
        f"technical_support, faq_question, complaint, account_modification, "
        f"escalation, general_inquiry.\n\n"
        f"Customer message: {message}\n\n"
        f"Reply with ONLY: intent|confidence (e.g. refund_request|0.95)"
    )
    text = await ainvoke_llm(prompt)
    parts = text.strip().split("|")
    return parts[0], float(parts[1]) if len(parts) > 1 else 0.75


def _determine_complexity(confidence: float) -> str:
    """Determine ticket complexity based on intent confidence."""
    if confidence > 0.9:
        return TicketComplexity.SIMPLE
    if confidence > 0.7:
        return TicketComplexity.MEDIUM
    if confidence > 0.5:
        return TicketComplexity.COMPLEX
    return TicketComplexity.CRITICAL


@safe_node("INTENT_CLASSIFIER", fallback={"intent": "general_inquiry", "intent_confidence": 0.0, "complexity": "simple"})
async def intent_classifier(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the intent of the customer's message (async).

    Reads: raw_message
    Writes: intent, intent_confidence, complexity
    """
    raw_message = state.get("raw_message", "")

    # Try rule-based first, then LLM fallback
    intent_str, confidence = _classify_intent_rule_based(raw_message)

    # If low confidence, try LLM
    if confidence < 0.8 and not MOCK_MODE:
        intent_str, confidence = await _classify_intent_llm(raw_message)

    # Validate intent against enum values
    valid_intents = {e.value for e in IntentType}
    if intent_str not in valid_intents:
        intent_str = IntentType.GENERAL_INQUIRY

    complexity = _determine_complexity(confidence)

    return {
        "intent": intent_str,
        "intent_confidence": confidence,
        "complexity": complexity,
    }
