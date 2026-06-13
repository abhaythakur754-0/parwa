"""
OutboundWebhook Model (BC-001, BC-003)

Stores user-configured outbound webhook endpoints.
BC-001: Scoped by company_id with index.
BC-003: HMAC signing secret for outbound payload verification.
"""

import uuid
import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Integer, JSON,
    String, Text, Boolean,
)

from database.base import Base


class OutboundWebhook(Base):
    __tablename__ = "outbound_webhooks"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    company_id = Column(
        String(36), nullable=False, index=True,
    )
    url = Column(String(2048), nullable=False)
    events = Column(JSON, nullable=False, default=list)  # ["ticket.created", "ticket.resolved", ...]
    secret = Column(
        String(64), nullable=False,
        default=lambda: f"whsec_{secrets.token_hex(24)}",
    )
    active = Column(Boolean, nullable=False, default=True)
    last_triggered_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Supported event types for outbound webhooks
    VALID_EVENTS = [
        "ticket.created",
        "ticket.resolved",
        "ticket.escalated",
        "agent.response",
        "sla.breached",
        "integration.error",
    ]
