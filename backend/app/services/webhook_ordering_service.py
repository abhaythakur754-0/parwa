"""
Webhook Ordering Service (BG-07, W5D5)

Ensures webhook events are processed in the correct order based on
their occurrence timestamp. Some events must be processed in sequence:
- subscription.created before subscription.updated
- transaction.paid before transaction.completed

Strategy:
1. Store all incoming events in webhook_sequences with occurred_at
2. Process in order by occurred_at timestamp
3. If earlier event arrives after later event, reprocess chain

This prevents race conditions where events arrive out of order.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import and_, asc, desc
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.billing_extended import WebhookSequence

logger = logging.getLogger("parwa.webhook_ordering_service")

# Event categories that require ordered processing
ORDERED_EVENT_TYPES = {
    # Subscription events - must process in lifecycle order
    "subscription.created",
    "subscription.updated",
    "subscription.activated",
    "subscription.canceled",
    "subscription.past_due",
    "subscription.paused",
    "subscription.resumed",
    # Transaction events - paid before completed
    "transaction.paid",
    "transaction.completed",
    "transaction.payment_failed",
    "transaction.canceled",
    "transaction.updated",
}

# Events that must come before others (dependency map)
EVENT_DEPENDENCIES = {
    "subscription.updated": ["subscription.created", "subscription.activated"],
    "subscription.canceled": ["subscription.created", "subscription.activated"],
    "subscription.past_due": ["subscription.created", "subscription.activated"],
    "subscription.paused": ["subscription.created", "subscription.activated"],
    "subscription.resumed": ["subscription.paused"],
    "transaction.completed": ["transaction.paid"],
}


def get_or_create_webhook_sequence(
    paddle_event_id: str,
    event_type: str,
    occurred_at: datetime,
    company_id: Optional[str] = None,
) -> WebhookSequence:
    """
    Get existing or create new webhook sequence record.

    This is idempotent - if the event already exists, returns it.
    """
    db: Session = SessionLocal()
    try:
        # Check for existing
        existing = (
            db.query(WebhookSequence)
            .filter(
                WebhookSequence.paddle_event_id == paddle_event_id,
            )
            .first()
        )

        if existing:
            return existing

        # Create new
        sequence = WebhookSequence(
            paddle_event_id=paddle_event_id,
            event_type=event_type,
            occurred_at=occurred_at,
            company_id=company_id,
            status="pending",
        )

        db.add(sequence)
        db.commit()
        db.refresh(sequence)

        logger.info(
            "webhook_sequence_created event_id=%s type=%s occurred_at=%s",
            paddle_event_id,
            event_type,
            occurred_at.isoformat(),
        )

        return sequence

    except Exception as e:
        db.rollback()
        logger.error(
            "webhook_sequence_create_error event_id=%s error=%s",
            paddle_event_id,
            str(e),
        )
        raise
    finally:
        db.close()


def get_next_processing_order(company_id: str) -> int:
    """
    Get the next processing order number for a company.

    Processing order is sequential per company.
    """
    db: Session = SessionLocal()
    try:
        last = (
            db.query(WebhookSequence)
            .filter(
                WebhookSequence.company_id == company_id,
            )
            .order_by(desc(WebhookSequence.processing_order))
            .first()
        )

        if last and last.processing_order is not None:
            return last.processing_order + 1

        return 1

    finally:
        db.close()


def get_pending_events_ordered(
    company_id: str,
    limit: int = 100,
) -> List[WebhookSequence]:
    """
    Get pending events for a company, ordered by occurrence time.

    This ensures events are processed in the correct order.
    """
    db: Session = SessionLocal()
    try:
        events = (
            db.query(WebhookSequence)
            .filter(
                and_(
                    WebhookSequence.company_id == company_id,
                    WebhookSequence.status == "pending",
                )
            )
            .order_by(asc(WebhookSequence.occurred_at))
            .limit(limit)
            .all()
        )

        return events

    finally:
        db.close()


def mark_sequence_processing(sequence_id: str) -> None:
    """Mark a webhook sequence as currently being processed."""
    db: Session = SessionLocal()
    try:
        record = (
            db.query(WebhookSequence)
            .filter(
                WebhookSequence.id == sequence_id,
            )
            .first()
        )

        if record:
            record.status = "processing"
            record.processed_at = datetime.now(timezone.utc)
            db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mark_sequence_processed(
    sequence_id: str,
    processing_order: Optional[int] = None,
) -> None:
    """Mark a webhook sequence as successfully processed."""
    db: Session = SessionLocal()
    try:
        record = (
            db.query(WebhookSequence)
            .filter(
                WebhookSequence.id == sequence_id,
            )
            .first()
        )

        if record:
            record.status = "processed"
            record.processed_at = datetime.now(timezone.utc)
            if processing_order is not None:
                record.processing_order = processing_order
            db.commit()

            logger.info(
                "webhook_sequence_processed id=%s order=%s",
                sequence_id,
                processing_order,
            )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mark_sequence_failed(
    sequence_id: str,
    error_message: str,
) -> None:
    """Mark a webhook sequence as failed."""
    db: Session = SessionLocal()
    try:
        record = (
            db.query(WebhookSequence)
            .filter(
                WebhookSequence.id == sequence_id,
            )
            .first()
        )

        if record:
            record.status = "failed"
            record.error_message = error_message[:500] if error_message else None
            record.retry_count = (record.retry_count or 0) + 1
            db.commit()

            logger.warning(
                "webhook_sequence_failed id=%s error=%s",
                sequence_id,
                error_message[:100],
            )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_dependencies_met(
    event_type: str,
    company_id: str,
    occurred_at: datetime,
) -> Dict[str, Any]:
    """
    Check if all dependencies for an event have been processed.

    Returns:
        Dict with 'met' boolean and 'missing' list of unmet dependencies
    """
    dependencies = EVENT_DEPENDENCIES.get(event_type, [])

    if not dependencies:
        return {"met": True, "missing": []}

    db: Session = SessionLocal()
    try:
        # Check if all dependencies have been processed
        # for events that occurred BEFORE this one
        processed_deps = (
            db.query(WebhookSequence.event_type)
            .filter(
                and_(
                    WebhookSequence.company_id == company_id,
                    WebhookSequence.event_type.in_(dependencies),
                    WebhookSequence.occurred_at < occurred_at,
                    WebhookSequence.status == "processed",
                )
            )
            .all()
        )

        processed_types = {r[0] for r in processed_deps}
        missing = [d for d in dependencies if d not in processed_types]

        return {
            "met": len(missing) == 0,
            "missing": missing,
        }

    finally:
        db.close()


def process_ordered(
    company_id: str,
    paddle_event_id: str,
    event_type: str,
    occurred_at: datetime,
    processor: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Process a webhook event in order.

    If dependencies aren't met, marks event as pending and returns.
    The missed webhook recovery task will process it later.

    Args:
        company_id: Company ID
        paddle_event_id: Paddle event ID
        event_type: Event type
        occurred_at: When the event occurred
        processor: Callable that processes the event

    Returns:
        Processing result
    """
    # Create sequence record
    sequence = get_or_create_webhook_sequence(
        paddle_event_id=paddle_event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        company_id=company_id,
    )

    # Already processed?
    if sequence.status == "processed":
        logger.info(
            "webhook_already_processed event_id=%s",
            paddle_event_id,
        )
        return {"status": "already_processed", "duplicate": True}

    # Check dependencies
    deps = check_dependencies_met(event_type, company_id, occurred_at)

    if not deps["met"]:
        logger.info(
            "webhook_dependencies_not_met event_id=%s missing=%s",
            paddle_event_id,
            deps["missing"],
        )
        # Leave as pending - recovery task will process later
        return {
            "status": "pending",
            "reason": "dependencies_not_met",
            "missing": deps["missing"],
        }

    # Get processing order
    order = get_next_processing_order(company_id)

    # Mark as processing
    mark_sequence_processing(sequence.id)

    try:
        # Execute processor
        result = processor()

        # Mark as processed
        mark_sequence_processed(sequence.id, order)

        result["processing_order"] = order
        return result

    except Exception as e:
        mark_sequence_failed(sequence.id, str(e))
        raise


def get_stuck_events(
    company_id: Optional[str] = None,
    max_age_hours: int = 24,
) -> List[Dict[str, Any]]:
    """
    Find events stuck in 'pending' or 'processing' state.

    These may need manual intervention or retry.

    Args:
        company_id: Optional company filter
        max_age_hours: Maximum age in hours to consider stuck

    Returns:
        List of stuck event details
    """
    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(
            hours=max_age_hours
        )

        query = db.query(WebhookSequence).filter(
            and_(
                WebhookSequence.status.in_(["pending", "processing"]),
                WebhookSequence.created_at < cutoff,
            )
        )

        if company_id:
            query = query.filter(WebhookSequence.company_id == company_id)

        stuck = query.order_by(asc(WebhookSequence.created_at)).all()

        return [
            {
                "id": s.id,
                "paddle_event_id": s.paddle_event_id,
                "event_type": s.event_type,
                "company_id": s.company_id,
                "status": s.status,
                "occurred_at": s.occurred_at.isoformat() if s.occurred_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "retry_count": s.retry_count,
                "error_message": s.error_message,
            }
            for s in stuck
        ]

    finally:
        db.close()


def retry_stuck_event(sequence_id: str) -> Dict[str, Any]:
    """
    Reset a stuck event to pending for retry.

    Args:
        sequence_id: The webhook sequence ID

    Returns:
        Updated event details
    """
    db: Session = SessionLocal()
    try:
        record = (
            db.query(WebhookSequence)
            .filter(
                WebhookSequence.id == sequence_id,
            )
            .first()
        )

        if not record:
            raise ValueError(f"Sequence {sequence_id} not found")

        if record.status not in ["pending", "processing", "failed"]:
            raise ValueError(f"Cannot retry event with status {record.status}")

        record.status = "pending"
        record.processed_at = None
        record.error_message = None
        record.retry_count = (record.retry_count or 0) + 1
        db.commit()

        logger.info(
            "webhook_sequence_retry id=%s retry_count=%s",
            sequence_id,
            record.retry_count,
        )

        return {
            "id": record.id,
            "status": record.status,
            "retry_count": record.retry_count,
        }

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cleanup_old_sequences(days: int = 30) -> int:
    """
    Delete old processed sequences.

    Args:
        days: Delete sequences older than this many days

    Returns:
        Number of sequences deleted
    """
    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(
            days=days
        )

        deleted = (
            db.query(WebhookSequence)
            .filter(
                and_(
                    WebhookSequence.status == "processed",
                    WebhookSequence.created_at < cutoff,
                )
            )
            .delete()
        )

        db.commit()

        logger.info("webhook_sequences_cleaned deleted=%d", deleted)
        return deleted

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
