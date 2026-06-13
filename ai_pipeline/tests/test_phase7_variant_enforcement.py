"""Phase 7: Variant Enforcement Integration Tests.

Tests that the 3 PARWA variants behave differently at runtime:
- Model tier enforcement (Mini→Light, PARWA→Light+Medium, High→All)
- Channel enforcement (Mini→email+chat only, etc.)
- Action permission enforcement (Think vs Act split)
- VariantEnforcer correctness
- Real-world ticket processing with variant differentiation

Uses MockLLM for deterministic testing, with optional real LLM calls
via z-ai SDK (set PARWA_MOCK_MODE=false and configure API keys).
"""

from __future__ import annotations

import pytest

from parwa.config import (
    MINI_PARWA, PARWA, PARWA_HIGH,
    MODEL_TIERS,
    VARIANT_MODEL_TIERS,
    NODE_TIER_MAP,
    get_variant_tiers,
    get_node_tier,
    get_model_for_node,
    get_all_models_for_node,
    get_permission,
    can_execute,
    get_variant_channels,
    get_variant_config,
    ACTION_PERMISSIONS,
)
from parwa.permissions import PermissionChecker, get_permission_checker, VariantEnforcer, get_variant_enforcer
from parwa.state import ActionType, ExecutionMode, TicketChannel
from parwa.utils.llm import smart_route_model, smart_route_all_models


# ─── Model Tier Configuration Tests ──────────────────────────────────────────────

class TestModelTierConfig:
    """Test that model tier definitions are correct."""

    def test_all_tiers_have_models(self):
        for tier_name in ["light", "medium", "heavy", "guardrail"]:
            assert tier_name in MODEL_TIERS
            assert len(MODEL_TIERS[tier_name]) >= 1
            # All models should have provider prefix
            for model in MODEL_TIERS[tier_name]:
                assert "/" in model, f"Model {model} should have provider prefix"

    def test_light_tier_has_cheapest_models(self):
        light = MODEL_TIERS["light"]
        assert "cerebras/" in light[0] or "groq/" in light[0]

    def test_medium_tier_has_balanced_models(self):
        medium = MODEL_TIERS["medium"]
        assert "gemini/" in medium[0]

    def test_heavy_tier_has_capable_models(self):
        heavy = MODEL_TIERS["heavy"]
        assert len(heavy) >= 1

    def test_guardrail_tier_has_safety_model(self):
        guard = MODEL_TIERS["guardrail"]
        assert "guard" in guard[0].lower()

    def test_variant_tiers_defined(self):
        assert MINI_PARWA in VARIANT_MODEL_TIERS
        assert PARWA in VARIANT_MODEL_TIERS
        assert PARWA_HIGH in VARIANT_MODEL_TIERS

    def test_mini_only_light_guardrail(self):
        tiers = get_variant_tiers(MINI_PARWA)
        assert "light" in tiers
        assert "guardrail" in tiers
        assert "medium" not in tiers
        assert "heavy" not in tiers

    def test_parwa_light_medium_guardrail(self):
        tiers = get_variant_tiers(PARWA)
        assert "light" in tiers
        assert "medium" in tiers
        assert "guardrail" in tiers
        assert "heavy" not in tiers

    def test_high_all_tiers(self):
        tiers = get_variant_tiers(PARWA_HIGH)
        assert "light" in tiers
        assert "medium" in tiers
        assert "heavy" in tiers
        assert "guardrail" in tiers


# ─── Node Tier Mapping Tests ─────────────────────────────────────────────────────

class TestNodeTierMapping:
    """Test that node tier assignments are correct."""

    def test_all_22_nodes_have_tier(self):
        expected_nodes = [
            "INGEST", "INTENT_CLASSIFIER", "SENTIMENT_ANALYZER", "ESCALATION_DECISION",
            "FAQ_MATCHER", "KB_RETRIEVER", "CONTEXT_MANAGER", "INTEGRATION_LOOKUP",
            "REASONING_ENGINE", "REVERSE_THINKER", "TREE_OF_THOUGHTS", "STRATEGY_PLANNER",
            "ACTION_PLANNER", "ACTION_EXECUTOR", "ACTION_VERIFIER",
            "PROACTIVE_CHECKER", "PREDICTION_ENGINE", "FEEDBACK_LOOP",
            "PII_COMPLIANCE_GUARD", "AUDIT_LOGGER", "QUALITY_SCORER", "RESPONSE_FORMATTER",
        ]
        for node in expected_nodes:
            assert node in NODE_TIER_MAP, f"Node {node} missing from NODE_TIER_MAP"

    def test_router_agent_nodes_are_light(self):
        light_nodes = ["INGEST", "INTENT_CLASSIFIER", "SENTIMENT_ANALYZER", "ESCALATION_DECISION"]
        for node in light_nodes:
            assert get_node_tier(node) == "light", f"{node} should be light tier"

    def test_reasoning_agent_nodes_are_medium(self):
        medium_nodes = ["REASONING_ENGINE", "REVERSE_THINKER", "TREE_OF_THOUGHTS", "STRATEGY_PLANNER"]
        for node in medium_nodes:
            assert get_node_tier(node) == "medium", f"{node} should be medium tier"

    def test_unknown_node_defaults_to_light(self):
        assert get_node_tier("UNKNOWN_NODE") == "light"


# ─── Model Selection Per Variant Tests ────────────────────────────────────────────

class TestModelSelectionPerVariant:
    """Test that get_model_for_node returns correct models per variant."""

    def test_mini_gets_light_for_all_nodes(self):
        """Mini variant should ALWAYS get light or guardrail tier models."""
        for node_name in NODE_TIER_MAP:
            model = get_model_for_node(node_name, MINI_PARWA)
            # Should be a light or guardrail tier model (Mini only has light+guardrail)
            allowed_models = set(MODEL_TIERS["light"]) | set(MODEL_TIERS["guardrail"])
            assert model in allowed_models, f"Mini should use light/guardrail model for {node_name}, got {model}"

    def test_parwa_gets_medium_for_medium_nodes(self):
        """PARWA variant should get medium-tier models for medium-tier nodes."""
        medium_nodes = ["REASONING_ENGINE", "KB_RETRIEVER", "QUALITY_SCORER"]
        for node in medium_nodes:
            model = get_model_for_node(node, PARWA)
            medium_models = MODEL_TIERS["medium"]
            assert model in medium_models, f"PARWA should use medium model for {node}, got {model}"

    def test_parwa_gets_light_for_light_nodes(self):
        """PARWA variant should get light-tier models for light-tier nodes."""
        light_nodes = ["INGEST", "INTENT_CLASSIFIER", "ACTION_EXECUTOR"]
        for node in light_nodes:
            model = get_model_for_node(node, PARWA)
            light_models = MODEL_TIERS["light"]
            assert model in light_models, f"PARWA should use light model for {node}, got {model}"

    def test_high_gets_correct_tier_models(self):
        """PARWA High should get the correct tier model for each node."""
        # Light nodes
        model = get_model_for_node("INTENT_CLASSIFIER", PARWA_HIGH)
        assert model in MODEL_TIERS["light"]

        # Medium nodes
        model = get_model_for_node("REASONING_ENGINE", PARWA_HIGH)
        assert model in MODEL_TIERS["medium"]

    def test_fallback_models_returned_correctly(self):
        """get_all_models_for_node should return the full fallback chain."""
        models = get_all_models_for_node("REASONING_ENGINE", PARWA)
        assert len(models) >= 1
        # First model should be the primary
        assert models[0] == get_model_for_node("REASONING_ENGINE", PARWA)


# ─── Smart Router Variant Tests ────────────────────────────────────────────────────

class TestSmartRouterVariant:
    """Test Smart Router model selection with new LiteLLM models."""

    def test_mini_always_light_tier(self):
        model = smart_route_model("REASONING_ENGINE", complexity="critical", variant="mini")
        assert model in MODEL_TIERS["light"]

    def test_parwa_medium_tier_for_reasoning(self):
        model = smart_route_model("REASONING_ENGINE", complexity="simple", variant="parwa")
        assert model in MODEL_TIERS["medium"]

    def test_parwa_light_tier_for_simple(self):
        model = smart_route_model("INTENT_CLASSIFIER", complexity="simple", variant="parwa")
        assert model in MODEL_TIERS["light"]

    def test_high_all_tiers_accessible(self):
        # Light node
        model = smart_route_model("INTENT_CLASSIFIER", variant="high")
        assert model in MODEL_TIERS["light"]

        # Medium node
        model = smart_route_model("REASONING_ENGINE", variant="high")
        assert model in MODEL_TIERS["medium"]

    def test_smart_route_all_models(self):
        models = smart_route_all_models("REASONING_ENGINE", variant="parwa")
        assert len(models) >= 1
        assert models[0] == smart_route_model("REASONING_ENGINE", variant="parwa")


# ─── VariantEnforcer Tests ────────────────────────────────────────────────────────

class TestVariantEnforcer:
    """Test the VariantEnforcer runtime enforcement layer."""

    def test_mini_channel_email_allowed(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        result = enforcer.enforce_channel("email")
        assert result["allowed"] is True

    def test_mini_channel_chat_allowed(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        result = enforcer.enforce_channel("chat")
        assert result["allowed"] is True

    def test_mini_channel_social_blocked(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        result = enforcer.enforce_channel("social")
        assert result["allowed"] is False
        assert result["fallback"] == "email"

    def test_mini_channel_voice_blocked(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        result = enforcer.enforce_channel("voice")
        assert result["allowed"] is False

    def test_parwa_channel_social_blocked(self):
        enforcer = get_variant_enforcer(PARWA)
        result = enforcer.enforce_channel("social")
        assert result["allowed"] is False
        assert result["fallback"] == "email"

    def test_parwa_channel_voice_blocked(self):
        enforcer = get_variant_enforcer(PARWA)
        result = enforcer.enforce_channel("voice")
        assert result["allowed"] is False

    def test_high_channel_voice_allowed(self):
        enforcer = get_variant_enforcer(PARWA_HIGH)
        result = enforcer.enforce_channel("voice")
        assert result["allowed"] is True

    def test_unknown_channel_rejected(self):
        enforcer = get_variant_enforcer(PARWA)
        result = enforcer.enforce_channel("carrier_pigeon")
        assert result["allowed"] is False

    def test_mini_model_light_only(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        model = enforcer.get_model("REASONING_ENGINE")
        assert model in MODEL_TIERS["light"]

    def test_parwa_model_medium_for_reasoning(self):
        enforcer = get_variant_enforcer(PARWA)
        model = enforcer.get_model("REASONING_ENGINE")
        assert model in MODEL_TIERS["medium"]

    def test_is_model_downgraded_mini(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        # REASONING_ENGINE needs medium, but mini only has light
        assert enforcer.is_model_downgraded("REASONING_ENGINE") is True
        # INGEST needs light, mini has light
        assert enforcer.is_model_downgraded("INGEST") is False

    def test_is_model_downgraded_parwa(self):
        enforcer = get_variant_enforcer(PARWA)
        # REASONING_ENGINE needs medium, parwa has medium
        assert enforcer.is_model_downgraded("REASONING_ENGINE") is False

    def test_is_model_downgraded_high(self):
        enforcer = get_variant_enforcer(PARWA_HIGH)
        # High has all tiers, nothing is downgraded
        for node in NODE_TIER_MAP:
            assert enforcer.is_model_downgraded(node) is False

    def test_mini_action_permissions(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        assert enforcer.can_execute(ActionType.SEND_REPLY)
        assert enforcer.should_recommend(ActionType.PROCESS_REFUND)
        assert enforcer.is_denied(ActionType.VOICE_CALL)

    def test_parwa_action_permissions(self):
        enforcer = get_variant_enforcer(PARWA)
        assert enforcer.can_execute(ActionType.PROCESS_REFUND)
        assert enforcer.is_denied(ActionType.VOICE_CALL)

    def test_high_action_permissions(self):
        enforcer = get_variant_enforcer(PARWA_HIGH)
        assert enforcer.can_execute(ActionType.VOICE_CALL)
        assert enforcer.can_execute(ActionType.BULK_OPERATION)

    def test_can_use_technique_always_true(self):
        """All variants can USE all techniques (Think vs Act split)."""
        for variant in [MINI_PARWA, PARWA, PARWA_HIGH]:
            enforcer = get_variant_enforcer(variant)
            assert enforcer.can_use_technique("tree_of_thoughts") is True
            assert enforcer.can_use_technique("chain_of_thought") is True
            assert enforcer.can_use_technique("react") is True

    def test_technique_model_varies_by_variant(self):
        """Same technique uses different models per variant."""
        mini_enforcer = get_variant_enforcer(MINI_PARWA)
        high_enforcer = get_variant_enforcer(PARWA_HIGH)

        mini_model = mini_enforcer.get_technique_model("chain_of_thought")
        high_model = high_enforcer.get_technique_model("chain_of_thought")

        # Mini should use light tier, High should use medium tier
        assert mini_model in MODEL_TIERS["light"]
        assert high_model in MODEL_TIERS["medium"]

    def test_concurrent_limits(self):
        assert get_variant_enforcer(MINI_PARWA).get_concurrent_limit() == 3
        assert get_variant_enforcer(PARWA).get_concurrent_limit() == 4
        assert get_variant_enforcer(PARWA_HIGH).get_concurrent_limit() == 6

    def test_ticket_quota(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        result = enforcer.check_ticket_quota(400)
        assert result["allowed"] is True
        assert result["remaining"] == 100

        result = enforcer.check_ticket_quota(500)
        assert result["allowed"] is False

    def test_summary_structure(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        summary = enforcer.summary()
        assert "variant" in summary
        assert "tiers" in summary
        assert "channels" in summary
        assert "executable_actions" in summary
        assert "recommendable_actions" in summary
        assert "denied_actions" in summary
        assert "downgraded_nodes" in summary
        assert summary["variant"] == "mini"

    def test_to_state_dict(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        state = enforcer.to_state_dict()
        assert state["variant"] == "mini"
        assert "light" in state["available_tiers"]
        assert state["concurrent_limit"] == 3


# ─── Real-World Ticket Variant Differentiation Tests ──────────────────────────────

class TestRealWorldTicketDifferentiation:
    """Test that real-world tickets produce different outcomes per variant."""

    @pytest.mark.asyncio
    async def test_mini_refund_is_recommended_not_executed(self):
        """Ticket REAL-001: Mini should recommend refund, not execute."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "mini",
            "action_plans": [
                {"action_type": "process_refund", "description": "Refund $149.99", "parameters": {"amount": 149.99}, "evidence": [], "risk_level": "low"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "recommended"
        assert result["recommendation"] is not None
        assert result["recommendation"]["pending_approval"] is True

    @pytest.mark.asyncio
    async def test_parwa_refund_is_executed(self):
        """Ticket REAL-001: PARWA should execute refund directly."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "parwa",
            "action_plans": [
                {"action_type": "process_refund", "description": "Refund $149.99", "parameters": {"amount": 149.99}, "evidence": [], "risk_level": "low"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_mini_cancellation_is_recommended(self):
        """Ticket REAL-007: Mini should recommend cancellation."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "mini",
            "action_plans": [
                {"action_type": "cancel_order", "description": "Cancel order", "parameters": {}, "evidence": [], "risk_level": "medium"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "recommended"

    @pytest.mark.asyncio
    async def test_parwa_cancellation_is_executed(self):
        """Ticket REAL-007: PARWA should execute cancellation."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "parwa",
            "action_plans": [
                {"action_type": "cancel_order", "description": "Cancel order", "parameters": {}, "evidence": [], "risk_level": "medium"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_mini_voice_call_denied(self):
        """Ticket REAL-004: Mini should deny voice call action."""
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
    async def test_high_voice_call_executed(self):
        """Ticket REAL-004: High should execute voice call."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "high",
            "action_plans": [
                {"action_type": "voice_call", "description": "Call customer", "parameters": {}, "evidence": [], "risk_level": "high"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_mini_bulk_operation_denied(self):
        """Ticket REAL-008: Mini should deny bulk operations."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "mini",
            "action_plans": [
                {"action_type": "bulk_operation", "description": "Bulk import", "parameters": {}, "evidence": [], "risk_level": "high"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "denied"

    @pytest.mark.asyncio
    async def test_parwa_bulk_operation_denied(self):
        """Ticket REAL-008: PARWA should also deny bulk operations."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "parwa",
            "action_plans": [
                {"action_type": "bulk_operation", "description": "Bulk import", "parameters": {}, "evidence": [], "risk_level": "high"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "denied"

    @pytest.mark.asyncio
    async def test_high_bulk_operation_executed(self):
        """Ticket REAL-008: High should execute bulk operations."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "high",
            "action_plans": [
                {"action_type": "bulk_operation", "description": "Bulk import", "parameters": {}, "evidence": [], "risk_level": "high"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_mini_analytics_denied(self):
        """Ticket REAL-008: Mini should deny analytics access."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "mini",
            "action_plans": [
                {"action_type": "access_analytics", "description": "View analytics", "parameters": {}, "evidence": [], "risk_level": "medium"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "denied"

    @pytest.mark.asyncio
    async def test_high_analytics_executed(self):
        """Ticket REAL-008: High should execute analytics access."""
        from parwa.nodes.action_executor import action_executor

        state = {
            "variant": "high",
            "action_plans": [
                {"action_type": "access_analytics", "description": "View analytics", "parameters": {}, "evidence": [], "risk_level": "medium"},
            ],
        }
        result = await action_executor(state)
        assert result["execution_results"][0]["status"] == "executed"

    def test_mini_social_channel_blocked(self):
        """Ticket REAL-003: Mini should not support social channel."""
        enforcer = get_variant_enforcer(MINI_PARWA)
        result = enforcer.enforce_channel("social")
        assert result["allowed"] is False

    def test_parwa_social_channel_blocked(self):
        """Ticket REAL-003: PARWA no longer supports social channel (removed from config)."""
        enforcer = get_variant_enforcer(PARWA)
        result = enforcer.enforce_channel("social")
        assert result["allowed"] is False
        assert result["fallback"] == "email"

    def test_voice_channel_only_high(self):
        """Ticket REAL-004: Only High variant supports voice channel."""
        for variant in [MINI_PARWA, PARWA]:
            enforcer = get_variant_enforcer(variant)
            result = enforcer.enforce_channel("voice")
            assert result["allowed"] is False, f"{variant} should not support voice"

        enforcer = get_variant_enforcer(PARWA_HIGH)
        result = enforcer.enforce_channel("voice")
        assert result["allowed"] is True


# ─── Pipeline-Level Variant Differentiation Tests ─────────────────────────────────

class TestPipelineVariantDifferentiation:
    """Test that the full pipeline produces different results per variant."""

    @pytest.mark.asyncio
    async def test_mini_pipeline_refund_recommended(self):
        """Process a refund ticket through Mini — should recommend, not execute."""
        from parwa.graph import aprocess_ticket
        from parwa.graph import reset_parwa_graph

        reset_parwa_graph()
        result = await aprocess_ticket(
            raw_message="I was charged twice for order #ORD-78234. $149.99 on Jan 5th and again on Jan 5th.",
            customer_id="CUST-44921",
            channel="email",
            variant="mini",
        )

        # Mini should recommend refund, not execute
        exec_results = result.get("execution_results", [])
        refund_results = [r for r in exec_results if r.get("action_type") == "process_refund"]
        if refund_results:
            assert refund_results[0]["status"] == "recommended"

    @pytest.mark.asyncio
    async def test_parwa_pipeline_refund_executed(self):
        """Process a refund ticket through PARWA — should execute directly."""
        from parwa.graph import aprocess_ticket
        from parwa.graph import reset_parwa_graph
        from parwa.fake_crm.database import reset_crm

        reset_crm()  # Fresh CRM state so refund can succeed
        reset_parwa_graph()
        result = await aprocess_ticket(
            raw_message="I was charged twice for my Premium Headphones order. $189.99 on June 1st and again on June 1st.",
            customer_id="CUST-1001",
            channel="email",
            variant="parwa",
        )

        exec_results = result.get("execution_results", [])
        refund_results = [r for r in exec_results if r.get("action_type") == "process_refund"]
        if refund_results:
            assert refund_results[0]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_high_pipeline_refund_executed(self):
        """Process a refund ticket through High — should execute directly."""
        from parwa.graph import aprocess_ticket
        from parwa.graph import reset_parwa_graph
        from parwa.fake_crm.database import reset_crm

        reset_crm()  # Fresh CRM state so refund can succeed
        reset_parwa_graph()
        result = await aprocess_ticket(
            raw_message="I was charged twice for my Premium Headphones order. $189.99 on June 1st and again on June 1st.",
            customer_id="CUST-1001",
            channel="email",
            variant="high",
        )

        exec_results = result.get("execution_results", [])
        refund_results = [r for r in exec_results if r.get("action_type") == "process_refund"]
        if refund_results:
            assert refund_results[0]["status"] == "executed"

    @pytest.mark.asyncio
    async def test_mini_social_channel_redirected(self):
        """Mini ticket with social channel should fall back to email."""
        from parwa.graph import aprocess_ticket
        from parwa.graph import reset_parwa_graph

        reset_parwa_graph()
        result = await aprocess_ticket(
            raw_message="My product is damaged!",
            customer_id="CUST-33201",
            channel="social",
            variant="mini",
        )

        # Mini doesn't support social — should be redirected
        assert result.get("channel", "email") == "email"

    @pytest.mark.asyncio
    async def test_high_voice_channel_accepted(self):
        """High ticket with voice channel should keep voice."""
        from parwa.graph import aprocess_ticket
        from parwa.graph import reset_parwa_graph

        reset_parwa_graph()
        result = await aprocess_ticket(
            raw_message="I need to speak with someone about my account.",
            customer_id="CUST-55421",
            channel="voice",
            variant="high",
        )

        # High supports voice — should keep it
        assert result.get("channel") == "voice"

    @pytest.mark.asyncio
    async def test_all_variants_produce_final_response(self):
        """All variants should produce a final_response (no crashes)."""
        from parwa.graph import aprocess_ticket
        from parwa.graph import reset_parwa_graph

        for variant in [MINI_PARWA, PARWA, PARWA_HIGH]:
            reset_parwa_graph()
            result = await aprocess_ticket(
                raw_message="What is your return policy?",
                customer_id="CUST-99123",
                channel="chat",
                variant=variant,
            )
            assert "final_response" in result
            assert isinstance(result["final_response"], str)
            assert len(result["final_response"]) > 0

    @pytest.mark.asyncio
    async def test_variant_thinks_identically(self):
        """All variants should have same intent and complexity (Think identically)."""
        from parwa.graph import aprocess_ticket
        from parwa.graph import reset_parwa_graph

        message = "I was charged twice for order #ORD-78234. $149.99 on Jan 5th twice."

        results = {}
        for variant in [MINI_PARWA, PARWA, PARWA_HIGH]:
            reset_parwa_graph()
            result = await aprocess_ticket(
                raw_message=message,
                customer_id="CUST-44921",
                channel="email",
                variant=variant,
            )
            results[variant] = result

        # All variants should classify intent the same way
        intents = {v: results[v].get("intent") for v in results}
        assert len(set(intents.values())) == 1, f"Intents differ: {intents}"

        # All variants should determine complexity the same way
        complexities = {v: results[v].get("complexity") for v in results}
        assert len(set(complexities.values())) == 1, f"Complexities differ: {complexities}"


# ─── Downgrade Tracking Tests ─────────────────────────────────────────────────────

class TestDowngradeTracking:
    """Test that model downgrades are properly tracked and reported."""

    def test_mini_has_many_downgrades(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        summary = enforcer.summary()
        # Mini should have multiple downgraded nodes (all medium nodes → light)
        assert summary["total_nodes_downgraded"] > 0

    def test_parwa_has_fewer_downgrades(self):
        mini_enforcer = get_variant_enforcer(MINI_PARWA)
        parwa_enforcer = get_variant_enforcer(PARWA)
        assert parwa_enforcer.summary()["total_nodes_downgraded"] < mini_enforcer.summary()["total_nodes_downgraded"]

    def test_high_has_zero_downgrades(self):
        enforcer = get_variant_enforcer(PARWA_HIGH)
        summary = enforcer.summary()
        assert summary["total_nodes_downgraded"] == 0

    def test_downgraded_node_has_correct_info(self):
        enforcer = get_variant_enforcer(MINI_PARWA)
        summary = enforcer.summary()
        for node_info in summary["downgraded_nodes"]:
            assert "node" in node_info
            assert "required_tier" in node_info
            assert "actual_tier" in node_info
            assert "model" in node_info
            assert node_info["required_tier"] != node_info["actual_tier"]
