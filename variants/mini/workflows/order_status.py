"""
PARWA Mini Order Status Workflow.

Handles order status lookup and response formatting.
"""
from typing import Dict, Any, Optional
from variants.mini.tools.order_lookup import OrderLookupTool
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class OrderStatusWorkflow:
    """
    Workflow for checking and reporting order status.

    Steps:
    1. Lookup order by ID or customer info
    2. Format status response
    3. Return to customer
    """

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None
    ) -> None:
        """
        Initialize order status workflow.

        Args:
            mini_config: Mini configuration
        """
        self._config = mini_config or get_mini_config()
        self._order_tool = OrderLookupTool()

    async def execute(self, order_id: str) -> Dict[str, Any]:
        """
        Execute the order status workflow.

        Args:
            order_id: Order identifier

        Returns:
            Dict with workflow result
        """
        logger.info({
            "event": "order_status_workflow_started",
            "order_id": order_id,
        })

        # Step 1: Lookup order
        order = await self._order_tool.lookup(order_id)

        if not order:
            return {
                "status": "not_found",
                "order_id": order_id,
                "message": f"Order {order_id} not found. Please check the order ID and try again.",
            }

        # Step 2: Format response
        status = order.get("status", "unknown")
        tracking = order.get("tracking_number")

        response = {
            "status": "found",
            "order_id": order_id,
            "order_status": status,
            "total": order.get("total"),
            "currency": order.get("currency", "USD"),
            "created_at": order.get("created_at"),
            "message": self._format_status_message(order),
        }

        # Add tracking if available
        if tracking:
            response["tracking_number"] = tracking
            response["tracking_message"] = f"Your order has been shipped. Tracking number: {tracking}"
        elif status == "processing":
            response["tracking_message"] = "Your order is being processed and will ship soon."

        # Step 3: Check if refundable
        refund_check = await self._order_tool.is_refundable(order_id)
        response["refundable"] = refund_check.get("refundable", False)
        response["refund_reason"] = refund_check.get("reason")

        return response

    async def execute_by_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get order status by customer ID.

        Args:
            customer_id: Customer identifier

        Returns:
            Dict with workflow result
        """
        logger.info({
            "event": "order_status_by_customer",
            "customer_id": customer_id,
        })

        orders = await self._order_tool.lookup_by_customer(customer_id)

        if not orders:
            return {
                "status": "no_orders",
                "customer_id": customer_id,
                "message": "No orders found for this customer.",
            }

        # Format order summary
        order_summaries = []
        for order in orders:
            order_summaries.append({
                "order_id": order.get("order_id"),
                "status": order.get("status"),
                "total": order.get("total"),
                "created_at": order.get("created_at"),
            })

        return {
            "status": "found",
            "customer_id": customer_id,
            "orders": order_summaries,
            "total_orders": len(orders),
            "message": f"Found {len(orders)} order(s).",
        }

    async def execute_by_email(self, email: str) -> Dict[str, Any]:
        """
        Get order status by customer email.

        Args:
            email: Customer email

        Returns:
            Dict with workflow result
        """
        logger.info({
            "event": "order_status_by_email",
            "email": email,
        })

        orders = await self._order_tool.lookup_by_email(email)

        if not orders:
            return {
                "status": "no_orders",
                "email": email,
                "message": "No orders found for this email address.",
            }

        # Format order summary
        order_summaries = []
        for order in orders:
            order_summaries.append({
                "order_id": order.get("order_id"),
                "status": order.get("status"),
                "total": order.get("total"),
                "created_at": order.get("created_at"),
            })

        return {
            "status": "found",
            "email": email,
            "orders": order_summaries,
            "total_orders": len(orders),
            "message": f"Found {len(orders)} order(s) for {email}.",
        }

    def _format_status_message(self, order: Dict[str, Any]) -> str:
        """
        Format a human-readable status message.

        Args:
            order: Order data

        Returns:
            Status message
        """
        status = order.get("status", "unknown")
        order_id = order.get("order_id", "unknown")

        status_messages = {
            "processing": f"Your order {order_id} is being processed and will ship soon.",
            "shipped": f"Your order {order_id} has been shipped!",
            "delivered": f"Your order {order_id} has been delivered.",
            "cancelled": f"Your order {order_id} has been cancelled.",
            "refunded": f"Your order {order_id} has been refunded.",
            "returned": f"Your order {order_id} return has been processed.",
        }

        return status_messages.get(
            status,
            f"Your order {order_id} status: {status}"
        )

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "OrderStatusWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"
