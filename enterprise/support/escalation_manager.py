"""
Enterprise Support - Escalation Manager
Manage escalations for enterprise support
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class EscalationLevel(str, Enum):
    L1 = "level_1"
    L2 = "level_2"
    L3 = "level_3"
    EXECUTIVE = "executive"


class EscalationReason(str, Enum):
    TIME_BASED = "time_based"
    PRIORITY = "priority"
    CUSTOMER_REQUEST = "customer_request"
    COMPLEXITY = "complexity"
    SLA_BREACH = "sla_breach"


class Escalation(BaseModel):
    """Escalation record"""
    escalation_id: str
    ticket_id: str
    client_id: str
    from_level: EscalationLevel
    to_level: EscalationLevel
    reason: EscalationReason
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None

    model_config = ConfigDict()


class EscalationPolicy(BaseModel):
    """Escalation policy"""
    level: EscalationLevel
    max_response_hours: int
    auto_escalate_hours: int
    notify_emails: List[str] = Field(default_factory=list)

    model_config = ConfigDict()


class EscalationManager:
    """
    Manage escalations for enterprise support.
    """

    DEFAULT_POLICIES = {
        EscalationLevel.L1: EscalationPolicy(
            level=EscalationLevel.L1,
            max_response_hours=8,
            auto_escalate_hours=4
        ),
        EscalationLevel.L2: EscalationPolicy(
            level=EscalationLevel.L2,
            max_response_hours=4,
            auto_escalate_hours=2
        ),
        EscalationLevel.L3: EscalationPolicy(
            level=EscalationLevel.L3,
            max_response_hours=2,
            auto_escalate_hours=1
        ),
        EscalationLevel.EXECUTIVE: EscalationPolicy(
            level=EscalationLevel.EXECUTIVE,
            max_response_hours=1,
            auto_escalate_hours=0
        )
    }

    def __init__(self):
        self.escalations: Dict[str, Escalation] = {}
        self.ticket_levels: Dict[str, EscalationLevel] = {}

    def escalate(
        self,
        ticket_id: str,
        client_id: str,
        reason: EscalationReason,
        notes: Optional[str] = None
    ) -> Escalation:
        """Escalate a ticket"""
        import uuid

        current_level = self.ticket_levels.get(ticket_id, EscalationLevel.L1)
        next_level = self._get_next_level(current_level)

        escalation = Escalation(
            escalation_id=f"esc_{uuid.uuid4().hex[:8]}",
            ticket_id=ticket_id,
            client_id=client_id,
            from_level=current_level,
            to_level=next_level,
            reason=reason,
            notes=notes
        )

        self.escalations[escalation.escalation_id] = escalation
        self.ticket_levels[ticket_id] = next_level

        return escalation

    def _get_next_level(self, current: EscalationLevel) -> EscalationLevel:
        """Get next escalation level"""
        levels = [EscalationLevel.L1, EscalationLevel.L2, EscalationLevel.L3, EscalationLevel.EXECUTIVE]
        try:
            idx = levels.index(current)
            return levels[min(idx + 1, len(levels) - 1)]
        except ValueError:
            return EscalationLevel.L2

    def acknowledge(self, escalation_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an escalation"""
        if escalation_id not in self.escalations:
            return False

        escalation = self.escalations[escalation_id]
        escalation.acknowledged = True
        escalation.acknowledged_at = datetime.utcnow()
        escalation.acknowledged_by = acknowledged_by
        return True

    def get_ticket_escalations(self, ticket_id: str) -> List[Escalation]:
        """Get all escalations for a ticket"""
        return [e for e in self.escalations.values() if e.ticket_id == ticket_id]

    def get_pending_escalations(self) -> List[Escalation]:
        """Get all pending escalations"""
        return [e for e in self.escalations.values() if not e.acknowledged]

    def check_auto_escalate(self, ticket_id: str, created_at: datetime) -> Optional[Escalation]:
        """Check if ticket should be auto-escalated"""
        current_level = self.ticket_levels.get(ticket_id, EscalationLevel.L1)
        policy = self.DEFAULT_POLICIES.get(current_level)

        if not policy or policy.auto_escalate_hours == 0:
            return None

        hours_elapsed = (datetime.utcnow() - created_at).total_seconds() / 3600
        if hours_elapsed >= policy.auto_escalate_hours:
            return self.escalate(
                ticket_id=ticket_id,
                client_id="system",
                reason=EscalationReason.TIME_BASED,
                notes=f"Auto-escalated after {hours_elapsed:.1f} hours"
            )

        return None
