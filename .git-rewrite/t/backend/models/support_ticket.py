import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
import enum

from backend.app.database import Base


class ChannelEnum(str, enum.Enum):
    chat = "chat"
    email = "email"
    sms = "sms"
    voice = "voice"


class TicketStatusEnum(str, enum.Enum):
    open = "open"
    pending_approval = "pending_approval"
    resolved = "resolved"
    escalated = "escalated"


class AITierEnum(str, enum.Enum):
    light = "light"
    medium = "medium"
    heavy = "heavy"


class SentimentEnum(str, enum.Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class SupportTicket(Base):
    """
    Core ticket model for all customer support requests processed by PARWA.
    """
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    customer_email = Column(String, nullable=False)
    channel = Column(SQLEnum(ChannelEnum, name="channel_enum"), nullable=False)
    status = Column(SQLEnum(TicketStatusEnum, name="ticket_status_enum"), nullable=False, default=TicketStatusEnum.open)
    category = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    ai_recommendation = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_tier_used = Column(SQLEnum(AITierEnum, name="ai_tier_enum"), nullable=True)
    sentiment = Column(SQLEnum(SentimentEnum, name="sentiment_enum"), nullable=True)
    assigned_to = Column(UUID(as_uuid=True), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint('ai_confidence >= 0.0 AND ai_confidence <= 1.0', name='check_ai_confidence_range'),
    )

    def is_pending_approval(self) -> bool:
        """
        Check if the ticket is currently pending approval.
        """
        return self.status == TicketStatusEnum.pending_approval

    def __repr__(self) -> str:
        """
        String representation of the Model. Masks the customer_email for security.
        """
        masked_email = f"{self.customer_email[:3]}***" if self.customer_email else "None"
        return f"<SupportTicket(id={self.id}, company_id={self.company_id}, customer_email='{masked_email}', status={self.status})>"
