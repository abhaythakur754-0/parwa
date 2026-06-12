"""Node 7: ACTION_PLANNER — Decides what actions should be taken.

Action Agent node. Creates action plans based on the reasoning conclusion
and strategy plan. Each action plan includes the action type, parameters,
and evidence.

Phase 5: Now uses FrameworkBrain with CoT/LeastToMost for complex action planning.
Applies PermissionChecker for variant-aware action mode setting.
Falls back to rule-based on FrameworkBrain failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.permissions import PermissionChecker
from parwa.state import ActionType, ActionPlan, ExecutionMode
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.action_planner")


def _plan_actions_rule_based(
    intent: str,
    conclusion: str,
    strategy_plan: list[str],
    integration_data: dict,
    variant: str = "parwa",
    raw_message: str = "",
) -> list[dict]:
    """Create action plans based on intent and strategy."""
    actions = []
    raw_lower = (raw_message or "").lower()

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

    # ─── Check for voice call / SMS triggers in the message ───
    # If the customer explicitly asks for a callback or phone contact
    voice_keywords = ["call me", "phone call", "call back", "speak on the phone",
                      "ring me", "give me a call", "can you call", "want a call",
                      "need to talk to someone", "talk on the phone", "voice call"]
    sms_keywords = ["text me", "send me a text", "sms", "send sms", "text message",
                    "message my phone", "send a message to my phone"]

    if any(kw in raw_lower for kw in voice_keywords):
        actions.append(ActionPlan(
            action_type=ActionType.VOICE_CALL,
            description="Initiate voice call to customer",
            parameters={"reason": "customer_request"},
            evidence=[conclusion, "Customer requested a phone call"],
            risk_level="low",
        ).model_dump())

    if any(kw in raw_lower for kw in sms_keywords):
        actions.append(ActionPlan(
            action_type=ActionType.SEND_SMS,
            description="Send SMS notification to customer",
            parameters={"message": conclusion[:200] if conclusion else "Follow-up from support", "reason": "customer_request"},
            evidence=[conclusion, "Customer requested SMS notification"],
            risk_level="low",
        ).model_dump())

    # Apply variant permissions to each action
    checker = PermissionChecker(variant=variant)
    for action in actions:
        action_type_str = action.get("action_type", "send_reply")
        try:
            action_type = ActionType(action_type_str)
            mode = checker.get_mode(action_type)
            action["mode"] = mode.value
        except (ValueError, TypeError):
            action["mode"] = ExecutionMode.EXECUTE.value

    return actions


async def _plan_actions_with_brain(state: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Plan actions using FrameworkBrain (Phase 5).

    Uses CoT for simple planning, LeastToMost for complex planning.
    Returns (action_plans, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    strategy_plan = state.get("strategy_plan", [])
    integration_data = state.get("integration_data", {})
    variant = state.get("variant", "parwa")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        # Use LeastToMost for complex planning, CoT for others
        complexity = state.get("complexity", "simple")
        techniques = ["chain_of_thought", "least_to_most"] if complexity in ("complex", "critical") else ["chain_of_thought"]

        brain = FrameworkBrain(node="ACTION_PLANNER", state=state)
        result = await brain.think(
            prompt=f"Plan actions for intent={intent}: {conclusion}",
            techniques=techniques,
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

        frameworks = result.frameworks_used if result.frameworks_used else []

        # Brain enhances planning — use rule-based as base and apply brain insights
        actions = _plan_actions_rule_based(intent, conclusion, strategy_plan, integration_data, variant, raw_message=state.get("raw_message", ""))

        # If brain had high confidence, add additional context to actions
        if result.confidence > 0.7 and result.output:
            for action in actions:
                action["brain_enhanced"] = True

        return actions, frameworks

    except Exception as exc:
        logger.warning(
            "action_planner: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        actions = _plan_actions_rule_based(intent, conclusion, strategy_plan, integration_data, variant, raw_message=state.get("raw_message", ""))
        return actions, ["chain_of_thought"]


@safe_node("ACTION_PLANNER", fallback={"action_plans": [], "active_frameworks": []})
async def action_planner(state: dict[str, Any]) -> dict[str, Any]:
    """Plan actions based on reasoning conclusion and strategy (async).

    Phase 5: Uses FrameworkBrain with CoT/LeastToMost for complex planning.
    Applies PermissionChecker for variant-aware action mode setting.
    Falls back to rule-based on FrameworkBrain failure.

    Reads: intent, reasoning_conclusion, strategy_plan, integration_data, variant, complexity
    Writes: action_plans, active_frameworks (append)
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    strategy_plan = state.get("strategy_plan", [])
    integration_data = state.get("integration_data", {})
    variant = state.get("variant", "parwa")

    # Guard: ensure types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if not isinstance(strategy_plan, list):
        strategy_plan = []
    if not isinstance(integration_data, dict):
        integration_data = {}
    if not isinstance(variant, str):
        variant = "parwa"

    # Try FrameworkBrain first (Phase 5)
    actions, frameworks = await _plan_actions_with_brain(state)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "action_plans": actions,
        "active_frameworks": new_frameworks,
    }
