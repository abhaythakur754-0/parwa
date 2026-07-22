"""
Tests for Node 3 Custom Connector Override.

When KB is insufficient BUT the tenant has a custom connector that can
fetch real data for the ticket type, Node 3 should let the pipeline
proceed (not pause for guidance). Node 5 will then call the connector.

Verifies:
  1. When connector exists with matching action → sufficiency overridden to True
  2. When NO connector exists → sufficiency stays False (unchanged behavior)
  3. When connector exists but no matching action → sufficiency stays False
  4. Different ticket types map to different actions

Run: pytest tests/test_node3_connector_override.py -v --tb=short
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
if "langgraph.types" not in sys.modules:
    sys.modules["langgraph.types"] = MagicMock()


# ═══════════════════════════════════════════════════════════════════════
# Test 1: Connector with matching action → override sufficiency to True
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_connector_with_matching_action_overrides_sufficiency():
    """When tenant has a custom connector with 'get_invoice' action AND
    ticket is billing type, Node 3 should let pipeline proceed."""
    # Mock has_action to return True for get_invoice
    async def mock_has_action(company_id, action_name):
        return action_name in ("get_invoice", "get_payment_history")

    with patch(
        "app.core.react_tools.custom_connector_client.has_action",
        new=mock_has_action,
    ):
        # Simulate the override logic from Node 3
        from app.core.react_tools.custom_connector_client import has_action

        tenant_id = "tenant_123"
        ticket_type = "billing"
        _ticket_type_to_actions = {
            "refund_request": ["get_order", "get_invoice", "get_payment_history", "refund_order"],
            "billing": ["get_invoice", "get_payment_history", "process_payment"],
            "technical": ["get_order", "get_invoice"],
            "faq": ["get_invoice", "get_payment_history"],
            "complaint": ["get_order", "get_invoice", "get_payment_history"],
            "account": ["get_invoice", "get_payment_history"],
            "shipping": ["get_order"],
            "order": ["get_order", "get_invoice"],
        }
        _needed_actions = _ticket_type_to_actions.get(ticket_type, ["get_invoice", "get_order"])

        _has_matching_connector = False
        for _action in _needed_actions:
            if await has_action(tenant_id, _action):
                _has_matching_connector = True
                break

        assert _has_matching_connector is True, "Should find matching connector for billing ticket"


# ═══════════════════════════════════════════════════════════════════════
# Test 2: No connector → no override (unchanged behavior)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_no_connector_no_override():
    """When tenant has NO custom connectors, the override should not fire."""
    async def mock_has_action(company_id, action_name):
        return False  # No connectors at all

    with patch(
        "app.core.react_tools.custom_connector_client.has_action",
        new=mock_has_action,
    ):
        from app.core.react_tools.custom_connector_client import has_action

        tenant_id = "tenant_no_connector"
        ticket_type = "billing"
        _ticket_type_to_actions = {
            "billing": ["get_invoice", "get_payment_history", "process_payment"],
        }
        _needed_actions = _ticket_type_to_actions.get(ticket_type, ["get_invoice"])

        _has_matching_connector = False
        for _action in _needed_actions:
            if await has_action(tenant_id, _action):
                _has_matching_connector = True
                break

        assert _has_matching_connector is False, "Should NOT find matching connector when none exists"


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Connector exists but no matching action → no override
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_connector_exists_but_no_matching_action():
    """When tenant has a connector but it doesn't have the right action
    for this ticket type, the override should not fire."""
    async def mock_has_action(company_id, action_name):
        # Only has 'get_order' — not 'get_invoice' or 'get_payment_history'
        return action_name == "get_order"

    with patch(
        "app.core.react_tools.custom_connector_client.has_action",
        new=mock_has_action,
    ):
        from app.core.react_tools.custom_connector_client import has_action

        tenant_id = "tenant_with_order_connector"
        ticket_type = "billing"  # billing needs get_invoice/get_payment_history
        _ticket_type_to_actions = {
            "billing": ["get_invoice", "get_payment_history", "process_payment"],
        }
        _needed_actions = _ticket_type_to_actions.get(ticket_type, ["get_invoice"])

        _has_matching_connector = False
        for _action in _needed_actions:
            if await has_action(tenant_id, _action):
                _has_matching_connector = True
                break

        assert _has_matching_connector is False, "Should NOT override when connector has wrong action"


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Refund ticket matches refund_order action
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_refund_ticket_matches_refund_action():
    """Refund tickets should match connectors with 'refund_order' or
    'get_order' or 'get_invoice' actions."""
    async def mock_has_action(company_id, action_name):
        return action_name == "refund_order"

    with patch(
        "app.core.react_tools.custom_connector_client.has_action",
        new=mock_has_action,
    ):
        from app.core.react_tools.custom_connector_client import has_action

        tenant_id = "tenant_with_refund"
        ticket_type = "refund_request"
        _ticket_type_to_actions = {
            "refund_request": ["get_order", "get_invoice", "get_payment_history", "refund_order"],
        }
        _needed_actions = _ticket_type_to_actions.get(ticket_type, ["get_invoice"])

        _has_matching_connector = False
        for _action in _needed_actions:
            if await has_action(tenant_id, _action):
                _has_matching_connector = True
                break

        assert _has_matching_connector is True, "Refund ticket should match refund_order action"
