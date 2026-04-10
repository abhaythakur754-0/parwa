"""
Ticket Lifecycle Service - Orchestrates all PS handlers (Day 32)

Handles:
- PS01: Out-of-plan scope check
- PS02: AI can't solve escalation
- PS03: Client asks for human
- PS04: Disputes/reopen flow
- PS05: Duplicate detection
- PS07: Account suspended/frozen
- PS08: Awaiting client reminders
- PS13: Variant down handling

This service coordinates all ticket lifecycle operations.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.tickets import Ticket, TicketStatus, TicketPriority
from database.models.core import User, Company


class TicketLifecycleService:
    """
    Orchestrates all ticket lifecycle PS handlers.
    
    This service provides high-level methods that coordinate
    multiple PS handlers for complex ticket lifecycle operations.
    """
    
    # PS08: Awaiting client reminder intervals (hours)
    AWAITING_CLIENT_REMINDERS = [24, 168, 336]  # 1 day, 1 week, 2 weeks
    
    # PS04: Reopen window (days)
    REOPEN_WINDOW_DAYS = 7
    
    # PS02: AI attempt limit before escalation
    AI_ATTEMPT_LIMIT = 3
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
    
    # ── PS01: Out-of-Plan Scope ─────────────────────────────────────
    
    def check_out_of_plan_scope(
        self,
        ticket: Ticket,
    ) -> Dict[str, Any]:
        """
        PS01: Check if ticket is out of plan scope.
        
        Checks variant capabilities and tags if beyond scope.
        """
        # Get company plan
        company = self.db.query(Company).filter(
            Company.id == self.company_id,
        ).first()
        
        if not company:
            return {"in_scope": True, "reason": None}
        
        # Check plan capabilities (simplified)
        plan_tier = getattr(company, 'plan_tier', 'starter')
        
        # Define scope limits by plan
        scope_limits = {
            "starter": {"ai_responses": 10, "channels": ["email"]},
            "growth": {"ai_responses": 50, "channels": ["email", "chat"]},
            "high": {"ai_responses": -1, "channels": ["email", "chat", "sms", "voice"]},
        }
        
        limits = scope_limits.get(plan_tier, scope_limits["starter"])
        
        result = {
            "in_scope": True,
            "plan_tier": plan_tier,
            "limits": limits,
            "out_of_scope_reason": None,
            "upgrade_suggestion": None,
        }
        
        # Check channel scope
        if ticket.channel and ticket.channel not in limits["channels"]:
            result["in_scope"] = False
            result["out_of_scope_reason"] = f"Channel '{ticket.channel}' not available on {plan_tier} plan"
            result["upgrade_suggestion"] = "Upgrade to access this channel"
            
            # Tag ticket
            self._add_tag(ticket, "out_of_scope:channel")
        
        return result
    
    # ── PS02: AI Can't Solve ────────────────────────────────────────
    
    def handle_ai_cant_solve(
        self,
        ticket_id: str,
        attempt_count: int,
        reason: str,
    ) -> Dict[str, Any]:
        """
        PS02: Handle AI unable to solve ticket.
        
        After N attempts, auto-escalate to human.
        """
        ticket = self._get_ticket(ticket_id)
        
        result = {
            "ticket_id": ticket_id,
            "attempt_count": attempt_count,
            "escalated": False,
            "status": ticket.status,
        }
        
        # Check if limit reached
        if attempt_count >= self.AI_ATTEMPT_LIMIT:
            # Escalate to human
            from app.services.ticket_state_machine import TicketStateMachine
            
            state_machine = TicketStateMachine(self.db, self.company_id)
            
            state_machine.transition(
                ticket=ticket,
                to_status=TicketStatus.awaiting_human,
                reason="ai_cant_solve",
                metadata={"attempt_count": attempt_count, "reason": reason},
            )
            
            result["escalated"] = True
            result["status"] = TicketStatus.awaiting_human.value
            
            # Update escalation level
            ticket.escalation_level = (ticket.escalation_level or 0) + 1
            
            self.db.commit()
        
        return result
    
    # ── PS03: Client Asks for Human ─────────────────────────────────
    
    def handle_human_request(
        self,
        ticket_id: str,
        ai_summary: str,
        requested_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        PS03: Handle client request for human agent.
        
        Immediately escalates with AI conversation summary.
        """
        ticket = self._get_ticket(ticket_id)
        
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        # Transition to awaiting_human
        state_machine.transition(
            ticket=ticket,
            to_status=TicketStatus.awaiting_human,
            reason="ps03",
            actor_id=requested_by,
            metadata={"ai_summary": ai_summary[:1000]},  # Limit summary length
        )
        
        # Update escalation info
        ticket.escalation_level = (ticket.escalation_level or 0) + 1
        
        self.db.commit()
        
        # Notify human queue
        from app.services.notification_service import NotificationService
        
        notification_service = NotificationService(self.db, self.company_id)
        
        notification_service.notify_human_queue(
            ticket_id=ticket_id,
            summary=ai_summary,
            escalation_reason="client_requested_human",
        )
        
        return {
            "ticket_id": ticket_id,
            "status": TicketStatus.awaiting_human.value,
            "escalated": True,
        }
    
    # ── PS04: Disputes/Reopen Flow ────────────────────────────────────
    
    def reopen_ticket(
        self,
        ticket_id: str,
        reason: str,
        reopened_by: Optional[str] = None,
    ) -> Ticket:
        """
        PS04: Reopen a closed/resolved ticket.
        
        Tracks reopen count and auto-escalates if needed.
        """
        ticket = self._get_ticket(ticket_id)
        
        from app.services.ticket_state_machine import TicketStateMachine, TransitionValidator
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        # Validate reopen
        can_reopen, error = TransitionValidator.validate_reopen(ticket)
        if not can_reopen:
            raise ValidationError(error)
        
        # Increment reopen count
        ticket.reopen_count = (ticket.reopen_count or 0) + 1
        
        # Determine target status
        if TransitionValidator.should_auto_escalate(ticket):
            # Auto-escalate to human after multiple reopens
            target_status = TicketStatus.awaiting_human
            transition_reason = "auto_escalate"
        else:
            target_status = TicketStatus.reopened
            transition_reason = "client_disputed"
        
        state_machine.transition(
            ticket=ticket,
            to_status=target_status,
            reason=transition_reason,
            actor_id=reopened_by,
            metadata={"reopen_reason": reason},
        )
        
        self.db.commit()
        self.db.refresh(ticket)
        
        return ticket
    
    # ── PS05: Duplicate Detection ───────────────────────────────────
    
    def check_duplicate(
        self,
        subject: str,
        content: str,
        customer_id: str,
    ) -> Dict[str, Any]:
        """
        PS05: Check for duplicate tickets.
        
        Compares against recent open tickets from same customer.
        """
        # Look for similar tickets in last 7 days
        since = datetime.utcnow() - timedelta(days=7)
        
        recent_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.customer_id == customer_id,
            Ticket.status.in_([
                TicketStatus.open.value,
                TicketStatus.assigned.value,
                TicketStatus.in_progress.value,
            ]),
            Ticket.created_at >= since,
        ).all()
        
        duplicates = []
        
        for existing in recent_tickets:
            similarity = self._calculate_similarity(
                subject, content,
                existing.subject or "", ""
            )
            
            if similarity > 0.85:  # 85% similarity threshold
                duplicates.append({
                    "ticket_id": existing.id,
                    "subject": existing.subject,
                    "similarity": similarity,
                    "created_at": existing.created_at.isoformat() if existing.created_at else None,
                })
        
        return {
            "is_duplicate": len(duplicates) > 0,
            "duplicates": duplicates,
            "similarity_threshold": 0.85,
        }
    
    # ── PS07: Account Suspended/Frozen ──────────────────────────────────────
    
    def freeze_tickets_for_account(
        self,
        reason: str = "account_suspended",
    ) -> Dict[str, Any]:
        """
        PS07: Freeze all open tickets when account is suspended.
        """
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        # Get all open tickets
        open_statuses = [
            TicketStatus.open.value,
            TicketStatus.assigned.value,
            TicketStatus.in_progress.value,
            TicketStatus.awaiting_client.value,
            TicketStatus.awaiting_human.value,
        ]
        
        tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status.in_(open_statuses),
        ).all()
        
        frozen_count = 0
        
        for ticket in tickets:
            try:
                state_machine.transition(
                    ticket=ticket,
                    to_status=TicketStatus.frozen,
                    reason=reason,
                )
                frozen_count += 1
            except ValidationError:
                continue
        
        self.db.commit()
        
        return {
            "frozen_count": frozen_count,
            "reason": reason,
        }
    
    def thaw_tickets_for_account(
        self,
    ) -> Dict[str, Any]:
        """
        PS07: Thaw all frozen tickets when account is reactivated.
        """
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        frozen_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status == TicketStatus.frozen.value,
        ).all()
        
        thawed_count = 0
        
        for ticket in frozen_tickets:
            try:
                state_machine.transition(
                    ticket=ticket,
                    to_status=TicketStatus.open,
                    reason="account_reactivated",
                )
                thawed_count += 1
            except ValidationError:
                continue
        
        self.db.commit()
        
        return {"thawed_count": thawed_count}
    
    def cleanup_frozen_tickets(
        self,
        days_frozen: int = 30,
    ) -> Dict[str, Any]:
        """
        PS07: Close frozen tickets after 30 days.
        """
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        cutoff = datetime.utcnow() - timedelta(days=days_frozen)
        
        frozen_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status == TicketStatus.frozen.value,
            Ticket.frozen_at < cutoff,
        ).all()
        
        closed_count = 0
        
        for ticket in frozen_tickets:
            try:
                state_machine.transition(
                    ticket=ticket,
                    to_status=TicketStatus.closed,
                    reason="frozen_timeout",
                )
                closed_count += 1
            except ValidationError:
                continue
        
        self.db.commit()
        
        return {"closed_count": closed_count}
    
    # ── PS08: Awaiting Client Reminders ───────────────────────────────────
    
    def send_awaiting_client_reminder(
        self,
        ticket_id: str,
        reminder_type: str,
    ) -> Dict[str, Any]:
        """
        PS08: Send reminder for ticket awaiting client response.
        """
        ticket = self._get_ticket(ticket_id)
        
        messages = {
            "24h": "We're waiting for your response on this ticket.",
            "7d": "This ticket needs your input. Please respond to keep it active.",
            "14d": "Last reminder: This ticket will be closed if we don't hear from you soon.",
        }
        
        from app.services.notification_service import NotificationService
        
        notification_service = NotificationService(self.db, self.company_id)
        
        notification_service.send_notification(
            event_type="ticket_updated",
            recipient_ids=[ticket.customer_id],
            data={
                "ticket_id": ticket.id,
                "ticket_subject": ticket.subject,
                "message": messages.get(reminder_type, "Reminder: Please respond to your ticket."),
                "reminder_type": reminder_type,
            },
            channels=["email"],
            ticket_id=ticket.id,
        )
        
        return {
            "ticket_id": ticket_id,
            "sent": True,
            "reminder_type": reminder_type,
        }
    
    def get_awaiting_client_tickets_for_reminder(
        self,
    ) -> Dict[str, List[str]]:
        """
        PS08: Get tickets needing reminders grouped by reminder type.
        """
        now = datetime.utcnow()
        
        tickets_24h = []
        tickets_7d = []
        tickets_14d = []
        
        awaiting_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status == TicketStatus.awaiting_client.value,
        ).all()
        
        for ticket in awaiting_tickets:
            last_activity = ticket.updated_at or ticket.created_at
            if not last_activity:
                continue
            
            hours_waiting = (now - last_activity).total_seconds() / 3600
            
            # Check for 14d first (highest priority)
            if hours_waiting >= 336:  # 14 days
                tickets_14d.append(ticket.id)
            elif hours_waiting >= 168:  # 7 days
                tickets_7d.append(ticket.id)
            elif hours_waiting >= 24:  # 24 hours
                tickets_24h.append(ticket.id)
        
        return {
            "24h": tickets_24h,
            "7d": tickets_7d,
            "14d": tickets_14d,
        }
    
    # ── PS13: Variant Down Handling ─────────────────────────────────────────
    
    def handle_variant_down(
        self,
        variant_id: str,
    ) -> Dict[str, Any]:
        """
        PS13: Handle variant going offline.
        
        Queue tickets assigned to variant, retry when back.
        """
        # Find tickets assigned to this variant
        variant_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.assigned_to == variant_id,
            Ticket.status.in_([
                TicketStatus.open.value,
                TicketStatus.assigned.value,
                TicketStatus.in_progress.value,
            ]),
        ).all()
        
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        queued_count = 0
        
        for ticket in variant_tickets:
            try:
                state_machine.transition(
                    ticket=ticket,
                    to_status=TicketStatus.queued,
                    reason="variant_down",
                    metadata={"variant_id": variant_id},
                )
                queued_count += 1
            except ValidationError:
                continue
        
        self.db.commit()
        
        return {
            "variant_id": variant_id,
            "queued_tickets": queued_count,
        }
    
    def handle_variant_up(
        self,
        variant_id: str,
    ) -> Dict[str, Any]:
        """
        PS13: Handle variant coming back online.
        
        Resume queued tickets.
        """
        queued_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.status == TicketStatus.queued.value,
        ).all()
        
        from app.services.ticket_state_machine import TicketStateMachine
        
        state_machine = TicketStateMachine(self.db, self.company_id)
        
        resumed_count = 0
        
        for ticket in queued_tickets:
            try:
                state_machine.transition(
                    ticket=ticket,
                    to_status=TicketStatus.open,
                    reason="variant_back_online",
                )
                
                # Re-assign to variant
                ticket.assigned_to = variant_id
                resumed_count += 1
            except ValidationError:
                continue
        
        self.db.commit()
        
        return {
            "variant_id": variant_id,
            "resumed_tickets": resumed_count,
        }
    
    # ── Helper Methods ──────────────────────────────────────────────────────
    
    def _get_ticket(
        self,
        ticket_id: str,
    ) -> Ticket:
        """Get ticket by ID."""
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()
        
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        
        return ticket
    
    def _add_tag(
        self,
        ticket: Ticket,
        tag: str,
    ) -> None:
        """Add a tag to a ticket."""
        try:
            tags = json.loads(ticket.tags) if ticket.tags else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        
        if tag not in tags:
            tags.append(tag)
            ticket.tags = json.dumps(tags)
            self.db.commit()
    
    def _calculate_similarity(
        self,
        subject1: str,
        content1: str,
        subject2: str,
        content2: str,
    ) -> float:
        """Calculate text similarity (simplified)."""
        # Simple word overlap similarity
        text1 = f"{subject1} {content1}".lower().split()
        text2 = f"{subject2} {content2}".lower().split()
        
        if not text1 or not text2:
            return 0.0
        
        set1 = set(text1)
        set2 = set(text2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
