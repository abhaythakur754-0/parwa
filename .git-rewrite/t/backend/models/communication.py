"""
Communication Models

SQLAlchemy models for client communication including:
- ClientMessage: Messages sent to clients
- MessageTemplate: Message templates
- ScheduledNotification: Scheduled notifications
- CommunicationPreference: Client communication preferences
"""
import enum
import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import Column, String, Boolean, DateTime, Date, Enum, ForeignKey, Numeric, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import validates, relationship
from sqlalchemy.sql import func
from backend.app.database import Base


class MessageChannel(str, enum.Enum):
    """Communication channels."""
    EMAIL = "email"
    IN_APP = "in_app"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"


class MessageStatus(str, enum.Enum):
    """Status of a message."""
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"


class MessageType(str, enum.Enum):
    """Types of messages."""
    CHECK_IN = "check_in"
    ANNOUNCEMENT = "announcement"
    ALERT = "alert"
    REMINDER = "reminder"
    RETENTION = "retention"
    ONBOARDING = "onboarding"
    SUPPORT = "support"
    CUSTOM = "custom"


class TemplateCategory(str, enum.Enum):
    """Categories of message templates."""
    ONBOARDING = "onboarding"
    CHECK_IN = "check_in"
    ANNOUNCEMENT = "announcement"
    RETENTION = "retention"
    SUPPORT = "support"
    ALERT = "alert"
    RENEWAL = "renewal"
    CUSTOM = "custom"


class ScheduleStatus(str, enum.Enum):
    """Status of a scheduled notification."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RecurrenceType(str, enum.Enum):
    """Types of recurrence."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class ClientMessage(Base):
    """
    SQLAlchemy model for client messages.

    Stores all messages sent to clients.
    """
    __tablename__ = "client_messages"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Column[str] = Column(String(50), unique=True, nullable=False)
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Message details
    channel: Column[MessageChannel] = Column(
        Enum(MessageChannel), nullable=False, index=True
    )
    message_type: Column[MessageType] = Column(
        Enum(MessageType), nullable=False, index=True
    )
    status: Column[MessageStatus] = Column(
        Enum(MessageStatus), nullable=False, index=True
    )

    # Content
    subject: Column[str] = Column(String(500), nullable=False)
    body: Column[str] = Column(Text, nullable=False)

    # Sender/Recipient
    sender: Column[str] = Column(String(255), nullable=True)
    recipient: Column[str] = Column(String(255), nullable=True)

    # Template reference
    template_id: Column[str] = Column(String(100), nullable=True)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    sent_at: Column[datetime] = Column(DateTime, nullable=True)
    delivered_at: Column[datetime] = Column(DateTime, nullable=True)
    read_at: Column[datetime] = Column(DateTime, nullable=True)

    # Tracking
    open_count: Column[int] = Column(Integer, default=0)
    click_count: Column[int] = Column(Integer, default=0)

    # Metadata
    metadata_json: Column[dict] = Column(JSONB, default=dict)

    # Relationships
    company = relationship("Company", back_populates="client_messages")

    def __repr__(self) -> str:
        return f"<ClientMessage(id={self.message_id}, client={self.client_id}, channel={self.channel})>"


class MessageTemplate(Base):
    """
    SQLAlchemy model for message templates.

    Stores reusable message templates.
    """
    __tablename__ = "message_templates"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Column[str] = Column(String(100), unique=True, nullable=False)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True, index=True
    )  # Null for system templates

    # Template details
    name: Column[str] = Column(String(255), nullable=False)
    category: Column[TemplateCategory] = Column(
        Enum(TemplateCategory), nullable=False, index=True
    )
    description: Column[str] = Column(Text, nullable=True)

    # Content templates
    subject_template: Column[str] = Column(String(500), nullable=False)
    body_template: Column[str] = Column(Text, nullable=False)

    # Variables
    variables: Column[list] = Column(JSONB, default=list)

    # Channel
    channel: Column[str] = Column(String(20), nullable=False)

    # Status
    is_active: Column[bool] = Column(Boolean, default=True, index=True)
    is_system: Column[bool] = Column(Boolean, default=False)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, onupdate=func.now(), default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<MessageTemplate(id={self.template_id}, name={self.name})>"


class ScheduledNotification(Base):
    """
    SQLAlchemy model for scheduled notifications.

    Stores notifications scheduled for future delivery.
    """
    __tablename__ = "scheduled_notifications"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schedule_id: Column[str] = Column(String(50), unique=True, nullable=False)
    client_id: Column[str] = Column(String(50), nullable=False, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Message details
    channel: Column[str] = Column(String(20), nullable=False)
    subject: Column[str] = Column(String(500), nullable=False)
    body: Column[str] = Column(Text, nullable=False)

    # Scheduling
    scheduled_for: Column[datetime] = Column(DateTime, nullable=False, index=True)
    timezone: Column[str] = Column(String(50), default="UTC")
    status: Column[ScheduleStatus] = Column(
        Enum(ScheduleStatus), nullable=False, index=True
    )

    # Recurrence
    recurrence: Column[RecurrenceType] = Column(
        Enum(RecurrenceType), default=RecurrenceType.NONE
    )
    recurrence_config: Column[dict] = Column(JSONB, default=dict)
    next_occurrence: Column[datetime] = Column(DateTime, nullable=True)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    sent_at: Column[datetime] = Column(DateTime, nullable=True)

    # Metadata
    metadata_json: Column[dict] = Column(JSONB, default=dict)

    # Relationships
    company = relationship("Company", back_populates="scheduled_notifications")

    def __repr__(self) -> str:
        return f"<ScheduledNotification(id={self.schedule_id}, client={self.client_id}, scheduled={self.scheduled_for})>"


class CommunicationPreference(Base):
    """
    SQLAlchemy model for client communication preferences.

    Stores preferences for how clients want to be contacted.
    """
    __tablename__ = "communication_preferences"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Column[str] = Column(String(50), nullable=False, unique=True, index=True)
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Channel preferences
    email_enabled: Column[bool] = Column(Boolean, default=True)
    in_app_enabled: Column[bool] = Column(Boolean, default=True)
    sms_enabled: Column[bool] = Column(Boolean, default=False)
    slack_enabled: Column[bool] = Column(Boolean, default=False)
    webhook_enabled: Column[bool] = Column(Boolean, default=False)

    # Preferred channel
    preferred_channel: Column[MessageChannel] = Column(
        Enum(MessageChannel), default=MessageChannel.EMAIL
    )

    # Quiet hours (hour in 24-hour format, UTC)
    quiet_hours_start: Column[int] = Column(Integer, nullable=True)
    quiet_hours_end: Column[int] = Column(Integer, nullable=True)

    # Frequency caps
    frequency_cap_daily: Column[int] = Column(Integer, default=5)
    frequency_cap_weekly: Column[int] = Column(Integer, default=20)

    # Contact info
    primary_email: Column[str] = Column(String(255), nullable=True)
    primary_phone: Column[str] = Column(String(50), nullable=True)
    slack_channel: Column[str] = Column(String(100), nullable=True)
    webhook_url: Column[str] = Column(String(500), nullable=True)

    # Timestamps
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, onupdate=func.now(), default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<CommunicationPreference(client={self.client_id})>"


class CommunicationSummary:
    """
    Non-persisted model for communication summary data.

    Used for aggregating and presenting communication statistics.
    """
    def __init__(
        self,
        total_messages: int,
        by_status: dict,
        by_channel: dict,
        by_type: dict,
        read_rate: float,
        response_rate: float
    ):
        self.total_messages = total_messages
        self.by_status = by_status
        self.by_channel = by_channel
        self.by_type = by_type
        self.read_rate = read_rate
        self.response_rate = response_rate
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "total_messages": self.total_messages,
            "by_status": self.by_status,
            "by_channel": self.by_channel,
            "by_type": self.by_type,
            "read_rate": self.read_rate,
            "response_rate": self.response_rate,
            "timestamp": self.timestamp.isoformat(),
        }
