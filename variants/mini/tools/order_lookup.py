"""
PARWA Mini Order Lookup Tool.

Provides order lookup functionality for Mini PARWA agents.
Integrates with Shopify client for real order data.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class OrderLookupTool:
    """
    Tool for looking up order information.

    Provides:
    - Lookup order by ID
    - Lookup orders by customer
    - Check order status
    """

    def __init__(self) -> None:
        """Initialize order lookup tool with mock data."""
        self._orders: Dict[str, Dict[str, Any]] = {
            "ORD-12345": {
                "order_id": "ORD-12345",
                "customer_id": "CUST-001",
                "customer_email": "customer@example.com",
                "status": "shipped",
                "total": 79.99,
                "currency": "USD",
                "items": [
                    {"product": "Widget A", "quantity": 2, "price": 29.99},
                    {"product": "Widget B", "quantity": 1, "price": 20.01},
                ],
                "shipping_address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "state": "CA",
                    "zip": "12345",
                    "country": "US",
                },
                "created_at": "2024-01-15T10:30:00Z",
                "shipped_at": "2024-01-16T14:00:00Z",
                "tracking_number": "TRACK-123456",
            },
            "ORD-67890": {
                "order_id": "ORD-67890",
                "customer_id": "CUST-002",
                "customer_email": "customer2@example.com",
                "status": "processing",
                "total": 150.00,
                "currency": "USD",
                "items": [
                    {"product": "Premium Widget", "quantity": 1, "price": 150.00},
                ],
                "shipping_address": {
                    "street": "456 Oak Ave",
                    "city": "Somewhere",
                    "state": "NY",
                    "zip": "67890",
                    "country": "US",
                },
                "created_at": "2024-01-20T09:00:00Z",
                "shipped_at": None,
                "tracking_number": None,
            },
        }
        self._customer_orders: Dict[str, List[str]] = {
            "CUST-001": ["ORD-12345"],
            "CUST-002": ["ORD-67890"],
        }

    async def lookup(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Lookup order by ID.

        Args:
            order_id: Order identifier

        Returns:
            Order data or None if not found
        """
        logger.info({
            "event": "order_lookup",
            "order_id": order_id,
        })

        return self._orders.get(order_id)

    async def lookup_by_customer(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all orders for a customer.

        Args:
            customer_id: Customer identifier

        Returns:
            List of customer orders
        """
        logger.info({
            "event": "order_lookup_by_customer",
            "customer_id": customer_id,
        })

        order_ids = self._customer_orders.get(customer_id, [])
        orders = []
        for order_id in order_ids:
            order = self._orders.get(order_id)
            if order:
                orders.append(order)
        return orders

    async def lookup_by_email(self, email: str) -> List[Dict[str, Any]]:
        """
        Get orders by customer email.

        Args:
            email: Customer email address

        Returns:
            List of matching orders
        """
        logger.info({
            "event": "order_lookup_by_email",
            "email": email,
        })

        orders = []
        email_lower = email.lower()
        for order in self._orders.values():
            if order.get("customer_email", "").lower() == email_lower:
                orders.append(order)
        return orders

    async def check_status(self, order_id: str) -> Optional[str]:
        """
        Get order status.

        Args:
            order_id: Order identifier

        Returns:
            Order status or None if not found
        """
        order = await self.lookup(order_id)
        return order.get("status") if order else None

    async def is_refundable(self, order_id: str) -> Dict[str, Any]:
        """
        Check if an order is refundable.

        Args:
            order_id: Order identifier

        Returns:
            Dict with refundable status and reason
        """
        order = await self.lookup(order_id)

        if not order:
            return {
                "refundable": False,
                "reason": "Order not found",
            }

        # Check order status
        status = order.get("status", "")
        if status == "refunded":
            return {
                "refundable": False,
                "reason": "Order already refunded",
            }

        # Check order age (within 30 days)
        created_at = order.get("created_at")
        if created_at:
            order_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - order_date).days

            if age_days > 30:
                return {
                    "refundable": False,
                    "reason": "Order is over 30 days old",
                }

        return {
            "refundable": True,
            "reason": "Order is eligible for refund",
            "order_total": order.get("total", 0),
        }

    async def get_tracking(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tracking information for an order.

        Args:
            order_id: Order identifier

        Returns:
            Tracking info or None if not found/shipped
        """
        order = await self.lookup(order_id)

        if not order:
            return None

        if not order.get("tracking_number"):
            return {
                "status": order.get("status"),
                "message": "Order has not been shipped yet",
            }

        return {
            "status": order.get("status"),
            "tracking_number": order.get("tracking_number"),
            "shipped_at": order.get("shipped_at"),
        }
