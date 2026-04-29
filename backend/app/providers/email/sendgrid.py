"""
SendGrid Email Provider

Implementation of the EmailProvider interface for SendGrid.
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


class SendGridEmailProvider(EmailProvider):
    """SendGrid email provider.

    Configuration:
        - api_key: SendGrid API key (required)
        - from_email: Default sender email (optional)
    """

    provider_name = "sendgrid"
    display_name = "SendGrid"
    description = "Email delivery and marketing platform"
    website = "https://sendgrid.com"

    required_config_fields = ["api_key"]
    optional_config_fields = ["from_email"]

    capabilities = [
        ProviderCapability.SEND_EMAIL,
        ProviderCapability.SEND_TEMPLATE_EMAIL,
        ProviderCapability.WEBHOOK_EVENTS,
        ProviderCapability.TRACK_OPENS,
        ProviderCapability.TRACK_CLICKS,
        ProviderCapability.BATCH_OPERATIONS,
    ]

    API_URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.from_email = config.get("from_email", "noreply@parwa.ai")
        self._status = ProviderStatus.ACTIVE

    def test_connection(self) -> ProviderResult:
        """Test SendGrid API connection."""
        try:
            response = httpx.get(
                "https://api.sendgrid.com/v3/user/profile",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
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
            "emails_per_second": 100,
            "emails_per_day": 100,  # Free plan
            "note": "Limits vary by plan. Check your SendGrid dashboard.",
        }

    def send_email(self, message: EmailMessage) -> ProviderResult:
        """Send an email via SendGrid API."""
        payload = {
            "personalizations": [
                {
                    "to": [{"email": message.to}],
                    "subject": message.subject,
                }
            ],
            "from": {
                "email": message.from_email or self.from_email,
                "name": message.from_name or "PARWA",
            },
            "content": [
                {
                    "type": "text/html",
                    "value": message.html_content,
                }
            ],
        }

        if message.text_content:
            payload["content"].insert(
                0,
                {
                    "type": "text/plain",
                    "value": message.text_content,
                },
            )

        if message.cc:
            payload["personalizations"][0]["cc"] = [{"email": e} for e in message.cc]

        if message.bcc:
            payload["personalizations"][0]["bcc"] = [{"email": e} for e in message.bcc]

        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code == 202:
                message_id = response.headers.get("X-Message-Id", "")
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_email",
                    message_id=message_id,
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
        template_id: str,
        to: str,
        variables: Dict[str, Any],
    ) -> ProviderResult:
        """Send an email using a SendGrid template."""
        payload = {
            "personalizations": [
                {
                    "to": [{"email": to}],
                    "dynamic_template_data": variables,
                }
            ],
            "from": {"email": self.from_email},
            "template_id": template_id,
        }

        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if response.status_code == 202:
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_template_email",
                    message_id=response.headers.get("X-Message-Id"),
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
