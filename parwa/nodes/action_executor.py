"""Node 8: ACTION_EXECUTOR — Executes planned actions or creates recommendations.

Action Agent node. THIS IS THE KEY NODE for variant differentiation.
- If variant allows EXECUTE: runs the action
- If variant allows RECOMMEND: creates a recommendation for human approval
- If variant DENIES: skips the action
"""

from __future__ import annotations

from typing import Any

from parwa.config import get_permission
from parwa.state import ActionType, ExecutionMode


def _execute_action(action_plan: dict, state: dict) -> dict[str, Any]:
    """Execute an action directly. Returns execution result."""
    action_type = action_plan.get("action_type", "send_reply")
    params = action_plan.get("parameters", {})

    return {
        "action_type": action_type,
        "status": "executed",
        "message": f"Action '{action_type}' executed successfully",
        "parameters": params,
    }


def _create_recommendation(action_plan: dict, state: dict) -> dict[str, Any]:
    """Create a recommendation for human approval (Mini PARWA)."""
    action_type = action_plan.get("action_type", "send_reply")
    evidence = action_plan.get("evidence", [])
    params = action_plan.get("parameters", {})
    risk_level = action_plan.get("risk_level", "low")
    quality_score = state.get("quality_score", 0)

    return {
        "pending_approval": True,
        "action_type": action_type,
        "description": action_plan.get("description", ""),
        "evidence": evidence,
        "parameters": params,
        "risk_level": risk_level,
        "quality_score": quality_score,
        "message": f"Recommended action '{action_type}' pending human approval for this variant.",
    }


def action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute or recommend actions based on variant permissions.

    Reads: action_plans, variant
    Writes: execution_results, recommendation
    """
    variant = state.get("variant", "parwa")
    action_plans = state.get("action_plans", [])

    execution_results = []
    recommendation = None

    for plan in action_plans:
        action_type_str = plan.get("action_type", "send_reply")

        # Get the ActionType enum
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.SEND_REPLY

        # Check variant permissions
        permission = get_permission(variant, action_type)

        if permission == ExecutionMode.EXECUTE:
            result = _execute_action(plan, state)
            execution_results.append(result)

        elif permission == ExecutionMode.RECOMMEND:
            # Don't execute — create recommendation for human
            recommendation = _create_recommendation(plan, state)
            execution_results.append({
                "action_type": action_type_str,
                "status": "recommended",
                "message": f"Action '{action_type_str}' requires human approval for variant '{variant}'",
            })

        elif permission == ExecutionMode.DENY:
            execution_results.append({
                "action_type": action_type_str,
                "status": "denied",
                "message": f"Action '{action_type_str}' is not available for variant '{variant}'",
            })

    return {
        "execution_results": execution_results,
        "recommendation": recommendation,
    }
