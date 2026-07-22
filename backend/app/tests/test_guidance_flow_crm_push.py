"""
Unit tests for guidance flow CRM push (BC-017 Gap 2 + Gap 3).

Gap 2: push_resume_result was fire-and-forget. Now wrapped with retry +
      backoff + DLQ + metrics (error_type=crm_resume_push_failed).
Gap 3: No max-attempts counter existed. Now: when GUIDANCE_MAX_RETRIES
      exceeded, reprocess_status=REPROCESS_EXHAUSTED is set (terminal)
      and push_permanent_failure_to_crm() resets the CRM ticket to
      "open"/"new" so the human queue picks it up fresh.

Together: when AI can't solve, CRM ticket looks like a fresh new ticket
again in the human queue — exactly like before PARWA touched it.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_vault():
    """Reset InMemory vault + processing set before each test."""
    from app.core.escalation_vault.vault_db import reset_vault_db
    reset_vault_db()
    from app.core.escalation_vault.guidance_ticket_flow import reset_guidance_state
    reset_guidance_state()
    yield
    reset_vault_db()
    reset_guidance_state()


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Make retries instant so tests don't wait."""
    from app.core.escalation_vault import guidance_ticket_flow as mod
    monkeypatch.setattr(mod, "_sleep", lambda _: None)


@pytest.fixture(autouse=True)
def _mock_crm_credentials(monkeypatch):
    """BC-MCP-Wiring: mock IntegrationService.get_crm_config_for_tenant.

    The resume + permanent-failure push helpers now load real credentials
    from the integrations table before calling CRMBridge. In unit tests
    we don't have a DB, so patch the credential lookup to return a fake
    config dict.
    """
    from unittest.mock import MagicMock

    fake_service = MagicMock()
    fake_service.get_crm_config_for_tenant.return_value = {
        "api_key": "fake-zendesk-token",
        "subdomain": "test",
        "email": "agent@test.com",
    }
    monkeypatch.setattr(
        "app.services.integration_service.IntegrationService",
        lambda db: fake_service,
    )
    monkeypatch.setattr("database.base.SessionLocal", lambda: MagicMock())


def _seed_escalation(
    *,
    escalation_id: str = "esc-001",
    tenant_id: str = "t1",
    original_ticket_id: str = "ticket-1",
    crm_ticket_id: str = "ZD-777",
    crm_provider: str = "zendesk",
    reprocess_attempts: int = 0,
):
    """Seed the InMemory vault with one escalation record."""
    from app.core.escalation_vault.vault_db import get_vault_db, HUMAN_GUIDANCE_PROVIDED

    vault = get_vault_db()
    record = asyncio.run(vault.save_escalation({
        "escalation_id": escalation_id,
        "tenant_id": tenant_id,
        "original_ticket_id": original_ticket_id,
        "notification_key": "PARWA-NFY-001",
        "escalation_source": "node_8_super_node",
        "original_query": "how do I refund?",
        "ticket_type": "refund_request",
        "complexity": "medium",
        "crm_ticket_id": crm_ticket_id,
        "crm_provider": crm_provider,
        "human_status": HUMAN_GUIDANCE_PROVIDED,
    }))
    # Set reprocess_attempts if non-zero
    if reprocess_attempts > 0:
        asyncio.run(vault.increment_reprocess_attempts(escalation_id))
        for _ in range(reprocess_attempts - 1):
            asyncio.run(vault.increment_reprocess_attempts(escalation_id))
    return record


def _patch_llm_call_success():
    """Patch the LLM call inside guidance flow to return a passing response.

    The response must share words with the guidance text so the
    `guidance_alignment` quality check passes.
    """
    return patch(
        "app.core.parwa_pipeline.llm_client.llm_call",
        new=AsyncMock(return_value=(
            "Thank you for your refund request. To process your refund, please use "
            "the refund form within 30 days of purchase. The customer support team "
            "will review your request and respond with detailed next steps. "
            "Refunds are typically processed within 5-7 business days."
        )),
    )


def _patch_llm_call_low_quality():
    """Patch the LLM call to return a low-quality (very short) response."""
    return patch(
        "app.core.parwa_pipeline.llm_client.llm_call",
        new=AsyncMock(return_value="ok"),
    )


def _patch_crm_resume_success():
    return patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_resume_result",
        new=AsyncMock(return_value={
            "success": True,
            "crm_ticket_id": "ZD-777",
            "crm_status": "solved",
        }),
    )


def _patch_crm_resume_soft_fail():
    return patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_resume_result",
        new=AsyncMock(return_value={
            "success": False,
            "error": "Zendesk 503",
            "crm_ticket_id": "ZD-777",
        }),
    )


def _patch_crm_permanent_failure_success():
    return patch(
        "app.core.crm_bridge.crm_bridge.CRMBridge.push_permanent_failure",
        new=AsyncMock(return_value={
            "success": True,
            "crm_ticket_id": "ZD-777",
            "crm_status": "open",
        }),
    )


# ══════════════════════════════════════════════════════════════════
# 1. REPROCESSED_ATTEMPTS COUNTER (BC-017 foundation)
# ══════════════════════════════════════════════════════════════════


class TestReprocessAttemptsCounter:
    """Verify the per-escalation attempt counter increments atomically."""

    def test_increment_starts_at_one(self):
        from app.core.escalation_vault.vault_db import get_vault_db
        _seed_escalation()
        vault = get_vault_db()
        count = asyncio.run(vault.increment_reprocess_attempts("esc-001"))
        assert count == 1

    def test_increment_increments_subsequent_calls(self):
        from app.core.escalation_vault.vault_db import get_vault_db
        _seed_escalation()
        vault = get_vault_db()
        asyncio.run(vault.increment_reprocess_attempts("esc-001"))
        asyncio.run(vault.increment_reprocess_attempts("esc-001"))
        count = asyncio.run(vault.increment_reprocess_attempts("esc-001"))
        assert count == 3

    def test_increment_returns_negative_one_on_not_found(self):
        from app.core.escalation_vault.vault_db import get_vault_db
        _seed_escalation()
        vault = get_vault_db()
        count = asyncio.run(vault.increment_reprocess_attempts("does-not-exist"))
        assert count == -1

    def test_vault_manager_wrapper_works(self):
        from app.core.escalation_vault.vault_manager import VaultManager
        _seed_escalation()
        count = asyncio.run(VaultManager.increment_reprocess_attempts("esc-001"))
        assert count == 1


# ══════════════════════════════════════════════════════════════════
# 2. GAP 2 — Resume push retry + DLQ
# ══════════════════════════════════════════════════════════════════


class TestGap2ResumePushRetry:
    """When guidance passes, push_resume_result must use retry+DLQ."""

    def test_resume_push_first_attempt_success(self):
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

        _seed_escalation()
        with _patch_llm_call_success(), _patch_crm_resume_success() as mock_push:
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Tell the customer to use the refund form within 30 days of purchase.",
                tenant_id="t1",
            ))
        assert result["success"] is True
        assert mock_push.await_count == 1
        assert result["crm_push"]["success"] is True

    def test_resume_push_retries_on_soft_fail_then_succeeds(self):
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

        _seed_escalation()
        side_effects = [
            {"success": False, "error": "503"},
            {"success": True, "crm_ticket_id": "ZD-777"},
        ]
        with _patch_llm_call_success(), \
             patch(
                 "app.core.crm_bridge.crm_bridge.CRMBridge.push_resume_result",
                 new=AsyncMock(side_effect=side_effects),
             ) as mock_push:
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Tell the customer to use the refund form within 30 days of purchase.",
                tenant_id="t1",
            ))
        assert result["success"] is True
        assert mock_push.await_count == 2
        assert result["crm_push"]["success"] is True

    def test_resume_push_dlq_on_all_retries_exhausted(self):
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

        _seed_escalation()
        with _patch_llm_call_success(), \
             _patch_crm_resume_soft_fail(), \
             patch(
                 "app.core.escalation_vault.guidance_ticket_flow._persist_crm_resume_failure_to_dlq",
                 return_value="dlq-resume-001",
             ) as mock_dlq:
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Tell the customer to use the refund form within 30 days of purchase.",
                tenant_id="t1",
            ))
        # Customer-facing flow still passed
        assert result["success"] is True
        # But CRM push failed
        assert result["crm_push"]["success"] is False
        assert result["crm_push"]["dlq_entry_id"] == "dlq-resume-001"
        assert mock_dlq.called


# ══════════════════════════════════════════════════════════════════
# 3. GAP 3 — Exhausted detection + permanent failure push
# ══════════════════════════════════════════════════════════════════


class TestGap3ExhaustedDetection:
    """When MAX_GUIDANCE_RETRIES exceeded, set EXHAUSTED + push permanent failure."""

    def test_under_limit_failure_marks_failed_not_exhausted(self):
        """First-attempt failure (attempt_count=1, max=3) → FAILED, not EXHAUSTED."""
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket
        from app.core.escalation_vault.vault_db import get_vault_db, REPROCESS_FAILED

        _seed_escalation(reprocess_attempts=0)  # will be incremented to 1
        with _patch_llm_call_low_quality():
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Refund form.",
                tenant_id="t1",
            ))
        assert result["success"] is False
        assert result["exhausted"] is False
        assert result["reprocess_attempts"] == 1
        assert "attempt 1/3" in result["error"]

        vault = get_vault_db()
        record = asyncio.run(vault.get_escalation("esc-001"))
        assert record["reprocess_status"] == REPROCESS_FAILED

    def test_at_limit_failure_marks_exhausted(self):
        """When attempt_count reaches MAX_RETRIES, mark EXHAUSTED (terminal)."""
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket
        from app.core.escalation_vault.vault_db import get_vault_db, REPROCESS_EXHAUSTED

        # Seed with 2 prior attempts; this call will increment to 3 (= MAX)
        _seed_escalation(reprocess_attempts=2)
        with _patch_llm_call_low_quality(), \
             _patch_crm_permanent_failure_success() as mock_pf:
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Refund form.",
                tenant_id="t1",
            ))
        assert result["success"] is False
        assert result["exhausted"] is True
        assert result["reprocess_attempts"] == 3
        assert "exhausted" in result["error"]

        # CRM was reset to "open"/"new"
        assert mock_pf.await_count == 1
        mock_kwargs = mock_pf.call_args.kwargs
        assert mock_kwargs["provider"] == "zendesk"
        assert mock_kwargs["ticket_id"] == "ZD-777"
        assert mock_kwargs["attempts"] == 3

        # Vault is in terminal EXHAUSTED state
        vault = get_vault_db()
        record = asyncio.run(vault.get_escalation("esc-001"))
        assert record["reprocess_status"] == REPROCESS_EXHAUSTED

    def test_over_limit_no_more_calls(self):
        """An EXHAUSTED escalation should NOT be re-queued by batch."""
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket
        from app.core.escalation_vault.vault_db import get_vault_db, REPROCESS_EXHAUSTED

        # Manually put escalation in EXHAUSTED state
        _seed_escalation(reprocess_attempts=3)
        vault = get_vault_db()
        asyncio.run(vault.update_reprocess_status_direct("esc-001", REPROCESS_EXHAUSTED))

        # batch should skip it
        from app.core.escalation_vault.guidance_ticket_flow import batch_guidance_tickets
        result = asyncio.run(batch_guidance_tickets(tenant_id="t1"))
        # It either gets skipped, OR gets re-run (which would be a bug).
        # Let's check: if processed, then we have a regression.
        for r in result.get("results", []):
            if r.get("escalation_id") == "esc-001":
                pytest.fail("EXHAUSTED escalation was re-processed — should be skipped")
        # Skipped count includes our exhausted record
        assert result["total_skipped"] >= 1

    def test_permanent_failure_push_uses_failure_context(self):
        """push_permanent_failure must receive attempts + failure_context."""
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

        _seed_escalation(reprocess_attempts=2)
        with _patch_llm_call_low_quality(), \
             _patch_crm_permanent_failure_success() as mock_pf:
            asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Refund form.",
                tenant_id="t1",
            ))
        call_kwargs = mock_pf.call_args.kwargs
        assert call_kwargs["attempts"] == 3
        ctx = call_kwargs["failure_context"]
        assert "last_quality" in ctx
        assert "failure_analysis" in ctx
        assert "what_was_tried" in ctx
        assert ctx["ticket_type"] == "refund_request"
        assert ctx["complexity"] == "medium"

    def test_permanent_failure_push_dlq_on_crm_down(self):
        """If even the permanent-failure push fails, persist to DLQ."""
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

        _seed_escalation(reprocess_attempts=2)
        with _patch_llm_call_low_quality(), \
             patch(
                 "app.core.crm_bridge.crm_bridge.CRMBridge.push_permanent_failure",
                 new=AsyncMock(side_effect=ConnectionError("Zendesk DNS failed")),
             ), \
             patch(
                 "app.core.escalation_vault.guidance_ticket_flow._persist_crm_permanent_failure_to_dlq",
                 return_value="dlq-pf-001",
             ) as mock_dlq:
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Refund form.",
                tenant_id="t1",
            ))
        assert result["exhausted"] is True
        assert result["crm_push"]["success"] is False
        assert result["crm_push"]["dlq_entry_id"] == "dlq-pf-001"
        assert "manual_action_required" in result["crm_push"]
        assert mock_dlq.called

    def test_exhausted_does_not_fire_when_quality_passes(self):
        """Even at MAX_RETRIES, if quality passes, mark DONE (not EXHAUSTED)."""
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket
        from app.core.escalation_vault.vault_db import get_vault_db, REPROCESS_DONE

        _seed_escalation(reprocess_attempts=2)
        with _patch_llm_call_success(), _patch_crm_resume_success():
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Tell the customer to use the refund form within 30 days of purchase.",
                tenant_id="t1",
            ))
        assert result["success"] is True
        assert result["exhausted"] is False
        # Vault marked DONE (success path), not EXHAUSTED
        vault = get_vault_db()
        record = asyncio.run(vault.get_escalation("esc-001"))
        assert record["reprocess_status"] == REPROCESS_DONE


# ══════════════════════════════════════════════════════════════════
# 4. STATE FIELD COVERAGE
# ══════════════════════════════════════════════════════════════════


class TestReturnShape:
    """Verify the new return fields exist on every path."""

    def test_return_includes_reprocess_attempts(self):
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

        _seed_escalation()
        with _patch_llm_call_success(), _patch_crm_resume_success():
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Use the refund form.",
                tenant_id="t1",
            ))
        assert "reprocess_attempts" in result
        assert isinstance(result["reprocess_attempts"], int)
        assert result["reprocess_attempts"] >= 1

    def test_return_includes_exhausted_flag(self):
        from app.core.escalation_vault.guidance_ticket_flow import create_guidance_ticket

        _seed_escalation()
        with _patch_llm_call_success(), _patch_crm_resume_success():
            result = asyncio.run(create_guidance_ticket(
                escalation_id="esc-001",
                guidance="Use the refund form.",
                tenant_id="t1",
            ))
        assert "exhausted" in result
        assert isinstance(result["exhausted"], bool)
