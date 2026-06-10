"""Variant configurations for Mini PARWA, PARWA, and PARWA High.

Same Brain, Different Capacity.
All variants share identical AI (22 nodes, 6 agents, 7 frameworks).
The difference is Volume x Channels x Concurrency x Action Permissions.
"""

from __future__ import annotations

from parwa.state import ActionType, ExecutionMode, TicketChannel


# ─── Variant Definitions ────────────────────────────────────────────────────────

MINI_PARWA = "mini"
PARWA = "parwa"
PARWA_HIGH = "high"

VARIANT_NAMES = {MINI_PARWA, PARWA, PARWA_HIGH}


# ─── Variant Pricing & Capacity ─────────────────────────────────────────────────

VARIANT_CONFIG: dict[str, dict] = {
    MINI_PARWA: {
        "price_monthly": 999,
        "tickets_per_month": 500,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT],
        "concurrent_tickets": 3,
        "ai_resolution_rate": 0.60,
        "voice_addon_price": 199,
    },
    PARWA: {
        "price_monthly": 2499,
        "tickets_per_month": 2000,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT, TicketChannel.SOCIAL],
        "concurrent_tickets": 4,
        "ai_resolution_rate": 0.75,
        "voice_addon_price": 199,
    },
    PARWA_HIGH: {
        "price_monthly": 4999,
        "tickets_per_month": 5000,
        "channels": [TicketChannel.EMAIL, TicketChannel.CHAT, TicketChannel.SOCIAL, TicketChannel.VOICE],
        "concurrent_tickets": 6,
        "ai_resolution_rate": 0.85,
        "voice_addon_price": 0,  # included
    },
}


# ─── Action Permission Matrix ───────────────────────────────────────────────────
# Mini PARWA: Execute basics + Recommend restricted
# PARWA: Execute all
# PARWA High: Execute all + analytics + bulk + custom

ACTION_PERMISSIONS: dict[str, dict[ActionType, ExecutionMode]] = {
    MINI_PARWA: {
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE,
        ActionType.PROCESS_REFUND: ExecutionMode.RECOMMEND,
        ActionType.CANCEL_ORDER: ExecutionMode.RECOMMEND,
        ActionType.MODIFY_ACCOUNT: ExecutionMode.RECOMMEND,
        ActionType.VOICE_CALL: ExecutionMode.DENY,       # add-on only
        ActionType.POST_SOCIAL: ExecutionMode.DENY,       # no social channel
        ActionType.BULK_OPERATION: ExecutionMode.DENY,
        ActionType.API_WEBHOOK: ExecutionMode.DENY,
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.DENY,
        ActionType.ACCESS_ANALYTICS: ExecutionMode.DENY,
    },
    PARWA: {
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE,
        ActionType.PROCESS_REFUND: ExecutionMode.EXECUTE,
        ActionType.CANCEL_ORDER: ExecutionMode.EXECUTE,
        ActionType.MODIFY_ACCOUNT: ExecutionMode.EXECUTE,
        ActionType.VOICE_CALL: ExecutionMode.DENY,       # add-on only
        ActionType.POST_SOCIAL: ExecutionMode.EXECUTE,
        ActionType.BULK_OPERATION: ExecutionMode.DENY,
        ActionType.API_WEBHOOK: ExecutionMode.EXECUTE,
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.EXECUTE,
        ActionType.ACCESS_ANALYTICS: ExecutionMode.DENY,
    },
    PARWA_HIGH: {
        ActionType.SEND_REPLY: ExecutionMode.EXECUTE,
        ActionType.SHARE_FAQ: ExecutionMode.EXECUTE,
        ActionType.SHARE_POLICY: ExecutionMode.EXECUTE,
        ActionType.CREATE_NOTE: ExecutionMode.EXECUTE,
        ActionType.ESCALATE_TO_HUMAN: ExecutionMode.EXECUTE,
        ActionType.PROCESS_REFUND: ExecutionMode.EXECUTE,
        ActionType.CANCEL_ORDER: ExecutionMode.EXECUTE,
        ActionType.MODIFY_ACCOUNT: ExecutionMode.EXECUTE,
        ActionType.VOICE_CALL: ExecutionMode.EXECUTE,    # included
        ActionType.POST_SOCIAL: ExecutionMode.EXECUTE,
        ActionType.BULK_OPERATION: ExecutionMode.EXECUTE,
        ActionType.API_WEBHOOK: ExecutionMode.EXECUTE,
        ActionType.CUSTOM_INTEGRATION: ExecutionMode.EXECUTE,
        ActionType.ACCESS_ANALYTICS: ExecutionMode.EXECUTE,
    },
}


# ─── Helper Functions ────────────────────────────────────────────────────────────

def get_permission(variant: str, action_type: ActionType) -> ExecutionMode:
    """Get the execution mode for an action type on a specific variant.

    Args:
        variant: One of "mini", "parwa", "high"
        action_type: The action to check permissions for

    Returns:
        ExecutionMode: EXECUTE, RECOMMEND, or DENY
    """
    if variant not in ACTION_PERMISSIONS:
        raise ValueError(f"Unknown variant: {variant}. Must be one of {VARIANT_NAMES}")
    return ACTION_PERMISSIONS[variant].get(action_type, ExecutionMode.DENY)


def can_execute(variant: str, action_type: ActionType) -> bool:
    """Check if a variant can directly execute an action (vs recommend or deny)."""
    return get_permission(variant, action_type) == ExecutionMode.EXECUTE


def get_variant_channels(variant: str) -> list[TicketChannel]:
    """Get the channels available for a variant."""
    if variant not in VARIANT_CONFIG:
        raise ValueError(f"Unknown variant: {variant}")
    return VARIANT_CONFIG[variant]["channels"]


def get_variant_config(variant: str) -> dict:
    """Get the full configuration for a variant."""
    if variant not in VARIANT_CONFIG:
        raise ValueError(f"Unknown variant: {variant}")
    return VARIANT_CONFIG[variant]
