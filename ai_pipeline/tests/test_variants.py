"""Variant differentiation tests — CLAUDE.md required.

Tests that the 3 PARWA variants (Mini, PARWA, High) behave differently
at runtime while sharing the same AI brain.

Key principle: All variants THINK identically, ACTING is permission-gated.
"""

from __future__ import annotations

import pytest

from parwa.config import (
    MINI_PARWA, PARWA, PARWA_HIGH,
    get_permission, can_execute, get_variant_channels, get_variant_config,
    ACTION_PERMISSIONS, VARIANT_CONFIG,
)
from parwa.permissions import PermissionChecker, get_permission_checker
from parwa.state import ActionType, ExecutionMode, TicketChannel


# ─── Variant Config Tests ──────────────────────────────────────────────────────

class TestVariantConfigs:
    """Test that each variant has correct pricing, capacity, and channels."""

    def test_mini_pricing(self):
        config = get_variant_config(MINI_PARWA)
        assert config["price_monthly"] == 999
        assert config["tickets_per_month"] == 500
        assert config["concurrent_tickets"] == 3
        assert config["ai_resolution_rate"] == 0.60

    def test_parwa_pricing(self):
        config = get_variant_config(PARWA)
        assert config["price_monthly"] == 2499
        assert config["tickets_per_month"] == 2000
        assert config["concurrent_tickets"] == 4
        assert config["ai_resolution_rate"] == 0.75

    def test_high_pricing(self):
        config = get_variant_config(PARWA_HIGH)
        assert config["price_monthly"] == 4999
        assert config["tickets_per_month"] == 5000
        assert config["concurrent_tickets"] == 6
        assert config["ai_resolution_rate"] == 0.85

    def test_mini_channels(self):
        channels = get_variant_channels(MINI_PARWA)
        assert TicketChannel.EMAIL in channels
        assert TicketChannel.CHAT in channels
        assert TicketChannel.SOCIAL not in channels
        assert TicketChannel.VOICE not in channels

    def test_parwa_channels(self):
        channels = get_variant_channels(PARWA)
        assert TicketChannel.EMAIL in channels
        assert TicketChannel.CHAT in channels
        assert TicketChannel.SOCIAL not in channels  # social media removed
        assert TicketChannel.VOICE not in channels

    def test_high_channels(self):
        channels = get_variant_channels(PARWA_HIGH)
        assert TicketChannel.EMAIL in channels
        assert TicketChannel.CHAT in channels
        assert TicketChannel.SOCIAL not in channels  # social media removed
        assert TicketChannel.VOICE in channels

    def test_invalid_variant_raises(self):
        with pytest.raises(ValueError):
            get_variant_config("enterprise")

    def test_invalid_variant_channels_raises(self):
        with pytest.raises(ValueError):
            get_variant_channels("starter")


# ─── Action Permission Tests ───────────────────────────────────────────────────

class TestActionPermissions:
    """Test the Think vs Act split across variants."""

    # Mini: Can execute basics, recommend restricted, deny advanced
    def test_mini_can_execute_basics(self):
        basics = [
            ActionType.SEND_REPLY,
            ActionType.SHARE_FAQ,
            ActionType.SHARE_POLICY,
            ActionType.CREATE_NOTE,
            ActionType.ESCALATE_TO_HUMAN,
        ]
        for action in basics:
            assert can_execute(MINI_PARWA, action), f"Mini should execute {action.value}"

    def test_mini_recommends_refunds(self):
        assert get_permission(MINI_PARWA, ActionType.PROCESS_REFUND) == ExecutionMode.RECOMMEND
        assert get_permission(MINI_PARWA, ActionType.CANCEL_ORDER) == ExecutionMode.RECOMMEND
        assert get_permission(MINI_PARWA, ActionType.MODIFY_ACCOUNT) == ExecutionMode.RECOMMEND

    def test_mini_denies_advanced(self):
        denied = [
            ActionType.VOICE_CALL,
            ActionType.POST_SOCIAL,
            ActionType.BULK_OPERATION,
            ActionType.API_WEBHOOK,
            ActionType.CUSTOM_INTEGRATION,
            ActionType.ACCESS_ANALYTICS,
        ]
        for action in denied:
            assert get_permission(MINI_PARWA, action) == ExecutionMode.DENY, f"Mini should deny {action.value}"

    # PARWA: Execute most, deny voice/bulk/analytics
    def test_parwa_executes_most(self):
        execute_actions = [
            ActionType.SEND_REPLY, ActionType.SHARE_FAQ, ActionType.SHARE_POLICY,
            ActionType.CREATE_NOTE, ActionType.ESCALATE_TO_HUMAN,
            ActionType.PROCESS_REFUND, ActionType.CANCEL_ORDER,
            ActionType.MODIFY_ACCOUNT,
            ActionType.API_WEBHOOK, ActionType.CUSTOM_INTEGRATION,
        ]
        for action in execute_actions:
            assert can_execute(PARWA, action), f"PARWA should execute {action.value}"

    def test_parwa_denies_voice_bulk_analytics(self):
        assert get_permission(PARWA, ActionType.VOICE_CALL) == ExecutionMode.DENY
        assert get_permission(PARWA, ActionType.BULK_OPERATION) == ExecutionMode.DENY
        assert get_permission(PARWA, ActionType.ACCESS_ANALYTICS) == ExecutionMode.DENY

    # High: Execute everything
    def test_high_executes_all(self):
        denied_for_high = {ActionType.POST_SOCIAL}  # social media removed
        for action in ActionType:
            if action in denied_for_high:
                assert not can_execute(PARWA_HIGH, action), f"High should deny {action.value} (social removed)"
            else:
                assert can_execute(PARWA_HIGH, action), f"High should execute {action.value}"


# ─── PermissionChecker Tests ───────────────────────────────────────────────────

class TestPermissionChecker:
    """Test the PermissionChecker runtime enforcement layer."""

    def test_mini_checker(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        assert checker.can_execute(ActionType.SEND_REPLY)
        assert not checker.can_execute(ActionType.PROCESS_REFUND)
        assert checker.should_recommend(ActionType.PROCESS_REFUND)
        assert checker.is_denied(ActionType.VOICE_CALL)

    def test_parwa_checker(self):
        checker = PermissionChecker(variant=PARWA)
        assert checker.can_execute(ActionType.PROCESS_REFUND)
        assert not checker.should_recommend(ActionType.PROCESS_REFUND)
        assert checker.is_denied(ActionType.VOICE_CALL)

    def test_high_checker(self):
        checker = PermissionChecker(variant=PARWA_HIGH)
        assert checker.can_execute(ActionType.VOICE_CALL)
        assert checker.can_execute(ActionType.BULK_OPERATION)
        assert checker.can_execute(ActionType.ACCESS_ANALYTICS)

    def test_channel_validation_mini(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        assert checker.can_use_channel(TicketChannel.EMAIL)
        assert checker.can_use_channel(TicketChannel.CHAT)
        assert not checker.can_use_channel(TicketChannel.SOCIAL)
        assert not checker.can_use_channel(TicketChannel.VOICE)

    def test_channel_validation_mini_rejects_social(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        is_valid, reason = checker.validate_channel(TicketChannel.SOCIAL)
        assert not is_valid
        assert "social" in reason.lower()

    def test_channel_validation_high_allows_most(self):
        checker = PermissionChecker(variant=PARWA_HIGH)
        for channel in TicketChannel:
            if channel == TicketChannel.SOCIAL:
                assert not checker.can_use_channel(channel)  # social removed
            else:
                assert checker.can_use_channel(channel)

    def test_executable_actions_mini(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        executable = checker.get_executable_actions()
        assert ActionType.SEND_REPLY in executable
        assert ActionType.PROCESS_REFUND not in executable

    def test_recommendable_actions_mini(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        recommendable = checker.get_recommendable_actions()
        assert ActionType.PROCESS_REFUND in recommendable
        assert ActionType.CANCEL_ORDER in recommendable

    def test_denied_actions_mini(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        denied = checker.get_denied_actions()
        assert ActionType.VOICE_CALL in denied
        assert ActionType.BULK_OPERATION in denied

    def test_apply_to_action_plans_mini(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        plans = [
            {"action_type": "send_reply"},
            {"action_type": "process_refund"},
            {"action_type": "voice_call"},
        ]
        result = checker.apply_to_action_plans(plans)
        assert result[0]["mode"] == "execute"
        assert result[1]["mode"] == "recommend"
        assert result[2]["mode"] == "deny"

    def test_apply_to_action_plans_high(self):
        checker = PermissionChecker(variant=PARWA_HIGH)
        plans = [
            {"action_type": "send_reply"},
            {"action_type": "process_refund"},
            {"action_type": "voice_call"},
        ]
        result = checker.apply_to_action_plans(plans)
        assert all(p["mode"] == "execute" for p in result)

    def test_concurrent_limit(self):
        assert PermissionChecker(MINI_PARWA).get_concurrent_limit() == 3
        assert PermissionChecker(PARWA).get_concurrent_limit() == 4
        assert PermissionChecker(PARWA_HIGH).get_concurrent_limit() == 6

    def test_ticket_limit(self):
        assert PermissionChecker(MINI_PARWA).get_ticket_limit() == 500
        assert PermissionChecker(PARWA).get_ticket_limit() == 2000
        assert PermissionChecker(PARWA_HIGH).get_ticket_limit() == 5000

    def test_ai_resolution_rate(self):
        assert PermissionChecker(MINI_PARWA).get_ai_resolution_rate() == 0.60
        assert PermissionChecker(PARWA).get_ai_resolution_rate() == 0.75
        assert PermissionChecker(PARWA_HIGH).get_ai_resolution_rate() == 0.85

    def test_summary(self):
        checker = PermissionChecker(variant=MINI_PARWA)
        summary = checker.summary()
        assert summary["variant"] == "mini"
        assert len(summary["executable_actions"]) == 6
        assert len(summary["recommendable_actions"]) == 3
        assert len(summary["denied_actions"]) == 6

    def test_factory_function(self):
        checker = get_permission_checker("parwa")
        assert checker.variant == "parwa"


# ─── Variant Action Execution Differentiation ──────────────────────────────────

class TestActionExecutorVariantBehavior:
    """Test that action_executor behaves differently per variant."""

    @pytest.mark.asyncio
    async def test_mini_refund_is_recommended(self):
        """Mini PARWA should recommend (not execute) refunds."""
        from parwa.nodes.action_executor import action_executor
        state = {
            "variant": "mini",
            "action_plans": [
                {"action_type": "process_refund", "description": "Refund $49.99", "parameters": {"amount": 49.99}, "evidence": [], "risk_level": "low"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "recommended"
        assert result["recommendation"] is not None
        assert result["recommendation"]["pending_approval"] is True

    @pytest.mark.asyncio
    async def test_parwa_refund_is_executed(self):
        """PARWA should execute refunds directly."""
        from parwa.nodes.action_executor import action_executor
        state = {
            "variant": "parwa",
            "action_plans": [
                {"action_type": "process_refund", "description": "Refund $49.99", "parameters": {"amount": 49.99}, "evidence": [], "risk_level": "low"},
            ],
        }
        result = await action_executor(state)
        # MOCK_MODE returns "simulated" when no CRM customer; "executed" with real CRM
        assert result["execution_results"][0]["status"] in ("executed", "simulated")

    @pytest.mark.asyncio
    async def test_mini_voice_call_is_denied(self):
        """Mini PARWA should deny voice calls."""
        from parwa.nodes.action_executor import action_executor
        state = {
            "variant": "mini",
            "action_plans": [
                {"action_type": "voice_call", "description": "Call customer", "parameters": {}, "evidence": [], "risk_level": "high"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "denied"

    @pytest.mark.asyncio
    async def test_high_voice_call_is_executed(self):
        """PARWA High should execute voice calls."""
        from parwa.nodes.action_executor import action_executor
        state = {
            "variant": "high",
            "action_plans": [
                {"action_type": "voice_call", "description": "Call customer", "parameters": {}, "evidence": [], "risk_level": "high"},
            ],
        }
        result = await action_executor(state)
        # MOCK_MODE returns "simulated" when no delivery provider; "executed" with real provider
        assert result["execution_results"][0]["status"] in ("executed", "simulated")

    @pytest.mark.asyncio
    async def test_mini_send_reply_is_executed(self):
        """Mini PARWA should execute basic actions like send_reply."""
        from parwa.nodes.action_executor import action_executor
        state = {
            "variant": "mini",
            "action_plans": [
                {"action_type": "send_reply", "description": "Reply to customer", "parameters": {}, "evidence": [], "risk_level": "low"},
            ],
        }
        result = await action_executor(state)
        # MOCK_MODE returns "simulated" when no CRM customer; "executed" with real CRM
        assert result["execution_results"][0]["status"] in ("executed", "simulated")


# ─── Smart Router Variant Tests ────────────────────────────────────────────────

class TestSmartRouterVariantBehavior:
    """Test that Smart Router selects different models per variant."""

    def test_mini_always_uses_light_tier(self):
        """Mini variant should always use LIGHT tier models."""
        from parwa.utils.llm import smart_route_model
        from parwa.config import MODEL_TIERS
        model = smart_route_model("REASONING_ENGINE", complexity="critical", variant="mini")
        assert model in MODEL_TIERS["light"], f"Mini should use light tier, got {model}"

    def test_parwa_uses_tier_based_routing(self):
        """PARWA variant should use MEDIUM for medium nodes, LIGHT for light nodes."""
        from parwa.utils.llm import smart_route_model
        from parwa.config import MODEL_TIERS
        # REASONING_ENGINE is medium tier -> PARWA gets medium model
        model = smart_route_model("REASONING_ENGINE", complexity="simple", variant="parwa")
        assert model in MODEL_TIERS["medium"], f"PARWA should use medium model for REASONING_ENGINE, got {model}"
        # INTENT_CLASSIFIER is light tier -> PARWA gets light model
        model = smart_route_model("INTENT_CLASSIFIER", complexity="simple", variant="parwa")
        assert model in MODEL_TIERS["light"], f"PARWA should use light model for INTENT_CLASSIFIER, got {model}"

    def test_high_uses_correct_tiers(self):
        """High variant should use the correct tier model per node."""
        from parwa.utils.llm import smart_route_model
        from parwa.config import MODEL_TIERS
        # REASONING_ENGINE is medium tier
        model = smart_route_model("REASONING_ENGINE", complexity="simple", variant="high")
        assert model in MODEL_TIERS["medium"], f"High should use medium model for REASONING_ENGINE, got {model}"
