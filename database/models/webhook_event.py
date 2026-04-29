"""
WebhookEvent Model (BC-003, BC-001)

Stores incoming webhook events for idempotent processing.
BC-001: Scoped by company_id with index.
BC-003: Unique constraint on (provider, event_id) for idempotency.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from database.base import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_id",
            name="uq_webhook_provider_event_id",
        ),
    )

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    company_id = Column(
        String(36),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)
    event_id = Column(String(255), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
    )
    processing_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    processing_attempts = Column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
