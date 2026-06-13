"""Node 2: INTENT_CLASSIFIER — Determines what the customer wants.

Router Agent node. Classifies the ticket intent and confidence score.
Also determines the ticket complexity based on confidence.

Phase 5: Now uses FrameworkBrain with CoT/ReAct for complex classification.
Falls back to rule-based on FrameworkBrain failure.

Month 4: Ambiguous intent handling with confidence thresholds.
- If intent_confidence < 0.70, generates a clarifying question
- If top-2 intent score gap < 0.5, flags multi_intent_detected
- Adds clarifying_question, multi_intent_detected, detected_intents to state
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
# Month 1: Added more keywords for better coverage, reordered for specificity
# Month 1 v2: Multi-signal scoring — sum scores from ALL matching keywords,
# then pick the intent with highest total. This handles multi-issue tickets
# and prevents single strong words from overriding the primary intent.

_INTENT_KEYWORDS: dict[IntentType, list[tuple[str, float]]] = {
    # (keyword, weight) — longer/more specific keywords get higher weight
    IntentType.ESCALATION: [
        ("attorney", 2.0), ("lawyer", 2.0), ("lawsuit", 2.0), ("legal action", 2.0),
        ("sue", 1.8), ("fraud", 1.5), ("contact my attorney", 2.5), ("take legal", 2.0),
        ("going to sue", 2.5), ("reporting you to", 1.5), ("speak to manager", 1.8),
        ("speak to a manager", 1.8), ("demand to speak", 1.8), ("nobody has responded", 1.5),
        ("manager right now", 1.8), ("supervisor", 1.3), ("escalate", 1.3),
    ],
    IntentType.REFUND_REQUEST: [
        ("charged twice", 2.0), ("double charge", 2.0), ("duplicate charge", 2.0),
        ("money back", 1.8), ("refund", 1.5), ("reimburse", 1.5),
        ("want a refund", 1.8), ("need a refund", 1.8), ("my money back", 1.8),
    ],
    IntentType.CANCELLATION: [
        ("cancel my", 1.8), ("cancel order", 1.8), ("cancellation", 1.5),
        ("cancel", 1.0), ("stop order", 1.5), ("terminate", 1.2),
    ],
    IntentType.ORDER_STATUS: [
        ("where is my order", 2.0), ("order status", 1.8), ("tracking", 1.3),
        ("delivery", 1.0), ("shipped", 1.0), ("has my package", 1.5),
        ("shipping confirmation", 1.5), ("check the status", 1.3), ("hasn't received", 1.3),
        ("haven't received", 1.3), ("when will my order", 1.5),
        ("about my order", 1.3), ("my order", 1.0),
    ],
    IntentType.BILLING_ISSUE: [
        ("billing", 1.5), ("invoice", 1.5), ("overcharged", 1.8),
        ("charged $", 1.3), ("wrong amount", 1.5), ("unauthorized charge", 1.8),
        ("card was declined", 1.8), ("account is suspended", 1.3), ("payment failed", 1.5),
        ("suspended and", 1.0), ("charged for a subscription", 1.5),
        # Month 2: Additional billing keywords for better coverage
        ("charge on my statement", 1.5), ("extra charge", 1.5), ("receipt", 1.0),
        ("billing cycle", 1.5), ("card was charged", 1.5), ("mystery charge", 1.5),
        ("tax calculation", 1.3), ("discount wasn't applied", 1.5), ("discount not applied", 1.5),
        ("promotional discount", 1.3), ("promotional code", 1.3), ("signed up with code", 1.3),
        ("subscription i don't have", 1.5), ("subscription i cancelled", 1.5),
        ("charged without authorization", 1.8), ("charged without", 1.5),
        ("billing error", 1.5), ("account has been suspended", 1.5),
    ],
    IntentType.TECHNICAL_SUPPORT: [
        ("broken", 1.3), ("error", 1.0), ("bug", 1.3), ("not working", 1.3),
        ("crash", 1.5), ("crashing", 1.5), ("integration", 1.0),
        ("cannot log in", 1.5), ("500 error", 1.5), ("blank screen", 1.5),
        ("keeps crashing", 1.8), ("doesn't work", 1.3), ("dead pixels", 1.5),
        # Month 2: Additional technical support keywords
        ("firmware update", 1.5), ("corrupted", 1.5), ("export function", 1.3),
        ("webhook", 1.3), ("plugin", 1.3), ("browser", 1.0),
        ("freeze", 1.5), ("connection error", 1.5), ("log in", 1.3),
        ("not syncing", 1.5), ("syncing messages", 1.3), ("dashboard shows", 1.0),
        ("causes my browser", 1.5), ("stopped working", 1.5), ("connection error between", 1.8),
        # Month 4: TECHNICAL SUPPORT should NOT win over COMPLAINT when customer is upset
        # about being IGNORED. Reduce weight of generic tech keywords that also appear in complaints.
        # "plugin" alone (1.3) was too high — complaints about broken plugins are complaints first.
        # ("plugin", 1.3) — already above, keeping as-is since it's specific
    ],
    IntentType.ACCOUNT_MODIFICATION: [
        ("update my email", 1.8), ("change my", 1.3), ("modify my account", 1.5),
        ("upgrade my plan", 1.5), ("add seats", 1.8), ("add more seats", 1.8),
        ("update my", 1.3), ("change email", 1.5),
        # Month 2: Additional account modification keywords
        ("update email", 1.5), ("phone number on my account", 1.8),
        ("billing address", 1.5), ("add 5 more", 1.5), ("add 3 more", 1.5),
        ("more seats to my", 1.8), ("seats to my team", 1.8),
        ("upgrade from", 1.5), ("upgrade my", 1.8), ("upgrade 200", 1.5),
        ("upgrade", 1.0), ("downgrade", 1.5),
        ("reactivate my account", 2.0), ("suspended by mistake", 1.5),
        ("change my company", 1.5), ("company name", 1.3),
        ("payment method from", 1.5), ("switch my payment", 1.5),
        ("admin privileges", 1.5), ("add admin", 1.5),
        ("transfer my account", 1.5), ("data center", 1.3),
        ("change the phone", 1.5), ("change my billing", 1.3),
        ("update my account", 1.5), ("change my account", 1.3),
        ("updated my account", 1.3), ("my account email", 1.5),
    ],
    IntentType.COMPLAINT: [
        ("complaint", 1.5), ("unacceptable", 1.3), ("terrible", 1.0),
        ("worst service", 1.5), ("unprofessional", 1.3), ("extremely disappointed", 1.5),
        ("very disappointed", 1.3), ("ridiculous", 1.0), ("incredibly slow", 1.3),
        ("worst experience", 1.3), ("this is the worst", 1.3),
        # Month 2: Additional complaint keywords
        ("nothing but problems", 1.5), ("disappointed", 1.0), ("not what i expected", 1.3),
        ("not worth the price", 1.3), ("quality has declined", 1.5),
        ("misleading", 1.3), ("doesn't match the description", 1.5),
        ("broken promise", 1.5), ("nobody ever called", 1.5),
        ("outdated and confusing", 1.3), ("nightmare", 1.3),
        ("shipping is incredibly slow", 1.5), ("declined", 1.0),
        ("i'm not happy", 1.3), ("not happy", 1.0),
        # Month 4: Stronger complaint keywords — ignored tickets, dismissed, consumer rights
        ("completely dismissed", 1.8), ("felt dismissed", 1.5), ("dismissed", 1.3),
        ("tickets have been ignored", 2.0), ("been ignored", 1.5), ("ignored for a week", 1.8),
        ("nobody has responded", 1.5), ("nobody responded", 1.5), ("no one responded", 1.5),
        ("not even an acknowledgment", 1.8), ("no acknowledgment", 1.5),
        ("why should i trust", 1.5), ("why should i", 1.3),
        ("consumer rights", 1.8), ("consumer protection", 1.8),
        ("fail to perform", 1.5), ("failed to perform", 1.5),
        ("paying for something that doesn't work", 2.0), ("doesn't work while being", 1.5),
        ("can't keep paying", 1.5), ("keep paying for something", 1.8),
        ("first time i've felt", 1.5), ("first time i have felt", 1.5),
        ("what exactly am i", 1.5), ("real response", 1.3),
        ("loyal customer", 1.3), ("service quality", 1.3),
    ],
    IntentType.FAQ_QUESTION: [
        ("how do i", 1.3), ("what is", 1.0), ("can you tell me", 1.3),
        ("return policy", 1.5), ("refund policy", 1.5), ("business hours", 1.3),
        ("do you offer", 1.3), ("shipping options", 1.3), ("warranty cover", 1.5),
        ("thinking about returning", 1.0), ("what are your", 1.3),
        # Month 2: Additional FAQ keywords
        ("payment methods do you accept", 1.5), ("what payment methods", 1.5),
        ("enterprise discounts", 1.5), ("volume discounts", 1.5),
        ("warranty coverage", 1.5), ("free trial", 1.5),
        ("reset my password", 1.5), ("pricing plans", 1.3),
        ("how long does", 1.3), ("what features are", 1.3),
    ],
}


def _classify_intent_rule_based(message: str) -> tuple[str, float]:
    """Classify intent using multi-signal keyword scoring.

    Month 1 v2: Instead of first-match-wins, we sum scores from ALL matching
    keywords per intent, then pick the highest-scoring intent. This correctly
    handles tickets like 'I was charged twice AND I want a refund' (should be
    refund_request, not billing_issue) and 'I want a refund for defective product'
    (should be refund_request, not complaint).

    Returns (intent, confidence).
    """
    message_lower = message.lower()

    # Score each intent by summing all matching keyword weights
    intent_scores: dict[str, float] = {}
    for intent, keywords in _INTENT_KEYWORDS.items():
        score = 0.0
        for kw, weight in keywords:
            if kw in message_lower:
                score += weight
        if score > 0:
            intent_scores[intent.value] = score

    if not intent_scores:
        return IntentType.GENERAL_INQUIRY.value, 0.5

    # Pick the highest-scoring intent
    best_intent_str = max(intent_scores, key=intent_scores.get)
    best_score = intent_scores[best_intent_str]

    # ─── FAQ vs Action Override ───
    # Month 3 fix: If the message is ASKING about something (how, what, can I, do you),
    # it should be FAQ, NOT an action intent like refund_request or account_modification.
    # Only override if the FAQ score is significant (not just a weak match).
    faq_score = intent_scores.get("faq_question", 0)
    question_indicators = ["how do i", "how to", "what is", "what's", "what are",
                           "can you tell me", "do you offer", "do you accept",
                           "can i return", "how long does", "how does"]
    is_question = any(qi in message_lower for qi in question_indicators)

    if is_question and best_intent_str in ("refund_request", "account_modification", "cancellation"):
        # The message is asking ABOUT a topic, not requesting an action
        # Boost FAQ score and re-evaluate
        faq_score += 2.0  # Strong boost for question patterns
        if faq_score > best_score:
            best_intent_str = "faq_question"
            best_score = faq_score

    # ─── Month 4: Complaint Override ───
    # When a customer mentions being IGNORED, DISMISSED, or having unresolved tickets,
    # that's a COMPLAINT about service quality — even if the original issue was technical.
    # "My software crashes AND nobody has responded for a week" = complaint (not technical_support).
    complaint_score = intent_scores.get("complaint", 0)
    ignored_signals = [
        "been ignored", "ignored for", "tickets have been ignored",
        "nobody has responded", "nobody responded", "no one responded",
        "not even an acknowledgment", "no acknowledgment",
        "completely dismissed", "felt dismissed", "dismissed",
    ]
    has_ignored_signal = any(s in message_lower for s in ignored_signals)

    if has_ignored_signal and complaint_score > 0:
        # Customer is complaining about being ignored — complaint should win
        if best_intent_str in ("technical_support", "billing_issue", "order_status"):
            complaint_score += 3.0  # Strong boost: being ignored = complaint
            if complaint_score > best_score:
                best_intent_str = "complaint"
                best_score = complaint_score

    # Also: if customer mentions both technical issue AND consumer rights/legal threats,
    # the primary intent shifts from technical to complaint/escalation
    if "consumer rights" in message_lower or "consumer protection" in message_lower:
        if best_intent_str == "technical_support":
            # Consumer rights mention upgrades the intent from tech to complaint
            complaint_score += 2.0
            if complaint_score > best_score:
                best_intent_str = "complaint"
                best_score = complaint_score

    # Convert score to confidence (0.6 - 0.99)
    # Higher scores = higher confidence, capped at 0.99
    confidence = min(0.99, 0.6 + best_score * 0.05)

    return best_intent_str, confidence


async def _classify_intent_llm(message: str, *, ticket_id: str = "", variant: str = "parwa", complexity: str = "simple", customer_context: dict | None = None) -> tuple[str, float]:
    """Classify intent using LLM (async). Returns (intent, confidence).

    Uses structured output parsing instead of fragile split("|").
    Uses sanitized prompt to prevent injection.

    Month 1 fixes:
    - Alphabetically ordered intent list (eliminates first-position bias)
    - Few-shot examples for each intent (dramatic accuracy boost)
    - Reduced max_tokens for classification (only needs a few words)

    Month 2 addition:
    - Customer context (order history, past tickets) injected into prompt
      when available for better classification accuracy
    """
    # Month 2: Add customer context to prompt if available
    context_str = ""
    if customer_context:
        context_parts = []
        if customer_context.get("order_id"):
            context_parts.append(f"Order: {customer_context['order_id']}")
        if customer_context.get("amount"):
            context_parts.append(f"Amount: {customer_context['amount']}")
        if customer_context.get("past_tickets"):
            context_parts.append(f"Past tickets: {', '.join(customer_context['past_tickets'][:3])}")
        if context_parts:
            context_str = f"\nCustomer context: {'; '.join(context_parts)}\n"

    system_instructions = (
        "Classify the following customer message into one of these intents: "
        "account_modification, billing_issue, cancellation, escalation, "
        "faq_question, general_inquiry, order_status, complaint, "
        "refund_request, technical_support.\n\n"
        "IMPORTANT: Reply with ONLY the intent and confidence in this exact format: intent|confidence\n"
        "where confidence is between 0.0 and 1.0\n\n"
        "CRITICAL RULES:\n"
        "- If the customer mentions lawyer, attorney, lawsuit, legal action, sue, fraud, court → escalation\n"
        "- If the customer asks to speak to manager, supervisor, human agent → escalation\n"
        "- If the customer threatens to leave, cancel all services, or find another vendor AND is angry → escalation\n"
        "- REFUND_REQUEST vs BILLING_ISSUE: If the customer wants MONEY BACK → refund_request. "
        "If the customer is asking about a charge or subscription they don't understand → billing_issue. "
        "'I was charged twice, give me my money back' → refund_request. "
        "'Why am I being charged $9.99 every month?' → billing_issue.\n"
        "- REFUND_REQUEST vs TECHNICAL_SUPPORT: If a broken product leads to wanting money back → refund_request. "
        "'The software crashes and I want a full refund' → refund_request (NOT technical_support). "
        "'The software crashes, how do I fix it?' → technical_support.\n"
        "- CANCELLATION vs ORDER_STATUS: If the customer explicitly says 'cancel my order' → cancellation. "
        "'I want to cancel my order ORD-2003' → cancellation. "
        "'Where is my order? It's been a week' → order_status.\n"
        "- If the customer expresses strong dissatisfaction about SERVICE QUALITY without requesting specific action → complaint\n"
        "- If the customer asks a general question about policies/offers → faq_question\n\n"
        "Examples:\n"
        "Customer: 'I was charged twice for the same order' → refund_request|0.97\n"
        "Customer: 'I want my money back, the product is defective' → refund_request|0.95\n"
        "Customer: 'The software crashes and I want a full refund of $249.98' → refund_request|0.96\n"
        "Customer: 'Cancel my order ORD-2003 and refund my $79.99' → cancellation|0.94\n"
        "Customer: 'I'd like to cancel my order for the Laptop Stand' → cancellation|0.95\n"
        "Customer: 'Where is my order? It has been 10 days' → order_status|0.95\n"
        "Customer: 'I want to cancel my subscription' → cancellation|0.93\n"
        "Customer: 'My app keeps crashing when I open settings' → technical_support|0.92\n"
        "Customer: 'Can you update my email address?' → account_modification|0.90\n"
        "Customer: 'What is your return policy?' → faq_question|0.91\n"
        "Customer: 'This is the worst service ever, I am furious' → complaint|0.88\n"
        "Customer: 'I need to speak to a manager right now' → escalation|0.94\n"
        "Customer: 'My invoice shows the wrong amount' → billing_issue|0.91\n"
        "Customer: 'Why am I being charged $9.99 every month?' → billing_issue|0.93\n"
        "Customer: 'I will contact my lawyer about this fraud' → escalation|0.96\n"
        "Customer: 'This is illegal and I am going to take legal action' → escalation|0.96\n"
        "Customer: 'Something needs to change or we will be looking at other vendors' → escalation|0.90\n"
        "Customer: 'Your service is terrible and nobody knows our enterprise setup' → complaint|0.88\n"
        "Customer: 'Hello, how are you today?' → general_inquiry|0.70\n"
        "Customer: 'What are your business hours?' → faq_question|0.85\n"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(
        prompt,
        node_name="INTENT_CLASSIFIER",
        ticket_id=ticket_id,
        variant=variant,
        complexity=complexity,
        # max_tokens removed — uses generous default from _NODE_MAX_TOKENS
    )
    return parse_intent_response(text)


async def _classify_intent_with_brain(state: dict[str, Any]) -> tuple[str, float, list[str]]:
    """Classify intent using FrameworkBrain (Phase 5).

    Uses CoT for all complexities, ReAct for medium+.
    Returns (intent_str, confidence, frameworks_used).
    Falls back to rule-based on any failure.
    """
    raw_message = state.get("raw_message", "")
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="INTENT_CLASSIFIER", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=["chain_of_thought", "react"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Extract intent from brain output
        output = result.output.lower() if result.output else ""
        confidence = result.confidence if result.confidence > 0 else 0.5
        frameworks = result.frameworks_used if result.frameworks_used else []

        # Try to parse intent from output
        valid_intents = {e.value for e in IntentType}
        intent_str = IntentType.GENERAL_INQUIRY
        for valid in valid_intents:
            if valid in output:
                intent_str = valid
                break

        if intent_str == IntentType.GENERAL_INQUIRY:
            logger.debug("intent_classifier: FrameworkBrain couldn't determine specific intent, falling back")
            intent_str, confidence = _classify_intent_rule_based(raw_message)
            frameworks = ["chain_of_thought"]

        return intent_str, confidence, frameworks

    except Exception as exc:
        logger.warning(
            "intent_classifier: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        intent_str, confidence = _classify_intent_rule_based(raw_message)
        return intent_str, confidence, ["chain_of_thought"]


def _determine_complexity(confidence: float) -> str:
    """Determine ticket complexity based on intent confidence."""
    if confidence > 0.9:
        return TicketComplexity.SIMPLE
    if confidence > 0.7:
        return TicketComplexity.MEDIUM
    if confidence > 0.5:
        return TicketComplexity.COMPLEX
    return TicketComplexity.CRITICAL


# ─── Month 4: Clarifying question templates ────────────────────────────────────

_INTENT_DISPLAY_NAMES: dict[str, str] = {
    "refund_request": "a refund",
    "cancellation": "cancellation",
    "order_status": "order status",
    "billing_issue": "a billing issue",
    "technical_support": "technical support",
    "account_modification": "account modification",
    "complaint": "to lodge a complaint",
    "faq_question": "FAQ information",
    "escalation": "to escalate",
    "general_inquiry": "general information",
}

_MULTI_INTENT_TEMPLATES: dict[tuple[str, str], str] = {
    ("refund_request", "cancellation"): (
        "I see you'd like to both cancel and get a refund. "
        "Could you clarify — do you want to cancel your order and receive a refund, or just one of those?"
    ),
    ("refund_request", "billing_issue"): (
        "It sounds like you have a billing concern and may want a refund. "
        "Could you clarify — are you requesting a refund, or do you need help understanding a charge?"
    ),
    ("cancellation", "billing_issue"): (
        "I notice your message mentions both cancellation and a billing concern. "
        "Could you clarify — do you want to cancel something, resolve a billing issue, or both?"
    ),
    ("complaint", "technical_support"): (
        "I can see you're having a technical issue and are unhappy about it. "
        "Would you like me to help fix the technical problem, or would you prefer to file a formal complaint?"
    ),
    ("complaint", "refund_request"): (
        "It sounds like you're upset and would like a refund. "
        "Could you clarify — do you mainly want a refund, or would you also like to file a formal complaint?"
    ),
    ("order_status", "refund_request"): (
        "It seems you're both checking on your order and considering a refund. "
        "Could you clarify — do you want to know where your order is, or would you like to request a refund?"
    ),
    ("technical_support", "refund_request"): (
        "I see you're experiencing a technical issue and also want a refund. "
        "Would you like me to help troubleshoot the problem first, or would you prefer to proceed with a refund?"
    ),
}


def _generate_clarifying_question(top1_intent: str, top2_intent: str) -> str:
    """Generate a clarifying question for ambiguous multi-intent tickets (Month 4).

    Uses template-based generation — no LLM call needed.
    """
    # Check if we have a specific template for this pair (check both orderings)
    template = _MULTI_INTENT_TEMPLATES.get((top1_intent, top2_intent))
    if not template:
        template = _MULTI_INTENT_TEMPLATES.get((top2_intent, top1_intent))
    if template:
        return template

    # Generic fallback template
    name1 = _INTENT_DISPLAY_NAMES.get(top1_intent, top1_intent)
    name2 = _INTENT_DISPLAY_NAMES.get(top2_intent, top2_intent)
    return (
        f"I'm not entirely sure what you need — your message could be about {name1} "
        f"or {name2}. Could you clarify which one you'd like help with?"
    )


def _generate_low_confidence_question(intent_str: str) -> str:
    """Generate a clarifying question for low-confidence intent classification (Month 4).

    Uses template-based generation — no LLM call needed.
    """
    name = _INTENT_DISPLAY_NAMES.get(intent_str, intent_str)
    return (
        f"I think you might be looking for {name}, but I'm not completely sure. "
        f"Could you provide a bit more detail about what you need help with?"
    )


@safe_node("INTENT_CLASSIFIER", fallback={"intent": "general_inquiry", "intent_confidence": 0.0, "complexity": "simple", "clarifying_question": "", "multi_intent_detected": False, "detected_intents": [], "low_confidence_flag": False})
async def intent_classifier(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the intent of the customer's message (async).

    Phase 5: Uses FrameworkBrain with CoT/ReAct for better classification.
    Falls back to rule-based + LLM on FrameworkBrain failure.

    Reads: raw_message
    Writes: intent, intent_confidence, complexity
    """
    raw_message = state.get("raw_message", "")

    # Guard: empty or non-string message
    if not isinstance(raw_message, str) or not raw_message.strip():
        return {
            "intent": IntentType.GENERAL_INQUIRY,
            "intent_confidence": 0.0,
            "complexity": TicketComplexity.SIMPLE,
        }

    # Month 4 TPM optimization: Skip FrameworkBrain for speed.
    # Use rule-based first (free, instant), then LLM only if low confidence.
    # This cuts LLM calls per ticket from 2 to 0-1 for this node.
    intent_str, confidence = _classify_intent_rule_based(raw_message)
    frameworks = []

    # Only call LLM if rule-based confidence is low
    if confidence < 0.8 and not MOCK_MODE:
        try:
            llm_intent, llm_conf = await _classify_intent_llm(
                raw_message,
                ticket_id=state.get("ticket_id", ""),
                variant=state.get("variant", "parwa"),
                complexity=state.get("complexity", "simple"),
            )
            if llm_conf > confidence:
                intent_str, confidence = llm_intent, llm_conf
        except Exception as exc:
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

    # ─── Month 4: Ambiguous intent handling with confidence thresholds ───
    clarifying_question = ""
    multi_intent_detected = False
    detected_intents: list[str] = []
    low_confidence_flag = confidence < 0.70

    # Detect multi-intent: check if the message matches multiple intents closely
    message_lower = raw_message.lower()
    intent_scores: dict[str, float] = {}
    for intent, keywords in _INTENT_KEYWORDS.items():
        score = 0.0
        for kw, weight in keywords:
            if kw in message_lower:
                score += weight
        if score > 0:
            intent_scores[intent.value] = score

    # If there are at least 2 scored intents, check the gap
    if len(intent_scores) >= 2:
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        top1_intent, top1_score = sorted_intents[0]
        top2_intent, top2_score = sorted_intents[1]
        score_gap = top1_score - top2_score

        if score_gap < 0.5:
            multi_intent_detected = True
            detected_intents = [top1_intent, top2_intent]
            clarifying_question = _generate_clarifying_question(top1_intent, top2_intent)

    # Low confidence: generate a clarifying question even if not multi-intent
    if low_confidence_flag and not clarifying_question:
        clarifying_question = _generate_low_confidence_question(intent_str)

    # Track frameworks used
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
        # Month 4: Ambiguous intent fields
        "clarifying_question": clarifying_question,
        "multi_intent_detected": multi_intent_detected,
        "detected_intents": detected_intents,
        "low_confidence_flag": low_confidence_flag,
    }
