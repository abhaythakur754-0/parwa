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

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, Optional
from uuid import UUID

# H-08: Maximum age for webhook events (5 minutes) — prevents replay attacks
MAX_WEBHOOK_AGE_SECONDS = 300

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin
from app.clients.paddle_client import get_paddle_client
from app.config import get_settings
from app.services.payment_failure_service import (
    get_payment_failure_service,
    PaymentFailureError,
)
from database.base import SessionLocal, get_db
from database.models.core import User, Company

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
# BC-011: Signature verification is delegated to PaddleClient.verify_webhook_signature()
# which implements the correct Paddle Billing format (ts=;h1=) rather than the
# Paddle Classic HMAC-SHA256(secret, raw_body) format that was previously used here.


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

    # Verify signature using PaddleClient (correct Paddle Billing ts=;h1= format)
    # Paddle sends the header as "Paddle-Signature" (hyphen), not "paddle_signature" (underscore)
    signature = request.headers.get("Paddle-Signature", "")
    webhook_secret = getattr(settings, "PADDLE_WEBHOOK_SECRET", "")

    # H-07/M-36 FIX: ALWAYS reject webhooks when no secret is configured.
    # No environment bypasses — fail closed in ALL environments.
    if not webhook_secret:
        logger.error(
            "paddle_webhook_no_secret_configured_rejected",
            extra={"source_ip": request.client.host if request.client else None},
        )
        raise HTTPException(
            status_code=500,
            detail="Webhook not configured — PADDLE_WEBHOOK_SECRET is required",
        )

    # Use PaddleClient.verify_webhook_signature() for correct Paddle Billing verification
    paddle_client = get_paddle_client()
    if not paddle_client.verify_webhook_signature(body, signature):
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

    # H-08: Verify timestamp freshness to prevent replay attacks.
    # Fail-closed: reject if timestamp is missing or unparseable.
    occurred_at = (
        payload.get("occurred_at")
        or payload.get("created_at")
        or payload.get("timestamp")
        or payload.get("event_time")
    )
    if not occurred_at:
        logger.error(
            "paddle_webhook_replay_rejected_no_timestamp",
            extra={"source_ip": request.client.host if request.client else None},
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Webhook event has no timestamp. "
                "Rejecting as potential replay attack."
            ),
        )
    try:
        if isinstance(occurred_at, datetime):
            event_time = occurred_at
        else:
            event_time = datetime.fromisoformat(
                str(occurred_at).replace("Z", "+00:00")
            )
        age = (datetime.now(timezone.utc) - event_time).total_seconds()
        if age > MAX_WEBHOOK_AGE_SECONDS:
            logger.warning(
                "paddle_webhook_replay_rejected event_age=%ss",
                int(age),
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Webhook event is too old "
                    f"({int(age)}s > {MAX_WEBHOOK_AGE_SECONDS}s max). "
                    f"Possible replay attack."
                ),
            )
    except (ValueError, TypeError) as parse_err:
        logger.warning(
            "paddle_webhook_replay_rejected_unparseable_timestamp error=%s",
            parse_err,
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Webhook event timestamp is unparseable. "
                "Rejecting as potential replay attack."
            ),
        )

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

    # Route to specific handlers via event mapping
    handler = EVENT_HANDLER_MAP.get(event_type)
    if handler:
        background_tasks.add_task(
            handler,
            company_id=company_id,
            event_id=event_id,
            event_type=event_type,
            data=data,
        )
    else:
        # Unrecognised event types are still accepted (200) so Paddle
        # doesn't retry, but we log them for observability.
        logger.info(
            "paddle_webhook_unhandled_event event_type=%s event_id=%s company_id=%s",
            event_type,
            event_id,
            company_id,
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
async def get_billing_status(
    company_id: str,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """
    Get billing status for a company.

    C-11: Requires platform admin authentication.
    Returns subscription status and any active payment failures.
    """
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
    event_type: str,
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
    event_type: str,
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


async def _process_subscription_event(
    company_id: str,
    event_id: str,
    event_type: str,
    data: Dict[str, Any],
):
    """Process subscription lifecycle events (created, updated, activated)."""
    try:
        subscription_id = data.get("id", data.get("subscription_id", event_id))
        status = data.get("status", "unknown")

        logger.info(
            "subscription_event_processed company_id=%s event_type=%s event_id=%s "
            "subscription_id=%s status=%s",
            company_id,
            event_type,
            event_id,
            subscription_id,
            status,
        )

        # Update local subscription record if we have a matching one
        with SessionLocal() as db:
            from database.models.billing import Subscription
            sub = db.query(Subscription).filter(
                Subscription.paddle_subscription_id == subscription_id,
            ).first()
            if sub and status != sub.status:
                sub.status = status
                db.commit()
                logger.info(
                    "subscription_status_updated company_id=%s sub_id=%s old=%s new=%s",
                    company_id,
                    subscription_id,
                    sub.status,
                    status,
                )

    except Exception as e:
        logger.error(
            "subscription_event_error company_id=%s event_id=%s error=%s",
            company_id,
            event_id,
            str(e)[:200],
        )


async def _process_subscription_canceled(
    company_id: str,
    event_id: str,
    event_type: str,
    data: Dict[str, Any],
):
    """Process subscription canceled event."""
    try:
        subscription_id = data.get("id", data.get("subscription_id", event_id))

        logger.info(
            "subscription_canceled company_id=%s event_id=%s subscription_id=%s",
            company_id,
            event_id,
            subscription_id,
        )

        # Update local subscription record
        with SessionLocal() as db:
            from database.models.billing import Subscription
            sub = db.query(Subscription).filter(
                Subscription.paddle_subscription_id == subscription_id,
            ).first()
            if sub:
                sub.status = "canceled"
                db.commit()

    except Exception as e:
        logger.error(
            "subscription_canceled_error company_id=%s event_id=%s error=%s",
            company_id,
            event_id,
            str(e)[:200],
        )


async def _process_subscription_past_due(
    company_id: str,
    event_id: str,
    event_type: str,
    data: Dict[str, Any],
):
    """Process subscription past_due event — triggers dunning."""
    try:
        subscription_id = data.get("id", data.get("subscription_id", event_id))

        logger.warning(
            "subscription_past_due company_id=%s event_id=%s subscription_id=%s",
            company_id,
            event_id,
            subscription_id,
        )

        # Update local subscription record
        with SessionLocal() as db:
            from database.models.billing import Subscription
            sub = db.query(Subscription).filter(
                Subscription.paddle_subscription_id == subscription_id,
            ).first()
            if sub:
                sub.status = "past_due"
                db.commit()

    except Exception as e:
        logger.error(
            "subscription_past_due_error company_id=%s event_id=%s error=%s",
            company_id,
            event_id,
            str(e)[:200],
        )


async def _process_transaction_event(
    company_id: str,
    event_id: str,
    event_type: str,
    data: Dict[str, Any],
):
    """Process transaction lifecycle events (paid, completed)."""
    try:
        transaction_id = data.get("id", data.get("transaction_id", event_id))
        status = data.get("status", "unknown")

        logger.info(
            "transaction_event_processed company_id=%s event_type=%s event_id=%s "
            "transaction_id=%s status=%s",
            company_id,
            event_type,
            event_id,
            transaction_id,
            status,
        )

        # If this is a successful payment and the service was stopped, resume it
        if event_type in ("transaction.paid", "transaction.completed"):
            service = get_payment_failure_service()
            is_stopped = await service.is_service_stopped(UUID(company_id))
            if is_stopped:
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
                    "transaction_resumed_service company_id=%s event_id=%s",
                    company_id,
                    event_id,
                )

    except Exception as e:
        logger.error(
            "transaction_event_error company_id=%s event_id=%s error=%s",
            company_id,
            event_id,
            str(e)[:200],
        )


# ── Event Handler Mapping ────────────────────────────────────────────────

EVENT_HANDLER_MAP: Dict[str, Callable] = {
    # Payment events
    "payment.failed": _process_payment_failed,
    "payment.succeeded": _process_payment_succeeded,
    # Transaction events
    "transaction.paid": _process_transaction_event,
    "transaction.completed": _process_transaction_event,
    "transaction.payment_failed": _process_payment_failed,
    # Subscription events
    "subscription.created": _process_subscription_event,
    "subscription.updated": _process_subscription_event,
    "subscription.activated": _process_subscription_event,
    "subscription.canceled": _process_subscription_canceled,
    "subscription.past_due": _process_subscription_past_due,
}
