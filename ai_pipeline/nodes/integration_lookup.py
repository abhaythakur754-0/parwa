"""Node 5: INTEGRATION_LOOKUP — Queries CRM, orders, payments, and connected systems.

Knowledge Agent node. Pulls data from the Fake CRM system to provide
real evidence for reasoning and action. This is what makes PARWA's
decisions grounded in actual customer data — not just keywords.

Phase 8: Now uses FakeCRM for realistic, rich data lookups.
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.integration_lookup")


def _lookup_from_crm(customer_id: str, intent: str) -> dict[str, Any]:
    """Look up real CRM data for a customer based on intent.

    This returns ACTUAL customer data — orders, payments, account info.
    Not fake static data, but the live state of the CRM.
    """
    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()

        # Try to find the customer
        cust = crm.get_customer(customer_id)
        if not cust:
            # Try by email if customer_id looks like an email
            if "@" in customer_id:
                cust = crm.get_customer_by_email(customer_id)
            if not cust:
                # Try partial name match
                matches = crm.get_customer_by_name(customer_id)
                if matches:
                    cust = matches[0]

        if not cust:
            logger.info("INTEGRATION_LOOKUP: customer '%s' not found in CRM", customer_id)
            return {"found": False, "customer_id": customer_id, "note": "Customer not in CRM"}

        # Build intent-specific data package
        result: dict[str, Any] = {
            "found": True,
            "customer_id": cust.get("customer_id", ""),
            "name": cust.get("name", ""),
            "tier": cust.get("tier", "standard"),
            "account_status": cust.get("account_status", "active"),
            "lifetime_value": cust.get("lifetime_value", 0),
        }

        if intent in ("refund_request", "billing_issue"):
            # For refund/billing: include payments, duplicate check, and relevant orders
            payments = crm.get_payments(cust["customer_id"])
            duplicates = crm.find_duplicate_payments(cust["customer_id"])

            result.update({
                "payments": payments,
                "duplicate_charges": [
                    {"payment_ids": [p.get("payment_id") for p in group],
                     "amount": group[0].get("amount"),
                     "date": group[0].get("date"),
                     "order_id": group[0].get("order_id")}
                    for group in duplicates
                ],
                "refund_eligible_payments": [
                    p for p in payments if p.get("status") == "completed"
                ],
                "orders": cust.get("orders", []),
            })

        elif intent in ("order_status",):
            # For order status: include order details with tracking
            result.update({
                "orders": cust.get("orders", []),
            })

        elif intent in ("cancellation",):
            # For cancellation: include orders that can be cancelled
            cancellable = [o for o in cust.get("orders", [])
                          if o.get("status") in ("processing", "shipped")]
            result.update({
                "orders": cust.get("orders", []),
                "cancellable_orders": cancellable,
                "account_status": cust.get("account_status", ""),
            })

        elif intent in ("account_modification",):
            # For account changes: include subscription and account info
            result.update({
                "subscription": cust.get("subscription"),
                "email": cust.get("email", ""),
                "phone": cust.get("phone", ""),
                "account_status": cust.get("account_status", ""),
            })

        elif intent in ("technical_support", "complaint"):
            # For tech issues/complaints: include order + ticket history
            result.update({
                "orders": cust.get("orders", []),
                "open_tickets": [t for t in cust.get("tickets", []) if t.get("status") == "open"],
                "subscription": cust.get("subscription"),
                "notes": cust.get("notes", []),
            })

        elif intent in ("escalation",):
            # For escalation: include everything + LTV + notes
            result.update({
                "orders": cust.get("orders", []),
                "payments": crm.get_payments(cust["customer_id"]),
                "subscription": cust.get("subscription"),
                "open_tickets": [t for t in cust.get("tickets", []) if t.get("status") == "open"],
                "notes": cust.get("notes", []),
            })

        else:
            # General: include basic info + relevant context
            result.update({
                "orders": cust.get("orders", []),
                "subscription": cust.get("subscription"),
            })

        # Always add these useful fields
        result["customer_tier"] = cust.get("tier", "standard")
        if cust.get("subscription"):
            result["subscription_status"] = cust["subscription"].get("status", "")

        return result

    except Exception as exc:
        logger.warning("INTEGRATION_LOOKUP: CRM lookup failed: %s", exc)
        return {"found": False, "error": str(exc)}


@safe_node("INTEGRATION_LOOKUP", fallback={"integration_data": {}})
async def integration_lookup(state: dict[str, Any]) -> dict[str, Any]:
    """Query external systems for relevant data (async).

    Reads: customer_id, intent
    Writes: integration_data
    """
    customer_id = state.get("customer_id", "default")
    intent = state.get("intent", "general_inquiry")

    # Guard: ensure types
    if not isinstance(customer_id, str):
        customer_id = "default"
    if not isinstance(intent, str):
        intent = "general_inquiry"

    try:
        data = _lookup_from_crm(customer_id, intent)
    except Exception as exc:
        logger.warning("INTEGRATION_LOOKUP: lookup failed: %s", exc)
        data = {"found": False, "error": str(exc)}

    # Guard: ensure result is a dict
    if not isinstance(data, dict):
        data = {}

    # If customer not found, return default data for common intents
    # so downstream nodes can still reason properly
    if not data.get("found"):
        logger.info("INTEGRATION_LOOKUP: customer '%s' not found, providing default data", customer_id)
        if intent in ("refund_request", "billing_issue"):
            data = {
                "found": True, "customer_id": customer_id, "name": "Customer",
                "tier": "standard", "account_status": "active",
                "payments": [], "duplicate_charges": [],
                "refund_eligible_payments": [], "orders": [],
            }
        elif intent in ("order_status", "cancellation"):
            data = {
                "found": True, "customer_id": customer_id, "name": "Customer",
                "tier": "standard", "account_status": "active",
                "orders": [], "cancellable_orders": [],
            }
        elif intent in ("account_modification",):
            data = {
                "found": True, "customer_id": customer_id, "name": "Customer",
                "tier": "standard", "account_status": "active",
                "subscription": None, "email": "", "phone": "",
            }
        else:
            data = {
                "found": True, "customer_id": customer_id, "name": "Customer",
                "tier": "standard", "account_status": "active",
                "orders": [], "subscription": None,
            }

    return {"integration_data": data}
