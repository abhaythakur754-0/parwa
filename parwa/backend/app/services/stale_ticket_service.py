"""
Stale Ticket Service - PS06: Stale detection + auto-close (Day 32)

Handles:
- Detection of stale tickets (no activity for configurable period)
- Stale notification escalation
- Auto-close after double timeout
- Priority-based timeout configuration
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.tickets import Ticket, TicketStatus, TicketPriority


class StaleTicketService:
    """
    PS06: Stale ticket detection and management.
    
    Stale Flow:
    1. Ticket in awaiting_client status with no response for 24h → flag stale
    2. Notify agent after 24h of inactivity
    3. Auto-close after double timeout (48h for low priority, varies by priority)
    
    Priority-based timeouts (in hours):
    - critical: 4h warning, 8h auto-close
    - high: 8h warning, 16h auto-close
    - medium: 24h warning, 48h auto-close
    - low: 48h warning, 96h auto-close
    """
    
    # Priority-based timeout configuration (in hours)
    PRIORITY_TIMEOUTS = {
        TicketPriority.critical: {"warning": 4, "auto_close": 8},
        TicketPriority.high: {"warning": 8, "auto_close": 16},
        TicketPriority.medium: {"warning": 24, "auto_close": 48},
        TicketPriority.low: {"warning": 48, "auto_close": 96},
    }
    
    # Statuses eligible for stale detection
    STALE_ELIGIBLE_STATUSES = [
        TicketStatus.awaiting_client,
        TicketStatus.open,
        TicketStatus.assigned,
    ]
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
    
    def detect_stale_tickets(
        self,
        statuses: Optional[List[TicketStatus]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect all stale tickets for the company.
        
        Returns list of stale tickets with staleness details.
        """
        statuses = statuses or self.STALE_ELIGIBLE_STATUSES
        
        stale_tickets = []
        
        for status in statuses:
            # Get tickets in this status
            tickets = self.db.query(Ticket).filter(
                Ticket.company_id == self.company_id,
                Ticket.status == status.value,
            ).all()
            
            for ticket in tickets:
                staleness = self._calculate_staleness(ticket)
                if staleness["is_stale"]:
                    stale_tickets.append({
                        "ticket_id": ticket.id,
                        "status": ticket.status,
                        "priority": ticket.priority,
                        "last_activity": staleness["last_activity"],
                        "hours_inactive": staleness["hours_inactive"],
                        "staleness_level": staleness["staleness_level"],
                        "auto_close_at": staleness["auto_close_at"],
                    })
        
        return stale_tickets
    
    def mark_as_stale(
        self,
        ticket_id: str,
        reason: str = "no_response",
    ) -> Ticket:
        """
        Mark a ticket as stale.
        
        Args:
            ticket_id: Ticket ID
            reason: Reason for marking stale
            
        Returns:
            Updated ticket
        """
        ticket = self._get_ticket(ticket_id)
        
        if ticket.status not in [s.value for s in self.STALE_ELIGIBLE_STATUSES]:
            raise ValidationError(
                f"Cannot mark ticket in {ticket.status} status as stale"
            )
        
        # Import state machine
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        # Transition to stale
        state_machine.transition(
            ticket=ticket,
            to_status=TicketStatus.stale,
            reason="no_response" if reason == "no_response" else "ps06",
        )
        
        ticket.stale_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(ticket)
        
        return ticket
    
    def send_stale_notification(
        self,
        ticket_id: str,
    ) -> Dict[str, Any]:
        """
        Send stale notification for a ticket.
        
        Notifies assigned agent about stale status.
        """
        ticket = self._get_ticket(ticket_id)
        
        if not ticket.stale_at:
            raise ValidationError("Ticket is not marked as stale")
        
        # Import notification service
        from app.services.notification_service import NotificationService
        
        notification_service = NotificationService(self.db, self.company_id)
        
        # Notify assigned agent
        if ticket.assigned_to:
            notification_service.send_notification(
                event_type="ticket_updated",
                recipient_ids=[ticket.assigned_to],
                data={
                    "ticket_id": ticket.id,
                    "ticket_subject": ticket.subject,
                    "update_type": "stale",
                    "message": "Ticket has been marked as stale due to inactivity",
                },
                channels=["in_app", "email"],
                priority="high",
                ticket_id=ticket.id,
            )
        
        return {
            "ticket_id": ticket_id,
            "notified": bool(ticket.assigned_to),
            "assigned_to": ticket.assigned_to,
        }
    
    def auto_close_stale(
        self,
        ticket_id: str,
    ) -> Ticket:
        """
        Auto-close a stale ticket after double timeout.
        
        Args:
            ticket_id: Ticket ID
            
        Returns:
            Updated ticket
        """
        ticket = self._get_ticket(ticket_id)
        
        if ticket.status != TicketStatus.stale.value:
            raise ValidationError("Only stale tickets can be auto-closed")
        
        # Check if double timeout reached
        staleness = self._calculate_staleness(ticket)
        if staleness["staleness_level"] != "double_timeout":
            raise ValidationError("Double timeout not yet reached")
        
        # Import state machine
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        # Transition to closed
        state_machine.transition(
            ticket=ticket,
            to_status=TicketStatus.closed,
            reason="double_timeout",
        )
        
        # Add auto-close metadata
        ticket.metadata_json = ticket.metadata_json or "{}"
        import json
        metadata = json.loads(ticket.metadata_json) if isinstance(ticket.metadata_json, str) else ticket.metadata_json
        metadata["auto_closed"] = True
        metadata["auto_close_reason"] = "stale_double_timeout"
        metadata["auto_closed_at"] = datetime.now(timezone.utc).isoformat()
        ticket.metadata_json = json.dumps(metadata)
        
        self.db.commit()
        self.db.refresh(ticket)
        
        return ticket
    
    def get_stale_candidates(
        self,
        hours_threshold: Optional[int] = None,
    ) -> List[Ticket]:
        """
        Get tickets that are candidates for stale marking.
        
        Args:
            hours_threshold: Override default threshold
            
        Returns:
            List of tickets approaching staleness
        """
        candidates = []
        
        for status in self.STALE_ELIGIBLE_STATUSES:
            tickets = self.db.query(Ticket).filter(
                Ticket.company_id == self.company_id,
                Ticket.status == status.value,
            ).all()
            
            for ticket in tickets:
                staleness = self._calculate_staleness(ticket)
                
                # Check if within warning threshold
                priority = TicketPriority(ticket.priority) if ticket.priority else TicketPriority.medium
                warning_hours = hours_threshold or self.PRIORITY_TIMEOUTS[priority]["warning"]
                
                if staleness["hours_inactive"] >= warning_hours:
                    candidates.append(ticket)
        
        return candidates
    
    def get_auto_close_candidates(
        self,
    ) -> List[Ticket]:
        """Get stale tickets ready for auto-close."""
        candidates = []
        
        stale_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status == TicketStatus.stale.value,
        ).all()
        
        for ticket in stale_tickets:
            staleness = self._calculate_staleness(ticket)
            if staleness["staleness_level"] == "double_timeout":
                candidates.append(ticket)
        
        return candidates
    
    def revive_stale_ticket(
        self,
        ticket_id: str,
        actor_id: str,
    ) -> Ticket:
        """
        Revive a stale ticket (agent picks it up).
        
        Args:
            ticket_id: Ticket ID
            actor_id: User ID who picked up the ticket
            
        Returns:
            Updated ticket
        """
        ticket = self._get_ticket(ticket_id)
        
        if ticket.status != TicketStatus.stale.value:
            raise ValidationError("Only stale tickets can be revived")
        
        # Import state machine
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        # Transition to in_progress
        state_machine.transition(
            ticket=ticket,
            to_status=TicketStatus.in_progress,
            reason="agent_picked_up",
            actor_id=actor_id,
        )
        
        # Clear stale metadata
        ticket.stale_at = None
        
        self.db.commit()
        self.db.refresh(ticket)
        
        return ticket
    
    def _calculate_staleness(
        self,
        ticket: Ticket,
    ) -> Dict[str, Any]:
        """Calculate staleness details for a ticket."""
        now = datetime.now(timezone.utc)
        
        # Determine last activity time
        last_activity = ticket.updated_at or ticket.created_at
        
        # Calculate hours since last activity
        if last_activity:
            hours_inactive = (now - last_activity).total_seconds() / 3600
        else:
            hours_inactive = 0
        
        # Get priority-based thresholds
        priority = TicketPriority(ticket.priority) if ticket.priority else TicketPriority.medium
        thresholds = self.PRIORITY_TIMEOUTS.get(priority, self.PRIORITY_TIMEOUTS[TicketPriority.medium])
        
        warning_hours = thresholds["warning"]
        auto_close_hours = thresholds["auto_close"]
        
        # Determine staleness level
        staleness_level = "none"
        if hours_inactive >= auto_close_hours * 2:
            staleness_level = "double_timeout"
        elif hours_inactive >= auto_close_hours:
            staleness_level = "timeout"
        elif hours_inactive >= warning_hours:
            staleness_level = "warning"
        
        # Calculate auto-close time
        if ticket.stale_at:
            auto_close_at = ticket.stale_at + timedelta(hours=auto_close_hours)
        else:
            auto_close_at = (last_activity or now) + timedelta(hours=auto_close_hours * 2)
        
        return {
            "last_activity": last_activity,
            "hours_inactive": round(hours_inactive, 2),
            "warning_threshold": warning_hours,
            "auto_close_threshold": auto_close_hours,
            "staleness_level": staleness_level,
            "is_stale": staleness_level in ["warning", "timeout", "double_timeout"],
            "auto_close_at": auto_close_at,
        }
    
    def _get_ticket(self, ticket_id: str) -> Ticket:
        """Get ticket by ID."""
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()
        
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        
        return ticket
    
    def get_stale_statistics(
        self,
    ) -> Dict[str, Any]:
        """Get stale ticket statistics for the company."""
        stale_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status == TicketStatus.stale.value,
        ).count()
        
        # Count by staleness level
        by_level = {"warning": 0, "timeout": 0, "double_timeout": 0}
        
        all_stale = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status == TicketStatus.stale.value,
        ).all()
        
        for ticket in all_stale:
            staleness = self._calculate_staleness(ticket)
            if staleness["staleness_level"] in by_level:
                by_level[staleness["staleness_level"]] += 1
        
        # Count approaching stale
        approaching = len(self.get_stale_candidates())
        
        return {
            "total_stale": stale_tickets,
            "by_level": by_level,
            "approaching_stale": approaching,
        }
