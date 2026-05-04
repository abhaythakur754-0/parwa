"""
Extended Billing Models (BC-001, BC-002)

Additional billing tables for Week 5:
- ClientRefund: PARWA clients refunding THEIR customers
- PaymentMethod: Payment method cache from Paddle
- UsageRecord: Daily/monthly usage tracking
- VariantLimit: Variant feature limits
- IdempotencyKey: Webhook idempotency tracking
- WebhookSequence: Webhook ordering tracking
- ProrationAudit: Proration calculation audit trail
- PaymentFailure: Payment failure audit log

BC-001: Every table has company_id
BC-002: All money fields are DECIMAL(10,2) — NEVER float
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Integer, Numeric, String, Text, ForeignKey, Index
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Client Refund Model ─────────────────────────────────────────────────────

class ClientRefund(Base):
    """
    PARWA clients refunding THEIR customers.
    
    This is NOT PARWA refunding clients (NO REFUNDS policy).
    Use case: PARWA client has e-commerce store, customer requests refund,
    PARWA AI agent processes refund, we track for analytics.
    """
    __tablename__ = "client_refunds"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    currency = Column(String(3), default="USD")
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending/processed/failed
    external_ref = Column(String(255), nullable=True)  # Client's payment system ref
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # Relationships
    company = relationship("Company", back_populates="client_refunds")


# ── Payment Method Model ────────────────────────────────────────────────────

class PaymentMethod(Base):
    """Payment method cache from Paddle."""
    __tablename__ = "payment_methods"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    paddle_payment_method_id = Column(String(255), nullable=False, unique=True)
    method_type = Column(String(20))  # card/paypal/wire/apple_pay/google_pay
    last_four = Column(String(4))
    expiry_month = Column(Integer)
    expiry_year = Column(Integer)
    card_brand = Column(String(20))  # visa/mastercard/amex/etc
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # Relationships
    company = relationship("Company", back_populates="payment_methods")


# ── Usage Record Model ──────────────────────────────────────────────────────

class UsageRecord(Base):
    """Daily/monthly usage tracking."""
    __tablename__ = "usage_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_date = Column(Date, nullable=False)
    record_month = Column(String(7), nullable=False)  # YYYY-MM
    tickets_used = Column(Integer, default=0)
    ai_agents_used = Column(Integer, default=0)
    voice_minutes_used = Column(Numeric(10, 2), default=Decimal("0.00"))  # BC-002
    overage_tickets = Column(Integer, default=0)
    overage_charges = Column(Numeric(10, 2), default=Decimal("0.00"))  # BC-002
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Unique constraint: one record per company per day
    __table_args__ = (
        Index("uq_usage_records_company_date", "company_id", "record_date", unique=True),
    )

    # Relationships
    company = relationship("Company", back_populates="usage_records")


# ── Variant Limit Model ─────────────────────────────────────────────────────

class VariantLimit(Base):
    """Variant feature limits."""
    __tablename__ = "variant_limits"

    id = Column(String(36), primary_key=True, default=_uuid)
    variant_name = Column(String(50), unique=True, nullable=False)  # starter/growth/high
    monthly_tickets = Column(Integer, nullable=False)
    ai_agents = Column(Integer, nullable=False)
    team_members = Column(Integer, nullable=False)
    voice_slots = Column(Integer, nullable=False)
    kb_docs = Column(Integer, nullable=False)
    price_monthly = Column(Numeric(10, 2), nullable=False)  # BC-002
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


# ── Idempotency Key Model ──────────────────────────────────────────────────

class IdempotencyKey(Base):
    """Webhook idempotency tracking."""
    __tablename__ = "idempotency_keys"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True)
    idempotency_key = Column(String(255), unique=True, nullable=False)
    resource_type = Column(String(50), nullable=False)  # paddle_webhook, stripe_webhook, etc
    resource_id = Column(String(255), nullable=True)
    request_body_hash = Column(String(64), nullable=True)  # SHA-256 hash
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    expires_at = Column(DateTime, nullable=False)


# ── Webhook Sequence Model ──────────────────────────────────────────────────

class WebhookSequence(Base):
    """Webhook ordering tracking."""
    __tablename__ = "webhook_sequences"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=True)
    paddle_event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processing_order = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")  # pending/processing/processed/failed
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Proration Audit Model ───────────────────────────────────────────────────

class ProrationAudit(Base):
    """Proration calculation audit trail."""
    __tablename__ = "proration_audits"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_variant = Column(String(50), nullable=False)
    new_variant = Column(String(50), nullable=False)
    old_price = Column(Numeric(10, 2), nullable=False)  # BC-002
    new_price = Column(Numeric(10, 2), nullable=False)  # BC-002
    days_remaining = Column(Integer, nullable=False)
    days_in_period = Column(Integer, nullable=False)
    unused_amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    proration_amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    credit_applied = Column(Numeric(10, 2), default=Decimal("0.00"))  # BC-002
    charge_applied = Column(Numeric(10, 2), default=Decimal("0.00"))  # BC-002
    billing_cycle_start = Column(Date, nullable=False)
    billing_cycle_end = Column(Date, nullable=False)
    calculated_at = Column(DateTime, default=lambda: datetime.utcnow())
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    company = relationship("Company", back_populates="proration_audits")


# ── Payment Failure Model ───────────────────────────────────────────────────

class PaymentFailure(Base):
    """Payment failure audit log."""
    __tablename__ = "payment_failures"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    paddle_subscription_id = Column(String(255), nullable=True)
    paddle_transaction_id = Column(String(255), nullable=True)
    failure_code = Column(String(50), nullable=True)
    failure_reason = Column(Text, nullable=True)
    amount_attempted = Column(Numeric(10, 2), nullable=True)  # BC-002
    currency = Column(String(3), default="USD")
    service_stopped_at = Column(DateTime, nullable=True)
    service_resumed_at = Column(DateTime, nullable=True)
    notification_sent = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    company = relationship("Company", back_populates="payment_failures")


# ── Convenience Functions ───────────────────────────────────────────────────

def get_variant_limits(variant_name: str) -> Optional[dict]:
    """
    Get variant limits by name.
    
    Returns dict with limits or None if not found.
    """
    # Hardcoded fallback (matches migration data)
    LIMITS = {
        "starter": {
            "monthly_tickets": 2000,
            "ai_agents": 1,
            "team_members": 3,
            "voice_slots": 0,
            "kb_docs": 100,
            "price_monthly": Decimal("999.00"),
        },
        "growth": {
            "monthly_tickets": 5000,
            "ai_agents": 3,
            "team_members": 10,
            "voice_slots": 2,
            "kb_docs": 500,
            "price_monthly": Decimal("2499.00"),
        },
        "high": {
            "monthly_tickets": 15000,
            "ai_agents": 5,
            "team_members": 25,
            "voice_slots": 5,
            "kb_docs": 2000,
            "price_monthly": Decimal("3999.00"),
        },
    }
    return LIMITS.get(variant_name.lower())


def calculate_overage(tickets_used: int, ticket_limit: int) -> dict:
    """
    Calculate overage charges.
    
    Overage rate: $0.10/ticket over limit
    
    Returns dict with overage_tickets and overage_charges.
    """
    overage_tickets = max(0, tickets_used - ticket_limit)
    overage_charges = Decimal(str(overage_tickets)) * Decimal("0.10")
    
    return {
        "overage_tickets": overage_tickets,
        "overage_charges": overage_charges,
        "overage_rate": Decimal("0.10"),
    }
