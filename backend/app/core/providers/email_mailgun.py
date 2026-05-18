"""
PARWA AI — Mailgun Email Provider

API reference: https://documentation.mailgun.com/en/latest/api-reference.html
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from .base import ConnectionStatus, EmailProvider, ProviderResult

logger = logging.getLogger(__name__)

MAILGRID_BASE_URL = "https://api.mailgun.net/v3"


class MailgunProvider(EmailProvider):
    """Mailgun email provider adapter."""

    provider_name = "Mailgun"
    provider_type = "mailgun"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "api_key",
                "type": "password",
                "label": "Mailgun API Key",
                "required": True,
                "help_text": "Starts with 'key-' — find it in Mailgun → Domains → API Keys",
            },
            {
                "name": "domain",
                "type": "text",
                "label": "Sending Domain",
                "required": True,
                "help_text": "The verified domain to send from (e.g. mail.yourdomain.com)",
            },
            {
                "name": "from_email",
                "type": "text",
                "label": "Default From Email",
                "required": False,
                "help_text": "Sender e-mail address (must use the sending domain)",
            },
            {
                "name": "from_name",
                "type": "text",
                "label": "Default From Name",
                "required": False,
                "help_text": "Display name for the sender",
            },
            {
                "name": "region",
                "type": "select",
                "label": "Mailgun Region",
                "required": False,
                "help_text": "US (default) or EU region",
                "options": [
                    {"value": "us", "label": "US"},
                    {"value": "eu", "label": "EU"},
                ],
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["send_email", "templates", "webhooks", " inbound_routing"]

    # ── Helpers ──────────────────────────────────────────────────────────

    def _base_url(self) -> str:
        """Return the correct API base URL depending on region."""
        region = self._credentials.get("region", "us")
        if region == "eu":
            return "https://api.eu.mailgun.net/v3"
        return MAILGRID_BASE_URL

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        api_key = credentials.get("api_key", "")
        domain = credentials.get("domain", "")

        if not api_key:
            return ProviderResult.fail("API key is required")
        if not api_key.startswith("key-"):
            return ProviderResult.fail("Mailgun API keys must start with 'key-'")
        if not domain:
            return ProviderResult.fail("Sending domain is required")
        if "." not in domain:
            return ProviderResult.fail("Domain appears invalid — must contain a dot")

        return ProviderResult.ok("Credentials look valid")

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING
        api_key = credentials.get("api_key", "")
        domain = credentials.get("domain", "")

        region = credentials.get("region", "us")
        base = "https://api.eu.mailgun.net/v3" if region == "eu" else MAILGRID_BASE_URL

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get domain stats — lightweight read-only call
                response = await client.get(
                    f"{base}/domains/{domain}",
                    auth=("api", api_key),
                )

            if response.status_code == 200:
                data = response.json()
                domain_info = data.get("domain", {})
                state = domain_info.get("state", "unknown")
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to Mailgun domain '{domain}' (state: {state})",
                    data={"domain": domain_info},
                )

            self.status = ConnectionStatus.ERROR
            if response.status_code == 401:
                return ProviderResult.fail("Invalid Mailgun API key")
            if response.status_code == 404:
                return ProviderResult.fail(f"Domain '{domain}' not found in Mailgun")

            return ProviderResult.fail(
                f"Mailgun returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to Mailgun timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach Mailgun API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing Mailgun connection")
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
        domain = self._credentials.get("domain", "")
        from_email = kwargs.get("from_email") or self._credentials.get("from_email", f"postmaster@{domain}")
        from_name = kwargs.get("from_name") or self._credentials.get("from_name", "")

        if not api_key:
            return ProviderResult.fail("No API key configured — call set_credentials first")
        if not domain:
            return ProviderResult.fail("Sending domain is required")

        base_url = self._base_url()

        # Mailgun uses form-encoded data
        form_data: Dict[str, Any] = {
            "from": f"{from_name} <{from_email}>" if from_name else from_email,
            "to": [to],
            "subject": subject,
            "html": body,
        }

        # Optional fields
        if kwargs.get("cc"):
            form_data["cc"] = list(kwargs["cc"])
        if kwargs.get("bcc"):
            form_data["bcc"] = list(kwargs["bcc"])
        if kwargs.get("reply_to"):
            form_data["h:Reply-To"] = kwargs["reply_to"]

        # Template mode
        if kwargs.get("template_id"):
            form_data["template"] = kwargs["template_id"]
            if kwargs.get("template_data"):
                import json
                form_data["h:X-Mailgun-Variables"] = json.dumps(kwargs["template_data"])
            form_data.pop("html", None)
            form_data.pop("subject", None)

        # Tagging
        if kwargs.get("tags"):
            form_data["o:tag"] = list(kwargs["tags"])

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{base_url}/{domain}/messages",
                    auth=("api", api_key),
                    data=form_data,
                )

            if response.status_code == 200:
                data = response.json()
                message_id = data.get("id", "")
                return ProviderResult.ok(
                    "Email sent via Mailgun",
                    data={"message_id": message_id, "provider": "mailgun"},
                )

            return ProviderResult.fail(
                f"Mailgun send failed (HTTP {response.status_code}): {response.text[:500]}",
                data={"status_code": response.status_code, "body": response.text[:500]},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Mailgun send request timed out")
        except Exception as exc:
            logger.exception("Error sending email via Mailgun")
            return ProviderResult.fail(f"Unexpected error: {exc}")
