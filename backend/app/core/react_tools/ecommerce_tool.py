"""
PARWA Phase 4 — ECommerce Tool (wired to ProviderBridge)

Category: ecommerce
Methods: get_order, cancel_order, refund_order, get_product
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import BaseReactTool, ToolResult, _mock_order

logger = logging.getLogger(__name__)


class ECommerceTool(BaseReactTool):
    """E-commerce integration tool — Shopify, WooCommerce, etc."""

    name = "ecommerce_tool"
    description = "Get order details, cancel orders, process refunds, get product info"
    category = "ecommerce"

    async def get_order(
        self,
        company_id: str,
        order_id: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Get order details."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="get_order",
                fallback_fn=lambda **kw: _mock_order(order_id=order_id),
                order_id=order_id,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Found order {order_id}",
                action_type="lookup_order",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("ecommerce get_order failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="lookup_order", variant_tier=variant_tier,
            )

    async def cancel_order(
        self,
        company_id: str,
        order_id: str,
        reason: str = "customer_request",
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Cancel an order and initiate refund."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="cancel_order",
                fallback_fn=lambda **kw: {
                    "order_id": order_id,
                    "status": "cancelled",
                    "reason": reason,
                    "refund_initiated": True,
                },
                order_id=order_id,
                reason=reason,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Order {order_id} cancelled with refund",
                action_type="cancel_order",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("ecommerce cancel_order failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="cancel_order", variant_tier=variant_tier,
            )

    async def refund_order(
        self,
        company_id: str,
        order_id: str,
        amount: Optional[float] = None,
        reason: str = "customer_request",
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Refund an order (full or partial)."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="refund_order",
                fallback_fn=lambda **kw: {
                    "order_id": order_id,
                    "refund_amount": amount or 59.98,
                    "reason": reason,
                    "status": "refunded",
                },
                order_id=order_id,
                amount=amount,
                reason=reason,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Order {order_id} refunded",
                action_type="refund_order",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("ecommerce refund_order failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="refund_order", variant_tier=variant_tier,
            )

    async def get_product(
        self,
        company_id: str,
        product_id: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Get product information."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="get_product",
                fallback_fn=lambda **kw: {
                    "product_id": product_id,
                    "name": "Widget Pro",
                    "price": 29.99,
                    "in_stock": True,
                    "description": "Premium widget for professionals",
                },
                product_id=product_id,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Found product {product_id}",
                action_type="lookup_product",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("ecommerce get_product failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="lookup_product", variant_tier=variant_tier,
            )
