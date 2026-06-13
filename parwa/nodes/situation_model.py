"""Node: SITUATION_MODEL — Builds a holistic context model before reasoning.

P2 NEW NODE: The Situation Model is the "big picture" builder. It sits AFTER
the knowledge pipeline (KB, Context, Integration) and BEFORE reasoning.
It synthesizes everything we know about the ticket into a structured
situation model that captures:

  1. WHO: Customer profile (account type, history, value tier)
  2. WHAT: What the customer actually wants (not just intent — specific desire)
  3. WHY: Underlying motivation (why now? what triggered this?)
  4. CONSTRAINTS: Policy limits, time constraints, regulatory requirements
  5. EVIDENCE: What we actually KNOW vs what we assume
  6. RISK: What could go wrong if we get this wrong

This is fundamentally different from what individual nodes do:
  - Intent classifier: Categorizes the request
  - Context manager: Manages conversation context
  - Situation model: SYNTHESIZES everything into a coherent picture

Without the situation model, reasoning operates on fragments — it sees
"refund_request" but doesn't understand WHY the customer is frustrated,
WHAT specific outcome they expect, or WHAT constraints limit the response.

The situation model gives reasoning a complete picture to work with.

Variant behavior:
  - mini: Rule-based synthesis (fast, no LLM)
  - parwa: LLM-enhanced synthesis (balanced)
  - high: Deep LLM analysis with multiple perspectives (thorough)
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.situation_model")


def _build_situation_rule_based(state: dict[str, Any]) -> dict[str, Any]:
    """Build situation model using rules (fast, no LLM).

    Synthesizes the scattered state fragments into a coherent picture.
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")
    sentiment = state.get("sentiment", "neutral")
    complexity = state.get("complexity", "simple")
    integration_data = state.get("integration_data", {})
    faq_match = state.get("faq_match")
    kb_results = state.get("kb_results", [])
    urgency = state.get("sentiment_urgency", 0.0)

    raw_lower = (raw_message or "").lower()

    # ─── WHO: Customer profile ────────────────────────────────────
    customer_profile = {
        "account_type": "standard",
        "value_tier": "standard",
        "has_payment_history": bool(integration_data.get("charges")),
        "has_order_history": bool(integration_data.get("orders")),
        "contact_count": 1,
        "is_returning": False,
    }

    # Detect returning customer from message clues
    return_keywords = ["again", "still", "still not", "still waiting", "another",
                       "second time", "third", "again about", "follow up", "follow-up"]
    if any(kw in raw_lower for kw in return_keywords):
        customer_profile["is_returning"] = True
        customer_profile["contact_count"] = 3  # estimate

    # Detect VIP/high-value customer
    vip_keywords = ["enterprise", "premium", "business plan", "our team",
                    "multiple seats", "our company", "our organization"]
    if any(kw in raw_lower for kw in vip_keywords):
        customer_profile["value_tier"] = "premium"

    # ─── WHAT: Specific desire (not just intent category) ──────────
    specific_desire = {
        "intent_category": intent,
        "desired_outcome": "",
        "specifics": [],
    }

    intent_outcome_map = {
        "refund_request": "Get money back for a charge",
        "cancellation": "Stop a subscription or order",
        "order_status": "Know where their order is",
        "billing_issue": "Resolve a billing discrepancy",
        "account_modification": "Change account details",
        "technical_support": "Fix a technical problem",
        "faq_question": "Get an answer to a question",
        "complaint": "Be heard and get resolution",
        "escalation": "Speak to a human with authority",
        "general_inquiry": "Get help with an issue",
    }
    specific_desire["desired_outcome"] = intent_outcome_map.get(intent, "Resolve their issue")

    # Extract specifics from the message
    specifics = []
    if "refund" in raw_lower:
        if "double" in raw_lower or "twice" in raw_lower or "duplicate" in raw_lower:
            specifics.append("duplicate_charge_refund")
        elif "overcharge" in raw_lower or "overcharged" in raw_lower or "wrong amount" in raw_lower:
            specifics.append("overcharge_refund")
        else:
            specifics.append("general_refund")
    if "cancel" in raw_lower:
        specifics.append("wants_cancellation")
    if "email" in raw_lower and ("update" in raw_lower or "change" in raw_lower):
        specifics.append("email_change")
    if "password" in raw_lower:
        specifics.append("password_reset")
    if "shipping" in raw_lower or "delivery" in raw_lower:
        specifics.append("shipping_concern")
    specific_desire["specifics"] = specifics

    # ─── WHY: Underlying motivation ────────────────────────────────
    motivation = {
        "primary_trigger": "",
        "emotional_state": sentiment,
        "urgency_level": "low",
        "patience_level": "moderate",
    }

    # Detect trigger
    if "charged twice" in raw_lower or "double charge" in raw_lower:
        motivation["primary_trigger"] = "financial_error"
    elif "not working" in raw_lower or "broken" in raw_lower or "can't access" in raw_lower:
        motivation["primary_trigger"] = "service_failure"
    elif "third email" in raw_lower or "still not resolved" in raw_lower:
        motivation["primary_trigger"] = "repeated_failure"
    elif "how do i" in raw_lower or "what is" in raw_lower:
        motivation["primary_trigger"] = "information_need"
    else:
        motivation["primary_trigger"] = "direct_request"

    # Urgency and patience
    if urgency >= 0.8 or sentiment in ("angry", "frustrated"):
        motivation["urgency_level"] = "high"
        motivation["patience_level"] = "low"
    elif urgency >= 0.5:
        motivation["urgency_level"] = "medium"
        motivation["patience_level"] = "moderate"

    # ─── CONSTRAINTS: Policy and regulatory limits ────────────────
    constraints = {
        "policy_limits": [],
        "regulatory_requirements": [],
        "time_constraints": [],
    }

    # Policy limits based on intent
    if intent == "refund_request":
        constraints["policy_limits"].append("Refund must be within policy window")
        constraints["policy_limits"].append("Refund amount must match actual charge")
    elif intent == "cancellation":
        constraints["policy_limits"].append("Cancellation must follow subscription terms")
    elif intent == "account_modification":
        constraints["policy_limits"].append("Account changes require verification")

    # Regulatory
    if any(kw in raw_lower for kw in ["gdpr", "data", "privacy", "delete my data", "right to erasure"]):
        constraints["regulatory_requirements"].append("GDPR data protection applies")
    if any(kw in raw_lower for kw in ["attorney", "lawsuit", "legal"]):
        constraints["regulatory_requirements"].append("Legal escalation required")

    # Time
    if "immediately" in raw_lower or "urgent" in raw_lower or "asap" in raw_lower:
        constraints["time_constraints"].append("Customer expects immediate resolution")
    if motivation["patience_level"] == "low":
        constraints["time_constraints"].append("Low patience — resolution must be quick")

    # ─── EVIDENCE: What we KNOW vs what we ASSUME ─────────────────
    known_facts = []
    assumptions = []

    # Known facts from integration data
    if integration_data.get("charges"):
        known_facts.append(f"Customer has {len(integration_data['charges'])} charge(s) on record")
    if integration_data.get("orders"):
        known_facts.append(f"Customer has {len(integration_data['orders'])} order(s) on record")

    # Known facts from FAQ/KB
    if faq_match and isinstance(faq_match, dict) and faq_match.get("relevance_score", 0) > 0.7:
        known_facts.append(f"FAQ matches this case (relevance: {faq_match.get('relevance_score', 0):.2f})")
    if kb_results:
        known_facts.append(f"KB has {len(kb_results)} relevant article(s)")

    # Assumptions (things we're inferring without direct evidence)
    if intent == "refund_request" and not integration_data.get("charges"):
        assumptions.append("Assuming charges exist but CRM data is incomplete")
    if not faq_match and not kb_results:
        assumptions.append("Assuming this is not a common FAQ question")

    # ─── RISK: What could go wrong ────────────────────────────────
    risks = []

    if sentiment in ("angry", "frustrated") and complexity in ("complex", "critical"):
        risks.append({"type": "escalation_risk", "severity": "high",
                      "description": "Angry customer with complex issue — may escalate to manager/social media"})
    if intent in ("refund_request", "cancellation") and not integration_data:
        risks.append({"type": "financial_without_verification", "severity": "high",
                      "description": "Financial action without CRM verification could be wrong"})
    if motivation["patience_level"] == "low":
        risks.append({"type": "churn_risk", "severity": "medium",
                      "description": "Low patience customer — poor resolution may cause churn"})
    if customer_profile["is_returning"]:
        risks.append({"type": "repeated_contact_risk", "severity": "medium",
                      "description": "Returning customer — previous resolution may have failed"})

    # ─── Assemble the situation model ─────────────────────────────
    situation = {
        "who": customer_profile,
        "what": specific_desire,
        "why": motivation,
        "constraints": constraints,
        "evidence": {
            "known_facts": known_facts,
            "assumptions": assumptions,
        },
        "risks": risks,
        "synthesis": _build_synthesis(
            customer_profile, specific_desire, motivation,
            constraints, known_facts, assumptions, risks,
        ),
    }

    return situation


def _build_synthesis(
    customer_profile: dict,
    specific_desire: dict,
    motivation: dict,
    constraints: dict,
    known_facts: list,
    assumptions: list,
    risks: list,
) -> str:
    """Build a one-paragraph synthesis of the situation for downstream nodes."""
    parts = []

    # Who + What
    value = customer_profile.get("value_tier", "standard")
    intent = specific_desire.get("intent_category", "unknown")
    outcome = specific_desire.get("desired_outcome", "resolve their issue")
    parts.append(
        f"A {value}-tier customer wants to {outcome} (intent: {intent})."
    )

    # Why
    trigger = motivation.get("primary_trigger", "direct_request")
    emotion = motivation.get("emotional_state", "neutral")
    patience = motivation.get("patience_level", "moderate")
    if emotion != "neutral" or patience != "moderate":
        parts.append(
            f"They are {emotion} with {patience} patience, triggered by {trigger}."
        )

    # Evidence
    if known_facts:
        parts.append(f"Known: {'; '.join(known_facts[:3])}.")
    if assumptions:
        parts.append(f"Assumed: {'; '.join(assumptions[:2])}.")

    # Constraints
    policy_limits = constraints.get("policy_limits", [])
    if policy_limits:
        parts.append(f"Must respect: {'; '.join(policy_limits[:2])}.")

    # Risks
    high_risks = [r for r in risks if r.get("severity") == "high"]
    if high_risks:
        parts.append(f"HIGH RISK: {high_risks[0]['description']}.")

    return " ".join(parts)


async def _build_situation_llm(state: dict[str, Any]) -> dict[str, Any]:
    """Build situation model with LLM enhancement (async).

    Uses rule-based as foundation, then asks LLM to enrich it.
    """
    # Start with rule-based foundation
    situation = _build_situation_rule_based(state)

    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")
    variant = state.get("variant", "parwa")

    if not raw_message:
        return situation

    # Ask LLM to identify nuances the rules missed
    rule_synthesis = situation.get("synthesis", "")

    system_instructions = (
        "You are analyzing a customer support ticket to build a complete SITUATION MODEL.\n"
        "Below is a rule-based analysis. Your job is to enrich it with insights the rules missed.\n\n"
        "Focus on:\n"
        "- What is the customer ACTUALLY asking for (beyond the intent category)?\n"
        "- What emotional subtext is present?\n"
        "- What is the hidden risk that rules might miss?\n"
        "- What constraint or policy should be considered?\n\n"
        f"Intent: {intent}\n"
        f"Customer message: {raw_message[:500]}\n"
        f"Rule-based analysis: {rule_synthesis}\n\n"
        "Reply in this EXACT format:\n"
        "ACTUAL_DESIRE: <what they really want>\n"
        "EMOTIONAL_SUBTEXT: <emotional context>\n"
        "HIDDEN_RISK: <risk rules might miss>\n"
        "POLICY_CONSTRAINT: <policy to respect>\n"
        "SYNTHESIS: <one sentence combining everything>"
    )

    try:
        safe_prompt = build_safe_prompt(system_instructions, "Enrich the situation model.")
        text = await ainvoke_llm(
            safe_prompt,
            node_name="SITUATION_MODEL",
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
            # max_tokens removed — uses generous default
        )

        # Parse LLM enrichment
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("ACTUAL_DESIRE:"):
                situation["what"]["actual_desire"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("EMOTIONAL_SUBTEXT:"):
                situation["why"]["emotional_subtext"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("HIDDEN_RISK:"):
                risk_desc = line.split(":", 1)[1].strip()
                situation["risks"].append({
                    "type": "llm_detected_risk",
                    "severity": "medium",
                    "description": risk_desc,
                })
            elif line.upper().startswith("POLICY_CONSTRAINT:"):
                constraint_desc = line.split(":", 1)[1].strip()
                situation["constraints"]["policy_limits"].append(constraint_desc)
            elif line.upper().startswith("SYNTHESIS:"):
                # Override the rule-based synthesis with the enriched one
                situation["llm_synthesis"] = line.split(":", 1)[1].strip()

        situation["llm_enhanced"] = True

    except Exception as exc:
        logger.warning("situation_model: LLM enrichment failed (%s), using rule-based only", exc)

    return situation


@safe_node("SITUATION_MODEL", fallback={
    "situation_model": {},
    "active_frameworks": [],
    "evidence_chain": [],
    "feed_forward_signals": [],
})
async def situation_model(state: dict[str, Any]) -> dict[str, Any]:
    """Build a holistic situation model before deep reasoning (async).

    P2 NEW NODE: Synthesizes all scattered state fragments into a
    coherent picture that reasoning can actually USE. Without this,
    reasoning sees "refund_request" but doesn't understand the full
    context — who the customer is, why they're here, what constraints
    apply, and what risks exist.

    Also generates FEED-FORWARD SIGNALS (P3) that predict what
    downstream nodes will need, pre-injecting that info into state.

    Variant behavior:
      - mini: Rule-based synthesis only (fast, cheap)
      - parwa: Rule-based + LLM enrichment (balanced)
      - high: Deep LLM analysis (thorough)

    Reads: raw_message, intent, sentiment, complexity, integration_data, faq_match, kb_results, sentiment_urgency
    Writes: situation_model, active_frameworks (append), evidence_chain (append), feed_forward_signals (append)
    """
    variant = state.get("variant", "parwa")

    # Guard type
    if not isinstance(variant, str):
        variant = "parwa"

    # Step 1: Build rule-based situation (all variants)
    situation = _build_situation_rule_based(state)

    # Step 2: LLM enrichment for parwa and high variants
    if variant in ("parwa", "high") and not MOCK_MODE:
        situation = await _build_situation_llm(state)

    # Step 3: High variant gets a second LLM pass for risk analysis
    if variant == "high" and not MOCK_MODE:
        try:
            risks_text = "; ".join(
                r.get("description", "") for r in situation.get("risks", [])
            )
            system_instructions = (
                "Analyze these identified risks for a customer support ticket. "
                "Find any ADDITIONAL risks that might be missed.\n\n"
                f"Intent: {state.get('intent', 'general_inquiry')}\n"
                f"Customer message: {state.get('raw_message', '')[:300]}\n"
                f"Identified risks: {risks_text}\n\n"
                "List 0-2 additional risks in format:\n"
                "RISK: <description>"
            )
            safe_prompt = build_safe_prompt(system_instructions, "Find additional risks.")
            text = await ainvoke_llm(
                safe_prompt,
                node_name="SITUATION_MODEL_RISK",
                ticket_id=state.get("ticket_id", ""),
                variant=variant,
                # max_tokens removed — uses generous default
            )
            for line in text.strip().split("\n"):
                line = line.strip()
                if line.upper().startswith("RISK:"):
                    risk_desc = line.split(":", 1)[1].strip()
                    situation["risks"].append({
                        "type": "llm_deep_risk",
                        "severity": "medium",
                        "description": risk_desc,
                    })
        except Exception as exc:
            logger.debug("situation_model: deep risk analysis failed (%s)", exc)

    # ─── P3: Feed-forward signals ─────────────────────────────────
    # Predict what downstream nodes will need and pre-inject signals
    feed_forward_signals = _generate_feed_forward_signals(situation, state)

    # Track frameworks
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    if "situation_model" not in existing:
        new_frameworks.append("situation_model")

    # Build evidence chain entry
    new_evidence = [{
        "claim": f"Situation: {situation.get('synthesis', '')[:150]}",
        "sources": situation.get("evidence", {}).get("known_facts", [])[:3],
        "confidence": 0.85 if situation.get("llm_enhanced") else 0.70,
        "technique": "situation_model",
        "category": "context",
        "node": "SITUATION_MODEL",
        "risk_count": len(situation.get("risks", [])),
        "high_risk_count": len([r for r in situation.get("risks", []) if r.get("severity") == "high"]),
    }]

    logger.info(
        "situation_model: built for intent=%s variant=%s risks=%d high_risks=%d",
        state.get("intent", "unknown"), variant,
        len(situation.get("risks", [])),
        len([r for r in situation.get("risks", []) if r.get("severity") == "high"]),
    )

    return {
        "situation_model": situation,
        "active_frameworks": new_frameworks,
        "evidence_chain": new_evidence,
        "feed_forward_signals": feed_forward_signals,
    }


def _generate_feed_forward_signals(situation: dict, state: dict[str, Any]) -> list[dict[str, Any]]:
    """P3: Generate feed-forward signals for downstream nodes.

    These are proactive hints that tell downstream nodes what to expect,
    so they can prepare rather than discover from scratch.

    Examples:
    - "reasoning_engine: customer is frustrated, be empathetic"
    - "action_planner: refund amount likely $49.99, pre-prepare refund action"
    - "response_formatter: include timeline in response"
    """
    signals = []

    intent = state.get("intent", "general_inquiry")
    motivation = situation.get("why", {})
    risks = situation.get("risks", [])
    constraints = situation.get("constraints", {})

    # Signal to reasoning engine about emotional context
    if motivation.get("emotional_state") in ("angry", "frustrated"):
        signals.append({
            "target_node": "REASONING_ENGINE",
            "signal_type": "empathy_required",
            "detail": f"Customer is {motivation.get('emotional_state')} with {motivation.get('patience_level')} patience",
            "priority": "high",
        })

    # Signal to action planner about likely actions
    if intent == "refund_request":
        integration_data = state.get("integration_data", {})
        if isinstance(integration_data, dict) and integration_data.get("charges"):
            amount = integration_data["charges"][0].get("amount", 49.99) if integration_data["charges"] else 49.99
            signals.append({
                "target_node": "ACTION_PLANNER",
                "signal_type": "pre_prepare_action",
                "detail": f"Refund of ${amount} likely needed — pre-verify eligibility",
                "priority": "high",
            })

    # Signal to response formatter about what to include
    if motivation.get("urgency_level") == "high":
        signals.append({
            "target_node": "RESPONSE_FORMATTER",
            "signal_type": "include_urgency",
            "detail": "Include specific timeline and next steps in response",
            "priority": "medium",
        })

    # Signal to escalation about risk of escalation
    high_risks = [r for r in risks if r.get("severity") == "high"]
    if high_risks:
        signals.append({
            "target_node": "ESCALATION_DECISION",
            "signal_type": "escalation_risk",
            "detail": f"High-risk situation: {high_risks[0].get('description', '')[:100]}",
            "priority": "high",
        })

    # Signal to quality scorer about what to watch for
    assumptions = situation.get("evidence", {}).get("assumptions", [])
    if assumptions:
        signals.append({
            "target_node": "QUALITY_SCORER",
            "signal_type": "verify_assumptions",
            "detail": f"Verify assumptions: {'; '.join(assumptions[:2])}",
            "priority": "medium",
        })

    # Signal to proactive checker about predicted follow-up
    if intent in ("refund_request", "cancellation"):
        signals.append({
            "target_node": "PROACTIVE_CHECKER",
            "signal_type": "predict_followup",
            "detail": f"After {intent}, customer will likely ask about {'timeline' if intent == 'refund_request' else 'alternatives'}",
            "priority": "low",
        })

    # Signal policy constraints to action nodes
    policy_limits = constraints.get("policy_limits", [])
    if policy_limits:
        signals.append({
            "target_node": "ACTION_EXECUTOR",
            "signal_type": "policy_constraint",
            "detail": f"Must respect: {'; '.join(policy_limits[:2])}",
            "priority": "high",
        })

    return signals
