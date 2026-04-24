"""
Paddle Service for Jarvis Integration (Phase 10 — Week 6 Day 7)

Service layer wrapping PaddleClient for Jarvis-specific operations:
- Demo pack checkout ($1, 500 messages + 3 min AI call, 24h)
- Variant subscription checkout (full subscription)
- Webhook processing (demo pack success, variant subscription success)
- Payment status queries

Uses the existing PaddleClient (BC-002) for all Paddle API calls.
"""

import logging
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.clients.paddle_client import PaddleClient, get_paddle_client, PaddleError

logger = logging.getLogger("parwa.services.paddle")


# ── Constants ────────────────────────────────────────────────────────

DEMO_PACK_AMOUNT = "1.00"
DEMO_PACK_CURRENCY = "USD"
DEMO_PACK_MESSAGES = 500
DEMO_PACK_CALL_MINUTES = 3
DEMO_PACK_DURATION_HOURS = 24

# Default price IDs — used until PADDLE_PRICE_IDS env var is set
_DEFAULT_PRICE_IDS: Dict[str, str] = {
    "demo_pack": "pri_demo_pack_01",
    # Plan price IDs
    "mini_parwa": "pri_mini_parwa_01",
    "parwa": "pri_parwa_01",
    "high_parwa": "pri_high_parwa_01",
    # E-commerce variants
    "order_management": "pri_order_mgmt_01",
    "returns_refunds": "pri_returns_01",
    "product_faq": "pri_faq_01",
    "shipping_inquiries": "pri_shipping_01",
    "payment_issues": "pri_payment_issues_01",
    # SaaS variants
    "technical_support": "pri_tech_support_01",
    "billing_support": "pri_billing_support_01",
    "feature_requests": "pri_feature_req_01",
    "api_support": "pri_api_support_01",
    "account_issues": "pri_account_issues_01",
    # Logistics variants
    "shipment_tracking": "pri_shipment_track_01",
    "delivery_issues": "pri_delivery_issues_01",
    "warehouse_queries": "pri_warehouse_01",
    "fleet_management": "pri_fleet_01",
    "customs": "pri_customs_01",
    # Industry Add-On price IDs (Day 3: V2-V10)
    "addon_ecommerce_monthly": "pri_addon_ecommerce_mo",
    "addon_ecommerce_yearly": "pri_addon_ecommerce_yr",
    "addon_saas_monthly": "pri_addon_saas_mo",
    "addon_saas_yearly": "pri_addon_saas_yr",
    "addon_logistics_monthly": "pri_addon_logistics_mo",
    "addon_logistics_yearly": "pri_addon_logistics_yr",
    "addon_others_monthly": "pri_addon_others_mo",
    "addon_others_yearly": "pri_addon_others_yr",
    # Healthcare variants
    "appointment_scheduling": "pri_appt_sched_01",
    "insurance_verification": "pri_insurance_01",
    "medical_records": "pri_med_records_01",
    "prescription_management": "prescription_mgmt_01",
    "medical_billing": "pri_med_billing_01",
}


def _load_price_ids() -> Dict[str, str]:
    """Load price IDs from env config, falling back to defaults."""
    try:
        from app.config import get_settings
        _settings = get_settings()
        env_json = _settings.PADDLE_PRICE_IDS
        if env_json:
            overrides = json.loads(env_json)
            merged = {**_DEFAULT_PRICE_IDS, **overrides}
            logger.info("paddle_price_ids_loaded_from_env count=%d", len(merged))
            return merged
    except Exception as e:
        logger.warning("paddle_price_ids_env_parse_failed error=%s", str(e))
    return dict(_DEFAULT_PRICE_IDS)


# Price ID lookups — loaded once at module level
_PRICE_IDS = _load_price_ids()

DEMO_PACK_PRICE_ID = _PRICE_IDS.get("demo_pack", "pri_demo_pack_01")

# Plan → Paddle price ID mapping (configurable)
PLAN_PRICE_IDS: Dict[str, str] = {
    "mini_parwa": _PRICE_IDS.get("mini_parwa", "pri_mini_parwa_01"),
    "parwa": _PRICE_IDS.get("parwa", "pri_parwa_01"),
    "high_parwa": _PRICE_IDS.get("high_parwa", "pri_high_parwa_01"),
}

# Industry variant price IDs — all non-plan entries
VARIANT_PRICE_IDS: Dict[str, str] = {
    k: v for k, v in _PRICE_IDS.items()
    if k not in ("demo_pack", "mini_parwa", "parwa", "high_parwa")
}


class PaddleServiceError(Exception):
    """Base exception for Paddle service errors."""
    def __init__(self, message: str, code: str = "paddle_service_error", details: Any = None):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(self.message)


class DemoPackAlreadyActiveError(PaddleServiceError):
    """Raised when user tries to purchase demo pack while one is active."""
    def __init__(self, message: str = "Demo pack is already active"):
        super().__init__(message, code="demo_pack_already_active")


class CheckoutCreationError(PaddleServiceError):
    """Raised when Paddle checkout creation fails."""
    def __init__(self, message: str = "Failed to create checkout", details: Any = None):
        super().__init__(message, code="checkout_creation_failed", details=details)


class PaymentNotFoundError(PaddleServiceError):
    """Raised when payment/session not found."""
    def __init__(self, message: str = "Payment not found"):
        super().__init__(message, code="payment_not_found")


class WebhookProcessingError(PaddleServiceError):
    """Raised when webhook processing fails."""
    def __init__(self, message: str = "Webhook processing failed", details: Any = None):
        super().__init__(message, code="webhook_processing_failed", details=details)


# ── Paddle Service ──────────────────────────────────────────────────────────


class PaddleService:
    """
    Service layer for Jarvis-specific Paddle operations.

    Wraps the PaddleClient with business logic for:
    - Demo pack purchases ($1, 24h access)
    - Variant subscription checkouts
    - Webhook event processing
    - Payment status tracking
    """

    def __init__(self, client: Optional[PaddleClient] = None):
        self._client = client

    @property
    def client(self) -> PaddleClient:
        """Get or create Paddle client."""
        if self._client is None:
            self._client = get_paddle_client()
        return self._client

    # ── Demo Pack Operations ─────────────────────────────────────────────

    async def create_demo_pack_checkout(
        self,
        session_id: str,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Paddle checkout for the $1 Demo Pack.

        The demo pack provides:
        - 500 messages for 24 hours
        - 1 AI-powered demo call (3 minutes)
        - Full onboarding guidance

        Args:
            session_id: Jarvis session ID (stored in custom_data)
            customer_email: Optional customer email (for pre-fill)
            customer_name: Optional customer name (for pre-fill)

        Returns:
            Dict with checkout URL and transaction details:
            {
                "checkout_url": str,
                "transaction_id": str,
                "status": "pending",
                "amount": "1.00",
                "currency": "USD",
                "pack_type": "demo",
            }

        Raises:
            CheckoutCreationError: If checkout creation fails
        """
        logger.info(
            "paddle_service_create_demo_pack session_id=%s email=%s",
            session_id,
            customer_email or "none",
        )

        try:
            # Build checkout items
            items = [
                {
                    "price_id": DEMO_PACK_PRICE_ID,
                    "quantity": 1,
                }
            ]

            # Build custom data to link checkout to session
            custom_data = {
                "session_id": session_id,
                "pack_type": "demo",
                "source": "jarvis_onboarding",
            }

            # Create customer data if provided
            customer_data = {}
            if customer_email:
                customer_data["email"] = customer_email
            if customer_name:
                customer_data["name"] = customer_name

            # Build checkout request
            checkout_data: Dict[str, Any] = {
                "items": items,
                "custom_data": custom_data,
            }

            if customer_data:
                checkout_data["customer"] = customer_data

            # Use Paddle's Transactions API to create a one-time checkout
            result = await self.client._request(
                "POST",
                "/transactions",
                json=checkout_data,
            )

            checkout_url = result.get("checkout", {}).get("url")
            transaction_id = result.get("id", "")

            if not checkout_url:
                logger.error(
                    "paddle_service_no_checkout_url session_id=%s result=%s",
                    session_id,
                    str(result)[:200],
                )
                raise CheckoutCreationError(
                    "Paddle returned no checkout URL",
                    details={"result": str(result)[:500]},
                )

            logger.info(
                "paddle_service_demo_pack_created session_id=%s txn=%s url=%s",
                session_id,
                transaction_id,
                checkout_url[:80],
            )

            return {
                "checkout_url": checkout_url,
                "transaction_id": transaction_id,
                "status": "pending",
                "amount": DEMO_PACK_AMOUNT,
                "currency": DEMO_PACK_CURRENCY,
                "pack_type": "demo",
            }

        except PaddleError as e:
            logger.error(
                "paddle_service_demo_pack_paddle_error session_id=%s error=%s",
                session_id,
                str(e),
            )
            raise CheckoutCreationError(
                f"Paddle API error: {str(e)}",
                details={"paddle_error": str(e)},
            ) from e
        except CheckoutCreationError:
            raise
        except Exception as e:
            logger.error(
                "paddle_service_demo_pack_unexpected session_id=%s error=%s",
                session_id,
                str(e),
            )
            raise CheckoutCreationError(
                f"Unexpected error: {str(e)}",
            ) from e

    async def handle_demo_pack_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a demo pack payment success webhook event.

        Called when transaction.completed or transaction.paid fires
        for a demo pack purchase.

        Updates the Jarvis session:
        - pack_type = "demo"
        - pack_expiry = now + 24 hours
        - message_count_today = 0
        - remaining_today = 500
        - demo_call_remaining = true

        Args:
            event_data: Parsed Paddle event data dict containing:
                - transaction_id: str
                - customer_id: str (optional)
                - amount: str
                - status: str
                - custom_data: dict with session_id and pack_type

        Returns:
            Dict with processing result:
            {
                "status": "processed",
                "action": "demo_pack_activated",
                "session_id": str,
                "pack_expiry": str (ISO),
                "messages_allowed": 500,
                "demo_call_remaining": true,
            }

        Raises:
            WebhookProcessingError: If processing fails
        """
        transaction_id = event_data.get("transaction_id", "")
        custom_data = event_data.get("custom_data", {})
        session_id = custom_data.get("session_id", "")

        if not session_id:
            raise WebhookProcessingError(
                "No session_id in webhook custom_data",
                details={"transaction_id": transaction_id},
            )

        logger.info(
            "paddle_service_demo_pack_webhook session_id=%s txn=%s",
            session_id,
            transaction_id,
        )

        # Calculate pack expiry (24 hours from now)
        expiry = datetime.now(timezone.utc) + timedelta(hours=DEMO_PACK_DURATION_HOURS)

        # Return the data that should be applied to the session
        # The actual session update is done by the caller (JarvisService or API handler)
        result = {
            "status": "processed",
            "action": "demo_pack_activated",
            "session_id": session_id,
            "transaction_id": transaction_id,
            "amount": event_data.get("amount", DEMO_PACK_AMOUNT),
            "currency": event_data.get("currency", DEMO_PACK_CURRENCY),
            "pack_type": "demo",
            "pack_expiry": expiry.isoformat(),
            "messages_allowed": DEMO_PACK_MESSAGES,
            "message_count_today": 0,
            "remaining_today": DEMO_PACK_MESSAGES,
            "demo_call_remaining": True,
            "demo_call_minutes": DEMO_PACK_CALL_MINUTES,
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "paddle_service_demo_pack_activated session_id=%s expiry=%s",
            session_id,
            expiry.isoformat(),
        )

        return result

    # ── Variant Subscription Operations ──────────────────────────────────

    async def create_variant_checkout(
        self,
        session_id: str,
        variants: List[Dict[str, Any]],
        industry: str,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Paddle checkout for variant subscription(s).

        Builds checkout items from selected variants and their quantities.

        Args:
            session_id: Jarvis session ID
            variants: List of variant dicts with:
                - id: str (variant identifier, e.g. "returns_refunds")
                - name: str (display name)
                - quantity: int (number of units)
                - price: float or int (price per unit per month)
            industry: Industry name (e.g. "e-commerce")
            customer_email: Optional email for pre-fill
            customer_name: Optional name for pre-fill

        Returns:
            Dict with checkout details:
            {
                "checkout_url": str,
                "transaction_id": str,
                "status": "pending",
                "amount": str,
                "currency": "USD",
                "items": [...],
                "variant_count": int,
                "total_monthly": str,
            }

        Raises:
            CheckoutCreationError: If checkout creation fails
        """
        logger.info(
            "paddle_service_create_variant_checkout session_id=%s "
            "variants=%d industry=%s",
            session_id,
            len(variants),
            industry,
        )

        try:
            # Build checkout items from variants
            items = []
            total_monthly = Decimal("0")

            for variant in variants:
                variant_id = variant.get("id", "")
                quantity = variant.get("quantity", 1)
                price = variant.get("price", variant.get("price_per_month", 0))

                # Look up Paddle price ID
                price_id = VARIANT_PRICE_IDS.get(variant_id)
                if not price_id:
                    logger.warning(
                        "paddle_service_unknown_variant variant=%s session=%s",
                        variant_id,
                        session_id,
                    )
                    # Use a fallback price ID based on variant name
                    price_id = f"pri_{variant_id}_01"

                items.append({
                    "price_id": price_id,
                    "quantity": int(quantity),
                })

                total_monthly += Decimal(str(price)) * int(quantity)

            if not items:
                raise CheckoutCreationError("No variants selected for checkout")

            # Build custom data
            custom_data = {
                "session_id": session_id,
                "pack_type": "subscription",
                "source": "jarvis_onboarding",
                "industry": industry,
                "variant_ids": [v.get("id", "") for v in variants],
                "variant_quantities": {v.get("id", ""): v.get("quantity", 1) for v in variants},
            }

            # Create customer data
            customer_data = {}
            if customer_email:
                customer_data["email"] = customer_email
            if customer_name:
                customer_data["name"] = customer_name

            # Build checkout request
            checkout_data: Dict[str, Any] = {
                "items": items,
                "custom_data": custom_data,
            }

            if customer_data:
                checkout_data["customer"] = customer_data

            # Create subscription checkout
            result = await self.client._request(
                "POST",
                "/transactions",
                json=checkout_data,
            )

            checkout_url = result.get("checkout", {}).get("url")
            transaction_id = result.get("id", "")

            if not checkout_url:
                logger.error(
                    "paddle_service_no_variant_checkout_url session_id=%s",
                    session_id,
                )
                raise CheckoutCreationError(
                    "Paddle returned no checkout URL for variant subscription",
                )

            logger.info(
                "paddle_service_variant_checkout_created session_id=%s txn=%s "
                "total=$%s variants=%d",
                session_id,
                transaction_id,
                str(total_monthly),
                len(variants),
            )

            return {
                "checkout_url": checkout_url,
                "transaction_id": transaction_id,
                "status": "pending",
                "amount": str(total_monthly),
                "currency": "USD",
                "items": items,
                "variant_count": len(variants),
                "total_monthly": str(total_monthly),
                "industry": industry,
            }

        except PaddleError as e:
            logger.error(
                "paddle_service_variant_paddle_error session_id=%s error=%s",
                session_id,
                str(e),
            )
            raise CheckoutCreationError(
                f"Paddle API error: {str(e)}",
                details={"paddle_error": str(e)},
            ) from e
        except CheckoutCreationError:
            raise
        except Exception as e:
            logger.error(
                "paddle_service_variant_unexpected session_id=%s error=%s",
                session_id,
                str(e),
            )
            raise CheckoutCreationError(
                f"Unexpected error: {str(e)}",
            ) from e

    async def handle_subscription_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a variant subscription success webhook event.

        Called when subscription.activated fires for a Jarvis variant subscription.

        Updates the Jarvis session:
        - payment_status = "completed"
        - Records hired variants from custom_data

        Args:
            event_data: Paddle event data containing:
                - subscription_id: str
                - customer_id: str
                - status: str
                - items: list of subscription items
                - custom_data: dict with session_id, variant_ids, industry

        Returns:
            Dict with processing result:
            {
                "status": "processed",
                "action": "subscription_activated",
                "session_id": str,
                "subscription_id": str,
                "hired_variants": [...],
                "industry": str,
            }

        Raises:
            WebhookProcessingError: If processing fails
        """
        subscription_id = event_data.get("subscription_id", "")
        custom_data = event_data.get("custom_data", {})
        session_id = custom_data.get("session_id", "")

        if not session_id:
            raise WebhookProcessingError(
                "No session_id in subscription webhook custom_data",
                details={"subscription_id": subscription_id},
            )

        variant_ids = custom_data.get("variant_ids", [])
        industry = custom_data.get("industry", "unknown")
        variant_quantities = custom_data.get("variant_quantities", {})

        logger.info(
            "paddle_service_subscription_webhook session_id=%s sub=%s "
            "variants=%s industry=%s",
            session_id,
            subscription_id,
            variant_ids,
            industry,
        )

        # Build hired variants list
        hired_variants = []
        for vid in variant_ids:
            qty = variant_quantities.get(vid, 1)
            price_id = VARIANT_PRICE_IDS.get(vid, "")
            hired_variants.append({
                "id": vid,
                "quantity": qty,
                "paddle_price_id": price_id,
            })

        result = {
            "status": "processed",
            "action": "subscription_activated",
            "session_id": session_id,
            "subscription_id": subscription_id,
            "customer_id": event_data.get("customer_id", ""),
            "hired_variants": hired_variants,
            "industry": industry,
            "variant_count": len(hired_variants),
            "currency": event_data.get("currency", "USD"),
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "paddle_service_subscription_activated session_id=%s sub=%s "
            "variants=%d",
            session_id,
            subscription_id,
            len(hired_variants),
        )

        return result

    # ── Payment Status ───────────────────────────────────────────────────

    async def get_payment_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current payment status for a session.

        Queries the database (and optionally Redis) for payment
        information linked to this session, including active payment
        failures, subscription status, and recent successful payment
        webhook events.

        Args:
            session_id: Jarvis session ID

        Returns:
            Dict with payment status:
            {
                "status": "none" | "pending" | "completed" | "failed" | "canceled",
                "paddle_transaction_id": str | null,
                "amount": str | null,
                "currency": str,
                "paid_at": str | null,
                "pack_type": "free" | "demo" | "subscription",
                "session_id": str,
            }
        """
        logger.info("paddle_service_get_payment_status session_id=%s", session_id)

        # Default result when nothing is found
        result: Dict[str, Any] = {
            "status": "none",
            "paddle_transaction_id": None,
            "amount": None,
            "currency": "USD",
            "paid_at": None,
            "pack_type": "free",
            "session_id": session_id,
        }

        # ── Resolve company_id and paddle_subscription_id ────────
        company_id: Optional[str] = None
        paddle_subscription_id: Optional[str] = None

        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            session_key = f"parwa:session:{session_id}"
            meta = await redis_client.hgetall(session_key)
            if meta:
                raw_cid = meta.get("company_id") or meta.get(b"company_id")
                if raw_cid is not None:
                    company_id = (
                        raw_cid.decode("utf-8")
                        if isinstance(raw_cid, bytes)
                        else str(raw_cid)
                    )
                raw_sid = (
                    meta.get("paddle_subscription_id")
                    or meta.get(b"paddle_subscription_id")
                )
                if raw_sid is not None:
                    paddle_subscription_id = (
                        raw_sid.decode("utf-8")
                        if isinstance(raw_sid, bytes)
                        else str(raw_sid)
                    )
        except Exception as exc:
            logger.debug(
                "paddle_service_redis_unavailable error=%s", str(exc),
            )

        if not company_id:
            logger.info(
                "paddle_service_no_company_for_session session_id=%s",
                session_id,
            )
            return result

        # ── Database queries ─────────────────────────────────────
        from database.base import SessionLocal
        from database.models.billing import Subscription
        from database.models.billing_extended import PaymentFailure
        from database.models.webhook_event import WebhookEvent

        try:
            with SessionLocal() as db:
                # 1. Check for unresolved payment failures
                failure = (
                    db.query(PaymentFailure)
                    .filter(
                        PaymentFailure.company_id == company_id,
                        PaymentFailure.resolved.is_(False),
                    )
                    .order_by(PaymentFailure.created_at.desc())
                    .first()
                )

                if failure:
                    result["status"] = "failed"
                    result["failure_code"] = failure.failure_code
                    result["failure_reason"] = failure.failure_reason
                    if failure.paddle_transaction_id:
                        result["paddle_transaction_id"] = (
                            failure.paddle_transaction_id
                        )
                    if failure.amount_attempted is not None:
                        result["amount"] = str(failure.amount_attempted)
                    result["currency"] = failure.currency or "USD"

                # 2. Check subscription status
                sub_q = db.query(Subscription).filter(
                    Subscription.company_id == company_id,
                )
                if paddle_subscription_id:
                    sub_q = sub_q.filter(
                        Subscription.paddle_subscription_id
                        == paddle_subscription_id,
                    )
                subscription = sub_q.order_by(
                    Subscription.created_at.desc(),
                ).first()

                if subscription:
                    sub_status = (subscription.status or "").lower()
                    if sub_status in ("active", "trialing"):
                        result["status"] = "completed"
                        result["pack_type"] = "subscription"
                        result["tier"] = subscription.tier
                        result["currency"] = "USD"
                        if subscription.paddle_subscription_id:
                            result["paddle_subscription_id"] = (
                                subscription.paddle_subscription_id
                            )
                    elif sub_status == "past_due":
                        if result["status"] != "failed":
                            result["status"] = "failed"
                            result["pack_type"] = "subscription"
                    elif sub_status == "canceled":
                        if result["status"] == "none":
                            result["status"] = "canceled"
                            result["pack_type"] = "subscription"

                # 3. Check for recent successful payment webhook events
                recent_cutoff = datetime.utcnow() - timedelta(hours=24)
                events = (
                    db.query(WebhookEvent)
                    .filter(
                        WebhookEvent.company_id == company_id,
                        WebhookEvent.event_type.in_([
                            "transaction.paid",
                            "transaction.completed",
                        ]),
                        WebhookEvent.created_at >= recent_cutoff,
                    )
                    .order_by(WebhookEvent.created_at.desc())
                    .limit(10)
                    .all()
                )

                for evt in events:
                    payload = evt.payload or {}
                    # custom_data may be at top level or nested under
                    # data.custom_data depending on Paddle event shape
                    custom_data = (
                        payload.get("custom_data")
                        or payload.get("data", {}).get("custom_data", {})
                    )
                    evt_session_id = custom_data.get("session_id", "")
                    if evt_session_id != session_id:
                        continue

                    # Found a matching successful payment event
                    evt_data = (
                        payload.get("data", {}).get("transaction", {})
                    )
                    result["status"] = "completed"
                    if evt.completed_at:
                        result["paid_at"] = evt.completed_at.isoformat()
                    txn_id = (
                        evt_data.get("id")
                        or evt_data.get("transaction_id")
                    )
                    if txn_id:
                        result["paddle_transaction_id"] = txn_id
                    totals = evt_data.get("details", {}).get("totals", {})
                    amt = (
                        totals.get("total")
                        or evt_data.get("total")
                        or evt_data.get("amount")
                    )
                    if amt is not None:
                        result["amount"] = str(amt)
                    cur = (
                        evt_data.get("details", {}).get("currency_code")
                        or evt_data.get("currency_code", "USD")
                    )
                    result["currency"] = cur
                    pack = custom_data.get("pack_type", "demo")
                    result["pack_type"] = pack
                    break  # use the most recent match

        except Exception as exc:
            logger.error(
                "paddle_service_get_payment_status_error "
                "session_id=%s error=%s",
                session_id,
                str(exc),
            )

        return result

    # ── Idempotency ──────────────────────────────────────────────────────

    @staticmethod
    def is_duplicate_event(
        event_id: str,
        processed_ids: Optional[set] = None,
    ) -> bool:
        """
        Check if a webhook event has already been processed (idempotency).

        Uses the caller-supplied *processed_ids* set for fast in-memory
        lookup.  The set is ephemeral — it does not survive process
        restarts.

        TODO(M4): Persist processed event IDs in a durable store (Redis
        SET or a database table with a short TTL) so that idempotency
        is maintained across restarts and across multiple workers.
        Suggested key: ``parwa:paddle:processed:{event_id}`` with a
        48-hour TTL.

        Args:
            event_id: Paddle event notification ID
            processed_ids: Set of already-processed event IDs (in-memory or cached)

        Returns:
            True if this event was already processed
        """
        if processed_ids is None:
            return False
        return event_id in processed_ids

    @staticmethod
    def mark_event_processed(
        event_id: str,
        processed_ids: set,
    ) -> None:
        """
        Mark a webhook event as processed.

        Adds *event_id* to the in-memory set and logs the event for
        audit/debugging purposes.

        TODO(M4): Also persist to Redis or DB so the record survives
        restarts.  Example:
            ``redis.setex(f"parwa:paddle:processed:{event_id}", 172800, "1")``

        Args:
            event_id: Paddle event notification ID
            processed_ids: Set to add the event ID to
        """
        processed_ids.add(event_id)
        logger.debug(
            "paddle_event_marked_processed event_id=%s set_size=%d",
            event_id,
            len(processed_ids),
        )


# ── Factory ─────────────────────────────────────────────────────────────────

_paddle_service: Optional[PaddleService] = None


def get_paddle_service() -> PaddleService:
    """
    Get the Paddle service singleton.

    Returns:
        PaddleService instance
    """
    global _paddle_service
    if _paddle_service is None:
        _paddle_service = PaddleService()
        logger.info("paddle_service_initialized")
    return _paddle_service
