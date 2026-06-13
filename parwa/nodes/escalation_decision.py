"""Node 20: ESCALATION_DECISION — Decides whether a human should handle this.

Router Agent node. Separately decides whether to escalate to a human.
Escalation is too important to be buried inside Action Planner.

Phase 5: Now uses FrameworkBrain with UoT for uncertain escalation cases.
Falls back to rule-based on FrameworkBrain failure.

P2: CONFIDENCE-GATED ESCALATION — Now uses a confidence gate that considers
the combined confidence of ALL upstream signals (intent, sentiment, situation
model, evidence chain) to make a more nuanced escalation decision. Instead
of just rule-based yes/no, it computes an escalation confidence score and
gates the decision on that.

Month 4: Smart Escalation with Confidence < 60%
- If overall pipeline confidence < 0.60, auto-escalate regardless of other factors
- If customer mentions legal terms, IMMEDIATELY escalate — no exceptions
- If customer is VIP/enterprise AND sentiment is angry, escalate
- Track escalation trigger reason in state
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
        "Context — Sentiment: {sentiment}, Complexity: {complexity}, Intent: {intent}\n\n"
        "Reply with ONLY: true|reason or false|\n\n"
        "Escalation reasons:\n"
        "- legal_threat: Customer mentions lawyer, attorney, lawsuit, legal action, court, fraud, sue\n"
        "- high_urgency: Customer has contacted support multiple times, issue remains unresolved, "
        "SLA violations, multiple open tickets with no response\n"
        "- complex_technical: Issue requires engineering investigation beyond AI capability\n"
        "- vip_customer: High-value customer requiring personal attention, enterprise accounts, "
        "SLA commitments not met, dedicated account team complaints\n"
        "- angry_customer_with_critical_issue: Angry sentiment + business-critical problem\n"
        "- customer_requested_escalation: Customer explicitly asks for manager/supervisor, "
        "threatens to leave or find another vendor\n"
        "- business_threat: Customer threatens to cancel contract, switch vendors, or take "
        "business elsewhere — especially enterprise/VIP customers\n\n"
        "IMPORTANT: When in doubt, ESCALATE. Missing an escalation is worse than a false positive.\n\n"
        "Examples:\n"
        "Customer: 'I will contact my attorney' → true|legal_threat\n"
        "Customer: 'This is my third email and nobody has helped' → true|high_urgency\n"
        "Customer: 'Our entire team cannot access the platform' → true|complex_technical\n"
        "Customer: 'I need to speak to a manager immediately' → true|customer_requested_escalation\n"
        "Customer: 'Where is my order?' → false|\n"
        "Customer: 'Can I get a refund?' → false|\n"
        "Customer: 'Your system is broken and I am losing $10K per day' → true|angry_customer_with_critical_issue\n"
        "Customer: 'The level of service has been terrible and we are looking at other vendors' → true|business_threat\n"
        "Customer: 'I pay $4999/month and I am getting responses 3 days later' → true|vip_customer\n"
        "Customer: 'Something needs to change or we will be looking at other vendors' → true|business_threat\n"
    )
    prompt = build_safe_prompt(system_instructions, message)
    text = await ainvoke_llm(
        prompt,
        node_name="ESCALATION_DECISION",
        ticket_id=ticket_id,
        variant=variant,
        complexity=complexity_level,
        # max_tokens removed — uses generous default from _NODE_MAX_TOKENS
    )
    return parse_escalation_response(text)


async def _should_escalate_with_brain(state: dict[str, Any]) -> tuple[bool, str, list[str]]:
    """Determine escalation using FrameworkBrain (Phase 5).

    Uses UoT for uncertain cases, CoT for others.
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


def _compute_escalation_confidence_gate(state: dict[str, Any]) -> dict[str, Any]:
    """P2: Compute a confidence-gated escalation score.

    Instead of binary yes/no from rules, this computes a continuous
    escalation confidence based on multiple signals:
    - Intent confidence (how sure are we about what they want?)
    - Evidence strength (how much evidence supports our reasoning?)
    - Situation risk (how risky is this situation?)
    - Feed-forward signals (did upstream nodes flag escalation risk?)

    If the combined confidence exceeds the threshold, we escalate
    even if the rules didn't trigger.
    """
    intent_confidence = state.get("intent_confidence", 0.5)
    sentiment = state.get("sentiment", "neutral")
    complexity = state.get("complexity", "simple")

    # Start with base escalation confidence
    escalation_conf = 0.0
    factors = []

    # Factor 1: Low intent confidence → escalate
    if isinstance(intent_confidence, (int, float)) and intent_confidence < 0.5:
        penalty = (0.5 - intent_confidence) * 0.4  # max 0.2
        escalation_conf += penalty
        factors.append(f"low_intent_confidence ({intent_confidence:.2f})")

    # Factor 2: Situation model risks
    situation = state.get("situation_model", {})
    if isinstance(situation, dict):
        risks = situation.get("risks", [])
        high_risks = [r for r in risks if isinstance(r, dict) and r.get("severity") == "high"]
        if high_risks:
            escalation_conf += 0.25
            factors.append(f"situation_high_risk ({len(high_risks)})")
        elif len(risks) >= 2:
            escalation_conf += 0.10
            factors.append(f"situation_multiple_risks ({len(risks)})")

    # Factor 3: Feed-forward escalation signals
    ff_signals = state.get("feed_forward_signals", [])
    if isinstance(ff_signals, list):
        for signal in ff_signals:
            if isinstance(signal, dict) and signal.get("signal_type") == "escalation_risk":
                escalation_conf += 0.15
                factors.append("feed_forward_escalation_signal")
                break

    # Factor 4: Evidence chain contradictions
    evidence_chain = state.get("evidence_chain", [])
    if isinstance(evidence_chain, list) and len(evidence_chain) > 1:
        claims = []
        for entry in evidence_chain:
            if isinstance(entry, dict):
                claims.append(entry.get("claim", "").lower())

        has_positive = any(any(s in c for s in ["passed", "eligible", "approved"]) for c in claims)
        has_negative = any(any(s in c for s in ["failed", "denied", "vulnerability"]) for c in claims)
        if has_positive and has_negative:
            escalation_conf += 0.20
            factors.append("contradictory_evidence")

    # Determine if confidence gate triggers escalation
    # Threshold: 0.3 (significant combined signal needed)
    threshold = 0.3
    should_escalate = escalation_conf >= threshold

    # Determine reason
    gate_reason = "confidence_gate_combined"
    if "low_intent_confidence" in str(factors):
        gate_reason = "confidence_gate_low_intent"
    elif "situation_high_risk" in str(factors):
        gate_reason = "confidence_gate_high_risk"
    elif "contradictory_evidence" in str(factors):
        gate_reason = "confidence_gate_contradictions"
    elif "feed_forward_escalation_signal" in str(factors):
        gate_reason = "confidence_gate_upstream_signal"

    return {
        "should_escalate": should_escalate,
        "confidence": round(escalation_conf, 3),
        "threshold": threshold,
        "factors": factors,
        "reason": gate_reason,
    }


@safe_node("ESCALATION_DECISION", fallback={"should_escalate": False, "escalation_reason": "node_error", "confidence_gate": {}, "active_frameworks": [], "escalation_trigger_reason": ""})
async def escalation_decision(state: dict[str, Any]) -> dict[str, Any]:
    """Decide whether to escalate this ticket to a human (async).

    Phase 5: Uses FrameworkBrain with UoT for uncertain cases.
    Falls back to rule-based + LLM on FrameworkBrain failure.

    P2: CONFIDENCE-GATED ESCALATION — Now uses a confidence gate that
    considers the combined confidence of ALL upstream signals (intent,
    sentiment, situation model, evidence chain) to make a more nuanced
    escalation decision. Instead of just rule-based yes/no, it computes
    an escalation confidence score and gates the decision on that.

    Month 4: Smart Escalation — auto-escalate when pipeline confidence < 0.60,
    immediate escalation for legal terms, VIP+angry escalation, and tracking
    the escalation trigger reason.

    Reads: raw_message, sentiment, sentiment_urgency, complexity, intent,
           intent_confidence, situation_model, evidence_chain, feed_forward_signals
    Writes: should_escalate, escalation_reason, confidence_gate, active_frameworks (append),
            escalation_trigger_reason
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

    escalation_trigger_reason = ""

    # ─── Month 4: Immediate legal escalation — no exceptions ───
    msg_lower = raw_message.lower() if raw_message else ""
    legal_terms = ["attorney", "lawyer", "lawsuit", "legal action", "sue", "legal"]
    for term in legal_terms:
        if term in msg_lower:
            return {
                "should_escalate": True,
                "escalation_reason": "legal_threat_immediate",
                "confidence_gate": {},
                "active_frameworks": [],
                "escalation_trigger_reason": "month4_legal_term_immediate",
            }

    # ─── Month 4: Auto-escalate if pipeline confidence < 0.60 ───
    if intent_confidence < 0.60:
        return {
            "should_escalate": True,
            "escalation_reason": "low_pipeline_confidence",
            "confidence_gate": _compute_escalation_confidence_gate(state),
            "active_frameworks": [],
            "escalation_trigger_reason": f"month4_low_confidence_{intent_confidence:.2f}",
        }

    # ─── Month 4: VIP/enterprise + angry → escalate ───
    customer_tier = state.get("customer_tier", "")
    # Also check integration_data for customer tier info
    integration_data = state.get("integration_data", {})
    if isinstance(integration_data, dict):
        customer_info = integration_data.get("customer", {})
        if isinstance(customer_info, dict):
            customer_tier = customer_tier or customer_info.get("tier", "")

    if customer_tier in ("enterprise", "vip") and sentiment in (SentimentType.ANGRY, "angry"):
        return {
            "should_escalate": True,
            "escalation_reason": "vip_enterprise_angry_customer",
            "confidence_gate": _compute_escalation_confidence_gate(state),
            "active_frameworks": [],
            "escalation_trigger_reason": f"month4_vip_angry_{customer_tier}",
        }

    # Always run rule-based first — it catches clear-cut cases
    should_escalate, reason = _should_escalate_rule_based(
        sentiment, sentiment_urgency, complexity, intent, intent_confidence,
        raw_message=raw_message,
    )

    if should_escalate:
        escalation_trigger_reason = "rule_based"

    # P2: If rules say no, try confidence-gated decision
    confidence_gate = _compute_escalation_confidence_gate(state)

    # If confidence gate says escalate but rules didn't, escalate
    if not should_escalate and confidence_gate.get("should_escalate", False):
        should_escalate = True
        reason = confidence_gate.get("reason", "confidence_gate_triggered")
        escalation_trigger_reason = "confidence_gate"
        logger.info(
            "escalation: confidence gate triggered (gate_confidence=%.2f, reason=%s)",
            confidence_gate.get("confidence", 0), reason,
        )

    # If rules say no and confidence gate says no, try LLM for nuance
    # Month 4 TPM optimization: Skip FrameworkBrain, go straight to LLM only for complex tickets
    frameworks = []
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
                escalation_trigger_reason = "llm_fallback"
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
        "confidence_gate": confidence_gate,
        "active_frameworks": new_frameworks,
        "escalation_trigger_reason": escalation_trigger_reason,
    }
