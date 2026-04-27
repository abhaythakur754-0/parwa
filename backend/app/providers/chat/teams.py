"""
Microsoft Teams Chat Provider

Integration with Microsoft Teams for sending messages to channels and chats.

Supports two modes of operation:
  1. **Webhook mode** (simple): Send messages via an Office 365 Connector
     webhook URL. No OAuth required — just the webhook URL.
  2. **Graph API mode** (advanced): Full CRUD on channels, threads, and
     messages using Microsoft Graph API with OAuth 2.0 (Azure AD app
     registration required).

Configuration:
    - webhook_url: Office 365 Connector webhook URL (required for simple posting)
    - tenant_id: Azure AD tenant ID (optional, for Graph API)
    - client_id: Azure AD client ID (optional, for Graph API)
    - client_secret: Azure AD client secret (optional, for Graph API)

API References:
    - Webhook: https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/connectors-using
    - Graph API: https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview
"""

import logging
from typing import Any, Dict, Optional

import httpx

from app.providers.base import (
    ChatProvider,
    ChatMessage,
    ProviderResult,
    ProviderStatus,
    ProviderCapability,
)

logger = logging.getLogger(__name__)


class TeamsChatProvider(ChatProvider):
    """Microsoft Teams chat provider.

    Supports both webhook-based message posting (no auth required) and
    full Microsoft Graph API access for advanced operations.

    Configuration:
        - webhook_url: Office 365 Connector webhook URL (required)
        - tenant_id: Azure AD tenant ID (optional, for Graph API)
        - client_id: Azure AD client ID (optional, for Graph API)
        - client_secret: Azure AD client secret (optional, for Graph API)
    """

    provider_name = "teams"
    display_name = "Microsoft Teams"
    description = "Microsoft Teams chat integration via webhook or Graph API"
    website = "https://www.microsoft.com/en-us/microsoft-teams"

    required_config_fields = ["webhook_url"]
    optional_config_fields = ["tenant_id", "client_id", "client_secret"]

    capabilities = [
        ProviderCapability.SEND_MESSAGE,
        ProviderCapability.RICH_MESSAGES,
        ProviderCapability.WEBHOOKS,
    ]

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    GRAPH_SCOPES = "https://graph.microsoft.com/.default"

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the Microsoft Teams chat provider.

        Args:
            config: Configuration dict with at least 'webhook_url'.
        """
        super().__init__(config)
        self.webhook_url: str = config["webhook_url"]
        self.tenant_id: Optional[str] = config.get("tenant_id")
        self.client_id: Optional[str] = config.get("client_id")
        self.client_secret: Optional[str] = config.get("client_secret")
        self._access_token: Optional[str] = None
        self._status = ProviderStatus.ACTIVE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_graph_credentials(self) -> bool:
        """Check if Graph API credentials are configured."""
        return bool(self.tenant_id and self.client_id and self.client_secret)

    def _get_graph_access_token(self) -> Optional[str]:
        """Obtain an OAuth 2.0 access token for Microsoft Graph API.

        Uses the client_credentials flow.

        Returns:
            Access token string, or None if credentials are missing.
        """
        if not self._has_graph_credentials():
            return None

        # Return cached token if available
        if self._access_token:
            return self._access_token

        token_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}"
            f"/oauth2/v2.0/token"
        )

        try:
            response = httpx.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": self.GRAPH_SCOPES,
                },
                timeout=15.0,
            )

            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                return self._access_token

            logger.warning(
                "Teams Graph token request failed (%d): %s",
                response.status_code,
                response.text[:200],
            )
            return None
        except Exception as exc:
            logger.error("Teams Graph token request error: %s", exc)
            return None

    def _get_graph_headers(self) -> Dict[str, str]:
        """Return auth headers for Graph API requests."""
        token = self._get_graph_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Provider interface
    # ------------------------------------------------------------------

    def test_connection(self) -> ProviderResult:
        """Test the Teams integration.

        - With webhook only: sends a minimal test message to the webhook URL.
        - With Graph API: verifies the access token and fetches tenant info.
        """
        if not self._has_graph_credentials():
            # Simple webhook test — just check if the URL is reachable
            return self._test_webhook()

        return self._test_graph_api()

    def _test_webhook(self) -> ProviderResult:
        """Test the webhook URL by sending a lightweight request."""
        try:
            # Send an empty summary card as a ping
            payload = {
                "summary": "PARWA Connection Test",
                "sections": [{
                    "activityTitle": "PARWA Provider Test",
                    "activitySubtitle": "Teams webhook connectivity check",
                }],
            }
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=10.0,
            )

            if response.status_code == 200:
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={"mode": "webhook"},
                )

            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_code=str(response.status_code),
                error_message=response.text[:200],
            )
        except Exception as exc:
            logger.warning("Teams webhook test failed: %s", exc)
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message=str(exc)[:200],
            )

    def _test_graph_api(self) -> ProviderResult:
        """Test the Graph API connection by fetching the service principal."""
        token = self._get_graph_access_token()
        if not token:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message="Failed to obtain Graph API access token",
            )

        try:
            response = httpx.get(
                f"{self.GRAPH_BASE_URL}/servicePrincipals?$filter=appId eq '{self.client_id}'",
                headers=self._get_graph_headers(),
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="test_connection",
                    metadata={
                        "mode": "graph_api",
                        "tenant_id": self.tenant_id,
                        "app_found": len(data.get("value", [])) > 0,
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
            logger.warning("Teams Graph API test failed: %s", exc)
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="test_connection",
                error_message=str(exc)[:200],
            )

    def get_rate_limits(self) -> Dict[str, Any]:
        """Return Microsoft Graph API rate-limit information.

        Reference: https://learn.microsoft.com/en-us/graph/throttling-limits
        """
        return {
            "messages_per_minute": 30,
            "throttle_limit": "10,000 requests per 10 minutes per app per tenant",
            "note": "See https://learn.microsoft.com/en-us/graph/throttling-limits",
        }

    def send_message(self, message: ChatMessage) -> ProviderResult:
        """Send a message to a Teams channel.

        **Webhook mode** (default):
            Sends an Adaptive Card or plain text via the configured webhook URL.
            The message's ``channel_id`` is used only for metadata — all messages
            go to the webhook's pre-configured channel.

        **Graph API mode** (when Azure AD credentials are provided):
            Sends to a specific channel identified by ``message.channel_id``
            using ``POST /teams/{team_id}/channels/{channel_id}/messages``.
            In this mode, ``channel_id`` should be formatted as
            ``{team_id}/{channel_id}`` or just ``{channel_id}`` if the team
            is known from configuration.

        Args:
            message: ChatMessage with text, optional blocks/attachments.

        Returns:
            ProviderResult with success status.
        """
        if not self._has_graph_credentials():
            return self._send_via_webhook(message)
        return self._send_via_graph_api(message)

    def _send_via_webhook(self, message: ChatMessage) -> ProviderResult:
        """Send a message via Office 365 Connector webhook.

        Uses the Microsoft Teams Incoming Webhook format with
        Adaptive Card support.

        Args:
            message: ChatMessage to send.

        Returns:
            ProviderResult with success status.
        """
        # Build the webhook payload
        # Teams supports both simple text and rich "sections" / "facts"
        payload: Dict[str, Any] = {
            "text": message.text,
            "summary": message.text[:100],
        }

        # If blocks are provided, render as Adaptive Card
        if message.blocks:
            payload.pop("text", None)
            payload["@type"] = "MessageCard"
            payload["@context"] = "http://schema.org/extensions"
            payload["sections"] = message.blocks

        # If attachments are provided, add as potentialAction or facts
        if message.attachments:
            if "sections" not in payload:
                payload["@type"] = "MessageCard"
                payload["@context"] = "http://schema.org/extensions"
            if "sections" not in payload:
                payload["sections"] = []
            for att in message.attachments:
                if isinstance(att, dict):
                    payload["sections"].append(att)

        try:
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=30.0,
            )

            if response.status_code == 200:
                logger.debug(
                    "Teams webhook message sent to %s", message.channel_id
                )
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_message",
                    metadata={
                        "channel_id": message.channel_id,
                        "mode": "webhook",
                    },
                )

            error_detail = response.text[:200]
            logger.warning(
                "Teams webhook send_message failed (%d): %s",
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
            logger.error("Teams webhook send_message error: %s", exc)
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_message",
                error_message=str(exc)[:200],
            )

    def _send_via_graph_api(self, message: ChatMessage) -> ProviderResult:
        """Send a message via Microsoft Graph API.

        Uses ``POST /chats/{chat_id}/messages`` or
        ``POST /teams/{team_id}/channels/{channel_id}/messages``.

        Args:
            message: ChatMessage to send.

        Returns:
            ProviderResult with success status.
        """
        headers = self._get_graph_headers()
        if not headers.get("Authorization"):
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_message",
                error_message="No Graph API access token available",
            )

        graph_body: Dict[str, Any] = {"body": {"content": message.text}}

        # Determine the endpoint based on channel_id format
        # If channel_id contains "/", treat as team_id/channel_id
        channel_id = message.channel_id
        if "/" in channel_id:
            parts = channel_id.split("/", 1)
            api_url = (
                f"{self.GRAPH_BASE_URL}/teams/{parts[0]}"
                f"/channels/{parts[1]}/messages"
            )
        else:
            # Default to chat messages endpoint
            api_url = f"{self.GRAPH_BASE_URL}/chats/{channel_id}/messages"

        try:
            response = httpx.post(
                api_url,
                json=graph_body,
                headers=headers,
                timeout=30.0,
            )

            if response.status_code in (200, 201, 202):
                data = response.json()
                logger.debug(
                    "Teams Graph message sent: id=%s channel=%s",
                    data.get("id"),
                    channel_id,
                )
                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    operation="send_message",
                    message_id=data.get("id"),
                    metadata={
                        "channel_id": channel_id,
                        "mode": "graph_api",
                    },
                )

            error_detail = response.text[:200]
            logger.warning(
                "Teams Graph send_message failed (%d): %s",
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
            logger.error("Teams Graph send_message error: %s", exc)
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                operation="send_message",
                error_message=str(exc)[:200],
            )

    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Retrieve information about a Teams channel.

        Uses Microsoft Graph API: ``GET /channels/{channel_id}``.
        Requires Azure AD credentials to be configured.

        Args:
            channel_id: Teams channel ID (or team_id/channel_id).

        Returns:
            Dict with channel metadata or an error key.
        """
        if not self._has_graph_credentials():
            return {
                "error": "Graph API credentials required for channel info. "
                         "Provide tenant_id, client_id, and client_secret.",
                "provider": self.provider_name,
            }

        headers = self._get_graph_headers()
        if not headers.get("Authorization"):
            return {
                "error": "Failed to obtain Graph API access token",
                "provider": self.provider_name,
            }

        # Determine endpoint
        if "/" in channel_id:
            parts = channel_id.split("/", 1)
            api_url = (
                f"{self.GRAPH_BASE_URL}/teams/{parts[0]}"
                f"/channels/{parts[1]}"
            )
        else:
            api_url = f"{self.GRAPH_BASE_URL}/chats/{channel_id}"

        try:
            response = httpx.get(api_url, headers=headers, timeout=10.0)

            if response.status_code == 200:
                return response.json()

            logger.warning(
                "Teams get_channel_info failed (%d): %s",
                response.status_code,
                response.text[:200],
            )
            return {
                "error": response.text[:200],
                "status_code": response.status_code,
            }
        except Exception as exc:
            logger.error("Teams get_channel_info error: %s", exc)
            return {"error": str(exc)[:200]}

    # ------------------------------------------------------------------
    # Webhook parsing (for receiving messages from Teams bot framework)
    # ------------------------------------------------------------------

    def parse_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse an incoming Teams Bot Framework webhook payload.

        Args:
            data: Raw webhook JSON from Microsoft Teams Bot Framework.

        Returns:
            Normalized dict with channel_id, from, text, etc.
        """
        activity = data.get("activity", data)
        from_info = activity.get("from", {})
        channel_data = activity.get("channelData", {})
        return {
            "message_id": activity.get("id"),
            "channel_id": activity.get("channelId"),
            "conversation_id": activity.get("conversation", {}).get("id"),
            "from_id": from_info.get("id"),
            "from_name": from_info.get("name"),
            "text": activity.get("text"),
            "text_format": activity.get("textFormat"),
            "type": activity.get("type"),
            "timestamp": activity.get("timestamp"),
            "tenant_id": channel_data.get("tenant", {}).get("id"),
        }
