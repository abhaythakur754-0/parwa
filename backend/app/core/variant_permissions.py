"""
Variant Task Permissions — Defines what each variant CAN and CANNOT do.

CRITICAL ARCHITECTURE DECISION:
  All 3 variants (Mini, Pro, High) have the SAME intelligence, SAME techniques,
  SAME reasoning capabilities. The ONLY difference is what ACTIONS they are
  ALLOWED to take.

  This is the "same brain, different restrictions" model:
    - Mini: Like having 3-4 smart interns — they understand everything but
            can only handle simple tasks. They escalate anything complex.
    - Pro:  Like having junior customer care employees — they can handle
            most things but need approval for high-value/destructive actions.
    - High: Like having senior employees — full autonomy on everything.

What's the SAME across all variants:
  - Same 27 nodes in the pipeline
  - Same 25 AI techniques (CoT, ReAct, ToT, UoT, GST, etc.)
  - Same reasoning depth and quality
  - Same classification accuracy
  - Same empathy and understanding
  - Same learning (MetaLearner, DSPy, Reflexion)
  - Same quality scoring

What's DIFFERENT:
  - Which TASKS they can handle (refund, cancellation, etc.)
  - Monetary limits on actions
  - Whether they can take autonomous actions
  - Whether they need approval for certain actions
  - CLARA quality threshold (how strict the quality gate is)
  - Maximum quality retries
  - Model tier (cost optimization — not intelligence limitation)

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set

logger = logging.getLogger("parwa.variant_permissions")


# ══════════════════════════════════════════════════════════════════
# TASK TYPES
# ══════════════════════════════════════════════════════════════════


class TaskType(str, Enum):
    """All possible task types a variant can encounter."""

    # General
    GENERAL_INQUIRY = "general_inquiry"
    FAQ = "faq"
    GREETING = "greeting"
    THANKS = "thanks"

    # Information
    PRODUCT_INFO = "product_info"
    POLICY_QUESTION = "policy_question"
    ORDER_STATUS = "order_status"
    SHIPPING_INFO = "shipping_info"
    TRACKING = "tracking"

    # Support
    TECHNICAL_SUPPORT = "technical_support"
    BUG_REPORT = "bug_report"
    HOW_TO = "how_to"
    PASSWORD_RESET = "password_reset"
    LOGIN_ISSUE = "login_issue"

    # Complaints & Feedback
    COMPLAINT = "complaint"
    FEEDBACK = "feedback"
    REVIEW = "review"
    DISSATISFIED = "dissatisfied"

    # Billing (restricted for Mini)
    BILLING_INQUIRY = "billing_inquiry"
    INVOICE_REQUEST = "invoice_request"
    PAYMENT_ISSUE = "payment_issue"
    REFUND_REQUEST = "refund_request"
    PARTIAL_REFUND = "partial_refund"
    CHARGEBACK = "chargeback"
    OVERCHARGE = "overcharge"
    SUBSCRIPTION_CHANGE = "subscription_change"

    # Retention (restricted for Mini)
    CANCELLATION = "cancellation"
    DOWNGRADE = "downgrade"
    RETENTION = "retention"

    # Escalation
    ESCALATION = "escalation"
    HUMAN_HANDOFF = "human_handoff"
    MANAGER_REQUEST = "manager_request"

    # Emergency
    EMERGENCY = "emergency"
    LEGAL_THREAT = "legal_threat"
    SAFETY_CONCERN = "safety_concern"
    CHARGE = "charge"  # Charge-related inquiry

    # Account
    ACCOUNT_UPDATE = "account_update"
    DATA_REQUEST = "data_request"
    PRIVACY_REQUEST = "privacy_request"


class ActionLevel(str, Enum):
    """How the variant should respond when encountering a restricted task."""
    ALLOW = "allow"                  # Handle it fully
    ALLOW_WITH_LIMIT = "allow_with_limit"  # Handle but with monetary/value limits
    INFORM_AND_ESCALATE = "inform_and_escalate"  # Acknowledge, explain limitation, escalate
    ESCALATE_IMMEDIATELY = "escalate_immediately"  # Immediately hand off to higher tier
    REFUSE_WITH_EXPLANATION = "refuse_with_explanation"  # Explain why, offer alternatives


# ══════════════════════════════════════════════════════════════════
# PERMISSION CONFIGURATION
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class VariantPermissionConfig:
    """Permission configuration for a single variant tier.

    Defines what tasks the variant can handle and what actions it can take.
    ALL variants have the same intelligence — only actions differ.
    """
    variant_tier: str

    # Tasks this variant can handle FULLY
    allowed_tasks: FrozenSet[TaskType]

    # Tasks this variant can handle but with limits
    limited_tasks: FrozenSet[TaskType]

    # Tasks this variant must escalate
    escalation_tasks: FrozenSet[TaskType]

    # Tasks this variant should refuse (with explanation)
    refused_tasks: FrozenSet[TaskType]

    # Monetary limits
    max_refund_amount: float  # Max refund amount the variant can process
    max_credit_amount: float  # Max credit/discount amount
    max_discount_percent: float  # Max discount percentage

    # Autonomous actions
    can_issue_refund: bool
    can_cancel_subscription: bool
    can_apply_credit: bool
    can_change_plan: bool
    can_send_email: bool
    can_make_phone_call: bool
    can_access_billing: bool
    can_modify_account: bool
    can_escalate_to_human: bool

    # Quality settings (NOT intelligence — just quality strictness)
    clara_threshold: float  # CLARA quality gate threshold
    max_quality_retries: int  # How many times to retry generation

    # Model tier (cost optimization, NOT intelligence limitation)
    model_tier: str  # "light", "medium", "heavy"

    # Context window
    max_context_tokens: int  # Max context window size

    # Technique tiers (ALL enabled for ALL variants now)
    enabled_technique_tiers: FrozenSet[str]  # {"tier1", "tier2", "tier3"}

    # Learning settings
    dspy_enabled: bool  # Whether DSPy auto-optimization is active
    meta_learner_enabled: bool  # Whether MetaLearner is active
    reflexion_enabled: bool  # Whether Reflexion self-correction is active


# ══════════════════════════════════════════════════════════════════
# PERMISSION DEFINITIONS FOR EACH VARIANT
# ══════════════════════════════════════════════════════════════════

# Mini Parwa — Smart intern: understands everything, handles simple tasks only
MINI_PERMISSIONS = VariantPermissionConfig(
    variant_tier="mini_parwa",
    allowed_tasks=frozenset({
        TaskType.GENERAL_INQUIRY,
        TaskType.FAQ,
        TaskType.GREETING,
        TaskType.THANKS,
        TaskType.PRODUCT_INFO,
        TaskType.POLICY_QUESTION,
        TaskType.ORDER_STATUS,
        TaskType.SHIPPING_INFO,
        TaskType.TRACKING,
        TaskType.HOW_TO,
        TaskType.PASSWORD_RESET,
        TaskType.LOGIN_ISSUE,
    }),
    limited_tasks=frozenset({
        TaskType.TECHNICAL_SUPPORT,
        TaskType.BUG_REPORT,
        TaskType.COMPLAINT,
        TaskType.FEEDBACK,
        TaskType.REVIEW,
        TaskType.BILLING_INQUIRY,
        TaskType.INVOICE_REQUEST,
    }),
    escalation_tasks=frozenset({
        TaskType.REFUND_REQUEST,
        TaskType.PARTIAL_REFUND,
        TaskType.CHARGEBACK,
        TaskType.OVERCHARGE,
        TaskType.CANCELLATION,
        TaskType.DOWNGRADE,
        TaskType.RETENTION,
        TaskType.SUBSCRIPTION_CHANGE,
        TaskType.ESCALATION,
        TaskType.HUMAN_HANDOFF,
        TaskType.MANAGER_REQUEST,
        TaskType.LEGAL_THREAT,
        TaskType.SAFETY_CONCERN,
        TaskType.CHARGE,
    }),
    refused_tasks=frozenset({
        TaskType.PAYMENT_ISSUE,  # Mini doesn't touch payment processing
    }),
    max_refund_amount=0.0,
    max_credit_amount=0.0,
    max_discount_percent=0.0,
    can_issue_refund=False,
    can_cancel_subscription=False,
    can_apply_credit=False,
    can_change_plan=False,
    can_send_email=False,
    can_make_phone_call=False,
    can_access_billing=False,
    can_modify_account=False,
    can_escalate_to_human=True,
    # Quality: Mini uses lighter quality gate but SAME techniques
    clara_threshold=70.0,
    max_quality_retries=1,
    # Model: Light model (cost optimization, NOT dumber)
    model_tier="light",
    # Context: Smaller context for cost efficiency
    max_context_tokens=8000,
    # ALL technique tiers enabled — same intelligence as High
    enabled_technique_tiers=frozenset({"tier1", "tier2", "tier3"}),
    # Learning: ALL learning enabled for ALL variants
    dspy_enabled=True,
    meta_learner_enabled=True,
    reflexion_enabled=True,
)

# Pro Parwa — Junior employee: handles most things, needs approval for big stuff
PRO_PERMISSIONS = VariantPermissionConfig(
    variant_tier="parwa",
    allowed_tasks=frozenset({
        TaskType.GENERAL_INQUIRY,
        TaskType.FAQ,
        TaskType.GREETING,
        TaskType.THANKS,
        TaskType.PRODUCT_INFO,
        TaskType.POLICY_QUESTION,
        TaskType.ORDER_STATUS,
        TaskType.SHIPPING_INFO,
        TaskType.TRACKING,
        TaskType.HOW_TO,
        TaskType.PASSWORD_RESET,
        TaskType.LOGIN_ISSUE,
        TaskType.TECHNICAL_SUPPORT,
        TaskType.BUG_REPORT,
        TaskType.COMPLAINT,
        TaskType.FEEDBACK,
        TaskType.REVIEW,
        TaskType.DISSATISFIED,
        TaskType.BILLING_INQUIRY,
        TaskType.INVOICE_REQUEST,
        TaskType.PAYMENT_ISSUE,
        TaskType.OVERCHARGE,
    }),
    limited_tasks=frozenset({
        TaskType.REFUND_REQUEST,
        TaskType.PARTIAL_REFUND,
        TaskType.SUBSCRIPTION_CHANGE,
        TaskType.ACCOUNT_UPDATE,
        TaskType.DATA_REQUEST,
    }),
    escalation_tasks=frozenset({
        TaskType.CHARGEBACK,
        TaskType.CANCELLATION,
        TaskType.DOWNGRADE,
        TaskType.RETENTION,
        TaskType.ESCALATION,
        TaskType.HUMAN_HANDOFF,
        TaskType.MANAGER_REQUEST,
        TaskType.LEGAL_THREAT,
        TaskType.SAFETY_CONCERN,
    }),
    refused_tasks=frozenset(),
    max_refund_amount=500.0,
    max_credit_amount=200.0,
    max_discount_percent=15.0,
    can_issue_refund=True,
    can_cancel_subscription=False,
    can_apply_credit=True,
    can_change_plan=False,
    can_send_email=True,
    can_make_phone_call=False,
    can_access_billing=True,
    can_modify_account=True,
    can_escalate_to_human=True,
    # Quality: Standard quality gate
    clara_threshold=85.0,
    max_quality_retries=2,
    # Model: Medium model
    model_tier="medium",
    # Context: Medium context
    max_context_tokens=16000,
    # ALL technique tiers
    enabled_technique_tiers=frozenset({"tier1", "tier2", "tier3"}),
    # Learning: ALL learning enabled
    dspy_enabled=True,
    meta_learner_enabled=True,
    reflexion_enabled=True,
)

# High Parwa — Senior employee: full autonomy
HIGH_PERMISSIONS = VariantPermissionConfig(
    variant_tier="parwa_high",
    allowed_tasks=frozenset({
        TaskType.GENERAL_INQUIRY,
        TaskType.FAQ,
        TaskType.GREETING,
        TaskType.THANKS,
        TaskType.PRODUCT_INFO,
        TaskType.POLICY_QUESTION,
        TaskType.ORDER_STATUS,
        TaskType.SHIPPING_INFO,
        TaskType.TRACKING,
        TaskType.HOW_TO,
        TaskType.PASSWORD_RESET,
        TaskType.LOGIN_ISSUE,
        TaskType.TECHNICAL_SUPPORT,
        TaskType.BUG_REPORT,
        TaskType.COMPLAINT,
        TaskType.FEEDBACK,
        TaskType.REVIEW,
        TaskType.DISSATISFIED,
        TaskType.BILLING_INQUIRY,
        TaskType.INVOICE_REQUEST,
        TaskType.PAYMENT_ISSUE,
        TaskType.OVERCHARGE,
        TaskType.REFUND_REQUEST,
        TaskType.PARTIAL_REFUND,
        TaskType.CHARGEBACK,
        TaskType.SUBSCRIPTION_CHANGE,
        TaskType.CANCELLATION,
        TaskType.DOWNGRADE,
        TaskType.RETENTION,
        TaskType.ACCOUNT_UPDATE,
        TaskType.DATA_REQUEST,
        TaskType.PRIVACY_REQUEST,
    }),
    limited_tasks=frozenset(),
    escalation_tasks=frozenset({
        TaskType.ESCALATION,
        TaskType.HUMAN_HANDOFF,
        TaskType.MANAGER_REQUEST,
        TaskType.LEGAL_THREAT,
        TaskType.SAFETY_CONCERN,
        TaskType.EMERGENCY,
    }),
    refused_tasks=frozenset(),
    max_refund_amount=50000.0,
    max_credit_amount=5000.0,
    max_discount_percent=50.0,
    can_issue_refund=True,
    can_cancel_subscription=True,
    can_apply_credit=True,
    can_change_plan=True,
    can_send_email=True,
    can_make_phone_call=True,
    can_access_billing=True,
    can_modify_account=True,
    can_escalate_to_human=True,
    # Quality: Strictest quality gate
    clara_threshold=95.0,
    max_quality_retries=2,
    # Model: Heavy model
    model_tier="heavy",
    # Context: Full context
    max_context_tokens=32000,
    # ALL technique tiers
    enabled_technique_tiers=frozenset({"tier1", "tier2", "tier3"}),
    # Learning: ALL learning enabled
    dspy_enabled=True,
    meta_learner_enabled=True,
    reflexion_enabled=True,
)


# ══════════════════════════════════════════════════════════════════
# PERMISSION LOOKUP
# ══════════════════════════════════════════════════════════════════

# Registry of all permission configs
_PERMISSIONS: Dict[str, VariantPermissionConfig] = {
    "mini_parwa": MINI_PERMISSIONS,
    "parwa": PRO_PERMISSIONS,
    "parwa_high": HIGH_PERMISSIONS,
    # Legacy aliases
    "mini": MINI_PERMISSIONS,
    "pro": PRO_PERMISSIONS,
    "high": HIGH_PERMISSIONS,
}


def get_permissions(variant_tier: str) -> VariantPermissionConfig:
    """Get the permission configuration for a variant tier.

    Args:
        variant_tier: The variant tier identifier.

    Returns:
        Permission configuration. Falls back to Mini if unknown tier.
    """
    return _PERMISSIONS.get(variant_tier, MINI_PERMISSIONS)


def check_task_permission(
    variant_tier: str,
    task_type: TaskType | str,
) -> ActionLevel:
    """Check if a variant can handle a specific task type.

    Returns how the variant should respond:
      - ALLOW: Handle it fully
      - ALLOW_WITH_LIMIT: Handle but with value limits
      - INFORM_AND_ESCALATE: Acknowledge, explain limitation, escalate
      - ESCALATE_IMMEDIATELY: Hand off immediately
      - REFUSE_WITH_EXPLANATION: Explain why, offer alternatives

    Args:
        variant_tier: The variant tier.
        task_type: The task type to check.

    Returns:
        ActionLevel indicating how to respond.
    """
    try:
        perms = get_permissions(variant_tier)

        # Normalize task type
        if isinstance(task_type, str):
            task_type = TaskType(task_type)

        if task_type in perms.allowed_tasks:
            return ActionLevel.ALLOW

        if task_type in perms.limited_tasks:
            return ActionLevel.ALLOW_WITH_LIMIT

        if task_type in perms.escalation_tasks:
            return ActionLevel.INFORM_AND_ESCALATE

        if task_type in perms.refused_tasks:
            return ActionLevel.REFUSE_WITH_EXPLANATION

        # Default: allow with limit (be permissive rather than restrictive)
        return ActionLevel.ALLOW_WITH_LIMIT

    except (ValueError, KeyError):
        logger.warning("check_task_permission: unknown task_type=%s variant=%s", task_type, variant_tier)
        return ActionLevel.ALLOW_WITH_LIMIT
    except Exception:
        return ActionLevel.ALLOW_WITH_LIMIT


def check_monetary_permission(
    variant_tier: str,
    action: str,
    amount: float,
) -> ActionLevel:
    """Check if a variant can perform a monetary action.

    Args:
        variant_tier: The variant tier.
        action: "refund", "credit", "discount"
        amount: The monetary amount.

    Returns:
        ActionLevel indicating how to respond.
    """
    try:
        perms = get_permissions(variant_tier)

        if action == "refund":
            if not perms.can_issue_refund:
                return ActionLevel.INFORM_AND_ESCALATE
            if amount <= perms.max_refund_amount:
                return ActionLevel.ALLOW
            return ActionLevel.INFORM_AND_ESCALATE

        if action == "credit":
            if not perms.can_apply_credit:
                return ActionLevel.INFORM_AND_ESCALATE
            if amount <= perms.max_credit_amount:
                return ActionLevel.ALLOW
            return ActionLevel.INFORM_AND_ESCALATE

        if action == "discount":
            if amount <= perms.max_discount_percent:
                return ActionLevel.ALLOW
            return ActionLevel.INFORM_AND_ESCALATE

        return ActionLevel.ALLOW_WITH_LIMIT

    except Exception:
        return ActionLevel.ALLOW_WITH_LIMIT


def get_escalation_message(
    variant_tier: str,
    task_type: TaskType | str,
) -> str:
    """Get a natural escalation message for when a variant can't handle a task.

    The variant UNDERSTANDS the task (same intelligence) but is not
    AUTHORIZED to handle it. This generates a helpful, empathetic message
    that acknowledges the customer's need and explains the handoff.

    Args:
        variant_tier: The variant tier.
        task_type: The task type being escalated.

    Returns:
        A natural escalation message.
    """
    try:
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                task_type = TaskType.GENERAL_INQUIRY

        # Map task types to natural escalation messages
        _messages: Dict[TaskType, str] = {
            TaskType.REFUND_REQUEST: (
                "I completely understand your refund request, and I want to make sure "
                "this gets handled properly for you. Let me connect you with a specialist "
                "who can process this right away."
            ),
            TaskType.PARTIAL_REFUND: (
                "I understand your concern about the charges. Let me get someone "
                "who can review this and process the appropriate adjustment for you."
            ),
            TaskType.CANCELLATION: (
                "I hear you, and I want to make sure we find the best solution. "
                "Let me connect you with our retention specialist who can help "
                "explore all your options."
            ),
            TaskType.CHARGEBACK: (
                "I understand your concern about this charge. This needs careful "
                "review, so let me connect you with our billing specialist right away."
            ),
            TaskType.SUBSCRIPTION_CHANGE: (
                "I'd love to help with your subscription change. Let me get you "
                "to someone who can make that happen for you."
            ),
            TaskType.LEGAL_THREAT: (
                "I understand your frustration, and I take this very seriously. "
                "Let me connect you with our senior team immediately."
            ),
            TaskType.SAFETY_CONCERN: (
                "Your safety is our top priority. Let me connect you with someone "
                "who can address this immediately."
            ),
            TaskType.MANAGER_REQUEST: (
                "Absolutely, I'll connect you with a manager right away."
            ),
        }

        return _messages.get(
            task_type,
            "I want to make sure you get the best help possible. "
            "Let me connect you with a specialist who can assist you further.",
        )

    except Exception:
        return "Let me connect you with someone who can help you further."


def get_permission_summary(variant_tier: str) -> Dict[str, Any]:
    """Get a summary of permissions for a variant tier.

    Useful for logging, debugging, and UI display.

    Args:
        variant_tier: The variant tier.

    Returns:
        Dict with permission summary.
    """
    try:
        perms = get_permissions(variant_tier)
        return {
            "variant_tier": perms.variant_tier,
            "allowed_task_count": len(perms.allowed_tasks),
            "limited_task_count": len(perms.limited_tasks),
            "escalation_task_count": len(perms.escalation_tasks),
            "refused_task_count": len(perms.refused_tasks),
            "can_issue_refund": perms.can_issue_refund,
            "can_cancel_subscription": perms.can_cancel_subscription,
            "can_apply_credit": perms.can_apply_credit,
            "max_refund_amount": perms.max_refund_amount,
            "clara_threshold": perms.clara_threshold,
            "max_quality_retries": perms.max_quality_retries,
            "model_tier": perms.model_tier,
            "max_context_tokens": perms.max_context_tokens,
            "technique_tiers": sorted(perms.enabled_technique_tiers),
            "learning_enabled": {
                "dspy": perms.dspy_enabled,
                "meta_learner": perms.meta_learner_enabled,
                "reflexion": perms.reflexion_enabled,
            },
        }
    except Exception:
        return {"error": "failed_to_get_permissions"}
