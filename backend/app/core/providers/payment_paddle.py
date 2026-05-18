"""
PARWA AI — Paddle Payment Provider

API reference: https://developer.paddle.com/api-reference/overview
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from .base import ConnectionStatus, PaymentProvider, ProviderResult

logger = logging.getLogger(__name__)

PADDLE_BASE_URL = "https://api.paddle.com"


class PaddleProvider(PaymentProvider):
    """Paddle payment provider adapter (Paddle Billing / Paddle.com)."""

    provider_name = "Paddle"
    provider_type = "paddle"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "api_key",
                "type": "password",
                "label": "Paddle API Key",
                "required": True,
                "help_text": "Starts with 'pdl_' — create one in Paddle → Developer Tools → Authentication",
            },
            {
                "name": "client_token",
                "type": "password",
                "label": "Paddle Client Token",
                "required": True,
                "help_text": "Used for client-side checkout (starts with 'pdl_clt_')",
            },
            {
                "name": "environment",
                "type": "select",
                "label": "Environment",
                "required": False,
                "help_text": "Sandbox or Production",
                "options": [
                    {"value": "sandbox", "label": "Sandbox"},
                    {"value": "production", "label": "Production"},
                ],
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["subscriptions", "one_time_payments", "webhooks", "refunds"]

    # ── Helpers ──────────────────────────────────────────────────────────

    def _base_url(self) -> str:
        """Return sandbox or production base URL."""
        env = self._credentials.get("environment", "production")
        if env == "sandbox":
            return "https://sandbox-api.paddle.com"
        return PADDLE_BASE_URL

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        api_key = credentials.get("api_key", "")
        client_token = credentials.get("client_token", "")

        if not api_key:
            return ProviderResult.fail("API key is required")
        if not api_key.startswith("pdl_"):
            return ProviderResult.fail("Paddle API keys must start with 'pdl_'")
        if len(api_key) < 20:
            return ProviderResult.fail("API key appears too short")
        if not client_token:
            return ProviderResult.fail("Client token is required")

        return ProviderResult.ok("Credentials look valid")

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING
        api_key = credentials.get("api_key", "")
        env = credentials.get("environment", "production")
        base = "https://sandbox-api.paddle.com" if env == "sandbox" else PADDLE_BASE_URL

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # List transactions (1 result) — lightweight read-only
                response = await client.get(
                    f"{base}/transactions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"per_page": 1},
                )

            if response.status_code == 200:
                data = response.json()
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to Paddle ({env})",
                    data={"environment": env, "meta": data.get("meta", {})},
                )

            self.status = ConnectionStatus.ERROR
            if response.status_code == 401:
                return ProviderResult.fail("Invalid Paddle API key")
            if response.status_code == 403:
                return ProviderResult.fail("Paddle API key does not have the required permissions")

            return ProviderResult.fail(
                f"Paddle returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to Paddle timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach Paddle API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing Paddle connection")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── Get subscription ─────────────────────────────────────────────────

    async def get_subscription(self, subscription_id: str) -> ProviderResult:
        api_key = self._credentials.get("api_key", "")

        if not api_key:
            return ProviderResult.fail("No API key configured — call set_credentials first")

        base_url = self._base_url()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{base_url}/subscriptions/{subscription_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

            if response.status_code == 200:
                data = response.json()
                subscription = data.get("data", {})
                return ProviderResult.ok(
                    f"Subscription retrieved: {subscription.get('id', subscription_id)}",
                    data={"subscription": subscription, "provider": "paddle"},
                )

            if response.status_code == 404:
                return ProviderResult.fail(
                    f"Subscription '{subscription_id}' not found in Paddle"
                )

            return ProviderResult.fail(
                f"Paddle returned HTTP {response.status_code}: {response.text[:500]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Paddle subscription request timed out")
        except Exception as exc:
            logger.exception("Error retrieving Paddle subscription")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── List transactions ────────────────────────────────────────────────

    async def list_transactions(
        self,
        per_page: int = 50,
        page: int = 1,
        **kwargs: Any,
    ) -> ProviderResult:
        """List transactions with pagination."""
        api_key = self._credentials.get("api_key", "")

        if not api_key:
            return ProviderResult.fail("No API key configured")

        base_url = self._base_url()
        params: Dict[str, Any] = {"per_page": per_page, "page": page}
        if kwargs.get("status"):
            params["status"] = kwargs["status"]
        if kwargs.get("customer_id"):
            params["customer_id"] = kwargs["customer_id"]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{base_url}/transactions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params=params,
                )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult.ok(
                    "Transactions retrieved",
                    data=data,
                )

            return ProviderResult.fail(
                f"Paddle returned HTTP {response.status_code}: {response.text[:500]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Paddle transaction request timed out")
        except Exception as exc:
            logger.exception("Error listing Paddle transactions")
            return ProviderResult.fail(f"Unexpected error: {exc}")
