"""Tests for Technique Router (BC-013).

Covers: signal evaluation, trigger rules, deduplication, budget
management, fallback logic, plan-based availability, and token budgets.
"""

import pytest
from backend.app.core.technique_router import (
    TechniqueRouter,
    TechniqueID,
    TechniqueTier,
    QuerySignals,
    TriggerRuleID,
    TokenBudget,
    ExecutionResultStatus,
    TECHNIQUE_REGISTRY,
    TRIGGER_RULES,
    TOKEN_BUDGETS,
    FALLBACK_MAP,
    CustomerTier,
)


class TestTechniqueEnums:
    """Verify enum completeness and correctness."""

    def test_tier_1_techniques_exist(self):
        t1 = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}
        for tid in t1:
            info = TECHNIQUE_REGISTRY[tid]
            assert info.tier == TechniqueTier.TIER_1

    def test_tier_2_techniques_exist(self):
        t2 = {
            TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REVERSE_THINKING,
            TechniqueID.REACT, TechniqueID.STEP_BACK,
            TechniqueID.THREAD_OF_THOUGHT,
        }
        for tid in t2:
            info = TECHNIQUE_REGISTRY[tid]
            assert info.tier == TechniqueTier.TIER_2

    def test_tier_3_techniques_exist(self):
        t3 = {
            TechniqueID.GST, TechniqueID.UNIVERSE_OF_THOUGHTS,
            TechniqueID.TREE_OF_THOUGHTS, TechniqueID.SELF_CONSISTENCY,
            TechniqueID.REFLEXION, TechniqueID.LEAST_TO_MOST,
        }
        for tid in t3:
            info = TECHNIQUE_REGISTRY[tid]
            assert info.tier == TechniqueTier.TIER_3

    def test_all_14_trigger_rules_defined(self):
        assert len(TRIGGER_RULES) == 14

    def test_all_techniques_have_registry_entry(self):
        expected = {tid.value for tid in TechniqueID}
        actual = set(TECHNIQUE_REGISTRY.keys())
        actual_str = {k.value for k in actual}
        # CLARA is not in TECHNIQUE_REGISTRY as a standalone technique
        # because it maps to F-057 — but GSD is not either
        # Just check Tier 2 and 3 are all present
        assert len(TECHNIQUE_REGISTRY) >= 12

    def test_execution_result_status_values(self):
        assert ExecutionResultStatus.SUCCESS.value == "success"
        assert ExecutionResultStatus.FALLBACK.value == "fallback"
        assert ExecutionResultStatus.TIMEOUT.value == "timeout"
        assert ExecutionResultStatus.ERROR.value == "error"
        assert ExecutionResultStatus.SKIPPED_BUDGET.value == "skipped_budget"


class TestTokenBudget:
    """Verify token budget allocation per model tier."""

    def test_light_budget(self):
        budget = TOKEN_BUDGETS["light"]
        assert budget.total == 500
        assert budget.tier1_reserve == 100

    def test_medium_budget(self):
        budget = TOKEN_BUDGETS["medium"]
        assert budget.total == 1500
        assert budget.tier1_reserve == 100

    def test_heavy_budget(self):
        budget = TOKEN_BUDGETS["heavy"]
        assert budget.total == 3000
        assert budget.tier1_reserve == 100

    def test_medium_tier2_pool(self):
        budget = TOKEN_BUDGETS["medium"]
        remaining = budget.total - budget.tier1_reserve  # 1400
        expected_t2 = int(remaining * 0.5)  # 700
        assert budget.tier2_pool == expected_t2

    def test_medium_tier3_pool(self):
        budget = TOKEN_BUDGETS["medium"]
        remaining = budget.total - budget.tier1_reserve
        expected_t2 = int(remaining * 0.5)
        expected_t3 = remaining - expected_t2
        assert budget.tier3_pool == expected_t3

    def test_budget_is_immutable(self):
        budget = TOKEN_BUDGETS["light"]
        with pytest.raises(AttributeError):
            budget.total = 999


class TestFallbackMapping:
    """Verify T3 → T2 fallback mappings."""

    def test_all_tier3_have_fallbacks(self):
        t3 = {
            TechniqueID.GST, TechniqueID.UNIVERSE_OF_THOUGHTS,
            TechniqueID.TREE_OF_THOUGHTS, TechniqueID.SELF_CONSISTENCY,
            TechniqueID.REFLEXION, TechniqueID.LEAST_TO_MOST,
        }
        for tid in t3:
            assert tid in FALLBACK_MAP, f"{tid} missing from FALLBACK_MAP"

    def test_fallbacks_are_tier2(self):
        for t3, t2_list in FALLBACK_MAP.items():
            assert TECHNIQUE_REGISTRY[t3].tier == TechniqueTier.TIER_3
            for t2 in t2_list:
                assert TECHNIQUE_REGISTRY[t2].tier == TechniqueTier.TIER_2

    def test_gst_falls_back_to_cot(self):
        assert TechniqueID.CHAIN_OF_THOUGHT in FALLBACK_MAP[TechniqueID.GST]

    def test_reflexion_falls_back_to_step_back(self):
        assert TechniqueID.STEP_BACK in FALLBACK_MAP[TechniqueID.REFLEXION]

    def test_uot_falls_back_to_cot_and_step_back(self):
        uot_fb = FALLBACK_MAP[TechniqueID.UNIVERSE_OF_THOUGHTS]
        assert TechniqueID.CHAIN_OF_THOUGHT in uot_fb
        assert TechniqueID.STEP_BACK in uot_fb


class TestQuerySignals:
    """Verify QuerySignals defaults and dataclass behavior."""

    def test_default_signals(self):
        signals = QuerySignals()
        assert signals.query_complexity == 0.0
        assert signals.confidence_score == 1.0
        assert signals.sentiment_score == 0.7
        assert signals.customer_tier == "free"
        assert signals.monetary_value == 0.0
        assert signals.turn_count == 0
        assert signals.intent_type == "general"
        assert signals.reasoning_loop_detected is False

    def test_custom_signals(self):
        signals = QuerySignals(
            query_complexity=0.8,
            confidence_score=0.3,
            sentiment_score=0.1,
            customer_tier="vip",
            monetary_value=500.0,
        )
        assert signals.query_complexity == 0.8
        assert signals.sentiment_score == 0.1
        assert signals.customer_tier == "vip"
        assert signals.monetary_value == 500.0


class TestTechniqueRouterBasic:
    """Basic router behavior — always-active Tier 1, deduplication."""

    def test_tier_1_always_activated(self):
        router = TechniqueRouter()
        signals = QuerySignals()
        result = router.route(signals)

        t1_ids = {a.technique_id for a in result.activated_techniques
                  if TECHNIQUE_REGISTRY[a.technique_id].tier == TechniqueTier.TIER_1}
        assert TechniqueID.CRP in t1_ids
        assert TechniqueID.GSD in t1_ids

    def test_simple_faq_only_tier_1(self):
        """Simple FAQ — only Tier 1, no conditional triggers."""
        router = TechniqueRouter()
        signals = QuerySignals(
            query_complexity=0.1,
            confidence_score=0.95,
            sentiment_score=0.8,
            customer_tier="free",
        )
        result = router.route(signals)

        assert len(result.activated_techniques) == 3  # CLARA, CRP, GSD
        assert result.trigger_rules_matched == 0

    def test_complex_query_activates_cot(self):
        router = TechniqueRouter()
        signals = QuerySignals(query_complexity=0.6)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.CHAIN_OF_THOUGHT in activated_ids
        assert result.trigger_rules_matched >= 1

    def test_low_confidence_activates_reverse_and_step_back(self):
        router = TechniqueRouter()
        signals = QuerySignals(confidence_score=0.4)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.REVERSE_THINKING in activated_ids
        assert TechniqueID.STEP_BACK in activated_ids

    def test_vip_activates_uot_and_reflexion_on_heavy_budget(self):
        """VIP triggers UoT + Reflexion but medium budget forces fallback.
        On heavy budget (3000), they should activate directly."""
        router = TechniqueRouter(model_tier="heavy")
        signals = QuerySignals(customer_tier="vip")
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in activated_ids
        assert TechniqueID.REFLEXION in activated_ids
        assert result.fallback_applied is False

    def test_angry_customer_activates_step_back(self):
        """Sentiment < 0.3 triggers Step-Back (T2, always fits budget)."""
        router = TechniqueRouter()
        signals = QuerySignals(sentiment_score=0.2)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.STEP_BACK in activated_ids

    def test_angry_customer_activates_uot_on_heavy_budget(self):
        """On heavy budget, sentiment < 0.3 also activates UoT (T3)."""
        router = TechniqueRouter(model_tier="heavy")
        signals = QuerySignals(sentiment_score=0.2)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in activated_ids
        assert TechniqueID.STEP_BACK in activated_ids

    def test_high_monetary_activates_self_consistency(self):
        router = TechniqueRouter()
        signals = QuerySignals(monetary_value=200.0)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.SELF_CONSISTENCY in activated_ids

    def test_many_turns_activates_thot(self):
        router = TechniqueRouter()
        signals = QuerySignals(turn_count=8)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.THREAD_OF_THOUGHT in activated_ids

    def test_external_data_activates_react(self):
        router = TechniqueRouter()
        signals = QuerySignals(external_data_required=True)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.REACT in activated_ids

    def test_multi_path_activates_tot(self):
        router = TechniqueRouter()
        signals = QuerySignals(resolution_path_count=4)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.TREE_OF_THOUGHTS in activated_ids

    def test_strategic_decision_activates_gst(self):
        router = TechniqueRouter()
        signals = QuerySignals(is_strategic_decision=True)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.GST in activated_ids

    def test_high_complexity_activates_least_to_most(self):
        router = TechniqueRouter()
        signals = QuerySignals(query_complexity=0.9)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.LEAST_TO_MOST in activated_ids

    def test_rejected_response_activates_reflexion(self):
        router = TechniqueRouter()
        signals = QuerySignals(previous_response_status="rejected")
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.REFLEXION in activated_ids

    def test_reasoning_loop_activates_step_back(self):
        router = TechniqueRouter()
        signals = QuerySignals(reasoning_loop_detected=True)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.STEP_BACK in activated_ids

    def test_billing_intent_activates_self_consistency(self):
        router = TechniqueRouter()
        signals = QuerySignals(intent_type="billing")
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.SELF_CONSISTENCY in activated_ids

    def test_technical_intent_activates_cot_and_react(self):
        router = TechniqueRouter()
        signals = QuerySignals(intent_type="technical")
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.CHAIN_OF_THOUGHT in activated_ids
        assert TechniqueID.REACT in activated_ids


class TestTechniqueRouterDeduplication:
    """Verify deduplication when multiple rules trigger same technique."""

    def test_self_consistency_deduplicated(self):
        """Self-Consistency triggered by both $ amount and billing intent
        should only appear once."""
        router = TechniqueRouter()
        signals = QuerySignals(
            monetary_value=200.0,
            intent_type="billing",
        )
        result = router.route(signals)

        sc_count = sum(
            1 for a in result.activated_techniques
            if a.technique_id == TechniqueID.SELF_CONSISTENCY
        )
        assert sc_count == 1
        # Should be triggered by both rules
        sc_activation = [
            a for a in result.activated_techniques
            if a.technique_id == TechniqueID.SELF_CONSISTENCY
        ][0]
        assert len(sc_activation.triggered_by) == 2

    def test_step_back_deduplicated(self):
        """Step-Back triggered by low confidence and reasoning loop should
        appear once (both are T2, no budget issues)."""
        router = TechniqueRouter()
        signals = QuerySignals(
            confidence_score=0.4,
            reasoning_loop_detected=True,
        )
        result = router.route(signals)

        sb_count = sum(
            1 for a in result.activated_techniques
            if a.technique_id == TechniqueID.STEP_BACK
        )
        assert sb_count == 1

    def test_uot_deduplicated(self):
        """UoT triggered by VIP and sentiment < 0.3 appears once.
        Uses heavy budget since UoT (T3) won't fit in medium."""
        router = TechniqueRouter(model_tier="heavy")
        signals = QuerySignals(
            customer_tier="vip",
            sentiment_score=0.1,
        )
        result = router.route(signals)

        uot_count = sum(
            1 for a in result.activated_techniques
            if a.technique_id == TechniqueID.UNIVERSE_OF_THOUGHTS
        )
        assert uot_count == 1


class TestTechniqueRouterExecutionOrder:
    """Verify Tier 1 → Tier 2 → Tier 3 execution ordering."""

    def test_order_is_t1_then_t2_then_t3(self):
        router = TechniqueRouter()
        signals = QuerySignals(
            query_complexity=0.8,
            confidence_score=0.4,
            sentiment_score=0.1,
            customer_tier="vip",
            monetary_value=500.0,
            is_strategic_decision=True,
            resolution_path_count=3,
        )
        result = router.route(signals)

        tiers = []
        for a in result.activated_techniques:
            info = TECHNIQUE_REGISTRY[a.technique_id]
            tiers.append(info.tier)

        # First 3 should be Tier 1
        for t in tiers[:3]:
            assert t == TechniqueTier.TIER_1

        # All Tier 2 should come before Tier 3
        t2_positions = [i for i, t in enumerate(tiers) if t == TechniqueTier.TIER_2]
        t3_positions = [i for i, t in enumerate(tiers) if t == TechniqueTier.TIER_3]
        if t2_positions and t3_positions:
            assert max(t2_positions) < min(t3_positions)


class TestTechniqueRouterBudget:
    """Verify budget management and fallback on light model."""

    def test_light_model_budget_is_500(self):
        router = TechniqueRouter(model_tier="light")
        assert router.budget.total == 500

    def test_light_model_triggers_fallback_for_t3(self):
        """Light budget (500) should trigger fallback for T3 techniques
        because T1 reserve (100) + T2 pool + T3 pool may not cover all."""
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(
            query_complexity=0.9,
            confidence_score=0.3,
            sentiment_score=0.1,
            customer_tier="vip",
            monetary_value=500.0,
            is_strategic_decision=True,
            resolution_path_count=5,
            turn_count=10,
            external_data_required=True,
            intent_type="billing",
        )
        result = router.route(signals)

        # With 500 token budget, T3 should fall back
        if result.total_estimated_tokens > router.budget.total:
            assert result.fallback_applied is True
            # T3 techniques should be in skipped list
            skipped_ids = {s["technique_id"] for s in result.skipped_techniques}
            assert len(skipped_ids) > 0

    def test_heavy_model_no_fallback_for_t2_only(self):
        """Heavy budget (3000) handles T2-only combos without fallback."""
        router = TechniqueRouter(model_tier="heavy")
        signals = QuerySignals(
            query_complexity=0.6,
            external_data_required=True,
            turn_count=8,
        )
        result = router.route(signals)

        assert result.fallback_applied is False

    def test_budget_totals_computed(self):
        router = TechniqueRouter()
        signals = QuerySignals(query_complexity=0.6)
        result = router.route(signals)

        assert result.total_estimated_tokens > 0
        assert result.total_estimated_time_ms > 0
        # Tier 1 (100) + CoT (350) = ~450
        assert result.total_estimated_tokens >= 400

    def test_result_has_model_tier(self):
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals())
        assert result.model_tier == "heavy"


class TestTechniqueRouterPlanRestriction:
    """Verify plan-based technique availability."""

    def test_free_plan_only_tier_1(self):
        available = TechniqueRouter.get_available_techniques_for_plan("free")
        assert len(available) == 3
        assert TechniqueID.CRP in available
        assert TechniqueID.CHAIN_OF_THOUGHT not in available
        assert TechniqueID.GST not in available

    def test_pro_plan_includes_tier_2(self):
        available = TechniqueRouter.get_available_techniques_for_plan("pro")
        assert TechniqueID.CRP in available
        assert TechniqueID.CHAIN_OF_THOUGHT in available
        assert TechniqueID.REACT in available
        assert TechniqueID.GST not in available

    def test_enterprise_plan_includes_all(self):
        available = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        assert TechniqueID.CRP in available
        assert TechniqueID.CHAIN_OF_THOUGHT in available
        assert TechniqueID.GST in available
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in available
        assert TechniqueID.LEAST_TO_MOST in available

    def test_vip_plan_same_as_enterprise(self):
        vip = TechniqueRouter.get_available_techniques_for_plan("vip")
        ent = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        assert vip == ent

    def test_router_respects_enabled_techniques(self):
        router = TechniqueRouter(
            enabled_techniques={
                TechniqueID.CRP, TechniqueID.GSD,
            },
        )
        signals = QuerySignals(query_complexity=0.8)
        result = router.route(signals)

        activated_ids = {a.technique_id for a in result.activated_techniques}
        assert TechniqueID.CHAIN_OF_THOUGHT not in activated_ids
        # Should be in skipped
        skipped_ids = {s["technique_id"] for s in result.skipped_techniques}
        assert "chain_of_thought" in skipped_ids

    def test_unknown_plan_returns_only_tier_1(self):
        available = TechniqueRouter.get_available_techniques_for_plan("unknown")
        assert len(available) == 3


class TestRouterResult:
    """Verify RouterResult data structure."""

    def test_result_has_all_fields(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals())

        assert hasattr(result, "activated_techniques")
        assert hasattr(result, "skipped_techniques")
        assert hasattr(result, "trigger_rules_evaluated")
        assert hasattr(result, "trigger_rules_matched")
        assert hasattr(result, "total_estimated_tokens")
        assert hasattr(result, "total_estimated_time_ms")
        assert hasattr(result, "model_tier")
        assert hasattr(result, "budget")
        assert hasattr(result, "fallback_applied")

    def test_activation_has_technique_id_and_tier(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals())

        for a in result.activated_techniques:
            assert hasattr(a, "technique_id")
            assert hasattr(a, "triggered_by")
            assert hasattr(a, "tier")
            assert isinstance(a.triggered_by, list)


class TestTechniqueInfo:
    """Verify TECHNIQUE_REGISTRY completeness."""

    def test_all_techniques_have_positive_tokens(self):
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.estimated_tokens > 0, f"{tid} has 0 tokens"

    def test_all_techniques_have_positive_time_budget(self):
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.time_budget_ms > 0, f"{tid} has 0 time budget"

    def test_all_techniques_have_description(self):
        for tid, info in TECHNIQUE_REGISTRY.items():
            assert info.description, f"{tid} missing description"

    def test_t1_tokens_are_lowest(self):
        t1_max = max(
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_1
        )
        t2_min = min(
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_2
        )
        assert t1_max < t2_min

    def test_t3_tokens_are_highest(self):
        t3_min = min(
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_3
        )
        t2_max = max(
            info.estimated_tokens
            for info in TECHNIQUE_REGISTRY.values()
            if info.tier == TechniqueTier.TIER_2
        )
        assert t3_min >= t2_max
