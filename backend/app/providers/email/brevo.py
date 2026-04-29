"""
Brevo (Sendinblue) Email Provider

Implementation of the EmailProvider interface for Brevo.
Brevo is a popular transactional email service.
"""

from typing import Any, Dict

import httpx

from app.providers.base import (
    EmailProvider,
    EmailMessage,
    ProviderResult,
    ProviderStatus,
    ProviderCapability,
)


class BrevoEmailProvider(EmailProvider):
    """Brevo (formerly Sendinblue) email provider.

    Configuration:
        - api_key: Brevo API key (required)
        - from_email: Default sender email (optional)
        - from_name: Default sender name (optional)
    """

    provider_name = "brevo"
    display_name = "Brevo"
    description = "Transactional and marketing email service"
    website = "https://www.brevo.com"

    required_config_fields = ["api_key"]
    optional_config_fields = ["from_email", "from_name"]

    capabilities = [
        ProviderCapability.SEND_EMAIL,
        ProviderCapability.SEND_TEMPLATE_EMAIL,
        ProviderCapability.WEBHOOK_EVENTS,
        ProviderCapability.TRACK_OPENS,
        ProviderCapability.TRACK_CLICKS,
    ]

    API_URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.from_email = config.get("from_email", "noreply@parwa.ai")
        self.from_name = config.get("from_name", "PARWA")
        self._status = ProviderStatus.ACTIVE

    def test_connection(self) -> ProviderResult:
        """Test Brevo API connection."""
        try:
            # Test by getting account info
            response = httpx.get(
                "https://api.brevo.com/v3/account",
                headers={"api-key": self.api_key},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={"email": data.get("email", "unknown")},
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
        """Get Brevo rate limits."""
        # Brevo has different limits based on plan
        # These are typical limits
        return {
            "emails_per_second": 50,
            "emails_per_day": 300,  # Free plan
            "emails_per_month": 300,  # Free plan
            "note": "Limits vary by plan. Check your Brevo dashboard.",
        }

    def send_email(self, message: EmailMessage) -> ProviderResult:
        """Send an email via Brevo API."""
        # Build payload
        payload = {
            "sender": {
                "name": message.from_name or self.from_name,
                "email": message.from_email or self.from_email,
            },
            "to": [{"email": message.to}],
            "subject": message.subject,
            "htmlContent": message.html_content,
        }

        if message.text_content:
            payload["textContent"] = message.text_content

        if message.reply_to:
            payload["replyTo"] = {"email": message.reply_to}

        if message.cc:
            payload["cc"] = [{"email": email} for email in message.cc]

        if message.bcc:
            payload["bcc"] = [{"email": email} for email in message.bcc]

        if message.headers:
            payload["headers"] = message.headers

        if message.attachments:
            payload["attachment"] = [
                {"name": att.get("name", "attachment"), "content": att.get("content", "")}
                for att in message.attachments
            ]

        if message.tags:
            payload["tags"] = message.tags

        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={
                    "api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_email",
                    message_id=data.get("messageId"),
                    metadata={"to": message.to},
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
        self,
        template_id: int,
        to: str,
        variables: Dict[str, Any],
    ) -> ProviderResult:
        """Send an email using a Brevo template."""
        payload = {
            "templateId": int(template_id),
            "to": [{"email": to}],
            "params": variables,
        }

        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={
                    "api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_template_email",
                    message_id=data.get("messageId"),
                )
            else:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="send_template_email",
                    error_code=str(response.status_code),
                    error_message=response.text[:200],
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_template_email",
                error_message=str(e)[:200],
            )
