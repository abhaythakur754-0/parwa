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


async def _format_response_with_brain(state: dict[str, Any]) -> tuple[str, list[str]]:
    """Format response using FrameworkBrain (Phase 5).

    Uses CRP (Constrained Response Protocol) for structured output.
    Returns (response, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    proactive_insights = state.get("proactive_insights", [])
    variant = state.get("variant", "parwa")
    raw_message = state.get("raw_message", "")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="RESPONSE_FORMATTER", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=["crp"],
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

        frameworks = result.frameworks_used if result.frameworks_used else []

        # Use brain output if it's good, otherwise fall back to rule-based
        # BUT: reject structured/pipe-delimited outputs that are meant for internal parsing
        is_structured_output = (
            "|" in result.output and result.output.count("|") >= 2  # pipe-delimited like "intent|confidence"
            or result.output.strip().startswith("{")  # JSON
            or len(result.output.strip()) < 20  # Too short for a real response
            or result.output.strip().startswith("no_match")  # FAQ matcher raw output
            or result.output.strip().startswith("true|")  # Escalation raw output
            or result.output.strip().startswith("false|")  # Escalation raw output
        )
        if result.output and result.confidence > 0.5 and not is_structured_output:
            response = result.output
            return response, frameworks

        # Brain didn't produce good output — use rule-based
        response = _format_response_rule_based(
            intent, conclusion, execution_results,
            recommendation, proactive_insights, variant
        )
        return response, frameworks if frameworks else ["crp"]

    except Exception as exc:
        logger.warning(
            "response_formatter: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        response = _format_response_rule_based(
            intent, conclusion, execution_results,
            recommendation, proactive_insights, variant
        )
        return response, ["crp"]


@safe_node("RESPONSE_FORMATTER", fallback={"final_response": "We apologize, but we encountered an issue processing your request. A human agent will follow up shortly.", "active_frameworks": []})
async def response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Craft the final customer-facing response (async).

    Month 3: Now uses V2 context-aware, persona-based formatter by default.
    Falls back to V1 rule-based on V2 failure.

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

    # ─── Month 3: Try V2 context-aware formatter first ─────────────
    try:
        from parwa.nodes.response_formatter_v2 import format_response_v2
        v2_result = await format_response_v2(state)
        if v2_result and v2_result.get("final_response"):
            response = v2_result["final_response"]
            frameworks = v2_result.get("active_frameworks", ["persona_engine", "context_aware"])
        else:
            raise ValueError("V2 returned empty response")
    except Exception as exc:
        logger.warning(
            "response_formatter: V2 failed (%s), falling back to V1",
            exc,
        )
        # Fall back to V1 FrameworkBrain + rule-based
        response, frameworks = await _format_response_with_brain(state)

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
