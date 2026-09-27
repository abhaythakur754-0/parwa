"""
Unit tests for Node 6.5 — Deliver (BC-015) — PRODUCTION

Tests cover:
  1. Channel-of-origin preference: reply on the same channel the ticket came in on
  2. SMS length fallback: response > limit → upgrade to email
  3. Provider failure fallback: dispatch returns error → fallback to next channel
  4. Missing channel_type → default to email (safest channel)
  5. Empty/missing final_response → skip dispatch, log error
  6. Already-delivered state (idempotency): don't re-dispatch
  7. Multi-tenant: passes tenant_id correctly to dispatcher
  8. Technique log: every decision is logged with node=6.5
  9. Non-blocking: any error in dispatcher is caught, pipeline still ends

PRODUCTION HARDENING TESTS (v2):
  10. Retry within a channel: dispatch called multiple times before fallback
  11. Circuit breaker: opens after N failures, fast-fails subsequent attempts
  12. Circuit breaker: closes on success (probe through half-open)
  13. DLQ persistence: all channels failed → entry persisted to DLQ
  14. Audit log: every attempt writes an audit row (best-effort)
  15. Metrics: counters incremented for every attempt + fallback + CB + DLQ
  16. Config-driven: thresholds read from settings, not hard-coded
  17. delivery_message_id stored from dispatcher result
  18. delivery_retry_count tracks total retries across channels
  19. delivery_circuit_open flag set when breaker trips
  20. delivery_dlq_entry_id set when all channels fail
  21. delivery_attempts counts ACTUAL attempts (bug fix from v1)
  22. DB session closed after each per-channel attempt
  23. State preservation: input state never mutated, token usage unchanged
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


def _make_state(
    channel_type: str = "email",
    final_response: str = "Here is your answer.",
    ticket_id: str = "ticket-123",
    tenant_id: str = "company-abc",
    variant_tier_short: str = "parwa",
) -> Dict[str, Any]:
    """Build a minimal pipeline state for Node 6.5 testing."""
    return {
        "ticket_id": ticket_id,
        "tenant_id": tenant_id,
        "channel_type": channel_type,
        "final_response": final_response,
        "formatted_response": final_response,
        "variant_tier_short": variant_tier_short,
        "variant_tier": "parwa",
        "status": "resolved",
        "technique_log": [],
        "total_token_usage": 5,
    }


def _mock_db_session():
    """Mock DB session so we can verify it's closed after each attempt."""
    session = MagicMock()
    session.close = MagicMock()
    return session


def _mock_dispatcher_success(channel: str = "email", message_id: str = "msg-abc"):
    """Mock ChannelDispatcher whose .dispatch() always succeeds."""
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = {
        "status": "dispatched",
        "channel": channel,
        "ticket_id": "ticket-123",
        "message_id": message_id,
    }
    return dispatcher


def _mock_dispatcher_error(error_msg: str = "Twilio timeout"):
    """Mock ChannelDispatcher whose .dispatch() raises an exception."""
    dispatcher = MagicMock()
    dispatcher.dispatch.side_effect = Exception(error_msg)
    return dispatcher


def _mock_dispatcher_status(status: str, channel: str):
    """Mock ChannelDispatcher that returns a custom status dict."""
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = {
        "status": status,
        "channel": channel,
        "ticket_id": "ticket-123",
    }
    return dispatcher


def _patch_dispatcher(*dispatchers_and_sessions):
    """Patch _get_dispatcher to return a sequence of (dispatcher, session) tuples.

    Each call to _get_dispatcher returns the next tuple. This lets us
    simulate fallback chains where each channel gets a fresh dispatcher.
    """
    tuples = [(d, _mock_db_session()) for d in dispatchers_and_sessions]
    return patch(
        "app.core.parwa_pipeline.nodes.node_6_5_deliver._get_dispatcher",
        side_effect=tuples,
    )


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Reset the global circuit breaker before each test."""
    from app.core.parwa_pipeline.delivery_circuit_breaker import (
        reset_delivery_circuit_breaker,
    )
    reset_delivery_circuit_breaker()
    yield
    reset_delivery_circuit_breaker()


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Make retries instant so tests don't wait for backoff.

    Patches the module-level _sleep alias (not the global time.sleep)
    so other tests that rely on real time (e.g. CB cooldown) still work.
    """
    from app.core.parwa_pipeline.nodes import node_6_5_deliver as mod
    monkeypatch.setattr(mod, "_sleep", lambda _: None)


# ══════════════════════════════════════════════════════════════════
# 1. CHANNEL-OF-ORIGIN PREFERENCE (BC-015 core rule)
# ══════════════════════════════════════════════════════════════════


class TestChannelOfOrigin:
    """The customer wrote in on channel X. We MUST reply on channel X
    unless a fallback rule explicitly overrides."""

    def test_email_in_email_out(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply here.")
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_status"] == "dispatched"
        assert result["delivery_message_id"] == "msg-abc"
        assert result["delivery_attempts"] == 1
        assert result["delivery_retry_count"] == 0
        assert result["delivery_circuit_open"] is False
        assert result["delivery_dlq_entry_id"] is None

    def test_sms_in_sms_out(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="Short reply.")
        with _patch_dispatcher(_mock_dispatcher_success("sms")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "sms"

    def test_chat_in_chat_out(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="chat", final_response="Chat reply.")
        with _patch_dispatcher(_mock_dispatcher_success("chat")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "chat"

    def test_voice_in_voice_out(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="voice", final_response="Voice reply.")
        with _patch_dispatcher(_mock_dispatcher_success("voice")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "voice"


# ══════════════════════════════════════════════════════════════════
# 2. SMS LENGTH FALLBACK (BC-015 channel-capacity rule)
# ══════════════════════════════════════════════════════════════════


class TestSMSLengthFallback:
    """If the response is too long for SMS, fall back to email."""

    def test_long_sms_response_upgrades_to_email(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        long_response = "x" * 2000
        state = _make_state(channel_type="sms", final_response=long_response)

        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_fallback_reason"] == "sms_length_exceeded"

    def test_short_sms_response_stays_on_sms(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="Refund processed.")
        with _patch_dispatcher(_mock_dispatcher_success("sms")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "sms"
        assert result.get("delivery_fallback_reason") is None

    def test_boundary_1600_chars_stays_on_sms(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="x" * 1600)
        with _patch_dispatcher(_mock_dispatcher_success("sms")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "sms"

    def test_1601_chars_upgrades_to_email(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="x" * 1601)
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_fallback_reason"] == "sms_length_exceeded"


# ══════════════════════════════════════════════════════════════════
# 3. PROVIDER FAILURE FALLBACK
# ══════════════════════════════════════════════════════════════════


class TestProviderFailureFallback:
    """If the chosen channel provider fails, fall back to next channel."""

    def test_sms_provider_failure_falls_back_to_email(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="Short reply.")
        with _patch_dispatcher(
            _mock_dispatcher_error("Twilio timeout"),
            _mock_dispatcher_success("email"),
        ):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_fallback_reason"] == "provider_failure:sms"

    def test_email_provider_failure_falls_back_to_internal(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(
            _mock_dispatcher_error("Brevo 503"),
            _mock_dispatcher_success("internal"),
        ):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "internal"
        assert result["delivery_fallback_reason"] == "provider_failure:email"


# ══════════════════════════════════════════════════════════════════
# 4. MISSING CHANNEL_TYPE → DEFAULT TO EMAIL
# ══════════════════════════════════════════════════════════════════


class TestMissingChannel:
    def test_missing_channel_type_defaults_to_email(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_fallback_reason"] == "missing_channel_default"

    def test_none_channel_type_defaults_to_email(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="", final_response="Reply.")
        state["channel_type"] = None
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_fallback_reason"] == "missing_channel_default"

    def test_unknown_channel_type_defaults_to_email(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="telegram", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_fallback_reason"] == "unknown_channel_default"


# ══════════════════════════════════════════════════════════════════
# 5. EMPTY RESPONSE → SKIP DISPATCH
# ══════════════════════════════════════════════════════════════════


class TestEmptyResponse:
    def test_empty_final_response_skips_dispatch(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="")
        dispatcher = _mock_dispatcher_success("email")
        with _patch_dispatcher(dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "skipped_empty_response"
        assert result["delivery_channel"] is None
        assert result["delivery_attempts"] == 0
        # Dispatcher was never called
        assert not dispatcher.dispatch.called

    def test_whitespace_only_response_skips_dispatch(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="   \n\t  ")
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "skipped_empty_response"

    def test_missing_final_response_key_skips_dispatch(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state()
        del state["final_response"]
        del state["formatted_response"]
        # simple_answer and super_node_answer never existed in _make_state
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "skipped_empty_response"


# ══════════════════════════════════════════════════════════════════
# 6. IDEMPOTENCY
# ══════════════════════════════════════════════════════════════════


class TestIdempotency:
    def test_already_delivered_skips_redispatch(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        state["delivery_status"] = "dispatched"
        state["delivery_channel"] = "email"
        dispatcher = _mock_dispatcher_success("email")
        with _patch_dispatcher(dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        # Dispatcher never called
        assert not dispatcher.dispatch.called
        assert result["delivery_status"] == "dispatched"
        assert result["delivery_channel"] == "email"


# ══════════════════════════════════════════════════════════════════
# 7. TECHNIQUE LOG
# ══════════════════════════════════════════════════════════════════


class TestTechniqueLog:
    def test_log_has_node_6_5_entry(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        logs = result["technique_log"]
        assert len(logs) >= 2  # ChannelDecision + DispatchAttempt
        assert all(log["node"] == 6.5 for log in logs)

    def test_log_records_fallback_decision(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="x" * 2000)
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        decision_log = next(
            log for log in result["technique_log"]
            if log["technique"] == "ChannelDecision"
        )
        assert "sms_length_exceeded" in decision_log["result_summary"]


# ══════════════════════════════════════════════════════════════════
# 8. MULTI-TENANT
# ══════════════════════════════════════════════════════════════════


class TestMultiTenant:
    def test_tenant_id_passed_to_dispatcher(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(
            channel_type="email", final_response="Reply.",
            tenant_id="tenant-xyz-789",
        )
        dispatcher = _mock_dispatcher_success("email")
        with _patch_dispatcher(dispatcher):
            asyncio.run(node_6_5_deliver(state))

        dispatcher.dispatch.assert_called_once()
        assert dispatcher.dispatch.call_args.kwargs["company_id"] == "tenant-xyz-789"


# ══════════════════════════════════════════════════════════════════
# 9. NON-BLOCKING
# ══════════════════════════════════════════════════════════════════


class TestNonBlocking:
    def test_dispatcher_construction_failure_does_not_crash(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._get_dispatcher",
            side_effect=Exception("DB down"),
        ), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_to_dlq",
            return_value="dlq-1",
        ):
            result = asyncio.run(node_6_5_deliver(state))

        # Pipeline completes — never crashes
        assert result["delivery_status"] == "error"
        assert result["delivery_dlq_entry_id"] == "dlq-1"

    def test_all_channels_fail_returns_error_status(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(
            _mock_dispatcher_error("email down"),
            _mock_dispatcher_error("internal down"),
        ), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_to_dlq",
            return_value="dlq-2",
        ):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "error"
        assert result["delivery_dlq_entry_id"] == "dlq-2"


# ══════════════════════════════════════════════════════════════════
# 10. STATE PRESERVATION
# ══════════════════════════════════════════════════════════════════


class TestStatePreservation:
    def test_does_not_mutate_input_state(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        original = dict(state)
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            asyncio.run(node_6_5_deliver(state))

        # Input state unchanged
        assert state == original

    def test_token_usage_preserved_and_zero_added(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["node_6_5_token_usage"] == 0
        assert result["total_token_usage"] == state["total_token_usage"]


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — 11. RETRY WITH BACKOFF
# ══════════════════════════════════════════════════════════════════


class TestRetryWithinChannel:
    """Within a single channel, the dispatcher should be retried up to
    DELIVERY_MAX_RETRIES times before falling back to the next channel."""

    def test_first_attempt_success_no_retries(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        dispatcher = _mock_dispatcher_success("email")
        with _patch_dispatcher(dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        assert dispatcher.dispatch.call_count == 1
        assert result["delivery_retry_count"] == 0

    def test_retries_on_soft_failure_then_succeeds(self):
        """Soft failure (status=error) should retry, not immediately fall back."""
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        dispatcher = MagicMock()
        # First attempt: soft fail, second: soft fail, third: success
        dispatcher.dispatch.side_effect = [
            {"status": "error", "error": "transient"},
            {"status": "error", "error": "transient"},
            {"status": "dispatched", "channel": "email", "message_id": "m1"},
        ]
        with _patch_dispatcher(dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        assert dispatcher.dispatch.call_count == 3
        assert result["delivery_status"] == "dispatched"
        assert result["delivery_retry_count"] == 2

    def test_retries_on_exception_then_succeeds(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        dispatcher = MagicMock()
        dispatcher.dispatch.side_effect = [
            Exception("connection reset"),
            {"status": "dispatched", "channel": "email", "message_id": "m1"},
        ]
        with _patch_dispatcher(dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        assert dispatcher.dispatch.call_count == 2
        assert result["delivery_retry_count"] == 1

    def test_exhausts_retries_then_falls_back_to_next_channel(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        # Email channel: 4 attempts (1 + 3 retries), all fail
        email_dispatcher = MagicMock()
        email_dispatcher.dispatch.side_effect = [
            {"status": "error", "error": "down"},
            {"status": "error", "error": "down"},
            {"status": "error", "error": "down"},
            {"status": "error", "error": "down"},
        ]
        # Internal channel: success
        internal_dispatcher = _mock_dispatcher_success("internal")
        with _patch_dispatcher(email_dispatcher, internal_dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        # 4 calls on email (1 + 3 retries), then 1 call on internal
        assert email_dispatcher.dispatch.call_count == 4
        assert internal_dispatcher.dispatch.call_count == 1
        assert result["delivery_channel"] == "internal"
        assert result["delivery_retry_count"] == 3


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — 12. CIRCUIT BREAKER
# ══════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    def test_cb_opens_after_threshold_failures(self):
        """After N consecutive failures on a channel, the breaker opens."""
        from app.core.parwa_pipeline.delivery_circuit_breaker import (
            DeliveryCircuitBreaker,
        )
        cb = DeliveryCircuitBreaker(threshold=3, reset_seconds=60)
        assert not cb.is_open("email")

        cb.record_failure("email")
        cb.record_failure("email")
        assert not cb.is_open("email")  # 2 < 3
        just_opened = cb.record_failure("email")
        assert just_opened is True
        assert cb.is_open("email")

    def test_cb_closes_on_success(self):
        from app.core.parwa_pipeline.delivery_circuit_breaker import (
            DeliveryCircuitBreaker,
        )
        cb = DeliveryCircuitBreaker(threshold=2, reset_seconds=60)
        cb.record_failure("email")
        cb.record_failure("email")
        assert cb.is_open("email")

        cb.record_success("email")
        assert not cb.is_open("email")
        assert cb.get_channel_state("email")["failures"] == 0

    def test_cb_half_opens_after_cooldown(self):
        from app.core.parwa_pipeline.delivery_circuit_breaker import (
            DeliveryCircuitBreaker,
        )
        import time as _time
        # Use small but non-zero reset_seconds so the breaker stays open
        # briefly, then half-opens after the cooldown elapses.
        cb = DeliveryCircuitBreaker(threshold=1, reset_seconds=0.1)
        cb.record_failure("email")
        # Immediately after failure, breaker is open
        assert cb.is_open("email")

        # Wait for cooldown to elapse
        _time.sleep(0.15)
        # After cooldown, breaker should half-open (allow probe)
        assert not cb.is_open("email")

    def test_cb_open_skips_dispatch_for_that_channel(self):
        """If the breaker is open for email, that channel is skipped entirely."""
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver
        from app.core.parwa_pipeline.delivery_circuit_breaker import (
            get_delivery_circuit_breaker,
        )

        # Pre-open the breaker for email by lowering threshold and recording a failure
        cb = get_delivery_circuit_breaker()
        cb._threshold = 1
        cb._reset_seconds = 300  # long cooldown so it stays open during test
        cb.record_failure("email")
        assert cb.is_open("email")

        state = _make_state(channel_type="email", final_response="Reply.")
        email_dispatcher = _mock_dispatcher_success("email")  # would succeed but CB skips
        internal_dispatcher = _mock_dispatcher_success("internal")  # fallback succeeds
        with _patch_dispatcher(email_dispatcher, internal_dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        # Email dispatcher never called because CB is open
        assert not email_dispatcher.dispatch.called
        # Internal fallback called
        assert internal_dispatcher.dispatch.called

        assert result["delivery_channel"] == "internal"
        assert result["delivery_circuit_open"] is True

    def test_cb_tripped_flag_set_in_result(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        # Make the dispatcher fail enough times to trip the breaker
        dispatcher = MagicMock()
        # Set threshold to 1 so first failure trips it
        with patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver.get_delivery_circuit_breaker"
        ) as gcb:
            cb = MagicMock()
            cb.is_open.return_value = False
            # First failure trips the breaker
            cb.record_failure.return_value = True
            gcb.return_value = cb

            with _patch_dispatcher(
                _mock_dispatcher_error("down"),
                _mock_dispatcher_success("internal"),
            ):
                result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_circuit_open"] is True


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — 13. DLQ PERSISTENCE
# ══════════════════════════════════════════════════════════════════


class TestDLQPersistence:
    def test_dlq_entry_created_on_all_channels_failed(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(
            _mock_dispatcher_error("email down"),
            _mock_dispatcher_error("internal down"),
        ), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_to_dlq",
            return_value="dlq-entry-id-123",
        ) as pdlq:
            result = asyncio.run(node_6_5_deliver(state))

        assert pdlq.called
        dlq_call = pdlq.call_args
        assert dlq_call.kwargs["tenant_id"] == "company-abc"
        assert dlq_call.kwargs["ticket_id"] == "ticket-123"
        assert dlq_call.kwargs["channel_type"] == "email"
        assert "All channels failed" in dlq_call.kwargs["error_message"]
        assert result["delivery_dlq_entry_id"] == "dlq-entry-id-123"

    def test_no_dlq_on_success(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_to_dlq"
        ) as pdlq:
            result = asyncio.run(node_6_5_deliver(state))

        assert not pdlq.called
        assert result["delivery_dlq_entry_id"] is None

    def test_dlq_persistence_failure_does_not_crash(self):
        """If DLQ itself fails, we still complete the pipeline."""
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        # The real _persist_to_dlq swallows exceptions and returns None,
        # so we simulate the inner try/except by patching to return None
        # (which is what happens when the real DLQ call fails internally).
        with _patch_dispatcher(
            _mock_dispatcher_error("down"),
            _mock_dispatcher_error("down"),
        ), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_to_dlq",
            return_value=None,
        ):
            result = asyncio.run(node_6_5_deliver(state))

        # Pipeline completes despite DLQ failure
        assert result["delivery_status"] == "error"
        # dlq_entry_id is None because persistence failed
        assert result["delivery_dlq_entry_id"] is None


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — 14. AUDIT LOGGING
# ══════════════════════════════════════════════════════════════════


class TestAuditLogging:
    def test_audit_entry_written_on_success(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._write_audit_entry",
            return_value="audit-id-1",
        ) as paudit:
            result = asyncio.run(node_6_5_deliver(state))

        assert paudit.called
        kwargs = paudit.call_args.kwargs
        assert kwargs["tenant_id"] == "company-abc"
        assert kwargs["ticket_id"] == "ticket-123"
        assert kwargs["channel"] == "email"
        assert kwargs["status"] == "dispatched"
        assert result["delivery_audit_id"] == "audit-id-1"

    def test_audit_entry_written_on_failure(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(
            _mock_dispatcher_error("down"),
            _mock_dispatcher_success("internal"),
        ), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._write_audit_entry",
            return_value="audit-id-x",
        ) as paudit:
            result = asyncio.run(node_6_5_deliver(state))

        # Audit called for every attempt (failed email + successful internal)
        assert paudit.call_count >= 2

    def test_audit_failure_does_not_crash_delivery(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        # The real _write_audit_entry has an internal try/except that returns None
        # on failure. Patch it to return None to simulate audit DB failure.
        with _patch_dispatcher(_mock_dispatcher_success("email")), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._write_audit_entry",
            return_value=None,
        ):
            result = asyncio.run(node_6_5_deliver(state))

        # Delivery still succeeds
        assert result["delivery_status"] == "dispatched"
        assert result["delivery_audit_id"] is None

    def test_audit_disabled_when_setting_off(self, monkeypatch):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver
        from app.config import get_settings

        # Force-disable audit
        settings = get_settings()
        monkeypatch.setattr(settings, "DELIVERY_AUDIT_ENABLED", False)

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")), patch(
            "app.services.audit_service.create_audit_entry"
        ) as pcreate:
            result = asyncio.run(node_6_5_deliver(state))

        assert not pcreate.called
        assert result["delivery_audit_id"] is None


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — 15. METRICS
# ══════════════════════════════════════════════════════════════════


class TestMetrics:
    def test_attempt_metric_emitted_on_success(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(_mock_dispatcher_success("email")), patch(
            "app.core.metrics.record_delivery_attempt"
        ) as pm:
            asyncio.run(node_6_5_deliver(state))

        pm.assert_called()
        # Verify it was called with channel=email, status=success
        call = pm.call_args
        assert call.args[0] == "email"
        assert call.args[1] == "success"

    def test_fallback_metric_emitted_on_sms_length_exceeded(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="x" * 2000)
        with _patch_dispatcher(_mock_dispatcher_success("email")), patch(
            "app.core.metrics.record_delivery_fallback"
        ) as pf:
            asyncio.run(node_6_5_deliver(state))

        pf.assert_called_once()
        call = pf.call_args
        assert call.args[0] == "sms"
        assert call.args[1] == "sms_length_exceeded"

    def test_dlq_metric_emitted_on_all_fail(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(
            _mock_dispatcher_error("down"),
            _mock_dispatcher_error("down"),
        ), patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_to_dlq",
            return_value="dlq-1",
        ), patch(
            "app.core.metrics.record_delivery_dlq"
        ) as pdlq_m:
            asyncio.run(node_6_5_deliver(state))

        pdlq_m.assert_called_once_with("email")


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — 16. CONFIG-DRIVEN THRESHOLDS
# ══════════════════════════════════════════════════════════════════


class TestConfigDriven:
    def test_sms_limit_read_from_settings(self, monkeypatch):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver
        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "DELIVERY_SMS_CHAR_LIMIT", 500)

        # 600 chars > 500 limit → upgrade to email
        state = _make_state(channel_type="sms", final_response="x" * 600)
        with _patch_dispatcher(_mock_dispatcher_success("email")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_channel"] == "email"
        assert result["delivery_fallback_reason"] == "sms_length_exceeded"

    def test_max_retries_read_from_settings(self, monkeypatch):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver
        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "DELIVERY_MAX_RETRIES", 1)

        state = _make_state(channel_type="email", final_response="Reply.")
        dispatcher = MagicMock()
        dispatcher.dispatch.side_effect = [
            {"status": "error", "error": "down"},  # attempt 1
            {"status": "error", "error": "down"},  # retry 1 (max_retries=1)
            # next channel (internal) should succeed
        ]
        internal_dispatcher = _mock_dispatcher_success("internal")
        with _patch_dispatcher(dispatcher, internal_dispatcher):
            result = asyncio.run(node_6_5_deliver(state))

        # max_retries=1 → 2 total attempts on email (1 + 1 retry)
        assert dispatcher.dispatch.call_count == 2
        assert result["delivery_retry_count"] == 1


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — 17-21. STATE FIELDS & BUG FIXES
# ══════════════════════════════════════════════════════════════════


class TestProductionStateFields:
    def test_delivery_message_id_stored_from_result(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="email", final_response="Reply.")
        with _patch_dispatcher(
            _mock_dispatcher_success("email", message_id="msg-xyz-999")
        ):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_message_id"] == "msg-xyz-999"

    def test_delivery_attempts_counts_actual_attempts_not_logs(self):
        """BUG FIX: v1 used len(logs)-1 which miscounted. v2 counts real attempts."""
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="Short.")
        # SMS succeeds first try → 1 attempt only
        with _patch_dispatcher(_mock_dispatcher_success("sms")):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_attempts"] == 1

    def test_delivery_attempts_counts_fallback_attempts(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="Short.")
        with _patch_dispatcher(
            _mock_dispatcher_error("sms down"),
            _mock_dispatcher_success("email"),
        ):
            result = asyncio.run(node_6_5_deliver(state))

        # SMS (failed) + email (success) = 2 attempts
        assert result["delivery_attempts"] == 2

    def test_db_session_closed_after_each_attempt(self):
        """Each per-channel dispatch must close its DB session."""
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state(channel_type="sms", final_response="Short.")
        sessions = []

        def _make_dispatcher_pair(dispatcher):
            session = _mock_db_session()
            sessions.append(session)
            return (dispatcher, session)

        with patch(
            "app.core.parwa_pipeline.nodes.node_6_5_deliver._get_dispatcher",
            side_effect=[
                _make_dispatcher_pair(_mock_dispatcher_error("sms down")),
                _make_dispatcher_pair(_mock_dispatcher_success("email")),
            ],
        ):
            asyncio.run(node_6_5_deliver(state))

        # Both sessions closed
        assert len(sessions) == 2
        for session in sessions:
            assert session.close.called


# ══════════════════════════════════════════════════════════════════
# PRODUCTION HARDENING — EXCEPTION HIERARCHY
# ══════════════════════════════════════════════════════════════════


class TestExceptionHierarchy:
    def test_delivery_error_has_correct_code(self):
        from app.exceptions import DeliveryError
        e = DeliveryError("all channels failed")
        assert e.error_code == "DELIVERY_ERROR"
        assert e.status_code == 502

    def test_circuit_open_error_has_correct_code(self):
        from app.exceptions import DeliveryCircuitOpenError
        e = DeliveryCircuitOpenError("breaker tripped")
        assert e.error_code == "DELIVERY_CIRCUIT_OPEN"
        assert e.status_code == 503

    def test_timeout_error_has_correct_code(self):
        from app.exceptions import DeliveryTimeoutError
        e = DeliveryTimeoutError("30s elapsed")
        assert e.error_code == "DELIVERY_TIMEOUT"
        assert e.status_code == 504

    def test_all_inherit_from_parwa_base(self):
        from app.exceptions import (
            ParwaBaseError, DeliveryError,
            DeliveryCircuitOpenError, DeliveryTimeoutError,
        )
        for exc_cls in (DeliveryError, DeliveryCircuitOpenError, DeliveryTimeoutError):
            assert issubclass(exc_cls, ParwaBaseError)
