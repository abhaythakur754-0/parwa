"""
Shopify API Client (Day 1 — E-Commerce MCP Integration)

Implements the Shopify REST Admin API for:
- Order lookup and search
- Customer data retrieval
- Product search and inventory
- Refund initiation
- Fulfillment tracking

API Docs: https://shopify.dev/docs/api/admin-rest

Features:
- Automatic retry with exponential backoff
- Shopify rate limit handling (2 req/sec for basic, 4 req/sec for plus)
- Per-tenant configuration (shop_domain + access_token from integrations table)
- Request timeout with circuit breaker pattern
- Structured logging

Usage:
    client = ShopifyClient(shop_domain="mystore.myshopify.com", access_token="shpat_xxx")
    order = await client.get_order("1234")
    products = await client.search_products("blue shirt")
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlencode

import httpx

logger = logging.getLogger("parwa.clients.shopify")

# Shopify API version — update when Shopify releases new stable versions
SHOPIFY_API_VERSION = "2024-01"

# Rate limiting: Shopify allows 2 requests/sec (basic), 4 req/sec (plus)
RATE_LIMIT_REQUESTS = 2
RATE_LIMIT_WINDOW = 1.0  # seconds

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_MAX_DELAY = 30

# Request timeout
REQUEST_TIMEOUT = 30.0
CONNECT_TIMEOUT = 10.0


class ShopifyError(Exception):
    """Base exception for Shopify API errors."""
    pass


class ShopifyAuthError(ShopifyError):
    """Authentication error (401/403)."""
    pass


class ShopifyRateLimitError(ShopifyError):
    """Rate limit exceeded (429)."""
    pass


class ShopifyNotFoundError(ShopifyError):
    """Resource not found (404)."""
    pass


class ShopifyValidationError(ShopifyError):
    """Validation error (400/422)."""
    pass


class ShopifyClient:
    """
    Shopify REST Admin API Client for e-commerce integrations.

    Multi-tenant: Each client instance is initialized with a specific
    tenant's shop_domain and access_token from the integrations table.

    Usage:
        client = ShopifyClient(shop_domain="mystore.myshopify.com", access_token="shpat_xxx")
        order = await client.get_order("1234")
    """

    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        api_version: str = SHOPIFY_API_VERSION,
    ):
        # Clean shop domain (strip https://, trailing slashes)
        self.shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{self.shop_domain}/admin/api/{api_version}/"

        # Rate limiting state
        self._request_times: List[float] = []
        self._rate_limit_wait: float = 0

        # HTTP client (created lazily)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT),
                headers={
                    "X-Shopify-Access-Token": self.access_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _check_rate_limit(self) -> None:
        """Check and enforce Shopify rate limiting.

        Shopify basic: 2 requests/sec, Plus: 4 requests/sec.
        We use 2/sec as the safe default.
        """
        now = time.time()
        self._request_times = [
            t for t in self._request_times
            if now - t < RATE_LIMIT_WINDOW
        ]
        if len(self._request_times) >= RATE_LIMIT_REQUESTS:
            wait_time = RATE_LIMIT_WINDOW - (now - self._request_times[0]) + 0.1
            logger.debug("shopify_rate_limit_wait seconds=%.2f", wait_time)
            self._rate_limit_wait = wait_time
        else:
            self._rate_limit_wait = 0
        self._request_times.append(now)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to Shopify Admin API.

        Includes automatic retry with exponential backoff.
        All sleeps use asyncio.sleep() to avoid blocking the event loop.
        """
        self._check_rate_limit()

        # Async rate limit wait (non-blocking)
        if self._rate_limit_wait > 0:
            await asyncio.sleep(self._rate_limit_wait)
            self._rate_limit_wait = 0

        url = urljoin(self.base_url, endpoint)
        client = await self._get_client()

        last_error: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(method, url, **kwargs)

                # Success
                if response.status_code < 400:
                    return response.json()

                # Handle specific errors
                if response.status_code == 401:
                    raise ShopifyAuthError("Invalid Shopify access token")
                if response.status_code == 403:
                    raise ShopifyAuthError("Shopify API access forbidden — check scopes")
                if response.status_code == 404:
                    raise ShopifyNotFoundError(f"Shopify resource not found: {endpoint}")
                if response.status_code == 422:
                    error_data = response.json()
                    errors = error_data.get("errors", {})
                    raise ShopifyValidationError(
                        f"Shopify validation error: {json.dumps(errors)[:500]}"
                    )
                if response.status_code == 429:
                    # Shopify rate limit — retry after suggested time
                    retry_after = float(response.headers.get("Retry-After", RETRY_BASE_DELAY))
                    logger.warning("shopify_rate_limited retry_after=%.1f", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                # Other errors — retry for 5xx
                if response.status_code >= 500:
                    last_error = ShopifyError(f"Shopify server error: {response.status_code}")
                else:
                    last_error = ShopifyError(
                        f"Shopify API error: {response.status_code} — {response.text[:300]}"
                    )

            except httpx.TimeoutException as e:
                last_error = ShopifyError(f"Shopify request timeout: {e}")
            except httpx.RequestError as e:
                last_error = ShopifyError(f"Shopify request failed: {e}")

            # Exponential backoff before retry (non-blocking)
            if attempt < MAX_RETRIES - 1:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    "shopify_retry attempt=%d delay=%d error=%s",
                    attempt + 1,
                    delay,
                    str(last_error),
                )
                await asyncio.sleep(delay)

        raise last_error or ShopifyError("Unknown Shopify API error")

    # ── Order Methods ─────────────────────────────────────────────────

    async def get_order(self, order_id: str, *, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get order details by ID.

        API: GET /orders/{order_id}.json

        Args:
            order_id: Shopify order ID (e.g., "1234567890")
            fields: Optional list of fields to include (reduces response size)

        Returns:
            Dict with full order data including:
            - id, order_number, email, created_at
            - total_price, subtotal_price, currency
            - financial_status, fulfillment_status
            - line_items, customer, shipping_address, billing_address
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", f"orders/{order_id}.json", params=params)
        return result.get("order", result)

    async def list_orders(
        self,
        *,
        status: str = "any",
        limit: int = 50,
        since_id: Optional[str] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        financial_status: Optional[str] = None,
        fulfillment_status: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List orders with optional filters.

        API: GET /orders.json

        Args:
            status: "open", "closed", "cancelled", "any" (default: "any")
            limit: Max orders to return (1-250, default 50)
            since_id: Return orders after this ID (for pagination)
            created_at_min: Min created date (ISO 8601)
            created_at_max: Max created date (ISO 8601)
            financial_status: "pending", "authorized", "partially_paid", "paid",
                             "partially_refunded", "refunded", "voided"
            fulfillment_status: "shipped", "partial", "unshipped", "any"
            email: Filter by customer email

        Returns:
            Dict with "orders" key containing list of order objects
        """
        params: Dict[str, Any] = {"status": status, "limit": min(limit, 250)}
        if since_id:
            params["since_id"] = since_id
        if created_at_min:
            params["created_at_min"] = created_at_min
        if created_at_max:
            params["created_at_max"] = created_at_max
        if financial_status:
            params["financial_status"] = financial_status
        if fulfillment_status:
            params["fulfillment_status"] = fulfillment_status
        if email:
            params["email"] = email

        return await self._request("GET", "orders.json", params=params)

    async def get_order_by_name(self, order_name: str) -> Dict[str, Any]:
        """
        Look up an order by its order number (e.g., "#1001").

        API: GET /orders.json?name={order_name}

        Args:
            order_name: Order number as shown to customer (e.g., "#1001" or "1001")

        Returns:
            First matching order dict, or empty dict if not found
        """
        # Shopify allows searching by name
        params = {"name": order_name, "limit": 1}
        result = await self._request("GET", "orders.json", params=params)
        orders = result.get("orders", [])
        return orders[0] if orders else {}

    # ── Customer Methods ──────────────────────────────────────────────

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer details by ID.

        API: GET /customers/{customer_id}.json

        Returns:
            Dict with customer data: id, email, first_name, last_name,
            phone, orders_count, total_spent, addresses, etc.
        """
        result = await self._request("GET", f"customers/{customer_id}.json")
        return result.get("customer", result)

    async def search_customers(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Search customers by query.

        API: GET /customers/search.json?query={query}

        Args:
            query: Search query (e.g., "email:john@example.com" or "john")
            limit: Max results (1-250, default 50)

        Returns:
            Dict with "customers" key containing list of customer objects
        """
        params: Dict[str, Any] = {"query": query, "limit": min(limit, 250)}
        return await self._request("GET", "customers/search.json", params=params)

    async def get_customer_orders(
        self,
        customer_id: str,
        *,
        status: str = "any",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get all orders for a specific customer.

        API: GET /customers/{customer_id}/orders.json

        Args:
            customer_id: Shopify customer ID
            status: Order status filter (default: "any")
            limit: Max orders to return (1-250)

        Returns:
            Dict with "orders" key containing list of order objects
        """
        params: Dict[str, Any] = {"status": status, "limit": min(limit, 250)}
        return await self._request(
            "GET", f"customers/{customer_id}/orders.json", params=params
        )

    # ── Product Methods ───────────────────────────────────────────────

    async def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        Get product details by ID.

        API: GET /products/{product_id}.json

        Returns:
            Dict with product data: id, title, body_html, vendor,
            product_type, variants, images, options, status, etc.
        """
        result = await self._request("GET", f"products/{product_id}.json")
        return result.get("product", result)

    async def search_products(
        self,
        query: str,
        *,
        limit: int = 10,
        collection_id: Optional[str] = None,
        product_type: Optional[str] = None,
        vendor: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Any]:
        """
        Search products by query string.

        API: GET /products.json with filters

        Note: Shopify REST API doesn't have a full-text product search
        endpoint like the GraphQL API. This filters by title, product_type,
        vendor, and collection_id. For full-text search, use the
        Shopify GraphQL API (future enhancement).

        Args:
            query: Search query (filters by title containing this string)
            limit: Max products to return (1-250, default 10)
            collection_id: Filter by collection
            product_type: Filter by product type
            vendor: Filter by vendor
            status: "active", "archived", "draft" (default: "active")

        Returns:
            Dict with "products" key containing list of product objects
        """
        params: Dict[str, Any] = {
            "limit": min(limit, 250),
            "status": status,
        }
        if collection_id:
            params["collection_id"] = collection_id
        if product_type:
            params["product_type"] = product_type
        if vendor:
            params["vendor"] = vendor

        result = await self._request("GET", "products.json", params=params)

        # Client-side title filtering since Shopify REST doesn't support
        # full-text product search
        products = result.get("products", [])
        if query:
            query_lower = query.lower()
            products = [
                p for p in products
                if query_lower in (p.get("title", "")).lower()
                or query_lower in (p.get("body_html", "")).lower()
                or any(query_lower in v.get("sku", "").lower() for v in p.get("variants", []))
            ]
            result["products"] = products

        return result

    async def get_product_inventory(self, product_id: str) -> Dict[str, Any]:
        """
        Get inventory levels for a product's variants.

        API: GET /products/{product_id}.json (includes variants with inventory)

        Returns:
            Dict with inventory data per variant:
            - variant_id, sku, title, available, inventory_quantity,
              inventory_policy, old_inventory_quantity
        """
        result = await self.get_product(product_id)
        variants = result.get("variants", [])

        inventory_data = []
        for variant in variants:
            inventory_data.append({
                "variant_id": variant.get("id"),
                "sku": variant.get("sku", ""),
                "title": variant.get("title", ""),
                "available": variant.get("available", False),
                "inventory_quantity": variant.get("inventory_quantity", 0),
                "inventory_policy": variant.get("inventory_policy", "deny"),
                "price": variant.get("price", "0.00"),
                "compare_at_price": variant.get("compare_at_price"),
                "grams": variant.get("grams", 0),
                "requires_shipping": variant.get("requires_shipping", True),
            })

        return {
            "product_id": product_id,
            "product_title": result.get("title", ""),
            "variants": inventory_data,
            "total_available": sum(
                1 for v in inventory_data if v["available"]
            ),
        }

    # ── Refund Methods ────────────────────────────────────────────────

    async def initiate_refund(
        self,
        order_id: str,
        *,
        refund_line_items: Optional[List[Dict[str, Any]]] = None,
        shipping: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        restock: bool = True,
    ) -> Dict[str, Any]:
        """
        Initiate a refund on a Shopify order.

        API: POST /orders/{order_id}/refunds.json

        PARWA never touches the money — Shopify processes the actual
        refund through the original payment method. This just tells
        Shopify to create the refund.

        Args:
            order_id: Shopify order ID
            refund_line_items: List of items to refund. Each item:
                - line_item_id: str (from order.line_items[].id)
                - quantity: int
                - restock_type: "no_restock", "cancel", "return" (default: "return")
                - amount: str (optional, for partial refund of item)
            shipping: Shipping refund amount: {"full_refund": True} or
                     {"amount": "5.00"}
            note: Optional refund note
            restock: Whether to restock items (default: True)

        Returns:
            Dict with refund data: id, order_id, created_at,
            refund_line_items, transactions, etc.
        """
        # First, get the order to build refund line items if not provided
        if refund_line_items is None:
            order = await self.get_order(order_id)
            refund_line_items = []
            for item in order.get("line_items", []):
                refund_line_items.append({
                    "line_item_id": item["id"],
                    "quantity": item.get("quantity", 1),
                    "restock_type": "return" if restock else "no_restock",
                })

        # Build refund payload
        refund_data: Dict[str, Any] = {
            "refund": {
                "shipping": shipping or {},
                "refund_line_items": refund_line_items,
            }
        }
        if note:
            refund_data["refund"]["note"] = note

        result = await self._request(
            "POST",
            f"orders/{order_id}/refunds.json",
            json=refund_data,
        )
        return result.get("refund", result)

    async def calculate_refund(
        self,
        order_id: str,
        *,
        refund_line_items: Optional[List[Dict[str, Any]]] = None,
        shipping: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate refund amounts without actually creating a refund.

        API: POST /orders/{order_id}/refunds/calculate.json

        Use this before initiate_refund to show the agent/user
        exactly how much will be refunded.

        Args:
            order_id: Shopify order ID
            refund_line_items: Items to calculate refund for
            shipping: Shipping refund details

        Returns:
            Dict with calculated refund amounts (no actual refund created)
        """
        if refund_line_items is None:
            order = await self.get_order(order_id)
            refund_line_items = []
            for item in order.get("line_items", []):
                refund_line_items.append({
                    "line_item_id": item["id"],
                    "quantity": item.get("quantity", 1),
                    "restock_type": "no_restock",  # Don't restock on calculate
                })

        refund_data: Dict[str, Any] = {
            "refund": {
                "shipping": shipping or {},
                "refund_line_items": refund_line_items,
            }
        }

        result = await self._request(
            "POST",
            f"orders/{order_id}/refunds/calculate.json",
            json=refund_data,
        )
        return result.get("refund", result)

    # ── Fulfillment Methods ───────────────────────────────────────────

    async def get_fulfillments(self, order_id: str) -> Dict[str, Any]:
        """
        Get fulfillments for an order (tracking info).

        API: GET /orders/{order_id}/fulfillments.json

        Returns:
            Dict with "fulfillments" key containing list with:
            - id, status, tracking_company, tracking_number, tracking_url,
              created_at, updated_at, line_items, etc.
        """
        result = await self._request(
            "GET", f"orders/{order_id}/fulfillments.json"
        )
        return result

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get comprehensive order status including fulfillment tracking.

        Combines order data with fulfillment data for a complete picture.

        Args:
            order_id: Shopify order ID

        Returns:
            Dict with:
            - order_id, order_number, status, financial_status, fulfillment_status
            - total_price, currency, created_at
            - tracking_numbers, tracking_urls, tracking_companies
            - estimated_delivery (if available)
        """
        order = await self.get_order(order_id, fields=[
            "id", "order_number", "email", "financial_status",
            "fulfillment_status", "total_price", "currency", "created_at",
            "fulfillments", "line_items",
        ])

        # Extract tracking info from fulfillments
        tracking_numbers = []
        tracking_urls = []
        tracking_companies = []
        for fulfillment in order.get("fulfillments", []):
            for tracking in fulfillment.get("tracking_numbers", []):
                tracking_numbers.append(tracking)
            for url in fulfillment.get("tracking_urls", []):
                tracking_urls.append(url)
            company = fulfillment.get("tracking_company", "")
            if company:
                tracking_companies.append(company)

        return {
            "order_id": str(order.get("id", "")),
            "order_number": order.get("order_number", ""),
            "email": order.get("email", ""),
            "financial_status": order.get("financial_status", ""),
            "fulfillment_status": order.get("fulfillment_status", "unfulfilled"),
            "total_price": order.get("total_price", "0.00"),
            "currency": order.get("currency", "USD"),
            "created_at": order.get("created_at", ""),
            "tracking_numbers": tracking_numbers,
            "tracking_urls": tracking_urls,
            "tracking_companies": tracking_companies,
            "item_count": len(order.get("line_items", [])),
        }

    # ── Shop Info ─────────────────────────────────────────────────────

    async def get_shop_info(self) -> Dict[str, Any]:
        """
        Get shop information (used for connection testing).

        API: GET /shop.json

        Returns:
            Dict with shop data: name, email, domain, currency, etc.
        """
        result = await self._request("GET", "shop.json")
        return result.get("shop", result)

    # ── Webhook Verification ──────────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        webhook_secret: str,
    ) -> bool:
        """
        Verify Shopify webhook signature using HMAC-SHA256.

        Shopify sends an X-Shopify-Hmac-Sha256 header with every webhook.
        The signature is Base64-encoded HMAC-SHA256 of the raw request body
        using the webhook secret as the key.

        Args:
            payload: Raw request body bytes
            signature: Value from 'X-Shopify-Hmac-Sha256' header
            webhook_secret: Shopify webhook shared secret

        Returns:
            True if signature is valid, False otherwise
        """
        if not webhook_secret:
            logger.warning("shopify_webhook_no_secret")
            return False

        try:
            expected = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256,
            ).digest()

            # Shopify sends Base64-encoded signature
            import base64
            expected_b64 = base64.b64encode(expected).decode()

            return hmac.compare_digest(expected_b64, signature)
        except Exception as exc:
            logger.warning("shopify_webhook_verify_error error=%s", str(exc))
            return False


# ── Tenant-Aware Client Factory ───────────────────────────────────────

# Cache of client instances per shop_domain
_client_cache: Dict[str, ShopifyClient] = {}


def get_shopify_client(shop_domain: str, access_token: str) -> ShopifyClient:
    """
    Get or create a ShopifyClient for a specific tenant.

    Uses a simple cache keyed by shop_domain. If the access_token
    changes (e.g., client re-authorizes), the old client is replaced.

    Args:
        shop_domain: Tenant's Shopify shop domain
        access_token: Tenant's Shopify access token

    Returns:
        ShopifyClient instance configured for this tenant
    """
    cache_key = shop_domain

    # Check if cached client exists and token matches
    if cache_key in _client_cache:
        client = _client_cache[cache_key]
        if client.access_token == access_token:
            return client

    # Create new client (token changed or first time)
    client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)
    _client_cache[cache_key] = client

    logger.info("shopify_client_created shop_domain=%s", shop_domain)

    return client


async def close_all_shopify_clients() -> None:
    """Close all cached Shopify clients (for shutdown)."""
    global _client_cache
    for client in _client_cache.values():
        await client.close()
    _client_cache = {}
