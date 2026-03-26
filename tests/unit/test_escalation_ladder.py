"""
Unit tests for Escalation Ladder Service.

CRITICAL TESTS:
- Phase 1 fires at 24h
- Phase 2 fires at 48h
- Phase 3 fires at 72h
- Phase 4 is final
"""
import pytest
from datetime import datetime, timezone, timedelta

from backend.services.escalation_ladder import (
    EscalationLadder,
    EscalationPhase,
    EscalationAction,
    EscalationPhaseConfig,
    ESCALATION_PHASES,
    get_escalation_ladder,
)


@pytest.fixture
def escalation_ladder():
    """Create escalation ladder instance."""
    return EscalationLadder()


class TestEscalationLadderPhaseDetection:
    """Tests for phase detection based on time."""

    def test_phase_0_new_ticket(self, escalation_ladder):
        """Test that new ticket is in Phase 0."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=1)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_0

    def test_phase_1_fires_at_24h(self, escalation_ladder):
        """CRITICAL: Phase 1 fires at 24 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=24)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_1

    def test_phase_1_fires_just_over_24h(self, escalation_ladder):
        """Test Phase 1 fires just over 24 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=25)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_1

    def test_phase_2_fires_at_48h(self, escalation_ladder):
        """CRITICAL: Phase 2 fires at 48 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=48)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_2

    def test_phase_3_fires_at_72h(self, escalation_ladder):
        """CRITICAL: Phase 3 fires at 72 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=72)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_3

    def test_phase_4_fires_at_96h(self, escalation_ladder):
        """CRITICAL: Phase 4 (final) fires at 96 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=96)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_4

    def test_phase_4_is_final_for_very_old_tickets(self, escalation_ladder):
        """Test that very old tickets stay in Phase 4."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=200)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_4


class TestEscalationLadderNextEscalation:
    """Tests for get_next_escalation method."""

    @pytest.mark.asyncio
    async def test_next_escalation_from_phase_0(self, escalation_ladder):
        """Test next escalation from Phase 0."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=1)

        result = escalation_ladder.get_next_escalation(
            ticket_id="ticket-123",
            ticket_created_at=created_at,
            now=now,
        )

        assert result["current_phase"] == EscalationPhase.PHASE_0.value
        assert result["next_phase"] == EscalationPhase.PHASE_1.value
        assert result["hours_until_next"] > 20  # ~23 hours remaining

    @pytest.mark.asyncio
    async def test_next_escalation_from_phase_1(self, escalation_ladder):
        """Test next escalation from Phase 1."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=30)

        result = escalation_ladder.get_next_escalation(
            ticket_id="ticket-123",
            ticket_created_at=created_at,
            now=now,
        )

        assert result["current_phase"] == EscalationPhase.PHASE_1.value
        assert result["next_phase"] == EscalationPhase.PHASE_2.value

    @pytest.mark.asyncio
    async def test_no_next_escalation_from_phase_4(self, escalation_ladder):
        """Test no next escalation from Phase 4 (final)."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=100)

        result = escalation_ladder.get_next_escalation(
            ticket_id="ticket-123",
            ticket_created_at=created_at,
            now=now,
        )

        assert result["current_phase"] == EscalationPhase.PHASE_4.value
        assert result["next_phase"] is None


class TestEscalationLadderEscalate:
    """Tests for escalate method."""

    @pytest.mark.asyncio
    async def test_escalate_to_phase_1(self, escalation_ladder):
        """Test escalating to Phase 1."""
        result = await escalation_ladder.escalate(
            ticket_id="ticket-123",
            phase=EscalationPhase.PHASE_1,
            reason="No response in 24 hours",
        )

        assert result["success"] is True
        assert result["phase"] == EscalationPhase.PHASE_1.value
        assert "notify_agent" in result["actions"]

    @pytest.mark.asyncio
    async def test_escalate_to_phase_2(self, escalation_ladder):
        """Test escalating to Phase 2."""
        result = await escalation_ladder.escalate(
            ticket_id="ticket-123",
            phase=EscalationPhase.PHASE_2,
            reason="No response in 48 hours",
        )

        assert result["success"] is True
        assert result["phase"] == EscalationPhase.PHASE_2.value
        assert "team_lead" in result["notify_targets"]

    @pytest.mark.asyncio
    async def test_escalate_to_phase_3(self, escalation_ladder):
        """Test escalating to Phase 3."""
        result = await escalation_ladder.escalate(
            ticket_id="ticket-123",
            phase=EscalationPhase.PHASE_3,
            reason="No response in 72 hours",
        )

        assert result["success"] is True
        assert result["phase"] == EscalationPhase.PHASE_3.value
        assert "manager" in result["notify_targets"]

    @pytest.mark.asyncio
    async def test_escalate_to_phase_4_final(self, escalation_ladder):
        """Test escalating to Phase 4 (final)."""
        result = await escalation_ladder.escalate(
            ticket_id="ticket-123",
            phase=EscalationPhase.PHASE_4,
            reason="Critical escalation required",
        )

        assert result["success"] is True
        assert result["phase"] == EscalationPhase.PHASE_4.value
        assert "executive" in result["notify_targets"]
        assert result["priority_boost"] == 5


class TestEscalationLadderShouldEscalate:
    """Tests for should_escalate method."""

    def test_should_escalate_true(self, escalation_ladder):
        """Test should_escalate returns True when phase changes."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=25)

        should = escalation_ladder.should_escalate(
            ticket_created_at=created_at,
            current_phase=EscalationPhase.PHASE_0,
            now=now,
        )

        assert should is True

    def test_should_escalate_false_same_phase(self, escalation_ladder):
        """Test should_escalate returns False when same phase."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=25)

        should = escalation_ladder.should_escalate(
            ticket_created_at=created_at,
            current_phase=EscalationPhase.PHASE_1,
            now=now,
        )

        assert should is False


class TestEscalationLadderPhaseConfig:
    """Tests for phase configuration."""

    def test_phase_1_config_correct(self, escalation_ladder):
        """Test Phase 1 configuration is correct."""
        config = escalation_ladder.get_phase_config(EscalationPhase.PHASE_1)

        assert config is not None
        assert config.hours_threshold == 24
        assert config.name == "Agent Notification"
        assert EscalationAction.NOTIFY_AGENT in config.actions

    def test_phase_2_config_correct(self, escalation_ladder):
        """Test Phase 2 configuration is correct."""
        config = escalation_ladder.get_phase_config(EscalationPhase.PHASE_2)

        assert config is not None
        assert config.hours_threshold == 48
        assert config.name == "Team Lead Escalation"
        assert EscalationAction.NOTIFY_TEAM_LEAD in config.actions

    def test_phase_3_config_correct(self, escalation_ladder):
        """Test Phase 3 configuration is correct."""
        config = escalation_ladder.get_phase_config(EscalationPhase.PHASE_3)

        assert config is not None
        assert config.hours_threshold == 72
        assert config.name == "Manager Notification"
        assert EscalationAction.NOTIFY_MANAGER in config.actions

    def test_phase_4_config_correct(self, escalation_ladder):
        """Test Phase 4 configuration is correct."""
        config = escalation_ladder.get_phase_config(EscalationPhase.PHASE_4)

        assert config is not None
        assert config.hours_threshold == 96
        assert config.name == "Executive Escalation"
        assert EscalationAction.NOTIFY_EXECUTIVE in config.actions


class TestEscalationLadderHistory:
    """Tests for escalation history tracking."""

    @pytest.mark.asyncio
    async def test_escalation_history_tracked(self, escalation_ladder):
        """Test that escalation history is tracked."""
        await escalation_ladder.escalate(
            ticket_id="ticket-123",
            phase=EscalationPhase.PHASE_1,
            reason="Test escalation",
        )

        history = escalation_ladder.get_escalation_history("ticket-123")

        assert len(history) == 1
        assert history[0]["phase"] == EscalationPhase.PHASE_1.value

    @pytest.mark.asyncio
    async def test_multiple_escalations_tracked(self, escalation_ladder):
        """Test that multiple escalations are tracked."""
        await escalation_ladder.escalate(
            ticket_id="ticket-123",
            phase=EscalationPhase.PHASE_1,
            reason="First escalation",
        )
        await escalation_ladder.escalate(
            ticket_id="ticket-123",
            phase=EscalationPhase.PHASE_2,
            reason="Second escalation",
        )

        history = escalation_ladder.get_escalation_history("ticket-123")

        assert len(history) == 2


class TestEscalationLadderFactory:
    """Tests for factory function."""

    def test_get_escalation_ladder_returns_instance(self):
        """Test factory returns ladder instance."""
        ladder = get_escalation_ladder()

        assert isinstance(ladder, EscalationLadder)
