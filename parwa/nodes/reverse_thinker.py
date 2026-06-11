"""Node 10: REVERSE_THINKER — Works backwards from the goal to validate the solution.

Reasoning Agent node. Validates the reasoning conclusion by tracing
backwards from the goal to the evidence. If validation fails,
triggers a loop-back to the Reasoning Engine.

Phase 2: Now uses FrameworkBrain with Reverse Thinking technique.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.llm import MOCK_MODE, get_mock_llm, get_llm
from parwa.utils.node_base import safe_node

import logging

logger = logging.getLogger("parwa.node.reverse_thinker")


def _reverse_think_rule_based(
    conclusion: str,
    kb_results: list[dict],
    integration_data: dict,
) -> dict[str, Any]:
    """Validate conclusion by tracing backwards. Returns validation dict."""
    # Start from the conclusion and trace back to evidence
    trace_steps = []
    evidence_found = True

    trace_steps.append(f"Goal: {conclusion}")

    # Check if there's KB evidence supporting the conclusion
    if kb_results:
        trace_steps.append(f"KB evidence found: {len(kb_results)} document(s)")
    else:
        trace_steps.append("No KB evidence found")
        evidence_found = False

    # Check if there's integration data supporting the conclusion
    if integration_data and len(integration_data) > 1:
        trace_steps.append("CRM data available for verification")
    else:
        trace_steps.append("Limited CRM data")
        # Don't fail on just this - some tickets don't need CRM data

    trace_steps.append(f"Evidence confirmed: {'PASSED' if evidence_found else 'INSUFFICIENT'}")

    return {
        "passed": evidence_found,
        "trace": " -> ".join(trace_steps),
        "evidence_found": evidence_found,
    }


async def _reverse_think_with_brain(state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Reverse think using FrameworkBrain (Phase 2).

    Returns (validation_dict, frameworks_used).
    Falls back to rule-based on any failure.
    """
    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="REVERSE_THINKER", state=state)
        result = await brain.think_single(
            "reverse_thinking",
            prompt=state.get("reasoning_conclusion", ""),
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        passed = result.metadata.get("passed", False)
        validation = {
            "passed": passed,
            "trace": " -> ".join(result.chain) if result.chain else "Reverse trace via FrameworkBrain",
            "evidence_found": passed,
            "framework_brain": True,
            "confidence": result.confidence,
        }

        return validation, result.frameworks_used

    except Exception as exc:
        logger.warning(
            "reverse_thinker: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        validation = _reverse_think_rule_based(
            state.get("reasoning_conclusion", ""),
            state.get("kb_results", []),
            state.get("integration_data", {}),
        )
        return validation, ["reverse_thinking"]


@safe_node("REVERSE_THINKER", fallback={"reverse_validation": {"passed": False, "trace": "node_failed", "evidence_found": False}, "active_frameworks": [], "should_loop_back": False})
async def reverse_thinker(state: dict[str, Any]) -> dict[str, Any]:
    """Validate the reasoning conclusion by working backwards (async).

    Phase 2: Uses FrameworkBrain with Reverse Thinking technique.
    Falls back to rule-based on FrameworkBrain failure.

    Reads: reasoning_conclusion, kb_results, integration_data
    Writes: reverse_validation, active_frameworks (append), should_loop_back
    """
    # Try FrameworkBrain first (Phase 2)
    validation, frameworks = await _reverse_think_with_brain(state)

    # Add framework tracking — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # Ensure at least reverse_thinking is tracked
    if not new_frameworks and "reverse_thinking" not in existing:
        new_frameworks.append("reverse_thinking")

    # If validation fails and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = not validation["passed"] and loop_count < max_loops

    return {
        "reverse_validation": validation,
        "active_frameworks": new_frameworks,
        "should_loop_back": should_loop,
    }
