"""
Day 3 Unit Tests - Shadow Mode Ticket Integration

Tests for:
- evaluate_ticket_shadow
- resolve_ticket_with_shadow (both shadow and auto-execute paths)
- approve_ticket_resolution
- undo_ticket_resolution
- get_ticket_shadow_details
- shadow_status filtering
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock
from decimal import Decimal

from app.services.ticket_service import TicketService
from app.exceptions import NotFoundError, ValidationError
from database.models.tickets import (
    Ticket,
    Customer,
    TicketStatus,
    TicketPriority,
)
from database.models.shadow_mode import ShadowLog


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_company_id():
    """Test company ID."""
    return "test-company-123"


@pytest.fixture
def ticket_service(mock_db, mock_company_id):
    """Ticket service instance."""
    return TicketService(mock_db, mock_company_id)


@pytest.fixture
def sample_ticket():
    """Sample ticket for testing."""
    ticket = Ticket()
    ticket.id = "ticket-123"
    ticket.company_id = "test-company-123"
    ticket.customer_id = "customer-456"
    ticket.channel = "email"
    ticket.status = TicketStatus.in_progress.value
    ticket.subject = "Test ticket"
    ticket.priority = TicketPriority.medium.value
    ticket.category = None
    ticket.tags = "[]"
    ticket.assigned_to = None
    ticket.reopen_count = 0
    ticket.frozen = False
    ticket.is_spam = False
    ticket.awaiting_human = False
    ticket.awaiting_client = False
    ticket.escalation_level = 1
    ticket.sla_breached = False
    ticket.shadow_status = "none"
    ticket.shadow_log_id = None
    ticket.risk_score = None
    ticket.approved_by = None
    ticket.approved_at = None
    ticket.created_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    ticket.closed_at = None
    return ticket


@pytest.fixture
def pending_approval_ticket(sample_ticket):
    """Ticket pending shadow approval."""
    sample_ticket.shadow_status = "pending_approval"
    sample_ticket.shadow_log_id = "shadow-log-123"
    sample_ticket.risk_score = Decimal("0.6500")
    return sample_ticket


@pytest.fixture
def approved_ticket(sample_ticket):
    """Approved shadow ticket."""
    sample_ticket.shadow_status = "approved"
    sample_ticket.shadow_log_id = "shadow-log-123"
    sample_ticket.risk_score = Decimal("0.6500")
    sample_ticket.approved_by = "manager-123"
    sample_ticket.approved_at = datetime.now(timezone.utc)
    sample_ticket.status = TicketStatus.resolved.value
    return sample_ticket


@pytest.fixture
def auto_approved_ticket(sample_ticket):
    """Auto-approved shadow ticket."""
    sample_ticket.shadow_status = "auto_approved"
    sample_ticket.shadow_log_id = "shadow-log-123"
    sample_ticket.risk_score = Decimal("0.2000")
    sample_ticket.status = TicketStatus.resolved.value
    return sample_ticket


# ── EVALUATE TICKET SHADOW TESTS ─────────────────────────────────────────────

class TestEvaluateTicketShadow:
    """Tests for evaluate_ticket_shadow method."""

    def test_evaluate_ticket_shadow_success(self, ticket_service, mock_db, sample_ticket):
        """Test successful shadow evaluation."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket):
            with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                mock_shadow = MagicMock()
                mock_shadow.evaluate_action_risk.return_value = {
                    "requires_approval": True,
                    "risk_score": 0.65,
                    "mode": "supervised",
                    "reason": "Test reason",
                    "layers": {},
                    "auto_execute": False,
                }
                MockShadowService.return_value = mock_shadow

                result = ticket_service.evaluate_ticket_shadow(
                    ticket_id="ticket-123",
                    action_type="ticket_close",
                )

        assert result["requires_approval"] is True
        assert result["risk_score"] == 0.65
        assert result["mode"] == "supervised"
        assert result["shadow_log_id"] is None
        assert "error" not in result

    def test_evaluate_ticket_shadow_auto_execute(self, ticket_service, mock_db, sample_ticket):
        """Test shadow evaluation with auto-execute result."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket):
            with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                mock_shadow = MagicMock()
                mock_shadow.evaluate_action_risk.return_value = {
                    "requires_approval": False,
                    "risk_score": 0.15,
                    "mode": "graduated",
                    "reason": "Low risk, auto-execute",
                    "layers": {},
                    "auto_execute": True,
                }
                MockShadowService.return_value = mock_shadow

                result = ticket_service.evaluate_ticket_shadow(
                    ticket_id="ticket-123",
                    action_type="ticket_close",
                )

        assert result["requires_approval"] is False
        assert result["risk_score"] == 0.15
        assert result["mode"] == "graduated"
        assert result["auto_execute"] is True

    def test_evaluate_ticket_shadow_not_found(self, ticket_service, mock_db):
        """Test shadow evaluation when ticket not found."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=NotFoundError("Ticket not found")
        ):
            result = ticket_service.evaluate_ticket_shadow(
                ticket_id="nonexistent-ticket",
                action_type="ticket_close",
            )

        assert result["requires_approval"] is True
        assert result["risk_score"] == 0.5
        assert result["mode"] == "supervised"
        assert result["error"] == "Ticket not found"

    def test_evaluate_ticket_shadow_exception(self, ticket_service, mock_db):
        """Test shadow evaluation handles exceptions gracefully (BC-008)."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=Exception("Unexpected error")
        ):
            result = ticket_service.evaluate_ticket_shadow(
                ticket_id="ticket-123",
                action_type="ticket_close",
            )

        assert result["requires_approval"] is True
        assert result["error"] == "Unexpected error"


# ── RESOLVE TICKET WITH SHADOW TESTS ────────────────────────────────────────

class TestResolveTicketWithShadow:
    """Tests for resolve_ticket_with_shadow method."""

    def test_resolve_requires_approval(self, ticket_service, mock_db, sample_ticket):
        """Test resolution that requires approval."""
        sample_ticket.status = TicketStatus.in_progress.value

        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket):
            with patch.object(
                ticket_service, 'evaluate_ticket_shadow',
                return_value={
                    "requires_approval": True,
                    "risk_score": 0.65,
                    "mode": "supervised",
                    "auto_execute": False,
                }
            ):
                with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                    mock_shadow = MagicMock()
                    mock_shadow.log_shadow_action.return_value = {"id": "shadow-log-123"}
                    MockShadowService.return_value = mock_shadow

                    result = ticket_service.resolve_ticket_with_shadow(
                        ticket_id="ticket-123",
                        manager_id="manager-123",
                        resolution_note="Test resolution",
                    )

        assert result["success"] is True
        assert result["pending_approval"] is True
        assert result["resolved"] is False
        assert result["shadow_log_id"] == "shadow-log-123"
        assert sample_ticket.shadow_status == "pending_approval"

    def test_resolve_auto_execute(self, ticket_service, mock_db, sample_ticket):
        """Test auto-execute resolution."""
        sample_ticket.status = TicketStatus.in_progress.value

        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket):
            with patch.object(
                ticket_service, 'evaluate_ticket_shadow',
                return_value={
                    "requires_approval": False,
                    "risk_score": 0.15,
                    "mode": "graduated",
                    "auto_execute": True,
                }
            ):
                with patch.object(ticket_service, '_record_status_change'):
                    with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                        mock_shadow = MagicMock()
                        mock_shadow.log_shadow_action.return_value = {"id": "shadow-log-123"}
                        mock_shadow.approve_shadow_action.return_value = {"id": "shadow-log-123"}
                        MockShadowService.return_value = mock_shadow

                        result = ticket_service.resolve_ticket_with_shadow(
                            ticket_id="ticket-123",
                            manager_id="manager-123",
                            resolution_note="Auto resolution",
                        )

        assert result["success"] is True
        assert result["resolved"] is True
        assert result["pending_approval"] is False
        assert sample_ticket.shadow_status == "auto_approved"
        assert sample_ticket.status == TicketStatus.resolved.value

    def test_resolve_invalid_status(self, ticket_service, mock_db, sample_ticket):
        """Test resolution fails for invalid ticket status."""
        sample_ticket.status = TicketStatus.open.value

        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket):
            with patch.object(
                ticket_service, 'evaluate_ticket_shadow',
                return_value={
                    "requires_approval": True,
                    "risk_score": 0.5,
                    "mode": "supervised",
                    "auto_execute": False,
                }
            ):
                result = ticket_service.resolve_ticket_with_shadow(
                    ticket_id="ticket-123",
                    manager_id="manager-123",
                )

        assert result["success"] is False
        assert "Cannot resolve ticket in status" in result["error"]

    def test_resolve_ticket_not_found(self, ticket_service, mock_db):
        """Test resolution when ticket not found."""
        with patch.object(
            ticket_service, 'evaluate_ticket_shadow',
            return_value={"requires_approval": True, "risk_score": 0.5, "mode": "supervised"}
        ):
            with patch.object(
                ticket_service, 'get_ticket',
                side_effect=NotFoundError("Ticket not found")
            ):
                result = ticket_service.resolve_ticket_with_shadow(
                    ticket_id="nonexistent-ticket",
                )

        assert result["success"] is False
        assert result["error"] == "Ticket not found"


# ── APPROVE TICKET RESOLUTION TESTS ─────────────────────────────────────────

class TestApproveTicketResolution:
    """Tests for approve_ticket_resolution method."""

    def test_approve_success(self, ticket_service, mock_db, pending_approval_ticket):
        """Test successful approval."""
        mock_db.query.return_value.filter.return_value.first.return_value = pending_approval_ticket

        with patch.object(ticket_service, 'get_ticket', return_value=pending_approval_ticket):
            with patch.object(ticket_service, '_record_status_change'):
                with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                    mock_shadow = MagicMock()
                    mock_shadow.approve_shadow_action.return_value = {"id": "shadow-log-123"}
                    MockShadowService.return_value = mock_shadow

                    result = ticket_service.approve_ticket_resolution(
                        ticket_id="ticket-123",
                        manager_id="manager-123",
                        note="Approved for testing",
                    )

        assert result["success"] is True
        assert result["shadow_status"] == "approved"
        assert result["approved_by"] == "manager-123"
        assert pending_approval_ticket.status == TicketStatus.resolved.value

    def test_approve_not_pending(self, ticket_service, mock_db, sample_ticket):
        """Test approval fails when ticket is not pending."""
        sample_ticket.shadow_status = "approved"

        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket):
            result = ticket_service.approve_ticket_resolution(
                ticket_id="ticket-123",
                manager_id="manager-123",
            )

        assert result["success"] is False
        assert "not pending approval" in result["error"]

    def test_approve_no_shadow_log(self, ticket_service, mock_db, pending_approval_ticket):
        """Test approval fails when no shadow log exists."""
        pending_approval_ticket.shadow_log_id = None

        with patch.object(ticket_service, 'get_ticket', return_value=pending_approval_ticket):
            result = ticket_service.approve_ticket_resolution(
                ticket_id="ticket-123",
                manager_id="manager-123",
            )

        assert result["success"] is False
        assert "No shadow log entry" in result["error"]

    def test_approve_ticket_not_found(self, ticket_service, mock_db):
        """Test approval when ticket not found."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=NotFoundError("Ticket not found")
        ):
            result = ticket_service.approve_ticket_resolution(
                ticket_id="nonexistent-ticket",
                manager_id="manager-123",
            )

        assert result["success"] is False
        assert result["error"] == "Ticket not found"


# ── UNDO TICKET RESOLUTION TESTS ────────────────────────────────────────────

class TestUndoTicketResolution:
    """Tests for undo_ticket_resolution method."""

    def test_undo_approved_ticket(self, ticket_service, mock_db, approved_ticket):
        """Test undoing an approved resolution."""
        with patch.object(ticket_service, 'get_ticket', return_value=approved_ticket):
            with patch.object(ticket_service, '_record_status_change'):
                with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                    mock_shadow = MagicMock()
                    mock_shadow.undo_auto_approved_action.return_value = {
                        "undo_id": "undo-log-123",
                        "shadow_log_id": "shadow-log-123",
                    }
                    MockShadowService.return_value = mock_shadow

                    result = ticket_service.undo_ticket_resolution(
                        ticket_id="ticket-123",
                        reason="Mistaken approval",
                        manager_id="manager-456",
                    )

        assert result["success"] is True
        assert result["shadow_status"] == "undone"
        assert result["ticket_status"] == TicketStatus.reopened.value
        assert approved_ticket.reopen_count == 1

    def test_undo_auto_approved_ticket(self, ticket_service, mock_db, auto_approved_ticket):
        """Test undoing an auto-approved resolution."""
        with patch.object(ticket_service, 'get_ticket', return_value=auto_approved_ticket):
            with patch.object(ticket_service, '_record_status_change'):
                with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                    mock_shadow = MagicMock()
                    mock_shadow.undo_auto_approved_action.return_value = {
                        "undo_id": "undo-log-123",
                    }
                    MockShadowService.return_value = mock_shadow

                    result = ticket_service.undo_ticket_resolution(
                        ticket_id="ticket-123",
                        reason="Incorrect auto-approval",
                    )

        assert result["success"] is True
        assert result["shadow_status"] == "undone"

    def test_undo_not_approved_state(self, ticket_service, mock_db, pending_approval_ticket):
        """Test undo fails when ticket is not in approved state."""
        with patch.object(ticket_service, 'get_ticket', return_value=pending_approval_ticket):
            result = ticket_service.undo_ticket_resolution(
                ticket_id="ticket-123",
                reason="Test undo",
            )

        assert result["success"] is False
        assert "not in an approved state" in result["error"]

    def test_undo_no_shadow_log(self, ticket_service, mock_db, approved_ticket):
        """Test undo fails when no shadow log exists."""
        approved_ticket.shadow_log_id = None

        with patch.object(ticket_service, 'get_ticket', return_value=approved_ticket):
            result = ticket_service.undo_ticket_resolution(
                ticket_id="ticket-123",
                reason="Test undo",
            )

        assert result["success"] is False
        assert "No shadow log entry" in result["error"]

    def test_undo_ticket_not_found(self, ticket_service, mock_db):
        """Test undo when ticket not found."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=NotFoundError("Ticket not found")
        ):
            result = ticket_service.undo_ticket_resolution(
                ticket_id="nonexistent-ticket",
                reason="Test undo",
            )

        assert result["success"] is False
        assert result["error"] == "Ticket not found"


# ── GET TICKET SHADOW DETAILS TESTS ─────────────────────────────────────────

class TestGetTicketShadowDetails:
    """Tests for get_ticket_shadow_details method."""

    def test_get_shadow_details_with_log(self, ticket_service, mock_db, approved_ticket):
        """Test getting shadow details with shadow log."""
        mock_shadow_log = MagicMock()
        mock_shadow_log.id = "shadow-log-123"
        mock_shadow_log.action_type = "ticket_close"
        mock_shadow_log.mode = "supervised"
        mock_shadow_log.jarvis_risk_score = 0.65
        mock_shadow_log.manager_decision = "approved"
        mock_shadow_log.manager_note = "Test note"
        mock_shadow_log.resolved_at = datetime.now(timezone.utc)
        mock_shadow_log.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = mock_shadow_log

        with patch.object(ticket_service, 'get_ticket', return_value=approved_ticket):
            result = ticket_service.get_ticket_shadow_details(ticket_id="ticket-123")

        assert result["ticket_id"] == "ticket-123"
        assert result["shadow_status"] == "approved"
        assert result["shadow_log_id"] == "shadow-log-123"
        assert result["shadow_log"] is not None
        assert result["shadow_log"]["action_type"] == "ticket_close"

    def test_get_shadow_details_no_log(self, ticket_service, mock_db, sample_ticket):
        """Test getting shadow details without shadow log."""
        sample_ticket.shadow_log_id = None

        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket):
            result = ticket_service.get_ticket_shadow_details(ticket_id="ticket-123")

        assert result["ticket_id"] == "ticket-123"
        assert result["shadow_status"] == "none"
        assert result["shadow_log_id"] is None
        assert "shadow_log" not in result

    def test_get_shadow_details_not_found(self, ticket_service, mock_db):
        """Test getting shadow details when ticket not found."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=NotFoundError("Ticket not found")
        ):
            result = ticket_service.get_ticket_shadow_details(
                ticket_id="nonexistent-ticket"
            )

        assert result["ticket_id"] == "nonexistent-ticket"
        assert result["error"] == "Ticket not found"


# ── SHADOW STATUS FILTERING TESTS ───────────────────────────────────────────

class TestShadowStatusFiltering:
    """Tests for shadow_status filtering in list_tickets."""

    def test_filter_pending_approval(self, ticket_service, mock_db, pending_approval_ticket, sample_ticket):
        """Test filtering by pending_approval shadow status."""
        # Create list with mixed shadow statuses
        sample_ticket.shadow_status = "none"
        tickets = [pending_approval_ticket, sample_ticket]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = tickets
        mock_db.query.return_value = mock_query

        result, total = ticket_service.list_tickets()

        # Filter in Python (as done in the API)
        filtered = [t for t in result if getattr(t, 'shadow_status', 'none') == 'pending_approval']

        assert len(filtered) == 1
        assert filtered[0].shadow_status == "pending_approval"

    def test_filter_approved(self, ticket_service, mock_db, approved_ticket, sample_ticket):
        """Test filtering by approved shadow status."""
        sample_ticket.shadow_status = "none"
        tickets = [approved_ticket, sample_ticket]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = tickets
        mock_db.query.return_value = mock_query

        result, total = ticket_service.list_tickets()

        filtered = [t for t in result if getattr(t, 'shadow_status', 'none') == 'approved']

        assert len(filtered) == 1
        assert filtered[0].shadow_status == "approved"


# ── BC-008 DEFENSIVE ERROR HANDLING TESTS ───────────────────────────────────

class TestDefensiveErrorHandling:
    """Tests for BC-008: Never crash the caller."""

    def test_evaluate_handles_all_exceptions(self, ticket_service):
        """Test evaluate_ticket_shadow never crashes on any exception."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=RuntimeError("Unexpected error")
        ):
            result = ticket_service.evaluate_ticket_shadow("ticket-123", "ticket_close")

        assert result["requires_approval"] is True
        assert result["mode"] == "supervised"
        assert "error" in result

    def test_resolve_handles_all_exceptions(self, ticket_service):
        """Test resolve_ticket_with_shadow never crashes on any exception."""
        with patch.object(
            ticket_service, 'evaluate_ticket_shadow',
            return_value={"requires_approval": True, "risk_score": 0.5, "mode": "supervised"}
        ):
            with patch.object(
                ticket_service, 'get_ticket',
                side_effect=RuntimeError("DB error")
            ):
                result = ticket_service.resolve_ticket_with_shadow("ticket-123")

        assert result["success"] is False
        assert "error" in result

    def test_approve_handles_all_exceptions(self, ticket_service):
        """Test approve_ticket_resolution never crashes on any exception."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=RuntimeError("DB error")
        ):
            result = ticket_service.approve_ticket_resolution(
                "ticket-123",
                "manager-123",
            )

        assert result["success"] is False
        assert "error" in result

    def test_undo_handles_all_exceptions(self, ticket_service):
        """Test undo_ticket_resolution never crashes on any exception."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=RuntimeError("DB error")
        ):
            result = ticket_service.undo_ticket_resolution(
                "ticket-123",
                "Test reason",
            )

        assert result["success"] is False
        assert "error" in result

    def test_get_details_handles_all_exceptions(self, ticket_service):
        """Test get_ticket_shadow_details never crashes on any exception."""
        with patch.object(
            ticket_service, 'get_ticket',
            side_effect=RuntimeError("DB error")
        ):
            result = ticket_service.get_ticket_shadow_details("ticket-123")

        assert "error" in result
        assert result["ticket_id"] == "ticket-123"


# ── BC-001 COMPANY SCOPING TESTS ─────────────────────────────────────────────

class TestCompanyScoping:
    """Tests for BC-001: All operations scoped by company_id."""

    def test_evaluate_uses_company_id(self, ticket_service, sample_ticket):
        """Test evaluate uses correct company_id."""
        with patch.object(ticket_service, 'get_ticket', return_value=sample_ticket) as mock_get:
            with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                mock_shadow = MagicMock()
                mock_shadow.evaluate_action_risk.return_value = {
                    "requires_approval": True,
                    "risk_score": 0.5,
                    "mode": "supervised",
                }
                MockShadowService.return_value = mock_shadow

                ticket_service.evaluate_ticket_shadow("ticket-123", "ticket_close")

                # Verify get_ticket was called which uses company_id scoping
                mock_get.assert_called_once_with("ticket-123")

    def test_approve_scoped_to_company(self, ticket_service, pending_approval_ticket):
        """Test approve is scoped to correct company."""
        with patch.object(ticket_service, 'get_ticket', return_value=pending_approval_ticket) as mock_get:
            with patch.object(ticket_service, '_record_status_change'):
                with patch('app.services.ticket_service.ShadowModeService') as MockShadowService:
                    mock_shadow = MagicMock()
                    mock_shadow.approve_shadow_action.return_value = {"id": "shadow-log-123"}
                    MockShadowService.return_value = mock_shadow

                    ticket_service.approve_ticket_resolution("ticket-123", "manager-123")

                    # Verify get_ticket was called (which enforces company_id)
                    mock_get.assert_called_once_with("ticket-123")
