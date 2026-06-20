"""
Comprehensive unit tests for Technique Router (BC-013).

Tests cover:
  - TokenBudget allocation and immutability
  - TechniqueRouter.route() — all 14 trigger rules (R1–R14)
  - Tier 1 always-active guarantee
  - Deduplication across multiple trigger rules
  - Token / time budget totals
  - Fallback logic (T3 → T2) and fallback_applied flag
  - enabled_techniques filtering
  - get_available_techniques_for_plan() per plan tier
  - model_tier budget selection

Pure synchronous unit tests — no async, no DB, no external calls.
"""

import pytest

try:
    from backend.app.core.technique_router import (
        FALLBACK_MAP,
        CustomerTier,
        ExecutionResultStatus,
        QuerySignals,
        RouterResult,
        TechniqueActivation,
        TechniqueID,
        TechniqueInfo,
        TechniqueRouter,
        TechniqueTier,
        TokenBudget,
        TOKEN_BUDGETS,
        TriggerRuleID,
        TECHNIQUE_REGISTRY,
        TRIGGER_RULES,
    )
except ImportError:
    from parwa.backend.app.core.technique_router import (
        FALLBACK_MAP,
        CustomerTier,
        ExecutionResultStatus,
        QuerySignals,
        RouterResult,
        TechniqueActivation,
        TechniqueID,
        TechniqueInfo,
        TechniqueRouter,
        TechniqueTier,
        TokenBudget,
        TOKEN_BUDGETS,
        TriggerRuleID,
        TECHNIQUE_REGISTRY,
        TRIGGER_RULES,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIER_1_IDS = {TechniqueID.CLARA, TechniqueID.CRP, TechniqueID.GSD}


def _activated_ids(result: RouterResult) -> set:
    """Return set of TechniqueID from activated_techniques."""
    return {a.technique_id for a in result.activated_techniques}


def _find_activation(result: RouterResult, tid: TechniqueID):
    """Return the TechniqueActivation for a given TechniqueID, or None."""
    for a in result.activated_techniques:
        if a.technique_id == tid:
            return a
    return None


def _tier_of(tid: TechniqueID) -> TechniqueTier:
    """Lookup the tier of a technique from the registry."""
    return TECHNIQUE_REGISTRY[tid].tier


def _tokens_of(tid: TechniqueID) -> int:
    """Lookup estimated_tokens for a technique."""
    return TECHNIQUE_REGISTRY[tid].estimated_tokens


def _time_of(tid: TechniqueID) -> int:
    """Lookup time_budget_ms for a technique."""
    return TECHNIQUE_REGISTRY[tid].time_budget_ms


# ===================================================================
# 1-4. TokenBudget Tests
# ===================================================================


class TestTokenBudgetAllocation:
    """TokenBudget: tier2 gets 50% of remaining, tier3 gets the rest."""

    def test_tier2_gets_50_pct_of_remaining(self):
        """tier2_pool == int(remaining * 0.5) where remaining = total - tier1_reserve."""
        budget = TokenBudget(total=1500, tier1_reserve=100)
        remaining = 1500 - 100  # 1400
        expected_t2 = int(remaining * 0.5)  # 700
        assert budget.tier2_pool == expected_t2

    def test_tier3_gets_rest_of_remaining(self):
        """tier3_pool == remaining - tier2_pool."""
        budget = TokenBudget(total=1500, tier1_reserve=100)
        remaining = 1500 - 100
        expected_t2 = int(remaining * 0.5)
        expected_t3 = remaining - expected_t2
        assert budget.tier3_pool == expected_t3

    def test_light_budget_total_500(self):
        """Pre-defined light budget has total=500."""
        budget = TOKEN_BUDGETS["light"]
        assert budget.total == 500

    def test_light_budget_pools(self):
        """Light budget: remaining=400, t2=200, t3=200."""
        budget = TOKEN_BUDGETS["light"]
        assert budget.tier1_reserve == 100
        assert budget.tier2_pool == 200
        assert budget.tier3_pool == 200

    def test_medium_budget_total_1500(self):
        """Pre-defined medium budget has total=1500."""
        budget = TOKEN_BUDGETS["medium"]
        assert budget.total == 1500

    def test_medium_budget_pools(self):
        """Medium budget: remaining=1400, t2=700, t3=700."""
        budget = TOKEN_BUDGETS["medium"]
        assert budget.tier1_reserve == 100
        assert budget.tier2_pool == 700
        assert budget.tier3_pool == 700

    def test_heavy_budget_total_3000(self):
        """Pre-defined heavy budget has total=3000."""
        budget = TOKEN_BUDGETS["heavy"]
        assert budget.total == 3000

    def test_heavy_budget_pools(self):
        """Heavy budget: remaining=2900, t2=1450, t3=1450."""
        budget = TOKEN_BUDGETS["heavy"]
        assert budget.tier1_reserve == 100
        assert budget.tier2_pool == 1450
        assert budget.tier3_pool == 1450

    def test_budget_is_frozen(self):
        """TokenBudget is a frozen dataclass — attributes cannot be reassigned."""
        budget = TOKEN_BUDGETS["light"]
        with pytest.raises(AttributeError):
            budget.total = 999

    def test_budget_pools_sum_to_total(self):
        """tier1_reserve + tier2_pool + tier3_pool == total for all predefined budgets."""
        for name, budget in TOKEN_BUDGETS.items():
            assert budget.tier1_reserve + budget.tier2_pool + budget.tier3_pool == budget.total, (
                f"{name} budget pools don't sum to total"
            )

    def test_custom_tier1_reserve(self):
        """TokenBudget with custom tier1_reserve calculates pools correctly."""
        budget = TokenBudget(total=1000, tier1_reserve=200)
        remaining = 1000 - 200  # 800
        assert budget.tier2_pool == 400
        assert budget.tier3_pool == 400


# ===================================================================
# 5. Tier 1 Always Active
# ===================================================================


class TestTier1AlwaysActive:
    """Tier 1 techniques (CLARA, CRP, GSD) are always activated."""

    def test_tier1_always_present_with_default_signals(self):
        """Even with default QuerySignals (no triggers), all Tier 1 present."""
        router = TechniqueRouter()
        result = router.route(QuerySignals())
        ids = _activated_ids(result)
        assert ids == TIER_1_IDS

    def test_tier1_present_with_complex_signals(self):
        """Tier 1 still present when many conditional rules fire."""
        router = TechniqueRouter(model_tier="heavy")
        signals = QuerySignals(
            query_complexity=0.9,
            confidence_score=0.3,
            sentiment_score=0.1,
            customer_tier="vip",
            monetary_value=500.0,
            is_strategic_decision=True,
            resolution_path_count=5,
        )
        result = router.route(signals)
        ids = _activated_ids(result)
        assert TIER_1_IDS.issubset(ids)

    def test_tier1_triggered_by_always_active_label(self):
        """Each Tier 1 activation lists 'always_active_tier_1' in triggered_by."""
        router = TechniqueRouter()
        result = router.route(QuerySignals())
        for a in result.activated_techniques:
            if a.technique_id in TIER_1_IDS:
                assert "always_active_tier_1" in a.triggered_by


# ===================================================================
# 6-19. Trigger Rule Tests (R1–R14)
# ===================================================================


class TestTriggerRuleR1:
    """R1: complexity > 0.4 → CHAIN_OF_THOUGHT."""

    def test_complexity_05_activates_cot(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.5))
        assert TechniqueID.CHAIN_OF_THOUGHT in _activated_ids(result)

    def test_complexity_04_does_not_activate_cot(self):
        """0.4 is NOT > 0.4 — boundary check."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.4))
        assert TechniqueID.CHAIN_OF_THOUGHT not in _activated_ids(result)

    def test_complexity_01_does_not_activate_cot(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.1))
        assert TechniqueID.CHAIN_OF_THOUGHT not in _activated_ids(result)


class TestTriggerRuleR2:
    """R2: confidence < 0.7 → REVERSE_THINKING + STEP_BACK."""

    def test_confidence_06_activates_reverse_and_step_back(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(confidence_score=0.6))
        ids = _activated_ids(result)
        assert TechniqueID.REVERSE_THINKING in ids
        assert TechniqueID.STEP_BACK in ids

    def test_confidence_07_does_not_activate(self):
        """0.7 is NOT < 0.7 — boundary check."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(confidence_score=0.7))
        ids = _activated_ids(result)
        assert TechniqueID.REVERSE_THINKING not in ids
        assert TechniqueID.STEP_BACK not in ids


class TestTriggerRuleR3:
    """R3: VIP customer → UoT + REFLEXION (T3, needs heavy budget)."""

    def test_vip_activates_uot_and_reflexion_on_heavy(self):
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals(customer_tier="vip"))
        ids = _activated_ids(result)
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in ids
        assert TechniqueID.REFLEXION in ids

    def test_vip_triggers_fallback_on_medium(self):
        """On medium budget, T3 techniques should be replaced by T2 fallbacks."""
        router = TechniqueRouter(model_tier="medium")
        result = router.route(QuerySignals(customer_tier="vip"))
        # UoT (1400) + Reflexion (400) + T1 (100) + others = > 1500
        # So fallback should be applied
        assert result.fallback_applied is True
        # UoT should be in skipped
        skipped_ids = {s["technique_id"] for s in result.skipped_techniques}
        assert "universe_of_thoughts" in skipped_ids

    def test_non_vip_does_not_trigger_r3(self):
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals(customer_tier="pro"))
        ids = _activated_ids(result)
        # UoT and Reflexion should not be there without VIP
        # (unless triggered by another rule)
        assert TechniqueID.UNIVERSE_OF_THOUGHTS not in ids


class TestTriggerRuleR4:
    """R4: sentiment < 0.3 → UoT + STEP_BACK."""

    def test_sentiment_02_activates_uot_and_step_back_on_heavy(self):
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals(sentiment_score=0.2))
        ids = _activated_ids(result)
        assert TechniqueID.UNIVERSE_OF_THOUGHTS in ids
        assert TechniqueID.STEP_BACK in ids

    def test_sentiment_03_does_not_activate(self):
        """0.3 is NOT < 0.3 — boundary check."""
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals(sentiment_score=0.3))
        ids = _activated_ids(result)
        assert TechniqueID.UNIVERSE_OF_THOUGHTS not in ids


class TestTriggerRuleR5:
    """R5: monetary > 100 → SELF_CONSISTENCY."""

    def test_monetary_101_activates_self_consistency(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(monetary_value=101.0))
        assert TechniqueID.SELF_CONSISTENCY in _activated_ids(result)

    def test_monetary_100_does_not_activate(self):
        """100 is NOT > 100 — boundary check."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(monetary_value=100.0))
        assert TechniqueID.SELF_CONSISTENCY not in _activated_ids(result)

    def test_monetary_zero_does_not_activate(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(monetary_value=0.0))
        assert TechniqueID.SELF_CONSISTENCY not in _activated_ids(result)


class TestTriggerRuleR6:
    """R6: turns > 5 → THREAD_OF_THOUGHT."""

    def test_turns_6_activates_thot(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(turn_count=6))
        assert TechniqueID.THREAD_OF_THOUGHT in _activated_ids(result)

    def test_turns_5_does_not_activate(self):
        """5 is NOT > 5 — boundary check."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(turn_count=5))
        assert TechniqueID.THREAD_OF_THOUGHT not in _activated_ids(result)


class TestTriggerRuleR7:
    """R7: external_data_required → REACT."""

    def test_external_data_true_activates_react(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(external_data_required=True))
        assert TechniqueID.REACT in _activated_ids(result)

    def test_external_data_false_does_not_activate(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(external_data_required=False))
        assert TechniqueID.REACT not in _activated_ids(result)


class TestTriggerRuleR8:
    """R8: resolution_paths >= 3 → TREE_OF_THOUGHTS."""

    def test_resolution_3_activates_tot(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(resolution_path_count=3))
        assert TechniqueID.TREE_OF_THOUGHTS in _activated_ids(result)

    def test_resolution_2_does_not_activate(self):
        """2 is NOT >= 3."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(resolution_path_count=2))
        assert TechniqueID.TREE_OF_THOUGHTS not in _activated_ids(result)


class TestTriggerRuleR9:
    """R9: is_strategic_decision → GST."""

    def test_strategic_true_activates_gst(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(is_strategic_decision=True))
        assert TechniqueID.GST in _activated_ids(result)

    def test_strategic_false_does_not_activate(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(is_strategic_decision=False))
        assert TechniqueID.GST not in _activated_ids(result)


class TestTriggerRuleR10:
    """R10: complexity > 0.7 → LEAST_TO_MOST."""

    def test_complexity_08_activates_least_to_most(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.8))
        assert TechniqueID.LEAST_TO_MOST in _activated_ids(result)

    def test_complexity_07_does_not_activate(self):
        """0.7 is NOT > 0.7 — boundary check."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.7))
        assert TechniqueID.LEAST_TO_MOST not in _activated_ids(result)


class TestTriggerRuleR11:
    """R11: previous_response_status 'rejected' or 'corrected' → REFLEXION."""

    def test_rejected_activates_reflexion(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(previous_response_status="rejected"))
        assert TechniqueID.REFLEXION in _activated_ids(result)

    def test_corrected_activates_reflexion(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(previous_response_status="corrected"))
        assert TechniqueID.REFLEXION in _activated_ids(result)

    def test_accepted_does_not_activate_reflexion(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(previous_response_status="accepted"))
        assert TechniqueID.REFLEXION not in _activated_ids(result)

    def test_none_does_not_activate_reflexion(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(previous_response_status="none"))
        assert TechniqueID.REFLEXION not in _activated_ids(result)


class TestTriggerRuleR12:
    """R12: reasoning_loop_detected → STEP_BACK."""

    def test_loop_detected_activates_step_back(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(reasoning_loop_detected=True))
        assert TechniqueID.STEP_BACK in _activated_ids(result)

    def test_no_loop_does_not_activate(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(reasoning_loop_detected=False))
        ids = _activated_ids(result)
        # STEP_BACK should not be present unless another rule fires it
        assert TechniqueID.STEP_BACK not in ids


class TestTriggerRuleR13:
    """R13: intent_type 'billing' → SELF_CONSISTENCY."""

    def test_billing_intent_activates_self_consistency(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(intent_type="billing"))
        assert TechniqueID.SELF_CONSISTENCY in _activated_ids(result)

    def test_general_intent_does_not_activate(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(intent_type="general"))
        assert TechniqueID.SELF_CONSISTENCY not in _activated_ids(result)


class TestTriggerRuleR14:
    """R14: intent_type 'technical' → CoT + ReAct."""

    def test_technical_intent_activates_cot_and_react(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(intent_type="technical"))
        ids = _activated_ids(result)
        assert TechniqueID.CHAIN_OF_THOUGHT in ids
        assert TechniqueID.REACT in ids

    def test_non_technical_intent_no_react_via_r14(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(intent_type="general"))
        assert TechniqueID.REACT not in _activated_ids(result)


# ===================================================================
# 20. Deduplication
# ===================================================================


class TestDeduplication:
    """Multiple rules can trigger the same technique — should dedup."""

    def test_self_consistency_triggered_by_r5_and_r13(self):
        """R5 (monetary > 100) and R13 (billing intent) both trigger SELF_CONSISTENCY.
        Should appear exactly once with both rule IDs in triggered_by."""
        router = TechniqueRouter()
        signals = QuerySignals(monetary_value=200.0, intent_type="billing")
        result = router.route(signals)

        sc_count = sum(
            1 for a in result.activated_techniques
            if a.technique_id == TechniqueID.SELF_CONSISTENCY
        )
        assert sc_count == 1
        sc = _find_activation(result, TechniqueID.SELF_CONSISTENCY)
        assert sc is not None
        assert TriggerRuleID.R5_MONETARY_GT_100.value in sc.triggered_by
        assert TriggerRuleID.R13_INTENT_BILLING.value in sc.triggered_by

    def test_step_back_triggered_by_r2_and_r12(self):
        """R2 (confidence < 0.7) and R12 (reasoning loop) both trigger STEP_BACK."""
        router = TechniqueRouter()
        signals = QuerySignals(confidence_score=0.4, reasoning_loop_detected=True)
        result = router.route(signals)

        sb_count = sum(
            1 for a in result.activated_techniques
            if a.technique_id == TechniqueID.STEP_BACK
        )
        assert sb_count == 1

    def test_uot_triggered_by_r3_and_r4_deduped_on_heavy(self):
        """R3 (VIP) and R4 (sentiment < 0.3) both trigger UoT."""
        router = TechniqueRouter(model_tier="heavy")
        signals = QuerySignals(customer_tier="vip", sentiment_score=0.1)
        result = router.route(signals)

        uot_count = sum(
            1 for a in result.activated_techniques
            if a.technique_id == TechniqueID.UNIVERSE_OF_THOUGHTS
        )
        assert uot_count == 1

    def test_cot_triggered_by_r1_and_r14(self):
        """R1 (complexity > 0.4) and R14 (technical intent) both trigger CoT."""
        router = TechniqueRouter()
        signals = QuerySignals(query_complexity=0.6, intent_type="technical")
        result = router.route(signals)

        cot_count = sum(
            1 for a in result.activated_techniques
            if a.technique_id == TechniqueID.CHAIN_OF_THOUGHT
        )
        assert cot_count == 1


# ===================================================================
# 21-23. Counter / Totals Tests
# ===================================================================


class TestCountersAndTotals:
    """trigger_rules_evaluated, trigger_rules_matched, tokens, time."""

    def test_all_14_rules_evaluated(self):
        """Every route() call evaluates all 14 trigger rules."""
        router = TechniqueRouter()
        result = router.route(QuerySignals())
        assert result.trigger_rules_evaluated == 14

    def test_rules_matched_with_default_signals(self):
        """Default signals match 0 rules — no conditional triggers."""
        router = TechniqueRouter()
        result = router.route(QuerySignals())
        assert result.trigger_rules_matched == 0

    def test_rules_matched_with_single_trigger(self):
        """Only R1 fires when complexity=0.5."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.5))
        assert result.trigger_rules_matched == 1

    def test_rules_matched_with_multiple_triggers(self):
        """R1 (complexity=0.5) + R10 (complexity=0.5 is NOT > 0.7) — only R1.
        Use complexity=0.8 to fire both R1 and R10."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.8))
        assert result.trigger_rules_matched >= 2  # R1 + R10

    def test_total_estimated_tokens_only_t1(self):
        """Default signals: only T1 = 50 (CLARA) + 30 (CRP) + 20 (GSD) = 100."""
        router = TechniqueRouter()
        result = router.route(QuerySignals())
        expected = _tokens_of(TechniqueID.CLARA) + _tokens_of(TechniqueID.CRP) + _tokens_of(TechniqueID.GSD)
        assert result.total_estimated_tokens == expected

    def test_total_estimated_tokens_with_cot(self):
        """complexity=0.6: T1 (100) + CoT (350) = 450."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.6))
        t1_total = sum(_tokens_of(tid) for tid in TIER_1_IDS)
        expected = t1_total + _tokens_of(TechniqueID.CHAIN_OF_THOUGHT)
        assert result.total_estimated_tokens == expected

    def test_total_estimated_time_ms_only_t1(self):
        """Default signals: T1 time = 100 (CLARA) + 50 (CRP) + 30 (GSD) = 180."""
        router = TechniqueRouter()
        result = router.route(QuerySignals())
        expected = sum(_time_of(tid) for tid in TIER_1_IDS)
        assert result.total_estimated_time_ms == expected

    def test_total_estimated_time_ms_with_cot(self):
        """complexity=0.6: T1 time (180) + CoT time (3000) = 3180."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.6))
        t1_time = sum(_time_of(tid) for tid in TIER_1_IDS)
        expected = t1_time + _time_of(TechniqueID.CHAIN_OF_THOUGHT)
        assert result.total_estimated_time_ms == expected


# ===================================================================
# 24-26. Fallback Tests
# ===================================================================


class TestFallback:
    """_apply_fallback: T3→T2 when over budget."""

    def test_fallback_applied_flag_set(self):
        """When tokens exceed budget, fallback_applied is True."""
        router = TechniqueRouter(model_tier="light")  # 500 total
        # T1 (100) + CoT (350) + Self-Consistency (950) = 1400 >> 500
        signals = QuerySignals(
            query_complexity=0.6,
            monetary_value=500.0,
        )
        result = router.route(signals)
        assert result.fallback_applied is True

    def test_no_fallback_when_under_budget(self):
        """When tokens are within budget, fallback_applied is False."""
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals(query_complexity=0.5))
        assert result.fallback_applied is False

    def test_skipped_techniques_populated_after_fallback(self):
        """After fallback, T3 techniques appear in skipped_techniques."""
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(query_complexity=0.8, is_strategic_decision=True)
        result = router.route(signals)
        assert len(result.skipped_techniques) > 0
        skipped_ids = {s["technique_id"] for s in result.skipped_techniques}
        assert len(skipped_ids) > 0

    def test_fallback_reason_is_token_budget_exceeded(self):
        """Skipped techniques after fallback have 'token_budget_exceeded' reason."""
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(is_strategic_decision=True)
        result = router.route(signals)
        reasons = {s.get("reason") for s in result.skipped_techniques}
        assert "token_budget_exceeded" in reasons or "token_budget_exceeded_no_fallback" in reasons

    def test_fallback_adds_t2_substitutes(self):
        """After GST fallback, CHAIN_OF_THOUGHT should appear in activated."""
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(is_strategic_decision=True)
        result = router.route(signals)
        # GST (1100) + T1 (100) = 1200 > 500 → fallback
        # GST falls back to CoT
        activated_ids = _activated_ids(result)
        assert TechniqueID.CHAIN_OF_THOUGHT in activated_ids

    def test_fallback_recalculates_totals(self):
        """After fallback, total_estimated_tokens should reflect only active techniques."""
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(is_strategic_decision=True)
        result = router.route(signals)
        # Recalculate from activated techniques
        expected_tokens = sum(
            TECHNIQUE_REGISTRY[a.technique_id].estimated_tokens
            for a in result.activated_techniques
        )
        assert result.total_estimated_tokens == expected_tokens

    def test_t3_replaced_not_duplicated_in_fallback(self):
        """T3 technique should not remain in activated_techniques after fallback."""
        router = TechniqueRouter(model_tier="medium")
        # UoT (1400) + Reflexion (400) + T1 (100) = 1900 > 1500
        signals = QuerySignals(customer_tier="vip")
        result = router.route(signals)
        activated_ids = _activated_ids(result)
        assert TechniqueID.UNIVERSE_OF_THOUGHTS not in activated_ids
        assert TechniqueID.REFLEXION not in activated_ids


# ===================================================================
# 27-28. enabled_techniques Tests
# ===================================================================


class TestEnabledTechniques:
    """enabled_techniques=None enables all; explicit set restricts."""

    def test_none_enables_all_techniques(self):
        """Default (None) should not restrict any triggered technique."""
        router = TechniqueRouter(enabled_techniques=None)
        result = router.route(QuerySignals(query_complexity=0.6))
        assert TechniqueID.CHAIN_OF_THOUGHT in _activated_ids(result)

    def test_restricted_set_skips_disabled_techniques(self):
        """enabled_techniques={T1 only} should skip triggered T2 techniques."""
        router = TechniqueRouter(enabled_techniques=TIER_1_IDS)
        result = router.route(QuerySignals(query_complexity=0.8, confidence_score=0.4))
        ids = _activated_ids(result)
        # CoT should be skipped, not activated
        assert TechniqueID.CHAIN_OF_THOUGHT not in ids
        # Should appear in skipped list with correct reason
        skipped_ids = {s["technique_id"] for s in result.skipped_techniques}
        assert "chain_of_thought" in skipped_ids
        skipped_reasons = {s["reason"] for s in result.skipped_techniques}
        assert "disabled_by_tenant_config" in skipped_reasons

    def test_partial_t2_enabled(self):
        """Only allow CoT from T2 — REVERSE_THINKING should be skipped."""
        router = TechniqueRouter(
            enabled_techniques=TIER_1_IDS | {TechniqueID.CHAIN_OF_THOUGHT}
        )
        result = router.route(QuerySignals(query_complexity=0.6, confidence_score=0.4))
        ids = _activated_ids(result)
        assert TechniqueID.CHAIN_OF_THOUGHT in ids
        assert TechniqueID.REVERSE_THINKING not in ids

    def test_enabled_techniques_allows_t3(self):
        """Explicitly including T3 techniques allows them through."""
        router = TechniqueRouter(
            model_tier="heavy",
            enabled_techniques=TIER_1_IDS | {TechniqueID.SELF_CONSISTENCY},
        )
        result = router.route(QuerySignals(monetary_value=200.0))
        ids = _activated_ids(result)
        assert TechniqueID.SELF_CONSISTENCY in ids


# ===================================================================
# 29-31. get_available_techniques_for_plan
# ===================================================================


class TestPlanAvailability:
    """get_available_techniques_for_plan: free=T1, pro=T1+T2, enterprise=T1+T2+T3."""

    def test_free_plan_tier1_only(self):
        available = TechniqueRouter.get_available_techniques_for_plan("free")
        assert available == TIER_1_IDS
        assert TechniqueID.CHAIN_OF_THOUGHT not in available
        assert TechniqueID.GST not in available

    def test_pro_plan_includes_tier2(self):
        available = TechniqueRouter.get_available_techniques_for_plan("pro")
        t2_ids = {
            TechniqueID.CHAIN_OF_THOUGHT, TechniqueID.REVERSE_THINKING,
            TechniqueID.REACT, TechniqueID.STEP_BACK,
            TechniqueID.THREAD_OF_THOUGHT,
        }
        assert TIER_1_IDS.issubset(available)
        assert t2_ids.issubset(available)
        assert TechniqueID.GST not in available
        assert TechniqueID.UNIVERSE_OF_THOUGHTS not in available

    def test_enterprise_plan_all_tiers(self):
        available = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        all_ids = {tid for tid in TechniqueID}
        assert available == all_ids

    def test_vip_plan_same_as_enterprise(self):
        vip = TechniqueRouter.get_available_techniques_for_plan("vip")
        ent = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        assert vip == ent

    def test_unknown_plan_falls_back_to_tier1(self):
        available = TechniqueRouter.get_available_techniques_for_plan("unknown_plan")
        assert available == TIER_1_IDS

    def test_pro_plan_count(self):
        """Pro = 3 (T1) + 5 (T2) = 8 techniques."""
        available = TechniqueRouter.get_available_techniques_for_plan("pro")
        assert len(available) == 8

    def test_enterprise_plan_count(self):
        """Enterprise = 3 (T1) + 5 (T2) + 6 (T3) = 14 techniques."""
        available = TechniqueRouter.get_available_techniques_for_plan("enterprise")
        assert len(available) == 14

    def test_free_plan_count(self):
        available = TechniqueRouter.get_available_techniques_for_plan("free")
        assert len(available) == 3


# ===================================================================
# 32. model_tier Affects Budget
# ===================================================================


class TestModelTierBudget:
    """model_tier selects the correct TOKEN_BUDGET."""

    def test_default_model_tier_is_medium(self):
        router = TechniqueRouter()
        assert router.model_tier == "medium"
        assert router.budget.total == TOKEN_BUDGETS["medium"].total

    def test_light_model_budget(self):
        router = TechniqueRouter(model_tier="light")
        assert router.budget.total == 500

    def test_medium_model_budget(self):
        router = TechniqueRouter(model_tier="medium")
        assert router.budget.total == 1500

    def test_heavy_model_budget(self):
        router = TechniqueRouter(model_tier="heavy")
        assert router.budget.total == 3000

    def test_unknown_model_tier_defaults_to_medium(self):
        """Unknown model tier falls back to medium budget."""
        router = TechniqueRouter(model_tier="nonexistent")
        assert router.budget.total == TOKEN_BUDGETS["medium"].total

    def test_result_carries_model_tier(self):
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals())
        assert result.model_tier == "heavy"

    def test_result_carries_budget(self):
        router = TechniqueRouter(model_tier="light")
        result = router.route(QuerySignals())
        assert result.budget is not None
        assert result.budget.total == 500


# ===================================================================
# Additional Edge Case Tests
# ===================================================================


class TestEdgeCases:
    """Additional edge cases and robustness checks."""

    def test_zero_complexity_no_conditional_triggers(self):
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.0))
        assert result.trigger_rules_matched == 0
        assert len(result.activated_techniques) == 3

    def test_max_complexity_triggers_r1_and_r10(self):
        """complexity=1.0 triggers R1 (>0.4) and R10 (>0.7)."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=1.0))
        assert result.trigger_rules_matched >= 2
        ids = _activated_ids(result)
        assert TechniqueID.CHAIN_OF_THOUGHT in ids
        assert TechniqueID.LEAST_TO_MOST in ids

    def test_fallback_preserves_t1_techniques(self):
        """Fallback should never remove Tier 1 techniques."""
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(
            query_complexity=0.9,
            confidence_score=0.2,
            is_strategic_decision=True,
            monetary_value=500.0,
            resolution_path_count=5,
        )
        result = router.route(signals)
        ids = _activated_ids(result)
        assert TIER_1_IDS.issubset(ids)

    def test_activation_triggered_by_list_type(self):
        """triggered_by is always a list of strings."""
        router = TechniqueRouter()
        result = router.route(QuerySignals(query_complexity=0.6))
        for a in result.activated_techniques:
            assert isinstance(a.triggered_by, list)
            for rule_id in a.triggered_by:
                assert isinstance(rule_id, str)

    def test_technique_activation_tier_correctness(self):
        """Each TechniqueActivation has the correct tier from registry."""
        router = TechniqueRouter(model_tier="heavy")
        result = router.route(QuerySignals(
            query_complexity=0.6,
            customer_tier="vip",
            is_strategic_decision=True,
        ))
        for a in result.activated_techniques:
            expected_tier = TECHNIQUE_REGISTRY[a.technique_id].tier
            assert a.tier == expected_tier

    def test_multiple_t3_techniques_all_fallback_on_light(self):
        """Multiple T3 techniques should all be replaced on light budget."""
        router = TechniqueRouter(model_tier="light")
        signals = QuerySignals(
            query_complexity=0.9,
            is_strategic_decision=True,
            monetary_value=500.0,
            resolution_path_count=5,
            customer_tier="vip",
        )
        result = router.route(signals)
        activated_ids = _activated_ids(result)
        t3_ids = {tid for tid, info in TECHNIQUE_REGISTRY.items() if info.tier == TechniqueTier.TIER_3}
        # No T3 techniques should remain after fallback on light budget
        assert activated_ids.isdisjoint(t3_ids)

    def test_router_result_default_values(self):
        """RouterResult has sensible defaults before routing."""
        result = RouterResult()
        assert result.activated_techniques == []
        assert result.skipped_techniques == []
        assert result.trigger_rules_evaluated == 0
        assert result.trigger_rules_matched == 0
        assert result.total_estimated_tokens == 0
        assert result.total_estimated_time_ms == 0
        assert result.fallback_applied is False
        assert result.budget is None

    def test_fallback_map_has_entries_for_all_t3(self):
        """Every T3 technique has at least one fallback entry."""
        t3_ids = {tid for tid, info in TECHNIQUE_REGISTRY.items() if info.tier == TechniqueTier.TIER_3}
        for tid in t3_ids:
            assert tid in FALLBACK_MAP, f"{tid} has no FALLBACK_MAP entry"

    def test_all_14_trigger_rule_ids_unique(self):
        """All 14 trigger rule IDs should be unique."""
        rule_ids = [r.rule_id for r in TRIGGER_RULES]
        assert len(rule_ids) == len(set(rule_ids))

    def test_technique_info_all_tiers_have_entries(self):
        """TECHNIQUE_REGISTRY has entries for all TechniqueID enum values."""
        for tid in TechniqueID:
            assert tid in TECHNIQUE_REGISTRY, f"{tid} not in TECHNIQUE_REGISTRY"
