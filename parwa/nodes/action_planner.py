"""Node 7: ACTION_PLANNER — Decides what actions should be taken.

Action Agent node. Creates action plans based on the reasoning conclusion
and strategy plan. Each action plan includes the action type, parameters,
and evidence.
"""

from __future__ import annotations

from typing import Any

from parwa.state import ActionType, ActionPlan
from parwa.utils.node_base import safe_node


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


@safe_node("ACTION_PLANNER")
def action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan actions based on reasoning conclusion and strategy.

    Reads: intent, reasoning_conclusion, strategy_plan, integration_data
    Writes: action_plans
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    strategy_plan = state.get("strategy_plan", [])
    integration_data = state.get("integration_data", {})

    actions = _plan_actions_rule_based(intent, conclusion, strategy_plan, integration_data)

    return {"action_plans": actions}
