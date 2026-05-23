"""
PARWA AI — SendGrid Email Provider

API reference: https://docs.sendgrid.com/api-reference
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from .base import ConnectionStatus, EmailProvider, ProviderResult

logger = logging.getLogger(__name__)

SENDGRID_BASE_URL = "https://api.sendgrid.com/v3"


class SendGridProvider(EmailProvider):
    """SendGrid email provider adapter."""

    provider_name = "SendGrid"
    provider_type = "sendgrid"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "api_key",
                "type": "password",
                "label": "SendGrid API Key",
                "required": True,
                "help_text": "Starts with 'SG.' — create one at SendGrid → Settings → API Keys",
            },
            {
                "name": "from_email",
                "type": "text",
                "label": "Default From Email",
                "required": False,
                "help_text": "Verified sender e-mail address",
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
        if not api_key.startswith("SG."):
            return ProviderResult.fail("SendGrid API keys must start with 'SG.'")
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
                    f"{SENDGRID_BASE_URL}/user/account",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )

            if response.status_code == 200:
                account = response.json()
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to SendGrid account: {account.get('email', 'unknown')}",
                    data={"account": account},
                )

            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail(
                f"SendGrid returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to SendGrid timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach SendGrid API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing SendGrid connection")
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

        # Build SendGrid v3 Mail Send payload
        payload: Dict[str, Any] = {
            "personalizations": [
                {"to": [{"email": to}]}
            ],
            "from": {"email": from_email, "name": from_name} if from_name else {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/html", "value": body}],
        }

        # Optional CC / BCC / Reply-To
        if kwargs.get("cc"):
            payload["personalizations"][0]["cc"] = [{"email": addr} for addr in kwargs["cc"]]
        if kwargs.get("bcc"):
            payload["personalizations"][0]["bcc"] = [{"email": addr} for addr in kwargs["bcc"]]
        if kwargs.get("reply_to"):
            payload["reply_to"] = {"email": kwargs["reply_to"]}

        # Template mode
        if kwargs.get("template_id"):
            payload["template_id"] = kwargs["template_id"]
            # In template mode, content and subject are optional
            payload.pop("content", None)
            payload.pop("subject", None)
            # Add dynamic template data if provided
            if kwargs.get("template_data"):
                payload["personalizations"][0]["dynamic_template_data"] = kwargs["template_data"]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{SENDGRID_BASE_URL}/mail/send",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            # SendGrid returns 202 Accepted on success with no body
            if response.status_code == 202:
                # The message ID is in the X-Message-Id header
                message_id = response.headers.get("X-Message-Id", "")
                return ProviderResult.ok(
                    "Email sent via SendGrid",
                    data={"message_id": message_id, "provider": "sendgrid"},
                )

            return ProviderResult.fail(
                f"SendGrid send failed (HTTP {response.status_code}): {response.text[:500]}",
                data={"status_code": response.status_code, "body": response.text[:500]},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("SendGrid send request timed out")
        except Exception as exc:
            logger.exception("Error sending email via SendGrid")
            return ProviderResult.fail(f"Unexpected error: {exc}")
