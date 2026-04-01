"""
Onboarding Models: onboarding_sessions, consent_records,
knowledge_documents, document_chunks, demo_sessions,
newsletter_subscribers.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Tables with tenant data have company_id.
newsletter_subscribers and demo_sessions are public-facing (no company_id).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    current_step = Column(Integer, default=1)  # 1-5
    completed_steps = Column(Text, default="[]")
    # in_progress, completed, abandoned
    status = Column(String(50), default="in_progress")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())
    completed_at = Column(DateTime)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    # tcpa, gdpr, call_recording
    consent_type = Column(String(50), nullable=False)
    consent_version = Column(String(20), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    granted = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer)
    category = Column(String(100))
    status = Column(String(50), default="processing")
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(
        String(36),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    content = Column(Text, nullable=False)
    # stored as base64 in SQLite, vector in PG
    embedding = Column(Text)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class DemoSession(Base):
    __tablename__ = "demo_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    guest_email = Column(String(255))
    guest_name = Column(String(255))
    guest_phone = Column(String(50))
    session_token = Column(
        String(255), nullable=False, unique=True,
    )
    messages_count = Column(Integer, default=0)
    max_messages = Column(Integer, default=10)
    is_voice = Column(Boolean, default=False)
    voice_payment_id = Column(String(255))
    voice_call_sid = Column(String(255))
    status = Column(String(50), default="active")
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255))
    source = Column(String(100))
    is_active = Column(Boolean, default=True)
    subscribed_at = Column(DateTime, default=lambda: datetime.utcnow())
    unsubscribed_at = Column(DateTime)
