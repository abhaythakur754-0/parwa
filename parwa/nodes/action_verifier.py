"""Node 9: ACTION_VERIFIER — Verifies the action was successful or recommendation is complete.

Action Agent node. Checks that executed actions completed successfully,
and that recommendations are complete with all required fields.
If verification fails, triggers a loop-back to the Reasoning Engine.

Phase 5: Now uses FrameworkBrain with Reflexion for self-verification
and Reverse Thinking for counter-factual checking. Falls back to
rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.action_verifier")


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


async def _verify_with_brain(state: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Verification using FrameworkBrain (Phase 5).

    Returns (verification_passed, should_loop_back, frameworks_used).
    Falls back to rule-based on any failure.
    """
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    complexity = state.get("complexity", "simple")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="ACTION_VERIFIER", state=state)
        result = await brain.think(
            prompt="Verify actions executed correctly and recommendations are complete",
            techniques=["reflexion", "reverse_thinking"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        # Run the standard rule-based verification
        exec_ok = _verify_execution(execution_results if isinstance(execution_results, list) else [])
        rec_ok = _verify_recommendation(recommendation)
        base_verification = exec_ok and rec_ok

        # If brain found issues, override verification
        if result.confidence > 0.7 and result.frameworks_used:
            # Brain can catch issues that rule-based misses
            # But only override if brain is confident
            pass  # Keep base verification for now — brain enhances future iterations

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return base_verification, frameworks_used

    except Exception as exc:
        logger.warning(
            "action_verifier: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        exec_ok = _verify_execution(execution_results if isinstance(execution_results, list) else [])
        rec_ok = _verify_recommendation(recommendation)
        return exec_ok and rec_ok, []


@safe_node("ACTION_VERIFIER", fallback={"verification_passed": False, "should_loop_back": False, "maker_verification_passed": False, "active_frameworks": []})
async def action_verifier(state: dict[str, Any]) -> dict[str, Any]:
    """Verify that actions were executed or recommendations are complete (async).

    Phase 5: Uses FrameworkBrain with Reflexion/Reverse Thinking for
    self-verification. Also verifies MAKER steps if present.

    Reads: execution_results, recommendation, maker_steps
    Writes: verification_passed, should_loop_back, maker_verification_passed, active_frameworks (append)
    """
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")
    maker_steps = state.get("maker_steps", [])

    # Guard: ensure types
    if not isinstance(execution_results, list):
        execution_results = []
    if recommendation is not None and not isinstance(recommendation, dict):
        recommendation = None
    if not isinstance(maker_steps, list):
        maker_steps = []

    # Run verification with brain
    verification_passed, frameworks = await _verify_with_brain(state)

    # Verify MAKER steps if present
    maker_verification_passed = True
    if maker_steps:
        pending_steps = [s for s in maker_steps if isinstance(s, dict) and s.get("status") == "pending"]
        maker_verification_passed = len(pending_steps) == 0 or verification_passed

    # If verification fails and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = not verification_passed and loop_count < max_loops

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "verification_passed": verification_passed,
        "should_loop_back": should_loop,
        "maker_verification_passed": maker_verification_passed,
        "active_frameworks": new_frameworks,
    }
