"""
Billing Schemas (BC-002)

Pydantic models for billing API requests and responses.
All money fields use Decimal (never float) per BC-002.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.pricing_config import (
    VariantType,
    VARIANT_LIMITS as _PC_VARIANT_LIMITS,
    VARIANT_PRICES,
)


# ── Enums ────────────────────────────────────────────────────────────────

# VariantType is imported from app.core.pricing_config — the single
# source of truth for all variant/price data.  Do NOT redefine it here.


class SubscriptionStatus(str, Enum):
    """Subscription status values."""
    PENDING = "pending"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELED = "canceled"
    PAYMENT_FAILED = "payment_failed"


class PaymentStatus(str, Enum):
    """Payment/transaction status values."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethodType(str, Enum):
    """Payment method types."""
    CARD = "card"
    PAYPAL = "paypal"
    WIRE = "wire"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


# ── Variant Limits ────────────────────────────────────────────────────────

# VARIANT_LIMITS is built from pricing_config — the single source of truth.
# pricing_config stores limits and prices separately to prevent accidental
# misuse; here we combine them for backward-compat with VariantLimits schema.
VARIANT_LIMITS = {
    vt: {**_PC_VARIANT_LIMITS[vt], "price": VARIANT_PRICES[vt]}
    for vt in VariantType
}


class VariantLimits(BaseModel):
    """Feature limits for a variant."""
    variant: VariantType
    monthly_tickets: int
    ai_agents: int
    team_members: int
    voice_slots: int
    kb_docs: int
    price: Decimal


# ── Subscription Schemas ──────────────────────────────────────────────────

class SubscriptionBase(BaseModel):
    """Base subscription fields."""
    variant: VariantType
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE


class SubscriptionCreate(SubscriptionBase):
    """Request to create a new subscription."""
    payment_method_id: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    """Request to update a subscription (upgrade/downgrade)."""
    variant: VariantType


class SubscriptionCancel(BaseModel):
    """Request to cancel a subscription."""
    reason: Optional[str] = None
    effective_immediately: bool = False


class SubscriptionInfo(BaseModel):
    """Subscription information response."""
    id: UUID
    company_id: UUID
    variant: VariantType
    status: SubscriptionStatus
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    paddle_subscription_id: Optional[str] = None
    created_at: datetime

    # Scheduled change fields (downgrade or cancel at period end)
    scheduled_change_type: Optional[str] = None  # "downgrade" or "cancel"
    scheduled_change_variant: Optional[str] = None  # target variant for downgrade

    # Checkout URL for pending subscriptions (new customers)
    checkout_url: Optional[str] = None

    # Computed limits for this variant
    limits: Optional[VariantLimits] = None

    class Config:
        from_attributes = True


# ── Usage Schemas ─────────────────────────────────────────────────────────

class UsageInfo(BaseModel):
    """Current usage information."""
    company_id: UUID
    record_month: str  # YYYY-MM
    tickets_used: int
    ticket_limit: int
    overage_tickets: int = 0
    overage_charges: Decimal = Decimal("0.00")
    usage_percentage: float = Field(..., ge=0.0)
    approaching_limit: bool = False
    limit_exceeded: bool = False


class UsageHistory(BaseModel):
    """Monthly usage history."""
    record_month: str
    tickets_used: int
    overage_tickets: int
    overage_charges: Decimal


# ── Payment Method Schemas ────────────────────────────────────────────────

class PaymentMethodBase(BaseModel):
    """Base payment method fields."""
    method_type: PaymentMethodType


class PaymentMethodInfo(BaseModel):
    """Payment method information."""
    id: UUID
    company_id: UUID
    method_type: PaymentMethodType
    last_four: Optional[str] = None
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None
    is_default: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ── Invoice Schemas ────────────────────────────────────────────────────────

class InvoiceInfo(BaseModel):
    """Invoice information."""
    id: UUID
    company_id: UUID
    paddle_invoice_id: Optional[str] = None
    amount: Decimal
    currency: str = "USD"
    status: str
    invoice_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceList(BaseModel):
    """Paginated invoice list."""
    invoices: List[InvoiceInfo]
    total: int
    page: int
    page_size: int


# ── Proration Schemas ─────────────────────────────────────────────────────

class ProrationResult(BaseModel):
    """Proration calculation result."""
    old_variant: VariantType
    new_variant: VariantType
    old_price: Decimal
    new_price: Decimal
    days_remaining: int
    days_in_period: int
    unused_amount: Decimal
    proration_credit: Decimal
    new_charge: Decimal
    net_charge: Decimal
    billing_cycle_start: date
    billing_cycle_end: date


class ProrationAudit(BaseModel):
    """Proration audit record."""
    id: UUID
    company_id: UUID
    old_variant: VariantType
    new_variant: VariantType
    old_price: Decimal
    new_price: Decimal
    days_remaining: int
    days_in_period: int
    unused_amount: Decimal
    proration_amount: Decimal
    credit_applied: Decimal = Decimal("0.00")
    charge_applied: Decimal = Decimal("0.00")
    calculated_at: datetime


# ── Payment Failure Schemas ────────────────────────────────────────────────

class PaymentFailureInfo(BaseModel):
    """Payment failure information."""
    id: UUID
    company_id: UUID
    paddle_subscription_id: Optional[str] = None
    paddle_transaction_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None
    amount_attempted: Optional[Decimal] = None
    currency: str = "USD"
    service_stopped_at: Optional[datetime] = None
    service_resumed_at: Optional[datetime] = None
    notification_sent: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ── Client Refund Schemas ──────────────────────────────────────────────────

class ClientRefundCreate(BaseModel):
    """Request to create a client refund (PARWA clients to THEIR customers)."""
    ticket_id: Optional[UUID] = None
    amount: Decimal = Field(..., gt=0)
    currency: str = "USD"
    reason: str

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Ensure amount is positive and has max 2 decimal places."""
        if v <= 0:
            raise ValueError("Amount must be positive")
        # Round to 2 decimal places
        return v.quantize(Decimal("0.01"))


class ClientRefundInfo(BaseModel):
    """Client refund information."""
    id: UUID
    company_id: UUID
    ticket_id: Optional[UUID] = None
    amount: Decimal
    currency: str = "USD"
    reason: str
    status: str = "pending"
    processed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Overage Schemas ────────────────────────────────────────────────────────

class OverageChargeInfo(BaseModel):
    """Overage charge information."""
    id: UUID
    company_id: UUID
    date: date
    tickets_over_limit: int
    charge_amount: Decimal
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Limit Check Schemas ─────────────────────────────────────────────────────

class LimitCheckResult(BaseModel):
    """Result of a variant limit check."""
    allowed: bool
    limit_type: str  # tickets, team_members, ai_agents, voice_slots, kb_docs
    current_usage: int
    limit: int
    remaining: int
    message: Optional[str] = None


# ── Webhook Idempotency Schemas ────────────────────────────────────────────

class IdempotencyKeyInfo(BaseModel):
    """Idempotency key information."""
    id: UUID
    company_id: Optional[UUID] = None
    idempotency_key: str
    resource_type: str
    resource_id: Optional[str] = None
    response_status: Optional[int] = None
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


# ── Webhook Sequence Schemas ────────────────────────────────────────────────

class WebhookSequenceInfo(BaseModel):
    """Webhook sequence/ordering information."""
    id: UUID
    company_id: Optional[UUID] = None
    paddle_event_id: str
    event_type: str
    occurred_at: datetime
    processed_at: Optional[datetime] = None
    processing_order: Optional[int] = None
    status: str = "pending"
    created_at: datetime

    class Config:
        from_attributes = True


# ── Common Response Schemas ────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    code: Optional[str] = None
