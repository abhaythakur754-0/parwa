"""
PARWA Agent Provisioning Models (F-099)

SQLAlchemy models for Paddle-triggered agent provisioning pipeline.
Tracks pending agent additions from checkout through payment to
provisioning completion.

Table:
- PendingAgent: Intermediate record for agents awaiting payment or
  being provisioned after a Paddle checkout.

Building Codes: BC-001 (multi-tenant), BC-002 (financial / Paddle),
               BC-003 (idempotency via paddle_event_id unique),
               BC-004 (Celery provisioning pipeline).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (used by CHECK constraints) ────────────

_PAYMENT_STATUSES = (
    "'pending','paid','failed','refunded','expired'"
)
_PROVISIONING_STATUSES = (
    "'awaiting_payment','provisioning','training','active','failed'"
)


# ── PendingAgent ───────────────────────────────────────────────

class PendingAgent(Base):
    """Intermediate record for an agent being provisioned via Paddle.

    Created when a user initiates agent checkout. Tracks payment status
    through Paddle webhooks and provisioning progress through the
    Celery pipeline.

    Lifecycle:
      awaiting_payment → (payment webhook) → provisioning → training → active
      awaiting_payment → (timeout 24h)     → expired
      provisioning/training                → failed

    BC-001: Scoped by company_id.
    BC-002: Financial operation linked to Paddle checkout/transaction.
    BC-003: paddle_event_id is unique for idempotent webhook processing.
    BC-004: Provisioning triggered via Celery task.
    """
    __tablename__ = "pending_agents"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_name = Column(String(200), nullable=False)
    specialty = Column(String(50), nullable=False)
    # JSON array: ["chat", "email", ...]
    channels = Column(Text, nullable=False, default="[]")
    paddle_checkout_id = Column(String(255), nullable=True)
    paddle_transaction_id = Column(String(255), nullable=True)
    # BC-003: Unique event ID for idempotent webhook processing
    paddle_event_id = Column(String(255), nullable=True, unique=True)
    payment_status = Column(String(20), nullable=False, default="pending")
    provisioning_status = Column(
        String(20), nullable=False, default="awaiting_payment",
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    provisioned_at = Column(DateTime, nullable=True)
    # 24h expiry for stale pending agents awaiting payment
    expires_at = Column(DateTime, nullable=True)

    # ── Relationships ──
    company = relationship("Company")

    __table_args__ = (
        CheckConstraint(
            f"payment_status IN ({_PAYMENT_STATUSES})",
            name="ck_pending_agent_payment_status",
        ),
        CheckConstraint(
            f"provisioning_status IN ({_PROVISIONING_STATUSES})",
            name="ck_pending_agent_provisioning_status",
        ),
        Index(
            "ix_pending_agents_company_payment",
            "company_id", "payment_status",
        ),
        Index(
            "ix_pending_agents_company_provisioning",
            "company_id", "provisioning_status",
        ),
        {"schema": None},
    )
