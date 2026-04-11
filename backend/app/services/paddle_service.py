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
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.clients.paddle_client import PaddleClient, get_paddle_client, PaddleError

logger = logging.getLogger("parwa.services.paddle")


# ── Constants ────────────────────────────────────────────────────────────────

DEMO_PACK_PRICE_ID = "pri_demo_pack_01"  # Paddle price ID for $1 demo pack
DEMO_PACK_AMOUNT = "1.00"
DEMO_PACK_CURRENCY = "USD"
DEMO_PACK_MESSAGES = 500
DEMO_PACK_CALL_MINUTES = 3
DEMO_PACK_DURATION_HOURS = 24

# Plan → Paddle price ID mapping (configurable)
PLAN_PRICE_IDS: Dict[str, str] = {
    "mini_parwa": "pri_mini_parwa_01",
    "parwa": "pri_parwa_01",
    "parwa_high": "pri_parwa_high_01",
}

# Industry variant price IDs
VARIANT_PRICE_IDS: Dict[str, str] = {
    # E-commerce
    "order_management": "pri_order_mgmt_01",
    "returns_refunds": "pri_returns_01",
    "product_faq": "pri_faq_01",
    "shipping_inquiries": "pri_shipping_01",
    "payment_issues": "pri_payment_issues_01",
    # SaaS
    "technical_support": "pri_tech_support_01",
    "billing_support": "pri_billing_support_01",
    "feature_requests": "pri_feature_req_01",
    "api_support": "pri_api_support_01",
    "account_issues": "pri_account_issues_01",
    # Logistics
    "shipment_tracking": "pri_shipment_track_01",
    "delivery_issues": "pri_delivery_issues_01",
    "warehouse_queries": "pri_warehouse_01",
    "fleet_management": "pri_fleet_01",
    "customs": "pri_customs_01",
    # Healthcare
    "appointment_scheduling": "pri_appt_sched_01",
    "insurance_verification": "pri_insurance_01",
    "medical_records": "pri_med_records_01",
    "prescription_management": "prescription_mgmt_01",
    "medical_billing": "pri_med_billing_01",
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

        Looks up the payment status from the session's stored payment data.

        Args:
            session_id: Jarvis session ID

        Returns:
            Dict with payment status:
            {
                "status": "none" | "pending" | "completed" | "failed",
                "paddle_transaction_id": str | null,
                "amount": str | null,
                "currency": str,
                "paid_at": str | null,
                "pack_type": "free" | "demo" | "subscription",
            }

        Note:
            This is a stub that returns default values.
            In production, this would query the database or session store
            for the actual payment state linked to this session.
        """
        logger.info("paddle_service_get_payment_status session_id=%s", session_id)

        # Default: no payment made
        return {
            "status": "none",
            "paddle_transaction_id": None,
            "amount": None,
            "currency": "USD",
            "paid_at": None,
            "pack_type": "free",
            "session_id": session_id,
        }

    # ── Idempotency ──────────────────────────────────────────────────────

    @staticmethod
    def is_duplicate_event(
        event_id: str,
        processed_ids: Optional[set] = None,
    ) -> bool:
        """
        Check if a webhook event has already been processed (idempotency).

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

        Args:
            event_id: Paddle event notification ID
            processed_ids: Set to add the event ID to
        """
        processed_ids.add(event_id)


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
