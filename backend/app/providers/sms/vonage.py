"""
Vonage SMS Provider

Implementation of the SMSProvider interface for Vonage (formerly Nexmo).
Uses the Vonage REST API: https://rest.nexmo.com
"""

from typing import Any, Dict, Optional

import httpx

from app.providers.base import (
    SMSProvider,
    SMSMessage,
    ProviderResult,
    ProviderStatus,
    ProviderCapability,
)


class VonageSMSProvider(SMSProvider):
    """Vonage SMS provider.

    Configuration:
        - api_key: Vonage API key (required)
        - api_secret: Vonage API secret (required)
        - from_number: Vonage phone number or sender name (optional, can override per message)
    """

    provider_name = "vonage"
    display_name = "Vonage"
    description = "Vonage Communications APIs for SMS and Voice"
    website = "https://www.vonage.com"

    required_config_fields = ["api_key", "api_secret"]
    optional_config_fields = ["from_number"]

    capabilities = [
        ProviderCapability.SEND_SMS,
        ProviderCapability.RECEIVE_SMS,
        ProviderCapability.WEBHOOKS,
        ProviderCapability.ANALYTICS,
    ]

    BASE_URL = "https://rest.nexmo.com"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.api_secret = config["api_secret"]
        self.from_number = config.get("from_number", "")
        self._status = ProviderStatus.ACTIVE

    def _get_auth_params(self) -> Dict[str, str]:
        return {"api_key": self.api_key, "api_secret": self.api_secret}

    def test_connection(self) -> ProviderResult:
        """Test the Vonage API connection by checking account balance."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/account/get-balance",
                params=self._get_auth_params(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={
                        "value": data.get("value"),
                        "auto_reload": data.get("autoReload", False),
                    },
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
            "messages_per_second": 30,
            "messages_per_day": "varies by account tier",
            "max_concatenated_parts": 6,
            "note": "Check Vonage dashboard for your account limits.",
        }

    def send_sms(self, message: SMSMessage) -> ProviderResult:
        """Send an SMS via Vonage's SMS API (POST /sms/json)."""
        from_number = message.from_number or self.from_number
        if not from_number:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_sms",
                error_message="No from number specified",
            )

        payload = {
            "from": from_number,
            "to": message.to,
            "text": message.body,
            **self._get_auth_params(),
        }

        if message.status_callback:
            payload["callback"] = message.status_callback

        if message.validity_period:
            payload["ttl"] = message.validity_period // 1000  # Vonage uses milliseconds

        try:
            response = httpx.post(
                f"{self.BASE_URL}/sms/json",
                json=payload,
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])
                if messages and messages[0].get("status") == "0":
                    return ProviderResult(
                        success=True,
                        provider_name=self.provider_name,
                        operation="send_sms",
                        message_id=messages[0].get("message-id"),
                        metadata={
                            "status": messages[0].get("status"),
                            "remaining_balance": data.get("message-count"),
                            "to": messages[0].get("to"),
                            "network": messages[0].get("network"),
                        },
                    )
                else:
                    msg = messages[0] if messages else {}
                    return ProviderResult(
                        success=False,
                        provider_name=self.provider_name,
                        operation="send_sms",
                        error_code=msg.get("status", "unknown"),
                        error_message=msg.get("error-text", "Unknown Vonage error"),
                    )
            else:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="send_sms",
                    error_code=str(response.status_code),
                    error_message=response.text[:200],
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_sms",
                error_message=str(e)[:200],
            )

    def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Check delivery status of a Vonage message."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/search/message",
                params={
                    "id": message_id,
                    **self._get_auth_params(),
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])
                if messages:
                    msg = messages[0]
                    return {
                        "message_id": msg.get("message-id"),
                        "status": msg.get("status"),
                        "error_code": msg.get("error-code"),
                        "network": msg.get("network"),
                        "price": msg.get("price"),
                        "remaining_balance": msg.get("remaining-balance"),
                        "date_sent": msg.get("date-received"),
                    }
                return {"error": "Message not found"}
            else:
                return {"error": response.text[:200]}
        except Exception as e:
            return {"error": str(e)[:200]}

    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Vonage inbound SMS webhook data."""
        return {
            "message_id": data.get("messageId"),
            "from": data.get("msisdn"),
            "to": data.get("to"),
            "body": data.get("text"),
            "keyword": data.get("keyword"),
            "status": data.get("status"),
            "timestamp": data.get("message-timestamp"),
        }
