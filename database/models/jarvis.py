"""
Jarvis Models: onboarding chat system.

Tables:
- JarvisSession: Per-user chat session with context_json memory,
  message limits, pack type, payment status.
- JarvisMessage: All chat messages (user, jarvis, system) with
  rich message types (text, cards, tickets, etc.).
- JarvisKnowledgeUsed: Tracks which knowledge base files were
  used per AI response (analytics + context).
- JarvisActionTicket: Every user action as a visible ticket in
  the chat stream with status tracking and result data.

Based on: JARVIS_SPECIFICATION.md v3.0 / JARVIS_ROADMAP.md v4.0
"""

from datetime import datetime

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
    "'limit_reached','pack_expired','error'"
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
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

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
    # recharge_cta, limit_reached, pack_expired, error
    message_type = Column(String(25), nullable=False, default="text")
    # Extra data for card-type messages (variant details, payment info, etc.)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

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
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

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
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())
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
