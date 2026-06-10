"""Node 21: QUALITY_SCORER — Scores the response before sending.

Compliance Agent node. Evaluates the response on accuracy, completeness,
and compliance. If score < 80, triggers a loop-back to improve the response.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.node_base import safe_node


def _score_quality_rule_based(
    intent: str,
    conclusion: str,
    verification_passed: bool,
    has_recommendation: bool,
    variant: str,
) -> tuple[float, list[str]]:
    """Score response quality using rules. Returns (score, issues)."""
    score = 60.0  # start at 60 (base for any ticket that reached this point)
    issues = []

    # Has reasoning conclusion
    if conclusion:
        score += 15
    else:
        issues.append("no_reasoning_conclusion")

    # Verification passed
    if verification_passed:
        score += 10
    else:
        issues.append("verification_failed")

    # Recommendation is complete (for Mini PARWA)
    if has_recommendation and variant == "mini":
        score += 10
    elif not has_recommendation and variant != "mini":
        score += 10

    # No issues = quality bonus
    if not issues:
        score += 5

    # Cap at 100
    score = min(100.0, score)

    return score, issues


@safe_node("QUALITY_SCORER")
async def quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """Score the quality of the response before sending (async).

    Reads: intent, reasoning_conclusion, verification_passed, recommendation, variant
    Writes: quality_score, quality_issues, should_loop_back
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    verification_passed = state.get("verification_passed", False)
    recommendation = state.get("recommendation")
    variant = state.get("variant", "parwa")

    score, issues = _score_quality_rule_based(
        intent, conclusion, verification_passed,
        recommendation is not None, variant
    )

    # If score < 80 and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = score < 80 and loop_count < max_loops

    return {
        "quality_score": score,
        "quality_issues": issues,
        "should_loop_back": should_loop,
    }
