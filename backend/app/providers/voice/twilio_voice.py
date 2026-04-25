"""Twilio Voice Provider."""

from app.providers.base import VoiceProvider, VoiceCall, ProviderResult, ProviderStatus
from typing import Any, Dict
import httpx

class TwilioVoiceProvider(VoiceProvider):
    provider_name = "twilio"
    display_name = "Twilio Voice"
    required_config_fields = ["account_sid", "auth_token"]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.account_sid = config["account_sid"]
        self.auth_token = config["auth_token"]
        self._status = ProviderStatus.ACTIVE
    
    def _get_auth(self) -> tuple:
        return (self.account_sid, self.auth_token)
    
    def test_connection(self) -> ProviderResult:
        return ProviderResult(success=True, provider_name=self.provider_name, operation="test_connection")
    
    def get_rate_limits(self) -> Dict[str, Any]:
        return {}
    
    def make_call(self, call: VoiceCall) -> ProviderResult:
        base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        payload = {
            "To": call.to,
            "From": call.from_number,
        }
        if call.url:
            payload["Url"] = call.url
        if call.status_callback:
            payload["StatusCallback"] = call.status_callback
        if call.record:
            payload["Record"] = "true"
        
        try:
            response = httpx.post(
                f"{base_url}/Calls.json",
                data=payload,
                auth=self._get_auth(),
                timeout=30.0,
            )
            if response.status_code == 201:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="make_call",
                    message_id=data.get("sid"),
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="make_call",
                error_message=response.text[:200],
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="make_call",
                error_message=str(e)[:200],
            )
    
    def get_call_status(self, call_id: str) -> Dict[str, Any]:
        base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        try:
            response = httpx.get(
                f"{base_url}/Calls/{call_id}.json",
                auth=self._get_auth(),
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json()
            return {"error": response.text[:200]}
        except Exception as e:
            return {"error": str(e)[:200]}
    
    def hangup_call(self, call_id: str) -> ProviderResult:
        base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        try:
            response = httpx.post(
                f"{base_url}/Calls/{call_id}.json",
                data={"Status": "completed"},
                auth=self._get_auth(),
                timeout=10.0,
            )
            if response.status_code == 200:
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="hangup_call",
                    message_id=call_id,
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="hangup_call",
                error_message=response.text[:200],
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="hangup_call",
                error_message=str(e)[:200],
            )
