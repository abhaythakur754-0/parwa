"""
Ticket State Machine - Complete state machine with all transitions (Day 32)

Handles:
- All valid status transitions
- Transition validation
- Side effects on transitions
- Audit logging of state changes

PS handlers covered:
- PS02: AI can't solve → awaiting_human
- PS04: Disputes/reopen flow
- PS06: Stale detection
- PS07: Account suspended/frozen
- PS08: Awaiting client
- PS13: Variant down/queued
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import ValidationError
from database.models.tickets import Ticket, TicketStatus, TicketStatusChange

logger = logging.getLogger("parwa.services.ticket_state_machine")


class TicketStateMachine:
    """
    Complete ticket state machine with all valid transitions.

    State Transitions:
    - open → assigned, queued, frozen, closed
    - assigned → in_progress, awaiting_client, awaiting_human, open
    - in_progress → awaiting_client, awaiting_human, resolved
    - awaiting_client → in_progress, stale, resolved
    - awaiting_human → in_progress, resolved
    - resolved → closed, reopened
    - reopened → in_progress, awaiting_human
    - closed → reopened
    - frozen → open, closed
    - queued → open
    - stale → in_progress, closed
    """

    # Define all valid transitions: {from_status: [to_status, ...]}
    VALID_TRANSITIONS: Dict[TicketStatus, List[TicketStatus]] = {
        TicketStatus.open: [
            TicketStatus.assigned,
            TicketStatus.queued,
            TicketStatus.frozen,
            TicketStatus.closed,
        ],
        TicketStatus.assigned: [
            TicketStatus.in_progress,
            TicketStatus.awaiting_client,
            TicketStatus.awaiting_human,
            TicketStatus.open,
        ],
        TicketStatus.in_progress: [
            TicketStatus.awaiting_client,
            TicketStatus.awaiting_human,
            TicketStatus.resolved,
        ],
        TicketStatus.awaiting_client: [
            TicketStatus.in_progress,
            TicketStatus.stale,
            TicketStatus.resolved,
        ],
        TicketStatus.awaiting_human: [
            TicketStatus.in_progress,
            TicketStatus.resolved,
        ],
        TicketStatus.resolved: [
            TicketStatus.closed,
            TicketStatus.reopened,
        ],
        TicketStatus.reopened: [
            TicketStatus.in_progress,
            TicketStatus.awaiting_human,
        ],
        TicketStatus.closed: [
            TicketStatus.reopened,
        ],
        TicketStatus.frozen: [
            TicketStatus.open,
            TicketStatus.closed,
        ],
        TicketStatus.queued: [
            TicketStatus.open,
        ],
        TicketStatus.stale: [
            TicketStatus.in_progress,
            TicketStatus.closed,
        ],
    }

    # Terminal states (no outgoing transitions except reopened for closed)
    TERMINAL_STATES = [TicketStatus.closed]

    # Transition reasons (for audit logging)
    TRANSITION_REASONS = {
        # open → *
        (TicketStatus.open, TicketStatus.assigned): ["manual_assign", "auto_assign"],
        (TicketStatus.open, TicketStatus.queued): ["variant_down", "ps13"],
        (TicketStatus.open, TicketStatus.frozen): ["account_suspended", "ps07"],
        (TicketStatus.open, TicketStatus.closed): ["spam", "invalid", "duplicate"],

        # assigned → *
        (TicketStatus.assigned, TicketStatus.in_progress): ["agent_started"],
        (TicketStatus.assigned, TicketStatus.awaiting_client): ["need_client_input", "ps08"],
        (TicketStatus.assigned, TicketStatus.awaiting_human): ["ai_cant_solve", "ps02"],
        (TicketStatus.assigned, TicketStatus.open): ["unassigned"],

        # in_progress → *
        (TicketStatus.in_progress, TicketStatus.awaiting_client): ["need_client_input", "ps08"],
        (TicketStatus.in_progress, TicketStatus.awaiting_human): ["escalated", "ps02", "ps03"],
        (TicketStatus.in_progress, TicketStatus.resolved): ["issue_fixed"],

        # awaiting_client → *
        (TicketStatus.awaiting_client, TicketStatus.in_progress): ["client_responded"],
        (TicketStatus.awaiting_client, TicketStatus.stale): ["no_response", "ps06"],
        (TicketStatus.awaiting_client, TicketStatus.resolved): ["client_confirmed"],

        # awaiting_human → *
        (TicketStatus.awaiting_human, TicketStatus.in_progress): ["human_picked_up"],
        (TicketStatus.awaiting_human, TicketStatus.resolved): ["human_resolved"],

        # resolved → *
        (TicketStatus.resolved, TicketStatus.closed): ["client_satisfied", "timeout"],
        (TicketStatus.resolved, TicketStatus.reopened): ["client_disputed", "ps04"],

        # reopened → *
        (TicketStatus.reopened, TicketStatus.in_progress): ["work_resumed"],
        (TicketStatus.reopened, TicketStatus.awaiting_human): ["auto_escalate", "ps04"],

        # closed → *
        (TicketStatus.closed, TicketStatus.reopened): ["within_reopen_window", "ps04"],

        # frozen → *
        (TicketStatus.frozen, TicketStatus.open): ["account_reactivated", "ps07"],
        (TicketStatus.frozen, TicketStatus.closed): ["frozen_timeout", "ps07"],

        # queued → *
        (TicketStatus.queued, TicketStatus.open): ["variant_back_online", "ps13"],

        # stale → *
        (TicketStatus.stale, TicketStatus.in_progress): ["agent_picked_up"],
        (TicketStatus.stale, TicketStatus.closed): ["double_timeout", "ps06"],
    }

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self._transition_hooks: Dict[Tuple[TicketStatus,
                                           TicketStatus], List[Callable]] = {}

    def can_transition(
        self,
        ticket: Ticket,
        to_status: TicketStatus,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a ticket can transition to a new status.

        Args:
            ticket: Ticket to check
            to_status: Target status

        Returns:
            Tuple of (can_transition, error_message)
        """
        current_status = TicketStatus(
            ticket.status) if isinstance(
            ticket.status,
            str) else ticket.status

        # Check if transition is valid
        valid_targets = self.VALID_TRANSITIONS.get(current_status, [])

        if to_status not in valid_targets:
            return False, f"Cannot transition from {
                current_status.value} to {
                to_status.value}"

        # Check additional constraints
        constraint_error = self._check_constraints(
            ticket, current_status, to_status)
        if constraint_error:
            return False, constraint_error

        return True, None

    def transition(
        self,
        ticket: Ticket,
        to_status: TicketStatus,
        reason: str,
        actor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Ticket:
        """
        Execute a state transition.

        Args:
            ticket: Ticket to transition
            to_status: Target status
            reason: Reason for transition
            actor_id: User ID who triggered the transition
            metadata: Additional metadata

        Returns:
            Updated ticket
        """
        current_status = TicketStatus(
            ticket.status) if isinstance(
            ticket.status,
            str) else ticket.status

        # Validate transition
        can_trans, error = self.can_transition(ticket, to_status)
        if not can_trans:
            raise ValidationError(error)

        # Validate reason
        transition_key = (current_status, to_status)
        valid_reasons = self.TRANSITION_REASONS.get(transition_key, [])
        if valid_reasons and reason not in valid_reasons:
            raise ValidationError(
                f"Invalid reason '{reason}' for transition {
                    current_status.value} → {
                    to_status.value}. " f"Valid reasons: {valid_reasons}")

        # Store old status
        old_status = current_status

        # Execute transition
        ticket.status = to_status.value if isinstance(
            to_status, TicketStatus) else to_status
        ticket.updated_at = datetime.now(timezone.utc)

        # Handle status-specific side effects
        self._handle_side_effects(
            ticket, old_status, to_status, reason, metadata)

        # Run transition hooks
        self._run_transition_hooks(
            ticket,
            old_status,
            to_status,
            reason,
            actor_id,
            metadata)

        self.db.flush()

        return ticket

    def _check_constraints(
        self,
        ticket: Ticket,
        from_status: TicketStatus,
        to_status: TicketStatus,
    ) -> Optional[str]:
        """Check additional constraints for specific transitions."""

        # PS04: Reopen constraints
        if to_status == TicketStatus.reopened:
            # Check if within reopen window (7 days)
            if ticket.resolved_at:
                days_since_resolved = (
                    datetime.now(
                        timezone.utc) -
                    ticket.resolved_at).days
                if days_since_resolved > 7:
                    return "Reopen window has expired (7 days)"

        # PS04: Closed → reopened constraints
        if from_status == TicketStatus.closed and to_status == TicketStatus.reopened:
            # Check if within reopen window
            if ticket.closed_at:
                days_since_closed = (
                    datetime.now(
                        timezone.utc) -
                    ticket.closed_at).days
                if days_since_closed > 7:
                    return "Reopen window has expired (7 days after closing)"

        # PS04: Auto-escalate on multiple reopens
        if from_status == TicketStatus.reopened and to_status == TicketStatus.awaiting_human:
            if ticket.reopen_count and ticket.reopen_count < 2:
                return "Auto-escalation requires at least 2 reopens"

        # PS07: Frozen timeout
        if from_status == TicketStatus.frozen and to_status == TicketStatus.closed:
            if ticket.frozen_at:
                days_frozen = (
                    datetime.now(
                        timezone.utc) -
                    ticket.frozen_at).days
                if days_frozen < 30:
                    return "Frozen tickets can only be closed after 30 days"

        return None

    def _handle_side_effects(
        self,
        ticket: Ticket,
        from_status: TicketStatus,
        to_status: TicketStatus,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Handle status-specific side effects."""

        # Track first response
        if to_status in [TicketStatus.in_progress, TicketStatus.resolved]:
            if not ticket.first_response_at:
                ticket.first_response_at = datetime.now(timezone.utc)

        # Track resolution
        if to_status == TicketStatus.resolved:
            ticket.resolved_at = datetime.now(timezone.utc)

        # Track close
        if to_status == TicketStatus.closed:
            ticket.closed_at = datetime.now(timezone.utc)

        # Track reopen
        if to_status == TicketStatus.reopened:
            ticket.reopen_count = (ticket.reopen_count or 0) + 1

        # Track frozen
        if to_status == TicketStatus.frozen:
            ticket.frozen_at = datetime.now(timezone.utc)
            ticket.frozen = True
        elif from_status == TicketStatus.frozen:
            ticket.frozen = False

        # Track stale
        if to_status == TicketStatus.stale:
            ticket.stale_at = datetime.now(timezone.utc)

        # Track awaiting client
        if to_status == TicketStatus.awaiting_client:
            ticket.awaiting_client = True
        elif from_status == TicketStatus.awaiting_client:
            ticket.awaiting_client = False

        # Track awaiting human
        if to_status == TicketStatus.awaiting_human:
            ticket.awaiting_human = True
        elif from_status == TicketStatus.awaiting_human:
            ticket.awaiting_human = False

    def register_transition_hook(
        self,
        from_status: TicketStatus,
        to_status: TicketStatus,
        hook: Callable,
    ) -> None:
        """Register a hook to be called on a specific transition."""
        key = (from_status, to_status)
        if key not in self._transition_hooks:
            self._transition_hooks[key] = []
        self._transition_hooks[key].append(hook)

    def _run_transition_hooks(
        self,
        ticket: Ticket,
        from_status: TicketStatus,
        to_status: TicketStatus,
        reason: str,
        actor_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Run registered hooks for a transition."""
        key = (from_status, to_status)
        hooks = self._transition_hooks.get(key, [])

        for hook in hooks:
            try:
                hook(ticket, reason, actor_id, metadata)
            except Exception as exc:
                logger.error(
                    "transition_hook_failed: hook=%s, error=%s",
                    type(hook).__name__,
                    exc,
                    exc_info=True,
                )

    def get_valid_transitions(self, ticket: Ticket) -> List[TicketStatus]:
        """Get list of valid target statuses for a ticket."""
        current_status = TicketStatus(
            ticket.status) if isinstance(
            ticket.status,
            str) else ticket.status
        return self.VALID_TRANSITIONS.get(current_status, [])

    def get_valid_reasons(
        self,
        from_status: TicketStatus,
        to_status: TicketStatus,
    ) -> List[str]:
        """Get list of valid reasons for a transition."""
        return self.TRANSITION_REASONS.get((from_status, to_status), [])

    def is_terminal_state(self, status: TicketStatus) -> bool:
        """Check if a status is a terminal state."""
        return status in self.TERMINAL_STATES

    def get_transition_history(
        self,
        ticket_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get transition history for a ticket.

        Queries the ``TicketStatusChange`` audit table for all status
        transitions recorded against *ticket_id* within the current
        company scope, ordered newest-first.

        Args:
            ticket_id: Ticket to query.
            limit: Maximum number of records to return (default 50).

        Returns:
            List of dicts with ``from``, ``to``, ``by``, ``reason``, ``at``.
        """
        try:
            changes = (
                self.db.query(TicketStatusChange)
                .filter(
                    TicketStatusChange.ticket_id == ticket_id,
                    TicketStatusChange.company_id == self.company_id,
                )
                .order_by(TicketStatusChange.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "from": c.from_status,
                    "to": c.to_status,
                    "by": c.changed_by,
                    "reason": c.reason,
                    "at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in changes
            ]
        except Exception:
            logger.exception(
                "get_transition_history_failed ticket_id=%s", ticket_id
            )
            return []


class TransitionValidator:
    """Utility class for validating specific transition scenarios."""

    @staticmethod
    def validate_reopen(ticket: Ticket) -> Tuple[bool, Optional[str]]:
        """PS04: Validate if a ticket can be reopened."""
        if ticket.status not in [
                TicketStatus.resolved.value,
                TicketStatus.closed.value]:
            return False, "Only resolved or closed tickets can be reopened"

        # Check reopen window
        closed_at = ticket.closed_at or ticket.resolved_at
        if closed_at:
            days_since = (datetime.now(timezone.utc) - closed_at).days
            if days_since > 7:
                return False, "Reopen window has expired (7 days)"

        return True, None

    @staticmethod
    def validate_escalation(ticket: Ticket) -> Tuple[bool, Optional[str]]:
        """PS02/PS03: Validate if a ticket can be escalated to human."""
        if ticket.status not in [
            TicketStatus.open.value,
            TicketStatus.assigned.value,
            TicketStatus.in_progress.value,
            TicketStatus.reopened.value,
        ]:
            return False, f"Cannot escalate ticket in {ticket.status} status"

        return True, None

    @staticmethod
    def validate_freeze(ticket: Ticket) -> Tuple[bool, Optional[str]]:
        """PS07: Validate if a ticket can be frozen."""
        if ticket.status == TicketStatus.frozen.value:
            return False, "Ticket is already frozen"

        if ticket.status == TicketStatus.closed.value:
            return False, "Cannot freeze a closed ticket"

        return True, None

    @staticmethod
    def validate_thaw(ticket: Ticket) -> Tuple[bool, Optional[str]]:
        """PS07: Validate if a ticket can be thawed."""
        if ticket.status != TicketStatus.frozen.value:
            return False, "Only frozen tickets can be thawed"

        return True, None

    @staticmethod
    def validate_spam_mark(ticket: Ticket) -> Tuple[bool, Optional[str]]:
        """PS15: Validate if a ticket can be marked as spam."""
        if ticket.status == TicketStatus.closed.value:
            return False, "Cannot mark closed ticket as spam"

        if ticket.is_spam:
            return False, "Ticket is already marked as spam"

        return True, None

    @staticmethod
    def should_auto_escalate(ticket: Ticket) -> bool:
        """PS04: Check if ticket should auto-escalate due to multiple reopens."""
        return ticket.reopen_count is not None and ticket.reopen_count >= 2
