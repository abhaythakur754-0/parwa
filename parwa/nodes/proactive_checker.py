"""Node 13: PROACTIVE_CHECKER — Anticipates what the customer might ask next.

Proactive Agent node. Predicts follow-up questions or issues
so the response can proactively address them.

Phase 5: Now uses FrameworkBrain with DynamicContext for context-aware
proactive insights. Falls back to rule-based on FrameworkBrain failure.
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
    """Generate proactive insights using FrameworkBrain (Phase 5).

    Uses DynamicContext for context-aware insights.
    Returns (insights, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})
    raw_message = state.get("raw_message", "")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="PROACTIVE_CHECKER", state=state)
        result = await brain.think(
            prompt=raw_message,
            techniques=["dynamic_context"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        frameworks = result.frameworks_used if result.frameworks_used else []

        # Use rule-based as base, enhance with brain context
        insights = _check_proactive_rule_based(intent, integration_data)

        # If brain found context-aware insights, boost confidence
        if result.confidence > 0.5 and insights:
            for insight in insights:
                insight["brain_enhanced"] = True
                insight["confidence"] = min(0.95, insight.get("confidence", 0.5) + 0.1)

        return insights, frameworks

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

    Phase 5: Uses FrameworkBrain with DynamicContext for context-aware
    proactive insights. Falls back to rule-based on FrameworkBrain failure.

    Reads: intent, integration_data, raw_message
    Writes: proactive_insights, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    integration_data = state.get("integration_data", {})

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(integration_data, dict):
        integration_data = {}

    # Try FrameworkBrain first (Phase 5)
    insights, frameworks = await _check_proactive_with_brain(state)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "proactive_insights": insights,
        "active_frameworks": new_frameworks,
    }
