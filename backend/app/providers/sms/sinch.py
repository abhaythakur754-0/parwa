"""
Sinch SMS Provider

Implementation of the SMSProvider interface for Sinch.
Uses the Sinch SMS API: https://sms.api.sinch.com
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


class SinchSMSProvider(SMSProvider):
    """Sinch SMS provider.

    Configuration:
        - service_plan_id: Sinch service plan ID (required)
        - api_token: Sinch API token (required)
        - from_number: Sinch phone number (optional, can override per message)
    """

    provider_name = "sinch"
    display_name = "Sinch"
    description = "Sinch Communications APIs for SMS and Voice"
    website = "https://www.sinch.com"

    required_config_fields = ["service_plan_id", "api_token"]
    optional_config_fields = ["from_number"]

    capabilities = [
        ProviderCapability.SEND_SMS,
        ProviderCapability.RECEIVE_SMS,
        ProviderCapability.WEBHOOKS,
        ProviderCapability.ANALYTICS,
    ]

    BASE_URL = "https://sms.api.sinch.com"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.service_plan_id = config["service_plan_id"]
        self.api_token = config["api_token"]
        self.from_number = config.get("from_number", "")
        self._status = ProviderStatus.ACTIVE

    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _get_base_path(self) -> str:
        return f"/xms/v1/{self.service_plan_id}"

    def test_connection(self) -> ProviderResult:
        """Test the Sinch API connection by checking groups (a lightweight endpoint)."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}{self._get_base_path()}/batches",
                headers=self._get_auth_headers(),
                timeout=10.0,
            )

            # 200 or 404 (no batches yet) both indicate a valid connection
            if response.status_code in (200, 404):
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={"service_plan_id": self.service_plan_id},
                )
            elif response.status_code == 401:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    error_code="401",
                    error_message="Invalid API token or service plan ID",
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
            "messages_per_second": 50,
            "messages_per_day": "varies by account tier",
            "max_concatenated_parts": 6,
            "note": "Check Sinch dashboard for your account limits.",
        }

    def send_sms(self, message: SMSMessage) -> ProviderResult:
        """Send an SMS via Sinch's SMS API (POST /xms/v1/{plan}/batches)."""
        from_number = message.from_number or self.from_number
        if not from_number:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_sms",
                error_message="No from number specified",
            )

        payload: Dict[str, Any] = {
            "from": from_number,
            "to": [message.to],
            "body": message.body,
        }

        if message.status_callback:
            payload["callback_url"] = message.status_callback

        try:
            response = httpx.post(
                f"{self.BASE_URL}{self._get_base_path()}/batches",
                json=payload,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )

            if response.status_code in (200, 201, 202):
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_sms",
                    message_id=data.get("id"),
                    metadata={
                        "batch_id": data.get("id"),
                        "to": data.get("to"),
                        "from": data.get("from"),
                        "body": data.get("body"),
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
        """Get delivery status of a Sinch batch/message."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}{self._get_base_path()}/batches/{message_id}",
                headers=self._get_auth_headers(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "message_id": data.get("id"),
                    "status": data.get("status"),
                    "from": data.get("from"),
                    "to": data.get("to"),
                    "body": data.get("body"),
                    "created_at": data.get("created_at"),
                    "modified_at": data.get("modified_at"),
                }
            else:
                return {"error": response.text[:200]}
        except Exception as e:
            return {"error": str(e)[:200]}

    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Sinch inbound SMS webhook data."""
        return {
            "message_id": data.get("id"),
            "from": data.get("from"),
            "to": data.get("to"),
            "body": data.get("body"),
            "status": data.get("status"),
        }
