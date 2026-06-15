"""
Permission Configuration — Tier-based restrictions for the unified variant graph.

This module defines what each variant tier is ALLOWED to do.
All tiers have the SAME intelligence/capability — only restrictions differ.

Design Principle:
  "A senior employee and an intern have the same brain.
   The difference is what decisions they're authorized to make."

Tier Mapping:
  Mini ≈ 3-4 interns: Observe, suggest, needs approval for everything
  Pro  ≈ Junior CC employees: Act on routine, escalate complex
  High ≈ Senior employees: Act on most things, escalate edge cases
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("permission_config")


class VariantTier(str, Enum):
    """Variant tier levels."""
    MINI = "mini_parwa"
    PRO = "parwa"
    HIGH = "parwa_high"


@dataclass
class PermissionConfig:
    """Permission configuration for a variant tier.

    Defines what a variant tier is ALLOWED to do.
    All nodes exist in the graph — these control execution behavior.
    """

    tier: VariantTier

    # ── Deep Enrichment ──────────────────────────────────────────
    # Which intent-specific deep enrichment nodes are allowed
    allowed_deep_enrichment: List[str] = field(default_factory=list)

    # ── Quality & Retry ──────────────────────────────────────────
    max_quality_retries: int = 0           # Mini=0, Pro=1, High=2
    clara_threshold: float = 70.0          # Mini=70, Pro=85, High=95

    # ── DSPy Optimization ────────────────────────────────────────
    use_dspy: bool = False                 # Mini=False, Pro=conditional, High=True
    dspy_min_complexity: float = 1.0       # Skip DSPy below this complexity

    # ── Auto-Fix & Auto-Action ───────────────────────────────────
    allow_auto_fix: bool = True            # ALL tiers get auto-fix
    allow_auto_action: bool = False        # Mini=False, Pro=True, High=True
    auto_action_confidence_min: float = 0.95  # Minimum confidence for auto-action

    # ── Advanced Reasoning ───────────────────────────────────────
    allow_reasoning_chain: bool = False    # Mini=False, Pro=True, High=True
    allow_technique_select: bool = False   # Mini=False, Pro=True, High=True
    allowed_techniques: List[str] = field(default_factory=lambda: ["baseline"])

    # ── Context Management ───────────────────────────────────────
    allow_context_compress: bool = False   # Mini=False, Pro=False, High=True
    allow_context_health: bool = False     # Mini=False, Pro=False, High=True
    allow_dedup: bool = False             # Mini=False, Pro=False, High=True

    # ── Strategic Decision ───────────────────────────────────────
    allow_strategic_decision: bool = False  # Mini=False, Pro=False, High=True
    allow_peer_review: bool = False        # Mini=False, Pro=False, High=True

    # ── Channels ─────────────────────────────────────────────────
    allowed_channels: List[str] = field(default_factory=lambda: ["chat", "email", "sms", "api"])

    # ── Domain Agents ────────────────────────────────────────────
    allowed_domain_agents: List[str] = field(default_factory=list)

    # ── Approval Requirements ────────────────────────────────────
    # What actions need human approval
    needs_approval_for_escalation: bool = True
    needs_approval_for_refund: bool = True
    needs_approval_for_monetary: bool = True
    needs_approval_for_account_change: bool = True

    # ── MAKER Validator ──────────────────────────────────────────
    maker_k_solutions: int = 1             # Mini=1, Pro=3, High=5
    maker_use_llm: bool = True             # All tiers use LLM for MAKER

    # ── Ask-When-Unsure ──────────────────────────────────────────
    ask_client_confidence_threshold: float = 0.5  # Below this → ask client via Jarvis
    allow_ask_client: bool = True          # All tiers can ask clients

    # ── Refund Batching ──────────────────────────────────────────
    allow_refund_batching: bool = True     # All tiers support batching

    # ── Smart Enrichment ─────────────────────────────────────────
    allow_smart_enrichment: bool = False   # Mini=False, Pro=True, High=True

    # ── LLM Model Tier ───────────────────────────────────────────
    llm_model_tier: str = "light"          # Mini=light, Pro=medium, High=heavy
    llm_max_tokens: int = 256              # Mini=256, Pro=600, High=1000
    llm_temperature: float = 0.7           # Mini=0.7, Pro=0.5, High=0.3


# ══════════════════════════════════════════════════════════════════
# PRE-BUILT CONFIGS FOR EACH TIER
# ══════════════════════════════════════════════════════════════════

MINI_CONFIG = PermissionConfig(
    tier=VariantTier.MINI,
    # Deep enrichment — Mini only gets billing_resolver and complaint_handler
    allowed_deep_enrichment=["billing_resolver", "complaint_handler"],
    # Quality — no retries, lower threshold
    max_quality_retries=0,
    clara_threshold=70.0,
    # DSPy — skip for cost
    use_dspy=False,
    dspy_min_complexity=1.0,
    # Auto-fix — YES, all tiers get this
    allow_auto_fix=True,
    allow_auto_action=False,
    auto_action_confidence_min=0.99,
    # Reasoning — no advanced reasoning
    allow_reasoning_chain=False,
    allow_technique_select=False,
    allowed_techniques=["baseline"],
    # Context — no advanced context management
    allow_context_compress=False,
    allow_context_health=False,
    allow_dedup=False,
    # Strategic — no
    allow_strategic_decision=False,
    allow_peer_review=False,
    # Channels — no voice
    allowed_channels=["chat", "email", "sms", "api"],
    # Domain agents — all 6 (same capability)
    allowed_domain_agents=[
        "faq_agent", "refund_agent", "technical_agent",
        "billing_agent", "complaint_agent", "escalation_agent",
    ],
    # Approval — Mini needs approval for everything
    needs_approval_for_escalation=True,
    needs_approval_for_refund=True,
    needs_approval_for_monetary=True,
    needs_approval_for_account_change=True,
    # MAKER
    maker_k_solutions=1,
    maker_use_llm=True,
    # Ask-when-unsure
    ask_client_confidence_threshold=0.5,
    allow_ask_client=True,
    # Refund batching
    allow_refund_batching=True,
    # Smart enrichment
    allow_smart_enrichment=False,
    # LLM
    llm_model_tier="light",
    llm_max_tokens=256,
    llm_temperature=0.7,
)

PRO_CONFIG = PermissionConfig(
    tier=VariantTier.PRO,
    # Deep enrichment — all 5
    allowed_deep_enrichment=[
        "complaint_handler", "retention_negotiator",
        "billing_resolver", "tech_diagnostic", "shipping_tracker",
    ],
    # Quality — 1 retry
    max_quality_retries=1,
    clara_threshold=85.0,
    # DSPy — conditional on complexity
    use_dspy=True,
    dspy_min_complexity=0.5,
    # Auto-fix + auto-action
    allow_auto_fix=True,
    allow_auto_action=True,
    auto_action_confidence_min=0.90,
    # Reasoning — Tier 1+2 techniques
    allow_reasoning_chain=True,
    allow_technique_select=True,
    allowed_techniques=["baseline", "cot", "react", "reverse_thinking", "step_back", "thot"],
    # Context — no advanced yet
    allow_context_compress=False,
    allow_context_health=False,
    allow_dedup=False,
    # Strategic — no
    allow_strategic_decision=False,
    allow_peer_review=False,
    # Channels — all including voice
    allowed_channels=["chat", "email", "sms", "api", "voice"],
    # Domain agents — all 6
    allowed_domain_agents=[
        "faq_agent", "refund_agent", "technical_agent",
        "billing_agent", "complaint_agent", "escalation_agent",
    ],
    # Approval — Pro needs approval for monetary + escalation
    needs_approval_for_escalation=True,
    needs_approval_for_refund=False,  # Pro can auto-refund within policy
    needs_approval_for_monetary=True,
    needs_approval_for_account_change=True,
    # MAKER
    maker_k_solutions=3,
    maker_use_llm=True,
    # Ask-when-unsure
    ask_client_confidence_threshold=0.4,
    allow_ask_client=True,
    # Refund batching
    allow_refund_batching=True,
    # Smart enrichment
    allow_smart_enrichment=True,
    # LLM
    llm_model_tier="medium",
    llm_max_tokens=600,
    llm_temperature=0.5,
)

HIGH_CONFIG = PermissionConfig(
    tier=VariantTier.HIGH,
    # Deep enrichment — all 5
    allowed_deep_enrichment=[
        "complaint_handler", "retention_negotiator",
        "billing_resolver", "tech_diagnostic", "shipping_tracker",
    ],
    # Quality — 2 retries, strictest threshold
    max_quality_retries=2,
    clara_threshold=95.0,
    # DSPy — always
    use_dspy=True,
    dspy_min_complexity=0.0,
    # Auto-fix + auto-action
    allow_auto_fix=True,
    allow_auto_action=True,
    auto_action_confidence_min=0.80,
    # Reasoning — Tier 1+2+3 techniques
    allow_reasoning_chain=True,
    allow_technique_select=True,
    allowed_techniques=[
        "baseline", "cot", "react", "reverse_thinking", "step_back", "thot",
        "gst", "uot", "tot", "self_consistency", "reflexion", "least_to_most",
    ],
    # Context — full management
    allow_context_compress=True,
    allow_context_health=True,
    allow_dedup=True,
    # Strategic — yes
    allow_strategic_decision=True,
    allow_peer_review=True,
    # Channels — all
    allowed_channels=["chat", "email", "sms", "api", "voice"],
    # Domain agents — all 6
    allowed_domain_agents=[
        "faq_agent", "refund_agent", "technical_agent",
        "billing_agent", "complaint_agent", "escalation_agent",
    ],
    # Approval — High only needs approval for emergencies
    needs_approval_for_escalation=False,
    needs_approval_for_refund=False,
    needs_approval_for_monetary=False,  # Within policy limits
    needs_approval_for_account_change=False,
    # MAKER
    maker_k_solutions=5,
    maker_use_llm=True,
    # Ask-when-unsure
    ask_client_confidence_threshold=0.3,
    allow_ask_client=True,
    # Refund batching
    allow_refund_batching=True,
    # Smart enrichment
    allow_smart_enrichment=True,
    # LLM
    llm_model_tier="heavy",
    llm_max_tokens=1000,
    llm_temperature=0.3,
)


# ══════════════════════════════════════════════════════════════════
# LOOKUP FUNCTION
# ══════════════════════════════════════════════════════════════════

_CONFIG_MAP = {
    VariantTier.MINI: MINI_CONFIG,
    VariantTier.PRO: PRO_CONFIG,
    VariantTier.HIGH: HIGH_CONFIG,
    "mini_parwa": MINI_CONFIG,
    "parwa": PRO_CONFIG,
    "parwa_high": HIGH_CONFIG,
    "mini": MINI_CONFIG,
    "pro": PRO_CONFIG,
    "high": HIGH_CONFIG,
}


def get_permission_config(tier: str | VariantTier) -> PermissionConfig:
    """Get the permission configuration for a variant tier.

    Args:
        tier: Variant tier string or enum value.

    Returns:
        PermissionConfig for the tier.

    Raises:
        ValueError: If tier is not recognized.
    """
    config = _CONFIG_MAP.get(tier)
    if config is None:
        # Handle VariantTier enum values that might not match string keys
        if hasattr(tier, 'value'):
            config = _CONFIG_MAP.get(tier.value)
        if config is None:
            logger.warning(
                "permission_config_unknown_tier",
                tier=str(tier),
                fallback="mini",
            )
            return MINI_CONFIG
    return config


def needs_approval(
    action_type: str,
    tier: str | VariantTier,
) -> bool:
    """Check if an action type needs human approval for this tier.

    Args:
        action_type: The action being taken (escalation, refund, monetary, account_change).
        tier: Variant tier.

    Returns:
        True if human approval is needed.
    """
    config = get_permission_config(tier)

    approval_map = {
        "escalation": config.needs_approval_for_escalation,
        "refund": config.needs_approval_for_refund,
        "monetary": config.needs_approval_for_monetary,
        "account_change": config.needs_approval_for_account_change,
    }

    return approval_map.get(action_type, True)  # Default: need approval


def is_node_allowed(
    node_name: str,
    tier: str | VariantTier,
) -> bool:
    """Check if a node is allowed to EXECUTE for this tier.

    ALL nodes exist in the graph — this determines if the node
    does real work or passes through with defaults.

    Args:
        node_name: Node name in the graph.
        tier: Variant tier.

    Returns:
        True if the node should execute for this tier.
    """
    config = get_permission_config(tier)

    # Nodes that are ALWAYS allowed (core pipeline)
    always_allowed = {
        "pii_check", "empathy_check", "emergency_check",
        "gsd_state", "classify", "extract_signals",
        "generate", "crp_compress", "clara_quality_gate",
        "format", "maker_validator", "guardrails",
        "confidence_assess", "auto_fix",
    }

    if node_name in always_allowed:
        return True

    # Domain agents — check allowed list
    if node_name.endswith("_agent") and node_name in config.allowed_domain_agents:
        return True

    # Deep enrichment — check allowed list
    if node_name in config.allowed_deep_enrichment:
        return True

    # Conditional nodes — check permission config
    conditional_map = {
        "smart_enrichment": config.allow_smart_enrichment,
        "technique_select": config.allow_technique_select,
        "reasoning_chain": config.allow_reasoning_chain,
        "context_compress": config.allow_context_compress,
        "context_health": config.allow_context_health,
        "dedup": config.allow_dedup,
        "strategic_decision": config.allow_strategic_decision,
        "peer_review": config.allow_peer_review,
        "auto_action": config.allow_auto_action,
        "dspy_optimizer": config.use_dspy,
        "quality_retry": config.max_quality_retries > 0,
    }

    if node_name in conditional_map:
        return conditional_map[node_name]

    # Unknown node — allow by default (fail-open for new nodes)
    logger.warning(
        "is_node_allowed_unknown_node",
        node_name=node_name,
        tier=str(tier),
    )
    return True
