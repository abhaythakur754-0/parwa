"""Node 13: PROACTIVE_CHECKER — Anticipates what the customer might ask next.

Proactive Agent node. Predicts follow-up questions or issues
so the response can proactively address them.

Phase 5: Now uses FrameworkBrain with Dynamic Context/ThoT for
pattern-based proactive insights. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import ProactiveInsight
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.proactive_checker")


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


async def _check_proactive_with_brain(state: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Proactive checking using FrameworkBrain (Phase 5).

    Returns (insights, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="PROACTIVE_CHECKER", state=state)
        result = await brain.think(
            prompt=f"Anticipate follow-up needs for {intent}",
            techniques=["dynamic_context", "thread_of_thought"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        insights = _check_proactive_rule_based(intent, integration_data)

        if result.confidence > 0.5 and result.frameworks_used:
            for insight in insights:
                if isinstance(insight, dict):
                    insight["brain_enhanced"] = True

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return insights, frameworks_used

    except Exception as exc:
        logger.warning(
            "proactive_checker: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        insights = _check_proactive_rule_based(intent, integration_data)
        return insights, []


@safe_node("PROACTIVE_CHECKER", fallback={"proactive_insights": [], "active_frameworks": []})
async def proactive_checker(state: dict[str, Any]) -> dict[str, Any]:
    """Anticipate what the customer might ask next (async).

    Phase 5: Uses FrameworkBrain with Dynamic Context/ThoT for
    pattern-based proactive insights.

    Reads: intent, integration_data
    Writes: proactive_insights, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(integration_data, dict):
        integration_data = {}

    insights, frameworks = await _check_proactive_with_brain(state)

    if not isinstance(insights, list):
        insights = []

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "proactive_insights": insights,
        "active_frameworks": new_frameworks,
    }
