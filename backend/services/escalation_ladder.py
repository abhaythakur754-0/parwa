"""
Escalation Ladder Service.

Implements a 4-phase escalation ladder for ticket management.
Phases fire at exact 24h/48h/72h/final thresholds.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EscalationPhase(int, Enum):
    """Escalation phase levels."""
    PHASE_0 = 0  # Initial (no escalation)
    PHASE_1 = 1  # 24 hours - Agent notification
    PHASE_2 = 2  # 48 hours - Team lead escalation
    PHASE_3 = 3  # 72 hours - Manager notification
    PHASE_4 = 4  # Final - Executive escalation


class EscalationAction(str, Enum):
    """Actions to take during escalation."""
    NOTIFY_AGENT = "notify_agent"
    NOTIFY_TEAM_LEAD = "notify_team_lead"
    NOTIFY_MANAGER = "notify_manager"
    NOTIFY_EXECUTIVE = "notify_executive"
    AUTO_ASSIGN = "auto_assign"
    INCREASE_PRIORITY = "increase_priority"
    ADD_TO_QUEUE = "add_to_queue"
    SEND_SLA_ALERT = "send_sla_alert"


@dataclass
class EscalationPhaseConfig:
    """Configuration for an escalation phase."""
    phase: EscalationPhase
    hours_threshold: float
    name: str
    description: str
    actions: List[EscalationAction]
    notify_targets: List[str]
    priority_boost: int = 0
    auto_assign: bool = False


# Phase configurations
ESCALATION_PHASES: Dict[EscalationPhase, EscalationPhaseConfig] = {
    EscalationPhase.PHASE_0: EscalationPhaseConfig(
        phase=EscalationPhase.PHASE_0,
        hours_threshold=0,
        name="Initial",
        description="Ticket just created, no escalation",
        actions=[],
        notify_targets=[],
    ),
    EscalationPhase.PHASE_1: EscalationPhaseConfig(
        phase=EscalationPhase.PHASE_1,
        hours_threshold=24,
        name="Agent Notification",
        description="24 hours - First escalation to assigned agent",
        actions=[
            EscalationAction.NOTIFY_AGENT,
            EscalationAction.SEND_SLA_ALERT,
        ],
        notify_targets=["assigned_agent"],
        priority_boost=1,
    ),
    EscalationPhase.PHASE_2: EscalationPhaseConfig(
        phase=EscalationPhase.PHASE_2,
        hours_threshold=48,
        name="Team Lead Escalation",
        description="48 hours - Escalate to team lead",
        actions=[
            EscalationAction.NOTIFY_AGENT,
            EscalationAction.NOTIFY_TEAM_LEAD,
            EscalationAction.INCREASE_PRIORITY,
        ],
        notify_targets=["assigned_agent", "team_lead"],
        priority_boost=2,
    ),
    EscalationPhase.PHASE_3: EscalationPhaseConfig(
        phase=EscalationPhase.PHASE_3,
        hours_threshold=72,
        name="Manager Notification",
        description="72 hours - Manager notification",
        actions=[
            EscalationAction.NOTIFY_AGENT,
            EscalationAction.NOTIFY_TEAM_LEAD,
            EscalationAction.NOTIFY_MANAGER,
            EscalationAction.INCREASE_PRIORITY,
        ],
        notify_targets=["assigned_agent", "team_lead", "manager"],
        priority_boost=3,
    ),
    EscalationPhase.PHASE_4: EscalationPhaseConfig(
        phase=EscalationPhase.PHASE_4,
        hours_threshold=96,
        name="Executive Escalation",
        description="Final - Executive escalation",
        actions=[
            EscalationAction.NOTIFY_AGENT,
            EscalationAction.NOTIFY_TEAM_LEAD,
            EscalationAction.NOTIFY_MANAGER,
            EscalationAction.NOTIFY_EXECUTIVE,
            EscalationAction.INCREASE_PRIORITY,
            EscalationAction.ADD_TO_QUEUE,
        ],
        notify_targets=["assigned_agent", "team_lead", "manager", "executive"],
        priority_boost=5,
        auto_assign=True,
    ),
}


class EscalationLadder:
    """
    Escalation Ladder for ticket management.

    Implements a 4-phase escalation system:
    - Phase 1 (24h): Agent notification
    - Phase 2 (48h): Team lead escalation
    - Phase 3 (72h): Manager notification
    - Phase 4 (Final): Executive escalation

    CRITICAL: Phases fire at EXACT thresholds.
    """

    def __init__(self, custom_phases: Optional[Dict[EscalationPhase, EscalationPhaseConfig]] = None) -> None:
        """
        Initialize escalation ladder.

        Args:
            custom_phases: Optional custom phase configurations
        """
        self.phases = custom_phases or ESCALATION_PHASES
        self._escalation_history: Dict[str, List[Dict[str, Any]]] = {}

    def get_current_phase(
        self,
        ticket_created_at: datetime,
        now: Optional[datetime] = None
    ) -> EscalationPhase:
        """
        Get current escalation phase based on ticket age.

        CRITICAL: Phase is determined by exact hour thresholds.

        Args:
            ticket_created_at: When the ticket was created
            now: Current time (defaults to now in UTC)

        Returns:
            Current escalation phase
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure both datetimes are timezone-aware
        if ticket_created_at.tzinfo is None:
            ticket_created_at = ticket_created_at.replace(tzinfo=timezone.utc)

        elapsed = now - ticket_created_at
        hours_elapsed = elapsed.total_seconds() / 3600

        # Determine phase based on thresholds
        if hours_elapsed >= self.phases[EscalationPhase.PHASE_4].hours_threshold:
            return EscalationPhase.PHASE_4
        elif hours_elapsed >= self.phases[EscalationPhase.PHASE_3].hours_threshold:
            return EscalationPhase.PHASE_3
        elif hours_elapsed >= self.phases[EscalationPhase.PHASE_2].hours_threshold:
            return EscalationPhase.PHASE_2
        elif hours_elapsed >= self.phases[EscalationPhase.PHASE_1].hours_threshold:
            return EscalationPhase.PHASE_1
        else:
            return EscalationPhase.PHASE_0

    def get_next_escalation(
        self,
        ticket_id: str,
        ticket_created_at: datetime,
        now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get the next escalation action for a ticket.

        Args:
            ticket_id: Ticket identifier
            ticket_created_at: When the ticket was created
            now: Current time

        Returns:
            Dict with next escalation details
        """
        current_phase = self.get_current_phase(ticket_created_at, now)
        phase_config = self.phases.get(current_phase)

        if not phase_config or current_phase == EscalationPhase.PHASE_0:
            return {
                "ticket_id": ticket_id,
                "current_phase": current_phase.value,
                "next_phase": None,
                "hours_until_next": None,
                "action_required": False,
            }

        # Calculate hours until next phase
        next_phase = None
        hours_until_next = None

        if current_phase.value < EscalationPhase.PHASE_4.value:
            next_phase_value = EscalationPhase(current_phase.value + 1)
            next_phase_config = self.phases.get(next_phase_value)

            if next_phase_config:
                next_phase = next_phase_value
                if now is None:
                    now = datetime.now(timezone.utc)

                if ticket_created_at.tzinfo is None:
                    ticket_created_at = ticket_created_at.replace(tzinfo=timezone.utc)

                elapsed = now - ticket_created_at
                hours_elapsed = elapsed.total_seconds() / 3600
                hours_until_next = next_phase_config.hours_threshold - hours_elapsed

        return {
            "ticket_id": ticket_id,
            "current_phase": current_phase.value,
            "current_phase_name": phase_config.name,
            "next_phase": next_phase.value if next_phase else None,
            "next_phase_name": self.phases[next_phase].name if next_phase else None,
            "hours_until_next": max(0, hours_until_next) if hours_until_next else None,
            "action_required": True,
            "actions": [a.value for a in phase_config.actions],
            "notify_targets": phase_config.notify_targets,
            "priority_boost": phase_config.priority_boost,
        }

    async def escalate(
        self,
        ticket_id: str,
        phase: EscalationPhase,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Escalate a ticket to a specific phase.

        Args:
            ticket_id: Ticket identifier
            phase: Target escalation phase
            reason: Reason for escalation

        Returns:
            Dict with escalation result
        """
        phase_config = self.phases.get(phase)

        if not phase_config:
            return {
                "success": False,
                "error": f"Invalid phase: {phase}",
                "ticket_id": ticket_id,
            }

        now = datetime.now(timezone.utc)

        escalation_record = {
            "ticket_id": ticket_id,
            "phase": phase.value,
            "phase_name": phase_config.name,
            "reason": reason,
            "escalated_at": now.isoformat(),
            "actions_taken": [a.value for a in phase_config.actions],
            "notified": phase_config.notify_targets,
        }

        # Track escalation history
        if ticket_id not in self._escalation_history:
            self._escalation_history[ticket_id] = []
        self._escalation_history[ticket_id].append(escalation_record)

        logger.warning({
            "event": "ticket_escalated",
            "ticket_id": ticket_id,
            "phase": phase.value,
            "phase_name": phase_config.name,
            "reason": reason,
        })

        return {
            "success": True,
            "ticket_id": ticket_id,
            "phase": phase.value,
            "phase_name": phase_config.name,
            "description": phase_config.description,
            "actions": [a.value for a in phase_config.actions],
            "notify_targets": phase_config.notify_targets,
            "priority_boost": phase_config.priority_boost,
            "escalated_at": now.isoformat(),
        }

    def get_escalation_history(self, ticket_id: str) -> List[Dict[str, Any]]:
        """
        Get escalation history for a ticket.

        Args:
            ticket_id: Ticket identifier

        Returns:
            List of escalation records
        """
        return self._escalation_history.get(ticket_id, [])

    def get_phase_config(self, phase: EscalationPhase) -> Optional[EscalationPhaseConfig]:
        """
        Get configuration for a specific phase.

        Args:
            phase: Escalation phase

        Returns:
            Phase configuration or None
        """
        return self.phases.get(phase)

    def get_all_phases(self) -> List[Dict[str, Any]]:
        """
        Get all phase configurations.

        Returns:
            List of phase configurations
        """
        return [
            {
                "phase": config.phase.value,
                "name": config.name,
                "description": config.description,
                "hours_threshold": config.hours_threshold,
                "actions": [a.value for a in config.actions],
                "notify_targets": config.notify_targets,
                "priority_boost": config.priority_boost,
            }
            for config in self.phases.values()
        ]

    def calculate_hours_in_phase(
        self,
        ticket_created_at: datetime,
        phase: EscalationPhase,
        now: Optional[datetime] = None
    ) -> float:
        """
        Calculate how many hours a ticket has been in a specific phase.

        Args:
            ticket_created_at: When the ticket was created
            phase: The phase to calculate for
            now: Current time

        Returns:
            Hours in the phase
        """
        if now is None:
            now = datetime.now(timezone.utc)

        if ticket_created_at.tzinfo is None:
            ticket_created_at = ticket_created_at.replace(tzinfo=timezone.utc)

        elapsed = now - ticket_created_at
        hours_elapsed = elapsed.total_seconds() / 3600

        phase_config = self.phases.get(phase)
        if not phase_config:
            return 0.0

        return max(0, hours_elapsed - phase_config.hours_threshold)

    def should_escalate(
        self,
        ticket_created_at: datetime,
        current_phase: EscalationPhase,
        now: Optional[datetime] = None
    ) -> bool:
        """
        Check if a ticket should be escalated to the next phase.

        Args:
            ticket_created_at: When the ticket was created
            current_phase: Current escalation phase
            now: Current time

        Returns:
            True if ticket should escalate
        """
        actual_phase = self.get_current_phase(ticket_created_at, now)
        return actual_phase.value > current_phase.value


def get_escalation_ladder() -> EscalationLadder:
    """Factory function to get escalation ladder instance."""
    return EscalationLadder()
