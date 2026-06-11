"""Node 13: PROACTIVE_CHECKER — Anticipates what the customer might ask next.

Proactive Agent node. Predicts follow-up questions or issues
so the response can proactively address them.
"""

from __future__ import annotations

from typing import Any

from parwa.state import ProactiveInsight
from parwa.utils.node_base import safe_node


def _check_proactive_rule_based(intent: str, integration_data: dict) -> list[dict]:
    """Generate proactive insights based on intent and data."""
    insights = []

    if intent == "refund_request":
        insights.append(ProactiveInsight(
            type="follow_up",
            description="Customer may ask about refund timeline",
            confidence=0.80,
            suggested_action="Include refund processing time in response",
        ).model_dump())
        # If integration data shows shipping delay
        if integration_data.get("orders"):
            for order in integration_data["orders"]:
                if order.get("status") == "delayed":
                    insights.append(ProactiveInsight(
                        type="follow_up",
                        description="Customer's shipping was also delayed",
                        confidence=0.75,
                        suggested_action="Offer shipping update proactively",
                    ).model_dump())

    elif intent == "order_status":
        insights.append(ProactiveInsight(
            type="follow_up",
            description="Customer may want to modify or cancel the order",
            confidence=0.50,
            suggested_action="Include modification options in response",
        ).model_dump())

    elif intent == "cancellation":
        insights.append(ProactiveInsight(
            type="follow_up",
            description="Customer may ask about reordering or alternatives",
            confidence=0.60,
            suggested_action="Suggest alternative products",
        ).model_dump())

    # Default proactive insight
    if not insights:
        insights.append(ProactiveInsight(
            type="follow_up",
            description="Customer may have additional questions",
            confidence=0.30,
            suggested_action="Offer further assistance",
        ).model_dump())

    return insights


@safe_node("PROACTIVE_CHECKER", fallback={"proactive_insights": []})
async def proactive_checker(state: dict[str, Any]) -> dict[str, Any]:
    """Anticipate what the customer might ask next (async).

    Reads: intent, integration_data
    Writes: proactive_insights
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(integration_data, dict):
        integration_data = {}

    insights = _check_proactive_rule_based(intent, integration_data)

    return {"proactive_insights": insights}
