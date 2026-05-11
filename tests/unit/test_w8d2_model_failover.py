"""
Tests for Model Failover System (F-055).

Covers:
- Circuit Breaker lifecycle (healthy → degraded → open → recovery → closed)
- FailoverManager reporting and chain selection
- DegradedResponseDetector quality checks
- FailoverChainExecutor end-to-end failover
- Edge cases (empty chain, all circuits open, company_id validation)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.app.core.model_failover import (
    CircuitBreaker,
    DegradedResponseDetector,
    FailoverChainExecutor,
    FailoverEvent,
    FailoverManager,
    FailoverReason,
    FAILOVER_CHAINS,
    ProviderState,
)


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def manager():
    """Fresh FailoverManager with default chains."""
    return FailoverManager(
        recovery_threshold=3,
        recovery_timeout_seconds=1.0,  # 1s for fast test recovery
    )


@pytest.fixture
def detector():
    """Fresh DegradedResponseDetector."""
    return DegradedResponseDetector()


@pytest.fixture
def executor(manager):
    """FailoverChainExecutor wired to a fresh manager."""
    return FailoverChainExecutor(manager)


@pytest.fixture
def fast_recovery_manager():
    """Manager with very fast recovery for timeout-based tests."""
    return FailoverManager(
        recovery_threshold=3,
        recovery_timeout_seconds=0.1,
    )


# ── Circuit Breaker Tests ──────────────────────────────────────────


class TestCircuitBreaker:
    """Circuit breaker state transitions."""

    def test_starts_healthy(self):
        cb = CircuitBreaker(provider="google", model_id="gemini-2.0-flash")
        assert cb.state == ProviderState.HEALTHY
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_three_consecutive_failures_opens_circuit(self, manager):
        """3 consecutive failures → circuit opens (unhealthy)."""
        for i in range(3):
            manager.report_failure(
                provider="google",
                model_id="gemini-2.0-flash",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Error #{i+1}",
            )

        state = manager.get_provider_state("google", "gemini-2.0-flash")
        assert state == ProviderState.CIRCUIT_OPEN

    def test_circuit_opens_after_threshold(self, manager):
        """Circuit only opens when failure_count >= recovery_threshold."""
        manager.report_failure(
            provider="cerebras",
            model_id="llama3.3-70b",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout",
        )
        assert manager.get_provider_state("cerebras", "llama3.3-70b") == ProviderState.DEGRADED

        manager.report_failure(
            provider="cerebras",
            model_id="llama3.3-70b",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout 2",
        )
        assert manager.get_provider_state("cerebras", "llama3.3-70b") == ProviderState.DEGRADED

        manager.report_failure(
            provider="cerebras",
            model_id="llama3.3-70b",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout 3",
        )
        assert manager.get_provider_state("cerebras", "llama3.3-70b") == ProviderState.CIRCUIT_OPEN

    def test_recovery_timeout_transitions_to_healthy(self, fast_recovery_manager):
        """After recovery_timeout → circuit transitions from open → healthy."""
        # Open the circuit
        for i in range(3):
            fast_recovery_manager.report_failure(
                provider="google",
                model_id="gemini-2.0-flash",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Error #{i+1}",
            )
        assert fast_recovery_manager.get_provider_state("google", "gemini-2.0-flash") == ProviderState.CIRCUIT_OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Check recovery
        fast_recovery_manager._check_recovery("google", "gemini-2.0-flash")
        state = fast_recovery_manager.get_provider_state("google", "gemini-2.0-flash")
        assert state == ProviderState.HEALTHY

    def test_success_in_half_open_closes_circuit(self, manager):
        """Success after recovery closes the circuit."""
        # Open the circuit
        for i in range(3):
            manager.report_failure(
                provider="groq",
                model_id="llama-3.3-70b-versatile",
                reason=FailoverReason.RATE_LIMIT,
                error_msg=f"Rate limit #{i+1}",
            )
        assert manager.get_provider_state("groq", "llama-3.3-70b-versatile") == ProviderState.CIRCUIT_OPEN

        # Manually set to healthy to simulate recovery timeout
        manager.reset_circuit("groq", "llama-3.3-70b-versatile")
        assert manager.get_provider_state("groq", "llama-3.3-70b-versatile") == ProviderState.HEALTHY

        # Report a failure to go degraded
        manager.report_failure(
            provider="groq",
            model_id="llama-3.3-70b-versatile",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout",
        )
        assert manager.get_provider_state("groq", "llama-3.3-70b-versatile") == ProviderState.DEGRADED

        # Success should close it
        manager.report_success(
            provider="groq",
            model_id="llama-3.3-70b-versatile",
            latency_ms=100,
            response={"content": "Good response"},
        )
        assert manager.get_provider_state("groq", "llama-3.3-70b-versatile") == ProviderState.HEALTHY

    def test_failure_in_half_open_reopens_circuit(self, manager):
        """Failure after recovery reopens the circuit."""
        # Open the circuit
        for i in range(3):
            manager.report_failure(
                provider="google",
                model_id="gemini-2.0-flash",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Error #{i+1}",
            )

        # Reset to healthy (simulating recovery timeout)
        manager.reset_circuit("google", "gemini-2.0-flash")

        # Fail again enough times to re-open
        for i in range(3):
            manager.report_failure(
                provider="google",
                model_id="gemini-2.0-flash",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Re-fail #{i+1}",
            )
        assert manager.get_provider_state("google", "gemini-2.0-flash") == ProviderState.CIRCUIT_OPEN

    def test_manual_reset_works(self, manager):
        """Manual reset restores circuit to healthy."""
        # Open the circuit
        for i in range(3):
            manager.report_failure(
                provider="cerebras",
                model_id="llama3.3-70b",
                reason=FailoverReason.CONNECTION_ERROR,
                error_msg="Connection refused",
            )
        assert manager.get_provider_state("cerebras", "llama3.3-70b") == ProviderState.CIRCUIT_OPEN

        # Manual reset
        result = manager.reset_circuit("cerebras", "llama3.3-70b")
        assert result is True
        assert manager.get_provider_state("cerebras", "llama3.3-70b") == ProviderState.HEALTHY

        # Verify failure count is reset
        circuit = manager._get_circuit("cerebras", "llama3.3-70b")
        assert circuit.failure_count == 0
        assert circuit.success_count == 0


# ── FailoverManager Tests ──────────────────────────────────────────


class TestFailoverManager:
    """FailoverManager reporting and chain logic."""

    def test_report_success_resets_failure_count(self, manager):
        """report_success resets the failure counter."""
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout",
        )
        circuit = manager._get_circuit("google", "gemini-2.0-flash")
        assert circuit.failure_count == 1

        manager.report_success(
            provider="google",
            model_id="gemini-2.0-flash",
            latency_ms=50,
            response={"content": "OK"},
        )
        # After success on a degraded circuit, state should go to healthy
        assert circuit.state == ProviderState.HEALTHY

    def test_report_failure_increments_count(self, manager):
        """report_failure increments the failure counter."""
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.RATE_LIMIT,
            error_msg="Rate limited",
        )
        circuit = manager._get_circuit("google", "gemini-2.0-flash")
        assert circuit.failure_count == 1
        assert circuit.total_failures == 1

        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timed out",
        )
        assert circuit.failure_count == 2
        assert circuit.total_failures == 2

    def test_get_failover_chain_returns_correct_order(self, manager):
        """get_failover_chain returns providers in correct order per tier."""
        chain = manager.get_failover_chain("light")
        assert len(chain) == 3
        assert chain[0][0] == "google"
        assert chain[1][0] == "cerebras"
        assert chain[2][0] == "groq"

        chain = manager.get_failover_chain("medium")
        assert len(chain) == 3

        chain = manager.get_failover_chain("heavy")
        assert len(chain) == 3

    def test_get_failover_chain_skips_unhealthy(self, manager):
        """get_failover_chain skips providers with open circuits."""
        # Open google circuit
        for i in range(3):
            manager.report_failure(
                provider="google",
                model_id="gemini-2.0-flash",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Error #{i+1}",
            )

        chain = manager.get_failover_chain("light")
        assert len(chain) == 2
        providers = [c[0] for c in chain]
        assert "google" not in providers
        assert "cerebras" in providers
        assert "groq" in providers

    def test_is_available_returns_correct_state(self, manager):
        """is_available correctly reflects circuit state."""
        assert manager.is_available("google", "gemini-2.0-flash") is True

        # 1 failure → degraded, still available
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout",
        )
        assert manager.is_available("google", "gemini-2.0-flash") is True

        # 3 failures → circuit open, not available
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout 2",
        )
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout 3",
        )
        assert manager.is_available("google", "gemini-2.0-flash") is False

    def test_get_all_circuit_states(self, manager):
        """get_all_circuit_states returns overview of all circuits."""
        states = manager.get_all_circuit_states()
        assert "google:gemini-2.0-flash" in states
        assert "cerebras:llama3.3-70b" in states
        assert "groq:llama-3.3-70b-versatile" in states

        for key, info in states.items():
            assert "state" in info
            assert "failure_count" in info
            assert "total_failures" in info
            assert "total_successes" in info

    def test_get_failover_stats(self, manager):
        """get_failover_stats returns company-specific stats."""
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.RATE_LIMIT,
            error_msg="Rate limited",
            company_id="comp_123",
        )
        manager.report_failure(
            provider="cerebras",
            model_id="llama3.3-70b",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout",
            company_id="comp_123",
        )
        # Different company
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.SERVER_ERROR,
            error_msg="500",
            company_id="comp_456",
        )

        stats = manager.get_failover_stats("comp_123", hours=24)
        assert stats["company_id"] == "comp_123"
        assert stats["total_failovers"] == 2
        assert "google" in stats["provider_stats"]
        assert "cerebras" in stats["provider_stats"]
        assert "comp_456" not in stats["provider_stats"]  # different company

    def test_unknown_tier_returns_empty_chain(self, manager):
        """Unknown tier returns empty chain."""
        chain = manager.get_failover_chain("nonexistent_tier")
        assert chain == []


# ── DegradedResponseDetector Tests ─────────────────────────────────


class TestDegradedResponseDetector:
    """Degraded response detection logic."""

    def test_empty_response_degraded(self, detector):
        assert detector.is_degraded("") == (True, "empty_response")
        assert detector.is_degraded("   ") == (True, "empty_response")
        assert detector.is_degraded(None) == (True, "empty_response")

    def test_very_short_response_degraded(self, detector):
        assert detector.is_degraded("Hi") == (True, "too_short (2 < 50 chars)")
        assert detector.is_degraded("OK") == (True, "too_short (2 < 50 chars)")

    def test_response_containing_error_text_degraded(self, detector):
        long_error = "We're sorry, but an internal server error occurred while processing your request. Please try again later."
        is_deg, reason = detector.is_degraded(long_error)
        assert is_deg is True
        assert "error_pattern" in reason

        rate_limit_text = "Rate limit exceeded for this API endpoint. Too many requests. Please wait and retry your request shortly."
        is_deg, reason = detector.is_degraded(rate_limit_text)
        assert is_deg is True
        assert "error_pattern" in reason

        error_500 = "The server returned a 500 error when trying to process this query. Something went wrong with the backend."
        is_deg, reason = detector.is_degraded(error_500)
        assert is_deg is True
        assert "error_pattern" in reason

    def test_refusal_patterns_degraded(self, detector):
        refusal = "I'm unable to provide you with the information you're looking for at this time. Please contact support for further assistance."
        is_deg, reason = detector.is_degraded(refusal)
        assert is_deg is True
        assert "refusal_pattern" in reason

    def test_repetitive_text_degraded(self, detector):
        # Create text with a repeating pattern
        phrase = "Please try again later. "
        repetitive = phrase * 8 + "Please try again later."
        is_deg, reason = detector.is_degraded(repetitive)
        assert is_deg is True
        assert reason == "repetitive_text"

    def test_gibberish_text_degraded(self, detector):
        # Non-word-like characters with low vowel ratio
        gibberish = "xkq zwm fjb pnt vlc rgn hsy bdf qwt jnm xkq zwm fjb pnt vlc rgn hsy bdf qwt jnm xkq zwm fjb pnt"
        is_deg, reason = detector.is_degraded(gibberish)
        assert is_deg is True
        assert "gibberish" in reason

    def test_normal_response_not_degraded(self, detector):
        normal = (
            "Thank you for reaching out! I'd be happy to help you with your "
            "billing question. Based on your account, I can see that your "
            "subscription was renewed on March 1st for $29.99. The charge "
            "appears on your invoice #INV-2024-0042. Is there anything else "
            "you'd like to know about this transaction?"
        )
        is_deg, reason = detector.is_degraded(normal)
        assert is_deg is False
        assert reason == "ok"

    def test_check_response_quality_good_response(self, detector):
        response = {
            "content": (
                "Based on your account history, I can confirm that your "
                "refund request has been processed successfully. The amount "
                "of $49.99 will be credited back to your original payment "
                "method within 5-7 business days."
            )
        }
        is_good, score, reason = detector.check_response_quality(response)
        assert is_good is True
        assert score >= 0.5
        assert reason == "ok"

    def test_check_response_quality_empty(self, detector):
        is_good, score, reason = detector.check_response_quality({"content": ""})
        assert is_good is False
        assert score == 0.0
        assert reason == "empty_response"

    def test_check_response_quality_short(self, detector):
        is_good, score, reason = detector.check_response_quality({"content": "Yes"})
        assert is_good is False
        assert score < 1.0
        assert "short" in reason

    def test_check_response_quality_error_text(self, detector):
        error_resp = {
            "content": "An internal server error occurred while processing. Service unavailable. Please try again later."
        }
        is_good, score, reason = detector.check_response_quality(error_resp)
        assert is_good is False
        assert score < 0.5
        assert "error_pattern" in reason

    def test_check_response_quality_dict_content(self, detector):
        """Handle response where 'content' is a dict."""
        response = {
            "content": {
                "content": (
                    "I'll help you resolve this issue right away. "
                    "Based on your ticket, the problem is with the API "
                    "configuration. Let me walk you through the fix step by step."
                )
            }
        }
        is_good, score, reason = detector.check_response_quality(response)
        assert is_good is True
        assert score >= 0.5


# ── FailoverChainExecutor Tests ────────────────────────────────────


class TestFailoverChainExecutor:
    """End-to-end failover chain execution."""

    def test_primary_succeeds_returns_immediately(self, executor, manager):
        """If primary provider succeeds, return immediately."""
        call_fn = MagicMock(
            return_value={"content": "Great response! I can help you with your billing inquiry right away.", "latency_ms": 50}
        )

        chain = [("google", "gemini-2.0-flash"), ("cerebras", "llama3.3-70b")]
        result = executor.execute_with_failover("comp_123", chain, call_fn)

        assert result["content"] == "Great response! I can help you with your billing inquiry right away."
        call_fn.assert_called_once_with("google", "gemini-2.0-flash")

    def test_primary_fails_backup_succeeds(self, executor, manager):
        """Primary fails, backup succeeds → returns backup result."""
        call_count = {"n": 0}

        def call_fn(provider, model_id):
            call_count["n"] += 1
            if provider == "google":
                raise ConnectionError("Connection refused")
            return {"content": "Backup response!", "latency_ms": 100}

        chain = [("google", "gemini-2.0-flash"), ("cerebras", "llama3.3-70b")]
        result = executor.execute_with_failover("comp_123", chain, call_fn, max_retries=1)

        assert result["content"] == "Backup response!"
        assert result["_failover_used"] is True
        assert call_count["n"] >= 2  # google retried + cerebras success

    def test_all_fail_returns_graceful_error(self, executor, manager):
        """ALL providers fail → returns graceful error response (BC-008)."""

        def call_fn(provider, model_id):
            raise TimeoutError("Request timed out")

        chain = [("google", "gemini-2.0-flash"), ("cerebras", "llama3.3-70b")]
        result = executor.execute_with_failover("comp_123", chain, call_fn, max_retries=1)

        assert result.get("_all_providers_failed") is True
        assert result.get("_graceful_degradation") is True
        assert "content" in result
        assert len(result["content"]) > 0  # never empty
        assert result.get("_error_code") == "F055_ALL_PROVIDERS_FAILED"

    def test_reports_failures_to_manager(self, executor, manager):
        """Failures are reported to the FailoverManager."""
        def call_fn(provider, model_id):
            raise ConnectionError("Refused")

        chain = [("google", "gemini-2.0-flash")]
        executor.execute_with_failover("comp_123", chain, call_fn, max_retries=1)

        circuit = manager._get_circuit("google", "gemini-2.0-flash")
        assert circuit.failure_count >= 1
        assert circuit.total_failures >= 1

    def test_reports_successes_to_manager(self, executor, manager):
        """Successes are reported to the FailoverManager."""
        call_fn = MagicMock(
            return_value={"content": "Success!", "latency_ms": 75}
        )

        chain = [("google", "gemini-2.0-flash")]
        executor.execute_with_failover("comp_123", chain, call_fn)

        circuit = manager._get_circuit("google", "gemini-2.0-flash")
        assert circuit.total_successes >= 1
        assert circuit.last_success_at is not None

    def test_degraded_response_triggers_failover(self, executor, manager):
        """Degraded response from primary triggers failover to backup."""

        def call_fn(provider, model_id):
            if provider == "google":
                return {"content": "Error: internal server error occurred", "latency_ms": 30}
            return {"content": "Good response from backup!", "latency_ms": 50}

        chain = [("google", "gemini-2.0-flash"), ("cerebras", "llama3.3-70b")]
        result = executor.execute_with_failover("comp_123", chain, call_fn, max_retries=1)

        assert result["content"] == "Good response from backup!"
        assert result["_failover_used"] is True

    def test_degraded_last_provider_returns_anyway(self, executor, manager):
        """If last provider returns degraded, still return it (BC-008)."""

        def call_fn(provider, model_id):
            return {"content": "internal server error 500", "latency_ms": 30}

        chain = [("google", "gemini-2.0-flash")]
        result = executor.execute_with_failover("comp_123", chain, call_fn, max_retries=1)

        # Should still return something — never crash
        assert "content" in result
        assert result.get("_degraded") is True

    def test_non_dict_result_wrapped(self, executor):
        """Non-dict result from call_fn is wrapped into a dict."""
        call_fn = MagicMock(return_value="plain string response")

        chain = [("google", "gemini-2.0-flash")]
        result = executor.execute_with_failover("comp_123", chain, call_fn)

        assert result["content"] == "plain string response"

    def test_connection_error_classification(self, executor):
        """ConnectionError is classified correctly."""
        reason, status = executor._classify_exception(
            ConnectionError("connection refused")
        )
        assert reason == FailoverReason.CONNECTION_ERROR
        assert status == 503

    def test_timeout_error_classification(self, executor):
        """TimeoutError is classified correctly."""
        reason, status = executor._classify_exception(
            TimeoutError("request timed out")
        )
        assert reason == FailoverReason.TIMEOUT
        assert status == 504

    def test_rate_limit_classification(self, executor):
        """Rate limit errors are classified correctly."""
        reason, status = executor._classify_exception(
            ConnectionError("429 rate limit too many requests")
        )
        assert reason == FailoverReason.RATE_LIMIT
        assert status == 429

    def test_auth_error_classification(self, executor):
        """Auth errors are classified correctly."""
        reason, status = executor._classify_exception(
            OSError("401 unauthorized auth failed")
        )
        assert reason == FailoverReason.AUTH_ERROR
        assert status == 403


# ── Edge Case Tests ────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_chain_returns_graceful_error(self, executor):
        """Empty chain → graceful error response."""
        result = executor.execute_with_failover("comp_123", [], MagicMock())
        assert result.get("_all_providers_failed") is True
        assert "content" in result

    def test_all_providers_circuit_open(self, manager):
        """All providers have open circuits → chain is empty."""
        for i in range(3):
            manager.report_failure(
                provider="google",
                model_id="gemini-2.0-flash",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Err {i}",
            )
            manager.report_failure(
                provider="cerebras",
                model_id="llama3.3-70b",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Err {i}",
            )
            manager.report_failure(
                provider="groq",
                model_id="llama-3.3-70b-versatile",
                reason=FailoverReason.SERVER_ERROR,
                error_msg=f"Err {i}",
            )

        chain = manager.get_failover_chain("light")
        assert chain == []

        executor = FailoverChainExecutor(manager)
        result = executor.execute_with_failover(
            "comp_123", chain, MagicMock(return_value="ok")
        )
        assert result.get("_all_providers_failed") is True

    def test_company_id_in_stats(self, manager):
        """company_id is properly tracked in stats (BC-001)."""
        manager.report_failure(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.TIMEOUT,
            error_msg="Timeout",
            company_id="tenant_abc",
        )
        stats = manager.get_failover_stats("tenant_abc")
        assert stats["company_id"] == "tenant_abc"
        assert stats["total_failovers"] == 1

        # Different company has no stats
        stats_other = manager.get_failover_stats("tenant_xyz")
        assert stats_other["total_failovers"] == 0

    def test_failover_event_fields(self, manager):
        """FailoverEvent has all expected fields."""
        event = FailoverEvent(
            provider="google",
            model_id="gemini-2.0-flash",
            reason=FailoverReason.RATE_LIMIT,
            error_message="Rate limited",
            timestamp=datetime.now(timezone.utc).isoformat(),
            latency_ms=100,
            http_status_code=429,
            response_snippet="Too many requests",
        )
        assert event.provider == "google"
        assert event.model_id == "gemini-2.0-flash"
        assert event.reason == FailoverReason.RATE_LIMIT
        assert event.latency_ms == 100
        assert event.http_status_code == 429

    def test_repeated_failures_accumulate(self, manager):
        """Multiple failures accumulate in total counts."""
        for i in range(5):
            manager.report_failure(
                provider="google",
                model_id="gemini-2.0-flash",
                reason=FailoverReason.TIMEOUT,
                error_msg=f"Timeout #{i}",
            )
        circuit = manager._get_circuit("google", "gemini-2.0-flash")
        assert circuit.total_failures == 5
        assert circuit.failure_count == 5

    def test_get_failover_stats_no_events(self, manager):
        """Stats for company with no events returns zeros."""
        stats = manager.get_failover_stats("nonexistent_company")
        assert stats["total_failovers"] == 0
        assert stats["provider_stats"] == {}

    def test_unknown_exception_wrapped_as_connection_error(self, executor, manager):
        """Non-standard exceptions are wrapped for uniform handling."""
        def call_fn(provider, model_id):
            raise ValueError("Something unexpected happened")

        chain = [("google", "gemini-2.0-flash")]
        # Should not raise — should fall through to graceful error
        result = executor.execute_with_failover("comp_123", chain, call_fn, max_retries=1)
        assert result.get("_all_providers_failed") is True

    def test_single_provider_chain_success(self, executor):
        """Single-provider chain works when provider succeeds."""
        call_fn = MagicMock(return_value={"content": "Solo response from the only available provider in the chain.", "latency_ms": 30})
        result = executor.execute_with_failover(
            "comp_123", [("google", "gemini-2.0-flash")], call_fn
        )
        assert result["content"] == "Solo response from the only available provider in the chain."
        assert result.get("_failover_used") is False

    def test_graceful_error_never_empty(self, executor):
        """Graceful error always has non-empty content (BC-008)."""
        result = executor._build_error_response([])
        assert "content" in result
        assert len(result["content"].strip()) > 0
        assert "text" in result
        assert len(result["text"].strip()) > 0
