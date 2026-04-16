"""
Webhook Health & Dead Letter Service (Day 5: WH1-WH4)

Webhook hardening for reliability:
- WH1: Webhook backfill mechanism (admin-triggered, fetches missed events from Paddle)
- WH2: Webhook health monitoring (track received/processed/failed rates)
- WH3: Dead letter queue (failed webhooks go to DLQ, auto-retry with exponential backoff)
- WH4: Webhook ordering guarantee (process events in order)

BC-001: All operations validate company_id
BC-003: All tasks have proper error handling
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from database.base import SessionLocal
from database.models.webhook_event import WebhookEvent
from database.models.billing_extended import WebhookSequence

logger = logging.getLogger("parwa.services.webhook_health")

# ── Constants ─────────────────────────────────────────────────────────────

# WH3: Maximum retry attempts before leaving for admin review
MAX_RETRY_ATTEMPTS: int = 3

# WH3: Exponential backoff base in minutes (2, 4, 8 minutes)
EXPONENTIAL_BACKOFF_BASE: int = 2

# WH2: Alert if failure rate exceeds 5%
HEALTH_ALERT_FAILURE_RATE: Decimal = Decimal("0.05")

# WH2: Alert if average processing time exceeds 5000ms
HEALTH_ALERT_SLOW_MS: int = 5000


# ── Exception Classes ─────────────────────────────────────────────────────

class WebhookHealthError(Exception):
    """Base exception for webhook health errors."""
    pass


class DeadLetterExhaustedError(WebhookHealthError):
    """Raised when a dead letter webhook has exceeded max retries."""
    pass


class WebhookOrderingError(WebhookHealthError):
    """Raised when a webhook ordering violation is detected."""
    pass


# ── ORM Stubs ────────────────────────────────────────────────────────────
# DeadLetterWebhook and WebhookHealthStat models are being added via
# migration in parallel. We define stubs here so the service is importable.

class _DeadLetterWebhookModel:
    """Stub for DeadLetterWebhook table schema.

    Columns: id, company_id, provider, event_id, event_type, payload,
             error_message, status, retry_count, max_retries,
             next_retry_at, created_at, updated_at
    """
    __tablename__ = "dead_letter_webhooks"
    pass


class _WebhookHealthStatModel:
    """Stub for WebhookHealthStat table schema.

    Columns: id, provider, date, events_received, events_processed,
             events_failed, avg_processing_time_ms, failure_rate,
             created_at
    """
    __tablename__ = "webhook_health_stats"
    pass


# ── Service Implementation ───────────────────────────────────────────────

class WebhookHealthService:
    """
    Webhook health monitoring, dead letter queue, and backfill service.

    Monitors webhook reliability, retries failed webhooks with exponential
    backoff, supports admin-triggered backfill from Paddle, and enforces
    event ordering.

    Usage:
        service = WebhookHealthService()

        # Record a processed webhook
        service.record_webhook_processed("paddle", "subscription.created", 150, success=True)

        # Get health report
        health = service.get_webhook_health(provider="paddle", days=7)

        # Add failed webhook to DLQ
        service.add_to_dead_letter_queue(company_id, "paddle", evt_id, "sub.created", payload, "timeout")

        # Process the dead letter queue
        service.process_dead_letter_queue()
    """

    def __init__(self) -> None:
        """Initialize the webhook health service."""
        self._dlq_table_available: Optional[bool] = None
        self._health_table_available: Optional[bool] = None

    # ── Table Availability Helpers ────────────────────────────────────────

    def _get_dlq_model(self, db: Session):
        """Return DeadLetterWebhook ORM class, or None if table unavailable."""
        if self._dlq_table_available is False:
            return None
        try:
            from database.models.billing_extended import DeadLetterWebhook  # type: ignore
            self._dlq_table_available = True
            return DeadLetterWebhook
        except ImportError:
            self._dlq_table_available = False
            logger.warning("dead_letter_webhooks table not available")
            return None

    def _get_health_stat_model(self, db: Session):
        """Return WebhookHealthStat ORM class, or None if table unavailable."""
        if self._health_table_available is False:
            return None
        try:
            from database.models.billing_extended import WebhookHealthStat  # type: ignore
            self._health_table_available = True
            return WebhookHealthStat
        except ImportError:
            self._health_table_available = False
            logger.warning("webhook_health_stats table not available")
            return None

    # ── Validation ───────────────────────────────────────────────────────

    @staticmethod
    def _validate_company_id(company_id: Any) -> str:
        """Validate and normalize company_id. BC-001."""
        if company_id is None:
            raise WebhookHealthError("company_id is required")
        if isinstance(company_id, UUID):
            return str(company_id)
        if isinstance(company_id, str):
            company_id = company_id.strip()
            if not company_id:
                raise WebhookHealthError("company_id cannot be empty")
            return company_id
        raise WebhookHealthError(
            f"Invalid company_id type: {type(company_id).__name__}"
        )

    # ── WH2: Webhook Health Monitoring ───────────────────────────────────

    def record_webhook_processed(
        self,
        provider: str,
        event_type: str,
        processing_time_ms: int,
        success: bool = True,
    ) -> Dict[str, Any]:
        """
        Record a webhook processing result for health monitoring. (WH2)

        Increments daily counters in WebhookHealthStat. Creates the
        stat row for today if it does not exist.

        Args:
            provider: Webhook provider name (e.g. "paddle")
            event_type: Event type string (e.g. "subscription.created")
            processing_time_ms: Processing time in milliseconds
            success: Whether processing succeeded

        Returns:
            Dict with updated health stats for today
        """
        if not provider or not isinstance(provider, str):
            raise WebhookHealthError("provider is required and must be a string")
        if not event_type or not isinstance(event_type, str):
            raise WebhookHealthError("event_type is required and must be a string")

        today = datetime.now(timezone.utc).date()

        with SessionLocal() as db:
            WebhookHealthStat = self._get_health_stat_model(db)
            if WebhookHealthStat is None:
                logger.info(
                    "webhook_health_record_skipped provider=%s type=%s success=%s",
                    provider, event_type, success,
                )
                return {
                    "provider": provider,
                    "date": today.isoformat(),
                    "recorded": False,
                    "message": "Health stat table not available.",
                }

            # Find or create today's stat row
            stat = (
                db.query(WebhookHealthStat)
                .filter(
                    WebhookHealthStat.provider == provider,
                    WebhookHealthStat.date == today,
                )
                .first()
            )

            if stat is None:
                stat = WebhookHealthStat(
                    id=str(uuid.uuid4()),
                    provider=provider,
                    date=today,
                    events_received=0,
                    events_processed=0,
                    events_failed=0,
                    avg_processing_time_ms=0,
                    failure_rate=Decimal("0.00"),
                    created_at=datetime.now(timezone.utc),
                )
                db.add(stat)

            # Update counters
            stat.events_received = (stat.events_received or 0) + 1

            if success:
                stat.events_processed = (stat.events_processed or 0) + 1
            else:
                stat.events_failed = (stat.events_failed or 0) + 1

            # Recalculate average processing time
            total_processed = (stat.events_processed or 0) + (stat.events_failed or 0)
            if total_processed > 0:
                current_avg = stat.avg_processing_time_ms or 0
                # Running average: (old_avg * (n-1) + new_value) / n
                stat.avg_processing_time_ms = int(
                    (current_avg * (total_processed - 1) + processing_time_ms)
                    / total_processed
                )

            # Recalculate failure rate
            received = stat.events_received or 1
            failed = stat.events_failed or 0
            stat.failure_rate = Decimal(str(round(failed / received, 4)))

            db.commit()

            logger.info(
                "webhook_health_recorded provider=%s type=%s success=%s "
                "received=%d processed=%d failed=%d avg_ms=%d",
                provider, event_type, success,
                stat.events_received, stat.events_processed,
                stat.events_failed, stat.avg_processing_time_ms,
            )

            return {
                "provider": provider,
                "date": today.isoformat(),
                "events_received": stat.events_received,
                "events_processed": stat.events_processed,
                "events_failed": stat.events_failed,
                "avg_processing_time_ms": stat.avg_processing_time_ms,
                "failure_rate": str(stat.failure_rate),
            }

    def get_webhook_health(
        self,
        provider: str = "paddle",
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get webhook health metrics for the specified period. (WH2)

        Returns aggregate metrics including total received, processed,
        failed counts, failure rate, and average processing time.
        Flags alert conditions.

        Args:
            provider: Webhook provider name
            days: Number of days to look back

        Returns:
            Dict with health summary and per-day breakdown:
                - total_received, total_processed, total_failed
                - failure_rate, avg_processing_time_ms
                - alerts (List[str]): Active alert conditions
                - daily_stats (List[Dict]): Per-day metrics
        """
        if days < 1:
            raise WebhookHealthError("days must be >= 1")

        since_date = datetime.now(timezone.utc).date() - timedelta(days=days - 1)

        with SessionLocal() as db:
            WebhookHealthStat = self._get_health_stat_model(db)
            if WebhookHealthStat is None:
                return {
                    "provider": provider,
                    "period_days": days,
                    "total_received": 0,
                    "total_processed": 0,
                    "total_failed": 0,
                    "failure_rate": "0.00",
                    "avg_processing_time_ms": 0,
                    "alerts": [],
                    "daily_stats": [],
                    "message": "Health stat table not available.",
                }

            rows = (
                db.query(WebhookHealthStat)
                .filter(
                    WebhookHealthStat.provider == provider,
                    WebhookHealthStat.date >= since_date,
                )
                .order_by(WebhookHealthStat.date.desc())
                .all()
            )

            total_received = sum(r.events_received or 0 for r in rows)
            total_processed = sum(r.events_processed or 0 for r in rows)
            total_failed = sum(r.events_failed or 0 for r in rows)

            # Calculate aggregates
            failure_rate = (
                Decimal(str(round(total_failed / total_received, 4)))
                if total_received > 0
                else Decimal("0.00")
            )

            # Weighted average of per-day averages
            total_time_weight = 0
            total_weight = 0
            for r in rows:
                day_total = (r.events_processed or 0) + (r.events_failed or 0)
                if day_total > 0:
                    total_time_weight += (r.avg_processing_time_ms or 0) * day_total
                    total_weight += day_total
            avg_time = int(total_time_weight / total_weight) if total_weight > 0 else 0

            # Check alert conditions
            alerts: List[str] = []
            if failure_rate > HEALTH_ALERT_FAILURE_RATE:
                alerts.append(
                    f"High failure rate: {failure_rate * 100:.1f}% "
                    f"(threshold: {HEALTH_ALERT_FAILURE_RATE * 100:.0f}%)"
                )
            if avg_time > HEALTH_ALERT_SLOW_MS:
                alerts.append(
                    f"Slow processing: {avg_time}ms avg "
                    f"(threshold: {HEALTH_ALERT_SLOW_MS}ms)"
                )

            daily_stats = [
                {
                    "date": r.date.isoformat(),
                    "events_received": r.events_received or 0,
                    "events_processed": r.events_processed or 0,
                    "events_failed": r.events_failed or 0,
                    "avg_processing_time_ms": r.avg_processing_time_ms or 0,
                    "failure_rate": str(r.failure_rate or "0.00"),
                }
                for r in rows
            ]

            logger.info(
                "webhook_health_retrieved provider=%s days=%d "
                "received=%d processed=%d failed=%d failure_rate=%s avg_ms=%d alerts=%d",
                provider, days,
                total_received, total_processed, total_failed,
                failure_rate, avg_time, len(alerts),
            )

            return {
                "provider": provider,
                "period_days": days,
                "total_received": total_received,
                "total_processed": total_processed,
                "total_failed": total_failed,
                "failure_rate": str(failure_rate),
                "avg_processing_time_ms": avg_time,
                "alerts": alerts,
                "daily_stats": daily_stats,
            }

    # ── WH3: Dead Letter Queue ───────────────────────────────────────────

    def add_to_dead_letter_queue(
        self,
        company_id: Any,
        provider: str,
        event_id: str,
        event_type: str,
        payload: Any,
        error_message: str,
    ) -> Dict[str, Any]:
        """
        Add a failed webhook to the dead letter queue. (WH3)

        Creates a DeadLetterWebhook record with status="pending",
        retry_count=0, max_retries=3, and next_retry_at set for
        immediate first retry.

        Args:
            company_id: Company UUID or str
            provider: Webhook provider name
            event_id: Provider event ID
            event_type: Event type string
            payload: Raw webhook payload (dict/list)
            error_message: Error that caused the failure

        Returns:
            Dict with dead letter record details
        """
        company_id_str = self._validate_company_id(company_id)

        if not event_id or not isinstance(event_id, str):
            raise WebhookHealthError("event_id is required")

        with SessionLocal() as db:
            DeadLetterWebhook = self._get_dlq_model(db)
            if DeadLetterWebhook is None:
                logger.warning(
                    "dlq_add_skipped company_id=%s event_id=%s",
                    company_id_str, event_id,
                )
                return {
                    "company_id": company_id_str,
                    "event_id": event_id,
                    "queued": False,
                    "message": "DLQ table not available.",
                }

            # Serialize payload
            if isinstance(payload, (dict, list)):
                payload_json = json.dumps(payload)
            elif isinstance(payload, str):
                payload_json = payload
            else:
                payload_json = json.dumps({"raw": str(payload)})

            now = datetime.now(timezone.utc)
            dlq_record = DeadLetterWebhook(
                id=str(uuid.uuid4()),
                company_id=company_id_str,
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                payload=payload_json,
                error_message=error_message,
                status="pending",
                retry_count=0,
                max_retries=MAX_RETRY_ATTEMPTS,
                next_retry_at=now,  # Available for immediate first retry
                created_at=now,
                updated_at=now,
            )
            db.add(dlq_record)
            db.commit()

            logger.info(
                "dlq_webhook_added company_id=%s provider=%s event_id=%s "
                "event_type=%s error=%s",
                company_id_str, provider, event_id, event_type,
                error_message[:100],
            )

            return {
                "id": dlq_record.id,
                "company_id": company_id_str,
                "provider": provider,
                "event_id": event_id,
                "event_type": event_type,
                "status": "pending",
                "retry_count": 0,
                "max_retries": MAX_RETRY_ATTEMPTS,
                "next_retry_at": now.isoformat(),
            }

    def retry_dead_letter_webhook(
        self,
        dead_letter_id: str,
    ) -> Dict[str, Any]:
        """
        Manually retry a dead letter webhook. (WH3)

        Checks retry_count < max_retries, increments retry count,
        and schedules next retry with exponential backoff:
        2^retry_count minutes.

        Args:
            dead_letter_id: Dead letter record ID

        Returns:
            Dict with retry status and scheduling info

        Raises:
            DeadLetterExhaustedError: If max retries exceeded
        """
        if not dead_letter_id or not isinstance(dead_letter_id, str):
            raise WebhookHealthError("dead_letter_id is required")

        with SessionLocal() as db:
            DeadLetterWebhook = self._get_dlq_model(db)
            if DeadLetterWebhook is None:
                return {
                    "id": dead_letter_id,
                    "retried": False,
                    "message": "DLQ table not available.",
                }

            record = (
                db.query(DeadLetterWebhook)
                .filter(DeadLetterWebhook.id == dead_letter_id)
                .first()
            )

            if record is None:
                raise WebhookHealthError(
                    f"Dead letter record {dead_letter_id} not found"
                )

            if record.retry_count >= record.max_retries:
                raise DeadLetterExhaustedError(
                    f"Dead letter {dead_letter_id} has exhausted "
                    f"{record.retry_count}/{record.max_retries} retries. "
                    "Requires admin review."
                )

            # Increment retry count
            record.retry_count = (record.retry_count or 0) + 1

            # Calculate exponential backoff: 2^retry_count minutes
            backoff_minutes = EXPONENTIAL_BACKOFF_BASE ** record.retry_count
            next_retry = datetime.now(timezone.utc) + timedelta(
                minutes=backoff_minutes
            )

            record.status = "retrying"
            record.next_retry_at = next_retry
            record.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                "dlq_retry_scheduled id=%s attempt=%d/%d next_retry=%s",
                dead_letter_id,
                record.retry_count,
                record.max_retries,
                next_retry.isoformat(),
            )

            return {
                "id": record.id,
                "event_id": record.event_id,
                "company_id": record.company_id,
                "retry_count": record.retry_count,
                "max_retries": record.max_retries,
                "backoff_minutes": backoff_minutes,
                "next_retry_at": next_retry.isoformat(),
                "status": "retrying",
            }

    def process_dead_letter_queue(self) -> Dict[str, Any]:
        """
        Process all due dead letter webhooks. (WH3)

        Finds all pending/retrying webhooks where next_retry_at <= now
        and attempts to re-process each one. Delegates to the webhook
        handler for actual processing.

        On success: marks status as "processed".
        On failure: increments retry, sets next_retry_at.
        After max_retries: leaves in "pending" for admin review.

        Returns:
            Dict with processing summary:
                - processed, failed, exhausted, errors
        """
        results: Dict[str, Any] = {
            "processed": 0,
            "failed": 0,
            "exhausted": 0,
            "skipped": 0,
            "errors": [],
        }

        now = datetime.now(timezone.utc)

        with SessionLocal() as db:
            DeadLetterWebhook = self._get_dlq_model(db)
            if DeadLetterWebhook is None:
                return {
                    **results,
                    "message": "DLQ table not available.",
                }

            # Find due webhooks
            due_webhooks = (
                db.query(DeadLetterWebhook)
                .filter(
                    DeadLetterWebhook.status.in_(["pending", "retrying"]),
                    DeadLetterWebhook.next_retry_at <= now,
                )
                .order_by(DeadLetterWebhook.created_at.asc())
                .limit(100)  # Batch limit
                .all()
            )

            logger.info(
                "dlq_processing_started count=%d",
                len(due_webhooks),
            )

            for record in due_webhooks:
                try:
                    # Check if max retries exhausted
                    if record.retry_count >= record.max_retries:
                        record.status = "exhausted"
                        record.updated_at = now
                        db.commit()
                        results["exhausted"] += 1

                        logger.warning(
                            "dlq_webhook_exhausted id=%s event_id=%s retries=%d",
                            record.id, record.event_id, record.retry_count,
                        )
                        continue

                    # Attempt re-processing via webhook handler
                    success = self._attempt_reprocess(record)

                    if success:
                        record.status = "processed"
                        record.updated_at = now
                        db.commit()
                        results["processed"] += 1

                        logger.info(
                            "dlq_webhook_processed id=%s event_id=%s",
                            record.id, record.event_id,
                        )
                    else:
                        # Failed — increment retry and schedule next
                        record.retry_count = (record.retry_count or 0) + 1
                        backoff_minutes = (
                            EXPONENTIAL_BACKOFF_BASE ** record.retry_count
                        )
                        record.next_retry_at = now + timedelta(
                            minutes=backoff_minutes
                        )
                        record.status = "retrying"
                        record.updated_at = now
                        db.commit()
                        results["failed"] += 1

                        logger.warning(
                            "dlq_webhook_retry_failed id=%s event_id=%s "
                            "attempt=%d next_in=%dmin",
                            record.id, record.event_id,
                            record.retry_count, backoff_minutes,
                        )

                except Exception as exc:
                    results["errors"].append({
                        "id": record.id,
                        "event_id": record.event_id,
                        "error": str(exc)[:200],
                    })
                    logger.error(
                        "dlq_webhook_processing_error id=%s error=%s",
                        record.id, str(exc)[:200],
                    )

        logger.info(
            "dlq_processing_completed processed=%d failed=%d exhausted=%d errors=%d",
            results["processed"], results["failed"],
            results["exhausted"], len(results["errors"]),
        )

        return results

    def _attempt_reprocess(self, record: Any) -> bool:
        """
        Attempt to re-process a dead letter webhook.

        Delegates to the webhook handler for actual processing.
        Catches all exceptions and returns False on failure.

        Args:
            record: DeadLetterWebhook record

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Parse payload
            payload = record.payload
            if isinstance(payload, str):
                payload = json.loads(payload)

            # Delegate to the paddle handler
            from app.webhooks.paddle_handler import handle_paddle_event

            event = {
                "event_type": record.event_type,
                "event_id": record.event_id,
                "company_id": record.company_id,
                "payload": payload,
            }

            result = handle_paddle_event(event)

            if result.get("status") == "processed":
                return True

            # Update error message
            record.error_message = result.get(
                "error",
                f"Handler returned status: {result.get('status')}"
            )
            return False

        except json.JSONDecodeError:
            record.error_message = "Invalid JSON payload in dead letter"
            return False
        except Exception as exc:
            record.error_message = f"Re-processing error: {str(exc)[:200]}"
            return False

    def discard_dead_letter_webhook(
        self,
        dead_letter_id: str,
    ) -> Dict[str, Any]:
        """
        Discard a dead letter webhook (mark as discarded). (WH3)

        Admin action to permanently remove a webhook from retry
        processing.

        Args:
            dead_letter_id: Dead letter record ID

        Returns:
            Dict with discard confirmation
        """
        if not dead_letter_id or not isinstance(dead_letter_id, str):
            raise WebhookHealthError("dead_letter_id is required")

        with SessionLocal() as db:
            DeadLetterWebhook = self._get_dlq_model(db)
            if DeadLetterWebhook is None:
                return {
                    "id": dead_letter_id,
                    "discarded": False,
                    "message": "DLQ table not available.",
                }

            record = (
                db.query(DeadLetterWebhook)
                .filter(DeadLetterWebhook.id == dead_letter_id)
                .first()
            )

            if record is None:
                raise WebhookHealthError(
                    f"Dead letter record {dead_letter_id} not found"
                )

            record.status = "discarded"
            record.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                "dlq_webhook_discarded id=%s event_id=%s",
                dead_letter_id, record.event_id,
            )

            return {
                "id": record.id,
                "event_id": record.event_id,
                "status": "discarded",
                "message": "Webhook discarded and removed from retry queue.",
            }

    def list_dead_letter_webhooks(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List dead letter webhooks. (WH3)

        Args:
            status: Filter by status (pending/retrying/processed/discarded/exhausted),
                or None for all
            limit: Maximum records to return

        Returns:
            List of dead letter webhook dicts
        """
        if limit < 1:
            raise WebhookHealthError("limit must be >= 1")

        valid_statuses = {"pending", "retrying", "processed", "discarded", "exhausted"}
        if status is not None and status not in valid_statuses:
            raise WebhookHealthError(
                f"Invalid status: {status}. "
                f"Must be one of: {valid_statuses}"
            )

        with SessionLocal() as db:
            DeadLetterWebhook = self._get_dlq_model(db)
            if DeadLetterWebhook is None:
                return []

            query = db.query(DeadLetterWebhook)

            if status is not None:
                query = query.filter(DeadLetterWebhook.status == status)

            records = (
                query
                .order_by(DeadLetterWebhook.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": r.id,
                    "company_id": r.company_id,
                    "provider": r.provider,
                    "event_id": r.event_id,
                    "event_type": r.event_type,
                    "error_message": r.error_message,
                    "status": r.status,
                    "retry_count": r.retry_count,
                    "max_retries": r.max_retries,
                    "next_retry_at": (
                        r.next_retry_at.isoformat() if r.next_retry_at else None
                    ),
                    "created_at": (
                        r.created_at.isoformat() if r.created_at else None
                    ),
                }
                for r in records
            ]

    # ── WH1: Webhook Backfill ────────────────────────────────────────────

    def backfill_webhooks(
        self,
        since_timestamp: str,
        company_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Fetch missed events from Paddle API and process them. (WH1)

        Admin-triggered mechanism to recover from webhook delivery gaps.
        Calls Paddle's GET /events endpoint with the since parameter,
        checks idempotency for each event, and processes new ones.

        Args:
            since_timestamp: ISO-8601 timestamp to fetch events from
            company_id: Optional company filter (UUID or str)

        Returns:
            Dict with:
                - events_fetched: Total events returned by Paddle
                - events_processed: Events that were newly processed
                - events_skipped: Events already processed (idempotent)
                - errors: List of processing errors
        """
        results: Dict[str, Any] = {
            "since": since_timestamp,
            "events_fetched": 0,
            "events_processed": 0,
            "events_skipped": 0,
            "errors": [],
        }

        # Validate timestamp
        try:
            since_dt = datetime.fromisoformat(
                since_timestamp.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            raise WebhookHealthError(
                f"Invalid since_timestamp: {since_timestamp}. "
                "Must be ISO-8601 format."
            )

        company_id_str = None
        if company_id is not None:
            company_id_str = self._validate_company_id(company_id)

        try:
            # Fetch events from Paddle
            events = self._fetch_paddle_events(since_timestamp)

            results["events_fetched"] = len(events)

            logger.info(
                "webhook_backfill_started since=%s company_id=%s fetched=%d",
                since_timestamp, company_id_str, len(events),
            )

            with SessionLocal() as db:
                for event_data in events:
                    try:
                        event_id = event_data.get("event_id") or event_data.get("id")
                        event_type = event_data.get("event_type") or event_data.get("type")

                        if not event_id or not event_type:
                            results["events_skipped"] += 1
                            continue

                        # Filter by company if specified
                        evt_company_id = event_data.get("company_id")
                        if company_id_str and evt_company_id != company_id_str:
                            results["events_skipped"] += 1
                            continue

                        # Check idempotency
                        existing = (
                            db.query(WebhookEvent)
                            .filter(
                                WebhookEvent.event_id == event_id,
                                WebhookEvent.provider == "paddle",
                            )
                            .first()
                        )

                        if existing:
                            results["events_skipped"] += 1
                            continue

                        # Process the event
                        from app.webhooks.paddle_handler import handle_paddle_event

                        result = handle_paddle_event(event_data)

                        if result.get("status") == "processed":
                            # Record as processed
                            webhook_event = WebhookEvent(
                                id=str(uuid.uuid4()),
                                company_id=evt_company_id or "",
                                provider="paddle",
                                event_id=event_id,
                                event_type=event_type,
                                payload=event_data.get("payload", {}),
                                status="completed",
                                processing_started_at=datetime.now(timezone.utc),
                                completed_at=datetime.now(timezone.utc),
                            )
                            db.add(webhook_event)
                            db.commit()
                            results["events_processed"] += 1
                        else:
                            # Add to DLQ if processing failed
                            self.add_to_dead_letter_queue(
                                company_id=evt_company_id or "",
                                provider="paddle",
                                event_id=event_id,
                                event_type=event_type,
                                payload=event_data.get("payload", {}),
                                error_message=result.get("error", "Processing failed"),
                            )
                            results["events_skipped"] += 1

                    except Exception as exc:
                        results["errors"].append({
                            "event_id": event_data.get("event_id", "unknown"),
                            "error": str(exc)[:200],
                        })
                        logger.error(
                            "backfill_event_error event_id=%s error=%s",
                            event_data.get("event_id"), str(exc)[:200],
                        )

        except Exception as exc:
            logger.error(
                "webhook_backfill_failed since=%s error=%s",
                since_timestamp, str(exc),
            )
            raise WebhookHealthError(
                f"Backfill failed: {str(exc)}"
            ) from exc

        logger.info(
            "webhook_backfill_completed fetched=%d processed=%d skipped=%d errors=%d",
            results["events_fetched"], results["events_processed"],
            results["events_skipped"], len(results["errors"]),
        )

        return results

    def _fetch_paddle_events(
        self,
        since_timestamp: str,
    ) -> List[Dict[str, Any]]:
        """
        Fetch events from Paddle's events API.

        Uses Paddle's GET /events endpoint with since parameter.
        Falls back to empty list if Paddle client unavailable.

        Args:
            since_timestamp: ISO-8601 timestamp

        Returns:
            List of event dicts from Paddle
        """
        try:
            from app.clients.paddle_client import get_paddle_client
            import asyncio

            paddle = get_paddle_client()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    paddle.list_events(since=since_timestamp)
                )
            finally:
                loop.close()

            return result.get("data", [])

        except Exception as exc:
            logger.warning(
                "paddle_events_fetch_failed since=%s error=%s",
                since_timestamp, str(exc)[:200],
            )
            return []

    # ── WH4: Webhook Ordering ────────────────────────────────────────────

    def ensure_webhook_ordering(
        self,
        company_id: Any,
        event_id: str,
        occurred_at: Any,
    ) -> Dict[str, Any]:
        """
        Ensure webhooks are processed in order for a company. (WH4)

        Checks the WebhookSequence table for earlier events that are
        still unprocessed. If a gap is detected, the current event
        is queued for later processing.

        Args:
            company_id: Company UUID or str
            event_id: Provider event ID
            occurred_at: Event timestamp (datetime or ISO string)

        Returns:
            Dict with:
                - delayed (bool): Whether this event should be delayed
                - waiting_for (str or None): Event ID being waited for
                - message (str): Status description
        """
        company_id_str = self._validate_company_id(company_id)

        if not event_id or not isinstance(event_id, str):
            raise WebhookHealthError("event_id is required")

        # Parse occurred_at
        if isinstance(occurred_at, str):
            try:
                occurred_dt = datetime.fromisoformat(
                    occurred_at.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                occurred_dt = datetime.now(timezone.utc)
        elif isinstance(occurred_at, datetime):
            occurred_dt = occurred_at
        else:
            occurred_dt = datetime.now(timezone.utc)

        with SessionLocal() as db:
            # Check if there's an earlier event still unprocessed
            gap_event = (
                db.query(WebhookSequence)
                .filter(
                    WebhookSequence.company_id == company_id_str,
                    WebhookSequence.status.in_(["pending", "processing"]),
                    WebhookSequence.occurred_at < occurred_dt,
                )
                .order_by(WebhookSequence.occurred_at.asc())
                .first()
            )

            if gap_event is not None:
                # Gap detected — delay this event
                logger.info(
                    "webhook_ordering_gap company_id=%s event_id=%s "
                    "waiting_for=%s gap_occurred=%s",
                    company_id_str, event_id,
                    gap_event.paddle_event_id,
                    gap_event.occurred_at.isoformat(),
                )

                return {
                    "delayed": True,
                    "waiting_for": gap_event.paddle_event_id,
                    "message": (
                        f"Event ordering gap detected. "
                        f"Waiting for earlier event {gap_event.paddle_event_id} "
                        f"(occurred at {gap_event.occurred_at.isoformat()})."
                    ),
                }

            # No gap — register this event as being processed
            sequence = WebhookSequence(
                id=str(uuid.uuid4()),
                company_id=company_id_str,
                paddle_event_id=event_id,
                event_type="",
                occurred_at=occurred_dt,
                status="processing",
                created_at=datetime.now(timezone.utc),
            )
            db.add(sequence)
            db.commit()

            logger.info(
                "webhook_ordering_ok company_id=%s event_id=%s",
                company_id_str, event_id,
            )

            return {
                "delayed": False,
                "waiting_for": None,
                "message": "No ordering gap detected. Event can be processed.",
            }


# ── Singleton Service ────────────────────────────────────────────────────

_webhook_health_service: Optional[WebhookHealthService] = None


def get_webhook_health_service() -> WebhookHealthService:
    """
    Get the webhook health service singleton.

    Returns:
        Shared WebhookHealthService instance
    """
    global _webhook_health_service
    if _webhook_health_service is None:
        _webhook_health_service = WebhookHealthService()
    return _webhook_health_service
