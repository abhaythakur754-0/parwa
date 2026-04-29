"""
Jarvis Production Models - Post-Onboarding AI Control Center

Tables:
- JarvisProductionSession: Active production Jarvis sessions per user
- JarvisActivityEvent: All tracked user/system activities for awareness
- JarvisMemory: Long-term memory and preferences per user
- JarvisDraft: Pending action drafts for review-then-execute
- JarvisAlert: Proactive alerts for important events
- JarvisActionLog: Audit trail of all actions taken by Jarvis

Based on: JARVIS_Production_Documentation.md
"""

from datetime import datetime
import uuid
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Integer, String, 
    Text, ForeignKey, Index, Numeric,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Jarvis Production Session ─────────────────────────────────────

class JarvisProductionSession(Base):
    """Active Production Jarvis session per user.
    
    Created after onboarding completes. Tracks all interactions,
    memory context, and session state.
    """
    __tablename__ = "jarvis_production_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Session state
    is_active = Column(Boolean, nullable=False, default=True)
    # Current conversation context (Redis-like fast access backup)
    context_json = Column(Text, default="{}")
    # Today's task memory (JSON array of activities)
    today_tasks_json = Column(Text, default="[]")
    # Last interaction
    last_interaction_at = Column(DateTime, nullable=True)
    # Variant tier: 'starter', 'growth', 'high'
    variant_tier = Column(String(20), nullable=False, default="starter")
    # Feature flags based on tier
    features_enabled_json = Column(Text, default="{}")
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    user = relationship("User")
    company = relationship("Company")
    activities = relationship(
        "JarvisActivityEvent", back_populates="session",
        cascade="all, delete-orphan",
    )
    memories = relationship(
        "JarvisMemory", back_populates="session",
        cascade="all, delete-orphan",
    )
    drafts = relationship(
        "JarvisDraft", back_populates="session",
        cascade="all, delete-orphan",
    )
    alerts = relationship(
        "JarvisAlert", back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "variant_tier IN ('starter', 'growth', 'high')",
            name="ck_jarvis_prod_tier",
        ),
        Index("ix_jarvis_prod_session_user_company", "user_id", "company_id"),
    )


# ── Jarvis Activity Event (Awareness System) ──────────────────────

class JarvisActivityEvent(Base):
    """Tracks all user and system activities for Jarvis awareness.
    
    This is the core of Jarvis's awareness system. Every click,
    page visit, action, and system event is logged here.
    """
    __tablename__ = "jarvis_activity_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("jarvis_production_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Event classification
    event_type = Column(String(50), nullable=False)  # 'page_visit', 'click', 'action', 'error', etc.
    event_category = Column(String(30), nullable=False)  # 'user', 'system', 'ai', 'integration'
    # Event details
    event_name = Column(String(100), nullable=False)  # 'viewed_approvals', 'paused_ai', etc.
    description = Column(Text, nullable=True)
    # Rich event data
    metadata_json = Column(Text, default="{}")
    # Context: where did this happen?
    page_url = Column(String(500), nullable=True)
    page_name = Column(String(100), nullable=True)
    # Related entities
    related_ticket_id = Column(String(36), nullable=True)
    related_user_id = Column(String(36), nullable=True)
    related_integration = Column(String(50), nullable=True)
    # Timestamp
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), index=True)

    # Relationships
    session = relationship("JarvisProductionSession", back_populates="activities")

    __table_args__ = (
        Index("ix_jarvis_activity_company_time", "company_id", "created_at"),
        Index("ix_jarvis_activity_user_time", "user_id", "created_at"),
        Index("ix_jarvis_activity_type_time", "event_type", "created_at"),
    )


# ── Jarvis Memory (Long-term) ─────────────────────────────────────

class JarvisMemory(Base):
    """Long-term memory storage for Jarvis.
    
    Stores user preferences, patterns, recurring questions,
    and important context that Jarvis should remember.
    """
    __tablename__ = "jarvis_memories"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("jarvis_production_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Memory classification
    category = Column(String(50), nullable=False)  # 'preference', 'pattern', 'history', 'context'
    memory_key = Column(String(100), nullable=False)  # e.g., 'preferred_greeting_style', 'common_tasks'
    # Memory content
    memory_value = Column(Text, nullable=False)  # JSON or text
    # Importance and retention
    importance = Column(Integer, default=5)  # 1-10 scale
    # Memory expiry (for temporary memories)
    expires_at = Column(DateTime, nullable=True)
    # Access tracking
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    session = relationship("JarvisProductionSession", back_populates="memories")

    __table_args__ = (
        CheckConstraint(
            "importance >= 1 AND importance <= 10",
            name="ck_jarvis_memory_importance",
        ),
        Index("ix_jarvis_memory_lookup", "company_id", "user_id", "category", "memory_key"),
    )


# ── Jarvis Draft (Review-Before-Execute) ───────────────────────────

class JarvisDraft(Base):
    """Pending action drafts for review-before-execute workflow.
    
    For bulk actions, financial operations, or high-impact changes,
    Jarvis creates a draft for user approval before execution.
    """
    __tablename__ = "jarvis_drafts"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("jarvis_production_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Draft classification
    draft_type = Column(String(50), nullable=False)  # 'email', 'sms', 'settings', 'bulk_action'
    # Draft content
    subject = Column(String(255), nullable=True)  # For emails
    content_json = Column(Text, nullable=False)  # Main content as JSON
    # Recipients (for communication drafts)
    recipient_count = Column(Integer, default=0)
    recipients_json = Column(Text, default="[]")
    # Status
    status = Column(String(20), nullable=False, default="pending")  # 'pending', 'approved', 'cancelled', 'expired'
    # Execution info
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    execution_result_json = Column(Text, nullable=True)
    # Expiry
    expires_at = Column(DateTime, nullable=True)
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    session = relationship("JarvisProductionSession", back_populates="drafts")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'cancelled', 'expired', 'executing', 'completed', 'failed')",
            name="ck_jarvis_draft_status",
        ),
        Index("ix_jarvis_draft_pending", "company_id", "status"),
    )


# ── Jarvis Alert (Proactive Notifications) ────────────────────────

class JarvisAlert(Base):
    """Proactive alerts from Jarvis for important events.
    
    Jarvis monitors the system and creates alerts when:
    - Approval queue overflows
    - Error rate spikes
    - Integration goes down
    - Ticket limit approaching
    - VIP customer has issue
    - Security anomalies detected
    """
    __tablename__ = "jarvis_alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("jarvis_production_sessions.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # NULL for company-wide alerts
    )
    # Alert classification
    alert_type = Column(String(50), nullable=False)  # 'error_spike', 'integration_down', etc.
    severity = Column(String(20), nullable=False)  # 'low', 'medium', 'high', 'critical'
    # Alert content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    # Suggested action (if any)
    suggested_action_json = Column(Text, nullable=True)
    # Status
    status = Column(String(20), nullable=False, default="active")  # 'active', 'acknowledged', 'dismissed', 'resolved'
    # Delivery tracking
    delivered_via = Column(String(50), nullable=True)  # 'in_app', 'email', 'sms'
    delivered_at = Column(DateTime, nullable=True)
    # Resolution
    acknowledged_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    # Related entity
    related_entity_type = Column(String(50), nullable=True)  # 'ticket', 'integration', 'user'
    related_entity_id = Column(String(36), nullable=True)
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    session = relationship("JarvisProductionSession", back_populates="alerts")

    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_jarvis_alert_severity",
        ),
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'dismissed', 'resolved')",
            name="ck_jarvis_alert_status",
        ),
        Index("ix_jarvis_alert_active", "company_id", "status", "severity"),
    )


# ── Jarvis Action Log (Audit Trail) ────────────────────────────────

class JarvisActionLog(Base):
    """Audit trail of all actions taken by or through Jarvis.
    
    Every action executed through Jarvis is logged here for:
    - Accountability
    - Undo capability
    - Analytics and patterns
    """
    __tablename__ = "jarvis_action_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("jarvis_production_sessions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False, index=True,
    )
    # Action details
    action_type = Column(String(50), nullable=False)  # 'send_sms', 'pause_ai', 'update_settings'
    action_category = Column(String(30), nullable=False)  # 'communication', 'ai_control', 'settings'
    # Execution mode
    execution_mode = Column(String(20), nullable=False)  # 'direct', 'draft_approved'
    # Input and output
    input_json = Column(Text, nullable=True)  # Parameters provided
    output_json = Column(Text, nullable=True)  # Result of action
    # Status
    status = Column(String(20), nullable=False, default="pending")  # 'pending', 'success', 'failed', 'undone'
    error_message = Column(Text, nullable=True)
    # Undo tracking
    can_undo = Column(Boolean, default=False)
    undone_at = Column(DateTime, nullable=True)
    undone_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    # Related draft (if applicable)
    draft_id = Column(String(36), ForeignKey("jarvis_drafts.id"), nullable=True)
    # Related entities
    related_ticket_id = Column(String(36), nullable=True)
    related_integration = Column(String(50), nullable=True)
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), index=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'success', 'failed', 'undone')",
            name="ck_jarvis_action_status",
        ),
        CheckConstraint(
            "execution_mode IN ('direct', 'draft_approved', 'auto')",
            name="ck_jarvis_action_mode",
        ),
        Index("ix_jarvis_action_company_time", "company_id", "created_at"),
        Index("ix_jarvis_action_user_time", "user_id", "created_at"),
    )
