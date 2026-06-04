"""
PARWA MCP — E-Commerce Server (Day 1 — Real Shopify Integration)

Provides e-commerce platform integration tools.
Supports Shopify, WooCommerce, Magento, and BigCommerce
for order lookup, product search, customer data retrieval,
refund initiation, and order status tracking.

Day 1 Update: Shopify tools now make REAL API calls instead of
returning placeholder data. Uses ShopifyClient from backend.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

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

# Backend API base URL for looking up tenant integration credentials
BACKEND_URL = "http://localhost:5100"


class EcommerceServer(MCPServerBase):
    """MCP sub-server for e-commerce platform integrations.

    Day 1: Shopify tools make real API calls.
    WooCommerce, Magento, BigCommerce remain placeholder until Day 2.
    """

    name = "ecommerce_server"
    description = "E-commerce platform integration (Shopify, WooCommerce, Magento, BigCommerce)"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register e-commerce tools."""
        # ── Order Lookup ─────────────────────────────────────────────
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_get_order",
                description="Look up an e-commerce order by platform order ID. "
                            "Returns order details, items, status, and optionally customer info. "
                            "For Shopify, makes a real API call to the tenant's store.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Platform order ID"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "include_items": {"type": "boolean", "default": True},
                        "include_customer": {"type": "boolean", "default": False},
                        "company_id": {"type": "string", "description": "Tenant company ID for credential lookup"},
                    },
                    "required": ["order_id"],
                },
                tags=["ecommerce", "order", "shopify", "woocommerce"],
            ),
            handler=self._invoke_get_order,
        )

        # ── Order Status ─────────────────────────────────────────────
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_order_status",
                description="Get order status including fulfillment tracking. "
                            "For Shopify, returns financial status, fulfillment status, "
                            "tracking numbers, and tracking URLs.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Platform order ID"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "company_id": {"type": "string", "description": "Tenant company ID"},
                    },
                    "required": ["order_id"],
                },
                tags=["ecommerce", "order", "status", "tracking"],
            ),
            handler=self._invoke_order_status,
        )

        # ── Product Search ───────────────────────────────────────────
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_search_products",
                description="Search for products on an e-commerce platform. "
                            "For Shopify, searches product titles, descriptions, and SKUs.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "limit": {"type": "integer", "default": 10},
                        "company_id": {"type": "string", "description": "Tenant company ID"},
                    },
                    "required": ["query"],
                },
                tags=["ecommerce", "product", "search", "shopify"],
            ),
            handler=self._invoke_search_products,
        )

        # ── Customer Orders ──────────────────────────────────────────
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_get_customer_orders",
                description="Get all orders for a specific e-commerce customer. "
                            "For Shopify, looks up customer by ID and retrieves their order history.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string", "description": "Platform customer ID or email"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "limit": {"type": "integer", "default": 20},
                        "company_id": {"type": "string", "description": "Tenant company ID"},
                    },
                    "required": ["customer_id"],
                },
                tags=["ecommerce", "customer", "orders"],
            ),
            handler=self._invoke_customer_orders,
        )

        # ── Refund Initiate ──────────────────────────────────────────
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_refund_initiate",
                description="Initiate a refund on an e-commerce order. "
                            "For Shopify, creates a refund via the Shopify API. "
                            "Shopify processes the actual refund — PARWA never touches the money. "
                            "Use ecommerce_refund_calculate first to preview the refund amount.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Platform order ID"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "items": {
                            "type": "array",
                            "description": "Items to refund. Empty = refund all items.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "line_item_id": {"type": "string"},
                                    "quantity": {"type": "integer"},
                                    "amount": {"type": "string"},
                                },
                            },
                        },
                        "shipping_refund": {
                            "type": "object",
                            "description": "Shipping refund: {'full_refund': true} or {'amount': '5.00'}",
                        },
                        "note": {"type": "string", "description": "Refund note"},
                        "restock": {"type": "boolean", "default": True},
                        "company_id": {"type": "string", "description": "Tenant company ID"},
                    },
                    "required": ["order_id"],
                },
                tags=["ecommerce", "refund", "shopify"],
            ),
            handler=self._invoke_refund_initiate,
        )

        # ── Refund Calculate ─────────────────────────────────────────
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_refund_calculate",
                description="Calculate refund amounts for an order without creating a refund. "
                            "Use this to preview how much will be refunded before initiating.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "Platform order ID"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "line_item_id": {"type": "string"},
                                    "quantity": {"type": "integer"},
                                },
                            },
                        },
                        "company_id": {"type": "string", "description": "Tenant company ID"},
                    },
                    "required": ["order_id"],
                },
                tags=["ecommerce", "refund", "calculate"],
            ),
            handler=self._invoke_refund_calculate,
        )

        # ── Inventory Check ──────────────────────────────────────────
        registry.register_tool(
            ToolDefinition(
                name="ecommerce_inventory_check",
                description="Check inventory levels for a product. "
                            "For Shopify, returns variant-level inventory data.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Platform product ID"},
                        "platform": {
                            "type": "string",
                            "enum": ["shopify", "woocommerce", "magento", "bigcommerce"],
                            "default": "shopify",
                        },
                        "company_id": {"type": "string", "description": "Tenant company ID"},
                    },
                    "required": ["product_id"],
                },
                tags=["ecommerce", "inventory", "shopify"],
            ),
            handler=self._invoke_inventory_check,
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

    # ── Credential Resolution ────────────────────────────────────────

    async def _get_shopify_credentials(
        self, company_id: str, context: Optional[dict] = None,
    ) -> Optional[Dict[str, str]]:
        """Resolve Shopify credentials for a tenant.

        Tries multiple sources in order:
        1. Context dict (passed by agent pipeline)
        2. Backend API (queries integrations table)
        3. Returns None if no credentials found
        """
        # Check context first (fastest path — agent pipeline may pass it)
        if context and "shopify_shop_domain" in context:
            return {
                "shop_domain": context["shopify_shop_domain"],
                "access_token": context["shopify_access_token"],
            }

        if not company_id:
            logger.warning("ecommerce_no_company_id")
            return None

        # Query backend integration service for Shopify credentials
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{BACKEND_URL}/api/integrations",
                    params={"company_id": company_id, "integration_type": "shopify", "status": "active"},
                )
                if response.status_code == 200:
                    integrations = response.json()
                    if isinstance(integrations, list) and integrations:
                        # Use the first active Shopify integration
                        integration = integrations[0]
                        config = integration.get("config", {})

                        # Config may have masked tokens — try to get unmasked
                        # from credentials_encrypted via a dedicated endpoint
                        shop_domain = config.get("shop_domain", "")
                        access_token = config.get("access_token", "")

                        if shop_domain and access_token and "****" not in access_token:
                            return {
                                "shop_domain": shop_domain,
                                "access_token": access_token,
                            }

                        # If token is masked, try the integration detail endpoint
                        int_id = integration.get("id")
                        if int_id:
                            detail_response = await client.get(
                                f"{BACKEND_URL}/api/integrations/{int_id}",
                                params={"company_id": company_id},
                            )
                            if detail_response.status_code == 200:
                                detail = detail_response.json()
                                config = detail.get("config", {})
                                access_token = config.get("access_token", "")
                                if access_token and "****" not in access_token:
                                    return {
                                        "shop_domain": config.get("shop_domain", shop_domain),
                                        "access_token": access_token,
                                    }
        except Exception as e:
            logger.error("ecommerce_credential_lookup_failed error=%s", str(e))

        logger.warning("ecommerce_no_shopify_credentials company_id=%s", company_id)
        return None

    async def _get_shopify_client(self, company_id: str, context: Optional[dict] = None):
        """Get a ShopifyClient instance for the given tenant.

        Returns (ShopifyClient, error_message) tuple.
        If credentials not found, returns (None, error_message).
        """
        from backend.app.clients.shopify_client import get_shopify_client

        creds = await self._get_shopify_credentials(company_id, context)
        if not creds:
            return None, "Shopify not connected. Please connect your Shopify store in Settings → Integrations."

        client = get_shopify_client(
            shop_domain=creds["shop_domain"],
            access_token=creds["access_token"],
        )
        return client, None

    # ── Tool Handlers ────────────────────────────────────────────────

    async def _invoke_get_order(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_get_order tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        platform = params.get("platform", "shopify")
        include_items = params.get("include_items", True)
        include_customer = params.get("include_customer", False)
        company_id = params.get("company_id", "") or (context or {}).get("company_id", "")

        logger.info("ecommerce_order_lookup order_id=%s platform=%s", order_id, platform)

        # ── Shopify: Real API Call ───────────────────────────────
        if platform == "shopify":
            client, error = await self._get_shopify_client(company_id, context)
            if error:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_get_order",
                    error=error,
                    metadata={"platform": "shopify", "status": "no_credentials"},
                )

            try:
                # Try to get order by ID first
                try:
                    order = await client.get_order(order_id)
                except Exception:
                    # If ID lookup fails, try by order name (#1001 format)
                    order = await client.get_order_by_name(order_id)

                if not order:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="ecommerce_get_order",
                        error=f"Order {order_id} not found on Shopify",
                        metadata={"platform": "shopify"},
                    )

                # Format the response
                items = []
                if include_items:
                    for item in order.get("line_items", []):
                        items.append({
                            "name": item.get("title", ""),
                            "quantity": item.get("quantity", 1),
                            "price": item.get("price", "0.00"),
                            "sku": item.get("sku", ""),
                            "variant_title": item.get("variant_title", ""),
                            "vendor": item.get("vendor", ""),
                            "requires_shipping": item.get("requires_shipping", True),
                            "taxable": item.get("taxable", True),
                        })

                customer_data = None
                if include_customer and order.get("customer"):
                    c = order["customer"]
                    customer_data = {
                        "id": str(c.get("id", "")),
                        "email": c.get("email", ""),
                        "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                        "phone": c.get("phone", ""),
                        "orders_count": c.get("orders_count", 0),
                        "total_spent": c.get("total_spent", "0.00"),
                    }

                return ToolInvokeResponse(
                    success=True,
                    tool_name="ecommerce_get_order",
                    data={
                        "order_id": str(order.get("id", "")),
                        "order_number": order.get("order_number", ""),
                        "platform": "shopify",
                        "status": order.get("fulfillment_status") or order.get("financial_status", "unknown"),
                        "financial_status": order.get("financial_status", ""),
                        "fulfillment_status": order.get("fulfillment_status", "unfulfilled"),
                        "total": float(order.get("total_price", 0)),
                        "subtotal": float(order.get("subtotal_price", 0)),
                        "currency": order.get("currency", "USD"),
                        "items": items,
                        "customer": customer_data,
                        "shipping_address": order.get("shipping_address"),
                        "created_at": order.get("created_at", ""),
                        "updated_at": order.get("updated_at", ""),
                        "tags": order.get("tags", ""),
                        "note": order.get("note", ""),
                    },
                    metadata={"platform": "shopify", "status": "live"},
                )

            except Exception as e:
                logger.error("ecommerce_shopify_order_error error=%s", str(e))
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_get_order",
                    error=f"Shopify API error: {str(e)}",
                    metadata={"platform": "shopify", "status": "error"},
                )

        # ── Other Platforms: Placeholder ─────────────────────────
        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_get_order",
            data={
                "order_id": order_id,
                "platform": platform,
                "status": "placeholder",
                "message": f"{platform} integration not yet implemented. Available on Day 2.",
            },
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_order_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_order_status tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        platform = params.get("platform", "shopify")
        company_id = params.get("company_id", "") or (context or {}).get("company_id", "")

        logger.info("ecommerce_order_status order_id=%s platform=%s", order_id, platform)

        if platform == "shopify":
            client, error = await self._get_shopify_client(company_id, context)
            if error:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_order_status",
                    error=error,
                    metadata={"platform": "shopify", "status": "no_credentials"},
                )

            try:
                status = await client.get_order_status(order_id)
                return ToolInvokeResponse(
                    success=True,
                    tool_name="ecommerce_order_status",
                    data=status,
                    metadata={"platform": "shopify", "status": "live"},
                )
            except Exception as e:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_order_status",
                    error=f"Shopify API error: {str(e)}",
                    metadata={"platform": "shopify", "status": "error"},
                )

        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_order_status",
            data={"order_id": order_id, "platform": platform, "status": "placeholder"},
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
        company_id = params.get("company_id", "") or (context or {}).get("company_id", "")

        logger.info("ecommerce_product_search query=%s platform=%s", query, platform)

        if platform == "shopify":
            client, error = await self._get_shopify_client(company_id, context)
            if error:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_search_products",
                    error=error,
                    metadata={"platform": "shopify", "status": "no_credentials"},
                )

            try:
                result = await client.search_products(query, limit=limit)
                products = result.get("products", [])

                # Format product data for agent consumption
                formatted_products = []
                for p in products:
                    variants = p.get("variants", [])
                    formatted_products.append({
                        "id": str(p.get("id", "")),
                        "title": p.get("title", ""),
                        "product_type": p.get("product_type", ""),
                        "vendor": p.get("vendor", ""),
                        "status": p.get("status", ""),
                        "price_range": (
                            f"{variants[0]['price']}" if variants else "N/A"
                        ) if variants else "N/A",
                        "available": any(v.get("available", False) for v in variants),
                        "variant_count": len(variants),
                        "sku": variants[0].get("sku", "") if variants else "",
                        "image": p.get("images", [{}])[0].get("src", "") if p.get("images") else "",
                    })

                return ToolInvokeResponse(
                    success=True,
                    tool_name="ecommerce_search_products",
                    data={
                        "products": formatted_products,
                        "total": len(formatted_products),
                        "query": query,
                    },
                    metadata={"platform": "shopify", "status": "live"},
                )

            except Exception as e:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_search_products",
                    error=f"Shopify API error: {str(e)}",
                    metadata={"platform": "shopify", "status": "error"},
                )

        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_search_products",
            data={"products": [], "total": 0, "message": f"{platform} not yet implemented"},
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
        company_id = params.get("company_id", "") or (context or {}).get("company_id", "")

        logger.info("ecommerce_customer_orders customer_id=%s platform=%s", customer_id, platform)

        if platform == "shopify":
            client, error = await self._get_shopify_client(company_id, context)
            if error:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_get_customer_orders",
                    error=error,
                    metadata={"platform": "shopify", "status": "no_credentials"},
                )

            try:
                # If customer_id looks like an email, search by email first
                if "@" in customer_id:
                    search_result = await client.search_customers(f"email:{customer_id}")
                    customers = search_result.get("customers", [])
                    if not customers:
                        return ToolInvokeResponse(
                            success=True,
                            tool_name="ecommerce_get_customer_orders",
                            data={
                                "customer_id": customer_id,
                                "orders": [],
                                "total": 0,
                                "message": f"No Shopify customer found with email {customer_id}",
                            },
                            metadata={"platform": "shopify", "status": "live"},
                        )
                    # Use first matching customer
                    customer_id = str(customers[0]["id"])

                # Get customer orders
                result = await client.get_customer_orders(customer_id, limit=limit)
                orders = result.get("orders", [])

                # Format orders for agent consumption
                formatted_orders = []
                for order in orders:
                    formatted_orders.append({
                        "order_id": str(order.get("id", "")),
                        "order_number": order.get("order_number", ""),
                        "total_price": order.get("total_price", "0.00"),
                        "currency": order.get("currency", "USD"),
                        "financial_status": order.get("financial_status", ""),
                        "fulfillment_status": order.get("fulfillment_status", "unfulfilled"),
                        "created_at": order.get("created_at", ""),
                        "item_count": len(order.get("line_items", [])),
                    })

                return ToolInvokeResponse(
                    success=True,
                    tool_name="ecommerce_get_customer_orders",
                    data={
                        "customer_id": customer_id,
                        "orders": formatted_orders,
                        "total": len(formatted_orders),
                    },
                    metadata={"platform": "shopify", "status": "live"},
                )

            except Exception as e:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_get_customer_orders",
                    error=f"Shopify API error: {str(e)}",
                    metadata={"platform": "shopify", "status": "error"},
                )

        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_get_customer_orders",
            data={"orders": [], "total": 0, "message": f"{platform} not yet implemented"},
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_refund_initiate(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_refund_initiate tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        platform = params.get("platform", "shopify")
        items = params.get("items", [])
        shipping_refund = params.get("shipping_refund")
        note = params.get("note", "")
        restock = params.get("restock", True)
        company_id = params.get("company_id", "") or (context or {}).get("company_id", "")

        logger.info("ecommerce_refund_initiate order_id=%s platform=%s", order_id, platform)

        if platform == "shopify":
            client, error = await self._get_shopify_client(company_id, context)
            if error:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_refund_initiate",
                    error=error,
                    metadata={"platform": "shopify", "status": "no_credentials"},
                )

            try:
                # Build refund line items if specified
                refund_line_items = None
                if items:
                    refund_line_items = []
                    for item in items:
                        refund_line_items.append({
                            "line_item_id": item.get("line_item_id", ""),
                            "quantity": item.get("quantity", 1),
                            "restock_type": "return" if restock else "no_restock",
                        })
                        if item.get("amount"):
                            refund_line_items[-1]["amount"] = item["amount"]

                result = await client.initiate_refund(
                    order_id,
                    refund_line_items=refund_line_items,
                    shipping=shipping_refund,
                    note=note or "Refund initiated via PARWA AI agent",
                    restock=restock,
                )

                return ToolInvokeResponse(
                    success=True,
                    tool_name="ecommerce_refund_initiate",
                    data={
                        "refund_id": str(result.get("id", "")),
                        "order_id": str(result.get("order_id", order_id)),
                        "created_at": result.get("created_at", ""),
                        "refund_line_items": result.get("refund_line_items", []),
                        "transactions": result.get("transactions", []),
                        "note": result.get("note", ""),
                        "message": "Refund created on Shopify. Shopify will process the refund to the original payment method.",
                    },
                    metadata={"platform": "shopify", "status": "live"},
                )

            except Exception as e:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_refund_initiate",
                    error=f"Shopify refund error: {str(e)}",
                    metadata={"platform": "shopify", "status": "error"},
                )

        return ToolInvokeResponse(
            success=False,
            tool_name="ecommerce_refund_initiate",
            error=f"{platform} refund not yet implemented",
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_refund_calculate(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_refund_calculate tool invocation."""
        params = parameters or {}
        order_id = params.get("order_id", "")
        platform = params.get("platform", "shopify")
        items = params.get("items", [])
        company_id = params.get("company_id", "") or (context or {}).get("company_id", "")

        logger.info("ecommerce_refund_calculate order_id=%s platform=%s", order_id, platform)

        if platform == "shopify":
            client, error = await self._get_shopify_client(company_id, context)
            if error:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_refund_calculate",
                    error=error,
                    metadata={"platform": "shopify", "status": "no_credentials"},
                )

            try:
                refund_line_items = None
                if items:
                    refund_line_items = []
                    for item in items:
                        refund_line_items.append({
                            "line_item_id": item.get("line_item_id", ""),
                            "quantity": item.get("quantity", 1),
                            "restock_type": "no_restock",  # Calculate only, don't restock
                        })

                result = await client.calculate_refund(
                    order_id,
                    refund_line_items=refund_line_items,
                )

                return ToolInvokeResponse(
                    success=True,
                    tool_name="ecommerce_refund_calculate",
                    data={
                        "order_id": order_id,
                        "refund_line_items": result.get("refund_line_items", []),
                        "transactions": result.get("transactions", []),
                        "total_refund_amount": sum(
                            float(t.get("amount", 0))
                            for t in result.get("transactions", [])
                        ),
                        "message": "This is a preview. No refund has been created.",
                    },
                    metadata={"platform": "shopify", "status": "live"},
                )

            except Exception as e:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_refund_calculate",
                    error=f"Shopify calculation error: {str(e)}",
                    metadata={"platform": "shopify", "status": "error"},
                )

        return ToolInvokeResponse(
            success=False,
            tool_name="ecommerce_refund_calculate",
            error=f"{platform} refund calculate not yet implemented",
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_inventory_check(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ecommerce_inventory_check tool invocation."""
        params = parameters or {}
        product_id = params.get("product_id", "")
        platform = params.get("platform", "shopify")
        company_id = params.get("company_id", "") or (context or {}).get("company_id", "")

        logger.info("ecommerce_inventory_check product_id=%s platform=%s", product_id, platform)

        if platform == "shopify":
            client, error = await self._get_shopify_client(company_id, context)
            if error:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_inventory_check",
                    error=error,
                    metadata={"platform": "shopify", "status": "no_credentials"},
                )

            try:
                inventory = await client.get_product_inventory(product_id)
                return ToolInvokeResponse(
                    success=True,
                    tool_name="ecommerce_inventory_check",
                    data=inventory,
                    metadata={"platform": "shopify", "status": "live"},
                )
            except Exception as e:
                return ToolInvokeResponse(
                    success=False,
                    tool_name="ecommerce_inventory_check",
                    error=f"Shopify API error: {str(e)}",
                    metadata={"platform": "shopify", "status": "error"},
                )

        return ToolInvokeResponse(
            success=True,
            tool_name="ecommerce_inventory_check",
            data={"product_id": product_id, "status": "placeholder"},
            metadata={"platform": platform, "status": "placeholder"},
        )


# Singleton instance
ecommerce_server = EcommerceServer()
