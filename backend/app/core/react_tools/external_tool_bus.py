"""
PARWA Phase 4 — ExternalToolBus (Refactored)

Variant-aware external service integration layer.
REFACTORED: Now uses ProviderBridge instead of direct API calls.

All 8 ReAct tools are registered and accessible through this bus.
Each tool respects variant permissions:
- Mini: recommend only (needs approval)
- PARWA: auto-execute (can undo)
- High: auto-execute + voice + recordings
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import (
    BaseReactTool, ToolResult, ProviderResult,
    PermissionLevel, VARIANT_PERMISSIONS,
)
from .crm_tool import CRMTool
from .billing_tool import BillingTool
from .order_tool import OrderTool
from .email_tool import EmailTool
from .sms_tool import SMSTool
from .helpdesk_tool import HelpDeskTool
from .ecommerce_tool import ECommerceTool
from .slack_tool import SlackTool

logger = logging.getLogger(__name__)


class ExternalToolBus:
    """Variant-aware external service integration layer.

    REFACTORED: Now uses ProviderBridge instead of direct API calls.
    All 8 ReAct tools are accessible through this bus.

    Usage:
        bus = ExternalToolBus(bridge=provider_bridge)
        result = await bus.crm_get_contact(company_id, variant_tier, customer_id="cust-001")
    """

    def __init__(
        self,
        bridge: Optional[Any] = None,
        executor: Optional[Any] = None,
    ):
        self._bridge = bridge
        self._executor = executor

        # Register all tools
        self._tools: Dict[str, BaseReactTool] = {
            "crm": CRMTool(bridge=bridge, executor=executor),
            "billing": BillingTool(bridge=bridge, executor=executor),
            "order": OrderTool(bridge=bridge, executor=executor),
            "email": EmailTool(bridge=bridge, executor=executor),
            "sms": SMSTool(bridge=bridge, executor=executor),
            "helpdesk": HelpDeskTool(bridge=bridge, executor=executor),
            "ecommerce": ECommerceTool(bridge=bridge, executor=executor),
            "slack": SlackTool(bridge=bridge, executor=executor),
        }

    @property
    def tools(self) -> Dict[str, BaseReactTool]:
        """Access individual tools by category name."""
        return self._tools

    # ------------------------------------------------------------------
    # CRM shortcuts
    # ------------------------------------------------------------------

    async def crm_get_contact(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["crm"].get_contact(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    async def crm_search_contacts(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["crm"].search_contacts(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    # ------------------------------------------------------------------
    # Billing shortcuts
    # ------------------------------------------------------------------

    async def billing_get_subscription(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["billing"].get_subscription(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    async def billing_create_refund(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        perm = VARIANT_PERMISSIONS.get(variant_tier, PermissionLevel.EXECUTE)
        if perm == PermissionLevel.RECOMMEND:
            return ToolResult(
                success=False,
                message="Refund requires approval on Mini plan",
                needs_approval=True,
                variant_tier=variant_tier,
                action_type="refund",
            )
        return await self._tools["billing"].create_refund(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    # ------------------------------------------------------------------
    # Order shortcuts
    # ------------------------------------------------------------------

    async def order_get_order(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["order"].get_order(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    async def order_cancel_order(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        perm = VARIANT_PERMISSIONS.get(variant_tier, PermissionLevel.EXECUTE)
        if perm == PermissionLevel.RECOMMEND:
            return ToolResult(
                success=False,
                message="Order cancellation requires approval on Mini plan",
                needs_approval=True,
                variant_tier=variant_tier,
                action_type="cancel_order",
            )
        return await self._tools["order"].cancel_order(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    # ------------------------------------------------------------------
    # Email shortcuts
    # ------------------------------------------------------------------

    async def email_send(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["email"].send_email(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    # ------------------------------------------------------------------
    # SMS shortcuts
    # ------------------------------------------------------------------

    async def sms_send(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["sms"].send_sms(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    # ------------------------------------------------------------------
    # HelpDesk shortcuts
    # ------------------------------------------------------------------

    async def helpdesk_create_ticket(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["helpdesk"].create_ticket(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    # ------------------------------------------------------------------
    # Slack shortcuts
    # ------------------------------------------------------------------

    async def slack_send_message(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        return await self._tools["slack"].send_message(
            company_id=company_id, variant_tier=variant_tier, **kwargs
        )

    # ------------------------------------------------------------------
    # Generic tool execution
    # ------------------------------------------------------------------

    async def execute_tool(
        self,
        tool_name: str,
        method: str,
        company_id: str,
        variant_tier: str,
        **kwargs,
    ) -> ToolResult:
        """Execute any tool by name and method.

        This is the main entry point for the AI pipeline to call tools.
        """
        try:
            tool = self._tools.get(tool_name)
            if not tool:
                return ToolResult(
                    success=False,
                    message=f"Unknown tool: {tool_name}",
                    tool_name=tool_name,
                )

            method_fn = getattr(tool, method, None)
            if not method_fn:
                return ToolResult(
                    success=False,
                    message=f"Unknown method: {tool_name}.{method}",
                    tool_name=tool_name,
                )

            return await method_fn(
                company_id=company_id,
                variant_tier=variant_tier,
                **kwargs,
            )

        except Exception as exc:
            logger.error("execute_tool failed: %s", exc)
            return ToolResult(
                success=False,
                message=str(exc),
                tool_name=tool_name,
            )

    def list_available_tools(self) -> List[Dict[str, str]]:
        """List all available tools and their methods."""
        tools_info = []
        for name, tool in self._tools.items():
            methods = [
                m for m in dir(tool)
                if not m.startswith("_") and callable(getattr(tool, m)) and m != "to_dict"
            ]
            tools_info.append({
                "name": tool.name,
                "category": name,
                "description": tool.description,
                "methods": methods,
            })
        return tools_info
