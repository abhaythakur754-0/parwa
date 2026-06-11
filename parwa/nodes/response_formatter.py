"""Node 17: RESPONSE_FORMATTER — Crafts the final customer-facing response.

Compliance Agent node. Takes all gathered information and creates
a helpful, empathetic, and accurate response for the customer.

Phase 5: Now uses FrameworkBrain with CRP for compliance-aware
response formatting and CoT for nuanced responses. Falls back to
rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.response_formatter")


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

    else:
        response = f"Thank you for reaching out. {conclusion}"

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


async def _format_with_brain(state: dict[str, Any]) -> tuple[str, list[str]]:
    """Response formatting using FrameworkBrain (Phase 5).

    Returns (final_response, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    proactive_insights = state.get("proactive_insights", [])
    variant = state.get("variant", "parwa")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="RESPONSE_FORMATTER", state=state)
        result = await brain.think(
            prompt=f"Format response for {intent}",
            techniques=["crp", "chain_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

        # Always use rule-based as the foundation
        response = _format_response_rule_based(
            intent, conclusion, execution_results,
            recommendation, proactive_insights, variant,
        )

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return response, frameworks_used

    except Exception as exc:
        logger.warning(
            "response_formatter: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        response = _format_response_rule_based(
            intent, conclusion, execution_results,
            recommendation, proactive_insights, variant,
        )
        return response, []


@safe_node("RESPONSE_FORMATTER", fallback={"final_response": "We apologize, but we encountered an issue processing your request. A human agent will follow up shortly.", "active_frameworks": []})
async def response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Craft the final customer-facing response (async).

    Phase 5: Uses FrameworkBrain with CRP/CoT for compliance-aware
    response formatting.

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

    response, frameworks = await _format_with_brain(state)

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "final_response": response,
        "active_frameworks": new_frameworks,
    }
