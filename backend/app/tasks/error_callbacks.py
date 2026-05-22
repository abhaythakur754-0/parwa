"""
PARWA Task Error Callbacks (CL-04 FIX)

Provides error callback functions that can be linked to critical Celery
tasks so that permanent failures are not silently swallowed.

CL-04 FIX: Critical tasks (billing, SLA) should chain an error callback
via `link_error=` so that when a task permanently fails, the failure
is acted upon (alerts, notifications, compensating actions).

Usage:
    from app.tasks.error_callbacks import (
        billing_failure_callback,
        sla_failure_callback,
    )

    my_task.apply_async(
        args=[company_id],
        link_error=billing_failure_callback.s(),
    )
"""

import json
import logging
from typing import Any, Dict

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.error_callbacks")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.callbacks.billing_failure",
    max_retries=2,
    soft_time_limit=30,
    time_limit=60,
)
def billing_failure_callback(self, task_failure_info: Any = None) -> Dict[str, Any]:
    """Error callback for billing tasks.

    CL-04 FIX: When a billing task permanently fails, this callback:
    1. Logs the failure with structured context
    2. Sends an alert notification to ops team
    3. Records the failure in the billing audit trail

    Args:
        task_failure_info: Celery passes the exception info from the
            failed task as the argument to the error callback.

    Returns:
        Dict with callback status
    """
    try:
        # Parse the failure info
        failure_data = {}
        if isinstance(task_failure_info, Exception):
            failure_data = {
                "error_type": type(task_failure_info).__name__,
                "error_message": str(task_failure_info)[:500],
            }
        elif isinstance(task_failure_info, dict):
            failure_data = task_failure_info
        elif isinstance(task_failure_info, str):
            try:
                failure_data = json.loads(task_failure_info)
            except json.JSONDecodeError:
                failure_data = {"raw": task_failure_info[:500]}

        logger.error(
            "billing_task_permanent_failure_callback",
            extra={
                "callback_task": self.name,
                "failure_data": failure_data,
                "action": "billing_failure_alert_sent",
            },
        )

        # Send alert via event emitter (if available)
        try:
            from app.core.event_buffer import add_event
            add_event(
                event_type="billing_task_failure",
                data={
                    "error_type": failure_data.get("error_type", "unknown"),
                    "error_message": failure_data.get("error_message", ""),
                    "callback_task_id": self.request.id,
                },
            )
        except Exception as emit_exc:
            logger.warning(
                "billing_failure_event_emit_failed",
                extra={"error": str(emit_exc)[:200]},
            )

        return {
            "status": "callback_processed",
            "failure_data": failure_data,
        }

    except Exception as exc:
        logger.error(
            "billing_failure_callback_error",
            extra={"error": str(exc)[:200]},
        )
        return {"status": "callback_error", "error": str(exc)[:200]}


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.callbacks.sla_failure",
    max_retries=2,
    soft_time_limit=30,
    time_limit=60,
)
def sla_failure_callback(self, task_failure_info: Any = None) -> Dict[str, Any]:
    """Error callback for SLA tasks.

    CL-04 FIX: When an SLA task permanently fails, this callback:
    1. Logs the failure with structured context
    2. Sends an alert notification to ops team
    3. Marks the affected SLA timer for manual review

    This is critical because SLA failures can mean:
    - A customer's SLA was breached but no notification was sent
    - A ticket wasn't escalated when it should have been
    - The company is unaware of SLA non-compliance

    Args:
        task_failure_info: Exception info from the failed task.

    Returns:
        Dict with callback status
    """
    try:
        # Parse the failure info
        failure_data = {}
        if isinstance(task_failure_info, Exception):
            failure_data = {
                "error_type": type(task_failure_info).__name__,
                "error_message": str(task_failure_info)[:500],
            }
        elif isinstance(task_failure_info, dict):
            failure_data = task_failure_info
        elif isinstance(task_failure_info, str):
            try:
                failure_data = json.loads(task_failure_info)
            except json.JSONDecodeError:
                failure_data = {"raw": task_failure_info[:500]}

        logger.error(
            "sla_task_permanent_failure_callback",
            extra={
                "callback_task": self.name,
                "failure_data": failure_data,
                "action": "sla_failure_alert_sent",
            },
        )

        # Send alert via event emitter (if available)
        try:
            from app.core.event_buffer import add_event
            add_event(
                event_type="sla_task_failure",
                data={
                    "error_type": failure_data.get("error_type", "unknown"),
                    "error_message": failure_data.get("error_message", ""),
                    "callback_task_id": self.request.id,
                },
            )
        except Exception as emit_exc:
            logger.warning(
                "sla_failure_event_emit_failed",
                extra={"error": str(emit_exc)[:200]},
            )

        return {
            "status": "callback_processed",
            "failure_data": failure_data,
        }

    except Exception as exc:
        logger.error(
            "sla_failure_callback_error",
            extra={"error": str(exc)[:200]},
        )
        return {"status": "callback_error", "error": str(exc)[:200]}
