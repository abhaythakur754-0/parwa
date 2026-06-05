"""
PARWA Day 4 — Unit Tests for ShopifyClient

Tests the ShopifyClient REST API wrapper with mocked HTTP responses.
Covers all API methods, error handling, rate limiting, retries,
webhook verification, and pagination.

Run: pytest tests/unit/test_shopify_client.py -v
"""

import base64
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Import the client
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.clients.shopify_client import (
    ShopifyClient,
    ShopifyResult,
    ShopifyError,
    ShopifyAuthError,
    ShopifyRateLimitError,
    ShopifyNotFoundError,
    create_shopify_client_from_config,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    """Create a ShopifyClient for testing."""
    return ShopifyClient(
        shop_domain="test-store.myshopify.com",
        access_token="shpat_test_token_123",
    )


@pytest.fixture
def mock_response_200():
    """Create a mock 200 response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.headers = {}
    return response


@pytest.fixture
def mock_response_201():
    """Create a mock 201 response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 201
    response.headers = {}
    return response


# ═══════════════════════════════════════════════════════════════════
# Test: Client Initialization
# ═══════════════════════════════════════════════════════════════════

class TestShopifyClientInit:
    """Tests for ShopifyClient initialization."""

    def test_basic_init(self, client):
        assert client.shop_domain == "test-store.myshopify.com"
        assert client.access_token == "shpat_test_token_123"
        assert client.api_version == "2024-01"
        assert client.base_url == "https://test-store.myshopify.com/admin/api/2024-01"

    def test_shop_domain_normalization(self):
        """Shop domain should be normalized (no https, no trailing slash)."""
        c = ShopifyClient(
            shop_domain="https://MyStore.myshopify.com/",
            access_token="token",
        )
        assert c.shop_domain == "MyStore.myshopify.com"
        assert "https://" not in c.shop_domain
        assert not c.shop_domain.endswith("/")

    def test_custom_api_version(self):
        c = ShopifyClient("test.myshopify.com", "token", api_version="2025-01")
        assert c.api_version == "2025-01"
        assert "2025-01" in c.base_url

    def test_custom_timeout(self):
        c = ShopifyClient("test.myshopify.com", "token", timeout=60)
        assert c.timeout == 60

    def test_custom_max_retries(self):
        c = ShopifyClient("test.myshopify.com", "token", max_retries=5)
        assert c.max_retries == 5


class TestShopifyClientHeaders:
    """Tests for request headers."""

    def test_get_headers(self, client):
        headers = client._get_headers()
        assert headers["X-Shopify-Access-Token"] == "shpat_test_token_123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"


# ═══════════════════════════════════════════════════════════════════
# Test: ShopifyResult
# ═══════════════════════════════════════════════════════════════════

class TestShopifyResult:
    """Tests for ShopifyResult wrapper."""

    def test_success_result(self):
        result = ShopifyResult(success=True, data={"id": 123}, status_code=200)
        assert result.success is True
        assert result.data == {"id": 123}
        assert result.error == ""
        assert result.status_code == 200

    def test_error_result(self):
        result = ShopifyResult(success=False, error="Not found", status_code=404)
        assert result.success is False
        assert result.error == "Not found"
        assert result.status_code == 404

    def test_to_dict(self):
        result = ShopifyResult(
            success=True,
            data={"order_id": "123"},
            status_code=200,
            metadata={"attempt": 1},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"]["order_id"] == "123"
        assert d["metadata"]["attempt"] == 1

    def test_default_values(self):
        result = ShopifyResult(success=True)
        assert result.data == {}
        assert result.metadata == {}
        assert result.error == ""
        assert result.status_code == 0


# ═══════════════════════════════════════════════════════════════════
# Test: Order API
# ═══════════════════════════════════════════════════════════════════

class TestOrderAPI:
    """Tests for Shopify order API methods."""

    @pytest.mark.asyncio
    async def test_get_order_success(self, client):
        """get_order should return order data on 200."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "order": {
                "id": 12345,
                "email": "buyer@example.com",
                "total_price": "99.99",
                "currency": "USD",
                "financial_status": "paid",
                "fulfillment_status": "fulfilled",
                "line_items": [],
            }
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_order("12345")

        assert result.success is True
        assert result.data["id"] == 12345
        assert result.data["email"] == "buyer@example.com"

    @pytest.mark.asyncio
    async def test_get_order_not_found(self, client):
        """get_order should return error on 404."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 404
        mock_resp.headers = {}
        mock_resp.text = "Not found"

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_order("99999")

        assert result.success is False
        assert result.status_code == 404
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_orders_success(self, client):
        """list_orders should return list of orders on 200."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "orders": [
                {"id": 1, "email": "a@test.com", "total_price": "10.00"},
                {"id": 2, "email": "b@test.com", "total_price": "20.00"},
            ]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.list_orders(status="any", limit=50)

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_count_orders(self, client):
        """count_orders should return count on 200."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {"count": 42}
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.count_orders()

        assert result.success is True
        assert result.data["count"] == 42

    @pytest.mark.asyncio
    async def test_update_order(self, client):
        """update_order should PUT and return updated order."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "order": {"id": 12345, "note": "Updated by PARWA"}
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.update_order("12345", {"note": "Updated by PARWA"})

        assert result.success is True
        assert result.data["note"] == "Updated by PARWA"

    @pytest.mark.asyncio
    async def test_close_order(self, client):
        """close_order should POST to /close endpoint."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "order": {"id": 12345, "closed_at": "2026-01-01T00:00:00Z"}
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.close_order("12345")

        assert result.success is True
        assert result.data["id"] == 12345

    @pytest.mark.asyncio
    async def test_cancel_order(self, client):
        """cancel_order should POST to /cancel endpoint."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "order": {"id": 12345, "cancelled_at": "2026-01-01T00:00:00Z"}
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.cancel_order("12345", reason="customer")

        assert result.success is True


# ═══════════════════════════════════════════════════════════════════
# Test: Product API
# ═══════════════════════════════════════════════════════════════════

class TestProductAPI:
    """Tests for Shopify product API methods."""

    @pytest.mark.asyncio
    async def test_get_product_success(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "product": {"id": 100, "title": "Widget", "vendor": "ACME", "status": "active"}
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_product("100")

        assert result.success is True
        assert result.data["title"] == "Widget"

    @pytest.mark.asyncio
    async def test_list_products_success(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "products": [
                {"id": 1, "title": "Product A"},
                {"id": 2, "title": "Product B"},
            ]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.list_products()

        assert result.success is True
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_search_products(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "products": [{"id": 1, "title": "Red Widget"}]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.search_products("red widget")

        assert result.success is True
        assert len(result.data) == 1

    @pytest.mark.asyncio
    async def test_count_products(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {"count": 15}
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.count_products()

        assert result.success is True
        assert result.data["count"] == 15


# ═══════════════════════════════════════════════════════════════════
# Test: Customer API
# ═══════════════════════════════════════════════════════════════════

class TestCustomerAPI:
    """Tests for Shopify customer API methods."""

    @pytest.mark.asyncio
    async def test_get_customer(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "customer": {"id": 500, "email": "alice@example.com", "first_name": "Alice"}
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_customer("500")

        assert result.success is True
        assert result.data["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_list_customers(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "customers": [
                {"id": 1, "email": "a@test.com"},
                {"id": 2, "email": "b@test.com"},
            ]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.list_customers()

        assert result.success is True
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_search_customers(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "customers": [{"id": 1, "email": "alice@example.com"}]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.search_customers("alice")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_customer_orders(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "orders": [{"id": 100, "total_price": "50.00"}]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_customer_orders("500")

        assert result.success is True
        assert len(result.data) == 1


# ═══════════════════════════════════════════════════════════════════
# Test: Fulfillment API
# ═══════════════════════════════════════════════════════════════════

class TestFulfillmentAPI:
    """Tests for Shopify fulfillment API methods."""

    @pytest.mark.asyncio
    async def test_list_fulfillments(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "fulfillments": [{"id": 1, "status": "pending"}]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.list_fulfillments("12345")

        assert result.success is True
        assert len(result.data) == 1

    @pytest.mark.asyncio
    async def test_create_fulfillment(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 201
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "fulfillment": {
                "id": 1,
                "status": "pending",
                "tracking_number": "1Z999AA10123456784",
                "tracking_url": "https://ups.com/track?id=1Z999",
            }
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.create_fulfillment(
                order_id="12345",
                tracking_number="1Z999AA10123456784",
                tracking_url="https://ups.com/track?id=1Z999",
                tracking_company="UPS",
            )

        assert result.success is True
        assert result.data["tracking_number"] == "1Z999AA10123456784"

    @pytest.mark.asyncio
    async def test_update_fulfillment(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "fulfillment": {
                "id": 1,
                "tracking_number": "1Z999AA999999999",
            }
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.update_fulfillment(
                fulfillment_id="1",
                order_id="12345",
                tracking_number="1Z999AA999999999",
            )

        assert result.success is True


# ═══════════════════════════════════════════════════════════════════
# Test: Refund API
# ═══════════════════════════════════════════════════════════════════

class TestRefundAPI:
    """Tests for Shopify refund API methods."""

    @pytest.mark.asyncio
    async def test_list_refunds(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "refunds": [{"id": 1, "note": "Customer return"}]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.list_refunds("12345")

        assert result.success is True
        assert len(result.data) == 1

    @pytest.mark.asyncio
    async def test_create_refund(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 201
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "refund": {
                "id": 10,
                "note": "Product defective",
                "transactions": [{"amount": "49.99"}],
            }
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.create_refund(
                order_id="12345",
                note="Product defective",
            )

        assert result.success is True
        assert result.data["id"] == 10


# ═══════════════════════════════════════════════════════════════════
# Test: Error Handling
# ═══════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Tests for error handling and retry logic."""

    @pytest.mark.asyncio
    async def test_auth_error_401(self, client):
        """401 should return auth error without retrying."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.headers = {}
        mock_resp.text = "Unauthorized"

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_order("12345")

        assert result.success is False
        assert result.status_code == 401
        assert "authentication" in result.error.lower() or "auth" in result.error.lower()

    @pytest.mark.asyncio
    async def test_forbidden_error_403(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 403
        mock_resp.headers = {}
        mock_resp.text = "Access denied"

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_order("12345")

        assert result.success is False
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_server_error_retries(self, client):
        """500 errors should trigger retries."""
        mock_resp_500 = MagicMock(spec=httpx.Response)
        mock_resp_500.status_code = 500
        mock_resp_500.headers = {}
        mock_resp_500.text = "Internal Server Error"

        mock_resp_200 = MagicMock(spec=httpx.Response)
        mock_resp_200.status_code = 200
        mock_resp_200.headers = {}
        mock_resp_200.json.return_value = {"order": {"id": 1}}
        mock_resp_200.text = json.dumps(mock_resp_200.json.return_value)

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return mock_resp_500
            return mock_resp_200

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            # Override sleep to speed up test
            with patch("time.sleep"):
                result = await client.get_order("1")

        assert result.success is True
        assert call_count == 2  # First fails, second succeeds

    @pytest.mark.asyncio
    async def test_timeout_retries(self, client):
        """Timeout should trigger retries."""
        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.TimeoutException("Request timed out")
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 200
            mock_resp.headers = {}
            mock_resp.json.return_value = {"order": {"id": 1}}
            mock_resp.text = json.dumps(mock_resp.json.return_value)
            return mock_resp

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = mock_request
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with patch("time.sleep"):
                result = await client.get_order("1")

        assert result.success is True
        assert call_count == 3  # 2 timeouts + 1 success

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, client):
        """Should fail after max retries."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.headers = {}
        mock_resp.text = "Server Error"

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with patch("time.sleep"):
                result = await client.get_order("1")

        assert result.success is False
        assert "max retries" in result.error.lower() or "exceeded" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════
# Test: Webhook Verification
# ═══════════════════════════════════════════════════════════════════

class TestWebhookVerification:
    """Tests for HMAC-SHA256 webhook signature verification."""

    def test_valid_signature(self):
        """Correctly computed signature should verify."""
        secret = "my_webhook_secret"
        payload = b'{"id": 123, "email": "test@example.com"}'

        # Compute correct HMAC
        computed = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
        expected_header = base64.b64encode(computed).decode("utf-8")

        assert ShopifyClient.verify_webhook_signature(payload, expected_header, secret) is True

    def test_invalid_signature(self):
        """Wrong signature should fail verification."""
        payload = b'{"id": 123}'
        wrong_hmac = "dGVzdA=="  # base64 of "test" — definitely wrong

        assert ShopifyClient.verify_webhook_signature(payload, wrong_hmac, "secret") is False

    def test_empty_hmac_header(self):
        """Empty HMAC header should fail."""
        assert ShopifyClient.verify_webhook_signature(b"{}", "", "secret") is False

    def test_empty_secret(self):
        """Empty secret should fail."""
        assert ShopifyClient.verify_webhook_signature(b"{}", "dGVzdA==", "") is False

    def test_none_hmac_header(self):
        """None HMAC header should fail."""
        assert ShopifyClient.verify_webhook_signature(b"{}", None, "secret") is False

    def test_none_secret(self):
        """None secret should fail."""
        assert ShopifyClient.verify_webhook_signature(b"{}", "dGVzdA==", None) is False

    def test_tampered_payload(self):
        """Tampered payload should fail verification."""
        secret = "my_secret"
        original_payload = b'{"amount": 100}'
        computed = hmac.new(secret.encode("utf-8"), original_payload, hashlib.sha256).digest()
        valid_hmac = base64.b64encode(computed).decode("utf-8")

        # Tamper with payload
        tampered_payload = b'{"amount": 999}'

        assert ShopifyClient.verify_webhook_signature(tampered_payload, valid_hmac, secret) is False


# ═══════════════════════════════════════════════════════════════════
# Test: Shop Info & Webhook Management
# ═══════════════════════════════════════════════════════════════════

class TestShopInfo:
    """Tests for shop info and webhook management."""

    @pytest.mark.asyncio
    async def test_get_shop(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "shop": {"id": 1, "name": "My Store", "domain": "mystore.com", "email": "admin@mystore.com"}
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.get_shop()

        assert result.success is True
        assert result.data["name"] == "My Store"

    @pytest.mark.asyncio
    async def test_test_connection(self, client):
        """test_connection should return shop summary."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "shop": {
                "id": 1,
                "name": "My Store",
                "domain": "mystore.com",
                "email": "admin@mystore.com",
                "currency": "USD",
                "iana_timezone": "America/New_York",
            }
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.test_connection()

        assert result.success is True
        assert result.data["shop_name"] == "My Store"
        assert result.data["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_create_webhook(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 201
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "webhook": {"id": 999, "topic": "orders/create", "address": "https://parwa.io/webhooks/shopify"}
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.create_webhook(
                topic="orders/create",
                address="https://parwa.io/webhooks/shopify",
            )

        assert result.success is True
        assert result.data["topic"] == "orders/create"

    @pytest.mark.asyncio
    async def test_list_webhooks(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {
            "webhooks": [
                {"id": 1, "topic": "orders/create"},
                {"id": 2, "topic": "customers/create"},
            ]
        }
        mock_resp.text = json.dumps(mock_resp.json.return_value)

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.list_webhooks()

        assert result.success is True
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_delete_webhook(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {}
        mock_resp.text = "{}"

        with patch.object(httpx, "AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await client.delete_webhook("999")

        assert result.success is True


# ═══════════════════════════════════════════════════════════════════
# Test: Factory Function
# ═══════════════════════════════════════════════════════════════════

class TestFactoryFunction:
    """Tests for create_shopify_client_from_config factory."""

    def test_creates_client_from_config(self):
        config = {
            "shop_domain": "myshop.myshopify.com",
            "access_token": "shpat_test",
        }
        client = create_shopify_client_from_config(config)
        assert client.shop_domain == "myshop.myshopify.com"
        assert client.access_token == "shpat_test"

    def test_empty_config(self):
        config = {}
        client = create_shopify_client_from_config(config)
        assert client.shop_domain == ""
        assert client.access_token == ""


# ═══════════════════════════════════════════════════════════════════
# Test: Rate Limiting
# ═══════════════════════════════════════════════════════════════════

class TestRateLimiting:
    """Tests for rate limiting enforcement."""

    def test_enforce_rate_limit_waits(self, client):
        """Should wait between requests if too fast."""
        client._last_request_time = 0  # Force wait
        with patch("time.sleep") as mock_sleep:
            with patch("time.time", return_value=0.1):
                client._enforce_rate_limit()
            # Since last_request_time=0 and time.time()=0.1, elapsed=0.1 < 0.5, so sleep IS called
            mock_sleep.assert_called()

    def test_update_rate_limit_state(self, client):
        """Should parse X-Shopify-Shop-Api-Call-Limit header."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.headers = {"X-Shopify-Shop-Api-Call-Limit": "5/40"}

        client._update_rate_limit_state(mock_resp)
        assert client._request_count == 5
