"""
Tests for Phase 3: Real Action Execution via custom connectors.

Verifies:
  1. _cancel_order calls real API when connector has 'cancel_order' action
  2. _cancel_order returns "not connected" when no connector
  3. _refund_order calls real API with amount + reason
  4. _refund_order returns "not connected" when no connector
  5. _refund_order rejects non-positive amounts
  6. _process_payment calls real API with payment details
  7. _process_payment returns "not connected" when no connector
  8. _process_payment rejects invalid amounts

Run: pytest tests/test_react_tools_phase3_actions.py -v --tb=short
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
    sys.modules["langgraph.graph"] = MagicMock()
    sys.modules["langgraph.graph"].END = "__end__"
    sys.modules["langgraph.graph"].StateGraph = MagicMock


# ═══════════════════════════════════════════════════════════════════════
# OrderTool — _cancel_order
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cancel_order_calls_real_api_when_connected():
    """When custom connector has 'cancel_order' action, calls the real API."""
    from app.core.react_tools.order_tool import OrderTool

    real_result = {
        "order_id": "1001",
        "status": "cancelled",
        "cancellation_reason": "Customer requested",
        "cancelled_at": "2026-07-11T10:00:00Z",
    }

    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        new_callable=AsyncMock,
        return_value=real_result,
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=True,
        ):
            tool = OrderTool()
            result = await tool._cancel_order("tenant_123", order_id="1001", reason="Customer requested")

    assert result.success is True
    assert result.data["status"] == "cancelled"
    assert result.data["order_id"] == "1001"


@pytest.mark.asyncio
async def test_cancel_order_returns_not_connected_when_no_connector():
    """When no connector exists, _cancel_order returns 'not connected'."""
    from app.core.react_tools.order_tool import OrderTool

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
            tool = OrderTool()
            result = await tool._cancel_order("tenant_123", order_id="1001")

    assert result.success is False
    assert result.data is None
    assert "not connected" in result.error.lower() or "no e-commerce" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# OrderTool — _refund_order
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_refund_order_calls_real_api_with_amount_and_reason():
    """When custom connector has 'refund_order' action, calls the real API
    with both the amount and reason in the request body."""
    from app.core.react_tools.order_tool import OrderTool

    real_result = {
        "refund_id": "REF-ABC123",
        "order_id": "1001",
        "amount": 99.00,
        "currency": "USD",
        "status": "processed",
    }

    mock_call = AsyncMock(return_value=real_result)
    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        mock_call,
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=True,
        ):
            tool = OrderTool()
            result = await tool._refund_order(
                "tenant_123", order_id="1001", amount=99.00, reason="Duplicate charge",
            )

    assert result.success is True
    assert result.data["refund_id"] == "REF-ABC123"
    assert result.data["amount"] == 99.00

    # Verify the call passed amount + reason in the body
    call_args = mock_call.call_args
    body = call_args.kwargs.get("body", {})
    assert body.get("amount") == 99.00
    assert body.get("reason") == "Duplicate charge"


@pytest.mark.asyncio
async def test_refund_order_returns_not_connected_when_no_connector():
    """When no connector exists, _refund_order returns 'not connected'."""
    from app.core.react_tools.order_tool import OrderTool

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
            tool = OrderTool()
            result = await tool._refund_order("tenant_123", order_id="1001", amount=50.00)

    assert result.success is False
    assert result.data is None
    assert "not connected" in result.error.lower() or "no e-commerce" in result.error.lower()


@pytest.mark.asyncio
async def test_refund_order_rejects_non_positive_amount():
    """Refund amount must be positive — rejects 0 and negative amounts."""
    from app.core.react_tools.order_tool import OrderTool

    tool = OrderTool()
    result = await tool._refund_order("tenant_123", order_id="1001", amount=0)
    assert result.success is False
    assert "positive" in result.error.lower()

    result = await tool._refund_order("tenant_123", order_id="1001", amount=-10.00)
    assert result.success is False
    assert "positive" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════
# BillingTool — _process_payment
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_process_payment_calls_real_api():
    """When custom connector has 'process_payment' action, calls the real API."""
    from app.core.react_tools.billing_tool import BillingTool

    real_result = {
        "payment_id": "PAY-XYZ789",
        "amount": 199.00,
        "status": "succeeded",
        "payment_method": "card_4242",
    }

    mock_call = AsyncMock(return_value=real_result)
    with patch(
        "app.core.react_tools.custom_connector_client.call_custom_action",
        mock_call,
    ):
        with patch(
            "app.core.react_tools.custom_connector_client.has_any_connector",
            new_callable=AsyncMock,
            return_value=True,
        ):
            tool = BillingTool()
            result = await tool._process_payment(
                "tenant_123", amount=199.00, payment_method="card_4242",
                invoice_id="INV-001", description="Annual subscription",
            )

    assert result.success is True
    assert result.data["payment_id"] == "PAY-XYZ789"
    assert result.data["status"] == "succeeded"

    # Verify the call passed all payment details
    call_args = mock_call.call_args
    body = call_args.kwargs.get("body", {})
    assert body.get("amount") == 199.00
    assert body.get("payment_method") == "card_4242"
    assert body.get("invoice_id") == "INV-001"


@pytest.mark.asyncio
async def test_process_payment_returns_not_connected_when_no_connector():
    """When no connector exists, _process_payment returns 'not connected'."""
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
            result = await tool._process_payment(
                "tenant_123", amount=50.00, payment_method="card_1234",
            )

    assert result.success is False
    assert result.data is None
    assert "not connected" in result.error.lower() or "no billing" in result.error.lower()


@pytest.mark.asyncio
async def test_process_payment_rejects_invalid_amount():
    """Payment amount must be positive."""
    from app.core.react_tools.billing_tool import BillingTool

    tool = BillingTool()
    result = await tool._process_payment("tenant_123", amount=0, payment_method="card")
    assert result.success is False
    assert "positive" in result.error.lower()

    result = await tool._process_payment("tenant_123", amount=-5.00, payment_method="card")
    assert result.success is False
    assert "positive" in result.error.lower()


@pytest.mark.asyncio
async def test_process_payment_requires_payment_method():
    """Payment method is required — rejects empty method."""
    from app.core.react_tools.billing_tool import BillingTool

    tool = BillingTool()
    result = await tool._process_payment("tenant_123", amount=50.00, payment_method="")
    assert result.success is False
    assert "payment method" in result.error.lower()
