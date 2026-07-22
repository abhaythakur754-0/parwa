"""
Unit tests for Escalation Vault — Atomic Claim (BC-016)

Tests cover:
  1. First agent claims a pending escalation → success=True
  2. Second agent tries to claim the same escalation → success=False, reason=already_claimed
  3. Claiming a non-existent escalation → success=False, reason=not_found
  4. Claiming an escalation not in pending state → success=False, reason=not_pending
  5. list_escalations excludes processing tickets by default
  6. list_escalations shows all tickets when exclude_processing=False
  7. Claimed ticket carries claimed_by_agent_id + claimed_at
  8. VaultManager.claim_escalation wraps the DB layer
  9. Concurrent claims — only one wins (race condition test)
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict
from unittest.mock import patch

import pytest


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_vault():
    """Use in-memory vault for each test."""
    from app.core.escalation_vault.vault_db import reset_vault_db
    reset_vault_db()
    yield
    reset_vault_db()


async def _save_escalation(
    escalation_id: str = "esc-001",
    tenant_id: str = "company-abc",
    ticket_id: str = "ticket-123",
) -> Dict[str, Any]:
    """Helper: save a fresh escalation to the vault."""
    from app.core.escalation_vault.vault_db import get_vault_db
    db = get_vault_db()
    return await db.save_escalation({
        "escalation_id": escalation_id,
        "tenant_id": tenant_id,
        "original_ticket_id": ticket_id,
        "notification_key": "PARWA-NFY-001",
        "original_query": "How do I refund?",
        "ticket_type": "refund_request",
        "complexity": "medium",
    })


# ══════════════════════════════════════════════════════════════════
# 1. FIRST AGENT CLAIMS PENDING ESCALATION
# ══════════════════════════════════════════════════════════════════


class TestClaimSuccess:
    """BC-016: First agent to claim a pending escalation wins."""

    def test_first_claim_succeeds(self):
        from app.core.escalation_vault.vault_db import get_vault_db, HUMAN_PROCESSING

        async def _run():
            await _save_escalation()
            db = get_vault_db()
            return await db.claim_escalation("esc-001", "agent-alice")

        result = asyncio.run(_run())

        assert result["success"] is True
        assert result["escalation_id"] == "esc-001"
        assert result["claimed_by"] == "agent-alice"
        assert result["reason"] == "claimed"

        # Verify the record was actually updated
        async def _verify():
            db = get_vault_db()
            return await db.get_escalation("esc-001")
        record = asyncio.run(_verify())
        assert record["human_status"] == HUMAN_PROCESSING
        assert record["claimed_by_agent_id"] == "agent-alice"
        assert record["claimed_at"] is not None


# ══════════════════════════════════════════════════════════════════
# 2. SECOND AGENT CANNOT CLAIM SAME ESCALATION
# ══════════════════════════════════════════════════════════════════


class TestClaimAlreadyClaimed:
    """BC-016: Subsequent claimants get success=False."""

    def test_second_claim_fails_with_already_claimed(self):
        from app.core.escalation_vault.vault_db import get_vault_db

        async def _run():
            await _save_escalation()
            db = get_vault_db()
            first = await db.claim_escalation("esc-001", "agent-alice")
            second = await db.claim_escalation("esc-001", "agent-bob")
            return first, second

        first, second = asyncio.run(_run())

        assert first["success"] is True
        assert second["success"] is False
        assert second["reason"] == "already_claimed"
        assert second["claimed_by"] == "agent-alice"  # original claimer


# ══════════════════════════════════════════════════════════════════
# 3. CLAIM NON-EXISTENT ESCALATION
# ══════════════════════════════════════════════════════════════════


class TestClaimNotFound:
    """Claiming a non-existent escalation returns reason=not_found."""

    def test_claim_nonexistent_returns_not_found(self):
        from app.core.escalation_vault.vault_db import get_vault_db

        async def _run():
            db = get_vault_db()
            return await db.claim_escalation("esc-does-not-exist", "agent-alice")

        result = asyncio.run(_run())

        assert result["success"] is False
        assert result["reason"] == "not_found"
        assert result["claimed_by"] is None


# ══════════════════════════════════════════════════════════════════
# 4. CLAIM ESCALATION NOT IN PENDING STATE
# ══════════════════════════════════════════════════════════════════


class TestClaimNotPending:
    """Claiming an escalation that's already in guidance_provided/resolved state."""

    def test_claim_after_guidance_provided_returns_not_pending(self):
        from app.core.escalation_vault.vault_db import (
            get_vault_db, HUMAN_GUIDANCE_PROVIDED,
        )

        async def _run():
            await _save_escalation()
            db = get_vault_db()
            # Manually move to guidance_provided
            await db.update_human_guidance("esc-001", "agent already helped", "test")
            # Now try to claim
            return await db.claim_escalation("esc-001", "agent-alice")

        result = asyncio.run(_run())

        assert result["success"] is False
        assert result["reason"] == "not_pending"


# ══════════════════════════════════════════════════════════════════
# 5. LIST EXCLUDES PROCESSING BY DEFAULT
# ══════════════════════════════════════════════════════════════════


class TestListExcludesProcessing:
    """BC-016: list_escalations hides tickets being worked by another agent."""

    def test_default_list_excludes_processing(self):
        from app.core.escalation_vault.vault_db import get_vault_db

        async def _run():
            # Save 2 escalations
            await _save_escalation("esc-001")
            await _save_escalation("esc-002")
            db = get_vault_db()
            # Claim the first one
            await db.claim_escalation("esc-001", "agent-alice")
            # List with default args
            return await db.list_escalations("company-abc")

        records = asyncio.run(_run())

        # Only esc-002 should appear (esc-001 is being worked by alice)
        ids = [r["escalation_id"] for r in records]
        assert "esc-002" in ids
        assert "esc-001" not in ids

    def test_admin_list_includes_processing(self):
        from app.core.escalation_vault.vault_db import get_vault_db

        async def _run():
            await _save_escalation("esc-001")
            await _save_escalation("esc-002")
            db = get_vault_db()
            await db.claim_escalation("esc-001", "agent-alice")
            # Admin view: exclude_processing=False
            return await db.list_escalations(
                "company-abc", exclude_processing=False,
            )

        records = asyncio.run(_run())

        ids = [r["escalation_id"] for r in records]
        assert "esc-001" in ids
        assert "esc-002" in ids


# ══════════════════════════════════════════════════════════════════
# 6. VAULTMANAGER WRAPPER
# ══════════════════════════════════════════════════════════════════


class TestVaultManagerClaim:
    """VaultManager.claim_escalation wraps the DB layer."""

    def test_vault_manager_claim_success(self):
        from app.core.escalation_vault.vault_manager import VaultManager

        async def _run():
            await _save_escalation()
            return await VaultManager.claim_escalation("esc-001", "agent-alice")

        result = asyncio.run(_run())

        assert result["success"] is True
        assert result["claimed_by"] == "agent-alice"

    def test_vault_manager_claim_already_claimed(self):
        from app.core.escalation_vault.vault_manager import VaultManager

        async def _run():
            await _save_escalation()
            await VaultManager.claim_escalation("esc-001", "agent-alice")
            return await VaultManager.claim_escalation("esc-001", "agent-bob")

        result = asyncio.run(_run())

        assert result["success"] is False
        assert result["reason"] == "already_claimed"


# ══════════════════════════════════════════════════════════════════
# 7. CONCURRENT CLAIMS — RACE CONDITION
# ══════════════════════════════════════════════════════════════════


class TestConcurrentClaim:
    """Two agents claim simultaneously — only one wins.

    Uses threading to simulate concurrent API calls hitting the vault
    at the same time. The InMemory backend's _lock ensures atomicity.
    """

    def test_concurrent_claims_only_one_wins(self):
        from app.core.escalation_vault.vault_db import get_vault_db

        async def _setup():
            await _save_escalation()

        asyncio.run(_setup())

        results = []
        barrier = threading.Barrier(2)  # both threads start at the same time

        def _claim(agent_id: str):
            async def _do():
                barrier.wait()  # synchronize start
                db = get_vault_db()
                return await db.claim_escalation("esc-001", agent_id)
            results.append(asyncio.run(_do()))

        t1 = threading.Thread(target=_claim, args=("agent-alice",))
        t2 = threading.Thread(target=_claim, args=("agent-bob",))

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Exactly one success, one already_claimed
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        assert len(successes) == 1
        assert len(failures) == 1
        assert failures[0]["reason"] == "already_claimed"
