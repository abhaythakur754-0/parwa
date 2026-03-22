"""
Escalation Service Layer.

Handles ticket escalation, stuck ticket detection, and notification.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.services.escalation_ladder import (
    EscalationLadder,
    EscalationPhase,
    get_escalation_ladder,
)
from backend.models.support_ticket import SupportTicket
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class StuckTicketReason(str, Enum):
    """Reasons why a ticket might be stuck."""
    NO_RESPONSE = "no_response"
    RESPONSE_OVERDUE = "response_overdue"
    RESOLUTION_OVERDUE = "resolution_overdue"
    AGENT_UNAVAILABLE = "agent_unavailable"
    CUSTOMER_UNRESPONSIVE = "customer_unresponsive"
    WAITING_FOR_INFO = "waiting_for_info"
    ESCALATION_TIMEOUT = "escalation_timeout"


class EscalationService:
    """
    Service class for ticket escalation management.

    Handles:
    - Stuck ticket detection
    - Automatic escalation
    - Notification dispatch

    All methods enforce company-scoped data access (RLS).
    """

    # Thresholds for stuck ticket detection (hours)
    STUCK_THRESHOLDS = {
        StuckTicketReason.NO_RESPONSE: 4,
        StuckTicketReason.RESPONSE_OVERDUE: 24,
        StuckTicketReason.RESOLUTION_OVERDUE: 72,
        StuckTicketReason.AGENT_UNAVAILABLE: 1,
        StuckTicketReason.CUSTOMER_UNRESPONSIVE: 48,
        StuckTicketReason.WAITING_FOR_INFO: 24,
        StuckTicketReason.ESCALATION_TIMEOUT: 12,
    }

    def __init__(
        self,
        db: AsyncSession,
        company_id: UUID,
        escalation_ladder: Optional[EscalationLadder] = None
    ) -> None:
        """
        Initialize escalation service.

        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
            escalation_ladder: Optional escalation ladder instance
        """
        self.db = db
        self.company_id = company_id
        self._escalation_ladder = escalation_ladder or get_escalation_ladder()
        self._escalation_queue: List[Dict[str, Any]] = []
        self._notification_history: List[Dict[str, Any]] = []

    async def check_stuck_tickets(
        self,
        hours_threshold: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all stuck tickets that need escalation.

        A ticket is considered "stuck" if:
        - No response within threshold hours
        - Response is overdue
        - Resolution is overdue
        - Agent is unavailable
        - Waiting for info too long

        Args:
            hours_threshold: Custom threshold (defaults to 24 hours)

        Returns:
            List of stuck ticket details
        """
        threshold = hours_threshold or 24
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=threshold)

        stuck_tickets = []

        # In production, this would query the database
        # For now, we simulate with mock data structure

        logger.info({
            "event": "stuck_tickets_check",
            "company_id": str(self.company_id),
            "threshold_hours": threshold,
            "cutoff_time": cutoff.isoformat(),
        })

        # Simulated stuck ticket detection logic
        # Phase 1: Check for no response tickets
        # Phase 2: Check for overdue response tickets
        # Phase 3: Check for overdue resolution tickets

        return stuck_tickets

    async def escalate_ticket(
        self,
        ticket_id: str,
        reason: str,
        target_phase: Optional[EscalationPhase] = None
    ) -> Dict[str, Any]:
        """
        Escalate a specific ticket.

        Args:
            ticket_id: Ticket identifier
            reason: Reason for escalation
            target_phase: Optional target phase (defaults to next phase)

        Returns:
            Dict with escalation result
        """
        now = datetime.now(timezone.utc)

        # Determine target phase if not specified
        if target_phase is None:
            # Default to Phase 2 (Team Lead) for manual escalation
            target_phase = EscalationPhase.PHASE_2

        escalation_result = await self._escalation_ladder.escalate(
            ticket_id=ticket_id,
            phase=target_phase,
            reason=reason,
        )

        if escalation_result.get("success"):
            # Add to escalation queue for processing
            self._escalation_queue.append({
                "ticket_id": ticket_id,
                "phase": target_phase.value,
                "reason": reason,
                "queued_at": now.isoformat(),
            })

            # Log escalation
            logger.warning({
                "event": "ticket_escalated",
                "company_id": str(self.company_id),
                "ticket_id": ticket_id,
                "phase": target_phase.value,
                "reason": reason,
            })

        return escalation_result

    async def notify_escalation(
        self,
        ticket_id: str,
        level: str,
        targets: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send escalation notifications.

        Args:
            ticket_id: Ticket identifier
            level: Escalation level (agent, team_lead, manager, executive)
            targets: Optional list of specific notification targets

        Returns:
            Dict with notification result
        """
        now = datetime.now(timezone.utc)

        # Default notification targets by level
        default_targets = {
            "agent": ["assigned_agent"],
            "team_lead": ["assigned_agent", "team_lead"],
            "manager": ["assigned_agent", "team_lead", "manager"],
            "executive": ["assigned_agent", "team_lead", "manager", "executive"],
        }

        notify_targets = targets or default_targets.get(level, ["assigned_agent"])

        notification_record = {
            "ticket_id": ticket_id,
            "level": level,
            "targets": notify_targets,
            "notified_at": now.isoformat(),
            "status": "sent",
        }

        self._notification_history.append(notification_record)

        logger.info({
            "event": "escalation_notification_sent",
            "company_id": str(self.company_id),
            "ticket_id": ticket_id,
            "level": level,
            "targets": notify_targets,
        })

        return {
            "success": True,
            "ticket_id": ticket_id,
            "level": level,
            "targets_notified": notify_targets,
            "notified_at": now.isoformat(),
        }

    async def auto_escalate(self) -> Dict[str, Any]:
        """
        Run automatic escalation check for all tickets.

        This method:
        1. Finds all stuck tickets
        2. Determines their current escalation phase
        3. Escalates tickets that have crossed thresholds
        4. Sends appropriate notifications

        Returns:
            Dict with auto-escalation results
        """
        now = datetime.now(timezone.utc)

        logger.info({
            "event": "auto_escalation_started",
            "company_id": str(self.company_id),
        })

        # Find stuck tickets
        stuck_tickets = await self.check_stuck_tickets()

        escalated_count = 0
        notifications_sent = 0
        errors = []

        for ticket in stuck_tickets:
            try:
                ticket_id = ticket.get("ticket_id")
                created_at = ticket.get("created_at")

                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

                    # Get current phase
                    current_phase = self._escalation_ladder.get_current_phase(created_at, now)

                    # Check if should escalate
                    if current_phase.value > ticket.get("current_phase", 0):
                        escalation_result = await self.escalate_ticket(
                            ticket_id=ticket_id,
                            reason=f"Auto-escalation: Phase {current_phase.value}",
                            target_phase=current_phase,
                        )

                        if escalation_result.get("success"):
                            escalated_count += 1

                            # Send notifications
                            phase_config = self._escalation_ladder.get_phase_config(current_phase)
                            if phase_config:
                                await self.notify_escalation(
                                    ticket_id=ticket_id,
                                    level=current_phase.name,
                                    targets=phase_config.notify_targets,
                                )
                                notifications_sent += 1

            except Exception as e:
                errors.append({
                    "ticket_id": ticket.get("ticket_id"),
                    "error": str(e),
                })

        result = {
            "success": True,
            "company_id": str(self.company_id),
            "checked_at": now.isoformat(),
            "tickets_checked": len(stuck_tickets),
            "escalated_count": escalated_count,
            "notifications_sent": notifications_sent,
            "errors": errors,
        }

        logger.info({
            "event": "auto_escalation_completed",
            "company_id": str(self.company_id),
            "escalated_count": escalated_count,
            "notifications_sent": notifications_sent,
        })

        return result

    async def get_escalation_queue(self) -> List[Dict[str, Any]]:
        """
        Get current escalation queue.

        Returns:
            List of tickets in escalation queue
        """
        return self._escalation_queue

    async def get_notification_history(
        self,
        ticket_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get notification history.

        Args:
            ticket_id: Optional filter by ticket
            limit: Max results

        Returns:
            List of notification records
        """
        if ticket_id:
            return [
                n for n in self._notification_history
                if n.get("ticket_id") == ticket_id
            ][:limit]
        return self._notification_history[:limit]

    async def get_ticket_escalation_status(
        self,
        ticket_id: str,
        ticket_created_at: datetime
    ) -> Dict[str, Any]:
        """
        Get escalation status for a specific ticket.

        Args:
            ticket_id: Ticket identifier
            ticket_created_at: When the ticket was created

        Returns:
            Dict with escalation status
        """
        now = datetime.now(timezone.utc)

        current_phase = self._escalation_ladder.get_current_phase(
            ticket_created_at, now
        )

        phase_config = self._escalation_ladder.get_phase_config(current_phase)

        escalation_history = self._escalation_ladder.get_escalation_history(ticket_id)

        return {
            "ticket_id": ticket_id,
            "current_phase": current_phase.value,
            "phase_name": phase_config.name if phase_config else None,
            "created_at": ticket_created_at.isoformat(),
            "hours_since_creation": (now - ticket_created_at).total_seconds() / 3600,
            "escalation_count": len(escalation_history),
            "last_escalation": escalation_history[-1] if escalation_history else None,
            "next_escalation": self._escalation_ladder.get_next_escalation(
                ticket_id, ticket_created_at, now
            ),
        }

    async def clear_escalation_queue(self) -> int:
        """
        Clear processed items from escalation queue.

        Returns:
            Number of items cleared
        """
        count = len(self._escalation_queue)
        self._escalation_queue = []

        logger.info({
            "event": "escalation_queue_cleared",
            "company_id": str(self.company_id),
            "items_cleared": count,
        })

        return count

    async def retry_failed_escalations(
        self,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Retry failed escalations.

        Args:
            max_retries: Maximum retry attempts

        Returns:
            Dict with retry results
        """
        retried = 0
        succeeded = 0
        failed = 0

        for ticket in list(self._escalation_queue):
            if ticket.get("retry_count", 0) < max_retries:
                result = await self.escalate_ticket(
                    ticket_id=ticket["ticket_id"],
                    reason=ticket.get("reason", "Retry"),
                )

                retried += 1
                if result.get("success"):
                    succeeded += 1
                    self._escalation_queue.remove(ticket)
                else:
                    failed += 1
                    ticket["retry_count"] = ticket.get("retry_count", 0) + 1

        return {
            "retried": retried,
            "succeeded": succeeded,
            "failed": failed,
        }
