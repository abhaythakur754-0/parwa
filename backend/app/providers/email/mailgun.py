"""
Mailgun Email Provider

Implementation of the EmailProvider interface for Mailgun.
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


class MailgunEmailProvider(EmailProvider):
    """Mailgun email provider.

    Configuration:
        - api_key: Mailgun API key (required)
        - domain: Mailgun domain (required)
    """

    provider_name = "mailgun"
    display_name = "Mailgun"
    description = "Email API service for developers"
    website = "https://www.mailgun.com"

    required_config_fields = ["api_key", "domain"]
    optional_config_fields = ["from_email"]

    capabilities = [
        ProviderCapability.SEND_EMAIL,
        ProviderCapability.WEBHOOK_EVENTS,
        ProviderCapability.TRACK_OPENS,
        ProviderCapability.TRACK_CLICKS,
    ]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.domain = config["domain"]
        self.from_email = config.get("from_email", f"noreply@{self.domain}")
        self._status = ProviderStatus.ACTIVE

    def test_connection(self) -> ProviderResult:
        try:
            import base64

            auth = base64.b64encode(f"api:{self.api_key}".encode()).decode()

            response = httpx.get(
                f"https://api.mailgun.net/v3/{self.domain}",
                headers={"Authorization": f"Basic {auth}"},
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
            "emails_per_second": 300,
            "note": "Limits vary by plan.",
        }

    def send_email(self, message: EmailMessage) -> ProviderResult:
        import base64

        auth = base64.b64encode(f"api:{self.api_key}".encode()).decode()

        data = {
            "from": f"{
                message.from_name or 'PARWA'} <{
                message.from_email or self.from_email}>",
            "to": message.to,
            "subject": message.subject,
            "html": message.html_content,
        }

        if message.text_content:
            data["text"] = message.text_content

        try:
            response = httpx.post(
                f"https://api.mailgun.net/v3/{self.domain}/messages",
                data=data,
                headers={"Authorization": f"Basic {auth}"},
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_email",
                    message_id=result.get("id"),
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
        # Mailgun uses different template approach
        return ProviderResult(
            success=False,
            provider_name=self.provider_name,
            operation="send_template_email",
            error_message="Template emails not supported for Mailgun provider",
        )
