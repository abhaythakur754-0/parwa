"""
PARWA AI — Vonage (formerly Nexmo) SMS Provider

API reference: https://developer.vonage.com/api/sms
"""

from __future__ import annotations

import hashlib
import logging
import random
import string
from typing import Any, Dict, List

import httpx

from .base import ConnectionStatus, ProviderResult, SMSProvider

logger = logging.getLogger(__name__)

VONAGE_REST_URL = "https://rest.nexmo.com"
VONAGE_API_URL = "https://api.nexmo.com"


class VonageProvider(SMSProvider):
    """Vonage (Nexmo) SMS provider adapter."""

    provider_name = "Vonage"
    provider_type = "vonage"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "api_key",
                "type": "text",
                "label": "Vonage API Key",
                "required": True,
                "help_text": "Found in Vonage Dashboard → API Settings",
            },
            {
                "name": "api_secret",
                "type": "password",
                "label": "Vonage API Secret",
                "required": True,
                "help_text": "Corresponding secret for the API key",
            },
            {
                "name": "from_number",
                "type": "text",
                "label": "Vonage Phone Number or Name",
                "required": True,
                "help_text": "Your Vonage number in E.164 format or an alphanumeric sender ID",
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["send_sms"]

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        api_key = credentials.get("api_key", "")
        api_secret = credentials.get("api_secret", "")
        from_number = credentials.get("from_number", "")

        if not api_key:
            return ProviderResult.fail("API key is required")
        if len(api_key) < 6:
            return ProviderResult.fail("API key appears too short")
        if not api_secret:
            return ProviderResult.fail("API secret is required")
        if len(api_secret) < 8:
            return ProviderResult.fail("API secret appears too short")
        if not from_number:
            return ProviderResult.fail("From number or sender ID is required")

        return ProviderResult.ok("Credentials look valid")

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING
        api_key = credentials.get("api_key", "")
        api_secret = credentials.get("api_secret", "")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get account balance — lightweight read-only call
                response = await client.get(
                    f"{VONAGE_REST_URL}/account/get-balance",
                    params={"api_key": api_key, "api_secret": api_secret},
                )

            if response.status_code == 200:
                data = response.json()
                balance = data.get("value", "unknown")
                currency = data.get("currency", "EUR")
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to Vonage — balance: {balance} {currency}",
                    data={"balance": data},
                )

            self.status = ConnectionStatus.ERROR
            if response.status_code == 401:
                return ProviderResult.fail("Invalid Vonage API key or secret")

            return ProviderResult.fail(
                f"Vonage returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to Vonage timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach Vonage API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing Vonage connection")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── Send SMS ─────────────────────────────────────────────────────────

    async def send_sms(
        self,
        to: str,
        message: str,
        **kwargs: Any,
    ) -> ProviderResult:
        api_key = self._credentials.get("api_key", "")
        api_secret = self._credentials.get("api_secret", "")
        from_number = kwargs.get("from_number") or self._credentials.get("from_number", "")

        if not api_key or not api_secret:
            return ProviderResult.fail("Vonage credentials not configured — call set_credentials first")
        if not from_number:
            return ProviderResult.fail("From number is required")

        form_data: Dict[str, Any] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "from": from_number,
            "to": to,
            "text": message,
        }

        # Optional: type (unicode, text, binary, wappush, etc.)
        if kwargs.get("type"):
            form_data["type"] = kwargs["type"]
        else:
            # Auto-detect if message contains non-ASCII
            try:
                message.encode("ascii")
                form_data["type"] = "text"
            except UnicodeEncodeError:
                form_data["type"] = "unicode"

        # Optional: status callback
        if kwargs.get("status_callback"):
            form_data["callback"] = kwargs["status_callback"]

        # Optional: delivery receipt callback
        if kwargs.get("delivery_callback"):
            form_data["dlr-url"] = kwargs["delivery_callback"]

        # Optional: client reference for tracking
        if kwargs.get("client_ref"):
            form_data["client-ref"] = kwargs["client_ref"]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{VONAGE_REST_URL}/sms/json",
                    data=form_data,
                )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])

                if messages and messages[0].get("status") == "0":
                    message_id = messages[0].get("message-id", "")
                    remaining_balance = messages[0].get("remaining-balance", "")
                    return ProviderResult.ok(
                        "SMS sent via Vonage",
                        data={
                            "message_id": message_id,
                            "remaining_balance": remaining_balance,
                            "provider": "vonage",
                        },
                    )

                # Vonage returns 200 even for errors — check message status
                error_text = messages[0].get("error-text", "Unknown error") if messages else "No messages returned"
                error_status = messages[0].get("status", "unknown") if messages else "unknown"
                return ProviderResult.fail(
                    f"Vonage SMS failed (status {error_status}): {error_text}",
                    data={"messages": messages},
                )

            return ProviderResult.fail(
                f"Vonage returned HTTP {response.status_code}: {response.text[:500]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Vonage SMS request timed out")
        except Exception as exc:
            logger.exception("Error sending SMS via Vonage")
            return ProviderResult.fail(f"Unexpected error: {exc}")
