"""
Remaining Tables: response_templates, email_logs, rate_limit_counters,
feature_flags, classification_log, guardrails_audit_log,
guardrails_blocked_queue, ai_response_feedback, confidence_thresholds,
human_corrections, approval_batches, notifications, first_victories.

Source: Infrastructure Gap Analysis (DBT-001)
BC-001: Every table has company_id.
BC-002: Money fields use DECIMAL(10,2).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Response Templates (Week 9: F-065 auto-response generation) ────


class ResponseTemplate(Base):
    __tablename__ = "response_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    intent_type = Column(String(100))
    template_text = Column(Text, nullable=False)
    variables = Column(Text, default="[]")  # JSON list of variable names
    language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Email Logs (Week 5/13 email tracking) ──────────────────────────


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient = Column(String(255), nullable=False)
    subject = Column(String(500))
    email_type = Column(
        String(50), nullable=False
    )  # verification, reset, notification, marketing
    provider = Column(String(50), default="brevo")
    provider_message_id = Column(String(255))
    status = Column(
        String(50), default="pending"
    )  # pending, sent, delivered, bounced, failed
    error_message = Column(Text)
    retries = Column(Integer, default=0)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Rate Limit Counters (distributed rate limiting) ────────────────


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Identifier for what's being rate limited (user_id, ip_hash, etc.)
    identifier = Column(String(255), nullable=False)
    # Category of rate limit (api, webhook_email, webhook_chat, etc.)
    category = Column(String(100), nullable=False)
    # Current count in the window
    count = Column(Integer, default=0)
    # Window start timestamp
    window_start = Column(DateTime, nullable=False)
    # Window end timestamp
    window_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        Index(
            "ix_rlc_identifier_category_window",
            "identifier",
            "category",
            "window_start",
        ),
    )


# ── Feature Flags (feature access control) ─────────────────────────


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flag_key = Column(String(100), nullable=False)
    flag_value = Column(Text, default="false")
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    enabled_for_tiers = Column(Text, default="[]")  # JSON list of tiers
    enabled_for_roles = Column(Text, default="[]")  # JSON list of roles
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "flag_key",
            name="uq_feature_flags_company_key",
        ),
    )


# ── Classification Log (Week 8: F-062 AI classification) ──────────


class ClassificationLog(Base):
    __tablename__ = "classification_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    interaction_id = Column(String(36))
    input_text = Column(Text)
    classified_intent = Column(String(100))
    classified_sentiment = Column(String(50))
    confidence_score = Column(Numeric(5, 2))
    model_name = Column(String(100))
    latency_ms = Column(Integer)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Guardrails Audit Log (Week 8: F-057) ──────────────────────────


class GuardrailsAuditLog(Base):
    __tablename__ = "guardrails_audit_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    # audit, policy_violation, escalation, manual_review
    event_type = Column(String(50), nullable=False)
    rule_id = Column(String(36))
    rule_name = Column(String(255))
    input_summary = Column(Text)
    output_summary = Column(Text)
    action_taken = Column(String(100))
    severity = Column(String(20), default="info")
    reviewed_by = Column(String(36), ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Guardrails Blocked Queue (Week 8: F-057, F-058) ───────────────


class GuardrailsBlockedQueue(Base):
    __tablename__ = "guardrails_blocked_queue"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    block_type = Column(String(50), nullable=False)
    original_response = Column(Text)
    block_reason = Column(Text)
    severity = Column(String(20), default="medium")
    status = Column(
        String(50), default="pending_review"
    )  # pending_review, resolved, escalated
    auto_resolved = Column(Boolean, default=False)
    resolved_by = Column(String(36), ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── AI Response Feedback (Week 9: F-065 confidence scoring) ───────


class AIResponseFeedback(Base):
    __tablename__ = "ai_response_feedback"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    interaction_id = Column(String(36))
    feedback_type = Column(
        String(50), nullable=False
    )  # thumbs_up, thumbs_down, correction
    feedback_text = Column(Text)
    ai_response_text = Column(Text)
    confidence_at_time = Column(Numeric(5, 2))
    provided_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Confidence Thresholds (Week 8: F-059) ─────────────────────────


class ConfidenceThreshold(Base):
    __tablename__ = "confidence_thresholds"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent_type = Column(String(100), nullable=False)
    # auto_respond, human_escalate, guardrail_block
    action_type = Column(String(50), nullable=False)
    min_confidence = Column(Numeric(5, 2), nullable=False)
    max_confidence = Column(Numeric(5, 2))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "intent_type",
            "action_type",
            name="uq_conf_thresh_company_intent_action",
        ),
    )


# ── Human Corrections (Week 19: F-101 training data) ───────────────


class HumanCorrection(Base):
    __tablename__ = "human_corrections"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    interaction_id = Column(String(36))
    original_response = Column(Text)
    corrected_response = Column(Text, nullable=False)
    correction_reason = Column(String(255))
    corrected_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("agents.id"))
    used_in_training = Column(Boolean, default=False)
    training_run_id = Column(String(36))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Approval Batches (Week 7: batch approval processing) ──────────


class ApprovalBatch(Base):
    __tablename__ = "approval_batches"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # pending, approved, partially_approved, rejected
    batch_status = Column(String(50), default="pending")
    total_items = Column(Integer, default=0)
    approved_items = Column(Integer, default=0)
    rejected_items = Column(Integer, default=0)
    reviewed_by = Column(String(36), ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Notifications (Week 7+: in-app notifications) ──────────────────


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # Event type: ticket_created, ticket_assigned, sla_warning, etc.
    event_type = Column(String(100))
    # Notification priority: low, medium, high, urgent
    priority = Column(String(20), default="medium")
    title = Column(String(255), nullable=False)
    message = Column(Text)
    # pending, sent, read, failed
    status = Column(String(50), default="pending")
    # JSON list of channels this notification was sent to
    channels = Column(Text, default='["in_app"]')
    # Related ticket if applicable
    ticket_id = Column(String(36), ForeignKey("tickets.id"))
    # User who triggered the notification
    sender_id = Column(String(36), ForeignKey("users.id"))
    # Additional data as JSON
    data_json = Column(Text, default="{}")
    action_url = Column(String(500))
    read_at = Column(DateTime)
    sent_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Notification Preferences (Day 31: MF05) ────────────────────────


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # Event type: ticket_created, ticket_assigned, sla_warning, etc.
    event_type = Column(String(100), nullable=False)
    # Whether notifications are enabled for this event
    enabled = Column(Boolean, default=True)
    # JSON list of channels: ["email", "in_app", "push"]
    channels = Column(Text, default='["in_app"]')
    # Minimum priority threshold: low, medium, high, urgent
    priority_threshold = Column(String(20), default="low")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "user_id",
            "event_type",
            name="uq_notification_prefs_company_user_event",
        ),
    )


# ── Notification Logs (Day 31: MF05) ───────────────────────────────


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    notification_id = Column(String(36), ForeignKey("notifications.id"))
    # Event that triggered notification
    event_type = Column(String(100), nullable=False)
    # Channel used: email, in_app, push
    channel = Column(String(50), nullable=False)
    # Input data for matching
    input_email = Column(String(255))
    input_phone = Column(String(50))
    input_social_id = Column(String(255))
    # Match result
    match_method = Column(String(50))
    confidence_score = Column(Numeric(5, 2))
    # Action taken: matched, created, suggested, none
    action_taken = Column(String(50))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── First Victories (Week 6: customer onboarding milestones) ──────


class FirstVictory(Base):
    __tablename__ = "first_victories"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # first_ticket_resolved, first_agent_created, first_integration_connected,
    # first_knowledge_doc_uploaded, first_api_key_created
    milestone_type = Column(String(100), nullable=False)
    achieved_at = Column(DateTime, default=lambda: datetime.utcnow())
    # Optional related resource ID
    resource_id = Column(String(36))
    resource_type = Column(String(50))
    celebrated = Column(Boolean, default=False)  # UI celebration shown
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "user_id",
            "milestone_type",
            name="uq_first_victories_company_user_milestone",
        ),
    )
