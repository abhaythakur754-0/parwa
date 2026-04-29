"""
Postmark Email Provider

Implementation of the EmailProvider interface for Postmark.
"""

from typing import Any, Dict

import httpx
from app.providers.base import (
    EmailMessage,
    EmailProvider,
    ProviderCapability,
    ProviderResult,
    ProviderStatus,
)


class PostmarkEmailProvider(EmailProvider):
    """Postmark email provider."""

    provider_name = "postmark"
    display_name = "Postmark"
    description = "Fast and reliable email delivery"
    website = "https://postmarkapp.com"

    required_config_fields = ["api_key"]
    optional_config_fields = ["from_email"]

    capabilities = [
        ProviderCapability.SEND_EMAIL,
        ProviderCapability.SEND_TEMPLATE_EMAIL,
        ProviderCapability.WEBHOOK_EVENTS,
        ProviderCapability.TRACK_OPENS,
        ProviderCapability.TRACK_CLICKS,
    ]

    API_URL = "https://api.postmarkapp.com/email"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.from_email = config.get("from_email", "noreply@parwa.ai")
        self._status = ProviderStatus.ACTIVE

    def test_connection(self) -> ProviderResult:
        try:
            response = httpx.get(
                "https://api.postmarkapp.com/server",
                headers={"X-Postmark-Server-Token": self.api_key},
                timeout=10.0,
            )

            if response.status_code == 200:
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                )
            else:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    error_code=str(response.status_code),
                    error_message=response.text[:200],
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message=str(e)[:200],
            )

    def get_rate_limits(self) -> Dict[str, Any]:
        return {
            "emails_per_second": 20,
            "note": "Limits vary by plan.",
        }

    def send_email(self, message: EmailMessage) -> ProviderResult:
        payload = {
            "From": message.from_email or self.from_email,
            "To": message.to,
            "Subject": message.subject,
            "HtmlBody": message.html_content,
        }

        if message.text_content:
            payload["TextBody"] = message.text_content

        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={
                    "X-Postmark-Server-Token": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_email",
                    message_id=str(data.get("MessageID")),
                )
            else:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="send_email",
                    error_code=str(response.status_code),
                    error_message=response.text[:200],
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_email",
                error_message=str(e)[:200],
            )

    def send_template_email(
        self, template_id: str, to: str, variables: Dict[str, Any]
    ) -> ProviderResult:
        payload = {
            "From": self.from_email,
            "To": to,
            "TemplateId": int(template_id),
            "TemplateModel": variables,
        }

        try:
            response = httpx.post(
                "https://api.postmarkapp.com/email/withTemplate",
                json=payload,
                headers={
                    "X-Postmark-Server-Token": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_template_email",
                    message_id=str(data.get("MessageID")),
                )
            else:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="send_template_email",
                    error_message=response.text[:200],
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_template_email",
                error_message=str(e)[:200],
            )
