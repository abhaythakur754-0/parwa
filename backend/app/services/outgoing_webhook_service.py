"""
PARWA Outgoing Webhook Service (F-031)

Dispatches outgoing webhooks on trigger events with:
- 3 retries with exponential backoff (2s, 4s, 8s)
- Delivery status tracking via WebhookDeliveryLog
- Auto-disable at 3 consecutive failures
- HMAC signature signing for request verification

Building Codes:
- BC-001: All operations scoped to company_id
- BC-003: HMAC verification on outgoing signatures
- BC-004: Celery tasks with company_id first param, max_retries=3
- BC-011: Credentials encrypted at rest
- BC-012: Graceful error handling, no raw errors exposed
"""

import hashlib
import hmac as hmac_mod
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import and_

from app.logger import get_logger
from database.base import get_db_context
from database.models.integration import (
    CustomIntegration,
    WebhookDeliveryLog,
)

logger = get_logger("outgoing_webhook_service")

# ── Constants ───────────────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]  # Exponential backoff in seconds
MAX_CONSECUTIVE_FAILURES = 3
REQUEST_TIMEOUT_SECONDS = 10

# Signature header name
SIGNATURE_HEADER = "X-Parwa-Signature"
TIMESTAMP_HEADER = "X-Parwa-Timestamp"


# ── Service ─────────────────────────────────────────────────────────


class OutgoingWebhookService:
    """Service for dispatching outgoing webhooks with retry logic."""

    def dispatch(
        self,
        company_id: str,
        trigger_event: str,
        payload: Dict[str, Any],
        trigger_event_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find and dispatch all active webhook_out integrations for a trigger event.

        This method is designed to be called from Celery tasks (BC-004)
        with company_id as the first parameter.

        Args:
            company_id: Tenant ID (BC-001).
            trigger_event: The event type that triggered the dispatch
                          (e.g., "ticket.created", "ticket.resolved").
            payload: The event payload to send.
            trigger_event_id: Optional ID of the triggering event.

        Returns:
            List of delivery results (one per matched webhook).
        """
        results = []

        try:
            with get_db_context() as db:
                # Find all active webhook_out integrations for this company
                # that subscribe to this trigger event
                integrations = (
                    db.query(CustomIntegration) .filter(
                        and_(
                            CustomIntegration.company_id == company_id,
                            CustomIntegration.integration_type == "webhook_out",
                            CustomIntegration.status == "active",
                        )) .all())

                for integration in integrations:
                    try:
                        result = self._dispatch_single(
                            db=db,
                            integration=integration,
                            trigger_event=trigger_event,
                            payload=payload,
                            trigger_event_id=trigger_event_id,
                        )
                        results.append(result)
                    except Exception as e:
                        logger.error(
                            "outgoing_webhook_dispatch_error",
                            integration_id=integration.id,
                            company_id=company_id,
                            error=str(e),
                        )
                        results.append({
                            "integration_id": integration.id,
                            "name": integration.name,
                            "success": False,
                            "error": "Internal dispatch error",
                        })

        except Exception as e:
            logger.error(
                "outgoing_webhook_dispatch_batch_error",
                company_id=company_id,
                trigger_event=trigger_event,
                error=str(e),
            )

        return results

    def dispatch_single(
        self,
        company_id: str,
        integration_id: str,
        trigger_event: str,
        payload: Dict[str, Any],
        trigger_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a single outgoing webhook (for manual retry).

        Args:
            company_id: Tenant ID.
            integration_id: Custom integration UUID.
            trigger_event: Event type.
            payload: Event payload.
            trigger_event_id: Optional event ID.

        Returns:
            Delivery result dict.
        """
        try:
            with get_db_context() as db:
                from app.services.custom_integration_service import (
                    CustomIntegrationService,
                )

                service = CustomIntegrationService(db)
                integration = service._get_by_id(integration_id, company_id)

                if not integration:
                    return {
                        "success": False,
                        "error": "Integration not found",
                    }

                if integration.integration_type != "webhook_out":
                    return {
                        "success": False,
                        "error": "Not a webhook_out integration",
                    }

                return self._dispatch_single(
                    db=db,
                    integration=integration,
                    trigger_event=trigger_event,
                    payload=payload,
                    trigger_event_id=trigger_event_id,
                )

        except Exception as e:
            logger.error(
                "outgoing_webhook_manual_dispatch_error",
                integration_id=integration_id,
                company_id=company_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": "Internal dispatch error",
            }

    def retry_delivery(self, delivery_log_id: str,
                       company_id: str) -> Dict[str, Any]:
        """Retry a failed webhook delivery.

        Args:
            delivery_log_id: WebhookDeliveryLog UUID.
            company_id: Tenant ID.

        Returns:
            Retry result dict.
        """
        try:
            with get_db_context() as db:
                log_entry = (
                    db.query(WebhookDeliveryLog)
                    .filter(
                        and_(
                            WebhookDeliveryLog.id == delivery_log_id,
                            WebhookDeliveryLog.company_id == company_id,
                        )
                    )
                    .first()
                )

                if not log_entry:
                    return {
                        "success": False,
                        "error": "Delivery log not found",
                    }

                integration = (
                    db.query(CustomIntegration) .filter(
                        and_(
                            CustomIntegration.id == log_entry.custom_integration_id,
                            CustomIntegration.company_id == company_id,
                        )) .first())

                if not integration:
                    return {
                        "success": False,
                        "error": "Integration not found",
                    }

                payload = {}
                if log_entry.payload_snapshot:
                    try:
                        payload = json.loads(log_entry.payload_snapshot)
                    except Exception:
                        payload = {}

                return self._dispatch_single(
                    db=db,
                    integration=integration,
                    trigger_event=log_entry.trigger_event,
                    payload=payload,
                    trigger_event_id=log_entry.trigger_event_id,
                )

        except Exception as e:
            logger.error(
                "outgoing_webhook_retry_error",
                delivery_log_id=delivery_log_id,
                company_id=company_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": "Internal retry error",
            }

    def get_delivery_logs(
        self,
        company_id: str,
        integration_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get delivery logs for a company's outgoing webhooks.

        Args:
            company_id: Tenant ID.
            integration_id: Optional filter by integration.
            status: Optional filter by status (pending/success/failed).
            limit: Max records to return.

        Returns:
            List of delivery log dicts.
        """
        logs = []
        try:
            with get_db_context() as db:
                query = db.query(WebhookDeliveryLog).filter(
                    WebhookDeliveryLog.company_id == company_id
                )

                if integration_id:
                    query = query.filter(
                        WebhookDeliveryLog.custom_integration_id == integration_id)

                if status:
                    query = query.filter(WebhookDeliveryLog.status == status)

                entries = query.order_by(
                    WebhookDeliveryLog.created_at.desc()
                ).limit(limit).all()

                logs = [self._log_to_dict(entry) for entry in entries]

        except Exception as e:
            logger.error(
                "outgoing_webhook_get_logs_error",
                company_id=company_id,
                error=str(e),
            )

        return logs

    # ── Internal Methods ──────────────────────────────────────────

    def _dispatch_single(
        self,
        db,
        integration: CustomIntegration,
        trigger_event: str,
        payload: Dict[str, Any],
        trigger_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch a single webhook with retry logic.

        Attempts delivery up to MAX_RETRIES times with exponential backoff.
        Logs each attempt via WebhookDeliveryLog.
        """
        from app.services.custom_integration_service import (
            CustomIntegrationService,
            _decrypt_config,
        )

        config = _decrypt_config(integration.config_encrypted)
        url = config.get("url", "")
        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})
        trigger_events = config.get("trigger_events", [])

        # Check if this trigger event matches
        if trigger_event not in trigger_events and "*" not in trigger_events:
            return {
                "integration_id": integration.id,
                "name": integration.name,
                "success": True,
                "skipped": True,
                "reason": "Trigger event not in subscription list",
            }

        if not url:
            return {
                "integration_id": integration.id,
                "name": integration.name,
                "success": False,
                "error": "No URL configured",
            }

        # Apply payload template if configured
        final_payload = self._apply_payload_template(
            template=config.get("payload_template"),
            payload=payload,
            trigger_event=trigger_event,
        )

        # Sign the payload if secret is configured
        headers = dict(headers)  # Copy
        headers["Content-Type"] = "application/json"
        webhook_secret = integration.webhook_secret
        if webhook_secret:
            timestamp = str(int(time.time()))
            payload_bytes = json.dumps(final_payload, sort_keys=True).encode()
            signature = self._sign_payload(
                payload_bytes, webhook_secret, timestamp)
            headers[SIGNATURE_HEADER] = signature
            headers[TIMESTAMP_HEADER] = timestamp

        # Store payload snapshot for debugging/retry
        payload_snapshot = json.dumps(final_payload, sort_keys=True)

        last_error = None
        success = False
        response_status = None
        response_body = None

        for attempt in range(1, MAX_RETRIES + 1):
            # Create delivery log entry
            log_entry = WebhookDeliveryLog(
                company_id=integration.company_id,
                custom_integration_id=integration.id,
                trigger_event=trigger_event,
                trigger_event_id=trigger_event_id,
                attempt=attempt,
                status="pending",
                payload_snapshot=payload_snapshot,
                scheduled_at=datetime.now(timezone.utc),
            )
            db.add(log_entry)
            db.flush()

            try:
                # Apply retry delay for subsequent attempts
                if attempt > 1 and attempt - 1 <= len(RETRY_DELAYS):
                    delay = RETRY_DELAYS[attempt - 2]
                    time.sleep(delay)

                # Make the HTTP request
                if method == "GET":
                    resp = httpx.get(
                        url, params=final_payload,
                        headers=headers, timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                else:
                    resp = httpx.request(
                        method=method, url=url,
                        json=final_payload, headers=headers,
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )

                response_status = resp.status_code
                response_body = resp.text[:2000]  # Truncate for storage
                now = datetime.now(timezone.utc)

                if resp.status_code < 500:
                    # Success (2xx, 3xx, 4xx treated as delivered)
                    success = True
                    log_entry.status = "success"
                    log_entry.response_status_code = resp.status_code
                    log_entry.response_body = response_body
                    log_entry.delivered_at = now

                    # Record success on the integration
                    service = CustomIntegrationService(db)
                    service.record_success(
                        integration.id, integration.company_id)

                    db.flush()
                    break
                else:
                    # Server error — retry
                    log_entry.status = "failed"
                    log_entry.response_status_code = resp.status_code
                    log_entry.response_body = response_body
                    log_entry.delivered_at = now
                    last_error = f"HTTP {resp.status_code}"
                    db.flush()

            except httpx.TimeoutException:
                now = datetime.now(timezone.utc)
                log_entry.status = "failed"
                log_entry.error_message = f"Timeout after {REQUEST_TIMEOUT_SECONDS}s"
                log_entry.delivered_at = now
                last_error = "Request timed out"
                db.flush()

            except Exception as e:
                now = datetime.now(timezone.utc)
                log_entry.status = "failed"
                log_entry.error_message = str(e)[:500]
                log_entry.delivered_at = now
                last_error = str(e)[:200]
                db.flush()

        # If all retries failed, record failure on the integration
        if not success:
            service = CustomIntegrationService(db)
            auto_disabled = service.record_failure(
                integration.id, integration.company_id,
                last_error or "All retry attempts failed",
            )

        return {
            "integration_id": integration.id,
            "name": integration.name,
            "success": success,
            "trigger_event": trigger_event,
            "attempts": MAX_RETRIES if not success else 1,
            "response_status": response_status,
            "error": last_error if not success else None,
        }

    def _apply_payload_template(
        self,
        template: Optional[Dict[str, Any]],
        payload: Dict[str, Any],
        trigger_event: str,
    ) -> Dict[str, Any]:
        """Apply payload template with variable substitution.

        Template variables: {{event}}, {{payload}}, {{timestamp}}
        """
        if not template:
            return payload

        try:
            result = json.dumps(template)
            result = result.replace("{{event}}", trigger_event)
            result = result.replace("{{payload}}", json.dumps(payload))
            result = result.replace(
                "{{timestamp}}", datetime.now(
                    timezone.utc).isoformat())
            return json.loads(result)
        except Exception:
            return payload

    @staticmethod
    def _sign_payload(
        payload_bytes: bytes,
        secret: str,
        timestamp: str,
    ) -> str:
        """Sign payload with HMAC-SHA256.

        Format: timestamp=xxx,signature=xxx

        BC-003: HMAC verification support.
        """
        signed_payload = f"{timestamp}.{payload_bytes.decode()}"
        signature = hmac_mod.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"t={timestamp},v1={signature}"

    def _log_to_dict(self, log_entry: WebhookDeliveryLog) -> Dict[str, Any]:
        """Convert WebhookDeliveryLog to dict."""
        return {
            "id": log_entry.id,
            "company_id": log_entry.company_id,
            "custom_integration_id": log_entry.custom_integration_id,
            "trigger_event": log_entry.trigger_event,
            "trigger_event_id": log_entry.trigger_event_id,
            "attempt": log_entry.attempt,
            "status": log_entry.status,
            "response_status_code": log_entry.response_status_code,
            "response_body": log_entry.response_body,
            "error_message": log_entry.error_message,
            "scheduled_at": (
                log_entry.scheduled_at.isoformat()
                if log_entry.scheduled_at
                else None
            ),
            "delivered_at": (
                log_entry.delivered_at.isoformat()
                if log_entry.delivered_at
                else None
            ),
            "created_at": (
                log_entry.created_at.isoformat()
                if log_entry.created_at
                else None
            ),
        }
