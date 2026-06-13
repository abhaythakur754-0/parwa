"""PARWA Variant Enforcer — Runtime enforcement of variant capabilities.

This module is the heart of Phase 7. It enforces the "Same Brain, Different
Capacity" principle at runtime across all 22 nodes:

1. Model Tier Enforcement: Mini->Light only, PARWA->Light+Medium, High->All
2. Channel Enforcement: Mini->email+chat, PARWA->+social, High->+voice
3. Action Permission Enforcement: Think vs Act split
4. Technique Tier Enforcement: Heavy techniques downgraded for lower variants
5. Concurrent Ticket Limits: Enforced at pipeline entry
6. Monthly Ticket Quota: Enforced at pipeline entry

Key principle: All variants THINK identically (same 22 nodes, same techniques).
ACTING is permission-gated — Mini can think about refunds but only RECOMMEND them.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.config import (
    MINI_PARWA,
    PARWA,
    PARWA_HIGH,
    MODEL_TIERS,
    VARIANT_MODEL_TIERS,
    NODE_TIER_MAP,
    get_permission,
    can_execute as _can_execute_action,
    get_variant_channels,
    get_variant_config,
    get_variant_tiers,
    get_node_tier,
    get_model_for_node,
    get_all_models_for_node,
    ACTION_PERMISSIONS,
    VARIANT_CONFIG,
)
from parwa.state import ActionType, ExecutionMode, TicketChannel

logger = logging.getLogger("parwa.variant_enforcer")


class VariantEnforcer:
    """Runtime enforcement layer for variant-specific capabilities.

    This is the single entry point for ALL variant checks in the pipeline.
    Instead of each node checking permissions independently, they delegate
    to the VariantEnforcer which centralizes all enforcement logic.

    Note: This class uses config.py directly (not PermissionChecker) to
    avoid circular imports with parwa.permissions.
    """

    def __init__(self, variant: str = "parwa") -> None:
        if variant not in VARIANT_CONFIG:
            raise ValueError(f"Unknown variant: {variant}")
        self.variant = variant

    # ─── Channel Enforcement ──────────────────────────────────────────────────

    def enforce_channel(self, channel: str | TicketChannel) -> dict[str, Any]:
        """Enforce channel availability for this variant."""
        if isinstance(channel, str):
            try:
                channel = TicketChannel(channel)
            except ValueError:
                return {
                    "allowed": False,
                    "channel": channel,
                    "reason": f"Unknown channel: {channel}",
                    "fallback": "email",
                }

        variant_channels = get_variant_channels(self.variant)
        channel_values = {ch.value if hasattr(ch, "value") else ch for ch in variant_channels}

        if channel.value in channel_values:
            return {
                "allowed": True,
                "channel": channel.value,
                "reason": "",
                "fallback": None,
            }

        fallback = variant_channels[0].value if variant_channels else "email"
        channel_names = [c.value if hasattr(c, "value") else str(c) for c in variant_channels]

        return {
            "allowed": False,
            "channel": channel.value,
            "reason": (
                f"Variant '{self.variant}' does not support channel '{channel.value}'. "
                f"Supported channels: {', '.join(channel_names)}"
            ),
            "fallback": fallback,
        }

    def can_use_channel(self, channel: str | TicketChannel) -> bool:
        """Check if this variant supports a given channel."""
        result = self.enforce_channel(channel)
        return result["allowed"]

    # ─── Model Tier Enforcement ───────────────────────────────────────────────

    def get_model(self, node_name: str) -> str:
        """Get the LLM model for a node, variant-aware."""
        return get_model_for_node(node_name, self.variant)

    def get_fallback_models(self, node_name: str) -> list[str]:
        """Get the full fallback model chain for a node."""
        return get_all_models_for_node(node_name, self.variant)

    def get_tier_for_node(self, node_name: str) -> str:
        """Get the model tier that will be used for a node on this variant."""
        required_tier = get_node_tier(node_name)
        available_tiers = get_variant_tiers(self.variant)

        if required_tier in available_tiers:
            return required_tier

        tier_priority = ["heavy", "medium", "light"]
        for tier in tier_priority:
            if tier in available_tiers:
                return tier
        return "light"

    def is_model_downgraded(self, node_name: str) -> bool:
        """Check if a node's model is being downgraded for this variant."""
        required_tier = get_node_tier(node_name)
        actual_tier = self.get_tier_for_node(node_name)
        return required_tier != actual_tier

    # ─── Action Permission Enforcement ────────────────────────────────────────

    def can_execute(self, action_type: ActionType) -> bool:
        """Check if this variant can EXECUTE an action (vs recommend/deny)."""
        return _can_execute_action(self.variant, action_type)

    def should_recommend(self, action_type: ActionType) -> bool:
        """Check if this variant should RECOMMEND an action (not execute)."""
        return get_permission(self.variant, action_type) == ExecutionMode.RECOMMEND

    def is_denied(self, action_type: ActionType) -> bool:
        """Check if this variant is DENIED an action entirely."""
        return get_permission(self.variant, action_type) == ExecutionMode.DENY

    def get_action_mode(self, action_type: ActionType) -> ExecutionMode:
        """Get the execution mode for an action on this variant."""
        return get_permission(self.variant, action_type)

    def apply_to_action_plans(self, action_plans: list[dict]) -> list[dict]:
        """Apply variant permissions to action plans."""
        result = []
        for plan in action_plans:
            plan = dict(plan)
            action_type_str = plan.get("action_type", "send_reply")
            try:
                action_type = ActionType(action_type_str)
            except (ValueError, TypeError):
                action_type = ActionType.SEND_REPLY
            mode = self.get_action_mode(action_type)
            plan["mode"] = mode.value
            result.append(plan)
        return result

    # ─── Technique Tier Enforcement ───────────────────────────────────────────

    def can_use_technique(self, technique_name: str) -> bool:
        """Check if a technique can be USED (thinking) on this variant.

        ALL techniques are available for THINKING on ALL variants.
        This always returns True — the variant gate is on ACTING, not THINKING.
        """
        return True

    def get_technique_model(self, technique_name: str) -> str:
        """Get the model to use for a FrameworkBrain technique."""
        technique_node_map = {
            "chain_of_thought": "FRAMEWORKBRAIN_COT",
            "cot": "FRAMEWORKBRAIN_COT",
            "react": "FRAMEWORKBRAIN_REACT",
            "tree_of_thoughts": "FRAMEWORKBRAIN_COT",
            "tot": "FRAMEWORKBRAIN_COT",
            "reverse_thinking": "FRAMEWORKBRAIN_COT",
            "reverse": "FRAMEWORKBRAIN_COT",
            "uncertainty_of_thought": "FRAMEWORKBRAIN_COT",
            "uot": "FRAMEWORKBRAIN_COT",
            "graph_of_strategic_thought": "FRAMEWORKBRAIN_COT",
            "gst": "FRAMEWORKBRAIN_COT",
            "clara": "FRAMEWORKBRAIN_CLARA",
            "hyde": "FRAMEWORKBRAIN_HYDE",
            "multi_query": "FRAMEWORKBRAIN_MULTI_QUERY",
            "step_back": "FRAMEWORKBRAIN_STEP_BACK",
            "reflexion": "FRAMEWORKBRAIN_REFLEXION",
            "self_consistency": "FRAMEWORKBRAIN_SC",
            "crp": "FRAMEWORKBRAIN_CRP",
            "least_to_most": "FRAMEWORKBRAIN_LTM",
            "thread_of_thought": "FRAMEWORKBRAIN_COT",
            "thot": "FRAMEWORKBRAIN_COT",
            "dynamic_context": "FRAMEWORKBRAIN_COT",
            "contextual_compression": "FRAMEWORKBRAIN_COT",
            "gsd": "FRAMEWORKBRAIN_COT",
            "smart_router": "FRAMEWORKBRAIN_COT",
            "maker": "FRAMEWORKBRAIN_COT",
            "adaptive_budget": "FRAMEWORKBRAIN_COT",
            "turbo_compress": "FRAMEWORKBRAIN_COT",
            "federated_reasoning": "FRAMEWORKBRAIN_COT",
            "zero_shot_validator": "FRAMEWORKBRAIN_COT",
            "meta_learner": "FRAMEWORKBRAIN_COT",
        }
        node_name = technique_node_map.get(technique_name, "FRAMEWORKBRAIN_COT")
        return self.get_model(node_name)

    # ─── Capacity Enforcement ─────────────────────────────────────────────────

    def get_concurrent_limit(self) -> int:
        """Get the concurrent ticket processing limit for this variant."""
        return get_variant_config(self.variant).get("concurrent_tickets", 3)

    def get_ticket_limit(self) -> int:
        """Get the monthly ticket limit for this variant."""
        return get_variant_config(self.variant).get("tickets_per_month", 500)

    def get_ai_resolution_rate(self) -> float:
        """Get the target AI resolution rate for this variant."""
        return get_variant_config(self.variant).get("ai_resolution_rate", 0.60)

    def check_ticket_quota(self, tickets_used_this_month: int) -> dict[str, Any]:
        """Check if the variant has remaining ticket quota."""
        limit = self.get_ticket_limit()
        remaining = max(0, limit - tickets_used_this_month)
        allowed = tickets_used_this_month < limit

        return {
            "allowed": allowed,
            "remaining": remaining,
            "limit": limit,
            "reason": "" if allowed else f"Monthly ticket limit ({limit}) exceeded for variant '{self.variant}'",
        }

    # ─── Summary ──────────────────────────────────────────────────────────────

    def get_executable_actions(self) -> list[ActionType]:
        """Get all actions this variant can directly execute."""
        permissions = ACTION_PERMISSIONS.get(self.variant, {})
        return [action for action, mode in permissions.items() if mode == ExecutionMode.EXECUTE]

    def get_recommendable_actions(self) -> list[ActionType]:
        """Get all actions this variant should recommend (not execute)."""
        permissions = ACTION_PERMISSIONS.get(self.variant, {})
        return [action for action, mode in permissions.items() if mode == ExecutionMode.RECOMMEND]

    def get_denied_actions(self) -> list[ActionType]:
        """Get all actions this variant is denied."""
        permissions = ACTION_PERMISSIONS.get(self.variant, {})
        return [action for action, mode in permissions.items() if mode == ExecutionMode.DENY]

    def summary(self) -> dict[str, Any]:
        """Get a complete summary of variant capabilities and restrictions."""
        tiers = get_variant_tiers(self.variant)
        variant_channels = get_variant_channels(self.variant)

        downgraded_nodes = []
        for node_name in NODE_TIER_MAP:
            if self.is_model_downgraded(node_name):
                required = get_node_tier(node_name)
                actual = self.get_tier_for_node(node_name)
                downgraded_nodes.append({
                    "node": node_name,
                    "required_tier": required,
                    "actual_tier": actual,
                    "model": self.get_model(node_name),
                })

        return {
            "variant": self.variant,
            "tiers": tiers,
            "channels": [c.value if hasattr(c, "value") else str(c) for c in variant_channels],
            "executable_actions": [a.value for a in self.get_executable_actions()],
            "recommendable_actions": [a.value for a in self.get_recommendable_actions()],
            "denied_actions": [a.value for a in self.get_denied_actions()],
            "concurrent_limit": self.get_concurrent_limit(),
            "ticket_limit": self.get_ticket_limit(),
            "ai_resolution_rate": self.get_ai_resolution_rate(),
            "downgraded_nodes": downgraded_nodes,
            "total_nodes_downgraded": len(downgraded_nodes),
        }

    def to_state_dict(self) -> dict[str, Any]:
        """Serialize key enforcement info for state passing."""
        return {
            "variant": self.variant,
            "available_tiers": get_variant_tiers(self.variant),
            "concurrent_limit": self.get_concurrent_limit(),
            "ticket_limit": self.get_ticket_limit(),
        }


def get_variant_enforcer(variant: str = "parwa") -> VariantEnforcer:
    """Factory function to create a VariantEnforcer."""
    return VariantEnforcer(variant=variant)
