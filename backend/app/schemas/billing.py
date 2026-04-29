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


# ── Enums ────────────────────────────────────────────────────────────────

class VariantType(str, Enum):
    """PARWA subscription variants."""
    MINI_PARWA = "mini_parwa"
    PARWA = "parwa"
    HIGH_PARWA = "high_parwa"


class SubscriptionStatus(str, Enum):
    """Subscription status values."""
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

class BillingFrequency(str, Enum):
    """Billing frequency."""
    MONTHLY = "monthly"
    YEARLY = "yearly"


VARIANT_LIMITS = {
    VariantType.MINI_PARWA: {
        "monthly_tickets": 2000,
        "ai_agents": 1,
        "team_members": 3,
        "voice_slots": 0,
        "kb_docs": 100,
        "price": Decimal("999.00"),
        "yearly_price": Decimal("9590.00"),
    },
    VariantType.PARWA: {
        "monthly_tickets": 5000,
        "ai_agents": 3,
        "team_members": 10,
        "voice_slots": 2,
        "kb_docs": 500,
        "price": Decimal("2499.00"),
        "yearly_price": Decimal("23990.00"),
    },
    VariantType.HIGH_PARWA: {
        "monthly_tickets": 15000,
        "ai_agents": 5,
        "team_members": 25,
        "voice_slots": 5,
        "kb_docs": 2000,
        "price": Decimal("3999.00"),
        "yearly_price": Decimal("38390.00"),
    },
}


# ── Industry Add-Ons (Day 3: V1-V10) ───────────────────────────────

INDUSTRY_ADD_ONS = {
    "ecommerce": {
        "display_name": "E-commerce",
        "price_monthly": Decimal("79.00"),
        "yearly_price": Decimal("790.00"),
        "tickets_added": 500,
        "kb_docs_added": 50,
        "description": "Order tracking, refund handling, product FAQ",
    },
    "saas": {
        "display_name": "SaaS",
        "price_monthly": Decimal("59.00"),
        "yearly_price": Decimal("590.00"),
        "tickets_added": 300,
        "kb_docs_added": 30,
        "description": "Technical support, bug triage, feature requests",
    },
    "logistics": {
        "display_name": "Logistics",
        "price_monthly": Decimal("69.00"),
        "yearly_price": Decimal("690.00"),
        "tickets_added": 400,
        "kb_docs_added": 40,
        "description": "Shipment tracking, delivery updates, returns",
    },
    "others": {
        "display_name": "Others",
        "price_monthly": Decimal("39.00"),
        "yearly_price": Decimal("390.00"),
        "tickets_added": 200,
        "kb_docs_added": 20,
        "description": "General support, FAQ, escalation",
    },
}


class IndustryAddOnStatus(str, Enum):
    """Status of a company's industry add-on."""
    ACTIVE = "active"
    INACTIVE = "inactive"      # Scheduled for removal at period end
    ARCHIVED = "archived"      # Previously removed, data archived


class CompanyVariantInfo(BaseModel):
    """Company variant add-on information (Day 3: V4)."""
    id: UUID
    company_id: UUID
    variant_id: str  # ecommerce, saas, logistics, others
    display_name: str
    status: IndustryAddOnStatus = IndustryAddOnStatus.ACTIVE
    price_per_month: Decimal
    tickets_added: int
    kb_docs_added: int
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    paddle_subscription_item_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyVariantCreate(BaseModel):
    """Request to add an industry variant add-on (Day 3: V2)."""
    variant_id: str

    @field_validator("variant_id")
    @classmethod
    def validate_variant_id(cls, v: str) -> str:
        v_lower = v.lower().strip()
        valid = {"ecommerce", "saas", "logistics", "others"}
        if v_lower not in valid:
            raise ValueError(
                f"Invalid variant_id '{v}'. Must be one of: {
                    ', '.join(
                        sorted(valid))}")
        return v_lower


class CompanyVariantList(BaseModel):
    """List of company variant add-ons."""
    variants: List[CompanyVariantInfo]
    total: int


class VariantLimits(BaseModel):
    """Feature limits for a variant."""
    variant: VariantType
    monthly_tickets: int
    ai_agents: int
    team_members: int
    voice_slots: int
    kb_docs: int
    price: Decimal
    yearly_price: Optional[Decimal] = None


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

    # Day 2 additions
    billing_frequency: BillingFrequency = BillingFrequency.MONTHLY
    pending_downgrade_tier: Optional[str] = None
    previous_tier: Optional[str] = None
    days_in_period: Optional[int] = None

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


# ── Effective Limits (Day 3: V6 - with stacking) ────────────────────

class EffectiveLimitsInfo(BaseModel):
    """Effective limits after stacking base plan + active add-ons."""
    base_monthly_tickets: int
    addon_tickets: int
    effective_monthly_tickets: int
    base_ai_agents: int
    addon_ai_agents: int  # Always 0 (agents don't stack)
    effective_ai_agents: int
    base_team_members: int
    addon_team_members: int  # Always 0 (team don't stack)
    effective_team_members: int
    base_voice_slots: int
    addon_voice_slots: int  # Always 0 (voice doesn't stack)
    effective_voice_slots: int
    base_kb_docs: int
    addon_kb_docs: int
    effective_kb_docs: int
    active_addons: List[str]


# ── Day 4 Schemas: Cancel Confirmation, Data Retention, Re-subscription ──

class CancelFeedbackRequest(BaseModel):
    """C1: Step 1 of cancel confirmation flow — feedback form."""
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Why are you leaving?")
    feedback: Optional[str] = Field(
        None, max_length=1000, description="Additional feedback")


class SaveOfferResponse(BaseModel):
    """C1: Save offer — 20% off next 3 months."""
    discount_percentage: int = 20
    discount_months: int = 3
    message: str = (
        "Stay with us! Get 20% off your next 3 months. "
        "Your discount will be applied to your next 3 invoices."
    )
    original_price: Optional[Decimal] = None
    discounted_price: Optional[Decimal] = None


class CancelConfirmRequest(BaseModel):
    """C1: Final cancel confirmation."""
    effective_immediately: bool = False
    accept_data_retention: bool = Field(
        False,
        description="Confirm understanding that data will be retained for 30 days after service stop.",
    )


class RetentionStatusResponse(BaseModel):
    """C4: Data retention status for a company."""
    status: str  # active, in_retention, retention_expired, no_subscription
    service_stopped_at: Optional[str] = None
    deletion_date: Optional[str] = None
    days_remaining: Optional[int] = None
    retention_period_days: int = 30
    message: Optional[str] = None


class DataExportRequestResponse(BaseModel):
    """C5: Data export request response."""
    export_id: Optional[str] = None
    status: str  # processing, completed, failed
    requested_at: Optional[str] = None
    message: str


class DataExportDownloadResponse(BaseModel):
    """C5: Data export download info."""
    export_id: str
    status: str
    file_size_bytes: Optional[int] = None
    format: str = "zip"
    expires_at: Optional[str] = None


class ResubscriptionRequest(BaseModel):
    """R1/R3: Re-subscription request."""
    variant: VariantType
    payment_method_id: Optional[str] = None
    billing_frequency: BillingFrequency = BillingFrequency.MONTHLY
    restore_data: bool = Field(
        True,
        description="Whether to restore archived data (only within retention period).",
    )


class ResubscriptionResponse(BaseModel):
    """R1/R2/R3: Re-subscription response."""
    subscription: SubscriptionInfo
    data_restored: bool
    message: str
    # "within_retention" or "after_retention"
    retention_status: Optional[str] = None


class PaymentMethodUpdateRequest(BaseModel):
    """G4: Payment method update request."""
    return_url: Optional[str] = Field(
        None,
        description="URL to redirect to after payment method update in Paddle portal.",
    )


class PaymentMethodUpdateResponse(BaseModel):
    """G4: Payment method update response."""
    paddle_portal_url: Optional[str] = None
    message: str


class PaymentFailureStatusResponse(BaseModel):
    """G1/G2: Payment failure status with 7-day window info."""
    has_active_failure: bool
    failure_id: Optional[str] = None
    failure_reason: Optional[str] = None
    service_stopped_at: Optional[str] = None
    days_since_failure: Optional[int] = None
    days_remaining_window: Optional[int] = None
    window_expires_at: Optional[str] = None
    message: str


# ── Common Response Schemas ────────────────────────────────────────────────

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    code: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# Day 6 Schemas: Trial, Pause, Promo, Analytics, Amendments, Enterprise,
#                Dashboard (DI1-DI5)
# ═══════════════════════════════════════════════════════════════════════


# ── MF1: Trial Schemas ────────────────────────────────────────────────────

class TrialStartRequest(BaseModel):
    """MF1: Request to start a trial."""
    trial_days: int = Field(default=14, ge=1, le=60)


class TrialStatusResponse(BaseModel):
    """MF1: Trial status response."""
    status: str  # none, not_started, active, expired
    trial_ends_at: Optional[str] = None
    trial_remaining_days: Optional[int] = None


# ── MF2: Pause/Resume Schemas ─────────────────────────────────────────────

class PauseResponse(BaseModel):
    """MF2: Pause response."""
    status: str
    paused_at: Optional[str] = None
    max_resume_date: Optional[str] = None


class ResumeResponse(BaseModel):
    """MF2: Resume response."""
    status: str
    resumed_at: Optional[str] = None
    pause_duration_days: Optional[int] = None
    period_end_extended_by_days: Optional[int] = None


# ── MF3: Promo Code Schemas ───────────────────────────────────────────────

class PromoApplyRequest(BaseModel):
    """MF3: Request to apply a promo code."""
    code: str
    tier: Optional[str] = None


class PromoValidateResponse(BaseModel):
    """MF3: Promo code validation response."""
    valid: bool
    code: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[str] = None
    error: Optional[str] = None


class PromoCodeInfo(BaseModel):
    """MF3: Promo code info for admin list."""
    id: str
    code: str
    discount_type: str
    discount_value: str
    max_uses: Optional[int] = None
    used_count: int = 0
    is_active: bool = True


class PromoCodeCreateRequest(BaseModel):
    """MF3: Admin create promo code."""
    code: str
    discount_type: str = Field(..., pattern="^(percentage|fixed)$")
    discount_value: Decimal = Field(..., gt=0)
    max_uses: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    applies_to_tiers: Optional[List[str]] = None


# ── MF4: Currency Schemas ─────────────────────────────────────────────────

class CurrencyResponse(BaseModel):
    """MF4: Company currency response."""
    currency: str = "USD"


# ── MF5: Timezone Schemas ─────────────────────────────────────────────────

class TimezoneResponse(BaseModel):
    """MF5: Billing timezone display settings."""
    timezone: str = "UTC"


# ── MF6: Enterprise Billing Schemas ───────────────────────────────────────

class EnterpriseBillingRequest(BaseModel):
    """MF6: Enable manual billing request."""
    company_id: str


class ManualInvoiceRequest(BaseModel):
    """MF6: Create manual invoice request."""
    company_id: str
    amount: Decimal = Field(..., gt=0)
    due_date: Optional[datetime] = None
    line_items: Optional[List[Dict[str, Any]]] = None


# ── MF7: Invoice Amendment Schemas ────────────────────────────────────────

class InvoiceAmendmentRequest(BaseModel):
    """MF7: Create amendment request."""
    new_amount: Decimal = Field(..., ge=0)
    amendment_type: str = Field(..., pattern="^(credit|additional_charge)$")
    reason: str


class InvoiceAmendmentInfo(BaseModel):
    """MF7: Invoice amendment info."""
    id: str
    invoice_id: str
    original_amount: str
    new_amount: str
    amendment_type: str
    reason: str
    approved_by: Optional[str] = None
    created_at: Optional[str] = None


# ── MF8-MF11: Analytics Schemas ───────────────────────────────────────────

class SpendingSummary(BaseModel):
    """MF8: Spending summary."""
    month: str
    base_plan: str
    overage_cost: str
    variant_costs: str
    total_spend: str
    projected_next_month: str


class ChannelBreakdown(BaseModel):
    """MF8: Channel breakdown."""
    month: str
    channels: Dict[str, Any]


class SpendingTrend(BaseModel):
    """MF8: Monthly spending trend item."""
    month: str
    tickets_used: int
    overage_cost: str


class BudgetAlert(BaseModel):
    """MF9: Budget alert status."""
    usage_percentage: float
    tickets_used: int
    ticket_limit: int
    thresholds_triggered: List[int]
    is_over_limit: bool


class VoiceUsageInfo(BaseModel):
    """MF10: Voice usage info."""
    period: str
    voice_minutes_used: float
    status: str


class SmsUsageInfo(BaseModel):
    """MF11: SMS usage info."""
    period: str
    sms_count: int
    status: str


# ── DI1-DI5: Dashboard Schemas ─────────────────────────────────────────────

class DashboardSummary(BaseModel):
    """DI1: Complete billing dashboard data."""
    subscription_status: Optional[str] = None
    current_plan: Optional[str] = None
    billing_frequency: Optional[str] = None
    current_period_end: Optional[str] = None
    usage_summary: Optional[Dict[str, Any]] = None
    spending_summary: Optional[Dict[str, Any]] = None
    budget_alert: Optional[Dict[str, Any]] = None
    trial_status: Optional[Dict[str, Any]] = None
    pause_status: Optional[Dict[str, Any]] = None


class PlanComparison(BaseModel):
    """DI2: Plan comparison for all tiers."""
    plans: List[Dict[str, Any]]


class VariantCatalogItem(BaseModel):
    """DI3: Variant catalog item."""
    variant_id: str
    display_name: str
    description: Optional[str] = None
    price_monthly: str
    price_yearly: str
    tickets_added: int
    kb_docs_added: int
    is_active: bool


class VariantCatalog(BaseModel):
    """DI3: Variant catalog response."""
    catalog: List[VariantCatalogItem]
    total: int
    active_count: int


class EnhancedInvoiceHistory(BaseModel):
    """DI4: Enhanced invoice history with YTD totals."""
    invoices: List[Dict[str, Any]]
    ytd_total: str
    pagination: Dict[str, Any]


class PaymentSchedule(BaseModel):
    """DI5: Payment schedule info."""
    next_payment_date: Optional[str] = None
    next_payment_amount: Optional[str] = None
    upcoming_charges: List[Dict[str, Any]]
    projected_monthly_total: Optional[str] = None
