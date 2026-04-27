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
    Boolean, Column, Date, DateTime, Integer, JSON, Numeric, String, Text, ForeignKey, Index
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


# ── Data Export Model (Day 4: C5) ───────────────────────────────────

class DataExport(Base):
    """
    Data export records for canceled subscriptions.

    C5: Tracks async data export jobs. When a customer cancels,
    they can export all company data as a ZIP file (JSON + CSV).
    """
    __tablename__ = "data_exports"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), nullable=False, default="processing")  # processing/completed/failed/expired
    format = Column(String(20), default="zip")
    file_size_bytes = Column(Integer, nullable=True)
    export_data_json = Column(Text, nullable=True)  # Temporary storage for export data
    error_message = Column(Text, nullable=True)
    requested_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    company = relationship("Company", back_populates="data_exports")


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
    grace_period_ends_at = Column(DateTime, nullable=True)  # 7-day grace period deadline
    notification_sent = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # Relationships
    company = relationship("Company", back_populates="payment_failures")


# ── Company Variant Add-On Model (Day 3: V1) ──────────────────────────

class CompanyVariant(Base):
    """Industry variant add-on for a company.

    Day 3 V1: Tracks which industry add-ons (E-commerce, SaaS, Logistics, Others)
    a company has purchased. Each add-on adds ticket and KB doc allocations
    to the base plan. Agents, team members, and voice slots do NOT stack.

    Lifecycle:
    - Add: Immediate activation, prorated charge for remaining period
    - Remove: Takes effect at next period end (status='inactive')
    - Archive: At period end cron, KB data archived (not deleted)
    - Restore: Re-add from archived, creates new Paddle item
    """
    __tablename__ = "company_variants"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=False, index=True)
    variant_id = Column(String(50), nullable=False)  # ecommerce, saas, logistics, others
    display_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active, inactive, archived
    price_per_month = Column(Numeric(10, 2), nullable=False)
    tickets_added = Column(Integer, nullable=False, default=0)
    kb_docs_added = Column(Integer, nullable=False, default=0)
    activated_at = Column(DateTime, nullable=True)
    deactivated_at = Column(DateTime, nullable=True)
    paddle_subscription_item_id = Column(String(255), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Chargeback Model (Day 5) ──────────────────────────────────────────────────

class Chargeback(Base):
    """Track chargebacks from payment processor.

    Status lifecycle: received → under_review → won/lost
    """
    __tablename__ = "chargebacks"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    paddle_transaction_id = Column(String(255), nullable=True)
    paddle_chargeback_id = Column(String(255), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    currency = Column(String(3), default="USD")
    reason = Column(String(100), nullable=True)
    status = Column(String(20), default="received")  # received/under_review/won/lost
    service_stopped_at = Column(DateTime, nullable=True)
    notification_sent_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


# ── Credit Balance Model (Day 5: RF3) ────────────────────────────────────────

class CreditBalance(Base):
    """Customer credit balance system.

    Sources: refund, promo, goodwill, cooling_off
    Status lifecycle: available → partially_used → fully_used/expired
    """
    __tablename__ = "credit_balances"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(10, 2), default=Decimal("0.00"))  # BC-002
    currency = Column(String(3), default="USD")
    source = Column(String(30), nullable=False)  # refund/promo/goodwill/cooling_off
    description = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    applied_to_invoice_id = Column(String(36), nullable=True)
    applied_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="available")  # available/partially_used/fully_used/expired
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


# ── Spending Cap Model (Day 5: SC1) ──────────────────────────────────────────

class SpendingCap(Base):
    """Customer-configurable overage spending caps.

    NULL max_overage_amount means no cap (default).
    Alert thresholds stored as JSON string, e.g. '[50,75,90]'.
    """
    __tablename__ = "spending_caps"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    max_overage_amount = Column(Numeric(10, 2), nullable=True)  # NULL=no cap (BC-002)
    alert_thresholds = Column(Text, nullable=True)  # JSON: '[50,75,90]'
    soft_cap_alerts_sent = Column(Text, nullable=True)  # JSON: tracking sent alerts
    is_active = Column(Boolean, default=False)
    acknowledged_warning = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


# ── Dead Letter Webhook Model (Day 5: WH3) ───────────────────────────────────

class DeadLetterWebhook(Base):
    """Failed webhook processing queue.

    Stores webhooks that failed processing for later retry or manual inspection.
    Status lifecycle: pending → retrying → processed/discarded
    """
    __tablename__ = "dead_letter_webhooks"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=True, index=True)
    provider = Column(String(50), default="paddle")
    event_id = Column(String(255), nullable=True)
    event_type = Column(String(100), nullable=True)
    payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending/retrying/processed/discarded
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


# ── Webhook Health Stat Model (Day 5: WH2) ──────────────────────────────────

class WebhookHealthStat(Base):
    """Webhook health monitoring.

    Daily aggregation of webhook processing metrics per provider.
    """
    __tablename__ = "webhook_health_stats"

    id = Column(String(36), primary_key=True, default=_uuid)
    provider = Column(String(50), default="paddle")
    date = Column(Date, nullable=True)
    events_received = Column(Integer, default=0)
    events_processed = Column(Integer, default=0)
    events_failed = Column(Integer, default=0)
    avg_processing_time_ms = Column(Numeric(10, 2), default=Decimal("0.00"))
    failure_rate = Column(Numeric(5, 4), default=Decimal("0.0000"))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ── Refund Audit Model (Day 5: RF5) ──────────────────────────────────────────

class RefundAudit(Base):
    """Refund audit trail.

    Tracks all refund requests with dual-approval for amounts > $500.
    Status lifecycle: pending → approved/rejected → processed/failed
    """
    __tablename__ = "refund_audits"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refund_type = Column(String(20), nullable=False)  # full/partial/credit/cooling_off
    original_amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    refund_amount = Column(Numeric(10, 2), nullable=False)  # BC-002
    reason = Column(Text, nullable=False)
    approver_id = Column(String(36), nullable=True)
    approver_name = Column(String(255), nullable=True)
    second_approver_id = Column(String(36), nullable=True)  # for amounts > $500
    second_approver_name = Column(String(255), nullable=True)
    paddle_refund_id = Column(String(255), nullable=True)
    credit_balance_id = Column(String(36), nullable=True)
    status = Column(String(20), default="pending")  # pending/approved/rejected/processed/failed
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


# ═══════════════════════════════════════════════════════════════════════
# Day 6 Models: PromoCode, CompanyPromoUse, InvoiceAmendment, PauseRecord
# ═══════════════════════════════════════════════════════════════════════


# ── Promo Code Model (Day 6: MF3) ──────────────────────────────────────

class PromoCode(Base):
    """MF3: Discount/promo code system."""
    __tablename__ = "promo_codes"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True)
    discount_type = Column(String(20), nullable=False)  # 'percentage' or 'fixed'
    discount_value = Column(Numeric(10, 2), nullable=False)
    max_uses = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    applies_to_tiers = Column(JSON, nullable=True)  # list of tier codes, null = all tiers
    created_by = Column(String, nullable=True)  # admin user id
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.utcnow())


# ── Company Promo Use Model (Day 6: MF3) ──────────────────────────────

class CompanyPromoUse(Base):
    """MF3: Track which companies used which promo codes."""
    __tablename__ = "company_promo_uses"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=False, index=True)
    promo_code_id = Column(String(36), nullable=False)
    applied_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    invoice_id = Column(String(36), nullable=True)
    discount_amount = Column(Numeric(10, 2), default=Decimal("0.00"))


# ── Invoice Amendment Model (Day 6: MF7) ──────────────────────────────

class InvoiceAmendment(Base):
    """MF7: Invoice amendment records."""
    __tablename__ = "invoice_amendments"

    id = Column(String(36), primary_key=True, default=_uuid)
    invoice_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), nullable=False, index=True)
    original_amount = Column(Numeric(10, 2), nullable=False)
    new_amount = Column(Numeric(10, 2), nullable=False)
    amendment_type = Column(String(20), nullable=False)  # 'credit' or 'additional_charge'
    reason = Column(Text, nullable=False)
    approved_by = Column(String(36), nullable=True)  # admin who approved
    paddle_credit_note_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow())


# ── Pause Record Model (Day 6: MF2) ──────────────────────────────────

class PauseRecord(Base):
    """MF2: Subscription pause/resume tracking."""
    __tablename__ = "pause_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=False, index=True)
    subscription_id = Column(String(36), nullable=False)
    paused_at = Column(DateTime(timezone=True), nullable=False)
    resumed_at = Column(DateTime(timezone=True), nullable=True)
    pause_duration_days = Column(Integer, nullable=True)
    max_pause_days = Column(Integer, default=30)
    period_end_extension_days = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow())


# ── Convenience Functions ───────────────────────────────────────────────────

def get_variant_limits(variant_name: str) -> Optional[dict]:
    """
    Get variant limits by name.
    
    Returns dict with limits or None if not found.
    """
    # Hardcoded fallback (matches migration data)
    LIMITS = {
        "mini_parwa": {
            "monthly_tickets": 2000,
            "ai_agents": 1,
            "team_members": 3,
            "voice_slots": 0,
            "kb_docs": 100,
            "price_monthly": Decimal("999.00"),
            "price_yearly": Decimal("9590.40"),  # 999 * 12 * 0.80 = 9590.40 (20% discount)
        },
        "parwa": {
            "monthly_tickets": 5000,
            "ai_agents": 3,
            "team_members": 10,
            "voice_slots": 2,
            "kb_docs": 500,
            "price_monthly": Decimal("2499.00"),
            "price_yearly": Decimal("23990.40"),  # 2499 * 12 * 0.80 = 23990.40 (20% discount)
        },
        "high_parwa": {
            "monthly_tickets": 15000,
            "ai_agents": 5,
            "team_members": 25,
            "voice_slots": 5,
            "kb_docs": 2000,
            "price_monthly": Decimal("3999.00"),
            "price_yearly": Decimal("38390.40"),  # 3999 * 12 * 0.80 = 38390.40 (20% discount)
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
