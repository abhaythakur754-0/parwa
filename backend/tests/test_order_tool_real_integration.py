"""
Tests for OrderTool real Shopify integration via ecommerce_client.

Verifies:
  1. When Shopify is connected → returns REAL order data (not mock)
  2. When Shopify is NOT connected → returns "not connected" error (not mock data)
  3. When order not found → returns "not found" error
  4. _list_orders returns real orders when connected
  5. _list_orders returns "not connected" when no integration

Run: pytest tests/test_order_tool_real_integration.py -v --tb=short
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub langgraph for imports
if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock


# ═══════════════════════════════════════════════════════════════════════
# Test 1: get_order returns real data when Shopify is connected
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_order_returns_real_data_when_connected():
    """When Shopify is connected, OrderTool._get_order must call the real
    Shopify API and return real order data — NOT mock data."""
    from app.core.react_tools.order_tool import OrderTool

    # Mock the ecommerce_client to return real order data
    real_order = {
        "order_id": "1234567890",
        "order_name": "#1001",
        "email": "customer@example.com",
        "created_at": "2026-07-10T10:00:00Z",
        "total_price": "199.00",
        "currency": "USD",
        "financial_status": "paid",
        "fulfillment_status": "fulfilled",
        "line_items": [{"title": "Annual Subscription", "quantity": 1, "price": "199.00"}],
        "customer": {"id": 987654, "email": "customer@example.com"},
    }

    with patch(
        "app.core.react_tools.ecommerce_client.fetch_real_order",
        new_callable=AsyncMock,
        return_value=real_order,
    ):
        with patch(
            "app.core.react_tools.ecommerce_client.is_connected",
            new_callable=AsyncMock,
            return_value=True,
        ):
            tool = OrderTool()
            result = await tool._get_order("tenant_123", order_id="1234567890")

    assert result.success is True
    assert result.data is not None
    assert result.data["order_id"] == "1234567890"
    assert result.data["total_price"] == "199.00"
    assert result.data["email"] == "customer@example.com"
    # Verify it's NOT mock data — mock data has different field names
    assert "mock" not in str(result.data).lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 2: get_order returns "not connected" when no Shopify integration
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_order_returns_not_connected_when_no_integration():
    """When Shopify is NOT connected, OrderTool must return an honest
    'not connected' error — NOT mock data."""
    from app.core.react_tools.order_tool import OrderTool

    with patch(
        "app.core.react_tools.ecommerce_client.fetch_real_order",
        new_callable=AsyncMock,
        return_value=None,  # No real data available
    ):
        with patch(
            "app.core.react_tools.ecommerce_client.is_connected",
            new_callable=AsyncMock,
            return_value=False,  # Not connected
        ):
            tool = OrderTool()
            result = await tool._get_order("tenant_123", order_id="any_order")

    assert result.success is False
    assert result.data is None
    assert "not connected" in result.error.lower()
    # CRITICAL: verify no mock data is returned
    assert result.data is None


# ═══════════════════════════════════════════════════════════════════════
# Test 3: get_order returns "not found" when connected but order doesn't exist
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_order_returns_not_found_when_order_missing():
    """When Shopify IS connected but the order ID doesn't exist,
    return 'not found' error — NOT mock data."""
    from app.core.react_tools.order_tool import OrderTool

    with patch(
        "app.core.react_tools.ecommerce_client.fetch_real_order",
        new_callable=AsyncMock,
        return_value=None,  # Order not found
    ):
        with patch(
            "app.core.react_tools.ecommerce_client.is_connected",
            new_callable=AsyncMock,
            return_value=True,  # Shopify IS connected
        ):
            tool = OrderTool()
            result = await tool._get_order("tenant_123", order_id="9999999999")

    assert result.success is False
    assert result.data is None
    assert "not found" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 4: list_orders returns real data when connected
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_orders_returns_real_data_when_connected():
    """When Shopify is connected, _list_orders returns real orders."""
    from app.core.react_tools.order_tool import OrderTool

    real_orders = [
        {
            "order_id": "1001",
            "order_name": "#1001",
            "total_price": "99.00",
            "financial_status": "paid",
            "line_items": [],
            "customer": None,
        },
        {
            "order_id": "1002",
            "order_name": "#1002",
            "total_price": "199.00",
            "financial_status": "refunded",
            "line_items": [],
            "customer": None,
        },
    ]

    with patch(
        "app.core.react_tools.ecommerce_client.fetch_real_orders",
        new_callable=AsyncMock,
        return_value=real_orders,
    ):
        tool = OrderTool()
        result = await tool._list_orders("tenant_123", limit=10)

    assert result.success is True
    assert result.data is not None
    assert result.data["total"] == 2
    assert len(result.data["orders"]) == 2
    assert result.data["orders"][0]["order_id"] == "1001"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: list_orders returns "not connected" when no integration
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_orders_returns_not_connected_when_no_integration():
    """When Shopify is NOT connected, _list_orders returns 'not connected'."""
    from app.core.react_tools.order_tool import OrderTool

    with patch(
        "app.core.react_tools.ecommerce_client.fetch_real_orders",
        new_callable=AsyncMock,
        return_value=None,  # Not connected
    ):
        tool = OrderTool()
        result = await tool._list_orders("tenant_123", limit=10)

    assert result.success is False
    assert result.data is None
    assert "not connected" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 6: ecommerce_client._get_credentials returns None when no integration
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ecommerce_client_credentials_return_none_when_not_connected():
    """The ecommerce_client credential lookup must return None when no
    Shopify integration is configured — not crash, not return fake creds."""
    from app.core.react_tools import ecommerce_client

    # Patch SessionLocal at the source (database.base) since it's imported
    # inside the function, not at module level of ecommerce_client.
    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_session.return_value = mock_db

    with patch("database.base.SessionLocal", mock_session):
        with patch(
            "app.services.integration_service.IntegrationService.get_credential_config",
            return_value=None,
        ):
            result = ecommerce_client._get_credentials("tenant_no_integration")

    assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Test 7: ecommerce_client._build_shopify_base_url handles various formats
# ═══════════════════════════════════════════════════════════════════════


def test_build_shopify_base_url_handles_various_formats():
    """The Shopify URL builder must handle all common shop domain formats."""
    from app.core.react_tools.ecommerce_client import _build_shopify_base_url

    # Full domain
    assert _build_shopify_base_url("my-shop.myshopify.com") == "https://my-shop.myshopify.com/admin/api/2024-01"
    # With https://
    assert _build_shopify_base_url("https://my-shop.myshopify.com") == "https://my-shop.myshopify.com/admin/api/2024-01"
    # Just the shop name
    assert _build_shopify_base_url("my-shop") == "https://my-shop.myshopify.com/admin/api/2024-01"
    # Empty
    assert _build_shopify_base_url("") == ""
