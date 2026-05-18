"""
PARWA AI — Twilio SMS Provider

API reference: https://www.twilio.com/docs/sms/api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import quote

import httpx

from .base import ConnectionStatus, ProviderResult, SMSProvider

logger = logging.getLogger(__name__)

TWILIO_BASE_URL = "https://api.twilio.com/2010-04-01"


class TwilioProvider(SMSProvider):
    """Twilio SMS provider adapter."""

    provider_name = "Twilio"
    provider_type = "twilio"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "account_sid",
                "type": "text",
                "label": "Twilio Account SID",
                "required": True,
                "help_text": "Starts with 'AC' — find it in Twilio Console → Dashboard",
            },
            {
                "name": "auth_token",
                "type": "password",
                "label": "Twilio Auth Token",
                "required": True,
                "help_text": "Found below the Account SID in Twilio Console",
            },
            {
                "name": "from_number",
                "type": "text",
                "label": "Twilio Phone Number",
                "required": True,
                "help_text": "Your Twilio number in E.164 format (e.g. +1234567890)",
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["send_sms", "verify_otp", "voice_calls"]

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        account_sid = credentials.get("account_sid", "")
        auth_token = credentials.get("auth_token", "")
        from_number = credentials.get("from_number", "")

        if not account_sid:
            return ProviderResult.fail("Account SID is required")
        if not account_sid.startswith("AC"):
            return ProviderResult.fail("Twilio Account SIDs must start with 'AC'")
        if len(account_sid) != 34:
            return ProviderResult.fail("Twilio Account SID must be 34 characters")
        if not auth_token:
            return ProviderResult.fail("Auth Token is required")
        if len(auth_token) < 20:
            return ProviderResult.fail("Auth Token appears too short")
        if not from_number:
            return ProviderResult.fail("From number is required")
        if not from_number.startswith("+"):
            return ProviderResult.fail("Phone number must be in E.164 format (start with +)")

        return ProviderResult.ok("Credentials look valid")

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING
        account_sid = credentials.get("account_sid", "")
        auth_token = credentials.get("auth_token", "")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Fetch account details — lightweight read-only
                response = await client.get(
                    f"{TWILIO_BASE_URL}/Accounts/{account_sid}.json",
                    auth=(account_sid, auth_token),
                )

            if response.status_code == 200:
                account = response.json()
                friendly_name = account.get("friendly_name", "unknown")
                status = account.get("status", "unknown")
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to Twilio account: {friendly_name} (status: {status})",
                    data={"account": account},
                )

            self.status = ConnectionStatus.ERROR
            if response.status_code == 401:
                return ProviderResult.fail("Invalid Twilio credentials")
            if response.status_code == 404:
                return ProviderResult.fail(f"Account SID '{account_sid}' not found")

            return ProviderResult.fail(
                f"Twilio returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to Twilio timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach Twilio API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing Twilio connection")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── Send SMS ─────────────────────────────────────────────────────────

    async def send_sms(
        self,
        to: str,
        message: str,
        **kwargs: Any,
    ) -> ProviderResult:
        account_sid = self._credentials.get("account_sid", "")
        auth_token = self._credentials.get("auth_token", "")
        from_number = kwargs.get("from_number") or self._credentials.get("from_number", "")

        if not account_sid or not auth_token:
            return ProviderResult.fail("Twilio credentials not configured — call set_credentials first")
        if not from_number:
            return ProviderResult.fail("From number is required")

        form_data: Dict[str, Any] = {
            "To": to,
            "From": from_number,
            "Body": message,
        }

        # Optional: media URLs (MMS)
        if kwargs.get("media_urls"):
            form_data["MediaUrl"] = list(kwargs["media_urls"])

        # Optional: status callback
        if kwargs.get("status_callback"):
            form_data["StatusCallback"] = kwargs["status_callback"]

        # Optional: messaging service SID (overrides From)
        if kwargs.get("messaging_service_sid"):
            form_data["MessagingServiceSid"] = kwargs["messaging_service_sid"]
            form_data.pop("From", None)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{TWILIO_BASE_URL}/Accounts/{account_sid}/Messages.json",
                    auth=(account_sid, auth_token),
                    data=form_data,
                )

            if response.status_code in (200, 201):
                data = response.json()
                message_sid = data.get("sid", "")
                status = data.get("status", "unknown")
                return ProviderResult.ok(
                    f"SMS sent via Twilio (status: {status})",
                    data={"message_id": message_sid, "status": status, "provider": "twilio"},
                )

            return ProviderResult.fail(
                f"Twilio SMS failed (HTTP {response.status_code}): {response.text[:500]}",
                data={"status_code": response.status_code, "body": response.text[:500]},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Twilio SMS request timed out")
        except Exception as exc:
            logger.exception("Error sending SMS via Twilio")
            return ProviderResult.fail(f"Unexpected error: {exc}")
