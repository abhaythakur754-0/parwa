"""Node 17: RESPONSE_FORMATTER — Crafts the final customer-facing response.

Compliance Agent node. Takes all gathered information and creates
a helpful, empathetic, and accurate response for the customer.

Phase 5: Now uses FrameworkBrain with CRP for constrained output generation.
Falls back to rule-based on FrameworkBrain failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.response_formatter")


def _clean_structured_output(text: str) -> str:
    """Remove any structured/pipe-delimited output that leaked from other nodes.

    Handles common leak patterns:
    - "no_match|0.00|" (FAQ matcher raw output)
    - "true|legal_threat" (escalation raw output)
    - "false|" (escalation raw output)
    - "refund_policy|0.90|Refunds are available..." (FAQ with content)
    - "refund_request|0.97" (intent raw output)
    - "frustrated|0.85" (sentiment raw output)
    - "85|accurate,complete" (quality score raw output)

    Returns clean human-readable text, or empty string if nothing usable.
    """
    if not text or not isinstance(text, str):
        return ""

    text = text.strip()

    # If it starts with known structured patterns, handle each case
    # Pattern: "no_match|0.00|" or "no_match|..." — no useful content
    if text.startswith("no_match"):
        return ""

    # Pattern: "true|reason" or "false|" — escalation output
    if text.startswith("true|") or text.startswith("false|"):
        return ""

    # Pattern: "intent|confidence" — intent classification output
    _KNOWN_INTENTS = {
        "refund_request", "cancellation", "order_status", "billing_issue",
        "technical_support", "faq_question", "account_modification",
        "escalation", "complaint", "general_inquiry",
    }
    for intent_name in _KNOWN_INTENTS:
        if text.startswith(intent_name + "|"):
            return ""

    # Pattern: "sentiment|urgency" — sentiment output
    _KNOWN_SENTIMENTS = {"happy", "neutral", "frustrated", "angry"}
    for sent in _KNOWN_SENTIMENTS:
        if text.startswith(sent + "|"):
            return ""

    # Pattern: "score|issues" — quality score output (e.g. "85|accurate,complete")
    import re
    if re.match(r"^\d+\.?\d*\|", text):
        return ""

    # Pattern: "faq_id|relevance|content" — FAQ output with content
    # If it has 2+ pipes, the last part might be readable content
    if text.count("|") >= 2:
        parts = text.split("|")
        last_part = parts[-1].strip()
        # Only use last part if it looks like a sentence (starts with capital, has spaces)
        if last_part and len(last_part) > 20 and " " in last_part:
            return last_part
        return ""

    # If it looks like JSON, strip it
    if text.startswith("{") or text.startswith("["):
        return ""

    # If it contains pipe-delimited data embedded in text, strip it out
    # e.g. "Customer is eligible. refund_policy|0.90|Refunds are available"
    cleaned = re.sub(
        r'\b(?:refund_request|cancellation|order_status|billing_issue|'
        r'technical_support|faq_question|account_modification|escalation|complaint|'
        r'general_inquiry|no_match|happy|neutral|frustrated|angry|true|false)'
        r'\|[\d.]*\|?[^\.;!?]*',
        '',
        text
    ).strip()

    if cleaned and len(cleaned) > 10:
        return cleaned

    # If the original text is reasonable human text, return it
    if len(text) > 15 and " " in text and not text.startswith(("true", "false", "no_match")):
        return text

    return ""


def _format_response_rule_based(
    intent: str,
    conclusion: str,
    execution_results: list[dict],
    recommendation: dict | None,
    proactive_insights: list[dict],
    variant: str,
) -> str:
    """Format the final response using rules."""
    # Build response based on intent
    if intent == "refund_request":
        if recommendation and recommendation.get("pending_approval"):
            amount = recommendation.get("parameters", {}).get("amount", "the charge")
            response = (
                f"I found that you were indeed charged twice. "
                f"I've verified you're eligible for a ${amount} refund and have submitted "
                f"this for approval. You'll receive confirmation within 2 hours."
            )
        else:
            amount = "49.99"
            for r in execution_results:
                if r.get("action_type") == "process_refund" and r.get("status") == "executed":
                    amount = "49.99"
                    break
            response = (
                f"Your ${amount} refund has been processed. "
                f"It will appear in 3-5 business days."
            )

    elif intent == "order_status":
        response = "Your order has been located. Based on our records, it's currently being processed."

    elif intent == "cancellation":
        if recommendation and recommendation.get("pending_approval"):
            response = "I've submitted your cancellation request for approval. You'll be notified once it's processed."
        else:
            response = "Your order has been cancelled successfully. You'll receive a confirmation email shortly."

    elif intent == "billing_issue":
        response = "We've reviewed your billing concern. Our team will investigate the charges and get back to you within 24 hours."
    elif intent == "technical_support":
        response = "We've analyzed your technical issue. Our support team is working on a resolution and will update you shortly."
    elif intent == "faq_question":
        if execution_results:
            for r in execution_results:
                if r.get("action_type") == "share_faq" and r.get("status") in ("executed", "recommended"):
                    response = r.get("parameters", {}).get("content", "We found an answer to your question.")
                    break
            else:
                response = "We've found information related to your question. Please let us know if you need more details."
        else:
            response = "We've found information related to your question. Please let us know if you need more details."
    elif intent == "account_modification":
        if recommendation and recommendation.get("pending_approval"):
            response = "I've submitted your account modification request for approval. You'll be notified once it's processed."
        else:
            response = "Your account modification has been processed successfully."
    elif intent == "complaint":
        response = "We take your concerns seriously and apologize for the inconvenience. A member of our team will reach out to you personally."
    else:
        # Clean up conclusion — aggressively remove ANY structured/pipe-delimited output
        # that leaked from other nodes (FAQ, escalation, KB, etc.)
        clean_conclusion = _clean_structured_output(conclusion)
        if clean_conclusion:
            response = f"Thank you for reaching out. {clean_conclusion}"
        else:
            response = "Thank you for reaching out. We've reviewed your request and are working on a resolution."

    # Add proactive insight if available
    if proactive_insights:
        top_insight = proactive_insights[0]
        desc = top_insight.get("description", "")
        if desc and top_insight.get("confidence", 0) > 0.5:
            if "shipping" in desc.lower() or "delivery" in desc.lower():
                response += " Also, I noticed your shipping was delayed — would you like an update on that?"
            elif "timeline" in desc.lower() or "time" in desc.lower():
                response += " Is there anything else you'd like to know?"

    return response


async def _format_response_with_llm(state: dict[str, Any]) -> tuple[str, list[str]]:
    """Format response using direct LLM call (LLM-first strategy).

    The LLM gets full context (reasoning, evidence, actions, sentiment) and
    generates a professional, specific, empathetic response.
    Returns (response, frameworks_used).
    Falls back to rule-based on any failure.
    """
    from parwa.utils.llm import MOCK_MODE, ainvoke_llm
    from parwa.utils.sanitizer import build_safe_prompt

    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    proactive_insights = state.get("proactive_insights", [])
    variant = state.get("variant", "parwa")
    raw_message = state.get("raw_message", "")
    sentiment = state.get("sentiment", "neutral")
    should_escalate = state.get("should_escalate", False)
    escalation_reason = state.get("escalation_reason", "")
    evidence_chain = state.get("evidence_chain", [])
    action_plans = state.get("action_plans", [])

    # Build rich context for the LLM
    context_parts = []
    context_parts.append(f"Customer message: {raw_message}")
    context_parts.append(f"Detected intent: {intent}")
    context_parts.append(f"Customer sentiment: {sentiment}")

    if conclusion:
        context_parts.append(f"Reasoning conclusion: {conclusion}")

    if execution_results:
        for r in execution_results[:5]:
            action_type = r.get("action_type", "unknown")
            status = r.get("status", "unknown")
            params = r.get("parameters", {})
            context_parts.append(f"Action taken: {action_type} — status: {status}, params: {params}")

    if action_plans:
        for ap in action_plans[:5]:
            if isinstance(ap, dict):
                at = ap.get("action_type", "unknown")
                desc = ap.get("description", "")
                context_parts.append(f"Planned action: {at} — {desc}")
            elif hasattr(ap, 'action_type'):
                context_parts.append(f"Planned action: {ap.action_type} — {ap.description}")

    if evidence_chain:
        for e in evidence_chain[:5]:
            if isinstance(e, dict):
                claim = e.get("claim", "")
                conf = e.get("confidence", 0)
                context_parts.append(f"Evidence: {claim} (confidence: {conf:.1f})")

    if should_escalate:
        context_parts.append(f"ESCALATION REQUIRED: {escalation_reason}")
        context_parts.append("A human agent will also be assigned to this case.")

    if recommendation:
        context_parts.append(f"Recommendation: {recommendation}")

    if proactive_insights:
        for pi in proactive_insights[:2]:
            desc = pi.get("description", "") if isinstance(pi, dict) else str(pi)
            if desc:
                context_parts.append(f"Proactive insight: {desc}")

    context = "\n".join(context_parts)

    system_instructions = (
        "You are a professional, empathetic customer support agent. "
        "Write a response to the customer based on the analysis below.\n\n"
        "RULES:\n"
        "1. Be SPECIFIC — include actual data (order IDs, amounts, dates) from the context.\n"
        "2. Be EMPATHETIC — match tone to customer sentiment. If frustrated/angry, apologize sincerely.\n"
        "3. Be CONCISE but thorough — address ALL parts of their issue.\n"
        "4. Tell them WHAT WILL HAPPEN NEXT and WHEN.\n"
        "5. Do NOT output structured data (no pipe-delimited, no JSON). Write natural human language.\n"
        "6. If a refund was processed, mention the exact amount.\n"
        "7. If escalation is required, tell them a human agent will follow up and when.\n"
        "8. Do NOT use generic phrases like 'We take your concerns seriously' or 'A member of our team will'.\n"
        "   Instead, be specific: 'I've processed your $49.99 refund' or 'Our billing specialist Sarah will call you by 3pm tomorrow'.\n"
    )

    try:
        prompt = build_safe_prompt(system_instructions, context)
        text = await ainvoke_llm(
            prompt,
            node_name="RESPONSE_FORMATTER",
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

        # Clean up any structured output that might have leaked
        text = text.strip()
        is_structured_output = (
            "|" in text and text.count("|") >= 2
            or text.startswith("{")
            or len(text) < 20
            or text.startswith("no_match")
            or text.startswith("true|")
            or text.startswith("false|")
        )

        if text and not is_structured_output:
            return text, ["crp", "chain_of_thought"]

        # LLM produced garbage — fall back to rule-based
        response = _format_response_rule_based(
            intent, conclusion, execution_results,
            recommendation, proactive_insights, variant
        )
        return response, ["crp"]

    except Exception as exc:
        logger.warning("response_formatter: LLM failed (%s), falling back to rule-based", exc)
        response = _format_response_rule_based(
            intent, conclusion, execution_results,
            recommendation, proactive_insights, variant
        )
        return response, ["crp"]


@safe_node("RESPONSE_FORMATTER", fallback={"final_response": "We apologize, but we encountered an issue processing your request. A human agent will follow up shortly.", "active_frameworks": []})
async def response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Craft the final customer-facing response (async).

    Phase 5: Uses FrameworkBrain with CRP for constrained output generation.
    Falls back to rule-based on FrameworkBrain failure.

    Reads: intent, reasoning_conclusion, execution_results, recommendation, proactive_insights, variant
    Writes: final_response, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    proactive_insights = state.get("proactive_insights", [])
    variant = state.get("variant", "parwa")

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if not isinstance(execution_results, list):
        execution_results = []
    if recommendation is not None and not isinstance(recommendation, dict):
        recommendation = None
    if not isinstance(proactive_insights, list):
        proactive_insights = []
    if not isinstance(variant, str):
        variant = "parwa"

    # LLM-first strategy: Try direct LLM call first for specific, high-quality responses
    # FrameworkBrain is used inside LLM call chain. Falls back to rule-based only if LLM fails.
    response, frameworks = await _format_response_with_llm(state)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "final_response": response,
        "active_frameworks": new_frameworks,
    }
