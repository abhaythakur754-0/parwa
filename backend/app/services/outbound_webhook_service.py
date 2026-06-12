"""
Outbound Webhook Dispatch Task (Phase 6)

Fires outbound webhooks when PARWA events occur (ticket created, resolved, etc.).
Dispatches via Celery with HMAC signing and retry logic.

BC-001: All queries scoped by company_id.
BC-003: HMAC signature on every outbound payload.
BC-004: Celery for background jobs, company_id first param.
"""

import hmac
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from database.base import get_db_context
from database.models.outbound_webhook import OutboundWebhook

logger = logging.getLogger("parwa.webhooks.outbound")

# Maximum retries with exponential backoff
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 60  # seconds


def _sign_payload(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature for the payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_event_payload(
    event_type: str,
    company_id: str,
    data: Dict[str, Any],
) -> str:
    """Build the JSON payload for an outbound webhook."""
    payload = {
        "event": event_type,
        "delivery_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "company_id": company_id,
        "data": data,
    }
    return json.dumps(payload, separators=(",", ":"))


@celery_app.task(
    name="webhooks.dispatch_outbound",
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=INITIAL_RETRY_DELAY,
    queue="webhook",
)
def dispatch_outbound_webhook(
    self,
    company_id: str,
    event_type: str,
    event_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Dispatch outbound webhooks for a given event.

    Called when a PARWA event occurs (e.g., ticket.created).
    Finds all active webhooks subscribed to this event type
    and sends HTTP POST with HMAC signature.

    BC-004: company_id is the first parameter.
    BC-001: Only webhooks belonging to this company are triggered.
    """
    logger.info(
        f"Dispatching outbound webhooks for {event_type}",
        extra={"company_id": company_id, "event_type": event_type},
    )

    dispatched = []
    failed = []

    with get_db_context() as db:
        # Find all active webhooks for this company subscribed to this event
        webhooks = (
            db.query(OutboundWebhook)
            .filter(
                OutboundWebhook.company_id == company_id,
                OutboundWebhook.active == True,  # noqa: E712
            )
            .all()
        )

        # Filter to only webhooks subscribed to this event type
        matching_webhooks = [
            wh for wh in webhooks
            if event_type in (wh.events or [])
        ]

    for webhook in matching_webhooks:
        try:
            payload_str = _build_event_payload(event_type, company_id, event_data)
            signature = _sign_payload(payload_str, webhook.secret)

            headers = {
                "Content-Type": "application/json",
                "X-Parwa-Signature": f"sha256={signature}",
                "X-Parwa-Event": event_type,
                "X-Parwa-Delivery": str(uuid.uuid4()),
            }

            with httpx.Client(timeout=10.0) as client:
                resp = client.post(webhook.url, content=payload_str, headers=headers)

            if 200 <= resp.status_code < 300:
                dispatched.append({"webhook_id": webhook.id, "status_code": resp.status_code})
                # Reset failure count on success
                with get_db_context() as db:
                    db_wh = db.query(OutboundWebhook).filter(OutboundWebhook.id == webhook.id).first()
                    if db_wh:
                        db_wh.last_triggered_at = datetime.now(timezone.utc)
                        db_wh.failure_count = 0
                        db_wh.last_error = None
                        db.commit()
            else:
                failed.append({"webhook_id": webhook.id, "status_code": resp.status_code})
                _record_failure(webhook.id, f"Endpoint returned {resp.status_code}")

        except Exception as e:
            failed.append({"webhook_id": webhook.id, "error": str(e)[:200]})
            _record_failure(webhook.id, str(e)[:500])

    result = {
        "event_type": event_type,
        "company_id": company_id,
        "dispatched": len(dispatched),
        "failed": len(failed),
        "details": {"dispatched": dispatched, "failed": failed},
    }

    logger.info(f"Outbound webhook dispatch complete: {result}")
    return result


def _record_failure(webhook_id: str, error_message: str) -> None:
    """Record a webhook delivery failure."""
    try:
        with get_db_context() as db:
            wh = db.query(OutboundWebhook).filter(OutboundWebhook.id == webhook_id).first()
            if wh:
                wh.failure_count = (wh.failure_count or 0) + 1
                wh.last_error = error_message[:500]
                db.commit()
    except Exception:
        pass  # Don't fail the dispatch if recording fails


def fire_webhook_event(
    company_id: str,
    event_type: str,
    data: Dict[str, Any],
) -> None:
    """Convenience function to fire a webhook event.

    Called from ticket services, SLA monitors, etc. to trigger
    outbound webhooks for subscribed endpoints.

    Usage:
        from app.services.outbound_webhook_service import fire_webhook_event

        fire_webhook_event(
            company_id="abc-123",
            event_type="ticket.created",
            data={"ticket_id": "TKT-001", "subject": "..."},
        )
    """
    dispatch_outbound_webhook.delay(company_id, event_type, data)
