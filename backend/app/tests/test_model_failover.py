"""Tests for Model Failover (F-055) – Day 2 AI Engine.

Covers:
- Circuit breaker state transitions
- Circuit recovery after timeout
- Failover chain skips unhealthy providers
- Degraded response detection
- FAILOVER_CHAINS use correct model IDs
- GUARDRAIL chain exists
- Events list trimming
"""

from __future__ import annotations

import time

import pytest
from app.core.model_failover import (
    FAILOVER_CHAINS,
    DegradedResponseDetector,
    FailoverChainExecutor,
    FailoverManager,
    FailoverReason,
    ProviderState,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def manager() -> FailoverManager:
    return FailoverManager(recovery_threshold=3, recovery_timeout_seconds=1.0)


@pytest.fixture
def detector() -> DegradedResponseDetector:
    return DegradedResponseDetector()


@pytest.fixture
def executor(manager: FailoverManager) -> FailoverChainExecutor:
    return FailoverChainExecutor(manager)


COMPANY_ID = "test-company-456"


# ── 1. Circuit breaker state transitions ─────────────────────────


class TestCircuitBreaker:
    def test_starts_healthy(self, manager: FailoverManager):
        state = manager.get_provider_state("cerebras", "llama-3.1-8b")
        assert state == ProviderState.HEALTHY

    def test_single_failure_degrades(self, manager: FailoverManager):
        manager.report_failure(
            "cerebras", "llama-3.1-8b", FailoverReason.TIMEOUT, "timeout"
        )
        state = manager.get_provider_state("cerebras", "llama-3.1-8b")
        assert state == ProviderState.DEGRADED

    def test_threshold_opens_circuit(self, manager: FailoverManager):
        for i in range(3):
            manager.report_failure(
                "cerebras", "llama-3.1-8b", FailoverReason.TIMEOUT, f"fail-{i}"
            )
        state = manager.get_provider_state("cerebras", "llama-3.1-8b")
        assert state == ProviderState.CIRCUIT_OPEN

    def test_success_resets_degraded(self, manager: FailoverManager):
        manager.report_failure(
            "cerebras", "llama-3.1-8b", FailoverReason.TIMEOUT, "fail"
        )
        manager.report_success("cerebras", "llama-3.1-8b", latency_ms=100, response={})
        state = manager.get_provider_state("cerebras", "llama-3.1-8b")
        assert state == ProviderState.HEALTHY

    def test_is_available_checks_state(self, manager: FailoverManager):
        assert manager.is_available("cerebras", "llama-3.1-8b") is True
        for _ in range(3):
            manager.report_failure(
                "cerebras", "llama-3.1-8b", FailoverReason.TIMEOUT, "fail"
            )
        assert manager.is_available("cerebras", "llama-3.1-8b") is False


# ── 2. Circuit recovery ──────────────────────────────────────────


class TestCircuitRecovery:
    def test_recovers_after_timeout(self):
        mgr = FailoverManager(recovery_threshold=2, recovery_timeout_seconds=0.1)
        mgr.report_failure("groq", "llama-3.1-8b", FailoverReason.SERVER_ERROR, "fail1")
        mgr.report_failure("groq", "llama-3.1-8b", FailoverReason.SERVER_ERROR, "fail2")
        assert (
            mgr.get_provider_state("groq", "llama-3.1-8b") == ProviderState.CIRCUIT_OPEN
        )
        time.sleep(0.15)
        assert mgr.get_provider_state("groq", "llama-3.1-8b") == ProviderState.HEALTHY


# ── 3. Failover chain ────────────────────────────────────────────


class TestGetFailoverChain:
    def test_returns_available_providers(self, manager: FailoverManager):
        chain = manager.get_failover_chain("light")
        assert len(chain) > 0
        for provider, model_id in chain:
            assert isinstance(provider, str)
            assert isinstance(model_id, str)

    def test_skips_circuit_open(self, manager: FailoverManager):
        for _ in range(3):
            manager.report_failure(
                "cerebras", "llama-3.1-8b", FailoverReason.TIMEOUT, "fail"
            )
        chain = manager.get_failover_chain("light")
        for provider, model_id in chain:
            assert not (provider == "cerebras" and model_id == "llama-3.1-8b")


# ── 4. Degraded response detection ───────────────────────────────


class TestDegradedResponseDetector:
    def test_empty_response(self, detector: DegradedResponseDetector):
        is_bad, reason = detector.is_degraded("")
        assert is_bad is True
        assert "empty" in reason

    def test_too_short(self, detector: DegradedResponseDetector):
        is_bad, reason = detector.is_degraded("Hi", expected_min_length=50)
        assert is_bad is True
        assert "too_short" in reason

    def test_error_pattern(self, detector: DegradedResponseDetector):
        is_bad, _ = detector.is_degraded(
            "Internal server error occurred while processing"
        )
        assert is_bad is True

    def test_refusal_pattern(self, detector: DegradedResponseDetector):
        is_bad, _ = detector.is_degraded("I cannot answer this question as I am an AI")
        assert is_bad is True

    def test_repetitive_text(self, detector: DegradedResponseDetector):
        is_bad, _ = detector.is_degraded(
            "Hello world. Hello world. Hello world. " * 5, expected_min_length=20
        )
        assert is_bad is True

    def test_gibberish(self, detector: DegradedResponseDetector):
        is_bad, _ = detector.is_degraded(
            "zzzzxxxcccbbbvvvnnnmmm" * 10, expected_min_length=20
        )
        assert is_bad is True

    def test_good_response(self, detector: DegradedResponseDetector):
        text = "This is a perfectly fine response with enough length and meaningful content."
        is_bad, _ = detector.is_degraded(text, expected_min_length=20)
        assert is_bad is False

    def test_quality_score(self, detector: DegradedResponseDetector):
        is_good, score, reason = detector.check_response_quality(
            {"content": "Good response here"}
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ── 5. Failover chains use correct model IDs ─────────────────────


class TestFailoverChains:
    def test_light_chain_uses_correct_models(self):
        light = FAILOVER_CHAINS.get("light", [])
        assert len(light) > 0
        # Should use llama-3.1-8b or gemma-3-27b-it (matching SmartRouter
        # registry)
        model_ids = [m for _, m in light]
        assert "llama-3.1-8b" in model_ids

    def test_medium_chain_has_gemini_flash_lite(self):
        medium = FAILOVER_CHAINS.get("medium", [])
        model_ids = [m for _, m in medium]
        assert "gemini-3.1-flash-lite" in model_ids

    def test_heavy_chain_has_gpt_oss(self):
        heavy = FAILOVER_CHAINS.get("heavy", [])
        model_ids = [m for _, m in heavy]
        assert "gpt-oss-120b" in model_ids

    def test_guardrail_chain_exists(self):
        assert "guardrail" in FAILOVER_CHAINS
        guardrail = FAILOVER_CHAINS["guardrail"]
        assert len(guardrail) > 0


# ── 6. Events trimming ───────────────────────────────────────────


class TestEventsTrimming:
    def test_manager_has_max_events(self, manager: FailoverManager):
        assert hasattr(manager, "_max_events")
        assert manager._max_events > 0

    def test_events_dont_exceed_max(self, manager: FailoverManager):
        manager._max_events = 100
        for i in range(200):
            manager.report_failure(
                "groq", "llama-3.1-8b", FailoverReason.TIMEOUT, f"fail-{i}"
            )
        assert len(manager._events) <= 100
