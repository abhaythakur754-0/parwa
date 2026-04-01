"""
Ticket Models: sessions, interactions, ticket_attachments,
ticket_internal_notes, customers, channels.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
(sessions/interactions)
BC-001: Every table has company_id (except channels).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, ForeignKey
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    external_id = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    name = Column(String(255))
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(50), nullable=False, unique=True)
    # email, chat, sms, voice, social
    channel_type = Column(String(50), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    customer_id = Column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL")
    )
    channel = Column(String(50), nullable=False)
    status = Column(String(50), default="open")
    subject = Column(String(255))
    priority = Column(String(20), default="normal")
    agent_id = Column(String(36), ForeignKey("agents.id"))
    assigned_to = Column(String(36), ForeignKey("users.id"))
    classification_intent = Column(String(100))
    classification_type = Column(String(50))
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())
    closed_at = Column(DateTime)

    interactions = relationship(
        "Interaction", back_populates="session",
        cascade="all, delete-orphan",
    )


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # customer, agent, system
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    channel = Column(String(50), nullable=False)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    session = relationship("Session", back_populates="interactions")


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    uploaded_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class TicketInternalNote(Base):
    __tablename__ = "ticket_internal_notes"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    author_id = Column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    content = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
