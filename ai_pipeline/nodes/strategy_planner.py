"""Node 11: STRATEGY_PLANNER — Creates a multi-step plan before executing.

Reasoning Agent node. Uses the Maker/Strategy Planning framework to create
an ordered execution plan before any action is taken.

Phase 2: Now uses FrameworkBrain with GST (Graph of Strategic Thought)
technique for complex tickets, and standard planning for simpler ones.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.llm import MOCK_MODE, get_mock_llm, get_llm
from parwa.utils.node_base import safe_node

import logging

logger = logging.getLogger("parwa.node.strategy_planner")


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


async def _plan_with_brain(state: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Strategy planning using FrameworkBrain (Phase 2).

    Returns (plan_steps, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    selected_path = state.get("selected_path")
    complexity = state.get("complexity", "simple")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="STRATEGY_PLANNER", state=state)

        # Use GST for complex tickets, simple planning for others
        if complexity in ("complex", "critical"):
            result = await brain.think_single(
                "graph_of_strategic_thought",
                prompt=conclusion or intent,
                ticket_id=state.get("ticket_id", ""),
                variant=state.get("variant", "parwa"),
            )
        else:
            # For simple/medium, just use rule-based with selected_path
            plan = _plan_strategy_rule_based(intent, conclusion, selected_path)
            return plan, ["maker_planning"]

        # Extract plan from GST result
        plan = result.metadata.get("plan_steps", [])

        # If GST produced decision nodes, extract actionable steps
        if not plan and result.output:
            # GST output format: "[Decision: X] → Y"
            # Extract the action part after →
            plan = []
            for line in result.output.split(";"):
                line = line.strip()
                if "→" in line:
                    action = line.split("→", 1)[1].strip()
                    # Remove "Depends on:" suffix for cleaner steps
                    if "depends on:" in action.lower():
                        action = action.split("(depends on:")[0].strip()
                    plan.append(action)
                elif line:
                    plan.append(line)

        # If still no plan, fall back
        if not plan:
            plan = _plan_strategy_rule_based(intent, conclusion, selected_path)
            return plan, ["maker_planning"]

        return plan, result.frameworks_used if result.frameworks_used else ["graph_of_strategic_thought"]

    except Exception as exc:
        logger.warning(
            "strategy_planner: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        plan = _plan_strategy_rule_based(intent, conclusion, selected_path)
        return plan, ["maker_planning"]


@safe_node("STRATEGY_PLANNER", fallback={"strategy_plan": [], "active_frameworks": []})
async def strategy_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Create a multi-step execution plan (async).

    Phase 2: Uses FrameworkBrain with GST for complex tickets,
    standard planning for simpler ones. Falls back to rule-based on failure.

    Reads: intent, reasoning_conclusion, selected_path, complexity
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

    # Try FrameworkBrain first (Phase 2)
    plan, frameworks = await _plan_with_brain(state)

    # Add framework tracking — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # Ensure at least maker_planning is tracked (backward compatibility)
    if not new_frameworks and "maker_planning" not in existing:
        new_frameworks.append("maker_planning")

    return {
        "strategy_plan": plan,
        "active_frameworks": new_frameworks,
    }
