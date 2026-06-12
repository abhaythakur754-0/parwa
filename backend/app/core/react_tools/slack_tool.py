"""
PARWA Phase 4 — Slack Tool (wired to ProviderBridge)

Category: communication
Methods: send_message, list_channels
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseReactTool, ToolResult, _mock_slack_result

logger = logging.getLogger(__name__)


class SlackTool(BaseReactTool):
    """Slack integration tool — send messages, list channels."""

    name = "slack_tool"
    description = "Send Slack messages, list channels"
    category = "communication"

    async def send_message(
        self,
        company_id: str,
        channel: str,
        message: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Send a message to a Slack channel."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="send_message",
                fallback_fn=lambda **kw: _mock_slack_result(channel=channel),
                channel=channel,
                message=message,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Message sent to {channel}",
                action_type="send_slack",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("slack send_message failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="send_slack", variant_tier=variant_tier,
            )

    async def list_channels(
        self,
        company_id: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """List available Slack channels."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="list_channels",
                fallback_fn=lambda **kw: [
                    {"id": "C001", "name": "#general", "members": 25},
                    {"id": "C002", "name": "#support", "members": 10},
                    {"id": "C003", "name": "#alerts", "members": 8},
                ],
            )
            return self._build_result(
                success=True,
                data=data,
                message="Found Slack channels",
                action_type="list_channels",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("slack list_channels failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="list_channels", variant_tier=variant_tier,
            )
