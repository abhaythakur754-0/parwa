"""
PARWA High SLA Agent.

SLA breach detection and management agent.
Integrates with shared/compliance/sla_calculator.py for breach calculations.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from shared.compliance.sla_calculator import (
    SLACalculator,
    SLATier,
    SLAType,
    SLABreachStatus,
    get_sla_calculator,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EscalationPhase(str, Enum):
    """SLA escalation phases."""
    PHASE_1 = "phase_1"  # 24 hours - Warning
    PHASE_2 = "phase_2"  # 48 hours - Escalation
    PHASE_3 = "phase_3"  # 72 hours - Manager notified
    PHASE_4 = "phase_4"  # 96+ hours - Executive escalation


@dataclass
class SLABreachRecord:
    """Record of an SLA breach."""
    breach_id: str
    ticket_id: str
    sla_type: SLAType
    tier: SLATier
    status: SLABreachStatus
    breach_duration_hours: float
    escalation_phase: EscalationPhase
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class ParwaHighSLAAgent(BaseAgent):
    """
    PARWA High SLA Agent.

    Provides SLA management capabilities including:
    - SLA breach detection
    - Multi-phase escalation (24h/48h/72h/96h)
    - Breach tracking and reporting
    - Integration with SLACalculator

    Escalation Phases:
    - Phase 1 (24h): Warning notification
    - Phase 2 (48h): Team lead escalation
    - Phase 3 (72h): Manager notification
    - Phase 4 (96h+): Executive escalation
    """

    # PARWA High specific settings
    PARWA_HIGH_ESCALATION_THRESHOLD = 0.50

    # Escalation timing (hours)
    ESCALATION_PHASES = {
        EscalationPhase.PHASE_1: 24,
        EscalationPhase.PHASE_2: 48,
        EscalationPhase.PHASE_3: 72,
        EscalationPhase.PHASE_4: 96,
    }

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        sla_calculator: Optional[SLACalculator] = None,
    ) -> None:
        """
        Initialize PARWA High SLA Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            sla_calculator: Optional SLACalculator instance
        """
        super().__init__(agent_id, config, company_id)

        self._sla_calculator = sla_calculator or get_sla_calculator()
        self._breach_records: Dict[str, SLABreachRecord] = {}
        self._escalation_queue: List[str] = []

        logger.info({
            "event": "parwa_high_sla_agent_initialized",
            "agent_id": agent_id,
            "tier": self.get_tier(),
            "variant": self.get_variant(),
        })

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA High uses 'heavy'."""
        return "heavy"

    def get_variant(self) -> str:
        """Get the PARWA High variant for this agent."""
        return "parwa_high"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process SLA request.

        Args:
            input_data: Must contain 'action' key
                - 'check_sla': Check SLA status for a ticket
                - 'detect_breach': Detect SLA breach
                - 'escalate_breach': Escalate a breach
                - 'acknowledge': Acknowledge a breach
                - 'get_stats': Get SLA statistics

        Returns:
            AgentResponse with processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_high_sla_process", {
            "action": action,
            "tier": self.get_tier(),
        })

        if action == "check_sla":
            return await self._handle_check_sla(input_data)
        elif action == "detect_breach":
            return await self._handle_detect_breach(input_data)
        elif action == "escalate_breach":
            return await self._handle_escalate_breach(input_data)
        elif action == "acknowledge":
            return await self._handle_acknowledge(input_data)
        elif action == "get_stats":
            return await self._handle_get_stats()
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def check_sla_status(
        self,
        ticket_id: str,
        tier: str = "standard",
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Check SLA status for a ticket.

        Args:
            ticket_id: Ticket identifier
            tier: SLA tier (critical, high, standard, low)
            created_at: Ticket creation time (defaults to now for demo)

        Returns:
            Dict with SLA status for each SLA type
        """
        if created_at is None:
            created_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # Map tier string to enum
        tier_map = {
            "critical": SLATier.CRITICAL,
            "high": SLATier.HIGH,
            "standard": SLATier.STANDARD,
            "low": SLATier.LOW,
        }
        sla_tier = tier_map.get(tier.lower(), SLATier.STANDARD)

        # Check all SLA types
        results = self._sla_calculator.check_breach(
            ticket_id=ticket_id,
            tier=sla_tier,
            created_at=created_at,
        )

        # Convert to dict format
        status = {}
        for sla_type, result in results.items():
            status[sla_type.value] = {
                "status": result.status.value,
                "is_breached": result.is_breached,
                "is_warning": result.is_warning,
                "time_elapsed_hours": result.time_elapsed_hours,
                "time_remaining_hours": result.time_remaining_hours,
                "percentage_used": result.percentage_used,
                "should_escalate": result.should_escalate,
            }

        return {
            "ticket_id": ticket_id,
            "tier": tier,
            "sla_status": status,
            "any_breached": any(s["is_breached"] for s in status.values()),
            "any_warning": any(s["is_warning"] for s in status.values()),
        }

    async def detect_breach(
        self,
        ticket_id: str,
        tier: str = "standard",
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Detect SLA breach for a ticket.

        Args:
            ticket_id: Ticket identifier
            tier: SLA tier
            created_at: Ticket creation time

        Returns:
            Dict with breach detection result
        """
        status = await self.check_sla_status(ticket_id, tier, created_at)

        breaches = []
        for sla_type, sla_status in status["sla_status"].items():
            if sla_status["is_breached"]:
                breach_id = f"BR-{ticket_id}-{sla_type}"

                # Determine escalation phase
                hours_elapsed = sla_status["time_elapsed_hours"]
                escalation_phase = self._determine_escalation_phase(hours_elapsed)

                breach_record = SLABreachRecord(
                    breach_id=breach_id,
                    ticket_id=ticket_id,
                    sla_type=SLAType(sla_type),
                    tier=SLATier(tier.lower()),
                    status=SLABreachStatus.BREACHED,
                    breach_duration_hours=sla_status["time_remaining_hours"] * -1,  # Negative means over
                    escalation_phase=escalation_phase,
                    created_at=datetime.now(timezone.utc),
                )

                self._breach_records[breach_id] = breach_record
                breaches.append({
                    "breach_id": breach_id,
                    "sla_type": sla_type,
                    "breach_duration_hours": abs(breach_record.breach_duration_hours),
                    "escalation_phase": escalation_phase.value,
                })

        # Log breach detection
        if breaches:
            self.log_action("parwa_high_sla_breach_detected", {
                "ticket_id": ticket_id,
                "breach_count": len(breaches),
            })

        return {
            "ticket_id": ticket_id,
            "has_breach": len(breaches) > 0,
            "breaches": breaches,
            "breach_count": len(breaches),
        }

    async def escalate_breach(
        self,
        ticket_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Escalate an SLA breach.

        Args:
            ticket_id: Ticket identifier
            reason: Reason for escalation

        Returns:
            Dict with escalation result
        """
        # Find breach records for this ticket
        ticket_breaches = [
            b for b in self._breach_records.values()
            if b.ticket_id == ticket_id
        ]

        if not ticket_breaches:
            return {
                "success": False,
                "message": f"No breach records found for ticket {ticket_id}",
            }

        # Advance escalation phase
        for breach in ticket_breaches:
            current_phase = breach.escalation_phase
            phases = list(EscalationPhase)
            current_idx = phases.index(current_phase)
            if current_idx < len(phases) - 1:
                breach.escalation_phase = phases[current_idx + 1]

        self._escalation_queue.append(ticket_id)

        self.log_action("parwa_high_sla_escalated", {
            "ticket_id": ticket_id,
            "reason": reason,
            "new_phase": ticket_breaches[0].escalation_phase.value,
        })

        return {
            "success": True,
            "ticket_id": ticket_id,
            "reason": reason,
            "escalation_phase": ticket_breaches[0].escalation_phase.value,
            "escalation_queue_position": len(self._escalation_queue),
        }

    def _determine_escalation_phase(self, hours_elapsed: float) -> EscalationPhase:
        """Determine escalation phase based on hours elapsed."""
        if hours_elapsed >= self.ESCALATION_PHASES[EscalationPhase.PHASE_4]:
            return EscalationPhase.PHASE_4
        elif hours_elapsed >= self.ESCALATION_PHASES[EscalationPhase.PHASE_3]:
            return EscalationPhase.PHASE_3
        elif hours_elapsed >= self.ESCALATION_PHASES[EscalationPhase.PHASE_2]:
            return EscalationPhase.PHASE_2
        else:
            return EscalationPhase.PHASE_1

    async def _handle_check_sla(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle check_sla action."""
        ticket_id = input_data.get("ticket_id")

        if not ticket_id:
            return AgentResponse(
                success=False,
                message="Missing required field: ticket_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.check_sla_status(
            ticket_id=ticket_id,
            tier=input_data.get("tier", "standard"),
            created_at=input_data.get("created_at"),
        )

        return AgentResponse(
            success=True,
            message=f"SLA status for {ticket_id}",
            data=result,
            confidence=0.95,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_detect_breach(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle detect_breach action."""
        ticket_id = input_data.get("ticket_id")

        if not ticket_id:
            return AgentResponse(
                success=False,
                message="Missing required field: ticket_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.detect_breach(
            ticket_id=ticket_id,
            tier=input_data.get("tier", "standard"),
            created_at=input_data.get("created_at"),
        )

        return AgentResponse(
            success=True,
            message=f"Breach detection for {ticket_id}: {result['breach_count']} breaches",
            data=result,
            confidence=0.95,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=result["has_breach"],
        )

    async def _handle_escalate_breach(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle escalate_breach action."""
        ticket_id = input_data.get("ticket_id")
        reason = input_data.get("reason", "SLA breach escalation")

        if not ticket_id:
            return AgentResponse(
                success=False,
                message="Missing required field: ticket_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.escalate_breach(ticket_id, reason)

        return AgentResponse(
            success=result["success"],
            message=f"Breach escalated for {ticket_id}" if result["success"] else result["message"],
            data=result,
            confidence=0.90,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=True,
        )

    async def _handle_acknowledge(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle acknowledge action."""
        breach_id = input_data.get("breach_id")
        acknowledged_by = input_data.get("acknowledged_by", "unknown")

        if not breach_id:
            return AgentResponse(
                success=False,
                message="Missing required field: breach_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        breach = self._breach_records.get(breach_id)
        if not breach:
            return AgentResponse(
                success=False,
                message=f"Breach record not found: {breach_id}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        breach.acknowledged = True
        breach.acknowledged_by = acknowledged_by
        breach.acknowledged_at = datetime.now(timezone.utc)

        return AgentResponse(
            success=True,
            message=f"Breach {breach_id} acknowledged by {acknowledged_by}",
            data={
                "breach_id": breach_id,
                "acknowledged": True,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": breach.acknowledged_at.isoformat(),
            },
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_stats(self) -> AgentResponse:
        """Handle get_stats action."""
        calculator_stats = self._sla_calculator.get_stats()

        return AgentResponse(
            success=True,
            message="SLA agent statistics",
            data={
                "calculator_stats": calculator_stats,
                "tracked_breaches": len(self._breach_records),
                "escalation_queue_size": len(self._escalation_queue),
                "variant": self.get_variant(),
                "tier": self.get_tier(),
            },
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )
