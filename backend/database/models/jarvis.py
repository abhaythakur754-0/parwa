"""
Jarvis Models: onboarding + customer care chat system.

Tables:
- JarvisSession: Per-user chat session with context_json memory,
  message limits, pack type, payment status.
  Supports both 'onboarding' and 'customer_care' session types.
- JarvisMessage: All chat messages (user, jarvis, system) with
  rich message types (text, cards, tickets, variant pipeline,
  proactive alerts, command responses, etc.).
- JarvisKnowledgeUsed: Tracks which knowledge base files were
  used per AI response (analytics + context).
- JarvisActionTicket: Every user action as a visible ticket in
  the chat stream with status tracking and result data.

Phase 1.3 additions:
- Extended _MESSAGE_TYPES to include CC mode types:
  variant_pipeline, ai_generated, direct_ai, proactive_alert,
  command_response
- Added awareness_snapshots relationship to JarvisSession
  (for jarvis_awareness_snapshots table in jarvis_cc.py)
- Added proactive_alerts relationship to JarvisSession

Based on: JARVIS_SPECIFICATION.md v3.0 / JARVIS_ROADMAP.md v4.0
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Integer, Numeric,
    String, Text, ForeignKey,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (used by CHECK constraints) ────────────

_SESSION_TYPES = "'onboarding','customer_care'"
_PACK_TYPES = "'free','demo'"
_PAYMENT_STATUSES = "'none','pending','completed','failed'"
_MESSAGE_ROLES = "'user','jarvis','system'"
_MESSAGE_TYPES = (
    "'text','bill_summary','payment_card','otp_card',"
    "'handoff_card','demo_call_card','action_ticket',"
    "'call_summary','recharge_cta',"
    "'limit_reached','pack_expired','error',"
    # Phase 1.3: Customer Care message types
    "'variant_pipeline','ai_generated','direct_ai',"
    "'proactive_alert','command_response'"
)
_TICKET_TYPES = (
    "'otp_verification','otp_verified',"
    "'payment_demo_pack','payment_variant','payment_variant_completed',"
    "'demo_call','demo_call_completed',"
    "'roi_import','handoff'"
)
_TICKET_STATUSES = "'pending','in_progress','completed','failed'"


# ── Jarvis Sessions ─────────────────────────────────────────────

class JarvisSession(Base):
    __tablename__ = "jarvis_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    # 'onboarding' before purchase, 'customer_care' after handoff
    type = Column(String(20), nullable=False, default="onboarding")
    # Full journey memory stored as JSON string.
    # Keys: pages_visited, industry, selected_variants, roi_result,
    #   demo_topics, concerns_raised, business_email, email_verified,
    #   referral_source, entry_source, detected_stage
    context_json = Column(Text, default="{}")
    # Message limits
    message_count_today = Column(Integer, nullable=False, default=0)
    last_message_date = Column(DateTime, nullable=True)
    total_message_count = Column(Integer, nullable=False, default=0)
    # Monetization: 'free' (20/day) or 'demo' (500 msgs + 3-min call)
    pack_type = Column(String(10), nullable=False, default="free")
    pack_expiry = Column(DateTime, nullable=True)
    demo_call_used = Column(Boolean, nullable=False, default=False)
    # Session state
    is_active = Column(Boolean, nullable=False, default=True)
    # Payment: 'none' | 'pending' | 'completed' | 'failed'
    payment_status = Column(String(15), nullable=False, default="none")
    handoff_completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # ── Relationships ──
    messages = relationship(
        "JarvisMessage", back_populates="session",
        cascade="all, delete-orphan",
        order_by="JarvisMessage.created_at",
    )
    action_tickets = relationship(
        "JarvisActionTicket", back_populates="session",
        cascade="all, delete-orphan",
    )
    # Phase 1.3: Awareness snapshots for CC sessions (Phase 2 writes here)
    awareness_snapshots = relationship(
        "JarvisAwarenessSnapshot", back_populates="session",
        cascade="all, delete-orphan",
        order_by="JarvisAwarenessSnapshot.created_at.desc()",
    )
    # Phase 1.3: Proactive alerts for CC sessions
    proactive_alerts = relationship(
        "JarvisProactiveAlert", back_populates="session",
        cascade="all, delete-orphan",
        order_by="JarvisProactiveAlert.created_at.desc()",
    )
    user = relationship("User")
    company = relationship("Company")

    __table_args__ = (
        CheckConstraint(
            f"type IN ({_SESSION_TYPES})",
            name="ck_jarvis_session_type",
        ),
        CheckConstraint(
            f"pack_type IN ({_PACK_TYPES})",
            name="ck_jarvis_session_pack_type",
        ),
        CheckConstraint(
            f"payment_status IN ({_PAYMENT_STATUSES})",
            name="ck_jarvis_session_payment_status",
        ),
        CheckConstraint(
            "message_count_today >= 0",
            name="ck_jarvis_session_msg_count_nonneg",
        ),
        CheckConstraint(
            "total_message_count >= 0",
            name="ck_jarvis_session_total_msg_nonneg",
        ),
        {"schema": None},
    )


# ── Jarvis Messages ────────────────────────────────────────────

class JarvisMessage(Base):
    __tablename__ = "jarvis_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # 'user' | 'jarvis' | 'system'
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    # Rich message types: text, bill_summary, payment_card, otp_card,
    # handoff_card, demo_call_card, action_ticket, call_summary,
    # recharge_cta, limit_reached, pack_expired, error,
    # variant_pipeline, ai_generated, direct_ai,
    # proactive_alert, command_response
    message_type = Column(String(25), nullable=False, default="text")
    # Extra data for card-type messages (variant details, payment info, etc.)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──
    session = relationship("JarvisSession", back_populates="messages")
    knowledge_used = relationship(
        "JarvisKnowledgeUsed", back_populates="message",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            f"role IN ({_MESSAGE_ROLES})",
            name="ck_jarvis_message_role",
        ),
        CheckConstraint(
            f"message_type IN ({_MESSAGE_TYPES})",
            name="ck_jarvis_message_type",
        ),
        {"schema": None},
    )


# ── Jarvis Knowledge Used ─────────────────────────────────────

class JarvisKnowledgeUsed(Base):
    __tablename__ = "jarvis_knowledge_used"

    id = Column(String(36), primary_key=True, default=_uuid)
    message_id = Column(
        String(36),
        ForeignKey("jarvis_messages.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # e.g. '01_pricing_tiers.json', '07_objection_handling.json'
    knowledge_file = Column(String(100), nullable=False)
    relevance_score = Column(Numeric(5, 2), default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──
    message = relationship("JarvisMessage", back_populates="knowledge_used")

    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100",
            name="ck_jarvis_ku_relevance_range",
        ),
        {"schema": None},
    )


# ── Jarvis Action Tickets ─────────────────────────────────────

class JarvisActionTicket(Base):
    __tablename__ = "jarvis_action_tickets"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("jarvis_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Links to the in-chat message that rendered this ticket card
    message_id = Column(
        String(36),
        ForeignKey("jarvis_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Ticket types: otp_verification, otp_verified, payment_demo_pack,
    # payment_variant, payment_variant_completed, demo_call,
    # demo_call_completed, roi_import, handoff
    ticket_type = Column(String(30), nullable=False)
    # 'pending' | 'in_progress' | 'completed' | 'failed'
    status = Column(String(15), nullable=False, default="pending")
    # Outcome data: call duration, summary, payment ID, error, etc.
    result_json = Column(Text, default="{}")
    # Extra data: phone, email, amounts, variant_ids, etc.
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    # ── Relationships ──
    session = relationship("JarvisSession", back_populates="action_tickets")
    message = relationship("JarvisMessage")

    __table_args__ = (
        CheckConstraint(
            f"ticket_type IN ({_TICKET_TYPES})",
            name="ck_jarvis_ticket_type",
        ),
        CheckConstraint(
            f"status IN ({_TICKET_STATUSES})",
            name="ck_jarvis_ticket_status",
        ),
        {"schema": None},
    )


# ── DB-Backed Jarvis Message Queue ─────────────────────────────────
# Stores incoming Jarvis chat messages for processing by background workers.
# Same pattern as ticket pipeline — survives Render restarts, handles
# unlimited concurrent users (INSERT is instant, workers poll at their own pace).


class JarvisMessageQueue(Base):
    """DB-backed queue for Jarvis chat messages.

    Why this exists:
      The in-memory semaphore approach froze when 3+ users chatted
      concurrently because sync DB calls in send_message() blocked the
      FastAPI event loop.

      This DB-backed queue solves it by:
      1. API endpoint INSERTs message (instant, ~5ms, no blocking)
      2. Returns queue position + message_id immediately
      3. Background workers (separate threads) poll the queue
      4. Workers process 2 at a time (configurable)
      5. Worker calls send_message() + saves response
      6. Client polls GET /jarvis/queue/{message_id} for the response

    This is the SAME architecture as the ticket pipeline
    (MAX_CONCURRENT_PIPELINES=10 workers polling DB), which handles
    10 concurrent tickets without freezing.

    User vision (2026-08-12): 'it can handle unlimited number of request
    as its storing in the database'
    """
    __tablename__ = "jarvis_message_queue"

    id = Column(String(36), primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    company_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36), nullable=False, index=True)

    # The user's message
    message_content = Column(Text, nullable=False)

    # Queue status
    # pending:     in queue, waiting for worker
    # processing:   worker is handling it
    # completed:    response is ready (in response_content)
    # failed:      error occurred (in error_message)
    status = Column(String(20), nullable=False, default="pending", index=True)

    # Queue ordering
    queue_position = Column(Integer, nullable=True)  # 1 = next to process
    queued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Response (filled when status='completed')
    response_content = Column(Text, nullable=True)
    response_metadata = Column(Text, nullable=True)  # JSON: pipeline info, latency, quality
    knowledge_used = Column(Text, nullable=True)  # JSON: list of KB sources

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=1)

    # Worker tracking
    worker_id = Column(String(50), nullable=True)  # which worker processed this

    def __repr__(self):
        return f"<JarvisMessageQueue id={self.id[:8]} status={self.status} user={self.user_id[:8]}>"

    def to_dict(self):
        """Serialize for API response."""
        import json as _json
        return {
            "id": self.id,
            "status": self.status,
            "queue_position": self.queue_position,
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "processing_started_at": self.processing_started_at.isoformat() if self.processing_started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "response": self.response_content if self.status == "completed" else None,
            "metadata": _json.loads(self.response_metadata) if self.response_metadata else None,
            "knowledge_used": _json.loads(self.knowledge_used) if self.knowledge_used else None,
            "error": self.error_message,
            "worker_id": self.worker_id,
        }
