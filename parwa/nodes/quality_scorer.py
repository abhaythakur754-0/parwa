"""Node 21: QUALITY_SCORER — Scores the response before sending.

Compliance Agent node. Evaluates the response on accuracy, completeness,
and compliance. If score < 80, triggers a loop-back to improve the response.

Phase 3: Now uses FrameworkBrain with Reflexion/Self-Consistency/CRP/Least-to-Most
for smarter quality scoring. Falls back to rule-based on failure.

Month 3: Now uses real LLM (via ainvoke_llm) to evaluate response quality
when not in mock mode. This produces honest, variable scores instead of
always returning 50 or 75.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

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


async def _score_with_llm(state: dict[str, Any]) -> tuple[float, list[str]]:
    """Score quality using real LLM evaluation.

    Sends the final response to the LLM and asks it to score on
    accuracy, completeness, compliance, and empathy. Returns (score, issues).

    Only used when not in mock mode.
    """
    final_response = state.get("final_response", "")
    intent = state.get("intent", "general_inquiry")
    raw_message = state.get("raw_message", "")
    variant = state.get("variant", "parwa")

    if not final_response:
        return 0.0, ["no_final_response"]

    system_instructions = (
        "You are a quality auditor for an AI customer support system. "
        "Score this AI response on a scale of 0-100 based on:\n"
        "- ACCURACY: Does the response match the evidence and address the actual issue?\n"
        "- COMPLETENESS: Are all parts of the customer's issue addressed?\n"
        "- COMPLIANCE: Is the response safe, policy-compliant, and appropriate?\n"
        "- EMPATHY: Is the tone appropriate for the customer's sentiment?\n"
        "- SPECIFICITY: Does it include specific data (order IDs, amounts, dates) or is it generic?\n\n"
        f"Customer intent: {intent}\n"
        f"Variant: {variant}\n\n"
        "Reply ONLY with: score|issue1,issue2,issue3\n"
        "where score is 0-100 and issues are comma-separated.\n"
        "Be HONEST — generic/template responses should score below 60. "
        "Only give 80+ if the response is truly excellent."
    )

    prompt = (
        f"CUSTOMER MESSAGE:\n{raw_message}\n\n"
        f"AI RESPONSE TO EVALUATE:\n{final_response}"
    )

    try:
        safe_prompt = build_safe_prompt(system_instructions, prompt)
        text = await ainvoke_llm(
            safe_prompt,
            node_name="QUALITY_SCORER",
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
            # max_tokens removed — uses generous default from _NODE_MAX_TOKENS
        )

        # Parse "score|issue1,issue2" format
        text = text.strip()
        if "|" in text:
            parts = text.split("|", 1)
            try:
                # Extract numeric score from the first part
                score_match = re.search(r'(\d+(?:\.\d+)?)', parts[0])
                score = float(score_match.group(1)) if score_match else 50.0
            except (ValueError, IndexError):
                score = 50.0
            issues = [i.strip() for i in parts[1].split(",") if i.strip()] if len(parts) > 1 else []
        else:
            # Try to extract just a number
            score_match = re.search(r'(\d+(?:\.\d+)?)', text)
            score = float(score_match.group(1)) if score_match else 50.0
            issues = []

        # Clamp score
        score = max(0.0, min(100.0, score))

        return score, issues

    except Exception as exc:
        logger.warning("quality_scorer: LLM evaluation failed (%s), using rule-based", exc)
        return -1.0, []  # Signal to fall back


@safe_node("QUALITY_SCORER", fallback={"quality_score": 0.0, "quality_issues": ["node_failed"], "should_loop_back": False, "active_frameworks": [], "evidence_chain": []})
async def quality_scorer(state: dict[str, Any]) -> dict[str, Any]:
    """Score the quality of the response before sending (async).

    Month 3: Now tries LLM evaluation first (honest scoring), then
    falls back to FrameworkBrain, then rule-based.

    P0: Now uses evidence_chain for quality assessment — checks if claims
    are supported by evidence, and if there are conflicting claims.

    Reads: intent, reasoning_conclusion, verification_passed, recommendation, variant,
           final_response, execution_results, evidence_chain
    Writes: quality_score, quality_issues, should_loop_back, active_frameworks (append), evidence_chain (append)
    """
    frameworks: list[str] = []
    score = 0.0
    issues: list[str] = []

    # ─── Strategy 1: Real LLM evaluation (most honest) ───
    if not MOCK_MODE:
        llm_score, llm_issues = await _score_with_llm(state)
        if llm_score >= 0:
            score = llm_score
            issues = llm_issues

            # Also run rule-based and take the LOWER score (conservative)
            intent = state.get("intent", "general_inquiry")
            conclusion = state.get("reasoning_conclusion", "")
            verification_passed = state.get("verification_passed", False)
            recommendation = state.get("recommendation")
            variant = state.get("variant", "parwa")

            rule_score, rule_issues = _score_quality_rule_based(
                intent, conclusion, verification_passed,
                recommendation is not None, variant,
                final_response=state.get("final_response", ""),
                execution_results=state.get("execution_results", []),
            )
            if rule_score < score:
                score = rule_score
                issues = rule_issues + llm_issues

            logger.debug("quality_scorer: LLM score=%.0f, rule score=%.0f, final=%.0f",
                        llm_score, rule_score, score)
        else:
            # LLM failed, try brain/rule-based
            score, issues, frameworks = await _score_with_brain(state)
    else:
        # Mock mode: use brain/rule-based
        score, issues, frameworks = await _score_with_brain(state)

    # ─── P0: Evidence-chain quality checks ───────────────────────────
    # Check if the evidence chain has issues that the other scorers missed
    existing_chain = state.get("evidence_chain", [])
    if existing_chain:
        # 1. Check for conflicting claims
        claims = []
        for entry in existing_chain:
            if isinstance(entry, dict):
                claims.append(entry.get("claim", "").lower())

        # Check for "FAILED" and "PASSED" in same chain (contradiction)
        has_passed = any("passed" in c or "eligible" in c or "confirmed" in c for c in claims)
        has_failed = any("failed" in c or "insufficient" in c or "no evidence" in c for c in claims)
        if has_passed and has_failed:
            score = max(0.0, score - 10)  # Contradictory evidence → lower score
            if "contradictory_evidence" not in issues:
                issues.append("contradictory_evidence")

        # 2. Check for low-confidence claims
        low_conf_claims = 0
        for entry in existing_chain:
            if isinstance(entry, dict) and entry.get("confidence", 1.0) < 0.5:
                low_conf_claims += 1
        if low_conf_claims > 0:
            score = max(0.0, score - (low_conf_claims * 3))
            if "low_confidence_evidence" not in issues:
                issues.append(f"low_confidence_evidence ({low_conf_claims} claims)")

        # 3. Check if reasoning has evidence backing (not just bare claims)
        reasoning_claims = [e for e in existing_chain if isinstance(e, dict) and e.get("category") == "reasoning"]
        unbacked_claims = [e for e in reasoning_claims if not e.get("sources")]
        if unbacked_claims and len(unbacked_claims) > 0:
            score = max(0.0, score - 5)
            if "unbacked_reasoning_claims" not in issues:
                issues.append("unbacked_reasoning_claims")

        # 4. BONUS: Multiple high-confidence evidence entries = stronger result
        high_conf = sum(1 for e in existing_chain if isinstance(e, dict) and e.get("confidence", 0) > 0.8)
        if high_conf >= 3:
            score = min(100.0, score + 5)  # Strong evidence chain → boost

    # ─── P1: Red Team and Debate quality adjustments ───────────────────
    # Factor in red_team findings and debate results for honest scoring

    # Red Team: If vulnerabilities were found, penalize score
    red_team_report = state.get("red_team_report", {})
    if isinstance(red_team_report, dict) and red_team_report:
        rt_severity = red_team_report.get("severity", "none")
        rt_vuln_count = red_team_report.get("vulnerability_count", 0)

        if rt_severity == "critical":
            score = max(0.0, score - 20)
            if "red_team_critical" not in issues:
                issues.append("red_team_critical")
        elif rt_severity == "high":
            score = max(0.0, score - 12)
            if "red_team_high" not in issues:
                issues.append("red_team_high")
        elif rt_severity == "medium":
            score = max(0.0, score - 5)
            if "red_team_medium" not in issues:
                issues.append("red_team_medium")

        # Bonus: Red team found nothing (passed)
        if red_team_report.get("passed", True) and rt_vuln_count == 0:
            score = min(100.0, score + 3)

    # Agent Debate: If skeptic won or debate was split, penalize
    debate_result = state.get("debate_result", {})
    if isinstance(debate_result, dict) and debate_result:
        debate_outcome = debate_result.get("outcome", "")
        debate_confidence = debate_result.get("confidence", 0.5)

        if debate_outcome == "skeptic_wins":
            score = max(0.0, score - 15)
            if "debate_skeptic_wins" not in issues:
                issues.append("debate_skeptic_wins")
        elif debate_outcome == "partial":
            score = max(0.0, score - 5)
            if "debate_partial" not in issues:
                issues.append("debate_partial")
        elif debate_outcome == "advocate_wins" and debate_confidence > 0.7:
            score = min(100.0, score + 3)  # Strong advocate win = slight boost

    # If score < 80 and we haven't exceeded max loops, trigger loop-back
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = score < 80 and loop_count < max_loops

    # For testing: if max_loops=0, never loop back
    if max_loops <= 0:
        should_loop = False

    # Track frameworks used — return ONLY new frameworks (reducer appends)
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    # P0: Add quality scoring evidence to chain
    new_evidence = [{
        "claim": f"Quality score: {score:.1f}/100 — {'PASS' if score >= 80 else 'FAIL'}",
        "sources": issues[:5] if issues else ["all_checks_passed"],
        "confidence": score / 100.0,
        "technique": "quality_scorer",
        "category": "quality",
        "node": "QUALITY_SCORER",
        "issues_count": len(issues),
    }]

    return {
        "quality_score": score,
        "quality_issues": issues,
        "should_loop_back": should_loop,
        "active_frameworks": new_frameworks,
        "evidence_chain": new_evidence,
    }
