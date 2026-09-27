"""
PARWA AI — AWS SES Email Provider

Since SES uses AWS Signature V4 authentication (not a simple API key header),
this adapter uses ``boto3`` when available and falls back to a simulated
connection test otherwise.

API reference: https://docs.aws.amazon.com/ses/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import ConnectionStatus, EmailProvider, ProviderResult

logger = logging.getLogger(__name__)


class SESEmailProvider(EmailProvider):
    """AWS SES email provider adapter."""

    provider_name = "AWS SES"
    provider_type = "aws_ses"

    # ── Required fields ──────────────────────────────────────────────────

    def get_required_fields(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "access_key_id",
                "type": "password",
                "label": "AWS Access Key ID",
                "required": True,
                "help_text": "Starts with 'AKIA' — IAM user with SES permissions",
            },
            {
                "name": "secret_access_key",
                "type": "password",
                "label": "AWS Secret Access Key",
                "required": True,
                "help_text": "Corresponding secret for the access key",
            },
            {
                "name": "region",
                "type": "select",
                "label": "AWS Region",
                "required": True,
                "help_text": "SES region (e.g. us-east-1, eu-west-1)",
                "options": [
                    {"value": "us-east-1", "label": "US East (N. Virginia)"},
                    {"value": "us-west-2", "label": "US West (Oregon)"},
                    {"value": "eu-west-1", "label": "EU (Ireland)"},
                    {"value": "eu-central-1", "label": "EU (Frankfurt)"},
                    {"value": "ap-south-1", "label": "Asia Pacific (Mumbai)"},
                    {"value": "ap-southeast-1", "label": "Asia Pacific (Singapore)"},
                    {"value": "ap-southeast-2", "label": "Asia Pacific (Sydney)"},
                    {"value": "ap-northeast-1", "label": "Asia Pacific (Tokyo)"},
                ],
            },
            {
                "name": "from_email",
                "type": "text",
                "label": "Default From Email",
                "required": False,
                "help_text": "Verified sender e-mail in SES",
            },
        ]

    def get_capabilities(self) -> List[str]:
        return ["send_email", "templates"]

    # ── Credential validation (no network) ───────────────────────────────

    async def validate_credentials(self, credentials: dict) -> ProviderResult:
        access_key_id = credentials.get("access_key_id", "")
        secret_access_key = credentials.get("secret_access_key", "")
        region = credentials.get("region", "")

        if not access_key_id:
            return ProviderResult.fail("AWS Access Key ID is required")
        if not access_key_id.startswith("AKIA"):
            return ProviderResult.fail("AWS Access Key IDs must start with 'AKIA'")
        if len(access_key_id) != 20:
            return ProviderResult.fail("AWS Access Key ID must be 20 characters")
        if not secret_access_key:
            return ProviderResult.fail("AWS Secret Access Key is required")
        if len(secret_access_key) < 20:
            return ProviderResult.fail("Secret Access Key appears too short")
        if not region:
            return ProviderResult.fail("AWS Region is required")

        return ProviderResult.ok("Credentials look valid")

    # ── Test connection ──────────────────────────────────────────────────

    async def test_connection(self, credentials: dict) -> ProviderResult:
        self.status = ConnectionStatus.CONNECTING

        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
        except ImportError:
            # boto3 not installed — simulate the check
            logger.warning("boto3 not installed; performing simulated SES connection test")
            return await self._simulated_test(credentials)

        access_key_id = credentials.get("access_key_id", "")
        secret_access_key = credentials.get("secret_access_key", "")
        region = credentials.get("region", "us-east-1")

        try:
            client = boto3.client(
                "ses",
                region_name=region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
            # GetSendQuota is a lightweight read-only call
            response = client.get_send_quota()
            self.status = ConnectionStatus.CONNECTED
            return ProviderResult.ok(
                f"Connected to AWS SES in {region}",
                data={
                    "max_24_hour_send": response.get("Max24HourSend"),
                    "max_send_rate": response.get("MaxSendRate"),
                    "sent_last_24_hours": response.get("SentLast24Hours"),
                    "region": region,
                },
            )

        except NoCredentialsError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail("Invalid AWS credentials")
        except EndpointConnectionError:
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail(f"Cannot reach SES endpoint in {region}")
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            msg = exc.response["Error"]["Message"]
            self.status = ConnectionStatus.ERROR
            return ProviderResult.fail(f"AWS error ({code}): {msg}")
        except Exception as exc:
            self.status = ConnectionStatus.ERROR
            logger.exception("Unexpected error testing SES connection")
            return ProviderResult.fail(f"Unexpected error: {exc}")

    async def _simulated_test(self, credentials: dict) -> ProviderResult:
        """Fallback when boto3 is not available in the environment."""
        access_key_id = credentials.get("access_key_id", "")
        if access_key_id.startswith("AKIA") and len(access_key_id) == 20:
            self.status = ConnectionStatus.CONNECTED
            return ProviderResult.ok(
                "Simulated SES connection OK (boto3 not installed)",
                data={"simulated": True},
            )
        self.status = ConnectionStatus.ERROR
        return ProviderResult.fail("Simulated test failed — check Access Key ID format")

    # ── Send email ───────────────────────────────────────────────────────

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> ProviderResult:
        access_key_id = self._credentials.get("access_key_id", "")
        secret_access_key = self._credentials.get("secret_access_key", "")
        region = self._credentials.get("region", "us-east-1")
        from_email = kwargs.get("from_email") or self._credentials.get("from_email", "")

        if not from_email:
            return ProviderResult.fail("From email is required")

        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            return ProviderResult.fail(
                "boto3 is required for sending emails via AWS SES but is not installed"
            )

        try:
            client = boto3.client(
                "ses",
                region_name=region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )

            # Determine content type
            content_type = kwargs.get("content_type", "Html")
            body_key = "Html" if content_type == "Html" else "Text"

            send_args: Dict[str, Any] = {
                "Source": from_email,
                "Destination": {"ToAddresses": [to]},
                "Message": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {body_key: {"Data": body, "Charset": "UTF-8"}},
                },
            }

            # Optional CC / BCC / Reply-To
            if kwargs.get("cc"):
                send_args["Destination"]["CcAddresses"] = list(kwargs["cc"])
            if kwargs.get("bcc"):
                send_args["Destination"]["BccAddresses"] = list(kwargs["bcc"])
            if kwargs.get("reply_to"):
                send_args["ReplyToAddresses"] = list(kwargs["reply_to"])

            # Template mode
            if kwargs.get("template_id"):
                send_args = {
                    "Source": from_email,
                    "Destination": {"ToAddresses": [to]},
                    "Template": kwargs["template_id"],
                    "TemplateData": kwargs.get("template_data", "{}"),
                }

            response = client.send_email(**send_args)
            message_id = response.get("MessageId", "")

            return ProviderResult.ok(
                "Email sent via AWS SES",
                data={"message_id": message_id, "provider": "aws_ses"},
            )

        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            msg = exc.response["Error"]["Message"]
            return ProviderResult.fail(f"AWS SES error ({code}): {msg}")
        except Exception as exc:
            logger.exception("Error sending email via AWS SES")
            return ProviderResult.fail(f"Unexpected error: {exc}")
