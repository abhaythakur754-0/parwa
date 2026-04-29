"""
PARWA ReAct Tool — Order Management  (F-157)

Exposes order-related actions to the ReAct agent:
- get_order         Fetch full details for a single order
- list_orders       List orders with optional filtering
- cancel_order      Cancel an open order
- get_order_status  Quick status check for one or many orders
- update_shipping   Change shipping address or carrier
- refund_order      Initiate a refund for a completed order

All actions are scoped to *company_id* (BC-001) and return
structured ToolResult (BC-008).
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Mock data factories ────────────────────────────────────────────

_CARRIERS = ["FedEx", "UPS", "DHL", "USPS", "OnTrac"]
_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled", "refunded"]
_ITEMS = [
    {"sku": "PARWA-PRO-001", "name": "PARWA Pro Annual Plan", "price": 299.00},
    {"sku": "PARWA-STD-001", "name": "PARWA Standard Monthly", "price": 49.00},
    {"sku": "PARWA-ENT-001", "name": "PARWA Enterprise Annual", "price": 999.00},
    {"sku": "ADDON-LANG-01", "name": "Additional Language Pack", "price": 19.00},
    {"sku": "ADDON-ANA-01", "name": "Analytics Dashboard", "price": 79.00},
]


def _mock_order(
    order_id: str | None = None,
    company_id: str = "",
    status: str = "pending",
) -> dict[str, Any]:
    """Generate a realistic mock order."""
    oid = order_id or f"ORD-{uuid.uuid4().hex[:8].upper()}"
    item = random.choice(_ITEMS)
    qty = random.randint(1, 5)
    carrier = random.choice(_CARRIERS) if status in ("shipped", "delivered") else None
    created = datetime.now(timezone.utc) - timedelta(
        days=random.randint(1, 90),
        hours=random.randint(0, 23),
    )
    shipped_at = created + timedelta(days=random.randint(1, 5)) if carrier else None
    delivered_at = (
        shipped_at + timedelta(days=random.randint(1, 7))
        if shipped_at and status == "delivered"
        else None
    )
    return {
        "order_id": oid,
        "company_id": company_id,
        "customer_id": f"CUST-{uuid.uuid4().hex[:6].upper()}",
        "status": status,
        "items": [
            {
                "sku": item["sku"],
                "name": item["name"],
                "quantity": qty,
                "unit_price": item["price"],
            }
        ],
        "total": round(item["price"] * qty, 2),
        "currency": "USD",
        "carrier": carrier,
        "tracking_number": f"1Z{uuid.uuid4().hex[:16].upper()}" if carrier else None,
        "shipping_address": {
            "line1": f"{random.randint(100, 9999)} Innovation Blvd",
            "city": random.choice(
                ["San Francisco", "Austin", "New York", "Seattle", "Denver"]
            ),
            "state": "CA",
            "zip": f"{random.randint(10000, 99999)}",
            "country": "US",
        },
        "created_at": created.isoformat(),
        "shipped_at": shipped_at.isoformat() if shipped_at else None,
        "delivered_at": delivered_at.isoformat() if delivered_at else None,
    }


def _mock_order_list(
    company_id: str,
    limit: int = 10,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Generate a list of mock orders."""
    orders: list[dict[str, Any]] = []
    for i in range(min(limit, 50)):
        status = status_filter or random.choice(_STATUSES)
        orders.append(_mock_order(company_id=company_id, status=status))
    return orders


# ── Tool Implementation ────────────────────────────────────────────


class OrderTool(BaseReactTool):
    """ReAct tool for Order Management API integration."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "order_management"

    @property
    def description(self) -> str:
        return (
            "Look up orders, check order status, cancel orders, "
            "get order history, update shipping details, and process refunds"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "get_order",
            "list_orders",
            "cancel_order",
            "get_order_status",
            "update_shipping",
            "refund_order",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="get_order",
                    description="Fetch full details for a single order by ID",
                    parameters={
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "Unique order identifier",
                            },
                        },
                        "required": ["order_id"],
                    },
                    required_params=["order_id"],
                    returns="Full order object with items, status, tracking, and shipping info",
                ),
                ActionSchema(
                    name="list_orders",
                    description="List orders with optional status filter and pagination",
                    parameters={
                        "type": "object",
                        "properties": {
                            "status": {
                                "type": "string",
                                "description": "Filter by status: pending, processing, shipped, delivered, cancelled, refunded",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Max orders to return (1-50)",
                                "default": 10,
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Pagination offset",
                                "default": 0,
                            },
                            "customer_id": {
                                "type": "string",
                                "description": "Filter by customer ID",
                            },
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="List of order objects",
                ),
                ActionSchema(
                    name="cancel_order",
                    description="Cancel an open (pending/processing) order",
                    parameters={
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "Order to cancel",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Cancellation reason",
                            },
                        },
                        "required": ["order_id"],
                    },
                    required_params=["order_id"],
                    returns="Updated order object with cancelled status",
                ),
                ActionSchema(
                    name="get_order_status",
                    description="Quick status check for one or more orders",
                    parameters={
                        "type": "object",
                        "properties": {
                            "order_ids": {
                                "type": "string",
                                "description": "Comma-separated list of order IDs",
                            },
                        },
                        "required": ["order_ids"],
                    },
                    required_params=["order_ids"],
                    returns="List of {order_id, status, tracking_number} objects",
                ),
                ActionSchema(
                    name="update_shipping",
                    description="Update shipping address or carrier for an order",
                    parameters={
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "Order to update",
                            },
                            "carrier": {
                                "type": "string",
                                "description": "New carrier name",
                            },
                            "tracking_number": {
                                "type": "string",
                                "description": "New tracking number",
                            },
                            "address": {
                                "type": "object",
                                "description": "New shipping address object",
                            },
                        },
                        "required": ["order_id"],
                    },
                    required_params=["order_id"],
                    returns="Updated order object",
                ),
                ActionSchema(
                    name="refund_order",
                    description="Initiate a refund for a completed or delivered order",
                    parameters={
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "Order to refund",
                            },
                            "amount": {
                                "type": "number",
                                "description": "Refund amount (omit for full refund)",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Refund reason",
                            },
                        },
                        "required": ["order_id"],
                    },
                    required_params=["order_id"],
                    returns="Refund confirmation with refund_id and amount",
                ),
            ],
        )

    # ── Execution ───────────────────────────────────────────────

    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """Route action to the appropriate handler."""

        # Simulate API latency
        await asyncio.sleep(random.uniform(0.02, 0.15))

        if action == "__health_check__":
            return ToolResult(
                success=True, error=None, data={"status": "ok"}, execution_time_ms=0
            )

        handler = {
            "get_order": self._get_order,
            "list_orders": self._list_orders,
            "cancel_order": self._cancel_order,
            "get_order_status": self._get_order_status,
            "update_shipping": self._update_shipping,
            "refund_order": self._refund_order,
        }.get(action)

        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {
                    ', '.join(
                        self.actions)}",
                data=None,
                execution_time_ms=0,
            )

        return await handler(company_id, **params)

    # ── Action Handlers ─────────────────────────────────────────

    async def _get_order(self, company_id: str, **params: Any) -> ToolResult:
        """Fetch full details for a single order."""
        order_id: str = params.get("order_id", "")

        # Try store first
        if order_id in self._store:
            order = self._store[order_id]
            if order["company_id"] != company_id:
                return ToolResult(
                    success=False,
                    error=f"Order {order_id} not found in company scope",
                    data=None,
                    execution_time_ms=0,
                )
            return ToolResult(success=True, error=None, data=order, execution_time_ms=0)

        order = _mock_order(order_id=order_id, company_id=company_id)
        self._store[order_id] = order
        return ToolResult(success=True, error=None, data=order, execution_time_ms=0)

    async def _list_orders(
        self,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """List orders with optional filtering."""
        status: str | None = params.get("status")
        limit: int = min(max(params.get("limit", 10), 1), 50)
        offset: int = max(params.get("offset", 0), 0)
        customer_id: str | None = params.get("customer_id")

        orders = _mock_order_list(
            company_id=company_id,
            limit=limit,
            status_filter=status,
        )

        if customer_id:
            orders = [o for o in orders if o.get("customer_id") == customer_id]

        paginated = orders[offset : offset + limit]
        return ToolResult(
            success=True,
            error=None,
            data={
                "orders": paginated,
                "total": len(orders),
                "limit": limit,
                "offset": offset,
            },
            execution_time_ms=0,
        )

    async def _cancel_order(self, company_id: str, **params: Any) -> ToolResult:
        """Cancel an open order."""
        order_id: str = params.get("order_id", "")
        reason: str = params.get("reason", "Cancelled by request")

        order = self._store.get(order_id) or _mock_order(
            order_id=order_id, company_id=company_id
        )

        if order["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Order {order_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        if order["status"] not in ("pending", "processing"):
            return ToolResult(
                success=False,
                error=f"Cannot cancel order in status '{
                    order['status']}'. Only pending/processing orders can be cancelled.",
                data={"current_status": order["status"]},
                execution_time_ms=0,
            )

        order["status"] = "cancelled"
        order["cancellation_reason"] = reason
        order["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        self._store[order_id] = order
        return ToolResult(success=True, error=None, data=order, execution_time_ms=0)

    async def _get_order_status(self, company_id: str, **params: Any) -> ToolResult:
        """Quick status check for one or more orders."""
        raw_ids: str = params.get("order_ids", "")
        order_ids = [oid.strip() for oid in raw_ids.split(",") if oid.strip()]

        if not order_ids:
            return ToolResult(
                success=False,
                error="No order IDs provided",
                data=None,
                execution_time_ms=0,
            )

        results: list[dict[str, Any]] = []
        for oid in order_ids[:20]:  # Max 20 at a time
            order = self._store.get(oid) or _mock_order(
                order_id=oid, company_id=company_id
            )
            results.append(
                {
                    "order_id": oid,
                    "status": order["status"],
                    "tracking_number": order.get("tracking_number"),
                    "carrier": order.get("carrier"),
                }
            )

        return ToolResult(
            success=True, error=None, data={"statuses": results}, execution_time_ms=0
        )

    async def _update_shipping(self, company_id: str, **params: Any) -> ToolResult:
        """Update shipping details for an order."""
        order_id: str = params.get("order_id", "")
        carrier: str | None = params.get("carrier")
        tracking_number: str | None = params.get("tracking_number")
        address: dict | None = params.get("address")

        order = self._store.get(order_id) or _mock_order(
            order_id=order_id, company_id=company_id
        )

        if order["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Order {order_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        if order["status"] in ("delivered", "cancelled", "refunded"):
            return ToolResult(
                success=False,
                error=f"Cannot update shipping for order in status '{
                    order['status']}'",
                data={"current_status": order["status"]},
                execution_time_ms=0,
            )

        updated_fields: list[str] = []
        if carrier:
            order["carrier"] = carrier
            updated_fields.append("carrier")
        if tracking_number:
            order["tracking_number"] = tracking_number
            updated_fields.append("tracking_number")
        if address:
            order["shipping_address"] = address
            updated_fields.append("shipping_address")

        if not updated_fields:
            return ToolResult(
                success=False,
                error="No shipping fields to update. Provide carrier, tracking_number, or address.",
                data=None,
                execution_time_ms=0,
            )

        order["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._store[order_id] = order
        return ToolResult(
            success=True,
            error=None,
            data={
                "order_id": order_id,
                "updated_fields": updated_fields,
                "order": order,
            },
            execution_time_ms=0,
        )

    async def _refund_order(self, company_id: str, **params: Any) -> ToolResult:
        """Initiate a refund for a completed order."""
        order_id: str = params.get("order_id", "")
        amount: float | None = params.get("amount")
        reason: str = params.get("reason", "Customer requested refund")

        order = self._store.get(order_id) or _mock_order(
            order_id=order_id,
            company_id=company_id,
            status="delivered",
        )

        if order["company_id"] != company_id:
            return ToolResult(
                success=False,
                error=f"Order {order_id} not found in company scope",
                data=None,
                execution_time_ms=0,
            )

        if order["status"] not in ("delivered", "shipped", "processing"):
            return ToolResult(
                success=False,
                error=f"Cannot refund order in status '{
                    order['status']}'. Only delivered/shipped/processing orders can be refunded.",
                data={"current_status": order["status"]},
                execution_time_ms=0,
            )

        if order.get("refunded"):
            return ToolResult(
                success=False,
                error=f"Order {order_id} has already been refunded",
                data=None,
                execution_time_ms=0,
            )

        refund_amount = amount if amount is not None else order["total"]
        refund_amount = round(min(refund_amount, order["total"]), 2)

        refund_id = f"REF-{uuid.uuid4().hex[:10].upper()}"
        order["status"] = "refunded"
        order["refunded"] = True
        order["refund"] = {
            "refund_id": refund_id,
            "amount": refund_amount,
            "currency": order.get("currency", "USD"),
            "reason": reason,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store[order_id] = order

        return ToolResult(
            success=True,
            error=None,
            data={
                "refund_id": refund_id,
                "order_id": order_id,
                "amount": refund_amount,
                "currency": order.get("currency", "USD"),
                "reason": reason,
                "status": "processed",
            },
            execution_time_ms=0,
        )
