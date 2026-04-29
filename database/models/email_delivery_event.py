"""
Email Delivery Event Model — Week 13 Day 3 (F-124)

Tracks email delivery events (bounces, complaints, delivered, OOO)
from Brevo webhooks. Used for contact email status management,
BC-006 compliance, and delivery analytics.

Building Codes:
- BC-001: Multi-tenant (company_id on every row)
- BC-006: Email communication rules
- BC-010: GDPR compliance (complaint tracking)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, Boolean,
    DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base, JSONType


class EmailDeliveryEvent(Base):
    """Email delivery event record.

    One row per delivery event (bounce, complaint, delivered, OOO).
    Links to OutboundEmail for full correlation.
    """

    __tablename__ = "email_delivery_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Event identification
    event_type = Column(String(50), nullable=False, index=True)
    # Values: "hard_bounce", "soft_bounce", "complaint", "delivered",
    #         "ooo", "rejected", "blocked"

    # Contact info
    recipient_email = Column(String(254), nullable=False)
    recipient_name = Column(String(200), nullable=True)

    # Correlation
    brevo_message_id = Column(String(255), nullable=True)
    brevo_event_id = Column(String(255), nullable=True, unique=True)
    outbound_email_id = Column(UUID(as_uuid=True), nullable=True)
    ticket_id = Column(UUID(as_uuid=True), nullable=True)

    # Event details
    reason = Column(Text, nullable=True)
    bounce_type = Column(String(50), nullable=True)
    # For bounce: "hard", "soft", "invalid_domain", "mailbox_full", etc.
    # For complaint: "spam", "abuse", etc.
    # For OOO: the auto-responder subject/body excerpt

    ooo_until = Column(DateTime(timezone=True), nullable=True)
    # For OOO: when the out-of-office ends (if provided)

    # Provider metadata
    provider = Column(String(50), nullable=False, default="brevo")
    provider_data = Column(JSONType, nullable=True)
    # Raw event payload from Brevo for audit

    # Status tracking
    is_processed = Column(Boolean, nullable=False, default=False)
    processing_error = Column(Text, nullable=True)

    # Soft bounce retry tracking
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    event_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
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
        Index("ix_delivery_company_event", "company_id", "event_type"),
        Index("ix_delivery_recipient", "recipient_email"),
        Index("ix_delivery_brevo_event", "brevo_event_id"),
        Index("ix_delivery_outbound", "outbound_email_id"),
        Index("ix_delivery_processed", "is_processed"),
        Index("ix_delivery_next_retry", "next_retry_at"),
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": str(self.id),
            "company_id": str(self.company_id),
            "event_type": self.event_type,
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "brevo_message_id": self.brevo_message_id,
            "brevo_event_id": self.brevo_event_id,
            "outbound_email_id": str(self.outbound_email_id) if self.outbound_email_id else None,
            "ticket_id": str(self.ticket_id) if self.ticket_id else None,
            "reason": self.reason,
            "bounce_type": self.bounce_type,
            "ooo_until": self.ooo_until.isoformat() if self.ooo_until else None,
            "provider": self.provider,
            "is_processed": self.is_processed,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "event_at": self.event_at.isoformat() if self.event_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
