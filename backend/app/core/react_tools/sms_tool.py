"""
PARWA Phase 4 — SMS Tool (wired to ProviderBridge)

Category: sms
Methods: send_sms
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .base import BaseReactTool, ToolResult, _mock_sms_result

logger = logging.getLogger(__name__)


class SMSTool(BaseReactTool):
    """SMS integration tool — Twilio, Vonage, etc."""

    name = "sms_tool"
    description = "Send SMS messages to customers"
    category = "sms"

    async def send_sms(
        self,
        company_id: str,
        to: str,
        message: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Send an SMS to a customer."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="send_sms",
                fallback_fn=lambda **kw: _mock_sms_result(to=to),
                to=to,
                message=message,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"SMS sent to {to}",
                action_type="send_sms",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("sms send_sms failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="send_sms", variant_tier=variant_tier,
            )
