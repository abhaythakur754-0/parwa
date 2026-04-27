"""
Plivo SMS Provider

Implementation of the SMSProvider interface for Plivo.
Uses the Plivo REST API: https://api.plivo.com/v1/Account/{auth_id}
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


class PlivoSMSProvider(SMSProvider):
    """Plivo SMS provider.

    Configuration:
        - auth_id: Plivo Auth ID (required)
        - auth_token: Plivo Auth Token (required)
        - from_number: Plivo phone number (optional, can override per message)
    """

    provider_name = "plivo"
    display_name = "Plivo"
    description = "Cloud communications platform for SMS and Voice"
    website = "https://www.plivo.com"

    required_config_fields = ["auth_id", "auth_token"]
    optional_config_fields = ["from_number"]

    capabilities = [
        ProviderCapability.SEND_SMS,
        ProviderCapability.RECEIVE_SMS,
        ProviderCapability.WEBHOOKS,
        ProviderCapability.ANALYTICS,
    ]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.auth_id = config["auth_id"]
        self.auth_token = config["auth_token"]
        self.from_number = config.get("from_number", "")
        self._status = ProviderStatus.ACTIVE

    def _get_base_url(self) -> str:
        return f"https://api.plivo.com/v1/Account/{self.auth_id}"

    def _get_auth(self) -> tuple:
        return (self.auth_id, self.auth_token)

    def test_connection(self) -> ProviderResult:
        """Test the Plivo API connection by fetching account details."""
        try:
            response = httpx.get(
                f"{self._get_base_url()}/",
                auth=self._get_auth(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={
                        "account_resource_uri": data.get("account_resource_uri"),
                        "cash_credits": data.get("cash_credits"),
                        "auto_recharge": data.get("auto_recharge"),
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
            "messages_per_second": 25,
            "messages_per_day": "varies by account tier",
            "max_concatenated_parts": 6,
            "note": "Check Plivo dashboard for your account limits.",
        }

    def send_sms(self, message: SMSMessage) -> ProviderResult:
        """Send an SMS via Plivo's Message API (POST /Account/{auth_id}/Message/)."""
        from_number = message.from_number or self.from_number
        if not from_number:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_sms",
                error_message="No from number specified",
            )

        payload = {
            "src": from_number,
            "dst": message.to,
            "text": message.body,
        }

        if message.status_callback:
            payload["url"] = message.status_callback
            payload["method"] = "POST"

        try:
            response = httpx.post(
                f"{self._get_base_url()}/Message/",
                json=payload,
                auth=self._get_auth(),
                timeout=30.0,
            )

            if response.status_code in (200, 201, 202):
                data = response.json()
                message_uuids = data.get("message_uuid", [])
                if message_uuids:
                    return ProviderResult(
                        success=True,
                        provider_name=self.provider_name,
                        operation="send_sms",
                        message_id=message_uuids[0] if isinstance(message_uuids, list) else str(message_uuids),
                        metadata={
                            "api_id": data.get("api_id"),
                            "message_uuids": message_uuids,
                            "to": data.get("to"),
                        },
                    )
                else:
                    return ProviderResult(
                        success=False,
                        provider_name=self.provider_name,
                        operation="send_sms",
                        error_message="No message UUID returned by Plivo",
                    )
            else:
                data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="send_sms",
                    error_code=data.get("error", str(response.status_code)),
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
        """Get delivery status of a Plivo message."""
        try:
            response = httpx.get(
                f"{self._get_base_url()}/Message/{message_id}/",
                auth=self._get_auth(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "message_id": data.get("message_uuid"),
                    "status": data.get("message_state"),
                    "from": data.get("from_number"),
                    "to": data.get("to_number"),
                    "total_amount": data.get("total_amount"),
                    "total_rate": data.get("total_rate"),
                    "units": data.get("units"),
                }
            else:
                return {"error": response.text[:200]}
        except Exception as e:
            return {"error": str(e)[:200]}

    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Plivo inbound SMS webhook data."""
        return {
            "message_id": data.get("MessageUUID"),
            "from": data.get("From"),
            "to": data.get("To"),
            "body": data.get("Text"),
            "status": data.get("MessageState"),
        }
