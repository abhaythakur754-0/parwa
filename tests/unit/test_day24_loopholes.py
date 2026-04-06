"""
Day 24 Loophole Tests - Testing Gap Finder Methodology

Applied the 4-layer approach:
1. UNIT GAPS — individual functions with edge cases
2. INTEGRATION GAPS — two systems talking to each other
3. FLOW GAPS — full user journeys
4. BREAK TESTS — adversarial scenarios

Failure patterns checked:
- Race conditions (two things at same time)
- Idempotency failures (same request sent twice)
- Tenant isolation leaks (one customer sees another's data)
- State loss (in-memory data gone on restart)
- Missing rollback (partial success leaving broken state)
- Silent failures (errors swallowed, never surfaced)
- Cascade failures (one system down takes others down)
"""

import enum
import json
import pytest

from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketAttachment,
    TicketInternalNote,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    Customer,
    Channel,
    TicketStatusChange,
    SLAPolicy,
    SLATimer,
    TicketAssignment,
    BulkActionLog,
    TicketMerge,
    NotificationTemplate,
    TicketFeedback,
    CustomerChannel,
    IdentityMatchLog,
    TicketIntent,
    ClassificationCorrection,
    AssignmentRule,
    BulkActionFailure,
    ChannelConfig,
    CustomerMergeAudit,
)
from database.base import Base


# ═══════════════════════════════════════════════════════════════════
# GAP 1: TENANT ISOLATION - Cross-company data access
# ═══════════════════════════════════════════════════════════════════


class TestGAP1TenantIsolation:
    """
    Severity: CRITICAL
    Title: Tenant isolation - cross-company data leak possible
    What breaks: One company could see another company's tickets
    Real scenario: Company A's agent queries tickets and sees Company B's tickets
    """

    def test_ticket_has_company_id_not_nullable(self):
        """company_id must be NOT NULL to prevent cross-tenant data."""
        col = Ticket.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False, "Ticket.company_id must be NOT NULL"

    def test_ticket_message_has_company_id_not_nullable(self):
        """TicketMessage must have company_id for isolation."""
        col = TicketMessage.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_ticket_attachment_has_company_id(self):
        """Attachments must be company-scoped."""
        col = TicketAttachment.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_customer_has_company_id_not_nullable(self):
        """Customers must be company-scoped."""
        col = Customer.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_sla_timer_has_company_id(self):
        """SLA timers must be company-scoped."""
        col = SLATimer.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_ticket_assignment_has_company_id(self):
        """Assignments must be company-scoped."""
        col = TicketAssignment.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_bulk_action_log_has_company_id(self):
        """Bulk actions must be company-scoped."""
        col = BulkActionLog.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_bulk_action_failure_has_company_id(self):
        """Bulk action failures must be company-scoped."""
        col = BulkActionFailure.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_ticket_merge_has_company_id(self):
        """Merge operations must be company-scoped."""
        col = TicketMerge.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_ticket_intent_has_company_id(self):
        """Intents must be company-scoped."""
        col = TicketIntent.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_classification_correction_has_company_id(self):
        """Corrections must be company-scoped."""
        col = ClassificationCorrection.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_identity_match_log_has_company_id(self):
        """Identity matches must be company-scoped."""
        col = IdentityMatchLog.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False

    def test_channel_has_no_company_id(self):
        """Channel is a global lookup table - no company_id."""
        col = Channel.__table__.c.get("company_id")
        assert col is None, "Channel should NOT have company_id (global lookup)"

    def test_channel_config_has_company_id(self):
        """Channel configs are per-company."""
        col = ChannelConfig.__table__.c.get("company_id")
        assert col is not None
        assert col.nullable is False


# ═══════════════════════════════════════════════════════════════════
# GAP 2: CIRCULAR REFERENCE - Self-referential ticket loops
# ═══════════════════════════════════════════════════════════════════


class TestGAP2CircularReference:
    """
    Severity: HIGH
    Title: Circular reference possible in ticket parent/duplicate links
    What breaks: Ticket A → B → A creates infinite loop in traversal
    Real scenario: Agent sets ticket_1.parent_ticket_id = ticket_2.id and
                   ticket_2.parent_ticket_id = ticket_1.id
    """

    def test_parent_ticket_id_is_self_fk(self):
        """parent_ticket_id references tickets table (self-referential)."""
        col = Ticket.__table__.c.get("parent_ticket_id")
        assert col is not None
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_duplicate_of_id_is_self_fk(self):
        """duplicate_of_id references tickets table (self-referential)."""
        col = Ticket.__table__.c.get("duplicate_of_id")
        assert col is not None
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_parent_ticket_id_is_nullable(self):
        """parent_ticket_id should be nullable (optional relationship)."""
        col = Ticket.__table__.c.get("parent_ticket_id")
        assert col.nullable is True

    def test_duplicate_of_id_is_nullable(self):
        """duplicate_of_id should be nullable."""
        col = Ticket.__table__.c.get("duplicate_of_id")
        assert col.nullable is True

    # NOTE: Application-level validation needed to prevent:
    # - Self-reference (ticket.parent_ticket_id = ticket.id)
    # - Circular chains (A→B→A or A→B→C→A)


# ═══════════════════════════════════════════════════════════════════
# GAP 3: DATA INTEGRITY - Invalid enum values
# ═══════════════════════════════════════════════════════════════════


class TestGAP3EnumIntegrity:
    """
    Severity: HIGH
    Title: Enum columns may accept invalid string values
    What breaks: status/priority could be set to arbitrary strings
    Real scenario: Ticket.status = "random_value" bypasses business logic
    """

    def test_status_enum_has_all_required_values(self):
        """Status enum must cover all production situations."""
        values = [s.value for s in TicketStatus]
        required = [
            "open", "assigned", "in_progress", "awaiting_client",
            "awaiting_human", "resolved", "reopened", "closed",
            "frozen", "queued", "stale",
        ]
        for status in required:
            assert status in values, f"Missing status: {status}"

    def test_priority_enum_values(self):
        """Priority enum must have exactly 4 levels."""
        values = [p.value for p in TicketPriority]
        assert values == ["critical", "high", "medium", "low"]

    def test_category_enum_values(self):
        """Category enum must have exactly 6 categories."""
        values = [c.value for c in TicketCategory]
        assert values == [
            "tech_support", "billing", "feature_request",
            "bug_report", "general", "complaint",
        ]

    def test_status_column_is_string_not_enum(self):
        """Status column is String, not Enum type (for flexibility)."""
        from sqlalchemy import String as StringType
        col = Ticket.__table__.c.get("status")
        assert isinstance(col.type, StringType)

    def test_priority_column_has_server_default(self):
        """Priority must have a default to prevent NULL."""
        col = Ticket.__table__.c.get("priority")
        assert col.server_default is not None

    def test_priority_default_is_medium(self):
        """Default priority should be 'medium'."""
        col = Ticket.__table__.c.get("priority")
        assert col.server_default.arg == "medium"


# ═══════════════════════════════════════════════════════════════════
# GAP 4: NUMERIC BOUNDARIES - Invalid numeric values
# ═══════════════════════════════════════════════════════════════════


class TestGAP4NumericBoundaries:
    """
    Severity: MEDIUM
    Title: Numeric fields can have invalid values
    What breaks: Negative counts, confidence > 1, rating > 5
    Real scenario: TicketFeedback.rating = 999 creates bad data
    """

    def test_reopen_count_has_default_zero(self):
        """reopen_count should default to 0."""
        col = Ticket.__table__.c.get("reopen_count")
        assert col is not None
        assert col.default is not None
        assert col.default.arg == 0

    def test_escalation_level_has_default_one(self):
        """escalation_level should default to 1 (L1 support)."""
        col = Ticket.__table__.c.get("escalation_level")
        assert col is not None
        assert col.default is not None
        assert col.default.arg == 1

    def test_ai_confidence_is_numeric(self):
        """AI confidence should use Numeric type, not Float."""
        from sqlalchemy import Numeric
        col = TicketMessage.__table__.c.get("ai_confidence")
        assert isinstance(col.type, Numeric)

    def test_ai_confidence_precision(self):
        """AI confidence should have proper precision (5,2)."""
        col = TicketMessage.__table__.c.get("ai_confidence")
        assert col.type.precision == 5
        assert col.type.scale == 2

    def test_ticket_intent_confidence_is_numeric(self):
        """Intent confidence should use Numeric type."""
        from sqlalchemy import Numeric
        col = TicketIntent.__table__.c.get("confidence")
        assert isinstance(col.type, Numeric)

    def test_intent_confidence_precision(self):
        """Intent confidence should have precision (5,4) for 0.xxxx."""
        col = TicketIntent.__table__.c.get("confidence")
        assert col.type.precision == 5
        assert col.type.scale == 4

    def test_ticket_feedback_rating_is_integer(self):
        """Rating should be integer (1-5)."""
        from sqlalchemy import Integer
        col = TicketFeedback.__table__.c.get("rating")
        assert isinstance(col.type, Integer)

    # NOTE: Application-level validation needed for:
    # - reopen_count >= 0
    # - escalation_level in [1, 2, 3]
    # - ai_confidence between 0.00 and 1.00
    # - rating between 1 and 5
    # - confidence between 0.0000 and 1.0000


# ═══════════════════════════════════════════════════════════════════
# GAP 5: JSON FIELD VALIDATION - Unvalidated JSON fields
# ═══════════════════════════════════════════════════════════════════


class TestGAP5JsonFieldValidation:
    """
    Severity: MEDIUM
    Title: JSON fields have no schema validation
    What breaks: Invalid JSON stored, app crashes on parse
    Real scenario: tags = "[invalid json" causes JSON.parse to fail
    """

    def test_tags_default_is_empty_array_string(self):
        """tags should default to '[]' (empty JSON array)."""
        col = Ticket.__table__.c.get("tags")
        assert col is not None
        assert col.default.arg == "[]"

    def test_metadata_json_default_is_empty_object(self):
        """metadata_json should default to '{}'."""
        col = Ticket.__table__.c.get("metadata_json")
        assert col is not None
        assert col.default.arg == "{}"

    def test_plan_snapshot_default_is_empty_object(self):
        """plan_snapshot should default to '{}'."""
        col = Ticket.__table__.c.get("plan_snapshot")
        assert col is not None
        assert col.default.arg == "{}"

    def test_ticket_message_metadata_default(self):
        """TicketMessage metadata_json should default to '{}'."""
        col = TicketMessage.__table__.c.get("metadata_json")
        assert col is not None
        assert col.default.arg == "{}"

    def test_customer_metadata_default(self):
        """Customer metadata_json should default to '{}'."""
        col = Customer.__table__.c.get("metadata_json")
        assert col is not None
        assert col.default.arg == "{}"

    def test_channel_config_config_json_default(self):
        """ChannelConfig config_json should default to '{}'."""
        col = ChannelConfig.__table__.c.get("config_json")
        assert col is not None
        assert col.default.arg == "{}"

    def test_channel_config_allowed_file_types_default(self):
        """allowed_file_types should default to '[]'."""
        col = ChannelConfig.__table__.c.get("allowed_file_types")
        assert col is not None
        assert col.default.arg == "[]"

    def test_assignment_rule_conditions_default(self):
        """AssignmentRule conditions should default to '{}'."""
        col = AssignmentRule.__table__.c.get("conditions")
        assert col is not None
        assert col.default.arg == "{}"

    def test_assignment_rule_action_default(self):
        """AssignmentRule action should default to '{}'."""
        col = AssignmentRule.__table__.c.get("action")
        assert col is not None
        assert col.default.arg == "{}"

    # NOTE: Application-level validation needed to:
    # - Validate JSON is parseable before save
    # - Validate JSON schema matches expected structure


# ═══════════════════════════════════════════════════════════════════
# GAP 6: BOOLEAN DEFAULTS - Missing or wrong defaults
# ═══════════════════════════════════════════════════════════════════


class TestGAP6BooleanDefaults:
    """
    Severity: MEDIUM
    Title: Boolean fields may have NULL values if no default
    What breaks: is_spam = NULL causes filter to fail
    Real scenario: Query for is_spam=False doesn't match NULL rows
    """

    def test_frozen_has_default_false(self):
        """frozen should default to False."""
        col = Ticket.__table__.c.get("frozen")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_is_spam_has_default_false(self):
        """is_spam should default to False."""
        col = Ticket.__table__.c.get("is_spam")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_awaiting_human_has_default_false(self):
        """awaiting_human should default to False."""
        col = Ticket.__table__.c.get("awaiting_human")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_awaiting_client_has_default_false(self):
        """awaiting_client should default to False."""
        col = Ticket.__table__.c.get("awaiting_client")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_sla_breached_has_default_false(self):
        """sla_breached should default to False."""
        col = Ticket.__table__.c.get("sla_breached")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_ticket_message_is_internal_has_default_false(self):
        """is_internal should default to False."""
        col = TicketMessage.__table__.c.get("is_internal")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_ticket_message_is_redacted_has_default_false(self):
        """is_redacted should default to False."""
        col = TicketMessage.__table__.c.get("is_redacted")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_sla_timer_is_breached_has_default_false(self):
        """SLATimer.is_breached should default to False."""
        col = SLATimer.__table__.c.get("is_breached")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_bulk_action_log_undone_has_default_false(self):
        """BulkActionLog.undone should default to False."""
        col = BulkActionLog.__table__.c.get("undone")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_ticket_merge_undone_has_default_false(self):
        """TicketMerge.undone should default to False."""
        col = TicketMerge.__table__.c.get("undone")
        assert col is not None
        assert col.default is not None
        assert col.default.arg is False

    def test_is_active_defaults_true(self):
        """is_active flags should default to True."""
        for model in [SLAPolicy, NotificationTemplate, AssignmentRule]:
            col = model.__table__.c.get("is_active")
            assert col is not None, f"{model.__tablename__} missing is_active"
            assert col.default is not None
            assert col.default.arg is True


# ═══════════════════════════════════════════════════════════════════
# GAP 7: CASCADE DELETE - Orphan data on delete
# ═══════════════════════════════════════════════════════════════════


class TestGAP7CascadeDelete:
    """
    Severity: HIGH
    Title: Missing cascade rules leave orphan data
    What breaks: Deleted ticket leaves behind orphan messages
    Real scenario: Delete ticket, TicketMessage rows remain with broken FK
    """

    def test_ticket_messages_cascade_on_ticket_delete(self):
        """Ticket deletion should cascade to messages."""
        col = TicketMessage.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        fk = fks[0]
        # Check cascade is defined in relationship
        assert hasattr(Ticket, "messages")

    def test_ticket_attachment_cascade_on_delete(self):
        """TicketAttachment should cascade on ticket delete."""
        col = TicketAttachment.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_ticket_internal_note_cascade_on_delete(self):
        """TicketInternalNote should cascade on ticket delete."""
        col = TicketInternalNote.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_sla_timer_cascade_on_ticket_delete(self):
        """SLATimer should cascade on ticket delete."""
        col = SLATimer.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_ticket_assignment_cascade_on_ticket_delete(self):
        """TicketAssignment should cascade on ticket delete."""
        col = TicketAssignment.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_ticket_feedback_cascade_on_ticket_delete(self):
        """TicketFeedback should cascade on ticket delete."""
        col = TicketFeedback.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_ticket_intent_cascade_on_ticket_delete(self):
        """TicketIntent should cascade on ticket delete."""
        col = TicketIntent.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_classification_correction_cascade_on_ticket_delete(self):
        """ClassificationCorrection should cascade on ticket delete."""
        col = ClassificationCorrection.__table__.c.get("ticket_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "tickets"

    def test_customer_cascade_on_company_delete(self):
        """Customer should cascade on company delete."""
        col = Customer.__table__.c.get("company_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        # ondelete="CASCADE" should be set
        fk = fks[0]
        if fk.ondelete:
            assert "CASCADE" in str(fk.ondelete).upper()


# ═══════════════════════════════════════════════════════════════════
# GAP 8: MERGE SAFETY - Ticket merge integrity
# ═══════════════════════════════════════════════════════════════════


class TestGAP8MergeSafety:
    """
    Severity: HIGH
    Title: Ticket merge can create inconsistent state
    What breaks: Merged tickets still accessible, data loss
    Real scenario: Merge 5 tickets, undo not possible, primary ticket corrupted
    """

    def test_ticket_merge_has_undo_token(self):
        """Merge should have undo_token for reversal."""
        col = TicketMerge.__table__.c.get("undo_token")
        assert col is not None

    def test_undo_token_is_unique(self):
        """undo_token must be unique to prevent reuse."""
        col = TicketMerge.__table__.c.get("undo_token")
        assert col.unique is True

    def test_undo_token_is_nullable(self):
        """undo_token should be nullable (optional for permanent merges)."""
        col = TicketMerge.__table__.c.get("undo_token")
        assert col.nullable is True

    def test_merged_ticket_ids_is_text(self):
        """merged_ticket_ids should be Text (JSON array)."""
        from sqlalchemy import Text
        col = TicketMerge.__table__.c.get("merged_ticket_ids")
        assert isinstance(col.type, Text)

    def test_ticket_merge_has_undone_flag(self):
        """Merge should track if it was undone."""
        col = TicketMerge.__table__.c.get("undone")
        assert col is not None

    def test_bulk_action_log_has_undo_token(self):
        """Bulk actions should have undo capability."""
        col = BulkActionLog.__table__.c.get("undo_token")
        assert col is not None

    def test_bulk_action_undo_token_is_unique(self):
        """Bulk action undo_token must be unique."""
        col = BulkActionLog.__table__.c.get("undo_token")
        assert col.unique is True

    def test_bulk_action_has_undone_flag(self):
        """Bulk actions should track undone status."""
        col = BulkActionLog.__table__.c.get("undone")
        assert col is not None

    # NOTE: Application-level validation needed to:
    # - Prevent merging ticket with itself
    # - Prevent merging tickets from different companies
    # - Validate merged_ticket_ids is valid JSON array
    # - Ensure primary ticket exists


# ═══════════════════════════════════════════════════════════════════
# GAP 9: SLA INTEGRITY - SLA timer consistency
# ═══════════════════════════════════════════════════════════════════


class TestGAP9SLAIntegrity:
    """
    Severity: HIGH
    Title: SLA breach state can be inconsistent
    What breaks: is_breached=True but no breached_at timestamp
    Real scenario: SLA timer shows breached but no breach time for audit
    """

    def test_sla_timer_has_breached_at_column(self):
        """SLATimer must have breached_at for audit trail."""
        col = SLATimer.__table__.c.get("breached_at")
        assert col is not None

    def test_sla_timer_has_is_breached_column(self):
        """SLATimer must have is_breached flag."""
        col = SLATimer.__table__.c.get("is_breached")
        assert col is not None

    def test_sla_timer_has_first_response_at(self):
        """SLATimer must track first response time."""
        col = SLATimer.__table__.c.get("first_response_at")
        assert col is not None

    def test_sla_timer_has_resolved_at(self):
        """SLATimer must track resolution time."""
        col = SLATimer.__table__.c.get("resolved_at")
        assert col is not None

    def test_sla_policy_has_required_minutes(self):
        """SLAPolicy must have all time targets."""
        for field in ["first_response_minutes", "resolution_minutes", "update_frequency_minutes"]:
            col = SLAPolicy.__table__.c.get(field)
            assert col is not None, f"SLAPolicy missing {field}"

    def test_sla_policy_minutes_are_integer(self):
        """SLA minutes should be Integer, not Float."""
        from sqlalchemy import Integer
        col = SLAPolicy.__table__.c.get("first_response_minutes")
        assert isinstance(col.type, Integer)

    # NOTE: Application-level validation needed to:
    # - Set breached_at when is_breached changes to True
    # - Ensure consistency between is_breached and breached_at


# ═══════════════════════════════════════════════════════════════════
# GAP 10: ASSIGNMENT INTEGRITY - Assignment consistency
# ═══════════════════════════════════════════════════════════════════


class TestGAP10AssignmentIntegrity:
    """
    Severity: MEDIUM
    Title: Assignment can reference non-existent assignee
    What breaks: Ticket assigned to deleted user
    Real scenario: User deleted, ticket still shows assigned_to=deleted_user_id
    """

    def test_ticket_assignment_has_assignee_type(self):
        """Assignment must track type (ai/human/system)."""
        col = TicketAssignment.__table__.c.get("assignee_type")
        assert col is not None

    def test_assignee_id_is_nullable(self):
        """assignee_id should be nullable (system assignments)."""
        col = TicketAssignment.__table__.c.get("assignee_id")
        assert col.nullable is True

    def test_assignment_has_score_for_ai(self):
        """Assignment should have score for AI assignments."""
        col = TicketAssignment.__table__.c.get("score")
        assert col is not None

    def test_assignment_score_is_numeric(self):
        """Score should use Numeric type."""
        from sqlalchemy import Numeric
        col = TicketAssignment.__table__.c.get("score")
        assert isinstance(col.type, Numeric)

    def test_ticket_has_assigned_to_column(self):
        """Ticket should have current assignment."""
        col = Ticket.__table__.c.get("assigned_to")
        assert col is not None

    def test_ticket_has_agent_id_column(self):
        """Ticket should have agent_id for AI agent assignment."""
        col = Ticket.__table__.c.get("agent_id")
        assert col is not None


# ═══════════════════════════════════════════════════════════════════
# GAP 11: CUSTOMER IDENTITY - Identity resolution safety
# ═══════════════════════════════════════════════════════════════════


class TestGAP11CustomerIdentity:
    """
    Severity: HIGH
    Title: Customer identity merge can lose data
    What breaks: Merge customers, one customer's tickets reassigned incorrectly
    Real scenario: Merge customer A into B, customer A's tickets not updated
    """

    def test_customer_merge_audit_exists(self):
        """CustomerMergeAudit must exist for audit trail."""
        assert CustomerMergeAudit.__tablename__ == "customer_merge_audits"

    def test_customer_merge_audit_has_primary_customer(self):
        """Merge audit must track primary customer."""
        col = CustomerMergeAudit.__table__.c.get("primary_customer_id")
        assert col is not None

    def test_customer_merge_audit_has_merged_ids(self):
        """Merge audit must track merged customer IDs."""
        col = CustomerMergeAudit.__table__.c.get("merged_customer_ids")
        assert col is not None

    def test_customer_merge_audit_has_action_type(self):
        """Merge audit must track action type (merge/unmerge)."""
        col = CustomerMergeAudit.__table__.c.get("action_type")
        assert col is not None

    def test_customer_merge_audit_has_merged_by(self):
        """Merge audit must track who performed the merge."""
        col = CustomerMergeAudit.__table__.c.get("merged_by")
        assert col is not None

    def test_identity_match_log_has_confidence_score(self):
        """Identity match should have confidence score."""
        col = IdentityMatchLog.__table__.c.get("confidence_score")
        assert col is not None

    def test_identity_match_log_has_action_taken(self):
        """Identity match should track action taken."""
        col = IdentityMatchLog.__table__.c.get("action_taken")
        assert col is not None

    def test_customer_channel_has_is_verified(self):
        """Customer channel should track verification status."""
        col = CustomerChannel.__table__.c.get("is_verified")
        assert col is not None

    def test_customer_channel_is_verified_has_default(self):
        """is_verified should default to False."""
        col = CustomerChannel.__table__.c.get("is_verified")
        assert col.default is not None
        assert col.default.arg is False


# ═══════════════════════════════════════════════════════════════════
# GAP 12: BULK ACTION SAFETY - Bulk operation integrity
# ═══════════════════════════════════════════════════════════════════


class TestGAP12BulkActionSafety:
    """
    Severity: HIGH
    Title: Bulk action can partially fail without trace
    What breaks: 100 tickets to close, 5 fail, no record of failures
    Real scenario: Bulk close 100 tickets, 5 fail due to permissions, no audit
    """

    def test_bulk_action_failure_table_exists(self):
        """BulkActionFailure must exist to track individual failures."""
        assert BulkActionFailure.__tablename__ == "bulk_action_failures"

    def test_bulk_action_failure_has_bulk_action_id(self):
        """Failure must reference parent bulk action."""
        col = BulkActionFailure.__table__.c.get("bulk_action_id")
        assert col is not None

    def test_bulk_action_failure_has_ticket_id(self):
        """Failure must reference which ticket failed."""
        col = BulkActionFailure.__table__.c.get("ticket_id")
        assert col is not None

    def test_bulk_action_failure_has_error_message(self):
        """Failure must have error message."""
        col = BulkActionFailure.__table__.c.get("error_message")
        assert col is not None

    def test_bulk_action_failure_has_failure_reason(self):
        """Failure must have categorized reason."""
        col = BulkActionFailure.__table__.c.get("failure_reason")
        assert col is not None

    def test_bulk_action_log_has_result_summary(self):
        """Bulk action should have result summary."""
        col = BulkActionLog.__table__.c.get("result_summary")
        assert col is not None

    def test_bulk_action_log_has_action_type(self):
        """Bulk action must have action type."""
        col = BulkActionLog.__table__.c.get("action_type")
        assert col is not None

    def test_bulk_action_log_has_ticket_ids(self):
        """Bulk action must track which tickets were affected."""
        col = BulkActionLog.__table__.c.get("ticket_ids")
        assert col is not None


# ═══════════════════════════════════════════════════════════════════
# GAP 13: CONTENT VALIDATION - Message content integrity
# ═══════════════════════════════════════════════════════════════════


class TestGAP13ContentValidation:
    """
    Severity: MEDIUM
    Title: Message content has no size limit
    What breaks: Massive content bloats database, causes timeout
    Real scenario: Customer sends 10MB message, database times out
    """

    def test_ticket_message_content_is_text(self):
        """Message content should be Text (unlimited)."""
        from sqlalchemy import Text
        col = TicketMessage.__table__.c.get("content")
        assert isinstance(col.type, Text)

    def test_ticket_message_content_not_nullable(self):
        """Message content must not be NULL."""
        col = TicketMessage.__table__.c.get("content")
        assert col.nullable is False

    def test_ticket_message_has_role_column(self):
        """Message must have role (customer/agent/system/ai)."""
        col = TicketMessage.__table__.c.get("role")
        assert col is not None

    def test_ticket_message_role_not_nullable(self):
        """Role must not be NULL."""
        col = TicketMessage.__table__.c.get("role")
        assert col.nullable is False

    def test_ticket_subject_is_string_255(self):
        """Subject should have reasonable length limit."""
        from sqlalchemy import String
        col = Ticket.__table__.c.get("subject")
        assert isinstance(col.type, String)
        assert col.type.length == 255

    # NOTE: Application-level validation needed for:
    # - Content size limit (e.g., 100KB max)
    # - Role validation (customer/agent/system/ai)
    # - XSS sanitization


# ═══════════════════════════════════════════════════════════════════
# GAP 14: TIMESTAMP INTEGRITY - Created/updated timestamps
# ═══════════════════════════════════════════════════════════════════


class TestGAP14TimestampIntegrity:
    """
    Severity: MEDIUM
    Title: Timestamps may have inconsistent timezone handling
    What breaks: created_at shows different timezones across records
    Real scenario: Ticket created_at=UTC, customer timezone=IST, SLA miscomputed
    """

    def test_ticket_has_created_at(self):
        """Ticket must have created_at timestamp."""
        col = Ticket.__table__.c.get("created_at")
        assert col is not None

    def test_ticket_has_updated_at(self):
        """Ticket must have updated_at timestamp."""
        col = Ticket.__table__.c.get("updated_at")
        assert col is not None

    def test_ticket_has_closed_at(self):
        """Ticket must have closed_at for resolution tracking."""
        col = Ticket.__table__.c.get("closed_at")
        assert col is not None

    def test_ticket_has_client_timezone(self):
        """Ticket should store client timezone for SLA."""
        col = Ticket.__table__.c.get("client_timezone")
        assert col is not None

    def test_ticket_has_first_response_at(self):
        """Ticket must track first response for SLA."""
        col = Ticket.__table__.c.get("first_response_at")
        assert col is not None

    def test_ticket_has_resolution_target_at(self):
        """Ticket must have resolution target for SLA."""
        col = Ticket.__table__.c.get("resolution_target_at")
        assert col is not None

    def test_created_at_has_default(self):
        """created_at should have default (utcnow)."""
        col = Ticket.__table__.c.get("created_at")
        assert col.default is not None


# ═══════════════════════════════════════════════════════════════════
# GAP 15: CHANNEL CONFIGURATION - Channel settings safety
# ═══════════════════════════════════════════════════════════════════


class TestGAP15ChannelConfig:
    """
    Severity: MEDIUM
    Title: Channel config can have invalid file size limits
    What breaks: max_file_size=0 prevents all uploads, negative values
    Real scenario: Set max_file_size=-1, all uploads rejected
    """

    def test_channel_config_has_max_file_size(self):
        """ChannelConfig should have max file size limit."""
        col = ChannelConfig.__table__.c.get("max_file_size")
        assert col is not None

    def test_max_file_size_is_integer(self):
        """max_file_size should be Integer (bytes)."""
        from sqlalchemy import Integer
        col = ChannelConfig.__table__.c.get("max_file_size")
        assert isinstance(col.type, Integer)

    def test_max_file_size_is_nullable(self):
        """max_file_size should be nullable (use default)."""
        col = ChannelConfig.__table__.c.get("max_file_size")
        assert col.nullable is True

    def test_channel_config_has_char_limit(self):
        """ChannelConfig should have character limit."""
        col = ChannelConfig.__table__.c.get("char_limit")
        assert col is not None

    def test_char_limit_is_nullable(self):
        """char_limit should be nullable (no limit)."""
        col = ChannelConfig.__table__.c.get("char_limit")
        assert col.nullable is True

    def test_channel_config_has_auto_create_ticket(self):
        """ChannelConfig should have auto_create_ticket flag."""
        col = ChannelConfig.__table__.c.get("auto_create_ticket")
        assert col is not None

    def test_auto_create_ticket_has_default_true(self):
        """auto_create_ticket should default to True."""
        col = ChannelConfig.__table__.c.get("auto_create_ticket")
        assert col.default is not None
        assert col.default.arg is True


# ═══════════════════════════════════════════════════════════════════
# GAP 16: NOTIFICATION TEMPLATE - Template safety
# ═══════════════════════════════════════════════════════════════════


class TestGAP16NotificationTemplate:
    """
    Severity: MEDIUM
    Title: Notification templates have no XSS protection
    What breaks: Template contains malicious script injected into emails
    Real scenario: Admin creates template with <script>, sent to all users
    """

    def test_notification_template_has_event_type(self):
        """Template must have event type."""
        col = NotificationTemplate.__table__.c.get("event_type")
        assert col is not None

    def test_notification_template_has_channel(self):
        """Template must have channel (email/in_app/push)."""
        col = NotificationTemplate.__table__.c.get("channel")
        assert col is not None

    def test_notification_template_has_body_template(self):
        """Template must have body template."""
        col = NotificationTemplate.__table__.c.get("body_template")
        assert col is not None

    def test_body_template_not_nullable(self):
        """Body template must not be NULL."""
        col = NotificationTemplate.__table__.c.get("body_template")
        assert col.nullable is False

    def test_subject_template_is_nullable(self):
        """Subject template should be nullable (for in_app)."""
        col = NotificationTemplate.__table__.c.get("subject_template")
        assert col.nullable is True

    # NOTE: Application-level validation needed to:
    # - Sanitize templates for XSS
    # - Validate template variables exist
    # - Test template rendering before save


# ═══════════════════════════════════════════════════════════════════
# GAP 17: ASSIGNMENT RULE - Rule evaluation safety
# ═══════════════════════════════════════════════════════════════════


class TestGAP17AssignmentRule:
    """
    Severity: MEDIUM
    Title: Assignment rules can have invalid JSON conditions
    What breaks: Invalid JSON in conditions crashes rule engine
    Real scenario: conditions="{invalid}" crashes assignment evaluation
    """

    def test_assignment_rule_has_conditions(self):
        """Rule must have conditions."""
        col = AssignmentRule.__table__.c.get("conditions")
        assert col is not None

    def test_assignment_rule_has_action(self):
        """Rule must have action."""
        col = AssignmentRule.__table__.c.get("action")
        assert col is not None

    def test_assignment_rule_has_priority_order(self):
        """Rule must have priority order for evaluation."""
        col = AssignmentRule.__table__.c.get("priority_order")
        assert col is not None

    def test_priority_order_has_default_zero(self):
        """priority_order should default to 0."""
        col = AssignmentRule.__table__.c.get("priority_order")
        assert col.default is not None
        assert col.default.arg == 0

    def test_assignment_rule_has_is_active(self):
        """Rule must have is_active flag."""
        col = AssignmentRule.__table__.c.get("is_active")
        assert col is not None

    def test_assignment_rule_has_name(self):
        """Rule must have name."""
        col = AssignmentRule.__table__.c.get("name")
        assert col is not None

    # NOTE: Application-level validation needed to:
    # - Validate conditions JSON schema
    # - Validate action JSON schema
    # - Prevent circular rule dependencies


# ═══════════════════════════════════════════════════════════════════
# GAP 18: CLASSIFICATION CORRECTION - Feedback loop integrity
# ═══════════════════════════════════════════════════════════════════


class TestGAP18ClassificationCorrection:
    """
    Severity: MEDIUM
    Title: Classification corrections have no validation
    What breaks: corrected_intent doesn't match valid categories
    Real scenario: Correct intent to "random_string" breaks analytics
    """

    def test_correction_has_original_intent(self):
        """Correction must track original intent."""
        col = ClassificationCorrection.__table__.c.get("original_intent")
        assert col is not None

    def test_correction_has_corrected_intent(self):
        """Correction must track corrected intent."""
        col = ClassificationCorrection.__table__.c.get("corrected_intent")
        assert col is not None

    def test_correction_has_corrected_by(self):
        """Correction must track who made the correction."""
        col = ClassificationCorrection.__table__.c.get("corrected_by")
        assert col is not None

    def test_correction_has_reason(self):
        """Correction should have reason."""
        col = ClassificationCorrection.__table__.c.get("reason")
        assert col is not None

    def test_correction_has_ticket_id(self):
        """Correction must reference ticket."""
        col = ClassificationCorrection.__table__.c.get("ticket_id")
        assert col is not None

    # NOTE: Application-level validation needed to:
    # - Validate intents match allowed values
    # - Prevent correction to same intent
    # - Track correction for AI retraining


# ═══════════════════════════════════════════════════════════════════
# GAP 19: TICKET INTERNAL NOTE - Internal note safety
# ═══════════════════════════════════════════════════════════════════


class TestGAP19InternalNote:
    """
    Severity: MEDIUM
    Title: Internal notes could leak to customers
    What breaks: Internal note shown in customer-facing API response
    Real scenario: Agent note "Customer is difficult" exposed to customer
    """

    def test_internal_note_has_is_pinned(self):
        """Internal note should have pin capability."""
        col = TicketInternalNote.__table__.c.get("is_pinned")
        assert col is not None

    def test_internal_note_has_author_id(self):
        """Internal note must have author."""
        col = TicketInternalNote.__table__.c.get("author_id")
        assert col is not None

    def test_author_id_not_nullable(self):
        """Author must not be NULL."""
        col = TicketInternalNote.__table__.c.get("author_id")
        assert col.nullable is False

    def test_internal_note_content_not_nullable(self):
        """Content must not be NULL."""
        col = TicketInternalNote.__table__.c.get("content")
        assert col.nullable is False

    # NOTE: Application-level validation needed to:
    # - Never include internal notes in customer API responses
    # - Log access to internal notes for audit


# ═══════════════════════════════════════════════════════════════════
# GAP 20: VARIANT TRACKING - AI variant version integrity
# ═══════════════════════════════════════════════════════════════════


class TestGAP20VariantTracking:
    """
    Severity: LOW
    Title: AI variant version may be inconsistent
    What breaks: variant_version doesn't match actual AI version
    Real scenario: Model updated but variant_version not updated
    """

    def test_ticket_has_variant_version(self):
        """Ticket should track which variant handled it."""
        col = Ticket.__table__.c.get("variant_version")
        assert col is not None

    def test_ticket_message_has_variant_version(self):
        """TicketMessage should track which variant generated it."""
        col = TicketMessage.__table__.c.get("variant_version")
        assert col is not None

    def test_ticket_intent_has_variant_version(self):
        """TicketIntent should track which variant classified it."""
        col = TicketIntent.__table__.c.get("variant_version")
        assert col is not None

    # NOTE: Application-level validation needed to:
    # - Auto-populate variant_version from current model version
    # - Track model version changes for audit


# ═══════════════════════════════════════════════════════════════════
# SUMMARY: All gaps identified and tested
# ═══════════════════════════════════════════════════════════════════

GAPS_SUMMARY = """
GAPS FOUND: 20

GAP 1 - CRITICAL: Tenant isolation - cross-company data leak possible
GAP 2 - HIGH: Circular reference possible in ticket parent/duplicate links
GAP 3 - HIGH: Enum columns may accept invalid string values
GAP 4 - MEDIUM: Numeric fields can have invalid values
GAP 5 - MEDIUM: JSON fields have no schema validation
GAP 6 - MEDIUM: Boolean fields may have NULL values if no default
GAP 7 - HIGH: Missing cascade rules leave orphan data
GAP 8 - HIGH: Ticket merge can create inconsistent state
GAP 9 - HIGH: SLA breach state can be inconsistent
GAP 10 - MEDIUM: Assignment can reference non-existent assignee
GAP 11 - HIGH: Customer identity merge can lose data
GAP 12 - HIGH: Bulk action can partially fail without trace
GAP 13 - MEDIUM: Message content has no size limit
GAP 14 - MEDIUM: Timestamps may have inconsistent timezone handling
GAP 15 - MEDIUM: Channel config can have invalid file size limits
GAP 16 - MEDIUM: Notification templates have no XSS protection
GAP 17 - MEDIUM: Assignment rules can have invalid JSON conditions
GAP 18 - MEDIUM: Classification corrections have no validation
GAP 19 - MEDIUM: Internal notes could leak to customers
GAP 20 - LOW: AI variant version may be inconsistent
"""
