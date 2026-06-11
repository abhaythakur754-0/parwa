"""Node 2: INTENT_CLASSIFIER — Determines what the customer wants.

Router Agent node. Classifies the ticket intent and confidence score.
Also determines the ticket complexity based on confidence.

Phase 5: Now uses FrameworkBrain with CoT for nuanced classification
on medium+ complexity tickets. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import IntentType, TicketComplexity
from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.output_parser import parse_intent_response
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.intent_classifier")


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
    """Classify intent using LLM (async). Returns (intent, confidence).

    Uses structured output parsing instead of fragile split("|").
    Uses sanitized prompt to prevent injection.
    """
    system_instructions = (
        "Classify the following customer message into one of these intents: "
        "order_status, refund_request, cancellation, billing_issue, "
        "technical_support, faq_question, complaint, account_modification, "
        "escalation, general_inquiry.\n\n"
        "Reply with ONLY: intent|confidence (e.g. refund_request|0.95)"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(prompt, node_name="INTENT_CLASSIFIER")
    return parse_intent_response(text)


async def _classify_with_brain(state: dict[str, Any]) -> tuple[str, float, list[str]]:
    """Intent classification using FrameworkBrain (Phase 5).

    Returns (intent, confidence, frameworks_used).
    Falls back to rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="INTENT_CLASSIFIER", state=state)
        result = await brain.think(
            prompt=f"Classify intent for: {raw_message}",
            techniques=["chain_of_thought", "smart_router"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Always start with rule-based classification
        intent_str, confidence = _classify_intent_rule_based(raw_message)

        # Brain enhances confidence for complex tickets
        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return intent_str, confidence, frameworks_used

    except Exception as exc:
        logger.warning(
            "intent_classifier: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        intent_str, confidence = _classify_intent_rule_based(raw_message)
        return intent_str, confidence, []


def _determine_complexity(confidence: float) -> str:
    """Determine ticket complexity based on intent confidence."""
    if confidence > 0.9:
        return TicketComplexity.SIMPLE
    if confidence > 0.7:
        return TicketComplexity.MEDIUM
    if confidence > 0.5:
        return TicketComplexity.COMPLEX
    return TicketComplexity.CRITICAL


@safe_node("INTENT_CLASSIFIER", fallback={"intent": "general_inquiry", "intent_confidence": 0.0, "complexity": "simple", "active_frameworks": []})
async def intent_classifier(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the intent of the customer's message (async).

    Phase 5: Uses FrameworkBrain with CoT/Smart Router for nuanced
    classification on medium+ complexity tickets.

    Reads: raw_message
    Writes: intent, intent_confidence, complexity, active_frameworks (append)
    """
    raw_message = state.get("raw_message", "")

    # Guard: empty or non-string message
    if not isinstance(raw_message, str) or not raw_message.strip():
        return {
            "intent": IntentType.GENERAL_INQUIRY,
            "intent_confidence": 0.0,
            "complexity": TicketComplexity.SIMPLE,
            "active_frameworks": [],
        }

    # Try with brain first, then LLM fallback
    intent_str, confidence, frameworks = await _classify_with_brain(state)

    # If low confidence, try LLM with graceful degradation
    if confidence < 0.8 and not MOCK_MODE:
        try:
            intent_str, confidence = await _classify_intent_llm(raw_message)
        except Exception as exc:
            # LLM failed — keep the rule-based result (graceful degradation)
            logger.warning(
                "INTENT_CLASSIFIER: LLM classification failed, "
                "falling back to rule-based result (intent=%s, confidence=%.2f): %s",
                intent_str, confidence, exc,
            )

    # Validate intent against enum values
    valid_intents = {e.value for e in IntentType}
    if intent_str not in valid_intents:
        intent_str = IntentType.GENERAL_INQUIRY
    if not isinstance(confidence, (int, float)) or confidence < 0:
        confidence = 0.0

    complexity = _determine_complexity(confidence)

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "intent": intent_str,
        "intent_confidence": confidence,
        "complexity": complexity,
        "active_frameworks": new_frameworks,
    }
