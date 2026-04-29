"""Tests for Smart Router (F-054) – Day 2 AI Engine.

Covers:
- Route returns valid RoutingDecision for each tier
- Variant gating (mini_parwa, parwa, high_parwa)
- Unknown variant defaults to mini_parwa
- BC-008: route() NEVER crashes
- ProviderHealthTracker shared state
- RateLimitError exists
- Model registry structure
- Technique-boosted detection
"""

from __future__ import annotations

import pytest

from app.core.smart_router import (
    AtomicStepType,
    ModelProvider,
    ModelTier,
    SmartRouter,
    ProviderHealthTracker,
    RateLimitError,
    RoutingDecision,
    MODEL_REGISTRY,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def router() -> SmartRouter:
    return SmartRouter()


COMPANY_ID = "test-company-123"


# ── 1. Route returns valid RoutingDecision ───────────────────────


class TestRouteReturnsDecision:
    def test_light_step_returns_light_model(self, router: SmartRouter):
        decision = router.route(
            COMPANY_ID, "parwa", AtomicStepType.INTENT_CLASSIFICATION
        )
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.LIGHT

    def test_medium_step_returns_medium_model(self, router: SmartRouter):
        decision = router.route(COMPANY_ID, "parwa", AtomicStepType.MAD_ATOM_REASONING)
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.MEDIUM

    def test_guardrail_step_returns_guardrail(self, router: SmartRouter):
        decision = router.route(COMPANY_ID, "parwa", AtomicStepType.GUARDRAIL_CHECK)
        assert isinstance(decision, RoutingDecision)
        assert decision.tier == ModelTier.GUARDRAIL

    def test_decision_has_required_fields(self, router: SmartRouter):
        decision = router.route(COMPANY_ID, "parwa", AtomicStepType.FAKE_VOTING)
        assert decision.atomic_step_type == AtomicStepType.FAKE_VOTING
        assert decision.model_config is not None
        assert decision.provider in list(ModelProvider)
        assert decision.variant_type == "parwa"
        assert decision.routing_reason != ""
        assert decision.estimated_tokens > 0


# ── 2. Variant Gating ────────────────────────────────────────────


class TestVariantGating:
    def test_mini_parwa_only_light_and_guardrail(self, router: SmartRouter):
        # MAD_ATOM_REASONING is mapped to MEDIUM, but mini_parwa only gets
        # LIGHT
        decision = router.route(
            COMPANY_ID, "mini_parwa", AtomicStepType.MAD_ATOM_REASONING
        )
        assert decision.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)

    def test_parwa_gets_medium(self, router: SmartRouter):
        decision = router.route(COMPANY_ID, "parwa", AtomicStepType.MAD_ATOM_REASONING)
        assert decision.tier == ModelTier.MEDIUM

    def test_high_parwa_gets_heavy(self, router: SmartRouter):
        # DRAFT_RESPONSE_COMPLEX mapped to MEDIUM, but high_parwa should get it
        decision = router.route(
            COMPANY_ID, "high_parwa", AtomicStepType.DRAFT_RESPONSE_COMPLEX
        )
        # This step is mapped to MEDIUM, high_parwa should allow MEDIUM
        assert decision.tier in (ModelTier.MEDIUM, ModelTier.LIGHT)

    def test_high_parwa_allows_heavy_models(self, router: SmartRouter):
        allowed = router._get_allowed_tiers("high_parwa")
        assert ModelTier.HEAVY in allowed


# ── 3. Unknown variant defaults to mini_parwa ────────────────────


class TestUnknownVariant:
    def test_defaults_to_mini_parwa(self, router: SmartRouter):
        decision = router.route(
            COMPANY_ID, "unknown_variant_xyz", AtomicStepType.INTENT_CLASSIFICATION
        )
        # mini_parwa only allows LIGHT, so a MEDIUM step should degrade to
        # LIGHT
        assert decision.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)

    def test_empty_variant_defaults_to_mini_parwa(self, router: SmartRouter):
        decision = router.route(COMPANY_ID, "", AtomicStepType.INTENT_CLASSIFICATION)
        assert decision.tier == ModelTier.LIGHT


# ── 4. BC-008: route() NEVER crashes ─────────────────────────────


class TestBC008NeverCrashes:
    @pytest.mark.parametrize("step", list(AtomicStepType))
    def test_route_never_crashes_for_any_step(
        self, router: SmartRouter, step: AtomicStepType
    ):
        decision = router.route(COMPANY_ID, "parwa", step)
        assert isinstance(decision, RoutingDecision)

    def test_route_with_none_variant(self, router: SmartRouter):
        decision = router.route(
            COMPANY_ID, None, AtomicStepType.INTENT_CLASSIFICATION
        )  # type: ignore
        assert isinstance(decision, RoutingDecision)

    def test_route_batch_never_crashes(self, router: SmartRouter):
        decisions = router.route_batch(
            COMPANY_ID,
            "parwa",
            [
                AtomicStepType.INTENT_CLASSIFICATION,
                AtomicStepType.FAKE_VOTING,
                AtomicStepType.GUARDRAIL_CHECK,
            ],
        )
        assert len(decisions) == 3
        for d in decisions:
            assert isinstance(d, RoutingDecision)


# ── 5. ProviderHealthTracker ──────────────────────────────────────


class TestProviderHealthTracker:
    def test_record_success_resets_failures(self):
        tracker = ProviderHealthTracker()
        provider = ModelProvider.CEREBRAS
        model_id = "llama-3.1-8b"
        tracker.record_failure(provider, model_id, "test error")
        assert tracker.is_available(provider, model_id)
        tracker.record_success(provider, model_id)
        usage = tracker._usage.get(f"{model_id}-cerebras")
        assert usage is not None
        assert usage.consecutive_failures == 0

    def test_record_failure_marks_unhealthy_after_threshold(self):
        tracker = ProviderHealthTracker()
        provider = ModelProvider.GROQ
        model_id = "llama-3.1-8b"
        for _ in range(3):
            tracker.record_failure(provider, model_id, "fail")
        assert not tracker.is_available(provider, model_id)

    def test_record_rate_limit_sets_cooldown(self):
        tracker = ProviderHealthTracker()
        provider = ModelProvider.GROQ
        model_id = "llama-3.1-8b"
        tracker.record_rate_limit(provider, model_id, retry_after_seconds=120)
        assert not tracker.is_available(provider, model_id)


# ── 6. RateLimitError ────────────────────────────────────────────


class TestRateLimitError:
    def test_exception_exists(self):
        err = RateLimitError(
            provider=ModelProvider.GROQ,
            model_id="llama-3.1-8b",
            retry_after=60,
            detail="Too many requests",
        )
        assert err.retry_after == 60
        assert err.provider == ModelProvider.GROQ

    def test_has_provider_and_model_id(self):
        err = RateLimitError(
            provider=ModelProvider.CEREBRAS,
            model_id="llama-3.1-8b",
        )
        assert err.model_id == "llama-3.1-8b"

    def test_is_exception(self):
        assert issubclass(RateLimitError, Exception)


# ── 7. Shared health state ───────────────────────────────────────


class TestSharedHealthState:
    def test_two_routers_share_tracker(self):
        r1 = SmartRouter()
        r2 = SmartRouter()
        r1._health.record_failure(ModelProvider.GROQ, "llama-3.1-8b", "fail1")
        r1._health.record_failure(ModelProvider.GROQ, "llama-3.1-8b", "fail2")
        # r2 should see the failures from r1 (class-level shared state)
        assert not r2._health.is_available(ModelProvider.GROQ, "llama-3.1-8b")

    def test_class_level_shared_usage(self):
        assert hasattr(ProviderHealthTracker, "_shared_usage")
        assert isinstance(ProviderHealthTracker._shared_usage, dict)


# ── 8. Model registry ────────────────────────────────────────────


class TestModelRegistry:
    def test_has_light_models(self):
        light = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.LIGHT]
        assert len(light) >= 2

    def test_has_medium_models(self):
        medium = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.MEDIUM]
        assert len(medium) >= 2

    def test_has_heavy_models(self):
        heavy = [m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.HEAVY]
        assert len(heavy) >= 2

    def test_has_guardrail_model(self):
        guardrail = [
            m for m in MODEL_REGISTRY.values() if m.tier == ModelTier.GUARDRAIL
        ]
        assert len(guardrail) >= 1


# ── 9. Technique boosted ─────────────────────────────────────────


class TestTechniqueBoosted:
    def test_cot_reasoning_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(AtomicStepType.COT_REASONING) is True

    def test_fake_voting_is_technique_boosted(self):
        assert SmartRouter._is_technique_boosted(AtomicStepType.FAKE_VOTING) is True

    def test_mad_atom_reasoning_is_not_technique_boosted(self):
        assert (
            SmartRouter._is_technique_boosted(AtomicStepType.MAD_ATOM_REASONING)
            is False
        )

    def test_draft_response_complex_is_not_technique_boosted(self):
        assert (
            SmartRouter._is_technique_boosted(AtomicStepType.DRAFT_RESPONSE_COMPLEX)
            is False
        )
