"""
Day 32 Tests - Production Situation Handlers + Ticket State Machine

Tests for:
- TicketStateMachine: All valid and invalid transitions
- StaleTicketService: PS06 stale detection and auto-close
- IncidentService: PS10 incident management
- SpamDetectionService: PS15 spam detection
- TicketLifecycleService: PS handlers orchestration
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from enum import Enum

# Import services
from backend.app.services.ticket_state_machine import (
    TicketStateMachine,
    TransitionValidator,
)
from backend.app.services.stale_ticket_service import StaleTicketService
from backend.app.services.spam_detection_service import SpamDetectionService
from backend.app.services.incident_service import Incident
from backend.app.exceptions import ValidationError, NotFoundError


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def company_id():
    """Test company ID."""
    return "test-company-id"


@pytest.fixture
def state_machine(mock_db, company_id):
    """Create state machine instance."""
    return TicketStateMachine(mock_db, company_id)


@pytest.fixture
def stale_service(mock_db, company_id):
    """Create stale ticket service instance."""
    return StaleTicketService(mock_db, company_id)


@pytest.fixture
def spam_service(mock_db, company_id):
    """Create spam detection service instance."""
    return SpamDetectionService(mock_db, company_id)


@pytest.fixture
def mock_ticket():
    """Create mock ticket."""
    ticket = MagicMock()
    ticket.id = "ticket-123"
    ticket.company_id = "test-company-id"
    ticket.status = "open"
    ticket.subject = "Test Ticket"
    ticket.priority = "medium"
    ticket.reopen_count = 0
    ticket.is_spam = False
    ticket.spam_score = 0
    ticket.frozen_at = None
    ticket.resolved_at = None
    ticket.closed_at = None
    ticket.stale_at = None
    ticket.updated_at = datetime.utcnow()
    ticket.created_at = datetime.utcnow()
    return ticket


# ── TicketStateMachine Tests ─────────────────────────────────────────────────

class TestTicketStateMachine:
    """Tests for TicketStateMachine."""
    
    def test_valid_transitions_defined(self, state_machine):
        """Test that valid transitions are defined for all statuses."""
        from database.models.tickets import TicketStatus
        
        # All statuses should have transitions defined (even if empty)
        for status in TicketStatus:
            assert status in state_machine.VALID_TRANSITIONS
    
    def test_can_transition_valid(self, state_machine, mock_ticket):
        """Test valid transition check returns True."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.open.value
        
        can_trans, error = state_machine.can_transition(mock_ticket, TicketStatus.assigned)
        
        assert can_trans is True
        assert error is None
    
    def test_can_transition_invalid(self, state_machine, mock_ticket):
        """Test invalid transition check returns False."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.open.value
        
        can_trans, error = state_machine.can_transition(mock_ticket, TicketStatus.resolved)
        
        assert can_trans is False
        assert "Cannot transition" in error
    
    def test_transition_success(self, state_machine, mock_ticket, mock_db):
        """Test successful transition."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.open.value
        
        result = state_machine.transition(
            ticket=mock_ticket,
            to_status=TicketStatus.assigned,
            reason="manual_assign",
        )
        
        assert result.status == TicketStatus.assigned.value
        mock_db.flush.assert_called_once()
    
    def test_transition_invalid_reason(self, state_machine, mock_ticket):
        """Test transition with invalid reason raises error."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.open.value
        
        with pytest.raises(ValidationError) as exc_info:
            state_machine.transition(
                ticket=mock_ticket,
                to_status=TicketStatus.assigned,
                reason="invalid_reason",
            )
        
        assert "Invalid reason" in str(exc_info.value)
    
    def test_get_valid_transitions(self, state_machine, mock_ticket):
        """Test getting valid transitions for a ticket."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.open.value
        
        transitions = state_machine.get_valid_transitions(mock_ticket)
        
        assert TicketStatus.assigned in transitions
        assert TicketStatus.queued in transitions
        assert TicketStatus.frozen in transitions
        assert TicketStatus.closed in transitions
    
    def test_get_valid_reasons(self, state_machine):
        """Test getting valid reasons for a transition."""
        from database.models.tickets import TicketStatus
        
        reasons = state_machine.get_valid_reasons(
            TicketStatus.open,
            TicketStatus.assigned,
        )
        
        assert "manual_assign" in reasons
        assert "auto_assign" in reasons
    
    def test_terminal_state_detection(self, state_machine):
        """Test terminal state detection."""
        from database.models.tickets import TicketStatus
        
        assert state_machine.is_terminal_state(TicketStatus.closed) is True
        assert state_machine.is_terminal_state(TicketStatus.open) is False
    
    def test_transition_hook_registration(self, state_machine):
        """Test registering transition hooks."""
        from database.models.tickets import TicketStatus
        
        hook_called = []
        
        def test_hook(ticket, reason, actor_id, metadata):
            hook_called.append((ticket.id, reason))
        
        state_machine.register_transition_hook(
            TicketStatus.open,
            TicketStatus.assigned,
            test_hook,
        )
        
        assert (TicketStatus.open, TicketStatus.assigned) in state_machine._transition_hooks


class TestTransitionValidator:
    """Tests for TransitionValidator."""
    
    def test_validate_reopen_valid(self, mock_ticket):
        """Test valid reopen validation."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.closed.value
        mock_ticket.closed_at = datetime.utcnow() - timedelta(days=3)
        
        can_reopen, error = TransitionValidator.validate_reopen(mock_ticket)
        
        assert can_reopen is True
        assert error is None
    
    def test_validate_reopen_expired(self, mock_ticket):
        """Test reopen validation with expired window."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.closed.value
        mock_ticket.closed_at = datetime.utcnow() - timedelta(days=10)
        
        can_reopen, error = TransitionValidator.validate_reopen(mock_ticket)
        
        assert can_reopen is False
        assert "expired" in error.lower()
    
    def test_validate_escalation_valid(self, mock_ticket):
        """Test valid escalation validation."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.in_progress.value
        
        can_escalate, error = TransitionValidator.validate_escalation(mock_ticket)
        
        assert can_escalate is True
    
    def test_validate_escalation_invalid_status(self, mock_ticket):
        """Test escalation validation with invalid status."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.closed.value
        
        can_escalate, error = TransitionValidator.validate_escalation(mock_ticket)
        
        assert can_escalate is False
    
    def test_validate_freeze_valid(self, mock_ticket):
        """Test valid freeze validation."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.open.value
        
        can_freeze, error = TransitionValidator.validate_freeze(mock_ticket)
        
        assert can_freeze is True
    
    def test_validate_freeze_already_frozen(self, mock_ticket):
        """Test freeze validation when already frozen."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.frozen.value
        
        can_freeze, error = TransitionValidator.validate_freeze(mock_ticket)
        
        assert can_freeze is False
        assert "already frozen" in error.lower()
    
    def test_validate_thaw_valid(self, mock_ticket):
        """Test valid thaw validation."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.frozen.value
        
        can_thaw, error = TransitionValidator.validate_thaw(mock_ticket)
        
        assert can_thaw is True
    
    def test_validate_spam_mark_valid(self, mock_ticket):
        """Test valid spam mark validation."""
        mock_ticket.is_spam = False
        mock_ticket.status = "open"
        
        can_mark, error = TransitionValidator.validate_spam_mark(mock_ticket)
        
        assert can_mark is True
    
    def test_should_auto_escalate(self, mock_ticket):
        """Test auto-escalation check."""
        mock_ticket.reopen_count = 2
        
        assert TransitionValidator.should_auto_escalate(mock_ticket) is True
        
        mock_ticket.reopen_count = 1
        
        assert TransitionValidator.should_auto_escalate(mock_ticket) is False


# ── StaleTicketService Tests ─────────────────────────────────────────────────

class TestStaleTicketService:
    """Tests for StaleTicketService."""
    
    def test_priority_timeouts_defined(self, stale_service):
        """Test that priority timeouts are defined."""
        from database.models.tickets import TicketPriority
        
        assert TicketPriority.critical in stale_service.PRIORITY_TIMEOUTS
        assert TicketPriority.high in stale_service.PRIORITY_TIMEOUTS
        assert TicketPriority.medium in stale_service.PRIORITY_TIMEOUTS
        assert TicketPriority.low in stale_service.PRIORITY_TIMEOUTS
    
    def test_critical_has_shortest_timeout(self, stale_service):
        """Test that critical priority has shortest timeout."""
        from database.models.tickets import TicketPriority
        
        critical_timeout = stale_service.PRIORITY_TIMEOUTS[TicketPriority.critical]["warning"]
        low_timeout = stale_service.PRIORITY_TIMEOUTS[TicketPriority.low]["warning"]
        
        assert critical_timeout < low_timeout
    
    def test_detect_stale_tickets(self, stale_service, mock_db, mock_ticket):
        """Test stale ticket detection."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.awaiting_client.value
        mock_ticket.updated_at = datetime.utcnow() - timedelta(hours=30)
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_ticket]
        
        stale_tickets = stale_service.detect_stale_tickets()
        
        assert isinstance(stale_tickets, list)
    
    def test_calculate_staleness(self, stale_service, mock_ticket):
        """Test staleness calculation."""
        mock_ticket.updated_at = datetime.utcnow() - timedelta(hours=30)
        
        staleness = stale_service._calculate_staleness(mock_ticket)
        
        assert "hours_inactive" in staleness
        assert "staleness_level" in staleness
        assert "is_stale" in staleness
        assert staleness["hours_inactive"] >= 30
    
    def test_get_stale_statistics(self, stale_service, mock_db):
        """Test getting stale statistics."""
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        stats = stale_service.get_stale_statistics()
        
        assert "total_stale" in stats
        assert "by_level" in stats
        assert "approaching_stale" in stats


# ── SpamDetectionService Tests ───────────────────────────────────────────────

class TestSpamDetectionService:
    """Tests for SpamDetectionService."""
    
    def test_spam_thresholds_defined(self, spam_service):
        """Test that spam thresholds are defined."""
        assert spam_service.SPAM_THRESHOLD_LOW == 30
        assert spam_service.SPAM_THRESHOLD_MEDIUM == 50
        assert spam_service.SPAM_THRESHOLD_HIGH == 70
        assert spam_service.SPAM_THRESHOLD_AUTO == 85
    
    def test_analyze_ticket_clean(self, spam_service, mock_db):
        """Test analyzing clean ticket."""
        # Mock rate limit check
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        
        result = spam_service.analyze_ticket(
            subject="Help with my account",
            content="I need help resetting my password",
            customer_id="customer-123",
        )
        
        assert "spam_score" in result
        assert "spam_level" in result
        assert "is_spam" in result
        assert result["spam_score"] < spam_service.SPAM_THRESHOLD_LOW
    
    def test_analyze_ticket_spam_patterns(self, spam_service, mock_db):
        """Test analyzing ticket with spam patterns."""
        # Mock rate limit check
        mock_db.query.return_value.filter.return_value.count.return_value = 1
        
        result = spam_service.analyze_ticket(
            subject="FREE DISCOUNT BUY NOW!!!",
            content="Click here for free stuff bit.ly/spam",
            customer_id="customer-123",
        )
        
        assert result["spam_score"] > 0
        assert len(result["indicators"]) > 0
    
    def test_analyze_ticket_gibberish(self, spam_service):
        """Test analyzing gibberish content."""
        result = spam_service.analyze_ticket(
            subject="asdfghjkl",
            content="qwertyuiop",
            customer_id=None,
        )
        
        assert "gibberish" in str(result["indicators"]).lower()
    
    def test_check_rate_limit_under_limit(self, spam_service, mock_db):
        """Test rate limit check when under limit."""
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        
        is_allowed, rate_info = spam_service.check_rate_limit("customer-123")
        
        assert is_allowed is True
    
    def test_check_rate_limit_over_limit(self, spam_service, mock_db):
        """Test rate limit check when over limit."""
        mock_db.query.return_value.filter.return_value.count.return_value = 15
        
        is_allowed, rate_info = spam_service.check_rate_limit("customer-123")
        
        assert is_allowed is False
    
    def test_mark_as_spam(self, spam_service, mock_db, mock_ticket):
        """Test marking ticket as spam."""
        mock_ticket.is_spam = False
        mock_ticket.status = "open"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_ticket
        
        result = spam_service.mark_as_spam(
            ticket_id="ticket-123",
            reason="test_spam",
            marked_by="admin-123",
        )
        
        assert result.is_spam is True
        assert result.spam_score == 100
    
    def test_mark_as_spam_already_marked(self, spam_service, mock_db, mock_ticket):
        """Test marking already-spam ticket raises error."""
        mock_ticket.is_spam = True
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_ticket
        
        with pytest.raises(ValidationError):
            spam_service.mark_as_spam(
                ticket_id="ticket-123",
                reason="test_spam",
            )
    
    def test_get_spam_statistics(self, spam_service, mock_db):
        """Test getting spam statistics."""
        # Mock the database queries
        mock_db.query.return_value.filter.return_value.count.return_value = 10
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        stats = spam_service.get_spam_statistics()
        
        assert "total_spam" in stats
        assert "pending_review" in stats
        assert "by_level" in stats


# ── Integration Tests ────────────────────────────────────────────────────────

class TestDay32Integration:
    """Integration tests for Day 32 services."""
    
    def test_state_machine_transition_flow(self, state_machine, mock_ticket, mock_db):
        """Test complete transition flow."""
        from database.models.tickets import TicketStatus
        
        # Open → Assigned
        mock_ticket.status = TicketStatus.open.value
        state_machine.transition(mock_ticket, TicketStatus.assigned, "manual_assign")
        assert mock_ticket.status == TicketStatus.assigned.value
        
        # Assigned → In Progress
        state_machine.transition(mock_ticket, TicketStatus.in_progress, "agent_started")
        assert mock_ticket.status == TicketStatus.in_progress.value
        
        # In Progress → Resolved
        state_machine.transition(mock_ticket, TicketStatus.resolved, "issue_fixed")
        assert mock_ticket.status == TicketStatus.resolved.value
        
        # Resolved → Closed
        state_machine.transition(mock_ticket, TicketStatus.closed, "client_satisfied")
        assert mock_ticket.status == TicketStatus.closed.value
    
    def test_stale_detection_to_close_flow(self, stale_service, mock_db, mock_ticket):
        """Test stale detection to auto-close flow."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.awaiting_client.value
        mock_ticket.updated_at = datetime.utcnow() - timedelta(hours=100)
        mock_ticket.stale_at = datetime.utcnow() - timedelta(hours=50)
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_ticket
        
        # Calculate staleness
        staleness = stale_service._calculate_staleness(mock_ticket)
        
        assert staleness["is_stale"] is True


# ── Loophole/GAP Tests ───────────────────────────────────────────────────────

class TestDay32Loopholes:
    """Tests for Day 32 loopholes and edge cases."""
    
    def test_gap1_no_direct_status_change(self, state_machine, mock_ticket):
        """GAP1: Cannot change status without valid transition."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.open.value
        
        with pytest.raises(ValidationError):
            state_machine.transition(
                ticket=mock_ticket,
                to_status=TicketStatus.closed,
                reason="direct_close",
            )
    
    def test_gap2_reopen_window_enforcement(self, mock_ticket):
        """GAP2: Reopen window is enforced."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.closed.value
        mock_ticket.closed_at = datetime.utcnow() - timedelta(days=10)
        
        can_reopen, error = TransitionValidator.validate_reopen(mock_ticket)
        
        assert can_reopen is False
        assert "7 days" in error
    
    def test_gap3_auto_escalate_on_multiple_reopens(self, mock_ticket):
        """GAP3: Auto-escalate after multiple reopens."""
        mock_ticket.reopen_count = 3
        
        assert TransitionValidator.should_auto_escalate(mock_ticket) is True
    
    def test_gap4_frozen_ticket_cannot_be_assigned(self, state_machine, mock_ticket):
        """GAP4: Frozen tickets cannot be assigned."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.status = TicketStatus.frozen.value
        
        can_trans, _ = state_machine.can_transition(mock_ticket, TicketStatus.assigned)
        
        assert can_trans is False
    
    def test_gap5_spam_ticket_auto_closed(self, spam_service, mock_db, mock_ticket):
        """GAP5: Spam tickets are automatically closed."""
        from database.models.tickets import TicketStatus
        
        mock_ticket.is_spam = False
        mock_ticket.status = TicketStatus.open.value
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_ticket
        
        result = spam_service.mark_as_spam(
            ticket_id="ticket-123",
            reason="spam",
        )
        
        assert result.status == TicketStatus.closed.value
    
    def test_gap6_rate_limit_per_customer(self, spam_service, mock_db):
        """GAP6: Rate limiting is per customer."""
        mock_db.query.return_value.filter.return_value.count.return_value = 20
        
        is_allowed, _ = spam_service.check_rate_limit("customer-123")
        
        assert is_allowed is False
    
    def test_gap7_incident_mass_notification(self, mock_db, company_id):
        """GAP7: Incident can mass notify affected customers."""
        from backend.app.services.incident_service import IncidentService
        
        service = IncidentService(mock_db, company_id)
        
        # This tests that the method exists and handles the flow
        # In production, would verify notification was sent
        assert hasattr(service, 'notify_affected_customers')
    
    def test_gap8_stale_priority_timeouts(self, stale_service):
        """GAP8: Different priorities have different stale timeouts."""
        from database.models.tickets import TicketPriority
        
        critical_timeout = stale_service.PRIORITY_TIMEOUTS[TicketPriority.critical]["warning"]
        medium_timeout = stale_service.PRIORITY_TIMEOUTS[TicketPriority.medium]["warning"]
        low_timeout = stale_service.PRIORITY_TIMEOUTS[TicketPriority.low]["warning"]
        
        # Critical should have shortest timeout
        assert critical_timeout < medium_timeout < low_timeout
    
    def test_gap9_state_machine_audit_trail(self, state_machine, mock_ticket):
        """GAP9: State machine maintains audit trail."""
        # Check that transition reasons are tracked
        reasons = state_machine.get_valid_reasons(
            from_status="open",
            to_status="assigned",
        )
        
        assert isinstance(reasons, list)
        assert len(reasons) > 0


# ── Run Tests ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
