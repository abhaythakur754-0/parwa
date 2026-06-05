"""
PARWA MCP — E-Commerce Server

Provides e-commerce platform integration tools.
Supports Shopify (primary), WooCommerce, Magento, and BigCommerce
for order lookup, product search, customer data retrieval,
fulfillment creation, and refund processing.

Connected to real Shopify Admin API via ShopifyClient when a
Shopify integration is configured. Falls back to placeholder
data when no integration is available.

Day 5 Addition:
  - shopify_refund_initiate: Full refund with Paddle payment processing
  - ecommerce_list_refunds: Refund history lookup
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

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

# Backend URL for fetching integration credentials
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


def _get_shopify_client(company_id: str) -> Optional[Any]:
    """Get a ShopifyClient for a company's active Shopify integration.

    Fetches the integration credentials from the backend API
    and creates a configured ShopifyClient instance.

    Args:
        company_id: PARWA company ID.

    Returns:
        ShopifyClient instance or None if no integration found.
    """
    try:
        import httpx
        from app.clients.shopify_client import ShopifyClient

        # Try to get Shopify integration from backend
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{BACKEND_URL}/api/integrations",
                params={"status": "active"},
                headers={"X-Company-Id": company_id},
            )

            if resp.status_code != 200:
                return None

            integrations = resp.json()
            for integration in integrations:
                if integration.get("type") == "shopify" and integration.get("status") == "active":
                    config = integration.get("config", {})
                    shop_domain = config.get("shop_domain", "")
                    access_token = config.get("access_token", "")

                    if shop_domain and access_token:
                        return ShopifyClient(
                            shop_domain=shop_domain,
                            access_token=access_token,
                        )

    except ImportError:
        logger.warning("shopify_client_not_available")
    except Exception as exc:
        logger.warning("shopify_client_fetch_failed error=%s", str(exc)[:200])

    return None


def _get_shopify_client_from_config(config: Dict[str, Any]) -> Optional[Any]:
    """Create a ShopifyClient directly from a config dict.

    Used when integration config is already available (e.g., from
    the MCP context) and we don't need to fetch from the backend.

    Args:
        config: Dict with shop_domain and access_token.

    Returns:
        ShopifyClient instance or None.
    """
    try:
        from app.clients.shopify_client import ShopifyClient

        shop_domain = config.get("shop_domain", "")
        access_token = config.get("access_token", "")

        if shop_domain and access_token:
            return ShopifyClient(
                shop_domain=shop_domain,
                access_token=access_token,
            )
    except ImportError:
        logger.warning("shopify_client_not_available")
    except Exception as exc:
        logger.warning("shopify_client_creation_failed error=%s", str(exc)[:200])

    return None


class EcommerceServer(MCPServerBase):
    """MCP sub-server for e-commerce platform integrations.

    Connects to real Shopify API when integration is available.
    Provides tools for order lookup, product search, customer data,
    fulfillment management, refund processing, and refund initiation
    with Paddle payment processing.
    """

    name = "ecommerce_server"
    description = "E-commerce platform integration (Shopify, WooCommerce, Magento, BigCommerce)"
    category = ToolCategory.INTEGRATION
    version = "3.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register e-commerce tools."""
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_get_order",
                description="Look up an e-commerce order by platform order ID. "
                            "Returns order details, items, and optionally customer info. "
                            "Supports Shopify (real API), WooCommerce, Magento, BigCommerce.",
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
                        "company_id": {"type": "string", "description": "PARWA company ID for Shopify integration lookup"},
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
                description="Search for products on an e-commerce platform. "
                            "Supports real Shopify API product search when integration is configured.",
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
                        "company_id": {"type": "string", "description": "PARWA company ID for Shopify integration lookup"},
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
                description="Get all orders for a specific e-commerce customer. "
                            "Uses real Shopify API when integration is configured.",
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
                        "company_id": {"type": "string", "description": "PARWA company ID for Shopify integration lookup"},
                    },
                    "required": ["customer_id"],
                },
                tags=["ecommerce", "customer", "orders"],
            ),
            handler=self._invoke_customer_orders,
        )

        registry.register_tool(
            ToolDefinition(
                name="ecommerce_create_fulfillment",
                description="Create a fulfillment for an e-commerce order with tracking info. "
                            "Uses real Shopify API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "tracking_number": {"type": "string"},
                        "tracking_url": {"type": "string"},
                        "tracking_company": {"type": "string"},
                        "notify_customer": {"type": "boolean", "default": True},
                        "platform": {
                            "type": "string",
                            "default": "shopify",
                        },
                        "company_id": {"type": "string", "description": "PARWA company ID for Shopify integration lookup"},
                    },
                    "required": ["order_id"],
                },
                tags=["ecommerce", "fulfillment", "shipping", "shopify"],
            ),
            handler=self._invoke_create_fulfillment,
        )

        registry.register_tool(
            ToolDefinition(
                name="ecommerce_create_refund",
                description="Create a refund for an e-commerce order. "
                            "Uses real Shopify API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "amount": {"type": "string", "description": "Refund amount"},
                        "reason": {"type": "string", "description": "Refund reason"},
                        "notify_customer": {"type": "boolean", "default": True},
                        "platform": {
                            "type": "string",
                            "default": "shopify",
                        },
                        "company_id": {"type": "string", "description": "PARWA company ID for Shopify integration lookup"},
                    },
                    "required": ["order_id"],
                },
                tags=["ecommerce", "refund", "shopify"],
            ),
            handler=self._invoke_create_refund,
        )

        # Day 5: Refund Initiate Tool — Shopify + Paddle atomic refund
        registry.register_tool(
            ToolDefinition(
                name="shopify_refund_initiate",
                description=(
                    "Initiate a refund for a Shopify order with Paddle payment processing. "
                    "Input: order_id + items + amount. "
                    "Output: refund object (ties into Paddle for payment processing). "
                    "This tool creates the refund in BOTH Shopify (marks items refunded) "
                    "and Paddle (processes the actual money back). "
                    "If Paddle fails after Shopify succeeds, the refund is marked 'partial' "
                    "and flagged for manual reconciliation. "
                    "Supports full refunds (all items) and partial refunds (specific items/amount)."
                ),
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Shopify order ID to refund",
                        },
                        "items": {
                            "type": "array",
                            "description": "Line items to refund. Each item has line_item_id (required), "
                                         "quantity (default 1), and amount (optional for partial). "
                                         "If empty, all order items will be refunded.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "line_item_id": {"type": "string"},
                                    "quantity": {"type": "integer", "default": 1},
                                    "amount": {"type": "string", "description": "Per-item refund amount (for partial refunds)"},
                                },
                                "required": ["line_item_id"],
                            },
                        },
                        "amount": {
                            "type": "string",
                            "description": "Total refund amount. If provided, overrides sum of items. "
                                         "If empty, refunds full order amount via Shopify.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the refund (e.g., 'Product defective', 'Duplicate order')",
                        },
                        "currency": {
                            "type": "string",
                            "default": "USD",
                            "description": "Currency code",
                        },
                        "notify_customer": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether to email the customer about the refund",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for integration lookup",
                        },
                        "paddle_customer_id": {
                            "type": "string",
                            "description": "Paddle customer ID for payment refund (optional)",
                        },
                        "paddle_transaction_id": {
                            "type": "string",
                            "description": "Paddle transaction ID for direct refund (optional)",
                        },
                    },
                    "required": ["order_id", "company_id"],
                },
                tags=["ecommerce", "refund", "shopify", "paddle", "payment"],
            ),
            handler=self._invoke_refund_initiate,
        )

        # Day 5: Refund History Tool
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_list_refunds",
                description=(
                    "List refunds for a Shopify order or company. "
                    "Returns refund history with status, amounts, and timestamps. "
                    "When order_id is provided, shows Shopify refunds for that order. "
                    "When only company_id is provided, shows company-wide refund history."
                ),
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Shopify order ID (optional — shows order-specific refunds)",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID (required for company-wide history)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by refund status (pending, processed, failed, canceled)",
                        },
                        "page": {
                            "type": "integer",
                            "default": 1,
                        },
                        "page_size": {
                            "type": "integer",
                            "default": 20,
                        },
                    },
                    "required": ["company_id"],
                },
                tags=["ecommerce", "refund", "history", "shopify"],
            ),
            handler=self._invoke_list_refunds,
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

    # ── Tool Handlers ─────────────────────────────────────────────

    async def _invoke_get_order(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_get_order tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        platform = params.get("platform", "shopify")
        company_id = params.get("company_id", "")
        include_items = params.get("include_items", True)

        logger.info("ecommerce_order_lookup", order_id=order_id, platform=platform)

        # Try real Shopify API
        if platform == "shopify" and company_id:
            shopify_client = _get_shopify_client(company_id)
            if shopify_client:
                fields = None
                if not include_items:
                    fields = ["id", "email", "total_price", "currency", "financial_status", "fulfillment_status"]

                result = await shopify_client.get_order(order_id, fields=fields)
                if result.success:
                    order = result.data
                    items = []
                    if include_items and "line_items" in order:
                        for item in order["line_items"]:
                            items.append({
                                "name": item.get("title", ""),
                                "quantity": item.get("quantity", 1),
                                "price": item.get("price", "0"),
                                "sku": item.get("sku", ""),
                            })

                    return ToolInvokeResponse(
                        success=True,
                        tool_name="ecommerce_get_order",
                        data={
                            "order_id": str(order.get("id", order_id)),
                            "platform": "shopify",
                            "status": order.get("financial_status", "unknown"),
                            "total": float(order.get("total_price", 0)),
                            "currency": order.get("currency", "USD"),
                            "items": items,
                            "email": order.get("email", ""),
                            "created_at": order.get("created_at", ""),
                            "fulfillment_status": order.get("fulfillment_status", ""),
                        },
                        metadata={"platform": "shopify", "source": "live_api"},
                    )

        # Fallback: placeholder response
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
        limit = params.get("limit", 10)
        company_id = params.get("company_id", "")

        logger.info("ecommerce_product_search", query=query, platform=platform)

        # Try real Shopify API
        if platform == "shopify" and company_id:
            shopify_client = _get_shopify_client(company_id)
            if shopify_client:
                result = await shopify_client.search_products(query=query, limit=limit)
                if result.success:
                    products = result.data if isinstance(result.data, list) else []
                    product_list = []
                    for product in products:
                        product_list.append({
                            "product_id": str(product.get("id", "")),
                            "title": product.get("title", ""),
                            "vendor": product.get("vendor", ""),
                            "product_type": product.get("product_type", ""),
                            "status": product.get("status", ""),
                            "price": (
                                product.get("variants", [{}])[0].get("price", "0")
                                if product.get("variants") else "0"
                            ),
                        })

                    return ToolInvokeResponse(
                        success=True,
                        tool_name="ecommerce_search_products",
                        data={"products": product_list, "total": len(product_list), "query": query},
                        metadata={"platform": "shopify", "source": "live_api"},
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_search_products",
            data={"products": [], "total": 0, "query": query},
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_customer_orders(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_get_customer_orders tool invocation."""
        params = parameters or {}
        customer_id = params.get("customer_id", "")
        platform = params.get("platform", "shopify")
        limit = params.get("limit", 20)
        company_id = params.get("company_id", "")

        logger.info("ecommerce_customer_orders", customer_id=customer_id)

        # Try real Shopify API
        if platform == "shopify" and company_id:
            shopify_client = _get_shopify_client(company_id)
            if shopify_client:
                result = await shopify_client.get_customer_orders(customer_id, limit=limit)
                if result.success:
                    orders = result.data if isinstance(result.data, list) else []
                    order_list = []
                    for order in orders:
                        order_list.append({
                            "order_id": str(order.get("id", "")),
                            "order_number": str(order.get("order_number", "")),
                            "total_price": order.get("total_price", "0"),
                            "currency": order.get("currency", "USD"),
                            "financial_status": order.get("financial_status", ""),
                            "created_at": order.get("created_at", ""),
                        })

                    return ToolInvokeResponse(
                        success=True,
                        tool_name="ecommerce_get_customer_orders",
                        data={"orders": order_list, "total": len(order_list), "customer_id": customer_id},
                        metadata={"platform": "shopify", "source": "live_api"},
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_get_customer_orders",
            data={"orders": [], "total": 0, "customer_id": customer_id},
            metadata={"status": "placeholder"},
        )

    async def _invoke_create_fulfillment(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_create_fulfillment tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        tracking_number = params.get("tracking_number", "")
        tracking_url = params.get("tracking_url", "")
        tracking_company = params.get("tracking_company", "")
        notify_customer = params.get("notify_customer", True)
        platform = params.get("platform", "shopify")
        company_id = params.get("company_id", "")

        logger.info("ecommerce_create_fulfillment", order_id=order_id, tracking=tracking_number)

        # Try real Shopify API
        if platform == "shopify" and company_id:
            shopify_client = _get_shopify_client(company_id)
            if shopify_client:
                result = await shopify_client.create_fulfillment(
                    order_id=order_id,
                    tracking_number=tracking_number,
                    tracking_url=tracking_url,
                    tracking_company=tracking_company,
                    notify_customer=notify_customer,
                )
                if result.success:
                    fulfillment = result.data
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="ecommerce_create_fulfillment",
                        data={
                            "fulfillment_id": str(fulfillment.get("id", "")),
                            "order_id": order_id,
                            "status": fulfillment.get("status", "pending"),
                            "tracking_number": fulfillment.get("tracking_number", tracking_number),
                            "tracking_url": fulfillment.get("tracking_url", tracking_url),
                            "tracking_company": fulfillment.get("tracking_company", tracking_company),
                        },
                        metadata={"platform": "shopify", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="ecommerce_create_fulfillment",
                        error=f"Shopify fulfillment creation failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_create_fulfillment",
            data={
                "fulfillment_id": "fl_placeholder",
                "order_id": order_id,
                "status": "placeholder",
                "tracking_number": tracking_number,
                "message": "Fulfillment placeholder — no Shopify integration configured",
            },
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_create_refund(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_create_refund tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        amount = params.get("amount", "")
        reason = params.get("reason", "")
        notify_customer = params.get("notify_customer", True)
        platform = params.get("platform", "shopify")
        company_id = params.get("company_id", "")

        logger.info("ecommerce_create_refund", order_id=order_id, amount=amount)

        # Try real Shopify API
        if platform == "shopify" and company_id:
            shopify_client = _get_shopify_client(company_id)
            if shopify_client:
                # First get the order to find line items for refund
                order_result = await shopify_client.get_order(order_id)
                refund_line_items = []

                if order_result.success and "line_items" in order_result.data:
                    for item in order_result.data["line_items"]:
                        refund_line_items.append({
                            "line_item_id": item.get("id"),
                            "quantity": item.get("quantity", 1),
                        })

                result = await shopify_client.create_refund(
                    order_id=order_id,
                    refund_line_items=refund_line_items if refund_line_items else None,
                    note=reason,
                    notify_customer=notify_customer,
                )
                if result.success:
                    refund = result.data
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="ecommerce_create_refund",
                        data={
                            "refund_id": str(refund.get("id", "")),
                            "order_id": order_id,
                            "amount": refund.get("transactions", [{}])[0].get("amount", amount) if refund.get("transactions") else amount,
                            "note": refund.get("note", reason),
                            "created_at": refund.get("created_at", ""),
                        },
                        metadata={"platform": "shopify", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="ecommerce_create_refund",
                        error=f"Shopify refund creation failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_create_refund",
            data={
                "refund_id": "rf_placeholder",
                "order_id": order_id,
                "amount": amount,
                "message": "Refund placeholder — no Shopify integration configured",
            },
            metadata={"platform": platform, "status": "placeholder"},
        )

    # ── Day 5: Refund Initiate Tool ──────────────────────────────

    async def _invoke_refund_initiate(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle shopify_refund_initiate tool invocation.

        This is the PRIMARY Refund Initiate Tool that bridges
        Shopify + Paddle for atomic refund processing.

        Input:  order_id + items + amount
        Output: refund object (ties into Paddle for payment processing)
        """
        params = parameters or {}
        order_id = params.get("order_id", "")
        items = params.get("items", [])
        amount = params.get("amount", "")
        reason = params.get("reason", "")
        currency = params.get("currency", "USD")
        notify_customer = params.get("notify_customer", True)
        company_id = params.get("company_id", "")
        paddle_customer_id = params.get("paddle_customer_id", "")
        paddle_transaction_id = params.get("paddle_transaction_id", "")

        logger.info(
            "shopify_refund_initiate: order=%s, company=%s, items=%d, amount=%s",
            order_id, company_id, len(items), amount,
        )

        if not order_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="shopify_refund_initiate",
                error="order_id is required",
            )

        if not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="shopify_refund_initiate",
                error="company_id is required",
            )

        # Get Shopify client
        shopify_client = _get_shopify_client(company_id)

        # Get Paddle bridge (optional — graceful if not available)
        paddle_bridge = self._get_paddle_bridge()

        # Use RefundBridge for atomic Shopify + Paddle refund
        try:
            from app.services.refund_bridge import get_refund_bridge
            bridge = get_refund_bridge()

            result = await bridge.initiate_refund(
                company_id=company_id,
                order_id=order_id,
                items=items,
                amount=amount if amount else None,
                reason=reason,
                currency=currency,
                notify_customer=notify_customer,
                shopify_client=shopify_client,
                paddle_bridge=paddle_bridge,
                paddle_customer_id=paddle_customer_id or None,
                paddle_transaction_id=paddle_transaction_id or None,
            )

            return ToolInvokeResponse(
                success=result.success,
                tool_name="shopify_refund_initiate",
                data=result.to_dict(),
                error=result.error if not result.success else "",
                metadata={
                    "refund_id": result.refund_id,
                    "shopify_status": result.shopify_status,
                    "paddle_status": result.paddle_status,
                    "requires_reconciliation": result.requires_reconciliation,
                },
            )

        except ImportError:
            # RefundBridge not available — fallback to Shopify-only refund
            logger.warning("refund_bridge_not_available_fallback_to_shopify_only")

            if shopify_client:
                # Build line items from provided items
                refund_line_items = []
                if items:
                    for item in items:
                        refund_line_items.append({
                            "line_item_id": item.get("line_item_id", ""),
                            "quantity": item.get("quantity", 1),
                        })

                # Build transactions if amount specified
                shopify_transactions = None
                if amount:
                    shopify_transactions = [{
                        "parent_id": None,
                        "amount": str(amount),
                        "kind": "refund",
                    }]

                shopify_result = await shopify_client.create_refund(
                    order_id=order_id,
                    refund_line_items=refund_line_items if refund_line_items else None,
                    transactions=shopify_transactions,
                    note=f"[PARWA] {reason}" if reason else "[PARWA] Refund initiated",
                    notify_customer=notify_customer,
                )

                if shopify_result.success:
                    refund = shopify_result.data
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="shopify_refund_initiate",
                        data={
                            "refund_id": str(refund.get("id", "")),
                            "order_id": order_id,
                            "amount": amount or str(refund.get("transactions", [{}])[0].get("amount", "0")),
                            "currency": currency,
                            "reason": reason,
                            "shopify_status": "processed",
                            "paddle_status": "skipped",
                            "items_refunded": items,
                            "note": "Shopify-only refund — Paddle payment processing not available",
                        },
                        metadata={"platform": "shopify", "source": "live_api", "paddle": "unavailable"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="shopify_refund_initiate",
                        error=f"Shopify refund failed: {shopify_result.error}",
                    )

            # No Shopify client either — placeholder
            return ToolInvokeResponse(
                success=True,
                tool_name="shopify_refund_initiate",
                data={
                    "refund_id": "rf_placeholder",
                    "order_id": order_id,
                    "amount": amount or "0.00",
                    "currency": currency,
                    "reason": reason,
                    "shopify_status": "placeholder",
                    "paddle_status": "placeholder",
                    "items_refunded": items,
                    "message": "Refund placeholder — no Shopify integration configured",
                },
                metadata={"status": "placeholder"},
            )

    # ── Day 5: Refund History Tool ───────────────────────────────

    async def _invoke_list_refunds(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_list_refunds tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        company_id = params.get("company_id", "")
        status = params.get("status")
        page = params.get("page", 1)
        page_size = params.get("page_size", 20)

        logger.info(
            "ecommerce_list_refunds: order=%s, company=%s, status=%s",
            order_id, company_id, status,
        )

        if not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="ecommerce_list_refunds",
                error="company_id is required",
            )

        # If order_id provided, get Shopify refunds for that order
        if order_id:
            shopify_client = _get_shopify_client(company_id)
            if shopify_client:
                result = await shopify_client.list_refunds(order_id)
                if result.success:
                    refunds = result.data if isinstance(result.data, list) else []
                    refund_list = []
                    for refund in refunds:
                        refund_list.append({
                            "refund_id": str(refund.get("id", "")),
                            "order_id": order_id,
                            "amount": str(sum(
                                float(t.get("amount", 0))
                                for t in refund.get("transactions", [])
                            )),
                            "note": refund.get("note", ""),
                            "created_at": refund.get("created_at", ""),
                            "line_items": [
                                {
                                    "line_item_id": str(li.get("line_item_id", "")),
                                    "quantity": li.get("quantity", 0),
                                }
                                for li in refund.get("refund_line_items", [])
                            ],
                        })

                    return ToolInvokeResponse(
                        success=True,
                        tool_name="ecommerce_list_refunds",
                        data={
                            "refunds": refund_list,
                            "total": len(refund_list),
                            "order_id": order_id,
                            "source": "shopify_api",
                        },
                        metadata={"platform": "shopify", "source": "live_api"},
                    )

        # Company-wide refund history via RefundBridge
        try:
            from app.services.refund_bridge import get_refund_bridge
            bridge = get_refund_bridge()
            history = await bridge.get_refund_history(
                company_id=company_id,
                status=status,
                page=page,
                page_size=page_size,
            )
            return ToolInvokeResponse(
                success=True,
                tool_name="ecommerce_list_refunds",
                data=history,
                metadata={"source": "refund_bridge"},
            )
        except ImportError:
            return ToolInvokeResponse(
                success=True,
                tool_name="ecommerce_list_refunds",
                data={
                    "refunds": [],
                    "total": 0,
                    "pagination": {"page": page, "page_size": page_size, "total": 0, "total_pages": 0},
                    "message": "No refund history available — RefundBridge not configured",
                },
                metadata={"status": "placeholder"},
            )

    # ── Paddle Bridge Helper ──────────────────────────────────────

    def _get_paddle_bridge(self) -> Optional[Any]:
        """Get a JarvisPaddleBridge instance if Paddle is configured.

        Returns None if Paddle is not configured (graceful degradation).
        """
        try:
            from app.services.jarvis_paddle_bridge import JarvisPaddleBridge

            api_key = os.environ.get("PADDLE_API_KEY", "")
            if not api_key:
                return None

            sandbox = os.environ.get("ENVIRONMENT", "development") != "production"
            return JarvisPaddleBridge(
                api_key=api_key,
                client_token=os.environ.get("PADDLE_CLIENT_TOKEN", ""),
                sandbox=sandbox,
            )
        except ImportError:
            logger.debug("paddle_bridge_not_available")
            return None
        except Exception as exc:
            logger.warning("paddle_bridge_init_failed error=%s", str(exc)[:200])
            return None


# Singleton instance
ecommerce_server = EcommerceServer()
