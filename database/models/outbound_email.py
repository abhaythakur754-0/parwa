"""
Outbound Email Model — Week 13 Day 2 (F-120)

Tracks outbound emails sent to customers, correlating
Brevo message_ids with ticket_ids for delivery tracking.

Building Codes:
- BC-001: company_id on every row
- BC-006: Links to ticket for rate limiting
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class OutboundEmail(Base):
    """Outbound email tracking record.

    One row per email sent to a customer via Brevo.
    Used for delivery tracking, rate limiting, and audit trail.
    """

    __tablename__ = "outbound_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Who we sent to
    recipient_email = Column(String(254), nullable=False)
    recipient_name = Column(String(200), nullable=True)
    subject = Column(String(500), nullable=False)

    # Threading headers (for correlating with inbound)
    reply_to_message_id = Column(String(255), nullable=True)
    references = Column(Text, nullable=True)

    # Brevo tracking
    brevo_message_id = Column(String(255), nullable=True, unique=True)
    delivery_status = Column(
        String(50),
        nullable=False,
        default="pending",
    )  # pending, sent, delivered, bounced, failed, complaint

    # Ticket association
    ticket_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    ticket_message_id = Column(UUID(as_uuid=True), nullable=True)

    # AI attribution
    role = Column(String(50), nullable=False, default="ai")
    model_used = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)

    # Content tracking
    content_length = Column(Integer, nullable=True)
    template_used = Column(String(100), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    sent_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    bounced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Indexes
    __table_args__ = (
        Index("ix_outbound_company_ticket", "company_id", "ticket_id"),
        Index("ix_outbound_brevo_id", "brevo_message_id"),
        Index("ix_outbound_delivery_status", "delivery_status"),
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "subject": self.subject,
            "reply_to_message_id": self.reply_to_message_id,
            "references": self.references,
            "brevo_message_id": self.brevo_message_id,
            "delivery_status": self.delivery_status,
            "ticket_id": str(self.ticket_id),
            "ticket_message_id": str(self.ticket_message_id) if self.ticket_message_id else None,
            "role": self.role,
            "model_used": self.model_used,
            "confidence": self.confidence,
            "content_length": self.content_length,
            "template_used": self.template_used,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "bounced_at": self.bounced_at.isoformat() if self.bounced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
