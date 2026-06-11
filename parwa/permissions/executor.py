"""PermissionExecutor — Enforces variant-specific action permissions.

This is the enforcement layer for the Think vs Act split:
  - All variants THINK identically (same 22 nodes, same 7 frameworks)
  - ACTING is permission-gated by variant tier

The PermissionExecutor reads the ACTION_PERMISSIONS matrix from config.py
and provides a clean interface for action_executor to check whether
an action should be EXECUTED, RECOMMENDED, or DENIED.

Usage inside action_executor:
    executor = PermissionExecutor(variant="mini")
    result = executor.evaluate(action_type="process_refund")
    # result.mode == "recommend"  (Mini PARWA can't execute refunds)
    # result.message explains why

Design principles:
  - NEVER raises exceptions — always returns a PermissionResult
  - Provides clear human-readable messages for RECOMMEND and DENY
  - Logs all permission decisions for audit trail
  - FrameworkBrain-agnostic — pure business logic
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from parwa.config import ACTION_PERMISSIONS, get_permission, can_execute
from parwa.state import ActionType, ExecutionMode

logger = logging.getLogger("parwa.permissions.executor")


@dataclass
class PermissionResult:
    """Result of a permission evaluation.

    Attributes:
        action_type: The action being evaluated.
        variant: The variant tier.
        mode: The execution mode (execute/recommend/deny).
        allowed: Whether the action can proceed (True for execute + recommend).
        can_auto_execute: Whether the action runs without human approval.
        reason: Human-readable explanation of the decision.
        metadata: Additional context for audit logging.
    """
    action_type: str
    variant: str
    mode: str  # "execute", "recommend", "deny"
    allowed: bool
    can_auto_execute: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for state storage and audit logging."""
        return {
            "action_type": self.action_type,
            "variant": self.variant,
            "mode": self.mode,
            "allowed": self.allowed,
            "can_auto_execute": self.can_auto_execute,
            "reason": self.reason,
        }


class PermissionExecutor:
    """Enforces variant-specific action permissions.

    Usage:
        executor = PermissionExecutor(variant="mini")
        result = executor.evaluate("process_refund")
        if result.can_auto_execute:
            execute_action()
        elif result.allowed:
            create_recommendation()
        else:
            skip_action()
    """

    # Human-readable explanations for each mode
    _REASON_TEMPLATES = {
        "execute": "{variant} variant allows direct execution of {action}.",
        "recommend": "{variant} variant requires human approval for {action}. The system can think through the action but must recommend it for human review.",
        "deny": "{variant} variant does not allow {action}. This action is restricted to higher tiers.",
    }

    # Variant-specific upgrade hints
    _UPGRADE_HINTS = {
        "mini": {
            "recommend": " Upgrade to PARWA ($2,499/mo) for direct execution.",
            "deny": " Upgrade to PARWA or PARWA High for access.",
        },
        "parwa": {
            "deny": " Upgrade to PARWA High ($4,999/mo) for access.",
        },
        "high": {
            "deny": " This action requires custom enterprise configuration.",
        },
    }

    def __init__(self, variant: str = "parwa") -> None:
        """Initialize the permission executor for a specific variant.

        Args:
            variant: One of "mini", "parwa", "high".
        """
        if variant not in ACTION_PERMISSIONS:
            logger.warning("Unknown variant '%s', defaulting to 'parwa'", variant)
            variant = "parwa"
        self.variant = variant

    def evaluate(self, action_type: str | ActionType) -> PermissionResult:
        """Evaluate whether an action is allowed for this variant.

        Args:
            action_type: The action to evaluate (string or ActionType enum).

        Returns:
            PermissionResult with the decision and explanation.
        """
        # Normalize action_type to string
        if isinstance(action_type, ActionType):
            action_type_str = action_type.value
        else:
            action_type_str = str(action_type)

        # Get the permission mode
        try:
            action_enum = ActionType(action_type_str)
            permission = get_permission(self.variant, action_enum)
            mode = permission.value if isinstance(permission, ExecutionMode) else str(permission)
        except (ValueError, KeyError) as exc:
            logger.warning(
                "PermissionExecutor: Unknown action '%s' for variant '%s': %s",
                action_type_str, self.variant, exc,
            )
            mode = "deny"

        # Build the result
        allowed = mode in ("execute", "recommend")
        can_auto_execute = mode == "execute"

        # Build reason
        reason = self._REASON_TEMPLATES.get(mode, "").format(
            variant=self.variant.upper() if self.variant != "parwa" else "PARWA",
            action=action_type_str,
        )

        # Add upgrade hint for non-execute modes
        if mode != "execute":
            hint = self._UPGRADE_HINTS.get(self.variant, {}).get(mode, "")
            reason += hint

        result = PermissionResult(
            action_type=action_type_str,
            variant=self.variant,
            mode=mode,
            allowed=allowed,
            can_auto_execute=can_auto_execute,
            reason=reason,
            metadata={
                "evaluated_by": "PermissionExecutor",
                "variant": self.variant,
            },
        )

        logger.debug(
            "PermissionExecutor: %s/%s → %s (allowed=%s)",
            self.variant, action_type_str, mode, allowed,
        )

        return result

    def evaluate_batch(self, action_types: list[str | ActionType]) -> list[PermissionResult]:
        """Evaluate multiple actions at once.

        Args:
            action_types: List of actions to evaluate.

        Returns:
            List of PermissionResults, one per action.
        """
        return [self.evaluate(at) for at in action_types]

    def get_allowed_actions(self) -> list[str]:
        """Get all actions allowed (execute or recommend) for this variant."""
        results = []
        for action in ActionType:
            result = self.evaluate(action)
            if result.allowed:
                results.append(action.value)
        return results

    def get_executable_actions(self) -> list[str]:
        """Get all actions that can be auto-executed for this variant."""
        results = []
        for action in ActionType:
            result = self.evaluate(action)
            if result.can_auto_execute:
                results.append(action.value)
        return results

    def get_denied_actions(self) -> list[str]:
        """Get all actions denied for this variant."""
        results = []
        for action in ActionType:
            result = self.evaluate(action)
            if not result.allowed:
                results.append(action.value)
        return results

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all permissions for this variant."""
        return {
            "variant": self.variant,
            "executable": self.get_executable_actions(),
            "recommended": [
                a.value for a in ActionType
                if self.evaluate(a).mode == "recommend"
            ],
            "denied": self.get_denied_actions(),
        }
