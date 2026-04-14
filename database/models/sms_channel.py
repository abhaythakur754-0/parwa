"""
SMS Channel Models — Week 13 Day 5 (F-123: SMS Channel)

Tables:
- SMSMessage: Inbound/outbound SMS messages with Twilio SID
  tracking, delivery status, and ticket association.
- SMSConversation: Maps phone number pairs to tickets for
  threading (same participants = same conversation).
- SMSChannelConfig: Per-company Twilio credentials and
  SMS settings (opt-out keywords, auto-reply, char limit).

Building Codes:
- BC-001: Every table has company_id
- BC-003: Idempotent webhook processing (Twilio MessageSid)
- BC-006: Rate limiting (5 msgs/number/hour outbound)
- BC-010: TCPA compliance (opt-out/STOP keywords)
- BC-011: Twilio credentials encrypted at rest
- BC-012: Structured error responses
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (CHECK constraints) ────────────────

_SMS_DIRECTIONS = "'inbound','outbound'"
_SMS_STATUSES = (
    "'queued','sent','delivered','undelivered',"
    "'failed','rejected','expired','receiving'"
)
_SMS_ROLES = "'agent','bot','system','visitor'"


class SMSMessage(Base):
    """SMS message tracking record.

    One row per SMS message (inbound or outbound) with Twilio
    SID correlation for delivery tracking and audit trail.

    BC-001: Scoped to company_id.
    BC-003: Twilio MessageSid used for idempotency.
    BC-010: TCPA opt-out tracking.
    """

    __tablename__ = "sms_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Conversation threading
    conversation_id = Column(
        String(36),
        ForeignKey("sms_conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Direction: inbound (from customer) or outbound (to customer)
    direction = Column(String(10), nullable=False)

    # Phone numbers in E.164 format
    from_number = Column(String(30), nullable=False, index=True)
    to_number = Column(String(30), nullable=False)

    # Message content
    body = Column(Text, nullable=False)
    num_segments = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=True)

    # Twilio tracking
    twilio_message_sid = Column(
        String(64), nullable=True, unique=True, index=True,
    )
    twilio_account_sid = Column(String(64), nullable=True)
    twilio_status = Column(
        String(20), nullable=False, default="queued",
    )
    twilio_error_code = Column(Integer, nullable=True)
    twilio_error_message = Column(Text, nullable=True)

    # Ticket association
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ticket_message_id = Column(String(36), nullable=True)

    # Sender info
    sender_id = Column(String(36), nullable=True)
    sender_role = Column(String(10), nullable=False, default="agent")

    # AI attribution
    is_ai_generated = Column(Boolean, nullable=False, default=False)
    ai_confidence = Column(Integer, nullable=True)
    ai_model = Column(String(100), nullable=True)

    # TCPA compliance (BC-010)
    is_opt_out = Column(Boolean, nullable=False, default=False)
    opt_out_keyword = Column(String(20), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # Relationships
    conversation = relationship(
        "SMSConversation", back_populates="messages",
    )
    ticket = relationship("Ticket", foreign_keys=[ticket_id])

    __table_args__ = (
        CheckConstraint(
            f"direction IN ({_SMS_DIRECTIONS})",
            name="ck_sms_msg_direction",
        ),
        CheckConstraint(
            f"twilio_status IN ({_SMS_STATUSES})",
            name="ck_sms_msg_status",
        ),
        CheckConstraint(
            f"sender_role IN ({_SMS_ROLES})",
            name="ck_sms_msg_role",
        ),
        CheckConstraint(
            "char_count IS NULL OR char_count >= 0",
            name="ck_sms_msg_char_count",
        ),
        CheckConstraint(
            "num_segments IS NULL OR num_segments >= 0",
            name="ck_sms_msg_segments",
        ),
        CheckConstraint(
            "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 100)",
            name="ck_sms_msg_ai_confidence_range",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_sms_msg_retry_count",
        ),
        Index(
            "ix_sms_company_from_to",
            "company_id", "from_number", "to_number",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize SMS message for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "conversation_id": self.conversation_id,
            "direction": self.direction,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "body": self.body,
            "num_segments": self.num_segments,
            "char_count": self.char_count,
            "twilio_message_sid": self.twilio_message_sid,
            "twilio_status": self.twilio_status,
            "ticket_id": self.ticket_id,
            "ticket_message_id": self.ticket_message_id,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role,
            "is_ai_generated": self.is_ai_generated,
            "ai_confidence": self.ai_confidence,
            "ai_model": self.ai_model,
            "is_opt_out": self.is_opt_out,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "sent_at": (
                self.sent_at.isoformat() if self.sent_at else None
            ),
            "delivered_at": (
                self.delivered_at.isoformat() if self.delivered_at else None
            ),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }


class SMSConversation(Base):
    """SMS conversation thread mapping.

    Maps a unique phone number pair (customer ↔ Twilio number)
    to a ticket for conversation threading. Multiple SMS messages
    between the same numbers are grouped into one conversation.

    BC-001: Scoped to company_id.
    """

    __tablename__ = "sms_conversations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Phone number pair (normalized E.164)
    customer_number = Column(String(30), nullable=False, index=True)
    twilio_number = Column(String(30), nullable=False)

    # Linked ticket
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Customer resolution
    customer_id = Column(String(36), nullable=True, index=True)

    # Conversation metrics
    message_count = Column(Integer, nullable=False, default=0)
    last_message_at = Column(DateTime, nullable=True)

    # TCPA opt-out tracking (BC-010)
    is_opted_out = Column(Boolean, nullable=False, default=False)
    opt_out_keyword = Column(String(20), nullable=True)
    opt_out_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # Relationships
    messages = relationship(
        "SMSMessage", back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SMSMessage.created_at",
    )
    ticket = relationship("Ticket", foreign_keys=[ticket_id])

    __table_args__ = (
        UniqueConstraint(
            "company_id", "customer_number", "twilio_number",
            name="uq_sms_conversation_numbers",
        ),
        CheckConstraint("message_count >= 0", name="ck_sms_conv_msg_count"),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize SMS conversation for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "customer_number": self.customer_number,
            "twilio_number": self.twilio_number,
            "ticket_id": self.ticket_id,
            "customer_id": self.customer_id,
            "message_count": self.message_count,
            "last_message_at": (
                self.last_message_at.isoformat()
                if self.last_message_at else None
            ),
            "is_opted_out": self.is_opted_out,
            "opt_out_keyword": self.opt_out_keyword,
            "opt_out_at": (
                self.opt_out_at.isoformat() if self.opt_out_at else None
            ),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


class SMSChannelConfig(Base):
    """Per-company Twilio SMS configuration.

    Stores encrypted Twilio credentials and SMS channel settings
    including opt-out keywords, rate limits, and auto-reply config.

    BC-001: One config per company.
    BC-010: TCPA opt-out keywords (STOP, CANCEL, UNSUBSCRIBE).
    BC-011: Credentials encrypted at rest.
    """

    __tablename__ = "sms_channel_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Twilio credentials (encrypted in production via BC-011)
    twilio_account_sid = Column(String(64), nullable=False)
    twilio_auth_token_encrypted = Column(Text, nullable=False)
    twilio_phone_number = Column(String(30), nullable=False)

    # Channel settings
    is_enabled = Column(Boolean, nullable=False, default=True)
    auto_create_ticket = Column(Boolean, nullable=False, default=True)
    char_limit = Column(Integer, nullable=False, default=1600)

    # Rate limiting (BC-006)
    max_outbound_per_hour = Column(Integer, nullable=False, default=5)
    max_outbound_per_day = Column(Integer, nullable=False, default=50)

    # TCPA opt-out keywords (BC-010)
    opt_out_keywords = Column(
        Text, nullable=False,
        default="STOP,STOPALL,UNSUBSCRIBE,CANCEL,QUIT,END",
    )
    opt_in_keywords = Column(
        Text, nullable=False,
        default="START,YES,UNSTOP,CONTINUE",
    )
    opt_out_response = Column(
        Text, nullable=False,
        default="You have been opted out. Reply START to resume.",
    )

    # Auto-reply
    auto_reply_enabled = Column(Boolean, nullable=False, default=False)
    auto_reply_message = Column(
        Text, nullable=True,
        default="Thanks for your message! An agent will respond shortly.",
    )
    auto_reply_delay_seconds = Column(Integer, nullable=False, default=10)

    # After-hours
    after_hours_message = Column(
        Text, nullable=True,
        default="We're currently closed. We'll respond during business hours.",
    )
    business_hours_json = Column(Text, default="{}")

    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        CheckConstraint("char_limit > 0", name="ck_sms_cfg_char_limit"),
        CheckConstraint(
            "max_outbound_per_hour > 0",
            name="ck_sms_cfg_hourly_limit",
        ),
        CheckConstraint(
            "max_outbound_per_day > 0",
            name="ck_sms_cfg_daily_limit",
        ),
        CheckConstraint(
            "auto_reply_delay_seconds >= 0",
            name="ck_sms_cfg_auto_reply_delay",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize SMS config for API responses (no secrets)."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "twilio_account_sid": self.twilio_account_sid,
            "twilio_phone_number": self.twilio_phone_number,
            "is_enabled": self.is_enabled,
            "auto_create_ticket": self.auto_create_ticket,
            "char_limit": self.char_limit,
            "max_outbound_per_hour": self.max_outbound_per_hour,
            "max_outbound_per_day": self.max_outbound_per_day,
            "opt_out_keywords": self.opt_out_keywords,
            "opt_in_keywords": self.opt_in_keywords,
            "opt_out_response": self.opt_out_response,
            "auto_reply_enabled": self.auto_reply_enabled,
            "auto_reply_message": self.auto_reply_message,
            "auto_reply_delay_seconds": self.auto_reply_delay_seconds,
            "after_hours_message": self.after_hours_message,
            "business_hours": self.business_hours_json,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }
