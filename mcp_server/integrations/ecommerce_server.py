"""
PARWA MCP — E-Commerce Server

Provides e-commerce platform integration tools.
Supports Shopify, WooCommerce, Magento, and BigCommerce
for order lookup, product search, and customer data retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    EcommerceOrderRequest,
    EcommerceOrderResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.ecommerce_server")


class EcommerceServer(MCPServerBase):
    """MCP sub-server for e-commerce platform integrations."""

    name = "ecommerce_server"
    description = "E-commerce platform integration (Shopify, WooCommerce, Magento, BigCommerce)"
    category = ToolCategory.INTEGRATION
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register e-commerce tools."""
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_get_order",
                description="Look up an e-commerce order by platform order ID. "
                            "Returns order details, items, and optionally customer info.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "include_items": {"type": "boolean", "default": True},
                        "include_customer": {"type": "boolean", "default": False},
                    },
                    "required": ["order_id"],
                },
                tags=["ecommerce", "order", "shopify", "woocommerce"],
            ),
            handler=self._invoke_get_order,
        )

        registry.register_tool(
            ToolDefinition(
                name="ecommerce_search_products",
                description="Search for products on an e-commerce platform.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
                tags=["ecommerce", "product", "search", "shopify"],
            ),
            handler=self._invoke_search_products,
        )

        registry.register_tool(
            ToolDefinition(
                name="ecommerce_get_customer_orders",
                description="Get all orders for a specific e-commerce customer.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "platform": {
                            "type": "string",
                            "default": "shopify",
                        },
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["customer_id"],
                },
                tags=["ecommerce", "customer", "orders"],
            ),
            handler=self._invoke_customer_orders,
        )

    def get_router(self) -> APIRouter:
        """Return the e-commerce REST router."""
        router = APIRouter(prefix="/integrations/ecommerce", tags=["Integration — E-Commerce"])

        @router.post("/order", response_model=EcommerceOrderResponse)
        async def get_order(request: EcommerceOrderRequest) -> EcommerceOrderResponse:
            """Look up an order via REST."""
            result = await self._invoke_get_order(request.model_dump())
            if result.success and result.data:
                return EcommerceOrderResponse(**result.data)
            return EcommerceOrderResponse(order_id=request.order_id, platform=request.platform)

        return router

    async def _invoke_get_order(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_get_order tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        platform = params.get("platform", "shopify")

        logger.info("ecommerce_order_lookup", order_id=order_id, platform=platform)

        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_get_order",
            data={
                "order_id": order_id,
                "platform": platform,
                "status": "fulfilled",
                "total": 149.99,
                "currency": "USD",
                "items": [
                    {
                        "name": "Sample Product",
                        "quantity": 1,
                        "price": 149.99,
                        "sku": "SKU-001",
                    }
                ],
                "created_at": "2025-01-10T14:30:00Z",
            },
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_search_products(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_search_products tool invocation."""
        params = parameters or {}
        query = params.get("query", "")
        platform = params.get("platform", "shopify")

        logger.info("ecommerce_product_search", query=query, platform=platform)

        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_search_products",
            data={"products": [], "total": 0},
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_customer_orders(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_get_customer_orders tool invocation."""
        params = parameters or {}
        customer_id = params.get("customer_id", "")

        logger.info("ecommerce_customer_orders", customer_id=customer_id)

        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_get_customer_orders",
            data={"orders": [], "total": 0},
            metadata={"status": "placeholder"},
        )


# Singleton instance
ecommerce_server = EcommerceServer()
