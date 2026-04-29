"""Slack Chat Provider."""

from typing import Any, Dict

import httpx
from app.providers.base import ChatMessage, ChatProvider, ProviderResult, ProviderStatus


class SlackChatProvider(ChatProvider):
    provider_name = "slack"
    display_name = "Slack"
    required_config_fields = ["bot_token"]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config["bot_token"]
        self._status = ProviderStatus.ACTIVE

    def test_connection(self) -> ProviderResult:
        try:
            response = httpx.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=10.0,
            )
            data = response.json()
            if data.get("ok"):
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={"team": data.get("team", "unknown")},
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message=data.get("error", "Unknown error"),
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message=str(e)[:200],
            )

    def get_rate_limits(self) -> Dict[str, Any]:
        return {"tier": "Tier 3 - ~50+ calls per minute"}

    def send_message(self, message: ChatMessage) -> ProviderResult:
        payload = {
            "channel": message.channel_id,
            "text": message.text,
        }
        if message.blocks:
            payload["blocks"] = message.blocks
        if message.attachments:
            payload["attachments"] = message.attachments
        if message.thread_ts:
            payload["thread_ts"] = message.thread_ts

        try:
            response = httpx.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            data = response.json()
            if data.get("ok"):
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_message",
                    message_id=data.get("ts"),
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_message",
                error_message=data.get("error", "Unknown error"),
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_message",
                error_message=str(e)[:200],
            )

    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        try:
            response = httpx.post(
                "https://slack.com/api/conversations.info",
                json={"channel": channel_id},
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=10.0,
            )
            data = response.json()
            if data.get("ok"):
                return data.get("channel", {})
            return {"error": data.get("error")}
        except Exception as e:
            return {"error": str(e)[:200]}
