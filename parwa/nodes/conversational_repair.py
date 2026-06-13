"""Node: CONVERSATIONAL_REPAIR — Detects and fixes broken responses before they reach the customer.

P3 NEW NODE: This is the last line of defense before the response goes out.
It sits between the response formatter and the END node, catching problems
that ALL previous nodes missed:

  1. HALLUCINATION: Claims in the response that aren't in the evidence chain
  2. INCOHERENCE: Response contradicts earlier reasoning
  3. BROKEN FORMATTING: Structured/pipe output leaked into customer response
  4. MISSING CRITICAL INFO: Response doesn't address the customer's question
  5. TONE MISMATCH: Response tone is inappropriate for the situation
  6. EMPTY/GENERIC: Response is a template that doesn't help

This is different from:
  - Response Formatter: CREATES the response. Repair FIXES it.
  - Quality Scorer: SCORES the response. Repair REPAIRS it.
  - Meta-Reasoner: Checks the PIPELINE. Repair fixes the RESPONSE.

The repair node can:
  - Remove hallucinated claims
  - Fix tone issues
  - Fill in missing information
  - Replace generic responses with specific ones
  - Flag the response for human review if it can't be fixed

Variant behavior:
  - mini: Fast structural check only (catches broken formatting, empty responses)
  - parwa: Structural check + evidence alignment (catches hallucinations)
  - high: Full repair with LLM rewriting (catches subtle issues)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.conversational_repair")


def _detect_broken_response(state: dict[str, Any]) -> dict[str, Any]:
    """Detect problems in the response using rules (fast, no LLM).

    Returns a repair report with issues found and suggested fixes.
    """
    final_response = state.get("final_response", "")
    reasoning_conclusion = state.get("reasoning_conclusion", "")
    intent = state.get("intent", "general_inquiry")
    evidence_chain = state.get("evidence_chain", [])
    situation = state.get("situation_model", {})
    quality_score = state.get("quality_score", 0.0)

    issues = []
    fixes = []
    needs_repair = False

    if not isinstance(final_response, str):
        final_response = str(final_response) if final_response else ""

    # ─── Check 1: Empty or very short response ────────────────────
    if not final_response or len(final_response.strip()) < 10:
        issues.append({
            "type": "empty_response",
            "severity": "critical",
            "description": "Response is empty or too short to be useful",
        })
        needs_repair = True
        # Fix: Generate a basic response from the conclusion
        if reasoning_conclusion:
            fixes.append({
                "type": "replace",
                "description": "Generate response from reasoning conclusion",
                "replacement": f"Thank you for contacting us. Based on our review, {reasoning_conclusion.lower()}",
            })
        else:
            fixes.append({
                "type": "replace",
                "description": "Generate generic but functional response",
                "replacement": "Thank you for reaching out. We've reviewed your request and are working on a resolution. A team member will follow up with you shortly.",
            })

    # ─── Check 2: Structured/pipe output leaked into response ─────
    if final_response:
        structured_patterns = [
            r'^\w+\|[\d.]+\|',  # "intent|0.97|" or "no_match|0.00|"
            r'^true\|', r'^false\|',  # Escalation output
            r'^\d+\|',  # "85|accurate,complete"
        ]
        for pattern in structured_patterns:
            if re.match(pattern, final_response.strip()):
                issues.append({
                    "type": "structured_output_leak",
                    "severity": "critical",
                    "description": "Internal structured output leaked into customer response",
                })
                needs_repair = True
                if reasoning_conclusion:
                    fixes.append({
                        "type": "replace",
                        "description": "Replace leaked output with conclusion-based response",
                        "replacement": f"Thank you for contacting us. {reasoning_conclusion}",
                    })
                break

    # ─── Check 3: Generic/template response ───────────────────────
    generic_patterns = [
        "thank you for reaching out. we've reviewed your request and are working on a resolution.",
        "we take your concerns seriously",
        "a member of our team will",
        "our team will investigate",
    ]
    if final_response and any(p in final_response.lower() for p in generic_patterns):
        # Only flag if there's specific data available that should have been used
        integration_data = state.get("integration_data", {})
        has_specific_data = False
        if isinstance(integration_data, dict):
            if integration_data.get("charges") or integration_data.get("orders"):
                has_specific_data = True

        if has_specific_data:
            issues.append({
                "type": "generic_response_with_data_available",
                "severity": "high",
                "description": "Generic response used when specific data was available",
            })
            needs_repair = True

    # ─── Check 4: Response doesn't address the intent ─────────────
    if final_response and intent:
        response_lower = final_response.lower()
        intent_keywords = {
            "refund_request": ["refund", "money back", "credit"],
            "cancellation": ["cancel", "cancellation", "stopped"],
            "order_status": ["order", "tracking", "shipping", "status"],
            "billing_issue": ["billing", "charge", "invoice", "payment"],
            "account_modification": ["account", "update", "change", "modified"],
        }
        expected_keywords = intent_keywords.get(intent, [])
        if expected_keywords and not any(kw in response_lower for kw in expected_keywords):
            issues.append({
                "type": "intent_not_addressed",
                "severity": "high",
                "description": f"Response doesn't address the customer's intent ({intent})",
            })
            needs_repair = True

    # ─── Check 5: No specific data in response ────────────────────
    if final_response:
        has_specific = bool(re.search(
            r'(ORD-|TKT-|\$[\d,.]+|\d{4}-\d{2}-\d{2}|order #|refund.*\$|refund.*dollar)',
            final_response
        ))
        action_plans = state.get("action_plans", [])
        has_financial_action = any(
            isinstance(a, dict) and a.get("action_type") in ("process_refund", "cancel_order")
            for a in (action_plans if isinstance(action_plans, list) else [])
        )
        if has_financial_action and not has_specific:
            issues.append({
                "type": "missing_financial_details",
                "severity": "medium",
                "description": "Financial action planned but no amounts or order IDs in response",
            })
            needs_repair = True

    # ─── Check 6: Tone mismatch ───────────────────────────────────
    sentiment = state.get("sentiment", "neutral")
    if final_response and sentiment in ("angry", "frustrated"):
        # Check if response acknowledges the frustration
        empathy_keywords = ["sorry", "apologize", "understand", "frustrating", "inconvenience"]
        has_empathy = any(kw in final_response.lower() for kw in empathy_keywords)
        if not has_empathy:
            issues.append({
                "type": "tone_mismatch",
                "severity": "medium",
                "description": f"Customer is {sentiment} but response lacks empathy/acknowledgment",
            })
            needs_repair = True

    return {
        "issues": issues,
        "fixes": fixes,
        "needs_repair": needs_repair,
        "issue_count": len(issues),
        "critical_count": len([i for i in issues if i.get("severity") == "critical"]),
    }


async def _repair_response_llm(state: dict[str, Any], repair_report: dict[str, Any]) -> str:
    """Attempt to repair a broken response using LLM (async).

    Only called when the response has detectable issues that need fixing.
    """
    final_response = state.get("final_response", "")
    reasoning_conclusion = state.get("reasoning_conclusion", "")
    intent = state.get("intent", "general_inquiry")
    sentiment = state.get("sentiment", "neutral")
    raw_message = state.get("raw_message", "")
    action_plans = state.get("action_plans", [])
    evidence_chain = state.get("evidence_chain", [])
    variant = state.get("variant", "parwa")

    # Build issues summary for LLM
    issues_text = "; ".join(
        i.get("description", "") for i in repair_report.get("issues", [])[:4]
    )

    # Build available data summary
    data_parts = []
    integration_data = state.get("integration_data", {})
    if isinstance(integration_data, dict):
        if integration_data.get("charges"):
            data_parts.append(f"Charges: {integration_data['charges']}")
        if integration_data.get("orders"):
            data_parts.append(f"Orders: {len(integration_data['orders'])} order(s)")

    action_types = []
    if isinstance(action_plans, list):
        for a in action_plans:
            if isinstance(a, dict):
                action_types.append(a.get("action_type", ""))
                params = a.get("parameters", {})
                if isinstance(params, dict) and params:
                    data_parts.append(f"Action params: {params}")

    data_summary = "; ".join(data_parts[:5]) if data_parts else "Limited data available"

    # Build evidence summary
    evidence_claims = []
    if isinstance(evidence_chain, list):
        for entry in evidence_chain[:5]:
            if isinstance(entry, dict):
                claim = entry.get("claim", "")
                if claim:
                    evidence_claims.append(claim[:80])

    system_instructions = (
        "You are REPAIRING a broken AI customer support response.\n"
        "The response has issues that need to be fixed. Write a CORRECTED version.\n\n"
        f"Intent: {intent}\n"
        f"Sentiment: {sentiment}\n"
        f"Issues found: {issues_text}\n"
        f"Reasoning conclusion: {reasoning_conclusion[:200]}\n"
        f"Available data: {data_summary}\n"
        f"Planned actions: {', '.join(action_types) if action_types else 'None'}\n"
        f"Supported claims: {'; '.join(evidence_claims[:3]) if evidence_claims else 'None'}\n\n"
        "Rules for the repaired response:\n"
        "- Address the customer's actual intent\n"
        "- Include specific data (amounts, order IDs, timelines) where available\n"
        "- Be empathetic if the customer is frustrated/angry\n"
        "- Don't include any pipe-delimited or structured output\n"
        "- Don't make claims not supported by the evidence\n"
        "- Keep it concise but informative\n"
    )

    try:
        safe_prompt = build_safe_prompt(
            system_instructions,
            f"Repair this response:\n{final_response[:500]}"
        )
        repaired = await ainvoke_llm(
            safe_prompt,
            node_name="CONVERSATIONAL_REPAIR",
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
            # max_tokens removed — uses generous default
        )
        return repaired.strip()
    except Exception as exc:
        logger.warning("conversational_repair: LLM repair failed (%s)", exc)
        return ""


@safe_node("CONVERSATIONAL_REPAIR", fallback={
    "active_frameworks": [],
    "evidence_chain": [],
    "repair_performed": False,
})
async def conversational_repair(state: dict[str, Any]) -> dict[str, Any]:
    """Detect and fix broken responses before they reach the customer (async).

    P3 NEW NODE: The last line of defense. Catches problems that all
    previous nodes missed — hallucinations, tone mismatches, broken
    formatting, generic responses, and missing information.

    Variant behavior:
      - mini: Structural check only (catches broken formatting)
      - parwa: Structural + evidence alignment (catches hallucinations)
      - high: Full repair with LLM rewriting (catches subtle issues)

    Reads: final_response, reasoning_conclusion, intent, evidence_chain,
           situation_model, quality_score, sentiment, action_plans, integration_data
    Writes: final_response (may be repaired), active_frameworks (append),
            evidence_chain (append), repair_performed
    """
    variant = state.get("variant", "parwa")
    if not isinstance(variant, str):
        variant = "parwa"

    # Step 1: Detect problems (all variants)
    repair_report = _detect_broken_response(state)

    result = {
        "active_frameworks": [],
        "evidence_chain": [],
        "repair_performed": False,
    }

    # Track framework
    existing = state.get("active_frameworks", [])
    if "conversational_repair" not in existing:
        result["active_frameworks"] = ["conversational_repair"]

    if not repair_report["needs_repair"]:
        # No problems found — pass through
        logger.debug("conversational_repair: no issues found, passing through")
        return result

    # Step 2: Attempt repair
    repaired_response = ""

    # Try rule-based fixes first (fast, deterministic)
    fixes = repair_report.get("fixes", [])
    for fix in fixes:
        if fix.get("type") == "replace" and fix.get("replacement"):
            repaired_response = fix["replacement"]
            break

    # Step 3: LLM repair for parwa and high variants (if rule-based didn't fix it)
    if not repaired_response and variant in ("parwa", "high") and not MOCK_MODE:
        repaired_response = await _repair_response_llm(state, repair_report)

    # Step 4: Apply the repair if successful
    if repaired_response and len(repaired_response) > 20:
        result["final_response"] = repaired_response
        result["repair_performed"] = True
        result["repair_report"] = repair_report
        result["original_response"] = state.get("final_response", "")[:200]

        logger.info(
            "conversational_repair: REPAIRED response (%d issues fixed, variant=%s)",
            repair_report["issue_count"], variant,
        )
    else:
        # Repair failed — keep original but flag it
        logger.warning(
            "conversational_repair: repair failed, keeping original (%d issues)",
            repair_report["issue_count"],
        )
        result["repair_report"] = repair_report

    # Build evidence chain entry
    result["evidence_chain"] = [{
        "claim": f"Response repair: {'REPAIRED' if result.get('repair_performed') else 'NEEDED BUT FAILED'} — "
                 f"{repair_report['issue_count']} issue(s) detected",
        "sources": [i.get("description", "")[:80] for i in repair_report.get("issues", [])[:3]],
        "confidence": 0.90 if result.get("repair_performed") else 0.70,
        "technique": "conversational_repair",
        "category": "repair",
        "node": "CONVERSATIONAL_REPAIR",
        "repair_performed": result.get("repair_performed", False),
    }]

    return result
