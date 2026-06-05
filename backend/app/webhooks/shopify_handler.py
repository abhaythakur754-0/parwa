"""
Shopify Webhook Handler (Day 1 — Expanded)

Handles Shopify webhook events:
- orders.create: New order created in Shopify store
- orders.updated: Order details changed
- orders/cancelled: Order was cancelled
- customers.create: New customer registered
- refunds/create: Refund issued on an order
- fulfillments/create: Fulfillment created (item shipped)

All handlers:
- Validate required fields in payload
- Extract normalized data
- Return structured result for service layer
- Are idempotent (checked at webhook_service level)
"""

import logging
from typing import Optional

from app.webhooks import register_handler

logger = logging.getLogger("parwa.webhooks.shopify")

# Required fields per Shopify event type
REQUIRED_FIELDS = {
    "orders.create": ["order_id", "email", "total_price", "currency"],
    "orders.updated": ["order_id"],
    "orders/cancelled": ["order_id"],
    "customers.create": ["customer_id", "email"],
    "refunds/create": ["order_id", "refund_id"],
    "fulfillments/create": ["order_id", "fulfillment_id"],
}


def _sanitize_field(value: str, max_length: int = 255) -> str:
    """Sanitize Shopify field value.

    Strips control characters and truncates.
    """
    if not value:
        return ""
    cleaned = "".join(
        c for c in str(value) if ord(c) >= 32 or c in "\n\r\t"
    )
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned.strip()


def _extract_order_data(payload: dict) -> dict:
    """Extract and normalize order data from Shopify payload.

    Shopify sends order data with nested objects:
    - order: {id, email, total_price, currency, ...}
    - customer: {id, first_name, last_name, ...}
    - line_items: [{title, quantity, price}, ...]
    """
    order = payload.get("order", payload) or {}
    customer = order.get("customer", {}) or {}
    line_items = order.get("line_items", []) or []

    items = []
    for item in line_items[:100]:  # Max 100 line items
        if not isinstance(item, dict):
            continue
        items.append({
            "title": _sanitize_field(item.get("title", ""), 500),
            "quantity": int(item.get("quantity", 1)),
            "price": str(item.get("price", "0")),
            "sku": _sanitize_field(item.get("sku", ""), 50),
        })

    return {
        "order_id": str(order.get("id") or order.get("order_number", "")),
        "order_number": str(order.get("order_number", "")),
        "email": _sanitize_field(order.get("email", "") or customer.get("email", ""), 254),
        "total_price": str(order.get("total_price", "0")),
        "currency": _sanitize_field(order.get("currency", "USD"), 10),
        "financial_status": _sanitize_field(order.get("financial_status", ""), 30),
        "fulfillment_status": _sanitize_field(order.get("fulfillment_status", ""), 30),
        "cancel_reason": _sanitize_field(order.get("cancel_reason", ""), 100),
        "cancelled_at": order.get("cancelled_at"),
        "customer_id": str(customer.get("id", "")),
        "customer_name": _sanitize_field(
            " ".join(filter(None, [
                customer.get("first_name", ""),
                customer.get("last_name", ""),
            ])), 200,
        ),
        "line_items": items,
        "created_at": order.get("created_at"),
        "updated_at": order.get("updated_at"),
    }


def _extract_customer_data(payload: dict) -> dict:
    """Extract and normalize customer data from Shopify payload.

    Shopify sends customer data:
    - customer: {id, email, first_name, last_name, phone, ...}
    """
    customer = payload.get("customer", payload) or {}

    return {
        "customer_id": str(customer.get("id", "")),
        "email": _sanitize_field(customer.get("email", ""), 254),
        "first_name": _sanitize_field(customer.get("first_name", ""), 100),
        "last_name": _sanitize_field(customer.get("last_name", ""), 100),
        "phone": _sanitize_field(customer.get("phone", ""), 30),
        "state": _sanitize_field(customer.get("state", ""), 30),
        "orders_count": int(customer.get("orders_count", 0)),
        "total_spent": str(customer.get("total_spent", "0")),
        "created_at": customer.get("created_at"),
    }


def _extract_refund_data(payload: dict) -> dict:
    """Extract and normalize refund data from Shopify payload.

    Shopify sends refund data:
    - refund: {id, order_id, refund_line_items, transactions, ...}
    """
    refund = payload.get("refund", payload) or {}

    # Extract refund line items
    refund_items = []
    for rli in (refund.get("refund_line_items") or [])[:100]:
        if not isinstance(rli, dict):
            continue
        line_item = rli.get("line_item", {}) or {}
        refund_items.append({
            "line_item_id": str(rli.get("line_item_id", "")),
            "quantity": int(rli.get("quantity", 0)),
            "restock_type": _sanitize_field(rli.get("restock_type", ""), 30),
            "item_title": _sanitize_field(line_item.get("title", ""), 500),
            "item_price": str(line_item.get("price", "0")),
        })

    # Extract transactions (actual refund amounts)
    transactions = []
    for txn in (refund.get("transactions") or [])[:50]:
        if not isinstance(txn, dict):
            continue
        transactions.append({
            "transaction_id": str(txn.get("id", "")),
            "amount": str(txn.get("amount", "0")),
            "kind": _sanitize_field(txn.get("kind", ""), 30),
            "gateway": _sanitize_field(txn.get("gateway", ""), 50),
            "status": _sanitize_field(txn.get("status", ""), 30),
        })

    return {
        "refund_id": str(refund.get("id", "")),
        "order_id": str(refund.get("order_id", "")),
        "created_at": refund.get("created_at"),
        "note": _sanitize_field(refund.get("note", ""), 500),
        "refund_line_items": refund_items,
        "transactions": transactions,
        "total_refund_amount": sum(
            float(t.get("amount", 0)) for t in transactions
            if t.get("kind") == "refund"
        ),
    }


def _extract_fulfillment_data(payload: dict) -> dict:
    """Extract and normalize fulfillment data from Shopify payload.

    Shopify sends fulfillment data:
    - fulfillment: {id, order_id, tracking_number, tracking_company, ...}
    """
    fulfillment = payload.get("fulfillment", payload) or {}

    # Extract line items being fulfilled
    fulfilled_items = []
    for item in (fulfillment.get("line_items") or [])[:100]:
        if not isinstance(item, dict):
            continue
        fulfilled_items.append({
            "line_item_id": str(item.get("id", "")),
            "title": _sanitize_field(item.get("title", ""), 500),
            "quantity": int(item.get("quantity", 0)),
            "sku": _sanitize_field(item.get("sku", ""), 50),
        })

    return {
        "fulfillment_id": str(fulfillment.get("id", "")),
        "order_id": str(fulfillment.get("order_id", "")),
        "status": _sanitize_field(fulfillment.get("status", ""), 30),
        "tracking_company": _sanitize_field(fulfillment.get("tracking_company", ""), 100),
        "tracking_number": _sanitize_field(fulfillment.get("tracking_number", ""), 100),
        "tracking_url": _sanitize_field(fulfillment.get("tracking_url", ""), 500),
        "tracking_numbers": [
            _sanitize_field(t, 100) for t in (fulfillment.get("tracking_numbers") or [])
        ],
        "tracking_urls": [
            _sanitize_field(u, 500) for u in (fulfillment.get("tracking_urls") or [])
        ],
        "line_items": fulfilled_items,
        "created_at": fulfillment.get("created_at"),
        "updated_at": fulfillment.get("updated_at"),
    }


def _validate_required_fields(
    event_type: str, data: dict,
) -> Optional[str]:
    """Validate that required fields exist in extracted data.

    Returns:
        Error message if validation fails, None if OK.
    """
    required = REQUIRED_FIELDS.get(event_type, [])
    for field in required:
        val = data.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            return f"Missing required field: {field}"
    return None


def handle_order_created(event: dict) -> dict:
    """Handle Shopify orders.create event."""
    payload = event.get("payload", {})
    order_data = _extract_order_data(payload)

    error = _validate_required_fields("orders.create", order_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_order_created order_id=%s total=%s %s",
        order_data["order_id"],
        order_data["total_price"],
        order_data["currency"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "order_created",
        "data": order_data,
    }


def handle_order_updated(event: dict) -> dict:
    """Handle Shopify orders.updated event.

    Fires when order details change: financial_status, fulfillment_status,
    line items, shipping address, tags, notes, etc.
    """
    payload = event.get("payload", {})
    order_data = _extract_order_data(payload)

    error = _validate_required_fields("orders.updated", order_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_order_updated order_id=%s financial=%s fulfillment=%s",
        order_data["order_id"],
        order_data["financial_status"],
        order_data["fulfillment_status"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "order_updated",
        "data": order_data,
    }


def handle_order_cancelled(event: dict) -> dict:
    """Handle Shopify orders/cancelled event.

    Fires when an order is cancelled. Includes cancel_reason
    (inventory, customer, fraud, other) and cancelled_at.
    """
    payload = event.get("payload", {})
    order_data = _extract_order_data(payload)

    error = _validate_required_fields("orders/cancelled", order_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_order_cancelled order_id=%s reason=%s",
        order_data["order_id"],
        order_data.get("cancel_reason", "unknown"),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "order_cancelled",
        "data": order_data,
    }


def handle_customer_created(event: dict) -> dict:
    """Handle Shopify customers.create event."""
    payload = event.get("payload", {})
    customer_data = _extract_customer_data(payload)

    error = _validate_required_fields("customers.create", customer_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_customer_created customer_id=%s email=%s",
        customer_data["customer_id"],
        customer_data["email"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "customer_created",
        "data": customer_data,
    }


def handle_refund_created(event: dict) -> dict:
    """Handle Shopify refunds/create event.

    Fires when a refund is issued on an order. Contains refund line items
    and transactions with actual refund amounts.

    This is critical for PARWA — when a refund is processed (either by the
    AI agent or by the merchant directly in Shopify), this webhook keeps
    PARWA's ticket context in sync.
    """
    payload = event.get("payload", {})
    refund_data = _extract_refund_data(payload)

    error = _validate_required_fields("refunds/create", refund_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_refund_created refund_id=%s order_id=%s total_refund=%s",
        refund_data["refund_id"],
        refund_data["order_id"],
        refund_data["total_refund_amount"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "refund_created",
        "data": refund_data,
    }


def handle_fulfillment_created(event: dict) -> dict:
    """Handle Shopify fulfillments/create event.

    Fires when a fulfillment is created (items shipped). Contains
    tracking number, tracking URL, and carrier information.

    This enables PARWA's shipping intelligence — when a package ships,
    the agent can proactively notify the customer with tracking info.
    """
    payload = event.get("payload", {})
    fulfillment_data = _extract_fulfillment_data(payload)

    error = _validate_required_fields("fulfillments/create", fulfillment_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_fulfillment_created fulfillment_id=%s order_id=%s tracking=%s",
        fulfillment_data["fulfillment_id"],
        fulfillment_data["order_id"],
        fulfillment_data["tracking_number"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "fulfillment_created",
        "data": fulfillment_data,
    }


# Event type to handler mapping
_SHOPIFY_HANDLERS = {
    "orders.create": handle_order_created,
    "orders.updated": handle_order_updated,
    "orders/cancelled": handle_order_cancelled,
    "customers.create": handle_customer_created,
    "refunds/create": handle_refund_created,
    "fulfillments/create": handle_fulfillment_created,
}


@register_handler("shopify")
def handle_shopify_event(event: dict) -> dict:
    """Main Shopify webhook handler dispatcher.

    Routes to the correct sub-handler based on event_type.

    Supported event types (Day 1):
    - orders.create
    - orders.updated
    - orders/cancelled
    - customers.create
    - refunds/create
    - fulfillments/create

    Args:
        event: Full event dict.

    Returns:
        Dict with status, action, and extracted data.
    """
    event_type = event.get("event_type", "")

    handler = _SHOPIFY_HANDLERS.get(event_type)
    if not handler:
        logger.warning(
            "shopify_unknown_event_type type=%s event_id=%s",
            event_type,
            event.get("event_id"),
            extra={"company_id": event.get("company_id")},
        )
        return {
            "status": "validation_error",
            "error": f"Unknown Shopify event type: {event_type}",
            "supported_types": list(_SHOPIFY_HANDLERS.keys()),
        }

    return handler(event)
