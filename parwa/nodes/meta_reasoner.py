"""Node: META_REASONER — Reasons about the pipeline's own reasoning quality.

P3 NEW NODE: The Meta-Reasoner sits AFTER the quality scorer and does
something no other node does — it reasons ABOUT the pipeline itself.

What it checks:
  1. Is the reasoning self-consistent? (Do different nodes agree?)
  2. Is the evidence chain coherent? (Do claims support each other?)
  3. Is the confidence calibrated? (Is high confidence warranted?)
  4. Are there blind spots? (Did the pipeline miss something obvious?)
  5. Is the reasoning circular? (Did nodes just validate each other?)

This is different from:
  - Quality Scorer: Scores the FINAL response. Meta-Reasoner scores the PROCESS.
  - Red Team: Attacks for logical flaws. Meta-Reasoner checks for structural issues.
  - Self-Consistency: Checks if outputs agree. Meta-Reasoner checks if the
    pipeline's reasoning STRUCTURE is sound.

Meta-reasoning catches problems that individual nodes can't see because
they only see their own slice of the pipeline. It's the "helicopter view"
that checks whether all the pieces fit together.

If meta-reasoning finds serious structural issues, it can:
  - Override the quality score (lower it)
  - Add warnings to the response
  - Trigger a loop-back with specific guidance on what to fix

Variant behavior:
  - mini: Lightweight structural check (fast)
  - parwa: Structural check + calibration analysis (balanced)
  - high: Full meta-reasoning with blind-spot detection (thorough)
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.meta_reasoner")


def _meta_reason_rule_based(state: dict[str, Any]) -> dict[str, Any]:
    """Check reasoning structure using rules (fast, no LLM).

    Examines the pipeline's reasoning STRUCTURE — not the content,
    but whether the structure is sound.
    """
    issues = []
    quality_adjustment = 0.0  # Positive = boost, negative = penalty

    evidence_chain = state.get("evidence_chain", [])
    quality_score = state.get("quality_score", 0.0)
    reasoning_chain = state.get("reasoning_chain", [])
    reasoning_conclusion = state.get("reasoning_conclusion", "")
    action_plans = state.get("action_plans", [])
    final_response = state.get("final_response", "")
    red_team_report = state.get("red_team_report", {})
    debate_result = state.get("debate_result", {})
    situation_model = state.get("situation_model", {})
    policy_report = state.get("policy_report", {})

    # ─── Check 1: Evidence chain coherence ────────────────────────
    # Are the evidence entries consistent with each other?
    if isinstance(evidence_chain, list) and len(evidence_chain) > 1:
        claims = []
        for entry in evidence_chain:
            if isinstance(entry, dict):
                claims.append(entry.get("claim", "").lower())

        # Check for direct contradictions
        positive_signals = ["passed", "eligible", "approved", "confirmed", "verified"]
        negative_signals = ["failed", "denied", "insufficient", "not eligible", "vulnerability"]

        has_positive = any(any(s in c for s in positive_signals) for c in claims)
        has_negative = any(any(s in c for s in negative_signals) for c in claims)

        if has_positive and has_negative:
            issues.append({
                "type": "contradictory_evidence_chain",
                "severity": "high",
                "description": "Evidence chain contains contradictory signals (both positive and negative)",
                "adjustment": -10,
            })
            quality_adjustment -= 10

    # ─── Check 2: Reasoning-to-action alignment ───────────────────
    # Do the actions match what the reasoning concluded?
    if reasoning_conclusion and isinstance(action_plans, list):
        conclusion_lower = reasoning_conclusion.lower()

        # If conclusion says "eligible for refund" but no refund action
        if "eligible" in conclusion_lower and "refund" in conclusion_lower:
            has_refund = any(
                isinstance(a, dict) and a.get("action_type") == "process_refund"
                for a in action_plans
            )
            if not has_refund:
                issues.append({
                    "type": "reasoning_action_mismatch",
                    "severity": "high",
                    "description": "Reasoning concludes refund eligibility but no refund action planned",
                    "adjustment": -15,
                })
                quality_adjustment -= 15

        # If conclusion is vague but actions are specific (or vice versa)
        vague_patterns = ["issue analyzed", "appropriate response", "can be formulated"]
        is_vague = any(p in conclusion_lower for p in vague_patterns)
        specific_actions = ["process_refund", "cancel_order", "modify_account"]
        has_specific = any(
            isinstance(a, dict) and a.get("action_type") in specific_actions
            for a in action_plans
        )
        if is_vague and has_specific:
            issues.append({
                "type": "vague_conclusion_specific_action",
                "severity": "medium",
                "description": "Vague reasoning conclusion but specific actions planned — reasoning may not justify actions",
                "adjustment": -5,
            })
            quality_adjustment -= 5

    # ─── Check 3: Confidence calibration ──────────────────────────
    # Is the quality score warranted given the evidence?
    evidence_strength = 0
    if isinstance(evidence_chain, list):
        for entry in evidence_chain:
            if isinstance(entry, dict):
                conf = entry.get("confidence", 0)
                if conf > 0.7:
                    evidence_strength += 1

    if quality_score >= 85 and evidence_strength < 2:
        issues.append({
            "type": "overconfident_score",
            "severity": "medium",
            "description": f"Quality score {quality_score:.0f} seems high given only {evidence_strength} strong evidence entries",
            "adjustment": -8,
        })
        quality_adjustment -= 8

    # ─── Check 4: Pipeline coverage ───────────────────────────────
    # Did all the important pipeline stages produce output?
    active_frameworks = state.get("active_frameworks", [])

    # Check if key nodes ran
    expected_for_complex = ["reasoning", "reverse", "red_team", "debate"]
    complexity = state.get("complexity", "simple")

    if complexity in ("complex", "critical"):
        missing = []
        for expected in expected_for_complex:
            found = any(expected in fw for fw in active_frameworks)
            if not found:
                missing.append(expected)

        if missing:
            issues.append({
                "type": "incomplete_pipeline",
                "severity": "medium",
                "description": f"Complex ticket but missing pipeline stages: {missing}",
                "adjustment": -5,
            })
            quality_adjustment -= 5

    # ─── Check 5: Circular reasoning detection ────────────────────
    # Did nodes just validate each other without independent evidence?
    if isinstance(evidence_chain, list) and len(evidence_chain) >= 3:
        # Check if multiple evidence entries say the same thing
        claim_texts = []
        for entry in evidence_chain:
            if isinstance(entry, dict):
                claim = entry.get("claim", "").lower()
                # Extract key words (skip common words)
                words = set(claim.split()) - {"the", "a", "is", "for", "and", "of", "to", "in"}
                claim_texts.append(words)

        # If first and last claims are nearly identical, it's circular
        if claim_texts and len(claim_texts) >= 2:
            overlap = claim_texts[0] & claim_texts[-1]
            if len(overlap) > len(claim_texts[0]) * 0.7 and len(claim_texts[0]) > 3:
                issues.append({
                    "type": "circular_reasoning_suspected",
                    "severity": "medium",
                    "description": "First and last evidence entries are nearly identical — possible circular reasoning",
                    "adjustment": -5,
                })
                quality_adjustment -= 5

    # ─── Check 6: Situation model alignment ───────────────────────
    # Does the final response address what the situation model identified?
    if isinstance(situation_model, dict) and situation_model:
        risks = situation_model.get("risks", [])
        high_risks = [r for r in risks if isinstance(r, dict) and r.get("severity") == "high"]

        if high_risks and isinstance(final_response, str):
            # Check if the response addresses the high-risk areas
            response_lower = final_response.lower()
            addressed_risks = 0
            for risk in high_risks:
                desc = risk.get("description", "").lower()
                # Extract key words from risk description
                key_words = [w for w in desc.split() if len(w) > 4 and w not in
                            {"customer", "might", "could", "would", "should"}]
                if any(kw in response_lower for kw in key_words):
                    addressed_risks += 1

            if addressed_risks < len(high_risks) and len(high_risks) > 0:
                issues.append({
                    "type": "unaddressed_risks",
                    "severity": "medium",
                    "description": f"{len(high_risks) - addressed_risks} high-risk item(s) not addressed in response",
                    "adjustment": -5,
                })
                quality_adjustment -= 5

    # ─── Check 7: Policy compliance alignment ─────────────────────
    if isinstance(policy_report, dict) and policy_report.get("has_hard_violations"):
        issues.append({
            "type": "policy_violations_unresolved",
            "severity": "high",
            "description": "Hard policy violations detected but not resolved",
            "adjustment": -15,
        })
        quality_adjustment -= 15

    # Determine overall meta-reasoning verdict
    if quality_adjustment <= -20:
        verdict = "poor"
    elif quality_adjustment <= -10:
        verdict = "concerning"
    elif quality_adjustment <= -5:
        verdict = "acceptable"
    else:
        verdict = "sound"

    return {
        "issues": issues,
        "quality_adjustment": quality_adjustment,
        "verdict": verdict,
        "checks_performed": 7,
        "pipeline_coverage": len(active_frameworks) if isinstance(active_frameworks, list) else 0,
    }


async def _meta_reason_llm(state: dict[str, Any], rule_result: dict[str, Any]) -> dict[str, Any]:
    """Enhance meta-reasoning with LLM analysis (async).

    The LLM can spot structural issues that rules miss, such as
    subtle logical gaps or overconfident conclusions.
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")
    reasoning_conclusion = state.get("reasoning_conclusion", "")
    final_response = state.get("final_response", "")
    variant = state.get("variant", "parwa")

    # Build summary for LLM
    evidence_chain = state.get("evidence_chain", [])
    evidence_summary = ""
    if isinstance(evidence_chain, list):
        parts = []
        for i, entry in enumerate(evidence_chain[:8], 1):
            if isinstance(entry, dict):
                parts.append(
                    f"  {i}. {entry.get('claim', '')[:80]} (conf: {entry.get('confidence', 0):.2f})"
                )
        evidence_summary = "\n".join(parts) if parts else "No evidence entries"

    rule_issues_text = "; ".join(
        i.get("description", "") for i in rule_result.get("issues", [])[:3]
    )

    system_instructions = (
        "You are a META-REASONER for an AI customer support pipeline.\n"
        "Your job: Evaluate whether the pipeline's REASONING STRUCTURE is sound.\n"
        "Don't evaluate the content — evaluate whether the reasoning PROCESS is reliable.\n\n"
        f"Intent: {intent}\n"
        f"Conclusion: {reasoning_conclusion[:200]}\n"
        f"Response: {final_response[:200]}\n"
        f"Evidence chain:\n{evidence_summary}\n"
        f"Rule-based issues found: {rule_issues_text or 'None'}\n\n"
        "Check for:\n"
        "- Is the conclusion actually supported by the evidence?\n"
        "- Are there logical gaps in the reasoning chain?\n"
        "- Is the response addressing the ACTUAL question?\n"
        "- Are there blind spots the pipeline missed?\n\n"
        "Reply in EXACT format:\n"
        "VERDICT: SOUND|ACCEPTABLE|CONCERNING|POOR\n"
        "ISSUE_1: <description or 'none'>\n"
        "ISSUE_2: <description or 'none'>\n"
        "ADJUSTMENT: <-20 to +5>\n"
        "BLIND_SPOT: <something the pipeline likely missed or 'none'>"
    )

    try:
        safe_prompt = build_safe_prompt(system_instructions, "Evaluate the reasoning structure.")
        text = await ainvoke_llm(
            safe_prompt,
            node_name="META_REASONER",
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
            max_tokens=150,
        )

        # Parse LLM response
        llm_verdict = "acceptable"
        llm_adjustment = 0
        llm_issues = []
        blind_spot = ""

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("VERDICT:"):
                v = line.split(":", 1)[1].strip().upper()
                llm_verdict = v.lower() if v in ("SOUND", "ACCEPTABLE", "CONCERNING", "POOR") else "acceptable"
            elif line.startswith("ISSUE_") and ":" in line:
                desc = line.split(":", 1)[1].strip()
                if desc.lower() not in ("none", "n/a"):
                    llm_issues.append({
                        "type": "llm_meta_issue",
                        "severity": "medium",
                        "description": desc,
                        "adjustment": -5,
                    })
            elif line.upper().startswith("ADJUSTMENT:"):
                try:
                    llm_adjustment = int(line.split(":", 1)[1].strip())
                    llm_adjustment = max(-20, min(5, llm_adjustment))
                except ValueError:
                    llm_adjustment = 0
            elif line.upper().startswith("BLIND_SPOT:"):
                bs = line.split(":", 1)[1].strip()
                if bs.lower() not in ("none", "n/a"):
                    blind_spot = bs

        # Merge with rule-based results
        merged_issues = list(rule_result.get("issues", [])) + llm_issues
        merged_adjustment = rule_result.get("quality_adjustment", 0) + llm_adjustment

        # Use the worse verdict
        verdict_order = {"sound": 0, "acceptable": 1, "concerning": 2, "poor": 3}
        rule_verdict = rule_result.get("verdict", "acceptable")
        final_verdict = llm_verdict if verdict_order.get(llm_verdict, 1) > verdict_order.get(rule_verdict, 1) else rule_verdict

        rule_result["issues"] = merged_issues
        rule_result["quality_adjustment"] = merged_adjustment
        rule_result["verdict"] = final_verdict
        rule_result["llm_issues"] = len(llm_issues)
        rule_result["blind_spot"] = blind_spot
        rule_result["llm_enhanced"] = True

    except Exception as exc:
        logger.warning("meta_reasoner: LLM analysis failed (%s), using rule-based only", exc)

    return rule_result


@safe_node("META_REASONER", fallback={
    "meta_reasoning": {"issues": [], "quality_adjustment": 0, "verdict": "acceptable"},
    "active_frameworks": [],
    "evidence_chain": [],
})
async def meta_reasoner(state: dict[str, Any]) -> dict[str, Any]:
    """Reason about the pipeline's own reasoning quality (async).

    P3 NEW NODE: Evaluates the REASONING STRUCTURE of the pipeline,
    not the content. Checks for coherence, calibration, blind spots,
    and structural issues that individual nodes can't see.

    Variant behavior:
      - mini: Rule-based structural check (fast)
      - parwa: Rule-based + LLM analysis (balanced)
      - high: Full meta-reasoning with blind-spot detection (thorough)

    Reads: evidence_chain, quality_score, reasoning_chain, reasoning_conclusion,
           action_plans, final_response, red_team_report, debate_result,
           situation_model, policy_report, active_frameworks, complexity
    Writes: meta_reasoning, active_frameworks (append), evidence_chain (append)
    """
    variant = state.get("variant", "parwa")

    # Guard type
    if not isinstance(variant, str):
        variant = "parwa"

    # Step 1: Rule-based meta-reasoning (all variants)
    result = _meta_reason_rule_based(state)

    # Step 2: LLM enhancement for parwa and high variants
    if variant in ("parwa", "high") and not MOCK_MODE:
        result = await _meta_reason_llm(state, result)

    # Apply quality adjustment if significant
    adjustment = result.get("quality_adjustment", 0)
    if adjustment < 0:
        current_score = state.get("quality_score", 0.0)
        adjusted_score = max(0.0, current_score + adjustment)
        result["original_quality_score"] = current_score
        result["adjusted_quality_score"] = adjusted_score

    # Track frameworks
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    if "meta_reasoner" not in existing:
        new_frameworks.append("meta_reasoner")

    # Build evidence chain entry
    verdict = result.get("verdict", "acceptable")
    issue_count = len(result.get("issues", []))

    new_evidence = [{
        "claim": f"Meta-reasoning: {verdict.upper()} — {issue_count} structural issue(s) found, "
                 f"quality adjustment: {adjustment:+.0f}",
        "sources": [i.get("description", "")[:80] for i in result.get("issues", [])[:3]],
        "confidence": 0.85,
        "technique": "meta_reasoner",
        "category": "meta",
        "node": "META_REASONER",
        "verdict": verdict,
        "quality_adjustment": adjustment,
    }]

    logger.info(
        "meta_reasoner: verdict=%s issues=%d adjustment=%+.0f variant=%s",
        verdict, issue_count, adjustment, variant,
    )

    return {
        "meta_reasoning": result,
        "active_frameworks": new_frameworks,
        "evidence_chain": new_evidence,
    }
