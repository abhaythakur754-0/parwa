"""
Shopify Webhook Handler (BC-003, GAP 1.5)

Handles Shopify webhook events:
- orders.create: New order created in Shopify store
- orders.updated: Order updated (status, tracking, etc.)
- orders.cancelled: Order cancelled by customer or merchant
- customers.create: New customer registered
- products.create: New product added to store
- app/uninstalled: Shopify app uninstalled from store

All handlers:
- Validate required fields in payload
- Extract normalized data
- Return structured result for service layer
- Are idempotent (checked at webhook_service level)
- BC-008: Never crash — all errors caught and returned gracefully
- BC-001: All operations scoped to company_id from event context
"""

import logging
from typing import Optional

from app.webhooks import register_handler

logger = logging.getLogger("parwa.webhooks.shopify")

# Required fields per Shopify event type
REQUIRED_FIELDS = {
    "orders.create": ["order_id", "email", "total_price", "currency"],
    "orders.updated": ["order_id", "email", "total_price", "currency"],
    "orders.cancelled": ["order_id", "email"],
    "customers.create": ["customer_id", "email"],
    "products.create": ["product_id", "title"],
    "app/uninstalled": ["shop_domain"],
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
        "cancel_reason": _sanitize_field(order.get("cancel_reason", ""), 50),
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
        "total_spent": str(customer.get("total_spent", "0.00")),
        "tags": _sanitize_field(customer.get("tags", ""), 500),
        "created_at": customer.get("created_at"),
        "updated_at": customer.get("updated_at"),
    }


def _extract_product_data(payload: dict) -> dict:
    """Extract and normalize product data from Shopify payload.

    Shopify sends product data:
    - product: {id, title, body_html, vendor, product_type, variants, ...}
    """
    product = payload.get("product", payload) or {}
    variants = product.get("variants", []) or []
    images = product.get("images", []) or []

    variant_list = []
    for variant in variants[:100]:  # Max 100 variants
        if not isinstance(variant, dict):
            continue
        variant_list.append({
            "variant_id": str(variant.get("id", "")),
            "title": _sanitize_field(variant.get("title", ""), 500),
            "price": str(variant.get("price", "0")),
            "sku": _sanitize_field(variant.get("sku", ""), 100),
            "inventory_quantity": int(variant.get("inventory_quantity", 0)),
            "compare_at_price": str(variant.get("compare_at_price", "")),
        })

    image_urls = []
    for image in images[:20]:  # Max 20 images
        if isinstance(image, dict) and image.get("src"):
            image_urls.append(_sanitize_field(image["src"], 2000))

    return {
        "product_id": str(product.get("id", "")),
        "title": _sanitize_field(product.get("title", ""), 500),
        "body_html": _sanitize_field(product.get("body_html", ""), 5000),
        "vendor": _sanitize_field(product.get("vendor", ""), 200),
        "product_type": _sanitize_field(product.get("product_type", ""), 200),
        "status": _sanitize_field(product.get("status", ""), 30),
        "tags": _sanitize_field(product.get("tags", ""), 500),
        "published_at": product.get("published_at"),
        "variants": variant_list,
        "images": image_urls,
        "created_at": product.get("created_at"),
        "updated_at": product.get("updated_at"),
    }


def _extract_shop_data(payload: dict) -> dict:
    """Extract shop data from app/uninstalled payload.

    Shopify sends shop data on app uninstall:
    - shop: {id, name, domain, email, ...}
    """
    # The app/uninstalled webhook may include shop details in the payload
    shop_domain = payload.get("shop_domain", "")
    shop_data = payload.get("shop", {}) or {}

    return {
        "shop_domain": _sanitize_field(shop_domain, 254),
        "shop_id": str(shop_data.get("id", "")),
        "shop_name": _sanitize_field(shop_data.get("name", ""), 200),
        "shop_email": _sanitize_field(shop_data.get("email", ""), 254),
        "shop_domain_full": _sanitize_field(
            shop_data.get("domain", shop_domain), 254
        ),
        "uninstalled_at": payload.get("uninstalled_at"),
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


# ── Event Handlers ────────────────────────────────────────────────


def handle_order_created(event: dict) -> dict:
    """Handle Shopify orders/create event.

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


def handle_order_updated(event: dict) -> dict:
    """Handle Shopify orders/updated event.

    Triggered when an order's financial_status, fulfillment_status,
    or other fields change. Important for tracking order lifecycle.

    Args:
        event: Full event dict with event_type "orders.updated".

    Returns:
        Dict with status, action, and extracted order data.
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

    Triggered when an order is cancelled by customer or merchant.
    Critical for refund processing and inventory restoration.

    Args:
        event: Full event dict with event_type "orders.cancelled".

    Returns:
        Dict with status, action, and extracted order data including
        cancel_reason and cancelled_at timestamp.
    """
    payload = event.get("payload", {})
    order_data = _extract_order_data(payload)

    # Override: cancelled orders may not have total_price after cancellation
    # but must have order_id and email
    error = _validate_required_fields("orders.cancelled", order_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_order_cancelled order_id=%s reason=%s cancelled_at=%s",
        order_data["order_id"],
        order_data.get("cancel_reason", "unknown"),
        order_data.get("cancelled_at"),
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
    """Handle Shopify customers/create event.

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


def handle_product_created(event: dict) -> dict:
    """Handle Shopify products/create event.

    Triggered when a new product is added to the Shopify store.
    Extracts product data including variants, images, and metadata.

    Args:
        event: Full event dict with event_type "products.create".

    Returns:
        Dict with status, action, and extracted product data.
    """
    payload = event.get("payload", {})
    product_data = _extract_product_data(payload)

    error = _validate_required_fields("products.create", product_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "shopify_product_created product_id=%s title=%s",
        product_data["product_id"],
        product_data["title"][:50],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "product_created",
        "data": product_data,
    }


def handle_app_uninstalled(event: dict) -> dict:
    """Handle Shopify app/uninstalled event.

    Triggered when a merchant uninstalls the PARWA app from their
    Shopify store. Critical for cleanup: mark integration as
    disconnected, stop webhook processing, disable data sync.

    Args:
        event: Full event dict with event_type "app/uninstalled".

    Returns:
        Dict with status, action, and extracted shop data.
    """
    payload = event.get("payload", {})
    shop_data = _extract_shop_data(payload)

    error = _validate_required_fields("app/uninstalled", shop_data)
    if error:
        # For app/uninstalled, we still process even if fields are missing
        # because the shop_domain may be in the event context
        shop_domain = event.get("shop_domain", "")
        if shop_domain:
            shop_data["shop_domain"] = shop_domain
        else:
            return {"status": "validation_error", "error": error}

    logger.warning(
        "shopify_app_uninstalled shop_domain=%s shop_id=%s",
        shop_data.get("shop_domain"),
        shop_data.get("shop_id"),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "app_uninstalled",
        "data": shop_data,
    }


# Event type to handler mapping
_SHOPIFY_HANDLERS = {
    "orders.create": handle_order_created,
    "orders.updated": handle_order_updated,
    "orders.cancelled": handle_order_cancelled,
    "customers.create": handle_customer_created,
    "products.create": handle_product_created,
    "app/uninstalled": handle_app_uninstalled,
}


@register_handler("shopify")
def handle_shopify_event(event: dict) -> dict:
    """Main Shopify webhook handler dispatcher.

    Routes to the correct sub-handler based on event_type.
    Supports 6 event types:
    - orders.create, orders.updated, orders.cancelled
    - customers.create
    - products.create
    - app/uninstalled

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

    try:
        return handler(event)
    except Exception as exc:
        logger.error(
            "shopify_handler_error type=%s error=%s",
            event_type, str(exc)[:200],
            extra={
                "company_id": event.get("company_id"),
                "event_id": event.get("event_id"),
            },
        )
        return {
            "status": "handler_error",
            "error": f"Handler error for {event_type}: {str(exc)[:200]}",
        }
