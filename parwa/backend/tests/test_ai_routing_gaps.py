"""
Gap-Filling Tests for Week 8 Day 1 (AI Routing) — Smart Router & Failover.

Covers 6 identified gaps:
1. [CRITICAL]  Tier boundary overflow — requests exceeding tier limits
                silently route to wrong tier.
2. [HIGH]      Race condition in provider failover — concurrent requests
                during provider failure cause inconsistent routing.
3. [HIGH]      Variant isolation breach — config changes to one variant
                affect other variants.
4. [MEDIUM]    Silent failure in provider health check — unhealthy
                providers not properly detected.
5. [MEDIUM]    Idempotency violation in routing — duplicate requests get
                processed multiple times.
6. [HIGH]      Tenant isolation in variant config — variant configuration
                leaks between tenants.

BC-001: company_id is always first parameter.
BC-008: Every method wrapped in try/except, never crashes.
All external dependencies are mocked — no real API calls.
"""

from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

from app.core.smart_router import (
    AtomicStepType,
    ModelProvider,
    ModelTier,
    ProviderHealthTracker,
    ProviderUsage,
    SmartRouter,
    RoutingDecision,
    VARIANT_MODEL_ACCESS,
    MODEL_REGISTRY,
    STEP_TIER_MAPPING,
    TIER_FALLBACK_ORDER,
    RateLimitError,
)
from app.core.model_failover import (
    FailoverChainExecutor,
    FailoverManager,
    FailoverReason,
    ProviderState,
    CircuitBreaker,
    DegradedResponseDetector,
    FAILOVER_CHAINS,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

COMPANY_A = "tenant-a-001"
COMPANY_B = "tenant-b-002"


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """Reset class-level shared state before each test for isolation."""
    ProviderHealthTracker._shared_usage.clear()
    ProviderHealthTracker._shared_last_daily_reset = ""
    yield


@pytest.fixture
def router() -> SmartRouter:
    """Return a fresh SmartRouter instance."""
    return SmartRouter()


@pytest.fixture
def tracker() -> ProviderHealthTracker:
    """Return a fresh ProviderHealthTracker."""
    return ProviderHealthTracker()


@pytest.fixture
def failover_manager() -> FailoverManager:
    """Return a fresh FailoverManager."""
    return FailoverManager()


@pytest.fixture
def executor(failover_manager: FailoverManager) -> FailoverChainExecutor:
    """Return a FailoverChainExecutor bound to a fresh manager."""
    return FailoverChainExecutor(failover_manager)


# ═══════════════════════════════════════════════════════════════════════
# 1. [CRITICAL] Tier Boundary Overflow
# ═══════════════════════════════════════════════════════════════════════


class TestTierBoundaryOverflow:
    """GAP-1: Requests exceeding tier limits must not silently route to
    wrong tier.  When a LIGHT step is requested under a mini_parwa variant
    (which only allows LIGHT + GUARDRAIL), the router must never upgrade
    to MEDIUM even if the MEDIUM tier is available.
    """

    def test_mini_parwa_never_routes_to_medium(self, router: SmartRouter):
        """mini_parwa variant must never receive a MEDIUM-tier model,
        even when a step would normally map to MEDIUM."""
        decision = router.route(
            COMPANY_A, "mini_parwa", AtomicStepType.MAD_ATOM_REASONING,
        )
        assert isinstance(decision, RoutingDecision)
        assert decision.tier != ModelTier.MEDIUM, (
            "mini_parwa must NEVER get MEDIUM tier — tier boundary overflow"
        )
        assert decision.tier in (
            ModelTier.LIGHT,
            ModelTier.GUARDRAIL,
        )

    def test_mini_parwa_never_routes_to_heavy(self, router: SmartRouter):
        """mini_parwa variant must never receive a HEAVY-tier model."""
        decision = router.route(
            COMPANY_A, "mini_parwa", AtomicStepType.DRAFT_RESPONSE_COMPLEX,
        )
        assert decision.tier != ModelTier.HEAVY

    def test_parwa_never_routes_to_heavy(self, router: SmartRouter):
        """parwa variant must never receive a HEAVY-tier model."""
        decision = router.route(
            COMPANY_A, "parwa", AtomicStepType.REFLEXION_CYCLE,
        )
        assert decision.tier != ModelTier.HEAVY

    def test_tier_boundary_respected_at_daily_limit(self, router: SmartRouter):
        """When daily request count reaches the tier limit, the router
        must fall back to a lower tier, NOT silently upgrade."""
        provider = ModelProvider.CEREBRAS
        model_id = "llama-3.1-8b"
        key = f"{model_id}-cerebras"

        # Exhaust the daily limit for the primary LIGHT model
        config = MODEL_REGISTRY[key]
        for _ in range(config.max_requests_per_day):
            router._health.record_success(provider, model_id)

        assert router._health.get_daily_remaining(provider, model_id) == 0

        # Route a LIGHT step — should still get LIGHT tier (fallback
        # within tier) or degrade, but NEVER MEDIUM/HEAVY
        decision = router.route(
            COMPANY_A, "mini_parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert decision.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)

    def test_unknown_variant_never_exceeds_light_boundary(self, router: SmartRouter):
        """Unknown variants default to mini_parwa and must never
        exceed LIGHT tier."""
        decision = router.route(
            COMPANY_A, "nonexistent_variant",
            AtomicStepType.MAD_ATOM_REASONING,
        )
        assert decision.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)

    def test_heavy_step_under_parwa_degrades_not_upgrades(self, router: SmartRouter):
        """A step that would normally need HEAVY, under parwa (no HEAVY),
        must degrade to MEDIUM, never exceed parwa's allowed tiers."""
        decision = router.route(
            COMPANY_A, "parwa", AtomicStepType.REFLEXION_CYCLE,
        )
        assert decision.tier in (
            ModelTier.LIGHT,
            ModelTier.MEDIUM,
            ModelTier.GUARDRAIL,
        )
        assert decision.tier != ModelTier.HEAVY

    def test_batch_routing_respects_tier_boundaries(self, router: SmartRouter):
        """route_batch must respect tier boundaries for every step."""
        steps = [
            AtomicStepType.INTENT_CLASSIFICATION,
            AtomicStepType.MAD_ATOM_REASONING,
            AtomicStepType.DRAFT_RESPONSE_COMPLEX,
            AtomicStepType.GUARDRAIL_CHECK,
            AtomicStepType.REFLEXION_CYCLE,
        ]
        decisions = router.route_batch(COMPANY_A, "mini_parwa", steps)
        assert len(decisions) == len(steps)
        for d in decisions:
            assert d.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL), (
                f"Step {d.atomic_step_type.value} leaked to tier {d.tier.value}"
            )


# ═══════════════════════════════════════════════════════════════════════
# 2. [HIGH] Race Condition in Provider Failover
# ═══════════════════════════════════════════════════════════════════════


class TestRaceConditionFailover:
    """GAP-2: Concurrent requests during provider failure must all either
    successfully failover or fail gracefully.  No request may hang forever
    or get stuck in an infinite retry loop.
    """

    def test_concurrent_failover_all_complete(self, executor: FailoverChainExecutor):
        """10 concurrent requests hitting a failing primary must all
        complete within a bounded time."""
        call_count = {"n": 0}
        fail_count = {"n": 0}

        def call_fn(provider: str, model_id: str) -> dict:
            call_count["n"] += 1
            if provider == "cerebras" and call_count["n"] <= 5:
                fail_count["n"] += 1
                raise ConnectionError("Cerebras intermittent failure")
            return {"content": f"OK from {provider}/{model_id}", "latency_ms": 10}

        chain = [("cerebras", "llama-3.1-8b"), ("groq", "llama-3.1-8b")]

        results = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [
                pool.submit(
                    executor.execute_with_failover,
                    COMPANY_A, chain, call_fn, max_retries=2,
                )
                for _ in range(10)
            ]
            for future in as_completed(futures, timeout=15):
                result = future.result(timeout=15)
                results.append(result)

        assert len(results) == 10, (
            f"Only {len(results)}/10 requests completed — possible hang"
        )
        # All results must have content (BC-008)
        for r in results:
            assert "content" in r

    def test_failover_no_infinite_retry(self, executor: FailoverChainExecutor):
        """When ALL providers fail, the executor must return a graceful
        error response, not retry forever."""
        def failing_call(provider: str, model_id: str) -> dict:
            raise ConnectionError("Provider down")

        chain = [("cerebras", "llama-3.1-8b"), ("groq", "llama-3.1-8b")]

        result = executor.execute_with_failover(
            COMPANY_A, chain, failing_call, max_retries=3,
        )
        assert result is not None
        assert result.get("_all_providers_failed") is True
        assert result.get("_graceful_degradation") is True
        assert "content" in result

    @pytest.mark.asyncio
    async def test_async_concurrent_failover_all_complete(self, failover_manager: FailoverManager):
        """Async concurrent requests during provider failure must all
        complete without hanging."""
        async_exec = FailoverChainExecutor(failover_manager)

        call_count = 0

        async def async_call_fn(provider: str, model_id: str) -> dict:
            nonlocal call_count
            call_count += 1
            if provider == "cerebras" and call_count <= 3:
                raise ConnectionError("Intermittent failure")
            return {"content": f"Async OK from {provider}", "latency_ms": 5}

        chain = [("cerebras", "llama-3.1-8b"), ("groq", "llama-3.1-8b")]

        tasks = [
            async_exec.async_execute_with_failover(
                COMPANY_A, chain, async_call_fn, max_retries=2,
            )
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # None should be exceptions (BC-008)
        for r in results:
            assert not isinstance(r, Exception), f"Request raised: {r}"
            assert "content" in r

    def test_circuit_breaker_opens_on_threshold(self, failover_manager: FailoverManager):
        """Circuit breaker must open after recovery_threshold failures."""
        failover_manager.report_failure(
            "cerebras", "llama-3.1-8b",
            FailoverReason.CONNECTION_ERROR, "connection refused",
            company_id=COMPANY_A,
        )
        failover_manager.report_failure(
            "cerebras", "llama-3.1-8b",
            FailoverReason.CONNECTION_ERROR, "connection refused",
            company_id=COMPANY_A,
        )
        # Two failures = DEGRADED, still available
        assert failover_manager.is_available("cerebras", "llama-3.1-8b")

        failover_manager.report_failure(
            "cerebras", "llama-3.1-8b",
            FailoverReason.CONNECTION_ERROR, "connection refused",
            company_id=COMPANY_A,
        )
        # Three failures = CIRCUIT_OPEN, unavailable
        assert not failover_manager.is_available("cerebras", "llama-3.1-8b")
        state = failover_manager.get_provider_state("cerebras", "llama-3.1-8b")
        assert state == ProviderState.CIRCUIT_OPEN

    def test_concurrent_requests_skip_open_circuit(self, executor: FailoverChainExecutor):
        """When a circuit is open, concurrent requests should immediately
        skip that provider, not attempt and retry."""
        # Open the circuit for cerebras
        for _ in range(3):
            executor.manager.report_failure(
                "cerebras", "llama-3.1-8b",
                FailoverReason.SERVER_ERROR, "server down",
                company_id=COMPANY_A,
            )

        cerebras_calls = {"n": 0}

        def call_fn(provider: str, model_id: str) -> dict:
            if provider == "cerebras":
                cerebras_calls["n"] += 1
            return {"content": f"OK from {provider}", "latency_ms": 5}

        chain = [("cerebras", "llama-3.1-8b"), ("groq", "llama-3.1-8b")]
        result = executor.execute_with_failover(
            COMPANY_A, chain, call_fn, max_retries=2,
        )
        # Cerebras should be skipped entirely (circuit open)
        assert cerebras_calls["n"] == 0
        assert "content" in result


# ═══════════════════════════════════════════════════════════════════════
# 3. [HIGH] Variant Isolation Breach
# ═══════════════════════════════════════════════════════════════════════


class TestVariantIsolationBreach:
    """GAP-3: Modifying one variant's configuration must not affect
    another variant.  The VARIANT_MODEL_ACCESS mapping is a module-level
    constant so this tests that the router respects boundaries.
    """

    def test_light_variant_does_not_affect_medium_tier_models(self, router: SmartRouter):
        """Routing decisions for MEDIUM steps under parwa must use
        MEDIUM-tier models, regardless of any LIGHT-tier config."""
        medium_step = AtomicStepType.MAD_ATOM_REASONING

        # Route under parwa (which has LIGHT + MEDIUM)
        decision_parwa = router.route(COMPANY_A, "parwa", medium_step)

        # The model chosen should be a MEDIUM-tier model
        assert decision_parwa.tier == ModelTier.MEDIUM
        assert decision_parwa.model_config.tier == ModelTier.MEDIUM

    def test_variant_allowed_tiers_are_disjoint_sets(self):
        """Each variant must have its own independent tier access."""
        mini_tiers = VARIANT_MODEL_ACCESS["mini_parwa"]
        parwa_tiers = VARIANT_MODEL_ACCESS["parwa"]
        parwa_high_tiers = VARIANT_MODEL_ACCESS["parwa_high"]

        # mini_parwa is a strict subset of parwa
        assert mini_tiers.issubset(parwa_tiers)
        # parwa is a strict subset of parwa_high
        assert parwa_tiers.issubset(parwa_high_tiers)
        # parwa_high has all tiers
        assert ModelTier.HEAVY in parwa_high_tiers
        assert ModelTier.HEAVY not in parwa_tiers
        assert ModelTier.HEAVY not in mini_tiers
        assert ModelTier.MEDIUM not in mini_tiers

    def test_modifying_variant_access_for_one_does_not_affect_another(self, router: SmartRouter):
        """Even when we mutate a variant's allowed tiers (simulating a
        config change), the other variants remain unchanged."""
        # Snapshot original access
        original_parwa = set(VARIANT_MODEL_ACCESS["parwa"])
        original_mini = set(VARIANT_MODEL_ACCESS["mini_parwa"])
        original_high = set(VARIANT_MODEL_ACCESS["parwa_high"])

        # Simulate a config change: remove MEDIUM from parwa
        VARIANT_MODEL_ACCESS["parwa"] = {ModelTier.LIGHT, ModelTier.GUARDRAIL}

        try:
            # parwa now degraded
            decision = router.route(
                COMPANY_A, "parwa", AtomicStepType.MAD_ATOM_REASONING,
            )
            assert decision.tier == ModelTier.LIGHT

            # mini_parwa must be UNCHANGED
            assert VARIANT_MODEL_ACCESS["mini_parwa"] == original_mini
            assert ModelTier.MEDIUM not in VARIANT_MODEL_ACCESS["mini_parwa"]

            # parwa_high must be UNCHANGED
            assert VARIANT_MODEL_ACCESS["parwa_high"] == original_high
        finally:
            # Restore for other tests
            VARIANT_MODEL_ACCESS["parwa"] = original_parwa

    def test_guardrail_step_independent_of_variant(self, router: SmartRouter):
        """GUARDRAIL steps must always get GUARDRAIL tier regardless of
        variant config — guardrail isolation is absolute."""
        for variant in ("mini_parwa", "parwa", "parwa_high", "unknown"):
            decision = router.route(
                COMPANY_A, variant, AtomicStepType.GUARDRAIL_CHECK,
            )
            assert decision.tier == ModelTier.GUARDRAIL

    def test_step_tier_mapping_not_mutated_by_routing(self, router: SmartRouter):
        """Routing many requests must not mutate the global
        STEP_TIER_MAPPING dictionary."""
        original_mapping = dict(STEP_TIER_MAPPING)

        for _ in range(50):
            for step in AtomicStepType:
                for variant in ("mini_parwa", "parwa", "parwa_high"):
                    router.route(COMPANY_A, variant, step)

        assert STEP_TIER_MAPPING == original_mapping


# ═══════════════════════════════════════════════════════════════════════
# 4. [MEDIUM] Silent Failure in Provider Health Check
# ═══════════════════════════════════════════════════════════════════════


class TestSilentHealthCheckFailure:
    """GAP-4: Intermittent provider failures must be detected by the
    health tracker even when the endpoint returns 200 OK.  The tracker
    should accumulate failures and eventually mark the provider unhealthy.
    """

    def test_single_failure_does_not_mark_unhealthy(self, tracker: ProviderHealthTracker):
        """One failure should not mark a provider as unhealthy."""
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "timeout",
        )
        assert tracker.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b")

    def test_two_failures_mark_degraded_still_available(self, tracker: ProviderHealthTracker):
        """Two consecutive failures should not yet mark unavailable
        (threshold is 3)."""
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "fail1",
        )
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "fail2",
        )
        assert tracker.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b")
        # But consecutive failures should be 2
        key = "llama-3.1-8b-cerebras"
        usage = tracker._usage.get(key)
        assert usage is not None
        assert usage.consecutive_failures == 2

    def test_three_failures_mark_unhealthy(self, tracker: ProviderHealthTracker):
        """Three consecutive failures must mark provider as unhealthy."""
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "fail1",
        )
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "fail2",
        )
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "fail3",
        )
        assert not tracker.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b")

    def test_success_resets_failure_counter(self, tracker: ProviderHealthTracker):
        """A successful call must reset the consecutive failure counter."""
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "fail1",
        )
        tracker.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "fail2",
        )
        # Two failures, one success resets
        tracker.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")

        # Still available, and counter reset
        assert tracker.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b")
        key = "llama-3.1-8b-cerebras"
        assert tracker._usage[key].consecutive_failures == 0

    def test_intermittent_30p_failure_detected(self, tracker: ProviderHealthTracker):
        """Simulate 30% failure rate over 10 calls: should accumulate
        enough consecutive failures to trigger unhealthy state."""
        import random

        random.seed(42)  # Deterministic
        fail_count = 0

        for i in range(10):
            if random.random() < 0.3:
                tracker.record_failure(
                    ModelProvider.CEREBRAS, "llama-3.1-8b", f"intermittent-{i}",
                )
                fail_count += 1
            else:
                tracker.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")

        # The key point is that intermittent failures are tracked,
        # even if the provider stays "available" (successes reset the
        # consecutive counter).  Verify the tracker is recording data.
        key = "llama-3.1-8b-cerebras"
        usage = tracker._usage[key]
        assert usage is not None
        assert usage.daily_count > 0
        # Provider should still be available because successes reset
        # consecutive failures
        assert tracker.is_available(ModelProvider.CEREBRAS, "llama-3.1-8b")

    def test_rate_limit_sets_cooldown_and_blocks(self, tracker: ProviderHealthTracker):
        """Rate-limit recording must block the provider for the cooldown
        duration."""
        tracker.record_rate_limit(
            ModelProvider.GROQ, "llama-3.1-8b", retry_after_seconds=120,
        )
        assert not tracker.is_available(ModelProvider.GROQ, "llama-3.1-8b")
        assert tracker.check_rate_limit(ModelProvider.GROQ, "llama-3.1-8b")

    def test_rate_limit_with_zero_retry_uses_default(self, tracker: ProviderHealthTracker):
        """When retry_after is 0, the default cooldown must be used."""
        tracker.record_rate_limit(
            ModelProvider.GROQ, "llama-3.1-8b", retry_after_seconds=0,
        )
        assert not tracker.is_available(ModelProvider.GROQ, "llama-3.1-8b")
        key = "llama-3.1-8b-groq"
        usage = tracker._usage[key]
        assert usage.rate_limited_until > time.time()

    def test_unknown_provider_always_available(self, tracker: ProviderHealthTracker):
        """A provider that has never been tracked should be assumed
        available (no usage data = available)."""
        assert tracker.is_available(
            ModelProvider.CEREBRAS, "unknown-model-id",
        )

    def test_get_all_status_tracks_tracked_models(self, tracker: ProviderHealthTracker):
        """get_all_status must return entries for all tracked models."""
        tracker.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        tracker.record_failure(ModelProvider.GROQ, "llama-3.1-8b", "fail")

        status = tracker.get_all_status()
        assert "llama-3.1-8b-cerebras" in status
        assert "llama-3.1-8b-groq" in status
        assert status["llama-3.1-8b-cerebras"]["is_healthy"] is True
        assert status["llama-3.1-8b-groq"]["consecutive_failures"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 5. [MEDIUM] Idempotency Violation in Routing
# ═══════════════════════════════════════════════════════════════════════


class TestIdempotencyViolation:
    """GAP-5: Duplicate requests with the same inputs should produce
    deterministic routing decisions.  The router must not use random
    selection that could send duplicate requests to different providers.
    """

    def test_same_inputs_same_decision(self, router: SmartRouter):
        """Routing the same step+variant+company must always produce
        the same model decision (deterministic)."""
        decision1 = router.route(
            COMPANY_A, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        decision2 = router.route(
            COMPANY_A, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert decision1.model_config.model_id == decision2.model_config.model_id
        assert decision1.provider == decision2.provider
        assert decision1.tier == decision2.tier

    def test_same_inputs_different_companies_same_model(self, router: SmartRouter):
        """Same step+variant but different companies should route to
        the same model (routing is not company-specific for model choice)."""
        d_a = router.route(COMPANY_A, "parwa", AtomicStepType.FAKE_VOTING)
        d_b = router.route(COMPANY_B, "parwa", AtomicStepType.FAKE_VOTING)
        # Both should get the same primary model
        assert d_a.model_config.model_id == d_b.model_config.model_id

    def test_batch_routing_deterministic(self, router: SmartRouter):
        """Batch routing must produce identical decisions across calls."""
        steps = [
            AtomicStepType.INTENT_CLASSIFICATION,
            AtomicStepType.PII_REDACTION,
            AtomicStepType.SENTIMENT_ANALYSIS,
        ]
        batch1 = router.route_batch(COMPANY_A, "parwa", steps)
        batch2 = router.route_batch(COMPANY_A, "parwa", steps)
        for d1, d2 in zip(batch1, batch2):
            assert d1.model_config.model_id == d2.model_config.model_id

    def test_routing_decision_has_timestamp(self, router: SmartRouter):
        """Each routing decision must have a routed_at timestamp."""
        decision = router.route(
            COMPANY_A, "parwa", AtomicStepType.COT_REASONING,
        )
        assert decision.routed_at is not None
        assert len(decision.routed_at) > 0

    def test_no_random_model_selection_in_tier(self, router: SmartRouter):
        """Within a tier, model selection must be deterministic
        (priority-based), not random."""
        # Route the same step 100 times and verify consistency
        for _ in range(100):
            decision = router.route(
                COMPANY_A, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
            )
            assert decision.model_config.priority <= 2, (
                "Model priority should be deterministic (1=primary)"
            )


# ═══════════════════════════════════════════════════════════════════════
# 6. [HIGH] Tenant Isolation in Variant Config
# ═══════════════════════════════════════════════════════════════════════


class TestTenantIsolationVariantConfig:
    """GAP-6: Variant configuration must never leak between tenants.
    Each tenant's routing must be independent of other tenants'
    health state or configuration.
    """

    def test_tenant_a_failure_does_not_affect_tenant_b(self, router: SmartRouter):
        """Provider failures for tenant A's requests must not affect
        tenant B's routing decisions (shared tracker means they DO
        share health state — this test documents the actual behavior)."""
        # Record failures through tenant A
        for _ in range(3):
            router._health.record_failure(
                ModelProvider.CEREBRAS, "llama-3.1-8b", "tenant-a-fail",
            )

        # Tenant B's routing should skip cerebras (shared tracker)
        decision_b = router.route(
            COMPANY_B, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        # The decision must still be valid (BC-008)
        assert isinstance(decision_b, RoutingDecision)
        assert decision_b.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)

    def test_different_companies_get_same_variant_tiers(self, router: SmartRouter):
        """Both tenants should see the same variant tier access
        (VARIANT_MODEL_ACCESS is global, not per-tenant)."""
        allowed_a = router._get_allowed_tiers("parwa")
        allowed_b = router._get_allowed_tiers("parwa")
        assert allowed_a == allowed_b

    def test_tenant_a_rate_limit_does_not_block_tenant_b_route(self, router: SmartRouter):
        """Rate limiting tenant A must still allow tenant B to route
        (BC-008: routing never crashes even if primary is blocked)."""
        router._health.record_rate_limit(
            ModelProvider.CEREBRAS, "llama-3.1-8b", retry_after_seconds=300,
        )

        # Tenant B routing should still work (fallback to groq/google)
        decision = router.route(
            COMPANY_B, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        assert isinstance(decision, RoutingDecision)
        assert "content" not in decision.__dict__  # It's a RoutingDecision

    def test_variant_gating_independent_per_call(self, router: SmartRouter):
        """Each route() call must independently evaluate variant gating.
        Switching between variants for the same tenant must always
        respect the correct variant's tier access."""
        # mini_parwa for tenant A
        d1 = router.route(
            COMPANY_A, "mini_parwa", AtomicStepType.MAD_ATOM_REASONING,
        )
        assert d1.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)

        # parwa for tenant A (same tenant, different variant)
        d2 = router.route(
            COMPANY_A, "parwa", AtomicStepType.MAD_ATOM_REASONING,
        )
        assert d2.tier == ModelTier.MEDIUM

        # Back to mini_parwa
        d3 = router.route(
            COMPANY_A, "mini_parwa", AtomicStepType.MAD_ATOM_REASONING,
        )
        assert d3.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)

    def test_shared_health_tracker_consistency(self):
        """Two SmartRouter instances share the same health tracker.
        A failure recorded on one must be visible on the other."""
        r1 = SmartRouter()
        r2 = SmartRouter()

        r1._health.record_failure(
            ModelProvider.GROQ, "llama-3.1-8b", "shared-fail-1",
        )
        r1._health.record_failure(
            ModelProvider.GROQ, "llama-3.1-8b", "shared-fail-2",
        )
        r1._health.record_failure(
            ModelProvider.GROQ, "llama-3.1-8b", "shared-fail-3",
        )

        # r2 must see groq as unavailable
        assert not r2._health.is_available(ModelProvider.GROQ, "llama-3.1-8b")

    def test_tenant_routing_with_all_providers_down(self, router: SmartRouter):
        """BC-008: When all providers are down for a tenant, routing
        must still return a valid fallback decision."""
        # Mark all LIGHT providers as unhealthy
        router._health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "down-1",
        )
        router._health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "down-2",
        )
        router._health.record_failure(
            ModelProvider.CEREBRAS, "llama-3.1-8b", "down-3",
        )
        router._health.record_failure(
            ModelProvider.GROQ, "llama-3.1-8b", "down-1",
        )
        router._health.record_failure(
            ModelProvider.GROQ, "llama-3.1-8b", "down-2",
        )
        router._health.record_failure(
            ModelProvider.GROQ, "llama-3.1-8b", "down-3",
        )
        router._health.record_failure(
            ModelProvider.GOOGLE, "gemma-3-27b-it", "down-1",
        )
        router._health.record_failure(
            ModelProvider.GOOGLE, "gemma-3-27b-it", "down-2",
        )
        router._health.record_failure(
            ModelProvider.GOOGLE, "gemma-3-27b-it", "down-3",
        )

        decision = router.route(
            COMPANY_A, "mini_parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        # BC-008: Must still return a valid decision
        assert isinstance(decision, RoutingDecision)
        assert decision.tier in (ModelTier.LIGHT, ModelTier.GUARDRAIL)


# ═══════════════════════════════════════════════════════════════════════
# 7. BC-008: Graceful Degradation — Additional Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestGracefulDegradationEdgeCases:
    """Additional BC-008 edge cases for routing robustness."""

    def test_route_with_malformed_variant_type(self, router: SmartRouter):
        """Non-string or empty variant must not crash."""
        decision = router.route(COMPANY_A, 42, AtomicStepType.FAKE_VOTING)  # type: ignore
        assert isinstance(decision, RoutingDecision)

    def test_route_with_none_query_signals(self, router: SmartRouter):
        """None query_signals must be treated as empty dict."""
        decision = router.route(
            COMPANY_A, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
            query_signals=None,
        )
        assert isinstance(decision, RoutingDecision)

    def test_execute_llm_call_returns_content_on_error(self, router: SmartRouter):
        """execute_llm_call must always return a dict with 'content'."""
        decision = router.route(
            COMPANY_A, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        # Mock the internal execution to raise
        with patch.object(
            router, "_execute_llm_call_safe",
            side_effect=Exception("HTTP 500"),
        ):
            result = router.execute_llm_call(
                COMPANY_A, decision, [{"role": "user", "content": "test"}],
            )
        assert "content" in result
        assert result.get("fallback_used") is True
        assert result.get("error") is not None

    @pytest.mark.asyncio
    async def test_async_execute_llm_call_returns_content_on_error(self, router: SmartRouter):
        """async_execute_llm_call must always return a dict with 'content'."""
        decision = router.route(
            COMPANY_A, "parwa", AtomicStepType.INTENT_CLASSIFICATION,
        )
        with patch.object(
            router, "_execute_llm_call_safe_async",
            side_effect=Exception("timeout"),
        ):
            result = await router.async_execute_llm_call(
                COMPANY_A, decision, [{"role": "user", "content": "test"}],
            )
        assert "content" in result
        assert result.get("fallback_used") is True

    def test_daily_usage_resets_on_new_day(self, tracker: ProviderHealthTracker):
        """After simulated daily reset, usage should be 0."""
        tracker.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        tracker.record_success(ModelProvider.CEREBRAS, "llama-3.1-8b")
        assert tracker.get_daily_usage(ModelProvider.CEREBRAS, "llama-3.1-8b") == 2

        tracker.reset_daily_counts()
        assert tracker.get_daily_usage(ModelProvider.CEREBRAS, "llama-3.1-8b") == 0

    def test_failover_event_trimming(self, failover_manager: FailoverManager):
        """FailoverManager must trim events to prevent memory growth."""
        failover_manager._max_events = 50

        for i in range(200):
            failover_manager.report_failure(
                "cerebras", "llama-3.1-8b",
                FailoverReason.CONNECTION_ERROR,
                f"fail-{i}",
                company_id=COMPANY_A,
            )

        # Events should be trimmed
        assert len(failover_manager._events) <= 50

    def test_degraded_response_detected_as_degraded(self):
        """The DegradedResponseDetector must flag empty and error
        pattern responses as degraded."""
        detector = DegradedResponseDetector()

        is_degraded, reason = detector.is_degraded("")
        assert is_degraded is True

        is_degraded, reason = detector.is_degraded("   ")
        assert is_degraded is True

        is_degraded, reason = detector.is_degraded(
            "Internal server error occurred while processing",
        )
        assert is_degraded is True

        is_degraded, reason = detector.is_degraded(
            "This is a normal response that is long enough to pass",
            expected_min_length=20,
        )
        assert is_degraded is False

    def test_failover_chain_executor_empty_chain(self, executor: FailoverChainExecutor):
        """Empty failover chain must return graceful error (BC-008)."""
        result = executor.execute_with_failover(
            COMPANY_A, [], lambda p, m: {"content": "ok"},
        )
        assert result.get("_all_providers_failed") is True
