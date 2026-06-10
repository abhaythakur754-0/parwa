"""Node 11: STRATEGY_PLANNER — Creates a multi-step plan before executing.

Reasoning Agent node. Uses the Maker/Strategy Planning framework to create
an ordered execution plan before any action is taken.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.llm import MOCK_MODE, get_mock_llm, get_llm
from parwa.utils.node_base import safe_node


def _plan_strategy_rule_based(intent: str, conclusion: str, selected_path: dict | None) -> list[str]:
    """Create a strategy plan based on intent and selected path."""
    # If a path was selected by ToT, use its steps
    if selected_path and selected_path.get("steps"):
        return selected_path["steps"]

    # Fallback: generate plan based on intent
    if intent == "refund_request":
        return [
            "Verify duplicate charge in CRM",
            "Calculate refund amount",
            "Check policy eligibility (30-day window)",
            "Submit for approval or execute refund",
            "Confirm refund with customer",
        ]
    elif intent == "cancellation":
        return [
            "Verify order is within cancellation window",
            "Check if order has shipped",
            "Process cancellation",
            "Confirm cancellation with customer",
        ]
    elif intent == "order_status":
        return [
            "Look up order in CRM",
            "Get tracking information",
            "Provide status update to customer",
        ]
    else:
        return [
            "Review available evidence",
            "Determine appropriate action",
            "Execute or recommend action",
            "Confirm resolution with customer",
        ]


@safe_node("STRATEGY_PLANNER", fallback={"strategy_plan": [], "active_frameworks": []})
async def strategy_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Create a multi-step execution plan (async).

    Reads: intent, reasoning_conclusion, selected_path
    Writes: strategy_plan, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    selected_path = state.get("selected_path")

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if selected_path is not None and not isinstance(selected_path, dict):
        selected_path = None

    plan = _plan_strategy_rule_based(intent, conclusion, selected_path)

    # Add framework tracking
    active_frameworks = list(state.get("active_frameworks", []))
    if "maker_planning" not in active_frameworks:
        active_frameworks.append("maker_planning")

    return {
        "strategy_plan": plan,
        "active_frameworks": active_frameworks,
    }
