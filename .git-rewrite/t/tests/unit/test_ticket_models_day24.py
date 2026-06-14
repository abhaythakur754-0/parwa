"""
Day 24 (Week 4 Day 1): Ticket Model Tests

Comprehensive tests for the rewritten ticket models covering:
- BL01: Table rename (Session→Ticket, Interaction→TicketMessage)
- BL02: All 11 new tables + 5 bonus tables = 16 new models
- MF01: TicketPriority enum
- MF02: TicketCategory enum
- MF03: Tags column
- BL04: No Float on money (billing uses Numeric)
- Production situation columns on Ticket and TicketMessage

Runs without DB — pure model introspection tests.
"""

import enum

import pytest

from database.models.tickets import (
    AssignmentRule,
    BulkActionFailure,
    BulkActionLog,
    Channel,
    ChannelConfig,
    ClassificationCorrection,
    Customer,
    CustomerChannel,
    CustomerMergeAudit,
    IdentityMatchLog,
    Interaction,
    NotificationTemplate,
    Session,
    SLAPolicy,
    SLATimer,
    Ticket,
    TicketAttachment,
    TicketAssignment,
    TicketCategory,
    TicketFeedback,
    TicketInternalNote,
    TicketIntent,
    TicketMerge,
    TicketMessage,
    TicketPriority,
    TicketStatus,
    TicketStatusChange,
)
from database.base import Base


# ═══════════════════════════════════════════════════════════════════
# BL01: Table Rename Tests
# ═══════════════════════════════════════════════════════════════════


class TestTableRename:
    """BL01: Verify Session→Ticket and Interaction→TicketMessage rename."""

    def test_session_alias_points_to_ticket(self):
        """Session should be an alias for Ticket."""
        assert Session is Ticket

    def test_interaction_alias_points_to_ticket_message(self):
        """Interaction should be an alias for TicketMessage."""
        assert Interaction is TicketMessage

    def test_ticket_tablename_is_tickets(self):
        """Ticket model should use 'tickets' table."""
        assert Ticket.__tablename__ == "tickets"

    def test_ticket_message_tablename_is_ticket_messages(self):
        """TicketMessage model should use 'ticket_messages' table."""
        assert TicketMessage.__tablename__ == "ticket_messages"

    def test_ticket_has_messages_relationship(self):
        """Ticket should have 'messages' relationship (was 'interactions')."""
        assert hasattr(Ticket, "messages")
        # Should NOT have old 'interactions' relationship name
        assert hasattr(Ticket, "interactions") is False

    def test_ticket_message_has_ticket_relationship(self):
        """TicketMessage should have 'ticket' relationship (was 'session')."""
        assert hasattr(TicketMessage, "ticket")
        # Should NOT have old 'session' relationship name
        assert hasattr(TicketMessage, "session") is False

    def test_ticket_attachment_references_tickets(self):
        """TicketAttachment FK should reference 'tickets.id'."""
        col = TicketAttachment.__table__.c.get("ticket_id")
        assert col is not None
        # Check FK target table name
        fk = list(col.foreign_keys)[0]
        assert fk.column.table.name == "tickets"

    def test_ticket_internal_note_references_tickets(self):
        """TicketInternalNote FK should reference 'tickets.id'."""
        col = TicketInternalNote.__table__.c.get("ticket_id")
        assert col is not None
        fk = list(col.foreign_keys)[0]
        assert fk.column.table.name == "tickets"


# ═══════════════════════════════════════════════════════════════════
# MF01: Priority System
# ═══════════════════════════════════════════════════════════════════


class TestPrioritySystem:
    """MF01: TicketPriority enum and priority column."""

    def test_priority_enum_exists(self):
        """TicketPriority enum should exist."""
        assert TicketPriority is not None

    def test_priority_enum_values(self):
        """Should have exactly 4 priority levels."""
        values = [p.value for p in TicketPriority]
        assert values == ["critical", "high", "medium", "low"]

    def test_priority_enum_is_string_enum(self):
        """Should be a string enum for easy comparison."""
        assert issubclass(TicketPriority, str)
        assert issubclass(TicketPriority, enum.Enum)

    def test_ticket_has_priority_column(self):
        """Ticket model should have priority column."""
        col = Ticket.__table__.c.get("priority")
        assert col is not None

    def test_ticket_priority_default_is_medium(self):
        """Default priority should be 'medium'."""
        col = Ticket.__table__.c.get("priority")
        assert col.server_default is not None
        assert col.server_default.arg == "medium"


# ═══════════════════════════════════════════════════════════════════
# MF02: Categories / Departments
# ═══════════════════════════════════════════════════════════════════


class TestCategorySystem:
    """MF02: TicketCategory enum and category column."""

    def test_category_enum_exists(self):
        """TicketCategory enum should exist."""
        assert TicketCategory is not None

    def test_category_enum_values(self):
        """Should have exactly 6 categories."""
        values = [c.value for c in TicketCategory]
        assert values == [
            "tech_support", "billing", "feature_request",
            "bug_report", "general", "complaint",
        ]

    def test_category_enum_is_string_enum(self):
        assert issubclass(TicketCategory, str)
        assert issubclass(TicketCategory, enum.Enum)

    def test_ticket_has_category_column(self):
        """Ticket model should have category column."""
        col = Ticket.__table__.c.get("category")
        assert col is not None

    def test_category_is_nullable(self):
        """Category should be nullable (set later by classification)."""
        col = Ticket.__table__.c.get("category")
        assert col.nullable is True


# ═══════════════════════════════════════════════════════════════════
# MF03: Tags / Labels
# ═══════════════════════════════════════════════════════════════════


class TestTagsSystem:
    """MF03: Tags column on tickets."""

    def test_ticket_has_tags_column(self):
        """Ticket model should have tags column."""
        col = Ticket.__table__.c.get("tags")
        assert col is not None

    def test_tags_default_is_empty_array(self):
        """Tags default should be '[]' (JSON array)."""
        col = Ticket.__table__.c.get("tags")
        assert col.default.arg == "[]"


# ═══════════════════════════════════════════════════════════════════
# TicketStatus Enum Tests
# ═══════════════════════════════════════════════════════════════════


class TestTicketStatusEnum:
    """Verify the expanded status enum covers all production situations."""

    def test_status_enum_exists(self):
        assert TicketStatus is not None

    def test_status_enum_has_all_values(self):
        """Should include all statuses needed for PS01-PS10 situations."""
        values = [s.value for s in TicketStatus]
        expected = [
            "open", "assigned", "in_progress",
            "awaiting_client",    # PS08
            "awaiting_human",     # PS02, PS03
            "resolved",
            "reopened",           # PS04
            "closed",
            "frozen",             # PS07
            "queued",             # PS13
            "stale",              # PS06
        ]
        assert values == expected

    def test_status_is_string_enum(self):
        assert issubclass(TicketStatus, str)
        assert issubclass(TicketStatus, enum.Enum)


# ═══════════════════════════════════════════════════════════════════
# Production Situation Columns on Ticket
# ═══════════════════════════════════════════════════════════════════


class TestTicketProductionColumns:
    """Verify all PS-related columns exist on Ticket model."""

    # PS04: reopen tracking
    def test_reopen_count_column(self):
        col = Ticket.__table__.c.get("reopen_count")
        assert col is not None

    # PS07: frozen when account suspended
    def test_frozen_column(self):
        col = Ticket.__table__.c.get("frozen")
        assert col is not None

    # PS19: cross-variant parent tickets
    def test_parent_ticket_id_column(self):
        col = Ticket.__table__.c.get("parent_ticket_id")
        assert col is not None

    # PS05: duplicate linking
    def test_duplicate_of_id_column(self):
        col = Ticket.__table__.c.get("duplicate_of_id")
        assert col is not None

    # MF21: spam flag
    def test_is_spam_column(self):
        col = Ticket.__table__.c.get("is_spam")
        assert col is not None

    # PS02: AI can't solve
    def test_awaiting_human_column(self):
        col = Ticket.__table__.c.get("awaiting_human")
        assert col is not None

    # PS08: awaiting client action
    def test_awaiting_client_column(self):
        col = Ticket.__table__.c.get("awaiting_client")
        assert col is not None

    # PS27: escalation level
    def test_escalation_level_column(self):
        col = Ticket.__table__.c.get("escalation_level")
        assert col is not None

    # PS11: SLA breach
    def test_sla_breached_column(self):
        col = Ticket.__table__.c.get("sla_breached")
        assert col is not None

    # PS14: plan snapshot for grandfathering
    def test_plan_snapshot_column(self):
        col = Ticket.__table__.c.get("plan_snapshot")
        assert col is not None

    # PS25: variant version
    def test_variant_version_column(self):
        col = Ticket.__table__.c.get("variant_version")
        assert col is not None

    # SLA tracking
    def test_first_response_at_column(self):
        col = Ticket.__table__.c.get("first_response_at")
        assert col is not None

    def test_resolution_target_at_column(self):
        col = Ticket.__table__.c.get("resolution_target_at")
        assert col is not None

    # PS23: client timezone
    def test_client_timezone_column(self):
        col = Ticket.__table__.c.get("client_timezone")
        assert col is not None


# ═══════════════════════════════════════════════════════════════════
# Production Situation Columns on TicketMessage
# ═══════════════════════════════════════════════════════════════════


class TestTicketMessageColumns:
    """Verify PS-related columns on TicketMessage model."""

    # BL07/PS29: PII redacted
    def test_is_redacted_column(self):
        col = TicketMessage.__table__.c.get("is_redacted")
        assert col is not None

    # F-049: AI confidence
    def test_ai_confidence_column(self):
        col = TicketMessage.__table__.c.get("ai_confidence")
        assert col is not None

    # PS25: variant version
    def test_variant_version_column(self):
        col = TicketMessage.__table__.c.get("variant_version")
        assert col is not None

    # F-049: classification
    def test_classification_column(self):
        col = TicketMessage.__table__.c.get("classification")
        assert col is not None

    # Internal notes distinction
    def test_is_internal_column(self):
        col = TicketMessage.__table__.c.get("is_internal")
        assert col is not None

    def test_ticket_message_tablename(self):
        assert TicketMessage.__tablename__ == "ticket_messages"

    def test_ticket_message_has_ticket_id_fk(self):
        col = TicketMessage.__table__.c.get("ticket_id")
        assert col is not None
        fk = list(col.foreign_keys)[0]
        assert fk.column.table.name == "tickets"


# ═══════════════════════════════════════════════════════════════════
# BL02: New Models — All 11 Missing Tables
# ═══════════════════════════════════════════════════════════════════


class TestBL02NewModels:
    """Verify all 11 missing tables from BL02 gap analysis now exist."""

    def test_ticket_intents_table(self):
        """BL02: ticket_intents"""
        assert TicketIntent.__tablename__ == "ticket_intents"
        assert hasattr(TicketIntent, "ticket_id")
        assert hasattr(TicketIntent, "intent")
        assert hasattr(TicketIntent, "urgency")
        assert hasattr(TicketIntent, "confidence")
        assert hasattr(TicketIntent, "variant_version")

    def test_classification_corrections_table(self):
        """BL02: classification_corrections"""
        assert ClassificationCorrection.__tablename__ == "classification_corrections"
        assert hasattr(ClassificationCorrection, "original_intent")
        assert hasattr(ClassificationCorrection, "corrected_intent")
        assert hasattr(ClassificationCorrection, "corrected_by")

    def test_ticket_assignments_table(self):
        """BL02: ticket_assignments"""
        assert TicketAssignment.__tablename__ == "ticket_assignments"
        assert hasattr(TicketAssignment, "assignee_type")
        assert hasattr(TicketAssignment, "score")

    def test_assignment_rules_table(self):
        """BL02: assignment_rules"""
        assert AssignmentRule.__tablename__ == "assignment_rules"
        assert hasattr(AssignmentRule, "conditions")
        assert hasattr(AssignmentRule, "action")
        assert hasattr(AssignmentRule, "priority_order")

    def test_bulk_action_logs_table(self):
        """BL02: bulk_action_logs"""
        assert BulkActionLog.__tablename__ == "bulk_action_logs"
        assert hasattr(BulkActionLog, "undo_token")
        assert hasattr(BulkActionLog, "undone")

    def test_bulk_action_failures_table(self):
        """BL02: bulk_action_failures"""
        assert BulkActionFailure.__tablename__ == "bulk_action_failures"
        assert hasattr(BulkActionFailure, "bulk_action_id")
        assert hasattr(BulkActionFailure, "ticket_id")
        assert hasattr(BulkActionFailure, "error_message")

    def test_ticket_merges_table(self):
        """BL02: ticket_merges"""
        assert TicketMerge.__tablename__ == "ticket_merges"
        assert hasattr(TicketMerge, "primary_ticket_id")
        assert hasattr(TicketMerge, "merged_ticket_ids")
        assert hasattr(TicketMerge, "undo_token")

    def test_customer_channels_table(self):
        """BL02: customer_channels"""
        assert CustomerChannel.__tablename__ == "customer_channels"
        assert hasattr(CustomerChannel, "customer_id")
        assert hasattr(CustomerChannel, "channel_type")
        assert hasattr(CustomerChannel, "external_id")
        assert hasattr(CustomerChannel, "is_verified")

    def test_channel_configs_table(self):
        """BL02: channel_configs"""
        assert ChannelConfig.__tablename__ == "channel_configs"
        assert hasattr(ChannelConfig, "channel_type")
        assert hasattr(ChannelConfig, "config_json")
        assert hasattr(ChannelConfig, "auto_create_ticket")
        assert hasattr(ChannelConfig, "allowed_file_types")
        assert hasattr(ChannelConfig, "max_file_size")

    def test_identity_match_logs_table(self):
        """BL02: identity_match_logs"""
        assert IdentityMatchLog.__tablename__ == "identity_match_logs"
        assert hasattr(IdentityMatchLog, "input_email")
        assert hasattr(IdentityMatchLog, "input_phone")
        assert hasattr(IdentityMatchLog, "match_method")
        assert hasattr(IdentityMatchLog, "confidence_score")
        assert hasattr(IdentityMatchLog, "action_taken")

    def test_customer_merge_audits_table(self):
        """BL02: customer_merge_audits"""
        assert CustomerMergeAudit.__tablename__ == "customer_merge_audits"
        assert hasattr(CustomerMergeAudit, "primary_customer_id")
        assert hasattr(CustomerMergeAudit, "merged_customer_ids")
        assert hasattr(CustomerMergeAudit, "action_type")
        assert hasattr(CustomerMergeAudit, "merged_by")


# ═══════════════════════════════════════════════════════════════════
# Bonus Models (MF support)
# ═══════════════════════════════════════════════════════════════════


class TestBonusModels:
    """Verify bonus models for MF04, MF05, MF06, MF13."""

    def test_ticket_status_changes_table(self):
        """MF04: Activity log."""
        assert TicketStatusChange.__tablename__ == "ticket_status_changes"
        assert hasattr(TicketStatusChange, "from_status")
        assert hasattr(TicketStatusChange, "to_status")
        assert hasattr(TicketStatusChange, "changed_by")

    def test_sla_policies_table(self):
        """MF06: SLA policies."""
        assert SLAPolicy.__tablename__ == "sla_policies"
        assert hasattr(SLAPolicy, "plan_tier")
        assert hasattr(SLAPolicy, "priority")
        assert hasattr(SLAPolicy, "first_response_minutes")
        assert hasattr(SLAPolicy, "resolution_minutes")

    def test_sla_timers_table(self):
        """MF06: SLA timers."""
        assert SLATimer.__tablename__ == "sla_timers"
        assert hasattr(SLATimer, "ticket_id")
        assert hasattr(SLATimer, "is_breached")
        assert hasattr(SLATimer, "breached_at")

    def test_notification_templates_table(self):
        """MF05: Notification templates."""
        assert NotificationTemplate.__tablename__ == "notification_templates"
        assert hasattr(NotificationTemplate, "event_type")
        assert hasattr(NotificationTemplate, "channel")
        assert hasattr(NotificationTemplate, "subject_template")
        assert hasattr(NotificationTemplate, "body_template")

    def test_ticket_feedbacks_table(self):
        """MF13: CSAT feedback."""
        assert TicketFeedback.__tablename__ == "ticket_feedbacks"
        assert hasattr(TicketFeedback, "rating")
        assert hasattr(TicketFeedback, "feedback_source")


# ═══════════════════════════════════════════════════════════════════
# BC-001: Every table has company_id (except Channel)
# ═══════════════════════════════════════════════════════════════════


class TestBC001CompanyID:
    """BC-001: Every table has company_id except Channel."""

    # Tables that SHOULD have company_id
    @pytest.mark.parametrize("model", [
        Ticket, TicketMessage, TicketAttachment, TicketInternalNote,
        Customer, TicketStatusChange, SLAPolicy, SLATimer,
        TicketAssignment, BulkActionLog, TicketMerge,
        NotificationTemplate, TicketFeedback, CustomerChannel,
        IdentityMatchLog, TicketIntent, ClassificationCorrection,
        AssignmentRule, BulkActionFailure, ChannelConfig,
        CustomerMergeAudit,
    ])
    def test_has_company_id(self, model):
        col = model.__table__.c.get("company_id")
        assert col is not None, f"{model.__tablename__} missing company_id"

    # Channel should NOT have company_id
    def test_channel_no_company_id(self):
        col = Channel.__table__.c.get("company_id")
        assert col is None, "Channel should not have company_id"


# ═══════════════════════════════════════════════════════════════════
# BL04: No Float on money columns
# ═══════════════════════════════════════════════════════════════════


class TestBL04NoFloatOnMoney:
    """BL04: Ticket models should not use Float for any numeric field."""

    @pytest.mark.parametrize("model", [
        Ticket, TicketMessage, TicketAttachment, TicketInternalNote,
        TicketStatusChange, SLAPolicy, SLATimer,
        TicketAssignment, BulkActionLog, TicketMerge,
        NotificationTemplate, TicketFeedback, CustomerChannel,
        IdentityMatchLog, TicketIntent, ClassificationCorrection,
        AssignmentRule, BulkActionFailure, ChannelConfig,
        CustomerMergeAudit,
    ])
    def test_no_float_columns(self, model):
        """None of the ticket-related models should use Float type."""
        from sqlalchemy import Float as SAType
        float_cols = [
            c.name for c in model.__table__.columns
            if isinstance(c.type, SAType)
        ]
        assert float_cols == [], (
            f"{model.__tablename__} has Float columns: {float_cols}"
        )

    def test_sla_policy_uses_integer_for_minutes(self):
        """SLA minutes should be Integer, not Float."""
        from sqlalchemy import Integer as SAType
        col = SLAPolicy.__table__.c.get("first_response_minutes")
        assert isinstance(col.type, SAType)

    def test_ticket_intent_uses_numeric_for_confidence(self):
        """Confidence scores should use Numeric, not Float."""
        from sqlalchemy import Numeric as SAType
        col = TicketIntent.__table__.c.get("confidence")
        assert isinstance(col.type, SAType)
