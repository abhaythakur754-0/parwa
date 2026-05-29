"""
PARWA AI — Stripe Payment Provider

API reference: https://docs.stripe.com/api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from .base import ConnectionStatus, PaymentProvider, ProviderResult

logger = logging.getLogger(__name__)

STRIPE_BASE_URL = "https://api.stripe.com/v1"


class StripeProvider(PaymentProvider):
    """Stripe payment provider adapter."""

    provider_name = "Stripe"
    provider_type = "stripe"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "api_key",
                "type": "password",
                "label": "Stripe Secret Key",
                "required": True,
                "help_text": "Starts with 'sk_live_' or 'sk_test_' — find it in Stripe → Developers → API Keys",
            },
            {
                "name": "webhook_secret",
                "type": "password",
                "label": "Webhook Signing Secret",
                "required": False,
                "help_text": "Starts with 'whsec_' — used to verify webhook signatures",
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["subscriptions", "one_time_payments", "webhooks", "refunds"]

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        api_key = credentials.get("api_key", "")

        if not api_key:
            return ProviderResult.fail("Secret key is required")
        if not api_key.startswith("sk_"):
            return ProviderResult.fail("Stripe secret keys must start with 'sk_'")
        if not (api_key.startswith("sk_live_") or api_key.startswith("sk_test_")):
            return ProviderResult.fail(
                "Stripe secret keys must start with 'sk_live_' or 'sk_test_'"
            )
        if len(api_key) < 20:
            return ProviderResult.fail("Secret key appears too short")

        # Detect environment from key prefix
        is_live = api_key.startswith("sk_live_")
        return ProviderResult.ok(
            f"Credentials look valid ({'live' if is_live else 'test'} mode)"
        )

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING
        api_key = credentials.get("api_key", "")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Retrieve balance — lightweight read-only call
                response = await client.get(
                    f"{STRIPE_BASE_URL}/balance",
                    auth=(api_key, ""),
                )

            if response.status_code == 200:
                data = response.json()
                # Stripe balance returns amounts per currency
                available = data.get("available", [])
                pending = data.get("pending", [])

                is_live = api_key.startswith("sk_live_")
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to Stripe ({'live' if is_live else 'test'} mode)",
                    data={
                        "mode": "live" if is_live else "test",
                        "available": available,
                        "pending": pending,
                    },
                )

            self.status = ConnectionStatus.ERROR
            if response.status_code == 401:
                return ProviderResult.fail("Invalid Stripe API key")
            if response.status_code == 403:
                return ProviderResult.fail(
                    "Stripe API key does not have the required permissions"
                )

            return ProviderResult.fail(
                f"Stripe returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to Stripe timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach Stripe API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing Stripe connection")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── Get subscription ─────────────────────────────────────────────────

    async def get_subscription(self, subscription_id: str) -> ProviderResult:
        api_key = self._credentials.get("api_key", "")

        if not api_key:
            return ProviderResult.fail("No API key configured — call set_credentials first")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{STRIPE_BASE_URL}/subscriptions/{subscription_id}",
                    auth=(api_key, ""),
                )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult.ok(
                    f"Subscription retrieved: {data.get('id', subscription_id)}",
                    data={"subscription": data, "provider": "stripe"},
                )

            if response.status_code == 404:
                return ProviderResult.fail(
                    f"Subscription '{subscription_id}' not found in Stripe"
                )

            return ProviderResult.fail(
                f"Stripe returned HTTP {response.status_code}: {response.text[:500]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Stripe subscription request timed out")
        except Exception as exc:
            logger.exception("Error retrieving Stripe subscription")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── List customers ───────────────────────────────────────────────────

    async def list_customers(
        self,
        limit: int = 10,
        starting_after: str | None = None,
        **kwargs: Any,
    ) -> ProviderResult:
        """List Stripe customers with pagination."""
        api_key = self._credentials.get("api_key", "")

        if not api_key:
            return ProviderResult.fail("No API key configured")

        params: Dict[str, Any] = {"limit": limit}
        if starting_after:
            params["starting_after"] = starting_after
        if kwargs.get("email"):
            params["email"] = kwargs["email"]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{STRIPE_BASE_URL}/customers",
                    auth=(api_key, ""),
                    params=params,
                )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult.ok(
                    "Customers retrieved",
                    data=data,
                )

            return ProviderResult.fail(
                f"Stripe returned HTTP {response.status_code}: {response.text[:500]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Stripe customer request timed out")
        except Exception as exc:
            logger.exception("Error listing Stripe customers")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── Create refund ────────────────────────────────────────────────────

    async def create_refund(
        self,
        payment_intent_id: str,
        amount: int | None = None,
        reason: str = "requested_by_customer",
        **kwargs: Any,
    ) -> ProviderResult:
        """Create a refund for a payment.

        Args:
            payment_intent_id: The Stripe PaymentIntent ID to refund.
            amount:            Amount in smallest currency unit (e.g. cents).
                               If omitted, refunds the full amount.
            reason:            One of "duplicate", "fraudulent",
                               "requested_by_customer".
        """
        api_key = self._credentials.get("api_key", "")

        if not api_key:
            return ProviderResult.fail("No API key configured")

        form_data: Dict[str, Any] = {
            "payment_intent": payment_intent_id,
            "reason": reason,
        }
        if amount is not None:
            form_data["amount"] = amount
        if kwargs.get("metadata"):
            for k, v in kwargs["metadata"].items():
                form_data[f"metadata[{k}]"] = v

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{STRIPE_BASE_URL}/refunds",
                    auth=(api_key, ""),
                    data=form_data,
                )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult.ok(
                    f"Refund created: {data.get('id', '')}",
                    data={"refund": data, "provider": "stripe"},
                )

            return ProviderResult.fail(
                f"Stripe refund failed (HTTP {response.status_code}): {response.text[:500]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Stripe refund request timed out")
        except Exception as exc:
            logger.exception("Error creating Stripe refund")
            return ProviderResult.fail(f"Unexpected error: {exc}")
