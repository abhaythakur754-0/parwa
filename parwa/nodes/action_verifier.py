"""Node 9: ACTION_VERIFIER — Verifies the action was successful or recommendation is complete.

Action Agent node. Checks that executed actions completed successfully,
and that recommendations are complete with all required fields.
If verification fails, triggers a loop-back to the Reasoning Engine.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.node_base import safe_node


def _verify_execution(execution_results: list[dict]) -> bool:
    """Verify that all executed actions completed successfully."""
    for result in execution_results:
        status = result.get("status", "")
        if status == "executed":
            continue  # success
        elif status == "recommended":
            continue  # valid outcome for Mini PARWA
        elif status == "denied":
            continue  # valid outcome for restricted variants
        elif status == "failed":
            return False  # actual failure
    return True


def _verify_recommendation(recommendation: dict | None) -> bool:
    """Verify that a recommendation has all required fields."""
    if recommendation is None:
        return True  # No recommendation needed = verified

    required_fields = ["pending_approval", "action_type", "evidence", "parameters"]
    for field in required_fields:
        if field not in recommendation:
            return False
    return True


@safe_node("ACTION_VERIFIER", fallback={"verification_passed": False, "should_loop_back": False})
async def action_verifier(state: dict[str, Any]) -> dict[str, Any]:
    """Verify that actions were executed or recommendations are complete (async).

    Reads: execution_results, recommendation
    Writes: verification_passed, should_loop_back
    """
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")

    # Guard: ensure types
    if not isinstance(execution_results, list):
        execution_results = []
    if recommendation is not None and not isinstance(recommendation, dict):
        recommendation = None

    exec_ok = _verify_execution(execution_results)
    rec_ok = _verify_recommendation(recommendation)
    verification_passed = exec_ok and rec_ok

    # If verification fails and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = not verification_passed and loop_count < max_loops

    return {
        "verification_passed": verification_passed,
        "should_loop_back": should_loop,
    }
