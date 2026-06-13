"""Node: RED_TEAM — Adversarial validator that actively tries to break the reasoning.

P1 NEW NODE: This node acts as a red-team / devil's advocate. It takes the
reasoning conclusion and evidence chain and actively tries to:
  1. Find logical fallacies in the reasoning
  2. Identify missing evidence that would weaken the conclusion
  3. Surface edge cases the reasoning didn't consider
  4. Check for hallucinated claims (claims without evidence backing)
  5. Detect confirmation bias (only supporting evidence considered)

If the red team finds CRITICAL flaws, it can trigger a loop-back to
re-reason. If it finds MINOR flaws, it adds caveats to the evidence chain.

This is fundamentally different from reverse_thinker:
  - Reverse Thinker: "Does the conclusion follow from the evidence?"
  - Red Team: "What could make this conclusion WRONG?"

The Red Team is intentionally adversarial — it WANTS to find problems.
This catches issues that self-validation (reverse_thinker) misses because
self-validation shares the same biases as the original reasoning.

Variant behavior:
  - mini: Red team uses fast rule-based checks only (cheap)
  - parwa: Red team uses LLM-based adversarial attacks (balanced)
  - high: Red team does both rule-based AND LLM-based, with multiple attack vectors
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.red_team")


# ─── Rule-based red team checks (fast, no LLM needed) ───────────────────────

def _red_team_rule_based(
    conclusion: str,
    evidence_chain: list[dict],
    intent: str,
    raw_message: str,
) -> dict[str, Any]:
    """Run adversarial checks using rules. Returns red_team_report.

    These are fast heuristic checks that catch common reasoning flaws
    without needing an LLM call. Used by all variants (mini relies
    exclusively on these).
    """
    vulnerabilities: list[dict[str, Any]] = []
    severity = "none"  # none, low, medium, high, critical

    # Check 1: Unbacked claims — claims with no sources
    unbacked = []
    for entry in evidence_chain:
        if isinstance(entry, dict):
            sources = entry.get("sources", [])
            if not sources or all(not s for s in sources):
                unbacked.append(entry.get("claim", "")[:80])

    if unbacked:
        vuln_severity = "high" if len(unbacked) > 2 else "medium"
        vulnerabilities.append({
            "type": "unbacked_claims",
            "severity": vuln_severity,
            "description": f"Found {len(unbacked)} claims with no supporting evidence",
            "claims": unbacked[:5],
            "recommendation": "These claims may be hallucinated. Loop back for re-reasoning.",
        })

    # Check 2: Low-confidence claims — claims with confidence < 0.5
    low_conf = []
    for entry in evidence_chain:
        if isinstance(entry, dict) and entry.get("confidence", 1.0) < 0.5:
            low_conf.append({
                "claim": entry.get("claim", "")[:80],
                "confidence": entry.get("confidence", 0.0),
            })

    if low_conf:
        vulnerabilities.append({
            "type": "low_confidence_claims",
            "severity": "medium",
            "description": f"Found {len(low_conf)} claims with confidence below 0.5",
            "claims": low_conf,
            "recommendation": "These claims are unreliable. Consider gathering more evidence.",
        })

    # Check 3: Contradictory claims — PASSED + FAILED or ELIGIBLE + NOT_ELIGIBLE
    claims_text = " ".join(
        entry.get("claim", "").lower()
        for entry in evidence_chain
        if isinstance(entry, dict)
    )
    has_positive = any(kw in claims_text for kw in ["passed", "eligible", "confirmed", "approved"])
    has_negative = any(kw in claims_text for kw in ["failed", "insufficient", "denied", "not eligible"])
    if has_positive and has_negative:
        vulnerabilities.append({
            "type": "contradictory_claims",
            "severity": "critical",
            "description": "Evidence chain contains contradictory claims (both positive and negative)",
            "recommendation": "Resolve contradictions before proceeding. This is a critical flaw.",
        })

    # Check 4: Missing evidence for intent — refund_request without refund evidence, etc.
    intent_evidence_map = {
        "refund_request": ["refund", "charge", "payment", "billing", "amount"],
        "cancellation": ["cancel", "subscription", "order", "membership"],
        "billing_issue": ["charge", "billing", "payment", "invoice", "amount"],
        "order_status": ["order", "tracking", "shipping", "delivery"],
        "account_modification": ["account", "update", "change", "modify", "email", "payment"],
    }
    required_keywords = intent_evidence_map.get(intent, [])
    if required_keywords:
        missing = [kw for kw in required_keywords if kw not in claims_text]
        if len(missing) > len(required_keywords) * 0.7:
            vulnerabilities.append({
                "type": "missing_intent_evidence",
                "severity": "medium",
                "description": f"No evidence found for key intent keywords: {missing}",
                "missing_keywords": missing,
                "recommendation": "The conclusion may not address the customer's actual intent.",
            })

    # Check 5: Circular reasoning — conclusion appears in evidence
    conclusion_lower = conclusion.lower().strip()
    if conclusion_lower:
        for entry in evidence_chain:
            if isinstance(entry, dict):
                sources = entry.get("sources", [])
                if any(conclusion_lower[:50] in str(s).lower() for s in sources):
                    vulnerabilities.append({
                        "type": "circular_reasoning",
                        "severity": "low",
                        "description": "Conclusion appears in its own supporting evidence — possible circular reasoning",
                        "recommendation": "Verify that the conclusion is independently supported.",
                    })
                    break

    # Check 6: Vague conclusion — too short or generic
    vague_patterns = [
        "issue analyzed", "appropriate response", "can be formulated",
        "can be processed", "corrective action needed", "situation reviewed",
    ]
    if any(p in conclusion.lower() for p in vague_patterns):
        vulnerabilities.append({
            "type": "vague_conclusion",
            "severity": "medium",
            "description": f"Conclusion is vague/generic: '{conclusion[:100]}'",
            "recommendation": "Loop back for more specific reasoning with concrete details.",
        })

    # Check 7: No integration data — decisions without CRM/account verification
    has_crm_evidence = any(
        isinstance(entry, dict) and entry.get("category") == "knowledge"
        and "crm" in str(entry.get("sources", [])).lower()
        for entry in evidence_chain
    )
    financial_intents = ["refund_request", "billing_issue", "cancellation"]
    if intent in financial_intents and not has_crm_evidence:
        vulnerabilities.append({
            "type": "no_financial_verification",
            "severity": "high",
            "description": f"Financial intent ({intent}) without CRM/account data verification",
            "recommendation": "Verify customer's account/charges before taking financial action.",
        })

    # Determine overall severity
    severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    max_severity = "none"
    for v in vulnerabilities:
        v_sev = v.get("severity", "low")
        if severity_order.get(v_sev, 0) > severity_order.get(max_severity, 0):
            max_severity = v_sev

    return {
        "vulnerabilities": vulnerabilities,
        "vulnerability_count": len(vulnerabilities),
        "severity": max_severity,
        "passed": max_severity not in ("high", "critical"),
        "technique": "rule_based",
    }


async def _red_team_llm(
    conclusion: str,
    evidence_chain: list[dict],
    intent: str,
    raw_message: str,
    *,
    ticket_id: str = "",
    variant: str = "parwa",
) -> dict[str, Any]:
    """Run adversarial checks using LLM. Returns red_team_report.

    The LLM is prompted to actively try to find flaws in the reasoning.
    This catches subtle logical errors and edge cases that rules miss.
    """
    # Build evidence summary for the LLM
    evidence_summary_parts = []
    for i, entry in enumerate(evidence_chain[:10], 1):
        if isinstance(entry, dict):
            claim = entry.get("claim", "")
            conf = entry.get("confidence", 0)
            sources = entry.get("sources", [])
            evidence_summary_parts.append(
                f"  {i}. Claim: {claim[:100]} (confidence: {conf:.2f}, sources: {len(sources)})"
            )

    evidence_summary = "\n".join(evidence_summary_parts) if evidence_summary_parts else "No evidence entries found."

    system_instructions = (
        "You are a RED TEAM adversary for an AI customer support system. "
        "Your job is to actively TRY TO FIND FLAWS in the AI's reasoning.\n\n"
        "Be AGGRESSIVE. Look for:\n"
        "- Logical fallacies (non sequiturs, false cause, hasty generalization)\n"
        "- Missing evidence that would change the conclusion\n"
        "- Edge cases the reasoning didn't consider\n"
        "- Hallucinated claims (claims without evidence backing)\n"
        "- Confirmation bias (only supporting evidence considered)\n"
        "- Overconfident conclusions on weak evidence\n"
        "- Policy violations or unsafe recommendations\n\n"
        f"Customer intent: {intent}\n"
        f"Customer message: {raw_message[:300]}\n\n"
        f"AI CONCLUSION:\n{conclusion}\n\n"
        f"EVIDENCE CHAIN:\n{evidence_summary}\n\n"
        "Reply in this EXACT format:\n"
        "VERDICT: PASS|LOW|MEDIUM|HIGH|CRITICAL\n"
        "FLAWS:\n"
        "- <flaw description 1>\n"
        "- <flaw description 2>\n"
        "RECOMMENDATION: <what to do about it>\n\n"
        "Be HONEST and STRICT. A good red teamer finds real problems."
    )

    prompt = f"Red-team the following AI conclusion and evidence chain."

    try:
        safe_prompt = build_safe_prompt(system_instructions, prompt)
        text = await ainvoke_llm(
            safe_prompt,
            node_name="RED_TEAM",
            ticket_id=ticket_id,
            variant=variant,
            max_tokens=200,
        )

        # Parse the response
        verdict = "medium"  # default if parsing fails
        flaws = []
        recommendation = ""

        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.upper().startswith("VERDICT:"):
                verdict_text = line.split(":", 1)[1].strip().upper()
                verdict_map = {
                    "PASS": "none", "LOW": "low", "MEDIUM": "medium",
                    "HIGH": "high", "CRITICAL": "critical",
                }
                verdict = verdict_map.get(verdict_text, "medium")
            elif line.startswith("- "):
                flaws.append(line[2:].strip())
            elif line.upper().startswith("RECOMMENDATION:"):
                recommendation = line.split(":", 1)[1].strip()

        # Build vulnerabilities from LLM findings
        vulnerabilities = []
        for i, flaw in enumerate(flaws[:5]):
            # Try to categorize the flaw
            flaw_lower = flaw.lower()
            if any(kw in flaw_lower for kw in ["hallucinat", "no evidence", "unbacked", "fabricated"]):
                flaw_type = "llm_hallucination_risk"
                severity = "high"
            elif any(kw in flaw_lower for kw in ["logical", "fallacy", "non sequitur", "contradiction"]):
                flaw_type = "llm_logical_flaw"
                severity = "high"
            elif any(kw in flaw_lower for kw in ["edge case", "missing", "not considered", "overlooked"]):
                flaw_type = "llm_missing_case"
                severity = "medium"
            elif any(kw in flaw_lower for kw in ["bias", "assumption", "overconfident"]):
                flaw_type = "llm_bias"
                severity = "medium"
            else:
                flaw_type = "llm_general_flaw"
                severity = "low"

            vulnerabilities.append({
                "type": flaw_type,
                "severity": severity,
                "description": flaw,
                "recommendation": recommendation if not recommendation else "Review and address this flaw.",
            })

        if not vulnerabilities and verdict not in ("none", "low"):
            vulnerabilities.append({
                "type": "llm_general_concern",
                "severity": verdict,
                "description": f"LLM red team found concerns but no specific flaws listed",
                "recommendation": recommendation or "Review the reasoning chain.",
            })

        return {
            "vulnerabilities": vulnerabilities,
            "vulnerability_count": len(vulnerabilities),
            "severity": verdict,
            "passed": verdict not in ("high", "critical"),
            "technique": "llm_red_team",
            "recommendation": recommendation,
        }

    except Exception as exc:
        logger.warning("red_team: LLM attack failed (%s), using rule-based only", exc)
        return {
            "vulnerabilities": [],
            "vulnerability_count": 0,
            "severity": "none",
            "passed": True,
            "technique": "llm_failed",
            "error": str(exc),
        }


@safe_node("RED_TEAM", fallback={
    "red_team_report": {"vulnerabilities": [], "vulnerability_count": 0, "severity": "none", "passed": True},
    "active_frameworks": [],
    "should_loop_back": False,
    "evidence_chain": [],
})
async def red_team(state: dict[str, Any]) -> dict[str, Any]:
    """Adversarial validation — actively tries to break the reasoning (async).

    P1 NEW NODE: Acts as a red-team adversary. Unlike reverse_thinker
    (which validates forward), this node ATTACKS the reasoning to find
    flaws that self-validation misses.

    Variant behavior:
      - mini: Rule-based checks only (fast, cheap)
      - parwa: Rule-based + LLM adversarial attack (balanced)
      - high: Rule-based + LLM with multiple attack vectors (thorough)

    Reads: reasoning_conclusion, evidence_chain, intent, raw_message, variant
    Writes: red_team_report, active_frameworks (append), should_loop_back, evidence_chain (append)
    """
    conclusion = state.get("reasoning_conclusion", "")
    evidence_chain = state.get("evidence_chain", [])
    intent = state.get("intent", "general_inquiry")
    raw_message = state.get("raw_message", "")
    variant = state.get("variant", "parwa")

    # Guard types
    if not isinstance(conclusion, str):
        conclusion = str(conclusion) if conclusion else ""
    if not isinstance(evidence_chain, list):
        evidence_chain = []
    if not isinstance(intent, str):
        intent = "general_inquiry"
    if not isinstance(variant, str):
        variant = "parwa"

    # Step 1: Always run rule-based checks (all variants)
    rule_report = _red_team_rule_based(conclusion, evidence_chain, intent, raw_message)

    # Step 2: Run LLM red-team for parwa and high variants
    llm_report = None
    if variant in ("parwa", "high") and not MOCK_MODE:
        llm_report = await _red_team_llm(
            conclusion, evidence_chain, intent, raw_message,
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
        )

    # Step 3: Merge reports — take the most severe finding
    all_vulnerabilities = list(rule_report.get("vulnerabilities", []))
    if llm_report:
        all_vulnerabilities.extend(llm_report.get("vulnerabilities", []))

    # Determine overall severity (worst wins)
    severity_order = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    max_severity = rule_report.get("severity", "none")
    if llm_report:
        llm_sev = llm_report.get("severity", "none")
        if severity_order.get(llm_sev, 0) > severity_order.get(max_severity, 0):
            max_severity = llm_sev

    # Build final report
    final_report = {
        "vulnerabilities": all_vulnerabilities,
        "vulnerability_count": len(all_vulnerabilities),
        "severity": max_severity,
        "passed": max_severity not in ("high", "critical"),
        "rule_based_vulnerabilities": rule_report.get("vulnerability_count", 0),
        "llm_vulnerabilities": len(llm_report.get("vulnerabilities", [])) if llm_report else 0,
        "technique": "rule_based" if not llm_report else "rule_based+llm",
    }

    # Should loop back? Only if critical/high severity AND we have loops left
    loop_count = state.get("loop_count", 0)
    max_loops = state.get("max_loops", 2)
    should_loop = max_severity in ("high", "critical") and loop_count < max_loops

    # Track frameworks
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    if "red_team" not in existing:
        new_frameworks.append("red_team")

    # Build evidence chain entry for red team findings
    new_evidence = [{
        "claim": f"Red team assessment: {max_severity.upper()} — "
                 f"{'PASSED' if final_report['passed'] else 'FAILED'} "
                 f"({len(all_vulnerabilities)} vulnerabilities found)",
        "sources": [v.get("description", "")[:80] for v in all_vulnerabilities[:3]],
        "confidence": 0.9 if max_severity in ("critical", "high") else 0.7,
        "technique": "red_team",
        "category": "adversarial",
        "node": "RED_TEAM",
        "severity": max_severity,
        "passed": final_report["passed"],
    }]

    logger.info(
        "red_team: severity=%s passed=%s vulnerabilities=%d should_loop=%s variant=%s",
        max_severity, final_report["passed"], len(all_vulnerabilities), should_loop, variant,
    )

    return {
        "red_team_report": final_report,
        "active_frameworks": new_frameworks,
        "should_loop_back": should_loop,
        "evidence_chain": new_evidence,
    }
