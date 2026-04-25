"""
MessageBird SMS Provider

Implementation of the SMSProvider interface for MessageBird.
"""

from typing import Any, Dict

import httpx

from app.providers.base import (
    SMSProvider,
    SMSMessage,
    ProviderResult,
    ProviderStatus,
    ProviderCapability,
)


class MessageBirdSMSProvider(SMSProvider):
    """MessageBird SMS provider."""
    
    provider_name = "messagebird"
    display_name = "MessageBird"
    description = "Cloud communications API platform"
    website = "https://messagebird.com"
    
    required_config_fields = ["api_key"]
    optional_config_fields = ["originator"]
    
    capabilities = [
        ProviderCapability.SEND_SMS,
        ProviderCapability.RECEIVE_SMS,
        ProviderCapability.WEBHOOKS,
    ]
    
    API_URL = "https://rest.messagebird.com/messages"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.originator = config.get("originator", "PARWA")
        self._status = ProviderStatus.ACTIVE
    
    def test_connection(self) -> ProviderResult:
        try:
            response = httpx.get(
                "https://rest.messagebird.com/balance",
                headers={"Authorization": f"AccessKey {self.api_key}"},
                timeout=10.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={"balance": data.get("amount", "unknown")},
                )
            else:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="test_connection",
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
        return {"note": "Rate limits vary by account."}
    
    def send_sms(self, message: SMSMessage) -> ProviderResult:
        payload = {
            "originator": message.from_number or self.originator,
            "recipients": [message.to],
            "body": message.body,
        }
        
        try:
            response = httpx.post(
                self.API_URL,
                json=payload,
                headers={
                    "Authorization": f"AccessKey {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            
            if response.status_code == 201:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_sms",
                    message_id=str(data.get("id")),
                )
            else:
                return ProviderResult(
                    success=False,
                    provider_name=self.provider_name,
                    operation="send_sms",
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
        try:
            response = httpx.get(
                f"{self.API_URL}/{message_id}",
                headers={"Authorization": f"AccessKey {self.api_key}"},
                timeout=10.0,
            )
            
            if response.status_code == 200:
                return response.json()
            return {"error": response.text[:200]}
        except Exception as e:
            return {"error": str(e)[:200]}
    
    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message_id": data.get("id"),
            "from": data.get("originator"),
            "to": data.get("recipient"),
            "body": data.get("body"),
            "status": data.get("status"),
        }
