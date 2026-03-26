"""
PARWA E-commerce MCP Server.

MCP server for e-commerce operations including order lookup,
product search, inventory management, and refund request creation.

CRITICAL: create_refund_request ONLY creates pending_approval records.
It NEVER directly executes refunds - this is enforced by the
ApprovalEnforcer in shared/guardrails/approval_enforcer.py.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


# Mock data for testing
MOCK_ORDERS = {
    "ORD-001": {
        "order_id": "ORD-001",
        "customer_id": "CUST-001",
        "status": "delivered",
        "total": 149.99,
        "currency": "USD",
        "items": [
            {"product_id": "PROD-001", "name": "Widget Pro", "quantity": 2, "price": 49.99},
            {"product_id": "PROD-002", "name": "Widget Cable", "quantity": 1, "price": 49.99}
        ],
        "created_at": "2026-03-15T10:30:00Z",
        "updated_at": "2026-03-18T14:00:00Z",
        "shipping_address": {
            "street": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94102",
            "country": "US"
        }
    },
    "ORD-002": {
        "order_id": "ORD-002",
        "customer_id": "CUST-002",
        "status": "processing",
        "total": 299.99,
        "currency": "USD",
        "items": [
            {"product_id": "PROD-003", "name": "Premium Widget", "quantity": 1, "price": 299.99}
        ],
        "created_at": "2026-03-20T08:00:00Z",
        "updated_at": "2026-03-20T08:00:00Z",
        "shipping_address": {
            "street": "456 Oak Ave",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "country": "US"
        }
    }
}

MOCK_CUSTOMERS = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "email": "john.doe@example.com",
        "name": "John Doe",
        "phone": "+1-555-0100",
        "total_orders": 5,
        "total_spent": 849.95,
        "loyalty_tier": "gold",
        "created_at": "2025-06-15T00:00:00Z"
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "email": "jane.smith@example.com",
        "name": "Jane Smith",
        "phone": "+1-555-0200",
        "total_orders": 2,
        "total_spent": 449.98,
        "loyalty_tier": "silver",
        "created_at": "2026-01-10T00:00:00Z"
    }
}

MOCK_PRODUCTS = [
    {
        "product_id": "PROD-001",
        "name": "Widget Pro",
        "description": "Professional-grade widget for all your needs",
        "price": 49.99,
        "currency": "USD",
        "category": "Electronics",
        "tags": ["widget", "professional", "electronics"],
        "inventory": 150,
        "rating": 4.5
    },
    {
        "product_id": "PROD-002",
        "name": "Widget Cable",
        "description": "High-quality cable for widget connectivity",
        "price": 49.99,
        "currency": "USD",
        "category": "Accessories",
        "tags": ["cable", "accessory", "connectivity"],
        "inventory": 200,
        "rating": 4.2
    },
    {
        "product_id": "PROD-003",
        "name": "Premium Widget",
        "description": "Top-tier widget with advanced features",
        "price": 299.99,
        "currency": "USD",
        "category": "Electronics",
        "tags": ["widget", "premium", "advanced"],
        "inventory": 50,
        "rating": 4.8
    },
    {
        "product_id": "PROD-004",
        "name": "Widget Starter Kit",
        "description": "Everything you need to get started with widgets",
        "price": 99.99,
        "currency": "USD",
        "category": "Kits",
        "tags": ["widget", "starter", "kit", "bundle"],
        "inventory": 75,
        "rating": 4.6
    }
]


class EcommerceServer(BaseMCPServer):
    """
    MCP server for e-commerce operations.

    Provides tools for:
    - Order lookup and management
    - Customer information retrieval
    - Product search
    - Inventory checks
    - Refund request creation (CRITICAL: creates pending_approval only)

    CRITICAL: This server NEVER directly executes refunds.
    All refund requests go through the approval workflow.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize E-commerce server.

        Args:
            config: Optional server configuration
        """
        super().__init__("ecommerce-server", config)
        self._orders = dict(MOCK_ORDERS)
        self._customers = dict(MOCK_CUSTOMERS)
        self._products = list(MOCK_PRODUCTS)
        self._pending_refunds: Dict[str, Dict[str, Any]] = {}

    def _register_tools(self) -> None:
        """Register all e-commerce tools."""
        self.register_tool(
            name="get_order",
            description="Retrieve order details by order ID",
            parameters_schema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to look up"
                    }
                },
                "required": ["order_id"]
            },
            handler=self._handle_get_order
        )

        self.register_tool(
            name="get_customer",
            description="Retrieve customer details by customer ID",
            parameters_schema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "The customer ID to look up"
                    }
                },
                "required": ["customer_id"]
            },
            handler=self._handle_get_customer
        )

        self.register_tool(
            name="search_products",
            description="Search products by query string",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for products"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10
                    }
                },
                "required": ["query"]
            },
            handler=self._handle_search_products
        )

        self.register_tool(
            name="get_inventory",
            description="Get inventory status for products",
            parameters_schema={
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Optional product ID for specific inventory"
                    }
                },
                "required": []
            },
            handler=self._handle_get_inventory
        )

        self.register_tool(
            name="create_refund_request",
            description="Create a pending refund request for approval. "
                        "CRITICAL: This does NOT execute the refund directly.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to refund"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Refund amount"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the refund request"
                    }
                },
                "required": ["order_id", "amount", "reason"]
            },
            handler=self._handle_create_refund_request
        )

    async def _handle_get_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_order tool call.

        Args:
            params: Tool parameters containing order_id

        Returns:
            Order details or error
        """
        order_id = params["order_id"]
        order = self._orders.get(order_id)

        if not order:
            logger.warning({
                "event": "order_not_found",
                "order_id": order_id
            })
            return {
                "status": "error",
                "message": f"Order '{order_id}' not found"
            }

        logger.info({
            "event": "order_retrieved",
            "order_id": order_id,
            "customer_id": order["customer_id"]
        })

        return {
            "status": "success",
            "order": order
        }

    async def _handle_get_customer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_customer tool call.

        Args:
            params: Tool parameters containing customer_id

        Returns:
            Customer details or error
        """
        customer_id = params["customer_id"]
        customer = self._customers.get(customer_id)

        if not customer:
            logger.warning({
                "event": "customer_not_found",
                "customer_id": customer_id
            })
            return {
                "status": "error",
                "message": f"Customer '{customer_id}' not found"
            }

        logger.info({
            "event": "customer_retrieved",
            "customer_id": customer_id
        })

        return {
            "status": "success",
            "customer": customer
        }

    async def _handle_search_products(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle search_products tool call.

        Args:
            params: Tool parameters containing query and optional limit

        Returns:
            List of matching products
        """
        query = params["query"].lower()
        limit = params.get("limit", 10)

        matching_products = []
        for product in self._products:
            # Search in name, description, category, and tags
            search_text = " ".join([
                product["name"].lower(),
                product["description"].lower(),
                product["category"].lower(),
                " ".join(product["tags"])
            ])

            if query in search_text:
                matching_products.append(product)

        results = matching_products[:limit]

        logger.info({
            "event": "products_searched",
            "query": query,
            "results_count": len(results)
        })

        return {
            "status": "success",
            "products": results,
            "total_found": len(matching_products),
            "returned": len(results)
        }

    async def _handle_get_inventory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_inventory tool call.

        Args:
            params: Tool parameters containing optional product_id

        Returns:
            Inventory information
        """
        product_id = params.get("product_id")

        if product_id:
            # Get inventory for specific product
            product = next(
                (p for p in self._products if p["product_id"] == product_id),
                None
            )

            if not product:
                return {
                    "status": "error",
                    "message": f"Product '{product_id}' not found"
                }

            return {
                "status": "success",
                "inventory": {
                    "product_id": product_id,
                    "name": product["name"],
                    "available": product["inventory"],
                    "status": "in_stock" if product["inventory"] > 0 else "out_of_stock"
                }
            }

        # Get inventory for all products
        inventory_list = [
            {
                "product_id": p["product_id"],
                "name": p["name"],
                "available": p["inventory"],
                "status": "in_stock" if p["inventory"] > 0 else "out_of_stock"
            }
            for p in self._products
        ]

        return {
            "status": "success",
            "inventory": inventory_list,
            "total_products": len(inventory_list)
        }

    async def _handle_create_refund_request(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle create_refund_request tool call.

        CRITICAL: This method ONLY creates a pending_approval record.
        It NEVER directly executes a refund. The actual refund
        must be processed through the approval workflow.

        Args:
            params: Tool parameters containing order_id, amount, reason

        Returns:
            Pending refund request details
        """
        order_id = params["order_id"]
        amount = params["amount"]
        reason = params["reason"]

        # Verify order exists
        order = self._orders.get(order_id)
        if not order:
            return {
                "status": "error",
                "message": f"Order '{order_id}' not found"
            }

        # Validate amount
        if amount <= 0:
            return {
                "status": "error",
                "message": "Refund amount must be greater than zero"
            }

        if amount > order["total"]:
            return {
                "status": "error",
                "message": f"Refund amount {amount} exceeds order total {order['total']}"
            }

        # Generate approval ID
        approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"

        # Create pending approval record
        refund_request = {
            "approval_id": approval_id,
            "order_id": order_id,
            "customer_id": order["customer_id"],
            "amount": amount,
            "currency": order["currency"],
            "reason": reason,
            "status": "pending_approval",  # CRITICAL: Always pending
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved_at": None,
            "approved_by": None
        }

        self._pending_refunds[approval_id] = refund_request

        # Log the refund request creation (audit trail)
        logger.info({
            "event": "refund_request_created",
            "approval_id": approval_id,
            "order_id": order_id,
            "amount": amount,
            "status": "pending_approval",
            "note": "Refund requires approval - NOT executed directly"
        })

        return {
            "status": "success",
            "message": "Refund request created - pending approval",
            "refund_request": refund_request,
            "important": "This refund has NOT been executed. "
                        "It requires approval before processing."
        }

    def get_pending_refund(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a pending refund request by approval ID.

        Args:
            approval_id: The approval ID to look up

        Returns:
            Refund request or None
        """
        return self._pending_refunds.get(approval_id)
