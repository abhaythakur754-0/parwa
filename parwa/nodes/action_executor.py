"""Node 8: ACTION_EXECUTOR — Executes planned actions or creates recommendations.

Action Agent node. THIS IS THE KEY NODE for variant differentiation.
- If variant allows EXECUTE: runs the action
- If variant allows RECOMMEND: creates a recommendation for human approval
- If variant DENIES: skips the action

Phase 5: Now uses FrameworkBrain with GSD for focused execution AND
PermissionExecutor for proper variant-based permission enforcement.
Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.config import get_permission
from parwa.permissions.executor import PermissionExecutor
from parwa.state import ActionType, ExecutionMode
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.action_executor")


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


def _create_recommendation(action_plan: dict, state: dict, perm_result=None) -> dict[str, Any]:
    """Create a recommendation for human approval (Mini PARWA)."""
    action_type = action_plan.get("action_type", "send_reply")
    evidence = action_plan.get("evidence", [])
    params = action_plan.get("parameters", {})
    risk_level = action_plan.get("risk_level", "low")
    quality_score = state.get("quality_score", 0)

    rec = {
        "pending_approval": True,
        "action_type": action_type,
        "description": action_plan.get("description", ""),
        "evidence": evidence,
        "parameters": params,
        "risk_level": risk_level,
        "quality_score": quality_score,
        "message": f"Recommended action '{action_type}' pending human approval for this variant.",
    }

    # Add permission reason if available
    if perm_result and hasattr(perm_result, "reason"):
        rec["permission_reason"] = perm_result.reason

    return rec


async def _execute_with_brain(state: dict[str, Any]) -> tuple[list[dict], dict | None, list[str]]:
    """Action execution using FrameworkBrain + PermissionExecutor (Phase 5).

    Returns (execution_results, recommendation, frameworks_used).
    Falls back to rule-based on any failure.
    """
    variant = state.get("variant", "parwa")
    action_plans = state.get("action_plans", [])

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="ACTION_EXECUTOR", state=state)
        result = await brain.think(
            prompt="Execute or recommend actions based on variant permissions",
            techniques=["gsd", "smart_router"],
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

        # Use PermissionExecutor for proper enforcement
        executor = PermissionExecutor(variant=variant)
        execution_results = []
        recommendation = None

        for plan in action_plans:
            action_type_str = plan.get("action_type", "send_reply")
            perm_result = executor.evaluate(action_type_str)

            if perm_result.can_auto_execute:
                exec_result = _execute_action(plan, state)
                if result.frameworks_used:
                    exec_result["brain_enhanced"] = True
                    exec_result["frameworks_used"] = result.frameworks_used
                execution_results.append(exec_result)

            elif perm_result.allowed:
                # RECOMMEND mode — create recommendation
                recommendation = _create_recommendation(plan, state, perm_result)
                execution_results.append({
                    "action_type": action_type_str,
                    "status": "recommended",
                    "message": perm_result.reason,
                })

            else:
                # DENY mode
                execution_results.append({
                    "action_type": action_type_str,
                    "status": "denied",
                    "message": perm_result.reason,
                })

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return execution_results, recommendation, frameworks_used

    except Exception as exc:
        logger.warning(
            "action_executor: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        execution_results, recommendation = _execute_rule_based(state)
        return execution_results, recommendation, []


def _execute_rule_based(state: dict[str, Any]) -> tuple[list[dict], dict | None]:
    """Rule-based execution with basic permission checking."""
    variant = state.get("variant", "parwa")
    action_plans = state.get("action_plans", [])

    if not isinstance(variant, str):
        variant = "parwa"
    if not isinstance(action_plans, list):
        action_plans = []

    execution_results = []
    recommendation = None

    for plan in action_plans:
        action_type_str = plan.get("action_type", "send_reply")

        # Get the ActionType enum
        try:
            action_type = ActionType(action_type_str)
        except (ValueError, TypeError):
            action_type = ActionType.SEND_REPLY

        # Check variant permissions
        try:
            permission = get_permission(variant, action_type)
        except (ValueError, KeyError) as exc:
            logger.warning(
                "ACTION_EXECUTOR: permission check failed for variant=%s action=%s: %s",
                variant, action_type_str, exc,
            )
            permission = ExecutionMode.DENY

        if permission == ExecutionMode.EXECUTE:
            result = _execute_action(plan, state)
            execution_results.append(result)

        elif permission == ExecutionMode.RECOMMEND:
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

    return execution_results, recommendation


@safe_node("ACTION_EXECUTOR", fallback={"execution_results": [], "recommendation": None, "active_frameworks": []})
async def action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute or recommend actions based on variant permissions (async).

    Phase 5: Uses FrameworkBrain with GSD/Smart Router AND
    PermissionExecutor for proper variant-based enforcement.

    Reads: action_plans, variant
    Writes: execution_results, recommendation, active_frameworks (append)
    """
    variant = state.get("variant", "parwa")
    action_plans = state.get("action_plans", [])

    # Guard: ensure types
    if not isinstance(variant, str):
        variant = "parwa"
    if not isinstance(action_plans, list):
        action_plans = []

    execution_results, recommendation, frameworks = await _execute_with_brain(state)

    if not isinstance(execution_results, list):
        execution_results = []

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "execution_results": execution_results,
        "recommendation": recommendation,
        "active_frameworks": new_frameworks,
    }
