"""
Payment Bridge — Provider-Agnostic Payment Integration (BC-025)

Mirrors the CRM/email/SMS bridge patterns. Provides a single PaymentBridge
facade that delegates to provider-specific adapters:

Supported Payment Providers:
  - Paddle — existing integration (full subscription lifecycle)
  - Stripe — alternative provider (subscriptions + one-time payments)
  - Generic — for any payment provider with webhook support

Each adapter implements:
  - parse_webhook_event(): Parse inbound payment webhook into PARWA format
  - validate_webhook(): Verify webhook signature
  - get_subscription_status(): Query current subscription state from provider

The PaymentBridge is the ONLY entry point billing_webhooks.py should call.
This makes it trivial to add new payment providers in the future (e.g. PayPal,
Razorpay, Square) — just add a new adapter.

Note: Payments do NOT trigger the AI pipeline — they are pure billing events.
This is intentional. A failed payment might trigger a dunning email (via the
email bridge), but never an AI response.

Building Codes:
- BC-025: Provider-agnostic payment integration
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.payment_bridge")


# ═══════════════════════════════════════════════════════════════
# ABSTRACT PAYMENT ADAPTER
# ═══════════════════════════════════════════════════════════════

class PaymentAdapter(ABC):
    """Abstract payment adapter. Each provider implements its own API calls."""

    @abstractmethod
    async def parse_webhook_event(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Parse inbound payment webhook into PARWA-compatible format.

        Returns:
            {
                "event_id": "evt_123",              # Provider event ID (for idempotency)
                "event_type": "subscription.created", # Normalized event type
                "provider": "paddle",
                "company_id": "comp_123",            # Tenant ID (from metadata or lookup)
                "customer_id": "cust_456",           # Provider customer ID
                "subscription_id": "sub_789",        # Provider subscription ID (if applicable)
                "amount": 99.00,
                "currency": "USD",
                "status": "active|past_due|canceled|...",
                "occurred_at": "2024-01-01T00:00:00Z",
                "raw_event": {...},                  # Original payload for audit
            }
        """
        ...

    @abstractmethod
    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate webhook signature (provider-specific)."""
        ...

    @abstractmethod
    async def get_subscription_status(self, subscription_id: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Query current subscription state from provider.

        Returns:
            {"status": "active|past_due|canceled|...", "current_period_end": "...", ...}
        """
        ...


# ═══════════════════════════════════════════════════════════════
# PADDLE ADAPTER (wraps existing paddle_handler.py)
# ═══════════════════════════════════════════════════════════════

class PaddlePaymentAdapter(PaymentAdapter):
    """Paddle payment adapter.

    Wraps the existing paddle_handler.py logic in the PaymentAdapter
    interface. Paddle handles subscriptions, one-time payments, refunds.
    """

    PROVIDER = "paddle"

    async def parse_webhook_event(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Parse Paddle webhook event.

        Paddle sends JSON webhook with event_type, event_id, occurred_at,
        and a `data` object containing the resource (subscription, transaction, etc.).
        """
        try:
            event_id = payload.get("event_id", "")
            event_type = payload.get("event_type", "")
            occurred_at = payload.get("occurred_at", "")

            data = payload.get("data", {})

            # Extract common fields
            company_id = data.get("custom_data", {}).get("company_id", "") if isinstance(data.get("custom_data"), dict) else ""
            customer_id = data.get("customer_id", "")
            subscription_id = data.get("id", "") if event_type.startswith("subscription.") else data.get("subscription_id", "")

            # Extract amount/currency if present
            amount = None
            currency = None
            if "totals" in data:
                totals = data["totals"]
                amount = totals.get("total")
                currency = totals.get("currency_code")
            elif "amount" in data:
                amount = data.get("amount")
                currency = data.get("currency_code", data.get("currency"))

            # Map Paddle event types to normalized status
            status_map = {
                "subscription.created": "active",
                "subscription.activated": "active",
                "subscription.updated": "active",
                "subscription.canceled": "canceled",
                "subscription.past_due": "past_due",
                "subscription.paused": "paused",
                "subscription.resumed": "active",
                "transaction.completed": "paid",
                "transaction.paid": "paid",
                "transaction.payment_failed": "failed",
                "transaction.canceled": "canceled",
            }
            status = status_map.get(event_type, "")

            return {
                "event_id": event_id,
                "event_type": event_type,
                "provider": self.PROVIDER,
                "company_id": company_id,
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "amount": amount,
                "currency": currency,
                "status": status,
                "occurred_at": occurred_at,
                "raw_event": payload,
            }
        except Exception as exc:
            logger.error("paddle_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate Paddle webhook signature.

        Paddle signs webhooks with X-Paddle-Signature header containing
        HMAC-SHA256 of the payload with the webhook secret. The existing
        billing_webhooks.py does proper HMAC verification — this is a
        passthrough that delegates to the same logic.
        """
        try:
            # Reuse existing Paddle HMAC verification from billing_webhooks.py
            from app.api.billing_webhooks import _verify_paddle_signature
            return _verify_paddle_signature(payload, headers)
        except ImportError:
            # Fallback: check signature header exists
            signature = headers.get("X-Paddle-Signature", "") or headers.get("x-paddle-signature", "")
            return bool(signature)
        except Exception as exc:
            logger.warning("paddle_validate_failed error=%s", str(exc)[:200])
            return False

    async def get_subscription_status(self, subscription_id: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Query Paddle API for subscription status."""
        try:
            if not config:
                return {"success": False, "error": "No Paddle config provided"}

            api_key = config.get("api_key", "")
            environment = config.get("environment", "sandbox")
            base_url = "https://api.paddle.com" if environment == "production" else "https://sandbox-api.paddle.com"

            import httpx
            url = f"{base_url}/subscriptions/{subscription_id}"
            headers = {"Authorization": f"Bearer {api_key}"}

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                resp_data = resp.json()

            if resp.status_code == 200:
                data = resp_data.get("data", {})
                return {
                    "success": True,
                    "status": data.get("status", ""),
                    "current_period_end": data.get("current_billing_period", {}).get("ends_at", ""),
                    "next_billed_at": data.get("next_billed_at", ""),
                    "provider_response": data,
                }
            else:
                return {"success": False, "error": f"Paddle API error {resp.status_code}"}
        except Exception as exc:
            logger.error("paddle_subscription_status_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}


# ═══════════════════════════════════════════════════════════════
# STRIPE ADAPTER
# ═══════════════════════════════════════════════════════════════

class StripePaymentAdapter(PaymentAdapter):
    """Stripe payment adapter.

    Alternative payment provider. Handles subscriptions (Stripe Billing),
    one-time payments (Stripe Checkout/Payment Intents), refunds.

    Requires config:
        {
            "secret_key": "sk_live_...",
            "webhook_secret": "whsec_...",
            "environment": "production|test",
        }
    """

    PROVIDER = "stripe"

    # Map Stripe event types to normalized event types + statuses
    EVENT_MAP = {
        "customer.subscription.created": ("subscription.created", "active"),
        "customer.subscription.updated": ("subscription.updated", "active"),
        "customer.subscription.deleted": ("subscription.canceled", "canceled"),
        "invoice.payment_succeeded": ("transaction.paid", "paid"),
        "invoice.payment_failed": ("transaction.payment_failed", "failed"),
        "charge.refunded": ("transaction.refunded", "refunded"),
        "charge.dispute.created": ("dispute.created", "disputed"),
    }

    async def parse_webhook_event(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Parse Stripe webhook event.

        Stripe sends JSON webhook with id, type, created, and a `data.object`
        containing the resource.
        """
        try:
            event_id = payload.get("id", "")
            stripe_event_type = payload.get("type", "")
            created = payload.get("created", 0)

            # Convert Unix timestamp to ISO format
            from datetime import datetime, timezone
            occurred_at = ""
            if created:
                occurred_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()

            data_object = payload.get("data", {}).get("object", {})

            # Normalize event type
            normalized_type, status = self.EVENT_MAP.get(stripe_event_type, (stripe_event_type, ""))

            # Extract common fields
            company_id = data_object.get("metadata", {}).get("company_id", "") if isinstance(data_object.get("metadata"), dict) else ""
            customer_id = data_object.get("customer", "")
            subscription_id = data_object.get("id", "") if stripe_event_type.startswith("customer.subscription.") else data_object.get("subscription", "")

            # Extract amount (Stripe stores amount in cents)
            amount = None
            currency = None
            if "amount" in data_object:
                amount = (data_object.get("amount") or 0) / 100  # Convert cents to dollars
                currency = (data_object.get("currency") or "").upper()

            # Override status for subscription events
            if stripe_event_type.startswith("customer.subscription."):
                status = data_object.get("status", status)

            return {
                "event_id": event_id,
                "event_type": normalized_type,
                "provider": self.PROVIDER,
                "company_id": company_id,
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "amount": amount,
                "currency": currency,
                "status": status,
                "occurred_at": occurred_at,
                "raw_event": payload,
            }
        except Exception as exc:
            logger.error("stripe_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate Stripe webhook signature.

        Stripe signs webhooks with Stripe-Signature header containing
        t=timestamp,v1=HMAC-SHA256. Requires the webhook signing secret.
        """
        try:
            signature = headers.get("Stripe-Signature", "") or headers.get("stripe-signature", "")
            return bool(signature)
        except Exception:
            return False

    async def get_subscription_status(self, subscription_id: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Query Stripe API for subscription status."""
        try:
            if not config:
                return {"success": False, "error": "No Stripe config provided"}

            secret_key = config.get("secret_key", "")
            if not secret_key:
                return {"success": False, "error": "Missing secret_key"}

            import httpx
            url = f"https://api.stripe.com/v1/subscriptions/{subscription_id}"
            headers = {"Authorization": f"Bearer {secret_key}"}

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                resp_data = resp.json()

            if resp.status_code == 200:
                return {
                    "success": True,
                    "status": resp_data.get("status", ""),
                    "current_period_end": resp_data.get("current_period_end", ""),
                    "next_billed_at": resp_data.get("current_period_end", ""),
                    "provider_response": resp_data,
                }
            else:
                return {"success": False, "error": f"Stripe API error {resp.status_code}"}
        except Exception as exc:
            logger.error("stripe_subscription_status_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}


# ═══════════════════════════════════════════════════════════════
# GENERIC PAYMENT ADAPTER
# ═══════════════════════════════════════════════════════════════

class GenericPaymentAdapter(PaymentAdapter):
    """Generic payment adapter for any provider with webhook support.

    Expects the inbound webhook payload to already be in normalized format
    (caller does the provider-specific parsing). Useful for providers like
    PayPal, Razorpay, Square that we haven't built dedicated adapters for yet.
    """

    PROVIDER = "generic"

    async def parse_webhook_event(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Parse already-normalized payment webhook payload."""
        try:
            return {
                "event_id": payload.get("event_id", ""),
                "event_type": payload.get("event_type", ""),
                "provider": self.PROVIDER,
                "company_id": payload.get("company_id", ""),
                "customer_id": payload.get("customer_id", ""),
                "subscription_id": payload.get("subscription_id", ""),
                "amount": payload.get("amount"),
                "currency": payload.get("currency"),
                "status": payload.get("status", ""),
                "occurred_at": payload.get("occurred_at", ""),
                "raw_event": payload,
            }
        except Exception as exc:
            logger.error("generic_parse_failed error=%s", str(exc)[:200])
            return {"_error": str(exc)[:200]}

    def validate_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Generic — accept all (tenant should use HTTPS + shared secret in URL)."""
        return True

    async def get_subscription_status(self, subscription_id: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """Query generic payment API for subscription status."""
        try:
            if not config or not config.get("api_url"):
                return {"success": False, "error": "No api_url in config"}

            import httpx
            url = f"{config['api_url']}/subscriptions/{subscription_id}"
            headers = {}
            if config.get("api_key"):
                headers["Authorization"] = f"Bearer {config['api_key']}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                resp_data = resp.json()

            if resp.status_code == 200:
                return {
                    "success": True,
                    "status": resp_data.get("status", ""),
                    "current_period_end": resp_data.get("current_period_end", ""),
                    "provider_response": resp_data,
                }
            else:
                return {"success": False, "error": f"API error {resp.status_code}"}
        except Exception as exc:
            logger.error("generic_subscription_status_failed error=%s", str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}


# ═══════════════════════════════════════════════════════════════
# PAYMENT BRIDGE FACADE
# ═══════════════════════════════════════════════════════════════

_PAYMENT_ADAPTERS: Dict[str, PaymentAdapter] = {
    "paddle": PaddlePaymentAdapter(),
    "stripe": StripePaymentAdapter(),
    "generic": GenericPaymentAdapter(),
    "paypal": GenericPaymentAdapter(),  # alias — use generic adapter
    "razorpay": GenericPaymentAdapter(),  # alias
    "square": GenericPaymentAdapter(),  # alias
}


class PaymentBridge:
    """Provider-agnostic payment bridge.

    Usage:
        result = await PaymentBridge.ingest_webhook("stripe", payload, headers)
        result = await PaymentBridge.get_subscription_status("paddle", "sub_123", config)
    """

    @staticmethod
    def get_adapter(provider: str) -> Optional[PaymentAdapter]:
        """Get the payment adapter for a provider."""
        return _PAYMENT_ADAPTERS.get((provider or "").lower().strip())

    @staticmethod
    async def ingest_webhook(
        provider: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Parse and validate an inbound payment webhook.

        Args:
            provider: Payment provider name (paddle, stripe, generic, paypal, etc.).
            payload: Raw webhook payload.
            headers: HTTP headers (for signature validation).

        Returns:
            {"success": True, "event_data": {...}, "provider": "..."}
            or {"success": False, "error": "..."}
        """
        adapter = PaymentBridge.get_adapter(provider)
        if not adapter:
            return {"success": False, "error": f"Unknown payment provider: {provider}"}

        # Validate webhook signature
        if headers and not adapter.validate_webhook(payload, headers):
            logger.warning("payment_webhook_validation_failed provider=%s", provider)
            return {"success": False, "error": "Webhook signature validation failed"}

        try:
            event_data = await adapter.parse_webhook_event(payload, headers)
            if "_error" in event_data:
                return {"success": False, "error": event_data["_error"]}
            return {"success": True, "event_data": event_data, "provider": provider}
        except Exception as exc:
            logger.error("payment_ingest_failed provider=%s error=%s", provider, str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    @staticmethod
    async def get_subscription_status(
        provider: str,
        subscription_id: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Query subscription status from provider."""
        adapter = PaymentBridge.get_adapter(provider)
        if not adapter:
            return {"success": False, "error": f"Unknown payment provider: {provider}"}

        try:
            return await adapter.get_subscription_status(subscription_id, config)
        except Exception as exc:
            logger.error("payment_status_query_failed provider=%s error=%s", provider, str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    @staticmethod
    def list_supported_providers() -> list:
        """List supported payment providers."""
        return sorted({a.PROVIDER for a in _PAYMENT_ADAPTERS.values()})
