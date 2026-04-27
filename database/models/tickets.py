"""
Ticket Models: tickets, ticket_messages, ticket_attachments,
ticket_internal_notes, customers, channels, and Week 4 support models.

Day 24 (Week 4 Day 1): Full ticket system model rewrite.
  - BL01: Session→Ticket, Interaction→TicketMessage
  - MF01: TicketPriority enum (critical/high/medium/low)
  - MF02: TicketCategory enum (tech_support/billing/feature_request/bug_report/general/complaint)
  - MF03: Tags column (JSON array stored as text)
  - BL02: 10 new model classes for SLA, assignment, bulk ops, merge, notifications, feedback,
          customer channels, identity matching, and status change tracking
  - BL04: No Float on money (verified: billing uses Numeric(10,2))

BC-001: Every table has company_id (except channels).
BC-002: Money fields use DECIMAL/Numeric, never Float.
"""

import enum
from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ────────────────────────────────────────────────────────


class TicketStatus(str, enum.Enum):
    """Full lifecycle of a ticket."""
    open = "open"
    assigned = "assigned"
    in_progress = "in_progress"
    awaiting_client = "awaiting_client"
    awaiting_human = "awaiting_human"
    resolved = "resolved"
    reopened = "reopened"
    closed = "closed"
    frozen = "frozen"
    queued = "queued"
    stale = "stale"


class TicketPriority(str, enum.Enum):
    """Priority levels for tickets."""
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TicketCategory(str, enum.Enum):
    """Classification categories for tickets."""
    tech_support = "tech_support"
    billing = "billing"
    feature_request = "feature_request"
    bug_report = "bug_report"
    general = "general"
    complaint = "complaint"


# ── Core Models ──────────────────────────────────────────────────


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    external_id = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    name = Column(String(255))
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(50), nullable=False, unique=True)
    # email, chat, sms, voice, social
    channel_type = Column(String(50), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class Ticket(Base):
    """Primary ticket model (renamed from Session).

    Tracks the full lifecycle of a customer support ticket with SLA,
    priority, classification, assignment, and status information.
    """
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    customer_id = Column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL")
    )
    channel = Column(String(50), nullable=False)
    status = Column(
        String(50), default=TicketStatus.open.value, nullable=False,
    )
    subject = Column(String(255))
    priority = Column(
        String(20),
        server_default=TicketPriority.medium.value,
        nullable=False,
    )
    category = Column(String(50), nullable=True)
    tags = Column(Text, default="[]")
    agent_id = Column(String(36), ForeignKey("agents.id"))
    assigned_to = Column(String(36), ForeignKey("users.id"))
    classification_intent = Column(String(100))
    classification_type = Column(String(50))
    metadata_json = Column(Text, default="{}")

    # PS04: reopen tracking
    reopen_count = Column(Integer, default=0, nullable=False)
    # PS07: frozen when account suspended
    frozen = Column(Boolean, default=False, nullable=False)
    # PS19: cross-variant parent tickets
    parent_ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # PS05: duplicate linking
    duplicate_of_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # MF21: spam flag
    is_spam = Column(Boolean, default=False, nullable=False)
    # PS02: AI can't solve
    awaiting_human = Column(Boolean, default=False, nullable=False)
    # PS08: awaiting client action
    awaiting_client = Column(Boolean, default=False, nullable=False)
    # PS27: escalation level (L1=1, L2=2, L3=3)
    escalation_level = Column(Integer, default=1, nullable=False)
    # PS11: SLA breach tracking
    sla_breached = Column(Boolean, default=False, nullable=False)
    # PS14: plan tier snapshot at creation for grandfathering
    plan_snapshot = Column(Text, default="{}")
    # PS25: which variant version handled this ticket
    variant_version = Column(String(100))
    # PS17: SLA first response tracking
    first_response_at = Column(DateTime)
    # SLA resolution target
    resolution_target_at = Column(DateTime)
    # PS23: client timezone for SLA
    client_timezone = Column(String(50))

    # ── Shadow Mode Fields (Day 3 additions) ─────────────────────
    # none, pending_approval, approved, rejected, auto_approved, undone
    shadow_status = Column(String(20), default="none", nullable=False)
    # Risk score 0.0-1.0 computed by Jarvis
    risk_score = Column(Numeric(5, 4), nullable=True)
    # User who approved (if applicable)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    # Link to shadow_log entry
    shadow_log_id = Column(
        String(36), ForeignKey("shadow_log.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())
    closed_at = Column(DateTime)

    # ── Optimistic Locking (Bug Fix Day 4) ─────────────────────────
    # Incremented on every update to detect race conditions.
    # Read current version, modify row, UPDATE ... WHERE version = read_version.
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    messages = relationship(
        "TicketMessage", back_populates="ticket",
        cascade="all, delete-orphan",
    )


class TicketMessage(Base):
    """Individual messages within a ticket (renamed from Interaction).

    Each message can be from customer, agent, system, or AI.
    """
    __tablename__ = "ticket_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # customer, agent, system, ai
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    channel = Column(String(50), nullable=False)
    metadata_json = Column(Text, default="{}")

    # Distinguish internal notes from customer-visible messages
    is_internal = Column(Boolean, default=False, nullable=False)
    # BL07/PS29: PII redacted messages
    is_redacted = Column(Boolean, default=False, nullable=False)
    # F-049: AI confidence on this response
    ai_confidence = Column(Numeric(5, 2), nullable=True)
    # PS25: which AI variant generated this
    variant_version = Column(String(100))
    # F-049: intent classification per message
    classification = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    ticket = relationship("Ticket", back_populates="messages")


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    uploaded_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class TicketInternalNote(Base):
    __tablename__ = "ticket_internal_notes"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    author_id = Column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    content = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Week 4 Support Models ────────────────────────────────────────


class TicketStatusChange(Base):
    """Activity log for every status change on a ticket (MF04 support)."""
    __tablename__ = "ticket_status_changes"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    from_status = Column(String(50))
    to_status = Column(String(50), nullable=False)
    changed_by = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    reason = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class SLAPolicy(Base):
    """SLA policies per plan × priority (MF06 support)."""
    __tablename__ = "sla_policies"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # starter, growth, high
    plan_tier = Column(String(50), nullable=False)
    # critical, high, medium, low
    priority = Column(String(20), nullable=False)
    # SLA targets in minutes
    first_response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)
    update_frequency_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class SLATimer(Base):
    """Per-ticket SLA tracking."""
    __tablename__ = "sla_timers"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    policy_id = Column(
        String(36), ForeignKey("sla_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    first_response_at = Column(DateTime)
    resolved_at = Column(DateTime)
    breached_at = Column(DateTime)
    is_breached = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class TicketAssignment(Base):
    """Track assignment history (F-050 support)."""
    __tablename__ = "ticket_assignments"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # ai, human, system
    assignee_type = Column(String(50), nullable=False)
    assignee_id = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # AI scoring for AI assignments
    score = Column(Numeric(5, 2), nullable=True)
    reason = Column(Text)
    assigned_at = Column(DateTime, default=lambda: datetime.utcnow())


class BulkActionLog(Base):
    """Track bulk operations (F-051 support)."""
    __tablename__ = "bulk_action_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # status_change, reassign, tag, merge, close
    action_type = Column(String(50), nullable=False)
    # JSON array of ticket IDs
    ticket_ids = Column(Text, nullable=False)
    performed_by = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    result_summary = Column(Text)
    # Unique token for undo capability
    undo_token = Column(String(255), unique=True, nullable=True)
    undone = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class TicketMerge(Base):
    """Track merged tickets (F-051 support)."""
    __tablename__ = "ticket_merges"

    id = Column(String(36), primary_key=True, default=_uuid)
    primary_ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # JSON array of merged ticket IDs
    merged_ticket_ids = Column(Text, nullable=False)
    merged_by = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    reason = Column(Text)
    undo_token = Column(String(255), unique=True, nullable=True)
    undone = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class NotificationTemplate(Base):
    """Email/notification templates (MF05 support)."""
    __tablename__ = "notification_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # ticket_created, ticket_updated, ticket_assigned, ticket_resolved,
    # ticket_closed, ticket_reopened, sla_warning, sla_breached
    event_type = Column(String(50), nullable=False)
    # email, in_app, push
    channel = Column(String(50), nullable=False)
    name = Column(String(100))  # Human-readable template name
    description = Column(Text)  # Template description
    version = Column(Integer, default=1)  # Template version for versioning
    subject_template = Column(Text)
    body_template = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class TicketFeedback(Base):
    """CSAT ratings (MF13 support)."""
    __tablename__ = "ticket_feedbacks"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    # email, in_app
    feedback_source = Column(String(50))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class CustomerChannel(Base):
    """Link customers to channels (F-052, F-070 support)."""
    __tablename__ = "customer_channels"

    id = Column(String(36), primary_key=True, default=_uuid)
    customer_id = Column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # email, chat, sms, voice, social
    channel_type = Column(String(50), nullable=False)
    # e.g., email address, phone number, social handle
    external_id = Column(String(255))
    is_verified = Column(Boolean, default=False, nullable=False)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class IdentityMatchLog(Base):
    """Track identity resolution attempts (F-070 support)."""
    __tablename__ = "identity_match_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    input_email = Column(String(255))
    input_phone = Column(String(50))
    matched_customer_id = Column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    # email, phone, social_id, device
    match_method = Column(String(50))
    confidence_score = Column(Numeric(5, 2))
    # matched, created, flagged
    action_taken = Column(String(50))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Remaining BL02 Tables ────────────────────────────────────────


class TicketIntent(Base):
    """AI classification results for tickets (F-049 support)."""
    __tablename__ = "ticket_intents"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # refund, technical, billing, complaint, feature_request, general
    intent = Column(String(50), nullable=False)
    # urgent, routine, informational
    urgency = Column(String(50))
    # AI model confidence 0.0-1.0
    confidence = Column(Numeric(5, 4), nullable=False)
    # Which AI variant produced this classification
    variant_version = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class ClassificationCorrection(Base):
    """Human corrections to AI classifications (F-049 feedback loop)."""
    __tablename__ = "classification_corrections"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    original_intent = Column(String(50), nullable=False)
    corrected_intent = Column(String(50), nullable=False)
    original_urgency = Column(String(50))
    corrected_urgency = Column(String(50))
    corrected_by = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    reason = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class AssignmentRule(Base):
    """Custom assignment rules per company (F-050 support)."""
    __tablename__ = "assignment_rules"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    # Condition: JSON with category, priority, channel filters
    conditions = Column(Text, default="{}", nullable=False)
    # Action: JSON with assignee_id, assignee_type, routing
    action = Column(Text, default="{}", nullable=False)
    priority_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class BulkActionFailure(Base):
    """Individual failures within a bulk action (F-051 support)."""
    __tablename__ = "bulk_action_failures"

    id = Column(String(36), primary_key=True, default=_uuid)
    bulk_action_id = Column(
        String(36), ForeignKey("bulk_action_logs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    ticket_id = Column(String(36), nullable=False)
    error_message = Column(Text, nullable=False)
    # status conflict, permission denied, not found, etc.
    failure_reason = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class ChannelConfig(Base):
    """Per-company channel configuration (F-052 support)."""
    __tablename__ = "channel_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    channel_type = Column(String(50), nullable=False)
    # email, chat, sms, voice, social
    is_enabled = Column(Boolean, default=True, nullable=False)
    # Channel-specific settings as JSON (API keys, webhooks, etc.)
    config_json = Column(Text, default="{}")
    # Auto-create ticket on inbound
    auto_create_ticket = Column(Boolean, default=True, nullable=False)
    # Character limit for this channel
    char_limit = Column(Integer, nullable=True)
    # Supported file types for this channel (JSON array)
    allowed_file_types = Column(Text, default="[]")
    # Max file size in bytes
    max_file_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class CustomerMergeAudit(Base):
    """Audit trail for customer identity merges (F-070 support)."""
    __tablename__ = "customer_merge_audits"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # The customer that survives the merge
    primary_customer_id = Column(
        String(36), ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # JSON array of absorbed customer IDs
    merged_customer_ids = Column(Text, nullable=False)
    merged_by = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    # merge_reason, unmerge
    action_type = Column(String(50), nullable=False)
    reason = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Ticket Triggers (MF08: Automated trigger rules) ────────────────

class TicketTrigger(Base):
    __tablename__ = "ticket_triggers"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text)
    # JSON: {"events": ["ticket_created", "ticket_updated"], "conditions": [...]}
    conditions = Column(Text, default="{}")
    # JSON: {"action": "change_status", "params": {"status": "in_progress"}}
    action = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    priority_order = Column(Integer, default=0)
    execution_count = Column(Integer, default=0)
    last_executed_at = Column(DateTime)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Custom Fields (MF09: Custom ticket fields) ──────────────────────

class CustomField(Base):
    __tablename__ = "custom_fields"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(255), nullable=False)
    field_key = Column(String(100), nullable=False)  # Used in metadata_json
    field_type = Column(String(50), nullable=False)  # text, number, dropdown, multi_select, date, checkbox
    # JSON: {"options": ["option1", "option2"], "required": true, "default": "..."}
    config = Column(Text, default="{}")
    # Which categories this field applies to (empty = all)
    applicable_categories = Column(Text, default="[]")
    is_required = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint(
            "company_id", "field_key",
            name="uq_custom_fields_company_key",
        ),
    )


# ── Ticket Collision (MF11: Concurrent editing detection) ───────────

class TicketCollision(Base):
    __tablename__ = "ticket_collisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(100))  # Browser session identifier
    started_at = Column(DateTime, default=lambda: datetime.utcnow())
    last_activity_at = Column(DateTime, default=lambda: datetime.utcnow())
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Backward Compatibility Aliases ───────────────────────────────
# Used by existing tests/code that reference the old class names.
# DO NOT remove until all references are migrated.

Session = Ticket  # noqa: F811
Interaction = TicketMessage  # noqa: F811
