"""
Paddle Webhook Handler (BC-003, BG-01, W5D5)

Handles ALL Paddle webhook events (25+ events) for subscription and payment lifecycle:
- Subscription Events (7): created, updated, activated, canceled, past_due, paused, resumed
- Transaction Events (5): completed, paid, payment_failed, canceled, updated
- Customer Events (3): created, updated, deleted
- Price Events (3): created, updated, deleted
- Discount Events (3): created, updated, deleted
- Credit Events (3): created, updated, deleted
- Adjustment Events (2): created, updated
- Report Events (2): created, updated

All handlers:
- Validate required fields in payload
- Return structured result dicts
- Are idempotent (checked at webhook_service level)
- Support webhook ordering via webhook_ordering_service
- Use idempotency keys via webhook_processor
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.webhooks import register_handler
from app.schemas.paddle import PaddleEventType, SUPPORTED_EVENT_TYPES

logger = logging.getLogger("parwa.webhooks.paddle")

# Required fields per Paddle event type
REQUIRED_FIELDS = {
    # Subscription events
    "subscription.created": ["subscription_id", "customer_id"],
    "subscription.updated": ["subscription_id"],
    "subscription.activated": ["subscription_id", "customer_id"],
    "subscription.canceled": ["subscription_id"],
    "subscription.past_due": ["subscription_id"],
    "subscription.paused": ["subscription_id"],
    "subscription.resumed": ["subscription_id"],
    # Transaction events
    "transaction.completed": ["transaction_id"],
    "transaction.paid": ["transaction_id"],
    "transaction.payment_failed": ["transaction_id"],
    "transaction.canceled": ["transaction_id"],
    "transaction.updated": ["transaction_id"],
    # Customer events
    "customer.created": ["customer_id"],
    "customer.updated": ["customer_id"],
    "customer.deleted": ["customer_id"],
    # Price events
    "price.created": ["price_id"],
    "price.updated": ["price_id"],
    "price.deleted": ["price_id"],
    # Discount events
    "discount.created": ["discount_id"],
    "discount.updated": ["discount_id"],
    "discount.deleted": ["discount_id"],
    # Credit events
    "credit.created": ["credit_id"],
    "credit.updated": ["credit_id"],
    "credit.deleted": ["credit_id"],
    # Adjustment events
    "adjustment.created": ["adjustment_id"],
    "adjustment.updated": ["adjustment_id"],
    # Report events
    "report.created": ["report_id"],
    "report.updated": ["report_id"],
}


# ── Data Extraction Functions ────────────────────────────────────────────────

def _extract_subscription_data(payload: dict) -> dict:
    """Extract subscription data from Paddle payload.

    Normalizes field names between Paddle Classic and Paddle Billing.
    Returns a dict with standard PARWA field names.
    """
    data = payload.get("data", {})
    subscription = data.get("subscription", data) or {}
    customer = data.get("customer", {}) or {}
    items = subscription.get("items", []) or []

    return {
        "subscription_id": subscription.get("id") or subscription.get("subscription_id"),
        "customer_id": customer.get("id") or customer.get("customer_id"),
        "status": subscription.get("status", "active"),
        "plan_id": subscription.get("plan_id") or (items[0].get("price_id") if items else None),
        "quantity": sum(item.get("quantity", 1) for item in items),
        "next_billing_date": subscription.get("next_billed_at") or subscription.get("next_billing_date"),
        "trial_end": subscription.get("trial_end"),
        "currency": subscription.get("currency_code", "USD"),
        "items": items,
        "custom_data": subscription.get("custom_data"),
        "created_at": subscription.get("created_at"),
        "updated_at": subscription.get("updated_at"),
        "paused_at": subscription.get("paused_at"),
        "canceled_at": subscription.get("canceled_at"),
    }


def _extract_transaction_data(payload: dict) -> dict:
    """Extract transaction data from Paddle payload."""
    data = payload.get("data", {})
    transaction = data.get("transaction", data) or {}
    details = transaction.get("details", {}) or {}

    return {
        "transaction_id": transaction.get("id") or transaction.get("transaction_id"),
        "subscription_id": transaction.get("subscription_id"),
        "customer_id": transaction.get("customer_id"),
        "invoice_id": transaction.get("invoice_id"),
        "status": transaction.get("status", "pending"),
        "amount": details.get("totals", {}).get("total") or transaction.get("total"),
        "currency": details.get("currency_code") or transaction.get("currency_code", "USD"),
        "tax": details.get("totals", {}).get("tax"),
        "discount": details.get("totals", {}).get("discount"),
        "payment_method": transaction.get("payment_method", "card"),
        "error_code": transaction.get("error", {}).get("code"),
        "error_detail": transaction.get("error", {}).get("detail"),
        "created_at": transaction.get("created_at"),
        "updated_at": transaction.get("updated_at"),
        "billed_at": transaction.get("billed_at"),
    }


def _extract_customer_data(payload: dict) -> dict:
    """Extract customer data from Paddle payload."""
    data = payload.get("data", {})
    customer = data.get("customer", data) or {}

    return {
        "customer_id": customer.get("id") or customer.get("customer_id"),
        "email": customer.get("email"),
        "name": customer.get("name"),
        "status": customer.get("status", "active"),
        "custom_data": customer.get("custom_data"),
        "created_at": customer.get("created_at"),
        "updated_at": customer.get("updated_at"),
    }


def _extract_price_data(payload: dict) -> dict:
    """Extract price/variant data from Paddle payload."""
    data = payload.get("data", {})
    price = data.get("price", data) or {}

    return {
        "price_id": price.get("id") or price.get("price_id"),
        "product_id": price.get("product_id"),
        "name": price.get("name"),
        "status": price.get("status", "active"),
        "unit_price": price.get("unit_price"),
        "currency_code": price.get("unit_price", {}).get("currency_code") if isinstance(price.get("unit_price"), dict) else None,
        "amount": price.get("unit_price", {}).get("amount") if isinstance(price.get("unit_price"), dict) else None,
        "created_at": price.get("created_at"),
        "updated_at": price.get("updated_at"),
    }


def _extract_discount_data(payload: dict) -> dict:
    """Extract discount data from Paddle payload."""
    data = payload.get("data", {})
    discount = data.get("discount", data) or {}

    return {
        "discount_id": discount.get("id") or discount.get("discount_id"),
        "code": discount.get("code"),
        "status": discount.get("status", "active"),
        "type": discount.get("type"),
        "amount": discount.get("amount"),
        "currency_code": discount.get("currency_code"),
        "created_at": discount.get("created_at"),
        "updated_at": discount.get("updated_at"),
    }


def _extract_credit_data(payload: dict) -> dict:
    """Extract credit data from Paddle payload."""
    data = payload.get("data", {})
    credit = data.get("credit", data) or {}

    return {
        "credit_id": credit.get("id") or credit.get("credit_id"),
        "customer_id": credit.get("customer_id"),
        "amount": credit.get("amount"),
        "currency_code": credit.get("currency_code"),
        "description": credit.get("description"),
        "created_at": credit.get("created_at"),
    }


def _extract_adjustment_data(payload: dict) -> dict:
    """Extract adjustment data from Paddle payload."""
    data = payload.get("data", {})
    adjustment = data.get("adjustment", data) or {}

    return {
        "adjustment_id": adjustment.get("id") or adjustment.get("adjustment_id"),
        "transaction_id": adjustment.get("transaction_id"),
        "subscription_id": adjustment.get("subscription_id"),
        "customer_id": adjustment.get("customer_id"),
        "amount": adjustment.get("amount"),
        "currency_code": adjustment.get("currency_code"),
        "reason": adjustment.get("reason"),
        "created_at": adjustment.get("created_at"),
    }


def _extract_report_data(payload: dict) -> dict:
    """Extract report data from Paddle payload."""
    data = payload.get("data", {})
    report = data.get("report", data) or {}

    return {
        "report_id": report.get("id") or report.get("report_id"),
        "status": report.get("status"),
        "type": report.get("type"),
        "filters": report.get("filters"),
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
    }


def _validate_required_fields(
    event_type: str, data: dict,
) -> Optional[str]:
    """Validate that required fields exist in extracted data.

    GAP 5 fix: Enhanced validation for:
    - Missing fields
    - Empty strings
    - Null values

    Returns:
        Error message string if validation fails, None if OK.
    """
    required = REQUIRED_FIELDS.get(event_type, [])
    for field in required:
        if field not in data:
            return f"Missing required field: {field}"
        value = data[field]
        if value is None:
            return f"Field {field} cannot be null"
        if isinstance(value, str) and not value.strip():
            return f"Field {field} cannot be empty"
    return None


def _parse_occurred_at(event: dict) -> datetime:
    """Parse occurred_at timestamp from event."""
    occurred_str = event.get("occurred_at") or event.get("occurred_at")
    if occurred_str:
        if isinstance(occurred_str, datetime):
            return occurred_str
        try:
            return datetime.fromisoformat(occurred_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc)


# ── Subscription Event Handlers (7 handlers) ────────────────────────────────

def handle_subscription_created(event: dict) -> dict:
    """Handle subscription.created event."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)

    error = _validate_required_fields("subscription.created", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_created subscription_id=%s customer_id=%s",
        sub_data["subscription_id"],
        sub_data["customer_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_created",
        "data": sub_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_subscription_updated(event: dict) -> dict:
    """Handle subscription.updated event (plan change, etc.)."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)
    previous = payload.get("previous_attributes", {})

    error = _validate_required_fields("subscription.updated", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_updated subscription_id=%s status=%s",
        sub_data["subscription_id"],
        sub_data["status"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
            "previous_status": previous.get("status"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_updated",
        "data": sub_data,
        "previous_attributes": previous,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_subscription_activated(event: dict) -> dict:
    """Handle subscription.activated event."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)

    error = _validate_required_fields("subscription.activated", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_activated subscription_id=%s",
        sub_data["subscription_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_activated",
        "data": sub_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_subscription_canceled(event: dict) -> dict:
    """Handle subscription.canceled event."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)
    sub_data["cancellation_reason"] = payload.get("data", {}).get(
        "cancellation_reason", "user_requested",
    )

    error = _validate_required_fields("subscription.canceled", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_canceled subscription_id=%s reason=%s",
        sub_data["subscription_id"],
        sub_data["cancellation_reason"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_canceled",
        "data": sub_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_subscription_past_due(event: dict) -> dict:
    """Handle subscription.past_due event."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)

    error = _validate_required_fields("subscription.past_due", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.warning(
        "paddle_subscription_past_due subscription_id=%s",
        sub_data["subscription_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_past_due",
        "data": sub_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_subscription_paused(event: dict) -> dict:
    """Handle subscription.paused event."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)

    error = _validate_required_fields("subscription.paused", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_paused subscription_id=%s",
        sub_data["subscription_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_paused",
        "data": sub_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_subscription_resumed(event: dict) -> dict:
    """Handle subscription.resumed event."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)

    error = _validate_required_fields("subscription.resumed", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_resumed subscription_id=%s",
        sub_data["subscription_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_resumed",
        "data": sub_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Transaction Event Handlers (5 handlers) ────────────────────────────────

def handle_transaction_completed(event: dict) -> dict:
    """Handle transaction.completed event."""
    payload = event.get("payload", {})
    tx_data = _extract_transaction_data(payload)

    error = _validate_required_fields("transaction.completed", tx_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_transaction_completed transaction_id=%s amount=%s %s",
        tx_data["transaction_id"],
        tx_data.get("amount"),
        tx_data.get("currency", "USD"),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
            "subscription_id": tx_data.get("subscription_id"),
        },
    )

    return {
        "status": "processed",
        "action": "transaction_completed",
        "data": tx_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_transaction_paid(event: dict) -> dict:
    """Handle transaction.paid event."""
    payload = event.get("payload", {})
    tx_data = _extract_transaction_data(payload)

    error = _validate_required_fields("transaction.paid", tx_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_transaction_paid transaction_id=%s amount=%s %s",
        tx_data["transaction_id"],
        tx_data.get("amount"),
        tx_data.get("currency", "USD"),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "transaction_paid",
        "data": tx_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_transaction_payment_failed(event: dict) -> dict:
    """Handle transaction.payment_failed event."""
    payload = event.get("payload", {})
    tx_data = _extract_transaction_data(payload)

    error = _validate_required_fields("transaction.payment_failed", tx_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.warning(
        "paddle_transaction_payment_failed transaction_id=%s error=%s",
        tx_data["transaction_id"],
        tx_data.get("error_code"),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
            "subscription_id": tx_data.get("subscription_id"),
        },
    )

    return {
        "status": "processed",
        "action": "transaction_payment_failed",
        "data": tx_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_transaction_canceled(event: dict) -> dict:
    """Handle transaction.canceled event."""
    payload = event.get("payload", {})
    tx_data = _extract_transaction_data(payload)

    error = _validate_required_fields("transaction.canceled", tx_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_transaction_canceled transaction_id=%s",
        tx_data["transaction_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "transaction_canceled",
        "data": tx_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_transaction_updated(event: dict) -> dict:
    """Handle transaction.updated event."""
    payload = event.get("payload", {})
    tx_data = _extract_transaction_data(payload)

    error = _validate_required_fields("transaction.updated", tx_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_transaction_updated transaction_id=%s status=%s",
        tx_data["transaction_id"],
        tx_data.get("status"),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "transaction_updated",
        "data": tx_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Customer Event Handlers (3 handlers) ───────────────────────────────────

def handle_customer_created(event: dict) -> dict:
    """Handle customer.created event."""
    payload = event.get("payload", {})
    cust_data = _extract_customer_data(payload)

    error = _validate_required_fields("customer.created", cust_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_customer_created customer_id=%s email=%s",
        cust_data["customer_id"],
        cust_data.get("email", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "customer_created",
        "data": cust_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_customer_updated(event: dict) -> dict:
    """Handle customer.updated event."""
    payload = event.get("payload", {})
    cust_data = _extract_customer_data(payload)
    previous = payload.get("previous_attributes", {})

    error = _validate_required_fields("customer.updated", cust_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_customer_updated customer_id=%s",
        cust_data["customer_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
            "previous_email": previous.get("email"),
        },
    )

    return {
        "status": "processed",
        "action": "customer_updated",
        "data": cust_data,
        "previous_attributes": previous,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_customer_deleted(event: dict) -> dict:
    """Handle customer.deleted event."""
    payload = event.get("payload", {})
    cust_data = _extract_customer_data(payload)

    error = _validate_required_fields("customer.deleted", cust_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_customer_deleted customer_id=%s",
        cust_data["customer_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "customer_deleted",
        "data": cust_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Price Event Handlers (3 handlers) ──────────────────────────────────────

def handle_price_created(event: dict) -> dict:
    """Handle price.created event."""
    payload = event.get("payload", {})
    price_data = _extract_price_data(payload)

    error = _validate_required_fields("price.created", price_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_price_created price_id=%s product_id=%s",
        price_data["price_id"],
        price_data.get("product_id"),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "price_created",
        "data": price_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_price_updated(event: dict) -> dict:
    """Handle price.updated event."""
    payload = event.get("payload", {})
    price_data = _extract_price_data(payload)

    error = _validate_required_fields("price.updated", price_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_price_updated price_id=%s",
        price_data["price_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "price_updated",
        "data": price_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_price_deleted(event: dict) -> dict:
    """Handle price.deleted event."""
    payload = event.get("payload", {})
    price_data = _extract_price_data(payload)

    error = _validate_required_fields("price.deleted", price_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_price_deleted price_id=%s",
        price_data["price_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "price_deleted",
        "data": price_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Discount Event Handlers (3 handlers) ───────────────────────────────────

def handle_discount_created(event: dict) -> dict:
    """Handle discount.created event."""
    payload = event.get("payload", {})
    discount_data = _extract_discount_data(payload)

    error = _validate_required_fields("discount.created", discount_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_discount_created discount_id=%s code=%s",
        discount_data["discount_id"],
        discount_data.get("code", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "discount_created",
        "data": discount_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_discount_updated(event: dict) -> dict:
    """Handle discount.updated event."""
    payload = event.get("payload", {})
    discount_data = _extract_discount_data(payload)

    error = _validate_required_fields("discount.updated", discount_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_discount_updated discount_id=%s",
        discount_data["discount_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "discount_updated",
        "data": discount_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_discount_deleted(event: dict) -> dict:
    """Handle discount.deleted event."""
    payload = event.get("payload", {})
    discount_data = _extract_discount_data(payload)

    error = _validate_required_fields("discount.deleted", discount_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_discount_deleted discount_id=%s",
        discount_data["discount_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "discount_deleted",
        "data": discount_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Credit Event Handlers (3 handlers) ─────────────────────────────────────

def handle_credit_created(event: dict) -> dict:
    """Handle credit.created event."""
    payload = event.get("payload", {})
    credit_data = _extract_credit_data(payload)

    error = _validate_required_fields("credit.created", credit_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_credit_created credit_id=%s customer_id=%s amount=%s",
        credit_data["credit_id"],
        credit_data.get("customer_id", ""),
        credit_data.get("amount", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "credit_created",
        "data": credit_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_credit_updated(event: dict) -> dict:
    """Handle credit.updated event."""
    payload = event.get("payload", {})
    credit_data = _extract_credit_data(payload)

    error = _validate_required_fields("credit.updated", credit_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_credit_updated credit_id=%s",
        credit_data["credit_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "credit_updated",
        "data": credit_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_credit_deleted(event: dict) -> dict:
    """Handle credit.deleted event."""
    payload = event.get("payload", {})
    credit_data = _extract_credit_data(payload)

    error = _validate_required_fields("credit.deleted", credit_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_credit_deleted credit_id=%s",
        credit_data["credit_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "credit_deleted",
        "data": credit_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Adjustment Event Handlers (2 handlers) ─────────────────────────────────

def handle_adjustment_created(event: dict) -> dict:
    """Handle adjustment.created event."""
    payload = event.get("payload", {})
    adj_data = _extract_adjustment_data(payload)

    error = _validate_required_fields("adjustment.created", adj_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_adjustment_created adjustment_id=%s transaction_id=%s amount=%s",
        adj_data["adjustment_id"],
        adj_data.get("transaction_id", ""),
        adj_data.get("amount", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "adjustment_created",
        "data": adj_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_adjustment_updated(event: dict) -> dict:
    """Handle adjustment.updated event."""
    payload = event.get("payload", {})
    adj_data = _extract_adjustment_data(payload)

    error = _validate_required_fields("adjustment.updated", adj_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_adjustment_updated adjustment_id=%s",
        adj_data["adjustment_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "adjustment_updated",
        "data": adj_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Report Event Handlers (2 handlers) ─────────────────────────────────────

def handle_report_created(event: dict) -> dict:
    """Handle report.created event."""
    payload = event.get("payload", {})
    report_data = _extract_report_data(payload)

    error = _validate_required_fields("report.created", report_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_report_created report_id=%s type=%s",
        report_data["report_id"],
        report_data.get("type", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "report_created",
        "data": report_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


def handle_report_updated(event: dict) -> dict:
    """Handle report.updated event."""
    payload = event.get("payload", {})
    report_data = _extract_report_data(payload)

    error = _validate_required_fields("report.updated", report_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_report_updated report_id=%s status=%s",
        report_data["report_id"],
        report_data.get("status", ""),
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "report_updated",
        "data": report_data,
        "occurred_at": _parse_occurred_at(event).isoformat(),
    }


# ── Handler Registry (25+ handlers) ────────────────────────────────────────

_PADDLE_HANDLERS = {
    # Subscription events (7)
    "subscription.created": handle_subscription_created,
    "subscription.updated": handle_subscription_updated,
    "subscription.activated": handle_subscription_activated,
    "subscription.canceled": handle_subscription_canceled,
    "subscription.past_due": handle_subscription_past_due,
    "subscription.paused": handle_subscription_paused,
    "subscription.resumed": handle_subscription_resumed,
    # Transaction events (5)
    "transaction.completed": handle_transaction_completed,
    "transaction.paid": handle_transaction_paid,
    "transaction.payment_failed": handle_transaction_payment_failed,
    "transaction.canceled": handle_transaction_canceled,
    "transaction.updated": handle_transaction_updated,
    # Customer events (3)
    "customer.created": handle_customer_created,
    "customer.updated": handle_customer_updated,
    "customer.deleted": handle_customer_deleted,
    # Price events (3)
    "price.created": handle_price_created,
    "price.updated": handle_price_updated,
    "price.deleted": handle_price_deleted,
    # Discount events (3)
    "discount.created": handle_discount_created,
    "discount.updated": handle_discount_updated,
    "discount.deleted": handle_discount_deleted,
    # Credit events (3)
    "credit.created": handle_credit_created,
    "credit.updated": handle_credit_updated,
    "credit.deleted": handle_credit_deleted,
    # Adjustment events (2)
    "adjustment.created": handle_adjustment_created,
    "adjustment.updated": handle_adjustment_updated,
    # Report events (2)
    "report.created": handle_report_created,
    "report.updated": handle_report_updated,
}

# Backward compatibility aliases
_PADDLE_HANDLERS["subscription.cancelled"] = handle_subscription_canceled
_PADDLE_HANDLERS["payment.succeeded"] = handle_transaction_paid
_PADDLE_HANDLERS["payment.failed"] = handle_transaction_payment_failed


def get_supported_event_types() -> list:
    """Return list of all supported Paddle event types."""
    return list(_PADDLE_HANDLERS.keys())


def _validate_event_type(event_type: str) -> Optional[str]:
    """Validate event_type is supported.

    Returns:
        Error message if invalid, None if valid.
    """
    if not event_type or not isinstance(event_type, str):
        return "event_type is required and must be a string"

    event_type = event_type.strip()
    if not event_type:
        return "event_type cannot be empty"

    if event_type not in _PADDLE_HANDLERS:
        return (
            f"Unsupported event_type: {event_type}. "
            f"Supported types: {len(_PADDLE_HANDLERS)} events"
        )

    return None


@register_handler("paddle")
def handle_paddle_event(event: dict) -> dict:
    """Main Paddle webhook handler dispatcher.

    Routes to the correct sub-handler based on event_type.
    Returns validation_error for unknown event types.

    Args:
        event: Full event dict with keys:
            - event_type: Paddle event type string
            - payload: Raw Paddle payload dict
            - company_id: Tenant company ID
            - event_id: Provider event ID

    Returns:
        Dict with status, action, and extracted data.
    """
    event_type = event.get("event_type", "")

    # Validate event_type
    type_error = _validate_event_type(event_type)
    if type_error:
        logger.warning(
            "paddle_invalid_event_type type=%s event_id=%s error=%s",
            event_type,
            event.get("event_id"),
            type_error,
            extra={"company_id": event.get("company_id")},
        )
        return {
            "status": "validation_error",
            "error": type_error,
            "supported_types_count": len(_PADDLE_HANDLERS),
        }

    # Validate company_id is present
    company_id = event.get("company_id")
    if not company_id:
        logger.warning(
            "paddle_missing_company_id event_id=%s",
            event.get("event_id"),
        )
        return {
            "status": "validation_error",
            "error": "Missing company_id in event",
        }

    # Validate event_id is present
    event_id = event.get("event_id")
    if not event_id:
        logger.warning(
            "paddle_missing_event_id company_id=%s",
            company_id,
        )
        return {
            "status": "validation_error",
            "error": "Missing event_id in event",
        }

    handler = _PADDLE_HANDLERS.get(event_type)
    if not handler:
        logger.warning(
            "paddle_unknown_event_type type=%s event_id=%s",
            event_type,
            event.get("event_id"),
            extra={"company_id": event.get("company_id")},
        )
        return {
            "status": "validation_error",
            "error": f"Unknown Paddle event type: {event_type}",
            "supported_types_count": len(_PADDLE_HANDLERS),
        }

    return handler(event)
