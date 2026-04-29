"""
Webhook Service (BC-003, BC-001)

Generic webhook processor with idempotency guarantees.
- Checks for duplicate events via (provider, event_id) constraint
- Stores events with status='pending' for async Celery dispatch
- Dispatches to Celery task queue "webhook" per routing config
- BC-001: All events require valid company_id
- BC-003: Response under 3 seconds (returns immediately)
- FIX L30: Max retry cap (MAX_RETRY_ATTEMPTS = 5)
- FIX L31: Error message truncation to 500 chars
- FIX L32: datetime.now(timezone.utc) -> datetime.now(timezone.utc)
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.base import SessionLocal

logger = logging.getLogger("parwa.webhook_service")

# Maximum retry attempts for failed webhooks (BC-003)
MAX_RETRY_ATTEMPTS = 5

# Maximum error message length
MAX_ERROR_MESSAGE_LENGTH = 500


def _validate_company_id(company_id: str) -> bool:
    """Validate company_id format (BC-001).

    Must be non-empty, max 128 chars, no control characters.
    """
    if not company_id or not isinstance(company_id, str):
        return False
    company_id = company_id.strip()
    if not company_id or len(company_id) > 128:
        return False
    if any(ord(c) < 32 for c in company_id):
        return False
    return True


def _validate_provider(provider: str) -> bool:
    """Validate provider is a supported value.

    Prevents arbitrary strings in the provider column.
    """
    if not provider or not isinstance(provider, str):
        return False
    provider = provider.strip().lower()
    valid = {"paddle", "twilio", "shopify", "brevo"}
    return provider in valid


def _validate_event_type(event_type: str) -> bool:
    """Validate event_type format.

    Must be non-empty, max 200 chars, no control characters.
    """
    if not event_type or not isinstance(event_type, str):
        return False
    event_type = event_type.strip()
    if not event_type or len(event_type) > 200:
        return False
    if any(ord(c) < 32 for c in event_type):
        return False
    return True


def _truncate_error(error: str) -> str:
    """Truncate error message to MAX_ERROR_MESSAGE_LENGTH.

    Prevents database errors from excessively long error messages.
    """
    if not error:
        return error
    if len(error) > MAX_ERROR_MESSAGE_LENGTH:
        return error[:MAX_ERROR_MESSAGE_LENGTH] + "...truncated"
    return error


def _dispatch_celery_task(
    company_id: str,
    event_db_id: str,
    provider: str,
) -> None:
    """Dispatch webhook processing to Celery.

    Sends the task to the 'webhook' queue per routing config.
    Failures are logged but do not block the HTTP response
    (BC-003: response under 3 seconds).
    """
    try:
        from app.tasks.celery_app import app
        app.send_task(
            "app.tasks.webhook_tasks."
            "process_webhook_event",
            args=[company_id, event_db_id],
            queue="webhook",
        )
        logger.info(
            "webhook_task_dispatched provider=%s "
            "event_db_id=%s company_id=%s",
            provider, event_db_id, company_id,
        )
    except Exception as exc:
        # Log but don't raise — the event is already persisted
        # and can be retried manually
        logger.warning(
            "webhook_task_dispatch_failed provider=%s "
            "event_db_id=%s error=%s",
            provider, event_db_id, exc,
        )


def process_webhook(
    company_id: str,
    provider: str,
    event_id: str,
    event_type: str,
    payload: dict,
) -> dict:
    """Process an incoming webhook event.

    Idempotency: If (provider, event_id) already exists and
    status is not 'pending', returns the existing record.

    Flow:
        1. Validate company_id (BC-001)
        2. Check idempotency — return existing if found
        3. INSERT new webhook_event with status='pending'
        4. Dispatch to Celery task (queue='webhook')
        5. Return immediately (BC-003: under 3 seconds)

    Args:
        company_id: Tenant company ID (BC-001).
        provider: Provider name (e.g. 'paddle', 'shopify').
        event_id: Provider-specific event ID for idempotency.
        event_type: Event type (e.g. 'payment.completed').
        payload: Event payload dictionary.

    Returns:
        Dict with 'id', 'status', 'duplicate' flag.

    Raises:
        ValueError: If company_id is invalid or fields missing.
    """
    # BC-001: Validate company_id before any DB write
    if not _validate_company_id(company_id):
        raise ValueError(
            "Invalid company_id: must be non-empty, "
            "max 128 chars, no control characters"
        )

    if not _validate_provider(provider):
        raise ValueError(
            "Invalid provider: must be one of "
            "paddle, twilio, shopify, brevo"
        )

    if not event_id or not isinstance(event_id, str):
        raise ValueError(
            "event_id is required and must be a string"
        )

    if not _validate_event_type(event_type):
        raise ValueError(
            "event_type must be non-empty, max 200 chars, "
            "no control characters"
        )

    db: Session = SessionLocal()
    try:
        from database.models.webhook_event import WebhookEvent

        # FIX L30: Idempotency check — return existing
        # regardless of status (including 'pending').
        # Previous code fell through for pending events,
        # causing IntegrityError on duplicate INSERT.
        existing = db.query(WebhookEvent).filter_by(
            provider=provider,
            event_id=event_id,
        ).first()

        if existing:
            return {
                "id": existing.id,
                "status": existing.status,
                "duplicate": True,
            }

        # Create new webhook event
        record = WebhookEvent(
            company_id=company_id.strip(),
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # Dispatch to Celery (non-blocking)
        _dispatch_celery_task(
            company_id, record.id, provider,
        )

        return {
            "id": record.id,
            "status": record.status,
            "duplicate": False,
        }
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_webhook_event(event_db_id: str) -> dict:
    """Retrieve a webhook event by its database record ID.

    Args:
        event_db_id: The UUID of the webhook event record.

    Returns:
        Dict with event details.

    Raises:
        ValueError: If event not found.
    """
    if not event_db_id:
        raise ValueError("event_db_id is required")

    db: Session = SessionLocal()
    try:
        from database.models.webhook_event import WebhookEvent
        record = db.query(WebhookEvent).filter_by(
            id=event_db_id,
        ).first()

        if not record:
            raise ValueError(
                f"Webhook event {event_db_id} not found"
            )

        return {
            "id": record.id,
            "company_id": record.company_id,
            "provider": record.provider,
            "event_id": record.event_id,
            "event_type": record.event_type,
            "payload": record.payload,
            "status": record.status,
            "processing_attempts": (
                record.processing_attempts
            ),
            "processing_started_at": (
                record.processing_started_at.isoformat()
                if record.processing_started_at
                else None
            ),
            "completed_at": (
                record.completed_at.isoformat()
                if record.completed_at
                else None
            ),
            "error_message": record.error_message,
            "created_at": (
                record.created_at.isoformat()
                if record.created_at
                else None
            ),
            "updated_at": (
                record.updated_at.isoformat()
                if record.updated_at
                else None
            ),
        }
    finally:
        db.close()


def retry_failed_webhook(event_db_id: str) -> dict:
    """Retry a failed webhook event.

    Resets the event to 'pending' status, clears error,
    increments processing_attempts, and re-dispatches
    to Celery.

    Args:
        event_db_id: The UUID of the webhook event record.

    Returns:
        Dict with updated event details.

    Raises:
        ValueError: If event not found or not in failed state.
    """
    if not event_db_id:
        raise ValueError("event_db_id is required")

    db: Session = SessionLocal()
    try:
        from database.models.webhook_event import WebhookEvent
        record = db.query(WebhookEvent).filter_by(
            id=event_db_id,
        ).first()

        if not record:
            raise ValueError(
                f"Webhook event {event_db_id} not found"
            )

        if record.status not in ("failed",):
            raise ValueError(
                "Can only retry failed events"
            )

        # FIX L32: Max retry cap to prevent infinite retries
        if (record.processing_attempts or 0) >= MAX_RETRY_ATTEMPTS:
            raise ValueError(
                f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) "
                f"exceeded for event {event_db_id}. "
                "Manual intervention required."
            )

        # Reset to pending, increment attempts
        record.status = "pending"
        record.completed_at = None
        record.processing_started_at = None
        record.error_message = None
        record.processing_attempts = (
            (record.processing_attempts or 0) + 1
        )
        db.commit()
        db.refresh(record)

        # Re-dispatch to Celery
        _dispatch_celery_task(
            record.company_id,
            record.id,
            record.provider,
        )

        return {
            "id": record.id,
            "status": record.status,
            "processing_attempts": (
                record.processing_attempts
            ),
            "duplicate": False,
        }
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mark_webhook_processed(
    event_db_id: str,
    status: str,
    error: str = None,
) -> dict:
    """Mark a webhook event as processed or failed.

    Args:
        event_db_id: The UUID of the webhook event record.
        status: Final status ('processed' or 'failed').
        error: Optional error message for failures.

    Returns:
        Dict with updated event details.

    Raises:
        ValueError: If event not found or invalid status.
    """
    valid_statuses = ("processed", "failed")
    if status not in valid_statuses:
        raise ValueError(
            f"status must be one of {valid_statuses}"
        )
    if not event_db_id:
        raise ValueError("event_db_id is required")

    db: Session = SessionLocal()
    try:
        from database.models.webhook_event import WebhookEvent
        record = db.query(WebhookEvent).filter_by(
            id=event_db_id,
        ).first()

        if not record:
            raise ValueError(
                f"Webhook event {event_db_id} not found"
            )

        now = datetime.now(timezone.utc)
        record.status = status
        record.completed_at = now
        if not record.processing_started_at:
            record.processing_started_at = now
        if error:
            # FIX L31: Truncate error message
            record.error_message = _truncate_error(error)

        db.commit()
        db.refresh(record)

        return {
            "id": record.id,
            "status": record.status,
            "completed_at": (
                record.completed_at.isoformat()
                if record.completed_at
                else None
            ),
            "error_message": record.error_message,
        }
    except ValueError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
