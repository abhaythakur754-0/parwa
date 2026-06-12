"""
PARWA Phase 4 — HelpDesk Tool (wired to ProviderBridge)

Category: helpdesk
Methods: create_ticket, update_ticket, add_ticket_comment
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import BaseReactTool, ToolResult, _mock_ticket

logger = logging.getLogger(__name__)


class HelpDeskTool(BaseReactTool):
    """HelpDesk integration tool — Zendesk, Freshdesk, etc."""

    name = "helpdesk_tool"
    description = "Create support tickets, update tickets, add comments"
    category = "helpdesk"

    async def create_ticket(
        self,
        company_id: str,
        subject: str,
        description: str,
        customer_id: str = "",
        priority: str = "medium",
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Create a support ticket."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="create_ticket",
                fallback_fn=lambda **kw: _mock_ticket(),
                subject=subject,
                description=description,
                customer_id=customer_id,
                priority=priority,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Ticket created: {subject}",
                action_type="create_ticket",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("helpdesk create_ticket failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="create_ticket", variant_tier=variant_tier,
            )

    async def update_ticket(
        self,
        company_id: str,
        ticket_id: str,
        updates: Dict[str, Any],
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Update a support ticket."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="update_ticket",
                fallback_fn=lambda **kw: {**_mock_ticket(ticket_id=ticket_id), **updates},
                ticket_id=ticket_id,
                updates=updates,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Ticket {ticket_id} updated",
                action_type="update_ticket",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("helpdesk update_ticket failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="update_ticket", variant_tier=variant_tier,
            )

    async def add_ticket_comment(
        self,
        company_id: str,
        ticket_id: str,
        comment: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Add a comment to a support ticket."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="add_ticket_comment",
                fallback_fn=lambda **kw: {
                    "ticket_id": ticket_id,
                    "comment_id": "cmt-001",
                    "comment": comment,
                    "added_at": "now",
                },
                ticket_id=ticket_id,
                comment=comment,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Comment added to ticket {ticket_id}",
                action_type="add_comment",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("helpdesk add_comment failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="add_comment", variant_tier=variant_tier,
            )
