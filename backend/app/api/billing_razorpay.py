"""
Razorpay Billing API Router — clean endpoints for subscription management.
Endpoints:
  GET  /api/billing/razorpay/subscriptions
  POST /api/billing/razorpay/subscribe
  POST /api/billing/razorpay/cancel
  POST /api/billing/razorpay/update-quantity
  POST /api/billing/razorpay/webhook
  GET  /api/billing/razorpay/tickets-by-variant
  GET  /api/billing/razorpay/pricing
  GET  /api/billing/razorpay/trial-status
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.clients.razorpay_client import get_razorpay_client, RazorpayError
from app.core.pricing_config import VariantType, VARIANT_PRICES, normalize_variant_name
from app.services.razorpay_service import (
    RazorpayServiceError, SubscriptionNotFoundError,
    create_variant_subscription, cancel_variant_subscription,
    update_subscription_quantity, get_company_subscriptions, handle_webhook_event,
)
from database.base import get_db
from database.models.core import Company, User

logger = logging.getLogger("parwa.api.billing_razorpay")
router = APIRouter(prefix="/api/billing/razorpay", tags=["billing-razorpay"])


class SubscribeRequest(BaseModel):
    variant: str = Field(..., description="mini, parwa, or high")
    quantity: int = Field(1, ge=1, le=100)


class CancelRequest(BaseModel):
    variant: str = Field(...)
    cancel_at_cycle_end: bool = Field(True)


class UpdateQuantityRequest(BaseModel):
    variant: str = Field(...)
    quantity: int = Field(..., ge=1, le=100)


class SubscriptionResponse(BaseModel):
    variant: str
    status: str
    razorpay_subscription_id: Optional[str] = None
    quantity: int = 1
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False


def _normalize_variant(variant_str: str) -> VariantType:
    try:
        return VariantType(normalize_variant_name(variant_str))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid variant '{variant_str}'. Must be: mini, parwa, or high.")


@router.get("/pricing")
async def get_pricing():
    return {
        "currency": "USD",
        "variants": [
            {"key": "mini", "name": "PARWA Mini", "monthly_price": float(VARIANT_PRICES[VariantType.MINI]), "description": "24/7 trainee AI agent. Replaces intern/fresher support rep.", "replaces": "Intern / Fresher"},
            {"key": "parwa", "name": "PARWA", "monthly_price": float(VARIANT_PRICES[VariantType.PARWA]), "description": "Junior agent with full technique suite. Replaces 1-3 yr experience rep.", "replaces": "Junior (1-3 yrs)"},
            {"key": "high", "name": "PARWA High", "monthly_price": float(VARIANT_PRICES[VariantType.HIGH]), "description": "Senior agent with advanced reasoning. Replaces 3+ yr experience rep.", "replaces": "Senior (3+ yrs)"},
        ],
    }


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin", "member")),
):
    company_id = str(user.company_id) if user.company_id else None
    if not company_id:
        raise HTTPException(400, "Company ID not found on user")
    subs = get_company_subscriptions(db, company_id)
    client = get_razorpay_client()
    result = []
    for sub in subs:
        razorpay_sub_id = sub.get("razorpay_subscription_id")
        quantity = 1
        current_status = sub.get("status", "unknown")
        if razorpay_sub_id and client.key_id:
            try:
                live = await client.get_subscription(razorpay_sub_id)
                quantity = live.get("quantity", 1)
                current_status = live.get("status", current_status)
            except RazorpayError as e:
                logger.warning("Failed to fetch live subscription %s: %s", razorpay_sub_id, e)
        result.append(SubscriptionResponse(
            variant=sub.get("variant", ""), status=current_status,
            razorpay_subscription_id=razorpay_sub_id, quantity=quantity,
            current_period_start=sub.get("current_period_start"),
            current_period_end=sub.get("current_period_end"),
            cancel_at_period_end=sub.get("cancel_at_period_end", False),
        ))
    return result


@router.post("/subscribe")
async def subscribe(
    data: SubscribeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    variant = _normalize_variant(data.variant)
    company = db.query(Company).filter(Company.id == user.company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")
    try:
        result = await create_variant_subscription(db=db, company=company, user=user, variant=variant, quantity=data.quantity)
        return result
    except RazorpayServiceError as e:
        raise HTTPException(502, str(e))


@router.post("/cancel")
async def cancel(
    data: CancelRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    variant = _normalize_variant(data.variant)
    company = db.query(Company).filter(Company.id == user.company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")
    try:
        return await cancel_variant_subscription(db=db, company=company, variant=variant, cancel_at_cycle_end=data.cancel_at_cycle_end)
    except SubscriptionNotFoundError as e:
        raise HTTPException(404, str(e))
    except RazorpayServiceError as e:
        raise HTTPException(502, str(e))


@router.post("/update-quantity")
async def update_quantity(
    data: UpdateQuantityRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    variant = _normalize_variant(data.variant)
    company = db.query(Company).filter(Company.id == user.company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")
    try:
        return await update_subscription_quantity(db=db, company=company, variant=variant, new_quantity=data.quantity)
    except SubscriptionNotFoundError as e:
        raise HTTPException(404, str(e))
    except RazorpayServiceError as e:
        raise HTTPException(502, str(e))


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    body_str = body.decode()
    signature = request.headers.get("X-Razorpay-Signature", "")
    client = get_razorpay_client()
    if not client.verify_webhook_signature(body_str, signature):
        logger.warning("Razorpay webhook signature verification failed")
        raise HTTPException(401, "Invalid webhook signature")
    try:
        event = json.loads(body_str)
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    try:
        result = await handle_webhook_event(db, event)
        return {"status": result.get("status", "processed")}
    except Exception as e:
        logger.exception("Webhook processing failed: %s", e)
        raise HTTPException(500, f"Webhook processing failed: {e}")


@router.get("/tickets-by-variant")
async def tickets_by_variant(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin", "member")),
):
    from sqlalchemy import func
    from database.models.tickets import Ticket
    company_id = str(user.company_id) if user.company_id else None
    if not company_id:
        raise HTTPException(400, "Company ID not found")
    rows = (
        db.query(Ticket.variant_version, func.count(Ticket.id))
        .filter(Ticket.company_id == company_id, Ticket.status.in_(["resolved", "closed"]))
        .group_by(Ticket.variant_version)
        .all()
    )
    result = {}
    for variant_value, count in rows:
        try:
            canonical = normalize_variant_name(variant_value or "mini")
        except Exception:
            canonical = "mini"
        result[canonical] = result.get(canonical, 0) + int(count or 0)
    return {"tickets_by_variant": result, "total_resolved": sum(result.values())}


# ── Free Trial Status ──────────────────────────────────────────────────

TRIAL_TICKET_LIMIT = 15
TRIAL_DURATION_HOURS = 24


@router.get("/trial-status")
async def get_trial_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin", "member")),
):
    """Return the company's free-trial status.

    Used by the dashboard TrialBanner to show:
      "Trial: X/15 tickets · Yh left · Upgrade"

    Returns:
        is_trial: bool — True if company is currently in trial.
        tickets_used: int — trial tickets used so far (preserved after trial ends).
        tickets_limit: int — 15 (hardcoded per pricing model).
        started_at: ISO datetime — when the trial started (null if never).
        ends_at: ISO datetime — when the trial ends/expires (null if never).
        time_remaining_hours: float — hours left in trial (0 if expired or not in trial).
        expired: bool — True if trial ended by time OR ticket count.
        expired_reason: str|null — "TIME" or "TICKETS" if expired, else null.
    """
    from datetime import datetime, timezone
    from database.models.core import Company

    company_id = str(user.company_id) if user.company_id else None
    if not company_id:
        raise HTTPException(400, "Company ID not found")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")

    is_trial = bool(getattr(company, "is_trial", False))
    used = int(getattr(company, "trial_tickets_used", 0) or 0)
    started_at = getattr(company, "trial_started_at", None)
    ends_at = getattr(company, "trial_ends_at", None)

    now = datetime.now(timezone.utc)
    time_remaining_hours = 0.0
    expired = False
    expired_reason = None

    if is_trial and ends_at:
        delta = ends_at - now
        time_remaining_hours = max(0.0, round(delta.total_seconds() / 3600, 2))
        if time_remaining_hours <= 0:
            expired = True
            expired_reason = "TIME"

    if is_trial and used >= TRIAL_TICKET_LIMIT:
        expired = True
        expired_reason = "TICKETS"

    return {
        "is_trial": is_trial,
        "tickets_used": used,
        "tickets_limit": TRIAL_TICKET_LIMIT,
        "started_at": started_at.isoformat() if started_at else None,
        "ends_at": ends_at.isoformat() if ends_at else None,
        "time_remaining_hours": time_remaining_hours,
        "expired": expired,
        "expired_reason": expired_reason,
    }
