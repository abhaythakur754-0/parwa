"""
AWS SES Email Provider

Implementation of the EmailProvider interface for Amazon SES.
"""

from typing import Any, Dict

from app.providers.base import (
    EmailMessage,
    EmailProvider,
    ProviderCapability,
    ProviderResult,
    ProviderStatus,
)


class SESEmailProvider(EmailProvider):
    """AWS SES email provider.

    Configuration:
        - access_key: AWS Access Key ID (required)
        - secret_key: AWS Secret Access Key (required)
        - region: AWS region (optional, default: us-east-1)
    """

    provider_name = "ses"
    display_name = "AWS SES"
    description = "Amazon Simple Email Service"
    website = "https://aws.amazon.com/ses/"

    required_config_fields = ["access_key", "secret_key"]
    optional_config_fields = ["region", "from_email"]

    capabilities = [
        ProviderCapability.SEND_EMAIL,
        ProviderCapability.SEND_TEMPLATE_EMAIL,
        ProviderCapability.WEBHOOK_EVENTS,
    ]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.access_key = config["access_key"]
        self.secret_key = config["secret_key"]
        self.region = config.get("region", "us-east-1")
        self.from_email = config.get("from_email", "noreply@parwa.ai")
        self._status = ProviderStatus.ACTIVE

    def test_connection(self) -> ProviderResult:
        try:
            import boto3

            client = boto3.client(
                "ses",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )
            client.get_send_quota()
            return ProviderResult(
                success=True,
                provider_name=self.provider_name,
                operation="test_connection",
            )
        except ImportError:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message="boto3 package not installed. Run: pip install boto3",
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
            "emails_per_second": 14,  # Default sandbox limit
            "emails_per_day": 200,  # Default sandbox limit
            "note": "Production limits are higher. Request increase via AWS console.",
        }

    def send_email(self, message: EmailMessage) -> ProviderResult:
        try:
            import boto3

            client = boto3.client(
                "ses",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )

            response = client.send_email(
                Source=message.from_email or self.from_email,
                Destination={"ToAddresses": [message.to]},
                Message={
                    "Subject": {"Data": message.subject},
                    "Body": {
                        "Html": {"Data": message.html_content},
                        **(
                            {"Text": {"Data": message.text_content}}
                            if message.text_content
                            else {}
                        ),
                    },
                },
            )

            return ProviderResult(
                success=True,
                provider_name=self.provider_name,
                operation="send_email",
                message_id=response.get("MessageId"),
            )
        except ImportError:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_email",
                error_message="boto3 package not installed",
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
        try:
            import json

            import boto3

            client = boto3.client(
                "ses",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )

            response = client.send_templated_email(
                Source=self.from_email,
                Destination={"ToAddresses": [to]},
                Template=template_id,
                TemplateData=json.dumps(variables),
            )

            return ProviderResult(
                success=True,
                provider_name=self.provider_name,
                operation="send_template_email",
                message_id=response.get("MessageId"),
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_template_email",
                error_message=str(e)[:200],
            )
