"""Tests for Smart Router (F-054) + Variant-Specific Model Access (SG-03).

Comprehensive tests covering:
- Model Registry: All 11 models present, correct tiers, correct providers
- Variant Gating (SG-03): mini_parwa, parwa, parwa_high
- Step Tier Mapping: Each atomic step -> correct tier
- Routing Decisions: simple/complex/vip/mini steps
- Fallback Chain: provider down, tier exhausted, all down
- Provider Health Tracking: success/failure/rate-limit
- MAKER Awareness: batch routing, technique-boosted steps
- Edge Cases: unknown variant, empty signals, all providers exhausted
- execute_llm_call: Google format, OpenAI format, retry, timeout
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.smart_router import (
    AtomicStepType,
    ModelConfig,
    ModelProvider,
    ModelTier,
    MODEL_REGISTRY,
    ProviderHealthTracker,
    ProviderUsage,
    RoutingDecision,
    SmartRouter,
    STEP_TIER_MAPPING,
    VARIANT_MODEL_ACCESS,
    TIER_FALLBACK_ORDER,
)


# ── Helpers ──────────────────────────────────────────────────────


@pytest.fixture
def router():
    """Fresh SmartRouter instance for each test."""
    return SmartRouter()


@pytest.fixture
def health():
    """Fresh ProviderHealthTracker for each test."""
    return ProviderHealthTracker()


# ══════════════════════════════════════════════════════════════════
# 1. MODEL REGISTRY
# ══════════════════════════════════════════════════════════════════


class TestModelRegistry:
    """Verify all 11 models are present and correctly configured."""

    def test_registry_has_10_models(self):
        """Spec tables define 10 models: 3 LIGHT + 3 MEDIUM + 3 HEAVY + 1 GUARDRAIL."""
        assert len(MODEL_REGISTRY) == 10

    def test_light_tier_has_3_models(self):
        light = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.LIGHT]
        assert len(light) == 3

    def test_medium_tier_has_3_models(self):
        medium = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.MEDIUM]
        assert len(medium) == 3

    def test_heavy_tier_has_3_models(self):
        heavy = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.HEAVY]
        assert len(heavy) == 3

    def test_guardrail_tier_has_1_model(self):
        guardrail = [
            m for m in MODEL_REGISTRY.values()
            if m.tier == ModelTier.GUARDRAIL
        ]
        assert len(guardrail) == 1
        assert guardrail[0].model_id == "llama-guard-4-12b"

    def test_light_tier_providers(self):
        light = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.LIGHT]
        providers = {m.provider for m in light}
        assert ModelProvider.CEREBRAS in providers
        assert ModelProvider.GROQ in providers
        assert ModelProvider.GOOGLE in providers

    def test_light_priority_order(self):
        """Cerebras=P1, Groq=P2, Google=P3 for LIGHT."""
        light = sorted(
            [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.LIGHT],
            key=lambda m: m.priority,
        )
        assert light[0].provider == ModelProvider.CEREBRAS
        assert light[1].provider == ModelProvider.GROQ
        assert light[2].provider == ModelProvider.GOOGLE

    def test_medium_priority_order(self):
        """Google=P1, Groq=P2, Groq=P3 for MEDIUM."""
        medium = sorted(
            [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.MEDIUM],
            key=lambda m: m.priority,
        )
        assert medium[0].provider == ModelProvider.GOOGLE
        assert medium[0].model_id == "gemini-2.0-flash-lite"

    def test_heavy_priority_order(self):
        """Groq=P1, Cerebras=P2, Groq=P3 for HEAVY."""
        heavy = sorted(
            [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.HEAVY],
            key=lambda m: m.priority,
        )
        assert heavy[0].provider == ModelProvider.GROQ
        assert heavy[0].model_id == "gpt-oss-120b"

    def test_guardrail_provider_is_groq(self):
        guardrail = [
            m for m in MODEL_REGISTRY.values()
            if m.tier == ModelTier.GUARDRAIL
        ][0]
        assert guardrail.provider == ModelProvider.GROQ

    def test_all_models_have_required_fields(self):
        for key, config in MODEL_REGISTRY.items():
            assert config.provider
            assert config.model_id
            assert config.display_name
            assert config.tier
            assert config.priority >= 1
            assert config.max_requests_per_day > 0
            assert config.max_tokens_per_minute > 0
            assert config.context_window > 0
            assert config.api_endpoint_base
            assert isinstance(config.is_openai_compatible, bool)
            assert isinstance(config.recommended_for, list)

    def test_google_models_not_openai_compatible(self):
        for config in MODEL_REGISTRY.values():
            if config.provider == ModelProvider.GOOGLE:
                assert config.is_openai_compatible is False

    def test_cerebras_models_openai_compatible(self):
        for config in MODEL_REGISTRY.values():
            if config.provider == ModelProvider.CEREBRAS:
                assert config.is_openai_compatible is True

    def test_groq_models_openai_compatible(self):
        for config in MODEL_REGISTRY.values():
            if config.provider == ModelProvider.GROQ:
                assert config.is_openai_compatible is True

    def test_heavy_models_have_larger_context_window(self):
        heavy = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.HEAVY]
        light = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.LIGHT]
        for h in heavy:
            for l in light:
                assert h.context_window >= l.context_window


# ══════════════════════════════════════════════════════════════════
# 2. VARIANT GATING (SG-03)
# ══════════════════════════════════════════════════════════════════


class TestVariantGating:
    """Verify SG-03 variant model access restrictions."""

    def test_mini_parwa_light_and_guardrail_only(self):
        tiers = VARIANT_MODEL_ACCESS["mini_parwa"]
        assert ModelTier.LIGHT in tiers
        assert ModelTier.GUARDRAIL in tiers
        assert ModelTier.MEDIUM not in tiers
        assert ModelTier.HEAVY not in tiers

    def test_parwa_light_medium_and_guardrail(self):
        tiers = VARIANT_MODEL_ACCESS["parwa"]
        assert ModelTier.LIGHT in tiers
        assert ModelTier.MEDIUM in tiers
        assert ModelTier.GUARDRAIL in tiers
        assert ModelTier.HEAVY not in tiers

    def test_parwa_high_all_tiers(self):
        tiers = VARIANT_MODEL_ACCESS["parwa_high"]
        assert ModelTier.LIGHT in tiers
        assert ModelTier.MEDIUM in tiers
        assert ModelTier.HEAVY in tiers
        assert ModelTier.GUARDRAIL in tiers

    def test_three_variants_defined(self):
        assert len(VARIANT_MODEL_ACCESS) == 3
        assert "mini_parwa" in VARIANT_MODEL_ACCESS
        assert "parwa" in VARIANT_MODEL_ACCESS
        assert "parwa_high" in VARIANT_MODEL_ACCESS

    def test_get_variant_info_mini_parwa(self, router):
        info = router.get_variant_info("mini_parwa")
        assert info["variant_type"] == "mini_parwa"
        assert "light" in info["allowed_tiers"]
        assert "guardrail" in info["allowed_tiers"]
        assert "medium" not in info["allowed_tiers"]
        assert "heavy" not in info["allowed_tiers"]

    def test_get_variant_info_parwa(self, router):
        info = router.get_variant_info("parwa")
        assert "light" in info["allowed_tiers"]
        assert "medium" in info["allowed_tiers"]

    def test_get_variant_info_parwa_high(self, router):
        info = router.get_variant_info("parwa_high")
        assert "heavy" in info["allowed_tiers"]


# ══════════════════════════════════════════════════════════════════
# 3. STEP TIER MAPPING
# ══════════════════════════════════════════════════════════════════


class TestStepTierMapping:
    """Verify each atomic step maps to correct tier."""

    def test_all_18_steps_have_mapping(self):
        assert len(STEP_TIER_MAPPING) == len(AtomicStepType)

    def test_intent_classification_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.INTENT_CLASSIFICATION] == ModelTier.LIGHT

    def test_pii_redaction_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.PII_REDACTION] == ModelTier.LIGHT

    def test_sentiment_analysis_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.SENTIMENT_ANALYSIS] == ModelTier.LIGHT

    def test_clara_quality_gate_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.CLARA_QUALITY_GATE] == ModelTier.LIGHT

    def test_crp_token_trim_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.CRP_TOKEN_TRIM] == ModelTier.LIGHT

    def test_gsd_state_step_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.GSD_STATE_STEP] == ModelTier.LIGHT

    def test_mad_decompose_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.MAD_DECOMPOSE] == ModelTier.LIGHT

    def test_mad_atom_simple_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.MAD_ATOM_SIMPLE] == ModelTier.LIGHT

    def test_mad_atom_reasoning_is_medium(self):
        assert STEP_TIER_MAPPING[AtomicStepType.MAD_ATOM_REASONING] == ModelTier.MEDIUM

    def test_cot_reasoning_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.COT_REASONING] == ModelTier.LIGHT

    def test_fake_voting_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.FAKE_VOTING] == ModelTier.LIGHT

    def test_consensus_analysis_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.CONSENSUS_ANALYSIS] == ModelTier.LIGHT

    def test_draft_response_simple_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.DRAFT_RESPONSE_SIMPLE] == ModelTier.LIGHT

    def test_draft_response_moderate_is_medium(self):
        assert STEP_TIER_MAPPING[AtomicStepType.DRAFT_RESPONSE_MODERATE] == ModelTier.MEDIUM

    def test_draft_response_complex_is_medium(self):
        assert STEP_TIER_MAPPING[AtomicStepType.DRAFT_RESPONSE_COMPLEX] == ModelTier.MEDIUM

    def test_reflexion_cycle_is_medium(self):
        assert STEP_TIER_MAPPING[AtomicStepType.REFLEXION_CYCLE] == ModelTier.MEDIUM

    def test_escalate_to_human_is_light(self):
        assert STEP_TIER_MAPPING[AtomicStepType.ESCALATE_TO_HUMAN] == ModelTier.LIGHT

    def test_guardrail_check_is_guardrail(self):
        assert STEP_TIER_MAPPING[AtomicStepType.GUARDRAIL_CHECK] == ModelTier.GUARDRAIL

    def test_light_steps_outnumber_medium(self):
        light_count = sum(
            1 for t in STEP_TIER_MAPPING.values() if t == ModelTier.LIGHT
        )
        medium_count = sum(
            1 for t in STEP_TIER_MAPPING.values() if t == ModelTier.MEDIUM
        )
        assert light_count > medium_count


# ══════════════════════════════════════════════════════════════════
# 4. ROUTING DECISIONS
# ══════════════════════════════════════════════════════════════════


class TestRoutingDecisions:
    """Test actual routing decisions from SmartRouter.route()."""

    def test_simple_step_routes_to_light(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.LIGHT
        assert decision.atomic_step_type == AtomicStepType.INTENT_CLASSIFICATION
        assert decision.variant_type == "parwa"

    def test_complex_step_routes_to_medium(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_COMPLEX,
        )
        assert decision.tier == ModelTier.MEDIUM

    def test_moderate_step_routes_to_medium(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
        )
        assert decision.tier == ModelTier.MEDIUM

    def test_reasoning_step_routes_to_medium(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.MAD_ATOM_REASONING,
        )
        assert decision.tier == ModelTier.MEDIUM

    def test_guardrail_step_always_routes_to_guardrail(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="mini_parwa",
            atomic_step=AtomicStepType.GUARDRAIL_CHECK,
        )
        assert decision.tier == ModelTier.GUARDRAIL
        assert decision.model_config.model_id == "llama-guard-4-12b"

    def test_parwa_high_can_get_heavy(self, router):
        """parwa_high allows HEAVY tier, but step must recommend it."""
        # draft_response_complex routes to MEDIUM even on parwa_high
        # because step mapping says MEDIUM. HEAVY is available but not
        # the recommended tier for any step.
        # Let's verify that the model selected is at least MEDIUM:
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa_high",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_COMPLEX,
        )
        assert decision.tier == ModelTier.MEDIUM

    def test_mini_parwa_medium_step_degrades_to_light(self, router):
        """mini_parwa can't access MEDIUM, so step degrades to LIGHT."""
        decision = router.route(
            company_id="comp_123",
            variant_type="mini_parwa",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
        )
        assert decision.tier == ModelTier.LIGHT

    def test_mini_parwa_reasoning_step_degrades_to_light(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="mini_parwa",
            atomic_step=AtomicStepType.MAD_ATOM_REASONING,
        )
        assert decision.tier == ModelTier.LIGHT

    def test_mini_parwa_never_gets_heavy(self, router):
        """No matter what step, mini_parwa never gets HEAVY tier."""
        for step in AtomicStepType:
            decision = router.route(
                company_id="comp_123",
                variant_type="mini_parwa",
                atomic_step=step,
            )
            assert decision.tier != ModelTier.HEAVY, (
                f"mini_parwa should never get HEAVY, got it for {step.value}"
            )

    def test_decision_has_model_config(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert isinstance(decision.model_config, ModelConfig)
        assert decision.model_config.model_id
        assert decision.model_config.provider

    def test_decision_has_fallback_models(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert isinstance(decision.fallback_models, list)

    def test_decision_has_routing_reason(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert isinstance(decision.routing_reason, str)
        assert len(decision.routing_reason) > 0

    def test_decision_has_utc_timestamp(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert decision.routed_at.endswith("Z") or "+" in decision.routed_at

    def test_technique_boosted_steps_flagged(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.COT_REASONING,
        )
        assert decision.technique_boosted is True

    def test_non_boosted_steps_not_flagged(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
        )
        assert decision.technique_boosted is False

    def test_company_id_is_first_user_parameter(self, router):
        """BC-001: company_id is always the second parameter (after self).
        inspect.signature on bound method excludes self, so params[0]=company_id."""
        import inspect
        sig = inspect.signature(router.route)
        params = list(sig.parameters.keys())
        # bound method signature excludes 'self'
        assert params[0] == "company_id"

    def test_vip_signals_in_routing_reason(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa_high",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_COMPLEX,
            query_signals={"customer_tier": "vip"},
        )
        assert "vip" in decision.routing_reason.lower()


# ══════════════════════════════════════════════════════════════════
# 5. FALLBACK CHAIN
# ══════════════════════════════════════════════════════════════════


class TestFallbackChain:
    """Test provider fallback logic."""

    def test_primary_provider_down_falls_to_backup(self, router):
        """When primary provider is unhealthy, falls to next in same tier."""
        # Mark primary LIGHT model (Cerebras) as unhealthy
        router._health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Connection refused"
        )
        router._health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Connection refused"
        )
        router._health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Connection refused"
        )

        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert decision.tier == ModelTier.LIGHT
        # Should not be Cerebras
        assert decision.provider != ModelProvider.CEREBRAS

    def test_all_in_tier_down_degrades_to_lower(self, router):
        """All models in MEDIUM tier down -> degrades to LIGHT."""
        # Mark all MEDIUM models unhealthy
        for config in MODEL_REGISTRY.values():
            if config.tier == ModelTier.MEDIUM:
                for _ in range(3):
                    router._health.record_failure(
                        config.provider, config.model_id, "Down",
                    )

        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_COMPLEX,
        )
        # Should degrade to LIGHT
        assert decision.tier == ModelTier.LIGHT

    def test_all_providers_down_returns_light_model(self, router):
        """BC-008: Even when ALL providers are down, returns LIGHT model."""
        # Mark EVERY model unhealthy
        for config in MODEL_REGISTRY.values():
            for _ in range(3):
                router._health.record_failure(
                    config.provider, config.model_id, "Total outage",
                )

        decision = router.route(
            company_id="comp_123",
            variant_type="parwa_high",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_COMPLEX,
        )
        # Should still return a valid decision
        assert isinstance(decision, RoutingDecision)
        assert isinstance(decision.model_config, ModelConfig)
        assert decision.tier == ModelTier.LIGHT

    def test_guardrail_fallback_works(self, router):
        """Guardrail tier should always find a model."""
        decision = router.route(
            company_id="comp_123",
            variant_type="mini_parwa",
            atomic_step=AtomicStepType.GUARDRAIL_CHECK,
        )
        assert decision.tier == ModelTier.GUARDRAIL
        assert decision.model_config.model_id == "llama-guard-4-12b"


# ══════════════════════════════════════════════════════════════════
# 6. PROVIDER HEALTH TRACKING
# ══════════════════════════════════════════════════════════════════


class TestProviderHealthTracking:
    """Test ProviderHealthTracker behavior."""

    def test_record_success_resets_failures(self, health):
        health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Timeout"
        )
        health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Timeout"
        )
        assert health._usage[
            "llama-3.1-8b-cerebras"
        ].consecutive_failures == 2

        health.record_success(
            ModelProvider.CEREBRAS, "llama-3.1-8b", tokens_used=100
        )
        assert health._usage[
            "llama-3.1-8b-cerebras"
        ].consecutive_failures == 0
        assert health._usage[
            "llama-3.1-8b-cerebras"
        ].is_healthy is True

    def test_record_failure_increments(self, health):
        health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Error 1"
        )
        health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Error 2"
        )
        assert health._usage[
            "llama-3.1-8b-cerebras"
        ].consecutive_failures == 2

    def test_3_failures_marks_unhealthy(self, health):
        health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Error"
        )
        health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Error"
        )
        assert health._usage[
            "llama-3.1-8b-cerebras"
        ].is_healthy is True

        health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "Error"
        )
        assert health._usage[
            "llama-3.1-8b-cerebras"
        ].is_healthy is False

    def test_unhealthy_provider_not_available(self, health):
        for _ in range(3):
            health.record_failure(
                ModelProvider.CEREBRAS, "llama-3.1-8b", "Down"
            )
        assert health.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b") is False

    def test_healthy_provider_is_available(self, health):
        assert health.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b") is True

    def test_unknown_provider_is_available(self, health):
        """No usage data = assume available."""
        assert health.is_available(ModelProvider.GROQ, "unknown-model") is True

    def test_daily_usage_tracking(self, health):
        assert health.get_daily_usage(
            ModelProvider.CEREBRAS, "llama-3.1-8b"
        ) == 0
        health.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        health.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        assert health.get_daily_usage(
            ModelProvider.CEREBRAS, "llama-3.1-8b"
        ) == 2

    def test_daily_remaining(self, health):
        health.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        remaining = health.get_daily_remaining(
            ModelProvider.CEREBRAS, "llama-3.1-8b"
        )
        assert remaining == 14399  # 14400 - 1

    def test_reset_daily_counts(self, health):
        health.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        health.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        assert health.get_daily_usage(
            ModelProvider.CEREBRAS, "llama-3.1-8b"
        ) == 2

        health.reset_daily_counts()
        assert health.get_daily_usage(
            ModelProvider.CEREBRAS, "llama-3.1-8b"
        ) == 0

    def test_rate_limit_check(self, health):
        assert health.check_rate_limit(
            ModelProvider.CEREBRAS, "llama-3.1-8b"
        ) is False

    def test_get_all_status(self, health):
        health.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        status = health.get_all_status()
        assert isinstance(status, dict)
        assert "llama-3.1-8b-cerebras" in status
        assert status["llama-3.1-8b-cerebras"]["daily_count"] == 1
        assert status["llama-3.1-8b-cerebras"]["is_healthy"] is True


# ══════════════════════════════════════════════════════════════════
# 7. MAKER AWARENESS
# ══════════════════════════════════════════════════════════════════


class TestMakerAwareness:
    """Test MAKER framework awareness in routing."""

    def test_route_batch_returns_multiple_decisions(self, router):
        steps = [
            AtomicStepType.INTENT_CLASSIFICATION,
            AtomicStepType.PII_REDACTION,
            AtomicStepType.SENTIMENT_ANALYSIS,
            AtomicStepType.DRAFT_RESPONSE_SIMPLE,
        ]
        decisions = router.route_batch(
            company_id="comp_123",
            variant_type="parwa",
            steps=steps,
        )
        assert len(decisions) == 4
        for d in decisions:
            assert isinstance(d, RoutingDecision)

    def test_fake_voting_routes_to_light(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.FAKE_VOTING,
        )
        assert decision.tier == ModelTier.LIGHT
        assert decision.technique_boosted is True

    def test_cot_reasoning_routes_to_light(self, router):
        """CoT reasoning uses LIGHT tier because the technique adds
        intelligence, not the model."""
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.COT_REASONING,
        )
        assert decision.tier == ModelTier.LIGHT
        assert decision.technique_boosted is True

    def test_consensus_analysis_routes_to_light(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.CONSENSUS_ANALYSIS,
        )
        assert decision.tier == ModelTier.LIGHT

    def test_clara_quality_gate_routes_to_light(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.CLARA_QUALITY_GATE,
        )
        assert decision.tier == ModelTier.LIGHT
        assert decision.technique_boosted is True

    def test_batch_mixed_steps_mixed_tiers(self, router):
        steps = [
            AtomicStepType.INTENT_CLASSIFICATION,  # LIGHT
            AtomicStepType.GUARDRAIL_CHECK,         # GUARDRAIL
            AtomicStepType.DRAFT_RESPONSE_MODERATE, # MEDIUM
        ]
        decisions = router.route_batch(
            company_id="comp_123",
            variant_type="parwa",
            steps=steps,
        )
        assert decisions[0].tier == ModelTier.LIGHT
        assert decisions[1].tier == ModelTier.GUARDRAIL
        assert decisions[2].tier == ModelTier.MEDIUM

    def test_batch_with_mini_parwa_all_light_except_guardrail(self, router):
        steps = [
            AtomicStepType.INTENT_CLASSIFICATION,
            AtomicStepType.DRAFT_RESPONSE_MODERATE,  # Would be MEDIUM
            AtomicStepType.GUARDRAIL_CHECK,
        ]
        decisions = router.route_batch(
            company_id="comp_123",
            variant_type="mini_parwa",
            steps=steps,
        )
        assert decisions[0].tier == ModelTier.LIGHT
        assert decisions[1].tier == ModelTier.LIGHT  # Degraded
        assert decisions[2].tier == ModelTier.GUARDRAIL


# ══════════════════════════════════════════════════════════════════
# 8. EDGE CASES
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and BC-008 compliance."""

    def test_unknown_variant_defaults_to_mini_parwa(self, router):
        """Unknown variant_type should default to safest (mini_parwa)."""
        decision = router.route(
            company_id="comp_123",
            variant_type="unknown_variant_xyz",
            atomic_step=AtomicStepType.DRAFT_RESPONSE_MODERATE,
        )
        # Should degrade to LIGHT since mini_parwa doesn't have MEDIUM
        assert decision.tier == ModelTier.LIGHT

    def test_empty_query_signals_uses_defaults(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
            query_signals={},
        )
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.LIGHT

    def test_none_query_signals_uses_defaults(self, router):
        decision = router.route(
            company_id="comp_123",
            variant_type="parwa",
            atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
            query_signals=None,
        )
        assert isinstance(decision, RoutingDecision)

    def test_all_providers_exhausted_never_crashes(self, router):
        """BC-008: Even total failure should return a valid decision."""
        # Simulate complete failure by making _route_safe raise
        with patch.object(
            router, "_route_safe", side_effect=RuntimeError("Total failure"),
        ):
            decision = router.route(
                company_id="comp_123",
                variant_type="parwa",
                atomic_step=AtomicStepType.INTENT_CLASSIFICATION,
            )
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.LIGHT
        assert "emergency_fallback" in decision.routing_reason

    def test_provider_status_returns_dict(self, router):
        status = router.get_provider_status()
        assert isinstance(status, dict)

    def test_empty_batch_returns_empty_list(self, router):
        decisions = router.route_batch(
            company_id="comp_123",
            variant_type="parwa",
            steps=[],
        )
        assert decisions == []


# ══════════════════════════════════════════════════════════════════
# 9. EXECUTE_LLM_CALL
# ══════════════════════════════════════════════════════════════════


class TestExecuteLLMCall:
    """Test LLM API call execution with mocked HTTP."""

    @pytest.fixture
    def openai_style_decision(self, router):
        return RoutingDecision(
            atomic_step_type=AtomicStepType.INTENT_CLASSIFICATION,
            model_config=MODEL_REGISTRY["llama-3.1-8b-cerebras"],
            provider=ModelProvider.CEREBRAS,
            tier=ModelTier.LIGHT,
            variant_type="parwa",
            routing_reason="test",
        )

    @pytest.fixture
    def google_style_decision(self, router):
        return RoutingDecision(
            atomic_step_type=AtomicStepType.INTENT_CLASSIFICATION,
            model_config=MODEL_REGISTRY["gemma-3-27b-it-google"],
            provider=ModelProvider.GOOGLE,
            tier=ModelTier.LIGHT,
            variant_type="parwa",
            routing_reason="test",
        )

    @pytest.fixture
    def messages(self):
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]

    def test_openai_compatible_call_succeeds(
        self, router, openai_style_decision, messages,
    ):
        """Cerebras/Groq OpenAI-compatible format works."""
        mock_response = {
            "content": "I'm doing well, thank you!",
            "model": "llama-3.1-8b",
            "provider": "cerebras",
            "finish_reason": "stop",
            "total_tokens": 28,
        }

        with patch.object(
            router, "_call_provider", return_value=mock_response,
        ):
            result = router.execute_llm_call(
                company_id="comp_123",
                routing_decision=openai_style_decision,
                messages=messages,
            )

        assert result["content"] == "I'm doing well, thank you!"
        assert result["provider"] == "cerebras"
        assert result["finish_reason"] == "stop"
        assert result["total_tokens"] == 28

    def test_google_api_call_succeeds(
        self, router, google_style_decision, messages,
    ):
        """Google AI Studio format works."""
        mock_response = {
            "content": "I'm doing well, thank you!",
            "model": "gemma-3-27b-it",
            "provider": "google",
            "finish_reason": "STOP",
            "total_tokens": 28,
        }

        with patch.object(
            router, "_call_provider", return_value=mock_response,
        ):
            result = router.execute_llm_call(
                company_id="comp_123",
                routing_decision=google_style_decision,
                messages=messages,
            )

        assert result["content"] == "I'm doing well, thank you!"
        assert result["provider"] == "google"
        assert result["finish_reason"] == "STOP"

    def test_retry_on_failure_with_fallback(
        self, router, openai_style_decision, messages,
    ):
        """On failure, retries then falls back to next model."""
        with patch.object(
            router, "_call_provider", side_effect=RuntimeError("Provider down"),
        ):
            result = router.execute_llm_call(
                company_id="comp_123",
                routing_decision=openai_style_decision,
                messages=messages,
            )

        # Should return error fallback since all retries fail
        assert "content" in result
        assert result.get("fallback_used") is True or result.get("error")

    def test_all_providers_fail_returns_safe_dict(
        self, router, openai_style_decision, messages,
    ):
        """BC-008: Even total failure returns a valid dict."""
        with patch(
            "backend.app.core.smart_router.SmartRouter._execute_llm_call_safe",
            side_effect=RuntimeError("Total catastrophe"),
        ):
            result = router.execute_llm_call(
                company_id="comp_123",
                routing_decision=openai_style_decision,
                messages=messages,
            )

        assert isinstance(result, dict)
        assert "content" in result
        assert "error" in result

    def test_google_empty_candidates_returns_safe(
        self, router, google_style_decision, messages,
    ):
        """Google returns empty candidates -> safe response."""
        mock_response = {
            "content": "",
            "model": "gemma-3-27b-it",
            "provider": "google",
            "finish_reason": "empty",
        }

        with patch.object(
            router, "_call_provider", return_value=mock_response,
        ):
            result = router.execute_llm_call(
                company_id="comp_123",
                routing_decision=google_style_decision,
                messages=messages,
            )

        assert result["content"] == ""
        assert result["finish_reason"] == "empty"

    def test_openai_empty_choices_returns_safe(
        self, router, openai_style_decision, messages,
    ):
        mock_response = {
            "content": "",
            "model": "llama-3.1-8b",
            "provider": "cerebras",
            "finish_reason": "empty",
        }

        with patch.object(
            router, "_call_provider", return_value=mock_response,
        ):
            result = router.execute_llm_call(
                company_id="comp_123",
                routing_decision=openai_style_decision,
                messages=messages,
            )

        assert result["content"] == ""
        assert result["finish_reason"] == "empty"


# ══════════════════════════════════════════════════════════════════
# 10. ENUMS
# ══════════════════════════════════════════════════════════════════


class TestEnums:
    """Verify enum completeness."""

    def test_model_provider_values(self):
        assert ModelProvider.GOOGLE.value == "google"
        assert ModelProvider.CEREBRAS.value == "cerebras"
        assert ModelProvider.GROQ.value == "groq"

    def test_model_tier_values(self):
        assert ModelTier.LIGHT.value == "light"
        assert ModelTier.MEDIUM.value == "medium"
        assert ModelTier.HEAVY.value == "heavy"
        assert ModelTier.GUARDRAIL.value == "guardrail"

    def test_atomic_step_type_count(self):
        assert len(AtomicStepType) == 18

    def test_all_step_types_have_tier_mapping(self):
        for step in AtomicStepType:
            assert step in STEP_TIER_MAPPING, f"{step} missing from mapping"


# ══════════════════════════════════════════════════════════════════
# 11. TOKEN ESTIMATION
# ══════════════════════════════════════════════════════════════════


class TestTokenEstimation:
    """Verify token estimation per step."""

    def test_light_steps_have_low_estimates(self, router):
        light_steps = {
            AtomicStepType.INTENT_CLASSIFICATION,
            AtomicStepType.PII_REDACTION,
            AtomicStepType.ESCALATE_TO_HUMAN,
        }
        for step in light_steps:
            assert router._estimate_tokens(step) <= 200

    def test_heavy_steps_have_high_estimates(self, router):
        assert router._estimate_tokens(
            AtomicStepType.DRAFT_RESPONSE_COMPLEX
        ) == 800
        assert router._estimate_tokens(
            AtomicStepType.MAD_ATOM_REASONING
        ) == 400


# ══════════════════════════════════════════════════════════════════
# 12. TECHNIQUE BOOSTED DETECTION
# ══════════════════════════════════════════════════════════════════


class TestTechniqueBoosted:
    """Verify technique-boosted detection."""

    def test_cot_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.COT_REASONING
        ) is True

    def test_fake_voting_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.FAKE_VOTING
        ) is True

    def test_consensus_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.CONSENSUS_ANALYSIS
        ) is True

    def test_clara_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.CLARA_QUALITY_GATE
        ) is True

    def test_crp_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.CRP_TOKEN_TRIM
        ) is True

    def test_gsd_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.GSD_STATE_STEP
        ) is True

    def test_draft_response_not_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.DRAFT_RESPONSE_SIMPLE
        ) is False

    def test_reflexion_not_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(
            AtomicStepType.REFLEXION_CYCLE
        ) is False
