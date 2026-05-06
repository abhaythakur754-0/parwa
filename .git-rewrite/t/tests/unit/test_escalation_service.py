"""
Unit tests for Escalation Service.

Tests for:
- Stuck ticket detection
- Escalation handling
- Notification dispatch
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.services.escalation_service import (
    EscalationService,
    StuckTicketReason,
)
from backend.services.escalation_ladder import EscalationPhase


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def escalation_service(mock_db):
    """Create escalation service instance."""
    company_id = uuid4()
    service = EscalationService(mock_db, company_id)
    return service


class TestEscalationServiceStuckTickets:
    """Tests for check_stuck_tickets method."""

    @pytest.mark.asyncio
    async def test_check_stuck_tickets_returns_list(self, escalation_service):
        """Test that check_stuck_tickets returns a list."""
        result = await escalation_service.check_stuck_tickets()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_check_stuck_tickets_with_custom_threshold(self, escalation_service):
        """Test check_stuck_tickets with custom threshold."""
        result = await escalation_service.check_stuck_tickets(hours_threshold=48)

        assert isinstance(result, list)


class TestEscalationServiceEscalate:
    """Tests for escalate_ticket method."""

    @pytest.mark.asyncio
    async def test_escalate_ticket_success(self, escalation_service):
        """Test successful ticket escalation."""
        result = await escalation_service.escalate_ticket(
            ticket_id="ticket-123",
            reason="No response for 24 hours",
        )

        assert result["success"] is True
        assert result["ticket_id"] == "ticket-123"

    @pytest.mark.asyncio
    async def test_escalate_ticket_to_specific_phase(self, escalation_service):
        """Test escalation to specific phase."""
        result = await escalation_service.escalate_ticket(
            ticket_id="ticket-123",
            reason="Critical escalation",
            target_phase=EscalationPhase.PHASE_3,
        )

        assert result["success"] is True
        assert result["phase"] == EscalationPhase.PHASE_3.value


class TestEscalationServiceNotify:
    """Tests for notify_escalation method."""

    @pytest.mark.asyncio
    async def test_notify_escalation_agent_level(self, escalation_service):
        """Test notification at agent level."""
        result = await escalation_service.notify_escalation(
            ticket_id="ticket-123",
            level="agent",
        )

        assert result["success"] is True
        assert "assigned_agent" in result["targets_notified"]

    @pytest.mark.asyncio
    async def test_notify_escalation_manager_level(self, escalation_service):
        """Test notification at manager level."""
        result = await escalation_service.notify_escalation(
            ticket_id="ticket-123",
            level="manager",
        )

        assert result["success"] is True
        assert "manager" in result["targets_notified"]

    @pytest.mark.asyncio
    async def test_notify_escalation_custom_targets(self, escalation_service):
        """Test notification with custom targets."""
        result = await escalation_service.notify_escalation(
            ticket_id="ticket-123",
            level="executive",
            targets=["ceo@company.com", "cto@company.com"],
        )

        assert result["success"] is True
        assert "ceo@company.com" in result["targets_notified"]


class TestEscalationServiceAutoEscalate:
    """Tests for auto_escalate method."""

    @pytest.mark.asyncio
    async def test_auto_escalate_runs(self, escalation_service):
        """Test that auto_escalate runs without error."""
        result = await escalation_service.auto_escalate()

        assert result["success"] is True
        assert "checked_at" in result
        assert "escalated_count" in result

    @pytest.mark.asyncio
    async def test_auto_escalate_returns_metrics(self, escalation_service):
        """Test that auto_escalate returns metrics."""
        result = await escalation_service.auto_escalate()

        assert "tickets_checked" in result
        assert "notifications_sent" in result


class TestEscalationServiceStatus:
    """Tests for get_ticket_escalation_status method."""

    @pytest.mark.asyncio
    async def test_get_ticket_escalation_status(self, escalation_service):
        """Test getting ticket escalation status."""
        created_at = datetime.now(timezone.utc) - timedelta(hours=25)

        result = await escalation_service.get_ticket_escalation_status(
            ticket_id="ticket-123",
            ticket_created_at=created_at,
        )

        assert result["ticket_id"] == "ticket-123"
        assert result["current_phase"] >= EscalationPhase.PHASE_1.value
        assert "hours_since_creation" in result


class TestEscalationServiceQueue:
    """Tests for escalation queue management."""

    @pytest.mark.asyncio
    async def test_get_escalation_queue(self, escalation_service):
        """Test getting escalation queue."""
        result = await escalation_service.get_escalation_queue()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_clear_escalation_queue(self, escalation_service):
        """Test clearing escalation queue."""
        # Add something to queue first
        await escalation_service.escalate_ticket("ticket-123", "test")

        cleared = await escalation_service.clear_escalation_queue()

        assert cleared >= 0
        assert len(await escalation_service.get_escalation_queue()) == 0


class TestEscalationServiceNotificationHistory:
    """Tests for notification history."""

    @pytest.mark.asyncio
    async def test_get_notification_history(self, escalation_service):
        """Test getting notification history."""
        await escalation_service.notify_escalation("ticket-123", "agent")

        result = await escalation_service.get_notification_history()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_notification_history_by_ticket(self, escalation_service):
        """Test getting notification history for specific ticket."""
        await escalation_service.notify_escalation("ticket-123", "agent")
        await escalation_service.notify_escalation("ticket-456", "agent")

        result = await escalation_service.get_notification_history(ticket_id="ticket-123")

        assert all(n["ticket_id"] == "ticket-123" for n in result)


class TestEscalationServiceRetry:
    """Tests for retry_failed_escalations method."""

    @pytest.mark.asyncio
    async def test_retry_failed_escalations(self, escalation_service):
        """Test retrying failed escalations."""
        result = await escalation_service.retry_failed_escalations()

        assert "retried" in result
        assert "succeeded" in result
        assert "failed" in result
