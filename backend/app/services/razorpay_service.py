"""
Razorpay Service — Business Logic
Maps PARWA variants to Razorpay plans/subscriptions.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.clients.razorpay_client import RazorpayClient, RazorpayError, get_razorpay_client
from app.core.pricing_config import VariantType, VARIANT_PRICES
from database.models.billing import Subscription, Invoice, Transaction
from database.models.core import Company, User

logger = logging.getLogger("parwa.services.razorpay")
CURRENCY = "USD"
CURRENCY_MULTIPLIER = 100
PLAN_CACHE_COMPANY_ID = "system_plan_cache"

VARIANT_PLAN_META = {
    # NOTE: Mini was removed 2026-07-26. Only 2 tiers remain.
    # Legacy Mini subscribers are auto-upgraded to Parwa via normalize_variant_name().
    VariantType.PARWA: {"name": "PARWA Monthly", "description": "PARWA — junior agent with full technique suite. Replaces 1-3 yr experience rep."},
    VariantType.HIGH: {"name": "PARWA High Monthly", "description": "PARWA High — senior agent with advanced reasoning. Replaces 3+ yr experience rep."},
}

class RazorpayServiceError(Exception): pass
class SubscriptionNotFoundError(RazorpayServiceError): pass

async def ensure_plan_exists(db: Session, client: RazorpayClient, variant: VariantType) -> str:
    cache_row = db.query(Subscription).filter(
        Subscription.company_id == PLAN_CACHE_COMPANY_ID,
        Subscription.tier == variant.value,
        Subscription.status == "plan_cache",
    ).first()
    if cache_row and cache_row.paddle_subscription_id:
        try:
            plan = await client.get_plan(cache_row.paddle_subscription_id)
            return plan["id"]
        except RazorpayError:
            pass
    price_usd = VARIANT_PRICES[variant]
    amount_cents = int(price_usd * CURRENCY_MULTIPLIER)
    meta = VARIANT_PLAN_META[variant]
    plan = await client.create_plan(name=meta["name"], amount=amount_cents, currency=CURRENCY, period="monthly", description=meta["description"])
    plan_id = plan["id"]
    if cache_row:
        cache_row.paddle_subscription_id = plan_id
    else:
        db.add(Subscription(company_id=PLAN_CACHE_COMPANY_ID, tier=variant.value, status="plan_cache", paddle_subscription_id=plan_id))
    db.commit()
    return plan_id

async def ensure_customer_exists(db: Session, client: RazorpayClient, company: Company, user: User) -> str:
    customer_link = db.query(Subscription).filter(
        Subscription.company_id == str(company.id),
        Subscription.status == "customer_link",
    ).first()
    if customer_link and customer_link.paddle_subscription_id:
        return customer_link.paddle_subscription_id
    customer = await client.create_customer(
        name=user.full_name or user.email or "PARWA Customer",
        email=user.email or f"company-{company.id}@parwa.buzz",
        notes={"company_id": str(company.id), "company_name": company.name or ""},
    )
    customer_id = customer["id"]
    db.add(Subscription(company_id=str(company.id), tier="customer", status="customer_link", paddle_subscription_id=customer_id))
    db.commit()
    return customer_id

async def create_variant_subscription(db: Session, company: Company, user: User, variant: VariantType, quantity: int = 1) -> Dict[str, Any]:
    client = get_razorpay_client()
    if not client.key_id:
        raise RazorpayServiceError("Razorpay not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
    plan_id = await ensure_plan_exists(db, client, variant)
    customer_id = await ensure_customer_exists(db, client, company, user)
    sub = await client.create_subscription(
        plan_id=plan_id, customer_id=customer_id, total_count=0, quantity=quantity,
        notes={"company_id": str(company.id), "variant": variant.value, "company_name": company.name or ""},
    )
    new_sub = Subscription(
        company_id=str(company.id), tier=variant.value, status="created",
        paddle_subscription_id=sub["id"], current_period_start=datetime.now(timezone.utc),
    )
    db.add(new_sub)
    db.commit()
    return {"subscription_id": sub["id"], "status": sub.get("status", "created"), "short_url": sub.get("short_url", ""), "variant": variant.value, "quantity": quantity, "plan_id": plan_id}

async def cancel_variant_subscription(db: Session, company: Company, variant: VariantType, cancel_at_cycle_end: bool = True) -> Dict[str, Any]:
    client = get_razorpay_client()
    sub_row = db.query(Subscription).filter(
        Subscription.company_id == str(company.id),
        Subscription.tier == variant.value,
        Subscription.status.in_(["created", "active", "authenticated", "pending"]),
    ).first()
    if not sub_row or not sub_row.paddle_subscription_id:
        raise SubscriptionNotFoundError(f"No active subscription found for variant {variant.value}")
    await client.cancel_subscription(sub_row.paddle_subscription_id, cancel_at_cycle_end=cancel_at_cycle_end)
    sub_row.status = "cancelled"
    sub_row.cancel_at_period_end = cancel_at_cycle_end
    db.commit()
    return {"subscription_id": sub_row.paddle_subscription_id, "status": "cancelled", "cancel_at_cycle_end": cancel_at_cycle_end, "variant": variant.value}

async def update_subscription_quantity(db: Session, company: Company, variant: VariantType, new_quantity: int) -> Dict[str, Any]:
    if new_quantity < 1:
        raise RazorpayServiceError("Quantity must be at least 1. Use cancel instead.")
    client = get_razorpay_client()
    sub_row = db.query(Subscription).filter(
        Subscription.company_id == str(company.id),
        Subscription.tier == variant.value,
        Subscription.status.in_(["created", "active", "authenticated", "pending"]),
    ).first()
    if not sub_row or not sub_row.paddle_subscription_id:
        raise SubscriptionNotFoundError(f"No active subscription found for variant {variant.value}. Use create_variant_subscription instead.")
    result = await client.update_subscription(sub_row.paddle_subscription_id, quantity=new_quantity)
    return {"subscription_id": sub_row.paddle_subscription_id, "status": result.get("status", "active"), "variant": variant.value, "quantity": new_quantity}

def get_company_subscriptions(db: Session, company_id: str) -> list:
    rows = db.query(Subscription).filter(
        Subscription.company_id == company_id,
        Subscription.status.in_(["created", "active", "authenticated", "pending", "cancelled"]),
    ).all()
    result = []
    for row in rows:
        if row.status in ("customer_link", "plan_cache"):
            continue
        result.append({
            "variant": row.tier, "status": row.status,
            "razorpay_subscription_id": row.paddle_subscription_id,
            "current_period_start": row.current_period_start.isoformat() if row.current_period_start else None,
            "current_period_end": row.current_period_end.isoformat() if row.current_period_end else None,
            "cancel_at_period_end": row.cancel_at_period_end,
        })
    return result

async def handle_webhook_event(db: Session, event: Dict[str, Any]) -> Dict[str, Any]:
    event_type = event.get("event", "")
    payload = event.get("payload", {})
    logger.info("Processing Razorpay webhook: %s", event_type)
    if event_type == "subscription.activated":
        return await _handle_activated(db, payload)
    elif event_type == "subscription.charged":
        return await _handle_charged(db, payload)
    elif event_type == "subscription.cancelled":
        return await _handle_cancelled(db, payload)
    elif event_type == "payment.captured":
        return await _handle_payment_captured(db, payload)
    elif event_type == "payment.authorized":
        return await _handle_payment_authorized(db, payload)
    elif event_type == "payment.failed":
        return await _handle_payment_failed(db, payload)
    elif event_type == "refund.processed":
        return await _handle_refund_processed(db, payload)
    else:
        logger.info("Unhandled webhook event: %s (ignoring)", event_type)
        return {"status": "ignored", "event": event_type}

async def _handle_activated(db, payload):
    sub = payload.get("subscription", {}).get("entity", {})
    rzp_id = sub.get("id", "")
    row = db.query(Subscription).filter(Subscription.paddle_subscription_id == rzp_id).first()
    if not row:
        return {"status": "not_found"}
    row.status = "active"
    if sub.get("current_start"): row.current_period_start = datetime.fromtimestamp(sub["current_start"], tz=timezone.utc)
    if sub.get("current_end"): row.current_period_end = datetime.fromtimestamp(sub["current_end"], tz=timezone.utc)
    # End the free trial for this company — they've now paid.
    # Pass the paid variant so the company's subscription_tier is updated
    # from the trial default ("high") to what they actually bought.
    _end_company_trial(db, row.company_id, paid_variant=row.tier)
    db.commit()
    return {"status": "active", "subscription_id": rzp_id, "variant": row.tier}

async def _handle_charged(db, payload):
    sub = payload.get("subscription", {}).get("entity", {})
    payment = payload.get("payment", {}).get("entity", {})
    rzp_id = sub.get("id", "")
    payment_id = payment.get("id", "")
    amount_usd = Decimal(payment.get("amount", 0)) / Decimal(100)
    row = db.query(Subscription).filter(Subscription.paddle_subscription_id == rzp_id).first()
    if not row:
        return {"status": "not_found"}
    if sub.get("current_start"): row.current_period_start = datetime.fromtimestamp(sub["current_start"], tz=timezone.utc)
    if sub.get("current_end"): row.current_period_end = datetime.fromtimestamp(sub["current_end"], tz=timezone.utc)
    row.status = "active"
    db.add(Invoice(company_id=row.company_id, paddle_invoice_id=payment_id, amount=amount_usd, currency="USD", status="paid", invoice_date=datetime.now(timezone.utc), paid_at=datetime.now(timezone.utc)))
    db.add(Transaction(company_id=row.company_id, paddle_transaction_id=payment_id, amount=amount_usd, currency="USD", status="completed", transaction_type="subscription_charge", description=f"Subscription charge for {row.tier} variant"))
    # End the free trial for this company — they've now paid.
    _end_company_trial(db, row.company_id, paid_variant=row.tier)
    db.commit()
    return {"status": "charged", "subscription_id": rzp_id, "amount": str(amount_usd)}


def _end_company_trial(db, company_id: str, paid_variant: str = None) -> None:
    """Flip is_trial=False on the company. Preserves trial_tickets_used
    and trial_started_at for analytics. trial_ends_at is set to now()
    so the frontend can show "your trial ended on X" if needed.

    Args:
        paid_variant: The variant the user just paid for (mini/parwa/high).
                      If provided, updates the company's subscription_tier
                      from the trial default ("high") to the paid tier.
    """
    from database.models.core import Company
    if not company_id:
        return
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company or not getattr(company, "is_trial", False):
        # Even if already not in trial, update the tier if a paid_variant
        # was provided (handles re-subscription / tier change).
        if company and paid_variant:
            company.subscription_tier = paid_variant
        return
    company.is_trial = False
    company.subscription_status = "active"
    # Update tier to what they actually paid for (trial was "high" by default)
    if paid_variant:
        company.subscription_tier = paid_variant
    # Don't clear trial_started_at / trial_tickets_used — keep for analytics.
    # trial_ends_at = now() so the banner can switch off cleanly.
    company.trial_ends_at = datetime.now(timezone.utc)

async def _handle_cancelled(db, payload):
    sub = payload.get("subscription", {}).get("entity", {})
    rzp_id = sub.get("id", "")
    row = db.query(Subscription).filter(Subscription.paddle_subscription_id == rzp_id).first()
    if not row:
        return {"status": "not_found"}
    row.status = "cancelled"
    db.commit()
    return {"status": "cancelled", "subscription_id": rzp_id, "variant": row.tier}

async def _handle_payment_failed(db, payload):
    sub = payload.get("subscription", {}).get("entity", {})
    rzp_id = sub.get("id", "")
    row = db.query(Subscription).filter(Subscription.paddle_subscription_id == rzp_id).first()
    if row:
        row.status = "pending"
        db.commit()
    return {"status": "payment_failed", "subscription_id": rzp_id}


# ─── Standard Checkout (one-time payment) handlers ─────────────────────────
# These handle events from Razorpay Standard Checkout (in-page modal) flow,
# as opposed to the Subscriptions API flow above.

def _extract_payment_entity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the payment.entity dict out of the webhook payload."""
    return payload.get("payment", {}).get("entity", {}) or {}


def _find_company_for_order(db, order_id: str):
    """Look up the company that owns this order.

    Razorpay orders are created via /api/razorpay/create-order with a receipt
    of the form 'parwa_<user_id_first_8>' or 'parwa_<timestamp>'. We can't
    always map back from order_id to company reliably, so we fall back to
    using the notes field if present, or skipping company linkage.
    """
    if not order_id:
        return None
    # Subscription-linked payments still have a subscription_id we can look up.
    return None  # caller must handle None case


async def _handle_payment_captured(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    """payment.captured — fires when a one-time payment is captured.

    For Standard Checkout with auto-capture (default), this fires immediately
    after the user pays. Creates an Invoice + Transaction record so the
    billing dashboard reflects the payment.
    """
    payment = _extract_payment_entity(payload)
    payment_id = payment.get("id", "")
    amount_raw = payment.get("amount", 0) or 0  # in paise
    currency = (payment.get("currency") or "INR").upper()
    amount = Decimal(amount_raw) / Decimal(100)

    # Try to find company via subscription link, fall back to notes
    sub_id = payment.get("subscription_id")
    company_id = None
    variant = "unknown"

    if sub_id:
        row = db.query(Subscription).filter(
            Subscription.paddle_subscription_id == sub_id
        ).first()
        if row:
            company_id = row.company_id
            variant = row.tier
            row.status = "active"
            db.add(Invoice(
                company_id=row.company_id,
                paddle_invoice_id=payment_id,
                amount=amount,
                currency=currency,
                status="paid",
                invoice_date=datetime.now(timezone.utc),
                paid_at=datetime.now(timezone.utc),
            ))

    # Always record a Transaction (even if we couldn't link to a subscription)
    if company_id:
        db.add(Transaction(
            company_id=company_id,
            paddle_transaction_id=payment_id,
            amount=amount,
            currency=currency,
            status="completed",
            transaction_type="payment_captured",
            description=f"Payment captured for {variant} variant (Standard Checkout)",
        ))

    db.commit()
    logger.info(
        "payment.captured: payment_id=%s amount=%s %s company=%s variant=%s",
        payment_id, amount, currency, company_id, variant,
    )
    return {
        "status": "captured",
        "payment_id": payment_id,
        "amount": str(amount),
        "currency": currency,
        "company_id": company_id,
    }


async def _handle_payment_authorized(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    """payment.authorized — payment authorized but not yet captured.

    With auto-capture (default for Standard Checkout), this is followed
    quickly by payment.captured. We log it but don't create invoice yet —
    wait for capture to record the actual money movement.
    """
    payment = _extract_payment_entity(payload)
    payment_id = payment.get("id", "")
    logger.info("payment.authorized: payment_id=%s (awaiting capture)", payment_id)
    return {"status": "authorized", "payment_id": payment_id}


async def _handle_refund_processed(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    """refund.processed — refund issued from Razorpay dashboard.

    Marks the related invoice as refunded so billing dashboard reflects it.
    """
    refund = payload.get("refund", {}).get("entity", {}) or {}
    refund_id = refund.get("id", "")
    payment_id = refund.get("payment_id", "")
    amount_raw = refund.get("amount", 0) or 0
    currency = (refund.get("currency") or "INR").upper()
    amount = Decimal(amount_raw) / Decimal(100)

    # Find invoice by payment_id and mark as refunded
    inv = db.query(Invoice).filter(Invoice.paddle_invoice_id == payment_id).first()
    if inv:
        inv.status = "refunded"
        db.add(Transaction(
            company_id=inv.company_id,
            paddle_transaction_id=refund_id,
            amount=-amount,  # negative to indicate outflow
            currency=currency,
            status="completed",
            transaction_type="refund_processed",
            description=f"Refund processed for payment {payment_id}",
        ))
        db.commit()
        logger.info("refund.processed: refund_id=%s payment_id=%s amount=%s",
                    refund_id, payment_id, amount)
        return {"status": "refunded", "refund_id": refund_id, "payment_id": payment_id}

    logger.info("refund.processed: no matching invoice for payment_id=%s", payment_id)
    return {"status": "no_invoice", "refund_id": refund_id}
