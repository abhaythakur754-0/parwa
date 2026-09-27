"""
Subscription Service — DB-only (Razorpay is the billing provider)

Paddle was removed on 2026-06-24. Razorpay handles all subscription
creation / cancellation / updates via `app.services.razorpay_service`
(exposed at `/api/billing/razorpay/*`). This service now only owns the
DB-side reads the billing dashboard needs (current subscription, usage,
overage history) plus DB-only status transitions (cancel-at-period-end,
reactivate) that don't require a provider round-trip.

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
S-08:   All `with SessionLocal() as db:` blocks are wrapped in sync
        `_db_work()` functions and executed via `asyncio.to_thread()`.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.schemas.billing import (
    SubscriptionInfo,
    SubscriptionStatus,
    VariantLimits,
)
from app.core.pricing_config import (
    VariantType,
    VARIANT_LIMITS,
    VARIANT_PRICES,
    VARIANT_TIER_ORDER,
    get_variant_price as _get_price_from_config,
    normalize_variant_name,
)
from database.base import SessionLocal
from database.models.billing import Subscription, CancellationRequest
from database.models.core import Company

logger = logging.getLogger("parwa.services.subscription")


# ── Exceptions (kept for backward compat — other modules import these) ──

class SubscriptionError(Exception):
    """Base exception for subscription errors."""
    def __init__(self, message: str = "Subscription operation failed", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class SubscriptionNotFoundError(SubscriptionError):
    def __init__(self, message: str = "Subscription not found", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class SubscriptionAlreadyExistsError(SubscriptionError):
    def __init__(self, message: str = "Company already has an active subscription", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class InvalidVariantError(SubscriptionError):
    def __init__(self, message: str = "Invalid variant specified", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class InvalidStatusTransitionError(SubscriptionError):
    def __init__(self, message: str = "Invalid subscription status transition", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class PaddleOperationError(SubscriptionError):
    """Legacy exception class — kept for import compatibility.

    Paddle is removed. This is never raised anymore, but old call sites
    may still `except PaddleOperationError:` so we keep the symbol.
    """
    def __init__(self, message: str = "Paddle operation failed", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


# ── Service ─────────────────────────────────────────────────────────────

class SubscriptionService:
    """DB-only subscription service.

    Razorpay (`app.services.razorpay_service`) is the billing provider.
    This service owns DB reads + DB-only status transitions.
    """

    VALID_STATUSES = {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.PAUSED,
        SubscriptionStatus.CANCELED,
        SubscriptionStatus.PAYMENT_FAILED,
        SubscriptionStatus.PENDING,
    }

    VALID_VARIANTS = {"starter", "growth", "high"}

    def __init__(self, *args, **kwargs):
        # No provider client anymore. Args kept for backward-compat calls
        # like `SubscriptionService(paddle_client=...)` — silently ignored.
        pass

    # ── Validators / helpers ────────────────────────────────────────────

    def _validate_variant(self, variant: str) -> str:
        variant_lower = variant.lower().strip()
        if variant_lower not in self.VALID_VARIANTS:
            raise InvalidVariantError(
                f"Invalid variant: {variant}. "
                f"Must be one of: {', '.join(sorted(self.VALID_VARIANTS))}"
            )
        return variant_lower

    def _get_variant_price(self, variant: str) -> Decimal:
        return _get_price_from_config(variant, billing_cycle="monthly")

    def _is_upgrade(self, old_variant: str, new_variant: str) -> bool:
        try:
            old_vt = VariantType(normalize_variant_name(old_variant))
            new_vt = VariantType(normalize_variant_name(new_variant))
            return VARIANT_TIER_ORDER[new_vt] > VARIANT_TIER_ORDER[old_vt]
        except ValueError:
            return False

    def _calculate_period_end(self, start: datetime) -> datetime:
        import calendar
        month = start.month + 1
        year = start.year
        if month > 12:
            month = 1
            year += 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(start.day, last_day)
        return start.replace(year=year, month=month, day=day)

    def _calculate_proration(
        self,
        old_variant: str,
        new_variant: str,
        billing_cycle_start: Optional[datetime],
        billing_cycle_end: Optional[datetime],
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        if billing_cycle_start is None:
            billing_cycle_start = now.replace(day=1, hour=0, minute=0, second=0)
        if billing_cycle_end is None:
            billing_cycle_end = self._calculate_period_end(billing_cycle_start)
        if billing_cycle_start.tzinfo is None:
            billing_cycle_start = billing_cycle_start.replace(tzinfo=timezone.utc)
        if billing_cycle_end.tzinfo is None:
            billing_cycle_end = billing_cycle_end.replace(tzinfo=timezone.utc)

        old_price = self._get_variant_price(old_variant)
        new_price = self._get_variant_price(new_variant)

        total_period = billing_cycle_end - billing_cycle_start
        remaining = billing_cycle_end - now
        days_in_period = max(total_period.days, 1)
        days_remaining = max(remaining.days, 0)

        daily_rate_old = old_price / Decimal(days_in_period)
        daily_rate_new = new_price / Decimal(days_in_period)
        unused_amount = daily_rate_old * Decimal(days_remaining)
        new_charge = daily_rate_new * Decimal(days_remaining)
        proration_credit = unused_amount
        net_charge = new_charge - proration_credit

        return {
            "old_variant": old_variant,
            "new_variant": new_variant,
            "old_price": old_price,
            "new_price": new_price,
            "days_in_period": days_in_period,
            "days_remaining": days_remaining,
            "unused_amount": unused_amount.quantize(Decimal("0.01")),
            "proration_credit": proration_credit.quantize(Decimal("0.01")),
            "new_charge": new_charge.quantize(Decimal("0.01")),
            "net_charge": net_charge.quantize(Decimal("0.01")),
            "billing_cycle_start": billing_cycle_start.date(),
            "billing_cycle_end": billing_cycle_end.date(),
        }

    def _to_subscription_info(self, subscription: Subscription) -> SubscriptionInfo:
        variant = VariantType(normalize_variant_name(subscription.tier))
        limits_data = VARIANT_LIMITS.get(variant)
        price = VARIANT_PRICES.get(variant)

        limits = None
        if limits_data:
            limits = VariantLimits(
                variant=variant,
                monthly_tickets=limits_data["monthly_tickets"],
                ai_agents=limits_data["ai_agents"],
                team_members=limits_data["team_members"],
                voice_slots=limits_data["voice_slots"],
                kb_docs=limits_data["kb_docs"],
                price=price,
            )

        checkout_url = None
        if subscription.metadata_json:
            try:
                import json as _json
                meta = _json.loads(subscription.metadata_json)
                checkout_url = meta.get("checkout_url")
            except (TypeError, ValueError):
                pass

        return SubscriptionInfo(
            id=UUID(subscription.id),
            company_id=UUID(subscription.company_id),
            variant=variant,
            status=SubscriptionStatus(subscription.status),
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end or False,
            paddle_subscription_id=subscription.paddle_subscription_id,
            created_at=subscription.created_at,
            scheduled_change_type=getattr(subscription, "scheduled_change_type", None),
            scheduled_change_variant=getattr(subscription, "scheduled_change_variant", None),
            checkout_url=checkout_url,
            limits=limits,
        )

    # ── Reads ───────────────────────────────────────────────────────────

    async def get_subscription(self, company_id: UUID) -> Optional[SubscriptionInfo]:
        def _db_work():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                ).order_by(Subscription.created_at.desc()).first()
                if not subscription:
                    return None
                return self._to_subscription_info(subscription)
        return await asyncio.to_thread(_db_work)

    async def get_subscription_status(self, company_id: UUID) -> str:
        sub_info = await self.get_subscription(company_id)
        return sub_info.status.value if sub_info else "none"

    async def get_usage_info(self, company_id: UUID) -> Dict[str, Any]:
        """Current usage vs plan limits for the billing dashboard."""
        from database.models.billing_extended import UsageRecord, get_variant_limits

        def _db_work():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.PAST_DUE.value,
                        SubscriptionStatus.PENDING.value,
                    ]),
                ).order_by(Subscription.created_at.desc()).first()

                variant = subscription.tier if subscription else "starter"
                limits = get_variant_limits(variant)

                # Current month usage
                now = datetime.now(timezone.utc)
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                tickets_used = db.query(UsageRecord).filter(
                    UsageRecord.company_id == str(company_id),
                    UsageRecord.date >= month_start.date(),
                ).count() if hasattr(UsageRecord, "date") else 0

                return {
                    "variant": variant,
                    "tickets_used": tickets_used,
                    "ticket_limit": limits.get("monthly_tickets", 0) if limits else 0,
                    "subscription_status": subscription.status if subscription else "none",
                    "current_period_start": subscription.current_period_start.isoformat() if subscription and subscription.current_period_start else None,
                    "current_period_end": subscription.current_period_end.isoformat() if subscription and subscription.current_period_end else None,
                }
        return await asyncio.to_thread(_db_work)

    async def get_overage_history(self, company_id: UUID, limit: int = 50) -> Dict[str, Any]:
        from database.models.billing import OverageCharge

        def _db_work():
            with SessionLocal() as db:
                charges = db.query(OverageCharge).filter(
                    OverageCharge.company_id == str(company_id),
                ).order_by(OverageCharge.date.desc()).limit(limit).all()
                return {
                    "overage_charges": [
                        {
                            "id": str(c.id),
                            "date": c.date.isoformat() if c.date else None,
                            "tickets_over_limit": c.tickets_over_limit,
                            "charge_amount": str(c.charge_amount) if c.charge_amount else "0.00",
                            "status": c.status,
                        }
                        for c in charges
                    ],
                    "total": len(charges),
                }
        return await asyncio.to_thread(_db_work)

    # ── DB-only status transitions ──────────────────────────────────────

    async def cancel_subscription(
        self,
        company_id: UUID,
        user_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        effective_immediately: bool = False,
    ) -> Dict[str, Any]:
        """Cancel subscription in the local DB.

        Note: this does NOT cancel the Razorpay subscription. Use
        `app.services.razorpay_service.cancel_variant_subscription` for
        the provider-side cancellation (called from /api/billing/razorpay/cancel).
        This method is kept for the legacy /api/billing/cancel endpoint
        and for internal status flips after a Razorpay cancellation webhook.
        """
        canceled_at = datetime.now(timezone.utc)

        def _db_write():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.PAST_DUE.value,
                        SubscriptionStatus.PENDING.value,
                    ]),
                ).with_for_update().first()

                if not subscription:
                    raise SubscriptionNotFoundError(
                        f"No active subscription for company {company_id}"
                    )

                if effective_immediately:
                    subscription.status = SubscriptionStatus.CANCELED.value
                    subscription.cancel_at_period_end = False
                    subscription.scheduled_change_type = None
                    subscription.scheduled_change_variant = None
                    company = db.query(Company).filter(
                        Company.id == str(company_id)
                    ).first()
                    if company:
                        company.subscription_status = SubscriptionStatus.CANCELED.value
                else:
                    subscription.cancel_at_period_end = True
                    subscription.scheduled_change_type = "cancel"
                    subscription.scheduled_change_variant = None

                cancellation = CancellationRequest(
                    company_id=str(company_id),
                    user_id=str(user_id) if user_id else None,
                    reason=reason or "",
                    status="completed" if effective_immediately else "scheduled",
                )
                db.add(cancellation)
                db.commit()
                db.refresh(subscription)

                logger.info(
                    "subscription_canceled company_id=%s immediate=%s",
                    company_id,
                    effective_immediately,
                )
                return {
                    "subscription": self._to_subscription_info(subscription),
                    "cancellation": {
                        "effective_immediately": effective_immediately,
                        "access_until": (
                            None if effective_immediately
                            else subscription.current_period_end
                        ),
                        "canceled_at": canceled_at,
                    },
                    "message": (
                        "Subscription canceled immediately."
                        if effective_immediately else
                        f"Subscription will be canceled at end of billing period "
                        f"({subscription.current_period_end.isoformat() if subscription.current_period_end else 'period end'}). "
                        "You can continue using PARWA until then."
                    ),
                }
        return await asyncio.to_thread(_db_write)

    async def reactivate_subscription(self, company_id: UUID) -> SubscriptionInfo:
        """Reactivate a canceled-but-still-active subscription (DB only)."""
        def _db_write():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    or_(
                        Subscription.cancel_at_period_end == True,
                        Subscription.scheduled_change_type == "cancel",
                    ),
                ).with_for_update().first()

                if not subscription:
                    raise InvalidStatusTransitionError(
                        "No subscription pending cancellation to reactivate"
                    )

                subscription.cancel_at_period_end = False
                subscription.scheduled_change_type = None
                subscription.scheduled_change_variant = None
                db.commit()
                db.refresh(subscription)
                logger.info("subscription_reactivated company_id=%s", company_id)
                return self._to_subscription_info(subscription)
        return await asyncio.to_thread(_db_write)

    # ── Deprecated provider-side operations ─────────────────────────────

    async def create_subscription(self, *args, **kwargs):
        raise SubscriptionError(
            "Paddle is removed. Create subscriptions via Razorpay: "
            "POST /api/billing/razorpay/subscribe "
            "(see app.services.razorpay_service.create_variant_subscription)"
        )

    async def upgrade_subscription(self, *args, **kwargs):
        raise SubscriptionError(
            "Paddle is removed. To change tier, cancel the current Razorpay "
            "subscription and create a new one at the desired variant: "
            "POST /api/billing/razorpay/cancel then POST /api/billing/razorpay/subscribe"
        )

    async def downgrade_subscription(self, *args, **kwargs):
        raise SubscriptionError(
            "Paddle is removed. To change tier, cancel the current Razorpay "
            "subscription and create a new one at the desired variant."
        )


# ── Singleton ───────────────────────────────────────────────────────────

_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
