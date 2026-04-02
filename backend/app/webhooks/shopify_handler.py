"""
Shopify Webhook Handler (BC-003, GAP 1.5)

Handles Shopify webhook events:
- orders.create: New order created in Shopify store
- customers.create: New customer registered

All handlers:
- Validate required fields in payload
- Extract normalized order/customer data
- Return structured result for service layer
- Are idempotent (checked at webhook_service level)
"""

import logging
from typing import Optional

from backend.app.webhooks import register_handler

logger = logging.getLogger("parwa.webhooks.shopify")

# Required fields per Shopify event type
REQUIRED_FIELDS = {
    "orders.create": ["order_id", "email", "total_price", "currency"],
    "customers.create": ["customer_id", "email"],
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
        })

    return {
        "order_id": str(order.get("id") or order.get("order_number", "")),
        "order_number": str(order.get("order_number", "")),
        "email": _sanitize_field(order.get("email", "") or customer.get("email", ""), 254),
        "total_price": str(order.get("total_price", "0")),
        "currency": _sanitize_field(order.get("currency", "USD"), 10),
        "financial_status": _sanitize_field(order.get("financial_status", ""), 30),
        "fulfillment_status": _sanitize_field(order.get("fulfillment_status", ""), 30),
        "customer_id": str(customer.get("id", "")),
        "customer_name": _sanitize_field(
            " ".join(filter(None, [
                customer.get("first_name", ""),
                customer.get("last_name", ""),
            ])), 200,
        ),
        "line_items": items,
        "created_at": order.get("created_at"),
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
        "created_at": customer.get("created_at"),
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
    """Handle Shopify orders.create event.

    Args:
        event: Full event dict with keys:
            - event_type: "orders.create"
            - payload: Raw Shopify payload
            - company_id: Tenant company ID
            - event_id: Provider event ID

    Returns:
        Dict with status, action, and extracted order data.
    """
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


def handle_customer_created(event: dict) -> dict:
    """Handle Shopify customers.create event.

    Args:
        event: Full event dict.

    Returns:
        Dict with status, action, and extracted customer data.
    """
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


# Event type to handler mapping
_SHOPIFY_HANDLERS = {
    "orders.create": handle_order_created,
    "customers.create": handle_customer_created,
}


@register_handler("shopify")
def handle_shopify_event(event: dict) -> dict:
    """Main Shopify webhook handler dispatcher.

    Routes to the correct sub-handler based on event_type.

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
