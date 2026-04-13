"""
PARWA Webhook Action Processor (F-121: Email Inbound)

Week 13 Day 1: Processes actions returned by webhook handlers.

After a webhook handler (e.g. brevo_handler) parses a webhook event and
returns {"action": "...", "data": {...}}, this processor routes the action
to the appropriate service.

Actions handled:
- create_ticket_draft: Dispatches to email_channel_service.process_inbound_email()

This keeps webhook handlers (parsing) separated from business logic (processing).

BC-001: All actions require company_id.
BC-003: Webhook actions are idempotent.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("parwa.webhook_action_processor")


def process_webhook_action(
    company_id: str,
    provider: str,
    handler_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Process a webhook handler result by dispatching to the appropriate service.

    Called after a webhook handler returns its result. If the result contains
    an "action" field, it routes to the corresponding service.

    Args:
        company_id: Tenant company ID (BC-001).
        provider: Provider name (e.g. "brevo", "paddle").
        handler_result: Dict returned by the provider's webhook handler.
            Expected keys:
            - status: "processed" or "validation_error"
            - action: Optional action string (e.g. "create_ticket_draft")
            - data: Optional payload dict for the action

    Returns:
        Dict with processing result:
        - status: "dispatched" | "skipped" | "error"
        - action: The action that was dispatched
        - ticket_id: Created ticket ID (if applicable)
        - error: Error message (if applicable)
    """
    if not handler_result or handler_result.get("status") != "processed":
        return {
            "status": "skipped",
            "reason": "Handler did not return 'processed' status",
        }

    action = handler_result.get("action")
    if not action:
        return {
            "status": "skipped",
            "reason": "No action specified in handler result",
        }

    data = handler_result.get("data", {})

    # Route actions by provider + action type
    if provider == "brevo" and action == "create_ticket_draft":
        return _process_brevo_inbound_email(company_id, data)

    if provider == "brevo" and action == "process_bounce":
        return _process_brevo_bounce(company_id, data)

    if provider == "brevo" and action == "process_complaint":
        return _process_brevo_complaint(company_id, data)

    logger.info(
        "webhook_action_no_handler provider=%s action=%s",
        provider, action,
        extra={"company_id": company_id},
    )

    return {
        "status": "skipped",
        "reason": f"No handler for action '{action}' from provider '{provider}'",
    }


def _process_brevo_inbound_email(
    company_id: str,
    email_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Process Brevo inbound email by creating/updating a ticket.

    Uses EmailChannelService to handle the full email processing pipeline.

    Args:
        company_id: Tenant company ID.
        email_data: Extracted email data from brevo_handler.

    Returns:
        Dict with processing result.
    """
    try:
        from database.base import get_db_context
        from app.services.email_channel_service import EmailChannelService

        with get_db_context() as db:
            service = EmailChannelService(db, company_id)
            ticket_id = service.process_inbound_email(email_data)

            if ticket_id:
                logger.info(
                    "webhook_email_processed ticket_id=%s sender=%s",
                    ticket_id,
                    email_data.get("sender_email"),
                    extra={"company_id": company_id},
                )
                return {
                    "status": "dispatched",
                    "action": "create_ticket_draft",
                    "ticket_id": ticket_id,
                }
            else:
                logger.info(
                    "webhook_email_skipped sender=%s",
                    email_data.get("sender_email"),
                    extra={"company_id": company_id},
                )
                return {
                    "status": "skipped",
                    "action": "create_ticket_draft",
                    "reason": "Email skipped (auto-reply, loop, or processing error)",
                }

    except Exception as exc:
        logger.error(
            "webhook_email_processing_error error=%s sender=%s",
            str(exc),
            email_data.get("sender_email"),
            extra={"company_id": company_id},
        )
        return {
            "status": "error",
            "action": "create_ticket_draft",
            "error": str(exc)[:500],
        }


def _process_brevo_bounce(
    company_id: str,
    bounce_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Process Brevo bounce event (stub for Day 3).

    Args:
        company_id: Tenant company ID.
        bounce_data: Bounce event data.

    Returns:
        Dict with processing result.
    """
    logger.info(
        "webhook_bounce_received (stub) email=%s",
        bounce_data.get("email"),
        extra={"company_id": company_id},
    )
    return {
        "status": "skipped",
        "action": "process_bounce",
        "reason": "Bounce processing not yet implemented (Day 3)",
    }


def _process_brevo_complaint(
    company_id: str,
    complaint_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Process Brevo complaint event (stub for Day 3).

    Args:
        company_id: Tenant company ID.
        complaint_data: Complaint event data.

    Returns:
        Dict with processing result.
    """
    logger.info(
        "webhook_complaint_received (stub) email=%s",
        complaint_data.get("email"),
        extra={"company_id": company_id},
    )
    return {
        "status": "skipped",
        "action": "process_complaint",
        "reason": "Complaint processing not yet implemented (Day 3)",
    }
