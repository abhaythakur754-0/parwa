"""
PARWA Phase 4 — Order Tool (wired to ProviderBridge)

Methods:
- get_order: Get order details
- list_orders: List customer orders
- cancel_order: Cancel an order
- update_order: Update an order
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseReactTool, ToolResult, _mock_order

logger = logging.getLogger(__name__)


class OrderTool(BaseReactTool):
    """E-commerce order tool — Shopify, WooCommerce, etc."""

    name = "order_tool"
    description = "Track orders, cancel orders, refund orders, get product info"
    category = "ecommerce"

    async def get_order(
        self,
        company_id: str,
        order_id: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Get order details by ID."""
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
            logger.error("order get_order failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="lookup_order", variant_tier=variant_tier,
            )

    async def list_orders(
        self,
        company_id: str,
        customer_id: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """List orders for a customer."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="list_orders",
                fallback_fn=lambda **kw: [
                    _mock_order(order_id="ORD-001"),
                    _mock_order(order_id="ORD-002"),
                ],
                customer_id=customer_id,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Found orders for customer {customer_id}",
                action_type="list_orders",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("order list_orders failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="list_orders", variant_tier=variant_tier,
            )

    async def cancel_order(
        self,
        company_id: str,
        order_id: str,
        reason: str = "customer_request",
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Cancel an order."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="cancel_order",
                fallback_fn=lambda **kw: {
                    "order_id": order_id,
                    "status": "cancelled",
                    "reason": reason,
                    "refund_amount": 59.98,
                },
                order_id=order_id,
                reason=reason,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Order {order_id} cancelled",
                action_type="cancel_order",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("order cancel_order failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="cancel_order", variant_tier=variant_tier,
            )

    async def update_order(
        self,
        company_id: str,
        order_id: str,
        updates: Dict[str, Any],
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Update an order."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="update_order",
                fallback_fn=lambda **kw: {**_mock_order(order_id=order_id), **updates},
                order_id=order_id,
                updates=updates,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Order {order_id} updated",
                action_type="update_order",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("order update_order failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="update_order", variant_tier=variant_tier,
            )
