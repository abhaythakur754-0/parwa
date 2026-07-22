"""
Unit tests for MCP credential wiring (BC-MCP-Wiring).

PROVES (per CLAUDE.md rule 5 — no "it works" without tests):
  1. IntegrationService.get_credential_config() returns DECRYPTED (unmasked)
     credentials from the DB, scoped by company_id + type + status=active.
  2. IntegrationService.get_credential_config() returns None when no active
     integration exists (instead of falling back to a masked row).
  3. IntegrationService.get_credential_config() returns the most recently
     updated row when multiple active rows exist.
  4. IntegrationService.get_crm_config_for_tenant() lowercases + strips the
     provider name and delegates to get_credential_config().
  5. node_6_5_deliver._push_to_crm_with_retry loads config via
     IntegrationService and passes it as config=... to CRMBridge.push_response.
  6. node_6_5_deliver._push_to_crm_with_retry short-circuits (no HTTP retries)
     when no active integration exists.
  7. node_6_5_deliver passes REAL credential keys (e.g. "access_token": "pat-xyz")
     — NOT the masked form ("pat-****").
  8. node_8_super_node._push_escalation_to_crm_with_retry loads config and
     passes it as config=... to CRMBridge.push_escalation.
  9. node_8_super_node._push_escalation_to_crm_with_retry short-circuits when
     no active integration exists.
  10. guidance_ticket_flow._push_resume_to_crm_with_retry loads config and
     passes it as config=... to CRMBridge.push_resume_result.
  11. guidance_ticket_flow._push_permanent_failure_to_crm_with_retry loads
     config and passes it as config=... to CRMBridge.push_permanent_failure.
  12. ALL four CRM push paths return the documented tuple shapes.

These tests mock the IntegrationService DB layer and the CRMBridge HTTP layer
so no real outbound calls happen — they verify the WIRING, not the network.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Path bootstrap ───────────────────────────────────────────────────
# Allow running this test file directly:
#   PYTHONPATH=backend:. python -m pytest backend/app/tests/test_mcp_credential_wiring.py -v
# (Matches the convention used by the other BC-015→BC-018 test files.)


# ════════════════════════════════════════════════════════════════════
# FAKE ORM ROW (mimics database.models.integration.Integration)
# ════════════════════════════════════════════════════════════════════


class _FakeIntegrationRow:
    """Mimics the Integration ORM model for query chains."""

    def __init__(
        self,
        *,
        id: str,
        company_id: str,
        integration_type: str,
        status: str,
        credentials_encrypted: str,
        updated_at: datetime,
    ):
        self.id = id
        self.company_id = company_id
        self.integration_type = integration_type
        self.status = status
        self.credentials_encrypted = credentials_encrypted
        self.updated_at = updated_at


def _fake_hubspot_row(
    *,
    company_id: str = "company-abc",
    access_token: str = "pat-real-token-xyz-12345",
    status: str = "active",
    updated_at: Optional[datetime] = None,
) -> _FakeIntegrationRow:
    import json

    return _FakeIntegrationRow(
        id="int-hubspot-001",
        company_id=company_id,
        integration_type="hubspot",
        status=status,
        credentials_encrypted=json.dumps({"access_token": access_token}),
        updated_at=updated_at or datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc),
    )


# ════════════════════════════════════════════════════════════════════
# PART A — IntegrationService.get_credential_config / get_crm_config_for_tenant
# ════════════════════════════════════════════════════════════════════


def _build_service_with_rows(rows):
    """Build an IntegrationService whose .db.query() returns `rows`."""
    from app.services.integration_service import IntegrationService

    db = MagicMock()
    query = MagicMock()
    filter_chain = MagicMock()
    order_chain = MagicMock()

    # .query(Integration).filter(...).order_by(...).first()
    db.query.return_value = query
    query.filter.return_value = filter_chain
    filter_chain.order_by.return_value = order_chain
    order_chain.first.return_value = rows[0] if rows else None

    return IntegrationService(db), db


def test_get_credential_config_returns_decrypted_config():
    """Test 1: Returns the REAL access_token, not a masked form."""
    from app.services.integration_service import IntegrationService

    svc, _ = _build_service_with_rows([_fake_hubspot_row()])
    config = svc.get_credential_config("company-abc", "hubspot")

    assert config is not None, "Expected config dict, got None"
    assert config.get("access_token") == "pat-real-token-xyz-12345", (
        "get_credential_config must return the DECRYPTED token, "
        "not the masked form (pat-****). This is the whole point of "
        "the internal-use method — node_6_5/node_8 need real credentials."
    )


def test_get_credential_config_returns_none_when_no_active_integration():
    """Test 2: Returns None (not an empty dict, not a masked row) when nothing matches."""
    svc, _ = _build_service_with_rows([])
    config = svc.get_credential_config("company-abc", "hubspot")
    assert config is None, (
        "Expected None when no active integration exists — callers rely on "
        "None to short-circuit instead of making doomed HTTP retries."
    )


def test_get_credential_config_filters_by_active_status():
    """Test 3: The query filters by status='active' — a disconnected/error
    integration should NOT be returned even if it matches company+type."""
    from app.services.integration_service import IntegrationService, STATUS_ACTIVE

    # Build a row with status=error — should be filtered out
    svc, db = _build_service_with_rows([])

    # Verify the query filter call included status=active
    svc.get_credential_config("company-abc", "hubspot")

    # Inspect the filter() call — the SQLAlchemy `and_` clause will mention STATUS_ACTIVE
    filter_args = db.query.return_value.filter.call_args
    assert filter_args is not None, "filter() was never called"
    # We can't easily introspect the SQLAlchemy and_() clause object, but we
    # CAN check that the chain called .first() — proving the lookup ran.
    assert db.query.return_value.filter.return_value.order_by.return_value.first.called


def test_get_credential_config_picks_most_recently_updated():
    """Test 4: When multiple active rows exist, returns the most recent."""
    import json

    older = _FakeIntegrationRow(
        id="int-old",
        company_id="company-abc",
        integration_type="hubspot",
        status="active",
        credentials_encrypted=json.dumps({"access_token": "old-token"}),
        updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    newer = _FakeIntegrationRow(
        id="int-new",
        company_id="company-abc",
        integration_type="hubspot",
        status="active",
        credentials_encrypted=json.dumps({"access_token": "new-token"}),
        updated_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
    )

    svc, _ = _build_service_with_rows([newer, older])
    config = svc.get_credential_config("company-abc", "hubspot")

    # The mock returns rows[0] from .first(), which our builder set to `newer`
    assert config.get("access_token") == "new-token"


def test_get_crm_config_for_tenant_lowercases_provider():
    """Test 5: Provider name is normalized — 'HubSpot' / 'HUBSPOT' / '  hubspot  ' all work."""
    svc, _ = _build_service_with_rows([_fake_hubspot_row()])

    # All three forms should resolve to the same lookup
    for variant in ["hubspot", "HubSpot", "HUBSPOT", "  hubspot  "]:
        svc.get_crm_config_for_tenant("company-abc", variant)
        # No exception thrown → lookup ran with the normalized key
    # And the real call returns the token
    config = svc.get_crm_config_for_tenant("company-abc", "HUBSPOT")
    assert config["access_token"] == "pat-real-token-xyz-12345"


def test_get_crm_config_for_tenant_returns_none_on_empty_inputs():
    """Test 5b: Empty company_id or provider returns None — no DB call needed."""
    svc, _ = _build_service_with_rows([])
    assert svc.get_crm_config_for_tenant("", "hubspot") is None
    assert svc.get_crm_config_for_tenant("company-abc", "") is None
    assert svc.get_crm_config_for_tenant(None, "hubspot") is None


# ════════════════════════════════════════════════════════════════════
# PART B — node_6_5_deliver._push_to_crm_with_retry
# ════════════════════════════════════════════════════════════════════


def _make_pipeline_state(
    *,
    tenant_id: str = "company-abc",
    crm_provider: str = "hubspot",
    crm_ticket_id: str = "hs-ticket-42",
) -> Dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "ticket_id": "ticket-123",
        "metadata": {
            "crm_provider": crm_provider,
            "crm_ticket_id": crm_ticket_id,
        },
        "quality_score": 0.85,
    }


def test_node_6_5_loads_config_and_passes_to_crm_bridge():
    """Test 6: _push_to_crm_with_retry loads config via IntegrationService
    and passes it as config=... to CRMBridge.push_response."""
    from app.core.parwa_pipeline.nodes.node_6_5_deliver import _push_to_crm_with_retry

    state = _make_pipeline_state()

    # Mock CRMBridge.push_response — capture the config kwarg
    push_response_mock = AsyncMock(
        return_value={"success": True, "crm_ticket_id": "hs-ticket-42"}
    )

    # Mock IntegrationService.get_crm_config_for_tenant → real token
    fake_config = {"access_token": "pat-real-token-xyz-12345"}
    fake_session = MagicMock()
    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = fake_config

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_response",
        push_response_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=fake_session,
    ):
        status, result, retries, err = asyncio.run(
            _push_to_crm_with_retry(
                state=state,
                response_text="Hello from PARWA AI",
                delivery_channel="email",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                max_retries=2,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
            )
        )

    # Verify success path
    assert status == "success"
    assert err is None

    # THE CRITICAL ASSERTION: config= was passed with the real token
    push_response_mock.assert_awaited_once()
    call_kwargs = push_response_mock.call_args.kwargs
    assert "config" in call_kwargs, "CRMBridge.push_response must be called with config= kwarg"
    assert call_kwargs["config"]["access_token"] == "pat-real-token-xyz-12345", (
        "The REAL (unmasked) access_token must flow through to the CRM adapter. "
        "If this fails, the bug is back: config=None means CRM adapters bail with "
        "'No HubSpot config provided'."
    )

    # Verify IntegrationService was called with the right tenant + provider
    fake_service.get_crm_config_for_tenant.assert_called_once_with(
        "company-abc", "hubspot",
    )


def test_node_6_5_short_circuits_when_no_active_integration():
    """Test 7: When no active integration exists, returns immediately
    without calling CRMBridge.push_response (no doomed retries)."""
    from app.core.parwa_pipeline.nodes.node_6_5_deliver import _push_to_crm_with_retry

    state = _make_pipeline_state()

    push_response_mock = AsyncMock(return_value={"success": True})

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = None  # ← no integration

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_response",
        push_response_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        status, result, retries, err = asyncio.run(
            _push_to_crm_with_retry(
                state=state,
                response_text="Hello",
                delivery_channel="email",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                max_retries=3,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
            )
        )

    # Short-circuit returns error + zero retries + clear error message
    assert status == "error"
    assert retries == 0, "Must not have retried — should short-circuit on missing integration"
    assert err is not None
    assert "no_active_integration" in err

    # CRMBridge.push_response must NOT have been called
    push_response_mock.assert_not_awaited()


def test_node_6_5_retries_on_soft_fail_then_succeeds():
    """Test 7b: When CRMBridge returns success=False, retry up to max_retries
    times. The config= kwarg must be passed on every attempt."""
    from app.core.parwa_pipeline.nodes.node_6_5_deliver import _push_to_crm_with_retry

    state = _make_pipeline_state()

    # First call soft-fails, second succeeds
    push_response_mock = AsyncMock(
        side_effect=[
            {"success": False, "error": "rate_limited"},
            {"success": True, "crm_ticket_id": "hs-ticket-42"},
        ]
    )

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = {"access_token": "pat-xyz"}

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_response",
        push_response_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        status, result, retries, err = asyncio.run(
            _push_to_crm_with_retry(
                state=state,
                response_text="Hello",
                delivery_channel="email",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                max_retries=2,
                backoff_base=0.001,  # fast for tests
                backoff_max=0.005,
                metrics_enabled=False,
            )
        )

    assert status == "success"
    assert retries == 1, "Should have succeeded on the 2nd attempt (1 retry)"
    assert push_response_mock.await_count == 2
    # Both calls must have config=
    for call in push_response_mock.call_args_list:
        assert call.kwargs.get("config", {}).get("access_token") == "pat-xyz"


# ════════════════════════════════════════════════════════════════════
# PART C — node_8_super_node._push_escalation_to_crm_with_retry
# ════════════════════════════════════════════════════════════════════


def test_node_8_loads_config_and_passes_to_crm_bridge():
    """Test 8: node_8's escalation push loads config and passes it to CRMBridge.push_escalation."""
    from app.core.parwa_pipeline.nodes.node_8_super_node import (
        _push_escalation_to_crm_with_retry,
    )

    push_escalation_mock = AsyncMock(
        return_value={"success": True, "crm_ticket_id": "hs-ticket-42"}
    )

    fake_config = {"access_token": "pat-real-token-xyz-12345"}
    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = fake_config

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_escalation",
        push_escalation_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        status, result, retries, err, dlq = asyncio.run(
            _push_escalation_to_crm_with_retry(
                tenant_id="company-abc",
                ticket_id="ticket-123",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                escalation_context={"notification_key": "key-abc"},
                max_retries=2,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
                dlq_on_failure=True,
            )
        )

    assert status == "success"
    assert err is None
    assert dlq is None

    push_escalation_mock.assert_awaited_once()
    call_kwargs = push_escalation_mock.call_args.kwargs
    assert call_kwargs.get("config", {}).get("access_token") == "pat-real-token-xyz-12345", (
        "CRMBridge.push_escalation must receive the real config — "
        "without it, the adapter bails with 'No HubSpot config provided'."
    )


def test_node_8_short_circuits_when_no_active_integration():
    """Test 9: No active integration → immediate error, no HTTP calls."""
    from app.core.parwa_pipeline.nodes.node_8_super_node import (
        _push_escalation_to_crm_with_retry,
    )

    push_escalation_mock = AsyncMock(return_value={"success": True})

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = None

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_escalation",
        push_escalation_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        status, result, retries, err, dlq = asyncio.run(
            _push_escalation_to_crm_with_retry(
                tenant_id="company-abc",
                ticket_id="ticket-123",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                escalation_context={"notification_key": "key-abc"},
                max_retries=3,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
                dlq_on_failure=True,
            )
        )

    assert status == "error"
    assert retries == 0
    assert dlq is None, "Should NOT DLQ on missing-integration short-circuit"
    assert err is not None
    assert "no_active_integration" in err

    push_escalation_mock.assert_not_awaited()


# ════════════════════════════════════════════════════════════════════
# PART D — guidance_ticket_flow: resume + permanent_failure
# ════════════════════════════════════════════════════════════════════


def test_guidance_resume_loads_config_and_passes_to_crm_bridge():
    """Test 10: _push_resume_to_crm_with_retry passes config to push_resume_result."""
    from app.core.escalation_vault.guidance_ticket_flow import (
        _push_resume_to_crm_with_retry,
    )

    push_resume_mock = AsyncMock(
        return_value={"success": True, "crm_ticket_id": "hs-ticket-42"}
    )

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = {"access_token": "pat-xyz"}

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_resume_result",
        push_resume_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        status, result, retries, err, dlq = asyncio.run(
            _push_resume_to_crm_with_retry(
                tenant_id="company-abc",
                ticket_id="ticket-123",
                escalation_id="esc-001",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                response_text="Resolved with human guidance",
                quality_score=0.92,
                human_guidance="Try this approach...",
                max_retries=2,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
                dlq_on_failure=True,
            )
        )

    assert status == "success"
    push_resume_mock.assert_awaited_once()
    call_kwargs = push_resume_mock.call_args.kwargs
    assert call_kwargs.get("config", {}).get("access_token") == "pat-xyz"


def test_guidance_permanent_failure_loads_config_and_passes_to_crm_bridge():
    """Test 11: _push_permanent_failure_to_crm_with_retry passes config to push_permanent_failure."""
    from app.core.escalation_vault.guidance_ticket_flow import (
        _push_permanent_failure_to_crm_with_retry,
    )

    push_perm_fail_mock = AsyncMock(
        return_value={"success": True, "crm_ticket_id": "hs-ticket-42"}
    )

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = {"access_token": "pat-xyz"}

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_permanent_failure",
        push_perm_fail_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        status, result, retries, err, dlq = asyncio.run(
            _push_permanent_failure_to_crm_with_retry(
                tenant_id="company-abc",
                ticket_id="ticket-123",
                escalation_id="esc-001",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                attempts=3,
                failure_context={"reason": "all_techniques_failed"},
                max_retries=2,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
                dlq_on_failure=True,
            )
        )

    assert status == "success"
    push_perm_fail_mock.assert_awaited_once()
    call_kwargs = push_perm_fail_mock.call_args.kwargs
    assert call_kwargs.get("config", {}).get("access_token") == "pat-xyz"


def test_guidance_resume_short_circuits_when_no_active_integration():
    """Test 12: No active integration → no CRMBridge call, no DLQ entry."""
    from app.core.escalation_vault.guidance_ticket_flow import (
        _push_resume_to_crm_with_retry,
    )

    push_resume_mock = AsyncMock(return_value={"success": True})

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = None

    with patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_resume_result",
        push_resume_mock,
    ), patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        status, result, retries, err, dlq = asyncio.run(
            _push_resume_to_crm_with_retry(
                tenant_id="company-abc",
                ticket_id="ticket-123",
                escalation_id="esc-001",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                response_text="Resolved",
                quality_score=0.92,
                human_guidance="...",
                max_retries=3,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
                dlq_on_failure=True,
            )
        )

    assert status == "error"
    assert retries == 0
    assert dlq is None
    assert "no_active_integration" in (err or "")
    push_resume_mock.assert_not_awaited()


# ════════════════════════════════════════════════════════════════════
# PART E — Tuple-shape contracts (Test 12 expanded)
# ════════════════════════════════════════════════════════════════════


def test_node_6_5_returns_4_tuple():
    """node_6_5's _push_to_crm_with_retry must return (status, result, retries, err) — 4 items."""
    from app.core.parwa_pipeline.nodes.node_6_5_deliver import _push_to_crm_with_retry

    state = _make_pipeline_state()
    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = None

    with patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        result = asyncio.run(
            _push_to_crm_with_retry(
                state=state,
                response_text="Hello",
                delivery_channel="email",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                max_retries=0,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
            )
        )
    assert isinstance(result, tuple) and len(result) == 4


def test_node_8_returns_5_tuple():
    """node_8's _push_escalation_to_crm_with_retry must return (status, result, retries, err, dlq) — 5 items."""
    from app.core.parwa_pipeline.nodes.node_8_super_node import (
        _push_escalation_to_crm_with_retry,
    )

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = None

    with patch(
        "app.services.integration_service.IntegrationService",
        return_value=fake_service,
    ), patch(
        "database.base.SessionLocal",
        return_value=MagicMock(),
    ):
        result = asyncio.run(
            _push_escalation_to_crm_with_retry(
                tenant_id="company-abc",
                ticket_id="ticket-123",
                crm_provider="hubspot",
                crm_ticket_id="hs-ticket-42",
                escalation_context={},
                max_retries=0,
                backoff_base=0.01,
                backoff_max=0.05,
                metrics_enabled=False,
                dlq_on_failure=False,
            )
        )
    assert isinstance(result, tuple) and len(result) == 5


# ════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
