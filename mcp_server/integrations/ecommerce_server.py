"""
PARWA MCP — E-Commerce Server (v2.0.0 — Wired to Real Backend)

Provides e-commerce platform integration tools.
Wired to real backend e-commerce integration via httpx passthrough.

When an integration is connected (Shopify/WooCommerce/BigCommerce credentials stored),
this server proxies requests through the backend.

When no integration is connected, returns honest "not connected" status instead of fake data.
"""

from __future__ import annotations

import os

import httpx
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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


class EcommerceServer(MCPServerBase):
    """MCP sub-server for e-commerce platform integrations — wired to real backend."""

    name = "ecommerce_server"
    description = "E-commerce platform integration (Shopify, WooCommerce, BigCommerce) — wired to backend"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

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
                        "company_id": {"type": "string"},
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
                        "company_id": {"type": "string"},
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
                        "company_id": {"type": "string"},
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

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend e-commerce integration API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "ecommerce_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("ecommerce_backend_failed", path=path, error=str(exc)[:200])
        return None

    def _not_connected_response(self, tool_name: str, platform: str) -> ToolInvokeResponse:
        """Return an honest 'not connected' response instead of fake data."""
        return ToolInvokeResponse(
            success=False,
            tool_name=tool_name,
            error=f"E-commerce platform '{platform}' is not connected. Connect your {platform} store in Settings → Integrations to enable order/product lookups.",
            metadata={"platform": platform, "status": "not_connected"},
        )

    async def _invoke_get_order(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_get_order tool invocation — wired to backend."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        platform = params.get("platform", "shopify")

        logger.info("ecommerce_get_order_invoked", order_id=order_id, platform=platform)

        payload = {
            "action": "get_order",
            "platform": platform,
            "order_id": order_id,
            "include_items": params.get("include_items", True),
            "include_customer": params.get("include_customer", False),
        }
        if params.get("company_id"):
            payload["company_id"] = params["company_id"]

        data = await self._backend_call("POST", "/api/v1/integrations/ecommerce/order", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="ecommerce_get_order",
                data=data,
                metadata={"platform": platform, "source": "backend"},
            )

        return self._not_connected_response("ecommerce_get_order", platform)

    async def _invoke_search_products(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_search_products tool invocation — wired to backend."""
        params = parameters or {}
        query = params.get("query", "")
        platform = params.get("platform", "shopify")

        logger.info("ecommerce_search_products_invoked", query=query, platform=platform)

        payload = {
            "action": "search_products",
            "platform": platform,
            "query": query,
            "limit": params.get("limit", 10),
        }
        if params.get("company_id"):
            payload["company_id"] = params["company_id"]

        data = await self._backend_call("POST", "/api/v1/integrations/ecommerce/products", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="ecommerce_search_products",
                data=data,
                metadata={"platform": platform, "source": "backend"},
            )

        return self._not_connected_response("ecommerce_search_products", platform)

    async def _invoke_customer_orders(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_get_customer_orders tool invocation — wired to backend."""
        params = parameters or {}
        customer_id = params.get("customer_id", "")
        platform = params.get("platform", "shopify")

        logger.info("ecommerce_customer_orders_invoked", customer_id=customer_id, platform=platform)

        payload = {
            "action": "get_customer_orders",
            "platform": platform,
            "customer_id": customer_id,
            "limit": params.get("limit", 20),
        }
        if params.get("company_id"):
            payload["company_id"] = params["company_id"]

        data = await self._backend_call("POST", "/api/v1/integrations/ecommerce/customer-orders", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="ecommerce_get_customer_orders",
                data=data,
                metadata={"platform": platform, "source": "backend"},
            )

        return self._not_connected_response("ecommerce_get_customer_orders", platform)


# Singleton instance
ecommerce_server = EcommerceServer()
