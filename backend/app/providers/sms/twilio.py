"""
Twilio SMS Provider

Implementation of the SMSProvider interface for Twilio.
"""

from typing import Any, Dict

import httpx
from app.providers.base import (
    ProviderCapability,
    ProviderResult,
    ProviderStatus,
    SMSMessage,
    SMSProvider,
)


class TwilioSMSProvider(SMSProvider):
    """Twilio SMS provider.

    Configuration:
        - account_sid: Twilio Account SID (required)
        - auth_token: Twilio Auth Token (required)
        - phone_number: Twilio phone number (optional, can override per message)
    """

    provider_name = "twilio"
    display_name = "Twilio"
    description = "Cloud communications platform for SMS and Voice"
    website = "https://www.twilio.com"

    required_config_fields = ["account_sid", "auth_token"]
    optional_config_fields = ["phone_number"]

    capabilities = [
        ProviderCapability.SEND_SMS,
        ProviderCapability.RECEIVE_SMS,
        ProviderCapability.SCHEDULE_SMS,
        ProviderCapability.SHORTCODE,
        ProviderCapability.WEBHOOKS,
        ProviderCapability.ANALYTICS,
    ]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.account_sid = config["account_sid"]
        self.auth_token = config["auth_token"]
        self.phone_number = config.get("phone_number", "")
        self._status = ProviderStatus.ACTIVE

    def _get_auth(self) -> tuple:
        return (self.account_sid, self.auth_token)

    def _get_base_url(self) -> str:
        return f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"

    def test_connection(self) -> ProviderResult:
        try:
            response = httpx.get(
                f"{self._get_base_url()}.json",
                auth=self._get_auth(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={"friendly_name": data.get("friendly_name", "unknown")},
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
            "messages_per_second": 10,
            "messages_per_day": "varies by phone number type",
            "note": "Check Twilio console for your account limits.",
        }

    def send_sms(self, message: SMSMessage) -> ProviderResult:
        from_number = message.from_number or self.phone_number
        if not from_number:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_sms",
                error_message="No from number specified",
            )

        payload = {
            "From": from_number,
            "To": message.to,
            "Body": message.body,
        }

        if message.media_urls:
            payload["MediaUrl"] = message.media_urls[:10]  # Max 10 media URLs

        if message.status_callback:
            payload["StatusCallback"] = message.status_callback

        if message.validity_period:
            payload["ValidityPeriod"] = message.validity_period

        try:
            response = httpx.post(
                f"{self._get_base_url()}/Messages.json",
                data=payload,
                auth=self._get_auth(),
                timeout=30.0,
            )

            if response.status_code == 201:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_sms",
                    message_id=data.get("sid"),
                    metadata={
                        "status": data.get("status"),
                        "to": data.get("to"),
                        "from": data.get("from"),
                    },
                )
            else:
                data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="send_sms",
                    error_code=data.get("code", str(response.status_code)),
                    error_message=data.get("message", response.text[:200]),
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_sms",
                error_message=str(e)[:200],
            )

    def get_message_status(self, message_id: str) -> Dict[str, Any]:
        try:
            response = httpx.get(
                f"{self._get_base_url()}/Messages/{message_id}.json",
                auth=self._get_auth(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "message_id": data.get("sid"),
                    "status": data.get("status"),
                    "error_code": data.get("error_code"),
                    "error_message": data.get("error_message"),
                    "date_sent": data.get("date_sent"),
                    "date_updated": data.get("date_updated"),
                    "price": data.get("price"),
                    "price_unit": data.get("price_unit"),
                }
            else:
                return {"error": response.text[:200]}
        except Exception as e:
            return {"error": str(e)[:200]}

    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Twilio SMS webhook data."""
        return {
            "message_id": data.get("MessageSid"),
            "account_sid": data.get("AccountSid"),
            "from": data.get("From"),
            "to": data.get("To"),
            "body": data.get("Body"),
            "num_media": data.get("NumMedia", "0"),
            # Would need to extract from MediaUrl0, MediaUrl1, etc.
            "media_urls": [],
            "status": data.get("SmsStatus"),
            "timestamp": data.get("DateSent"),
        }
