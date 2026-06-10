"""Node 5: INTEGRATION_LOOKUP — Queries CRM, orders, payments, and connected systems.

Knowledge Agent node. Pulls data from external systems (CRM, payment gateways,
shipping providers) to provide evidence for reasoning and action.
"""

from __future__ import annotations

from typing import Any

from parwa.utils.node_base import safe_node


# Mock CRM data per customer
_MOCK_CRM: dict[str, dict] = {
    "default": {
        "customer_id": "CUST-0000",
        "name": "John Doe",
        "email": "john@example.com",
        "orders": [
            {"order_id": "ORD-12345", "status": "delivered", "items": ["Widget Pro"], "total": 49.99},
        ],
        "charges": [
            {"amount": 49.99, "date": "2025-01-05", "description": "Widget Pro"},
            {"amount": 49.99, "date": "2025-01-05", "description": "Widget Pro (duplicate)"},
        ],
        "account_status": "active",
    },
}


def _lookup_integration_rule_based(customer_id: str, intent: str) -> dict[str, Any]:
    """Look up integration data using mock CRM."""
    # In production, this would call actual CRM/payment/shipping APIs
    data = _MOCK_CRM.get(customer_id, _MOCK_CRM["default"]).copy()

    # Filter based on what's relevant to the intent
    if intent in ("refund_request", "billing_issue"):
        return {
            "customer_id": data.get("customer_id", ""),
            "name": data.get("name", ""),
            "charges": data.get("charges", []),
            "account_status": data.get("account_status", ""),
        }
    if intent in ("order_status",):
        return {
            "customer_id": data.get("customer_id", ""),
            "orders": data.get("orders", []),
        }
    if intent in ("cancellation",):
        return {
            "customer_id": data.get("customer_id", ""),
            "orders": data.get("orders", []),
            "account_status": data.get("account_status", ""),
        }

    # Return all data for other intents
    return data


@safe_node("INTEGRATION_LOOKUP")
async def integration_lookup(state: dict[str, Any]) -> dict[str, Any]:
    """Query external systems for relevant data (async).

    Reads: customer_id, intent
    Writes: integration_data
    """
    customer_id = state.get("customer_id", "default")
    intent = state.get("intent", "general_inquiry")

    data = _lookup_integration_rule_based(customer_id, intent)

    return {"integration_data": data}
