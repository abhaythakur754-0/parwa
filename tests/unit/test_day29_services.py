"""
PARWA Day 29 Unit Tests

Tests for:
- BulkActionService: Bulk operations with undo
- TicketMergeService: Merge/unmerge logic
- SLAService: SLA policy + timer + breach detection

Day 29 - F-051, MF06, PS11, PS17 implementation tests.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.services.bulk_action_service import (
    BulkActionService,
    BulkActionError,
    BulkActionNotFoundError,
    BulkActionAlreadyUndoneError,
    BulkActionUndoExpiredError,
)
from backend.app.services.ticket_merge_service import (
    TicketMergeService,
    TicketMergeError,
    TicketNotFoundError,
    TicketAlreadyMergedError,
    MergeAlreadyUndoneError,
    CrossTenantMergeError,
)
from backend.app.services.sla_service import (
    SLAService,
    SLAError,
    SLAPolicyNotFoundError,
    DuplicateSLAPolicyError,
)
from backend.app.schemas.bulk_action import BulkActionType
from backend.app.schemas.sla import Priority, PlanTier


# ─────────────────────────────────────────────────────────────────────────────
# BulkActionService Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBulkActionService:
    """Tests for BulkActionService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def bulk_service(self, mock_db):
        """Create a BulkActionService instance."""
        return BulkActionService(mock_db)

    def test_max_tickets_per_action(self, bulk_service):
        """Test that MAX_TICKETS_PER_ACTION is set correctly."""
        assert bulk_service.MAX_TICKETS_PER_ACTION == 500

    def test_undo_window_hours(self, bulk_service):
        """Test that UNDO_WINDOW_HOURS is set correctly."""
        assert bulk_service.UNDO_WINDOW_HOURS == 24

    def test_execute_bulk_action_exceeds_max(self, bulk_service):
        """Test that bulk action fails when exceeding max tickets."""
        ticket_ids = [f"ticket-{i}" for i in range(501)]
        
        with pytest.raises(BulkActionError) as exc_info:
            bulk_service.execute_bulk_action(
                company_id="company-1",
                action_type="close",
                ticket_ids=ticket_ids,
                params={},
                performed_by="user-1",
            )
        
        assert "Maximum 500 tickets" in str(exc_info.value)

    def test_execute_bulk_action_removes_duplicates(self, bulk_service, mock_db):
        """Test that duplicate ticket IDs are removed."""
        mock_db.add = Mock()
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        
        # Mock query for tickets
        mock_ticket = Mock()
        mock_ticket.id = "ticket-1"
        mock_ticket.status = "open"
        mock_ticket.priority = "medium"
        mock_ticket.assigned_to = None
        mock_ticket.tags = "[]"
        mock_ticket.closed_at = None
        
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_ticket)
        mock_db.query = Mock(return_value=mock_query)
        
        result = bulk_service.execute_bulk_action(
            company_id="company-1",
            action_type="close",
            ticket_ids=["ticket-1", "ticket-1", "ticket-1"],
            params={},
            performed_by="user-1",
        )
        
        # Should have deduplicated to 1 ticket
        bulk_action, success_count, failure_count = result
        assert success_count == 1

    def test_validate_status_transition_valid(self, bulk_service):
        """Test valid status transitions pass validation."""
        # open -> assigned
        bulk_service._validate_status_transition("open", "assigned")
        
        # in_progress -> resolved
        bulk_service._validate_status_transition("in_progress", "resolved")
        
        # resolved -> closed
        bulk_service._validate_status_transition("resolved", "closed")

    def test_validate_status_transition_invalid(self, bulk_service):
        """Test invalid status transitions raise error."""
        # open -> resolved (invalid)
        with pytest.raises(BulkActionError):
            bulk_service._validate_status_transition("open", "resolved")
        
        # closed -> in_progress (invalid)
        with pytest.raises(BulkActionError):
            bulk_service._validate_status_transition("closed", "in_progress")

    def test_get_ticket_state(self, bulk_service):
        """Test getting ticket state for undo."""
        mock_ticket = Mock()
        mock_ticket.status = "open"
        mock_ticket.priority = "high"
        mock_ticket.assigned_to = "user-1"
        mock_ticket.tags = '["urgent"]'
        mock_ticket.closed_at = None
        
        state = bulk_service._get_ticket_state(mock_ticket)
        
        assert state["status"] == "open"
        assert state["priority"] == "high"
        assert state["assigned_to"] == "user-1"
        assert state["tags"] == '["urgent"]'
        assert state["closed_at"] is None


class TestBulkActionStatusChange:
    """Tests for bulk status change actions."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def bulk_service(self, mock_db):
        return BulkActionService(mock_db)

    def test_status_change_updates_ticket(self, bulk_service):
        """Test that status change updates ticket status."""
        mock_ticket = Mock()
        mock_ticket.status = "open"
        mock_ticket.updated_at = None
        
        bulk_service._execute_single_action(
            mock_ticket,
            BulkActionType.STATUS_CHANGE.value,
            {"new_status": "assigned"},
        )
        
        assert mock_ticket.status == "assigned"
        assert mock_ticket.updated_at is not None

    def test_close_action_sets_closed_at(self, bulk_service):
        """Test that close action sets closed_at timestamp."""
        mock_ticket = Mock()
        mock_ticket.status = "open"
        mock_ticket.closed_at = None
        mock_ticket.updated_at = None
        
        bulk_service._execute_single_action(
            mock_ticket,
            BulkActionType.CLOSE.value,
            {},
        )
        
        assert mock_ticket.status == "closed"
        assert mock_ticket.closed_at is not None


class TestBulkActionReassign:
    """Tests for bulk reassign actions."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def bulk_service(self, mock_db):
        return BulkActionService(mock_db)

    def test_reassign_updates_assignee(self, bulk_service):
        """Test that reassign updates assigned_to."""
        mock_ticket = Mock()
        mock_ticket.assigned_to = None
        mock_ticket.status = "open"
        mock_ticket.updated_at = None
        
        bulk_service._execute_single_action(
            mock_ticket,
            BulkActionType.REASSIGN.value,
            {"assignee_id": "user-2", "assignee_type": "human"},
        )
        
        assert mock_ticket.assigned_to == "user-2"
        assert mock_ticket.status == "assigned"


class TestBulkActionTags:
    """Tests for bulk tag actions."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def bulk_service(self, mock_db):
        return BulkActionService(mock_db)

    def test_add_tags(self, bulk_service):
        """Test adding tags to ticket."""
        mock_ticket = Mock()
        mock_ticket.tags = '["existing"]'
        mock_ticket.updated_at = None
        
        bulk_service._execute_single_action(
            mock_ticket,
            BulkActionType.TAG.value,
            {"tags": ["new"], "tag_action": "add"},
        )
        
        tags = json.loads(mock_ticket.tags)
        assert "existing" in tags
        assert "new" in tags

    def test_remove_tags(self, bulk_service):
        """Test removing tags from ticket."""
        mock_ticket = Mock()
        mock_ticket.tags = '["keep", "remove"]'
        mock_ticket.updated_at = None
        
        bulk_service._execute_single_action(
            mock_ticket,
            BulkActionType.TAG.value,
            {"tags": ["remove"], "tag_action": "remove"},
        )
        
        tags = json.loads(mock_ticket.tags)
        assert "keep" in tags
        assert "remove" not in tags

    def test_replace_tags(self, bulk_service):
        """Test replacing all tags."""
        mock_ticket = Mock()
        mock_ticket.tags = '["old1", "old2"]'
        mock_ticket.updated_at = None
        
        bulk_service._execute_single_action(
            mock_ticket,
            BulkActionType.TAG.value,
            {"tags": ["new1", "new2"], "tag_action": "replace"},
        )
        
        tags = json.loads(mock_ticket.tags)
        assert tags == ["new1", "new2"]


class TestBulkActionPriority:
    """Tests for bulk priority actions."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def bulk_service(self, mock_db):
        return BulkActionService(mock_db)

    def test_priority_change(self, bulk_service):
        """Test changing ticket priority."""
        mock_ticket = Mock()
        mock_ticket.priority = "low"
        mock_ticket.updated_at = None
        
        bulk_service._execute_single_action(
            mock_ticket,
            BulkActionType.PRIORITY.value,
            {"priority": "critical"},
        )
        
        assert mock_ticket.priority == "critical"


class TestBulkActionUndo:
    """Tests for bulk action undo functionality."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def bulk_service(self, mock_db):
        return BulkActionService(mock_db)

    def test_undo_not_found(self, bulk_service, mock_db):
        """Test undo with invalid token raises error."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(BulkActionNotFoundError):
            bulk_service.undo_bulk_action("company-1", "invalid-token")

    def test_undo_already_undone(self, bulk_service, mock_db):
        """Test undo on already undone action raises error."""
        mock_bulk_action = Mock()
        mock_bulk_action.undone = True
        
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_bulk_action)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(BulkActionAlreadyUndoneError):
            bulk_service.undo_bulk_action("company-1", "token")

    def test_undo_expired(self, bulk_service, mock_db):
        """Test undo after window expires raises error."""
        mock_bulk_action = Mock()
        mock_bulk_action.undone = False
        mock_bulk_action.created_at = datetime.utcnow() - timedelta(hours=25)
        
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_bulk_action)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(BulkActionUndoExpiredError):
            bulk_service.undo_bulk_action("company-1", "token")


# ─────────────────────────────────────────────────────────────────────────────
# TicketMergeService Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketMergeService:
    """Tests for TicketMergeService."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def merge_service(self, mock_db):
        return TicketMergeService(mock_db)

    def test_primary_ticket_not_found(self, merge_service, mock_db):
        """Test merge fails when primary ticket not found."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(TicketNotFoundError):
            merge_service.merge_tickets(
                company_id="company-1",
                primary_ticket_id="not-found",
                merged_ticket_ids=["ticket-2"],
                merged_by="user-1",
            )

    def test_merged_ticket_not_found(self, merge_service, mock_db):
        """Test merge fails when merged ticket not found."""
        primary_ticket = Mock()
        primary_ticket.id = "primary-1"
        primary_ticket.company_id = "company-1"
        
        # Track call count across different query types
        call_counts = {"ticket": 0, "merge": 0}
        
        def mock_query_side_effect(model):
            mock_q = Mock()
            
            def filter_side_effect(*args):
                mock_f = Mock()
                
                def first_side_effect():
                    # Check if this is a Ticket or TicketMerge query
                    # based on the model passed to query()
                    # First call: primary ticket (return ticket)
                    # Second call: merged ticket (return None to trigger not found)
                    call_counts["ticket"] += 1
                    
                    if call_counts["ticket"] == 1:
                        return primary_ticket  # Primary ticket found
                    return None  # Merged ticket not found
                
                mock_f.first = first_side_effect
                return mock_f
            
            mock_q.filter = filter_side_effect
            return mock_q
        
        mock_db.query = mock_query_side_effect
        
        with pytest.raises(TicketNotFoundError):
            merge_service.merge_tickets(
                company_id="company-1",
                primary_ticket_id="primary-1",
                merged_ticket_ids=["not-found"],
                merged_by="user-1",
            )

    def test_cross_tenant_merge_rejected(self, merge_service, mock_db):
        """Test merge rejects tickets from different companies."""
        primary_ticket = Mock()
        primary_ticket.id = "primary-1"
        primary_ticket.company_id = "company-1"
        
        other_ticket = Mock()
        other_ticket.id = "other-1"
        other_ticket.company_id = "company-2"  # Different company
        
        call_count = [0]
        
        def mock_query_side_effect(model):
            mock_q = Mock()
            
            def filter_side_effect(*args):
                mock_f = Mock()
                
                def first_side_effect():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return primary_ticket
                    return other_ticket
                
                mock_f.first = first_side_effect
                return mock_f
            
            mock_q.filter = filter_side_effect
            return mock_q
        
        mock_db.query = mock_query_side_effect
        
        with pytest.raises(CrossTenantMergeError):
            merge_service.merge_tickets(
                company_id="company-1",
                primary_ticket_id="primary-1",
                merged_ticket_ids=["other-1"],
                merged_by="user-1",
            )


class TestTicketUnmerge:
    """Tests for ticket unmerge functionality."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def merge_service(self, mock_db):
        return TicketMergeService(mock_db)

    def test_unmerge_not_found(self, merge_service, mock_db):
        """Test unmerge fails when merge not found."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(TicketNotFoundError):
            merge_service.unmerge_tickets("company-1", "not-found")

    def test_unmerge_already_undone(self, merge_service, mock_db):
        """Test unmerge fails when already undone."""
        mock_merge = Mock()
        mock_merge.undone = True
        
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_merge)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(MergeAlreadyUndoneError):
            merge_service.unmerge_tickets("company-1", "merge-id")


# ─────────────────────────────────────────────────────────────────────────────
# SLAService Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSLAService:
    """Tests for SLAService."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def sla_service(self, mock_db):
        return SLAService(mock_db)

    def test_default_policies_exist(self, sla_service):
        """Test that default policies are defined."""
        assert PlanTier.starter.value in sla_service.DEFAULT_POLICIES
        assert PlanTier.growth.value in sla_service.DEFAULT_POLICIES
        assert PlanTier.high.value in sla_service.DEFAULT_POLICIES

    def test_approaching_threshold(self, sla_service):
        """Test that approaching threshold is 75%."""
        assert sla_service.APPROACHING_THRESHOLD == 0.75

    def test_starter_critical_sla(self, sla_service):
        """Test Starter tier critical priority SLA times."""
        starter_critical = sla_service.DEFAULT_POLICIES[PlanTier.starter.value][Priority.critical.value]
        
        first_resp, resolution, update = starter_critical
        
        assert first_resp == 60  # 1 hour
        assert resolution == 480  # 8 hours
        assert update == 30  # 30 minutes

    def test_growth_is_half_starter(self, sla_service):
        """Test that Growth tier times are half of Starter."""
        starter_high = sla_service.DEFAULT_POLICIES[PlanTier.starter.value][Priority.high.value]
        growth_high = sla_service.DEFAULT_POLICIES[PlanTier.growth.value][Priority.high.value]
        
        assert growth_high[0] == starter_high[0] // 2
        assert growth_high[1] == starter_high[1] // 2


class TestSLAPolicyCRUD:
    """Tests for SLA policy CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def sla_service(self, mock_db):
        return SLAService(mock_db)

    def test_create_policy_success(self, sla_service, mock_db):
        """Test creating a new SLA policy."""
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Mock no existing policy
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        policy = sla_service.create_policy(
            company_id="company-1",
            plan_tier=PlanTier.starter.value,
            priority=Priority.critical.value,
            first_response_minutes=60,
            resolution_minutes=480,
            update_frequency_minutes=30,
        )
        
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_duplicate_policy_fails(self, sla_service, mock_db):
        """Test that duplicate policy creation fails."""
        existing_policy = Mock()
        
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=existing_policy)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(DuplicateSLAPolicyError):
            sla_service.create_policy(
                company_id="company-1",
                plan_tier=PlanTier.starter.value,
                priority=Priority.critical.value,
                first_response_minutes=60,
                resolution_minutes=480,
                update_frequency_minutes=30,
            )

    def test_get_policy_not_found(self, sla_service, mock_db):
        """Test getting non-existent policy returns None."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        result = sla_service.get_policy("company-1", "not-found")
        
        assert result is None

    def test_delete_policy_not_found(self, sla_service, mock_db):
        """Test deleting non-existent policy raises error."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        with pytest.raises(SLAPolicyNotFoundError):
            sla_service.delete_policy("company-1", "not-found")


class TestSLATimer:
    """Tests for SLA timer functionality."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def sla_service(self, mock_db):
        return SLAService(mock_db)

    def test_create_timer_sets_resolution_target(self, sla_service, mock_db):
        """Test that creating timer sets resolution target on ticket."""
        mock_policy = Mock()
        mock_policy.id = "policy-1"
        mock_policy.resolution_minutes = 480
        
        mock_ticket = Mock()
        mock_ticket.id = "ticket-1"
        mock_ticket.resolution_target_at = None
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Mock policy query
        policy_query = Mock()
        policy_query.filter = Mock(return_value=policy_query)
        policy_query.first = Mock(return_value=mock_policy)
        
        # Mock timer query (no existing)
        timer_query = Mock()
        timer_query.filter = Mock(return_value=timer_query)
        timer_query.first = Mock(return_value=None)
        
        # Mock ticket query
        ticket_query = Mock()
        ticket_query.filter = Mock(return_value=ticket_query)
        ticket_query.first = Mock(return_value=mock_ticket)
        
        def query_side_effect(model):
            if hasattr(model, '__tablename__'):
                if model.__tablename__ == 'sla_policies':
                    return policy_query
                elif model.__tablename__ == 'sla_timers':
                    return timer_query
                elif model.__tablename__ == 'tickets':
                    return ticket_query
            return Mock()
        
        mock_db.query = query_side_effect
        
        sla_service.create_timer(
            company_id="company-1",
            ticket_id="ticket-1",
            policy_id="policy-1",
        )
        
        assert mock_ticket.resolution_target_at is not None


class TestSLABreachDetection:
    """Tests for SLA breach detection (PS11, PS17)."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def sla_service(self, mock_db):
        return SLAService(mock_db)

    def test_check_breach_no_timer(self, sla_service, mock_db):
        """Test breach check returns False when no timer."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        is_breached, breach_type = sla_service.check_breach("company-1", "ticket-1")
        
        assert is_breached is False
        assert breach_type is None

    def test_is_approaching_breach_no_timer(self, sla_service, mock_db):
        """Test approaching check returns False when no timer."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        mock_db.query = Mock(return_value=mock_query)
        
        is_approaching, percentage = sla_service.is_approaching_breach("company-1", "ticket-1")
        
        assert is_approaching is False
        assert percentage is None


class TestSLAStats:
    """Tests for SLA statistics."""

    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def sla_service(self, mock_db):
        return SLAService(mock_db)

    def test_get_sla_stats_empty(self, sla_service, mock_db):
        """Test SLA stats when no timers exist."""
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[])
        mock_db.query = Mock(return_value=mock_query)
        
        stats = sla_service.get_sla_stats("company-1")
        
        assert stats["total_tickets"] == 0
        assert stats["breached_count"] == 0
        assert stats["compliant_count"] == 0
        assert stats["compliance_rate"] == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDay29Integration:
    """Integration tests for Day 29 components."""

    def test_bulk_action_type_enum_values(self):
        """Test that all bulk action types are defined."""
        assert BulkActionType.STATUS_CHANGE.value == "status_change"
        assert BulkActionType.REASSIGN.value == "reassign"
        assert BulkActionType.TAG.value == "tag"
        assert BulkActionType.PRIORITY.value == "priority"
        assert BulkActionType.CLOSE.value == "close"

    def test_priority_enum_values(self):
        """Test that all priority values are defined."""
        assert Priority.critical.value == "critical"
        assert Priority.high.value == "high"
        assert Priority.medium.value == "medium"
        assert Priority.low.value == "low"

    def test_plan_tier_enum_values(self):
        """Test that all plan tier values are defined."""
        assert PlanTier.starter.value == "starter"
        assert PlanTier.growth.value == "growth"
        assert PlanTier.high.value == "high"

    def test_bulk_action_service_initialization(self):
        """Test BulkActionService can be initialized."""
        mock_db = Mock(spec=Session)
        service = BulkActionService(mock_db)
        
        assert service.db == mock_db
        assert service.MAX_TICKETS_PER_ACTION == 500

    def test_ticket_merge_service_initialization(self):
        """Test TicketMergeService can be initialized."""
        mock_db = Mock(spec=Session)
        service = TicketMergeService(mock_db)
        
        assert service.db == mock_db

    def test_sla_service_initialization(self):
        """Test SLAService can be initialized."""
        mock_db = Mock(spec=Session)
        service = SLAService(mock_db)
        
        assert service.db == mock_db
        assert service.APPROACHING_THRESHOLD == 0.75
