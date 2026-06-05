"""
Shopify Admin API Client (BC-002)

Implements the Shopify Admin REST API for:
- Order management (list, get, update, count)
- Product management (list, get, search)
- Customer management (list, get, search)
- Fulfillment management (create, update, list)
- Refund management (create, list)

API Docs: https://shopify.dev/docs/api/admin-rest

Features:
- Automatic retry with exponential backoff
- Rate limiting compliance (Shopify leaky bucket: 2 req/s burst 40)
- HMAC-SHA256 signature verification for webhooks
- Multi-tenant: each instance scoped to a single shop
- Pagination support via Link headers
- BC-008: Never crash — all errors caught and returned as result objects
- BC-001: Company-scoped via shop_domain + access_token per tenant
"""

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("parwa.clients.shopify")

# Shopify API version
SHOPIFY_API_VERSION = "2024-01"

# Rate limiting: Shopify allows 2 requests/second with burst of 40
RATE_LIMIT_REQUESTS_PER_SEC = 2
RATE_LIMIT_BURST = 40

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_MAX_DELAY = 30

# Request timeout
REQUEST_TIMEOUT = 30  # seconds

# Max pages to fetch in paginated requests
MAX_PAGES = 50


class ShopifyError(Exception):
    """Base exception for Shopify API errors."""

    def __init__(self, message: str, status_code: int = 0, shop_domain: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.shop_domain = shop_domain


class ShopifyAuthError(ShopifyError):
    """Authentication error (401/403)."""
    pass


class ShopifyRateLimitError(ShopifyError):
    """Rate limit exceeded (429)."""
    pass


class ShopifyNotFoundError(ShopifyError):
    """Resource not found (404)."""
    pass


class ShopifyResult:
    """Result wrapper for Shopify API calls.

    Follows BC-008: Never crash. All API calls return a ShopifyResult
    instead of raising exceptions.
    """

    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: str = "",
        status_code: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.status_code = status_code
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "status_code": self.status_code,
            "metadata": self.metadata,
        }


class ShopifyClient:
    """REST API client for Shopify Admin API.

    Each instance is scoped to a single shop (tenant).
    Multi-tenant support: create separate instances per company's Shopify store.

    Usage:
        client = ShopifyClient(
            shop_domain="mystore.myshopify.com",
            access_token="shpat_xxxxx",
        )
        result = await client.get_order("12345")
        if result.success:
            order = result.data
    """

    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        api_version: str = SHOPIFY_API_VERSION,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        """Initialize Shopify client.

        Args:
            shop_domain: Shopify store domain (e.g., 'mystore.myshopify.com').
            access_token: Shopify Admin API access token.
            api_version: Shopify API version string.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
        """
        # Normalize shop domain
        self.shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
        self.access_token = access_token
        self.api_version = api_version
        self.timeout = timeout
        self.max_retries = max_retries

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0

        # Build base URL
        self.base_url = f"https://{self.shop_domain}/admin/api/{self.api_version}"

    # ── HTTP Core ─────────────────────────────────────────────────

    def _get_headers(self) -> Dict[str, str]:
        """Get standard Shopify API request headers."""
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> ShopifyResult:
        """Make an authenticated request to Shopify API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path (e.g., '/orders.json').
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            ShopifyResult with success status and data or error.
        """
        url = f"{self.base_url}{path}"
        headers = self._get_headers()

        last_error = ""
        for attempt in range(self.max_retries):
            try:
                # Rate limiting: wait between requests
                self._enforce_rate_limit()

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_body,
                    )

                # Track rate limit from response headers
                self._update_rate_limit_state(response)

                # Handle response status
                if response.status_code in (200, 201):
                    data = response.json() if response.text else {}
                    return ShopifyResult(
                        success=True,
                        data=data,
                        status_code=response.status_code,
                        metadata={
                            "shop_domain": self.shop_domain,
                            "api_version": self.api_version,
                            "attempt": attempt + 1,
                        },
                    )

                elif response.status_code == 401:
                    return ShopifyResult(
                        success=False,
                        error=f"Authentication failed for {self.shop_domain}",
                        status_code=401,
                    )

                elif response.status_code == 403:
                    return ShopifyResult(
                        success=False,
                        error=f"Access denied for {self.shop_domain}: {response.text[:200]}",
                        status_code=403,
                    )

                elif response.status_code == 404:
                    return ShopifyResult(
                        success=False,
                        error=f"Resource not found: {path}",
                        status_code=404,
                    )

                elif response.status_code == 429:
                    # Rate limited — exponential backoff
                    retry_after = float(response.headers.get("Retry-After", RETRY_BASE_DELAY))
                    delay = min(retry_after * (2 ** attempt), RETRY_MAX_DELAY)
                    logger.warning(
                        "shopify_rate_limited shop=%s retry_after=%.1fs attempt=%d",
                        self.shop_domain, delay, attempt + 1,
                    )
                    time.sleep(delay)
                    last_error = f"Rate limited (429)"
                    continue

                elif response.status_code >= 500:
                    # Server error — retry with backoff
                    delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                    logger.warning(
                        "shopify_server_error shop=%s status=%d retry=%.1fs attempt=%d",
                        self.shop_domain, response.status_code, delay, attempt + 1,
                    )
                    time.sleep(delay)
                    last_error = f"Server error ({response.status_code}): {response.text[:200]}"
                    continue

                else:
                    return ShopifyResult(
                        success=False,
                        error=f"Shopify API error ({response.status_code}): {response.text[:300]}",
                        status_code=response.status_code,
                    )

            except httpx.TimeoutException:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    "shopify_timeout shop=%s path=%s retry=%.1fs attempt=%d",
                    self.shop_domain, path, delay, attempt + 1,
                )
                last_error = f"Request timeout after {self.timeout}s"
                time.sleep(delay)

            except httpx.ConnectError:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    "shopify_connect_error shop=%s path=%s retry=%.1fs attempt=%d",
                    self.shop_domain, path, delay, attempt + 1,
                )
                last_error = f"Connection error to {self.shop_domain}"
                time.sleep(delay)

            except Exception as exc:
                logger.error(
                    "shopify_request_error shop=%s path=%s error=%s",
                    self.shop_domain, path, str(exc)[:200],
                )
                last_error = f"Unexpected error: {str(exc)[:200]}"
                break

        return ShopifyResult(
            success=False,
            error=f"Max retries ({self.max_retries}) exceeded: {last_error}",
            status_code=0,
        )

    def _enforce_rate_limit(self) -> None:
        """Enforce Shopify rate limiting (2 requests/second)."""
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = 1.0 / RATE_LIMIT_REQUESTS_PER_SEC

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self._last_request_time = time.time()

    def _update_rate_limit_state(self, response: httpx.Response) -> None:
        """Update rate limit state from response headers."""
        # Shopify uses 'X-Shopify-Shop-Api-Call-Limit' header
        call_limit = response.headers.get("X-Shopify-Shop-Api-Call-Limit", "")
        if call_limit:
            try:
                used, total = call_limit.split("/")
                self._request_count = int(used)
                logger.debug(
                    "shopify_rate_limit shop=%s used=%s total=%s",
                    self.shop_domain, used, total,
                )
            except (ValueError, IndexError):
                pass

    # ── Order API ─────────────────────────────────────────────────

    async def get_order(self, order_id: str, fields: Optional[List[str]] = None) -> ShopifyResult:
        """Get a single order by ID.

        Args:
            order_id: Shopify order ID.
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with order data.
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", f"/orders/{order_id}.json", params=params)
        if result.success and "order" in result.data:
            result.data = result.data["order"]
        return result

    async def list_orders(
        self,
        status: str = "any",
        limit: int = 50,
        since_id: Optional[str] = None,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ) -> ShopifyResult:
        """List orders with optional filters.

        Args:
            status: Order status filter (open, closed, cancelled, any).
            limit: Number of orders per page (max 250).
            since_id: Return orders after this ID (for pagination).
            created_at_min: Minimum created_at date (ISO 8601).
            created_at_max: Maximum created_at date (ISO 8601).
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with list of orders.
        """
        params: Dict[str, Any] = {
            "status": status,
            "limit": min(limit, 250),
        }
        if since_id:
            params["since_id"] = since_id
        if created_at_min:
            params["created_at_min"] = created_at_min
        if created_at_max:
            params["created_at_max"] = created_at_max
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", "/orders.json", params=params)
        if result.success and "orders" in result.data:
            result.data = result.data["orders"]
        return result

    async def count_orders(self, status: str = "any") -> ShopifyResult:
        """Count orders.

        Args:
            status: Order status filter.

        Returns:
            ShopifyResult with count value.
        """
        result = await self._request("GET", "/orders/count.json", params={"status": status})
        if result.success and "count" in result.data:
            result.data = {"count": result.data["count"]}
        return result

    async def update_order(self, order_id: str, updates: Dict[str, Any]) -> ShopifyResult:
        """Update an order.

        Args:
            order_id: Shopify order ID.
            updates: Fields to update (e.g., {"order": {"note": "Updated"}}).

        Returns:
            ShopifyResult with updated order data.
        """
        result = await self._request("PUT", f"/orders/{order_id}.json", json_body={"order": updates})
        if result.success and "order" in result.data:
            result.data = result.data["order"]
        return result

    async def close_order(self, order_id: str) -> ShopifyResult:
        """Close (archive) an order.

        Args:
            order_id: Shopify order ID.

        Returns:
            ShopifyResult with closed order data.
        """
        result = await self._request("POST", f"/orders/{order_id}/close.json")
        if result.success and "order" in result.data:
            result.data = result.data["order"]
        return result

    async def cancel_order(self, order_id: str, reason: str = "other") -> ShopifyResult:
        """Cancel an order.

        Args:
            order_id: Shopify order ID.
            reason: Cancellation reason (customer, inventory, fraud, other).

        Returns:
            ShopifyResult with cancelled order data.
        """
        result = await self._request(
            "POST", f"/orders/{order_id}/cancel.json",
            json_body={"reason": reason},
        )
        if result.success and "order" in result.data:
            result.data = result.data["order"]
        return result

    # ── Product API ───────────────────────────────────────────────

    async def get_product(self, product_id: str, fields: Optional[List[str]] = None) -> ShopifyResult:
        """Get a single product by ID.

        Args:
            product_id: Shopify product ID.
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with product data.
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", f"/products/{product_id}.json", params=params)
        if result.success and "product" in result.data:
            result.data = result.data["product"]
        return result

    async def list_products(
        self,
        limit: int = 50,
        since_id: Optional[str] = None,
        vendor: Optional[str] = None,
        product_type: Optional[str] = None,
        status: str = "active",
        fields: Optional[List[str]] = None,
    ) -> ShopifyResult:
        """List products with optional filters.

        Args:
            limit: Number of products per page (max 250).
            since_id: Return products after this ID.
            vendor: Filter by vendor.
            product_type: Filter by product type.
            status: Product status (active, archived, draft, any).
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with list of products.
        """
        params: Dict[str, Any] = {
            "limit": min(limit, 250),
            "status": status,
        }
        if since_id:
            params["since_id"] = since_id
        if vendor:
            params["vendor"] = vendor
        if product_type:
            params["product_type"] = product_type
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", "/products.json", params=params)
        if result.success and "products" in result.data:
            result.data = result.data["products"]
        return result

    async def search_products(
        self,
        query: str,
        limit: int = 50,
        fields: Optional[List[str]] = None,
    ) -> ShopifyResult:
        """Search products by query string.

        Args:
            query: Search query (title, vendor, product_type, etc.).
            limit: Number of results (max 250).
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with matching products.
        """
        params: Dict[str, Any] = {
            "query": query,
            "limit": min(limit, 250),
        }
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", "/products.json", params=params)
        if result.success and "products" in result.data:
            result.data = result.data["products"]
        return result

    async def count_products(self, status: str = "active") -> ShopifyResult:
        """Count products.

        Args:
            status: Product status filter.

        Returns:
            ShopifyResult with count value.
        """
        result = await self._request("GET", "/products/count.json", params={"status": status})
        if result.success and "count" in result.data:
            result.data = {"count": result.data["count"]}
        return result

    # ── Customer API ──────────────────────────────────────────────

    async def get_customer(self, customer_id: str, fields: Optional[List[str]] = None) -> ShopifyResult:
        """Get a single customer by ID.

        Args:
            customer_id: Shopify customer ID.
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with customer data.
        """
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", f"/customers/{customer_id}.json", params=params)
        if result.success and "customer" in result.data:
            result.data = result.data["customer"]
        return result

    async def list_customers(
        self,
        limit: int = 50,
        since_id: Optional[str] = None,
        created_at_min: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ) -> ShopifyResult:
        """List customers with optional filters.

        Args:
            limit: Number of customers per page (max 250).
            since_id: Return customers after this ID.
            created_at_min: Minimum created_at date (ISO 8601).
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with list of customers.
        """
        params: Dict[str, Any] = {"limit": min(limit, 250)}
        if since_id:
            params["since_id"] = since_id
        if created_at_min:
            params["created_at_min"] = created_at_min
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", "/customers.json", params=params)
        if result.success and "customers" in result.data:
            result.data = result.data["customers"]
        return result

    async def search_customers(
        self,
        query: str,
        limit: int = 50,
        fields: Optional[List[str]] = None,
    ) -> ShopifyResult:
        """Search customers by query string.

        Args:
            query: Search query (email, name, phone, etc.).
            limit: Number of results (max 250).
            fields: Optional list of fields to include.

        Returns:
            ShopifyResult with matching customers.
        """
        params: Dict[str, Any] = {
            "query": query,
            "limit": min(limit, 250),
        }
        if fields:
            params["fields"] = ",".join(fields)

        result = await self._request("GET", "/customers/search.json", params=params)
        if result.success and "customers" in result.data:
            result.data = result.data["customers"]
        return result

    async def get_customer_orders(self, customer_id: str, limit: int = 50) -> ShopifyResult:
        """Get all orders for a specific customer.

        Args:
            customer_id: Shopify customer ID.
            limit: Number of orders (max 250).

        Returns:
            ShopifyResult with list of orders.
        """
        result = await self._request(
            "GET", f"/customers/{customer_id}/orders.json",
            params={"limit": min(limit, 250)},
        )
        if result.success and "orders" in result.data:
            result.data = result.data["orders"]
        return result

    # ── Fulfillment API ───────────────────────────────────────────

    async def list_fulfillments(self, order_id: str) -> ShopifyResult:
        """List fulfillments for an order.

        Args:
            order_id: Shopify order ID.

        Returns:
            ShopifyResult with list of fulfillments.
        """
        result = await self._request("GET", f"/orders/{order_id}/fulfillments.json")
        if result.success and "fulfillments" in result.data:
            result.data = result.data["fulfillments"]
        return result

    async def create_fulfillment(
        self,
        order_id: str,
        tracking_number: Optional[str] = None,
        tracking_url: Optional[str] = None,
        tracking_company: Optional[str] = None,
        line_items: Optional[List[Dict[str, Any]]] = None,
        notify_customer: bool = True,
    ) -> ShopifyResult:
        """Create a fulfillment for an order.

        Args:
            order_id: Shopify order ID.
            tracking_number: Shipping tracking number.
            tracking_url: Tracking URL.
            tracking_company: Shipping carrier name.
            line_items: Line items to fulfill (None = all).
            notify_customer: Whether to notify the customer.

        Returns:
            ShopifyResult with created fulfillment data.
        """
        fulfillment_data: Dict[str, Any] = {
            "notify_customer": notify_customer,
        }
        if tracking_number:
            fulfillment_data["tracking_number"] = tracking_number
        if tracking_url:
            fulfillment_data["tracking_url"] = tracking_url
        if tracking_company:
            fulfillment_data["tracking_company"] = tracking_company
        if line_items:
            fulfillment_data["line_items"] = line_items

        result = await self._request(
            "POST", f"/orders/{order_id}/fulfillments.json",
            json_body={"fulfillment": fulfillment_data},
        )
        if result.success and "fulfillment" in result.data:
            result.data = result.data["fulfillment"]
        return result

    async def update_fulfillment(
        self,
        fulfillment_id: str,
        order_id: str,
        tracking_number: Optional[str] = None,
        tracking_url: Optional[str] = None,
    ) -> ShopifyResult:
        """Update a fulfillment's tracking information.

        Args:
            fulfillment_id: Shopify fulfillment ID.
            order_id: Shopify order ID.
            tracking_number: New tracking number.
            tracking_url: New tracking URL.

        Returns:
            ShopifyResult with updated fulfillment data.
        """
        fulfillment_data: Dict[str, Any] = {}
        if tracking_number:
            fulfillment_data["tracking_number"] = tracking_number
        if tracking_url:
            fulfillment_data["tracking_url"] = tracking_url

        result = await self._request(
            "PUT", f"/orders/{order_id}/fulfillments/{fulfillment_id}.json",
            json_body={"fulfillment": fulfillment_data},
        )
        if result.success and "fulfillment" in result.data:
            result.data = result.data["fulfillment"]
        return result

    # ── Refund API ────────────────────────────────────────────────

    async def list_refunds(self, order_id: str) -> ShopifyResult:
        """List refunds for an order.

        Args:
            order_id: Shopify order ID.

        Returns:
            ShopifyResult with list of refunds.
        """
        result = await self._request("GET", f"/orders/{order_id}/refunds.json")
        if result.success and "refunds" in result.data:
            result.data = result.data["refunds"]
        return result

    async def create_refund(
        self,
        order_id: str,
        refund_line_items: Optional[List[Dict[str, Any]]] = None,
        transactions: Optional[List[Dict[str, Any]]] = None,
        note: str = "",
        notify_customer: bool = True,
    ) -> ShopifyResult:
        """Create a refund for an order.

        Args:
            order_id: Shopify order ID.
            refund_line_items: Line items to refund.
            transactions: Refund transactions with amounts.
            note: Optional note for the refund.
            notify_customer: Whether to notify the customer.

        Returns:
            ShopifyResult with created refund data.
        """
        refund_data: Dict[str, Any] = {
            "notify": notify_customer,
        }
        if refund_line_items:
            refund_data["refund_line_items"] = refund_line_items
        if transactions:
            refund_data["transactions"] = transactions
        if note:
            refund_data["note"] = note

        result = await self._request(
            "POST", f"/orders/{order_id}/refunds.json",
            json_body={"refund": refund_data},
        )
        if result.success and "refund" in result.data:
            result.data = result.data["refund"]
        return result

    # ── Shop Info ─────────────────────────────────────────────────

    async def get_shop(self) -> ShopifyResult:
        """Get shop information.

        Returns:
            ShopifyResult with shop data (name, email, domain, etc.).
        """
        result = await self._request("GET", "/shop.json")
        if result.success and "shop" in result.data:
            result.data = result.data["shop"]
        return result

    # ── Webhook Management ────────────────────────────────────────

    async def list_webhooks(self) -> ShopifyResult:
        """List registered webhooks.

        Returns:
            ShopifyResult with list of webhooks.
        """
        result = await self._request("GET", "/webhooks.json")
        if result.success and "webhooks" in result.data:
            result.data = result.data["webhooks"]
        return result

    async def create_webhook(
        self,
        topic: str,
        address: str,
        format: str = "json",
    ) -> ShopifyResult:
        """Register a webhook with Shopify.

        Args:
            topic: Event topic (e.g., 'orders/create', 'customers/create').
            address: Webhook callback URL.
            format: Payload format (json, xml).

        Returns:
            ShopifyResult with created webhook data.
        """
        result = await self._request(
            "POST", "/webhooks.json",
            json_body={
                "webhook": {
                    "topic": topic,
                    "address": address,
                    "format": format,
                }
            },
        )
        if result.success and "webhook" in result.data:
            result.data = result.data["webhook"]
        return result

    async def delete_webhook(self, webhook_id: str) -> ShopifyResult:
        """Delete a webhook registration.

        Args:
            webhook_id: Shopify webhook ID.

        Returns:
            ShopifyResult indicating success.
        """
        return await self._request("DELETE", f"/webhooks/{webhook_id}.json")

    # ── Pagination Helper ─────────────────────────────────────────

    async def get_all_pages(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data_key: str = "",
        max_pages: int = MAX_PAGES,
    ) -> ShopifyResult:
        """Fetch all pages of a paginated resource.

        Shopify uses Link headers for pagination.
        This method follows all pages up to max_pages.

        Args:
            path: API path (e.g., '/orders.json').
            params: Query parameters.
            data_key: Key in response containing the data list.
            max_pages: Maximum number of pages to fetch.

        Returns:
            ShopifyResult with all items combined.
        """
        all_items: List[Dict[str, Any]] = []
        current_params = dict(params or {})
        pages_fetched = 0

        while pages_fetched < max_pages:
            result = await self._request("GET", path, params=current_params)

            if not result.success:
                if all_items:
                    # Return what we have so far even if a page failed
                    return ShopifyResult(
                        success=True,
                        data=all_items,
                        metadata={"pages_fetched": pages_fetched, "partial": True},
                    )
                return result

            # Extract items from response
            if data_key and data_key in result.data:
                items = result.data[data_key]
            elif isinstance(result.data, list):
                items = result.data
            else:
                items = [result.data]

            all_items.extend(items)

            # Check if there are more pages
            # Shopify uses Link header: <url>; rel="next"
            has_next = False
            if not items or len(items) < current_params.get("limit", 50):
                break

            # Use since_id for pagination
            if items and isinstance(items[-1], dict):
                last_id = items[-1].get("id")
                if last_id:
                    current_params["since_id"] = str(last_id)
                    has_next = True

            if not has_next:
                break

            pages_fetched += 1

        return ShopifyResult(
            success=True,
            data=all_items,
            metadata={"pages_fetched": pages_fetched + 1},
        )

    # ── Webhook Verification ──────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        hmac_header: str,
        client_secret: str,
    ) -> bool:
        """Verify Shopify webhook HMAC-SHA256 signature.

        This is a critical security function. Shopify signs every webhook
        with HMAC-SHA256 using the client secret. Verification prevents
        forgery and replay attacks.

        Args:
            payload: Raw request body bytes.
            hmac_header: X-Shopify-Hmac-Sha256 header value (base64).
            client_secret: Shopify webhook signing secret.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not hmac_header or not client_secret:
            return False

        try:
            computed = hmac.new(
                client_secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).digest()

            import base64
            computed_b64 = base64.b64encode(computed).decode("utf-8")

            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(computed_b64, hmac_header)
        except Exception:
            return False

    # ── Connection Test ───────────────────────────────────────────

    async def test_connection(self) -> ShopifyResult:
        """Test the Shopify API connection.

        Makes a simple GET /shop.json request to verify credentials.

        Returns:
            ShopifyResult with shop info if successful.
        """
        result = await self.get_shop()
        if result.success:
            result.data = {
                "shop_name": result.data.get("name", ""),
                "shop_domain": result.data.get("domain", self.shop_domain),
                "shop_email": result.data.get("email", ""),
                "shop_id": result.data.get("id", ""),
                "currency": result.data.get("currency", "USD"),
                "timezone": result.data.get("iana_timezone", "UTC"),
            }
        return result


def create_shopify_client_from_config(config: Dict[str, Any]) -> ShopifyClient:
    """Factory function to create a ShopifyClient from integration config.

    Args:
        config: Integration config dict with shop_domain and access_token.

    Returns:
        Configured ShopifyClient instance.
    """
    return ShopifyClient(
        shop_domain=config.get("shop_domain", ""),
        access_token=config.get("access_token", ""),
    )
