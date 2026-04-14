"""
Chat Widget Models — Week 13 Day 4 (F-122: Live Chat Widget)

Tables:
- ChatWidgetSession: Unauthenticated visitor chat session with
  visitor metadata (name, email, IP, user-agent, page URL).
- ChatWidgetMessage: Messages within a chat session (visitor,
  agent, system, bot). Supports rich content types.
- CannedResponse: Pre-built quick-reply templates for agents
  grouped by category (greeting, FAQ, closing, etc.).
- ChatWidgetConfig: Per-company widget customization (title,
  colors, welcome message, position, business hours).

Building Codes:
- BC-001: Every table has company_id (multi-tenant isolation)
- BC-005: Real-time events via Socket.io for new messages
- BC-011: Visitor sessions use HMAC-signed tokens, no JWT needed
- BC-012: Structured error responses
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
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

_SESSION_STATUSES = "'active','queued','assigned','closed','expired'"
_MESSAGE_ROLES = "'visitor','agent','system','bot'"
_MESSAGE_TYPES = (
    "'text','image','file','typing','system_event',"
    "'quick_reply','rating'"
)
_RATING_VALUES = "'1','2','3','4','5'"
_WIDGET_POSITIONS = "'bottom_right','bottom_left','top_right','top_left'"


class ChatWidgetSession(Base):
    """Visitor chat session (unauthenticated).

    Represents a single chat conversation between a website visitor
    and an agent/bot. Sessions are identified by a signed token
    (HMAC, not JWT) so no login is required.

    BC-001: Scoped to company_id.
    BC-011: visitor_token is HMAC-signed, not JWT.
    """

    __tablename__ = "chat_widget_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Visitor identity (optional — may be filled during chat)
    visitor_name = Column(String(100), nullable=True)
    visitor_email = Column(String(254), nullable=True)
    visitor_phone = Column(String(30), nullable=True)

    # Visitor metadata for analytics
    visitor_ip = Column(String(45), nullable=True)
    visitor_user_agent = Column(String(500), nullable=True)
    visitor_page_url = Column(String(1000), nullable=True)
    visitor_referrer = Column(String(1000), nullable=True)

    # Session state
    status = Column(String(20), nullable=False, default="active")

    # Assignment
    assigned_agent_id = Column(String(36), nullable=True, index=True)
    department = Column(String(100), nullable=True)

    # Linked ticket (auto-created or manual)
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Customer resolution (if visitor matches known customer)
    customer_id = Column(String(36), nullable=True, index=True)

    # Session metrics
    message_count = Column(Integer, nullable=False, default=0)
    visitor_message_count = Column(Integer, nullable=False, default=0)
    agent_response_time_seconds = Column(Integer, nullable=True)

    # Visitor satisfaction
    csat_rating = Column(Integer, nullable=True)
    csat_comment = Column(Text, nullable=True)

    # Timestamps
    first_message_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # Relationships
    messages = relationship(
        "ChatWidgetMessage", back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatWidgetMessage.created_at",
    )
    ticket = relationship("Ticket", foreign_keys=[ticket_id])

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_SESSION_STATUSES})",
            name="ck_chat_session_status",
        ),
        CheckConstraint(
            "message_count >= 0",
            name="ck_chat_session_msg_count",
        ),
        CheckConstraint(
            "visitor_message_count >= 0",
            name="ck_chat_session_visitor_msg_count",
        ),
        CheckConstraint(
            "csat_rating IS NULL OR (csat_rating >= 1 AND csat_rating <= 5)",
            name="ck_chat_session_csat_range",
        ),
        CheckConstraint(
            "agent_response_time_seconds IS NULL OR agent_response_time_seconds >= 0",
            name="ck_chat_session_response_time_nonneg",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize chat session for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "visitor_name": self.visitor_name,
            "visitor_email": self.visitor_email,
            "visitor_phone": self.visitor_phone,
            "status": self.status,
            "assigned_agent_id": self.assigned_agent_id,
            "department": self.department,
            "ticket_id": self.ticket_id,
            "customer_id": self.customer_id,
            "message_count": self.message_count,
            "visitor_message_count": self.visitor_message_count,
            "agent_response_time_seconds": self.agent_response_time_seconds,
            "csat_rating": self.csat_rating,
            "csat_comment": self.csat_comment,
            "first_message_at": (
                self.first_message_at.isoformat()
                if self.first_message_at else None
            ),
            "last_message_at": (
                self.last_message_at.isoformat()
                if self.last_message_at else None
            ),
            "closed_at": (
                self.closed_at.isoformat() if self.closed_at else None
            ),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


class ChatWidgetMessage(Base):
    """Message within a chat widget session.

    Supports multiple roles (visitor, agent, system, bot) and
    message types (text, image, file, typing indicator, etc.).

    BC-001: Scoped to company via session's company_id.
    BC-005: New messages trigger Socket.io events.
    """

    __tablename__ = "chat_widget_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("chat_widget_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(String(36), nullable=False, index=True)

    # Who sent this message
    sender_id = Column(String(36), nullable=True, index=True)
    sender_name = Column(String(100), nullable=True)
    role = Column(String(10), nullable=False)

    # Message content
    content = Column(Text, nullable=True)
    message_type = Column(String(20), nullable=False, default="text")

    # Attachments (JSON array of {url, filename, size, mime_type})
    attachments_json = Column(Text, default="[]")

    # For quick_reply type: list of options presented
    quick_replies_json = Column(Text, default="[]")

    # For system_event type: event name (e.g., session_assigned)
    event_name = Column(String(50), nullable=True)
    event_data_json = Column(Text, default="{}")

    # Bot/AI attribution
    is_ai_generated = Column(Boolean, nullable=False, default=False)
    ai_confidence = Column(Integer, nullable=True)

    # Read tracking
    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationship
    session = relationship(
        "ChatWidgetSession", back_populates="messages",
    )

    __table_args__ = (
        CheckConstraint(
            f"role IN ({_MESSAGE_ROLES})",
            name="ck_chat_msg_role",
        ),
        CheckConstraint(
            f"message_type IN ({_MESSAGE_TYPES})",
            name="ck_chat_msg_type",
        ),
        CheckConstraint(
            "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 100)",
            name="ck_chat_msg_ai_confidence_range",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize chat message for API responses."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "company_id": self.company_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type,
            "attachments": self.attachments_json,
            "quick_replies": self.quick_replies_json,
            "event_name": self.event_name,
            "event_data": self.event_data_json,
            "is_ai_generated": self.is_ai_generated,
            "ai_confidence": self.ai_confidence,
            "is_read": self.is_read,
            "read_at": (
                self.read_at.isoformat() if self.read_at else None
            ),
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }


class CannedResponse(Base):
    """Pre-built quick reply templates for agents.

    Agents can insert these during chat to speed up responses.
    Organized by category (greeting, FAQ, closing, etc.).

    BC-001: Scoped to company_id.
    """

    __tablename__ = "canned_responses"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="general")
    shortcut = Column(String(50), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "shortcut",
            name="uq_canned_response_company_shortcut",
        ),
        CheckConstraint("sort_order >= 0", name="ck_canned_sort_nonneg"),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize canned response for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "shortcut": self.shortcut,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }


class ChatWidgetConfig(Base):
    """Per-company chat widget customization.

    Controls the widget appearance, behavior, and business hours.

    BC-001: One config per company.
    """

    __tablename__ = "chat_widget_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Widget appearance
    widget_title = Column(String(100), nullable=False, default="Chat with us")
    welcome_message = Column(
        Text, nullable=False,
        default="Hi! How can we help you today?",
    )
    placeholder_text = Column(
        String(200), nullable=False, default="Type your message...",
    )
    primary_color = Column(String(7), nullable=False, default="#4F46E5")
    widget_position = Column(
        String(20), nullable=False, default="bottom_right",
    )

    # Behavior
    is_enabled = Column(Boolean, nullable=False, default=True)
    auto_greeting_enabled = Column(Boolean, nullable=False, default=True)
    auto_greeting_delay_seconds = Column(
        Integer, nullable=False, default=5,
    )
    bot_enabled = Column(Boolean, nullable=False, default=True)
    max_file_size_mb = Column(Integer, nullable=False, default=10)
    allowed_file_types = Column(Text, default='["image/*",".pdf",".doc",".docx"]')

    # Queue settings
    max_queue_size = Column(Integer, nullable=False, default=50)
    queue_message = Column(
        Text, nullable=True,
        default="All agents are busy. Please wait...",
    )

    # Business hours (JSON: {enabled, timezone, schedule: [{day, start, end}]})
    business_hours_json = Column(Text, default="{}")
    offline_message = Column(
        Text, nullable=True,
        default="We're currently offline. Leave us a message!",
    )

    # Request for visitor info
    require_visitor_name = Column(Boolean, nullable=False, default=False)
    require_visitor_email = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime, default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    __table_args__ = (
        CheckConstraint(
            f"widget_position IN ({_WIDGET_POSITIONS})",
            name="ck_widget_config_position",
        ),
        CheckConstraint(
            "auto_greeting_delay_seconds >= 0",
            name="ck_widget_greeting_delay_nonneg",
        ),
        CheckConstraint(
            "max_file_size_mb >= 1",
            name="ck_widget_max_file_size_min",
        ),
        CheckConstraint(
            "max_queue_size >= 1",
            name="ck_widget_max_queue_min",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize widget config for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "widget_title": self.widget_title,
            "welcome_message": self.welcome_message,
            "placeholder_text": self.placeholder_text,
            "primary_color": self.primary_color,
            "widget_position": self.widget_position,
            "is_enabled": self.is_enabled,
            "auto_greeting_enabled": self.auto_greeting_enabled,
            "auto_greeting_delay_seconds": self.auto_greeting_delay_seconds,
            "bot_enabled": self.bot_enabled,
            "max_file_size_mb": self.max_file_size_mb,
            "allowed_file_types": self.allowed_file_types,
            "max_queue_size": self.max_queue_size,
            "queue_message": self.queue_message,
            "business_hours": self.business_hours_json,
            "offline_message": self.offline_message,
            "require_visitor_name": self.require_visitor_name,
            "require_visitor_email": self.require_visitor_email,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }
