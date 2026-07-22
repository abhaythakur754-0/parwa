"""
FlexPay Models: Installment-based payment plans for PARWA subscriptions.

Allows collecting large subscription amounts ($999-$3999) in small daily 
installments ($100 base + extra every 3rd day) to stay under Razorpay's 
per-transaction limit while completing collection within the 30-day billing cycle.

BC-001: Every table has company_id.
BC-002: All money fields DECIMAL(10,2) — NEVER float.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, Numeric, String, Text, ForeignKey,
    Enum
)

from database.base import Base
import enum


def _uuid() -> str:
    return str(uuid.uuid4())


class FlexPayStatus(str, enum.Enum):
    """Lifecycle states for a FlexPay installment plan."""
    PENDING = "pending"           # Plan created, waiting for first payment
    ACTIVE = "active"             # First payment received, plan is running
    PAUSED = "paused"             # Payment failed, plan temporarily suspended
    COMPLETED = "completed"       # All installments paid successfully
    CANCELLED = "cancelled"       # Customer or system cancelled
    FAILED = "failed"             # Too many failures, plan terminated


class InstallmentStatus(str, enum.Enum):
    """Status of individual installment payments."""
    PENDING = "pending"           # Waiting to be charged
    PROCESSING = "processing"     # Currently being charged
    PAID = "paid"                 # Successfully collected
    FAILED = "failed"             # Charge failed, will retry
    SKIPPED = "skipped"           # Skipped (plan paused/cancelled)


class FlexPayPlan(Base):
    """Represents an installment payment plan for a subscription."""
    
    __tablename__ = "flexpay_plans"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    
    # Plan configuration
    variant_tier = Column(String(50), nullable=False)  # mini, parwa, high
    total_amount = Column(Numeric(10, 2), nullable=False)  # BC-002: $999, $2499, $3999
    installment_amount = Column(Numeric(10, 2), nullable=False)  # Base: $100
    extra_installment_amount = Column(Numeric(10, 2), nullable=True)  # Extra on day 3: $100
    total_installments = Column(Integer, nullable=False)  # Total number of payments
    completed_installments = Column(Integer, default=0, nullable=False)
    
    # Status tracking
    status = Column(
        String(20), nullable=False, default=FlexPayStatus.PENDING.value,
        index=True
    )
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)  # Should align with 30-day subscription
    
    # Razorpay integration
    razorpay_customer_id = Column(String(255))  # Tokenized customer
    razorpay_order_id = Column(String(255))  # Initial order if any
    
    # Failure tracking
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_failure_reason = Column(Text)
    last_failure_at = Column(DateTime)
    max_retries = Column(Integer, default=3, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    
    # Metadata
    notes = Column(Text)
    
    def __repr__(self):
        return f"<FlexPayPlan(id={self.id[:8]}..., variant={self.variant_tier}, status={self.status})>"


class FlexPayInstallment(Base):
    """Represents a single installment within a FlexPay plan."""
    
    __tablename__ = "flexpay_installments"

    id = Column(String(36), primary_key=True, default=_uuid)
    plan_id = Column(
        String(36), ForeignKey("flexpay_plans.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    
    # Installment details
    installment_number = Column(Integer, nullable=False)  # 1, 2, 3...N
    amount = Column(Numeric(10, 2), nullable=False)  # BC-002: Usually $100 or $200
    is_extra = Column(Boolean, default=False)  # True if this is the "extra" charge on day 3
    
    # Status tracking
    status = Column(
        String(20), nullable=False, default=InstallmentStatus.PENDING.value,
        index=True
    )
    
    # Razorpay payment info
    razorpay_payment_id = Column(String(255))
    razorpay_order_id = Column(String(255))
    razorpay_status = Column(String(50))  # From Razorpay webhook
    
    # Timing
    scheduled_at = Column(DateTime, nullable=False)  # When this should be charged
    processed_at = Column(DateTime)  # When it was actually charged
    
    # Failure handling
    failure_reason = Column(Text)
    retry_count = Column(Integer, default=0, nullable=False)
    retry_after = Column(DateTime)  # Next retry time
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<FlexPayInstallment(id={self.id[:8]}..., #{self.installment_number}, amount={self.amount}, status={self.status})>"
