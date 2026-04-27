"""
Discord Chat Provider — DEPRECATED

Integration with Discord via bot token for sending and receiving messages.

DEPRECATED: Discord is not available in the China market (PARWA's primary
market). This provider is retained for international deployments but should
not be used in production for China-based workflows. Discord is primarily a
chat/gaming platform and requires a dedicated adapter to map its guild/channel
model to PARWA's chat interface.

Configuration:
    - bot_token: Discord bot token (required)

API Reference:
    - https://discord.com/developers/docs/resources/channel#create-message
    - https://discord.com/developers/docs/resources/channel#get-channel
"""

import logging
from typing import Any, Dict

import httpx

from app.providers.base import (
    ChatProvider,
    ChatMessage,
    ProviderResult,
    ProviderStatus,
    ProviderCapability,
)

logger = logging.getLogger(__name__)


class DiscordChatProvider(ChatProvider):
    """Discord chat provider (DEPRECATED — not available in China).

    Uses the Discord REST API with a bot token to send messages to channels
    and DMs, and to retrieve channel information.

    NOTE: This provider is deprecated for PARWA's primary China market.
          It is retained for international/B2B customers who use Discord
          for community support workflows.

    Configuration:
        - bot_token: Discord bot token (required)
    """

    provider_name = "discord"
    display_name = "Discord"
    description = "Discord chat integration (DEPRECATED — not available in China market)"
    website = "https://discord.com"
    deprecated = True

    required_config_fields = ["bot_token"]

    capabilities = [
        ProviderCapability.SEND_MESSAGE,
        ProviderCapability.RECEIVE_MESSAGE,
        ProviderCapability.RICH_MESSAGES,
        ProviderCapability.FILE_SHARING,
        ProviderCapability.WEBHOOKS,
    ]

    BASE_URL = "https://discord.com/api/v10"

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the Discord chat provider.

        Args:
            config: Configuration dict with at least 'bot_token'.
        """
        super().__init__(config)
        self.bot_token: str = config["bot_token"]
        self._status = ProviderStatus.ACTIVE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_headers(self) -> Dict[str, str]:
        """Return authentication headers for Discord API requests."""
        return {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    def test_connection(self) -> ProviderResult:
        """Verify the bot token by calling Discord's /users/@me endpoint."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/users/@me",
                headers=self._get_headers(),
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={
                        "bot_id": data.get("id"),
                        "username": data.get("username"),
                        "warning": "DEPRECATED: Discord is not available in China.",
                    },
                )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_code=str(response.status_code),
                error_message=response.text[:200],
            )
        except Exception as exc:
            logger.warning("Discord test_connection failed: %s", exc)
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message=str(exc)[:200],
            )

    def get_rate_limits(self) -> Dict[str, Any]:
        """Return Discord rate-limit information.

        Reference: https://discord.com/developers/docs/topics/rate-limits
        """
        return {
            "messages_per_minute": 50,
            "global_rate_limit": "50 requests per second",
            "note": "DEPRECATED provider. Discord rate limits vary by endpoint.",
        }

    def send_message(self, message: ChatMessage) -> ProviderResult:
        """Send a message to a Discord channel or DM.

        Uses ``POST /channels/{channel_id}/messages``.

        Args:
            message: ChatMessage with channel_id, text, optional blocks/embeds.

        Returns:
            ProviderResult with the Discord message ID on success.
        """
        payload: Dict[str, Any] = {"content": message.text}

        # Discord uses "embeds" instead of Slack-style "attachments"
        if message.attachments:
            payload["embeds"] = message.attachments

        # Rich text — pass as embeds if provided via blocks
        if message.blocks:
            payload["embeds"] = message.blocks

        if message.thread_ts:
            # Discord message_reference for replying
            payload["message_reference"] = {
                "message_id": message.thread_ts,
                "channel_id": message.channel_id,
            }

        try:
            response = httpx.post(
                f"{self.BASE_URL}/channels/{message.channel_id}/messages",
                json=payload,
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                logger.debug(
                    "Discord message sent: id=%s channel=%s",
                    data.get("id"),
                    message.channel_id,
                )
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_message",
                    message_id=str(data.get("id")),
                    metadata={
                        "channel_id": message.channel_id,
                        "timestamp": data.get("timestamp"),
                    },
                )

            error_detail = response.text[:200]
            logger.warning(
                "Discord send_message failed (%d): %s",
                response.status_code,
                error_detail,
            )
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_message",
                error_code=str(response.status_code),
                error_message=error_detail,
            )
        except Exception as exc:
            logger.error("Discord send_message error: %s", exc)
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_message",
                error_message=str(exc)[:200],
            )

    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Retrieve information about a Discord channel.

        Uses ``GET /channels/{channel_id}``.

        Args:
            channel_id: Discord channel snowflake ID.

        Returns:
            Dict with channel metadata or an error key.
        """
        try:
            response = httpx.get(
                f"{self.BASE_URL}/channels/{channel_id}",
                headers=self._get_headers(),
                timeout=10.0,
            )

            if response.status_code == 200:
                return response.json()

            logger.warning(
                "Discord get_channel_info failed (%d): %s",
                response.status_code,
                response.text[:200],
            )
            return {
                "error": response.text[:200],
                "status_code": response.status_code,
            }
        except Exception as exc:
            logger.error("Discord get_channel_info error: %s", exc)
            return {"error": str(exc)[:200]}

    # ------------------------------------------------------------------
    # Webhook parsing (for receiving messages via Discord webhooks)
    # ------------------------------------------------------------------

    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse an incoming Discord interaction / webhook payload.

        Args:
            data: Raw webhook JSON from Discord.

        Returns:
            Normalized dict with channel_id, author, content, etc.
        """
        # Discord gateway events or webhook payloads
        message_data = data.get("d", data)  # unwrap if gateway event
        author = message_data.get("author", {})
        return {
            "message_id": message_data.get("id"),
            "channel_id": message_data.get("channel_id"),
            "guild_id": message_data.get("guild_id"),
            "author_id": author.get("id"),
            "author_username": author.get("username"),
            "content": message_data.get("content"),
            "embeds": message_data.get("embeds", []),
            "timestamp": message_data.get("timestamp"),
        }
