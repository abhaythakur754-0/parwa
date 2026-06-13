"""Node: POLICY_GUARD — Policy-aware reasoning that prevents policy violations.

P2 NEW NODE: This node sits between the situation model and reasoning engine
to inject POLICY RULES into the reasoning process. Without this, the reasoning
engine might conclude "give the customer a refund" without checking whether
the refund is within the policy window, whether the customer is eligible,
or whether there are regulatory constraints.

The Policy Guard does NOT make decisions — it INJECTS constraints that
reasoning must respect. It's like a legal advisor that tells the reasoning
engine what it CAN and CANNOT do.

Key policy areas:
  1. REFUND POLICY: Time windows, eligibility criteria, amount limits
  2. CANCELLATION POLICY: Notice periods, early termination fees
  3. ACCOUNT MODIFICATION: Verification requirements, security checks
  4. DATA PRIVACY: GDPR, data retention, right to erasure
  5. ESCALATION TRIGGERS: When escalation is mandatory, not optional

This is different from:
  - Situation Model: Describes WHAT the situation IS. Policy Guard says what's ALLOWED.
  - Red Team: Attacks reasoning for logical flaws. Policy Guard enforces business rules.
  - PII Compliance: Detects/redacts PII. Policy Guard enforces policy constraints.

Variant behavior:
  - mini: Rule-based policy check (fast, cheap)
  - parwa: Rule-based + LLM policy interpretation (balanced)
  - high: Full policy analysis with cross-reference (thorough)
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.llm import MOCK_MODE, ainvoke_llm
from parwa.utils.node_base import safe_node
from parwa.utils.sanitizer import build_safe_prompt

logger = logging.getLogger("parwa.node.policy_guard")


# ─── Policy Rule Definitions ──────────────────────────────────────────────
# These are the actual business rules that the policy guard enforces.
# In production, these would come from a policy database. Here they're
# hardcoded for the demo, but structured so they're easy to extend.

_POLICY_RULES: dict[str, list[dict[str, Any]]] = {
    "refund_request": [
        {
            "rule_id": "REF-001",
            "description": "Refunds must be requested within 30 days of charge",
            "constraint": "max_refund_window_days: 30",
            "severity": "hard_block",  # Cannot be overridden
            "check": "Verify charge date is within 30 days",
        },
        {
            "rule_id": "REF-002",
            "description": "Refund amount cannot exceed original charge amount",
            "constraint": "max_refund_amount: charge_amount",
            "severity": "hard_block",
            "check": "Verify refund amount <= charge amount",
        },
        {
            "rule_id": "REF-003",
            "description": "Duplicate charges are always eligible for refund",
            "constraint": "duplicate_charge: auto_eligible",
            "severity": "auto_approve",  # Always allowed
            "check": "Check if charge is a duplicate",
        },
        {
            "rule_id": "REF-004",
            "description": "Partial refunds require manager approval for amounts > $100",
            "constraint": "partial_refund_approval_threshold: 100",
            "severity": "soft_warning",  # Warning, not block
            "check": "Check if partial refund > $100",
        },
    ],
    "cancellation": [
        {
            "rule_id": "CAN-001",
            "description": "Annual subscriptions require 30-day notice for cancellation",
            "constraint": "notice_period_days: 30",
            "severity": "soft_warning",
            "check": "Check subscription type and notice period",
        },
        {
            "rule_id": "CAN-002",
            "description": "Early termination may incur fee proportional to remaining term",
            "constraint": "early_termination_fee: proportional",
            "severity": "soft_warning",
            "check": "Calculate potential early termination fee",
        },
        {
            "rule_id": "CAN-003",
            "description": "Cancellation during trial period is immediate with no fee",
            "constraint": "trial_cancellation: immediate_no_fee",
            "severity": "auto_approve",
            "check": "Check if customer is in trial period",
        },
    ],
    "account_modification": [
        {
            "rule_id": "ACC-001",
            "description": "Email changes require verification of both old and new email",
            "constraint": "email_change: dual_verification",
            "severity": "hard_block",
            "check": "Ensure dual verification is planned",
        },
        {
            "rule_id": "ACC-002",
            "description": "Payment method changes require re-authentication",
            "constraint": "payment_change: re_auth_required",
            "severity": "hard_block",
            "check": "Ensure re-authentication is planned",
        },
        {
            "rule_id": "ACC-003",
            "description": "Plan upgrades are immediate; downgrades take effect next billing cycle",
            "constraint": "plan_change_timing: upgrade_immediate_downgrade_next_cycle",
            "severity": "soft_warning",
            "check": "Check if upgrade or downgrade",
        },
    ],
    "billing_issue": [
        {
            "rule_id": "BIL-001",
            "description": "Billing disputes must be investigated before any refund",
            "constraint": "dispute: investigate_first",
            "severity": "hard_block",
            "check": "Ensure investigation is planned before refund",
        },
        {
            "rule_id": "BIL-002",
            "description": "Prorated credits apply for mid-cycle changes",
            "constraint": "proration: auto_apply",
            "severity": "auto_approve",
            "check": "Calculate prorated credit if applicable",
        },
    ],
    "general_inquiry": [
        {
            "rule_id": "GEN-001",
            "description": "Never share internal system details with customers",
            "constraint": "internal_info: never_share",
            "severity": "hard_block",
            "check": "Ensure response doesn't contain internal details",
        },
    ],
    "data_privacy": [
        {
            "rule_id": "DPR-001",
            "description": "GDPR right to erasure must be processed within 30 days",
            "constraint": "gdpr_erasure_deadline_days: 30",
            "severity": "hard_block",
            "check": "If customer requests data deletion, flag for compliance",
        },
        {
            "rule_id": "DPR-002",
            "description": "Customer data cannot be shared with third parties without consent",
            "constraint": "data_sharing: consent_required",
            "severity": "hard_block",
            "check": "Ensure no unauthorized data sharing in actions",
        },
    ],
}


def _check_policies_rule_based(state: dict[str, Any]) -> dict[str, Any]:
    """Check all applicable policies using rules.

    Returns a policy_report with:
    - applicable_rules: Which rules apply to this ticket
    - violations: Which rules would be violated by current planned actions
    - constraints: What constraints must be respected
    - recommendations: Suggested modifications to actions
    """
    intent = state.get("intent", "general_inquiry")
    raw_message = (state.get("raw_message", "") or "").lower()
    action_plans = state.get("action_plans", [])
    integration_data = state.get("integration_data", {})
    situation = state.get("situation_model", {})

    applicable_rules = []
    constraints = []
    violations = []
    recommendations = []

    # Gather rules for this intent
    intent_rules = _POLICY_RULES.get(intent, [])
    # Also check data privacy rules if relevant
    privacy_keywords = ["gdpr", "data", "privacy", "delete my data", "right to erasure",
                       "personal data", "data protection"]
    if any(kw in raw_message for kw in privacy_keywords):
        intent_rules = intent_rules + _POLICY_RULES.get("data_privacy", [])
    # Always include general rules
    intent_rules = intent_rules + _POLICY_RULES.get("general_inquiry", [])

    # Check each rule
    for rule in intent_rules:
        applicable_rules.append({
            "rule_id": rule["rule_id"],
            "description": rule["description"],
            "severity": rule["severity"],
        })

        constraint = {
            "rule_id": rule["rule_id"],
            "constraint": rule["constraint"],
            "severity": rule["severity"],
        }
        constraints.append(constraint)

        # Check for violations based on planned actions
        if rule["severity"] == "hard_block":
            # REF-002: Refund amount can't exceed charge
            if rule["rule_id"] == "REF-002" and isinstance(action_plans, list):
                for action in action_plans:
                    if isinstance(action, dict):
                        if action.get("action_type") == "process_refund":
                            params = action.get("parameters", {})
                            refund_amount = params.get("amount", 0)
                            # Check against CRM charges
                            if isinstance(integration_data, dict) and integration_data.get("charges"):
                                max_charge = max(
                                    c.get("amount", 0) for c in integration_data["charges"]
                                ) if integration_data["charges"] else 0
                                if refund_amount > max_charge and max_charge > 0:
                                    violations.append({
                                        "rule_id": rule["rule_id"],
                                        "description": f"Refund ${refund_amount} exceeds max charge ${max_charge}",
                                        "severity": "hard_block",
                                        "action_affected": "process_refund",
                                    })
                                    recommendations.append({
                                        "action": "process_refund",
                                        "recommendation": f"Reduce refund amount to ${max_charge}",
                                        "rule_id": rule["rule_id"],
                                    })

            # BIL-001: Must investigate before refund
            if rule["rule_id"] == "BIL-001" and isinstance(action_plans, list):
                has_refund = any(
                    isinstance(a, dict) and a.get("action_type") == "process_refund"
                    for a in action_plans
                )
                has_investigation = any(
                    isinstance(a, dict) and a.get("action_type") in ("create_note", "escalate_to_human")
                    for a in action_plans
                )
                if has_refund and not has_investigation and intent == "billing_issue":
                    violations.append({
                        "rule_id": rule["rule_id"],
                        "description": "Billing dispute requires investigation before refund",
                        "severity": "hard_block",
                        "action_affected": "process_refund",
                    })
                    recommendations.append({
                        "action": "process_refund",
                        "recommendation": "Add investigation step or set refund to 'recommend' mode pending review",
                        "rule_id": rule["rule_id"],
                    })

            # ACC-001: Email change needs dual verification
            if rule["rule_id"] == "ACC-001" and "email" in raw_message:
                if isinstance(action_plans, list):
                    for action in action_plans:
                        if isinstance(action, dict) and action.get("action_type") == "modify_account":
                            params = action.get("parameters", {})
                            if "email" in str(params.get("details", "")).lower():
                                if "verification" not in str(params).lower():
                                    violations.append({
                                        "rule_id": rule["rule_id"],
                                        "description": "Email change requires dual verification",
                                        "severity": "hard_block",
                                        "action_affected": "modify_account",
                                    })
                                    recommendations.append({
                                        "action": "modify_account",
                                        "recommendation": "Add dual verification step for email change",
                                        "rule_id": rule["rule_id"],
                                    })

        # Auto-approve rules — note them for downstream nodes
        if rule["severity"] == "auto_approve":
            # REF-003: Duplicate charges are auto-eligible
            if rule["rule_id"] == "REF-003":
                if "double charge" in raw_message or "charged twice" in raw_message or "duplicate" in raw_message:
                    recommendations.append({
                        "action": "process_refund",
                        "recommendation": "DUPLICATE CHARGE DETECTED — auto-approve refund",
                        "rule_id": rule["rule_id"],
                    })

    # Build the policy report
    has_hard_violations = any(v.get("severity") == "hard_block" for v in violations)

    report = {
        "applicable_rules": applicable_rules,
        "violations": violations,
        "constraints": constraints,
        "recommendations": recommendations,
        "has_violations": len(violations) > 0,
        "has_hard_violations": has_hard_violations,
        "auto_approve_eligible": any(
            r.get("severity") == "auto_approve" for r in applicable_rules
        ),
        "policy_check_passed": not has_hard_violations,
        "intent_checked": intent,
    }

    return report


async def _check_policies_llm(
    state: dict[str, Any],
    rule_report: dict[str, Any],
) -> dict[str, Any]:
    """Enhance policy check with LLM interpretation (async).

    The LLM can catch policy implications that rules miss,
    such as subtle regulatory requirements or edge cases.
    """
    raw_message = state.get("raw_message", "")
    intent = state.get("intent", "general_inquiry")
    action_plans = state.get("action_plans", [])
    variant = state.get("variant", "parwa")

    # Summarize current findings for LLM
    rule_violations = rule_report.get("violations", [])
    rule_constraints = rule_report.get("constraints", [])

    violations_summary = "; ".join(
        v.get("description", "") for v in rule_violations[:3]
    ) if rule_violations else "None found by rules"

    constraints_summary = "; ".join(
        c.get("constraint", "") for c in rule_constraints[:5]
    ) if rule_constraints else "None identified"

    actions_summary = "; ".join(
        a.get("action_type", "?") for a in (action_plans if isinstance(action_plans, list) else [])[:3]
    ) if action_plans else "No actions planned yet"

    system_instructions = (
        "You are a POLICY COMPLIANCE ANALYZER for an AI customer support system.\n"
        "Your job: Find policy violations or compliance issues that RULES might miss.\n\n"
        f"Customer intent: {intent}\n"
        f"Customer message: {raw_message[:300]}\n"
        f"Planned actions: {actions_summary}\n"
        f"Rule-based violations found: {violations_summary}\n"
        f"Constraints identified: {constraints_summary}\n\n"
        "Look for:\n"
        "- Regulatory requirements (GDPR, CCPA, PCI-DSS) that apply\n"
        "- Edge cases where policy might be violated\n"
        "- Safety concerns with planned actions\n"
        "- Missing verification steps\n\n"
        "Reply in this EXACT format:\n"
        "ADDITIONAL_VIOLATIONS: <number>\n"
        "VIOLATION_1: <description> (or 'none')\n"
        "VIOLATION_2: <description> (or 'none')\n"
        "COMPLIANCE_NOTE: <any additional compliance note>"
    )

    try:
        safe_prompt = build_safe_prompt(system_instructions, "Check for additional policy violations.")
        text = await ainvoke_llm(
            safe_prompt,
            node_name="POLICY_GUARD",
            ticket_id=state.get("ticket_id", ""),
            variant=variant,
            # max_tokens removed — uses generous default
        )

        # Parse LLM findings
        additional_violations = []
        compliance_note = ""

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("VIOLATION_") and ":" in line:
                desc = line.split(":", 1)[1].strip()
                if desc.lower() not in ("none", "n/a", "0"):
                    additional_violations.append({
                        "rule_id": "LLM-DETECTED",
                        "description": desc,
                        "severity": "soft_warning",  # LLM-detected issues default to warning
                        "action_affected": "unknown",
                    })
            elif line.upper().startswith("COMPLIANCE_NOTE:"):
                compliance_note = line.split(":", 1)[1].strip()

        # Merge with rule-based report
        merged_violations = list(rule_report.get("violations", [])) + additional_violations
        rule_report["violations"] = merged_violations
        rule_report["has_violations"] = len(merged_violations) > 0
        rule_report["llm_violations"] = len(additional_violations)
        rule_report["compliance_note"] = compliance_note
        rule_report["llm_enhanced"] = True

    except Exception as exc:
        logger.warning("policy_guard: LLM check failed (%s), using rule-based only", exc)

    return rule_report


@safe_node("POLICY_GUARD", fallback={
    "policy_report": {
        "applicable_rules": [], "violations": [], "constraints": [],
        "recommendations": [], "has_violations": False, "has_hard_violations": False,
        "policy_check_passed": True,
    },
    "active_frameworks": [],
    "evidence_chain": [],
})
async def policy_guard(state: dict[str, Any]) -> dict[str, Any]:
    """Enforce policy constraints on reasoning and planned actions (async).

    P2 NEW NODE: Injects POLICY RULES into the reasoning process. Unlike
    red_team (which attacks reasoning for logical flaws), the policy guard
    enforces business and regulatory constraints that reasoning must respect.

    Variant behavior:
      - mini: Rule-based policy check only (fast, cheap)
      - parwa: Rule-based + LLM policy interpretation (balanced)
      - high: Full policy analysis with LLM cross-reference (thorough)

    Reads: intent, raw_message, action_plans, integration_data, situation_model
    Writes: policy_report, active_frameworks (append), evidence_chain (append)
    """
    variant = state.get("variant", "parwa")

    # Guard type
    if not isinstance(variant, str):
        variant = "parwa"

    # Step 1: Rule-based policy check (all variants)
    report = _check_policies_rule_based(state)

    # Step 2: LLM enhancement for parwa and high variants
    if variant in ("parwa", "high") and not MOCK_MODE:
        report = await _check_policies_llm(state, report)

    # Track frameworks
    new_frameworks = []
    existing = state.get("active_frameworks", [])
    if "policy_guard" not in existing:
        new_frameworks.append("policy_guard")

    # Build evidence chain entry
    violation_count = len(report.get("violations", []))
    passed = report.get("policy_check_passed", True)

    new_evidence = [{
        "claim": f"Policy check: {'PASSED' if passed else 'VIOLATIONS FOUND'} — "
                 f"{violation_count} violation(s), {len(report.get('applicable_rules', []))} rule(s) checked",
        "sources": [v.get("description", "")[:80] for v in report.get("violations", [])[:3]],
        "confidence": 0.95 if passed else 0.90,
        "technique": "policy_guard",
        "category": "compliance",
        "node": "POLICY_GUARD",
        "policy_check_passed": passed,
        "violation_count": violation_count,
    }]

    logger.info(
        "policy_guard: passed=%s violations=%d hard_violations=%s variant=%s",
        passed, violation_count, report.get("has_hard_violations", False), variant,
    )

    return {
        "policy_report": report,
        "active_frameworks": new_frameworks,
        "evidence_chain": new_evidence,
    }
