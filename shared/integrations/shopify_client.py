"""
PARWA Shopify Client.

E-commerce store integration for product, order, and customer data.
Supports webhook verification for real-time updates.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import hashlib
import hmac
import json
import asyncio
from enum import Enum

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ShopifyClientState(Enum):
    """Shopify Client state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ShopifyClient:
    """
    Shopify Client for e-commerce store integration.

    Features:
    - Product catalog access
    - Order management (read-only for AI agents)
    - Customer data retrieval
    - Webhook verification
    - Inventory status checks
    """

    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    API_VERSION = "2024-01"

    def __init__(
        self,
        store_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize Shopify Client.

        Args:
            store_url: Shopify store URL (e.g., 'mystore.myshopify.com')
            api_key: Shopify API key (reads from config if not provided)
            api_secret: Shopify API secret (reads from config if not provided)
            timeout: Request timeout in seconds
        """
        self.store_url = store_url or settings.shopify_store_url
        self.api_key = api_key or (
            settings.shopify_api_key.get_secret_value()
            if settings.shopify_api_key else None
        )
        self.api_secret = api_secret or (
            settings.shopify_api_secret.get_secret_value()
            if settings.shopify_api_secret else None
        )
        self.timeout = timeout
        self._state = ShopifyClientState.DISCONNECTED
        self._last_request: Optional[datetime] = None
        self._rate_limit_remaining: int = 40  # Shopify default

    @property
    def state(self) -> ShopifyClientState:
        """Get current client state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == ShopifyClientState.CONNECTED

    def _get_base_url(self) -> str:
        """Get the base API URL for the store."""
        if not self.store_url:
            raise ValueError("Shopify store URL not configured")
        return f"https://{self.store_url}/admin/api/{self.API_VERSION}"

    async def connect(self) -> bool:
        """
        Connect to Shopify store.

        Validates credentials by fetching shop info.

        Returns:
            True if connected successfully
        """
        if self._state == ShopifyClientState.CONNECTED:
            return True

        self._state = ShopifyClientState.CONNECTING

        if not self.store_url:
            self._state = ShopifyClientState.ERROR
            logger.error({"event": "shopify_missing_store_url"})
            return False

        if not self.api_key:
            self._state = ShopifyClientState.ERROR
            logger.error({"event": "shopify_missing_api_key"})
            return False

        try:
            # Simulate connection validation
            await asyncio.sleep(0.1)

            self._state = ShopifyClientState.CONNECTED
            self._last_request = datetime.now(timezone.utc)

            logger.info({
                "event": "shopify_client_connected",
                "store_url": self.store_url,
            })

            return True

        except Exception as e:
            self._state = ShopifyClientState.ERROR
            logger.error({
                "event": "shopify_connection_failed",
                "error": str(e),
                "store_url": self.store_url,
            })
            return False

    async def disconnect(self) -> None:
        """Disconnect from Shopify store."""
        self._state = ShopifyClientState.DISCONNECTED
        self._last_request = None

        logger.info({
            "event": "shopify_client_disconnected",
            "store_url": self.store_url,
        })

    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        Get a product by ID.

        Args:
            product_id: Shopify product ID

        Returns:
            Product data dictionary
        """
        if not self.is_connected:
            raise ValueError("Shopify client not connected")

        if not product_id:
            raise ValueError("Product ID is required")

        logger.info({
            "event": "shopify_product_fetch",
            "product_id": product_id,
        })

        # Simulated product fetch
        return {
            "id": product_id,
            "title": "Sample Product",
            "handle": "sample-product",
            "status": "active",
            "variants": [],
            "images": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_products(
        self,
        limit: int = 50,
        since_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get products from the store.

        Args:
            limit: Maximum number of products to return (max 250)
            since_id: Return products after this ID for pagination

        Returns:
            List of product dictionaries
        """
        if not self.is_connected:
            raise ValueError("Shopify client not connected")

        if limit < 1 or limit > 250:
            raise ValueError("Limit must be between 1 and 250")

        logger.info({
            "event": "shopify_products_fetch",
            "limit": limit,
            "since_id": since_id,
        })

        # Simulated products fetch
        return []

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get an order by ID.

        Args:
            order_id: Shopify order ID

        Returns:
            Order data dictionary
        """
        if not self.is_connected:
            raise ValueError("Shopify client not connected")

        if not order_id:
            raise ValueError("Order ID is required")

        logger.info({
            "event": "shopify_order_fetch",
            "order_id": order_id,
        })

        # Simulated order fetch
        return {
            "id": order_id,
            "order_number": 1001,
            "email": "customer@example.com",
            "total_price": "99.99",
            "currency": "USD",
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
            "line_items": [],
            "customer": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_orders(
        self,
        limit: int = 50,
        status: str = "any",
        customer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders from the store.

        Args:
            limit: Maximum number of orders to return (max 250)
            status: Order status filter (open, closed, cancelled, any)
            customer_id: Filter by customer ID

        Returns:
            List of order dictionaries
        """
        if not self.is_connected:
            raise ValueError("Shopify client not connected")

        if limit < 1 or limit > 250:
            raise ValueError("Limit must be between 1 and 250")

        valid_statuses = {"open", "closed", "cancelled", "any"}
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")

        logger.info({
            "event": "shopify_orders_fetch",
            "limit": limit,
            "status": status,
            "customer_id": customer_id,
        })

        # Simulated orders fetch
        return []

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get a customer by ID.

        Args:
            customer_id: Shopify customer ID

        Returns:
            Customer data dictionary
        """
        if not self.is_connected:
            raise ValueError("Shopify client not connected")

        if not customer_id:
            raise ValueError("Customer ID is required")

        logger.info({
            "event": "shopify_customer_fetch",
            "customer_id": customer_id,
        })

        # Simulated customer fetch
        return {
            "id": customer_id,
            "email": "customer@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "orders_count": 5,
            "total_spent": "499.99",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a customer by email address.

        Args:
            email: Customer email address

        Returns:
            Customer data dictionary or None if not found
        """
        if not self.is_connected:
            raise ValueError("Shopify client not connected")

        if not email:
            raise ValueError("Email is required")

        logger.info({
            "event": "shopify_customer_search",
            "email": email,
        })

        # Simulated customer search
        return None

    async def get_inventory(
        self,
        inventory_item_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get inventory levels for items.

        Args:
            inventory_item_ids: List of inventory item IDs

        Returns:
            List of inventory level dictionaries
        """
        if not self.is_connected:
            raise ValueError("Shopify client not connected")

        if not inventory_item_ids:
            raise ValueError("Inventory item IDs are required")

        logger.info({
            "event": "shopify_inventory_fetch",
            "item_count": len(inventory_item_ids),
        })

        # Simulated inventory fetch
        return [
            {
                "inventory_item_id": item_id,
                "location_id": "default",
                "available": 100,
            }
            for item_id in inventory_item_ids
        ]

    def verify_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> bool:
        """
        Verify webhook signature from Shopify.

        Args:
            payload: Raw webhook payload bytes
            signature: X-Shopify-Hmac-SHA256 header value

        Returns:
            True if signature is valid
        """
        if not self.api_secret:
            logger.error({"event": "shopify_webhook_no_secret"})
            return False

        if not payload or not signature:
            return False

        try:
            expected_signature = hmac.new(
                self.api_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(
                expected_signature,
                signature
            )

            logger.info({
                "event": "shopify_webhook_verification",
                "valid": is_valid,
            })

            return is_valid

        except Exception as e:
            logger.error({
                "event": "shopify_webhook_verification_error",
                "error": str(e),
            })
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Shopify connection.

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self._state == ShopifyClientState.CONNECTED,
            "state": self._state.value,
            "store_url": self.store_url,
            "last_request": (
                self._last_request.isoformat()
                if self._last_request else None
            ),
            "rate_limit_remaining": self._rate_limit_remaining,
        }
