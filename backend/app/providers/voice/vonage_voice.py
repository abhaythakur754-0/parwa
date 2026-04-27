"""
Vonage Voice Provider

Implementation of the VoiceProvider interface for Vonage.
Uses the Vonage Voice API: https://api.nexmo.com/v1/calls
"""

from typing import Any, Dict

import httpx

from app.providers.base import (
    VoiceProvider,
    VoiceCall,
    ProviderResult,
    ProviderStatus,
    ProviderCapability,
)


class VonageVoiceProvider(VoiceProvider):
    """Vonage Voice provider.

    Configuration:
        - api_key: Vonage API key (required)
        - api_secret: Vonage API secret (required)
        - application_id: Vonage Voice Application ID (optional, for advanced NCCO flows)
    """

    provider_name = "vonage_voice"
    display_name = "Vonage Voice"
    description = "Vonage Voice API for outbound and inbound calls"
    website = "https://www.vonage.com/communications-apis/voice"

    required_config_fields = ["api_key", "api_secret"]
    optional_config_fields = ["application_id"]

    capabilities = [
        ProviderCapability.MAKE_CALL,
        ProviderCapability.RECEIVE_CALL,
        ProviderCapability.VOICEMAIL,
        ProviderCapability.TRANSCRIPTION,
        ProviderCapability.TEXT_TO_SPEECH,
        ProviderCapability.WEBHOOKS,
    ]

    BASE_URL = "https://api.nexmo.com"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.api_secret = config["api_secret"]
        self.application_id = config.get("application_id", "")
        self._status = ProviderStatus.ACTIVE

    def _get_auth_params(self) -> Dict[str, str]:
        return {"api_key": self.api_key, "api_secret": self.api_secret}

    def test_connection(self) -> ProviderResult:
        """Test the Vonage Voice API connection."""
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
            "concurrent_calls": "varies by account tier",
            "max_call_duration_seconds": 14400,
            "note": "Check Vonage dashboard for your account limits.",
        }

    def make_call(self, call: VoiceCall) -> ProviderResult:
        """Make an outbound voice call via Vonage's Voice API (POST /v1/calls)."""
        # Vonage Voice API requires an NCCO or an answer_url to instruct what happens on the call
        if not call.url:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="make_call",
                error_message="Vonage Voice requires a 'url' (answer_url) to define call behavior via NCCO",
            )

        payload: Dict[str, Any] = {
            "to": [{"type": "phone", "number": call.to}],
            "from": {"type": "phone", "number": call.from_number},
            "answer_url": [call.url],
        }

        if call.status_callback:
            payload["event_url"] = [call.status_callback]

        if call.machine_detection:
            payload["machine_detection"] = call.machine_detection

        try:
            response = httpx.post(
                f"{self.BASE_URL}/v1/calls",
                json=payload,
                params=self._get_auth_params(),
                timeout=30.0,
            )

            if response.status_code in (200, 201, 202):
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="make_call",
                    message_id=data.get("uuid"),
                    metadata={
                        "conversation_uuid": data.get("conversation_uuid"),
                        "status": data.get("status"),
                        "direction": data.get("direction"),
                    },
                )
            else:
                data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="make_call",
                    error_code=data.get("error_code", str(response.status_code)),
                    error_message=data.get("error_message", response.text[:200]),
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="make_call",
                error_message=str(e)[:200],
            )

    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Get status of a Vonage call."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/v1/calls/{call_id}",
                params=self._get_auth_params(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "call_id": data.get("uuid"),
                    "conversation_uuid": data.get("conversation_uuid"),
                    "status": data.get("status"),
                    "direction": data.get("direction"),
                    "rate": data.get("rate"),
                    "price": data.get("price"),
                    "duration": data.get("duration"),
                    "start_time": data.get("start_time"),
                    "end_time": data.get("end_time"),
                }
            else:
                return {"error": response.text[:200]}
        except Exception as e:
            return {"error": str(e)[:200]}

    def hangup_call(self, call_id: str) -> ProviderResult:
        """Hang up an ongoing Vonage call (PUT /v1/calls/{call_id} with action=hangup)."""
        try:
            response = httpx.put(
                f"{self.BASE_URL}/v1/calls/{call_id}",
                json={"action": "hangup"},
                params=self._get_auth_params(),
                timeout=10.0,
            )

            if response.status_code == 200:
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="hangup_call",
                    message_id=call_id,
                )
            else:
                data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="hangup_call",
                    error_code=data.get("error_code", str(response.status_code)),
                    error_message=data.get("error_message", response.text[:200]),
                )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="hangup_call",
                error_message=str(e)[:200],
            )
