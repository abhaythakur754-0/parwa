"""
Paddle Webhook Event Schemas

Pydantic models for all Paddle webhook events (25+ events).
Based on Paddle Billing API documentation.

Reference: https://developer.paddle.com/webhooks/overview
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


# ── Event Types Enum ───────────────────────────────────────────────────────

class PaddleEventType(str, Enum):
    """All Paddle webhook event types."""
    # Subscription events (7)
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_ACTIVATED = "subscription.activated"
    SUBSCRIPTION_CANCELED = "subscription.canceled"
    SUBSCRIPTION_PAST_DUE = "subscription.past_due"
    SUBSCRIPTION_PAUSED = "subscription.paused"
    SUBSCRIPTION_RESUMED = "subscription.resumed"

    # Transaction events (5)
    TRANSACTION_COMPLETED = "transaction.completed"
    TRANSACTION_PAID = "transaction.paid"
    TRANSACTION_PAYMENT_FAILED = "transaction.payment_failed"
    TRANSACTION_CANCELED = "transaction.canceled"
    TRANSACTION_UPDATED = "transaction.updated"

    # Customer events (3)
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    CUSTOMER_DELETED = "customer.deleted"

    # Price events (3)
    PRICE_CREATED = "price.created"
    PRICE_UPDATED = "price.updated"
    PRICE_DELETED = "price.deleted"

    # Discount events (3)
    DISCOUNT_CREATED = "discount.created"
    DISCOUNT_UPDATED = "discount.updated"
    DISCOUNT_DELETED = "discount.deleted"

    # Credit events (3)
    CREDIT_CREATED = "credit.created"
    CREDIT_UPDATED = "credit.updated"
    CREDIT_DELETED = "credit.deleted"

    # Adjustment events (2)
    ADJUSTMENT_CREATED = "adjustment.created"
    ADJUSTMENT_UPDATED = "adjustment.updated"

    # Report events (2)
    REPORT_CREATED = "report.created"
    REPORT_UPDATED = "report.updated"


# ── Base Event Models ──────────────────────────────────────────────────────

class PaddleEventData(BaseModel):
    """Base event data structure."""


class PaddleEvent(BaseModel):
    """Base Paddle webhook event."""
    event_id: str = Field(..., alias="event_id")
    event_type: PaddleEventType
    occurred_at: datetime
    notification_id: Optional[str] = None

    class Config:
        populate_by_name = True


# ── Subscription Event Data ────────────────────────────────────────────────

class PaddleSubscriptionItem(BaseModel):
    """Subscription item (line item)."""
    item_id: Optional[str] = None
    price_id: str
    quantity: int
    unit_price: Optional[Decimal] = None


class PaddleSubscriptionData(PaddleEventData):
    """Subscription data from Paddle."""
    id: str
    status: str
    customer_id: str
    items: List[PaddleSubscriptionItem]
    billing_cycle: Optional[Dict[str, Any]] = None
    next_billed_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    custom_data: Optional[Dict[str, Any]] = None


class SubscriptionCreatedEvent(PaddleEvent):
    """subscription.created event."""
    event_type: PaddleEventType = PaddleEventType.SUBSCRIPTION_CREATED
    data: PaddleSubscriptionData


class SubscriptionUpdatedEvent(PaddleEvent):
    """subscription.updated event."""
    event_type: PaddleEventType = PaddleEventType.SUBSCRIPTION_UPDATED
    data: PaddleSubscriptionData
    previous_attributes: Optional[Dict[str, Any]] = None


class SubscriptionActivatedEvent(PaddleEvent):
    """subscription.activated event."""
    event_type: PaddleEventType = PaddleEventType.SUBSCRIPTION_ACTIVATED
    data: PaddleSubscriptionData


class SubscriptionCanceledEvent(PaddleEvent):
    """subscription.canceled event."""
    event_type: PaddleEventType = PaddleEventType.SUBSCRIPTION_CANCELED
    data: PaddleSubscriptionData


class SubscriptionPastDueEvent(PaddleEvent):
    """subscription.past_due event."""
    event_type: PaddleEventType = PaddleEventType.SUBSCRIPTION_PAST_DUE
    data: PaddleSubscriptionData


class SubscriptionPausedEvent(PaddleEvent):
    """subscription.paused event."""
    event_type: PaddleEventType = PaddleEventType.SUBSCRIPTION_PAUSED
    data: PaddleSubscriptionData


class SubscriptionResumedEvent(PaddleEvent):
    """subscription.resumed event."""
    event_type: PaddleEventType = PaddleEventType.SUBSCRIPTION_RESUMED
    data: PaddleSubscriptionData


# ── Transaction Event Data ──────────────────────────────────────────────────

class PaddleTransactionDetails(BaseModel):
    """Transaction details from Paddle."""
    total: Decimal
    currency_code: str
    subtotal: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    discount: Optional[Decimal] = None


class PaddleTransactionData(PaddleEventData):
    """Transaction data from Paddle."""
    id: str
    status: str
    customer_id: Optional[str] = None
    subscription_id: Optional[str] = None
    invoice_id: Optional[str] = None
    details: Optional[PaddleTransactionDetails] = None
    billing_period: Optional[Dict[str, datetime]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    billed_at: Optional[datetime] = None


class TransactionCompletedEvent(PaddleEvent):
    """transaction.completed event."""
    event_type: PaddleEventType = PaddleEventType.TRANSACTION_COMPLETED
    data: PaddleTransactionData


class TransactionPaidEvent(PaddleEvent):
    """transaction.paid event."""
    event_type: PaddleEventType = PaddleEventType.TRANSACTION_PAID
    data: PaddleTransactionData


class TransactionPaymentFailedEvent(PaddleEvent):
    """transaction.payment_failed event."""
    event_type: PaddleEventType = PaddleEventType.TRANSACTION_PAYMENT_FAILED
    data: PaddleTransactionData
    error: Optional[Dict[str, Any]] = None


class TransactionCanceledEvent(PaddleEvent):
    """transaction.canceled event."""
    event_type: PaddleEventType = PaddleEventType.TRANSACTION_CANCELED
    data: PaddleTransactionData


class TransactionUpdatedEvent(PaddleEvent):
    """transaction.updated event."""
    event_type: PaddleEventType = PaddleEventType.TRANSACTION_UPDATED
    data: PaddleTransactionData


# ── Customer Event Data ─────────────────────────────────────────────────────

class PaddleCustomerData(PaddleEventData):
    """Customer data from Paddle."""
    id: str
    email: str
    name: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    custom_data: Optional[Dict[str, Any]] = None


class CustomerCreatedEvent(PaddleEvent):
    """customer.created event."""
    event_type: PaddleEventType = PaddleEventType.CUSTOMER_CREATED
    data: PaddleCustomerData


class CustomerUpdatedEvent(PaddleEvent):
    """customer.updated event."""
    event_type: PaddleEventType = PaddleEventType.CUSTOMER_UPDATED
    data: PaddleCustomerData
    previous_attributes: Optional[Dict[str, Any]] = None


class CustomerDeletedEvent(PaddleEvent):
    """customer.deleted event."""
    event_type: PaddleEventType = PaddleEventType.CUSTOMER_DELETED
    data: PaddleCustomerData


# ── Price Event Data ────────────────────────────────────────────────────────

class PaddlePriceData(PaddleEventData):
    """Price/variant data from Paddle."""
    id: str
    product_id: str
    name: Optional[str] = None
    unit_price: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PriceCreatedEvent(PaddleEvent):
    """price.created event."""
    event_type: PaddleEventType = PaddleEventType.PRICE_CREATED
    data: PaddlePriceData


class PriceUpdatedEvent(PaddleEvent):
    """price.updated event."""
    event_type: PaddleEventType = PaddleEventType.PRICE_UPDATED
    data: PaddlePriceData


class PriceDeletedEvent(PaddleEvent):
    """price.deleted event."""
    event_type: PaddleEventType = PaddleEventType.PRICE_DELETED
    data: PaddlePriceData


# ── Discount Event Data ─────────────────────────────────────────────────────

class PaddleDiscountData(PaddleEventData):
    """Discount data from Paddle."""
    id: str
    status: Optional[str] = None
    code: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DiscountCreatedEvent(PaddleEvent):
    """discount.created event."""
    event_type: PaddleEventType = PaddleEventType.DISCOUNT_CREATED
    data: PaddleDiscountData


class DiscountUpdatedEvent(PaddleEvent):
    """discount.updated event."""
    event_type: PaddleEventType = PaddleEventType.DISCOUNT_UPDATED
    data: PaddleDiscountData


class DiscountDeletedEvent(PaddleEvent):
    """discount.deleted event."""
    event_type: PaddleEventType = PaddleEventType.DISCOUNT_DELETED
    data: PaddleDiscountData


# ── Credit Event Data ────────────────────────────────────────────────────────

class PaddleCreditData(PaddleEventData):
    """Credit data from Paddle."""
    id: str
    customer_id: Optional[str] = None
    amount: Optional[str] = None
    currency_code: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class CreditCreatedEvent(PaddleEvent):
    """credit.created event."""
    event_type: PaddleEventType = PaddleEventType.CREDIT_CREATED
    data: PaddleCreditData


class CreditUpdatedEvent(PaddleEvent):
    """credit.updated event."""
    event_type: PaddleEventType = PaddleEventType.CREDIT_UPDATED
    data: PaddleCreditData


class CreditDeletedEvent(PaddleEvent):
    """credit.deleted event."""
    event_type: PaddleEventType = PaddleEventType.CREDIT_DELETED
    data: PaddleCreditData


# ── Adjustment Event Data ────────────────────────────────────────────────────

class PaddleAdjustmentData(PaddleEventData):
    """Adjustment data from Paddle."""
    id: str
    transaction_id: Optional[str] = None
    subscription_id: Optional[str] = None
    customer_id: Optional[str] = None
    amount: Optional[str] = None
    currency_code: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


class AdjustmentCreatedEvent(PaddleEvent):
    """adjustment.created event."""
    event_type: PaddleEventType = PaddleEventType.ADJUSTMENT_CREATED
    data: PaddleAdjustmentData


class AdjustmentUpdatedEvent(PaddleEvent):
    """adjustment.updated event."""
    event_type: PaddleEventType = PaddleEventType.ADJUSTMENT_UPDATED
    data: PaddleAdjustmentData


# ── Report Event Data ────────────────────────────────────────────────────────

class PaddleReportData(PaddleEventData):
    """Report data from Paddle."""
    id: str
    status: Optional[str] = None
    type: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReportCreatedEvent(PaddleEvent):
    """report.created event."""
    event_type: PaddleEventType = PaddleEventType.REPORT_CREATED
    data: PaddleReportData


class ReportUpdatedEvent(PaddleEvent):
    """report.updated event."""
    event_type: PaddleEventType = PaddleEventType.REPORT_UPDATED
    data: PaddleReportData


# ── Event Type Mapping ──────────────────────────────────────────────────────

EVENT_TYPE_TO_MODEL = {
    PaddleEventType.SUBSCRIPTION_CREATED: SubscriptionCreatedEvent,
    PaddleEventType.SUBSCRIPTION_UPDATED: SubscriptionUpdatedEvent,
    PaddleEventType.SUBSCRIPTION_ACTIVATED: SubscriptionActivatedEvent,
    PaddleEventType.SUBSCRIPTION_CANCELED: SubscriptionCanceledEvent,
    PaddleEventType.SUBSCRIPTION_PAST_DUE: SubscriptionPastDueEvent,
    PaddleEventType.SUBSCRIPTION_PAUSED: SubscriptionPausedEvent,
    PaddleEventType.SUBSCRIPTION_RESUMED: SubscriptionResumedEvent,
    PaddleEventType.TRANSACTION_COMPLETED: TransactionCompletedEvent,
    PaddleEventType.TRANSACTION_PAID: TransactionPaidEvent,
    PaddleEventType.TRANSACTION_PAYMENT_FAILED: TransactionPaymentFailedEvent,
    PaddleEventType.TRANSACTION_CANCELED: TransactionCanceledEvent,
    PaddleEventType.TRANSACTION_UPDATED: TransactionUpdatedEvent,
    PaddleEventType.CUSTOMER_CREATED: CustomerCreatedEvent,
    PaddleEventType.CUSTOMER_UPDATED: CustomerUpdatedEvent,
    PaddleEventType.CUSTOMER_DELETED: CustomerDeletedEvent,
    PaddleEventType.PRICE_CREATED: PriceCreatedEvent,
    PaddleEventType.PRICE_UPDATED: PriceUpdatedEvent,
    PaddleEventType.PRICE_DELETED: PriceDeletedEvent,
    PaddleEventType.DISCOUNT_CREATED: DiscountCreatedEvent,
    PaddleEventType.DISCOUNT_UPDATED: DiscountUpdatedEvent,
    PaddleEventType.DISCOUNT_DELETED: DiscountDeletedEvent,
    PaddleEventType.CREDIT_CREATED: CreditCreatedEvent,
    PaddleEventType.CREDIT_UPDATED: CreditUpdatedEvent,
    PaddleEventType.CREDIT_DELETED: CreditDeletedEvent,
    PaddleEventType.ADJUSTMENT_CREATED: AdjustmentCreatedEvent,
    PaddleEventType.ADJUSTMENT_UPDATED: AdjustmentUpdatedEvent,
    PaddleEventType.REPORT_CREATED: ReportCreatedEvent,
    PaddleEventType.REPORT_UPDATED: ReportUpdatedEvent,
}

# All supported event types (25+ events)
SUPPORTED_EVENT_TYPES = list(EVENT_TYPE_TO_MODEL.keys())
