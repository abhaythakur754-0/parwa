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

S-08 fix: All `with SessionLocal() as db:` blocks are wrapped in
sync `_db_work()` functions and executed via `asyncio.to_thread()` so
that synchronous SQLAlchemy I/O never blocks the asyncio event loop.
Async Paddle API calls remain on the event loop between the DB-read
and DB-write phases.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.clients.paddle_client import (
    PaddleClient,
    PaddleError,
    get_paddle_client,
)
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
from database.models.billing import Subscription, CancellationRequest, Invoice
from database.models.billing_extended import PaymentMethod, ProrationAudit
from database.models.core import Company

logger = logging.getLogger("parwa.services.subscription")


class SubscriptionError(Exception):
    """Base exception for subscription errors."""
    def __init__(self, message: str = "Subscription operation failed", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class SubscriptionNotFoundError(SubscriptionError):
    """Subscription not found."""
    def __init__(self, message: str = "Subscription not found", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class SubscriptionAlreadyExistsError(SubscriptionError):
    """Company already has an active subscription."""
    def __init__(self, message: str = "Company already has an active subscription", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class InvalidVariantError(SubscriptionError):
    """Invalid variant specified."""
    def __init__(self, message: str = "Invalid variant specified", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class InvalidStatusTransitionError(SubscriptionError):
    """Invalid subscription status transition."""
    def __init__(self, message: str = "Invalid subscription status transition", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


class PaddleOperationError(SubscriptionError):
    """Paddle operation failed — caller must handle this."""
    def __init__(self, message: str = "Paddle operation failed", **kwargs):
        self.message = message
        self.kwargs = kwargs
        super().__init__(self.message)


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
        SubscriptionStatus.PENDING,
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
        """Get monthly price for a variant — delegates to pricing_config."""
        return _get_price_from_config(variant, billing_cycle="monthly")

    # ── Bug 3 fix: Ensure Paddle customer exists before any Paddle call ──

    async def _ensure_paddle_customer(
        self, company: Company, db: Session
    ) -> str:
        """
        Ensure the company has a Paddle customer ID.
        Create one in Paddle if missing, and persist it on the company.

        Returns:
            The paddle_customer_id string.
        """
        if company.paddle_customer_id:
            return company.paddle_customer_id

        paddle = await self._get_paddle()

        # Determine email/name for the Paddle customer record.
        # Fall back to company name + placeholder email if needed.
        customer_email = getattr(company, "billing_email", None) or getattr(company, "email", None)
        if not customer_email:
            # Use a deterministic placeholder so we don't block signup
            customer_email = f"billing+{company.id}@parwa.placeholder"

        customer_name = company.name or f"Company {company.id[:8]}"

        try:
            result = await paddle.create_customer(
                email=customer_email,
                name=customer_name,
                custom_data={"company_id": company.id},
            )
            paddle_customer_id = result.get("data", {}).get("id")
            if not paddle_customer_id:
                raise PaddleOperationError(
                    "Paddle create_customer returned no customer ID"
                )
            company.paddle_customer_id = paddle_customer_id
            db.commit()
            logger.info(
                "paddle_customer_created company_id=%s paddle_customer_id=%s",
                company.id,
                paddle_customer_id,
            )
            return paddle_customer_id
        except PaddleError as e:
            raise PaddleOperationError(
                f"Failed to create Paddle customer for company {company.id}: {e}"
            ) from e

    # ── S-08: Helper to create a Paddle customer when no DB session is open ──

    async def _ensure_paddle_customer_async(self, company_id: UUID, company_paddle_customer_id: Optional[str]) -> str:
        """
        Ensure the company has a Paddle customer ID (async-only version).

        Used when the DB session is not held open across the Paddle call.
        Reads the paddle_customer_id; if missing, creates one via Paddle
        and persists it in a separate DB session.

        Returns:
            The paddle_customer_id string.
        """
        if company_paddle_customer_id:
            return company_paddle_customer_id

        # Read company details needed for Paddle
        def _db_read_company():
            with SessionLocal() as db:
                company = db.query(Company).filter(
                    Company.id == str(company_id)
                ).first()
                if not company:
                    return None, None
                return (
                    getattr(company, "billing_email", None) or getattr(company, "email", None),
                    company.name,
                )

        customer_email, customer_name = await asyncio.to_thread(_db_read_company)

        if not customer_email:
            customer_email = f"billing+{str(company_id)}@parwa.placeholder"
        if not customer_name:
            customer_name = f"Company {str(company_id)[:8]}"

        paddle = await self._get_paddle()

        try:
            result = await paddle.create_customer(
                email=customer_email,
                name=customer_name,
                custom_data={"company_id": str(company_id)},
            )
            paddle_customer_id = result.get("data", {}).get("id")
            if not paddle_customer_id:
                raise PaddleOperationError(
                    "Paddle create_customer returned no customer ID"
                )

            # Persist the new paddle_customer_id
            def _db_save_paddle_customer():
                with SessionLocal() as db:
                    company = db.query(Company).filter(
                        Company.id == str(company_id)
                    ).first()
                    if company:
                        company.paddle_customer_id = paddle_customer_id
                        db.commit()

            await asyncio.to_thread(_db_save_paddle_customer)

            logger.info(
                "paddle_customer_created company_id=%s paddle_customer_id=%s",
                company_id,
                paddle_customer_id,
            )
            return paddle_customer_id
        except PaddleError as e:
            raise PaddleOperationError(
                f"Failed to create Paddle customer for company {company_id}: {e}"
            ) from e

    async def create_subscription(
        self,
        company_id: UUID,
        variant: str,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new subscription for a company.

        Correct Paddle Billing flow:
        ─ New customers (no payment method):
          1. Ensure Paddle customer exists
          2. Create a Paddle checkout transaction
          3. Return checkout URL + create local subscription as PENDING
          4. Frontend redirects to Paddle checkout
          5. Paddle webhook confirms payment → webhook handler activates subscription

        ─ Existing customers (with saved payment method):
          1. Ensure Paddle customer exists
          2. Create subscription directly in Paddle
          3. If Paddle succeeds, create local subscription as ACTIVE
          4. If Paddle fails, do NOT create the subscription (Bug 1 fix)

        Args:
            company_id: Company UUID
            variant: Subscription variant (starter/growth/high)
            payment_method_id: Paddle payment method ID (optional for new customers)

        Returns:
            Dict with subscription info and optional checkout_url

        Raises:
            SubscriptionAlreadyExistsError: If company has active subscription
            InvalidVariantError: If variant is invalid
            PaddleOperationError: If a Paddle call fails
        """
        variant = self._validate_variant(variant)

        # ── S-08: DB read phase (offloaded to thread) ──
        def _db_read():
            with SessionLocal() as db:
                # Check for existing subscription with row lock (GAP 1 fix)
                existing = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.PENDING.value,
                    ]),
                ).with_for_update().first()

                if existing:
                    raise SubscriptionAlreadyExistsError(
                        f"Company {company_id} already has an active or pending subscription"
                    )

                # Get company for paddle_customer_id
                company = db.query(Company).filter(
                    Company.id == str(company_id)
                ).first()

                if not company:
                    raise SubscriptionError(f"Company {company_id} not found")

                return company.paddle_customer_id

        company_paddle_customer_id = await asyncio.to_thread(_db_read)

        # ── Bug 3 fix: Always ensure a Paddle customer exists ──
        paddle_customer_id = await self._ensure_paddle_customer_async(
            company_id, company_paddle_customer_id
        )

        # Calculate billing period
        now = datetime.now(timezone.utc)
        period_end = self._calculate_period_end(now)
        price_id = self._get_paddle_price_id(variant)

        # ── Branch: existing customer with payment method vs new checkout ──
        if payment_method_id:
            # ── Existing customer: create subscription directly in Paddle ──
            try:
                paddle = await self._get_paddle()
                result = await paddle.create_subscription(
                    customer_id=paddle_customer_id,
                    price_id=price_id,
                )
                paddle_subscription_id = result.get("data", {}).get("id")
                if not paddle_subscription_id:
                    raise PaddleOperationError(
                        "Paddle create_subscription returned no subscription ID"
                    )
                logger.info(
                    "subscription_created_paddle "
                    "company_id=%s variant=%s paddle_sub_id=%s",
                    company_id,
                    variant,
                    paddle_subscription_id,
                )
            except PaddleError as e:
                # ── Bug 1 fix: If Paddle fails, do NOT create the subscription ──
                logger.error(
                    "subscription_paddle_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                raise PaddleOperationError(
                    f"Failed to create subscription in Paddle: {e}"
                ) from e

            # ── S-08: DB write phase (offloaded to thread) ──
            def _db_write_active():
                with SessionLocal() as db:
                    # Paddle succeeded — create ACTIVE subscription locally
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
                    company = db.query(Company).filter(
                        Company.id == str(company_id)
                    ).first()
                    if company:
                        company.subscription_tier = variant
                        company.subscription_status = SubscriptionStatus.ACTIVE.value
                        company.paddle_subscription_id = paddle_subscription_id

                    db.commit()
                    db.refresh(subscription)

                    logger.info(
                        "subscription_created company_id=%s variant=%s sub_id=%s",
                        company_id,
                        variant,
                        subscription.id,
                    )

                    return {
                        "subscription": self._to_subscription_info(subscription),
                        "checkout_url": None,
                    }

            return await asyncio.to_thread(_db_write_active)

        else:
            # ── New customer: create Paddle checkout transaction ──
            # Bug 2 fix: Return checkout URL; subscription stays PENDING
            try:
                paddle = await self._get_paddle()
                txn_result = await paddle.create_checkout_transaction(
                    customer_id=paddle_customer_id,
                    price_id=price_id,
                    custom_data={
                        "company_id": str(company_id),
                        "variant": variant,
                    },
                )
            except PaddleError as e:
                logger.error(
                    "checkout_paddle_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                raise PaddleOperationError(
                    f"Failed to create Paddle checkout transaction: {e}"
                ) from e

            checkout_url = txn_result.get("data", {}).get("checkout", {}).get("url")
            paddle_transaction_id = txn_result.get("data", {}).get("id")

            # ── S-08: DB write phase (offloaded to thread) ──
            def _db_write_pending():
                with SessionLocal() as db:
                    # Create subscription as PENDING — webhook will activate it
                    subscription = Subscription(
                        company_id=str(company_id),
                        tier=variant,
                        status=SubscriptionStatus.PENDING.value,
                        current_period_start=now,
                        current_period_end=period_end,
                        paddle_subscription_id=None,
                    )
                    # Store the transaction id in metadata so webhook can correlate
                    import json as _json
                    subscription.metadata_json = _json.dumps({
                        "paddle_transaction_id": paddle_transaction_id,
                        "checkout_url": checkout_url,
                        "requested_variant": variant,
                    })

                    db.add(subscription)

                    # Update company status to pending
                    company = db.query(Company).filter(
                        Company.id == str(company_id)
                    ).first()
                    if company:
                        company.subscription_status = SubscriptionStatus.PENDING.value

                    db.commit()
                    db.refresh(subscription)

                    logger.info(
                        "subscription_pending_checkout company_id=%s variant=%s sub_id=%s txn_id=%s",
                        company_id,
                        variant,
                        subscription.id,
                        paddle_transaction_id,
                    )

                    return {
                        "subscription": self._to_subscription_info(subscription),
                        "checkout_url": checkout_url,
                    }

            return await asyncio.to_thread(_db_write_pending)

    async def get_subscription(self, company_id: UUID) -> Optional[SubscriptionInfo]:
        """
        Get subscription details for a company.

        Args:
            company_id: Company UUID

        Returns:
            SubscriptionInfo or None if no subscription
        """
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
        4. Call Paddle FIRST (Bug 4 fix)
        5. THEN update local DB

        Args:
            company_id: Company UUID
            new_variant: Target variant (must be higher tier)

        Returns:
            Dict with subscription info and proration details

        Raises:
            SubscriptionNotFoundError: No active subscription
            InvalidVariantError: Invalid or non-upgrade variant
            PaddleOperationError: If Paddle update fails
        """
        new_variant = self._validate_variant(new_variant)

        # ── S-08: DB read phase (offloaded to thread) ──
        def _db_read():
            with SessionLocal() as db:
                # GAP 1 fix: Use row-level lock to prevent race conditions
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                ).with_for_update().first()

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
                        "noop": True,
                        "subscription_info": self._to_subscription_info(subscription),
                    }

                # Calculate proration
                proration = self._calculate_proration(
                    old_variant=old_variant,
                    new_variant=new_variant,
                    billing_cycle_start=subscription.current_period_start,
                    billing_cycle_end=subscription.current_period_end,
                )

                return {
                    "noop": False,
                    "old_variant": old_variant,
                    "proration": proration,
                    "paddle_subscription_id": subscription.paddle_subscription_id,
                    "subscription_id": subscription.id,
                }

        read_result = await asyncio.to_thread(_db_read)

        # Handle no-op case
        if read_result.get("noop"):
            return {
                "subscription": read_result["subscription_info"],
                "proration": None,
                "message": "Already on this variant",
            }

        old_variant = read_result["old_variant"]
        proration = read_result["proration"]

        # ── Bug 4 fix: Call Paddle FIRST, then update local DB ──
        # If Paddle fails, we raise before committing any local changes.
        if read_result["paddle_subscription_id"]:
            try:
                paddle = await self._get_paddle()
                price_id = self._get_paddle_price_id(new_variant)
                await paddle.update_subscription(
                    read_result["paddle_subscription_id"],
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
                logger.error(
                    "subscription_paddle_upgrade_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                raise PaddleOperationError(
                    f"Failed to upgrade subscription in Paddle: {e}"
                ) from e

        # ── S-08: DB write phase (offloaded to thread) ──
        def _db_write():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.id == read_result["subscription_id"],
                ).with_for_update().first()

                # Paddle succeeded (or no Paddle subscription) — now update local DB
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

        return await asyncio.to_thread(_db_write)

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

        Bug 6 fix: Use scheduled_change_type / scheduled_change_variant
        instead of reusing cancel_at_period_end for downgrades.

        Args:
            company_id: Company UUID
            new_variant: Target variant (must be lower tier)

        Returns:
            Dict with subscription info and scheduled change

        Raises:
            SubscriptionNotFoundError: No active subscription
            InvalidVariantError: Invalid or non-downgrade variant
            PaddleOperationError: If Paddle update fails
        """
        new_variant = self._validate_variant(new_variant)

        # ── S-08: DB read phase (offloaded to thread) ──
        def _db_read():
            with SessionLocal() as db:
                # GAP 1 fix: Use row-level lock to prevent race conditions
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                ).with_for_update().first()

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
                        "noop": True,
                        "subscription_info": self._to_subscription_info(subscription),
                    }

                return {
                    "noop": False,
                    "old_variant": old_variant,
                    "paddle_subscription_id": subscription.paddle_subscription_id,
                    "subscription_id": subscription.id,
                    "current_period_end": subscription.current_period_end,
                }

        read_result = await asyncio.to_thread(_db_read)

        # Handle no-op case
        if read_result.get("noop"):
            return {
                "subscription": read_result["subscription_info"],
                "message": "Already on this variant",
            }

        old_variant = read_result["old_variant"]

        # Schedule the price change in Paddle (effective next period)
        if read_result["paddle_subscription_id"]:
            try:
                paddle = await self._get_paddle()
                price_id = self._get_paddle_price_id(new_variant)
                await paddle.update_subscription(
                    read_result["paddle_subscription_id"],
                    items=[{"price_id": price_id}],
                    effective_at=read_result["current_period_end"].isoformat()
                    if read_result["current_period_end"] else None,
                )
                logger.info(
                    "subscription_downgrade_scheduled_paddle "
                    "company_id=%s old=%s new=%s",
                    company_id,
                    old_variant,
                    new_variant,
                )
            except PaddleError as e:
                logger.error(
                    "subscription_paddle_downgrade_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                raise PaddleOperationError(
                    f"Failed to schedule downgrade in Paddle: {e}"
                ) from e

        # ── S-08: DB write phase (offloaded to thread) ──
        def _db_write():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.id == read_result["subscription_id"],
                ).with_for_update().first()

                # ── Bug 6 fix: Use scheduled_change approach, NOT cancel_at_period_end ──
                # Store the pending downgrade distinctly from a cancellation.
                subscription.scheduled_change_type = "downgrade"
                subscription.scheduled_change_variant = new_variant
                # Do NOT set cancel_at_period_end for downgrades — that flag
                # is exclusively for cancellations now.

                # Also store in metadata_json for backward compatibility and
                # for consumers that read the JSON blob directly.
                import json as _json
                meta = {}
                if subscription.metadata_json:
                    try:
                        meta = _json.loads(subscription.metadata_json)
                    except (TypeError, ValueError):
                        pass
                meta["scheduled_change_type"] = "downgrade"
                meta["scheduled_change_variant"] = new_variant
                subscription.metadata_json = _json.dumps(meta)

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
                        "change_type": "downgrade",
                        "current_variant": old_variant,
                        "new_variant": new_variant,
                        "effective_date": subscription.current_period_end,
                    },
                    "message": (
                        f"Downgrade to {new_variant} scheduled for "
                        f"{subscription.current_period_end.isoformat() if subscription.current_period_end else 'next billing cycle'}"
                    ),
                }

        return await asyncio.to_thread(_db_write)

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

        Bug 5 fix: If Paddle cancel fails, raise an error instead of
        silently continuing.

        Bug 7 fix: user_id is nullable — don't fall back to company_id.

        Args:
            company_id: Company UUID
            reason: Optional cancellation reason
            effective_immediately: If True, cancel now; otherwise at period end
            user_id: User who initiated cancellation (nullable)

        Returns:
            Dict with cancellation details

        Raises:
            SubscriptionNotFoundError: No active subscription
            PaddleOperationError: If Paddle cancellation fails
        """
        # ── S-08: DB read phase (offloaded to thread) ──
        def _db_read():
            with SessionLocal() as db:
                # GAP 1 fix: Use row-level lock to prevent race conditions
                subscription = db.query(Subscription).filter(
                    Subscription.company_id == str(company_id),
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                ).with_for_update().first()

                if not subscription:
                    raise SubscriptionNotFoundError(
                        f"No active subscription for company {company_id}"
                    )

                return {
                    "subscription_id": subscription.id,
                    "paddle_subscription_id": subscription.paddle_subscription_id,
                }

        read_result = await asyncio.to_thread(_db_read)

        canceled_at = datetime.now(timezone.utc)

        # Cancel in Paddle
        if read_result["paddle_subscription_id"]:
            try:
                paddle = await self._get_paddle()
                await paddle.cancel_subscription(
                    read_result["paddle_subscription_id"],
                    effective_from="immediately" if effective_immediately else "next_billing_period",
                    reason=reason,
                )
            except PaddleError as e:
                # ── Bug 5 fix: Raise instead of silently swallowing ──
                logger.error(
                    "subscription_paddle_cancel_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                raise PaddleOperationError(
                    f"Failed to {'cancel' if effective_immediately else 'schedule cancellation of'} subscription in Paddle: {e}"
                ) from e

        # ── S-08: DB write phase (offloaded to thread) ──
        def _db_write():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.id == read_result["subscription_id"],
                ).with_for_update().first()

                if effective_immediately:
                    # Immediate cancellation
                    subscription.status = SubscriptionStatus.CANCELED.value
                    subscription.cancel_at_period_end = False
                    # Clear any scheduled change (downgrade) since we're canceling
                    subscription.scheduled_change_type = None
                    subscription.scheduled_change_variant = None

                    # Update company status
                    company = db.query(Company).filter(
                        Company.id == str(company_id)
                    ).first()
                    if company:
                        company.subscription_status = SubscriptionStatus.CANCELED.value
                else:
                    # Cancel at period end (Netflix style)
                    subscription.cancel_at_period_end = True
                    subscription.scheduled_change_type = "cancel"
                    subscription.scheduled_change_variant = None
                    # Status remains active until period end

                # ── Bug 7 fix: user_id is nullable — no company_id fallback ──
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

        return await asyncio.to_thread(_db_write)

    async def reactivate_subscription(
        self,
        company_id: UUID,
    ) -> SubscriptionInfo:
        """
        Reactivate a canceled subscription (before period end).

        Only works for subscriptions that are canceled but still active
        (cancel_at_period_end = True or scheduled_change_type = "cancel").

        Bug 5 fix: If Paddle resume fails, raise an error instead of
        silently continuing.

        Args:
            company_id: Company UUID

        Returns:
            Updated SubscriptionInfo

        Raises:
            SubscriptionNotFoundError: No subscription to reactivate
            InvalidStatusTransitionError: Cannot reactivate this subscription
            PaddleOperationError: If Paddle resume fails
        """
        # ── S-08: DB read phase (offloaded to thread) ──
        def _db_read():
            with SessionLocal() as db:
                # GAP 1 fix: Use row-level lock to prevent race conditions
                # Match subscriptions that are pending cancellation — either via
                # cancel_at_period_end flag OR scheduled_change_type == "cancel"
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

                return {
                    "subscription_id": subscription.id,
                    "paddle_subscription_id": subscription.paddle_subscription_id,
                }

        read_result = await asyncio.to_thread(_db_read)

        # Resume in Paddle
        if read_result["paddle_subscription_id"]:
            try:
                paddle = await self._get_paddle()
                await paddle.resume_subscription(
                    read_result["paddle_subscription_id"]
                )
            except PaddleError as e:
                # ── Bug 5 fix: Raise instead of silently swallowing ──
                logger.error(
                    "subscription_paddle_resume_failed company_id=%s error=%s",
                    company_id,
                    str(e),
                )
                raise PaddleOperationError(
                    f"Failed to reactivate subscription in Paddle: {e}"
                ) from e

        # ── S-08: DB write phase (offloaded to thread) ──
        def _db_write():
            with SessionLocal() as db:
                subscription = db.query(Subscription).filter(
                    Subscription.id == read_result["subscription_id"],
                ).with_for_update().first()

                # Clear cancellation / scheduled-change flags
                subscription.cancel_at_period_end = False
                subscription.scheduled_change_type = None
                subscription.scheduled_change_variant = None

                db.commit()
                db.refresh(subscription)

                logger.info("subscription_reactivated company_id=%s", company_id)

                return self._to_subscription_info(subscription)

        return await asyncio.to_thread(_db_write)

    # ── Helper Methods ───────────────────────────────────────────────────

    def _is_upgrade(self, old_variant: str, new_variant: str) -> bool:
        """Check if new_variant is an upgrade from old_variant."""
        try:
            old_vt = VariantType(normalize_variant_name(old_variant))
            new_vt = VariantType(normalize_variant_name(new_variant))
            return VARIANT_TIER_ORDER[new_vt] > VARIANT_TIER_ORDER[old_vt]
        except ValueError:
            return False

    def _calculate_period_end(self, start: datetime) -> datetime:
        """Calculate the end of a billing period (1 month from start)."""
        import calendar

        month = start.month + 1
        year = start.year
        if month > 12:
            month = 1
            year += 1
        # Get last day of target month to handle 31st-day edge cases
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
        from app.config import get_settings
        settings = get_settings()

        price_map = {
            "starter": getattr(settings, "PADDLE_PRICE_STARTER", "pri_starter"),
            "growth": getattr(settings, "PADDLE_PRICE_GROWTH", "pri_growth"),
            "high": getattr(settings, "PADDLE_PRICE_HIGH", "pri_high"),
        }
        return price_map.get(variant, "pri_starter")

    def _to_subscription_info(self, subscription: Subscription) -> SubscriptionInfo:
        """Convert Subscription model to SubscriptionInfo schema."""
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

        # Extract checkout_url from metadata for pending subscriptions
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


# ── Singleton Service ────────────────────────────────────────────────────

_subscription_service: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get the subscription service singleton."""
    global _subscription_service
    if _subscription_service is None:
        _subscription_service = SubscriptionService()
    return _subscription_service
