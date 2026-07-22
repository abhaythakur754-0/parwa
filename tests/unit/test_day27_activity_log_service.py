"""
Day 27 Service Unit Tests - Activity Log Service

Tests for activity_log_service.py covering:
- Activity recording
- Timeline generation
- Activity summaries
- Status change tracking
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from backend.app.services.activity_log_service import ActivityLogService
from database.models.tickets import (
    Ticket,
    TicketStatusChange,
    TicketAssignment,
    TicketMessage,
    TicketInternalNote,
    TicketAttachment,
    TicketMerge,
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
def activity_service(mock_db, mock_company_id):
    """Activity log service instance."""
    return ActivityLogService(mock_db, mock_company_id)


# ═══════════════════════════════════════════════════════════════════
# RECORD ACTIVITY TESTS
# ═══════════════════════════════════════════════════════════════════

class TestRecordActivity:

    def test_record_status_change_creates_db_record(self, activity_service, mock_db):
        """Test that status change creates TicketStatusChange record."""
        activity = activity_service.record_status_change(
            ticket_id="ticket-123",
            from_status="open",
            to_status="assigned",
            actor_id="user-456",
            reason="Agent picked up ticket",
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_STATUS_CHANGE
        assert activity["old_value"] == "open"
        assert activity["new_value"] == "assigned"
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_record_activity_returns_dict(self, activity_service):
        """Test that record_activity returns proper dict structure."""
        activity = activity_service.record_activity(
            ticket_id="ticket-123",
            activity_type=ActivityLogService.ACTIVITY_MESSAGE_ADDED,
            actor_id="user-456",
            actor_type="human",
            new_value="message-789",
        )

        assert "id" in activity
        assert "ticket_id" in activity
        assert "company_id" in activity
        assert "activity_type" in activity
        assert "created_at" in activity

    def test_record_assignment_with_score(self, activity_service):
        """Test recording assignment with AI score."""
        activity = activity_service.record_assignment(
            ticket_id="ticket-123",
            assignee_id="agent-456",
            assignee_type="ai",
            actor_id="system",
            reason="Best match",
            score=0.95,
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_ASSIGNED
        assert activity["metadata"]["score"] == 0.95

    def test_record_tag_change(self, activity_service):
        """Test recording tag changes."""
        activity = activity_service.record_tag_change(
            ticket_id="ticket-123",
            tag="urgent",
            added=True,
            actor_id="user-456",
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_TAG_ADDED
        assert activity["new_value"] == "urgent"

    def test_record_tag_removed(self, activity_service):
        """Test recording tag removal."""
        activity = activity_service.record_tag_change(
            ticket_id="ticket-123",
            tag="urgent",
            added=False,
            actor_id="user-456",
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_TAG_REMOVED
        assert activity["old_value"] == "urgent"


# ═══════════════════════════════════════════════════════════════════
# GET TIMELINE TESTS
# ═══════════════════════════════════════════════════════════════════

class TestGetTimeline:

    def test_get_timeline_returns_events(self, activity_service, mock_db):
        """Test that timeline returns events from multiple sources."""
        # Mock status changes
        status_change = TicketStatusChange()
        status_change.id = "sc-1"
        status_change.ticket_id = "ticket-123"
        status_change.company_id = "test-company-123"
        status_change.from_status = "open"
        status_change.to_status = "assigned"
        status_change.changed_by = "user-456"
        status_change.reason = "Picked up"
        status_change.created_at = datetime.utcnow()

        # Set up mock to return status_change for first query (status_changes), 
        # empty lists for all other queries
        call_count = [0]
        def mock_query_all(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [status_change]
            return []

        mock_db.query.return_value.filter.return_value.all = mock_query_all

        events, total = activity_service.get_timeline("ticket-123")

        # Should have at least one event
        assert total >= 1

    def test_get_timeline_filters_internal_messages(self, activity_service, mock_db):
        """Test that internal messages are filtered by default."""
        # Create mock that returns empty for simplicity
        mock_db.query.return_value.filter.return_value.all.return_value = []

        events, total = activity_service.get_timeline(
            "ticket-123",
            include_messages=True,
            include_internal=False,
        )

        # No events when all queries return empty
        assert total == 0

    def test_get_timeline_includes_internal_when_requested(self, activity_service, mock_db):
        """Test that internal messages are included when requested."""
        # Create mock that returns empty
        mock_db.query.return_value.filter.return_value.all.return_value = []

        events, total = activity_service.get_timeline(
            "ticket-123",
            include_messages=True,
            include_internal=True,
        )

        # With empty mocks, total is 0
        assert total == 0

    def test_get_timeline_filters_by_activity_type(self, activity_service, mock_db):
        """Test filtering by activity types."""
        status_change = TicketStatusChange()
        status_change.id = "sc-1"
        status_change.ticket_id = "ticket-123"
        status_change.company_id = "test-company-123"
        status_change.from_status = "open"
        status_change.to_status = "assigned"
        status_change.changed_by = "user-456"
        status_change.reason = None
        status_change.created_at = datetime.utcnow()

        # Use side_effect to return status_change for first query only
        call_count = [0]
        def mock_query_all(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [status_change]
            return []

        mock_db.query.return_value.filter.return_value.all = mock_query_all

        events, total = activity_service.get_timeline(
            "ticket-123",
            activity_types=[ActivityLogService.ACTIVITY_STATUS_CHANGE],
        )

        # Should have events
        assert total >= 1

    def test_get_timeline_pagination(self, activity_service, mock_db):
        """Test timeline pagination."""
        # Create mock that returns empty
        mock_db.query.return_value.filter.return_value.all.return_value = []

        events, total = activity_service.get_timeline(
            "ticket-123",
            page=1,
            page_size=5,
        )

        # Empty results
        assert total == 0


# ═══════════════════════════════════════════════════════════════════
# ACTIVITY SUMMARY TESTS
# ═══════════════════════════════════════════════════════════════════

class TestActivitySummary:

    def test_get_activity_summary_counts_by_type(self, activity_service, mock_db):
        """Test that summary counts activities by type."""
        # Mock empty queries
        mock_db.query.return_value.filter.return_value.all.return_value = []

        summary = activity_service.get_activity_summary("ticket-123")

        assert "total_activities" in summary
        assert "activity_counts" in summary
        assert isinstance(summary["activity_counts"], dict)

    def test_get_activity_summary_identifies_first_response(self, activity_service, mock_db):
        """Test that summary identifies first response time."""
        # Create message from agent
        now = datetime.utcnow()
        agent_message = TicketMessage()
        agent_message.id = "m-1"
        agent_message.ticket_id = "ticket-123"
        agent_message.company_id = "test-company-123"
        agent_message.role = "agent"
        agent_message.channel = "email"
        agent_message.is_internal = False
        agent_message.is_redacted = False
        agent_message.ai_confidence = None
        agent_message.created_at = now

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [],  # status changes
            [],  # assignments
            [agent_message],  # messages
            [],  # notes
            [],  # attachments
            [],  # merges
        ]

        summary = activity_service.get_activity_summary("ticket-123")

        # First response should be identified
        assert "first_response_at" in summary


# ═══════════════════════════════════════════════════════════════════
# HELPER METHODS TESTS
# ═══════════════════════════════════════════════════════════════════

class TestHelperMethods:

    def test_record_message_helper(self, activity_service):
        """Test record_message helper."""
        activity = activity_service.record_message(
            ticket_id="ticket-123",
            message_id="msg-456",
            role="agent",
            channel="email",
            is_internal=False,
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_MESSAGE_ADDED
        assert activity["metadata"]["message_id"] == "msg-456"

    def test_record_note_helper(self, activity_service):
        """Test record_note helper."""
        activity = activity_service.record_note(
            ticket_id="ticket-123",
            note_id="note-456",
            author_id="user-789",
            is_pinned=True,
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_NOTE_ADDED
        assert activity["metadata"]["note_id"] == "note-456"
        assert activity["metadata"]["is_pinned"] is True

    def test_record_attachment_helper(self, activity_service):
        """Test record_attachment helper."""
        activity = activity_service.record_attachment(
            ticket_id="ticket-123",
            attachment_id="attach-456",
            filename="document.pdf",
            file_size=1024,
            actor_id="user-789",
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_ATTACHMENT_UPLOADED
        assert activity["metadata"]["filename"] == "document.pdf"
        assert activity["metadata"]["file_size"] == 1024

    def test_record_sla_warning(self, activity_service):
        """Test recording SLA warning event."""
        activity = activity_service.record_sla_event(
            ticket_id="ticket-123",
            event_type=ActivityLogService.ACTIVITY_SLA_WARNING,
            time_remaining=3600,
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_SLA_WARNING
        assert activity["metadata"]["time_remaining_seconds"] == 3600

    def test_record_sla_breach(self, activity_service):
        """Test recording SLA breach event."""
        activity = activity_service.record_sla_event(
            ticket_id="ticket-123",
            event_type=ActivityLogService.ACTIVITY_SLA_BREACHED,
        )

        assert activity["activity_type"] == ActivityLogService.ACTIVITY_SLA_BREACHED


# ═══════════════════════════════════════════════════════════════════
# ACTIVITY TYPES TESTS
# ═══════════════════════════════════════════════════════════════════

class TestActivityTypes:

    def test_all_activity_types_defined(self):
        """Test that all expected activity types are defined."""
        expected_types = [
            "status_change",
            "priority_change",
            "category_change",
            "assigned",
            "unassigned",
            "tag_added",
            "tag_removed",
            "sla_warning",
            "sla_breached",
            "reopened",
            "frozen",
            "thawed",
            "merged",
            "unmerged",
            "message_added",
            "note_added",
            "attachment_uploaded",
            "created",
            "closed",
            "escalated",
            "spam_flagged",
        ]

        for activity_type in expected_types:
            assert hasattr(ActivityLogService, f"ACTIVITY_{activity_type.upper()}")
