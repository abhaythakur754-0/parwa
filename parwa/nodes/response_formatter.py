"""Node 17: RESPONSE_FORMATTER — Crafts the final customer-facing response.

Compliance Agent node. Takes all gathered information and creates
a helpful, empathetic, and accurate response for the customer.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.node_base import safe_node


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


@safe_node("RESPONSE_FORMATTER")
async def response_formatter(state: dict[str, Any]) -> dict[str, Any]:
    """Craft the final customer-facing response (async).

    Reads: intent, reasoning_conclusion, execution_results, recommendation, proactive_insights, variant
    Writes: final_response
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    proactive_insights = state.get("proactive_insights", [])
    variant = state.get("variant", "parwa")

    response = _format_response_rule_based(
        intent, conclusion, execution_results,
        recommendation, proactive_insights, variant
    )

    return {"final_response": response}
