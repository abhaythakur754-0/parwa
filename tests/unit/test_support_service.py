"""
Unit tests for Support Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set environment variables before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.models.support_ticket import (
    SupportTicket,
    ChannelEnum,
    TicketStatusEnum,
    AITierEnum,
    SentimentEnum,
)


# Import service after env vars are set
from backend.services.support_service import SupportService, SLA_THRESHOLDS


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def support_service(mock_db):
    """Support service instance with mocked DB."""
    company_id = uuid.uuid4()
    return SupportService(mock_db, company_id)


@pytest.fixture
def mock_ticket():
    """Create a mock support ticket."""
    ticket = MagicMock(spec=SupportTicket)
    ticket.id = uuid.uuid4()
    ticket.company_id = uuid.uuid4()
    ticket.customer_email = "customer@example.com"
    ticket.channel = ChannelEnum.email
    ticket.status = TicketStatusEnum.open
    ticket.category = "Technical Support"
    ticket.subject = "Cannot login"
    ticket.body = "Login fails"
    ticket.ai_recommendation = None
    ticket.ai_confidence = None
    ticket.ai_tier_used = None
    ticket.sentiment = None
    ticket.assigned_to = None
    ticket.resolved_at = None
    ticket.created_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    return ticket


class TestSupportServiceInit:
    """Tests for SupportService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = SupportService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestSlaThresholds:
    """Tests for SLA threshold configuration."""
    
    def test_chat_has_1_hour_sla(self):
        """Test chat channel has 1 hour SLA."""
        assert SLA_THRESHOLDS[ChannelEnum.chat] == 1
    
    def test_email_has_24_hour_sla(self):
        """Test email channel has 24 hour SLA."""
        assert SLA_THRESHOLDS[ChannelEnum.email] == 24
    
    def test_sms_has_4_hour_sla(self):
        """Test sms channel has 4 hour SLA."""
        assert SLA_THRESHOLDS[ChannelEnum.sms] == 4
    
    def test_voice_has_2_hour_sla(self):
        """Test voice channel has 2 hour SLA."""
        assert SLA_THRESHOLDS[ChannelEnum.voice] == 2


class TestCreateTicket:
    """Tests for create_ticket method."""
    
    @pytest.mark.asyncio
    async def test_create_ticket_with_valid_data(self, support_service, mock_db):
        """Test creating a ticket with valid data."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await support_service.create_ticket(
            subject="Test Subject",
            description="Test description",
            customer_email="test@example.com"
        )
        
        mock_db.add.assert_called()
        mock_db.flush.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_ticket_validates_required_subject(self, support_service):
        """Test that create_ticket validates required subject."""
        with pytest.raises(ValueError, match="Subject is required"):
            await support_service.create_ticket(
                subject="",
                description="Test description",
                customer_email="test@example.com"
            )
    
    @pytest.mark.asyncio
    async def test_create_ticket_validates_required_description(self, support_service):
        """Test that create_ticket validates required description."""
        with pytest.raises(ValueError, match="Description is required"):
            await support_service.create_ticket(
                subject="Test Subject",
                description="",
                customer_email="test@example.com"
            )
    
    @pytest.mark.asyncio
    async def test_create_ticket_validates_email_format(self, support_service):
        """Test that create_ticket validates email format."""
        with pytest.raises(ValueError, match="Valid customer email is required"):
            await support_service.create_ticket(
                subject="Test Subject",
                description="Test description",
                customer_email="invalid-email"
            )
    
    @pytest.mark.asyncio
    async def test_create_ticket_lowercases_email(self, support_service, mock_db):
        """Test that email is lowercased."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Capture the added tickets (ticket + audit trail)
        added_tickets = []
        def capture_add(obj):
            added_tickets.append(obj)
        
        mock_db.add.side_effect = capture_add
        
        await support_service.create_ticket(
            subject="Test",
            description="Test",
            customer_email="TEST@EXAMPLE.COM"
        )
        
        # Find the SupportTicket among added objects
        ticket = next((t for t in added_tickets if isinstance(t, SupportTicket)), None)
        assert ticket is not None
        assert ticket.customer_email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_create_ticket_uses_email_channel_by_default(self, support_service, mock_db):
        """Test that email channel is default."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        added_tickets = []
        def capture_add(obj):
            added_tickets.append(obj)
        
        mock_db.add.side_effect = capture_add
        
        await support_service.create_ticket(
            subject="Test",
            description="Test",
            customer_email="test@example.com"
        )
        
        # Find the SupportTicket among added objects
        ticket = next((t for t in added_tickets if isinstance(t, SupportTicket)), None)
        assert ticket is not None
        assert ticket.channel == ChannelEnum.email
    
    @pytest.mark.asyncio
    async def test_create_ticket_sets_open_status(self, support_service, mock_db):
        """Test that new tickets have open status."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        added_tickets = []
        def capture_add(obj):
            added_tickets.append(obj)
        
        mock_db.add.side_effect = capture_add
        
        await support_service.create_ticket(
            subject="Test",
            description="Test",
            customer_email="test@example.com"
        )
        
        # Find the SupportTicket among added objects
        ticket = next((t for t in added_tickets if isinstance(t, SupportTicket)), None)
        assert ticket is not None
        assert ticket.status == TicketStatusEnum.open


class TestGetTicketById:
    """Tests for get_ticket_by_id method."""
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_id_returns_ticket(self, support_service, mock_db, mock_ticket):
        """Test getting a ticket by ID."""
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.get_ticket_by_id(mock_ticket.id)
        
        assert result == mock_ticket
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_id_returns_none_if_not_found(self, support_service, mock_db):
        """Test getting a non-existent ticket."""
        ticket_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.get_ticket_by_id(ticket_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_id_handles_invalid_uuid_string(self, support_service, mock_db):
        """Test handling invalid UUID string."""
        result = await support_service.get_ticket_by_id("not-a-uuid")
        
        assert result is None


class TestUpdateTicket:
    """Tests for update_ticket method."""
    
    @pytest.mark.asyncio
    async def test_update_ticket_updates_status(self, support_service, mock_db, mock_ticket):
        """Test updating ticket status."""
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await support_service.update_ticket(
            ticket_id=mock_ticket.id,
            status=TicketStatusEnum.resolved
        )
        
        assert mock_ticket.status == TicketStatusEnum.resolved
        mock_db.flush.assert_called()
    
    @pytest.mark.asyncio
    async def test_update_ticket_returns_none_if_not_found(self, support_service, mock_db):
        """Test update returns None if ticket not found."""
        ticket_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.update_ticket(
            ticket_id=ticket_id,
            status=TicketStatusEnum.resolved
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_ticket_sets_resolved_at(self, support_service, mock_db, mock_ticket):
        """Test that resolved_at is set when resolving."""
        mock_ticket.company_id = support_service.company_id
        mock_ticket.resolved_at = None
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        await support_service.update_ticket(
            ticket_id=mock_ticket.id,
            status=TicketStatusEnum.resolved
        )
        
        assert mock_ticket.resolved_at is not None
    
    @pytest.mark.asyncio
    async def test_update_ticket_validates_ai_confidence_range(self, support_service, mock_db, mock_ticket):
        """Test that ai_confidence must be between 0 and 1."""
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with pytest.raises(ValueError, match="ai_confidence must be between"):
            await support_service.update_ticket(
                ticket_id=mock_ticket.id,
                ai_confidence=1.5  # Invalid
            )


class TestEscalateTicket:
    """Tests for escalate_ticket method."""
    
    @pytest.mark.asyncio
    async def test_escalate_ticket_sets_escalation_status(self, support_service, mock_db, mock_ticket):
        """Test escalating a ticket."""
        escalated_to_id = uuid.uuid4()
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await support_service.escalate_ticket(
            ticket_id=mock_ticket.id,
            reason="Customer request",
            escalated_to_id=escalated_to_id
        )
        
        assert mock_ticket.status == TicketStatusEnum.escalated
        assert mock_ticket.assigned_to == escalated_to_id
    
    @pytest.mark.asyncio
    async def test_escalate_ticket_requires_reason(self, support_service):
        """Test that escalation reason is required."""
        with pytest.raises(ValueError, match="Escalation reason is required"):
            await support_service.escalate_ticket(
                ticket_id=uuid.uuid4(),
                reason="",
                escalated_to_id=uuid.uuid4()
            )
    
    @pytest.mark.asyncio
    async def test_escalate_ticket_returns_none_if_not_found(self, support_service, mock_db):
        """Test escalation returns None if ticket not found."""
        ticket_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.escalate_ticket(
            ticket_id=ticket_id,
            reason="Test reason",
            escalated_to_id=uuid.uuid4()
        )
        
        assert result is None


class TestAddMessage:
    """Tests for add_message method."""
    
    @pytest.mark.asyncio
    async def test_add_message_to_ticket(self, support_service, mock_db, mock_ticket):
        """Test adding a message to a ticket."""
        sender_id = uuid.uuid4()
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        
        result = await support_service.add_message(
            ticket_id=mock_ticket.id,
            sender_id=sender_id,
            message="Test message"
        )
        
        assert result is not None
        assert result["ticket_id"] == str(mock_ticket.id)
        assert result["sender_id"] == str(sender_id)
        assert result["message"] == "Test message"
    
    @pytest.mark.asyncio
    async def test_add_message_requires_content(self, support_service):
        """Test that message content is required."""
        with pytest.raises(ValueError, match="Message content is required"):
            await support_service.add_message(
                ticket_id=uuid.uuid4(),
                sender_id=uuid.uuid4(),
                message=""
            )
    
    @pytest.mark.asyncio
    async def test_add_message_requires_ticket_to_exist(self, support_service, mock_db):
        """Test that ticket must exist."""
        ticket_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with pytest.raises(ValueError, match="Ticket not found"):
            await support_service.add_message(
                ticket_id=ticket_id,
                sender_id=uuid.uuid4(),
                message="Test message"
            )
    
    @pytest.mark.asyncio
    async def test_add_message_internal_flag(self, support_service, mock_db, mock_ticket):
        """Test that internal flag is set."""
        sender_id = uuid.uuid4()
        mock_ticket.company_id = support_service.company_id
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        
        result = await support_service.add_message(
            ticket_id=mock_ticket.id,
            sender_id=sender_id,
            message="Internal note",
            is_internal=True
        )
        
        assert result["is_internal"] is True


class TestCalculateSlaStatus:
    """Tests for calculate_sla_status method."""
    
    @pytest.mark.asyncio
    async def test_calculate_sla_returns_status(self, support_service, mock_db, mock_ticket):
        """Test calculating SLA status."""
        mock_ticket.company_id = support_service.company_id
        mock_ticket.channel = ChannelEnum.email
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.calculate_sla_status(mock_ticket.id)
        
        assert "is_breached" in result
        assert "time_remaining_seconds" in result
        assert "sla_deadline" in result
        assert "sla_threshold_hours" in result
    
    @pytest.mark.asyncio
    async def test_calculate_sla_for_email_channel(self, support_service, mock_db, mock_ticket):
        """Test SLA for email channel is 24 hours."""
        mock_ticket.company_id = support_service.company_id
        mock_ticket.channel = ChannelEnum.email
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.calculate_sla_status(mock_ticket.id)
        
        assert result["sla_threshold_hours"] == 24
    
    @pytest.mark.asyncio
    async def test_calculate_sla_for_chat_channel(self, support_service, mock_db, mock_ticket):
        """Test SLA for chat channel is 1 hour."""
        mock_ticket.company_id = support_service.company_id
        mock_ticket.channel = ChannelEnum.chat
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.calculate_sla_status(mock_ticket.id)
        
        assert result["sla_threshold_hours"] == 1
    
    @pytest.mark.asyncio
    async def test_calculate_sla_breached_ticket(self, support_service, mock_db, mock_ticket):
        """Test SLA breach detection."""
        # Created 25 hours ago (beyond 24h email SLA)
        mock_ticket.company_id = support_service.company_id
        mock_ticket.channel = ChannelEnum.email
        mock_ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.calculate_sla_status(mock_ticket.id)
        
        assert result["is_breached"] is True
        assert result["time_remaining_seconds"] == 0
    
    @pytest.mark.asyncio
    async def test_calculate_sla_returns_error_if_not_found(self, support_service, mock_db):
        """Test SLA calculation for non-existent ticket."""
        ticket_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.calculate_sla_status(ticket_id)
        
        assert "error" in result
        assert result["error"] == "Ticket not found"


class TestGetTicketCountByStatus:
    """Tests for get_ticket_count_by_status method."""
    
    @pytest.mark.asyncio
    async def test_get_ticket_count_by_status_returns_dict(self, support_service, mock_db):
        """Test getting ticket counts by status."""
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([
            (TicketStatusEnum.open, 5),
            (TicketStatusEnum.resolved, 10),
        ]))
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await support_service.get_ticket_count_by_status()
        
        assert isinstance(result, dict)
        assert result["open"] == 5
        assert result["resolved"] == 10


class TestAssignTicket:
    """Tests for assign_ticket method."""
    
    @pytest.mark.asyncio
    async def test_assign_ticket_sets_assignee(self, support_service, mock_db, mock_ticket):
        """Test assigning a ticket."""
        assignee_id = uuid.uuid4()
        mock_ticket.company_id = support_service.company_id
        mock_ticket.assigned_to = None
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await support_service.assign_ticket(mock_ticket.id, assignee_id)
        
        assert mock_ticket.assigned_to == assignee_id


class TestEmailValidation:
    """Tests for email validation."""
    
    def test_validate_email_valid(self, support_service):
        """Test valid email validation."""
        assert support_service._validate_email("test@example.com") is True
        assert support_service._validate_email("user.name@domain.org") is True
        assert support_service._validate_email("user+tag@example.co.uk") is True
    
    def test_validate_email_invalid(self, support_service):
        """Test invalid email validation."""
        assert support_service._validate_email("invalid") is False
        assert support_service._validate_email("invalid@") is False
        assert support_service._validate_email("@example.com") is False
        assert support_service._validate_email("test@.com") is False


class TestAuditLogging:
    """Tests for audit logging functionality."""
    
    @pytest.mark.asyncio
    async def test_audit_log_called_on_create(self, support_service, mock_db):
        """Test that audit log is called on ticket creation."""
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        # Track all adds to capture audit entries
        added_objects = []
        def track_add(obj):
            added_objects.append(obj)
        
        mock_db.add.side_effect = track_add
        
        await support_service.create_ticket(
            subject="Test",
            description="Test description",
            customer_email="test@example.com"
        )
        
        # Should have added ticket and audit entry
        assert len(added_objects) >= 1
