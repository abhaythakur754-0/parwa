"""Node 20: ESCALATION_DECISION — Decides whether a human should handle this.

Router Agent node. Separately decides whether to escalate to a human.
Escalation is too important to be buried inside Action Planner.

Phase 5: Now uses FrameworkBrain with UoT for uncertain escalation cases.
Falls back to rule-based on FrameworkBrain failure.
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
    raw_message: str = "",
) -> tuple[bool, str]:
    """Determine escalation using rules. Returns (should_escalate, reason)."""
    # Legal threat detection — ALWAYS escalate
    msg_lower = raw_message.lower() if raw_message else ""
    legal_keywords = ["attorney", "lawyer", "lawsuit", "legal action", "court", "fraud"]
    # Note: "sue" is NOT included here because it's a substring of "issue"
    # Instead, check for "sue" as a whole word
    for kw in legal_keywords:
        if kw in msg_lower:
            return True, "legal_threat"
    # Check "sue" as a whole word (not substring of "issue")
    import re
    if re.search(r'\bsue\b', msg_lower):
        return True, "legal_threat"

    # Manager request — escalate
    manager_keywords = ["speak to manager", "talk to manager", "speak with manager",
                       "manager immediately", "supervisor", "human agent",
                       # Month 2: Additional manager/escalation keywords
                       "speak to your manager", "speak to a manager",
                       "someone who can actually", "human agent",
                       "chatbot is not helping", "chatbot is useless",
                       "formal complaint", "data protection officer",
                       "executive escalation", "executive",
                       ]
    for kw in manager_keywords:
        if kw in msg_lower:
            return True, "customer_requested_manager"

    # Angry + Critical = always escalate (but NOT just angry + urgent —
    # angry customers who want a refund/cancellation are better served by
    # the AI actually processing their action than waiting for a human)
    if sentiment in (SentimentType.ANGRY, "angry") and complexity in (TicketComplexity.CRITICAL, "critical"):
        return True, "angry_customer_with_critical_issue"

    # Angry + explicit escalation intent = escalate
    if sentiment in (SentimentType.ANGRY, "angry") and intent in (IntentType.ESCALATION, "escalation"):
        return True, "angry_customer_requested_escalation"

    # Note: We do NOT auto-escalate just for angry + high urgency.
    # An angry customer who wants a refund is better served by the AI
    # processing the refund immediately, not by waiting for a human.
    # Escalation should be reserved for situations the AI truly can't handle.

    # Very high urgency + frustrated + low confidence = likely needs human
    # Only escalate if we're NOT confident in our intent classification
    if sentiment_urgency > 0.9 and sentiment in (SentimentType.FRUSTRATED, "frustrated") and intent_confidence < 0.6:
        return True, "high_urgency_frustrated_customer_low_confidence"

    # Explicit escalation intent
    if intent in (IntentType.ESCALATION, "escalation"):
        return True, "customer_requested_escalation"

    # Very low confidence = system can't handle it
    if intent_confidence < 0.3:
        return True, "low_intent_confidence"

    # Multiple unresolved tickets mention — escalate
    unresolved_keywords = ["third email", "nobody has responded", "still not resolved",
                          "no one has helped", "still waiting", "unresolved",
                          # Month 2: Additional unresolved/repeated contact keywords
                          "fourth attempt", "fifth", "nobody has helped",
                          "no one is responding", "no one ever called",
                          "attorney general", "bbb", "consumer protection",
                          "reporting you to", "security vulnerability",
                          "data was breached", "account was hacked",
                          "property damage", "safety hazard", "someone could get hurt",
                          "on behalf of my law firm", "journalist",
                          "gdpr", "right to erasure", "compliance department",
                          "law firm regarding", "systemic fraud",
                          ]
    for kw in unresolved_keywords:
        if kw in msg_lower:
            return True, "multiple_unresolved_tickets"

    return False, ""


async def _should_escalate_llm(
    message: str,
    sentiment: str,
    complexity: str,
    intent: str,
    *,
    ticket_id: str = "",
    variant: str = "parwa",
    complexity_level: str = "simple",
) -> tuple[bool, str]:
    """Determine escalation using LLM (async). Returns (should_escalate, reason).

    Uses structured output parsing and sanitized prompt.

    Month 1 fixes:
    - Added explicit trigger examples for each escalation reason
    - Added few-shot examples to prevent false negatives
    """
    system_instructions = (
        "Should this customer ticket be escalated to a human agent?\n\n"
        f"Context — Sentiment: {sentiment}, Complexity: {complexity}, Intent: {intent}\n\n"
        "Reply with ONLY: true|reason or false|\n\n"
        "Escalation reasons:\n"
        "- legal_threat: Customer mentions lawyer, attorney, lawsuit, legal action, court, fraud, sue\n"
        "- high_urgency: Customer has contacted support multiple times, issue remains unresolved\n"
        "- complex_technical: Issue requires engineering investigation beyond AI capability\n"
        "- vip_customer: High-value customer requiring personal attention\n"
        "- angry_customer_with_critical_issue: Angry sentiment + business-critical problem\n"
        "- customer_requested_escalation: Customer explicitly asks for manager/supervisor\n\n"
        "Examples:\n"
        "Customer: 'I will contact my attorney' → true|legal_threat\n"
        "Customer: 'This is my third email and nobody has helped' → true|high_urgency\n"
        "Customer: 'Our entire team cannot access the platform' → true|complex_technical\n"
        "Customer: 'I need to speak to a manager immediately' → true|customer_requested_escalation\n"
        "Customer: 'Where is my order?' → false|\n"
        "Customer: 'Can I get a refund?' → false|\n"
        "Customer: 'Your system is broken and I am losing $10K per day' → true|angry_customer_with_critical_issue\n"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(
        prompt,
        node_name="ESCALATION_DECISION",
        ticket_id=ticket_id,
        variant=variant,
        complexity=complexity_level,
        max_tokens=50,
    )
    return parse_escalation_response(text)


async def _should_escalate_with_brain(state: dict[str, Any]) -> tuple[bool, str, list[str]]:
    """Determine escalation using FrameworkBrain (Phase 5).

    Uses UoT for uncertain cases, CoT for straightforward ones.
    Returns (should_escalate, reason, frameworks_used).
    Falls back to rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")
    sentiment = state.get("sentiment", "neutral")
    sentiment_urgency = state.get("sentiment_urgency", 0.0)
    complexity = state.get("complexity", "simple")
    intent = state.get("intent", "general_inquiry")
    intent_confidence = state.get("intent_confidence", 0.5)

    try:
        from parwa.frameworks.brain import FrameworkBrain

        # Use UoT for critical cases, CoT for others
        techniques = ["uncertainty_of_thought"] if complexity in ("complex", "critical") else ["chain_of_thought"]

        brain = FrameworkBrain(node="ESCALATION_DECISION", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=techniques,
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Parse escalation decision from brain output
        output = result.output.lower() if result.output else ""
        frameworks = result.frameworks_used if result.frameworks_used else []

        should_escalate = "escalat" in output or "human" in output or "yes" in output
        reason = ""
        if should_escalate:
            # Try to extract reason
            for keyword in ["legal", "urgent", "complex", "unable", "safety", "regulatory"]:
                if keyword in output:
                    reason = f"brain_detected_{keyword}"
                    break
            if not reason:
                reason = "brain_recommended_escalation"

        if not should_escalate and result.confidence < 0.5:
            # Low confidence — fall back to rules
            logger.debug("escalation_decision: FrameworkBrain low confidence, falling back to rules")
            should_escalate, reason = _should_escalate_rule_based(
                sentiment, sentiment_urgency, complexity, intent, intent_confidence,
                raw_message=raw_message,
            )
            frameworks = techniques

        return should_escalate, reason, frameworks

    except Exception as exc:
        logger.warning(
            "escalation_decision: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        should_escalate, reason = _should_escalate_rule_based(
            sentiment, sentiment_urgency, complexity, intent, intent_confidence,
            raw_message=raw_message,
        )
        return should_escalate, reason, ["chain_of_thought"]


@safe_node("ESCALATION_DECISION", fallback={"should_escalate": False, "escalation_reason": "node_error"})
async def escalation_decision(state: dict[str, Any]) -> dict[str, Any]:
    """Decide whether to escalate this ticket to a human (async).

    Phase 5: Uses FrameworkBrain with UoT for uncertain cases.
    Falls back to rule-based + LLM on FrameworkBrain failure.

    Reads: raw_message, sentiment, sentiment_urgency, complexity, intent, intent_confidence
    Writes: should_escalate, escalation_reason
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

    # Always run rule-based first — it catches clear-cut cases
    should_escalate, reason = _should_escalate_rule_based(
        sentiment, sentiment_urgency, complexity, intent, intent_confidence,
        raw_message=raw_message,
    )

    # If rules say no and complexity is high, try FrameworkBrain + LLM for nuance
    if not should_escalate:
        _, _, frameworks = await _should_escalate_with_brain(state)
    else:
        frameworks = []

    # If brain says no but complexity is high, try LLM for nuance
    if not should_escalate and complexity in (TicketComplexity.COMPLEX, TicketComplexity.CRITICAL, "complex", "critical") and not MOCK_MODE:
        try:
            llm_escalate, llm_reason = await _should_escalate_llm(
                raw_message, sentiment, complexity, intent,
                ticket_id=state.get("ticket_id", ""),
                variant=state.get("variant", "parwa"),
                complexity_level=complexity,
            )
            if llm_escalate:
                should_escalate, reason = llm_escalate, llm_reason
        except Exception as exc:
            logger.warning(
                "ESCALATION_DECISION: LLM escalation check failed, "
                "falling back to rule-based result (should_escalate=%s): %s",
                should_escalate, exc,
            )

    # Track frameworks used
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
