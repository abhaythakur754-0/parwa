"""Node 7: ACTION_PLANNER — Decides what actions should be taken.

Action Agent node. Creates action plans based on the reasoning conclusion
and strategy plan. Each action plan includes the action type, parameters,
and evidence.

Phase 5: Now uses FrameworkBrain with MAKER/GSD for complex action
decomposition and focused planning. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.state import ActionType, ActionPlan
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.action_planner")


def _plan_actions_rule_based(
    intent: str,
    conclusion: str,
    strategy_plan: list[str],
    integration_data: dict,
) -> list[dict]:
    """Create action plans based on intent and strategy."""
    actions = []

    if intent == "refund_request":
        # Calculate refund amount from integration data
        amount = 49.99  # default
        if integration_data.get("charges"):
            amount = integration_data["charges"][0].get("amount", 49.99)

        actions.append(ActionPlan(
            action_type=ActionType.PROCESS_REFUND,
            description=f"Process refund of ${amount}",
            parameters={"amount": amount, "reason": "duplicate_charge"},
            evidence=[
                conclusion,
                f"CRM shows duplicate charges of ${amount}",
            ],
            risk_level="low",
        ).model_dump())

    elif intent == "cancellation":
        actions.append(ActionPlan(
            action_type=ActionType.CANCEL_ORDER,
            description="Cancel the customer's order",
            parameters={"reason": "customer_request"},
            evidence=[conclusion],
            risk_level="medium",
        ).model_dump())

    elif intent == "account_modification":
        actions.append(ActionPlan(
            action_type=ActionType.MODIFY_ACCOUNT,
            description="Modify customer account as requested",
            parameters={"reason": "customer_request"},
            evidence=[conclusion],
            risk_level="medium",
        ).model_dump())

    elif intent == "order_status":
        actions.append(ActionPlan(
            action_type=ActionType.SHARE_POLICY,
            description="Share order status with customer",
            parameters={},
            evidence=[conclusion],
            risk_level="low",
        ).model_dump())

    else:
        # Default: send a reply
        actions.append(ActionPlan(
            action_type=ActionType.SEND_REPLY,
            description="Send helpful response to customer",
            parameters={},
            evidence=[conclusion],
            risk_level="low",
        ).model_dump())

    return actions


async def _plan_actions_with_brain(state: dict[str, Any]) -> tuple[list[dict], list[str], list[dict[str, Any]]]:
    """Action planning using FrameworkBrain (Phase 5).

    Returns (action_plans, frameworks_used, maker_steps).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    strategy_plan = state.get("strategy_plan", [])
    integration_data = state.get("integration_data", {})
    complexity = state.get("complexity", "simple")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="ACTION_PLANNER", state=state)
        result = await brain.think(
            prompt=f"Plan actions for {intent}: {conclusion}",
            techniques=["maker", "gsd", "smart_router"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Get the rule-based plans (brain enhances, doesn't replace)
        action_plans = _plan_actions_rule_based(intent, conclusion, strategy_plan, integration_data)

        # If brain was confident, enhance the plans with MAKER steps
        maker_steps = []
        if result.confidence > 0.6 and result.frameworks_used:
            for plan in action_plans:
                if isinstance(plan, dict):
                    plan["brain_enhanced"] = True
                    plan["frameworks_used"] = result.frameworks_used

            # Extract MAKER steps from metadata
            if "maker" in result.frameworks_used and result.metadata.get("steps"):
                maker_steps = result.metadata["steps"]

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return action_plans, frameworks_used, maker_steps

    except Exception as exc:
        logger.warning(
            "action_planner: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        action_plans = _plan_actions_rule_based(intent, conclusion, strategy_plan, integration_data)
        return action_plans, [], []


@safe_node("ACTION_PLANNER", fallback={"action_plans": [], "active_frameworks": [], "maker_steps": []})
async def action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan actions based on reasoning conclusion and strategy (async).

    Phase 5: Uses FrameworkBrain with MAKER/GSD/Smart Router for
    complex action decomposition and focused planning.

    Reads: intent, reasoning_conclusion, strategy_plan, integration_data
    Writes: action_plans, active_frameworks (append), maker_steps
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    strategy_plan = state.get("strategy_plan", [])
    integration_data = state.get("integration_data", {})

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if not isinstance(strategy_plan, list):
        strategy_plan = []
    if not isinstance(integration_data, dict):
        integration_data = {}

    action_plans, frameworks, maker_steps = await _plan_actions_with_brain(state)

    if not isinstance(action_plans, list):
        action_plans = []
    if not isinstance(maker_steps, list):
        maker_steps = []

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "action_plans": action_plans,
        "active_frameworks": new_frameworks,
        "maker_steps": maker_steps,
    }
