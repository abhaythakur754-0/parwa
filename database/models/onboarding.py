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
    """Onboarding wizard session state.

    Week 6: Tracks user progress through 5-step onboarding wizard.
    BC-001: company_id for tenant isolation.
    """
    __tablename__ = "onboarding_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    # Wizard progress (1-5)
    current_step = Column(Integer, default=1)
    completed_steps = Column(Text, default="[]")
    # in_progress, completed, abandoned
    status = Column(String(50), default="in_progress")

    # Week 6: Legal consent tracking (Step 2)
    legal_accepted = Column(Boolean, default=False)
    terms_accepted_at = Column(DateTime)
    privacy_accepted_at = Column(DateTime)
    ai_data_accepted_at = Column(DateTime)

    # Week 6: Integration state (Step 3)
    integrations = Column(Text, default="{}")  # JSON: {"email": true, "chat": false}

    # Week 6: Knowledge base files (Step 4)
    knowledge_base_files = Column(Text, default="[]")  # JSON array of file info

    # Week 6: AI personality config (Step 5)
    ai_name = Column(String(50), default="Jarvis")
    ai_tone = Column(String(20), default="professional")  # professional, friendly, casual
    ai_response_style = Column(String(20), default="concise")  # concise, detailed
    ai_greeting = Column(Text)

    # Week 6: Progress flags
    details_completed = Column(Boolean, default=False)  # Post-payment details done
    wizard_started = Column(Boolean, default=False)  # Wizard started
    first_victory_completed = Column(Boolean, default=False)  # First victory done

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
    status = Column(String(50), default="processing")  # processing, completed, failed
    chunk_count = Column(Integer, default=0)

    # Storage reference for async processing
    file_path = Column(Text, nullable=True)  # Storage path for raw file content
    storage_file_id = Column(String(36), nullable=True)  # Storage backend file ID

    # GAP 6: Failed document handling
    error_message = Column(Text, nullable=True)  # Error message if processing failed
    retry_count = Column(Integer, default=0)  # Number of retry attempts
    failed_at = Column(DateTime, nullable=True)  # When the last failure occurred

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
    # PostgreSQL: VECTOR(1536) via pgvector extension
    # SQLite tests: Text (base64-encoded)
    # Runtime type selected by database/base.py engine
    embedding = Column(Text, nullable=True)
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
