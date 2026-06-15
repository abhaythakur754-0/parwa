"""
Permission System for Unified Variant Pipeline.

Core Philosophy: Same capability, different restrictions.
  - ALL variants have the SAME intelligence and can ANALYZE the same way
  - The ONLY difference is what ACTIONS they're ALLOWED to execute
  - Mini can DIAGNOSE a refund issue but may not be ALLOWED to process it
  - Pro can process refunds but needs approval for strategic decisions
  - High can do everything with minimal approval

Permission Tiers:
  Mini (3-4 interns):
    - CAN: analyze, classify, generate responses, suggest solutions
    - CAN: auto-fix safe issues (cache clear, config reset)
    - CAN: show refund preview to customer (batch)
    - CANNOT: execute monetary actions, strategic decisions, override policies
    - NEEDS APPROVAL: refunds, compensation, escalation overrides

  Pro (junior employees):
    - CAN: everything Mini can + execute refunds, run deep enrichment
    - CAN: auto-fix moderate issues (credential refresh, rate limit reset)
    - CAN: process batch refunds (with customer approval)
    - CANNOT: strategic decisions, override policies, win-back sequences
    - NEEDS APPROVAL: high-value refunds, retention offers, overrides

  High (senior employees):
    - CAN: everything Pro can + strategic decisions, peer review, override
    - CAN: auto-fix all issues including risky ones
    - CAN: execute any refund, any compensation, any retention offer
    - NEEDS APPROVAL: only emergency manual overrides
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.logger import get_logger

logger = get_logger("unified_variant_permissions")


# ══════════════════════════════════════════════════════════════════
# TIER CONFIGURATION
# ══════════════════════════════════════════════════════════════════

TIER_CONFIG = {
    "mini_parwa": {
        "display_name": "Mini Parwa",
        "analogy": "3-4 smart interns",
        "quality_threshold": 0.70,
        "max_quality_retries": 1,
        "model_tier": "light",
        "technique_tiers": [1],  # Tier 1 only
        "maker_k_range": (3, 3),
        "maker_threshold": 0.50,
        "can_execute_actions": False,
        "can_auto_fix": True,
        "auto_fix_risk_limit": "low",
        "can_process_refunds": False,
        "can_show_refund_preview": True,
        "can_batch_refunds": True,
        "can_strategic_decision": False,
        "can_peer_review": False,
        "can_context_compress": False,
        "can_deep_enrichment": False,
        "can_run_techniques_t2": False,
        "can_run_techniques_t3": False,
        "approval_required_for": [
            "refund", "compensation", "monetary", "override",
            "escalation_override", "retention_offer", "winback",
            "strategic_decision", "policy_change",
        ],
        "restricted_actions": [
            "execute_refund", "process_compensation", "monetary_action",
            "strategic_decision", "policy_override", "winback_sequence",
            "retention_offer_execution", "escalation_override",
            "high_value_refund", "account_credit",
        ],
    },
    "parwa": {
        "display_name": "Pro Parwa",
        "analogy": "Junior CC employees",
        "quality_threshold": 0.80,
        "max_quality_retries": 2,
        "model_tier": "medium",
        "technique_tiers": [1, 2],  # Tier 1 + 2
        "maker_k_range": (3, 5),
        "maker_threshold": 0.60,
        "can_execute_actions": True,
        "can_auto_fix": True,
        "auto_fix_risk_limit": "medium",
        "can_process_refunds": True,
        "can_show_refund_preview": True,
        "can_batch_refunds": True,
        "can_strategic_decision": False,
        "can_peer_review": False,
        "can_context_compress": False,
        "can_deep_enrichment": True,
        "can_run_techniques_t2": True,
        "can_run_techniques_t3": False,
        "approval_required_for": [
            "high_value_refund", "override", "strategic_decision",
            "policy_change", "winback_sequence",
        ],
        "restricted_actions": [
            "strategic_decision", "policy_override", "winback_sequence",
            "override", "high_value_refund_without_approval",
        ],
    },
    "parwa_high": {
        "display_name": "High Parwa",
        "analogy": "Senior CC employees",
        "quality_threshold": 0.90,
        "max_quality_retries": 3,
        "model_tier": "heavy",
        "technique_tiers": [1, 2, 3],  # Tier 1 + 2 + 3
        "maker_k_range": (5, 7),
        "maker_threshold": 0.75,
        "can_execute_actions": True,
        "can_auto_fix": True,
        "auto_fix_risk_limit": "high",
        "can_process_refunds": True,
        "can_show_refund_preview": True,
        "can_batch_refunds": True,
        "can_strategic_decision": True,
        "can_peer_review": True,
        "can_context_compress": True,
        "can_deep_enrichment": True,
        "can_run_techniques_t2": True,
        "can_run_techniques_t3": True,
        "approval_required_for": [
            "emergency_manual_override",
        ],
        "restricted_actions": [],
    },
}


def get_permission_context(variant_tier: str) -> Dict[str, Any]:
    """Get the full permission context for a variant tier.

    This is injected into the pipeline state so every node can check
    what it's allowed to do.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'

    Returns:
        Full permission context dict with can_do, cannot_do, etc.
    """
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])

    can_do = []
    cannot_do = []

    # Build can_do list
    for key, value in config.items():
        if key.startswith("can_") and value:
            can_do.append(key.replace("can_", ""))

    # Build cannot_do list from restricted_actions
    cannot_do = config.get("restricted_actions", [])

    return {
        "tier": variant_tier,
        "display_name": config["display_name"],
        "analogy": config["analogy"],
        "can_do": can_do,
        "cannot_do": cannot_do,
        "restricted_actions": config["restricted_actions"],
        "approval_required_for": config["approval_required_for"],
        "key_limits": {
            "quality_threshold": config["quality_threshold"],
            "max_quality_retries": config["max_quality_retries"],
            "model_tier": config["model_tier"],
            "technique_tiers": config["technique_tiers"],
            "maker_k_range": config["maker_k_range"],
            "maker_threshold": config["maker_threshold"],
            "auto_fix_risk_limit": config["auto_fix_risk_limit"],
        },
        "approval_rules": {
            "all_monetary_need_approval": variant_tier == "mini_parwa",
            "high_value_needs_approval": variant_tier in ("mini_parwa", "parwa"),
            "strategic_needs_approval": variant_tier != "parwa_high",
            "emergency_needs_approval": True,  # Always
        },
    }


def get_quality_threshold(variant_tier: str) -> float:
    """Get quality threshold for a variant tier."""
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])
    return config["quality_threshold"]


def get_max_quality_retries(variant_tier: str) -> int:
    """Get max quality retries for a variant tier."""
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])
    return config["max_quality_retries"]


def get_restricted_actions(variant_tier: str) -> List[str]:
    """Get list of restricted actions for a variant tier."""
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])
    return config["restricted_actions"]


def can_execute_action(variant_tier: str, action: str) -> bool:
    """Check if a variant tier can execute a specific action.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'
        action: The action to check (e.g., 'execute_refund', 'strategic_decision')

    Returns:
        True if the action is allowed, False if restricted.
    """
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])
    restricted = config.get("restricted_actions", [])
    return action not in restricted


def needs_approval_for(variant_tier: str, action: str) -> bool:
    """Check if a variant tier needs approval for a specific action.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'
        action: The action to check

    Returns:
        True if approval is needed, False if auto-approved.
    """
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])
    approval_required = config.get("approval_required_for", [])
    return action in approval_required


def get_auto_fix_risk_limit(variant_tier: str) -> str:
    """Get the maximum risk level of auto-fix allowed for a tier.

    Returns:
        'low' for Mini, 'medium' for Pro, 'high' for High.
    """
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])
    return config.get("auto_fix_risk_limit", "low")


def should_node_run(variant_tier: str, node_name: str) -> bool:
    """Check if a node should RUN for a given variant tier.

    In the unified graph, ALL nodes exist but some may be skipped
    based on tier. However, the CORE PHILOSOPHY is that all nodes
    should run — the difference is in what they DO, not whether they run.

    Only truly irrelevant nodes are skipped:
      - context_compress: only for High (Pro doesn't have enough context to compress)
      - peer_review: only for High
      - strategic_decision: only for High
      - deep_enrichment nodes: only for Pro/High

    But even Mini's nodes that are "restricted" still RUN — they just
    produce restricted/output-limited results.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'
        node_name: Name of the node

    Returns:
        True if the node should execute for this tier.
    """
    config = TIER_CONFIG.get(variant_tier, TIER_CONFIG["mini_parwa"])

    # Nodes that only run for specific tiers
    TIER_NODE_MAP = {
        "context_compress": lambda c: c.get("can_context_compress", False),
        "peer_review": lambda c: c.get("can_peer_review", False),
        "strategic_decision": lambda c: c.get("can_strategic_decision", False),
        "dedup": lambda c: c.get("can_peer_review", False),  # Dedup runs alongside peer_review
        "context_health": lambda c: c.get("can_peer_review", False),  # Context health for High
        # Deep enrichment nodes — Pro and High
        "complaint_handler": lambda c: c.get("can_deep_enrichment", False),
        "retention_negotiator": lambda c: c.get("can_deep_enrichment", False),
        "billing_resolver": lambda c: c.get("can_deep_enrichment", False),
        "tech_diagnostic": lambda c: c.get("can_deep_enrichment", False),
        "shipping_tracker": lambda c: c.get("can_deep_enrichment", False),
    }

    checker = TIER_NODE_MAP.get(node_name)
    if checker is None:
        # Default: node runs for ALL tiers
        return True

    return checker(config)
