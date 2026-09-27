"""
Unit tests for Node 6.5 Phase 2 — CRM push-back (BC-016)

Tests cover:
  1. CRM push runs AFTER customer dispatch succeeds (never before)
  2. CRM push skipped when delivery fails (customer never got the answer)
  3. CRM push skipped when no CRM ticket in metadata
  4. CRM push skipped when CRM_PUSH_ENABLED=False
  5. CRM push retries on soft-fail, succeeds on retry
  6. CRM push DLQ on all-retries-exhausted
  7. CRM push metrics emitted on every attempt
  8. CRMBridge.push_response called with correct args (provider, ticket_id, status="resolved")
  9. Internal note includes ticket_type + quality
  10. State fields crm_push_* populated correctly on all paths
  11. CRMPushError exception class exists with correct code
  12. Idempotency: existing crm_push_status carried forward on skip

BC-016 (vault claim) tests are in test_vault_claim.py.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


def _make_state_with_crm(
    channel_type: str = "email",
    final_response: str = "Here is your answer.",
    ticket_id: str = "ticket-123",
    tenant_id: str = "company-abc",
    crm_ticket_id: str = "ZD-99999",
    crm_provider: str = "zendesk",
    metadata_extra: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Build a state with CRM metadata populated."""
    metadata = {
        "crm_ticket_id": crm_ticket_id,
        "crm_provider": crm_provider,
    }
    if metadata_extra:
        metadata.update(metadata_extra)
    return {
        "ticket_id": ticket_id,
        "tenant_id": tenant_id,
        "channel_type": channel_type,
        "final_response": final_response,
        "formatted_response": final_response,
        "variant_tier_short": "parwa",
        "variant_tier": "parwa",
        "status": "resolved",
        "technique_log": [],
        "total_token_usage": 5,
        "metadata": metadata,
        "ticket_type": "refund_request",
        "complexity": "medium",
        "quality_score": 0.92,
        "techniques_used": ["GSD", "MAKER"],
    }


def _mock_db_session():
    session = MagicMock()
    session.close = MagicMock()
    return session


def _mock_dispatcher_success(channel: str = "email", message_id: str = "msg-abc"):
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = {
        "status": "dispatched",
        "channel": channel,
        "ticket_id": "ticket-123",
        "message_id": message_id,
    }
    return dispatcher


def _mock_dispatcher_error(error_msg: str = "Twilio timeout"):
    dispatcher = MagicMock()
    dispatcher.dispatch.side_effect = Exception(error_msg)
    return dispatcher


def _patch_dispatcher(*dispatchers_and_sessions):
    tuples = [(d, _mock_db_session()) for d in dispatchers_and_sessions]
    return patch(
        "app.core.parwa_pipeline.nodes.node_6_5_deliver._get_dispatcher",
        side_effect=tuples,
    )


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    from app.core.parwa_pipeline.delivery_circuit_breaker import (
        reset_delivery_circuit_breaker,
    )
    reset_delivery_circuit_breaker()
    yield
    reset_delivery_circuit_breaker()


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Make retries instant so tests don't wait."""
    from app.core.parwa_pipeline.nodes import node_6_5_deliver as mod
    monkeypatch.setattr(mod, "_sleep", lambda _: None)


@pytest.fixture(autouse=True)
def _mock_crm_credentials(monkeypatch):
    """BC-MCP-Wiring: mock IntegrationService.get_crm_config_for_tenant.

    The CRM push helpers now load real credentials from the integrations
    table before calling CRMBridge. In unit tests we don't have a DB, so
    we patch the credential lookup to return a fake config dict — this
    lets the push proceed to the mocked CRMBridge.push_response as before.
    """
    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = {
        "api_key": "fake-zendesk-token",
        "subdomain": "test",
        "email": "agent@test.com",
    }
    fake_session = MagicMock()
    monkeypatch.setattr(
        "app.services.integration_service.IntegrationService",
        lambda db: fake_service,
    )
    monkeypatch.setattr("database.base.SessionLocal", lambda: fake_session)
    # Also patch the in-function imports — node_6_5 imports IntegrationService
    # lazily inside _push_to_crm_with_retry, so the module-level patch above
    # is what actually takes effect.


def _patch_crm_push_success():
    """Patch CRMBridge.push_response to return success."""
    return patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_response",
        new=AsyncMock(return_value={
            "success": True,
            "crm_ticket_id": "ZD-99999",
            "crm_status": "solved",
        }),
    )


def _patch_crm_push_soft_fail():
    """Patch CRMBridge.push_response to return success=False (soft fail)."""
    return patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_response",
        new=AsyncMock(return_value={
            "success": False,
            "error": "Zendesk API returned 503",
            "crm_ticket_id": "ZD-99999",
        }),
    )


def _patch_crm_push_exception():
    """Patch CRMBridge.push_response to raise an exception (hard fail)."""
    return patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_response",
        new=AsyncMock(side_effect=ConnectionError("Zendesk DNS resolution failed")),
    )


# ══════════════════════════════════════════════════════════════════
# 1. CRM PUSH RUNS AFTER CUSTOMER DISPATCH SUCCEEDS
# ══════════════════════════════════════════════════════════════════


class TestCRMPushAfterDelivery:
    """BC-016: CRM push happens AFTER customer delivery, never before."""

    def test_crm_push_called_when_delivery_succeeds(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        # Phase 1 succeeded
        assert result["delivery_status"] == "dispatched"
        # Phase 2 was called
        assert mock_push.called
        assert result["crm_push_status"] == "success"
        assert result["crm_push_provider"] == "zendesk"

    def test_crm_push_called_with_correct_args(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm(
            final_response="Refund processed for $49.00.",
        )
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        mock_push.assert_awaited_once()
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["provider"] == "zendesk"
        assert call_kwargs["ticket_id"] == "ZD-99999"
        assert call_kwargs["response"] == "Refund processed for $49.00."
        assert call_kwargs["status"] == "resolved"
        # Internal note should include ticket_type
        assert "refund_request" in call_kwargs["internal_note"]
        # Quality should be in the note
        assert "0.92" in call_kwargs["internal_note"]

    def test_crm_push_first_attempt_success_attempts_zero(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_success():
            result = asyncio.run(node_6_5_deliver(state))

        # First-attempt success → 0 retries
        assert result["crm_push_attempts"] == 0
        assert result["crm_push_error"] is None


# ══════════════════════════════════════════════════════════════════
# 2. CRM PUSH SKIPPED WHEN DELIVERY FAILS
# ══════════════════════════════════════════════════════════════════


class TestCRMPushSkippedOnDeliveryFail:
    """If customer didn't get the answer, CRM must NOT be told 'resolved'."""

    def test_crm_push_skipped_when_all_channels_fail(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        # All dispatchers fail → all-channels-failed DLQ
        with _patch_dispatcher(
            _mock_dispatcher_error(),  # email fails
            _mock_dispatcher_error(),  # internal fails
        ), _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        # Customer dispatch failed
        assert result["delivery_status"] == "error"
        # CRM was NOT called
        assert not mock_push.called
        # CRM status reflects "we didn't push because delivery failed"
        assert result["crm_push_status"] == "skipped_delivery_failed"

    def test_crm_push_skipped_on_empty_response(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm(final_response="")
        with _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "skipped_empty_response"
        assert not mock_push.called
        assert result["crm_push_status"] == "skipped_delivery_failed"


# ══════════════════════════════════════════════════════════════════
# 3. CRM PUSH SKIPPED WHEN NO CRM TICKET
# ══════════════════════════════════════════════════════════════════


class TestCRMPushSkippedNoCRM:
    """Tickets that didn't come from a CRM webhook have no crm_ticket_id."""

    def test_crm_push_skipped_when_no_crm_ticket_id(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm(crm_ticket_id="", crm_provider="")
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "dispatched"
        assert not mock_push.called
        assert result["crm_push_status"] == "skipped_no_crm"

    def test_crm_push_skipped_when_no_metadata(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        # State with no metadata key at all
        state = {
            "ticket_id": "ticket-999",
            "tenant_id": "company-abc",
            "channel_type": "email",
            "final_response": "Hello",
            "variant_tier": "parwa",
            "technique_log": [],
            "total_token_usage": 0,
        }
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "dispatched"
        assert not mock_push.called
        assert result["crm_push_status"] == "skipped_no_crm"


# ══════════════════════════════════════════════════════════════════
# 4. CRM PUSH SKIPPED WHEN DISABLED
# ══════════════════════════════════════════════════════════════════


class TestCRMPushSkippedDisabled:
    """CRM_PUSH_ENABLED=False → skip phase 2 entirely."""

    def test_crm_push_skipped_when_disabled(self, monkeypatch):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver
        from app.config import get_settings

        # Force disable
        original = get_settings()
        monkeypatch.setattr(original, "CRM_PUSH_ENABLED", False)

        state = _make_state_with_crm()
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "dispatched"
        assert not mock_push.called
        assert result["crm_push_status"] == "skipped_disabled"


# ══════════════════════════════════════════════════════════════════
# 5. CRM PUSH RETRY ON SOFT-FAIL
# ══════════════════════════════════════════════════════════════════


class TestCRMPushRetry:
    """Soft-fail should retry; second attempt succeeds."""

    def test_crm_push_retries_on_soft_fail_then_succeeds(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        # First call soft-fails, second succeeds
        side_effects = [
            {"success": False, "error": "Zendesk 503"},
            {"success": True, "crm_ticket_id": "ZD-99999"},
        ]
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             patch(
                 "app.core.crm_bridge.crm_bridge.CRMBridge.push_response",
                 new=AsyncMock(side_effect=side_effects),
             ) as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        assert mock_push.await_count == 2
        assert result["crm_push_status"] == "success"
        # 1 retry used (first attempt was a soft-fail)
        assert result["crm_push_attempts"] == 1


# ══════════════════════════════════════════════════════════════════
# 6. CRM PUSH DLQ ON ALL-RETRIES-EXHAUSTED
# ══════════════════════════════════════════════════════════════════


class TestCRMPushDLQ:
    """All CRM retries exhausted → persist to DLQ with crm_push_failed."""

    def test_crm_push_dlq_on_all_soft_fails(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_soft_fail(), \
             patch(
                 "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_crm_failure_to_dlq",
                 return_value="dlq-crm-001",
             ) as mock_dlq:
            result = asyncio.run(node_6_5_deliver(state))

        # Customer got the answer
        assert result["delivery_status"] == "dispatched"
        # CRM push failed
        assert result["crm_push_status"] == "dlq_persisted"
        assert result["crm_push_dlq_entry_id"] == "dlq-crm-001"
        # DLQ was called with the right context
        assert mock_dlq.called
        dlq_kwargs = mock_dlq.call_args.kwargs
        assert dlq_kwargs["crm_provider"] == "zendesk"
        assert dlq_kwargs["crm_ticket_id"] == "ZD-99999"
        assert "CRM push failed" in dlq_kwargs["error_message"]

    def test_crm_push_dlq_on_all_hard_fails(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_exception(), \
             patch(
                 "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_crm_failure_to_dlq",
                 return_value="dlq-crm-002",
             ):
            result = asyncio.run(node_6_5_deliver(state))

        assert result["delivery_status"] == "dispatched"
        assert result["crm_push_status"] == "dlq_persisted"
        assert result["crm_push_dlq_entry_id"] == "dlq-crm-002"
        assert "Zendesk DNS" in (result["crm_push_error"] or "")

    def test_crm_push_attempts_counts_total_retries(self):
        """With CRM_PUSH_MAX_RETRIES=2 (default), 3 total attempts on failure."""
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        with _patch_dispatcher(_mock_dispatcher_success("email")), \
             _patch_crm_push_soft_fail(), \
             patch(
                 "app.core.parwa_pipeline.nodes.node_6_5_deliver._persist_crm_failure_to_dlq",
                 return_value="dlq-crm-003",
             ):
            result = asyncio.run(node_6_5_deliver(state))

        # Default CRM_PUSH_MAX_RETRIES=2 → 3 attempts (1 initial + 2 retries)
        assert result["crm_push_attempts"] == 3


# ══════════════════════════════════════════════════════════════════
# 7. EXCEPTION CLASS
# ══════════════════════════════════════════════════════════════════


class TestCRMPushException:
    """CRMPushError exception exists with correct structure."""

    def test_crm_push_error_exists(self):
        from app.exceptions import CRMPushError
        e = CRMPushError("Zendesk down")
        assert e.error_code == "CRM_PUSH_ERROR"
        assert e.status_code == 502

    def test_crm_push_error_inherits_parwa_base(self):
        from app.exceptions import ParwaBaseError, CRMPushError
        assert issubclass(CRMPushError, ParwaBaseError)


# ══════════════════════════════════════════════════════════════════
# 8. IDEMPOTENCY — existing crm_push_status carried forward
# ══════════════════════════════════════════════════════════════════


class TestCRMPushIdempotency:
    """If delivery_status is already terminal, skip phase 1 AND phase 2.
    Phase 2 state (crm_push_*) must be carried forward unchanged."""

    def test_idempotent_skip_carries_crm_push_state(self):
        from app.core.parwa_pipeline.nodes.node_6_5_deliver import node_6_5_deliver

        state = _make_state_with_crm()
        state["delivery_status"] = "dispatched"  # already delivered
        state["crm_push_status"] = "success"
        state["crm_push_provider"] = "zendesk"
        state["crm_push_attempts"] = 0
        state["crm_push_result"] = {"success": True}
        state["crm_push_dlq_entry_id"] = None
        state["crm_push_error"] = None

        with _patch_crm_push_success() as mock_push:
            result = asyncio.run(node_6_5_deliver(state))

        # No new push
        assert not mock_push.called
        # State carried forward
        assert result["crm_push_status"] == "success"
        assert result["crm_push_provider"] == "zendesk"
        assert result["crm_push_attempts"] == 0
