"""
Billing Models: subscriptions, invoices, overage_charges, transactions,
webhook_events, cancellation_requests.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Every table has company_id.
BC-002: All money fields DECIMAL(10,2) — NEVER float.
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Integer, Numeric, String, Text, ForeignKey
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tier = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    paddle_subscription_id = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # ── Day 2 additions ─────────────────────────────────────────────
    # Y1: billing_frequency — monthly or yearly
    billing_frequency = Column(String(20), nullable=False, default="monthly")

    # D2: pending_downgrade_tier — target tier at period end
    pending_downgrade_tier = Column(String(50), nullable=True)

    # D5/D6: downgrade scheduling timestamps
    pending_downgrade_at = Column(DateTime, nullable=True)
    downgrade_executed_at = Column(DateTime, nullable=True)
    previous_tier = Column(String(50), nullable=True)  # for undo (D6)

    # Y4: days_in_period — stored for audit
    days_in_period = Column(Integer, nullable=True)

    # P5: metadata_json for extensibility
    metadata_json = Column(Text, nullable=True)

    # ── Day 4 additions ─────────────────────────────────────────────
    # C3/C4: service_stopped_at — when service was actually stopped
    service_stopped_at = Column(DateTime, nullable=True)

    # C7: data_hard_deleted — whether non-billing data was purged
    data_hard_deleted = Column(Boolean, default=False)

    # C7: data_deleted_at — when data was permanently deleted
    data_deleted_at = Column(DateTime, nullable=True)

    # C1: cancel_feedback — "Why are you leaving?" free text
    cancel_feedback = Column(Text, nullable=True)

    # C1: save_offer_accepted — whether the 20% save offer was accepted
    save_offer_accepted = Column(Boolean, default=False)


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    paddle_invoice_id = Column(String(255))
    amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    currency = Column(String(3), default="USD")
    status = Column(String(50), nullable=False, default="pending")
    invoice_date = Column(DateTime)
    due_date = Column(DateTime)
    paid_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class OverageCharge(Base):
    __tablename__ = "overage_charges"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date = Column(Date, nullable=False)
    tickets_over_limit = Column(Integer, nullable=False, default=0)
    charge_amount = Column(Numeric(10, 2), nullable=False, default=0)  # BC-002
    paddle_charge_id = Column(String(255))
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    paddle_transaction_id = Column(String(255))
    amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    currency = Column(String(3), default="USD")
    status = Column(String(50), nullable=False)
    transaction_type = Column(String(50), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class CancellationRequest(Base):
    __tablename__ = "cancellation_requests"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    feedback = Column(Text)
    status = Column(String(50), default="pending")
    contacted_at = Column(DateTime)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
