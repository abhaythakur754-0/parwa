"""Node 21: QUALITY_SCORER — Scores the response before sending.

Compliance Agent node. Evaluates the response on accuracy, completeness,
and compliance. If score < 80, triggers a loop-back to improve the response.

Phase 3: Now uses FrameworkBrain with Reflexion/Self-Consistency/CRP/Least-to-Most
for smarter quality scoring. Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.quality_scorer")


def _score_quality_rule_based(
    intent: str,
    conclusion: str,
    verification_passed: bool,
    has_recommendation: bool,
    variant: str,
    *,
    final_response: str = "",
    execution_results: list[dict] | None = None,
) -> tuple[float, list[str]]:
    """Score response quality using rules. Returns (score, issues).

    Month 1 fix: Now actually catches problems instead of always scoring 100.
    - Checks for generic/template responses
    - Checks for missing evidence in responses
    - Checks for missing action details
    - Deducts points for common quality issues
    """
    score = 75.0  # Start at 75 (base for any ticket that reached this point — means pipeline completed)
    issues = []

    # Has reasoning conclusion
    if conclusion:
        # Check if conclusion is actually substantive (not just restating the problem)
        if len(conclusion) < 20:
            score -= 5
            issues.append("shallow_conclusion")
        else:
            score += 10
    else:
        score -= 15
        issues.append("no_reasoning_conclusion")

    # Verification passed
    if verification_passed:
        score += 5
    else:
        score -= 10
        issues.append("verification_failed")

    # Recommendation is complete (for Mini PARWA)
    if has_recommendation and variant == "mini":
        score += 5
    elif not has_recommendation and variant != "mini":
        score += 5

    # Check final response quality
    if final_response:
        # Generic/template response detection
        generic_phrases = [
            "thank you for reaching out",
            "we've reviewed your request",
            "we take your concerns seriously",
            "a member of our team will",
            "our team will investigate",
            "our support team is working on",
        ]
        is_generic = any(phrase in final_response.lower() for phrase in generic_phrases)
        if is_generic:
            score -= 20
            issues.append("generic_response")

        # Check for specific data (order IDs, amounts, dates)
        import re
        has_specific_data = bool(re.search(r'(ORD-|TKT-|\$[\d,.]+|\d{4}-\d{2}-\d{2}|order #)', final_response))
        if has_specific_data:
            score += 10
        else:
            score -= 5
            issues.append("missing_specific_data")

        # Check response length (too short = likely incomplete)
        if len(final_response) < 50:
            score -= 10
            issues.append("response_too_short")
        elif len(final_response) > 30:
            score += 5
    else:
        score -= 20
        issues.append("no_final_response")

    # Check if execution actually did something
    if execution_results:
        has_executed_action = any(r.get("status") in ("executed", "recommended") for r in execution_results)
        if has_executed_action:
            score += 5
        else:
            score -= 5
            issues.append("no_action_taken")

    # Cap at 100
    score = max(0.0, min(100.0, score))

    return score, issues


async def _score_with_brain(state: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    """Quality scoring using FrameworkBrain (Phase 3).

    Returns (score, issues, frameworks_used).
    Falls back to rule-based on any failure.
    """
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    verification_passed = state.get("verification_passed", False)
    recommendation = state.get("recommendation")
    variant = state.get("variant", "parwa")

    # Guard types
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if not isinstance(verification_passed, bool):
        verification_passed = False
    if not isinstance(variant, str):
        variant = "parwa"

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="QUALITY_SCORER", state=state)

        # Use quality techniques based on complexity
        complexity = state.get("complexity", "simple")
        if complexity in ("complex", "critical"):
            techniques = ["reflexion", "self_consistency", "crp"]
        else:
            techniques = ["reflexion", "crp"]

        result = await brain.think(
            prompt=conclusion or intent,
            techniques=techniques,
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

        # Use brain result to adjust the rule-based score
        base_score, base_issues = _score_quality_rule_based(
            intent, conclusion, verification_passed,
            recommendation is not None, variant,
            final_response=state.get("final_response", ""),
            execution_results=state.get("execution_results", []),
        )

        # If brain found issues, add them
        brain_issues = result.metadata.get("issues", [])
        if brain_issues:
            base_issues.extend(brain_issues)

        # Brain confidence adjusts the score
        if result.confidence > 0.8:
            # Brain is confident — boost score
            base_score = min(100.0, base_score + 5)
        elif result.confidence < 0.5:
            # Brain found problems — reduce score
            base_score = max(0.0, base_score - 10)
            if "brain_low_confidence" not in base_issues:
                base_issues.append("brain_low_confidence")

        # Reflexion metadata
        reflexion_issues = result.metadata.get("issues_found", 0)
        if reflexion_issues > 0:
            base_score = max(0.0, base_score - (reflexion_issues * 3))

        frameworks = result.frameworks_used if result.frameworks_used else []

        return base_score, base_issues, frameworks

    except Exception as exc:
        logger.warning(
            "quality_scorer: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        score, issues = _score_quality_rule_based(
            intent, conclusion, verification_passed,
            recommendation is not None, variant,
            final_response=state.get("final_response", ""),
            execution_results=state.get("execution_results", []),
        )
        return score, issues, []


@safe_node("QUALITY_SCORER", fallback={"quality_score": 0.0, "quality_issues": ["node_failed"], "should_loop_back": False, "active_frameworks": []})
async def quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """Score the quality of the response before sending (async).

    Phase 3: Uses FrameworkBrain with Reflexion/Self-Consistency/CRP
    for smarter quality scoring. Falls back to rule-based on failure.

    Month 1 fix: Now passes final_response and execution_results to
    rule-based scorer so it can actually detect problems.

    Reads: intent, reasoning_conclusion, verification_passed, recommendation, variant,
           final_response, execution_results
    Writes: quality_score, quality_issues, should_loop_back, active_frameworks (append)
    """
    # Try FrameworkBrain first (Phase 3)
    score, issues, frameworks = await _score_with_brain(state)

    # Also run improved rule-based scoring and take the LOWER score
    # (being honest about quality means being conservative)
    intent = state.get("intent", "general_inquiry")
    conclusion = state.get("reasoning_conclusion", "")
    verification_passed = state.get("verification_passed", False)
    recommendation = state.get("recommendation")
    variant = state.get("variant", "parwa")
    final_response = state.get("final_response", "")
    execution_results = state.get("execution_results", [])

    rule_score, rule_issues = _score_quality_rule_based(
        intent, conclusion, verification_passed,
        recommendation is not None, variant,
        final_response=final_response,
        execution_results=execution_results,
    )

    # Take the lower (more honest) score
    if rule_score < score:
        score = rule_score
        issues = rule_issues + issues

    # If score < 80 and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = score < 80 and loop_count < max_loops

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "quality_score": score,
        "quality_issues": issues,
        "should_loop_back": should_loop,
        "active_frameworks": new_frameworks,
    }
