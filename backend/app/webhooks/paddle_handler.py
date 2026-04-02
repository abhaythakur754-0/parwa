"""
Paddle Webhook Handler (BC-003, GAP 1.5)

Handles Paddle webhook events for subscription and payment lifecycle:
- subscription.created: New subscription activation
- subscription.updated: Plan change, quantity change
- subscription.cancelled: Subscription termination
- payment.succeeded: Successful payment/charge
- payment.failed: Failed payment attempt

All handlers:
- Validate required fields in payload
- Return structured result dicts
- Are idempotent (checked at webhook_service level)
- Do NOT make external API calls (service layer handles that)
"""

import logging
from typing import Optional

from backend.app.webhooks import register_handler

logger = logging.getLogger("parwa.webhooks.paddle")

# Required fields per Paddle event type
REQUIRED_FIELDS = {
    "subscription.created": ["subscription_id", "plan_id", "customer_id"],
    "subscription.updated": ["subscription_id", "plan_id"],
    "subscription.cancelled": ["subscription_id", "cancellation_reason"],
    "payment.succeeded": ["payment_id", "subscription_id", "amount", "currency"],
    "payment.failed": ["payment_id", "subscription_id", "error_code"],
}


def _extract_subscription_data(payload: dict) -> dict:
    """Extract subscription data from Paddle payload.

    Normalizes field names between Paddle Classic and Paddle Billing.
    Returns a dict with standard PARWA field names.
    """
    data = payload.get("data", {})
    subscription = data.get("subscription", data) or {}
    customer = data.get("customer", {}) or {}

    return {
        "subscription_id": subscription.get("subscription_id") or subscription.get("id"),
        "plan_id": subscription.get("plan_id") or subscription.get("product_id"),
        "customer_id": customer.get("customer_id") or customer.get("id"),
        "status": subscription.get("status", "active"),
        "quantity": subscription.get("quantity", 1),
        "next_billing_date": subscription.get("next_billing_date"),
        "trial_end": subscription.get("trial_end"),
        "currency": subscription.get("currency", "USD"),
    }


def _extract_payment_data(payload: dict) -> dict:
    """Extract payment data from Paddle payload.

    Normalizes field names between Paddle versions.
    """
    data = payload.get("data", {})
    payment = data.get("payment", data) or {}
    billing_details = data.get("billing_details", {}) or {}

    return {
        "payment_id": payment.get("payment_id") or payment.get("id"),
        "subscription_id": payment.get("subscription_id"),
        "amount": payment.get("amount") or payment.get("total", "0"),
        "currency": payment.get("currency") or billing_details.get("currency", "USD"),
        "status": payment.get("status", "completed"),
        "method": payment.get("payment_method", "card"),
        "error_code": payment.get("error_code"),
    }


def _validate_required_fields(
    event_type: str, data: dict,
) -> Optional[str]:
    """Validate that required fields exist in extracted data.

    Returns:
        Error message string if validation fails, None if OK.
    """
    required = REQUIRED_FIELDS.get(event_type, [])
    for field in required:
        if field not in data or not data[field]:
            return f"Missing required field: {field}"
    return None


def handle_subscription_created(event: dict) -> dict:
    """Handle subscription.created event.

    Extracts subscription data and returns normalized result.
    Business logic (DB writes) happens in service layer.
    """
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)

    error = _validate_required_fields("subscription.created", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_created subscription_id=%s plan_id=%s",
        sub_data["subscription_id"],
        sub_data["plan_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_created",
        "data": sub_data,
    }


def handle_subscription_updated(event: dict) -> dict:
    """Handle subscription.updated event (plan change, etc.)."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)

    error = _validate_required_fields("subscription.updated", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_updated subscription_id=%s plan_id=%s",
        sub_data["subscription_id"],
        sub_data["plan_id"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_updated",
        "data": sub_data,
    }


def handle_subscription_cancelled(event: dict) -> dict:
    """Handle subscription.cancelled event."""
    payload = event.get("payload", {})
    sub_data = _extract_subscription_data(payload)
    sub_data["cancellation_reason"] = payload.get("data", {}).get(
        "cancellation_reason", "user_requested",
    )

    error = _validate_required_fields("subscription.cancelled", sub_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_subscription_cancelled subscription_id=%s reason=%s",
        sub_data["subscription_id"],
        sub_data["cancellation_reason"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "subscription_cancelled",
        "data": sub_data,
    }


def handle_payment_succeeded(event: dict) -> dict:
    """Handle payment.succeeded event."""
    payload = event.get("payload", {})
    pay_data = _extract_payment_data(payload)

    error = _validate_required_fields("payment.succeeded", pay_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.info(
        "paddle_payment_succeeded payment_id=%s amount=%s %s",
        pay_data["payment_id"],
        pay_data["amount"],
        pay_data["currency"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "payment_succeeded",
        "data": pay_data,
    }


def handle_payment_failed(event: dict) -> dict:
    """Handle payment.failed event."""
    payload = event.get("payload", {})
    pay_data = _extract_payment_data(payload)

    error = _validate_required_fields("payment.failed", pay_data)
    if error:
        return {"status": "validation_error", "error": error}

    logger.warning(
        "paddle_payment_failed payment_id=%s error=%s",
        pay_data["payment_id"],
        pay_data["error_code"],
        extra={
            "company_id": event.get("company_id"),
            "event_id": event.get("event_id"),
        },
    )

    return {
        "status": "processed",
        "action": "payment_failed",
        "data": pay_data,
    }


# Event type to handler mapping
_PADDLE_HANDLERS = {
    "subscription.created": handle_subscription_created,
    "subscription.updated": handle_subscription_updated,
    "subscription.cancelled": handle_subscription_cancelled,
    "payment.succeeded": handle_payment_succeeded,
    "payment.failed": handle_payment_failed,
}


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
            "supported_types": list(_PADDLE_HANDLERS.keys()),
        }

    return handler(event)
