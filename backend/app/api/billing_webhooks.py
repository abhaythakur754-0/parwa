"""
Billing Webhooks API (F-027, BG-16)

FastAPI routes for payment webhooks:
- POST /webhooks/paddle: Receive Paddle webhook events
- POST /webhooks/paddle/payment-failed: Payment failure webhook
- POST /webhooks/paddle/payment-succeeded: Payment success webhook
- GET /billing/status: Check billing status for company

BC-001: All routes validate company_id
BC-003: All responses under 3 seconds
BC-011: Webhook signature verification
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.payment_failure_service import (
    get_payment_failure_service,
    PaymentFailureError,
)

logger = logging.getLogger("parwa.api.billing_webhooks")

router = APIRouter(prefix="/api/v1", tags=["billing-webhooks"])


# ── Pydantic Models ────────────────────────────────────────────────────

class PaddleWebhookPayload(BaseModel):
    """Paddle webhook event payload."""
    event_type: str = Field(..., description="Paddle event type")
    event_id: str = Field(..., description="Unique event ID from Paddle")
    occurred_at: Optional[str] = Field(None, description="Event timestamp")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")


class PaymentFailedWebhook(BaseModel):
    """Payment failed webhook payload."""
    event_type: str = "payment.failed"
    event_id: str
    company_id: str
    paddle_subscription_id: Optional[str] = None
    paddle_transaction_id: str
    failure_code: str
    failure_reason: str
    amount_attempted: Decimal
    currency: str = "USD"


class PaymentSucceededWebhook(BaseModel):
    """Payment succeeded webhook payload."""
    event_type: str = "payment.succeeded"
    event_id: str
    company_id: str
    paddle_subscription_id: Optional[str] = None
    paddle_transaction_id: str
    amount: Decimal
    currency: str = "USD"


class BillingStatusResponse(BaseModel):
    """Billing status response."""
    company_id: str
    subscription_status: str
    service_stopped: bool
    active_failure: Optional[Dict[str, Any]] = None
    last_payment_failure: Optional[Dict[str, Any]] = None


# ── Webhook Signature Verification ──────────────────────────────────────

def verify_paddle_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """
    Verify Paddle webhook signature using HMAC-SHA256.

    B6 FIX: Standardized to PaddleClient's implementation which includes:
    - Parsing the Paddle signature format: ts={timestamp};h1={hash}
    - Verifying the hash is HMAC-SHA256 of '{timestamp}:{payload}'
    - Rejecting signatures older than 5 minutes (replay attack prevention)
    - Constant-time comparison to prevent timing attacks

    BC-011: Cryptographic verification of webhook authenticity.
    """
    if not secret:
        logger.warning("paddle_webhook_no_secret_configured")
        return False

    try:
        import time as _time

        # Parse Paddle signature format: ts={timestamp};h1={hash}
        parts = {}
        for part in signature.split(";"):
            key, _, value = part.partition("=")
            parts[key.strip()] = value.strip()

        ts_str = parts.get("ts")
        h1_hash = parts.get("h1")

        if not ts_str or not h1_hash:
            logger.warning(
                "paddle_webhook_invalid_format sig=%s",
                signature[:50],
            )
            return False

        # Verify timestamp is within 5 minutes (replay attack prevention)
        try:
            ts = int(ts_str)
        except ValueError:
            logger.warning("paddle_webhook_invalid_timestamp ts=%s", ts_str)
            return False

        current_time = int(_time.time())
        if abs(current_time - ts) > 300:  # 5 minutes
            logger.warning(
                "paddle_webhook_expired ts=%d current=%d diff=%d",
                ts, current_time, abs(current_time - ts),
            )
            return False

        # Compute HMAC-SHA256 of '{timestamp}:{payload}'
        signed_payload = f"{ts_str}:".encode() + payload
        expected = hmac.new(
            secret.encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(h1_hash, expected)

    except Exception as exc:
        logger.warning("paddle_webhook_verify_error error=%s", str(exc))
        return False


def extract_company_id_from_event(data: Dict[str, Any]) -> Optional[str]:
    """
    Extract company_id from Paddle event data.

    Tries multiple locations where company_id might be stored:
    - custom_data.company_id
    - passthrough.company_id
    - metadata.company_id
    
    This is also used as a standalone function for tests.
    """
    # Try custom_data first
    custom_data = data.get("custom_data", {}) or {}
    if custom_data.get("company_id"):
        return custom_data["company_id"]

    # Try passthrough (Paddle Classic)
    passthrough = data.get("passthrough", {}) or {}
    if isinstance(passthrough, str):
        try:
            passthrough = json.loads(passthrough)
        except json.JSONDecodeError:
            passthrough = {}
    if passthrough.get("company_id"):
        return passthrough["company_id"]

    # Try metadata
    metadata = data.get("metadata", {}) or {}
    if metadata.get("company_id"):
        return metadata["company_id"]

    return None


# ── Webhook Endpoints ────────────────────────────────────────────────────

@router.post("/webhooks/paddle")
async def handle_paddle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Main Paddle webhook endpoint.

    Receives all Paddle webhook events and routes to appropriate handlers.
    Implements idempotency and signature verification.

    BC-003: Responds immediately, processes in background.
    BC-011: Verifies HMAC-SHA256 signature.
    """
    settings = get_settings()

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    signature = request.headers.get("paddle_signature", "")
    webhook_secret = getattr(settings, "PADDLE_WEBHOOK_SECRET", "")

    if webhook_secret and not verify_paddle_signature(body, signature, webhook_secret):
        logger.warning(
            "paddle_webhook_invalid_signature signature=%s",
            signature[:20] + "..." if signature else "missing",
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event_type", "")
    event_id = payload.get("event_id", payload.get("id", ""))

    # Extract company_id
    data = payload.get("data", {})
    company_id = extract_company_id_from_event(data)

    if not company_id:
        logger.warning(
            "paddle_webhook_missing_company_id event_type=%s event_id=%s",
            event_type,
            event_id,
        )
        # Still return 200 to avoid Paddle retries for non-critical events
        return {"status": "accepted", "warning": "No company_id found"}

    logger.info(
        "paddle_webhook_received event_type=%s event_id=%s company_id=%s",
        event_type,
        event_id,
        company_id,
    )

    # Check idempotency (via webhook_service)
    from app.services.webhook_service import process_webhook

    result = process_webhook(
        company_id=company_id,
        provider="paddle",
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )

    if result.get("duplicate"):
        logger.info(
            "paddle_webhook_duplicate event_id=%s company_id=%s",
            event_id,
            company_id,
        )
        return {"status": "duplicate", "message": "Event already processed"}

    # Route to specific handlers
    if event_type == "payment.failed":
        # Trigger immediate service stop
        background_tasks.add_task(
            _process_payment_failed,
            company_id=company_id,
            event_id=event_id,
            data=data,
        )
    elif event_type == "payment.succeeded":
        # Check if this resolves a previous failure
        background_tasks.add_task(
            _process_payment_succeeded,
            company_id=company_id,
            event_id=event_id,
            data=data,
        )

    return {"status": "accepted", "event_id": event_id}


@router.post("/webhooks/paddle/payment-failed")
async def handle_payment_failed_webhook(
    webhook: PaymentFailedWebhook,
    background_tasks: BackgroundTasks,
):
    """
    Dedicated payment failed webhook endpoint.

    For explicit payment failure handling with company_id in payload.
    This is a convenience endpoint for direct payment failure notifications.
    """
    logger.warning(
        "payment_failed_webhook company_id=%s transaction_id=%s code=%s",
        webhook.company_id,
        webhook.paddle_transaction_id,
        webhook.failure_code,
    )

    # Process immediately
    service = get_payment_failure_service()

    try:
        result = await service.handle_payment_failure(
            company_id=UUID(webhook.company_id),
            paddle_transaction_id=webhook.paddle_transaction_id,
            failure_code=webhook.failure_code,
            failure_reason=webhook.failure_reason,
            amount_attempted=webhook.amount_attempted,
            paddle_subscription_id=webhook.paddle_subscription_id,
            currency=webhook.currency,
        )

        # Trigger background tasks for service stop
        if result.get("status") == "stopped":
            from app.tasks.payment_failure_tasks import stop_service_immediately
            stop_service_immediately.delay(
                company_id=webhook.company_id,
                failure_id=result["failure_id"],
                failure_reason=webhook.failure_reason,
            )

        return result

    except PaymentFailureError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhooks/paddle/payment-succeeded")
async def handle_payment_succeeded_webhook(
    webhook: PaymentSucceededWebhook,
    background_tasks: BackgroundTasks,
):
    """
    Dedicated payment succeeded webhook endpoint.

    Resumes service if company had a previous payment failure.
    """
    logger.info(
        "payment_succeeded_webhook company_id=%s transaction_id=%s",
        webhook.company_id,
        webhook.paddle_transaction_id,
    )

    service = get_payment_failure_service()

    # Check if service was stopped
    is_stopped = await service.is_service_stopped(UUID(webhook.company_id))

    if is_stopped:
        # Resume service
        result = await service.resume_service(
            company_id=UUID(webhook.company_id),
            paddle_transaction_id=webhook.paddle_transaction_id,
        )

        # Trigger background tasks for service resume
        if result.get("status") == "resumed":
            from app.tasks.payment_failure_tasks import resume_service
            resume_service.delay(
                company_id=webhook.company_id,
                transaction_id=webhook.paddle_transaction_id,
            )

        return result

    return {"status": "no_action", "message": "Service was not stopped"}


@router.get("/billing/status/{company_id}", response_model=BillingStatusResponse)
async def get_billing_status(company_id: str):
    """
    Get billing status for a company.

    Returns subscription status and any active payment failures.
    """
    from database.base import SessionLocal
    from database.models.core import Company
    from database.models.billing import Subscription

    with SessionLocal() as db:
        company = db.query(Company).filter(
            Company.id == company_id
        ).first()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        service = get_payment_failure_service()
        service_stopped = await service.is_service_stopped(UUID(company_id))
        active_failure = await service.get_active_failure(UUID(company_id))
        history = await service.get_payment_failure_history(UUID(company_id), limit=1)

    return BillingStatusResponse(
        company_id=company_id,
        subscription_status=company.subscription_status or "none",
        service_stopped=service_stopped,
        active_failure=active_failure,
        last_payment_failure=history[0] if history else None,
    )


# ── Background Task Functions ────────────────────────────────────────────

async def _process_payment_failed(
    company_id: str,
    event_id: str,
    data: Dict[str, Any],
):
    """Process payment failed event in background."""
    try:
        service = get_payment_failure_service()

        # Extract payment data
        transaction_id = data.get("transaction_id", data.get("id", event_id))
        subscription_id = data.get("subscription_id")
        failure_code = data.get("error_code", data.get("failure_code", "unknown"))
        failure_reason = data.get("error_message", data.get("failure_reason", "Unknown error"))

        # Get amount from various possible locations
        amount = Decimal("0")
        if data.get("amount"):
            amount = Decimal(str(data["amount"]))
        elif data.get("total"):
            amount = Decimal(str(data["total"]))

        result = await service.handle_payment_failure(
            company_id=UUID(company_id),
            paddle_transaction_id=transaction_id,
            failure_code=failure_code,
            failure_reason=failure_reason,
            amount_attempted=amount,
            paddle_subscription_id=subscription_id,
        )

        if result.get("status") == "stopped":
            from app.tasks.payment_failure_tasks import stop_service_immediately
            stop_service_immediately.delay(
                company_id=company_id,
                failure_id=result["failure_id"],
                failure_reason=failure_reason,
            )

        logger.info(
            "payment_failed_processed company_id=%s event_id=%s status=%s",
            company_id,
            event_id,
            result.get("status"),
        )

    except Exception as e:
        logger.error(
            "payment_failed_processing_error company_id=%s event_id=%s error=%s",
            company_id,
            event_id,
            str(e)[:200],
        )


async def _process_payment_succeeded(
    company_id: str,
    event_id: str,
    data: Dict[str, Any],
):
    """Process payment succeeded event in background."""
    try:
        service = get_payment_failure_service()
        is_stopped = await service.is_service_stopped(UUID(company_id))

        if is_stopped:
            transaction_id = data.get("transaction_id", data.get("id", event_id))

            result = await service.resume_service(
                company_id=UUID(company_id),
                paddle_transaction_id=transaction_id,
            )

            if result.get("status") == "resumed":
                from app.tasks.payment_failure_tasks import resume_service
                resume_service.delay(
                    company_id=company_id,
                    transaction_id=transaction_id,
                )

            logger.info(
                "payment_succeeded_resumed company_id=%s event_id=%s",
                company_id,
                event_id,
            )

    except Exception as e:
        logger.error(
            "payment_succeeded_processing_error company_id=%s event_id=%s error=%s",
            company_id,
            event_id,
            str(e)[:200],
        )
