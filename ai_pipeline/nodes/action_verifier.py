"""Node 9: ACTION_VERIFIER — Verifies the action was successful or recommendation is complete.

Action Agent node. Checks that executed actions completed successfully,
and that recommendations are complete with all required fields.
If verification fails, triggers a loop-back to the Reasoning Engine.

Phase 3: Now uses FrameworkBrain with Reverse Thinking + CoT to trace
actions back to their supporting evidence. Catches actions that can't
be traced to actual data — the #1 source of hallucinated actions.
Falls back to rule-based on FrameworkBrain failure.
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


async def _verify_with_brain(
    state: dict[str, Any],
    rule_passed: bool,
) -> tuple[bool, float, list[str]]:
    """Verify actions using FrameworkBrain with Reverse Thinking + CoT.

    Reverse Thinking traces each action back to its evidence — if an action
    can't be traced to KB, CRM, or FAQ data, it's flagged as unsupported.
    CoT provides step-by-step verification reasoning.

    Returns (verified, confidence, frameworks_used).
    Falls back to rule-based result on any failure.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="ACTION_VERIFIER", state=state)

        # Build verification prompt from action plans and evidence
        action_plans = state.get("action_plans", [])
        execution_results = state.get("execution_results", [])
        evidence_parts = []

        for action in action_plans:
            if isinstance(action, dict):
                action_type = action.get("action_type", "unknown")
                action_evidence = action.get("evidence", [])
                evidence_parts.append(f"Action: {action_type}, Evidence: {action_evidence}")

        for result in execution_results:
            if isinstance(result, dict):
                evidence_parts.append(f"Executed: {result.get('action_type', '?')} status={result.get('status', '?')}")

        verification_prompt = (
            f"Verify these actions can be traced to supporting evidence. "
            f"Rule-based check: {'PASSED' if rule_passed else 'FAILED'}. "
            f"Actions: {'; '.join(evidence_parts) if evidence_parts else 'No actions'}"
        )

        # Use Reverse Thinking + CoT for all tickets
        # Add ReAct for complex/critical (verify actions against real data)
        complexity = state.get("complexity", "simple")
        if complexity in ("complex", "critical"):
            techniques = ["reverse_thinking", "chain_of_thought", "react"]
        else:
            techniques = ["reverse_thinking", "chain_of_thought"]

        result = await brain.think(
            prompt=verification_prompt,
            techniques=techniques,
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        frameworks = result.frameworks_used if result.frameworks_used else []

        # If brain traced all actions to evidence with high confidence, confirm
        # If brain found untraceable actions, override rule-based result
        brain_passed = rule_passed
        if result.confidence > 0.7:
            # Brain is confident in its trace — use its verdict
            brain_passed = rule_passed  # Confirm rule-based
        elif result.confidence < 0.4:
            # Brain found evidence gaps — flag even if rule-based passed
            if rule_passed:
                logger.info(
                    "action_verifier: Reverse Thinking found evidence gaps — overriding rule-based PASS"
                )
            brain_passed = False

        return brain_passed, result.confidence, frameworks

    except Exception as exc:
        logger.warning(
            "action_verifier: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        return rule_passed, 0.0, []


@safe_node("ACTION_VERIFIER", fallback={"verification_passed": False, "should_loop_back": False, "active_frameworks": []})
async def action_verifier(state: dict[str, Any]) -> dict[str, Any]:
    """Verify that actions were executed or recommendations are complete (async).

    Phase 3: Uses FrameworkBrain with Reverse Thinking to trace actions
    back to supporting evidence. Catches hallucinated actions that pass
    rule-based checks but lack real evidence. Falls back to rule-based
    on FrameworkBrain failure.

    Reads: execution_results, recommendation, action_plans
    Writes: verification_passed, should_loop_back, active_frameworks (append)
    """
    execution_results = state.get("execution_results", [])
    recommendation = state.get("recommendation")

    # Guard: ensure types
    if not isinstance(execution_results, list):
        execution_results = []
    if recommendation is not None and not isinstance(recommendation, dict):
        recommendation = None

    # Step 1: Rule-based verification
    exec_ok = _verify_execution(execution_results)
    rec_ok = _verify_recommendation(recommendation)
    rule_passed = exec_ok and rec_ok

    # Step 2: FrameworkBrain verification (Phase 3)
    verified, brain_confidence, frameworks = await _verify_with_brain(state, rule_passed)

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # If verification fails and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = not verified and loop_count < max_loops

    return {
        "verification_passed": verified,
        "should_loop_back": should_loop,
        "active_frameworks": new_frameworks,
    }
