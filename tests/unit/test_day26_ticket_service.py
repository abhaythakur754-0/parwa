"""
Day 26 Unit Tests - Ticket Service

Tests for:
- Ticket CRUD operations
- PS01: Out-of-plan scope check
- PS05: Duplicate detection
- PS07: Account suspended check
- BL05: Rate limiting
- Status machine transitions
- Bulk operations
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from backend.app.services.ticket_service import TicketService
from backend.app.exceptions import NotFoundError, AuthorizationError, ValidationError
from database.models.tickets import (
    Ticket,
    Customer,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    TicketAssignment,
    TicketStatusChange,
)


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
    ticket.status = TicketStatus.open.value
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
    ticket.created_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    ticket.closed_at = None
    return ticket


@pytest.fixture
def sample_customer():
    """Sample customer for testing."""
    customer = Customer()
    customer.id = "customer-456"
    customer.company_id = "test-company-123"
    customer.email = "test@example.com"
    customer.name = "Test Customer"
    return customer


# ── CREATE TICKET TESTS ─────────────────────────────────────────────────────

class TestCreateTicket:
    """Tests for ticket creation."""

    def test_create_ticket_success(self, ticket_service, mock_db, sample_customer):
        """Test successful ticket creation."""
        # Mock customer validation
        mock_db.query.return_value.filter.return_value.first.return_value = sample_customer

        # Mock rate limit service
        with patch.object(ticket_service, '_check_rate_limit'):
            with patch.object(ticket_service, '_check_account_suspended'):
                with patch.object(ticket_service, '_check_scope', return_value=[]):
                    with patch.object(ticket_service, '_check_duplicate', return_value=None):
                        ticket = ticket_service.create_ticket(
                            customer_id="customer-456",
                            channel="email",
                            subject="Test subject",
                            priority=TicketPriority.high.value,
                        )

        # Verify ticket was created
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_ticket_with_tags(self, ticket_service, mock_db, sample_customer):
        """Test ticket creation with tags."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_customer

        with patch.object(ticket_service, '_check_rate_limit'):
            with patch.object(ticket_service, '_check_account_suspended'):
                with patch.object(ticket_service, '_check_scope', return_value=["auto-tag"]):
                    with patch.object(ticket_service, '_check_duplicate', return_value=None):
                        ticket = ticket_service.create_ticket(
                            customer_id="customer-456",
                            channel="email",
                            tags=["urgent", "billing"],
                        )

        assert mock_db.add.called

    def test_create_ticket_rate_limited(self, ticket_service, mock_db):
        """Test BL05: Rate limiting on ticket creation."""
        with patch.object(
            ticket_service, '_check_rate_limit',
            side_effect=AuthorizationError("Rate limit exceeded")
        ):
            with pytest.raises(AuthorizationError) as exc_info:
                ticket_service.create_ticket(
                    customer_id="customer-456",
                    channel="email",
                )
            assert "Rate limit" in str(exc_info.value)

    def test_create_ticket_account_suspended(self, ticket_service, mock_db, sample_customer):
        """Test PS07: Account suspended check."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_customer

        with patch.object(ticket_service, '_check_rate_limit'):
            with patch.object(
                ticket_service, '_check_account_suspended',
                side_effect=AuthorizationError("Account is suspended")
            ):
                with pytest.raises(AuthorizationError) as exc_info:
                    ticket_service.create_ticket(
                        customer_id="customer-456",
                        channel="email",
                    )
                assert "suspended" in str(exc_info.value).lower()

    def test_create_ticket_invalid_customer(self, ticket_service, mock_db):
        """Test validation fails for invalid customer."""
        # Mock customer not found
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch.object(ticket_service, '_check_rate_limit'):
            with patch.object(ticket_service, '_check_account_suspended'):
                with pytest.raises(ValidationError) as exc_info:
                    ticket_service.create_ticket(
                        customer_id="invalid-customer",
                        channel="email",
                    )
                assert "not found" in str(exc_info.value).lower()

    def test_create_ticket_duplicate_detected(self, ticket_service, mock_db, sample_customer):
        """Test PS05: Duplicate detection on create."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_customer

        with patch.object(ticket_service, '_check_rate_limit'):
            with patch.object(ticket_service, '_check_account_suspended'):
                with patch.object(ticket_service, '_check_scope', return_value=[]):
                    with patch.object(
                        ticket_service, '_check_duplicate',
                        return_value="existing-ticket-123"
                    ):
                        ticket = ticket_service.create_ticket(
                            customer_id="customer-456",
                            channel="email",
                            subject="Duplicate subject",
                        )

        assert mock_db.add.called


# ── GET TICKET TESTS ────────────────────────────────────────────────────────

class TestGetTicket:
    """Tests for getting a ticket."""

    def test_get_ticket_success(self, ticket_service, mock_db, sample_ticket):
        """Test successful ticket retrieval."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.get_ticket("ticket-123")

        assert result.id == "ticket-123"
        assert result.company_id == "test-company-123"

    def test_get_ticket_not_found(self, ticket_service, mock_db):
        """Test ticket not found raises error."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            ticket_service.get_ticket("nonexistent-ticket")

        assert "not found" in str(exc_info.value).lower()

    def test_get_ticket_wrong_company(self, ticket_service, mock_db):
        """Test ticket from different company is not accessible."""
        # Mock returns None because company_id filter doesn't match
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            ticket_service.get_ticket("other-company-ticket")


# ── LIST TICKETS TESTS ──────────────────────────────────────────────────────

class TestListTickets:
    """Tests for listing tickets."""

    def test_list_tickets_default(self, ticket_service, mock_db, sample_ticket):
        """Test listing tickets with default parameters."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_ticket]
        mock_db.query.return_value = mock_query

        tickets, total = ticket_service.list_tickets()

        assert total == 1
        assert len(tickets) == 1

    def test_list_tickets_with_status_filter(self, ticket_service, mock_db):
        """Test listing tickets with status filter."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        tickets, total = ticket_service.list_tickets(
            status=[TicketStatus.open.value, TicketStatus.assigned.value]
        )

        assert total == 0

    def test_list_tickets_with_pagination(self, ticket_service, mock_db):
        """Test listing tickets with pagination."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        tickets, total = ticket_service.list_tickets(page=2, page_size=10)

        assert total == 100
        # Verify offset was called with correct value
        mock_query.offset.assert_called_with(10)  # (page-1) * page_size

    def test_list_tickets_with_search(self, ticket_service, mock_db):
        """Test listing tickets with search query."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        tickets, total = ticket_service.list_tickets(search="urgent issue")


# ── UPDATE TICKET TESTS ─────────────────────────────────────────────────────

class TestUpdateTicket:
    """Tests for updating tickets."""

    def test_update_ticket_priority(self, ticket_service, mock_db, sample_ticket):
        """Test updating ticket priority."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.update_ticket(
            ticket_id="ticket-123",
            priority=TicketPriority.critical.value,
        )

        assert mock_db.commit.called

    def test_update_ticket_status_valid_transition(self, ticket_service, mock_db, sample_ticket):
        """Test valid status transition."""
        sample_ticket.status = TicketStatus.open.value
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.update_ticket(
            ticket_id="ticket-123",
            status=TicketStatus.assigned.value,
            user_id="user-123",
            reason="Assigning to agent",
        )

        assert mock_db.commit.called

    def test_update_ticket_status_invalid_transition(self, ticket_service, mock_db, sample_ticket):
        """Test invalid status transition raises error."""
        sample_ticket.status = TicketStatus.open.value
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        with pytest.raises(ValidationError) as exc_info:
            ticket_service.update_ticket(
                ticket_id="ticket-123",
                status=TicketStatus.resolved.value,  # Invalid: open -> resolved
            )

        assert "Invalid status transition" in str(exc_info.value)

    def test_update_ticket_reopen_increments_count(self, ticket_service, mock_db, sample_ticket):
        """Test reopening ticket increments reopen count."""
        sample_ticket.status = TicketStatus.resolved.value
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.update_ticket(
            ticket_id="ticket-123",
            status=TicketStatus.reopened.value,
        )

        assert sample_ticket.reopen_count == 1

    def test_update_ticket_closed_sets_closed_at(self, ticket_service, mock_db, sample_ticket):
        """Test closing ticket sets closed_at timestamp."""
        sample_ticket.status = TicketStatus.resolved.value
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.update_ticket(
            ticket_id="ticket-123",
            status=TicketStatus.closed.value,
        )

        assert sample_ticket.closed_at is not None


# ── DELETE TICKET TESTS ─────────────────────────────────────────────────────

class TestDeleteTicket:
    """Tests for deleting tickets."""

    def test_soft_delete_ticket(self, ticket_service, mock_db, sample_ticket):
        """Test PS12: Soft delete preserves metadata."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.delete_ticket("ticket-123", hard=False)

        assert result is True
        assert sample_ticket.status == TicketStatus.closed.value
        assert sample_ticket.subject == "[DELETED]"
        assert mock_db.commit.called

    def test_hard_delete_ticket(self, ticket_service, mock_db, sample_ticket):
        """Test hard delete removes ticket."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.delete_ticket("ticket-123", hard=True)

        assert result is True
        assert mock_db.delete.called


# ── ASSIGNMENT TESTS ────────────────────────────────────────────────────────

class TestAssignTicket:
    """Tests for ticket assignment."""

    def test_assign_ticket_success(self, ticket_service, mock_db, sample_ticket):
        """Test successful ticket assignment."""
        sample_ticket.status = TicketStatus.open.value
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.assign_ticket(
            ticket_id="ticket-123",
            assignee_id="agent-789",
            assignee_type="human",
            reason="Expert in this area",
        )

        assert sample_ticket.assigned_to == "agent-789"
        assert sample_ticket.status == TicketStatus.assigned.value
        assert mock_db.commit.called

    def test_unassign_ticket(self, ticket_service, mock_db, sample_ticket):
        """Test unassigning a ticket."""
        sample_ticket.assigned_to = "agent-789"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.assign_ticket(
            ticket_id="ticket-123",
            assignee_id=None,
        )

        assert sample_ticket.assigned_to is None

    def test_assign_ticket_records_history(self, ticket_service, mock_db, sample_ticket):
        """Test assignment creates history record."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.assign_ticket(
            ticket_id="ticket-123",
            assignee_id="agent-789",
            assignee_type="ai",
        )

        # Verify TicketAssignment was added
        assert mock_db.add.called


# ── TAGS TESTS ──────────────────────────────────────────────────────────────

class TestTicketTags:
    """Tests for ticket tag operations."""

    def test_add_tags(self, ticket_service, mock_db, sample_ticket):
        """Test adding tags to ticket."""
        sample_ticket.tags = "[]"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.add_tags("ticket-123", ["urgent", "billing"])

        tags = json.loads(result.tags)
        assert "urgent" in tags
        assert "billing" in tags

    def test_add_tags_no_duplicates(self, ticket_service, mock_db, sample_ticket):
        """Test adding duplicate tags doesn't create duplicates."""
        sample_ticket.tags = json.dumps(["urgent"])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.add_tags("ticket-123", ["urgent", "billing"])

        tags = json.loads(result.tags)
        assert tags.count("urgent") == 1
        assert "billing" in tags

    def test_remove_tag(self, ticket_service, mock_db, sample_ticket):
        """Test removing tag from ticket."""
        sample_ticket.tags = json.dumps(["urgent", "billing"])
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        result = ticket_service.remove_tag("ticket-123", "urgent")

        tags = json.loads(result.tags)
        assert "urgent" not in tags
        assert "billing" in tags


# ── STATUS TRANSITION TESTS ─────────────────────────────────────────────────

class TestStatusTransitions:
    """Tests for status state machine."""

    def test_valid_transition_open_to_assigned(self, ticket_service):
        """Test open -> assigned is valid."""
        ticket_service._validate_status_transition(
            TicketStatus.open.value,
            TicketStatus.assigned.value
        )

    def test_valid_transition_assigned_to_in_progress(self, ticket_service):
        """Test assigned -> in_progress is valid."""
        ticket_service._validate_status_transition(
            TicketStatus.assigned.value,
            TicketStatus.in_progress.value
        )

    def test_valid_transition_in_progress_to_resolved(self, ticket_service):
        """Test in_progress -> resolved is valid."""
        ticket_service._validate_status_transition(
            TicketStatus.in_progress.value,
            TicketStatus.resolved.value
        )

    def test_valid_transition_resolved_to_closed(self, ticket_service):
        """Test resolved -> closed is valid."""
        ticket_service._validate_status_transition(
            TicketStatus.resolved.value,
            TicketStatus.closed.value
        )

    def test_valid_transition_resolved_to_reopened(self, ticket_service):
        """Test resolved -> reopened is valid."""
        ticket_service._validate_status_transition(
            TicketStatus.resolved.value,
            TicketStatus.reopened.value
        )

    def test_valid_transition_closed_to_reopened(self, ticket_service):
        """Test closed -> reopened is valid."""
        ticket_service._validate_status_transition(
            TicketStatus.closed.value,
            TicketStatus.reopened.value
        )

    def test_invalid_transition_open_to_resolved(self, ticket_service):
        """Test open -> resolved is invalid."""
        with pytest.raises(ValidationError):
            ticket_service._validate_status_transition(
                TicketStatus.open.value,
                TicketStatus.resolved.value
            )

    def test_invalid_transition_closed_to_open(self, ticket_service):
        """Test closed -> open is invalid."""
        with pytest.raises(ValidationError):
            ticket_service._validate_status_transition(
                TicketStatus.closed.value,
                TicketStatus.open.value
            )


# ── DUPLICATE DETECTION TESTS ───────────────────────────────────────────────

class TestDuplicateDetection:
    """Tests for PS05: Duplicate detection."""

    def test_calculate_similarity_identical(self, ticket_service):
        """Test similarity calculation for identical strings."""
        similarity = ticket_service._calculate_similarity(
            "I cannot login to my account",
            "I cannot login to my account"
        )
        assert similarity == 1.0

    def test_calculate_similarity_different(self, ticket_service):
        """Test similarity calculation for different strings."""
        similarity = ticket_service._calculate_similarity(
            "I cannot login to my account",
            "The weather is nice today"
        )
        assert similarity < 0.3

    def test_calculate_similarity_similar(self, ticket_service):
        """Test similarity calculation for similar strings."""
        similarity = ticket_service._calculate_similarity(
            "I cannot login to my account",
            "I can't login to my account"
        )
        assert similarity > 0.5

    def test_check_duplicate_no_subject(self, ticket_service, mock_db):
        """Test duplicate check returns None for empty subject."""
        result = ticket_service._check_duplicate("customer-456", None)
        assert result is None

    def test_check_duplicate_finds_match(self, ticket_service, mock_db, sample_ticket):
        """Test duplicate check finds similar ticket."""
        sample_ticket.subject = "I cannot login to my account"
        sample_ticket.id = "existing-ticket"

        mock_db.query.return_value.filter.return_value.all.return_value = [sample_ticket]

        result = ticket_service._check_duplicate(
            "customer-456",
            "I cannot login to my account"
        )

        assert result == "existing-ticket"


# ── BULK OPERATIONS TESTS ────────────────────────────────────────────────────

class TestBulkOperations:
    """Tests for bulk operations."""

    def test_bulk_update_status_success(self, ticket_service, mock_db, sample_ticket):
        """Test successful bulk status update."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        success_count, failures = ticket_service.bulk_update_status(
            ticket_ids=["ticket-1", "ticket-2"],
            status=TicketStatus.closed.value,
        )

        # Both should succeed since mock returns same ticket
        assert success_count == 2
        assert len(failures) == 0

    def test_bulk_assign_success(self, ticket_service, mock_db, sample_ticket):
        """Test successful bulk assignment."""
        sample_ticket.status = TicketStatus.open.value
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket

        success_count, failures = ticket_service.bulk_assign(
            ticket_ids=["ticket-1", "ticket-2"],
            assignee_id="agent-789",
        )

        assert success_count == 2

    def test_bulk_operation_partial_failure(self, ticket_service, mock_db, sample_ticket):
        """Test bulk operation with partial failures."""
        # First call succeeds, second fails
        call_count = [0]

        def mock_first():
            call_count[0] += 1
            if call_count[0] == 1:
                return sample_ticket
            else:
                raise NotFoundError("Ticket not found")

        mock_db.query.return_value.filter.return_value.first = mock_first

        success_count, failures = ticket_service.bulk_update_status(
            ticket_ids=["ticket-1", "ticket-2"],
            status=TicketStatus.closed.value,
        )

        assert success_count == 1
        assert len(failures) == 1


# ── RATE LIMITING TESTS ──────────────────────────────────────────────────────

class TestRateLimiting:
    """Tests for BL05: Rate limiting."""

    def test_rate_limit_check_passes(self, ticket_service):
        """Test rate limit check passes when under limit."""
        with patch.object(
            ticket_service.rate_limit_service, 'check_rate_limit',
            return_value=True
        ):
            ticket_service._check_rate_limit("user-123")

    def test_rate_limit_check_fails(self, ticket_service):
        """Test rate limit check raises error when over limit."""
        with patch.object(
            ticket_service.rate_limit_service, 'check_rate_limit',
            return_value=False
        ):
            with pytest.raises(AuthorizationError):
                ticket_service._check_rate_limit("user-123")


# ── SCOPE CHECK TESTS ────────────────────────────────────────────────────────

class TestScopeCheck:
    """Tests for PS01: Out-of-plan scope check."""

    def test_scope_check_enterprise_category(self, ticket_service):
        """Test enterprise category gets tagged."""
        tags = ticket_service._check_scope(TicketCategory.feature_request.value)
        assert "enterprise_feature" in tags

    def test_scope_check_regular_category(self, ticket_service):
        """Test regular category gets no extra tags."""
        tags = ticket_service._check_scope(TicketCategory.billing.value)
        assert "enterprise_feature" not in tags

    def test_scope_check_none_category(self, ticket_service):
        """Test None category gets no tags."""
        tags = ticket_service._check_scope(None)
        assert len(tags) == 0
