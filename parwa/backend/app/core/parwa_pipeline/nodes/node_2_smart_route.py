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


# ── Route Decision Logic (3-dimensional) ──────────────────────────


def _check_capability(tier: str, ticket_type: str, complexity: str, action: str, action_details: Dict) -> bool:
    """Dimension 1: Can this tier HANDLE this ticket?"""
    caps = CAPABILITY_MATRIX[tier]

    # Simple/medium info: all tiers can handle
    if action == "provide_info":
        return True

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


def _route_decision(
    tenant_id: str, ticket_type: str, complexity: str, action: str, action_details: Dict
) -> tuple:
    """3-Dimensional Routing: capability + quota + efficiency.

    Returns (selected_tier, path, capabilities_list).
    Uses the LOWEST eligible tier to preserve higher quotas for harder tickets.
    """
    # Determine which path
    if complexity in ("simple", "medium") and action == "provide_info":
        target_path = "simple_path"
    elif complexity in ("simple", "medium") and action == "recommend":
        target_path = "simple_path"
    else:
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

    # 3. 3-Dimensional route decision
    selected_tier, path, capabilities = _route_decision(
        tenant_id, ticket_type, complexity, action, action_details
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