"""Node 10: REVERSE_THINKER — Works backwards from the goal to validate the solution.

Reasoning Agent node. Validates the reasoning conclusion by tracing
backwards from the goal to the evidence. If validation fails,
triggers a loop-back to the Reasoning Engine.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.llm import MOCK_MODE, get_mock_llm, get_llm
from parwa.utils.node_base import safe_node


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


@safe_node("REVERSE_THINKER")
async def reverse_thinker(state: dict[str, Any]) -> dict[str, Any]:
    """Validate the reasoning conclusion by working backwards (async).

    Reads: reasoning_conclusion, kb_results, integration_data
    Writes: reverse_validation, active_frameworks (append), should_loop_back
    """
    conclusion = state.get("reasoning_conclusion", "")
    kb_results = state.get("kb_results", [])
    integration_data = state.get("integration_data", {})

    validation = _reverse_think_rule_based(conclusion, kb_results, integration_data)

    # Add framework tracking
    active_frameworks = list(state.get("active_frameworks", []))
    if "reverse_thinking" not in active_frameworks:
        active_frameworks.append("reverse_thinking")

    # If validation fails and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = not validation["passed"] and loop_count < max_loops

    return {
        "reverse_validation": validation,
        "active_frameworks": active_frameworks,
        "should_loop_back": should_loop,
    }
