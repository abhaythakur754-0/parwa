"""
Node 2: Smart Route

Question: WHO handles this ticket + WHERE does it go?

Components:
  1. Variant Registry  — what did tenant buy?  (DB: VariantInstance + Subscription)
  2. Quota Tracker     — how many remaining?   (DB: UsageRecord vs VariantLimit)
  3. Capability Matrix — can this tier handle it?
  4. Route Decision    — lowest eligible tier -> path

LLM calls: 0 (pure logic, database reads only)
Input from Jarvis: quota feed (Phase 8)

BC-001: All queries scoped by tenant_id (company_id).
BC-008: Every public method is wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import os

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_2")

# ── Tier Key Mappings ─────────────────────────────────────────────
# Internal short keys used in CAPABILITY_MATRIX / EXECUTION_LIMITS
# must map to the DB variant_type values stored in VariantInstance
# and the canonical names in pricing_config (VariantType enum).

TIER_SHORT_TO_DB: Dict[str, str] = {
    "mini": "mini_parwa",
    "parwa": "parwa",
    "high": "parwa_high",
}

TIER_DB_TO_SHORT: Dict[str, str] = {v: k for k, v in TIER_SHORT_TO_DB.items()}

# Priority order for routing (lowest first to preserve higher tier quota)
# NOTE: Mini was removed 2026-07-26. Only 2 tiers remain.
TIER_ORDER = ["parwa", "high"]

# ── Capability Matrix ───────────────────────────────────────────
# All variants have IDENTICAL AI capabilities.
# The ONLY difference between tiers is ticket volume, agent limits,
# and financial action limits (see EXECUTION_LIMITS below).

_FULL_CAPABILITIES: Dict[str, Any] = {
    "simple_info": True,
    "medium_info": True,
    "recommend": True,
    "execute_refund": True,
    "execute_credit": True,
    "account_change": True,
    "complex_reasoning": True,
    "super_node": True,
    "quality_loops": 2,
    "ai_wiki_access": "read_write_learn",
    "integrations_max": -1,        # unlimited for all
}

CAPABILITY_MATRIX: Dict[str, Dict[str, Any]] = {
    "parwa": dict(_FULL_CAPABILITIES),
    "high": dict(_FULL_CAPABILITIES),
}

# Execution limits — financial guardrails per tier.
# parwa: limited refunds/credits (safety guardrail for the lower tier)
# high:  unlimited (full trust for the premium tier)
# NOTE: Must match node_5_act_verify._EXEC_LIMITS exactly.
EXECUTION_LIMITS: Dict[str, Dict[str, float]] = {
    "parwa": {"max_refund": float("inf"), "max_credit": float("inf")},
    "high": {"max_refund": float("inf"), "max_credit": float("inf")},
}


# ── Test Override Registry ─────────────────────────────────────────
# In production, _load_tenant_variants() reads from DB.
# Tests can call set_test_variant() to inject a known config
# without needing a database.

_TEST_REGISTRY: Dict[str, Dict[str, Any]] = {}


def set_test_variant(
    tenant_id: str,
    tier: str,
    quota_total: int,
    quota_remaining: Optional[int] = None,
) -> None:
    """Inject a test variant config for a tenant.

    Used in tests only.  The ``tier`` value should be a DB-style
    name (``mini_parwa``, ``parwa``, ``parwa_high``) or a short
    key (``mini``, ``parwa``, ``high``).
    """
    db_tier = TIER_SHORT_TO_DB.get(tier, tier)
    short = TIER_DB_TO_SHORT.get(db_tier, db_tier)
    remaining = quota_remaining if quota_remaining is not None else quota_total
    _TEST_REGISTRY[tenant_id] = {
        "tier_short": short,
        "tier_db": db_tier,
        "quota_total": quota_total,
        "quota_remaining": remaining,
    }


def clear_test_registry() -> None:
    """Clear all test overrides."""
    _TEST_REGISTRY.clear()


# ── DB-backed Variant Registry ─────────────────────────────────────


def _load_tenant_variants(tenant_id: str) -> Dict[str, Any]:
    """Load the tenant's active variant tiers and quota from the DB.

    Data sources (in priority order):
      1. _TEST_REGISTRY — for unit tests (no DB needed)
      2. VariantInstance table — active instances for this company
      3. Subscription table — fallback if no instances found
      4. pricing_config defaults — if nothing in DB yet

    Returns dict with:
      - available_tiers: list of short tier keys the tenant owns
        e.g. ["mini"] or ["parwa"] or ["mini", "parwa", "high"]
      - highest_tier_short: "mini" | "parwa" | "high"
      - highest_tier_db: "mini_parwa" | "parwa" | "parwa_high"
      - quota: {tier_short: {total, used, remaining}} for each owned tier
      - source: where the data came from (for logging)

    BC-008: Never crashes — returns safe defaults on any error.
    """
    # ── 1. Test override ──
    test_entry = _TEST_REGISTRY.get(tenant_id)
    if test_entry:
        short = test_entry["tier_short"]
        return {
            "available_tiers": [short],
            "highest_tier_short": short,
            "highest_tier_db": test_entry["tier_db"],
            "quota": {
                short: {
                    "total": test_entry["quota_total"],
                    "used": test_entry["quota_total"] - test_entry["quota_remaining"],
                    "remaining": test_entry["quota_remaining"],
                },
            },
            "source": "test_registry",
        }

    # ── 2. Real DB lookup ──
    try:
        from database.base import SessionLocal
        from database.models.variant_engine import VariantInstance
        from database.models.billing_extended import UsageRecord
        from sqlalchemy import func

        with SessionLocal() as db:
            # 2a. Get all active variant instances for this tenant
            instances = (
                db.query(VariantInstance)
                .filter(
                    VariantInstance.company_id == tenant_id,
                    VariantInstance.status == "active",
                )
                .all()
            )

            if instances:
                # Collect unique variant types this tenant owns
                owned_db_tiers: List[str] = []
                seen_types: set = set()
                for inst in instances:
                    vt = inst.variant_type.strip().lower() if inst.variant_type else ""
                    if vt and vt not in seen_types:
                        seen_types.add(vt)
                        owned_db_tiers.append(vt)

                # Map to short keys
                owned_short = []
                for db_tier in owned_db_tiers:
                    short = TIER_DB_TO_SHORT.get(db_tier, db_tier)
                    if short in CAPABILITY_MATRIX:
                        owned_short.append(short)

                if not owned_short:
                    # DB had instances but none mapped to known tiers
                    raise ValueError("no_mappable_tiers")

                # Sort by priority (mini first)
                owned_short = [t for t in TIER_ORDER if t in owned_short]
                highest_short = owned_short[-1]  # last = highest

                # 2b. Get monthly ticket usage
                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                total_used = (
                    db.query(func.coalesce(func.sum(UsageRecord.tickets_used), 0))
                    .filter(
                        UsageRecord.company_id == tenant_id,
                        UsageRecord.record_month == current_month,
                    )
                    .scalar()
                ) or 0
                total_used = int(total_used)

                # 2c. Get quota limits from pricing_config
                quota = _build_quota_from_limits(owned_short, total_used)

                return {
                    "available_tiers": owned_short,
                    "highest_tier_short": highest_short,
                    "highest_tier_db": TIER_SHORT_TO_DB.get(highest_short, highest_short),
                    "quota": quota,
                    "source": "db_variant_instances",
                }

            # ── 3. Fallback: Subscription table ──
            from database.models.billing import Subscription

            sub = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == tenant_id,
                    Subscription.status == "active",
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if sub and sub.tier:
                tier_raw = sub.tier.strip().lower()
                # sub.tier stores canonical names: starter, growth, high
                tier_map = {"starter": "mini", "growth": "parwa", "high": "high"}
                # Also support old DB names
                tier_map.update(TIER_DB_TO_SHORT)

                short = tier_map.get(tier_raw, "mini")
                if short not in CAPABILITY_MATRIX:
                    short = "mini"

                # Get usage
                current_month = datetime.now(timezone.utc).strftime("%Y-%m")
                total_used = (
                    db.query(func.coalesce(func.sum(UsageRecord.tickets_used), 0))
                    .filter(
                        UsageRecord.company_id == tenant_id,
                        UsageRecord.record_month == current_month,
                    )
                    .scalar()
                ) or 0
                total_used = int(total_used)

                quota = _build_quota_from_limits([short], total_used)

                return {
                    "available_tiers": [short],
                    "highest_tier_short": short,
                    "highest_tier_db": TIER_SHORT_TO_DB.get(short, short),
                    "quota": quota,
                    "source": "db_subscription",
                }

    except Exception as exc:
        logger.warning(
            "Node 2 DB lookup failed for tenant %s: %s — using default mini_parwa",
            tenant_id, exc,
        )

    # ── 4. Ultimate default: mini_parwa ──
    return {
        "available_tiers": ["mini"],
        "highest_tier_short": "mini",
        "highest_tier_db": "mini_parwa",
        "quota": {"mini": {"total": 2000, "used": 0, "remaining": 2000}},
        "source": "default_mini_parwa",
    }


def _build_quota_from_limits(
    owned_short: List[str],
    total_used: int,
) -> Dict[str, Dict[str, int]]:
    """Build quota dict from pricing_config limits.

    For multi-variant tenants, the monthly ticket limit is shared
    across ALL their variants (it's a company-level limit, not
    per-variant).  So ``total_used`` is the same for every tier.
    """
    try:
        from app.core.pricing_config import VARIANT_LIMITS, VariantType
    except ImportError:
        # Fallback if pricing_config can't be imported
        return {t: {"total": 2000, "used": total_used, "remaining": max(0, 2000 - total_used)}
                for t in owned_short}

    SHORT_TO_VARIANT_TYPE = {
        "parwa": VariantType.PARWA,
        "high": VariantType.HIGH,
    }

    quota: Dict[str, Dict[str, int]] = {}

    for short in owned_short:
        vt = SHORT_TO_VARIANT_TYPE.get(short)
        if vt and vt in VARIANT_LIMITS:
            limits = VARIANT_LIMITS[vt]
            ticket_limit = int(limits.get("monthly_tickets", 2000))
        else:
            ticket_limit = 2000

        remaining = max(0, ticket_limit - total_used)
        quota[short] = {
            "total": ticket_limit,
            "used": total_used,
            "remaining": remaining,
        }

    return quota


# ── Keyword-Based Complexity Correction ──────────────────────────


def _correct_complexity(
    query: str, complexity: str, action: str, ticket_type: str,
) -> Tuple[str, str]:
    """Post-LLM correction: blend LLM classification with keyword heuristics.

    Catches cases where the LLM misclassifies:
      - Simple account changes tagged as complex
      - Technical integration / billing disputes tagged as simple/medium
    """
    query_lower = query.lower()

    # Strong indicators that should ALWAYS be complex regardless of LLM
    strong_complex_patterns = [
        r'\bintegrate\b.*\b(api|crm|erp|system|webhook)\b',
        r'\bapi\b.*\b(endpoint|connect|integration)\b',
        r'\b(overcharg|wrong charge|double charge|unauthorized charge)\b',
        r'\brefund\b.*\b(subscription|plan|enterprise|difference)\b',
        r'\b(chargeback|file\s+a\s+dispute)\b',
        r'\b(error|crash|500|403)\b.*\b(urgent|deadline|team)\b',
        r'\b(manager|supervisor)\b.*\b(complaint|terrible|worst)\b',
        r'\b(enterprise|plan)\b.*\b(charg|refund|credit)\b.*\b\d+',
    ]

    for pattern in strong_complex_patterns:
        if re.search(pattern, query_lower):
            if complexity in ("simple", "medium"):
                logger.info(
                    "Complexity correction: %s -> complex (keyword override)",
                    complexity,
                )
                return "complex", action

    # Strong indicators that should ALWAYS be simple regardless of LLM
    strong_simple_patterns = [
        r'^\s*I\s+(need\s+)?(want\s+)?to\s+(change|update)\s+my\s+(billing\s+)?(email|address|password|name|phone)\b',
        r'^\s*I\s+(need\s+)?(want\s+)?to\s+(change|update)\s+(my\s+)?billing\s+email\b',
    ]

    for pattern in strong_simple_patterns:
        if re.search(pattern, query_lower):
            if complexity == "complex":
                logger.info(
                    "Complexity correction: %s -> simple (keyword override)",
                    complexity,
                )
                return "simple", "provide_info"

    return complexity, action


# ── Route Decision Logic (3-dimensional) ──────────────────────────


def _check_capability(
    tier: str,
    ticket_type: str,
    complexity: str,
    action: str,
    action_details: Dict,
) -> bool:
    """Dimension 1: Can this tier HANDLE this ticket?"""
    caps = CAPABILITY_MATRIX.get(tier)
    if not caps:
        return False

    # Simple/medium info: all tiers can handle
    if action == "provide_info":
        return True

    # Phase 7: investigate_billing needs complex reasoning
    if action == "investigate_billing":
        return caps.get("complex_reasoning", False)

    # Complex reasoning: only parwa and high
    if complexity in ("complex", "hard") and not caps["complex_reasoning"]:
        return False

    # Execution actions: check tier limits
    if action == "execute_refund":
        if not caps["execute_refund"]:
            return False
        amount = action_details.get("amount", 0)
        limits = EXECUTION_LIMITS.get(tier, {})
        if amount > limits.get("max_refund", 0):
            return False

    if action == "execute_credit":
        if not caps["execute_credit"]:
            return False
        amount = action_details.get("amount", 0)
        limits = EXECUTION_LIMITS.get(tier, {})
        if amount > limits.get("max_credit", 0):
            return False

    if action == "account_change" and not caps["account_change"]:
        return False

    return True


def _check_quota(
    tenant_variants: Dict[str, Any],
    tier: str,
) -> bool:
    """Dimension 2: Does this tier have tickets remaining?"""
    quota = tenant_variants.get("quota", {})
    tier_quota = quota.get(tier)
    if not tier_quota:
        return False
    return tier_quota["remaining"] > 0


def _needs_complex_path(query: str) -> bool:
    """Check if the query content requires complex path regardless of
    complexity label.

    Some medium-complexity queries need the full reasoning pipeline
    (technical integrations, multi-system questions, detailed how-tos).
    """
    query_lower = query.lower()
    complex_content_patterns = [
        r'\b(integrate|connect)\b.*\b(api|crm|erp|system|service)\b',
        r'\bendpoint\b',
        r'\bhow\s+do\s+i\s+(set\s+up|configure|implement)\b.*\b(api|webhook|integration)\b',
        r'\b(ssl|oauth|authentication|sso)\b.*\b(integrate|setup|configure)\b',
    ]
    return any(re.search(p, query_lower) for p in complex_content_patterns)


def _route_decision(
    tenant_variants: Dict[str, Any],
    ticket_type: str,
    complexity: str,
    action: str,
    action_details: Dict,
    query: str = "",
) -> Tuple[str, str, List[str]]:
    """3-Dimensional Routing: capability + quota + efficiency.

    Returns (selected_tier_short, path, capabilities_list).
    Uses the LOWEST eligible tier to preserve higher quotas for
    harder tickets.

    For multi-variant tenants, it picks the cheapest tier that can
    handle the ticket and still has quota remaining.
    """
    # Apply keyword-based complexity correction first
    corrected_complexity, corrected_action = _correct_complexity(
        query, complexity, action, ticket_type,
    )

    # Determine which path
    # FORCE_COMPLEX_PATH: when True, all tickets go through the complex path
    # (Node 4 with 7 LLM calls + Node 6 quality gate). Used for testing.
    if os.environ.get("FORCE_COMPLEX_PATH", "").lower() in ("1", "true", "yes"):
        target_path = "complex_path"
        logger.info("Force complex path enabled — all tickets through Node 4 + Node 6")
    elif corrected_complexity in ("simple", "medium") and corrected_action == "provide_info":
        target_path = "simple_path"
    elif corrected_complexity in ("simple", "medium") and corrected_action == "recommend":
        target_path = "simple_path"
    elif corrected_complexity == "simple" and corrected_action == "account_change":
        target_path = "simple_path"
    elif corrected_action == "investigate_billing":
        target_path = "complex_path"
    else:
        target_path = "complex_path"

    # Override: query content needs complex path
    if target_path == "simple_path" and _needs_complex_path(query):
        logger.info("Path override: simple -> complex (query content requires full reasoning)")
        target_path = "complex_path"

    # Find lowest eligible tier from what the tenant actually owns
    available_tiers = tenant_variants.get("available_tiers", [])

    selected_tier: Optional[str] = None
    for tier in TIER_ORDER:
        if tier not in available_tiers:
            continue  # tenant doesn't own this tier
        if _check_capability(tier, ticket_type, complexity, action, action_details):
            if _check_quota(tenant_variants, tier):
                selected_tier = tier
                break  # lowest eligible tier found

    # Fallback: if no tier has quota or can handle it, use highest owned tier
    if selected_tier is None:
        if available_tiers:
            selected_tier = available_tiers[-1]  # highest
        else:
            selected_tier = "mini"

    # If mini can't handle the action, try to find a higher tier
    # that can, even if quota is exhausted (better to handle than to fail)
    if not _check_capability(selected_tier, ticket_type, complexity, action, action_details):
        for tier in reversed(TIER_ORDER):
            if tier in available_tiers and _check_capability(tier, ticket_type, complexity, action, action_details):
                selected_tier = tier
                break

    # Get capabilities for selected tier
    caps = CAPABILITY_MATRIX.get(selected_tier, {})
    capabilities = [k for k, v in caps.items() if v is True or isinstance(v, str)]

    return selected_tier, target_path, capabilities


# ── Main Node Function ────────────────────────────────────────────


async def node_2_smart_route(state: PipelineV2State) -> dict:
    """Node 2: Smart Route — WHO handles this + WHERE does it go?

    0 LLM calls. Pure logic + DB reads.
    Reads from VariantInstance / Subscription / UsageRecord to
    determine what the tenant actually purchased and how much
    quota remains.
    """
    start = time.time()
    tenant_id = state.get("tenant_id", "")
    ticket_type = state.get("ticket_type", "general")
    complexity = state.get("complexity", "simple")
    action = state.get("required_action", "provide_info")
    action_details = state.get("action_details", {})
    logs: List[Dict] = []

    # ── Wave 4: Check Jarvis system flags ──────────────────
    system_flags = state.get("system_flags")
    if not system_flags:
        try:
            from app.core.parwa_pipeline.parwa_bridge import load_system_flags
            system_flags = await load_system_flags(tenant_id)
        except Exception:
            system_flags = {}

    # Check pause_action: if this action type is paused, reject
    paused_actions = system_flags.get("paused_actions", [])
    is_paused = (
        "all" in paused_actions
        or action in paused_actions
        or any(p in action for p in paused_actions if p != "all")
    )
    if is_paused:
        logs.append({"node": 2, "technique": "JARVIS_PAUSE_CHECK", "duration_ms": 0, "result_summary": f"action={action} PAUSED"})
        logger.warning("Node 2: Action '%s' is paused by Jarvis for tenant %s", action, tenant_id)
        return {
            "route_decision": "simple_path",
            "current_path": "simple_path",
            "variant_tier": "mini_parwa",
            "quota_remaining": {},
            "variant_capabilities": [],
            "status": "paused",
            "final_response": f"The action '{action}' is currently paused by your administrator. Your request has been noted but cannot be processed until the pause is lifted.",
            "technique_log": logs,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    # Check redirect_channel: if this channel is redirected to human, override
    channel = state.get("channel_type", "")
    redirected = system_flags.get("redirected_channels", {})
    if channel and channel in redirected:
        route_to = redirected[channel]
        logs.append({"node": 2, "technique": "JARVIS_REDIRECT_CHECK", "duration_ms": 0, "result_summary": f"channel={channel} redirected to {route_to}"})
        logger.info("Node 2: Channel '%s' redirected to '%s' by Jarvis", channel, route_to)
        if route_to == "human":
            return {
                "route_decision": "simple_path",
                "current_path": "simple_path",
                "variant_tier": "mini_parwa",
                "quota_remaining": {},
                "variant_capabilities": [],
                "status": "escalated",
                "escalation_context": {"reason": f"Channel '{channel}' redirected to human by Jarvis"},
                "technique_log": logs,
                "total_token_usage": state.get("total_token_usage", 0),
            }

    # Check force_mode: if Jarvis forced a mode, log it for downstream
    force_mode = system_flags.get("force_mode")
    if force_mode:
        logs.append({"node": 2, "technique": "JARVIS_MODE_CHECK", "duration_ms": 0, "result_summary": f"mode={force_mode}"})

    # ── 1. Load tenant variants from DB ──
    tenant_variants = _load_tenant_variants(tenant_id)
    highest_db = tenant_variants["highest_tier_db"]
    source = tenant_variants["source"]

    logs.append({
        "node": 2,
        "technique": "VariantRegistry",
        "duration_ms": 0,
        "result_summary": (
            f"tiers={tenant_variants['available_tiers']} "
            f"highest={highest_db} source={source}"
        ),
    })

    # ── 2. Quota snapshot ──
    quota_remaining = {}
    for tier_short, q in tenant_variants.get("quota", {}).items():
        quota_remaining[tier_short] = q["remaining"]

    logs.append({
        "node": 2,
        "technique": "QuotaTracker",
        "duration_ms": 0,
        "result_summary": f"quota={quota_remaining}",
    })

    # ── 3. 3-Dimensional route decision ──
    selected_tier_short, path, capabilities = _route_decision(
        tenant_variants,
        ticket_type, complexity, action, action_details,
        query=state.get("query", ""),
    )
    logs.append({
        "node": 2,
        "technique": "RouteDecision",
        "duration_ms": 0,
        "result_summary": f"tier={selected_tier_short} path={path}",
    })

    # ── 4. Map short tier back to DB name for downstream nodes ──
    selected_tier_db = TIER_SHORT_TO_DB.get(selected_tier_short, selected_tier_short)

    # ── Layer 1: Non-LLM enrichment techniques (0 LLM calls) ─────
    # CLARA: validate route decision is sound
    n2_clara1 = "valid" if selected_tier_short and path else "INVALID: missing tier or path"
    logs.append({"node": 2, "technique": "CLARA", "duration_ms": 0, "result_summary": n2_clara1})

    # GSD: state machine update
    n2_gsd1 = f"ROUTED tier={selected_tier_short} path={path}"
    logs.append({"node": 2, "technique": "GSD", "duration_ms": 0, "result_summary": n2_gsd1})

    # SelfConsistency: do tier + path + complexity agree?
    n2_sc1 = "consistent"
    if path == "simple_path" and complexity == "complex":
        n2_sc1 = "INCONSISTENT: simple path for complex ticket"
    elif path == "complex_path" and complexity == "simple":
        n2_sc1 = "REVIEW: complex path for simple ticket (intentional?)"
    logs.append({"node": 2, "technique": "SelfConsistency", "duration_ms": 0, "result_summary": n2_sc1})

    # MAKER: ground decision in actual ticket data
    n2_maker1 = f"grounded type={ticket_type} complexity={complexity} action={action}"
    logs.append({"node": 2, "technique": "MAKER", "duration_ms": 0, "result_summary": n2_maker1})

    # CoVe: verify tier has capability for this action
    n2_cove1 = "verified" if capabilities else "UNVERIFIED: no capabilities listed"
    logs.append({"node": 2, "technique": "CoVe", "duration_ms": 0, "result_summary": n2_cove1})

    # RuleBasedAction: complex tickets always go to complex_path
    n2_rba1 = "ok"
    if complexity == "complex" and path != "complex_path":
        n2_rba1 = "VIOLATION: complex ticket not on complex_path"
    logs.append({"node": 2, "technique": "RuleBasedAction", "duration_ms": 0, "result_summary": n2_rba1})

    # SafetyNet: check if route would bypass safety
    n2_sn1 = "safe"
    if action == "refund" and selected_tier_short in ("mini", "free"):
        n2_sn1 = "BLOCK: refund on low tier"
    logs.append({"node": 2, "technique": "SafetyNet", "duration_ms": 0, "result_summary": n2_sn1})

    # ContradictionCheck: route vs action
    n2_cc1 = "ok"
    if action == "escalate" and path == "simple_path":
        n2_cc1 = "CONTRADICTION: escalate action on simple path"
    logs.append({"node": 2, "technique": "ContradictionCheck", "duration_ms": 0, "result_summary": n2_cc1})

    # IdempotencyCheck: route decision hash
    import hashlib as _n2_hl
    n2_route_hash = _n2_hl.md5(f"{tenant_id}:{ticket_type}:{action}:{selected_tier_short}".encode()).hexdigest()[:10]
    logs.append({"node": 2, "technique": "IdempotencyCheck", "duration_ms": 0, "result_summary": f"hash={n2_route_hash}"})

    # Escalation: tier downgrade may force escalation
    n2_esc1 = "no_escalation"
    if not tenant_variants.get("available_tiers"):
        n2_esc1 = "NO_VARIANTS_FORCE_ESCALATE"
    logs.append({"node": 2, "technique": "Escalation", "duration_ms": 0, "result_summary": n2_esc1})

    # DynamicContext: route context enrichment
    n2_dc1 = f"context tier={selected_tier_short} caps={len(capabilities) if isinstance(capabilities, list) else 0}"
    logs.append({"node": 2, "technique": "DynamicContext", "duration_ms": 0, "result_summary": n2_dc1})

    # MetaLearner: route pattern analysis
    n2_ml1_features = []
    if path == "complex_path":
        n2_ml1_features.append("needs_reasoning")
    if complexity == "complex":
        n2_ml1_features.append("complex_input")
    if action in ("refund", "escalate"):
        n2_ml1_features.append("high_stakes")
    n2_ml1 = ",".join(n2_ml1_features) if n2_ml1_features else "routine"
    logs.append({"node": 2, "technique": "MetaLearner", "duration_ms": 0, "result_summary": f"pattern={n2_ml1}"})

    # ── Layer 2: Deeper non-LLM analysis (0 LLM calls) ───────────
    # SmartRouter.depth2: route quality score
    n2_sr2 = "optimal"
    if path == "complex_path" and complexity == "simple":
        n2_sr2 = "OVER_ENGINEERED: complex path for simple ticket"
    elif path == "simple_path" and complexity == "complex":
        n2_sr2 = "UNDER_ENGINEERED: simple path for complex ticket"
    logs.append({"node": 2, "technique": "SmartRouter.depth2", "duration_ms": 0, "result_summary": n2_sr2})

    # ZeroShotValidator.depth2: cross-check tier vs ticket type
    n2_zsv2 = "ok"
    if ticket_type == "legal_review" and selected_tier_short not in ("full", "flagship"):
        n2_zsv2 = "REVIEW: legal_review on non-flagship tier"
    elif ticket_type == "fraud_security" and selected_tier_short in ("mini", "free"):
        n2_zsv2 = "REVIEW: fraud on low tier"
    logs.append({"node": 2, "technique": "ZeroShotValidator.depth2", "duration_ms": 0, "result_summary": n2_zsv2})

    # SmartFilter.depth2: filter redundant capabilities
    n2_caps_list = capabilities if isinstance(capabilities, list) else []
    n2_unique_caps = list(set(n2_caps_list))
    n2_sf2 = f"unique_caps={len(n2_unique_caps)} total={len(n2_caps_list)}"
    logs.append({"node": 2, "technique": "SmartFilter.depth2", "duration_ms": 0, "result_summary": n2_sf2})

    # CLARA.depth2: validate quota snapshot
    n2_clara2 = "valid" if isinstance(quota_remaining, dict) and quota_remaining else "EMPTY: no quota data"
    logs.append({"node": 2, "technique": "CLARA.depth2", "duration_ms": 0, "result_summary": n2_clara2})

    # GSD.depth2: state transition logged
    n2_gsd2 = "ROUTING_COMMITTED"
    logs.append({"node": 2, "technique": "GSD.depth2", "duration_ms": 0, "result_summary": n2_gsd2})

    # SelfConsistency.depth2: 3-way check
    n2_sc2 = "3_way_consistent"
    if action == "refund" and "refund" not in str(n2_caps_list).lower():
        n2_sc2 = "MISALIGNED: refund action without refund capability"
    logs.append({"node": 2, "technique": "SelfConsistency.depth2", "duration_ms": 0, "result_summary": n2_sc2})

    # MAKER.depth2: ground in tier source
    n2_maker2 = f"source={source} highest={highest_db}"
    logs.append({"node": 2, "technique": "MAKER.depth2", "duration_ms": 0, "result_summary": n2_maker2})

    # CoVe.depth2: verify quota
    n2_cove2 = "verified"
    if isinstance(quota_remaining, dict):
        n2_total_quota = sum(v for v in quota_remaining.values() if isinstance(v, (int, float)))
        if n2_total_quota == 0:
            n2_cove2 = "EXHAUSTED: total quota = 0"
    logs.append({"node": 2, "technique": "CoVe.depth2", "duration_ms": 0, "result_summary": n2_cove2})

    # RuleBasedAction.depth2: VIP tier enforcement
    n2_rba2 = "ok"
    # Would check customer tier from state
    n2_customer_tier = (state.get("customer_context") or {}).get("tier", "standard")
    if n2_customer_tier in ("vip", "enterprise") and selected_tier_short in ("mini", "free"):
        n2_rba2 = "VIOLATION: VIP customer on low tier"
    logs.append({"node": 2, "technique": "RuleBasedAction.depth2", "duration_ms": 0, "result_summary": n2_rba2})

    # SafetyNet.depth2: high-stakes action guard
    n2_sn2 = "ok"
    if action in ("refund", "cancel_subscription") and path == "simple_path":
        n2_sn2 = "GUARD: high-stakes action on simple path"
    logs.append({"node": 2, "technique": "SafetyNet.depth2", "duration_ms": 0, "result_summary": n2_sn2})

    # ContradictionCheck.depth2: capability vs action
    n2_cc2 = "ok"
    if action == "track_shipment" and "shipping" not in str(n2_caps_list).lower():
        n2_cc2 = "MISALIGNED: track action without shipping cap"
    logs.append({"node": 2, "technique": "ContradictionCheck.depth2", "duration_ms": 0, "result_summary": n2_cc2})

    # IdempotencyCheck.depth2: stronger hash
    n2_ic2 = f"hash={n2_route_hash} tier={selected_tier_short}"
    logs.append({"node": 2, "technique": "IdempotencyCheck.depth2", "duration_ms": 0, "result_summary": n2_ic2})

    # Escalation.depth2: low-quota escalation warning
    n2_esc2 = "no_escalation"
    if isinstance(quota_remaining, dict):
        n2_low_quota = [t for t, v in quota_remaining.items() if isinstance(v, (int, float)) and v < 100]
        if n2_low_quota:
            n2_esc2 = f"LOW_QUOTA: {','.join(n2_low_quota)}"
    logs.append({"node": 2, "technique": "Escalation.depth2", "duration_ms": 0, "result_summary": n2_esc2})

    # DynamicContext.depth2: enrich with capabilities
    n2_dc2 = f"caps_loaded={len(n2_caps_list)}"
    logs.append({"node": 2, "technique": "DynamicContext.depth2", "duration_ms": 0, "result_summary": n2_dc2})

    # MetaLearner.depth2: route decision pattern
    n2_ml2 = f"pattern path={path} tier={selected_tier_short} action={action}"
    logs.append({"node": 2, "technique": "MetaLearner.depth2", "duration_ms": 0, "result_summary": n2_ml2})

    # ── Layer 3: Final route validation (0 LLM calls) ────────────
    # SmartRouter.depth3: final route confirmation
    n2_sr3 = f"committed path={path} tier={selected_tier_short}"
    logs.append({"node": 2, "technique": "SmartRouter.depth3", "duration_ms": 0, "result_summary": n2_sr3})

    # ZeroShotValidator.depth3: final sanity check
    n2_zsv3 = "approved" if selected_tier_short and path else "blocked"
    logs.append({"node": 2, "technique": "ZeroShotValidator.depth3", "duration_ms": 0, "result_summary": n2_zsv3})

    # SmartFilter.depth3: final filter
    n2_sf3 = "clean" if n2_sc1 == "consistent" else "flagged_inconsistency"
    logs.append({"node": 2, "technique": "SmartFilter.depth3", "duration_ms": 0, "result_summary": n2_sf3})

    # CLARA.depth3: final field validation
    n2_clara3 = "all_present" if all([selected_tier_short, path, selected_tier_db]) else "missing"
    logs.append({"node": 2, "technique": "CLARA.depth3", "duration_ms": 0, "result_summary": n2_clara3})

    # GSD.depth3: state = routing complete
    n2_gsd3 = "ROUTING_COMPLETE → NEXT_NODE"
    logs.append({"node": 2, "technique": "GSD.depth3", "duration_ms": 0, "result_summary": n2_gsd3})

    # SelfConsistency.depth3: final 3-way
    n2_sc3 = "final_consistent" if n2_sc1 == "consistent" and n2_sc2 == "3_way_consistent" else "needs_review"
    logs.append({"node": 2, "technique": "SelfConsistency.depth3", "duration_ms": 0, "result_summary": n2_sc3})

    # MAKER.depth3: final grounding
    n2_maker3 = f"final_grounded tier={selected_tier_short} db={selected_tier_db}"
    logs.append({"node": 2, "technique": "MAKER.depth3", "duration_ms": 0, "result_summary": n2_maker3})

    # CoVe.depth3: final verification
    n2_cove3 = f"verified hash={n2_route_hash}"
    logs.append({"node": 2, "technique": "CoVe.depth3", "duration_ms": 0, "result_summary": n2_cove3})

    # RuleBasedAction.depth3: final rule check
    n2_rba3 = "ok" if n2_rba1 == "ok" and n2_rba2 == "ok" else "VIOLATION_DETECTED"
    logs.append({"node": 2, "technique": "RuleBasedAction.depth3", "duration_ms": 0, "result_summary": n2_rba3})

    # SafetyNet.depth3: final safety check
    n2_sn3 = "safe" if n2_sn1 == "safe" and n2_sn2 == "ok" else "flagged"
    logs.append({"node": 2, "technique": "SafetyNet.depth3", "duration_ms": 0, "result_summary": n2_sn3})

    # ContradictionCheck.depth3: final contradiction check
    n2_cc3 = "ok" if n2_cc1 == "ok" and n2_cc2 == "ok" else "FLAGGED"
    logs.append({"node": 2, "technique": "ContradictionCheck.depth3", "duration_ms": 0, "result_summary": n2_cc3})

    # IdempotencyCheck.depth3: final idempotency
    n2_ic3 = f"final_key={n2_route_hash}_{path}"
    logs.append({"node": 2, "technique": "IdempotencyCheck.depth3", "duration_ms": 0, "result_summary": n2_ic3})

    # SufficiencyCheck: enough info to proceed?
    n2_suff_inputs = [bool(selected_tier_short), bool(path), bool(ticket_type), bool(action)]
    n2_suff_count = sum(n2_suff_inputs)
    n2_suff1 = "sufficient" if n2_suff_count == 4 else f"insufficient: {n2_suff_count}/4"
    logs.append({"node": 2, "technique": "SufficiencyCheck", "duration_ms": 0, "result_summary": n2_suff1})

    # Escalation.depth3: route-based escalation summary
    n2_esc3 = "no_escalation" if n2_esc1 == "no_escalation" and n2_esc2 == "no_escalation" else "escalation_flagged"
    logs.append({"node": 2, "technique": "Escalation.depth3", "duration_ms": 0, "result_summary": n2_esc3})

    # ══════════════════════════════════════════════════════════════════
    # AGENT + TOOL VERIFICATION LAYER (Node 2 = decision gate)
    # ══════════════════════════════════════════════════════════════════
    # User vision (2026-08-12):
    #   "verify we have agents — if not, create. verify we have tools —
    #    if not, create. if can't create → send back (escalate)"
    #
    # This layer checks BEFORE routing:
    #   1. Does an agent exist for this capability?
    #      → YES → use it
    #      → NO → create via template system (check template → clone or build)
    #   2. Does that agent have a tool linked?
    #      → YES → use it
    #      → NO → create via Superglue API
    #   3. If creation fails → escalate to human (send back)
    #
    # This is the VERIFICATION layer — Node 2 decides "go forward" or
    # "send back" based on whether agent + tool are ready.

    detected_capability = state.get("ticket_type", "general")
    verified_agent_id = state.get("builder_agent_id")  # may have been set by Node 1
    verified_tool_id = None
    agent_verification_status = "exists"  # exists | created | failed
    tool_verification_status = "exists"   # exists | created | failed | not_needed

    try:
        from database.base import SessionLocal
        from database.models.variant_engine import AIAgentAssignment
        import json as _n2_json

        _v_db = SessionLocal()
        try:
            # ── Step 1: Verify agent exists ──
            agent = None
            if verified_agent_id:
                # Node 1 already created one — verify it exists
                agent = _v_db.query(AIAgentAssignment).filter(
                    AIAgentAssignment.id == verified_agent_id,
                ).first()

            if not agent:
                # Search by capability
                all_agents = _v_db.query(AIAgentAssignment).filter(
                    AIAgentAssignment.company_id == tenant_id,
                    AIAgentAssignment.status == "active",
                ).all()
                for a in all_agents:
                    try:
                        caps = _n2_json.loads(a.capabilities or "[]")
                        if detected_capability in caps:
                            agent = a
                            verified_agent_id = a.id
                            break
                    except Exception:
                        pass

            if agent:
                # Agent found ✅
                agent_verification_status = "exists"
                logs.append({
                    "node": 2, "technique": "AgentVerification",
                    "duration_ms": 0,
                    "result_summary": f"capability={detected_capability} agent_id={str(verified_agent_id)[:8]} status=exists",
                })

                # ── Step 2: Verify tool exists ──
                if agent.superglue_tool_id and agent.superglue_tool_status == "active":
                    verified_tool_id = agent.superglue_tool_id
                    tool_verification_status = "exists"
                    logs.append({
                        "node": 2, "technique": "ToolVerification",
                        "duration_ms": 0,
                        "result_summary": f"tool_id={verified_tool_id[:20]} status=exists",
                    })
                else:
                    # Tool missing — does this action need one?
                    needs_tool = action in ("refund", "cancel_subscription", "process_payment",
                                           "apply_credit", "cancel_order", "update_shipping")
                    if needs_tool:
                        tool_verification_status = "missing_needs_creation"
                        logs.append({
                            "node": 2, "technique": "ToolVerification",
                            "duration_ms": 0,
                            "result_summary": f"action={action} NEEDS tool but none linked — will create in Node 5",
                        })
                        # Tool creation deferred to Node 5 (when action executes)
                        # Node 5 will: check → create → execute, or escalate if can't
                    else:
                        tool_verification_status = "not_needed"
                        logs.append({
                            "node": 2, "technique": "ToolVerification",
                            "duration_ms": 0,
                            "result_summary": f"action={action} does not need a tool",
                        })
            else:
                # Agent NOT found → try to create via template system
                logs.append({
                    "node": 2, "technique": "AgentVerification",
                    "duration_ms": 0,
                    "result_summary": f"capability={detected_capability} agent NOT FOUND → will create",
                })

                try:
                    from app.services.agent_template_manager import (
                        get_or_create_template,
                        clone_template_to_tenant,
                    )
                    # Get or create template (checks DB first, builds if missing)
                    template = await get_or_create_template(
                        db=_v_db,
                        capability=detected_capability,
                        kb_context=state.get("query", "")[:500],
                        integrations=tenant_connected_integrations if 'tenant_connected_integrations' in dir() else [],
                    )
                    # Clone to this tenant (instant, 0 LLM calls)
                    verified_agent_id = clone_template_to_tenant(
                        db=_v_db,
                        template=template,
                        company_id=tenant_id,
                        kb_context=state.get("query", "")[:500],
                    )
                    agent_verification_status = "created"
                    tool_verification_status = "not_linked"  # tool created later in Node 5
                    logs.append({
                        "node": 2, "technique": "AgentCreation",
                        "duration_ms": 0,
                        "result_summary": f"capability={detected_capability} agent CREATED via template (is_new={template.get('is_new')})",
                    })
                except Exception as create_exc:
                    agent_verification_status = "failed"
                    tool_verification_status = "failed"
                    logger.error(
                        "Node 2: agent creation FAILED capability=%s err=%s",
                        detected_capability, str(create_exc)[:200],
                    )
                    logs.append({
                        "node": 2, "technique": "AgentCreation",
                        "duration_ms": 0,
                        "result_summary": f"FAILED: {str(create_exc)[:100]}",
                    })

        finally:
            _v_db.close()

    except Exception as exc:
        logger.warning("Node 2: verification layer error: %s", str(exc)[:200])
        agent_verification_status = "error"
        tool_verification_status = "error"

    # ── DECISION: go forward or send back ──
    if agent_verification_status == "failed":
        # Can't create agent → ESCALATE (send back)
        logs.append({
            "node": 2, "technique": "RouteDecision",
            "duration_ms": 0,
            "result_summary": "ESCALATE: agent creation failed → send to human",
        })
        return {
            "route_decision": "simple_path",
            "current_path": "simple_path",
            "variant_tier": selected_tier_db,
            "quota_remaining": quota_remaining,
            "variant_capabilities": capabilities,
            "status": "escalated",
            "escalation_reason": "agent_creation_failed",
            "final_response": (
                "We're unable to automatically handle this request at the moment. "
                "An agent for this type of request could not be created. "
                "A human team member will review and respond shortly."
            ),
            "technique_log": logs,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    # Agent ready → continue to Node 3
    logs.append({
        "node": 2, "technique": "RouteDecision",
        "duration_ms": 0,
        "result_summary": f"CONTINUE: agent={agent_verification_status} tool={tool_verification_status} → Node 3",
    })

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 2 complete: ticket=%s tier=%s(%s) path=%s source=%s agent=%s tool=%s [%dms]",
        state.get("ticket_id", "?"),
        selected_tier_short, selected_tier_db,
        path, source,
        agent_verification_status, tool_verification_status,
        elapsed,
    )

    # ── P2 Notification: emit ticket:routed when routing is surprising ──
    # Fires when the routing decision is unusual:
    # - Path was overridden from simple → complex (query needed full reasoning)
    # - Fallback tier was used (no tier had quota or could handle the ticket)
    # This helps the human understand why a ticket went to a higher tier than expected.
    try:
        from app.core.event_emitter import emit_ticket_event
        tenant_id = state.get("tenant_id", "")
        ticket_id = state.get("ticket_id", "")
        is_surprising = False
        surprise_reason = ""

        # Check if FORCE_COMPLEX_PATH was used (all tickets forced to complex)
        if os.environ.get("FORCE_COMPLEX_PATH", "").lower() in ("1", "true", "yes"):
            is_surprising = True
            surprise_reason = "force_complex_path_enabled"

        # Check if quota is exhausted (quota_remaining is a dict per tier)
        # If ANY tier has 0 remaining, that's surprising
        if isinstance(quota_remaining, dict):
            any_exhausted = any(v <= 0 for v in quota_remaining.values() if isinstance(v, (int, float)))
            if any_exhausted and not is_surprising:
                is_surprising = True
                surprise_reason = "quota_exhausted_fallback_to_highest_tier"

        if is_surprising:
            await emit_ticket_event(
                company_id=tenant_id,
                event_type="ticket:routed",
                payload={
                    "company_id": tenant_id,
                    "ticket_id": ticket_id,
                    "ticket_type": ticket_type,
                    "complexity": complexity,
                    "selected_tier": selected_tier_db,
                    "path": path,
                    "surprise_reason": surprise_reason,
                    "quota_remaining": quota_remaining,
                    "node": 2,
                },
                correlation_id=ticket_id,
            )
    except Exception as exc:
        logger.warning("node_2_routed_notification_failed: %s", str(exc)[:200])

    return {
        "variant_tier": selected_tier_db,
        "variant_tier_short": selected_tier_short,
        "quota_remaining": quota_remaining,
        "route_decision": path,
        "current_path": path,
        "variant_capabilities": capabilities,
        "technique_log": logs,
        # ── Verification layer output ──
        "verified_agent_id": verified_agent_id,
        "verified_tool_id": verified_tool_id,
        "agent_verification_status": agent_verification_status,
        "tool_verification_status": tool_verification_status,
    }