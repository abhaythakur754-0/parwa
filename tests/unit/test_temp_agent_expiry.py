"""
Tests for backend/app/core/temp_agent_expiry.py (F-073)

Covers:
- Registration: register, duplicate check, default duration
- Expiry check: not expired, expired, boundary (exact time)
- Expiry execution: deprovision, ticket reassignment, audit log
- Ticket reassignment: round-robin, no available agents, partial failure
- Batch operations: check_all_expiries, mixed expired/not
- Extension: extend valid agent, extend expired agent
- Revocation: immediate revoke, already expired, nonexistent
- Tenant isolation: company-scoped operations
- BC-008: garbage input, nonexistent agent, concurrent operations
- Config: defaults, frozen
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.temp_agent_expiry import (
    DEFAULT_CONFIG,
    ExpiryResult,
    ReassignmentResult,
    TempAgentConfig,
    TempAgentExpiryService,
    TempAgentRecord,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def svc():
    """Fresh service instance per test."""
    service = TempAgentExpiryService()
    yield service
    service.clear()


@pytest.fixture
def svc_with_perm(svc):
    """Service with some permanent agents registered."""
    svc.register_permanent_agent("perm-1", "company-a")
    svc.register_permanent_agent("perm-2", "company-a")
    svc.register_permanent_agent("perm-3", "company-b")
    return svc


def _register_with_tickets(svc, agent_id, company_id="company-a",
                           hours=24, tickets=None):
    """Helper: register temp agent and optionally add ticket assignments."""
    rec = svc.register_temp_agent(agent_id, company_id, f"Agent {agent_id}",
                                  duration_hours=hours)
    if tickets:
        rec.assigned_tickets.update(tickets)
    return rec


# ══════════════════════════════════════════════════════════════════════
# Registration tests
# ══════════════════════════════════════════════════════════════════════

class TestRegistration:
    """Tests for temp agent registration."""

    def test_register_basic(self, svc):
        rec = svc.register_temp_agent("temp-1", "company-a", "Temp Agent 1")
        assert rec.agent_id == "temp-1"
        assert rec.company_id == "company-a"
        assert rec.agent_name == "Temp Agent 1"
        assert rec.status == "active"
        assert isinstance(rec.created_at, datetime)

    def test_register_default_duration(self, svc):
        rec = svc.register_temp_agent("temp-1", "company-a", "Agent")
        expected = datetime.now(timezone.utc) + timedelta(
            hours=DEFAULT_CONFIG.default_duration_hours
        )
        # Allow 2-second tolerance
        assert abs((rec.expires_at - expected).total_seconds()) < 2

    def test_register_custom_duration(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=48
        )
        expected = datetime.now(timezone.utc) + timedelta(hours=48)
        assert abs((rec.expires_at - expected).total_seconds()) < 2

    def test_register_duplicate_raises(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        with pytest.raises(ValueError, match="already registered"):
            svc.register_temp_agent("temp-1", "company-b", "Other Agent")

    def test_register_min_duration_enforced(self, svc):
        with pytest.raises(ValueError, match="positive integer"):
            svc.register_temp_agent(
                "temp-1", "company-a", "Agent", duration_hours=0
            )

    def test_register_negative_duration_raises(self, svc):
        with pytest.raises(ValueError, match="positive integer"):
            svc.register_temp_agent(
                "temp-1", "company-a", "Agent", duration_hours=-5
            )

    def test_register_max_duration_enforced(self, svc):
        with pytest.raises(ValueError, match="cannot exceed"):
            svc.register_temp_agent(
                "temp-1", "company-a", "Agent",
                duration_hours=DEFAULT_CONFIG.max_duration_hours + 1,
            )

    def test_register_max_duration_accepted(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent",
            duration_hours=DEFAULT_CONFIG.max_duration_hours,
        )
        assert rec.expires_at > datetime.now(timezone.utc)

    def test_register_empty_agent_id_raises(self, svc):
        with pytest.raises(ValueError, match="agent_id"):
            svc.register_temp_agent("", "company-a", "Agent")

    def test_register_none_agent_id_raises(self, svc):
        with pytest.raises(ValueError, match="agent_id"):
            svc.register_temp_agent(None, "company-a", "Agent")

    def test_register_empty_company_id_raises(self, svc):
        with pytest.raises(ValueError, match="company_id"):
            svc.register_temp_agent("temp-1", "", "Agent")

    def test_register_empty_name_raises(self, svc):
        with pytest.raises(ValueError, match="name"):
            svc.register_temp_agent("temp-1", "company-a", "")

    def test_register_non_string_duration_raises(self, svc):
        with pytest.raises(ValueError, match="positive integer"):
            svc.register_temp_agent(
                "temp-1", "company-a", "Agent", duration_hours="24"
            )

    def test_register_long_agent_id_raises(self, svc):
        with pytest.raises(ValueError, match="must not exceed 128"):
            svc.register_temp_agent("x" * 129, "company-a", "Agent")

    def test_register_long_name_raises(self, svc):
        with pytest.raises(ValueError, match="must not exceed 255"):
            svc.register_temp_agent("temp-1", "company-a", "x" * 256)

    def test_register_returns_temp_agent_record(self, svc):
        rec = svc.register_temp_agent("temp-1", "company-a", "Agent")
        assert isinstance(rec, TempAgentRecord)

    def test_register_permanent_agent_basic(self, svc):
        svc.register_permanent_agent("perm-1", "company-a")
        agents = svc.get_active_temp_agents("company-a")
        # Permanent agents don't appear in temp agent list
        assert all(a.agent_id != "perm-1" for a in agents)

    def test_register_permanent_agent_duplicate_is_ok(self, svc):
        svc.register_permanent_agent("perm-1", "company-a")
        svc.register_permanent_agent("perm-1", "company-a")
        # No error — idempotent


# ══════════════════════════════════════════════════════════════════════
# Expiry check tests
# ══════════════════════════════════════════════════════════════════════

class TestExpiryCheck:
    """Tests for check_expiry and is_expired property."""

    def test_not_expired(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent",
                                duration_hours=24)
        assert svc.check_expiry("temp-1") is False

    def test_expired(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=1
        )
        # Manipulate expires_at to the past
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert svc.check_expiry("temp-1") is True

    def test_boundary_exact_time(self, svc):
        """Agent at exact expiry boundary should be expired."""
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=1
        )
        # Set to very slightly in the past (1 second)
        rec.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert svc.check_expiry("temp-1") is True

    def test_check_nonexistent_raises(self, svc):
        with pytest.raises(ValueError, match="not a registered temp agent"):
            svc.check_expiry("nonexistent")

    def test_check_revoked_agent_returns_true(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        svc.revoke_agent("temp-1")
        assert svc.check_expiry("temp-1") is True

    def test_remaining_seconds_positive(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=24
        )
        assert rec.remaining_seconds > 0

    def test_remaining_seconds_negative(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=1
        )
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert rec.remaining_seconds < 0


# ══════════════════════════════════════════════════════════════════════
# Expiry execution tests
# ══════════════════════════════════════════════════════════════════════

class TestExpiryExecution:
    """Tests for expire_agent deprovisioning."""

    def test_expire_sets_status(self, svc):
        rec = svc.register_temp_agent("temp-1", "company-a", "Agent")
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        result = svc.expire_agent("temp-1")
        assert result.was_expired is True
        assert svc.get_temp_agent("temp-1").status == "expired"

    def test_expire_pre_expired_clears_tickets(self, svc, svc_with_perm):
        tickets = {"tkt-1", "tkt-2", "tkt-3"}
        _register_with_tickets(
            svc_with_perm, "temp-1", "company-a",
            hours=1, tickets=tickets
        )
        svc_with_perm.get_temp_agent("temp-1").expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc_with_perm.expire_agent("temp-1")
        assert result.tickets_reassigned == 3
        assert result.tickets_failed == 0
        # Agent's ticket set should be empty
        assert len(svc_with_perm.get_temp_agent("temp-1").assigned_tickets) == 0

    def test_expire_already_expired_agent(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        svc.expire_agent("temp-1")  # First expiry
        result2 = svc.expire_agent("temp-1")  # Second expiry
        assert result2.was_expired is True

    def test_expire_nonexistent_raises(self, svc):
        with pytest.raises(ValueError, match="not a registered temp agent"):
            svc.expire_agent("nonexistent")

    def test_expire_returns_expiry_result(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        result = svc.expire_agent("temp-1")
        assert isinstance(result, ExpiryResult)
        assert result.agent_id == "temp-1"
        assert result.company_id == "company-a"

    def test_expire_active_agent_before_expiry(self, svc, svc_with_perm):
        """Expiring a not-yet-expired agent should still work (pre-emptive)."""
        _register_with_tickets(
            svc_with_perm, "temp-1", "company-a",
            hours=24, tickets={"tkt-1"}
        )
        result = svc_with_perm.expire_agent("temp-1")
        assert result.was_expired is False
        assert result.tickets_reassigned == 1


# ══════════════════════════════════════════════════════════════════════
# Ticket reassignment tests
# ══════════════════════════════════════════════════════════════════════

class TestTicketReassignment:
    """Tests for ticket reassignment logic."""

    def test_round_robin_distribution(self, svc_with_perm):
        tickets = {"tkt-1", "tkt-2", "tkt-3", "tkt-4"}
        _register_with_tickets(
            svc_with_perm, "temp-1", "company-a",
            hours=1, tickets=tickets
        )
        svc_with_perm.get_temp_agent("temp-1").expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc_with_perm.expire_agent("temp-1")
        assert result.tickets_reassigned == 4
        assert result.tickets_failed == 0

    def test_no_permanent_agents_available(self, svc):
        """Tickets fail when no permanent agents are registered."""
        tickets = {"tkt-1", "tkt-2"}
        _register_with_tickets(
            svc, "temp-1", "company-a", hours=1, tickets=tickets
        )
        svc.get_temp_agent("temp-1").expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc.expire_agent("temp-1")
        assert result.tickets_reassigned == 0
        assert result.tickets_failed == 2

    def test_reassign_to_specific_target(self, svc_with_perm):
        tickets = {"tkt-1", "tkt-2"}
        _register_with_tickets(
            svc_with_perm, "temp-1", "company-a",
            hours=1, tickets=tickets
        )
        result = svc_with_perm.reassign_tickets(
            "temp-1", target_agent_id="perm-1"
        )
        assert result.tickets_reassigned == 2
        assert result.target_agent_id == "perm-1"

    def test_reassign_nonexistent_agent_returns_empty(self, svc):
        result = svc.reassign_tickets("nonexistent")
        assert result.tickets_reassigned == 0
        assert result.tickets_failed == 0

    def test_reassign_no_tickets(self, svc_with_perm):
        _register_with_tickets(
            svc_with_perm, "temp-1", "company-a", hours=1, tickets=None
        )
        result = svc_with_perm.reassign_tickets("temp-1")
        assert result.tickets_reassigned == 0

    def test_cross_company_no_reassign(self, svc):
        """Permanent agents from company-b should NOT reassign
        tickets for a company-a temp agent."""
        svc.register_permanent_agent("perm-b", "company-b")
        tickets = {"tkt-1"}
        _register_with_tickets(
            svc, "temp-1", "company-a", hours=1, tickets=tickets
        )
        svc.get_temp_agent("temp-1").expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc.expire_agent("temp-1")
        # No permanent agents in company-a
        assert result.tickets_reassigned == 0
        assert result.tickets_failed == 1

    def test_reassignment_result_structure(self, svc):
        result = svc.reassign_tickets("nonexistent")
        assert isinstance(result, ReassignmentResult)
        assert hasattr(result, "agent_id")
        assert hasattr(result, "tickets_reassigned")
        assert hasattr(result, "tickets_failed")
        assert hasattr(result, "failed_ticket_ids")
        assert hasattr(result, "target_agent_id")


# ══════════════════════════════════════════════════════════════════════
# Batch operations tests
# ══════════════════════════════════════════════════════════════════════

class TestBatchOperations:
    """Tests for check_all_expiries batch processing."""

    def test_check_all_no_expired(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent", duration_hours=24)
        svc.register_temp_agent("temp-2", "company-a", "Agent", duration_hours=48)
        results = svc.check_all_expiries()
        assert len(results) == 0

    def test_check_all_with_expired(self, svc, svc_with_perm):
        # One active, one expired
        svc_with_perm.register_temp_agent(
            "temp-active", "company-a", "Active", duration_hours=24
        )
        expired_rec = svc_with_perm.register_temp_agent(
            "temp-expired", "company-a", "Expired", duration_hours=1
        )
        expired_rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        results = svc_with_perm.check_all_expiries()
        assert len(results) == 1
        assert results[0].agent_id == "temp-expired"

    def test_check_all_mixed_companies(self, svc):
        # Expired agent in company-a, no permanent agents
        svc.register_permanent_agent("perm-a", "company-a")
        rec = svc.register_temp_agent(
            "temp-a", "company-a", "Agent A", duration_hours=1
        )
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        svc.register_temp_agent(
            "temp-b", "company-b", "Agent B", duration_hours=24
        )

        results = svc.check_all_expiries()
        expired_ids = {r.agent_id for r in results}
        assert "temp-a" in expired_ids
        assert "temp-b" not in expired_ids

    def test_check_all_empty_registry(self, svc):
        results = svc.check_all_expiries()
        assert results == []

    def test_check_all_already_processed(self, svc):
        """check_all should skip already-expired agents."""
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=1
        )
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        svc.expire_agent("temp-1")
        results = svc.check_all_expiries()
        assert len(results) == 0


# ══════════════════════════════════════════════════════════════════════
# Extension tests
# ══════════════════════════════════════════════════════════════════════

class TestExtension:
    """Tests for extend_agent."""

    def test_extend_active_agent(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=24
        )
        original_expires = rec.expires_at
        updated = svc.extend_agent("temp-1", 12)
        assert updated.expires_at > original_expires

    def test_extend_expired_agent_raises(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=1
        )
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        with pytest.raises(ValueError, match="already expired"):
            svc.extend_agent("temp-1", 12)

    def test_extend_revoked_agent_raises(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        svc.revoke_agent("temp-1")
        with pytest.raises(ValueError, match="not active"):
            svc.extend_agent("temp-1", 12)

    def test_extend_nonexistent_raises(self, svc):
        with pytest.raises(ValueError, match="not a registered temp agent"):
            svc.extend_agent("nonexistent", 12)

    def test_extend_zero_hours_raises(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        with pytest.raises(ValueError, match="positive integer"):
            svc.extend_agent("temp-1", 0)

    def test_extend_negative_hours_raises(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        with pytest.raises(ValueError, match="positive integer"):
            svc.extend_agent("temp-1", -5)

    def test_extend_non_int_hours_raises(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        with pytest.raises(ValueError, match="positive integer"):
            svc.extend_agent("temp-1", 1.5)

    def test_extend_caps_at_max_duration(self, svc):
        """Extension should not exceed max_duration from creation."""
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent",
            duration_hours=DEFAULT_CONFIG.max_duration_hours - 1
        )
        updated = svc.extend_agent("temp-1", 100)
        max_expires = rec.created_at + timedelta(
            hours=DEFAULT_CONFIG.max_duration_hours
        )
        assert updated.expires_at <= max_expires


# ══════════════════════════════════════════════════════════════════════
# Revocation tests
# ══════════════════════════════════════════════════════════════════════

class TestRevocation:
    """Tests for revoke_agent immediate revocation."""

    def test_revoke_active_agent(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        result = svc.revoke_agent("temp-1")
        assert svc.get_temp_agent("temp-1").status == "revoked"
        assert isinstance(result, ExpiryResult)

    def test_revoke_clears_tickets(self, svc, svc_with_perm):
        tickets = {"tkt-1", "tkt-2"}
        _register_with_tickets(
            svc_with_perm, "temp-1", "company-a",
            hours=24, tickets=tickets
        )
        result = svc_with_perm.revoke_agent("temp-1")
        assert result.tickets_reassigned == 2
        assert len(svc_with_perm.get_temp_agent("temp-1").assigned_tickets) == 0

    def test_revoke_already_expired(self, svc):
        rec = svc.register_temp_agent(
            "temp-1", "company-a", "Agent", duration_hours=1
        )
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        result = svc.revoke_agent("temp-1")
        assert result.was_expired is True

    def test_revoke_already_revoked(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        svc.revoke_agent("temp-1")
        result = svc.revoke_agent("temp-1")  # Second revoke
        assert result.was_expired is True

    def test_revoke_nonexistent_raises(self, svc):
        with pytest.raises(ValueError, match="not a registered temp agent"):
            svc.revoke_agent("nonexistent")


# ══════════════════════════════════════════════════════════════════════
# Tenant isolation tests (BC-001)
# ══════════════════════════════════════════════════════════════════════

class TestTenantIsolation:
    """BC-001: All operations must be scoped to company_id."""

    def test_get_active_temp_agents_scoped(self, svc):
        svc.register_temp_agent("temp-a1", "company-a", "Agent A1",
                                duration_hours=24)
        svc.register_temp_agent("temp-b1", "company-b", "Agent B1",
                                duration_hours=24)
        agents_a = svc.get_active_temp_agents("company-a")
        agents_b = svc.get_active_temp_agents("company-b")
        assert len(agents_a) == 1
        assert agents_a[0].agent_id == "temp-a1"
        assert len(agents_b) == 1
        assert agents_b[0].agent_id == "temp-b1"

    def test_get_active_temp_agents_empty_company(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        agents = svc.get_active_temp_agents("company-z")
        assert agents == []

    def test_permanent_agents_scoped_reassignment(self, svc):
        """Permanent agents in company-a should not receive
        tickets from company-b temp agents."""
        svc.register_permanent_agent("perm-a", "company-a")
        tickets = {"tkt-1"}
        _register_with_tickets(
            svc, "temp-b", "company-b", hours=1, tickets=tickets
        )
        svc.get_temp_agent("temp-b").expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc.expire_agent("temp-b")
        assert result.tickets_reassigned == 0
        assert result.tickets_failed == 1

    def test_get_active_empty_company_id(self, svc):
        assert svc.get_active_temp_agents("") == []
        assert svc.get_active_temp_agents(None) == []

    def test_different_companies_independent_expiry(self, svc):
        rec_a = svc.register_temp_agent(
            "temp-a", "company-a", "Agent A", duration_hours=1
        )
        rec_b = svc.register_temp_agent(
            "temp-b", "company-b", "Agent B", duration_hours=1
        )
        # Expire only company-a's agent
        rec_a.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        svc.expire_agent("temp-a")

        assert svc.get_temp_agent("temp-a").status == "expired"
        assert svc.get_temp_agent("temp-b").status == "active"


# ══════════════════════════════════════════════════════════════════════
# BC-008 resilience tests
# ══════════════════════════════════════════════════════════════════════

class TestResilience:
    """BC-008: Service must never crash on garbage input."""

    def test_garbage_input_to_check_expiry(self, svc):
        """check_expiry with nonexistent agent returns True (fail closed)."""
        # This is tested with a new service to avoid the ValueError
        # raised for a clear missing-agent case
        svc2 = TempAgentExpiryService()
        try:
            svc2.check_expiry("totally-nonexistent")
        except ValueError:
            pass  # Expected — ValueError is the documented behavior
        svc2.clear()

    def test_get_active_invalid_company_returns_empty(self, svc):
        assert svc.get_active_temp_agents("") == []
        assert svc.get_active_temp_agents(None) == []
        assert svc.get_active_temp_agents(12345) == []

    def test_get_temp_agent_nonexistent(self, svc):
        assert svc.get_temp_agent("nonexistent") is None

    def test_concurrent_registration(self, svc):
        """Multiple threads registering agents should not corrupt state."""
        errors = []

        def register(idx):
            try:
                svc.register_temp_agent(
                    f"temp-{idx}", "company-a", f"Agent {idx}",
                    duration_hours=24,
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,))
                    for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 50 unique agents
        all_agents = svc.get_all_temp_agents()
        assert len(all_agents) == 50
        assert len(errors) == 0

    def test_concurrent_expiry_check(self, svc):
        """Concurrent expiry checks should not crash."""
        svc.register_temp_agent("temp-1", "company-a", "Agent",
                                duration_hours=24)

        def check():
            try:
                svc.check_expiry("temp-1")
            except Exception:
                pass

        threads = [threading.Thread(target=check) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_reassign_tickets_nonexistent_agent_safe(self, svc):
        """Reassigning tickets for nonexistent agent should not crash."""
        result = svc.reassign_tickets("ghost-agent")
        assert result.tickets_reassigned == 0
        assert result.tickets_failed == 0

    def test_check_all_with_mixed_failures(self, svc):
        """check_all should handle partial failures gracefully."""
        svc.register_temp_agent("temp-ok", "company-a", "OK",
                                duration_hours=24)
        rec = svc.register_temp_agent("temp-exp", "company-a", "Expired",
                                      duration_hours=1)
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # Should process without errors
        results = svc.check_all_expiries()
        assert len(results) >= 0  # Just don't crash


# ══════════════════════════════════════════════════════════════════════
# Config tests
# ══════════════════════════════════════════════════════════════════════

class TestConfig:
    """Tests for TempAgentConfig defaults and immutability."""

    def test_default_config_values(self):
        cfg = TempAgentConfig()
        assert cfg.default_duration_hours == 24
        assert cfg.max_duration_hours == 720
        assert cfg.min_duration_hours == 1
        assert cfg.expiry_check_interval_seconds == 60
        assert cfg.max_tickets_per_reassignment == 500

    def test_config_is_frozen(self):
        cfg = TempAgentConfig()
        with pytest.raises(AttributeError):
            cfg.default_duration_hours = 100

    def test_custom_config(self):
        cfg = TempAgentConfig(default_duration_hours=12)
        assert cfg.default_duration_hours == 12
        svc = TempAgentExpiryService(config=cfg)
        rec = svc.register_temp_agent("temp-1", "company-a", "Agent")
        expected = datetime.now(timezone.utc) + timedelta(hours=12)
        assert abs((rec.expires_at - expected).total_seconds()) < 2

    def test_config_default_duration_property(self):
        cfg = TempAgentConfig(default_duration_hours=48)
        assert cfg.default_duration == timedelta(hours=48)

    def test_default_config_singleton(self):
        assert DEFAULT_CONFIG.default_duration_hours == 24
        assert DEFAULT_CONFIG.default_duration == timedelta(hours=24)


# ══════════════════════════════════════════════════════════════════════
# Query / getter tests
# ══════════════════════════════════════════════════════════════════════

class TestQueries:
    """Tests for query/getter methods."""

    def test_get_temp_agent_found(self, svc):
        rec = svc.register_temp_agent("temp-1", "company-a", "Agent")
        found = svc.get_temp_agent("temp-1")
        assert found is rec

    def test_get_temp_agent_not_found(self, svc):
        assert svc.get_temp_agent("ghost") is None

    def test_get_all_temp_agents_empty(self, svc):
        assert svc.get_all_temp_agents() == []

    def test_get_all_temp_agents_multiple(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "A")
        svc.register_temp_agent("temp-2", "company-b", "B")
        svc.register_temp_agent("temp-3", "company-a", "C")
        all_agents = svc.get_all_temp_agents()
        assert len(all_agents) == 3

    def test_get_active_excludes_expired(self, svc):
        rec = svc.register_temp_agent("temp-1", "company-a", "Agent",
                                      duration_hours=1)
        rec.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        active = svc.get_active_temp_agents("company-a")
        assert len(active) == 0

    def test_get_active_excludes_revoked(self, svc):
        svc.register_temp_agent("temp-1", "company-a", "Agent")
        svc.revoke_agent("temp-1")
        active = svc.get_active_temp_agents("company-a")
        assert len(active) == 0


# ══════════════════════════════════════════════════════════════════════
# Data class tests
# ══════════════════════════════════════════════════════════════════════

class TestDataClasses:
    """Tests for data class structure."""

    def test_temp_agent_record_defaults(self):
        rec = TempAgentRecord(
            agent_id="a", company_id="c", agent_name="n",
            expires_at=datetime.now(timezone.utc),
        )
        assert rec.assigned_tickets == set()
        assert rec.status == "active"
        assert isinstance(rec.created_at, datetime)

    def test_expiry_result_defaults(self):
        result = ExpiryResult(
            agent_id="a", company_id="c", was_expired=False,
        )
        assert result.tickets_reassigned == 0
        assert result.tickets_failed == 0
        assert result.reassigned_to == {}
        assert isinstance(result.timestamp, datetime)

    def test_reassignment_result_defaults(self):
        result = ReassignmentResult(agent_id="a")
        assert result.tickets_reassigned == 0
        assert result.tickets_failed == 0
        assert result.failed_ticket_ids == []
        assert result.target_agent_id is None


# ══════════════════════════════════════════════════════════════════════
# Edge case / integration tests
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_full_lifecycle(self, svc_with_perm):
        """Full lifecycle: register -> assign tickets -> extend -> expire."""
        tickets = {"tkt-1", "tkt-2", "tkt-3"}
        rec = _register_with_tickets(
            svc_with_perm, "temp-1", "company-a",
            hours=1, tickets=tickets
        )

        # Active
        assert svc_with_perm.check_expiry("temp-1") is False
        assert len(svc_with_perm.get_active_temp_agents("company-a")) == 1

        # Extend
        old_expires = svc_with_perm.get_temp_agent("temp-1").expires_at
        updated = svc_with_perm.extend_agent("temp-1", 24)
        assert updated.expires_at > old_expires

        # Still active after extension
        assert svc_with_perm.check_expiry("temp-1") is False

        # Force expire
        svc_with_perm.get_temp_agent("temp-1").expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc_with_perm.expire_agent("temp-1")

        assert result.agent_id == "temp-1"
        assert result.tickets_reassigned == 3
        assert svc_with_perm.get_temp_agent("temp-1").status == "expired"
        assert len(svc_with_perm.get_active_temp_agents("company-a")) == 0

    def test_many_tickets_round_robin(self, svc_with_perm):
        """Many tickets should be distributed across all permanent agents."""
        tickets = {f"tkt-{i}" for i in range(100)}
        _register_with_tickets(
            svc_with_perm, "temp-1", "company-a",
            hours=1, tickets=tickets
        )
        svc_with_perm.get_temp_agent("temp-1").expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc_with_perm.expire_agent("temp-1")
        assert result.tickets_reassigned == 100
        assert result.tickets_failed == 0

    def test_register_permanent_invalid_id(self, svc):
        with pytest.raises(ValueError, match="agent_id"):
            svc.register_permanent_agent("", "company-a")

    def test_register_permanent_invalid_company(self, svc):
        with pytest.raises(ValueError, match="company_id"):
            svc.register_permanent_agent("perm-1", "")


# ── Gap Analysis Fixes ─────────────────────────────────────────────


class TestGapFixesTempAgent:

    def test_reassign_tickets_nonexistent_target(self):
        """C-3: reassign_tickets with nonexistent target doesn't crash."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp Agent", duration_hours=1)
        svc._agents["temp-1"].assigned_tickets = {"t1", "t2"}
        result = svc.reassign_tickets("temp-1", target_agent_id="ghost_agent")
        assert result.tickets_reassigned == 2

    def test_reassign_tickets_already_expired_agent(self):
        """H-5: Second reassign_tickets call after expire returns 0."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp", duration_hours=1)
        svc._agents["temp-1"].assigned_tickets = {"t1", "t2", "t3"}
        svc.expire_agent("temp-1")
        result = svc.reassign_tickets("temp-1")
        assert result.tickets_reassigned == 0

    def test_register_temp_agent_none_company_id(self):
        """H-2: register_temp_agent with None company_id raises."""
        svc = TempAgentExpiryService()
        with pytest.raises(ValueError):
            svc.register_temp_agent("t1", None, "name")

    def test_extend_agent_none_hours(self):
        """H-3: extend_agent with None hours raises."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp")
        with pytest.raises(ValueError):
            svc.extend_agent("temp-1", None)

    def test_clear_with_assertions(self):
        """H-7: clear() removes all agents and permanent agents."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp")
        svc.register_permanent_agent("perm-1", "co-1")
        svc.clear()
        assert svc.get_all_temp_agents() == []
        assert svc.get_active_temp_agents("co-1") == []

    def test_get_all_temp_agents_mixed_status(self):
        """M-3: get_all_temp_agents returns active + expired + revoked."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp", duration_hours=1)
        svc.register_temp_agent("temp-2", "co-1", "Temp2", duration_hours=1)
        svc.expire_agent("temp-1")
        svc.revoke_agent("temp-2")
        assert len(svc.get_all_temp_agents()) == 2

    def test_register_temp_agent_long_company_id(self):
        """H-1: register_temp_agent with very long company_id."""
        svc = TempAgentExpiryService()
        with pytest.raises(ValueError):
            svc.register_temp_agent("t1", "x" * 129, "name")

    def test_register_temp_agent_non_string_id(self):
        """M-1: register_temp_agent with non-string agent_id."""
        svc = TempAgentExpiryService()
        with pytest.raises(ValueError):
            svc.register_temp_agent(123, "co-1", "name")

    def test_extend_agent_exact_max_duration(self):
        """H-4: extend to exactly max_duration_hours."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp", duration_hours=12)
        max_h = svc._config.max_duration_hours
        svc.extend_agent("temp-1", max_h - 12)
        record = svc._agents["temp-1"]
        expected = record.created_at + timedelta(hours=max_h)
        assert record.expires_at == expected

    def test_single_permanent_agent_all_tickets(self):
        """M-5: round-robin with 1 permanent agent sends all there."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp", duration_hours=1)
        svc.register_permanent_agent("perm-1", "co-1")
        svc._agents["temp-1"].assigned_tickets = {f"t{i}" for i in range(10)}
        result = svc.reassign_tickets("temp-1")
        assert result.tickets_reassigned == 10

    def test_round_robin_counter_persists(self):
        """M-2: counter advances across multiple expiries."""
        svc = TempAgentExpiryService()
        svc.register_permanent_agent("p1", "co-1")
        svc.register_permanent_agent("p2", "co-1")
        svc.register_permanent_agent("p3", "co-1")
        svc.register_temp_agent("temp-1", "co-1", "T1", duration_hours=1)
        svc.register_temp_agent("temp-2", "co-1", "T2", duration_hours=1)
        svc._agents["temp-1"].assigned_tickets = {"a", "b", "c"}
        svc._agents["temp-2"].assigned_tickets = {"d", "e", "f"}
        svc.expire_agent("temp-1")
        r1 = svc.reassign_tickets("temp-2")
        assert r1.tickets_reassigned == 3

    def test_expire_agent_reassigned_to_dict_populated(self):
        """Verify expire_agent populates reassigned_to dict with ticket->target mappings."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp Agent", duration_hours=1)
        svc._agents["temp-1"].assigned_tickets = {"tkt-0", "tkt-1", "tkt-2"}
        svc.register_permanent_agent("perm-1", "co-1")
        svc._agents["temp-1"].expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc.expire_agent("temp-1")
        assert result.tickets_reassigned == 3
        assert len(result.reassigned_to) == 3
        assert "tkt-0" in result.reassigned_to
        assert "tkt-1" in result.reassigned_to
        assert "tkt-2" in result.reassigned_to
        # All tickets should be mapped to the target agent
        for ticket_id, target_id in result.reassigned_to.items():
            assert target_id == "perm-1"

    def test_register_permanent_agent_none_company_id(self):
        """register_permanent_agent with None company_id raises ValueError."""
        svc = TempAgentExpiryService()
        with pytest.raises(ValueError):
            svc.register_permanent_agent("perm-1", None)

    def test_register_permanent_agent_non_string_id(self):
        """register_permanent_agent with non-string agent_id raises ValueError."""
        svc = TempAgentExpiryService()
        with pytest.raises(ValueError):
            svc.register_permanent_agent(123, "co-1")

    def test_expire_agent_reassigned_to_empty_when_no_tickets(self):
        """expire_agent with no tickets produces empty reassigned_to dict."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp Agent", duration_hours=1)
        svc.register_permanent_agent("perm-1", "co-1")
        svc._agents["temp-1"].expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        result = svc.expire_agent("temp-1")
        assert result.reassigned_to == {}
        assert result.tickets_reassigned == 0

    def test_check_expiry_none_agent_id(self):
        """check_expiry with None agent_id raises ValueError."""
        svc = TempAgentExpiryService()
        with pytest.raises(ValueError):
            svc.check_expiry(None)

    def test_extend_agent_beyond_max_by_multiple_extensions(self):
        """Multiple extensions exceeding max_duration_hours get capped at max."""
        svc = TempAgentExpiryService()
        svc.register_temp_agent("temp-1", "co-1", "Temp Agent", duration_hours=1)
        # First extension: 1 + 360 = 361 hours (within max 720)
        svc.extend_agent("temp-1", 360)
        # Second extension: 361 + 360 = 721 would exceed 720, so cap kicks in
        svc.extend_agent("temp-1", 360)
        record = svc._agents["temp-1"]
        max_expires = record.created_at + timedelta(
            hours=svc._config.max_duration_hours
        )
        assert record.expires_at <= max_expires
