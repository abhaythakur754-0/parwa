"""Plivo SMS Provider stub."""

from app.providers.base import SMSProvider, SMSMessage, ProviderResult, ProviderStatus, ProviderCapability
from typing import Any, Dict

class PlivoSMSProvider(SMSProvider):
    provider_name = "plivo"
    display_name = "Plivo"
    required_config_fields = ["auth_id", "auth_token"]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._status = ProviderStatus.ACTIVE
    
    def test_connection(self) -> ProviderResult:
        return ProviderResult(success=True, provider_name=self.provider_name, operation="test_connection")
    
    def get_rate_limits(self) -> Dict[str, Any]:
        return {}
    
    def send_sms(self, message: SMSMessage) -> ProviderResult:
        return ProviderResult(success=False, provider_name=self.provider_name, operation="send_sms", error_message="Not implemented")
    
    def get_message_status(self, message_id: str) -> Dict[str, Any]:
        return {}
