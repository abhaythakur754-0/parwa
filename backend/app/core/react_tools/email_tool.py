"""
PARWA Phase 4 — Email Tool (wired to ProviderBridge)

Category: email
Methods: send_email
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseReactTool, ToolResult, _mock_email_result

logger = logging.getLogger(__name__)


class EmailTool(BaseReactTool):
    """Email integration tool — SendGrid, SES, Brevo, etc."""

    name = "email_tool"
    description = "Send emails to customers"
    category = "email"

    async def send_email(
        self,
        company_id: str,
        to: str,
        subject: str,
        body: str,
        variant_tier: str = "parwa",
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> ToolResult:
        """Send an email to a customer."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="send_email",
                fallback_fn=lambda **kw: _mock_email_result(to=to),
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Email sent to {to}",
                action_type="send_email",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("email send_email failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="send_email", variant_tier=variant_tier,
            )
