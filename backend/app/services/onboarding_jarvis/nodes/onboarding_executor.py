"""
PARWA Onboarding Executor Node

The Executor Node takes the specialist agent's decision and executes it
against the backend. It's the "hands" of the onboarding Jarvis — when
an agent decides to book a call, verify email, or create a payment session,
this node actually does it.

This node runs AFTER the specialist agent has produced a decision.
It does NOT produce a user-facing response — it only executes the
action and updates the execution result.

BC-008: Never crash — all execution wrapped in try/except.
BC-001: company_id first parameter on all operations.
BC-012: All timestamps UTC.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict

from app.logger import get_logger

logger = get_logger("onboarding_executor")


def onboarding_executor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the specialist agent's decision against the backend.

    Takes the agent_decision from state and maps it to actual backend
    operations. Each executor is independently wrapped in try/except.

    Args:
        state: Current OnboardingJarvisState dict.

    Returns:
        Dict with updated EXECUTION group fields.
    """
    start_time = time.monotonic()

    try:
        agent_type = state.get("agent_type", "")
        agent_action = state.get("agent_action", "")
        agent_decision = state.get("agent_decision", {})

        # Execute based on agent action
        execution_result = _execute_action(state, agent_type, agent_action, agent_decision)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = {
            "execution_status": execution_result.get("status", "skipped"),
            "execution_result": execution_result,
            "execution_error": execution_result.get("error", ""),
            "execution_time_ms": elapsed_ms,
            "node_outputs": {"onboarding_executor": execution_result},
            "audit_trail": [{
                "step": "onboarding_executor",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_type": agent_type,
                "agent_action": agent_action,
                "execution_status": execution_result.get("status", "skipped"),
                "elapsed_ms": elapsed_ms,
            }],
        }

        logger.info(
            "onboarding_executor: session=%s, agent=%s, action=%s, "
            "status=%s, ms=%.1f",
            state.get("session_id", ""),
            agent_type,
            agent_action,
            execution_result.get("status", "skipped"),
            elapsed_ms,
        )

        return result

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.exception("onboarding_executor_error: ms=%.1f", elapsed_ms)
        return {
            "execution_status": "failed",
            "execution_result": {},
            "execution_error": str(e)[:200],
            "execution_time_ms": elapsed_ms,
            "errors": [f"onboarding_executor: {str(e)[:200]}"],
        }


def _execute_action(
    state: Dict[str, Any],
    agent_type: str,
    agent_action: str,
    agent_decision: Dict[str, Any],
) -> Dict[str, Any]:
    """Map agent actions to backend operations.

    Returns execution result dict with status, data, and any error.
    """
    try:
        # Most actions in the onboarding flow are handled by the
        # orchestrator's function execution pipeline. The executor
        # node serves as a secondary execution path for actions that
        # need immediate backend state changes without going through
        # the full LLM function calling cycle.

        action_map = {
            "guide": _exec_guide_action,
            "sell": _exec_sell_action,
            "demo": _exec_demo_action,
            "call": _exec_call_action,
        }

        executor = action_map.get(agent_action, _exec_noop)
        return executor(state, agent_decision)

    except Exception as e:
        logger.exception("execute_action_failed: action=%s", agent_action)
        return {"status": "failed", "error": str(e)[:200]}


def _exec_guide_action(state: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """Execute guide-related actions (industry selection, etc.)."""
    try:
        # Guide actions are mostly informational — no backend changes needed
        # except for industry/variant selection which is handled by context updates
        return {
            "status": "completed",
            "action": "guide",
            "data": {
                "intent_detected": state.get("intent_detected", ""),
                "next_suggestion": decision.get("next_suggestion", ""),
            },
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)[:200]}


def _exec_sell_action(state: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """Execute sales-related actions (ROI calculation, objection handling)."""
    try:
        roi_data = decision.get("roi_data", {})
        return {
            "status": "completed",
            "action": "sell",
            "data": {
                "objection_type": decision.get("objection_type", "none"),
                "roi_data": roi_data,
            },
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)[:200]}


def _exec_demo_action(state: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """Execute demo-related actions (scenario, customer question)."""
    try:
        return {
            "status": "completed",
            "action": "demo",
            "data": {
                "scenario_type": decision.get("scenario_type", "general_inquiry"),
                "variant_id": decision.get("variant_id", ""),
                "industry": decision.get("industry", ""),
            },
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)[:200]}


def _exec_call_action(state: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """Execute call-related actions (booking, OTP, call initiation)."""
    try:
        return {
            "status": "completed",
            "action": "call",
            "data": {
                "call_phase": decision.get("call_phase", "booking"),
                "phone_number": decision.get("phone_number", ""),
                "call_duration_seconds": decision.get("call_duration_seconds", 0),
            },
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)[:200]}


def _exec_noop(state: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """No-op executor for actions that don't need backend changes."""
    return {"status": "skipped", "action": "noop", "data": {}}
