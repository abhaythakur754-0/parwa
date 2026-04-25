"""Microsoft Teams Chat Provider stub."""

from app.providers.base import ChatProvider, ChatMessage, ProviderResult, ProviderStatus
from typing import Any, Dict

class TeamsChatProvider(ChatProvider):
    provider_name = "teams"
    display_name = "Microsoft Teams"
    required_config_fields = ["webhook_url"]
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._status = ProviderStatus.ACTIVE
    
    def test_connection(self) -> ProviderResult:
        return ProviderResult(success=True, provider_name=self.provider_name, operation="test_connection")
    
    def get_rate_limits(self) -> Dict[str, Any]:
        return {}
    
    def send_message(self, message: ChatMessage) -> ProviderResult:
        return ProviderResult(success=False, provider_name=self.provider_name, operation="send_message", error_message="Not implemented")
    
    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        return {}
