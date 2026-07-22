"""
Tests for BillingTool real custom-connector integration.

Verifies:
  1. _get_invoice returns real data when custom connector has 'get_invoice' action
  2. _get_invoice returns "not connected" when no connector exists
  3. _get_invoice returns "not found" when connector exists but API returns nothing
  4. _get_payment_history returns real data when action exists
  5. _get_payment_history returns "not connected" when no connector
  6. custom_connector_client._find_action matches by name
  7. custom_connector_client._substitute_path handles path params

Run: pytest tests/test_billing_tool_custom_connector.py -v --tb=short
"""
from __future__ import annotations

import sys
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock


# ═══════════════════════════════════════════════════════════════════════
# Test 1: _get_invoice returns real data when custom connector configured
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_invoice_returns_real_data_when_connector_configured():
    """When a custom connector with 'get_invoice' action exists, BillingTool
    calls the real API and returns real invoice data — NOT mock data."""
    from app.core.react_tools.billing_tool import BillingTool

    real_invoice = {
        "invoice_id": "INV-2026-001",
        "customer_id": "cust_123",
        "amount": 199.00,
        "currency": "USD",
        "status": "paid",
        "items": [{"description": "Annual Subscription", "amount": 199.00}],
    }

    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        new_callable=AsyncMock,
        return_value=real_invoice,
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=True,
        ):
            tool = BillingTool()
            result = await tool._get_invoice("tenant_123", invoice_id="INV-2026-001")

    assert result.success is True
    assert result.data is not None
    assert result.data["invoice_id"] == "INV-2026-001"
    assert result.data["amount"] == 199.00
    # Verify it's NOT mock data
    assert "mock" not in str(result.data).lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 2: _get_invoice returns "not connected" when no connector
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_invoice_returns_not_connected_when_no_connector():
    """When no custom connector exists, BillingTool returns an honest
    'not connected' error — NOT mock data."""
    from app.core.react_tools.billing_tool import BillingTool

    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=False,
        ):
            tool = BillingTool()
            result = await tool._get_invoice("tenant_123", invoice_id="any_invoice")

    assert result.success is False
    assert result.data is None
    assert "not connected" in result.error.lower() or "no billing" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 3: _get_invoice returns "not found" when connector exists but API fails
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_invoice_returns_not_found_when_api_returns_nothing():
    """When a connector exists but the API call returns no data (e.g.
    invoice not found), return 'not found' — NOT mock data."""
    from app.core.react_tools.billing_tool import BillingTool

    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        new_callable=AsyncMock,
        return_value=None,  # API returned nothing
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=True,  # Connector IS configured
        ):
            tool = BillingTool()
            result = await tool._get_invoice("tenant_123", invoice_id="INV-MISSING")

    assert result.success is False
    assert result.data is None
    assert "not found" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 4: _get_payment_history returns real data when action exists
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_payment_history_returns_real_data():
    """When custom connector has 'get_payment_history' action, returns
    real payment history — NOT mock data."""
    from app.core.react_tools.billing_tool import BillingTool

    real_history = {
        "payments": [
            {"payment_id": "pay_001", "amount": 99.00, "status": "succeeded", "currency": "USD"},
            {"payment_id": "pay_002", "amount": 199.00, "status": "succeeded", "currency": "USD"},
        ],
        "total_count": 2,
        "total_succeeded_amount": 298.00,
    }

    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        new_callable=AsyncMock,
        return_value=real_history,
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=True,
        ):
            tool = BillingTool()
            result = await tool._get_payment_history("tenant_123", limit=20)

    assert result.success is True
    assert result.data is not None
    assert result.data["total_count"] == 2
    assert len(result.data["payments"]) == 2
    assert result.data["payments"][0]["payment_id"] == "pay_001"


# ═══════════════════════════════════════════════════════════════════════
# Test 5: _get_payment_history returns "not connected" when no connector
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_payment_history_returns_not_connected():
    """When no connector exists, _get_payment_history returns 'not connected'."""
    from app.core.react_tools.billing_tool import BillingTool

    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=False,
        ):
            tool = BillingTool()
            result = await tool._get_payment_history("tenant_123", limit=10)

    assert result.success is False
    assert result.data is None
    assert "not connected" in result.error.lower() or "no billing" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# Test 6: _find_action matches by action name
# ═══════════════════════════════════════════════════════════════════════


def test_find_action_matches_by_name():
    """The _find_action function must find the right connector + action
    by matching the action name across all connectors."""
    from app.core.react_tools.custom_connector_client import _find_action

    connectors = [
        {
            "name": "Razorpay Connector",
            "base_url": "https://api.razorpay.com/v1",
            "actions": [
                {"name": "get_payment", "method": "GET", "path": "/payments/{id}"},
                {"name": "process_refund", "method": "POST", "path": "/payments/{id}/refund"},
            ],
        },
        {
            "name": "Shopify Connector",
            "base_url": "https://shop.example.com/admin",
            "actions": [
                {"name": "get_order", "method": "GET", "path": "/orders/{id}"},
            ],
        },
    ]

    # Find 'get_payment' — should match Razorpay connector
    found = _find_action(connectors, "get_payment")
    assert found is not None
    connector, action = found
    assert connector["name"] == "Razorpay Connector"
    assert action["path"] == "/payments/{id}"

    # Find 'get_order' — should match Shopify connector
    found = _find_action(connectors, "get_order")
    assert found is not None
    connector, action = found
    assert connector["name"] == "Shopify Connector"

    # Find non-existent action — should return None
    found = _find_action(connectors, "nonexistent_action")
    assert found is None


# ═══════════════════════════════════════════════════════════════════════
# Test 7: _substitute_path handles path parameters
# ═══════════════════════════════════════════════════════════════════════


def test_substitute_path_handles_params():
    """The _substitute_path function must replace {param} placeholders."""
    from app.core.react_tools.custom_connector_client import _substitute_path

    # Single param
    assert _substitute_path("/payments/{id}", {"id": "pay_123"}) == "/payments/pay_123"
    # Multiple params
    assert _substitute_path("/customers/{cust_id}/orders/{order_id}", {"cust_id": "c1", "order_id": "o2"}) == "/customers/c1/orders/o2"
    # No params
    assert _substitute_path("/health", {"id": "x"}) == "/health"
    # Numeric param converted to string
    assert _substitute_path("/orders/{id}", {"id": 12345}) == "/orders/12345"
