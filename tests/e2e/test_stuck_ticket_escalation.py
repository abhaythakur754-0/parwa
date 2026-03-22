"""
E2E Test: Stuck Ticket Escalation.

Tests the 4-phase escalation system with CRITICAL verification:
- Phase 1 fires at 24h
- Phase 2 fires at 48h
- Phase 3 fires at 72h
- Phase 4 fires at 96h (final)

Escalation Phases:
- Phase 0: Normal (0-24h)
- Phase 1: Agent Notification (24h)
- Phase 2: Team Lead Escalation (48h)
- Phase 3: Manager Notification (72h)
- Phase 4: Executive Escalation (96h)
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


class EscalationPhase(str, Enum):
    """Escalation phase types."""
    PHASE_0 = "phase_0"  # Normal (0-24h)
    PHASE_1 = "phase_1"  # Agent Notification (24h)
    PHASE_2 = "phase_2"  # Team Lead Escalation (48h)
    PHASE_3 = "phase_3"  # Manager Notification (72h)
    PHASE_4 = "phase_4"  # Executive Escalation (96h)


class EscalationAction(str, Enum):
    """Escalation action types."""
    NOTIFY_AGENT = "notify_agent"
    NOTIFY_TEAM_LEAD = "notify_team_lead"
    NOTIFY_MANAGER = "notify_manager"
    NOTIFY_EXECUTIVE = "notify_executive"
    PRIORITY_BOOST = "priority_boost"
    AUTO_ESCALATE = "auto_escalate"


class EscalationPhaseConfig:
    """Configuration for an escalation phase."""

    def __init__(
        self,
        phase: EscalationPhase,
        name: str,
        hours_threshold: int,
        actions: List[EscalationAction],
        notify_targets: List[str],
        priority_boost: int = 0
    ) -> None:
        """
        Initialize phase configuration.

        Args:
            phase: Phase identifier
            name: Human-readable name
            hours_threshold: Hours threshold for this phase
            actions: Actions to take
            notify_targets: Who to notify
            priority_boost: Priority increase amount
        """
        self.phase = phase
        self.name = name
        self.hours_threshold = hours_threshold
        self.actions = actions
        self.notify_targets = notify_targets
        self.priority_boost = priority_boost


class MockEscalationLadder:
    """Mock escalation ladder for E2E testing."""

    # Phase configurations - CRITICAL thresholds
    PHASE_CONFIGS = {
        EscalationPhase.PHASE_0: EscalationPhaseConfig(
            phase=EscalationPhase.PHASE_0,
            name="Normal",
            hours_threshold=0,
            actions=[],
            notify_targets=[],
            priority_boost=0
        ),
        EscalationPhase.PHASE_1: EscalationPhaseConfig(
            phase=EscalationPhase.PHASE_1,
            name="Agent Notification",
            hours_threshold=24,  # CRITICAL: 24 hours
            actions=[EscalationAction.NOTIFY_AGENT],
            notify_targets=["agent"],
            priority_boost=1
        ),
        EscalationPhase.PHASE_2: EscalationPhaseConfig(
            phase=EscalationPhase.PHASE_2,
            name="Team Lead Escalation",
            hours_threshold=48,  # CRITICAL: 48 hours
            actions=[EscalationAction.NOTIFY_TEAM_LEAD],
            notify_targets=["agent", "team_lead"],
            priority_boost=2
        ),
        EscalationPhase.PHASE_3: EscalationPhaseConfig(
            phase=EscalationPhase.PHASE_3,
            name="Manager Notification",
            hours_threshold=72,  # CRITICAL: 72 hours
            actions=[EscalationAction.NOTIFY_MANAGER],
            notify_targets=["agent", "team_lead", "manager"],
            priority_boost=3
        ),
        EscalationPhase.PHASE_4: EscalationPhaseConfig(
            phase=EscalationPhase.PHASE_4,
            name="Executive Escalation",
            hours_threshold=96,  # Final escalation
            actions=[
                EscalationAction.NOTIFY_EXECUTIVE,
                EscalationAction.AUTO_ESCALATE
            ],
            notify_targets=["agent", "team_lead", "manager", "executive"],
            priority_boost=5
        ),
    }

    def __init__(self) -> None:
        """Initialize escalation ladder."""
        self._escalation_history: Dict[str, List[Dict[str, Any]]] = {}
        self._notifications_sent: List[Dict[str, Any]] = []

    def get_current_phase(
        self,
        ticket_created_at: datetime,
        now: Optional[datetime] = None
    ) -> EscalationPhase:
        """
        Determine current escalation phase based on ticket age.

        CRITICAL: Phases must fire at exact 24h/48h/72h thresholds.

        Args:
            ticket_created_at: When ticket was created
            now: Current time (defaults to now)

        Returns:
            Current escalation phase
        """
        if now is None:
            now = datetime.now(timezone.utc)

        hours_elapsed = (now - ticket_created_at).total_seconds() / 3600

        if hours_elapsed >= 96:
            return EscalationPhase.PHASE_4
        elif hours_elapsed >= 72:
            return EscalationPhase.PHASE_3
        elif hours_elapsed >= 48:
            return EscalationPhase.PHASE_2
        elif hours_elapsed >= 24:
            return EscalationPhase.PHASE_1
        else:
            return EscalationPhase.PHASE_0

    async def escalate(
        self,
        ticket_id: str,
        phase: EscalationPhase,
        reason: str
    ) -> Dict[str, Any]:
        """
        Escalate a ticket to a specific phase.

        Args:
            ticket_id: Ticket ID
            phase: Target phase
            reason: Escalation reason

        Returns:
            Escalation result
        """
        config = self.PHASE_CONFIGS[phase]
        escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"

        escalation_record = {
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "phase": phase.value,
            "reason": reason,
            "actions": [a.value for a in config.actions],
            "notify_targets": config.notify_targets,
            "priority_boost": config.priority_boost,
            "escalated_at": datetime.now(timezone.utc).isoformat()
        }

        # Track history
        if ticket_id not in self._escalation_history:
            self._escalation_history[ticket_id] = []
        self._escalation_history[ticket_id].append(escalation_record)

        # Send notifications
        for target in config.notify_targets:
            self._notifications_sent.append({
                "escalation_id": escalation_id,
                "target": target,
                "phase": phase.value,
                "ticket_id": ticket_id
            })

        return {
            "success": True,
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "phase": phase.value,
            "phase_name": config.name,
            "actions": [a.value for a in config.actions],
            "notify_targets": config.notify_targets,
            "priority_boost": config.priority_boost
        }

    def get_escalation_history(
        self,
        ticket_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get escalation history for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of escalation records
        """
        return self._escalation_history.get(ticket_id, [])

    def get_notifications_sent(self) -> List[Dict[str, Any]]:
        """Get all notifications sent."""
        return self._notifications_sent.copy()

    def get_phase_config(
        self,
        phase: EscalationPhase
    ) -> Optional[EscalationPhaseConfig]:
        """
        Get configuration for a phase.

        Args:
            phase: Phase to get config for

        Returns:
            Phase configuration
        """
        return self.PHASE_CONFIGS.get(phase)


class MockTicketManager:
    """Mock ticket manager for E2E testing."""

    def __init__(self, escalation_ladder: MockEscalationLadder) -> None:
        """
        Initialize ticket manager.

        Args:
            escalation_ladder: Escalation ladder instance
        """
        self._escalation_ladder = escalation_ladder
        self._tickets: Dict[str, Dict[str, Any]] = {}

    async def create_ticket(
        self,
        company_id: str,
        customer_id: str,
        subject: str,
        description: str,
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a support ticket.

        Args:
            company_id: Company ID
            customer_id: Customer ID
            subject: Ticket subject
            description: Ticket description
            created_at: Creation time (for testing past tickets)

        Returns:
            Created ticket
        """
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        ticket = {
            "ticket_id": ticket_id,
            "company_id": company_id,
            "customer_id": customer_id,
            "subject": subject,
            "description": description,
            "status": "open",
            "created_at": created_at,
            "current_phase": EscalationPhase.PHASE_0.value,
            "escalation_history": []
        }

        self._tickets[ticket_id] = ticket
        return ticket

    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a ticket by ID.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket data or None
        """
        return self._tickets.get(ticket_id)

    async def check_and_escalate(
        self,
        ticket_id: str,
        now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Check if ticket needs escalation and escalate if needed.

        CRITICAL: Escalates based on 24h/48h/72h thresholds.

        Args:
            ticket_id: Ticket ID
            now: Current time (for testing)

        Returns:
            Escalation result
        """
        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return {"success": False, "error": "Ticket not found"}

        if now is None:
            now = datetime.now(timezone.utc)

        current_phase = self._escalation_ladder.get_current_phase(
            ticket["created_at"],
            now
        )

        # Check if already escalated to this phase
        current_ticket_phase = EscalationPhase(ticket["current_phase"])

        # Determine if we need to escalate
        if current_phase.value > current_ticket_phase.value:
            # Need to escalate through all intermediate phases
            results = []
            for phase in [
                EscalationPhase.PHASE_1,
                EscalationPhase.PHASE_2,
                EscalationPhase.PHASE_3,
                EscalationPhase.PHASE_4
            ]:
                if phase.value > current_ticket_phase.value and \
                   phase.value <= current_phase.value:
                    result = await self._escalation_ladder.escalate(
                        ticket_id=ticket_id,
                        phase=phase,
                        reason=f"Auto-escalation at {phase.value}"
                    )
                    results.append(result)
                    ticket["current_phase"] = phase.value
                    ticket["escalation_history"].append(result)

            return {
                "success": True,
                "ticket_id": ticket_id,
                "escalated_to": current_phase.value,
                "escalations": results
            }

        return {
            "success": True,
            "ticket_id": ticket_id,
            "escalated": False,
            "current_phase": current_phase.value,
            "message": "No escalation needed"
        }


@pytest.fixture
def escalation_ladder():
    """Create escalation ladder fixture."""
    return MockEscalationLadder()


@pytest.fixture
def ticket_manager(escalation_ladder):
    """Create ticket manager fixture."""
    return MockTicketManager(escalation_ladder)


class TestE2EEscalationPhaseDetection:
    """E2E tests for escalation phase detection - CRITICAL thresholds."""

    def test_phase_1_fires_at_24h(self, escalation_ladder):
        """CRITICAL: Phase 1 fires at exactly 24 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=24)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_1, \
            f"Expected PHASE_1 at 24h, got {phase}"

    def test_phase_2_fires_at_48h(self, escalation_ladder):
        """CRITICAL: Phase 2 fires at exactly 48 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=48)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_2, \
            f"Expected PHASE_2 at 48h, got {phase}"

    def test_phase_3_fires_at_72h(self, escalation_ladder):
        """CRITICAL: Phase 3 fires at exactly 72 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=72)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_3, \
            f"Expected PHASE_3 at 72h, got {phase}"

    def test_phase_4_fires_at_96h(self, escalation_ladder):
        """CRITICAL: Phase 4 (final) fires at 96 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=96)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_4, \
            f"Expected PHASE_4 at 96h, got {phase}"

    def test_phase_0_for_new_ticket(self, escalation_ladder):
        """Test Phase 0 for new ticket (under 24h)."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=12)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_0

    def test_phase_1_just_over_24h(self, escalation_ladder):
        """Test Phase 1 fires just over 24 hours."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=25)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_1

    def test_phase_4_for_very_old_ticket(self, escalation_ladder):
        """Test Phase 4 for very old ticket (over 96h)."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=200)

        phase = escalation_ladder.get_current_phase(created_at, now)

        assert phase == EscalationPhase.PHASE_4


class TestE2EEscalationActions:
    """E2E tests for escalation actions."""

    @pytest.mark.asyncio
    async def test_phase_1_notifies_agent(self, escalation_ladder):
        """Test Phase 1 notifies agent."""
        result = await escalation_ladder.escalate(
            ticket_id="TKT-001",
            phase=EscalationPhase.PHASE_1,
            reason="No response in 24 hours"
        )

        assert result["success"] is True
        assert "agent" in result["notify_targets"]
        assert result["priority_boost"] == 1

    @pytest.mark.asyncio
    async def test_phase_2_notifies_team_lead(self, escalation_ladder):
        """Test Phase 2 notifies team lead."""
        result = await escalation_ladder.escalate(
            ticket_id="TKT-002",
            phase=EscalationPhase.PHASE_2,
            reason="No response in 48 hours"
        )

        assert result["success"] is True
        assert "team_lead" in result["notify_targets"]
        assert result["priority_boost"] == 2

    @pytest.mark.asyncio
    async def test_phase_3_notifies_manager(self, escalation_ladder):
        """Test Phase 3 notifies manager."""
        result = await escalation_ladder.escalate(
            ticket_id="TKT-003",
            phase=EscalationPhase.PHASE_3,
            reason="No response in 72 hours"
        )

        assert result["success"] is True
        assert "manager" in result["notify_targets"]
        assert result["priority_boost"] == 3

    @pytest.mark.asyncio
    async def test_phase_4_notifies_executive(self, escalation_ladder):
        """Test Phase 4 notifies executive."""
        result = await escalation_ladder.escalate(
            ticket_id="TKT-004",
            phase=EscalationPhase.PHASE_4,
            reason="Critical escalation"
        )

        assert result["success"] is True
        assert "executive" in result["notify_targets"]
        assert result["priority_boost"] == 5


class TestE2EStuckTicketWorkflow:
    """E2E tests for complete stuck ticket escalation workflow."""

    @pytest.mark.asyncio
    async def test_ticket_stuck_24h_escalates_phase_1(
        self,
        ticket_manager,
        escalation_ladder
    ):
        """
        E2E: Ticket stuck for 24h → Phase 1 escalation.

        Steps:
        1. Create ticket
        2. Simulate 24 hours passing
        3. Check and escalate
        4. Verify Phase 1 escalation
        """
        # Step 1: Create ticket
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=24)

        ticket = await ticket_manager.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Stuck ticket",
            description="This ticket is stuck",
            created_at=created_at
        )

        # Step 2: Check and escalate at 24h
        result = await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        # Step 3: Verify Phase 1 escalation
        assert result["success"] is True
        assert "escalated_to" in result, f"Expected escalated_to in result: {result}"
        assert result["escalated_to"] == EscalationPhase.PHASE_1.value

        # Verify history
        history = escalation_ladder.get_escalation_history(ticket["ticket_id"])
        assert len(history) == 1
        assert history[0]["phase"] == EscalationPhase.PHASE_1.value

    @pytest.mark.asyncio
    async def test_ticket_stuck_48h_escalates_phase_2(
        self,
        ticket_manager,
        escalation_ladder
    ):
        """
        E2E: Ticket stuck for 48h → Phase 2 escalation.

        CRITICAL: Should escalate through Phase 1 to Phase 2.
        """
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=48)

        ticket = await ticket_manager.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Very stuck ticket",
            description="This ticket is very stuck",
            created_at=created_at
        )

        result = await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        assert result["success"] is True
        assert result["escalated_to"] == EscalationPhase.PHASE_2.value

        # Verify both Phase 1 and Phase 2 escalations
        history = escalation_ladder.get_escalation_history(ticket["ticket_id"])
        assert len(history) == 2

        phases = [h["phase"] for h in history]
        assert EscalationPhase.PHASE_1.value in phases
        assert EscalationPhase.PHASE_2.value in phases

    @pytest.mark.asyncio
    async def test_ticket_stuck_72h_escalates_phase_3(
        self,
        ticket_manager,
        escalation_ladder
    ):
        """
        E2E: Ticket stuck for 72h → Phase 3 escalation.

        CRITICAL: Should escalate through Phases 1, 2 to Phase 3.
        """
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=72)

        ticket = await ticket_manager.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Extremely stuck ticket",
            description="This ticket is extremely stuck",
            created_at=created_at
        )

        result = await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        assert result["success"] is True
        assert result["escalated_to"] == EscalationPhase.PHASE_3.value

        # Verify Phases 1, 2, and 3 escalations
        history = escalation_ladder.get_escalation_history(ticket["ticket_id"])
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_ticket_stuck_96h_escalates_phase_4(
        self,
        ticket_manager,
        escalation_ladder
    ):
        """
        E2E: Ticket stuck for 96h → Phase 4 (final) escalation.

        CRITICAL: Should escalate through all phases to Phase 4.
        """
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=96)

        ticket = await ticket_manager.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Critical stuck ticket",
            description="This ticket needs executive attention",
            created_at=created_at
        )

        result = await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        assert result["success"] is True
        assert result["escalated_to"] == EscalationPhase.PHASE_4.value

        # Verify all 4 phases
        history = escalation_ladder.get_escalation_history(ticket["ticket_id"])
        assert len(history) == 4

        phases = [h["phase"] for h in history]
        assert EscalationPhase.PHASE_1.value in phases
        assert EscalationPhase.PHASE_2.value in phases
        assert EscalationPhase.PHASE_3.value in phases
        assert EscalationPhase.PHASE_4.value in phases


class TestE2EEscalationNotifications:
    """E2E tests for escalation notifications."""

    @pytest.mark.asyncio
    async def test_notifications_sent_correctly(
        self,
        ticket_manager,
        escalation_ladder
    ):
        """Test notifications are sent to correct targets."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=72)

        ticket = await ticket_manager.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Notification test",
            description="Test notifications",
            created_at=created_at
        )

        await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        notifications = escalation_ladder.get_notifications_sent()

        # Should have notifications for Phase 1, 2, 3
        assert len(notifications) >= 6  # 1 + 2 + 3 = 6 notifications

        targets = [n["target"] for n in notifications]
        assert "agent" in targets
        assert "team_lead" in targets
        assert "manager" in targets


class TestE2EEscalationHistory:
    """E2E tests for escalation history tracking."""

    @pytest.mark.asyncio
    async def test_history_tracks_escalation_order(
        self,
        escalation_ladder
    ):
        """Test that history tracks escalation order correctly."""
        ticket_id = "TKT-HISTORY"

        # Escalate through phases
        await escalation_ladder.escalate(
            ticket_id=ticket_id,
            phase=EscalationPhase.PHASE_1,
            reason="First"
        )
        await escalation_ladder.escalate(
            ticket_id=ticket_id,
            phase=EscalationPhase.PHASE_2,
            reason="Second"
        )
        await escalation_ladder.escalate(
            ticket_id=ticket_id,
            phase=EscalationPhase.PHASE_3,
            reason="Third"
        )

        history = escalation_ladder.get_escalation_history(ticket_id)

        assert len(history) == 3

        # Verify order
        assert history[0]["phase"] == EscalationPhase.PHASE_1.value
        assert history[1]["phase"] == EscalationPhase.PHASE_2.value
        assert history[2]["phase"] == EscalationPhase.PHASE_3.value

    @pytest.mark.asyncio
    async def test_history_includes_timestamps(
        self,
        escalation_ladder
    ):
        """Test that history includes timestamps."""
        ticket_id = "TKT-TIMESTAMPS"

        await escalation_ladder.escalate(
            ticket_id=ticket_id,
            phase=EscalationPhase.PHASE_1,
            reason="Test"
        )

        history = escalation_ladder.get_escalation_history(ticket_id)

        assert len(history) == 1
        assert "escalated_at" in history[0]


class TestE2EEscalationEdgeCases:
    """E2E tests for escalation edge cases."""

    @pytest.mark.asyncio
    async def test_no_escalation_for_new_ticket(
        self,
        ticket_manager,
        escalation_ladder
    ):
        """Test that new tickets don't get escalated."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=1)

        ticket = await ticket_manager.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="New ticket",
            description="This is a new ticket",
            created_at=created_at
        )

        result = await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        assert result["escalated"] is False
        assert result["current_phase"] == EscalationPhase.PHASE_0.value

    @pytest.mark.asyncio
    async def test_already_escalated_ticket(
        self,
        ticket_manager,
        escalation_ladder
    ):
        """Test that already escalated tickets don't re-escalate."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(hours=25)

        ticket = await ticket_manager.create_ticket(
            company_id="company-123",
            customer_id="customer-456",
            subject="Already escalated",
            description="This ticket was already escalated",
            created_at=created_at
        )

        # First escalation
        await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        history1 = escalation_ladder.get_escalation_history(ticket["ticket_id"])

        # Check again (should not re-escalate)
        await ticket_manager.check_and_escalate(
            ticket_id=ticket["ticket_id"],
            now=now
        )

        history2 = escalation_ladder.get_escalation_history(ticket["ticket_id"])

        # Should be same length
        assert len(history1) == len(history2)
