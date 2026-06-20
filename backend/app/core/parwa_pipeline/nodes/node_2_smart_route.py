"""
Node 2: Smart Route

Question: WHO handles this ticket + WHERE does it go?

Components:
  1. Variant Registry  — what did tenant buy?
  2. Quota Tracker     — how many remaining?
  3. Capability Matrix — can this tier handle it?
  4. Route Decision    — lowest eligible tier → path

LLM calls: 0 (pure logic, database reads only)
Input from Jarvis: quota feed (Phase 8)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List

from app.core.parwa_pipeline.state_v2 import PipelineV2State

logger = logging.getLogger("parwa.pipeline.node_2")

# ── Capability Matrix (from roadmap Section 14) ───────────────────

CAPABILITY_MATRIX = {
    "mini": {
        "simple_info": True,
        "medium_info": True,
        "recommend": True,
        "execute_refund": False,
        "execute_credit": False,
        "account_change": False,
        "complex_reasoning": False,
        "super_node": False,
        "quality_loops": 0,
        "ai_wiki_access": "read",
        "integrations_max": 2,
    },
    "parwa": {
        "simple_info": True,
        "medium_info": True,
        "recommend": True,
        "execute_refund": True,       # ≤ $500
        "execute_credit": True,        # ≤ $200
        "account_change": True,        # limited
        "complex_reasoning": True,
        "super_node": True,
        "quality_loops": 2,
        "ai_wiki_access": "read_learn",
        "integrations_max": 5,
    },
    "high": {
        "simple_info": True,
        "medium_info": True,
        "recommend": True,
        "execute_refund": True,       # unlimited
        "execute_credit": True,        # unlimited
        "account_change": True,        # full
        "complex_reasoning": True,
        "super_node": True,
        "quality_loops": 2,
        "ai_wiki_access": "read_write_learn",
        "integrations_max": -1,        # unlimited
    },
}

# Execution limits per tier (from roadmap Section 4, Node 5)
EXECUTION_LIMITS = {
    "mini": {"max_refund": 0, "max_credit": 0},
    "parwa": {"max_refund": 500, "max_credit": 200},
    "high": {"max_refund": float("inf"), "max_credit": float("inf")},
}

# ── Mock Variant Registry (replaced by DB in Phase 4) ─────────────

# In production this reads from DB. For testing, use defaults.
MOCK_VARIANT_REGISTRY: Dict[str, Dict[str, Any]] = {}


def set_test_variant(tenant_id: str, tier: str, quota: int) -> None:
    """Set a test variant for a tenant. Used in testing only."""
    MOCK_VARIANT_REGISTRY[tenant_id] = {
        "tier": tier,
        "quota_total": quota,
        "quota_remaining": quota,
    }


# ── Keyword-Based Complexity Correction ──────────────────────────


def _correct_complexity(query: str, complexity: str, action: str, ticket_type: str) -> tuple:
    """Post-LLM correction: blend LLM classification with keyword heuristics.

    Catches cases where the LLM misclassifies:
      - Simple account changes tagged as complex
      - Technical integration / billing disputes tagged as simple/medium
    """
    query_lower = query.lower()

    # Strong indicators that should ALWAYS be complex regardless of LLM
    strong_complex_patterns = [
        r'\bintegrate\b.*\b(api|crm|erp|system|webhook)\b',       # Technical integration
        r'\bapi\b.*\b(endpoint|connect|integration)\b',          # API integration
        r'\b(overcharg|wrong charge|double charge|unauthorized charge)\b',  # Billing dispute
        r'\brefund\b.*\b(subscription|plan|enterprise|difference)\b',       # Subscription refund
        r'\b(chargeback|file\s+a\s+dispute)\b',                        # Escalation
        r'\b(error|crash|500|403)\b.*\b(urgent|deadline|team)\b',     # Critical tech issue
        r'\b(manager|supervisor)\b.*\b(complaint|terrible|worst)\b',  # Escalation complaint
        r'\b(enterprise|plan)\b.*\b(charg|refund|credit)\b.*\b\d+', # Monetary dispute with amount
    ]

    for pattern in strong_complex_patterns:
        if re.search(pattern, query_lower):
            if complexity in ("simple", "medium"):
                logger.info(
                    "Complexity correction: %s → complex (keyword override)",
                    complexity,
                )
                return "complex", action

    # Strong indicators that should ALWAYS be simple regardless of LLM
    strong_simple_patterns = [
        r'^\s*I\s+(need\s+)?(want\s+)?to\s+(change|update)\s+my\s+(billing\s+)?(email|address|password|name|phone)\b',  # Simple account update
        r'^\s*I\s+(need\s+)?(want\s+)?to\s+(change|update)\s+(my\s+)?billing\s+email\b',  # Explicit billing email
    ]

    for pattern in strong_simple_patterns:
        if re.search(pattern, query_lower):
            if complexity == "complex":
                logger.info(
                    "Complexity correction: %s → simple (keyword override)",
                    complexity,
                )
                return "simple", "provide_info"

    return complexity, action


# ── Route Decision Logic (3-dimensional) ──────────────────────────


def _check_capability(tier: str, ticket_type: str, complexity: str, action: str, action_details: Dict) -> bool:
    """Dimension 1: Can this tier HANDLE this ticket?"""
    caps = CAPABILITY_MATRIX[tier]

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
        if amount > EXECUTION_LIMITS[tier]["max_refund"]:
            return False

    if action == "execute_credit":
        if not caps["execute_credit"]:
            return False
        amount = action_details.get("amount", 0)
        if amount > EXECUTION_LIMITS[tier]["max_credit"]:
            return False

    if action == "account_change" and not caps["account_change"]:
        return False

    return True


def _check_quota(tenant_id: str, tier: str) -> bool:
    """Dimension 2: Does this tier have tickets remaining?"""
    reg = MOCK_VARIANT_REGISTRY.get(tenant_id)
    if not reg or reg["tier"] != tier:
        return False
    return reg["quota_remaining"] > 0


def _consume_quota(tenant_id: str, tier: str) -> None:
    """Decrement quota for the used tier."""
    reg = MOCK_VARIANT_REGISTRY.get(tenant_id)
    if reg and reg["tier"] == tier:
        reg["quota_remaining"] -= 1


TIER_ORDER = ["mini", "parwa", "high"]


def _needs_complex_path(query: str) -> bool:
    """Check if the query content requires complex path regardless of complexity label.

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
    tenant_id: str, ticket_type: str, complexity: str, action: str, action_details: Dict,
    query: str = ""
) -> tuple:
    """3-Dimensional Routing: capability + quota + efficiency.

    Returns (selected_tier, path, capabilities_list).
    Uses the LOWEST eligible tier to preserve higher quotas for harder tickets.
    """
    # Apply keyword-based complexity correction first
    corrected_complexity, corrected_action = _correct_complexity(query, complexity, action, ticket_type)

    # Determine which path
    if corrected_complexity in ("simple", "medium") and corrected_action == "provide_info":
        target_path = "simple_path"
    elif corrected_complexity in ("simple", "medium") and corrected_action == "recommend":
        target_path = "simple_path"
    elif corrected_complexity == "simple" and corrected_action == "account_change":
        # Simple account changes don't need full reasoning pipeline
        target_path = "simple_path"
    elif corrected_action == "investigate_billing":
        # Phase 7: Billing investigation always needs complex reasoning path
        target_path = "complex_path"
    else:
        target_path = "complex_path"

    # Override: query content needs complex path even if corrected to simple/medium
    if target_path == "simple_path" and _needs_complex_path(query):
        logger.info("Path override: simple → complex (query content requires full reasoning)")
        target_path = "complex_path"

    # Find lowest eligible tier
    selected_tier = None
    for tier in TIER_ORDER:
        reg = MOCK_VARIANT_REGISTRY.get(tenant_id)
        if not reg or reg["tier"] != tier:
            continue  # tenant doesn't have this tier
        if _check_capability(tier, ticket_type, complexity, action, action_details):
            if _check_quota(tenant_id, tier):
                selected_tier = tier
                break  # lowest eligible tier found

    # Fallback: if no tier has quota, use highest tier anyway
    if selected_tier is None:
        reg = MOCK_VARIANT_REGISTRY.get(tenant_id)
        if reg:
            selected_tier = reg["tier"]
        else:
            selected_tier = "parwa"  # default

    # Get capabilities for selected tier
    caps = CAPABILITY_MATRIX[selected_tier]
    capabilities = [k for k, v in caps.items() if v is True or isinstance(v, str)]

    return selected_tier, target_path, capabilities


# ── Main Node Function ────────────────────────────────────────────


async def node_2_smart_route(state: PipelineV2State) -> dict:
    """Node 2: Smart Route — WHO handles this + WHERE does it go?

    0 LLM calls. Pure logic.
    """
    start = time.time()
    tenant_id = state.get("tenant_id", "")
    ticket_type = state.get("ticket_type", "general")
    complexity = state.get("complexity", "simple")
    action = state.get("required_action", "provide_info")
    action_details = state.get("action_details", {})
    logs = []

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
            "variant_tier": "parwa",
            "quota_remaining": {},
            "variant_capabilities": [],
            "status": "paused",
            "final_response": f"The action '{action}' is currently paused by your administrator. Your request has been noted but cannot be processed until the pause is lifted.",
            "technique_log": logs,
            "total_token_usage": state.get("total_token_usage", 0),
        }

    # Check redirect_channel: if this channel is redirected to human, override path
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
                "variant_tier": "parwa",
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


    # 1. Variant Registry check
    reg = MOCK_VARIANT_REGISTRY.get(tenant_id, {"tier": "parwa", "quota_remaining": 999})
    logs.append({"node": 2, "technique": "VariantRegistry", "duration_ms": 0, "result_summary": f"tier={reg.get('tier', 'unknown')}"})

    # 2. Quota check
    quota_remaining = {
        tier: MOCK_VARIANT_REGISTRY.get(tenant_id, {}).get("quota_remaining", 0)
        for tier in TIER_ORDER
        if MOCK_VARIANT_REGISTRY.get(tenant_id, {}).get("tier") == tier
    }
    logs.append({"node": 2, "technique": "QuotaTracker", "duration_ms": 0, "result_summary": f"quota={quota_remaining}"})

    # 3. 3-Dimensional route decision (with keyword correction)
    selected_tier, path, capabilities = _route_decision(
        tenant_id, ticket_type, complexity, action, action_details,
        query=state.get("query", "")
    )
    logs.append({"node": 2, "technique": "RouteDecision", "duration_ms": 0, "result_summary": f"tier={selected_tier} path={path}"})

    # 4. Consume quota
    _consume_quota(tenant_id, selected_tier)

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Node 2 complete: ticket=%s tier=%s path=%s [%dms]",
        state["ticket_id"], selected_tier, path, elapsed,
    )

    return {
        "variant_tier": selected_tier,
        "quota_remaining": quota_remaining,
        "route_decision": path,
        "current_path": path,
        "variant_capabilities": capabilities,
        "technique_log": logs,
    }