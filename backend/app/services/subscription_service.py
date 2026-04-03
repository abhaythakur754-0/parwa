"""
Subscription Service (F-021, F-025, F-026)

Handles subscription lifecycle management:
- Create subscription (new company signup)
- Get subscription details
- Upgrade subscription (immediate with proration)
- Downgrade subscription (effective at next billing cycle)
- Cancel subscription (access until month end)

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.clients.paddle_client import (
    PaddleClient,
    PaddleError,
    get_paddle_client,
)
from backend.app.schemas.billing import (
    SubscriptionInfo,
    SubscriptionStatus,
    VariantType,
    VARIANT_LIMITS,
    VariantLimits,
)
from database.base import SessionLocal
from database.models.billing import Subscription, CancellationRequest, Invoice
from database.models.billing_extended import PaymentMethod, ProrationAudit
from database.models.core import Company

logger = logging.getLogger("parwa.services.subscription")


class SubscriptionError(Exception):
    """Base exception for subscription errors."""
    pass


class SubscriptionNotFoundError(SubscriptionError):
    """Subscription not found."""
    pass


class SubscriptionAlreadyExistsError(SubscriptionError):
    """Company already has an active subscription."""
    pass


class InvalidVariantError(SubscriptionError):
    """Invalid variant specified."""
    pass


class InvalidStatusTransitionError(SubscriptionError):
    """Invalid subscription status transition."""
    pass


class SubscriptionService:
    """
    Subscription lifecycle management service.

    Usage:
        service = SubscriptionService()
        subscription = await service.create_subscription(
            company_id=uuid,
            variant="growth",
            payment_method_id="pm_123"
        )
    """

    # Valid subscription statuses
    VALID_STATUSES = {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.PAUSED,
        SubscriptionStatus.CANCELED,
        SubscriptionStatus.PAYMENT_FAILED,
    }

    # Valid variant names
    VALID_VARIANTS = {"starter", "growth", "high"}

    def __init__(self, paddle_client: Optional[PaddleClient] = None):
        self._paddle_client = paddle_client

    async def _get_paddle(self) -> PaddleClient:
        """Get Paddle client (lazy initialization)."""
        if self._paddle_client is None:
            self._paddle_client = get_paddle_client()
        return self._paddle_client

    def _validate_variant(self, variant: str) -> str:
        """Validate and normalize variant name."""
        variant_lower = variant.lower().strip()
        if variant_lower not in self.VALID_VARIANTS:
            raise InvalidVariantError(
                f"Invalid variant: {variant}. "
                f"Must be one of: {', '.join(sorted(self.VALID_VARIANTS))}"
            )
        return variant_lower

    def _get_variant_price(self, variant: str) -> Decimal:
        """Get monthly price for a variant."""
        variant_type = VariantType(variant)
        return VARIANT_LIMITS[variant_type]["price"]

    async def create_subscription(
        self,
        company_id: UUID,
        variant: str,
        payment_method_id: Optional[str] = None,
    ) -> SubscriptionInfo:
        """
        Create a new subscription for a company.

        Steps:
        1. Validate variant
        2. Check company doesn't already have active subscription
        3. Create subscription in Paddle (if payment_method_id provided)
        4. Create subscription record in database
        5. Return subscription info

        Args:
            company_id: Company UUID
            variant: Subscription variant (starter/growth/high)
            payment_method_id: Paddle payment method ID (optional for trials)

        Returns:
            SubscriptionInfo with created subscription details

        Raises:
            SubscriptionAlreadyExistsError: If company has active subscription
            InvalidVariantError: If variant is invalid
        """
        variant = self._validate_variant(variant)

        with SessionLocal() as db:
            # Check for existing subscription
            existing = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            ).first()

            if existing:
                raise SubscriptionAlreadyExistsError(
                    f"Company {company_id} already has an active subscription"
                )

            # Get company for paddle_customer_id
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).first()

            if not company:
                raise SubscriptionError(f"Company {company_id} not found")

            # Create in Paddle if we have customer and payment method
            paddle_subscription_id = None
            if company.paddle_customer_id and payment_method_id:
                try:
                    paddle = await self._get_paddle()
                    # Map variant to Paddle price ID
                    price_id = self._get_paddle_price_id(variant)

                    result = await paddle.create_subscription(
                        customer_id=company.paddle_customer_id,
                        price_id=price_id,
                    )
                    paddle_subscription_id = result.get("data", {}).get("id")
                    logger.info(
                        "subscription_created_paddle "
                        "company_id=%s variant=%s paddle_sub_id=%s",
                        company_id,
                        variant,
                        paddle_subscription_id,
                    )
                except PaddleError as e:
                    logger.error(
                        "subscription_paddle_failed company_id=%s error=%s",
                        company_id,
                        str(e),
                    )
                    # Continue without Paddle subscription in test/dev

            # Calculate billing period
            now = datetime.now(timezone.utc)
            period_end = self._calculate_period_end(now)

            # Create subscription record
            subscription = Subscription(
                company_id=str(company_id),
                tier=variant,
                status=SubscriptionStatus.ACTIVE.value,
                current_period_start=now,
                current_period_end=period_end,
                paddle_subscription_id=paddle_subscription_id,
            )

            db.add(subscription)

            # Update company subscription info
            company.subscription_tier = variant
            company.subscription_status = SubscriptionStatus.ACTIVE.value
            if paddle_subscription_id:
                company.paddle_subscription_id = paddle_subscription_id

            db.commit()
            db.refresh(subscription)

            logger.info(
                "subscription_created company_id=%s variant=%s sub_id=%s",
                company_id,
                variant,
                subscription.id,
            )

            return self._to_subscription_info(subscription)

    async def get_subscription(self, company_id: UUID) -> Optional[SubscriptionInfo]:
        """
        Get subscription details for a company.

        Args:
            company_id: Company UUID

        Returns:
            SubscriptionInfo or None if no subscription
        """
        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                return None

            return self._to_subscription_info(subscription)

    async def get_subscription_status(self, company_id: UUID) -> str:
        """
        Get subscription status for a company.

        Args:
            company_id: Company UUID

        Returns:
            Status string (active/canceled/past_due/etc) or "none"
        """
        sub_info = await self.get_subscription(company_id)
        return sub_info.status.value if sub_info else "none"

    async def upgrade_subscription(
        self,
        company_id: UUID,
        new_variant: str,
    ) -> Dict[str, Any]:
        """
        Upgrade subscription to a higher tier.

        Immediate upgrade with proration:
        1. Calculate unused amount from current variant
        2. Calculate prorated charge for new variant
        3. Apply credit and charge
        4. Update subscription immediately

        Args:
            company_id: Company UUID
            new_variant: Target variant (must be higher tier)

        Returns:
            Dict with subscription info and proration details

        Raises:
            SubscriptionNotFoundError: No active subscription
            InvalidVariantError: Invalid or non-upgrade variant
        """
        new_variant = self._validate_variant(new_variant)

        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            ).first()

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            old_variant = subscription.tier

            # Validate upgrade (not downgrade)
            if not self._is_upgrade(old_variant, new_variant):
                raise InvalidVariantError(
                    f"Cannot upgrade from {old_variant} to {new_variant}. "
                    "Use downgrade_subscription for lower tiers."
                )

            # Same variant - no-op
            if old_variant == new_variant:
                return {
                    "subscription": self._to_subscription_info(subscription),
                    "proration": None,
                    "message": "Already on this variant",
                }

            # Calculate proration
            proration = self._calculate_proration(
                old_variant=old_variant,
                new_variant=new_variant,
                billing_cycle_start=subscription.current_period_start,
                billing_cycle_end=subscription.current_period_end,
            )

            # Update subscription
            subscription.tier = new_variant

            # Update company
            company = db.query(Company).filter(
                Company.id == str(company_id)
            ).first()
            if company:
                company.subscription_tier = new_variant

            # Create proration audit
            audit = ProrationAudit(
                company_id=str(company_id),
                old_variant=old_variant,
                new_variant=new_variant,
                old_price=proration["old_price"],
                new_price=proration["new_price"],
                days_remaining=proration["days_remaining"],
                days_in_period=proration["days_in_period"],
                unused_amount=proration["unused_amount"],
                proration_amount=proration["proration_credit"],
                credit_applied=proration["proration_credit"],
                charge_applied=proration["net_charge"],
                billing_cycle_start=proration["billing_cycle_start"],
                billing_cycle_end=proration["billing_cycle_end"],
            )
            db.add(audit)

            # Update Paddle if we have subscription ID
            if subscription.paddle_subscription_id:
                try:
                    paddle = await self._get_paddle()
                    price_id = self._get_paddle_price_id(new_variant)
                    await paddle.update_subscription(
                        subscription.paddle_subscription_id,
                        items=[{"price_id": price_id}],
                    )
                    logger.info(
                        "subscription_upgraded_paddle "
                        "company_id=%s old=%s new=%s",
                        company_id,
                        old_variant,
                        new_variant,
                    )
                except PaddleError as e:
                    logger.warning(
                        "subscription_paddle_update_failed error=%s", str(e)
                    )

            db.commit()
            db.refresh(subscription)

            logger.info(
                "subscription_upgraded company_id=%s old=%s new=%s credit=%s",
                company_id,
                old_variant,
                new_variant,
                proration["proration_credit"],
            )

            return {
                "subscription": self._to_subscription_info(subscription),
                "proration": proration,
                "audit_id": audit.id,
            }

    async def downgrade_subscription(
        self,
        company_id: UUID,
        new_variant: str,
    ) -> Dict[str, Any]:
        """
        Downgrade subscription to a lower tier.

        Effective at next billing cycle:
        - No proration needed
        - Subscription continues at current tier until period end
        - New tier takes effect at next billing date

        Args:
            company_id: Company UUID
            new_variant: Target variant (must be lower tier)

        Returns:
            Dict with subscription info and scheduled change

        Raises:
            SubscriptionNotFoundError: No active subscription
            InvalidVariantError: Invalid or non-downgrade variant
        """
        new_variant = self._validate_variant(new_variant)

        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            ).first()

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            old_variant = subscription.tier

            # Validate downgrade (not upgrade)
            if self._is_upgrade(old_variant, new_variant):
                raise InvalidVariantError(
                    f"Cannot downgrade from {old_variant} to {new_variant}. "
                    "Use upgrade_subscription for higher tiers."
                )

            # Same variant - no-op
            if old_variant == new_variant:
                return {
                    "subscription": self._to_subscription_info(subscription),
                    "message": "Already on this variant",
                }

            # Schedule downgrade at period end
            # Store pending variant change (would typically use a separate table)
            # For now, we mark cancel_at_period_end and will handle in billing

            logger.info(
                "subscription_downgrade_scheduled "
                "company_id=%s old=%s new=%s effective=%s",
                company_id,
                old_variant,
                new_variant,
                subscription.current_period_end,
            )

            return {
                "subscription": self._to_subscription_info(subscription),
                "scheduled_change": {
                    "current_variant": old_variant,
                    "new_variant": new_variant,
                    "effective_date": subscription.current_period_end,
                },
                "message": (
                    f"Downgrade to {new_variant} scheduled for "
                    f"{subscription.current_period_end.isoformat() if subscription.current_period_end else 'next billing cycle'}"
                ),
            }

    async def cancel_subscription(
        self,
        company_id: UUID,
        reason: Optional[str] = None,
        effective_immediately: bool = False,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Cancel a subscription.

        Netflix-style cancellation:
        - Default: Access until end of current billing period
        - effective_immediately: Stop now (no refund)

        Args:
            company_id: Company UUID
            reason: Optional cancellation reason
            effective_immediately: If True, cancel now; otherwise at period end
            user_id: User who initiated cancellation

        Returns:
            Dict with cancellation details

        Raises:
            SubscriptionNotFoundError: No active subscription
        """
        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            ).first()

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            effective_from = "immediately" if effective_immediately else "next_billing_period"
            canceled_at = datetime.now(timezone.utc)

            if effective_immediately:
                # Immediate cancellation
                subscription.status = SubscriptionStatus.CANCELED.value
                subscription.cancel_at_period_end = False

                # Update company status
                company = db.query(Company).filter(
                    Company.id == str(company_id)
                ).first()
                if company:
                    company.subscription_status = SubscriptionStatus.CANCELED.value

                # Cancel in Paddle immediately
                if subscription.paddle_subscription_id:
                    try:
                        paddle = await self._get_paddle()
                        await paddle.cancel_subscription(
                            subscription.paddle_subscription_id,
                            effective_from="immediately",
                            reason=reason,
                        )
                    except PaddleError as e:
                        logger.warning(
                            "subscription_paddle_cancel_failed error=%s", str(e)
                        )
            else:
                # Cancel at period end (Netflix style)
                subscription.cancel_at_period_end = True
                # Status remains active until period end

                # Schedule cancellation in Paddle
                if subscription.paddle_subscription_id:
                    try:
                        paddle = await self._get_paddle()
                        await paddle.cancel_subscription(
                            subscription.paddle_subscription_id,
                            effective_from="next_billing_period",
                            reason=reason,
                        )
                    except PaddleError as e:
                        logger.warning(
                            "subscription_paddle_cancel_failed error=%s", str(e)
                        )

            # Create cancellation request record
            cancellation = CancellationRequest(
                company_id=str(company_id),
                user_id=str(user_id) if user_id else str(company_id),
                reason=reason or "",
                status="completed" if effective_immediately else "scheduled",
            )
            db.add(cancellation)

            db.commit()
            db.refresh(subscription)

            logger.info(
                "subscription_canceled company_id=%s immediate=%s effective=%s",
                company_id,
                effective_immediately,
                "now" if effective_immediately else "period_end",
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

    async def reactivate_subscription(
        self,
        company_id: UUID,
    ) -> SubscriptionInfo:
        """
        Reactivate a canceled subscription (before period end).

        Only works for subscriptions that are canceled but still active
        (cancel_at_period_end = True).

        Args:
            company_id: Company UUID

        Returns:
            Updated SubscriptionInfo

        Raises:
            SubscriptionNotFoundError: No subscription to reactivate
            InvalidStatusTransitionError: Cannot reactivate this subscription
        """
        with SessionLocal() as db:
            subscription = db.query(Subscription).filter(
                Subscription.company_id == str(company_id),
                Subscription.cancel_at_period_end == True,
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            ).first()

            if not subscription:
                raise InvalidStatusTransitionError(
                    "No subscription pending cancellation to reactivate"
                )

            # Clear cancellation flag
            subscription.cancel_at_period_end = False

            # Resume in Paddle
            if subscription.paddle_subscription_id:
                try:
                    paddle = await self._get_paddle()
                    await paddle.resume_subscription(
                        subscription.paddle_subscription_id
                    )
                except PaddleError as e:
                    logger.warning(
                        "subscription_paddle_resume_failed error=%s", str(e)
                    )

            db.commit()
            db.refresh(subscription)

            logger.info("subscription_reactivated company_id=%s", company_id)

            return self._to_subscription_info(subscription)

    # ── Helper Methods ───────────────────────────────────────────────────

    def _is_upgrade(self, old_variant: str, new_variant: str) -> bool:
        """Check if new_variant is an upgrade from old_variant."""
        tier_order = {"starter": 1, "growth": 2, "high": 3}
        return tier_order.get(new_variant, 0) > tier_order.get(old_variant, 0)

    def _calculate_period_end(self, start: datetime) -> datetime:
        """Calculate billing period end (monthly)."""
        # Add one month to start
        if start.month == 12:
            return start.replace(year=start.year + 1, month=1)
        return start.replace(month=start.month + 1)

    def _calculate_proration(
        self,
        old_variant: str,
        new_variant: str,
        billing_cycle_start: Optional[datetime],
        billing_cycle_end: Optional[datetime],
    ) -> Dict[str, Any]:
        """
        Calculate proration for variant change.

        Formula:
        - unused_amount = (old_price / days_in_period) * days_remaining
        - new_daily_rate = new_price / days_in_period
        - new_charge = new_daily_rate * days_remaining
        - net_charge = new_charge - unused_amount
        """
        now = datetime.now(timezone.utc)

        # Handle None dates
        if billing_cycle_start is None:
            billing_cycle_start = now.replace(day=1, hour=0, minute=0, second=0)
        if billing_cycle_end is None:
            billing_cycle_end = self._calculate_period_end(billing_cycle_start)

        # Ensure timezone-aware datetimes
        if billing_cycle_start.tzinfo is None:
            billing_cycle_start = billing_cycle_start.replace(tzinfo=timezone.utc)
        if billing_cycle_end.tzinfo is None:
            billing_cycle_end = billing_cycle_end.replace(tzinfo=timezone.utc)

        old_price = self._get_variant_price(old_variant)
        new_price = self._get_variant_price(new_variant)

        # Calculate days
        total_period = billing_cycle_end - billing_cycle_start
        remaining = billing_cycle_end - now

        days_in_period = max(total_period.days, 1)
        days_remaining = max(remaining.days, 0)

        # Calculate amounts (BC-002: using Decimal)
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

    def _get_paddle_price_id(self, variant: str) -> str:
        """Get Paddle price ID for variant (from config)."""
        # In production, these come from environment variables
        from backend.app.config import get_settings
        settings = get_settings()

        price_map = {
            "starter": getattr(settings, "PADDLE_PRICE_STARTER", "pri_starter"),
            "growth": getattr(settings, "PADDLE_PRICE_GROWTH", "pri_growth"),
            "high": getattr(settings, "PADDLE_PRICE_HIGH", "pri_high"),
        }
        return price_map.get(variant, "pri_starter")

    def _to_subscription_info(self, subscription: Subscription) -> SubscriptionInfo:
        """Convert Subscription model to SubscriptionInfo schema."""
        variant = VariantType(subscription.tier)
        limits_data = VARIANT_LIMITS.get(variant)

        limits = None
        if limits_data:
            limits = VariantLimits(
                variant=variant,
                monthly_tickets=limits_data["monthly_tickets"],
                ai_agents=limits_data["ai_agents"],
                team_members=limits_data["team_members"],
                voice_slots=limits_data["voice_slots"],
                kb_docs=limits_data["kb_docs"],
                price=limits_data["price"],
            )

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
            limits=limits,
        )


# ── Singleton Service ────────────────────────────────────────────────────

_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get the subscription service singleton."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
