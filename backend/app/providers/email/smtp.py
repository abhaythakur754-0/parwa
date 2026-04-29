"""
SMTP Email Provider

Implementation of the EmailProvider interface for any SMTP server.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, Dict

from app.providers.base import (
    EmailProvider,
    EmailMessage,
    ProviderResult,
    ProviderStatus,
    ProviderCapability,
)


class SMTPEmailProvider(EmailProvider):
    """Custom SMTP email provider.

    Works with any SMTP server.

    Configuration:
        - host: SMTP server hostname (required)
        - port: SMTP port (required, typically 587 or 465)
        - username: SMTP username (required)
        - password: SMTP password (required)
        - use_tls: Use TLS (optional, default True)
        - from_email: Default sender email (optional)
    """

    provider_name = "smtp"
    display_name = "Custom SMTP"
    description = "Any SMTP server"
    website = ""

    required_config_fields = ["host", "port", "username", "password"]
    optional_config_fields = ["use_tls", "from_email"]

    capabilities = [
        ProviderCapability.SEND_EMAIL,
    ]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config["host"]
        self.port = int(config["port"])
        self.username = config["username"]
        self.password = config["password"]
        self.use_tls = config.get("use_tls", True)
        self.from_email = config.get("from_email", config["username"])
        self._status = ProviderStatus.ACTIVE

    def test_connection(self) -> ProviderResult:
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)

            return ProviderResult(
                success=True,
                provider_name=self.provider_name,
                operation="test_connection",
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
            "note": "Rate limits depend on your SMTP server configuration.",
        }

    def send_email(self, message: EmailMessage) -> ProviderResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = message.from_email or self.from_email
            msg["To"] = message.to
            msg["Subject"] = message.subject

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            # Add text content
            if message.text_content:
                msg.attach(MIMEText(message.text_content, "plain"))

            # Add HTML content
            msg.attach(MIMEText(message.html_content, "html"))

            # Add attachments
            for att in message.attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(att.get("content", ""))
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={att.get('name', 'attachment')}",
                )
                msg.attach(part)

            # Send
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(
                    message.from_email or self.from_email,
                    [message.to] + message.cc + message.bcc,
                    msg.as_string(),
                )

            return ProviderResult(
                success=True,
                provider_name=self.provider_name,
                operation="send_email",
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_email",
                error_message=str(e)[:200],
            )

    def send_template_email(self,
                            template_id: str,
                            to: str,
                            variables: Dict[str,
                                            Any]) -> ProviderResult:
        return ProviderResult(
            success=False,
            provider_name=self.provider_name,
            operation="send_template_email",
            error_message="Template emails not supported for SMTP provider",
        )
