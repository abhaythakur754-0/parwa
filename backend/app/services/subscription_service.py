"""
Subscription Service (F-021, F-025, F-026) — Day 4 Enhanced

Handles subscription lifecycle management:
- Create subscription (new company signup)
- Get subscription details
- Upgrade subscription (immediate with proration)
- Downgrade subscription (effective at next billing cycle)
- Cancel subscription (access until period end) with Netflix-style confirmation flow
- Yearly billing support (Y1-Y7)
- Exact 30-day billing periods (P1-P5)
- Period-end downgrade execution (D1-D6)
- Day 4: Cancel confirmation flow (C1), Period-end service stop (C3), Re-subscription (R1-R3)

BC-001: All operations validate company_id
BC-002: All money calculations use Decimal
"""

import calendar
import json as _json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.clients.paddle_client import (
    PaddleClient,
    PaddleError,
    get_paddle_client,
)
from app.schemas.billing import (
    BillingFrequency,
    SubscriptionInfo,
    SubscriptionStatus,
    VariantType,
    VARIANT_LIMITS,
    VariantLimits,
)
from database.base import SessionLocal
from database.models.billing import Subscription, CancellationRequest
from database.models.billing_extended import ProrationAudit
from database.models.core import Company

logger = logging.getLogger("parwa.services.subscription")

# ── Constants ──────────────────────────────────────────────────────────────

# P1/P3: All billing periods are exactly 30 days
BILLING_PERIOD_DAYS = 30

# Y4: Yearly period defaults
YEARLY_PERIOD_DAYS = 365

# D6: Undo window — 24 hours after downgrade execution
DOWNGRADE_UNDO_WINDOW_HOURS = 24

# D5: Pre-downgrade warning — 7 days before period end
PREDOWNGRADE_WARNING_DAYS = 7


class SubscriptionError(Exception):
    """Base exception for subscription errors."""


class SubscriptionNotFoundError(SubscriptionError):
    """Subscription not found."""


class SubscriptionAlreadyExistsError(SubscriptionError):
    """Company already has an active subscription."""


class InvalidVariantError(SubscriptionError):
    """Invalid variant specified."""


class InvalidStatusTransitionError(SubscriptionError):
    """Invalid subscription status transition."""


class DowngradeUndoExpiredError(SubscriptionError):
    """Downgrade undo window has expired."""


class SubscriptionService:
    """
    Subscription lifecycle management service.

    Usage:
        service = SubscriptionService()
        subscription = await service.create_subscription(
            company_id=uuid,
            variant="parwa",
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
    VALID_VARIANTS = {"mini_parwa", "parwa", "high_parwa"}

    # Valid billing frequencies
    VALID_FREQUENCIES = {"monthly", "yearly"}

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

    def _validate_frequency(self, frequency: str) -> str:
        """Validate and normalize billing frequency."""
        freq_lower = frequency.lower().strip()
        if freq_lower not in self.VALID_FREQUENCIES:
            raise SubscriptionError(
                f"Invalid billing frequency: {frequency}. "
                f"Must be one of: {', '.join(sorted(self.VALID_FREQUENCIES))}"
            )
        return freq_lower

    def _get_variant_price(self, variant: str, frequency: str = "monthly") -> Decimal:
        """Get price for a variant based on billing frequency."""
        variant_type = VariantType(variant)
        limits = VARIANT_LIMITS[variant_type]
        if frequency == "yearly":
            return limits.get("yearly_price", limits["price"] * 12)
        return limits["price"]

    # ═══════════════════════════════════════════════════════════════════
    # Period Calculation — P1/P2/P4/P5
    # ═══════════════════════════════════════════════════════════════════

    def _calculate_period_end(
        self,
        start: datetime,
        billing_frequency: str = "monthly",
    ) -> datetime:
        """
        Calculate billing period end.

        P1: Always use timedelta(days=30) for monthly (NOT variable month lengths).
        Y4: For yearly, use 365 days (366 for leap year).
        P5: Leap year check for yearly plans.

        Args:
            start: Period start datetime
            billing_frequency: 'monthly' or 'yearly'

        Returns:
            Period end datetime
        """
        if billing_frequency == "yearly":
            # P5: Yearly period = same date next year.
            # If the period crosses Feb 29 of a leap year, it's 366 days.
            end = start + timedelta(days=YEARLY_PERIOD_DAYS)
            end_candidate_366 = start + timedelta(days=366)
            # Check if any leap day falls within the period by examining
            # whether the next calendar year is a leap year and the period
            # crosses into it, or the start year is leap and start is before
            # Feb 29
            start_year = start.year
            next_year = start_year + 1
            use_366 = False
            # Case 1: Start year is leap and start is before Feb 29
            if calendar.isleap(start_year) and (
                start.month < 2 or (start.month == 2 and start.day <= 29)
            ):
                use_366 = True
            # Case 2: Next year is leap (period crosses into a leap year)
            if calendar.isleap(next_year):
                use_366 = True
            return end_candidate_366 if use_366 else end
        else:
            # P1: Monthly = exactly 30 days
            return start + timedelta(days=BILLING_PERIOD_DAYS)

    def _calculate_period_days(self, billing_frequency: str = "monthly") -> int:
        """
        Get the number of days in a billing period.

        P1: Monthly = 30 days.
        P5: Yearly = 365 or 366 days.

        Args:
            billing_frequency: 'monthly' or 'yearly'

        Returns:
            Number of days in the period
        """
        if billing_frequency == "yearly":
            return YEARLY_PERIOD_DAYS  # Default; actual may be 366
        return BILLING_PERIOD_DAYS

    def _calculate_period_days_for_range(
        self,
        start: datetime,
        end: datetime,
    ) -> int:
        """
        Calculate actual days in a period range.

        P5: For yearly, this accounts for leap year.

        Args:
            start: Period start
            end: Period end

        Returns:
            Number of days
        """
        delta = end - start
        return max(delta.days, 1)

    # ═══════════════════════════════════════════════════════════════════
    # Subscription Creation — Y3
    # ═══════════════════════════════════════════════════════════════════

    async def create_subscription(
        self,
        company_id: UUID,
        variant: str,
        payment_method_id: Optional[str] = None,
        billing_frequency: str = "monthly",
    ) -> SubscriptionInfo:
        """
        Create a new subscription for a company.

        Y3: Accept billing_frequency parameter for yearly subscriptions.

        Steps:
        1. Validate variant and frequency
        2. Check company doesn't already have active subscription
        3. Create subscription in Paddle (if payment_method_id provided)
        4. Create subscription record in database
        5. Return subscription info

        Args:
            company_id: Company UUID
            variant: Subscription variant (starter/growth/high)
            payment_method_id: Paddle payment method ID (optional for trials)
            billing_frequency: 'monthly' or 'yearly'

        Returns:
            SubscriptionInfo with created subscription details

        Raises:
            SubscriptionAlreadyExistsError: If company has active subscription
            InvalidVariantError: If variant is invalid
        """
        variant = self._validate_variant(variant)
        billing_frequency = self._validate_frequency(billing_frequency)

        with SessionLocal() as db:
            # Check for existing subscription with row lock (GAP 1 fix)
            existing = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .with_for_update()
                .first()
            )

            if existing:
                raise SubscriptionAlreadyExistsError(
                    f"Company {company_id} already has an active subscription"
                )

            # Get company for paddle_customer_id
            company = db.query(Company).filter(Company.id == str(company_id)).first()

            if not company:
                raise SubscriptionError(f"Company {company_id} not found")

            # Create in Paddle if we have customer and payment method
            paddle_subscription_id = None
            if company.paddle_customer_id and payment_method_id:
                try:
                    paddle = await self._get_paddle()
                    # Y2/Y3: Map variant + frequency to Paddle price ID
                    price_id = self._get_paddle_price_id(variant, billing_frequency)

                    result = await paddle.create_subscription(
                        customer_id=company.paddle_customer_id,
                        price_id=price_id,
                    )
                    paddle_subscription_id = result.get("data", {}).get("id")
                    logger.info(
                        "subscription_created_paddle "
                        "company_id=%s variant=%s freq=%s paddle_sub_id=%s",
                        company_id,
                        variant,
                        billing_frequency,
                        paddle_subscription_id,
                    )
                except PaddleError as e:
                    logger.error(
                        "subscription_paddle_failed company_id=%s error=%s",
                        company_id,
                        str(e),
                    )
                    # CRITICAL FIX: Mark subscription as payment_failed
                    # instead of silently continuing as 'active' when Paddle
                    # has no record. Store failure details in metadata_json.
                    paddle_subscription_id = None

            # Determine subscription status based on Paddle success
            # If Paddle call was attempted (company has customer + payment)
            # but failed, the subscription must NOT be marked active.
            paddle_sync_pending = False
            if (
                company.paddle_customer_id
                and payment_method_id
                and paddle_subscription_id is None
            ):
                # Paddle was required but failed — do not grant active access
                effective_status = SubscriptionStatus.PAYMENT_FAILED.value
                paddle_sync_pending = True
            else:
                # No Paddle call attempted (no customer/payment yet)
                # or Paddle succeeded — safe to proceed
                effective_status = SubscriptionStatus.ACTIVE.value

            # Calculate billing period
            now = datetime.now(timezone.utc)
            period_end = self._calculate_period_end(now, billing_frequency)
            period_days = self._calculate_period_days_for_range(now, period_end)

            # Build metadata JSON with Paddle sync info
            metadata = None
            if paddle_sync_pending:
                metadata = _json.dumps(
                    {
                        "paddle_sync_pending": True,
                        "paddle_creation_failed": True,
                        "note": "Paddle subscription creation failed; "
                        "retry via reconciliation or manual setup",
                    }
                )

            # Create subscription record
            subscription = Subscription(
                company_id=str(company_id),
                tier=variant,
                status=effective_status,
                current_period_start=now,
                current_period_end=period_end,
                paddle_subscription_id=paddle_subscription_id,
                billing_frequency=billing_frequency,
                days_in_period=period_days,
                metadata_json=metadata,
            )

            db.add(subscription)

            # Update company subscription info
            company.subscription_tier = variant
            company.subscription_status = effective_status
            if paddle_subscription_id:
                company.paddle_subscription_id = paddle_subscription_id

            db.commit()
            db.refresh(subscription)

            logger.info(
                "subscription_created company_id=%s variant=%s freq=%s sub_id=%s",
                company_id,
                variant,
                billing_frequency,
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
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )

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

    # ═══════════════════════════════════════════════════════════════════
    # Upgrade — Y5: Support yearly proration
    # ═══════════════════════════════════════════════════════════════════

    async def upgrade_subscription(
        self,
        company_id: UUID,
        new_variant: str,
    ) -> Dict[str, Any]:
        """
        Upgrade subscription to a higher tier.

        Immediate upgrade with proration.
        Y5: If customer is yearly, proration uses annual price / 365.

        Args:
            company_id: Company UUID
            new_variant: Target variant (must be higher tier)

        Returns:
            Dict with subscription info and proration details
        """
        new_variant = self._validate_variant(new_variant)

        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .with_for_update()
                .first()
            )

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            old_variant = subscription.tier
            billing_frequency = (
                getattr(subscription, "billing_frequency", "monthly") or "monthly"
            )

            if not self._is_upgrade(old_variant, new_variant):
                raise InvalidVariantError(
                    f"Cannot upgrade from {old_variant} to {new_variant}. "
                    "Use downgrade_subscription for lower tiers."
                )

            if old_variant == new_variant:
                return {
                    "subscription": self._to_subscription_info(subscription),
                    "proration": None,
                    "message": "Already on this variant",
                }

            # Calculate proration (frequency-aware)
            proration = self._calculate_proration(
                old_variant=old_variant,
                new_variant=new_variant,
                billing_cycle_start=subscription.current_period_start,
                billing_cycle_end=subscription.current_period_end,
                billing_frequency=billing_frequency,
            )

            # Update subscription
            subscription.tier = new_variant

            # Update company
            company = db.query(Company).filter(Company.id == str(company_id)).first()
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
                    price_id = self._get_paddle_price_id(new_variant, billing_frequency)
                    await paddle.update_subscription(
                        subscription.paddle_subscription_id,
                        items=[{"price_id": price_id}],
                    )
                    logger.info(
                        "subscription_upgraded_paddle "
                        "company_id=%s old=%s new=%s freq=%s",
                        company_id,
                        old_variant,
                        new_variant,
                        billing_frequency,
                    )
                except PaddleError as e:
                    logger.warning("subscription_paddle_update_failed error=%s", str(e))

            db.commit()
            db.refresh(subscription)

            logger.info(
                "subscription_upgraded company_id=%s old=%s new=%s credit=%s freq=%s",
                company_id,
                old_variant,
                new_variant,
                proration["proration_credit"],
                billing_frequency,
            )

            return {
                "subscription": self._to_subscription_info(subscription),
                "proration": proration,
                "audit_id": audit.id,
            }

    # ═══════════════════════════════════════════════════════════════════
    # Downgrade — D2: Store pending_downgrade_tier on model
    # ═══════════════════════════════════════════════════════════════════

    async def downgrade_subscription(
        self,
        company_id: UUID,
        new_variant: str,
    ) -> Dict[str, Any]:
        """
        Downgrade subscription to a lower tier.

        Effective at next billing cycle.
        D2: Store pending_downgrade_tier on subscription model.

        Args:
            company_id: Company UUID
            new_variant: Target variant (must be lower tier)

        Returns:
            Dict with subscription info and scheduled change
        """
        new_variant = self._validate_variant(new_variant)

        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .with_for_update()
                .first()
            )

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            old_variant = subscription.tier

            if self._is_upgrade(old_variant, new_variant):
                raise InvalidVariantError(
                    f"Cannot downgrade from {old_variant} to {new_variant}. "
                    "Use upgrade_subscription for higher tiers."
                )

            if old_variant == new_variant:
                return {
                    "subscription": self._to_subscription_info(subscription),
                    "message": "Already on this variant",
                }

            # Schedule downgrade at period end
            now_ts = datetime.now(timezone.utc)

            # D2: Use pending_downgrade_tier column (Day 2 model)
            subscription.pending_downgrade_tier = new_variant
            subscription.cancel_at_period_end = True
            subscription.pending_downgrade_at = now_ts

            db.commit()
            db.refresh(subscription)

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
                    f"{
                        subscription.current_period_end.isoformat() if subscription.current_period_end else 'next billing cycle'}"
                ),
            }

    # ═══════════════════════════════════════════════════════════════════
    # Cancel — D3: Support scheduled cancellation at period end
    # ═══════════════════════════════════════════════════════════════════

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
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .with_for_update()
                .first()
            )

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            effective_from = (
                "immediately" if effective_immediately else "next_billing_period"
            )
            canceled_at = datetime.now(timezone.utc)

            if effective_immediately:
                subscription.status = SubscriptionStatus.CANCELED.value
                subscription.cancel_at_period_end = False

                company = (
                    db.query(Company).filter(Company.id == str(company_id)).first()
                )
                if company:
                    company.subscription_status = SubscriptionStatus.CANCELED.value

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
                subscription.cancel_at_period_end = True

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
                        None
                        if effective_immediately
                        else subscription.current_period_end
                    ),
                    "canceled_at": canceled_at,
                },
                "message": (
                    "Subscription canceled immediately."
                    if effective_immediately
                    else "Subscription will be canceled at end of billing period "
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
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.cancel_at_period_end,
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .with_for_update()
                .first()
            )

            if not subscription:
                raise InvalidStatusTransitionError(
                    "No subscription pending cancellation to reactivate"
                )

            subscription.cancel_at_period_end = False
            subscription.pending_downgrade_tier = None  # Clear pending downgrade too

            if subscription.paddle_subscription_id:
                try:
                    paddle = await self._get_paddle()
                    await paddle.resume_subscription(
                        subscription.paddle_subscription_id
                    )
                except PaddleError as e:
                    logger.warning("subscription_paddle_resume_failed error=%s", str(e))

            db.commit()
            db.refresh(subscription)

            logger.info("subscription_reactivated company_id=%s", company_id)

            return self._to_subscription_info(subscription)

    # ═══════════════════════════════════════════════════════════════════
    # D6: Downgrade Undo (within 24 hours)
    # ═══════════════════════════════════════════════════════════════════

    async def undo_downgrade(
        self,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        Undo a recently executed downgrade.

        D6: Within 24 hours of downgrade execution, restore the previous
        tier, unpause agents, restore team roles, unarchive docs.

        Args:
            company_id: Company UUID

        Returns:
            Dict with restored subscription info

        Raises:
            SubscriptionNotFoundError: No subscription found
            DowngradeUndoExpiredError: 24-hour window has passed
            SubscriptionError: No downgrade to undo
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .with_for_update()
                .first()
            )

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            if not subscription.downgrade_executed_at:
                raise SubscriptionError("No recent downgrade to undo")

            # Check 24-hour window
            now = datetime.now(timezone.utc)
            executed_at = subscription.downgrade_executed_at
            if executed_at.tzinfo is None:
                executed_at = executed_at.replace(tzinfo=timezone.utc)

            elapsed = now - executed_at
            if elapsed.total_seconds() > DOWNGRADE_UNDO_WINDOW_HOURS * 3600:
                raise DowngradeUndoExpiredError(
                    "Downgrade undo window expired. "
                    f"Downgrade was executed {
                        elapsed.total_seconds()
                        / 3600:.1f} "
                    f"hours ago (limit: {DOWNGRADE_UNDO_WINDOW_HOURS} hours)."
                )

            # Restore previous tier
            old_tier = subscription.previous_tier
            new_tier = subscription.tier

            subscription.tier = old_tier
            subscription.previous_tier = None
            subscription.downgrade_executed_at = None

            # Update company
            company = db.query(Company).filter(Company.id == str(company_id)).first()
            if company:
                company.subscription_tier = old_tier

            db.commit()
            db.refresh(subscription)

            # D4 undo: Restore resources
            try:
                await self._restore_resources_after_undo(
                    db, company_id, old_tier, new_tier
                )
            except Exception as e:
                logger.error(
                    "downgrade_undo_resource_restore_failed " "company_id=%s error=%s",
                    company_id,
                    str(e),
                )

            logger.info(
                "downgrade_undo company_id=%s restored_to=%s",
                company_id,
                old_tier,
            )

            return {
                "subscription": self._to_subscription_info(subscription),
                "restored_to": old_tier,
                "downgraded_from": new_tier,
                "message": (f"Downgrade undone. Subscription restored to {old_tier}."),
            }

    # ═══════════════════════════════════════════════════════════════════
    # Y7: Switch Billing Frequency (monthly ↔ yearly)
    # ═══════════════════════════════════════════════════════════════════

    async def switch_billing_frequency(
        self,
        company_id: UUID,
        new_frequency: str,
    ) -> Dict[str, Any]:
        """
        Switch billing frequency (monthly ↔ yearly).

        Same tier, different frequency. Prorate remaining period.

        Args:
            company_id: Company UUID
            new_frequency: 'monthly' or 'yearly'

        Returns:
            Dict with updated subscription and proration details
        """
        new_frequency = self._validate_frequency(new_frequency)

        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .with_for_update()
                .first()
            )

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            current_frequency = (
                getattr(subscription, "billing_frequency", "monthly") or "monthly"
            )

            if current_frequency == new_frequency:
                return {
                    "subscription": self._to_subscription_info(subscription),
                    "message": f"Already on {new_frequency} billing",
                }

            variant = subscription.tier

            # Calculate proration for remaining period
            now = datetime.now(timezone.utc)
            period_end = subscription.current_period_end
            if period_end and period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)

            if period_end and now < period_end:
                remaining_days = (period_end - now).days
            else:
                remaining_days = 0

            # Calculate credit from old frequency
            old_price = self._get_variant_price(variant, current_frequency)
            old_period_days = getattr(
                subscription, "days_in_period", None
            ) or self._calculate_period_days(current_frequency)

            credit = (old_price / Decimal(max(old_period_days, 1))) * Decimal(
                max(remaining_days, 0)
            )

            # Calculate charge for new frequency
            new_price = self._get_variant_price(variant, new_frequency)
            new_period_days = self._calculate_period_days(new_frequency)

            charge = (new_price / Decimal(max(new_period_days, 1))) * Decimal(
                max(remaining_days, 0)
            )

            net_charge = charge - credit

            # Update subscription
            subscription.billing_frequency = new_frequency

            # Recalculate period end with new frequency
            new_period_end = self._calculate_period_end(now, new_frequency)
            new_period_days_actual = self._calculate_period_days_for_range(
                now, new_period_end
            )
            subscription.current_period_start = now
            subscription.current_period_end = new_period_end
            subscription.days_in_period = new_period_days_actual

            # Update Paddle if we have subscription ID
            if subscription.paddle_subscription_id:
                try:
                    paddle = await self._get_paddle()
                    price_id = self._get_paddle_price_id(variant, new_frequency)
                    await paddle.update_subscription(
                        subscription.paddle_subscription_id,
                        items=[{"price_id": price_id}],
                    )
                    logger.info(
                        "frequency_switched_paddle "
                        "company_id=%s variant=%s old_freq=%s new_freq=%s",
                        company_id,
                        variant,
                        current_frequency,
                        new_frequency,
                    )
                except PaddleError as e:
                    logger.warning("frequency_switch_paddle_failed error=%s", str(e))

            db.commit()
            db.refresh(subscription)

            logger.info(
                "frequency_switched company_id=%s variant=%s %s→%s",
                company_id,
                variant,
                current_frequency,
                new_frequency,
            )

            return {
                "subscription": self._to_subscription_info(subscription),
                "credit_from_old": str(credit.quantize(Decimal("0.01"))),
                "charge_for_new": str(charge.quantize(Decimal("0.01"))),
                "net_charge": str(net_charge.quantize(Decimal("0.01"))),
                "remaining_days": remaining_days,
                "message": (f"Switched from {current_frequency} to {new_frequency}."),
            }

    # ═══════════════════════════════════════════════════════════════════
    # D1-D4: Period-End Transition Processing
    # ═══════════════════════════════════════════════════════════════════

    def process_period_end_transitions(self) -> Dict[str, Any]:
        """
        D1: Period-end automation cron task.

        Runs daily at midnight UTC. Processes:
        - D2: Subscriptions with pending_downgrade_tier where period_end <= today
        - D3: Subscriptions with cancel_at_period_end=True where period_end <= today

        Returns:
            Dict with processing summary
        """
        now = datetime.now(timezone.utc)
        results = {
            "timestamp": now.isoformat(),
            "downgrades_applied": 0,
            "cancellations_applied": 0,
            "variants_archived": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            # D2: Find subscriptions with pending downgrade
            pending_downgrades = (
                db.query(Subscription)
                .filter(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.pending_downgrade_tier.isnot(None),
                    Subscription.current_period_end <= now,
                )
                .all()
            )

            for sub in pending_downgrades:
                try:
                    self._apply_pending_downgrade(db, sub)
                    results["downgrades_applied"] += 1
                except Exception as e:
                    logger.error(
                        "period_end_downgrade_failed sub_id=%s error=%s",
                        sub.id,
                        str(e),
                    )
                    results["errors"].append(
                        {
                            "subscription_id": sub.id,
                            "type": "downgrade",
                            "error": str(e)[:200],
                        }
                    )

            # D3: Find subscriptions with scheduled cancellation (no pending
            # downgrade)
            pending_cancellations = (
                db.query(Subscription)
                .filter(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.cancel_at_period_end,
                    Subscription.pending_downgrade_tier.is_(None),
                    Subscription.current_period_end <= now,
                )
                .all()
            )

            for sub in pending_cancellations:
                try:
                    self._apply_scheduled_cancellation(db, sub)
                    results["cancellations_applied"] += 1
                except Exception as e:
                    logger.error(
                        "period_end_cancellation_failed sub_id=%s error=%s",
                        sub.id,
                        str(e),
                    )
                    results["errors"].append(
                        {
                            "subscription_id": sub.id,
                            "type": "cancellation",
                            "error": str(e)[:200],
                        }
                    )

            db.commit()

            # V7: Process variant removals at period end
            try:
                from app.services.variant_addon_service import get_variant_addon_service

                addon_service = get_variant_addon_service()
                variant_results = addon_service.process_variant_period_end()
                results["variants_archived"] = variant_results.get("archived_count", 0)
                if variant_results.get("errors"):
                    results["errors"].extend(
                        [
                            {"type": "variant_archival", "error": e}
                            for e in variant_results["errors"]
                        ]
                    )
            except Exception as e:
                logger.error("variant_period_end_failed error=%s", str(e))
                results["errors"].append(
                    {
                        "type": "variant_period_end",
                        "error": str(e)[:200],
                    }
                )

        logger.info(
            "period_end_transitions_processed "
            "downgrades=%d cancellations=%d variants_archived=%d errors=%d",
            results["downgrades_applied"],
            results["cancellations_applied"],
            results["variants_archived"],
            len(results["errors"]),
        )

        return results

    def _apply_pending_downgrade(
        self,
        db: Session,
        subscription: Subscription,
    ) -> None:
        """
        D2: Apply pending downgrade at period end.

        Steps:
        1. Update subscription.tier to pending variant
        2. Update company.subscription_tier
        3. Clear pending_downgrade_variant
        4. Set new period dates
        5. Sync to Paddle
        6. D4: Cleanup resources
        """
        old_tier = subscription.tier
        new_tier = subscription.pending_downgrade_tier
        billing_frequency = (
            getattr(subscription, "billing_frequency", "monthly") or "monthly"
        )
        now = datetime.now(timezone.utc)

        # Store previous tier for undo (D6)
        subscription.previous_tier = old_tier
        subscription.downgrade_executed_at = now

        # Apply tier change
        subscription.tier = new_tier
        subscription.pending_downgrade_tier = None
        subscription.cancel_at_period_end = False
        subscription.pending_downgrade_at = None

        # Calculate new period
        new_period_end = self._calculate_period_end(now, billing_frequency)
        new_period_days = self._calculate_period_days_for_range(now, new_period_end)
        subscription.current_period_start = now
        subscription.current_period_end = new_period_end
        subscription.days_in_period = new_period_days

        # Update company
        company = (
            db.query(Company).filter(Company.id == subscription.company_id).first()
        )
        if company:
            company.subscription_tier = new_tier

        db.flush()

        # D4: Resource cleanup on downgrade
        try:
            self._cleanup_resources_on_downgrade(
                db, subscription.company_id, old_tier, new_tier
            )
        except Exception as e:
            logger.error(
                "resource_cleanup_failed company_id=%s error=%s",
                subscription.company_id,
                str(e),
            )

        logger.info(
            "pending_downgrade_applied " "company_id=%s old=%s new=%s freq=%s",
            subscription.company_id,
            old_tier,
            new_tier,
            billing_frequency,
        )

    def _apply_scheduled_cancellation(
        self,
        db: Session,
        subscription: Subscription,
    ) -> None:
        """
        D3: Apply scheduled cancellation at period end.

        Steps:
        1. Set status='canceled'
        2. Clear cancel_at_period_end flag
        3. Trigger 30-day data retention timer
        4. C3: Apply service stop (pause agents, disable team, disable channels)
        """
        subscription.status = SubscriptionStatus.CANCELED.value
        subscription.cancel_at_period_end = False

        # Set service_stopped_at for retention tracking
        now = datetime.now(timezone.utc)
        if hasattr(subscription, "service_stopped_at"):
            subscription.service_stopped_at = now  # type: ignore

        # Update company status
        company = (
            db.query(Company).filter(Company.id == subscription.company_id).first()
        )
        if company:
            company.subscription_status = SubscriptionStatus.CANCELED.value

        # C3: Apply service stop on cancel
        try:
            self._apply_service_stop_on_cancel(db, subscription.company_id)
        except Exception as e:
            logger.error(
                "service_stop_on_cancel_failed company_id=%s error=%s",
                subscription.company_id,
                str(e),
            )

        logger.info(
            "scheduled_cancellation_applied company_id=%s sub_id=%s",
            subscription.company_id,
            subscription.id,
        )

    # ═══════════════════════════════════════════════════════════════════
    # D4: Resource Cleanup on Downgrade
    # ═══════════════════════════════════════════════════════════════════

    def _cleanup_resources_on_downgrade(
        self,
        db: Session,
        company_id: str,
        old_tier: str,
        new_tier: str,
    ) -> Dict[str, Any]:
        """
        D4: Resource cleanup when downgrading.

        After tier change:
        (a) Pause extra AI agents — set status='paused' beyond new limit
        (b) Downgrade extra team members — set role='viewer' beyond new limit
        (c) Archive extra KB docs — set is_archived=True beyond new limit
        (d) Disable voice channels — stop accepting voice calls

        Args:
            db: Database session
            company_id: Company ID string
            old_tier: Previous tier name
            new_tier: New tier name

        Returns:
            Dict with cleanup summary
        """
        old_limits = VARIANT_LIMITS.get(VariantType(old_tier), {})
        new_limits = VARIANT_LIMITS.get(VariantType(new_tier), {})

        cleanup = {
            "agents_paused": 0,
            "team_members_downgraded": 0,
            "kb_docs_archived": 0,
            "voice_channels_disabled": 0,
        }

        # (a) Pause extra AI agents
        try:
            from database.models.core import Agent

            agent_limit = new_limits.get("ai_agents", 1)
            active_agents = (
                db.query(Agent)
                .filter(
                    Agent.company_id == company_id,
                    Agent.status == "active",
                )
                .order_by(Agent.created_at.asc())
                .all()
            )

            for i, agent in enumerate(active_agents):
                if i >= agent_limit:
                    agent.status = "paused"
                    cleanup["agents_paused"] += 1
        except Exception as e:
            logger.warning("agent_cleanup_failed error=%s", str(e))

        # (b) Downgrade extra team members
        try:
            from database.models.core import User

            member_limit = new_limits.get("team_members", 3)
            active_members = (
                db.query(User)
                .filter(
                    User.company_id == company_id,
                    User.is_active,
                    User.role != "owner",
                )
                .order_by(User.created_at.asc())
                .all()
            )

            for i, member in enumerate(active_members):
                if i >= member_limit:
                    member.role = "viewer"
                    cleanup["team_members_downgraded"] += 1
        except Exception as e:
            logger.warning("team_cleanup_failed error=%s", str(e))

        # (c) Archive extra KB docs
        try:
            from database.models.provisioning import KnowledgeBaseDocument

            kb_limit = new_limits.get("kb_docs", 100)
            active_docs = (
                db.query(KnowledgeBaseDocument)
                .filter(
                    KnowledgeBaseDocument.company_id == company_id,
                    KnowledgeBaseDocument.is_archived is False,
                )
                .order_by(KnowledgeBaseDocument.created_at.asc())
                .all()
            )

            for i, doc in enumerate(active_docs):
                if i >= kb_limit:
                    doc.is_archived = True
                    cleanup["kb_docs_archived"] += 1
        except Exception as e:
            logger.warning("kb_cleanup_failed error=%s", str(e))

        # (d) Disable voice channels
        try:
            voice_limit = new_limits.get("voice_slots", 0)
            old_voice_slots = old_limits.get("voice_slots", 0)
            if voice_limit < old_voice_slots:
                disabled = old_voice_slots - voice_limit
                cleanup["voice_channels_disabled"] = disabled
                # TODO: Integration with voice service to actually disable
                # channels
        except Exception as e:
            logger.warning("voice_cleanup_failed error=%s", str(e))

        logger.info(
            "resource_cleanup_completed company_id=%s %s→%s "
            "agents=%d team=%d kb=%d voice=%d",
            company_id,
            old_tier,
            new_tier,
            cleanup["agents_paused"],
            cleanup["team_members_downgraded"],
            cleanup["kb_docs_archived"],
            cleanup["voice_channels_disabled"],
        )

        return cleanup

    # ═══════════════════════════════════════════════════════════════════
    # D6: Restore Resources After Undo
    # ═══════════════════════════════════════════════════════════════════

    async def _restore_resources_after_undo(
        self,
        db: Session,
        company_id: str,
        restored_tier: str,
        previous_downgraded_tier: str,
    ) -> Dict[str, Any]:
        """
        D6: Restore resources after undoing a downgrade.

        Reverse of _cleanup_resources_on_downgrade:
        - Unpause agents
        - Restore team member roles
        - Unarchive KB docs
        - Re-enable voice channels
        """
        restored_limits = VARIANT_LIMITS.get(VariantType(restored_tier), {})

        restored = {
            "agents_unpaused": 0,
            "team_members_restored": 0,
            "kb_docs_unarchived": 0,
            "voice_channels_enabled": 0,
        }

        # (a) Unpause agents
        try:
            from database.models.core import Agent

            agent_limit = restored_limits.get("ai_agents", 1)
            paused_agents = (
                db.query(Agent)
                .filter(
                    Agent.company_id == company_id,
                    Agent.status == "paused",
                )
                .order_by(Agent.created_at.asc())
                .limit(agent_limit)
                .all()
            )

            for agent in paused_agents:
                agent.status = "active"
                restored["agents_unpaused"] += 1
        except Exception as e:
            logger.warning("agent_restore_failed error=%s", str(e))

        # (b) Restore team member roles
        try:
            from database.models.core import User

            viewer_members = (
                db.query(User)
                .filter(
                    User.company_id == company_id,
                    User.is_active,
                    User.role == "viewer",
                )
                .all()
            )

            for member in viewer_members:
                member.role = "agent"  # Restore default non-owner role
                restored["team_members_restored"] += 1
        except Exception as e:
            logger.warning("team_restore_failed error=%s", str(e))

        # (c) Unarchive KB docs
        try:
            from database.models.provisioning import KnowledgeBaseDocument

            archived_docs = (
                db.query(KnowledgeBaseDocument)
                .filter(
                    KnowledgeBaseDocument.company_id == company_id,
                    KnowledgeBaseDocument.is_archived,
                )
                .limit(restored_limits.get("kb_docs", 100))
                .all()
            )

            for doc in archived_docs:
                doc.is_archived = False
                restored["kb_docs_unarchived"] += 1
        except Exception as e:
            logger.warning("kb_restore_failed error=%s", str(e))

        # (d) Re-enable voice channels
        voice_slots = restored_limits.get("voice_slots", 0)
        if voice_slots > 0:
            restored["voice_channels_enabled"] = voice_slots

        db.commit()

        logger.info(
            "resource_restore_completed company_id=%s restored_to=%s "
            "agents=%d team=%d kb=%d voice=%d",
            company_id,
            restored_tier,
            restored["agents_unpaused"],
            restored["team_members_restored"],
            restored["kb_docs_unarchived"],
            restored["voice_channels_enabled"],
        )

        return restored

    # ═══════════════════════════════════════════════════════════════════
    # D5: Pre-Downgrade Warning (7 days before period end)
    # ═══════════════════════════════════════════════════════════════════

    def check_pre_downgrade_warnings(self) -> Dict[str, Any]:
        """
        D5: Check and send pre-downgrade warnings.

        7 days before period end with pending downgrade, send email
        + notification warning about what resources will be affected.

        Returns:
            Dict with warning summary
        """
        now = datetime.now(timezone.utc)
        warning_threshold = now + timedelta(days=PREDOWNGRADE_WARNING_DAYS)

        results = {
            "timestamp": now.isoformat(),
            "warnings_sent": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            # Find subscriptions needing warning
            subscriptions = (
                db.query(Subscription)
                .filter(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.pending_downgrade_tier.isnot(None),
                    Subscription.current_period_end > now,
                    Subscription.current_period_end <= warning_threshold,
                )
                .all()
            )

            for sub in subscriptions:
                try:
                    warning_data = self._build_downgrade_warning_data(db, sub)
                    # Send notification (email + socket.io)
                    try:
                        from app.core.event_emitter import emit_billing_event
                        import asyncio

                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                emit_billing_event(
                                    company_id=sub.company_id,
                                    event_type="pre_downgrade_warning",
                                    data=warning_data,
                                )
                            )
                        finally:
                            loop.close()
                    except Exception as e:
                        logger.warning(
                            "pre_downgrade_socket_failed company_id=%s error=%s",
                            sub.company_id,
                            str(e),
                        )

                    results["warnings_sent"] += 1
                except Exception as e:
                    logger.error(
                        "pre_downgrade_warning_failed sub_id=%s error=%s",
                        sub.id,
                        str(e),
                    )
                    results["errors"].append(
                        {
                            "subscription_id": sub.id,
                            "error": str(e)[:200],
                        }
                    )

        logger.info(
            "pre_downgrade_warnings_processed sent=%d errors=%d",
            results["warnings_sent"],
            len(results["errors"]),
        )

        return results

    def _build_downgrade_warning_data(
        self,
        db: Session,
        subscription: Subscription,
    ) -> Dict[str, Any]:
        """
        Build warning data listing affected resources.

        D5: "In 7 days, 2 agents will be paused, 7 team members will
        lose access, 400 documents will be archived."
        """
        old_tier = subscription.tier
        new_tier = subscription.pending_downgrade_tier

        old_limits = VARIANT_LIMITS.get(VariantType(old_tier), {})
        new_limits = VARIANT_LIMITS.get(VariantType(new_tier), {})

        # Count current resources
        agents_paused = 0
        team_downgraded = 0
        docs_archived = 0

        try:
            from database.models.core import Agent

            agent_limit = new_limits.get("ai_agents", 1)
            active_count = (
                db.query(Agent)
                .filter(
                    Agent.company_id == subscription.company_id,
                    Agent.status == "active",
                )
                .count()
            )
            agents_paused = max(0, active_count - agent_limit)
        except Exception:
            pass

        try:
            from database.models.core import User

            member_limit = new_limits.get("team_members", 3)
            member_count = (
                db.query(User)
                .filter(
                    User.company_id == subscription.company_id,
                    User.is_active,
                    User.role != "owner",
                )
                .count()
            )
            team_downgraded = max(0, member_count - member_limit)
        except Exception:
            pass

        try:
            from database.models.provisioning import KnowledgeBaseDocument

            kb_limit = new_limits.get("kb_docs", 100)
            doc_count = (
                db.query(KnowledgeBaseDocument)
                .filter(
                    KnowledgeBaseDocument.company_id == subscription.company_id,
                    KnowledgeBaseDocument.is_archived is False,
                )
                .count()
            )
            docs_archived = max(0, doc_count - kb_limit)
        except Exception:
            pass

        return {
            "company_id": subscription.company_id,
            "current_tier": old_tier,
            "new_tier": new_tier,
            "effective_date": (
                subscription.current_period_end.isoformat()
                if subscription.current_period_end
                else None
            ),
            "days_until_change": PREDOWNGRADE_WARNING_DAYS,
            "affected_resources": {
                "agents_to_pause": agents_paused,
                "team_members_to_downgrade": team_downgraded,
                "kb_docs_to_archive": docs_archived,
                "voice_channels_to_disable": max(
                    0,
                    old_limits.get("voice_slots", 0) - new_limits.get("voice_slots", 0),
                ),
            },
        }

    # ═══════════════════════════════════════════════════════════════════
    # P4: Usage Period Aligned to Billing Period
    # ═══════════════════════════════════════════════════════════════════

    def get_current_billing_period(
        self,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        P4: Get the current billing period window.

        Returns the 30-day (or 365-day for yearly) billing window,
        NOT calendar month.

        Args:
            company_id: Company UUID

        Returns:
            Dict with period_start, period_end, days_in_period, etc.
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if not subscription:
                return {
                    "company_id": str(company_id),
                    "period_start": None,
                    "period_end": None,
                    "days_in_period": BILLING_PERIOD_DAYS,
                    "billing_frequency": "monthly",
                }

            billing_frequency = (
                getattr(subscription, "billing_frequency", "monthly") or "monthly"
            )

            days_in_period = getattr(
                subscription, "days_in_period", None
            ) or self._calculate_period_days(billing_frequency)

            return {
                "company_id": str(company_id),
                "period_start": subscription.current_period_start,
                "period_end": subscription.current_period_end,
                "days_in_period": days_in_period,
                "billing_frequency": billing_frequency,
                "tier": subscription.tier,
            }

    # ═══════════════════════════════════════════════════════════════════
    # Y6: Renewal Handling
    # ═══════════════════════════════════════════════════════════════════

    def process_renewals(self) -> Dict[str, Any]:
        """
        Y6: Process subscription renewals.

        At period end for active subscriptions (not canceled, not
        pending downgrade), renew the billing period.

        For yearly: auto-renew via Paddle.
        Send renewal reminder 30 days before.

        Returns:
            Dict with renewal summary
        """
        now = datetime.now(timezone.utc)
        results = {
            "timestamp": now.isoformat(),
            "renewed": 0,
            "errors": [],
        }

        # Send renewal reminders (30 days before)
        reminder_threshold = now + timedelta(days=30)
        with SessionLocal() as db:
            upcoming_renewals = (
                db.query(Subscription)
                .filter(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.cancel_at_period_end is False,
                    Subscription.current_period_end > now,
                    Subscription.current_period_end <= reminder_threshold,
                )
                .all()
            )

            for sub in upcoming_renewals:
                try:
                    freq = getattr(sub, "billing_frequency", "monthly") or "monthly"
                    logger.info(
                        "renewal_reminder company_id=%s tier=%s freq=%s ends=%s",
                        sub.company_id,
                        sub.tier,
                        freq,
                        sub.current_period_end,
                    )
                    # TODO: Send email reminder via email service
                except Exception as e:
                    results["errors"].append(
                        {
                            "subscription_id": sub.id,
                            "type": "reminder",
                            "error": str(e)[:200],
                        }
                    )

        # Process expired subscriptions (renew)
        with SessionLocal() as db:
            expired = (
                db.query(Subscription)
                .filter(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.cancel_at_period_end is False,
                    Subscription.pending_downgrade_tier.is_(None),
                    Subscription.current_period_end <= now,
                )
                .all()
            )

            for sub in expired:
                try:
                    freq = getattr(sub, "billing_frequency", "monthly") or "monthly"
                    new_period_end = self._calculate_period_end(now, freq)
                    new_period_days = self._calculate_period_days_for_range(
                        now, new_period_end
                    )

                    sub.current_period_start = now
                    sub.current_period_end = new_period_end
                    sub.days_in_period = new_period_days

                    results["renewed"] += 1

                    logger.info(
                        "subscription_renewed company_id=%s tier=%s freq=%s new_end=%s",
                        sub.company_id,
                        sub.tier,
                        freq,
                        new_period_end,
                    )
                except Exception as e:
                    results["errors"].append(
                        {
                            "subscription_id": sub.id,
                            "type": "renewal",
                            "error": str(e)[:200],
                        }
                    )

            db.commit()

        logger.info(
            "renewals_processed renewed=%d errors=%d",
            results["renewed"],
            len(results["errors"]),
        )

        return results

    # ── Helper Methods ───────────────────────────────────────────────────

    def _is_upgrade(self, old_variant: str, new_variant: str) -> bool:
        """Check if new_variant is an upgrade from old_variant."""
        tier_order = {"mini_parwa": 1, "parwa": 2, "high_parwa": 3}
        return tier_order.get(new_variant, 0) > tier_order.get(old_variant, 0)

    def _calculate_proration(
        self,
        old_variant: str,
        new_variant: str,
        billing_cycle_start: Optional[datetime],
        billing_cycle_end: Optional[datetime],
        billing_frequency: str = "monthly",
    ) -> Dict[str, Any]:
        """
        Calculate proration for variant change.

        P3: daily_rate = price / 30 always (30-day divisor regardless of
        actual days in period for monthly).
        Y5: For yearly, daily_rate = yearly_price / days_in_period.

        Formula:
        - unused_amount = (old_price / divisor) * days_remaining
        - new_daily_rate = new_price / divisor
        - new_charge = new_daily_rate * days_remaining
        - net_charge = new_charge - unused_amount
        """
        now = datetime.now(timezone.utc)

        if billing_cycle_start is None:
            billing_cycle_start = now
        if billing_cycle_end is None:
            billing_cycle_end = self._calculate_period_end(
                billing_cycle_start, billing_frequency
            )

        if billing_cycle_start.tzinfo is None:
            billing_cycle_start = billing_cycle_start.replace(tzinfo=timezone.utc)
        if billing_cycle_end.tzinfo is None:
            billing_cycle_end = billing_cycle_end.replace(tzinfo=timezone.utc)

        old_price = self._get_variant_price(old_variant, billing_frequency)
        new_price = self._get_variant_price(new_variant, billing_frequency)

        # Calculate days
        total_period = billing_cycle_end - billing_cycle_start
        remaining = billing_cycle_end - now

        # P3: For monthly, ALWAYS use 30-day divisor
        if billing_frequency == "monthly":
            days_in_period = BILLING_PERIOD_DAYS
        else:
            # Y5: For yearly, detect leap year from cycle start
            # and use 366 if the cycle spans a Feb 29
            period_end_calc = self._calculate_period_end(billing_cycle_start, "yearly")
            days_in_period = (period_end_calc - billing_cycle_start).days
            if days_in_period < 1:
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
            "billing_frequency": billing_frequency,
        }

    def _get_paddle_price_id(
        self,
        variant: str,
        billing_frequency: str = "monthly",
    ) -> str:
        """
        Get Paddle price ID for variant + frequency.

        Y2: Yearly price IDs from PADDLE_YEARLY_PRICE_IDS env var.
        """
        from app.config import get_settings

        settings = get_settings()

        # Monthly price map
        monthly_map = {
            "mini_parwa": getattr(
                settings, "PADDLE_PRICE_MINI_PARWA", "pri_mini_parwa"
            ),
            "parwa": getattr(settings, "PADDLE_PRICE_PARWA", "pri_parwa"),
            "high_parwa": getattr(
                settings, "PADDLE_PRICE_HIGH_PARWA", "pri_high_parwa"
            ),
        }

        if billing_frequency == "yearly":
            # Y2: Load yearly price IDs from env
            yearly_ids_str = getattr(settings, "PADDLE_YEARLY_PRICE_IDS", "")
            if yearly_ids_str:
                try:
                    import json

                    yearly_ids = json.loads(yearly_ids_str)
                    yearly_map = {
                        "mini_parwa": yearly_ids.get(
                            "mini_parwa", "pri_mini_parwa_yearly"
                        ),
                        "parwa": yearly_ids.get("parwa", "pri_parwa_yearly"),
                        "high_parwa": yearly_ids.get(
                            "high_parwa", "pri_high_parwa_yearly"
                        ),
                    }
                    return yearly_map.get(
                        variant, monthly_map.get(variant, "pri_mini_parwa")
                    )
                except (json.JSONDecodeError, TypeError):
                    pass

            # Default yearly price IDs
            yearly_defaults = {
                "mini_parwa": "pri_mini_parwa_yearly",
                "parwa": "pri_parwa_yearly",
                "high_parwa": "pri_high_parwa_yearly",
            }
            return yearly_defaults.get(
                variant, monthly_map.get(variant, "pri_mini_parwa")
            )

        return monthly_map.get(variant, "pri_mini_parwa")

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

        billing_frequency = BillingFrequency(
            getattr(subscription, "billing_frequency", "monthly") or "monthly"
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
            billing_frequency=billing_frequency,
            pending_downgrade_tier=getattr(
                subscription, "pending_downgrade_tier", None
            ),
            previous_tier=getattr(subscription, "previous_tier", None),
            days_in_period=getattr(subscription, "days_in_period", None),
            limits=limits,
        )

    # ═══════════════════════════════════════════════════════════════════
    # R1-R3: Re-subscription
    # ═══════════════════════════════════════════════════════════════════

    async def resubscribe(
        self,
        company_id: UUID,
        variant: str,
        billing_frequency: str = "monthly",
        restore_data: bool = True,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        R1/R2/R3: Re-subscription after cancellation.

        Logic:
        1. Find canceled subscription for company
        2. Check if within 30-day retention (service_stopped_at + 30 > now)
        3. If within retention AND restore_data: restore agents, team, channels from archive
        4. If after retention: warn but allow fresh start
        5. Create new subscription with chosen variant/frequency via Paddle
        6. Return subscription info with retention_status

        Args:
            company_id: Company UUID
            variant: Subscription variant (starter/growth/high)
            billing_frequency: 'monthly' or 'yearly'
            restore_data: Whether to restore archived data (only within retention)
            payment_method_id: Optional Paddle payment method ID

        Returns:
            Dict with subscription info, data_restored flag, and retention_status

        Raises:
            SubscriptionAlreadyExistsError: If company has active subscription
            InvalidVariantError: If variant is invalid
            SubscriptionError: If no canceled subscription found
        """
        variant = self._validate_variant(variant)
        billing_frequency = self._validate_frequency(billing_frequency)

        with SessionLocal() as db:
            # Check for existing active subscription
            existing_active = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .first()
            )

            if existing_active:
                raise SubscriptionAlreadyExistsError(
                    f"Company {company_id} already has an active subscription"
                )

            # Find canceled subscription
            canceled_sub = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.CANCELED.value,
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if not canceled_sub:
                raise SubscriptionError(
                    f"No canceled subscription found for company {company_id}. "
                    "Please create a new subscription instead."
                )

            # Determine retention status
            now = datetime.now(timezone.utc)
            service_stopped_at = getattr(canceled_sub, "service_stopped_at", None)
            if not service_stopped_at:
                # Use the canceled_at or created_at as fallback
                service_stopped_at = canceled_sub.updated_at or canceled_sub.created_at

            if service_stopped_at and service_stopped_at.tzinfo is None:
                service_stopped_at = service_stopped_at.replace(tzinfo=timezone.utc)

            retention_deadline = (
                service_stopped_at + timedelta(days=30) if service_stopped_at else None
            )

            within_retention = (
                retention_deadline is not None and now < retention_deadline
            )
            retention_status = (
                "within_retention" if within_retention else "after_retention"
            )

            data_restored = False

            # Restore data if within retention and requested
            if within_retention and restore_data:
                try:
                    await self._restore_archived_data(db, str(company_id), variant)
                    data_restored = True
                    logger.info(
                        "resubscribe_data_restored company_id=%s variant=%s",
                        company_id,
                        variant,
                    )
                except Exception as e:
                    logger.error(
                        "resubscribe_data_restore_failed company_id=%s error=%s",
                        company_id,
                        str(e),
                    )

            # Get company for Paddle
            company = db.query(Company).filter(Company.id == str(company_id)).first()

            if not company:
                raise SubscriptionError(f"Company {company_id} not found")

            # Create new subscription in Paddle
            paddle_subscription_id = None
            if company.paddle_customer_id and payment_method_id:
                try:
                    paddle = await self._get_paddle()
                    price_id = self._get_paddle_price_id(variant, billing_frequency)
                    result = await paddle.create_subscription(
                        customer_id=company.paddle_customer_id,
                        price_id=price_id,
                    )
                    paddle_subscription_id = result.get("data", {}).get("id")
                    logger.info(
                        "resubscribe_paddle_created company_id=%s paddle_sub_id=%s",
                        company_id,
                        paddle_subscription_id,
                    )
                except PaddleError as e:
                    logger.error(
                        "resubscribe_paddle_failed company_id=%s error=%s",
                        company_id,
                        str(e),
                    )

            # Create new subscription record
            period_end = self._calculate_period_end(now, billing_frequency)
            period_days = self._calculate_period_days_for_range(now, period_end)

            new_subscription = Subscription(
                company_id=str(company_id),
                tier=variant,
                status=SubscriptionStatus.ACTIVE.value,
                current_period_start=now,
                current_period_end=period_end,
                paddle_subscription_id=paddle_subscription_id,
                billing_frequency=billing_frequency,
                days_in_period=period_days,
            )
            db.add(new_subscription)

            # Update company
            company.subscription_tier = variant
            company.subscription_status = SubscriptionStatus.ACTIVE.value
            if paddle_subscription_id:
                company.paddle_subscription_id = paddle_subscription_id

            db.commit()
            db.refresh(new_subscription)

            logger.info(
                "resubscribe_completed company_id=%s variant=%s freq=%s "
                "retention=%s data_restored=%s",
                company_id,
                variant,
                billing_frequency,
                retention_status,
                data_restored,
            )

            message = (
                f"Welcome back! Subscription reactivated with {variant} plan."
                if data_restored
                else (
                    f"Subscription created with {variant} plan. "
                    "Your previous data could not be restored."
                    if within_retention and not data_restored
                    else (
                        f"Subscription created with {variant} plan. "
                        "Your previous data has expired (past 30-day retention)."
                    )
                )
            )

            return {
                "subscription": self._to_subscription_info(new_subscription),
                "data_restored": data_restored,
                "message": message,
                "retention_status": retention_status,
            }

    async def _restore_archived_data(
        self,
        db: Session,
        company_id: str,
        new_variant: str,
    ) -> Dict[str, Any]:
        """
        R2/R3: Restore archived data for a re-subscribing company.

        Restores:
        - AI agents (set status back to active)
        - Team member access (set is_active=True, restore roles)
        - Channels (set is_enabled=True)

        Args:
            db: Database session
            company_id: Company ID string
            new_variant: New variant name (for limit enforcement)

        Returns:
            Dict with restoration summary
        """
        new_limits = VARIANT_LIMITS.get(VariantType(new_variant), {})
        restored = {
            "agents_restored": 0,
            "team_members_restored": 0,
            "channels_restored": 0,
        }

        # Restore AI agents
        try:
            from database.models.core import Agent

            agent_limit = new_limits.get("ai_agents", 1)
            paused_agents = (
                db.query(Agent)
                .filter(
                    Agent.company_id == company_id,
                    Agent.status.in_(["paused", "disabled", "archived"]),
                )
                .order_by(Agent.created_at.asc())
                .limit(agent_limit)
                .all()
            )

            for agent in paused_agents:
                agent.status = "active"
                restored["agents_restored"] += 1
        except Exception as e:
            logger.warning(
                "resubscribe_agent_restore_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        # Restore team members (except owner)
        try:
            from database.models.core import User

            member_limit = new_limits.get("team_members", 3)
            inactive_members = (
                db.query(User)
                .filter(
                    User.company_id == company_id,
                    User.is_active is False,
                    User.role != "owner",
                )
                .order_by(User.created_at.asc())
                .limit(member_limit)
                .all()
            )

            for member in inactive_members:
                member.is_active = True
                if member.role == "viewer":
                    member.role = "agent"
                restored["team_members_restored"] += 1
        except Exception as e:
            logger.warning(
                "resubscribe_team_restore_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        # Restore channels
        try:
            from database.models.core import Channel

            disabled_channels = (
                db.query(Channel)
                .filter(
                    Channel.company_id == company_id,
                    Channel.is_enabled is False,
                )
                .all()
            )

            for channel in disabled_channels:
                channel.is_enabled = True
                restored["channels_restored"] += 1
        except Exception as e:
            logger.warning(
                "resubscribe_channel_restore_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        db.flush()
        return restored

    # ═══════════════════════════════════════════════════════════════════
    # C1: Cancel Confirmation Flow — Save Cancel Feedback
    # ═══════════════════════════════════════════════════════════════════

    def save_cancel_feedback(
        self,
        company_id: UUID,
        reason: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        C1: Step 1 of cancel confirmation flow — save cancel reason/feedback.

        Args:
            company_id: Company UUID
            reason: Cancellation reason (short)
            feedback: Additional feedback text

        Returns:
            Dict with saved feedback info
        """
        with SessionLocal() as db:
            feedback_record = CancellationRequest(
                company_id=str(company_id),
                user_id=str(company_id),
                reason=reason or "",
                status="feedback_received",
            )

            # Store additional feedback in a metadata field if available
            if hasattr(feedback_record, "metadata_json"):
                feedback_record.metadata_json = {"feedback": feedback or ""}

            db.add(feedback_record)
            db.commit()
            db.refresh(feedback_record)

            logger.info(
                "cancel_feedback_saved company_id=%s reason=%s",
                company_id,
                reason or "not_provided",
            )

            return {
                "feedback_id": feedback_record.id,
                "status": "feedback_saved",
                "message": "Feedback saved. You can continue to cancel or accept a special offer.",
            }

    # ═══════════════════════════════════════════════════════════════════
    # C1: Cancel Confirmation Flow — Save Offer (20% off 3 months)
    # ═══════════════════════════════════════════════════════════════════

    def apply_save_offer(
        self,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        C1: Apply save offer — 20% discount for next 3 months.

        Finds the active subscription, calculates discounted price,
        and applies the discount.

        Args:
            company_id: Company UUID

        Returns:
            Dict with offer details including original/discounted price
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                )
                .first()
            )

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No active subscription for company {company_id}"
                )

            variant = subscription.tier
            billing_frequency = (
                getattr(subscription, "billing_frequency", "monthly") or "monthly"
            )

            original_price = self._get_variant_price(variant, billing_frequency)
            discounted_price = original_price * Decimal("0.80")  # 20% off
            discounted_price = discounted_price.quantize(Decimal("0.01"))

            # Apply discount flag on subscription (or company)
            if hasattr(subscription, "metadata_json"):
                metadata = subscription.metadata_json or {}
                metadata["save_offer_applied"] = True
                metadata["save_offer_discount_pct"] = 20
                metadata["save_offer_months_remaining"] = 3
                subscription.metadata_json = metadata
                db.commit()

            logger.info(
                "save_offer_applied company_id=%s variant=%s freq=%s "
                "original=%s discounted=%s",
                company_id,
                variant,
                billing_frequency,
                original_price,
                discounted_price,
            )

            return {
                "discount_percentage": 20,
                "discount_months": 3,
                "original_price": original_price,
                "discounted_price": discounted_price,
                "message": (
                    "Stay with us! Get 20% off your next 3 months. "
                    "Your discount will be applied to your next 3 invoices."
                ),
            }

    # ═══════════════════════════════════════════════════════════════════
    # C3: Period-End Service Stop on Cancel
    # ═══════════════════════════════════════════════════════════════════

    def _apply_service_stop_on_cancel(
        self,
        db: Session,
        company_id: str,
    ) -> Dict[str, Any]:
        """
        C3: Stop all services when subscription is canceled at period end.

        Called from _apply_scheduled_cancellation():
        - Pause all AI agents
        - Disable team member access (except admin/owner) — set is_active=False
        - Mark all channels as disabled
        - Log the action

        Args:
            db: Database session
            company_id: Company ID string

        Returns:
            Dict with service stop summary
        """
        now = datetime.now(timezone.utc)
        stopped = {
            "agents_paused": 0,
            "team_members_disabled": 0,
            "channels_disabled": 0,
        }

        # Pause all AI agents
        try:
            from database.models.core import Agent

            active_agents = (
                db.query(Agent)
                .filter(
                    Agent.company_id == company_id,
                    Agent.status == "active",
                )
                .all()
            )

            for agent in active_agents:
                agent.status = "paused"
                stopped["agents_paused"] += 1
        except Exception as e:
            logger.warning(
                "service_stop_agents_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        # Disable team member access (except admin/owner)
        try:
            from database.models.core import User

            active_members = (
                db.query(User)
                .filter(
                    User.company_id == company_id,
                    User.is_active,
                    User.role.notin_(["owner", "admin"]),
                )
                .all()
            )

            for member in active_members:
                member.is_active = False
                stopped["team_members_disabled"] += 1
        except Exception as e:
            logger.warning(
                "service_stop_team_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        # Disable all channels
        try:
            from database.models.core import Channel

            active_channels = (
                db.query(Channel)
                .filter(
                    Channel.company_id == company_id,
                    Channel.is_enabled,
                )
                .all()
            )

            for channel in active_channels:
                channel.is_enabled = False
                stopped["channels_disabled"] += 1
        except Exception as e:
            logger.warning(
                "service_stop_channels_failed company_id=%s error=%s",
                company_id,
                str(e),
            )

        logger.info(
            "service_stop_completed company_id=%s " "agents=%d team=%d channels=%d",
            company_id,
            stopped["agents_paused"],
            stopped["team_members_disabled"],
            stopped["channels_disabled"],
        )

        return stopped

    # ═══════════════════════════════════════════════════════════════════
    # G2: Auto-Cancel After Payment Failure Timeout (7 days)
    # ═══════════════════════════════════════════════════════════════════

    def process_payment_failure_timeouts(self) -> Dict[str, Any]:
        """
        G2: Auto-cancel subscriptions after 7 days of payment failure.

        Query subscriptions where status=payment_failed AND
        payment_failed_at + 7 days <= now. For each: cancel and
        enter 30-day data retention.

        Returns:
            Dict with processing summary
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        results = {
            "timestamp": now.isoformat(),
            "cutoff": cutoff.isoformat(),
            "subscriptions_canceled": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            failed_subs = (
                db.query(Subscription)
                .filter(
                    Subscription.status == SubscriptionStatus.PAYMENT_FAILED.value,
                )
                .all()
            )

            for sub in failed_subs:
                try:
                    payment_failed_at = getattr(sub, "payment_failed_at", None)
                    if not payment_failed_at:
                        continue

                    if payment_failed_at.tzinfo is None:
                        payment_failed_at = payment_failed_at.replace(
                            tzinfo=timezone.utc
                        )

                    # Check if 7-day window has elapsed
                    if payment_failed_at <= cutoff:
                        # Cancel subscription
                        sub.status = SubscriptionStatus.CANCELED.value
                        sub.service_stopped_at = now  # type: ignore

                        # Update company
                        company = (
                            db.query(Company)
                            .filter(Company.id == sub.company_id)
                            .first()
                        )
                        if company:
                            company.subscription_status = (
                                SubscriptionStatus.CANCELED.value
                            )

                        # C3: Apply service stop
                        self._apply_service_stop_on_cancel(db, sub.company_id)

                        results["subscriptions_canceled"] += 1

                        logger.info(
                            "payment_failure_timeout_canceled "
                            "company_id=%s sub_id=%s failed_at=%s",
                            sub.company_id,
                            sub.id,
                            payment_failed_at.isoformat(),
                        )
                except Exception as e:
                    logger.error(
                        "payment_failure_timeout_failed " "sub_id=%s error=%s",
                        sub.id,
                        str(e),
                    )
                    results["errors"].append(
                        {
                            "subscription_id": sub.id,
                            "company_id": sub.company_id,
                            "error": str(e)[:200],
                        }
                    )

            db.commit()

        logger.info(
            "payment_failure_timeouts_processed canceled=%d errors=%d",
            results["subscriptions_canceled"],
            len(results["errors"]),
        )

        return results

    # ═══════════════════════════════════════════════════════════════════
    # G3: Auto-Retry Failed Payments
    # ═══════════════════════════════════════════════════════════════════

    async def retry_failed_payment(
        self,
        company_id: UUID,
    ) -> Dict[str, Any]:
        """
        G3: Retry a failed payment via Paddle.

        Gets the company's subscription with payment_failed status,
        calls Paddle to retry the charge, and updates status on success.

        Args:
            company_id: Company UUID

        Returns:
            Dict with retry result

        Raises:
            SubscriptionNotFoundError: No failed subscription found
            SubscriptionError: If retry fails
        """
        with SessionLocal() as db:
            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.PAYMENT_FAILED.value,
                )
                .with_for_update()
                .first()
            )

            if not subscription:
                raise SubscriptionNotFoundError(
                    f"No payment_failed subscription for company {company_id}"
                )

            # Attempt Paddle retry
            paddle_sub_id = subscription.paddle_subscription_id
            if paddle_sub_id:
                try:
                    paddle = await self._get_paddle()
                    # Paddle doesn't have a direct "retry" endpoint,
                    # but we can re-activate the subscription to trigger
                    # a new payment attempt
                    await paddle.resume_subscription(paddle_sub_id)

                    # Update status
                    subscription.status = SubscriptionStatus.ACTIVE.value
                    subscription.payment_failed_at = None  # type: ignore

                    company = (
                        db.query(Company).filter(Company.id == str(company_id)).first()
                    )
                    if company:
                        company.subscription_status = SubscriptionStatus.ACTIVE.value

                    db.commit()
                    db.refresh(subscription)

                    logger.info(
                        "payment_retry_succeeded company_id=%s sub_id=%s",
                        company_id,
                        subscription.id,
                    )

                    return {
                        "success": True,
                        "subscription": self._to_subscription_info(subscription),
                        "message": "Payment retry successful. Subscription reactivated.",
                    }
                except PaddleError as e:
                    logger.error(
                        "payment_retry_paddle_failed company_id=%s error=%s",
                        company_id,
                        str(e),
                    )
                    raise SubscriptionError(f"Payment retry failed: {str(e)}")
            else:
                # No Paddle subscription — manual retry, just reset status
                subscription.status = SubscriptionStatus.ACTIVE.value
                subscription.payment_failed_at = None  # type: ignore
                db.commit()
                db.refresh(subscription)

                logger.info(
                    "payment_retry_manual_reset company_id=%s sub_id=%s",
                    company_id,
                    subscription.id,
                )

                return {
                    "success": True,
                    "subscription": self._to_subscription_info(subscription),
                    "message": "Payment status reset to active.",
                }

    def process_auto_retry_payments(self) -> Dict[str, Any]:
        """
        G3: Auto-retry failed payments on Day 1, 3, 5, 7 after failure.

        Checks payment_failed subscriptions and retries if today is
        an eligible retry day (1, 3, 5, or 7 days after failure).

        Returns:
            Dict with processing summary
        """
        now = datetime.now(timezone.utc)
        results = {
            "timestamp": now.isoformat(),
            "retries_attempted": 0,
            "retries_succeeded": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            failed_subs = (
                db.query(Subscription)
                .filter(
                    Subscription.status == SubscriptionStatus.PAYMENT_FAILED.value,
                )
                .all()
            )

            for sub in failed_subs:
                try:
                    payment_failed_at = getattr(sub, "payment_failed_at", None)
                    if not payment_failed_at:
                        continue

                    if payment_failed_at.tzinfo is None:
                        payment_failed_at = payment_failed_at.replace(
                            tzinfo=timezone.utc
                        )

                    days_since_failure = (now - payment_failed_at).days

                    # Only retry on Day 1, 3, 5, 7
                    if days_since_failure not in {1, 3, 5, 7}:
                        continue

                    results["retries_attempted"] += 1

                    # Use asyncio to call the async retry method
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        retry_result = loop.run_until_complete(
                            self.retry_failed_payment(UUID(sub.company_id))
                        )
                        if retry_result.get("success"):
                            results["retries_succeeded"] += 1
                    finally:
                        loop.close()

                except Exception as e:
                    logger.error(
                        "auto_retry_failed company_id=%s error=%s",
                        sub.company_id,
                        str(e),
                    )
                    results["errors"].append(
                        {
                            "subscription_id": sub.id,
                            "company_id": sub.company_id,
                            "error": str(e)[:200],
                        }
                    )

        logger.info(
            "auto_retry_payments_processed attempted=%d succeeded=%d errors=%d",
            results["retries_attempted"],
            results["retries_succeeded"],
            len(results["errors"]),
        )

        return results

    # ═══════════════════════════════════════════════════════════════════
    # G4: Payment Method Update
    # ═══════════════════════════════════════════════════════════════════

    async def generate_payment_method_update_url(
        self,
        company_id: UUID,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        G4: Generate Paddle portal URL for payment method update.

        Generates a Paddle Billing Portal URL where the customer can
        update their payment method. After update, auto-retry any
        failed payment.

        Args:
            company_id: Company UUID
            return_url: Optional URL to redirect to after update

        Returns:
            Dict with portal URL and message
        """
        with SessionLocal() as db:
            company = db.query(Company).filter(Company.id == str(company_id)).first()

            if not company:
                raise SubscriptionError(f"Company {company_id} not found")

            subscription = (
                db.query(Subscription)
                .filter(
                    Subscription.company_id == str(company_id),
                )
                .order_by(Subscription.created_at.desc())
                .first()
            )

            if not subscription or not subscription.paddle_subscription_id:
                return {
                    "paddle_portal_url": None,
                    "message": "No Paddle subscription found. "
                    "Contact support to update your payment method.",
                }

            try:
                paddle = await self._get_paddle()
                # Generate Paddle portal URL
                portal_url = await paddle.generate_portal_url(
                    subscription.paddle_subscription_id,
                    return_url=return_url,
                )

                logger.info(
                    "payment_method_portal_generated company_id=%s",
                    company_id,
                )

                return {
                    "paddle_portal_url": portal_url,
                    "message": "Payment method update portal URL generated. "
                    "Complete the update in the Paddle portal.",
                }
            except PaddleError as e:
                logger.error(
                    "payment_method_portal_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                # Return a fallback message
                return {
                    "paddle_portal_url": None,
                    "message": (
                        "Unable to generate payment portal URL. "
                        "Please contact support to update your payment method."
                    ),
                }


# ── Singleton Service ────────────────────────────────────────────────────

_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get the subscription service singleton."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
