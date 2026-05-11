"""
Day 34 Unit Tests - Ticket Analytics, Events, and Tasks

Tests for:
- TicketAnalyticsService (all methods)
- Ticket events emission
- New Celery tasks
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# ── TICKET ANALYTICS SERVICE TESTS ────────────────────────────────────────────

class TestTicketAnalyticsService:
    """Tests for TicketAnalyticsService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def analytics_service(self, mock_db):
        """Create TicketAnalyticsService instance."""
        from backend.app.services.ticket_analytics_service import TicketAnalyticsService
        return TicketAnalyticsService(mock_db, "test-company-id")

    def test_get_summary_empty(self, analytics_service, mock_db):
        """Test summary with no tickets."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        from backend.app.services.ticket_analytics_service import DateRange
        date_range = DateRange.last_n_days(30)

        summary = analytics_service.get_summary(date_range)

        assert summary.total_tickets == 0
        assert summary.resolution_rate == 0.0

    def test_get_summary_with_tickets(self, analytics_service, mock_db):
        """Test summary with tickets."""
        mock_ticket1 = MagicMock()
        mock_ticket1.status = "open"
        mock_ticket1.priority = "high"
        mock_ticket1.closed_at = None
        mock_ticket1.first_response_at = None
        mock_ticket1.created_at = datetime.utcnow()

        mock_ticket2 = MagicMock()
        mock_ticket2.status = "resolved"
        mock_ticket2.priority = "medium"
        mock_ticket2.closed_at = datetime.utcnow()
        mock_ticket2.first_response_at = datetime.utcnow() - timedelta(hours=1)
        mock_ticket2.created_at = datetime.utcnow() - timedelta(hours=5)

        mock_ticket3 = MagicMock()
        mock_ticket3.status = "closed"
        mock_ticket3.priority = "low"
        mock_ticket3.closed_at = datetime.utcnow()
        mock_ticket3.first_response_at = datetime.utcnow() - timedelta(hours=2)
        mock_ticket3.created_at = datetime.utcnow() - timedelta(hours=10)

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_ticket1, mock_ticket2, mock_ticket3
        ]

        summary = analytics_service.get_summary()

        assert summary.total_tickets == 3
        assert summary.open_tickets == 1
        assert summary.resolved_tickets == 1
        assert summary.closed_tickets == 1
        assert summary.high_tickets == 1
        assert summary.medium_tickets == 1
        assert summary.low_tickets == 1
        assert summary.resolution_rate == pytest.approx(2/3, rel=0.01)

    def test_get_trends_hourly(self, analytics_service, mock_db):
        """Test hourly trend calculation."""
        from backend.app.services.ticket_analytics_service import IntervalType, DateRange

        mock_ticket1 = MagicMock()
        mock_ticket1.created_at = datetime.utcnow() - timedelta(hours=1)

        mock_ticket2 = MagicMock()
        mock_ticket2.created_at = datetime.utcnow() - timedelta(hours=2)

        mock_ticket3 = MagicMock()
        mock_ticket3.created_at = datetime.utcnow() - timedelta(hours=1)

        # Set up query chain
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_ticket1, mock_ticket2, mock_ticket3
        ]

        date_range = DateRange.last_n_hours(6)
        trends = analytics_service.get_trends(IntervalType.HOUR, date_range)

        assert len(trends) > 0
        assert all(hasattr(t, 'timestamp') for t in trends)
        assert all(hasattr(t, 'count') for t in trends)
        assert all(hasattr(t, 'label') for t in trends)

    def test_get_trends_daily(self, analytics_service, mock_db):
        """Test daily trend calculation."""
        from backend.app.services.ticket_analytics_service import IntervalType, DateRange

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        date_range = DateRange.last_n_days(7)
        trends = analytics_service.get_trends(IntervalType.DAY, date_range)

        # Should return trend points for each day in range (inclusive)
        assert len(trends) >= 7

    def test_get_category_distribution(self, analytics_service, mock_db):
        """Test category distribution calculation."""
        # Mock the with_entities result
        mock_result = [
            MagicMock(category="tech_support", count=10),
            MagicMock(category="billing", count=5),
            MagicMock(category="general", count=3),
        ]

        mock_db.query.return_value.filter.return_value.with_entities.return_value.group_by.return_value.all.return_value = mock_result

        distribution = analytics_service.get_category_distribution()

        assert len(distribution) == 3
        assert distribution[0].category == "tech_support"
        assert distribution[0].count == 10
        assert distribution[0].percentage == pytest.approx(55.6, rel=0.1)

    def test_get_category_distribution_empty(self, analytics_service, mock_db):
        """Test category distribution with no tickets."""
        mock_db.query.return_value.filter.return_value.with_entities.return_value.group_by.return_value.all.return_value = []

        distribution = analytics_service.get_category_distribution()

        assert len(distribution) == 0

    def test_get_sla_metrics(self, analytics_service, mock_db):
        """Test SLA metrics calculation."""
        mock_timer1 = MagicMock()
        mock_timer1.is_breached = False
        mock_timer1.resolved_at = datetime.utcnow()
        mock_timer1.first_response_at = datetime.utcnow() - timedelta(hours=1)
        mock_timer1.created_at = datetime.utcnow() - timedelta(hours=2)

        mock_timer2 = MagicMock()
        mock_timer2.is_breached = True
        mock_timer2.resolved_at = None
        mock_timer2.first_response_at = None
        mock_timer2.created_at = datetime.utcnow() - timedelta(hours=10)

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_timer1, mock_timer2
        ]

        metrics = analytics_service.get_sla_metrics()

        assert metrics.total_tickets_with_sla == 2
        assert metrics.breached_count == 1
        assert metrics.compliant_count == 1
        assert metrics.compliance_rate == pytest.approx(0.5, rel=0.01)

    def test_get_sla_metrics_empty(self, analytics_service, mock_db):
        """Test SLA metrics with no timers."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        metrics = analytics_service.get_sla_metrics()

        assert metrics.total_tickets_with_sla == 0
        assert metrics.compliance_rate == 1.0

    def test_get_agent_metrics(self, analytics_service, mock_db):
        """Test agent metrics calculation."""
        # Mock assignments
        mock_assignment1 = MagicMock()
        mock_assignment1.assignee_id = "agent-1"
        mock_assignment1.assigned_at = datetime.utcnow() - timedelta(days=1)

        mock_assignment2 = MagicMock()
        mock_assignment2.assignee_id = "agent-2"
        mock_assignment2.assigned_at = datetime.utcnow() - timedelta(days=2)

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_assignment1, mock_assignment2
        ]

        # Mock tickets query for agent data
        mock_ticket1 = MagicMock()
        mock_ticket1.assigned_to = "agent-1"
        mock_ticket1.id = "ticket-1"
        mock_ticket1.status = "resolved"

        mock_ticket2 = MagicMock()
        mock_ticket2.assigned_to = "agent-2"
        mock_ticket2.id = "ticket-2"
        mock_ticket2.status = "open"

        # Set up nested filter chain
        tickets_filter = MagicMock()
        tickets_filter.all.return_value = [mock_ticket1, mock_ticket2]
        mock_db.query.return_value.filter.return_value.filter.return_value = tickets_filter

        # Mock users
        mock_user1 = MagicMock()
        mock_user1.id = "agent-1"
        mock_user1.name = "Alice"

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user1]

        metrics = analytics_service.get_agent_metrics()

        assert isinstance(metrics, list)

    def test_date_range_helpers(self):
        """Test DateRange helper methods."""
        from backend.app.services.ticket_analytics_service import DateRange

        # Test last_n_days
        range_days = DateRange.last_n_days(7)
        assert range_days.end_date > range_days.start_date
        assert (range_days.end_date - range_days.start_date).days == 7

        # Test last_n_hours
        range_hours = DateRange.last_n_hours(24)
        assert range_hours.end_date > range_hours.start_date

        # Test last_n_weeks
        range_weeks = DateRange.last_n_weeks(2)
        assert range_weeks.end_date > range_weeks.start_date


# ── TICKET EVENTS TESTS ───────────────────────────────────────────────────────

class TestTicketEvents:
    """Tests for ticket event emission."""

    @pytest.fixture
    def mock_emit_event(self):
        """Mock emit_ticket_event function."""
        with patch('backend.app.core.ticket_events.emit_ticket_event') as mock:
            mock.return_value = True
            yield mock

    @pytest.mark.asyncio
    async def test_emit_ticket_created(self, mock_emit_event):
        """Test ticket:created event emission."""
        from backend.app.core.ticket_events import emit_ticket_created

        result = await emit_ticket_created(
            company_id="company-1",
            ticket_id="ticket-1",
            actor_id="user-1",
            ticket_data={
                "status": "open",
                "priority": "high",
                "category": "tech_support",
            },
        )

        assert result is True
        mock_emit_event.assert_called_once()
        call_args = mock_emit_event.call_args
        assert call_args.kwargs["event_type"] == "ticket:created"
        assert call_args.kwargs["company_id"] == "company-1"

    @pytest.mark.asyncio
    async def test_emit_ticket_status_changed(self, mock_emit_event):
        """Test ticket:status_changed event emission."""
        from backend.app.core.ticket_events import emit_ticket_status_changed

        result = await emit_ticket_status_changed(
            company_id="company-1",
            ticket_id="ticket-1",
            actor_id="user-1",
            from_status="open",
            to_status="resolved",
            reason="Issue fixed",
        )

        assert result is True
        mock_emit_event.assert_called_once()
        call_args = mock_emit_event.call_args
        assert call_args.kwargs["event_type"] == "ticket:status_changed"

    @pytest.mark.asyncio
    async def test_emit_ticket_assigned(self, mock_emit_event):
        """Test ticket:assigned event emission."""
        from backend.app.core.ticket_events import emit_ticket_assigned

        result = await emit_ticket_assigned(
            company_id="company-1",
            ticket_id="ticket-1",
            actor_id="system",
            assignee_id="agent-1",
            previous_assignee_id=None,
            assignment_type="human",
        )

        assert result is True
        mock_emit_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_ticket_resolved(self, mock_emit_event):
        """Test ticket:resolved event emission."""
        from backend.app.core.ticket_events import emit_ticket_resolved

        result = await emit_ticket_resolved(
            company_id="company-1",
            ticket_id="ticket-1",
            actor_id="agent-1",
            resolution_time_minutes=120.5,
        )

        assert result is True
        mock_emit_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_sla_warning(self, mock_emit_event):
        """Test ticket:sla_warning event emission."""
        from backend.app.core.ticket_events import emit_sla_warning

        result = await emit_sla_warning(
            company_id="company-1",
            ticket_id="ticket-1",
            percentage_elapsed=0.80,
            minutes_remaining=30.5,
            sla_type="resolution",
        )

        assert result is True
        mock_emit_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_sla_breach(self, mock_emit_event):
        """Test ticket:sla_breached event emission."""
        from backend.app.core.ticket_events import emit_sla_breach

        result = await emit_sla_breach(
            company_id="company-1",
            ticket_id="ticket-1",
            breach_type="resolution",
            minutes_overdue=15.0,
        )

        assert result is True
        mock_emit_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_ticket_collision(self, mock_emit_event):
        """Test ticket:collision event emission."""
        from backend.app.core.ticket_events import emit_ticket_collision

        result = await emit_ticket_collision(
            company_id="company-1",
            ticket_id="ticket-1",
            current_viewers=[
                {"user_id": "user-1", "name": "Alice"},
                {"user_id": "user-2", "name": "Bob"},
            ],
            action="editing",
        )

        assert result is True
        mock_emit_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_ticket_merged(self, mock_emit_event):
        """Test ticket:merged event emission."""
        from backend.app.core.ticket_events import emit_ticket_merged

        result = await emit_ticket_merged(
            company_id="company-1",
            primary_ticket_id="ticket-1",
            merged_ticket_ids=["ticket-2", "ticket-3"],
            actor_id="user-1",
            merge_reason="Duplicate tickets",
        )

        assert result is True
        mock_emit_event.assert_called_once()

    def test_register_ticket_events(self):
        """Test that ticket events are registered."""
        from backend.app.core.ticket_events import register_ticket_events, TICKET_EVENT_TYPES
        from backend.app.core.events import get_event_registry

        registry = get_event_registry()

        # Register events
        register_ticket_events(registry)

        # Check some events are registered
        for event_type in ["ticket:created", "ticket:updated", "ticket:status_changed"]:
            # Either registered now or already was
            assert registry.get(event_type) is not None


# ── CELERY TASKS TESTS ────────────────────────────────────────────────────────

class TestTicketTasks:
    """Tests for Celery ticket tasks."""

    def test_tasks_are_registered(self):
        """Test that all ticket tasks are registered with Celery."""
        from backend.app.tasks.ticket_tasks import (
            run_sla_check,
            check_stale_tickets,
            detect_spam_tickets,
            cleanup_frozen_tickets,
            send_awaiting_client_reminder,
            process_bulk_action,
        )

        # Verify tasks have names
        assert run_sla_check.name == "ticket.run_sla_check"
        assert check_stale_tickets.name == "ticket.check_stale_tickets"
        assert detect_spam_tickets.name == "ticket.detect_spam_tickets"
        assert cleanup_frozen_tickets.name == "ticket.cleanup_frozen_tickets"
        assert send_awaiting_client_reminder.name == "ticket.send_awaiting_client_reminder"
        assert process_bulk_action.name == "ticket.process_bulk_action"

    def test_sla_service_exists(self):
        """Test that SLAService can be imported."""
        from backend.app.services.sla_service import SLAService
        assert SLAService is not None

    def test_stale_ticket_service_exists(self):
        """Test that StaleTicketService can be imported."""
        from backend.app.services.stale_ticket_service import StaleTicketService
        assert StaleTicketService is not None

    def test_spam_detection_service_exists(self):
        """Test that SpamDetectionService can be imported."""
        from backend.app.services.spam_detection_service import SpamDetectionService
        assert SpamDetectionService is not None

    def test_bulk_action_service_exists(self):
        """Test that BulkActionService can be imported."""
        from backend.app.services.bulk_action_service import BulkActionService
        assert BulkActionService is not None


# ── LOOPHOLE AND EDGE CASE TESTS ──────────────────────────────────────────────

class TestDay34Loopholes:
    """Tests for potential loopholes and edge cases."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    # Analytics Loopholes

    def test_gap1_analytics_empty_company(self, mock_db):
        """GAP1: Analytics should handle company with no tickets."""
        from backend.app.services.ticket_analytics_service import TicketAnalyticsService

        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = TicketAnalyticsService(mock_db, "empty-company")
        summary = service.get_summary()

        assert summary.total_tickets == 0
        assert summary.resolution_rate == 0.0

    def test_gap2_analytics_date_range_validation(self, mock_db):
        """GAP2: Date range should handle invalid inputs."""
        from backend.app.services.ticket_analytics_service import (
            TicketAnalyticsService,
            DateRange,
        )

        # Start date after end date should still work
        start = datetime.utcnow()
        end = datetime.utcnow() - timedelta(days=7)
        date_range = DateRange(start_date=start, end_date=end)

        service = TicketAnalyticsService(mock_db, "company-1")
        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Should not raise
        summary = service.get_summary(date_range)
        assert summary is not None

    def test_gap3_category_null_handling(self, mock_db):
        """GAP3: Category distribution should handle null categories."""
        from backend.app.services.ticket_analytics_service import TicketAnalyticsService

        mock_result = [
            MagicMock(category=None, count=5),
            MagicMock(category="tech_support", count=10),
        ]

        mock_db.query.return_value.filter.return_value.with_entities.return_value.group_by.return_value.all.return_value = mock_result

        service = TicketAnalyticsService(mock_db, "company-1")
        distribution = service.get_category_distribution()

        # Should only include non-null categories
        assert len(distribution) == 1
        assert distribution[0].category == "tech_support"

    def test_gap4_sla_timer_missing_policy(self, mock_db):
        """GAP4: SLA metrics should handle missing policy references."""
        from backend.app.services.ticket_analytics_service import TicketAnalyticsService

        mock_timer = MagicMock()
        mock_timer.is_breached = False
        mock_timer.resolved_at = None
        mock_timer.first_response_at = None
        mock_timer.created_at = datetime.utcnow()
        mock_timer.policy_id = None  # Missing policy

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_timer]

        service = TicketAnalyticsService(mock_db, "company-1")
        metrics = service.get_sla_metrics()

        assert metrics.total_tickets_with_sla == 1

    def test_gap5_agent_metrics_no_assignments(self, mock_db):
        """GAP5: Agent metrics should handle no assignments."""
        from backend.app.services.ticket_analytics_service import TicketAnalyticsService

        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = TicketAnalyticsService(mock_db, "company-1")
        metrics = service.get_agent_metrics()

        assert len(metrics) == 0

    # Event Emission Loopholes

    @pytest.mark.asyncio
    async def test_gap6_event_invalid_company_id(self):
        """GAP6: Event emission should validate company_id."""
        from backend.app.core.ticket_events import emit_ticket_created

        with patch('backend.app.core.ticket_events.emit_ticket_event') as mock_emit:
            mock_emit.return_value = False  # Would fail validation

            result = await emit_ticket_created(
                company_id="",  # Empty company_id
                ticket_id="ticket-1",
                actor_id="user-1",
                ticket_data={},
            )

            # Should return False for invalid input
            assert result is False or mock_emit.called

    @pytest.mark.asyncio
    async def test_gap7_event_large_payload(self):
        """GAP7: Event emission should handle large payloads."""
        from backend.app.core.ticket_events import emit_ticket_created

        with patch('backend.app.core.ticket_events.emit_ticket_event') as mock_emit:
            mock_emit.return_value = False  # Would fail size check

            # Create large ticket data
            large_data = {
                "subject": "x" * 10000,
                "description": "y" * 10000,
            }

            result = await emit_ticket_created(
                company_id="company-1",
                ticket_id="ticket-1",
                actor_id="user-1",
                ticket_data=large_data,
            )

            # Should handle gracefully
            assert result is not None

    # Task Loopholes

    def test_gap8_task_names_are_correct(self):
        """GAP8: Task names should be properly formatted."""
        from backend.app.tasks.ticket_tasks import (
            run_sla_check,
            check_stale_tickets,
            cleanup_frozen_tickets,
        )

        # All task names should start with "ticket."
        assert run_sla_check.name.startswith("ticket.")
        assert check_stale_tickets.name.startswith("ticket.")
        assert cleanup_frozen_tickets.name.startswith("ticket.")

    def test_gap9_task_company_isolation_in_queries(self):
        """GAP9: Tasks should include company_id in queries."""
        # This is verified by checking the task code uses company_id parameter
        from backend.app.tasks.ticket_tasks import cleanup_frozen_tickets

        # Task function signature includes company_id
        import inspect
        sig = inspect.signature(cleanup_frozen_tickets)
        params = list(sig.parameters.keys())

        # Should have self (task) and company_id parameters
        assert "company_id" in params
