"""
Tier Permissions — Defines WHAT each variant tier CAN and CANNOT do.

This is the CORE of the "same capability, different restrictions" philosophy.
ALL variants have the same intelligence (same nodes, same reasoning depth),
but they are RESTRICTED from certain actions based on their tier.

Think of it like employee levels:
  - Intern (Mini): Smart enough to understand everything, but NOT authorized
    to issue refunds, offer compensation, or make strategic decisions
  - Junior (Pro): Can handle standard operations, limited compensation,
    can escalate but not override
  - Senior (High): Full authority, can do everything, override decisions

Permission Categories:
  1. ACTION_PERMISSIONS — What the variant is ALLOWED to do
     - refund: Can process refunds?
     - compensation: Can offer compensation/discounts?
     - escalation: Can escalate to human?
     - auto_fix: Can apply automated fixes?
     - override: Can override previous decisions?
     - strategic: Can make strategic decisions (retention offers, win-back)?
     - monetary: Any action involving money?
     - data_access: Level of customer data access
     - notification: Can send proactive notifications?
     - cancellation: Can process cancellations?

  2. EXECUTION_LIMITS — How far the variant can go
     - max_refund_amount: Maximum refund without approval
     - max_compensation_amount: Maximum compensation
     - max_retries: How many quality retries allowed
     - quality_threshold: Minimum quality score to pass
     - max_escalation_level: Highest escalation tier allowed
     - max_conversation_turns: Auto-escalate after N turns

  3. APPROVAL_REQUIREMENTS — What needs human sign-off
     - Every action that exceeds the tier's limits needs approval
     - Approval goes through Jarvis Command Graph → approval_gate

Usage:
    from app.core.variant_engine.tier_permissions import (
        TierPermissions,
        get_permissions,
        check_permission,
    )

    # Get full permissions for a tier
    perms = get_permissions("mini_parwa")

    # Check a specific permission
    if check_permission("mini_parwa", "refund"):
        # Mini is allowed to refund (it CAN, but with limits)
        ...

    # Check if an action needs approval
    if needs_approval("mini_parwa", "refund", amount=50.0):
        # Route to approval gate
        ...

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("tier_permissions")


# ══════════════════════════════════════════════════════════════════
# PERMISSION DEFINITIONS
# ══════════════════════════════════════════════════════════════════


class TierPermissions:
    """Permission configuration for a variant tier.

    This defines what a variant CAN do and what its LIMITS are.
    The variant's INTELLIGENCE is the same across all tiers —
    it's the AUTHORIZATION that differs.

    Analogy:
        A junior doctor and a senior doctor both went to medical school
        (same knowledge). The junior can't perform surgery (not authorized),
        but they CAN diagnose the same conditions (same capability).
    """

    def __init__(
        self,
        tier: str,
        action_permissions: Dict[str, bool],
        execution_limits: Dict[str, Any],
        approval_requirements: Dict[str, Any],
        restricted_actions: List[str],
        description: str = "",
    ):
        self.tier = tier
        self.action_permissions = action_permissions
        self.execution_limits = execution_limits
        self.approval_requirements = approval_requirements
        self.restricted_actions = restricted_actions
        self.description = description


# ── MINI PARWA PERMISSIONS ────────────────────────────────────────
# Mini = Smart intern. Understands everything, but restricted actions.
# Can diagnose, classify, suggest — but can't EXECUTE most actions.
# Must escalate to Pro/High or get human approval for actions.

MINI_PARWA_PERMISSIONS = TierPermissions(
    tier="mini_parwa",
    description=(
        "Mini Parwa — Smart Intern Level. Same intelligence as Pro/High, "
        "but restricted from executing most actions. Can diagnose, analyze, "
        "and recommend — but must escalate for refunds, compensation, "
        "strategic decisions, and monetary actions."
    ),
    action_permissions={
        # ── What Mini CAN do ──
        "classify": True,           # Classify intents (same as Pro/High)
        "analyze_sentiment": True,  # Full sentiment analysis
        "detect_emergency": True,   # Emergency detection (critical safety)
        "detect_pii": True,         # PII redaction (privacy requirement)
        "extract_signals": True,    # Signal extraction (same capability)
        "select_technique": True,   # Technique selection (same reasoning)
        "reason": True,             # Full reasoning chain
        "generate_response": True,  # Response generation
        "quality_check": True,      # Quality gate validation
        "deep_enrichment": True,    # Deep enrichment (complaint, billing, etc.)
        "empathy": True,            # Empathy engine
        "context_enrich": True,     # Context enrichment
        "context_compress": True,   # Context compression
        "dedup_check": True,        # Dedup checking
        "peer_review": True,        # Peer review logic
        "smart_enrichment": True,   # Smart enrichment (EI, churn, etc.)

        # ── What Mini CAN do (with approval required) ──
        "auto_fix": True,           # CAN auto-fix (needs approval) — same CAPABILITY
        "refund_preview": True,     # CAN preview refunds (must show to customer first)

        # ── What Mini CAN do with restrictions ──
        "escalation": True,           # CAN escalate to human (critical safety net)

        # ── What Mini CANNOT do (restricted) ──
        "refund": False,            # Cannot process refunds (but CAN preview them)
        "compensation": False,      # Cannot offer compensation/discounts
        "override": False,          # Cannot override previous decisions
        "strategic_decision": False, # Cannot make strategic decisions
        "monetary": False,          # Cannot take ANY monetary action
        "cancellation": False,      # Cannot process cancellations
        "winback": False,           # Cannot initiate win-back sequences
        "paddle_dispute": False,    # Cannot auto-resolve Paddle disputes
        "carrier_api": False,       # Cannot call carrier APIs
        "proactive_notification": False,  # Cannot send proactive notifications
        "retention_offer": False,   # Cannot offer retention deals
        "auto_escalation": False,   # Cannot auto-escalate (must suggest)
    },
    execution_limits={
        "max_refund_amount": 0.0,           # No refunds at all
        "max_compensation_amount": 0.0,     # No compensation
        "max_retries": 1,                   # 1 quality retry
        "quality_threshold": 0.70,          # 70% quality threshold
        "max_escalation_level": "tier_1",   # Can only suggest tier 1 escalation
        "max_conversation_turns": 5,        # Auto-escalate after 5 turns
        "max_tokens_per_response": 500,     # Token limit per response
        "response_style": "concise",        # Concise responses
    },
    approval_requirements={
        "refund": "always",                 # Refunds always need approval
        "compensation": "always",           # Compensation always needs approval
        "escalation": "always",             # Escalations always need approval
        "cancellation": "always",           # Cancellations always need approval
        "monetary": "always",               # Any monetary action needs approval
        "strategic": "always",              # Strategic decisions need approval
        "auto_fix": "always",               # Auto-fixes need approval
        "override": "always",               # Overrides need approval
        "notification": "always",           # Proactive notifications need approval
        "data_export": "always",            # Data export needs approval
    },
    restricted_actions=[
        "refund", "compensation", "override",
        "strategic_decision", "monetary", "cancellation", "winback",
        "paddle_dispute", "carrier_api", "proactive_notification",
        "retention_offer", "auto_escalation",
        # NOTE: auto_fix is NOT restricted — Mini has same CAPABILITY
        # but needs approval (auto_fix: True with approval_required: always)
    ],
)


# ── PRO PARWA PERMISSIONS ─────────────────────────────────────────
# Pro = Junior employee. Can handle standard operations with limits.
# Can process small refunds, offer limited compensation, auto-escalate.
# Needs approval for large amounts and strategic decisions.

PRO_PARWA_PERMISSIONS = TierPermissions(
    tier="parwa",
    description=(
        "Pro Parwa — Junior Employee Level. Same intelligence as Mini/High, "
        "but with standard operational authority. Can process refunds up to "
        "a limit, offer limited compensation, auto-escalate, and handle "
        "cancellations with approval. Needs approval for strategic decisions "
        "and large monetary actions."
    ),
    action_permissions={
        # ── What Pro CAN do ──
        "classify": True,
        "analyze_sentiment": True,
        "detect_emergency": True,
        "detect_pii": True,
        "extract_signals": True,
        "select_technique": True,
        "reason": True,
        "generate_response": True,
        "quality_check": True,
        "deep_enrichment": True,
        "empathy": True,
        "context_enrich": True,
        "context_compress": True,
        "dedup_check": True,
        "peer_review": True,
        "smart_enrichment": True,

        # ── What Pro CAN do (that Mini can't) ──
        "refund": True,             # Can process refunds (with limits)
        "compensation": True,       # Can offer limited compensation
        "auto_fix": True,           # Can apply automated fixes
        "auto_escalation": True,    # Can auto-escalate
        "escalation": True,         # Can escalate to human
        "cancellation": True,       # Can process cancellations (with approval)
        "paddle_dispute": True,     # Can auto-resolve Paddle disputes
        "carrier_api": True,        # Can call carrier APIs
        "proactive_notification": True,  # Can send proactive notifications
        "refund_preview": True,     # Can preview and batch refunds

        # ── What Pro CANNOT do (restricted) ──
        "override": False,          # Cannot override previous decisions
        "strategic_decision": False, # Cannot make strategic decisions
        "strategic": False,         # Alias for strategic_decision
        "monetary": False,          # Cannot take large monetary actions
        "winback": False,           # Cannot initiate win-back sequences
        "retention_offer": False,   # Cannot offer retention deals
    },
    execution_limits={
        "max_refund_amount": 100.0,         # Refunds up to $100
        "max_compensation_amount": 50.0,    # Compensation up to $50
        "max_retries": 2,                   # 2 quality retries
        "quality_threshold": 0.80,          # 80% quality threshold
        "max_escalation_level": "tier_2",   # Can escalate to tier 2
        "max_conversation_turns": 10,       # Auto-escalate after 10 turns
        "max_tokens_per_response": 1000,    # Token limit per response
        "response_style": "balanced",       # Balanced responses
    },
    approval_requirements={
        "refund": "over_limit",             # Needs approval if over $100
        "compensation": "over_limit",       # Needs approval if over $50
        "escalation": "tier_3_plus",        # Needs approval for tier 3+
        "cancellation": "high_value",       # Needs approval for high-value accounts
        "monetary": "over_limit",           # Needs approval if over limits
        "strategic": "always",              # Strategic decisions always need approval
        "auto_fix": "high_risk",            # High-risk auto-fixes need approval
        "override": "always",               # Overrides always need approval
        "notification": "never",            # Proactive notifications don't need approval
        "data_export": "always",            # Data export needs approval
    },
    restricted_actions=[
        "override", "strategic_decision", "monetary",
        "winback", "retention_offer",
    ],
)


# ── HIGH PARWA PERMISSIONS ────────────────────────────────────────
# High = Senior employee. Full authority, can do everything.
# Only needs approval for extreme/exceptional actions.

HIGH_PARWA_PERMISSIONS = TierPermissions(
    tier="parwa_high",
    description=(
        "High Parwa — Senior Employee Level. Same intelligence as Mini/Pro, "
        "but with full authority. Can process unlimited refunds, offer "
        "compensation, make strategic decisions, override previous decisions, "
        "and initiate win-back sequences. Only needs approval for extreme "
        "actions (e.g., very large refunds, legal-sensitive overrides)."
    ),
    action_permissions={
        # ── High can do EVERYTHING ──
        "classify": True,
        "analyze_sentiment": True,
        "detect_emergency": True,
        "detect_pii": True,
        "extract_signals": True,
        "select_technique": True,
        "reason": True,
        "generate_response": True,
        "quality_check": True,
        "deep_enrichment": True,
        "empathy": True,
        "context_enrich": True,
        "context_compress": True,
        "dedup_check": True,
        "peer_review": True,
        "smart_enrichment": True,

        # ── Full action authority ──
        "refund": True,
        "compensation": True,
        "auto_fix": True,
        "override": True,
        "strategic_decision": True,
        "strategic": True,         # Alias for strategic_decision
        "monetary": True,
        "cancellation": True,
        "winback": True,
        "paddle_dispute": True,
        "carrier_api": True,
        "proactive_notification": True,
        "retention_offer": True,
        "auto_escalation": True,
        "escalation": True,       # Can escalate freely
        "refund_preview": True,     # Can preview and batch refunds
    },
    execution_limits={
        "max_refund_amount": 10000.0,       # Refunds up to $10,000
        "max_compensation_amount": 5000.0,  # Compensation up to $5,000
        "max_retries": 3,                   # 3 quality retries
        "quality_threshold": 0.90,          # 90% quality threshold
        "max_escalation_level": "tier_3",   # Can escalate to tier 3
        "max_conversation_turns": 20,       # Auto-escalate after 20 turns
        "max_tokens_per_response": 2000,    # Token limit per response
        "response_style": "comprehensive",  # Comprehensive responses
    },
    approval_requirements={
        "refund": "over_10000",             # Only extreme refunds need approval
        "compensation": "over_5000",        # Only extreme compensation
        "escalation": "never",              # Can escalate freely
        "cancellation": "enterprise_only",  # Only enterprise accounts need approval
        "monetary": "over_10000",           # Only extreme amounts
        "strategic": "never",               # Can make strategic decisions
        "auto_fix": "never",                # Can auto-fix freely
        "override": "legal_sensitive",      # Only legal-sensitive overrides
        "notification": "never",            # Can notify freely
        "data_export": "bulk_only",         # Only bulk exports need approval
    },
    restricted_actions=[],  # No restricted actions for High
)


# ══════════════════════════════════════════════════════════════════
# PERMISSION REGISTRY
# ══════════════════════════════════════════════════════════════════

_TIER_REGISTRY: Dict[str, TierPermissions] = {
    "mini_parwa": MINI_PARWA_PERMISSIONS,
    "parwa": PRO_PARWA_PERMISSIONS,
    "parwa_high": HIGH_PARWA_PERMISSIONS,
}


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════


def get_permissions(variant_tier: str) -> TierPermissions:
    """Get the full permission configuration for a variant tier.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'

    Returns:
        TierPermissions object with all permissions and limits.

    Raises:
        ValueError: If variant_tier is unknown.
    """
    try:
        perms = _TIER_REGISTRY.get(variant_tier)
        if perms is None:
            logger.warning(
                "Unknown variant_tier '%s' — defaulting to mini_parwa",
                variant_tier,
            )
            return MINI_PARWA_PERMISSIONS
        return perms
    except Exception:
        logger.exception("get_permissions_error — defaulting to mini_parwa")
        return MINI_PARWA_PERMISSIONS


def check_permission(variant_tier: str, action: str) -> bool:
    """Check if a variant tier is allowed to perform an action.

    This is the GATEKEEPER. Every node that wants to EXECUTE an action
    (not just think about it) must check this first.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'
        action: The action to check (e.g., 'refund', 'compensation')

    Returns:
        True if the action is permitted, False otherwise.
    """
    try:
        perms = get_permissions(variant_tier)
        allowed = perms.action_permissions.get(action, False)

        if not allowed:
            logger.info(
                "Permission denied: tier=%s, action=%s — restricted",
                variant_tier, action,
            )

        return allowed
    except Exception:
        logger.exception(
            "check_permission_error: tier=%s, action=%s — denying",
            variant_tier, action,
        )
        return False  # Fail-closed: deny on error


def needs_approval(
    variant_tier: str,
    action: str,
    amount: Optional[float] = None,
    risk_level: str = "normal",
    account_value: str = "standard",
) -> bool:
    """Check if an action needs human approval before execution.

    This is used by the approval_gate node in Jarvis Command Graph.
    Even if a tier CAN do something, certain circumstances require
    human sign-off.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'
        action: The action being attempted
        amount: Monetary amount involved (if applicable)
        risk_level: 'normal' | 'high' | 'critical'
        account_value: 'standard' | 'high_value' | 'enterprise'

    Returns:
        True if human approval is needed, False if auto-approved.
    """
    try:
        perms = get_permissions(variant_tier)
        approval_rule = perms.approval_requirements.get(action, "always")

        if approval_rule == "never":
            return False

        if approval_rule == "always":
            return True

        if approval_rule == "over_limit":
            limit = perms.execution_limits.get(
                f"max_{action}_amount", 0.0
            )
            if amount is not None and amount > limit:
                return True
            return False

        if approval_rule == "over_10000":
            if amount is not None and amount > 10000.0:
                return True
            return False

        if approval_rule == "over_5000":
            if amount is not None and amount > 5000.0:
                return True
            return False

        if approval_rule == "high_risk":
            return risk_level in ("high", "critical")

        if approval_rule == "tier_3_plus":
            return risk_level == "critical"

        if approval_rule == "high_value":
            return account_value in ("high_value", "enterprise")

        if approval_rule == "enterprise_only":
            return account_value == "enterprise"

        if approval_rule == "legal_sensitive":
            return risk_level == "critical"

        if approval_rule == "bulk_only":
            return False  # Determined by other factors

        # Default: need approval if we can't determine
        return True

    except Exception:
        logger.exception(
            "needs_approval_error: tier=%s, action=%s — requiring approval",
            variant_tier, action,
        )
        return True  # Fail-closed: require approval on error


def get_execution_limit(variant_tier: str, limit_name: str) -> Any:
    """Get an execution limit for a variant tier.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'
        limit_name: Name of the limit (e.g., 'max_refund_amount')

    Returns:
        The limit value, or a safe default if not found.
    """
    try:
        perms = get_permissions(variant_tier)
        return perms.execution_limits.get(limit_name)
    except Exception:
        logger.exception(
            "get_execution_limit_error: tier=%s, limit=%s",
            variant_tier, limit_name,
        )
        return None


def get_restricted_actions(variant_tier: str) -> List[str]:
    """Get the list of actions that are RESTRICTED for this tier.

    Restricted means the variant understands these concepts but
    is NOT authorized to execute them. The node should:
    1. Still ANALYZE and REASON about the action
    2. SUGGEST the action to a human or higher tier
    3. NOT execute the action directly

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'

    Returns:
        List of restricted action names.
    """
    try:
        perms = get_permissions(variant_tier)
        return list(perms.restricted_actions)
    except Exception:
        logger.exception(
            "get_restricted_actions_error: tier=%s", variant_tier,
        )
        return ["refund", "compensation", "monetary", "strategic_decision"]


def get_quality_threshold(variant_tier: str) -> float:
    """Get the quality threshold for a variant tier.

    All variants go through the quality gate, but with different
    thresholds. Mini is 70%, Pro is 80%, High is 90%.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'

    Returns:
        Quality threshold float (0.0-1.0).
    """
    return get_execution_limit(variant_tier, "quality_threshold") or 0.70


def get_max_retries(variant_tier: str) -> int:
    """Get the maximum quality retries for a variant tier.

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'

    Returns:
        Maximum retry count.
    """
    return get_execution_limit(variant_tier, "max_retries") or 1


def build_permission_context(variant_tier: str) -> Dict[str, Any]:
    """Build a complete permission context for injection into prompts.

    This creates a structured object that tells the LLM what it CAN
    and CANNOT do. The LLM uses this to shape its response —
    e.g., "I can help you with that refund request. Let me escalate
    this to our specialist team who can process it for you."

    Args:
        variant_tier: 'mini_parwa' | 'parwa' | 'parwa_high'

    Returns:
        Dict with all permission information formatted for prompt injection.
    """
    try:
        perms = get_permissions(variant_tier)

        # Build "can do" list
        can_do = [
            action for action, allowed in perms.action_permissions.items()
            if allowed
        ]

        # Build "cannot do" list
        cannot_do = [
            action for action, allowed in perms.action_permissions.items()
            if not allowed
        ]

        # Build key limits
        limits = perms.execution_limits

        return {
            "tier": variant_tier,
            "description": perms.description,
            "can_do": can_do,
            "cannot_do": cannot_do,
            "restricted_actions": perms.restricted_actions,
            "key_limits": {
                "max_refund": limits.get("max_refund_amount", 0),
                "max_compensation": limits.get("max_compensation_amount", 0),
                "quality_threshold": limits.get("quality_threshold", 0.7),
                "max_retries": limits.get("max_retries", 1),
                "max_turns": limits.get("max_conversation_turns", 5),
                "response_style": limits.get("response_style", "concise"),
            },
            "approval_rules": perms.approval_requirements,
        }

    except Exception:
        logger.exception(
            "build_permission_context_error: tier=%s", variant_tier,
        )
        # Safe fallback — most restrictive
        return {
            "tier": variant_tier,
            "description": "Restricted mode — error loading permissions",
            "can_do": ["classify", "generate_response", "empathy"],
            "cannot_do": ["refund", "compensation", "monetary", "strategic_decision"],
            "restricted_actions": ["refund", "compensation", "monetary", "strategic_decision"],
            "key_limits": {
                "max_refund": 0,
                "max_compensation": 0,
                "quality_threshold": 0.7,
                "max_retries": 1,
                "max_turns": 5,
                "response_style": "concise",
            },
            "approval_rules": {"refund": "always", "compensation": "always"},
        }
