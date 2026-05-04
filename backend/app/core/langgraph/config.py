"""
PARWA LangGraph Configuration

Central configuration for the multi-agent LangGraph system.
All variant-driven behavior is defined here.

Key Config Sections:
  1. VARIANT_CONFIG     — Per-tier feature flags and capabilities
  2. MAKER_CONFIG       — MAKER K-solution validator settings per tier
  3. TECHNIQUE_TIER_ACCESS — Which technique tiers are available per variant
  4. AGENT_AVAILABILITY — Which domain agents are available per tier
  5. CHANNEL_AVAILABILITY — Which channels are supported per tier

Design Rules:
  - variant_tier is the single source of truth
  - Mini: 3 agents, T1 techniques, MAKER efficiency, no voice
  - Pro:  6 agents, T1+T2 techniques, MAKER balanced, voice enabled
  - High: All agents, T1+T2+T3 techniques, MAKER conservative, voice+video

BC-001: All configs are tenant-scoped via variant_tier.
BC-008: Graceful degradation — if variant_tier is unknown, fall back to mini.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from app.logger import get_logger

logger = get_logger("langgraph_config")


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class VariantTier(str, Enum):
    """PARWA variant tiers — maps to subscription plans."""
    MINI = "mini"
    PRO = "pro"
    HIGH = "high"


class MakerMode(str, Enum):
    """MAKER K-solution validator modes — one per tier."""
    EFFICIENCY = "efficiency"    # Mini: K=3, fast, lower threshold
    BALANCED = "balanced"        # Pro: K=3-5, moderate
    CONSERVATIVE = "conservative"  # High: K=5-7, thorough, high threshold


class SystemMode(str, Enum):
    """System operating modes."""
    AUTO = "auto"              # Fully automated
    SUPERVISED = "supervised"  # Human-in-the-loop for risky actions
    SHADOW = "shadow"          # Shadow mode: observe, don't act
    PAUSED = "paused"          # AI paused, human-only


class EmergencyState(str, Enum):
    """Emergency state levels."""
    NORMAL = "normal"
    YELLOW_ALERT = "yellow_alert"
    RED_ALERT = "red_alert"
    FULL_STOP = "full_stop"


class ApprovalDecision(str, Enum):
    """Control system approval decisions."""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_HUMAN_APPROVAL = "needs_human_approval"
    AUTO_APPROVED = "auto_approved"


class ActionType(str, Enum):
    """Action type classifications for Control System."""
    INFORMATIONAL = "informational"  # Just respond, no side effects
    MONETARY = "monetary"          # Involves money (refund, discount)
    DESTRUCTIVE = "destructive"    # Cannot be undone (delete account)
    ESCALATION = "escalation"       # Hand off to human


# ══════════════════════════════════════════════════════════════════
# MAKER CONFIG — K-Solution Validator per Tier
# ══════════════════════════════════════════════════════════════════

MAKER_CONFIG: Dict[str, Dict[str, Any]] = {
    VariantTier.MINI.value: {
        "mode": MakerMode.EFFICIENCY.value,
        "k": 3,
        "k_range": None,
        "threshold": 0.50,
        "description": "Efficiency mode: Generate 3 solutions, accept if confidence >= 50%",
        "red_flag_action": "auto_escalate",  # On red flag, escalate to human
        "decomposition_enabled": False,       # Skip decomposition for speed
        "audit_trail_level": "minimal",       # Only record final decision
    },
    VariantTier.PRO.value: {
        "mode": MakerMode.BALANCED.value,
        "k": 4,
        "k_range": (3, 5),
        "threshold": 0.60,
        "description": "Balanced mode: Generate 3-5 solutions, accept if confidence >= 60%",
        "red_flag_action": "human_approval",  # On red flag, need human approval
        "decomposition_enabled": True,        # Enable problem decomposition
        "audit_trail_level": "standard",      # Record key decision points
    },
    VariantTier.HIGH.value: {
        "mode": MakerMode.CONSERVATIVE.value,
        "k": 6,
        "k_range": (5, 7),
        "threshold": 0.75,
        "description": "Conservative mode: Generate 5-7 solutions, accept if confidence >= 75%",
        "red_flag_action": "human_approval_mandatory",  # Always need human for red flags
        "decomposition_enabled": True,        # Full decomposition
        "audit_trail_level": "full",          # Record everything
    },
}


# ══════════════════════════════════════════════════════════════════
# TECHNIQUE TIER ACCESS — Which technique tiers are available
# ══════════════════════════════════════════════════════════════════

TECHNIQUE_TIER_ACCESS: Dict[str, Dict[str, Any]] = {
    VariantTier.MINI.value: {
        "available_tiers": ["tier_1"],
        "techniques": ["clara", "crp", "gsd"],
        "description": "Tier 1 only: CLARA + CRP + GSD — always active techniques",
        "max_technique_tokens": 200,
    },
    VariantTier.PRO.value: {
        "available_tiers": ["tier_1", "tier_2"],
        "techniques": [
            "clara", "crp", "gsd",                          # Tier 1
            "chain_of_thought", "reverse_thinking",         # Tier 2
            "react", "step_back", "thread_of_thought",      # Tier 2
        ],
        "description": "Tier 1 + Tier 2: Adds CoT, Reverse Thinking, ReAct, Step-Back, ThoT",
        "max_technique_tokens": 1200,
    },
    VariantTier.HIGH.value: {
        "available_tiers": ["tier_1", "tier_2", "tier_3"],
        "techniques": [
            "clara", "crp", "gsd",                          # Tier 1
            "chain_of_thought", "reverse_thinking",         # Tier 2
            "react", "step_back", "thread_of_thought",      # Tier 2
            "gst", "universe_of_thoughts", "tree_of_thoughts",  # Tier 3
            "self_consistency", "reflexion", "least_to_most",    # Tier 3
        ],
        "description": "All tiers: Full technique stack including premium T3 techniques",
        "max_technique_tokens": 3000,
    },
}


# ══════════════════════════════════════════════════════════════════
# AGENT AVAILABILITY — Which domain agents are available per tier
# ══════════════════════════════════════════════════════════════════

AGENT_AVAILABILITY: Dict[str, Dict[str, Any]] = {
    VariantTier.MINI.value: {
        "domain_agents": ["faq", "technical", "billing"],
        "max_concurrent_agents": 5,
        "total_agent_pool": 5,
        "description": "3 domain agents: FAQ, Technical, Billing — essential coverage",
        "fallback_agent": "faq",  # If intent doesn't match available agents
    },
    VariantTier.PRO.value: {
        "domain_agents": ["faq", "refund", "technical", "billing", "complaint", "escalation"],
        "max_concurrent_agents": 15,
        "total_agent_pool": 15,
        "description": "6 domain agents: Full coverage including Refund, Complaint, Escalation",
        "fallback_agent": "faq",
    },
    VariantTier.HIGH.value: {
        "domain_agents": ["faq", "refund", "technical", "billing", "complaint", "escalation"],
        "max_concurrent_agents": 50,
        "total_agent_pool": 50,
        "description": "All 6 domain agents with maximum concurrent capacity",
        "fallback_agent": "escalation",  # High tier defaults to escalation for unknown
    },
}


# ══════════════════════════════════════════════════════════════════
# CHANNEL AVAILABILITY — Which channels are supported per tier
# ══════════════════════════════════════════════════════════════════

CHANNEL_AVAILABILITY: Dict[str, Dict[str, Any]] = {
    VariantTier.MINI.value: {
        "channels": ["email", "sms", "chat", "api"],
        "voice_enabled": False,
        "video_enabled": False,
        "description": "Text-only channels: Email, SMS, Chat, API — no voice/video",
    },
    VariantTier.PRO.value: {
        "channels": ["email", "sms", "chat", "api", "voice"],
        "voice_enabled": True,
        "video_enabled": False,
        "description": "All text channels + Voice calls — no video",
    },
    VariantTier.HIGH.value: {
        "channels": ["email", "sms", "chat", "api", "voice", "video"],
        "voice_enabled": True,
        "video_enabled": True,
        "description": "All channels including Voice and Video",
    },
}


# ══════════════════════════════════════════════════════════════════
# CONTROL SYSTEM CONFIG — Approval requirements per tier
# ══════════════════════════════════════════════════════════════════

CONTROL_CONFIG: Dict[str, Dict[str, Any]] = {
    VariantTier.MINI.value: {
        "approval_required_for": [],  # Auto-approve everything
        "auto_approve_threshold": 0.50,
        "interrupt_before": False,
        "human_approval_timeout_seconds": 0,
        "description": "No human approval needed — fully automated",
    },
    VariantTier.PRO.value: {
        "approval_required_for": [ActionType.MONETARY.value, ActionType.DESTRUCTIVE.value],
        "auto_approve_threshold": 0.60,
        "interrupt_before": True,  # interrupt_before for money/destructive actions
        "human_approval_timeout_seconds": 300,  # 5 minutes
        "vip_rules": True,  # VIP customers always get human review
        "description": "Human approval for monetary + destructive actions + VIP",
    },
    VariantTier.HIGH.value: {
        "approval_required_for": [
            ActionType.MONETARY.value,
            ActionType.DESTRUCTIVE.value,
            ActionType.ESCALATION.value,
        ],
        "auto_approve_threshold": 0.75,
        "interrupt_before": True,  # interrupt_before for all risky actions
        "human_approval_timeout_seconds": 600,  # 10 minutes
        "vip_rules": True,
        "money_rules": True,  # All monetary actions need review
        "description": "Human approval for monetary + destructive + escalation actions",
    },
}


# ══════════════════════════════════════════════════════════════════
# COMPREHENSIVE VARIANT CONFIG — All configs merged per tier
# ══════════════════════════════════════════════════════════════════

VARIANT_CONFIG: Dict[str, Dict[str, Any]] = {
    VariantTier.MINI.value: {
        "tier": VariantTier.MINI.value,
        "display_name": "Mini Parwa",
        "price_usd": 999,
        "maker": MAKER_CONFIG[VariantTier.MINI.value],
        "techniques": TECHNIQUE_TIER_ACCESS[VariantTier.MINI.value],
        "agents": AGENT_AVAILABILITY[VariantTier.MINI.value],
        "channels": CHANNEL_AVAILABILITY[VariantTier.MINI.value],
        "control": CONTROL_CONFIG[VariantTier.MINI.value],
        "pipeline_timeout_seconds": 20.0,
        "max_tokens_per_response": 1000,
        "description": "Mini Parwa — Essential AI customer care, 3 agents, T1 techniques",
    },
    VariantTier.PRO.value: {
        "tier": VariantTier.PRO.value,
        "display_name": "Parwa Pro",
        "price_usd": 2499,
        "maker": MAKER_CONFIG[VariantTier.PRO.value],
        "techniques": TECHNIQUE_TIER_ACCESS[VariantTier.PRO.value],
        "agents": AGENT_AVAILABILITY[VariantTier.PRO.value],
        "channels": CHANNEL_AVAILABILITY[VariantTier.PRO.value],
        "control": CONTROL_CONFIG[VariantTier.PRO.value],
        "pipeline_timeout_seconds": 30.0,
        "max_tokens_per_response": 1500,
        "description": "Parwa Pro — Full AI customer care, 6 agents, T1+T2 techniques, Voice",
    },
    VariantTier.HIGH.value: {
        "tier": VariantTier.HIGH.value,
        "display_name": "Parwa High",
        "price_usd": 3999,
        "maker": MAKER_CONFIG[VariantTier.HIGH.value],
        "techniques": TECHNIQUE_TIER_ACCESS[VariantTier.HIGH.value],
        "agents": AGENT_AVAILABILITY[VariantTier.HIGH.value],
        "control": CONTROL_CONFIG[VariantTier.HIGH.value],
        "channels": CHANNEL_AVAILABILITY[VariantTier.HIGH.value],
        "pipeline_timeout_seconds": 45.0,
        "max_tokens_per_response": 2000,
        "description": "Parwa High — Premium AI customer care, all agents, all techniques, Voice+Video",
    },
}


# ══════════════════════════════════════════════════════════════════
# INTENT → AGENT MAPPING
# ══════════════════════════════════════════════════════════════════

INTENT_AGENT_MAP: Dict[str, str] = {
    "faq": "faq",
    "general": "faq",
    "greeting": "faq",
    "refund": "refund",
    "return": "refund",
    "cancellation": "refund",
    "technical": "technical",
    "troubleshoot": "technical",
    "bug": "technical",
    "billing": "billing",
    "payment": "billing",
    "invoice": "billing",
    "subscription": "billing",
    "complaint": "complaint",
    "feedback": "complaint",
    "dissatisfied": "complaint",
    "escalation": "escalation",
    "manager": "escalation",
    "supervisor": "escalation",
    "legal": "escalation",
    "urgent": "escalation",
}


# ══════════════════════════════════════════════════════════════════
# ACTION → ACTION_TYPE CLASSIFICATION
# ══════════════════════════════════════════════════════════════════

ACTION_TYPE_MAP: Dict[str, str] = {
    "respond": ActionType.INFORMATIONAL.value,
    "answer": ActionType.INFORMATIONAL.value,
    "inform": ActionType.INFORMATIONAL.value,
    "refund": ActionType.MONETARY.value,
    "discount": ActionType.MONETARY.value,
    "credit": ActionType.MONETARY.value,
    "waive_fee": ActionType.MONETARY.value,
    "cancel_subscription": ActionType.DESTRUCTIVE.value,
    "delete_account": ActionType.DESTRUCTIVE.value,
    "escalate": ActionType.ESCALATION.value,
    "human_handoff": ActionType.ESCALATION.value,
    "create_ticket": ActionType.INFORMATIONAL.value,
    "update_ticket": ActionType.INFORMATIONAL.value,
}


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def get_variant_config(variant_tier: str) -> Dict[str, Any]:
    """
    Get full variant configuration for a given tier.

    Falls back to mini if the variant_tier is unknown (BC-008).

    Args:
        variant_tier: One of 'mini', 'pro', 'high'

    Returns:
        Full variant configuration dict
    """
    config = VARIANT_CONFIG.get(variant_tier)
    if config is None:
        logger.warning(
            "unknown_variant_tier_fallback_to_mini",
            requested_tier=variant_tier,
        )
        config = VARIANT_CONFIG[VariantTier.MINI.value]
    return config


def get_maker_config(variant_tier: str) -> Dict[str, Any]:
    """Get MAKER configuration for a given tier. Falls back to mini."""
    config = MAKER_CONFIG.get(variant_tier)
    if config is None:
        config = MAKER_CONFIG[VariantTier.MINI.value]
    return config


def get_available_agents(variant_tier: str) -> List[str]:
    """Get list of available domain agents for a given tier."""
    agent_config = AGENT_AVAILABILITY.get(variant_tier, AGENT_AVAILABILITY[VariantTier.MINI.value])
    return agent_config["domain_agents"]


def get_available_techniques(variant_tier: str) -> List[str]:
    """Get list of available technique IDs for a given tier."""
    tech_config = TECHNIQUE_TIER_ACCESS.get(variant_tier, TECHNIQUE_TIER_ACCESS[VariantTier.MINI.value])
    return tech_config["techniques"]


def get_available_channels(variant_tier: str) -> List[str]:
    """Get list of available channels for a given tier."""
    channel_config = CHANNEL_AVAILABILITY.get(variant_tier, CHANNEL_AVAILABILITY[VariantTier.MINI.value])
    return channel_config["channels"]


def is_voice_enabled(variant_tier: str) -> bool:
    """Check if voice is enabled for a given tier (Pro + High only)."""
    channel_config = CHANNEL_AVAILABILITY.get(variant_tier, CHANNEL_AVAILABILITY[VariantTier.MINI.value])
    return channel_config["voice_enabled"]


def is_video_enabled(variant_tier: str) -> bool:
    """Check if video is enabled for a given tier (High only)."""
    channel_config = CHANNEL_AVAILABILITY.get(variant_tier, CHANNEL_AVAILABILITY[VariantTier.MINI.value])
    return channel_config["video_enabled"]


def map_intent_to_agent(intent: str, variant_tier: str) -> str:
    """
    Map classified intent to the appropriate domain agent,
    respecting variant tier agent availability.

    If the intent maps to an agent that's not available for this tier,
    falls back to the tier's configured fallback agent.

    Args:
        intent: Classified intent string
        variant_tier: Variant tier string

    Returns:
        Agent name string (one of available domain agents)
    """
    target = INTENT_AGENT_MAP.get(intent, "faq")
    available = get_available_agents(variant_tier)

    if target not in available:
        agent_config = AGENT_AVAILABILITY.get(variant_tier, AGENT_AVAILABILITY[VariantTier.MINI.value])
        fallback = agent_config["fallback_agent"]
        logger.info(
            "agent_unavailable_using_fallback",
            intent=intent,
            target_agent=target,
            fallback_agent=fallback,
            variant_tier=variant_tier,
        )
        return fallback

    return target


def classify_action_type(proposed_action: str) -> str:
    """
    Classify a proposed action into an action type category.

    Used by the Control System to determine if human approval is needed.

    Args:
        proposed_action: The action proposed by the domain agent

    Returns:
        Action type string (informational, monetary, destructive, escalation)
    """
    return ACTION_TYPE_MAP.get(proposed_action, ActionType.INFORMATIONAL.value)


def needs_human_approval(action_type: str, variant_tier: str) -> bool:
    """
    Determine if a given action type requires human approval
    for the specified variant tier.

    Args:
        action_type: One of informational, monetary, destructive, escalation
        variant_tier: Variant tier string

    Returns:
        True if human approval is required
    """
    control = CONTROL_CONFIG.get(variant_tier, CONTROL_CONFIG[VariantTier.MINI.value])
    required_for = control.get("approval_required_for", [])
    return action_type in required_for


def get_maker_k_value(variant_tier: str, complexity_score: float = 0.5) -> int:
    """
    Get the K value for MAKER based on variant tier and query complexity.

    For tiers with k_range, K is dynamically selected based on complexity:
      - Low complexity (0.0-0.3): Use minimum K
      - Medium complexity (0.3-0.7): Use middle K
      - High complexity (0.7-1.0): Use maximum K

    Args:
        variant_tier: Variant tier string
        complexity_score: Query complexity 0.0-1.0

    Returns:
        K value (number of solutions to generate)
    """
    maker = get_maker_config(variant_tier)

    if maker.get("k_range") is not None:
        k_min, k_max = maker["k_range"]
        if complexity_score <= 0.3:
            return k_min
        elif complexity_score >= 0.7:
            return k_max
        else:
            return (k_min + k_max) // 2
    else:
        return maker["k"]


def validate_variant_tier(variant_tier: str) -> bool:
    """
    Validate that a variant_tier string is recognized.

    Args:
        variant_tier: Variant tier string to validate

    Returns:
        True if valid, False otherwise
    """
    return variant_tier in VARIANT_CONFIG


def get_all_valid_tiers() -> List[str]:
    """Get list of all valid variant tier values."""
    return [t.value for t in VariantTier]
