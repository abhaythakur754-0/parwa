"""
PARWA Phase 4 — ExternalToolBus (UNIVERSAL — Refactored)

Variant-aware external service integration layer.
REFACTORED: Now uses UniversalToolRegistry for DYNAMIC tool registration.
ANY platform tool can be integrated — not just the original 8.

The ExternalToolBus is the HIGH-LEVEL interface that:
1. Wraps UniversalToolRegistry for convenience
2. Adds variant permission checks at the bus level
3. Provides shortcut methods for common operations
4. Allows AI pipeline to call any tool by name

Usage:
    bus = ExternalToolBus(bridge=provider_bridge)
    result = await bus.crm_get_contact(company_id, variant_tier, customer_id="cust-001")
    # OR use the universal interface:
    result = await bus.execute("notion_tool", "search", company_id, variant_tier, query="docs")
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .base import (
    BaseReactTool, ToolResult, ProviderResult,
    PermissionLevel, VARIANT_PERMISSIONS,
)
from .universal_registry import UniversalToolRegistry, DynamicTool
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

    UNIVERSAL: Supports ANY platform tool via UniversalToolRegistry.
    Built-in 8 tools are always available. Additional tools are
    registered dynamically from REST connectors, OpenAPI imports,
    or direct registration.

    Usage:
        bus = ExternalToolBus(bridge=provider_bridge)
        result = await bus.crm_get_contact(company_id, variant_tier, customer_id="cust-001")
        result = await bus.execute("notion_tool", "search", company_id, variant_tier, query="docs")
    """

    def __init__(
        self,
        bridge: Optional[Any] = None,
        executor: Optional[Any] = None,
    ):
        self._bridge = bridge
        self._executor = executor

        # Initialize the universal registry
        self._registry = UniversalToolRegistry(bridge=bridge, executor=executor)

        # Convenience references to built-in tools
        self._tools: Dict[str, BaseReactTool] = {
            "crm": self._registry.get_tool("crm_tool"),
            "billing": self._registry.get_tool("billing_tool"),
            "order": self._registry.get_tool("order_tool"),
            "email": self._registry.get_tool("email_tool"),
            "sms": self._registry.get_tool("sms_tool"),
            "helpdesk": self._registry.get_tool("helpdesk_tool"),
            "ecommerce": self._registry.get_tool("ecommerce_tool"),
            "slack": self._registry.get_tool("slack_tool"),
        }

    @property
    def tools(self) -> Dict[str, BaseReactTool]:
        """Access individual built-in tools by category name."""
        return self._tools

    @property
    def registry(self) -> UniversalToolRegistry:
        """Access the universal registry for dynamic operations."""
        return self._registry

    # ------------------------------------------------------------------
    # Universal execute — MAIN ENTRY POINT for AI pipeline
    # ------------------------------------------------------------------

    async def execute(
        self,
        tool_name: str,
        method: str,
        company_id: str,
        variant_tier: str = "parwa",
        **kwargs,
    ) -> ToolResult:
        """Execute any registered tool by name and method.

        This is the universal interface — works for built-in AND dynamic tools.
        """
        return await self._registry.execute(
            tool_name=tool_name,
            method=method,
            company_id=company_id,
            variant_tier=variant_tier,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Dynamic tool registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        category: str,
        methods: Dict[str, Callable],
    ) -> bool:
        """Register a custom tool at runtime."""
        return self._registry.register_tool(
            name=name,
            description=description,
            category=category,
            methods=methods,
        )

    def unregister_tool(self, name: str) -> bool:
        """Remove a dynamically registered tool."""
        return self._registry.unregister_tool(name)

    def register_rest_connector_tool(
        self,
        connector_name: str,
        base_url: str,
        openapi_spec: Optional[Dict] = None,
        auth_type: str = "bearer",
        credentials: Optional[Dict] = None,
    ) -> bool:
        """Auto-register a tool from a REST connector / OpenAPI spec."""
        return self._registry.register_rest_connector_tool(
            connector_name=connector_name,
            base_url=base_url,
            openapi_spec=openapi_spec,
            auth_type=auth_type,
            credentials=credentials,
        )

    # ------------------------------------------------------------------
    # List all tools
    # ------------------------------------------------------------------

    def list_available_tools(self, company_id: Optional[str] = None) -> List[Dict[str, str]]:
        """List all available tools (built-in + dynamic)."""
        return self._registry.list_tools(company_id=company_id)

    def get_tool_schema_for_ai(self) -> List[Dict[str, Any]]:
        """Get tool schemas for AI function calling."""
        return self._registry.get_tool_schema_for_ai()

    # ------------------------------------------------------------------
    # CRM shortcuts
    # ------------------------------------------------------------------

    async def crm_get_contact(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("crm")
        if tool:
            return await tool.get_contact(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="CRM tool not available", tool_name="crm_tool")

    async def crm_search_contacts(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("crm")
        if tool:
            return await tool.search_contacts(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="CRM tool not available", tool_name="crm_tool")

    # ------------------------------------------------------------------
    # Billing shortcuts
    # ------------------------------------------------------------------

    async def billing_get_subscription(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("billing")
        if tool:
            return await tool.get_subscription(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="Billing tool not available", tool_name="billing_tool")

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
        tool = self._tools.get("billing")
        if tool:
            return await tool.create_refund(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="Billing tool not available", tool_name="billing_tool")

    # ------------------------------------------------------------------
    # Order shortcuts
    # ------------------------------------------------------------------

    async def order_get_order(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("order")
        if tool:
            return await tool.get_order(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="Order tool not available", tool_name="order_tool")

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
        tool = self._tools.get("order")
        if tool:
            return await tool.cancel_order(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="Order tool not available", tool_name="order_tool")

    # ------------------------------------------------------------------
    # Email shortcuts
    # ------------------------------------------------------------------

    async def email_send(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("email")
        if tool:
            return await tool.send_email(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="Email tool not available", tool_name="email_tool")

    # ------------------------------------------------------------------
    # SMS shortcuts
    # ------------------------------------------------------------------

    async def sms_send(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("sms")
        if tool:
            return await tool.send_sms(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="SMS tool not available", tool_name="sms_tool")

    # ------------------------------------------------------------------
    # HelpDesk shortcuts
    # ------------------------------------------------------------------

    async def helpdesk_create_ticket(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("helpdesk")
        if tool:
            return await tool.create_ticket(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="HelpDesk tool not available", tool_name="helpdesk_tool")

    # ------------------------------------------------------------------
    # Slack shortcuts
    # ------------------------------------------------------------------

    async def slack_send_message(
        self, company_id: str, variant_tier: str, **kwargs
    ) -> ToolResult:
        tool = self._tools.get("slack")
        if tool:
            return await tool.send_message(
                company_id=company_id, variant_tier=variant_tier, **kwargs
            )
        return ToolResult(success=False, message="Slack tool not available", tool_name="slack_tool")
