"""
PARWA AI — Brevo (formerly Sendinblue) Email Provider

API reference: https://developers.brevo.com/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from .base import ConnectionStatus, EmailProvider, ProviderResult

logger = logging.getLogger(__name__)

BREVO_BASE_URL = "https://api.brevo.com/v3"


class BrevoProvider(EmailProvider):
    """Brevo (Sendinblue) email provider adapter."""

    provider_name = "Brevo"
    provider_type = "brevo"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "api_key",
                "type": "password",
                "label": "Brevo API Key",
                "required": True,
                "help_text": "Starts with 'xkeysib-' — find it in Brevo → SMTP & API → API Keys",
            },
            {
                "name": "from_email",
                "type": "text",
                "label": "Default From Email",
                "required": False,
                "help_text": "Sender e-mail address registered in Brevo",
            },
            {
                "name": "from_name",
                "type": "text",
                "label": "Default From Name",
                "required": False,
                "help_text": "Display name for the sender",
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["send_email", "templates", "webhooks"]

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        api_key = credentials.get("api_key", "")
        if not api_key:
            return ProviderResult.fail("API key is required")
        if not api_key.startswith("xkeysib-"):
            return ProviderResult.fail(
                "Brevo API keys must start with 'xkeysib-'"
            )
        if len(api_key) < 20:
            return ProviderResult.fail("API key appears too short")
        return ProviderResult.ok("Credentials look valid")

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING
        api_key = credentials.get("api_key", "")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{BREVO_BASE_URL}/account",
                    headers={"api-key": api_key},
                )

            if response.status_code == 200:
                account = response.json()
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to Brevo account: {account.get('email', 'unknown')}",
                    data={"account": account},
                )

            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail(
                f"Brevo returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to Brevo timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach Brevo API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing Brevo connection")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    # ── Send email ───────────────────────────────────────────────────────

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResult:
        api_key = self._credentials.get("api_key", "")
        from_email = kwargs.get("from_email") or self._credentials.get("from_email", "")
        from_name = kwargs.get("from_name") or self._credentials.get("from_name", "")

        if not api_key:
            return ProviderResult.fail("No API key configured — call set_credentials first")
        if not from_email:
            return ProviderResult.fail("From email is required")

        payload: Dict[str, Any] = {
            "sender": {"email": from_email, "name": from_name} if from_name else {"email": from_email},
            "to": [{"email": to}],
            "subject": subject,
            "htmlContent": body,
        }

        # Optional CC / BCC
        if kwargs.get("cc"):
            payload["cc"] = [{"email": addr} for addr in kwargs["cc"]]
        if kwargs.get("bcc"):
            payload["bcc"] = [{"email": addr} for addr in kwargs["bcc"]]
        if kwargs.get("reply_to"):
            payload["replyTo"] = {"email": kwargs["reply_to"]}
        if kwargs.get("template_id"):
            payload["templateId"] = int(kwargs["template_id"])
            # When using a template, subject and htmlContent are optional
            payload.pop("htmlContent", None)
            payload.pop("subject", None)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{BREVO_BASE_URL}/smtp/email",
                    headers={"api-key": api_key, "Content-Type": "application/json"},
                    json=payload,
                )

            if response.status_code in (200, 201):
                data = response.json()
                message_id = data.get("messageId", "")
                return ProviderResult.ok(
                    "Email sent via Brevo",
                    data={"message_id": message_id, "provider": "brevo"},
                )

            return ProviderResult.fail(
                f"Brevo send failed (HTTP {response.status_code}): {response.text[:500]}",
                data={"status_code": response.status_code, "body": response.text[:500]},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Brevo send request timed out")
        except Exception as exc:
            logger.exception("Error sending email via Brevo")
            return ProviderResult.fail(f"Unexpected error: {exc}")
