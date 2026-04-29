"""
PARWA Test Configuration — Mock external dependencies for unit tests.

Mocks modules that don't exist on disk (database, shared) and provides
test settings for app.config so no real DB/Redis/API keys are needed.

CRITICAL: Must NOT mock app.config as a standalone module type BEFORE
the real app package is discovered by Python's import system.
Instead, we set env vars and let app.config's Settings class validate
against them, then override get_settings to return a mock.
"""

import pytest
from decimal import Decimal as _Decimal
import sys
import types
import os
from unittest.mock import MagicMock

# ════════════════════════════════════════════════════════════════════════
# Phase 1: Set required env vars BEFORE any app imports
# ════════════════════════════════════════════════════════════════════════
if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-32c"
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///test.db"
if not os.environ.get("JWT_SECRET_KEY"):
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing-32c"
if not os.environ.get("DATA_ENCRYPTION_KEY"):
    os.environ["DATA_ENCRYPTION_KEY"] = "test-encryption-key-for-testing-32"
if not os.environ.get("ENVIRONMENT"):
    os.environ["ENVIRONMENT"] = "test"
if not os.environ.get("REFRESH_TOKEN_PEPPER"):
    os.environ["REFRESH_TOKEN_PEPPER"] = "test-refresh-token-pepper-for-testing-32c"


# ════════════════════════════════════════════════════════════════════════
# Phase 2: Mock modules that DON'T exist on disk
# ════════════════════════════════════════════════════════════════════════

_mock_db = MagicMock()

# ── database layer (doesn't exist as real package) ──────────────────
_fake_database = types.ModuleType("database")
_fake_base = types.ModuleType("database.base")
_fake_models = types.ModuleType("database.models")
_fake_jarvis_models = types.ModuleType("database.models.jarvis")
_fake_core_models = types.ModuleType("database.models.core")
_fake_onboarding_models = types.ModuleType("database.models.onboarding")


_fake_base.Base = MagicMock()
_fake_base.engine = MagicMock()
_fake_base.SessionLocal = MagicMock(return_value=_mock_db)


def _fake_get_db():
    """Fake get_db generator for tests."""
    try:
        yield _mock_db
    finally:
        pass


_fake_base.get_db = _fake_get_db
_fake_base.get_tenant_db = _fake_get_db
_fake_base.init_db = MagicMock()
_fake_base.TenantSession = MagicMock()
_fake_core_models.__all__ = []
_fake_onboarding_models.__all__ = []

# User and Company are imported from database.models.core by deps.py
_MockUser = type(
    "User", (), {"id": None, "company_id": None, "role": None, "is_active": True}
)
_MockCompany = type(
    "Company",
    (),
    {
        "id": None,
        "name": None,
        "industry": None,
        "subscription_tier": None,
        "subscription_status": "active",
    },
)
setattr(_fake_core_models, "User", _MockUser)
setattr(_fake_core_models, "Company", _MockCompany)
setattr(_fake_core_models, "RefreshToken", MagicMock(name="RefreshToken"))
setattr(_fake_core_models, "OAuthAccount", MagicMock(name="OAuthAccount"))

for model_name in [
    "JarvisSession",
    "JarvisMessage",
    "JarvisKnowledgeUsed",
    "JarvisActionTicket",
    "Ticket",
    "TicketMessage",
    "TicketIntent",
    "ClassificationCorrection",
    "TicketPriority",
    "TicketStatusChange",
    "TicketMerge",
    "Customer",
    "CustomerChannel",
    "OnboardingSession",
    "AITokenBudget",
    "Subscription",
    "OverageCharge",
    "OverageRecord",
    "Invoice",
    "AuditEntry",
    "Webhook",
    "WebhookDelivery",
]:
    setattr(_fake_jarvis_models, model_name, MagicMock(name=model_name))

for model_name in ["DocumentChunk", "KnowledgeDocument"]:
    setattr(_fake_onboarding_models, model_name, MagicMock(name=model_name))

# ── Attribute chain support for ORM mock queries ─────────────────


class _AttrChainer:
    """Supports SQLAlchemy-style attribute chaining on mock model classes.
    e.g., EmailDeliveryEvent.created_at.desc() for order_by() calls,
    Model.severity.in_([...]) for filter expressions.
    """

    def __getattr__(self, name):
        return _AttrChainer()

    def desc(self):
        return self

    def asc(self):
        return self

    def __ge__(self, other):
        return True  # Always pass for mock filter comparisons

    def __le__(self, other):
        return True

    def __gt__(self, other):
        return True  # Support > comparisons

    def __lt__(self, other):
        return False  # Support < comparisons (for expires_at < now etc.)

    def __eq__(self, other):
        return True  # Filters always match in mocks

    def __ne__(self, other):
        return False

    def in_(self, *args):
        return self  # Support .in_() for filter expressions

    def isnot(self, *args):
        return self  # Support .isnot() for filter expressions

    def is_(self, *args):
        return self  # Support .is_(None) for filter expressions

    def contains(self, *args):
        return self  # Support .contains() for JSON column queries

    def __bool__(self):
        return True

    def __or__(self, other):
        return self  # Support | (SQLAlchemy OR) for filter expressions

    def __and__(self, other):
        return self  # Support & (SQLAlchemy AND) for filter expressions

    def nulls_last(self):
        return self  # Support .nulls_last() for order_by() calls


# ── Common mock model helpers (used across multiple model modules) ──


def _mock_model_init(self, **kwargs):
    for k, v in kwargs.items():
        setattr(self, k, v)


def _mock_model_to_dict(self):
    return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


# ── database.models.billing and billing_extended (Day 1/2 billing) ──
_fake_billing_models = types.ModuleType("database.models.billing")
_fake_billing_extended = types.ModuleType("database.models.billing_extended")

_MockSubscription = type(
    "Subscription",
    (object,),
    {
        "__tablename__": "subscriptions",
        "id": None,
        "company_id": None,
        "tier": None,
        "status": _AttrChainer(),
        "paddle_subscription_id": None,
        "current_period_start": _AttrChainer(),
        "current_period_end": _AttrChainer(),
        "cancel_at_period_end": _AttrChainer(),
        "billing_frequency": "monthly",
        "pending_downgrade_tier": _AttrChainer(),
        "pending_downgrade_at": _AttrChainer(),
        "downgrade_executed_at": None,
        "previous_tier": None,
        "trial_days": 0,
        "trial_started_at": _AttrChainer(),
        "trial_ends_at": _AttrChainer(),
        "days_in_period": 30,
        "metadata_json": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
    },
)
_MockInvoice = type(
    "Invoice",
    (object,),
    {
        "__tablename__": "invoices",
        "id": None,
        "company_id": None,
        "paddle_invoice_id": None,
        "amount": None,
        "currency": "USD",
        "status": "draft",
        "invoice_date": None,
        "paid_at": None,
        "__init__": _mock_model_init,
    },
)
_MockCancellationRequest = type(
    "CancellationRequest",
    (object,),
    {
        "__tablename__": "cancellation_requests",
        "id": None,
        "company_id": None,
        "user_id": None,
        "reason": None,
        "status": "scheduled",
        "__init__": _mock_model_init,
    },
)
_MockPaymentMethod = type(
    "PaymentMethod",
    (object,),
    {
        "__tablename__": "payment_methods",
        "id": None,
        "company_id": None,
        "__init__": _mock_model_init,
    },
)
_MockProrationAudit = type(
    "ProrationAudit",
    (object,),
    {
        "__tablename__": "proration_audits",
        "id": None,
        "company_id": None,
        "old_variant": None,
        "new_variant": None,
        "old_price": None,
        "new_price": None,
        "days_remaining": None,
        "days_in_period": None,
        "unused_amount": None,
        "proration_amount": None,
        "credit_applied": None,
        "charge_applied": None,
        "billing_cycle_start": None,
        "billing_cycle_end": None,
        "calculated_at": _AttrChainer(),
        "__init__": _mock_model_init,
    },
)


def _company_variant_init(self, **kwargs):
    """CompanyVariant init that sets proper defaults for AttrChainer fields."""
    import uuid as _uuid

    _mock_model_init(self, **kwargs)
    # Set defaults for fields that use _AttrChainer on the class
    # so instances get proper Python types (not _AttrChainer) for Pydantic
    # validation
    if "id" not in kwargs:
        self.id = str(_uuid.uuid4())
    if "deactivated_at" not in kwargs:
        self.deactivated_at = None
    if "activated_at" not in kwargs:
        self.activated_at = None
    if "created_at" not in kwargs:
        self.created_at = None


_MockCompanyVariant = type(
    "CompanyVariant",
    (object,),
    {
        "__tablename__": "company_variants",
        "id": None,
        "company_id": None,
        "variant_id": None,
        "display_name": None,
        "status": _AttrChainer(),
        "price_per_month": None,
        "tickets_added": 0,
        "kb_docs_added": 0,
        "activated_at": _AttrChainer(),
        "deactivated_at": _AttrChainer(),
        "paddle_subscription_item_id": None,
        "metadata_json": None,
        "created_at": _AttrChainer(),
        "__init__": _company_variant_init,
    },
)
setattr(_fake_billing_models, "Subscription", _MockSubscription)
setattr(_fake_billing_models, "Invoice", _MockInvoice)
setattr(_fake_billing_models, "CancellationRequest", _MockCancellationRequest)
setattr(_fake_billing_extended, "PaymentMethod", _MockPaymentMethod)
setattr(_fake_billing_extended, "ProrationAudit", _MockProrationAudit)
setattr(_fake_billing_extended, "CompanyVariant", _MockCompanyVariant)

# ── Day 5 models: chargeback, credit_balance, spending_cap, etc. ──
_MockChargeback = type(
    "Chargeback",
    (object,),
    {
        "__tablename__": "chargebacks",
        "id": None,
        "company_id": None,
        "paddle_transaction_id": None,
        "paddle_chargeback_id": None,
        "amount": None,
        "currency": "USD",
        "reason": None,
        "status": "received",
        "service_stopped_at": None,
        "notification_sent_at": None,
        "resolved_at": None,
        "resolution_notes": None,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockCreditBalance = type(
    "CreditBalance",
    (object,),
    {
        "__tablename__": "credit_balances",
        "id": None,
        "company_id": None,
        "amount": _AttrChainer(),
        "currency": "USD",
        "source": None,
        "description": None,
        "expires_at": _AttrChainer(),
        "applied_to_invoice_id": None,
        "applied_at": None,
        "status": _AttrChainer(),
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockSpendingCap = type(
    "SpendingCap",
    (object,),
    {
        "__tablename__": "spending_caps",
        "id": None,
        "company_id": None,
        "max_overage_amount": None,
        "alert_thresholds": None,
        "soft_cap_alerts_sent": None,
        "is_active": _AttrChainer(),
        "acknowledged_warning": False,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockDeadLetterWebhook = type(
    "DeadLetterWebhook",
    (object,),
    {
        "__tablename__": "dead_letter_webhooks",
        "id": None,
        "company_id": None,
        "provider": "paddle",
        "event_id": None,
        "event_type": None,
        "payload": None,
        "error_message": None,
        "status": _AttrChainer(),
        "retry_count": 0,
        "max_retries": 3,
        "next_retry_at": None,
        "last_error": None,
        "processed_at": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockWebhookHealthStat = type(
    "WebhookHealthStat",
    (object,),
    {
        "__tablename__": "webhook_health_stats",
        "id": None,
        "provider": "paddle",
        "date": None,
        "events_received": 0,
        "events_processed": 0,
        "events_failed": 0,
        "avg_processing_time_ms": None,
        "failure_rate": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockRefundAudit = type(
    "RefundAudit",
    (object,),
    {
        "__tablename__": "refund_audits",
        "id": None,
        "company_id": None,
        "refund_type": None,
        "original_amount": None,
        "refund_amount": None,
        "reason": None,
        "approver_id": None,
        "approver_name": None,
        "second_approver_id": None,
        "second_approver_name": None,
        "paddle_refund_id": None,
        "credit_balance_id": None,
        "status": "pending",
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockWebhookSequence = type(
    "WebhookSequence",
    (object,),
    {
        "__tablename__": "webhook_sequences",
        "id": None,
        "company_id": None,
        "paddle_event_id": None,
        "event_type": None,
        "occurred_at": _AttrChainer(),
        "processed_at": None,
        "processing_order": None,
        "status": _AttrChainer(),
        "error_message": None,
        "retry_count": 0,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockUsageRecord = type(
    "UsageRecord",
    (object,),
    {
        "__tablename__": "usage_records",
        "id": None,
        "company_id": None,
        "record_date": None,
        "record_month": None,
        "tickets_used": 0,
        "ai_agents_used": 0,
        "voice_minutes_used": None,
        "overage_tickets": 0,
        "overage_charges": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockClientRefund = type(
    "ClientRefund",
    (object,),
    {
        "__tablename__": "client_refunds",
        "id": None,
        "company_id": None,
        "ticket_id": None,
        "amount": None,
        "currency": "USD",
        "reason": None,
        "status": "pending",
        "external_ref": None,
        "processed_at": None,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockIdempotencyKey = type(
    "IdempotencyKey",
    (object,),
    {
        "__tablename__": "idempotency_keys",
        "id": None,
        "company_id": None,
        "idempotency_key": None,
        "resource_type": None,
        "resource_id": None,
        "request_body_hash": None,
        "response_status": None,
        "response_body": None,
        "created_at": _AttrChainer(),
        "expires_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockVariantLimit = type(
    "VariantLimit",
    (object,),
    {
        "__tablename__": "variant_limits",
        "id": None,
        "variant_name": None,
        "monthly_tickets": None,
        "ai_agents": None,
        "team_members": None,
        "voice_slots": None,
        "kb_docs": None,
        "price_monthly": None,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockPaymentFailure = type(
    "PaymentFailure",
    (object,),
    {
        "__tablename__": "payment_failures",
        "id": None,
        "company_id": None,
        "paddle_subscription_id": None,
        "paddle_transaction_id": None,
        "failure_code": None,
        "failure_reason": None,
        "amount_attempted": None,
        "currency": "USD",
        "service_stopped_at": None,
        "service_resumed_at": None,
        "notification_sent": False,
        "resolved": False,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

# Day 5: Add all models to fake billing_extended
for _name, _cls in [
    ("Chargeback", _MockChargeback),
    ("CreditBalance", _MockCreditBalance),
    ("SpendingCap", _MockSpendingCap),
    ("DeadLetterWebhook", _MockDeadLetterWebhook),
    ("WebhookHealthStat", _MockWebhookHealthStat),
    ("RefundAudit", _MockRefundAudit),
    ("WebhookSequence", _MockWebhookSequence),
    ("UsageRecord", _MockUsageRecord),
    ("ClientRefund", _MockClientRefund),
    ("IdempotencyKey", _MockIdempotencyKey),
    ("VariantLimit", _MockVariantLimit),
    ("PaymentFailure", _MockPaymentFailure),
]:
    setattr(_fake_billing_extended, _name, _cls)

# Day 6: Add new mock models + Subscription alias for convenience
# (Subscription lives in billing, but some code imports from billing_extended)
_MockPromoCode = type(
    "PromoCode",
    (object,),
    {
        "__tablename__": "promo_codes",
        "id": None,
        "code": None,
        "discount_type": None,
        "discount_value": None,
        "max_uses": None,
        "used_count": 0,
        "valid_from": None,
        "valid_until": None,
        "applies_to_tiers": None,
        "created_by": None,
        "is_active": True,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockCompanyPromoUse = type(
    "CompanyPromoUse",
    (object,),
    {
        "__tablename__": "company_promo_uses",
        "id": None,
        "company_id": None,
        "promo_code_id": None,
        "applied_at": _AttrChainer(),
        "invoice_id": None,
        "discount_amount": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockInvoiceAmendment = type(
    "InvoiceAmendment",
    (object,),
    {
        "__tablename__": "invoice_amendments",
        "id": None,
        "invoice_id": None,
        "company_id": None,
        "original_amount": None,
        "new_amount": None,
        "amendment_type": None,
        "reason": None,
        "approved_by": None,
        "paddle_credit_note_id": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockPauseRecord = type(
    "PauseRecord",
    (object,),
    {
        "__tablename__": "pause_records",
        "id": None,
        "company_id": None,
        "subscription_id": None,
        "paused_at": _AttrChainer(),
        "resumed_at": _AttrChainer(),
        "pause_duration_days": None,
        "max_pause_days": 30,
        "period_end_extension_days": 0,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockDataExport = type(
    "DataExport",
    (object,),
    {
        "__tablename__": "data_exports",
        "id": None,
        "company_id": None,
        "status": "processing",
        "format": "zip",
        "file_size_bytes": None,
        "export_data_json": None,
        "error_message": None,
        "requested_at": None,
        "completed_at": None,
        "expires_at": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

for _name, _cls in [
    ("PromoCode", _MockPromoCode),
    ("CompanyPromoUse", _MockCompanyPromoUse),
    ("InvoiceAmendment", _MockInvoiceAmendment),
    ("PauseRecord", _MockPauseRecord),
    ("DataExport", _MockDataExport),
]:
    setattr(_fake_billing_extended, _name, _cls)

# Also add Transaction to billing models (used by refund_service)
_MockTransaction = type(
    "Transaction",
    (object,),
    {
        "__tablename__": "transactions",
        "id": None,
        "company_id": None,
        "paddle_transaction_id": None,
        "amount": None,
        "currency": "USD",
        "status": "completed",
        "kind": "payment",
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
setattr(_fake_billing_models, "Transaction", _MockTransaction)

# ── database.models.webhook_event (used by webhook_health_service) ──
_fake_webhook_event = types.ModuleType("database.models.webhook_event")
_MockWebhookEvent = type(
    "WebhookEvent",
    (object,),
    {
        "__tablename__": "webhook_events",
        "id": None,
        "company_id": None,
        "provider": "paddle",
        "event_id": None,
        "event_type": None,
        "payload": None,
        "status": "pending",
        "processing_started_at": None,
        "completed_at": None,
        "error_message": None,
        "processing_attempts": 0,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
setattr(_fake_webhook_event, "WebhookEvent", _MockWebhookEvent)
sys.modules.setdefault("database.models.webhook_event", _fake_webhook_event)

# Also add Agent to core models (used by resource cleanup)
setattr(
    _fake_core_models,
    "Agent",
    type(
        "Agent",
        (object,),
        {
            "id": None,
            "company_id": _AttrChainer(),
            "status": "active",
            "created_at": _AttrChainer(),
            "__init__": _mock_model_init,
        },
    ),
)

# ── database.models.email_channel and outbound_email (Week 13) ────
_fake_email_channel = types.ModuleType("database.models.email_channel")
_fake_outbound_email = types.ModuleType("database.models.outbound_email")
_fake_tickets_models = types.ModuleType("database.models.tickets")

# Customer mock with optional fields used by bounce/complaint service
_MockCustomer = type(
    "Customer",
    (),
    {
        "id": None,
        "company_id": None,
        "email": None,
        "name": None,
        "email_valid": True,
        "email_status": None,
        "email_opt_out": False,
        "notification_preferences": None,
    },
)
setattr(_fake_tickets_models, "Customer", _MockCustomer)

# Ticket/TicketMessage needed by outbound_email_service.py (imports from
# database.models.tickets)
_MockTicket = type(
    "Ticket",
    (),
    {
        "id": None,
        "company_id": None,
        "customer_id": None,
        "channel": "email",
        "subject": None,
        "status": "open",
        "category": None,
        "priority": "medium",
        "first_response_at": None,
        "metadata_json": None,
    },
)
_MockTicketMessage = type(
    "TicketMessage",
    (),
    {
        "id": None,
        "company_id": _AttrChainer(),
        "ticket_id": _AttrChainer(),
        "role": "customer",
        "channel": "email",
        "content": None,
        "metadata_json": None,
        "created_at": _AttrChainer(),
    },
)
setattr(_fake_tickets_models, "Ticket", _MockTicket)
setattr(_fake_tickets_models, "TicketMessage", _MockTicketMessage)

# TicketFeedback and TicketAssignment needed by agent_dashboard_service.py
# (Week 17)
_MockTicketFeedback = type(
    "TicketFeedback",
    (object,),
    {
        "id": None,
        "company_id": _AttrChainer(),
        "ticket_id": None,
        "rating": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockTicketAssignment = type(
    "TicketAssignment",
    (object,),
    {
        "id": None,
        "company_id": _AttrChainer(),
        "ticket_id": None,
        "assignee_id": None,
        "assigned_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
setattr(_fake_tickets_models, "TicketFeedback", _MockTicketFeedback)
setattr(_fake_tickets_models, "TicketAssignment", _MockTicketAssignment)

sys.modules.setdefault("database.models.tickets", _fake_tickets_models)

_MockEmailThread = type(
    "EmailThread",
    (),
    {
        "id": None,
        "company_id": _AttrChainer(),
        "ticket_id": _AttrChainer(),
        "thread_message_id": None,
        "latest_message_id": None,
        "message_count": 0,
        "participants_json": "[]",
    },
)
_MockInboundEmail = type(
    "InboundEmail",
    (),
    {
        "id": None,
        "company_id": _AttrChainer(),
        "ticket_id": _AttrChainer(),
        "sender_email": _AttrChainer(),
        "sender_name": None,
        "body_html": None,
        "body_text": None,
        "message_id": None,
        "created_at": _AttrChainer(),
        "in_reply_to": None,
        "references": None,
        "is_auto_reply": False,
        "is_loop": False,
        "is_processed": False,
        "headers_json": None,
        "raw_size_bytes": 0,
        "recipient_email": None,
    },
)
_MockOutboundEmail = type(
    "OutboundEmail",
    (),
    {
        "id": None,
        "company_id": _AttrChainer(),
        "recipient_email": None,
        "subject": None,
        "delivery_status": None,
        "ticket_id": _AttrChainer(),
        "brevo_message_id": None,
        "__tablename__": "outbound_emails",
        "to_dict": lambda self: {},
        "bounced_at": None,
        "delivered_at": None,
        "error_message": None,
        "created_at": _AttrChainer(),
        "sent_at": None,
        "reply_to_message_id": None,
        "references": None,
    },
)

for model_name in ["EmailThread", "InboundEmail"]:
    setattr(
        _fake_email_channel,
        model_name,
        _MockEmailThread if model_name == "EmailThread" else _MockInboundEmail,
    )
setattr(_fake_outbound_email, "OutboundEmail", _MockOutboundEmail)

_MockEmailDeliveryEvent = type(
    "EmailDeliveryEvent",
    (object,),
    {
        "id": None,
        "company_id": _AttrChainer(),
        "event_type": None,
        "recipient_email": None,
        "recipient_name": None,
        "brevo_message_id": None,
        "brevo_event_id": None,
        "outbound_email_id": None,
        "ticket_id": None,
        "reason": None,
        "bounce_type": None,
        "ooo_until": None,
        "provider": "brevo",
        "provider_data": None,
        "is_processed": _AttrChainer(),
        "processing_error": None,
        "retry_count": 0,
        "max_retries": 3,
        "next_retry_at": None,
        "event_at": None,
        "created_at": _AttrChainer(),
        "updated_at": None,
        "__tablename__": "email_delivery_events",
    },
)


def _email_delivery_to_dict(self):
    return {
        "id": getattr(self, "id", None),
        "event_type": getattr(self, "event_type", None),
    }


_MockEmailDeliveryEvent.to_dict = _email_delivery_to_dict


def _email_delivery_init(self, **kwargs):
    for k, v in kwargs.items():
        setattr(self, k, v)


_MockEmailDeliveryEvent.__init__ = _email_delivery_init

_fake_delivery_event = types.ModuleType("database.models.email_delivery_event")
setattr(_fake_delivery_event, "EmailDeliveryEvent", _MockEmailDeliveryEvent)

sys.modules.setdefault("database.models.email_channel", _fake_email_channel)
sys.modules.setdefault("database.models.outbound_email", _fake_outbound_email)
sys.modules.setdefault("database.models.email_delivery_event", _fake_delivery_event)

# ── database.models.ooo_detection (Week 13 Day 3 — F-122) ──────────
_fake_ooo_models = types.ModuleType("database.models.ooo_detection")

_MockOOODetectionRule = type(
    "OOODetectionRule",
    (object,),
    {
        "__tablename__": "ooo_detection_rules",
        "id": None,
        "company_id": _AttrChainer(),
        "rule_type": "body",
        "pattern": None,
        "pattern_type": "regex",
        "classification": "ooo",
        "active": _AttrChainer(),
        "match_count": 0,
        "last_matched_at": None,
        "created_at": None,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockOOODetectionLog = type(
    "OOODetectionLog",
    (object,),
    {
        "__tablename__": "ooo_detection_log",
        "id": None,
        "company_id": _AttrChainer(),
        "thread_id": None,
        "sender_email": None,
        "classification": "ooo",
        "confidence": 0.0,
        "detected_signals": None,
        "rule_ids_matched": None,
        "action_taken": "tagged",
        "related_ticket_id": None,
        "message_id": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockOOOSenderProfile = type(
    "OOOSenderProfile",
    (object,),
    {
        "__tablename__": "ooo_sender_profiles",
        "id": None,
        "company_id": _AttrChainer(),
        "sender_email": None,
        "ooo_detected_count": 0,
        "last_ooo_at": None,
        "ooo_until": None,
        "active_ooo": False,
        "created_at": None,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

setattr(_fake_ooo_models, "OOODetectionRule", _MockOOODetectionRule)
setattr(_fake_ooo_models, "OOODetectionLog", _MockOOODetectionLog)
setattr(_fake_ooo_models, "OOOSenderProfile", _MockOOOSenderProfile)
sys.modules.setdefault("database.models.ooo_detection", _fake_ooo_models)

# ── database.models.email_bounces (Week 13 Day 3 — F-124) ─────────
_fake_bounces_models = types.ModuleType("database.models.email_bounces")

_MockEmailBounce = type(
    "EmailBounce",
    (object,),
    {
        "__tablename__": "email_bounces",
        "id": None,
        "company_id": _AttrChainer(),
        "customer_email": None,
        "bounce_type": "hard",
        "bounce_reason": None,
        "provider": "gmail",
        "provider_code": None,
        "event_id": None,
        "related_ticket_id": None,
        "email_status_before": "active",
        "email_status_after": "hard_bounced",
        "whitelisted": False,
        "whitelist_justification": None,
        "whitelisted_by": None,
        "whitelisted_at": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockCustomerEmailStatus = type(
    "CustomerEmailStatus",
    (object,),
    {
        "__tablename__": "customer_email_status",
        "id": None,
        "company_id": _AttrChainer(),
        "customer_email": None,
        "email_status": "active",
        "bounce_count": 0,
        "complaint_count": 0,
        "last_bounce_at": None,
        "last_complaint_at": None,
        "suppressed_at": None,
        "whitelisted": False,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockEmailDeliverabilityAlert = type(
    "EmailDeliverabilityAlert",
    (object,),
    {
        "__tablename__": "email_deliverability_alerts",
        "id": None,
        "company_id": _AttrChainer(),
        "alert_type": "bounce_spike",
        "severity": _AttrChainer(),
        "message": None,
        "metric_value": 0.0,
        "threshold": 0.0,
        "acknowledged": _AttrChainer(),
        "acknowledged_by": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

setattr(_fake_bounces_models, "EmailBounce", _MockEmailBounce)
setattr(_fake_bounces_models, "CustomerEmailStatus", _MockCustomerEmailStatus)
setattr(_fake_bounces_models, "EmailDeliverabilityAlert", _MockEmailDeliverabilityAlert)
sys.modules.setdefault("database.models.email_bounces", _fake_bounces_models)

# ── database.models.chat_widget (Week 13 Day 4 — F-122) ────────
_fake_chat_widget_models = types.ModuleType("database.models.chat_widget")

_MockChatWidgetSession = type(
    "ChatWidgetSession",
    (object,),
    {
        "__tablename__": "chat_widget_sessions",
        "id": None,
        "company_id": _AttrChainer(),
        "visitor_name": None,
        "visitor_email": None,
        "visitor_phone": None,
        "visitor_ip": None,
        "visitor_user_agent": None,
        "visitor_page_url": None,
        "visitor_referrer": None,
        "status": "active",
        "assigned_agent_id": None,
        "department": None,
        "ticket_id": None,
        "customer_id": None,
        "message_count": 0,
        "visitor_message_count": 0,
        "agent_response_time_seconds": None,
        "csat_rating": None,
        "csat_comment": None,
        "first_message_at": None,
        "last_message_at": None,
        "closed_at": None,
        "created_at": None,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockChatWidgetMessage = type(
    "ChatWidgetMessage",
    (object,),
    {
        "__tablename__": "chat_widget_messages",
        "id": None,
        "session_id": None,
        "company_id": None,
        "sender_id": None,
        "sender_name": None,
        "role": "visitor",
        "content": None,
        "message_type": "text",
        "attachments_json": "[]",
        "quick_replies_json": "[]",
        "event_name": None,
        "event_data_json": "{}",
        "is_ai_generated": False,
        "ai_confidence": None,
        "is_read": False,
        "read_at": None,
        "created_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockCannedResponse = type(
    "CannedResponse",
    (object,),
    {
        "__tablename__": "canned_responses",
        "id": None,
        "company_id": None,
        "title": None,
        "content": None,
        "category": "general",
        "shortcut": None,
        "sort_order": 0,
        "is_active": True,
        "created_by": None,
        "updated_by": None,
        "created_at": None,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockChatWidgetConfig = type(
    "ChatWidgetConfig",
    (object,),
    {
        "__tablename__": "chat_widget_configs",
        "id": None,
        "company_id": None,
        "widget_title": "Chat with us",
        "welcome_message": "Hi!",
        "placeholder_text": "Type here...",
        "primary_color": "#4F46E5",
        "widget_position": "bottom_right",
        "is_enabled": True,
        "auto_greeting_enabled": True,
        "auto_greeting_delay_seconds": 5,
        "bot_enabled": True,
        "max_file_size_mb": 10,
        "allowed_file_types": "[]",
        "max_queue_size": 50,
        "queue_message": None,
        "business_hours_json": "{}",
        "offline_message": None,
        "require_visitor_name": False,
        "require_visitor_email": False,
        "created_at": None,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

setattr(_fake_chat_widget_models, "ChatWidgetSession", _MockChatWidgetSession)
setattr(_fake_chat_widget_models, "ChatWidgetMessage", _MockChatWidgetMessage)
setattr(_fake_chat_widget_models, "CannedResponse", _MockCannedResponse)
setattr(_fake_chat_widget_models, "ChatWidgetConfig", _MockChatWidgetConfig)
sys.modules.setdefault("database.models.chat_widget", _fake_chat_widget_models)

# ── database.models.sms_channel (Week 13 Day 5 — F-123) ────────
_fake_sms_models = types.ModuleType("database.models.sms_channel")

_MockSMSMessage = type(
    "SMSMessage",
    (object,),
    {
        "__tablename__": "sms_messages",
        "id": None,
        "company_id": _AttrChainer(),
        "conversation_id": None,
        "direction": "inbound",
        "from_number": None,
        "to_number": None,
        "body": None,
        "num_segments": 1,
        "char_count": None,
        "twilio_message_sid": None,
        "twilio_account_sid": None,
        "twilio_status": "queued",
        "twilio_error_code": None,
        "twilio_error_message": None,
        "ticket_id": None,
        "ticket_message_id": None,
        "sender_id": None,
        "sender_role": "visitor",
        "is_ai_generated": False,
        "ai_confidence": None,
        "ai_model": None,
        "is_opt_out": False,
        "opt_out_keyword": None,
        "error_message": None,
        "retry_count": 0,
        "sent_at": None,
        "delivered_at": None,
        "created_at": _AttrChainer(),
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockSMSConversation = type(
    "SMSConversation",
    (object,),
    {
        "__tablename__": "sms_conversations",
        "id": None,
        "company_id": _AttrChainer(),
        "customer_number": None,
        "twilio_number": None,
        "ticket_id": None,
        "customer_id": None,
        "message_count": 0,
        "last_message_at": None,
        "is_opted_out": False,
        "opt_out_keyword": None,
        "opt_out_at": None,
        "created_at": None,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

_MockSMSChannelConfig = type(
    "SMSChannelConfig",
    (object,),
    {
        "__tablename__": "sms_channel_configs",
        "id": None,
        "company_id": None,
        "twilio_account_sid": None,
        "twilio_auth_token_encrypted": None,
        "twilio_phone_number": None,
        "is_enabled": True,
        "auto_create_ticket": True,
        "char_limit": 1600,
        "max_outbound_per_hour": 5,
        "max_outbound_per_day": 50,
        "opt_out_keywords": "STOP,STOPALL,UNSUBSCRIBE,CANCEL,QUIT,END",
        "opt_in_keywords": "START,YES,UNSTOP,CONTINUE",
        "opt_out_response": "You have been opted out.",
        "auto_reply_enabled": False,
        "auto_reply_message": None,
        "auto_reply_delay_seconds": 10,
        "after_hours_message": None,
        "business_hours_json": "{}",
        "created_at": None,
        "updated_at": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)

setattr(_fake_sms_models, "SMSMessage", _MockSMSMessage)
setattr(_fake_sms_models, "SMSConversation", _MockSMSConversation)
setattr(_fake_sms_models, "SMSChannelConfig", _MockSMSChannelConfig)
sys.modules.setdefault("database.models.sms_channel", _fake_sms_models)

# ── database.models.integration (Week 17 Day 1 — F-031) ────────
_fake_integration_models = types.ModuleType("database.models.integration")

_MockCustomIntegration = type(
    "CustomIntegration",
    (object,),
    {
        "__tablename__": "custom_integrations",
        "id": None,
        "company_id": _AttrChainer(),
        "name": None,
        "integration_type": None,
        "status": "draft",
        "config_encrypted": None,
        "settings": "{}",
        "webhook_id": None,
        "webhook_secret": None,
        "consecutive_error_count": 0,
        "last_error_message": None,
        "last_tested_at": None,
        "last_test_result": None,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
setattr(_fake_integration_models, "CustomIntegration", _MockCustomIntegration)
sys.modules.setdefault("database.models.integration", _fake_integration_models)

# ── database.models.agent (Week 17 Day 1 — F-097) ──────────────
_fake_agent_models = types.ModuleType("database.models.agent")

_MockAgent = type(
    "Agent",
    (object,),
    {
        "__tablename__": "agents",
        "id": None,
        "company_id": _AttrChainer(),
        "name": None,
        "status": "draft",
        "specialty": None,
        "description": None,
        "base_model": None,
        "model_checkpoint_id": None,
        "channels": None,
        "permissions": None,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "activated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockInstructionSet = type(
    "InstructionSet",
    (object,),
    {
        "__tablename__": "instruction_sets",
        "id": None,
        "company_id": _AttrChainer(),
        "agent_id": None,
        "name": None,
        "version": 1,
        "status": "active",
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
setattr(_fake_agent_models, "Agent", _MockAgent)
setattr(_fake_agent_models, "InstructionSet", _MockInstructionSet)
sys.modules.setdefault("database.models.agent", _fake_agent_models)

# ── database.models.agent_metrics (Week 17 Day 2 — F-098) ────
_fake_agent_metrics_models = types.ModuleType("database.models.agent_metrics")

_MockAgentMetricsDaily = type(
    "AgentMetricsDaily",
    (object,),
    {
        "__tablename__": "agent_metrics_daily",
        "id": None,
        "company_id": _AttrChainer(),
        "agent_id": _AttrChainer(),
        "date": _AttrChainer(),
        "resolution_rate": None,
        "avg_confidence": None,
        "avg_csat": None,
        "escalation_rate": None,
        "avg_handle_time_seconds": None,
        "tickets_handled": 0,
        "resolved_count": 0,
        "escalated_count": 0,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockAgentMetricThreshold = type(
    "AgentMetricThreshold",
    (object,),
    {
        "__tablename__": "agent_metric_thresholds",
        "id": None,
        "company_id": _AttrChainer(),
        "agent_id": _AttrChainer(),
        "resolution_rate_min": 70.0,
        "confidence_min": 65.0,
        "csat_min": 3.5,
        "escalation_max_pct": 15.0,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
_MockAgentPerformanceAlert = type(
    "AgentPerformanceAlert",
    (object,),
    {
        "__tablename__": "agent_performance_alerts",
        "id": None,
        "company_id": _AttrChainer(),
        "agent_id": _AttrChainer(),
        "metric_name": None,
        "current_value": None,
        "threshold_value": None,
        "consecutive_days_below": 0,
        "status": "active",
        "resolved_at": None,
        "created_at": _AttrChainer(),
        "updated_at": _AttrChainer(),
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
setattr(_fake_agent_metrics_models, "AgentMetricsDaily", _MockAgentMetricsDaily)
setattr(_fake_agent_metrics_models, "AgentMetricThreshold", _MockAgentMetricThreshold)
setattr(_fake_agent_metrics_models, "AgentPerformanceAlert", _MockAgentPerformanceAlert)
sys.modules.setdefault("database.models.agent_metrics", _fake_agent_metrics_models)

# ── database.models.provisioning (Week 17 Day 2 — F-099) ──
_fake_provisioning_models = types.ModuleType("database.models.provisioning")

_MockPendingAgent = type(
    "PendingAgent",
    (object,),
    {
        "__tablename__": "pending_agents",
        "id": _AttrChainer(),
        "company_id": _AttrChainer(),
        "agent_name": None,
        "specialty": None,
        "channels": None,
        "payment_status": "pending",
        "provisioning_status": "awaiting_payment",
        "paddle_event_id": None,
        "paddle_checkout_id": None,
        "paddle_transaction_id": None,
        "created_at": _AttrChainer(),
        "expires_at": _AttrChainer(),
        "provisioned_at": None,
        "error_message": None,
        "__init__": _mock_model_init,
        "to_dict": _mock_model_to_dict,
    },
)
setattr(_fake_provisioning_models, "PendingAgent", _MockPendingAgent)
sys.modules.setdefault("database.models.provisioning", _fake_provisioning_models)

sys.modules.setdefault("database", _fake_database)
sys.modules.setdefault("database.base", _fake_base)
sys.modules.setdefault("database.models", _fake_models)
sys.modules.setdefault("database.models.jarvis", _fake_jarvis_models)
sys.modules.setdefault("database.models.core", _fake_core_models)
sys.modules.setdefault("database.models.onboarding", _fake_onboarding_models)
sys.modules.setdefault("database.models.billing", _fake_billing_models)
# ── Add get_variant_limits helper (used by refund_service cooling-off) ──


def _get_variant_limits(variant_name: str):
    """Mock version of get_variant_limits from billing_extended."""
    _LIMITS = {
        "mini_parwa": {"price_monthly": _Decimal("999.00")},
        "parwa": {"price_monthly": _Decimal("2499.00")},
        "enterprise": {"price_monthly": _Decimal("3999.00")},
    }
    return _LIMITS.get(variant_name)


setattr(_fake_billing_extended, "get_variant_limits", _get_variant_limits)

sys.modules.setdefault("database.models.billing_extended", _fake_billing_extended)

# ── shared layer (exists on disk but imports database.models.onboarding) ──
_FAKE_SHARED = types.ModuleType("shared")
_FAKE_SHARED_UTILS = types.ModuleType("shared.utils")
_FAKE_SHARED_UTILS_PAGINATION = types.ModuleType("shared.utils.pagination")
_FAKE_SHARED_UTILS_PAGINATION.DEFAULT_PAGE_SIZE = 20
_FAKE_SHARED_UTILS_PAGINATION.MAX_PAGE_SIZE = 100
_FAKE_SHARED_UTILS_PAGINATION.MAX_OFFSET = 10000
_FAKE_KB = types.ModuleType("shared.knowledge_base")
_FAKE_KB_MANAGER = types.ModuleType("shared.knowledge_base.manager")
_FAKE_KB_RETRIEVER = types.ModuleType("shared.knowledge_base.retriever")
_FAKE_KB_VECTOR = types.ModuleType("shared.knowledge_base.vector_search")
_FAKE_KB_CHUNKER = types.ModuleType("shared.knowledge_base.chunker")
_FAKE_KB_REINDEX = types.ModuleType("shared.knowledge_base.reindexing")

# Populate vector_search mock with expected exports
_FAKE_KB_VECTOR.EMBEDDING_DIMENSION = 1536
_FAKE_KB_VECTOR.VectorStore = MagicMock()
_FAKE_KB_VECTOR.get_vector_store = MagicMock()
_FAKE_KB_VECTOR.add_documents = MagicMock()

for mod in [
    _FAKE_SHARED,
    _FAKE_SHARED_UTILS,
    _FAKE_SHARED_UTILS_PAGINATION,
    _FAKE_KB,
    _FAKE_KB_MANAGER,
    _FAKE_KB_RETRIEVER,
    _FAKE_KB_VECTOR,
    _FAKE_KB_CHUNKER,
    _FAKE_KB_REINDEX,
]:
    sys.modules.setdefault(mod.__name__, mod)


# ════════════════════════════════════════════════════════════════════════
# Phase 3: Mock app submodules that need special handling
# ════════════════════════════════════════════════════════════════════════

# ── app.logger — mock so structlog doesn't need real config in tests ───
_mock_logger = MagicMock()
sys.modules.setdefault("app.logger", _mock_logger)

# ── app.core.* — ONLY mock submodules that don't exist on disk ──────
_CORE_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "core")

for mod_path, attrs in {
    "app.core.sentiment_engine": {"SentimentAnalyzer": MagicMock()},
    "app.core.graceful_escalation": {
        "GracefulEscalationManager": MagicMock(),
        "EscalationContext": MagicMock(),
        "EscalationTrigger": MagicMock(),
    },
}.items():
    mod_file = mod_path.replace(".", "/") + ".py"
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", mod_file)):
        mod = types.ModuleType(mod_path)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules.setdefault(mod_path, mod)

# ── app.services — some tests import from app.services.* ─────────────
# Mock specific service modules that tests reference but may not exist
# or may have cascading import issues.
_SERVICES_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "services")

for mod_path in [
    "app.services.prompt_template_service",
    "app.services.token_budget_service",
    "app.services.response_template_service",
]:
    mod_file = mod_path.replace(".", "/") + ".py"
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", mod_file)):
        sys.modules.setdefault(mod_path, MagicMock())

# ── app.core.email_renderer — mock for outbound email tests ────────
_core_dir = os.path.join(os.path.dirname(__file__), "..", "app", "core")
_email_renderer_path = os.path.join(_core_dir, "email_renderer.py")
if os.path.exists(_email_renderer_path):
    # Real file exists — don't mock it
    pass
else:
    _fake_email_renderer = types.ModuleType("app.core.email_renderer")
    _fake_email_renderer.render_email_template = MagicMock(
        return_value="<html><body>Mock Template</body></html>"
    )
    sys.modules.setdefault("app.core.email_renderer", _fake_email_renderer)

# ── app.core.event_emitter — mock for async event tests ─────────────
_event_emitter_path = os.path.join(_core_dir, "event_emitter.py")
if not os.path.exists(_event_emitter_path):
    _fake_event_emitter = types.ModuleType("app.core.event_emitter")
    _fake_event_emitter.emit_ticket_event = MagicMock()
    sys.modules.setdefault("app.core.event_emitter", _fake_event_emitter)


# ════════════════════════════════════════════════════════════════════════
# Phase 4: pytest fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    from app.config import Settings

    return Settings()


@pytest.fixture
def mock_db_session():
    """Provide a mock database session."""
    return _mock_db


@pytest.fixture
def company_id():
    """Default test company ID."""
    return "test-company-123"
