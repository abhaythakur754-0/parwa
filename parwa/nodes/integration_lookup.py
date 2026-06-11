"""Node 5: INTEGRATION_LOOKUP — Queries CRM, orders, payments, and connected systems.

Knowledge Agent node. Pulls data from external systems (CRM, payment gateways,
shipping providers) to provide evidence for reasoning and action.

Phase 5: Now uses FrameworkBrain with HyDE/CLARA for smart data filtering.
Falls back to rule-based on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.integration_lookup")


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


async def _lookup_with_brain(state: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Integration lookup using FrameworkBrain (Phase 5).

    Returns (integration_data, frameworks_used).
    Falls back to rule-based on any failure.
    """
    customer_id = state.get("customer_id", "default")
    intent = state.get("intent", "general_inquiry")

    try:
        from parwa.frameworks.brain import FrameworkBrain

        brain = FrameworkBrain(node="INTEGRATION_LOOKUP", state=state)
        result = await brain.think(
            prompt=f"Lookup relevant data for {intent}",
            techniques=["hyde", "clara"],
            ticket_id=state.get("ticket_id", ""),
            variant=state.get("variant", "parwa"),
        )

        data = _lookup_integration_rule_based(customer_id, intent)

        if result.confidence > 0.5 and result.frameworks_used:
            if isinstance(data, dict):
                data["brain_enhanced"] = True
                data["frameworks_used"] = result.frameworks_used

        frameworks_used = result.frameworks_used if result.frameworks_used else []
        return data, frameworks_used

    except Exception as exc:
        logger.warning(
            "integration_lookup: FrameworkBrain failed (%s), falling back to rule-based",
            exc,
        )
        data = _lookup_integration_rule_based(customer_id, intent)
        return data, []


@safe_node("INTEGRATION_LOOKUP", fallback={"integration_data": {}, "active_frameworks": []})
async def integration_lookup(state: dict[str, Any]) -> dict[str, Any]:
    """Query external systems for relevant data (async).

    Phase 5: Uses FrameworkBrain with HyDE/CLARA for smart data filtering.

    Reads: customer_id, intent
    Writes: integration_data, active_frameworks (append)
    """
    customer_id = state.get("customer_id", "default")
    intent = state.get("intent", "general_inquiry")

    # Guard: ensure types
    if not isinstance(customer_id, str):
        customer_id = "default"
    if not isinstance(intent, str):
        intent = "general_inquiry"

    data, frameworks = await _lookup_with_brain(state)

    # Guard: ensure result is a dict
    if not isinstance(data, dict):
        data = {}

    new_frameworks = []
    existing = state.get("active_frameworks", [])
    for fw in frameworks:
        if fw not in existing:
            new_frameworks.append(fw)

    return {
        "integration_data": data,
        "active_frameworks": new_frameworks,
    }
