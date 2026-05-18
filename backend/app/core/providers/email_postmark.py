"""
PARWA AI — Postmark Email Provider

API reference: https://postmarkapp.com/developer/api/overview
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from .base import ConnectionStatus, EmailProvider, ProviderResult

logger = logging.getLogger(__name__)

POSTMARK_BASE_URL = "https://api.postmarkapp.com"


class PostmarkProvider(EmailProvider):
    """Postmark email provider adapter."""

    provider_name = "Postmark"
    provider_type = "postmark"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "api_key",
                "type": "password",
                "label": "Postmark Server Token",
                "required": True,
                "help_text": "36-character hex UUID — find it in Postmark → Servers → API Tokens",
            },
            {
                "name": "from_email",
                "type": "text",
                "label": "Default From Email",
                "required": False,
                "help_text": "Verified sender signature e-mail",
            },
            {
                "name": "from_name",
                "type": "text",
                "label": "Default From Name",
                "required": False,
                "help_text": "Display name for the sender",
            },
            {
                "name": "message_stream",
                "type": "select",
                "label": "Message Stream",
                "required": False,
                "help_text": "Outbound (default) or broadcast stream",
                "options": [
                    {"value": "outbound", "label": "Outbound (Transactional)"},
                    {"value": "broadcast", "label": "Broadcast"},
                ],
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["send_email", "templates", "webhooks"]

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        api_key = credentials.get("api_key", "")

        if not api_key:
            return ProviderResult.fail("Server token is required")
        # Postmark server tokens are UUIDs (36 chars with dashes, 32 hex without)
        import re
        if not re.match(r"^[a-f0-9\-]{32,36}$", api_key):
            return ProviderResult.fail(
                "Postmark server token should be a 36-character hex UUID"
            )

        return ProviderResult.ok("Credentials look valid")

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING
        api_key = credentials.get("api_key", "")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{POSTMARK_BASE_URL}/server",
                    headers={
                        "X-Postmark-Server-Token": api_key,
                        "Accept": "application/json",
                    },
                )

            if response.status_code == 200:
                server = response.json()
                self.status = ConnectionStatus.CONNECTED
                return ProviderResult.ok(
                    f"Connected to Postmark server: {server.get('Name', 'unknown')}",
                    data={"server": server},
                )

            self.status = ConnectionStatus.ERROR
            if response.status_code == 401:
                return ProviderResult.fail("Invalid Postmark server token")
            if response.status_code == 422:
                return ProviderResult.fail("Postmark request was unprocessable")

            return ProviderResult.fail(
                f"Postmark returned HTTP {response.status_code}: {response.text[:300]}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Connection to Postmark timed out")
        except httpx.ConnectError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Cannot reach Postmark API — check network")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing Postmark connection")
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
        message_stream = kwargs.get("message_stream") or self._credentials.get("message_stream", "outbound")

        if not api_key:
            return ProviderResult.fail("No server token configured — call set_credentials first")
        if not from_email:
            return ProviderResult.fail("From email is required")

        payload: Dict[str, Any] = {
            "From": f"{from_name} <{from_email}>" if from_name else from_email,
            "To": to,
            "Subject": subject,
            "HtmlBody": body,
            "MessageStream": message_stream,
        }

        # Optional fields
        if kwargs.get("cc"):
            payload["Cc"] = ", ".join(kwargs["cc"])
        if kwargs.get("bcc"):
            payload["Bcc"] = ", ".join(kwargs["bcc"])
        if kwargs.get("reply_to"):
            payload["ReplyTo"] = kwargs["reply_to"]

        # Template mode
        if kwargs.get("template_id"):
            payload["TemplateId"] = int(kwargs["template_id"])
            if kwargs.get("template_data"):
                payload["TemplateModel"] = kwargs["template_data"]
            payload.pop("HtmlBody", None)
            payload.pop("Subject", None)

        # Tag
        if kwargs.get("tag"):
            payload["Tag"] = kwargs["tag"]

        # Track opens / links
        if kwargs.get("track_opens") is not None:
            payload["TrackOpens"] = kwargs["track_opens"]
        if kwargs.get("track_links") is not None:
            payload["TrackLinks"] = kwargs["track_links"]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{POSTMARK_BASE_URL}/email",
                    headers={
                        "X-Postmark-Server-Token": api_key,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            if response.status_code == 200:
                data = response.json()
                message_id = data.get("MessageID", "")
                return ProviderResult.ok(
                    "Email sent via Postmark",
                    data={"message_id": message_id, "provider": "postmark"},
                )

            # Postmark returns error details in JSON
            error_msg = "Unknown error"
            try:
                err_data = response.json()
                error_msg = err_data.get("Message", response.text[:300])
            except Exception:
                error_msg = response.text[:300]

            return ProviderResult.fail(
                f"Postmark send failed (HTTP {response.status_code}): {error_msg}",
                data={"status_code": response.status_code},
            )

        except httpx.TimeoutException:
            return ProviderResult.fail("Postmark send request timed out")
        except Exception as exc:
            logger.exception("Error sending email via Postmark")
            return ProviderResult.fail(f"Unexpected error: {exc}")
