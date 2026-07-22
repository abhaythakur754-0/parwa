"""
Builder Agent Non-LLM Techniques — 34 zero-cost enrichment functions.

Adapted from Node 6's 16 non-LLM techniques for agent CONFIG validation
instead of answer validation. Each technique can be reused across
multiple Builder stages (EXPLORE, DESIGN, VERIFY, REFINE) because
the SAME technique asks a DIFFERENT question at each stage.

Layer architecture (mirrors Node 6):
  L1 PRE-FLIGHT:  SafetyNet, CLARA, SmartRouter, TierGate,
                  ExistingAgentScan, CapabilityExpansion, GuardrailCheck
  L2 DESIGN AID:  TemplateInjection, StructurePreset, CrossConflictDetection
  L3 SCORING:     ZeroShotValidator, GSD, ThoT, StructureCheck,
                  KBGrounding, AdequacyCheck, CoVe, MAKER, CoverageCheck,
                  ReverseThinking, StepBackCheck, LeastToMost,
                  TheoryOfMind, FakeVoting
  L4 AGGREGATION: SelfConsistency, ContradictionCheck, SufficiencyCheck,
                  GapInjection, EscalationRuleEnrichment, MetaLearner,
                  ContextualCompression, Escalation, RuleBasedAction

Total: 34 techniques, 0 LLM calls.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("parwa.builder.non_llm")


# ═══════════════════════════════════════════════════════════════════
# L1: PRE-FLIGHT TECHNIQUES (run before any LLM call)
# ═══════════════════════════════════════════════════════════════════


# ── 1. SafetyNet — scrub PII from text ──────────────────────────────

_PII_PATTERNS = [
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),                      # phone
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), # email
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),                               # SSN
    re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),         # credit card
    re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),             # IP address
]


def safety_net_scrub(text: str) -> Dict[str, Any]:
    """Scrub PII from text before sending to LLM.

    Used in EXPLORE (scrub ticket_query) and VERIFY (scrub final config).
    """
    if not text:
        return {"scrubbed": text, "pii_found": False, "count": 0}

    scrubbed = text
    count = 0
    for pattern in _PII_PATTERNS:
        matches = pattern.findall(scrubbed)
        if matches:
            count += len(matches)
            scrubbed = pattern.sub("[REDACTED]", scrubbed)

    return {
        "scrubbed": scrubbed,
        "pii_found": count > 0,
        "count": count,
    }


# ── 2. CLARA — quick confidence estimate ────────────────────────────

_CAPABILITY_CONFIDENCE = {
    "refund_processing": 0.95,
    "billing_inquiry": 0.95,
    "technical_support": 0.90,
    "faq_general": 0.98,
    "complaint_handling": 0.90,
    "account_management": 0.92,
    "shipping_delivery": 0.93,
    "product_information": 0.95,
    "fraud_security": 0.80,
    "legal_review": 0.70,
    "vip_enterprise": 0.75,
    "freight_tracking": 0.85,
    "subscription_management": 0.88,
    "api_technical": 0.80,
    "insurance_claim": 0.78,
    "prescription_refill": 0.75,
    "loan_mortgage": 0.77,
    "booking_reservation": 0.90,
    "loyalty_rewards": 0.88,
    "port_activation": 0.82,
    "outage_report": 0.85,
    "lease_maintenance": 0.83,
    "policy_quote": 0.80,
    "other": 0.50,
}


def clara_confidence(capability: str, query: str) -> Dict[str, Any]:
    """Quick confidence: is this capability obvious or complex?

    High confidence (>0.90) + template exists → can skip DESIGN, use template.
    Low confidence (<0.70) → need full EXPLORE + DESIGN stages.
    """
    base = _CAPABILITY_CONFIDENCE.get(capability, 0.50)

    # Adjust based on query complexity
    query_lower = query.lower() if query else ""
    complex_signals = ["legal", "lawsuit", "regulatory", "compliance",
                       "fraud", "investigation", "multiple", "complex"]
    simple_signals = ["how do i", "what is", "where is", "when does", "can i"]

    for signal in complex_signals:
        if signal in query_lower:
            base -= 0.10
    for signal in simple_signals:
        if signal in query_lower:
            base += 0.05

    confidence = max(0.0, min(1.0, base))
    can_skip_design = confidence >= 0.90

    return {
        "confidence": round(confidence, 3),
        "can_skip_design": can_skip_design,
        "level": "high" if confidence >= 0.90 else "medium" if confidence >= 0.70 else "low",
    }


# ── 3. SmartRouter — skip LLM stages when non-LLM signals are strong ──

def smart_route(clara_result: Dict, existing_match: bool,
                tier_allows_custom: bool) -> Dict[str, Any]:
    """Decide if we can skip LLM-heavy stages.

    If CLARA says high confidence AND existing agent matches AND tier allows
    custom → just clone the existing agent config with minor tweaks.
    Saves 8-12 LLM calls.
    """
    skip_design = (
        clara_result.get("can_skip_design", False)
        and existing_match
    )
    skip_verify = skip_design and clara_result.get("confidence", 0) >= 0.95

    if not tier_allows_custom:
        # parwa tier: only templates, no custom building
        return {
            "action": "template_only",
            "skip_design": True,
            "skip_verify": True,
            "skip_refine": True,
            "reason": "Tier only allows templates",
        }

    if skip_design and skip_verify:
        return {
            "action": "clone_existing",
            "skip_design": True,
            "skip_verify": True,
            "skip_refine": True,
            "reason": "High confidence + existing match",
        }

    if skip_design:
        return {
            "action": "use_template_as_base",
            "skip_design": True,
            "skip_verify": False,
            "skip_refine": False,
            "reason": "High confidence but no existing match — use template, verify normally",
        }

    return {
        "action": "full_build",
        "skip_design": False,
        "skip_verify": False,
        "skip_refine": False,
        "reason": "Low confidence or complex — full Builder pipeline needed",
    }


# ── 4. TierGate — check tenant tier permissions ─────────────────────

def tier_gate(tier: str, agent_role: str = "custom") -> Dict[str, Any]:
    """Check if tenant's tier allows creating this type of agent.

    mini_parwa → no agents at all (reject)
    parwa → pre-built templates only (no custom)
    parwa_high → full custom agent creation ($5/mo each)
    """
    if tier == "mini_parwa":
        return {
            "allowed": False,
            "reason": "Mini PARWA tier does not support agents. Upgrade to PARWA to get pre-built agents.",
            "max_type": "none",
        }

    if tier == "parwa" and agent_role == "custom":
        return {
            "allowed": True,
            "reason": "PARWA tier supports pre-built agents only. Will use template.",
            "max_type": "template",
        }

    return {
        "allowed": True,
        "reason": "PARWA High tier supports full custom agent creation.",
        "max_type": "custom",
    }


# ── 5. ExistingAgentScan — check for duplicate agents ───────────────

def existing_agent_scan(tenant_agents: List[Dict], capability: str) -> Dict[str, Any]:
    """Check if tenant already has an agent covering this capability.

    If overlap > 80%, we should skip Builder entirely and just route
    to the existing agent.
    """
    if not tenant_agents or not capability:
        return {"has_match": False, "overlap": 0.0, "matching_agent": None}

    cap_lower = capability.lower()
    best_match = None
    best_overlap = 0.0

    for agent in tenant_agents:
        agent_caps = agent.get("capabilities", [])
        if isinstance(agent_caps, str):
            try:
                agent_caps = json.loads(agent_caps)
            except (json.JSONDecodeError, TypeError):
                agent_caps = []

        # Calculate overlap
        if not agent_caps:
            continue

        matching = sum(1 for c in agent_caps if c.lower() == cap_lower or cap_lower in c.lower())
        overlap = matching / max(len(agent_caps), 1)

        if overlap > best_overlap:
            best_overlap = overlap
            best_match = agent

    # Also check if capability name appears in agent name
    for agent in tenant_agents:
        name_lower = agent.get("name", "").lower()
        if cap_lower.replace("_", " ") in name_lower:
            best_overlap = max(best_overlap, 0.85)
            best_match = agent

    return {
        "has_match": best_overlap >= 0.80,
        "overlap": round(best_overlap, 3),
        "matching_agent": best_match,
        "should_skip_builder": best_overlap >= 0.80,
    }


# ── 6. CapabilityExpansion — expand capability using patterns ───────

# Reuse CAPABILITY_PATTERNS from Node 1
_CAPABILITY_PATTERNS = {
    "fraud_security": [r"\bfraud\b", r"\bscam\b", r"\bunauthorized\b", r"\bstolen\b"],
    "shipping_delivery": [r"\bshipping\b", r"\bdelivery\b", r"\btracking\b", r"\bpackage\b"],
    "billing_inquiry": [r"\bbilling\b", r"\bcharge\b", r"\binvoice\b", r"\bpayment\b"],
    "refund_processing": [r"\brefund\b", r"\breturn\b", r"\bmoney back\b", r"\breimburse\b"],
    "technical_support": [r"\btechnical\b", r"\bbug\b", r"\berror\b", r"\bbroken\b"],
    "complaint_handling": [r"\bcomplaint\b", r"\bunhappy\b", r"\bdissatisfied\b", r"\bupset\b"],
    "account_management": [r"\baccount\b", r"\bpassword\b", r"\blogin\b", r"\bprofile\b"],
    "subscription_management": [r"\bsubscription\b", r"\bplan\b", r"\bupgrade\b", r"\bdowngrade\b"],
    "booking_reservation": [r"\bbooking\b", r"\breservation\b", r"\bflight\b", r"\bhotel\b"],
    "loyalty_rewards": [r"\bloyalty\b", r"\breward\b", r"\bpoints?\b", r"\bmiles?\b"],
    "insurance_claim": [r"\bclaim\b", r"\bcoverage\b", r"\bbenefit\b", r"\bdeductible\b"],
    "prescription_refill": [r"\bprescription\b", r"\brefill\b", r"\bmedication\b", r"\bpharmacy\b"],
    "legal_review": [r"\blawsuit\b", r"\blawyer\b", r"\battorney\b", r"\blegal\b"],
    "port_activation": [r"\bport-?in\b", r"\bactivation\b", r"\bsim\b", r"\bimei\b"],
    "outage_report": [r"\boutage\b", r"\bservice down\b", r"\bno internet\b", r"\bno signal\b"],
    "lease_maintenance": [r"\blease\b", r"\btenant\b", r"\brental\b", r"\bmaintenance\b"],
    "policy_quote": [r"\bpolicy\b", r"\bquote\b", r"\bpremium\b", r"\bbeneficiary\b"],
    "loan_mortgage": [r"\bloan\b", r"\bmortgage\b", r"\binterest rate\b", r"\brefinance\b"],
    "freight_tracking": [r"\bfreight\b", r"\bcargo\b", r"\bshipment\b", r"\bcontainer\b"],
    "api_technical": [r"\bapi\b", r"\bwebhook\b", r"\bendpoint\b", r"\brate limit\b"],
    "product_information": [r"\bproduct\b", r"\bfeatures?\b", r"\bspecs?\b", r"\bcompatib\b"],
    "vip_enterprise": [r"\bvip\b", r"\benterprise\b", r"\bkey account\b", r"\bexecutive\b"],
    "faq_general": [r"\bhow to\b", r"\bwhat is\b", r"\bfaq\b", r"\bquestion\b"],
}


def capability_expansion(capability: str, query: str) -> Dict[str, Any]:
    """Expand a single capability into related sub-capabilities.

    EXPLORE: enrich the LLM prompt with discovered capabilities.
    DESIGN: catch capabilities that LLM candidates might miss.
    """
    if not query:
        return {"expanded": [capability], "added": []}

    query_lower = query.lower()
    added = []

    for cap_key, patterns in _CAPABILITY_PATTERNS.items():
        if cap_key == capability:
            continue  # already have this one
        for pattern in patterns:
            if re.search(pattern, query_lower):
                if cap_key not in added:
                    added.append(cap_key)
                break

    expanded = [capability] + added
    return {
        "expanded": expanded,
        "added": added,
        "original": capability,
    }


# ── 7. GuardrailCheck — non-LLM safety scan ─────────────────────────

_HARMFUL_PATTERNS = [
    re.compile(r'\b(?:kill yourself|suicide|self-harm|end it all)\b', re.I),
    re.compile(r'\b(?:hack\s+into|sql\s+injection|ddos|exploit)\b', re.I),
    re.compile(r'\b(?:discriminat|harass|threat|stalk)\b', re.I),
    re.compile(r'\b(?:child\s+abuse|sexual\s+assault|pedophil)\b', re.I),
    re.compile(r'\b(?:bomb|terrorist|explosive)\b', re.I),
]

_DANGEROUS_INSTRUCTIONS = [
    re.compile(r'\baccess\s+(?:bank|credit\s+card|financial)\s+account\b', re.I),
    re.compile(r'\bshare\s+(?:customer|user)\s+(?:data|information)\s+(?:with|to)\b', re.I),
    re.compile(r'\b(?:delete|remove)\s+all\s+(?:data|records|accounts)\b', re.I),
    re.compile(r'\bauto(?:matically)?\s+(?:approve|process)\s+all\b', re.I),
    re.compile(r'\bbypass\s+(?:security|verification|authentication)\b', re.I),
]


def guardrail_check(text: str) -> Dict[str, Any]:
    """Non-LLM safety scan for harmful or dangerous content.

    EXPLORE: scan ticket_query before LLM.
    VERIFY: scan final config before saving.
    """
    if not text:
        return {"safe": True, "flags": [], "flag_count": 0}

    flags = []

    # Check for harmful content
    for pattern in _HARMFUL_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            flags.extend([f"harmful: {m}" for m in matches[:3]])

    # Check for dangerous agent instructions
    for pattern in _DANGEROUS_INSTRUCTIONS:
        matches = pattern.findall(text)
        if matches:
            flags.extend([f"dangerous_instruction: {m}" for m in matches[:3]])

    return {
        "safe": len(flags) == 0,
        "flags": flags[:5],
        "flag_count": len(flags),
    }


# ═══════════════════════════════════════════════════════════════════
# L2: DESIGN AID TECHNIQUES (help LLM generate better candidates)
# ═══════════════════════════════════════════════════════════════════


# ── 8. TemplateInjection — use pre-built template as Candidate #1 ───

# Simplified industry templates (full list in 02_industry_variants.json)
_AGENT_TEMPLATES = {
    "refund_processing": {
        "instructions": "Handle refund requests professionally. Verify order details, check refund eligibility per policy, process refund to original payment method, and confirm timeline with customer.",
        "restrictions": "Never process refunds above $500 without manager approval. Always verify order number and purchase date before processing. Escalate disputed refunds to human.",
        "capabilities": ["refund_processing", "billing_inquiry"],
    },
    "billing_inquiry": {
        "instructions": "Handle billing questions and disputes. Explain charges clearly, verify payment history, identify billing errors, and initiate corrections when warranted.",
        "restrictions": "Never share full credit card numbers. Always verify customer identity before discussing billing details. Escalate suspected fraud immediately.",
        "capabilities": ["billing_inquiry", "account_management"],
    },
    "technical_support": {
        "instructions": "Provide step-by-step technical troubleshooting. Start with simplest solutions, escalate if issue persists after 3 attempts. Document all steps taken.",
        "restrictions": "Never instruct customers to modify system files. Never share internal infrastructure details. Always recommend backup before changes.",
        "capabilities": ["technical_support", "faq_general"],
    },
    "complaint_handling": {
        "instructions": "Handle customer complaints with empathy and professionalism. Acknowledge the issue, apologize sincerely, offer resolution options, and follow up.",
        "restrictions": "Never dismiss customer concerns. Never argue with customers. Always escalate legal threats to human. Document all complaints.",
        "capabilities": ["complaint_handling", "account_management"],
    },
    "shipping_delivery": {
        "instructions": "Handle shipping and delivery inquiries. Track packages, explain delivery timelines, report lost or damaged shipments, and arrange replacements.",
        "restrictions": "Never promise specific delivery dates for international shipments. Always verify tracking number before providing status. Escalate lost packages over $200.",
        "capabilities": ["shipping_delivery", "refund_processing"],
    },
    "account_management": {
        "instructions": "Handle account-related requests including login issues, password resets, profile updates, and account changes. Verify identity before any changes.",
        "restrictions": "Never share passwords. Always verify identity via 2FA before account changes. Never delete accounts without explicit written confirmation.",
        "capabilities": ["account_management", "faq_general"],
    },
    "booking_reservation": {
        "instructions": "Handle booking and reservation requests. Check availability, make reservations, process modifications and cancellations, and explain policies.",
        "restrictions": "Never guarantee availability without real-time check. Always confirm cancellation policy before booking. Escalate group bookings over 10 people.",
        "capabilities": ["booking_reservation", "refund_processing"],
    },
    "subscription_management": {
        "instructions": "Handle subscription and plan management. Explain plan differences, process upgrades/downgrades, manage renewals, and handle cancellation requests.",
        "restrictions": "Never cancel without confirming retention offers first. Always explain what happens to data on downgrade. Escalate enterprise plan changes.",
        "capabilities": ["subscription_management", "billing_inquiry"],
    },
}


def template_injection(capability: str) -> Dict[str, Any]:
    """Find a pre-built template for this capability.

    If found, use as Candidate #1 in DESIGN stage. Saves 1 LLM call
    and guarantees 1 strong candidate.
    """
    template = _AGENT_TEMPLATES.get(capability)

    if template:
        return {
            "has_template": True,
            "template": template,
            "saves_llm_calls": 1,
        }

    # Try partial match
    cap_words = set(capability.replace("_", " ").lower().split())
    for key, tmpl in _AGENT_TEMPLATES.items():
        key_words = set(key.replace("_", " ").lower().split())
        if cap_words & key_words:
            return {
                "has_template": True,
                "template": tmpl,
                "saves_llm_calls": 1,
                "partial_match": key,
            }

    return {"has_template": False, "template": None, "saves_llm_calls": 0}


# ── 9. StructurePreset — reject malformed JSON early ────────────────

_MIN_INSTRUCTIONS_LEN = 50
_MIN_RESTRICTIONS_LEN = 30
_MIN_CAPABILITIES_COUNT = 2


def structure_preset(candidate_json: Dict) -> Dict[str, Any]:
    """Validate candidate JSON structure before parsing.

    Rejects malformed configs immediately — don't waste time
    trying to parse or fix them.
    """
    if not candidate_json or not isinstance(candidate_json, dict):
        return {"valid": False, "issues": ["Not a valid JSON object"]}

    issues = []

    instructions = str(candidate_json.get("instructions", ""))
    if len(instructions) < _MIN_INSTRUCTIONS_LEN:
        issues.append(f"Instructions too short ({len(instructions)} chars, need {_MIN_INSTRUCTIONS_LEN})")

    restrictions = str(candidate_json.get("restrictions", ""))
    if len(restrictions) < _MIN_RESTRICTIONS_LEN:
        issues.append(f"Restrictions too short ({len(restrictions)} chars, need {_MIN_RESTRICTIONS_LEN})")

    capabilities = candidate_json.get("capabilities", [])
    if not isinstance(capabilities, list):
        issues.append("Capabilities must be a list")
    elif len(capabilities) < _MIN_CAPABILITIES_COUNT:
        issues.append(f"Need at least {_MIN_CAPABILITIES_COUNT} capabilities, got {len(capabilities)}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


# ── 10. CrossConflictDetection — check for agent conflicts ──────────

def cross_conflict_detection(
    new_capabilities: List[str],
    existing_agents: List[Dict],
    tenant_id: str,
) -> Dict[str, Any]:
    """Check if new agent's capabilities conflict with existing agents.

    If two agents both claim "refund_processing", tickets will route
    to both or neither. Add domain scoping to prevent conflicts.
    """
    if not existing_agents:
        return {"has_conflict": False, "conflicts": [], "suggestions": []}

    conflicts = []
    suggestions = []

    for agent in existing_agents:
        agent_caps = agent.get("capabilities", [])
        if isinstance(agent_caps, str):
            try:
                agent_caps = json.loads(agent_caps)
            except (json.JSONDecodeError, TypeError):
                agent_caps = []

        overlap = [c for c in new_capabilities if c in agent_caps]
        if overlap:
            conflicts.append({
                "agent": agent.get("name", "unknown"),
                "overlapping_capabilities": overlap,
            })
            suggestions.append(
                f"Add domain scope to distinguish from '{agent.get('name')}': "
                f"they handle {overlap}, your agent should be more specific."
            )

    return {
        "has_conflict": len(conflicts) > 0,
        "conflicts": conflicts,
        "suggestions": suggestions,
    }


# ═══════════════════════════════════════════════════════════════════
# L3: SCORING TECHNIQUES (evaluate config quality, 0 LLM calls)
# ═══════════════════════════════════════════════════════════════════


# ── 11. ZeroShotValidator — flag unusual patterns ────────────────────

_UNUSUAL_COMBOS = [
    (["fraud_security", "hospitality"], "Fraud agent for hospitality industry — unusual, verify need"),
    (["legal_review", "bakery"], "Legal agent for bakery — unusual, verify need"),
    (["prescription_refill", "ecommerce"], "Prescription agent for e-commerce — verify regulatory compliance"),
    (["loan_mortgage", "restaurant"], "Loan agent for restaurant — unusual, verify need"),
    (["vip_enterprise", "startup"], "VIP agent for startup — may not have enterprise customers"),
]


def zero_shot_validator(capability: str, domain: str, capabilities: List[str]) -> Dict[str, Any]:
    """Flag unusual capability/domain combinations.

    EXPLORE: catch weird requests before spending LLM tokens.
    VERIFY: double-check after synthesis (new combos might be weird).
    """
    domain_lower = (domain or "").lower()
    flags = []

    for combo_caps, reason in _UNUSUAL_COMBOS:
        if capability in combo_caps and any(d in domain_lower for d in combo_caps[1:]):
            flags.append(reason)
        for c in capabilities:
            if c in combo_caps and any(d in domain_lower for d in combo_caps[1:]):
                flags.append(reason)

    # Check for contradictory capabilities
    contradiction_pairs = [
        ("refund_processing", "no_refund"),
        ("technical_support", "non_technical"),
    ]
    cap_set = set(c.lower() for c in capabilities)
    for c1, c2 in contradiction_pairs:
        if c1 in cap_set and c2 in cap_set:
            flags.append(f"Contradictory capabilities: {c1} and {c2}")

    return {
        "is_unusual": len(flags) > 0,
        "flags": flags,
        "flag_count": len(flags),
    }


# ── 12. GSD — per-part quality check ────────────────────────────────

def gsd_check(config: Dict) -> Dict[str, Any]:
    """Check each config field separately: instructions, restrictions, capabilities.

    DESIGN: score each candidate part → synthesis uses best parts.
    VERIFY: catch weak sections that voters missed.
    """
    instructions = str(config.get("instructions", ""))
    restrictions = str(config.get("restrictions", ""))
    capabilities = config.get("capabilities", [])
    if isinstance(capabilities, str):
        try:
            capabilities = json.loads(capabilities)
        except (json.JSONDecodeError, TypeError):
            capabilities = [capabilities]

    # Instructions quality
    inst_score = 0.50
    if len(instructions) >= 100:
        inst_score += 0.15
    if len(instructions) >= 200:
        inst_score += 0.10
    if any(w in instructions.lower() for w in ["always", "never", "must", "ensure"]):
        inst_score += 0.10  # has concrete rules
    if any(w in instructions.lower() for w in ["escalate", "verify", "confirm"]):
        inst_score += 0.10  # has safety checks
    if "help the customer" in instructions.lower() and len(instructions) < 100:
        inst_score -= 0.15  # generic + short = bad

    # Restrictions quality
    rest_score = 0.50
    if len(restrictions) >= 50:
        rest_score += 0.15
    if len(restrictions) >= 100:
        rest_score += 0.10
    if any(w in restrictions.lower() for w in ["never", "always", "must not", "escalate"]):
        rest_score += 0.15  # has hard rules
    if "unsure" in restrictions.lower() or "uncertain" in restrictions.lower():
        rest_score += 0.10  # has uncertainty handling

    # Capabilities quality
    cap_score = 0.50
    if len(capabilities) >= 2:
        cap_score += 0.15
    if len(capabilities) >= 3:
        cap_score += 0.10
    if len(capabilities) >= 5:
        cap_score += 0.05
    # Check for diversity (not all variations of same word)
    unique_words = set()
    for c in capabilities:
        unique_words.update(c.replace("_", " ").lower().split())
    if len(unique_words) >= 4:
        cap_score += 0.10

    inst_score = max(0.0, min(1.0, inst_score))
    rest_score = max(0.0, min(1.0, rest_score))
    cap_score = max(0.0, min(1.0, cap_score))
    overall = (inst_score + rest_score + cap_score) / 3.0

    return {
        "instructions_score": round(inst_score, 3),
        "restrictions_score": round(rest_score, 3),
        "capabilities_score": round(cap_score, 3),
        "overall": round(overall, 3),
        "weakest_part": min(
            [("instructions", inst_score), ("restrictions", rest_score), ("capabilities", cap_score)],
            key=lambda x: x[1],
        )[0],
    }


# ── 13. ThoT — coherence check ──────────────────────────────────────

def thot_coherence(config: Dict) -> Dict[str, Any]:
    """Check if instructions + restrictions + capabilities are internally consistent.

    Catches contradictions like:
    - Instructions say "always refund" but restrictions say "never refund"
    - Capabilities list "refund_processing" but instructions mention booking
    """
    instructions = str(config.get("instructions", "")).lower()
    restrictions = str(config.get("restrictions", "")).lower()
    capabilities = config.get("capabilities", [])
    if isinstance(capabilities, str):
        try:
            capabilities = json.loads(capabilities)
        except (json.JSONDecodeError, TypeError):
            capabilities = [capabilities]

    cap_text = " ".join(c.replace("_", " ") for c in capabilities).lower()
    issues = []

    # Check 1: Instructions vs Restrictions contradictions
    contradiction_pairs = [
        ("always refund", "never refund"),
        ("auto approve", "must verify"),
        ("share information", "never share"),
        ("process immediately", "wait for approval"),
        ("guaranteed", "not guaranteed"),
    ]
    for inst_phrase, rest_phrase in contradiction_pairs:
        if inst_phrase in instructions and rest_phrase in restrictions:
            issues.append(f"Contradiction: instructions say '{inst_phrase}' but restrictions say '{rest_phrase}'")

    # Check 2: Capabilities vs Instructions alignment
    cap_words = set(cap_text.split())
    inst_words = set(instructions.split())
    if cap_words:
        overlap = len(cap_words & inst_words) / max(len(cap_words), 1)
        if overlap < 0.10:
            issues.append("Instructions barely mention any capability keywords — may be off-target")

    # Check 3: Restrictions vs Capabilities alignment
    rest_words = set(restrictions.split())
    if cap_words:
        overlap = len(cap_words & rest_words) / max(len(cap_words), 1)
        if overlap < 0.05:
            issues.append("Restrictions don't reference any capability keywords — may be generic")

    score = max(0.0, min(1.0, 1.0 - (len(issues) * 0.20)))

    return {
        "coherent": len(issues) == 0,
        "issues": issues,
        "score": round(score, 3),
    }


# ── 14. StructureCheck — config has required fields ─────────────────

def structure_check(config: Dict) -> Dict[str, Any]:
    """Check if config has all required fields with adequate content.

    Hard gate — malformed configs NEVER pass VERIFY.
    """
    required_fields = ["instructions", "restrictions", "capabilities"]
    missing = [f for f in required_fields if f not in config or not config[f]]

    violations = []

    instructions = str(config.get("instructions", ""))
    if len(instructions) < 50:
        violations.append(f"Instructions too short: {len(instructions)} chars (need 50+)")

    restrictions = str(config.get("restrictions", ""))
    if len(restrictions) < 30:
        violations.append(f"Restrictions too short: {len(restrictions)} chars (need 30+)")

    capabilities = config.get("capabilities", [])
    if isinstance(capabilities, str):
        try:
            capabilities = json.loads(capabilities)
        except (json.JSONDecodeError, TypeError):
            capabilities = []
    if len(capabilities) < 2:
        violations.append(f"Need at least 2 capabilities, got {len(capabilities)}")

    score = 1.0
    if missing:
        score -= 0.30
    score -= len(violations) * 0.10
    score = max(0.0, min(1.0, score))

    return {
        "passes": len(missing) == 0 and len(violations) == 0,
        "missing_fields": missing,
        "violations": violations,
        "score": round(score, 3),
    }


# ── 15. KBGrounding — check if KB docs support this capability ──────

def kb_grounding(capability: str, kb_chunk_count: int) -> Dict[str, Any]:
    """Check if tenant has KB documents for this agent's capabilities.

    If no docs for "prescription_refill" → warn in restrictions.
    """
    if kb_chunk_count == 0:
        return {
            "has_kb": False,
            "score": 0.30,
            "warning": "No KB docs uploaded — agent will have limited knowledge.",
        }

    if kb_chunk_count < 5:
        return {
            "has_kb": True,
            "score": 0.60,
            "warning": f"Only {kb_chunk_count} KB chunks — consider uploading more docs.",
        }

    if kb_chunk_count < 20:
        return {
            "has_kb": True,
            "score": 0.80,
            "warning": None,
        }

    return {
        "has_kb": True,
        "score": 0.95,
        "warning": None,
    }


# ── 16. AdequacyCheck — are instructions specific enough? ────────────

_GENERIC_PHRASES = [
    "help the customer",
    "assist the user",
    "provide support",
    "handle inquiries",
    "answer questions",
    "be helpful",
    "be professional",
]


def adequacy_check(instructions: str, capability: str) -> Dict[str, Any]:
    """Check if instructions are specific or just generic boilerplate.

    Catches lazy instructions like "Help the customer with their issue"
    that LLM voters might accept but are useless in practice.
    """
    if not instructions:
        return {"adequate": False, "score": 0.0, "issues": ["No instructions provided"]}

    inst_lower = instructions.lower()
    issues = []
    score = 0.70  # baseline

    # Check for generic phrases
    generic_found = [p for p in _GENERIC_PHRASES if p in inst_lower]
    if generic_found and len(instructions) < 200:
        issues.append(f"Generic instructions: contains '{generic_found[0]}' without specifics")
        score -= 0.15

    # Check if capability is mentioned in instructions
    cap_words = capability.replace("_", " ").lower().split()
    if not any(w in inst_lower for w in cap_words):
        issues.append(f"Instructions don't mention the capability '{capability}'")
        score -= 0.20

    # Check for action words (specific instructions)
    action_words = ["verify", "check", "confirm", "process", "escalate", "review",
                    "calculate", "validate", "authorize", "schedule"]
    actions_found = sum(1 for w in action_words if w in inst_lower)
    if actions_found >= 2:
        score += 0.10
    elif actions_found == 0:
        issues.append("No action words in instructions — may be too vague")
        score -= 0.10

    score = max(0.0, min(1.0, score))

    return {
        "adequate": score >= 0.60,
        "score": round(score, 3),
        "issues": issues,
    }


# ── 17. CoVe — verify capabilities against available tools ───────────

_TOOL_REQUIRED_CAPABILITIES = {
    "refund_processing": ["stripe", "payment_processor"],
    "shipping_delivery": ["shipping_api", "tracking_service"],
    "booking_reservation": ["booking_api", "calendar_service"],
    "subscription_management": ["billing_api", "subscription_service"],
    "insurance_claim": ["claims_api", "document_service"],
    "prescription_refill": ["pharmacy_api", "verification_service"],
    "loan_mortgage": ["financial_api", "credit_check"],
    "freight_tracking": ["logistics_api", "tracking_service"],
}


def cove_verify(
    capabilities: List[str],
    integrations: List[Dict],
) -> Dict[str, Any]:
    """Verify agent's claimed capabilities against available tools/integrations.

    Agent claims "refund_processing" but no Stripe integration → flag.
    """
    if not capabilities:
        return {"verified": True, "gaps": [], "score": 0.90}

    integration_types = set()
    for integ in integrations:
        integ_type = integ.get("type", "").lower() if isinstance(integ, dict) else str(integ).lower()
        integration_types.add(integ_type)

    gaps = []
    for cap in capabilities:
        required_tools = _TOOL_REQUIRED_CAPABILITIES.get(cap, [])
        if required_tools:
            missing_tools = [t for t in required_tools if not any(t in it for it in integration_types)]
            if missing_tools and not integration_types:
                # No integrations at all — just flag, don't block
                gaps.append({
                    "capability": cap,
                    "missing_tools": missing_tools,
                    "severity": "warning",
                    "message": f"'{cap}' typically needs {missing_tools} but no integrations found. Agent will be limited to advisory only.",
                })

    score = max(0.50, 1.0 - (len(gaps) * 0.15))

    return {
        "verified": len(gaps) == 0,
        "gaps": gaps,
        "score": round(score, 3),
    }


# ── 18. MAKER — find missing capabilities ───────────────────────────

# Common capability pairings: if you have X, you probably also need Y
_CAPABILITY_PAIRS = {
    "refund_processing": ["billing_inquiry", "account_management"],
    "billing_inquiry": ["account_management"],
    "technical_support": ["faq_general"],
    "complaint_handling": ["account_management", "refund_processing"],
    "shipping_delivery": ["refund_processing"],
    "booking_reservation": ["refund_processing", "cancellation"],
    "subscription_management": ["billing_inquiry"],
    "insurance_claim": ["account_management"],
    "prescription_refill": ["account_management"],
    "loan_mortgage": ["account_management", "billing_inquiry"],
    "fraud_security": ["account_management"],
    "legal_review": ["complaint_handling"],
    "vip_enterprise": ["account_management", "complaint_handling"],
    "loyalty_rewards": ["account_management", "billing_inquiry"],
    "port_activation": ["account_management"],
    "outage_report": ["technical_support"],
    "lease_maintenance": ["account_management", "complaint_handling"],
    "policy_quote": ["account_management"],
}


def maker_find_gaps(capability: str, current_capabilities: List[str]) -> Dict[str, Any]:
    """Find capabilities that are commonly needed but MISSING.

    DESIGN: find what each candidate is missing.
    VERIFY: find what synthesized config is missing.
    REFINE: identify specific gaps to fix.
    """
    if not capability:
        return {"gaps": [], "gap_count": 0, "suggested_additions": []}

    cap_lower = capability.lower()
    current_set = set(c.lower() for c in current_capabilities)

    # Find commonly paired capabilities
    paired = _CAPABILITY_PAIRS.get(cap_lower, [])
    gaps = [p for p in paired if p not in current_set]

    # Also check if any existing capability's pairs are missing
    for c in current_capabilities:
        c_pairs = _CAPABILITY_PAIRS.get(c.lower(), [])
        for p in c_pairs:
            if p not in current_set and p not in gaps:
                gaps.append(p)

    return {
        "gaps": gaps[:5],  # limit to top 5
        "gap_count": len(gaps),
        "suggested_additions": gaps[:3],  # top 3 most important
    }


# ── 19. CoverageCheck — does config cover detected capability? ──────

def coverage_check(capability: str, config: Dict) -> Dict[str, Any]:
    """Check if capabilities list actually covers the detected capability.

    Catches off-target configs: detected "refund_processing" but
    capabilities list only has "faq_general" and "account_management".
    """
    capabilities = config.get("capabilities", [])
    if isinstance(capabilities, str):
        try:
            capabilities = json.loads(capabilities)
        except (json.JSONDecodeError, TypeError):
            capabilities = []

    cap_words = set(capability.replace("_", " ").lower().split())

    # Check if capability itself is in the list
    direct_match = capability.lower() in [c.lower() for c in capabilities]

    # Check if capability words appear in any listed capability
    word_coverage = 0
    for word in cap_words:
        for listed_cap in capabilities:
            if word in listed_cap.lower():
                word_coverage += 1
                break

    word_score = word_coverage / max(len(cap_words), 1)

    if direct_match:
        return {"covers": True, "score": 1.0, "gaps": []}

    if word_score >= 0.5:
        return {"covers": True, "score": 0.80, "gaps": [f"Partial match — '{capability}' not directly in capabilities list"]}

    return {
        "covers": False,
        "score": round(word_score, 3),
        "gaps": [f"Detected capability '{capability}' not covered by capabilities: {capabilities}"],
    }


# ── 20. ReverseThinking — what could go WRONG? ──────────────────────

_RISK_PATTERNS = {
    "refund_processing": [
        "No amount limit → agent could process $10,000 refunds",
        "No verification step → fraud risk",
        "No escalation for disputes → customer frustration",
    ],
    "billing_inquiry": [
        "No identity verification → privacy violation",
        "No charge cap → unauthorized credits",
        "No audit trail → compliance risk",
    ],
    "technical_support": [
        "No escalation after N attempts → customer stuck in loop",
        "No system access limits → agent might instruct dangerous operations",
        "No rollback instructions → customer makes irreversible changes",
    ],
    "complaint_handling": [
        "No empathy requirement → agent feels cold",
        "No escalation for legal threats → liability risk",
        "No documentation → can't track patterns",
    ],
    "legal_review": [
        "No hard block on legal advice → company liability",
        "No mandatory human escalation → risk of wrong guidance",
        "No jurisdiction scope → agent gives advice for wrong legal system",
    ],
    "shipping_delivery": [
        "No tracking verification → wrong package info",
        "No international shipping scope → wrong promises",
        "No loss threshold → small and large losses treated same",
    ],
}


def reverse_thinking(capability: str, config: Dict) -> Dict[str, Any]:
    """What could go WRONG with this agent?

    VERIFY: identify risks in final config.
    REFINE: identify NEW risks introduced by fixes.
    """
    risks = list(_RISK_PATTERNS.get(capability, []))

    instructions = str(config.get("instructions", "")).lower()
    restrictions = str(config.get("restrictions", "")).lower()

    # Dynamic risk checks
    if "refund" in capability.lower() or "credit" in capability.lower():
        if "limit" not in restrictions and "max" not in restrictions:
            risks.append("No refund/credit amount limit in restrictions → financial risk")
        if "verify" not in instructions and "confirm" not in instructions:
            risks.append("No verification before refund processing → fraud risk")

    if "legal" in capability.lower():
        if "escalate" not in restrictions:
            risks.append("Legal agent without mandatory escalation → liability risk")

    if "medical" in capability.lower() or "prescription" in capability.lower():
        if "not provide medical advice" not in restrictions:
            risks.append("Medical/prescription agent without medical advice disclaimer → health risk")

    # Check for absolute promises
    absolute_phrases = ["guaranteed", "100%", "always", "never fail", "no matter what"]
    for phrase in absolute_phrases:
        if phrase in instructions:
            risks.append(f"Absolute promise in instructions: '{phrase}' → overcommitment risk")

    risk_score = max(0.0, 1.0 - (len(risks) * 0.12))

    return {
        "risks": risks[:7],
        "risk_count": len(risks),
        "risk_score": round(risk_score, 3),
    }


# ── 21. StepBackCheck — does config fit tenant's overall strategy? ──

def step_back_check(
    capability: str,
    tenant_agents: List[Dict],
    domain: str,
) -> Dict[str, Any]:
    """Zoom out: does this agent fit the tenant's overall customer care strategy?

    Don't create a "legal review" agent for a bakery that only
    handles 2 ticket types. Don't create a 15th agent when 3 would do.
    """
    score = 0.95  # start high, deduct for strategic misalignment
    issues = []

    # Check 1: Agent count — too many agents for this tenant?
    agent_count = len(tenant_agents)
    if agent_count >= 10:
        issues.append(f"Tenant already has {agent_count} agents — consider consolidating instead of adding more")
        score -= 0.10

    # Check 2: Capability overlap with existing agents
    existing_caps = set()
    for agent in tenant_agents:
        caps = agent.get("capabilities", [])
        if isinstance(caps, str):
            try:
                caps = json.loads(caps)
            except (json.JSONDecodeError, TypeError):
                caps = []
        existing_caps.update(c.lower() for c in caps)

    new_cap = capability.lower()
    if new_cap in existing_caps:
        issues.append(f"Capability '{capability}' already covered by existing agent — possible duplicate")
        score -= 0.20

    # Check 3: Domain coherence
    agent_domains = [a.get("domain", "") for a in tenant_agents if a.get("domain")]
    if domain and agent_domains:
        # Check if new domain is wildly different
        common_domains = set(d.lower() for d in agent_domains if d)
        if common_domains and domain.lower() not in common_domains and domain != "auto":
            issues.append(f"New agent domain '{domain}' differs from existing domains {common_domains}")
            score -= 0.05

    return {
        "passes": score >= 0.80,
        "score": round(max(0.0, min(1.0, score)), 3),
        "issues": issues,
    }


# ── 22. LeastToMost — decompose capabilities into sub-skills ────────

_CAPABILITY_SUBSKILLS = {
    "refund_processing": ["verify_order", "check_eligibility", "calculate_amount", "process_refund", "confirm_timeline"],
    "billing_inquiry": ["identify_charge", "explain_charge", "verify_payment", "initiate_correction", "confirm_resolution"],
    "technical_support": ["reproduce_issue", "diagnose_problem", "provide_solution", "verify_fix", "document_steps"],
    "complaint_handling": ["acknowledge_issue", "empathize", "investigate", "offer_resolution", "follow_up"],
    "shipping_delivery": ["locate_package", "explain_status", "handle_delay", "arrange_replacement", "confirm_delivery"],
    "booking_reservation": ["check_availability", "make_booking", "modify_booking", "cancel_booking", "confirm_details"],
    "account_management": ["verify_identity", "retrieve_account", "make_changes", "confirm_changes", "secure_account"],
    "subscription_management": ["explain_plans", "process_change", "handle_upgrade", "handle_downgrade", "manage_renewal"],
}


def least_to_most_verify(capability: str, instructions: str) -> Dict[str, Any]:
    """Break capabilities into sub-skills, verify each is covered in instructions.

    "refund_processing" = verify amount + process refund + confirm →
    all mentioned in instructions?
    """
    subskills = _CAPABILITY_SUBSKILLS.get(capability)
    if not subskills:
        return {
            "claims_total": 0,
            "claims_verified": 0,
            "score": 0.90,
            "missing_subskills": [],
        }

    inst_lower = instructions.lower() if instructions else ""
    missing = []

    verified = 0
    for skill in subskills:
        # Check if any word from the subskill appears in instructions
        skill_words = skill.replace("_", " ").split()
        if any(w in inst_lower for w in skill_words):
            verified += 1
        else:
            missing.append(skill)

    score = verified / max(len(subskills), 1)

    return {
        "claims_total": len(subskills),
        "claims_verified": verified,
        "score": round(max(0.0, min(1.0, score)), 3),
        "missing_subskills": missing,
    }


# ── 23. TheoryOfMind — does config serve REAL intent? ───────────────

_CAPABILITY_INTENT = {
    "refund_processing": {"real_intent": "get money back", "must_address": ["refund", "amount", "process"]},
    "cancel": {"real_intent": "stop the service/subscription", "must_address": ["cancel", "confirm", "effective"]},
    "complaint_handling": {"real_intent": "be heard and get resolution", "must_address": ["acknowledge", "resolve", "sorry"]},
    "billing_inquiry": {"real_intent": "understand or fix a charge", "must_address": ["charge", "amount", "explain"]},
    "technical_support": {"real_intent": "fix a problem they can't solve alone", "must_address": ["step", "fix", "try"]},
    "shipping_delivery": {"real_intent": "know where their package is", "must_address": ["tracking", "status", "location"]},
    "booking_reservation": {"real_intent": "confirm or change their booking", "must_address": ["booking", "confirm", "details"]},
    "account_management": {"real_intent": "get access to their account", "must_address": ["account", "verify", "access"]},
    "subscription_management": {"real_intent": "change or cancel their plan", "must_address": ["plan", "change", "confirm"]},
    "legal_review": {"real_intent": "get legal concern addressed safely", "must_address": ["legal", "escalate", "human"]},
}


def theory_of_mind(capability: str, config: Dict, query: str = "") -> Dict[str, Any]:
    """Does the config address what the customer REALLY wants?

    EXPLORE: "What does the customer REALLY want?" → enrich LLM prompt.
    DESIGN: "Does this candidate address the real intent?" → score candidate.
    VERIFY: "Does final config serve the real intent?" → final check.
    REFINE: "Did the fix drift away from the real intent?" → prevent drift.
    """
    cap_lower = capability.lower() if capability else ""

    # Find matching intent
    intent_info = _CAPABILITY_INTENT.get(cap_lower)

    # Try partial match from query
    if not intent_info and query:
        query_lower = query.lower()
        for key, info in _CAPABILITY_INTENT.items():
            if key in query_lower:
                intent_info = info
                break

    if not intent_info:
        return {"intent_addressed": True, "missing": [], "score": 0.90, "reason": "No specific intent pattern matched"}

    # Check if config addresses the real intent
    config_text = (
        str(config.get("instructions", "")) + " " +
        str(config.get("restrictions", "")) + " " +
        " ".join(str(c) for c in config.get("capabilities", []))
    ).lower()

    missing = [term for term in intent_info["must_address"] if term not in config_text]

    if not missing:
        return {
            "intent_addressed": True,
            "missing": [],
            "score": 0.95,
            "real_intent": intent_info["real_intent"],
        }

    addressed_count = len(intent_info["must_address"]) - len(missing)
    total = len(intent_info["must_address"])
    score = 0.60 + (0.35 * addressed_count / total)

    return {
        "intent_addressed": len(missing) <= 1,
        "missing": missing,
        "score": round(min(1.0, score), 3),
        "real_intent": intent_info["real_intent"],
    }


# ── 24. FakeVoting — non-LLM voter ─────────────────────────────────

def fake_voting(config: Dict, capability: str, query: str) -> Dict[str, Any]:
    """Simulate 3 independent 'voters' rating the agent config.

    Voter 1 (Customer Perspective): Would the customer be satisfied?
    Voter 2 (Policy Perspective): Is this config policy-compliant?
    Voter 3 (Completeness): Does it cover everything needed?

    Zero cost. Runs alongside 3 LLM voters for 6-voter consensus.
    """
    instructions = str(config.get("instructions", "")).lower()
    restrictions = str(config.get("restrictions", "")).lower()
    capabilities = config.get("capabilities", [])
    if isinstance(capabilities, str):
        try:
            capabilities = json.loads(capabilities)
        except (json.JSONDecodeError, TypeError):
            capabilities = [capabilities]

    # Voter 1: Customer satisfaction
    v1 = 0.75
    empathy_words = ["sorry", "understand", "apologize", "help", "assist"]
    action_words = ["will", "can", "process", "send", "confirm", "verify"]
    if any(w in instructions for w in empathy_words):
        v1 += 0.10
    if any(w in instructions for w in action_words):
        v1 += 0.10
    if len(instructions) < 50:
        v1 -= 0.15

    # Voter 2: Policy compliance
    v2 = 0.75
    if any(w in restrictions for w in ["never", "must not", "always"]):
        v2 += 0.10
    if "escalate" in restrictions:
        v2 += 0.10
    if any(w in restrictions for w in ["guarantee", "100%", "always"]):
        v2 -= 0.10

    # Voter 3: Completeness
    v3 = 0.70
    if len(capabilities) >= 3:
        v3 += 0.10
    if len(instructions) >= 100 and len(restrictions) >= 50:
        v3 += 0.10
    if capability.replace("_", " ").lower() in instructions:
        v3 += 0.10

    v1 = max(0.0, min(1.0, v1))
    v2 = max(0.0, min(1.0, v2))
    v3 = max(0.0, min(1.0, v3))

    voter_scores = [v1, v2, v3]
    avg = sum(voter_scores) / 3.0
    spread = max(voter_scores) - min(voter_scores)

    if spread > 0.20:
        consensus = avg - (spread * 0.3)
    else:
        consensus = avg + 0.03

    return {
        "consensus": round(max(0.0, min(1.0, consensus)), 4),
        "voters": {
            "customer_satisfaction": round(v1, 4),
            "policy_compliance": round(v2, 4),
            "completeness": round(v3, 4),
        },
        "agreed": spread <= 0.15,
        "spread": round(spread, 4),
    }


# ═══════════════════════════════════════════════════════════════════
# L4: AGGREGATION TECHNIQUES (final decision-making)
# ═══════════════════════════════════════════════════════════════════


# ── 25. SelfConsistency — LLM vs non-LLM agreement ──────────────────

def self_consistency(llm_score: float, non_llm_scores: List[float]) -> Dict[str, Any]:
    """Check if LLM voters agree with non-LLM checks.

    If LLM says 0.9 but non-LLM says 0.5 → contradiction!
    """
    if not non_llm_scores:
        return {"consistent": True, "gap": 0.0, "score": 0.90}

    non_llm_avg = sum(non_llm_scores) / len(non_llm_scores)
    gap = abs(llm_score - non_llm_avg)

    if gap > 0.25:
        direction = "LLM_overrates" if llm_score > non_llm_avg else "non_LLM_overrates"
        return {
            "consistent": False,
            "gap": round(gap, 3),
            "direction": direction,
            "llm_score": round(llm_score, 3),
            "non_llm_avg": round(non_llm_avg, 3),
            "score": round(min(llm_score, non_llm_avg), 3),
        }

    return {
        "consistent": True,
        "gap": round(gap, 3),
        "direction": "agreement",
        "score": round((llm_score + non_llm_avg) / 2.0, 3),
    }


# ── 26. ContradictionCheck — LLM overrates vs non-LLM? ──────────────

def contradiction_check(llm_avg: float, non_llm_avg: float) -> Dict[str, Any]:
    """If LLM >> non-LLM, the LLM is overrating. Force REFINE.

    VERIFY: force REFINE when LLM is too generous.
    REFINE: did LLM fix the gap or just hide it?
    """
    gap = abs(llm_avg - non_llm_avg)

    if gap > 0.30:
        return {
            "has_contradiction": True,
            "direction": "LLM_overrates" if llm_avg > non_llm_avg else "non_LLM_overrates",
            "gap": round(gap, 3),
            "llm_avg": round(llm_avg, 3),
            "non_llm_avg": round(non_llm_avg, 3),
            "action": "force_refine",
        }

    return {
        "has_contradiction": False,
        "gap": round(gap, 3),
        "action": "pass",
    }


# ── 27. SufficiencyCheck — does agent actually SOLVE the capability? ─

_NON_AGENT_PHRASES = [
    "contact support",
    "reach out to our team",
    "please call",
    "escalate this",
    "unable to help",
    "i cannot",
    "i can't help",
    "not authorized",
]


def sufficiency_check(capability: str, config: Dict) -> Dict[str, Any]:
    """Does this agent actually SOLVE the detected capability?

    Config looks good but instructions say "contact support for refund"
    → the agent doesn't actually process refunds, just redirects.
    """
    instructions = str(config.get("instructions", "")).lower()
    restrictions = str(config.get("restrictions", "")).lower()
    full_text = instructions + " " + restrictions

    # Check for non-agent phrases in instructions (not restrictions)
    non_agent_found = [p for p in _NON_AGENT_PHRASES if p in instructions]

    if non_agent_found and len(instructions) < 200:
        return {
            "sufficient": False,
            "reason": f"Instructions say '{non_agent_found[0]}' — agent doesn't actually handle this",
            "score": 0.40,
        }

    # Check if capability is addressed in instructions
    cap_words = capability.replace("_", " ").lower().split()
    words_covered = sum(1 for w in cap_words if w in instructions)

    if words_covered == 0:
        return {
            "sufficient": False,
            "reason": f"Instructions don't mention '{capability}' at all",
            "score": 0.30,
        }

    if words_covered < len(cap_words) * 0.5:
        return {
            "sufficient": False,
            "reason": f"Only {words_covered}/{len(cap_words)} capability words addressed in instructions",
            "score": 0.60,
        }

    return {
        "sufficient": True,
        "reason": "Agent addresses the detected capability",
        "score": 0.90,
    }


# ── 28. GapInjection — inject specific fix hints for REFINE ──────────

_FIX_HINTS = {
    "missing empathy": "Add empathy language: 'I understand your frustration', 'I'm sorry to hear about this'",
    "missing amount limit": "Add financial limit to restrictions: 'Max refund $500 without approval'",
    "missing verification": "Add verification step: 'Always verify order number and customer identity before processing'",
    "missing escalation": "Add escalation trigger: 'Escalate to human if customer threatens legal action'",
    "too generic": "Make instructions specific: replace 'help the customer' with concrete steps for this capability",
    "no safety rules": "Add safety restrictions: at minimum include 'Never share customer data' and 'Always verify identity'",
    "weak restrictions": "Strengthen restrictions: add 'Never auto-approve' and 'Always confirm with customer before action'",
    "missing capability": "Add commonly paired capability — see MAKER suggestions",
}


def gap_injection(verify_issues: List[str], capability: str) -> Dict[str, Any]:
    """Analyze verify_issues with keyword matching, inject fix hints.

    REFINE: tell Reflexion exactly what to fix, not just "improve it".
    """
    if not verify_issues:
        return {"hints": [], "hint_count": 0}

    hints = []
    all_issues = " ".join(str(i).lower() for i in verify_issues)

    for trigger, hint in _FIX_HINTS.items():
        trigger_words = trigger.split()
        if any(w in all_issues for w in trigger_words):
            hints.append(hint)

    # Add capability-specific hints
    if "refund" in capability.lower():
        if "amount" not in all_issues:
            hints.append("CRITICAL: Add refund amount limit to restrictions (e.g., 'Max refund $500 without manager approval')")
    if "legal" in capability.lower():
        if "escalate" not in all_issues:
            hints.append("CRITICAL: Legal agents MUST always escalate to human — add mandatory human escalation rule")
    if "prescription" in capability.lower() or "medical" in capability.lower():
        if "medical advice" not in all_issues:
            hints.append("CRITICAL: Medical/prescription agents must include 'Never provide medical advice — refer to healthcare provider'")

    return {
        "hints": hints[:5],
        "hint_count": len(hints),
    }


# ── 29. EscalationRuleEnrichment — auto-append domain rules ──────────

_DOMAIN_RULES = {
    "refund_processing": [
        "Always verify order number and purchase date before processing refund.",
        "Max refund $500 without manager approval.",
        "Always confirm refund amount and timeline with customer.",
    ],
    "billing_inquiry": [
        "Always verify customer identity before discussing billing details.",
        "Never share full credit card numbers.",
        "Escalate suspected fraud immediately.",
    ],
    "complaint_handling": [
        "Always acknowledge the customer's frustration first.",
        "Never dismiss customer concerns.",
        "Always escalate legal threats to human immediately.",
    ],
    "technical_support": [
        "Always start with simplest troubleshooting step.",
        "Escalate after 3 failed resolution attempts.",
        "Never instruct customers to modify system files.",
    ],
    "legal_review": [
        "NEVER provide legal advice — always escalate to human.",
        "Always document legal concerns for compliance review.",
        "Never promise legal outcomes.",
    ],
    "shipping_delivery": [
        "Never promise specific delivery dates for international shipments.",
        "Always verify tracking number before providing status.",
        "Escalate lost packages over $200.",
    ],
    "prescription_refill": [
        "Never provide medical advice or dosage recommendations.",
        "Always refer to healthcare provider for medical questions.",
        "Verify patient identity before any prescription information.",
    ],
    "fraud_security": [
        "Never share security investigation details with the caller.",
        "Always escalate suspected fraud to security team.",
        "Never confirm or deny account details to unverified callers.",
    ],
}


def escalation_rule_enrichment(capability: str, current_restrictions: str) -> Dict[str, Any]:
    """Auto-append domain-specific escalation rules to restrictions.

    REFINE: add rules that LLM might forget.
    """
    rules = _DOMAIN_RULES.get(capability, [])
    if not rules:
        return {"added_rules": [], "rule_count": 0}

    # Only add rules not already present
    rest_lower = current_restrictions.lower() if current_restrictions else ""
    new_rules = []
    for rule in rules:
        # Check if key concept from rule already exists
        rule_key = rule.split(".")[0].lower()[:30]
        if rule_key not in rest_lower:
            new_rules.append(rule)

    return {
        "added_rules": new_rules,
        "rule_count": len(new_rules),
    }


# ── 30. MetaLearner — learn from past Builder runs ──────────────────

def meta_learner_adjust(
    capability: str,
    past_builder_results: List[Dict],
) -> Dict[str, Any]:
    """Adjust expectations based on past Builder runs.

    If "legal_review" agents always needed 2+ refine loops,
    we should expect that and plan accordingly.
    """
    if not past_builder_results:
        return {"adjustment": 0.0, "expected_loops": 1, "reason": "No past data"}

    # Filter to same capability
    same_cap = [r for r in past_builder_results if r.get("capability", "").lower() == capability.lower()]

    if len(same_cap) < 2:
        return {"adjustment": 0.0, "expected_loops": 1, "reason": "Not enough past data for this capability"}

    # Calculate average refine iterations
    avg_loops = sum(r.get("refine_iterations", 1) for r in same_cap) / len(same_cap)
    avg_score = sum(r.get("refine_quality_score", 0.8) for r in same_cap) / len(same_cap)

    adjustment = 0.0
    if avg_score > 0.95:
        adjustment = -0.03  # system likely overrating
    elif avg_score < 0.80:
        adjustment = 0.05  # system underrating, be more lenient

    return {
        "adjustment": adjustment,
        "expected_loops": max(1, round(avg_loops)),
        "past_avg_score": round(avg_score, 3),
        "sample_size": len(same_cap),
        "reason": f"Past {len(same_cap)} builds for '{capability}': avg_loops={avg_loops:.1f}, avg_score={avg_score:.3f}",
    }


# ── 31. ContextualCompression — remove filler from config ───────────

_FILLER_PHRASES = [
    "please note that",
    "it is important to",
    "in order to",
    "as a general rule",
    "keep in mind that",
    "it should be noted",
    "for your information",
]


def contextual_compression(text: str) -> Dict[str, Any]:
    """Remove repetitive filler from instructions/restrictions.

    REFINE: tighter config = less ambiguity for the agent.
    """
    if not text:
        return {"compressed": text, "removed_count": 0}

    compressed = text
    removed = 0

    # Remove filler phrases
    for phrase in _FILLER_PHRASES:
        while phrase in compressed.lower():
            # Case-insensitive removal
            idx = compressed.lower().find(phrase)
            compressed = compressed[:idx] + compressed[idx + len(phrase):]
            removed += 1

    # Remove double spaces
    while "  " in compressed:
        compressed = compressed.replace("  ", " ")

    # Remove trailing/leading whitespace per sentence
    compressed = ". ".join(s.strip() for s in compressed.split(".") if s.strip())

    return {
        "compressed": compressed.strip(),
        "removed_count": removed,
        "original_len": len(text),
        "compressed_len": len(compressed.strip()),
    }


# ── 32. Escalation — auto-escalate on quality fail ──────────────────

def should_escalate(
    quality_passed: bool,
    refine_iterations: int,
    max_iterations: int = 3,
    contradiction: Optional[Dict] = None,
    sufficiency: Optional[Dict] = None,
) -> Dict[str, Any]:
    """If Builder can't get score ≥ 0.8 after max loops → flag for human.

    REFINE: don't ship a bad agent.
    """
    reasons = []

    if not quality_passed and refine_iterations >= max_iterations:
        reasons.append(f"Quality still below threshold after {refine_iterations} refine iterations")

    if contradiction and contradiction.get("has_contradiction"):
        reasons.append(
            f"LLM vs non-LLM gap {contradiction.get('gap', 0):.2f} "
            f"({contradiction.get('direction', 'unknown')})"
        )

    if sufficiency and not sufficiency.get("sufficient", True):
        reasons.append(f"Agent doesn't solve the capability: {sufficiency.get('reason', 'unknown')}")

    return {
        "escalate": len(reasons) > 0,
        "reasons": reasons,
    }


# ── 33. RuleBasedAction — per-capability structural rules ───────────

_CAPABILITY_RULES = {
    "refund_processing": {
        "must_contain": ["refund", "amount"],
        "should_contain": ["verify", "policy"],
        "description": "Refund agent must mention amount and verification",
    },
    "billing_inquiry": {
        "must_contain": ["charge", "billing"],
        "should_contain": ["verify", "explain"],
        "description": "Billing agent must reference charges and verification",
    },
    "technical_support": {
        "must_contain": ["step", "fix"],
        "should_contain": ["troubleshoot", "escalate"],
        "description": "Technical agent must include steps and escalation",
    },
    "complaint_handling": {
        "must_contain": ["sorry", "apologize"],
        "should_contain": ["resolve", "escalate"],
        "description": "Complaint agent must show empathy",
    },
    "legal_review": {
        "must_contain": ["escalate", "human"],
        "should_contain": ["legal", "document"],
        "description": "Legal agent MUST escalate to human",
    },
    "shipping_delivery": {
        "must_contain": ["tracking", "status"],
        "should_contain": ["delivery", "estimate"],
        "description": "Shipping agent must mention tracking",
    },
}


def rule_based_check(config: Dict, capability: str) -> Dict[str, Any]:
    """Per-capability structural rules that LLM cannot override.

    VERIFY + REFINE: hard business rules.
    """
    rules = _CAPABILITY_RULES.get(capability)
    if not rules:
        return {"passed": True, "violations": [], "description": "No capability-specific rules"}

    full_text = (
        str(config.get("instructions", "")) + " " +
        str(config.get("restrictions", ""))
    ).lower()

    violations = []
    for term in rules["must_contain"]:
        if term not in full_text:
            violations.append(f"Missing required term: '{term}'")

    missing_recommended = []
    for term in rules["should_contain"]:
        if term not in full_text:
            missing_recommended.append(term)

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "missing_recommended": missing_recommended,
        "description": rules["description"],
    }
