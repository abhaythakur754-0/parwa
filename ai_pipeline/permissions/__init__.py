"""PARWA Action Permission Matrix.

This module provides the runtime permission enforcement layer for the
Think vs Act split. All variants THINK identically, but ACTING is
permission-gated based on the variant configuration.

Key principle: Mini PARWA can THINK everything, but ACT only on basics
and RECOMMEND the rest. PARWA executes most actions. PARWA High
executes everything.

Usage:
    from parwa.permissions import PermissionChecker

    checker = PermissionChecker(variant="mini")
    if checker.can_execute(ActionType.PROCESS_REFUND):
        # Execute the refund
    elif checker.should_recommend(ActionType.PROCESS_REFUND):
        # Create a recommendation for human approval
    else:
        # Deny the action
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.config import (
    get_permission,
    can_execute,
    get_variant_channels,
    get_variant_config,
    VARIANT_CONFIG,
    ACTION_PERMISSIONS,
    MODEL_TIERS,
    VARIANT_MODEL_TIERS,
    get_variant_tiers,
    get_node_tier,
    get_model_for_node,
    get_all_models_for_node,
)
from parwa.state import ActionType, ExecutionMode, TicketChannel

# Phase 7: VariantEnforcer for full runtime enforcement
from parwa.permissions.variant_enforcer import VariantEnforcer, get_variant_enforcer

logger = logging.getLogger("parwa.permissions")


class PermissionChecker:
    """Runtime permission checker for variant-specific action enforcement.

    Centralizes all permission logic so nodes don't have to deal with
    variant-specific rules directly. Every action node should check
    permissions through this class before executing.

    Usage:
        checker = PermissionChecker(variant="mini")
        mode = checker.get_mode(ActionType.PROCESS_REFUND)
        # Returns ExecutionMode.RECOMMEND for mini

        if checker.can_execute(ActionType.SEND_REPLY):
            # Go ahead and execute
    """

    def __init__(self, variant: str = "parwa") -> None:
        self.variant = variant

    def get_mode(self, action_type: ActionType) -> ExecutionMode:
        """Get the execution mode for an action on this variant.

        Args:
            action_type: The action to check.

        Returns:
            EXECUTE, RECOMMEND, or DENY.
        """
        return get_permission(self.variant, action_type)

    def can_execute(self, action_type: ActionType) -> bool:
        """Check if this variant can directly execute an action."""
        return can_execute(self.variant, action_type)

    def should_recommend(self, action_type: ActionType) -> bool:
        """Check if this variant should recommend (not execute) an action."""
        return self.get_mode(action_type) == ExecutionMode.RECOMMEND

    def is_denied(self, action_type: ActionType) -> bool:
        """Check if this variant is denied from an action entirely."""
        return self.get_mode(action_type) == ExecutionMode.DENY

    def can_use_channel(self, channel: TicketChannel) -> bool:
        """Check if this variant supports a given channel."""
        variant_channels = get_variant_channels(self.variant)
        return channel in variant_channels

    def validate_channel(self, channel: TicketChannel) -> tuple[bool, str]:
        """Validate that the variant supports the given channel.

        Returns:
            Tuple of (is_valid, reason_if_invalid).
        """
        if self.can_use_channel(channel):
            return True, ""
        variant_channels = get_variant_channels(self.variant)
        channel_names = [c.value if hasattr(c, "value") else str(c) for c in variant_channels]
        return False, (
            f"Variant '{self.variant}' does not support channel '{channel.value}'. "
            f"Supported channels: {', '.join(channel_names)}"
        )

    def get_executable_actions(self) -> list[ActionType]:
        """Get all actions this variant can directly execute."""
        permissions = ACTION_PERMISSIONS.get(self.variant, {})
        return [
            action for action, mode in permissions.items()
            if mode == ExecutionMode.EXECUTE
        ]

    def get_recommendable_actions(self) -> list[ActionType]:
        """Get all actions this variant should recommend (not execute)."""
        permissions = ACTION_PERMISSIONS.get(self.variant, {})
        return [
            action for action, mode in permissions.items()
            if mode == ExecutionMode.RECOMMEND
        ]

    def get_denied_actions(self) -> list[ActionType]:
        """Get all actions this variant is denied."""
        permissions = ACTION_PERMISSIONS.get(self.variant, {})
        return [
            action for action, mode in permissions.items()
            if mode == ExecutionMode.DENY
        ]

    def get_concurrent_limit(self) -> int:
        """Get the concurrent ticket limit for this variant."""
        config = get_variant_config(self.variant)
        return config.get("concurrent_tickets", 3)

    def get_ticket_limit(self) -> int:
        """Get the monthly ticket limit for this variant."""
        config = get_variant_config(self.variant)
        return config.get("tickets_per_month", 500)

    def get_ai_resolution_rate(self) -> float:
        """Get the target AI resolution rate for this variant."""
        config = get_variant_config(self.variant)
        return config.get("ai_resolution_rate", 0.60)

    def apply_to_action_plans(self, action_plans: list[dict]) -> list[dict]:
        """Apply permission enforcement to a list of action plans.

        For each action plan, sets the execution mode based on variant
        permissions. This is the key integration point with ACTION_PLANNER.

        Args:
            action_plans: List of action plan dicts from ACTION_PLANNER.

        Returns:
            Modified action plans with mode set correctly.
        """
        result = []
        for plan in action_plans:
            plan = dict(plan)  # Don't modify original
            action_type_str = plan.get("action_type", "send_reply")

            try:
                action_type = ActionType(action_type_str)
            except (ValueError, TypeError):
                action_type = ActionType.SEND_REPLY

            mode = self.get_mode(action_type)
            plan["mode"] = mode.value

            result.append(plan)

        return result

    def summary(self) -> dict[str, Any]:
        """Get a summary of permissions for this variant."""
        return {
            "variant": self.variant,
            "executable_actions": [a.value for a in self.get_executable_actions()],
            "recommendable_actions": [a.value for a in self.get_recommendable_actions()],
            "denied_actions": [a.value for a in self.get_denied_actions()],
            "channels": [c.value if hasattr(c, "value") else str(c)
                        for c in get_variant_channels(self.variant)],
            "concurrent_limit": self.get_concurrent_limit(),
            "ticket_limit": self.get_ticket_limit(),
            "ai_resolution_rate": self.get_ai_resolution_rate(),
        }


def get_permission_checker(variant: str = "parwa") -> PermissionChecker:
    """Factory function to create a PermissionChecker.

    Args:
        variant: The PARWA variant ("mini", "parwa", "high").

    Returns:
        A PermissionChecker instance for the given variant.
    """
    return PermissionChecker(variant=variant)
