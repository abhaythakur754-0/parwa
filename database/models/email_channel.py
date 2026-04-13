"""
Email Channel Models: inbound_emails, email_threads.

Week 13 Day 1 (F-121: Email Inbound).

Stores raw inbound emails for audit trail and maps email
threads (Message-ID chains) to tickets for threading support.

BC-001: Every table has company_id.
BC-003: Idempotent webhook processing.
BC-006: Email communication.
BC-010: Data lifecycle (raw emails retained for audit).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
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


class InboundEmail(Base):
    """Raw inbound email storage for audit trail.

    Every email received via Brevo inbound parse webhook is stored
    here before processing. This enables:
    - Audit trail for compliance (BC-010)
    - Idempotent processing (BC-003) — same Message-ID processed once
    - Loop detection via Message-ID lookup
    - Debugging and replay capability
    """

    __tablename__ = "inbound_emails"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # RFC 2822 email headers
    message_id = Column(String(255), unique=True, index=True)
    in_reply_to = Column(String(255), nullable=True)
    references = Column(Text, nullable=True)

    # Email metadata
    sender_email = Column(String(254), nullable=False, index=True)
    sender_name = Column(String(200), nullable=True)
    recipient_email = Column(String(254), nullable=False)
    subject = Column(String(500), nullable=True)
    body_html = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    headers_json = Column(Text, default="{}")

    # Processing state
    is_auto_reply = Column(Boolean, default=False, nullable=False)
    is_loop = Column(Boolean, default=False, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
    )
    processing_error = Column(Text, nullable=True)
    raw_size_bytes = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationship
    ticket = relationship("Ticket", foreign_keys=[ticket_id])

    def to_dict(self) -> dict:
        """Serialize inbound email for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "message_id": self.message_id,
            "in_reply_to": self.in_reply_to,
            "references": self.references,
            "sender_email": self.sender_email,
            "sender_name": self.sender_name,
            "recipient_email": self.recipient_email,
            "subject": self.subject,
            "is_auto_reply": self.is_auto_reply,
            "is_loop": self.is_loop,
            "is_processed": self.is_processed,
            "ticket_id": self.ticket_id,
            "processing_error": self.processing_error,
            "raw_size_bytes": self.raw_size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EmailThread(Base):
    """Maps email threads (Message-ID chains) to tickets.

    When an email comes in with In-Reply-To or References headers,
    we use this table to find the existing ticket and add the new
    message to it instead of creating a new ticket.
    """

    __tablename__ = "email_threads"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Thread tracking
    thread_message_id = Column(String(255), nullable=False, index=True)
    latest_message_id = Column(String(255), nullable=True)
    message_count = Column(Integer, default=1, nullable=False)
    participants_json = Column(Text, default="[]")

    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())

    # Relationship
    ticket = relationship("Ticket", foreign_keys=[ticket_id])

    def to_dict(self) -> dict:
        """Serialize email thread for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "ticket_id": self.ticket_id,
            "thread_message_id": self.thread_message_id,
            "latest_message_id": self.latest_message_id,
            "message_count": self.message_count,
            "participants": self.participants_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
