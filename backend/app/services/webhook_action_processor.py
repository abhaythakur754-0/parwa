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

    # BC-024: Fix broken Twilio SMS inbound — was previously dropped because
    # no handler existed for "store_sms_notification" action. Now we route
    # it to the SMS channel service which creates a ticket + triggers AI.
    if provider == "twilio" and action == "store_sms_notification":
        return _process_twilio_inbound_sms(company_id, data)

    # BC-024: Also support vonage and generic SMS providers
    if provider in ("vonage", "nexmo") and action == "store_sms_notification":
        return _process_sms_inbound(company_id, "vonage", data)

    if provider == "generic" and action == "store_sms_notification":
        return _process_sms_inbound(company_id, "generic", data)

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
            service = EmailChannelService(db)
            result = service.process_inbound_email(
                company_id=company_id, email_data=email_data,
            )
            ticket_id = result.get("ticket_id") if isinstance(result, dict) else result

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
    """Process Brevo bounce event (F-124).

    Delegates to BounceComplaintService for full bounce processing:
    hard/soft classification, email status update, retry scheduling.

    Args:
        company_id: Tenant company ID.
        bounce_data: Bounce event data with email, bounce_type, reason.

    Returns:
        Dict with processing result.
    """
    try:
        from database.base import get_db_context
        from app.services.bounce_complaint_service import (
            BounceComplaintService,
        )

        with get_db_context() as db:
            service = BounceComplaintService(db)
            result = service.process_bounce(
                company_id=company_id,
                bounce_data=bounce_data,
            )
            logger.info(
                "webhook_bounce_processed email=%s status=%s",
                bounce_data.get("email"),
                result.get("status"),
                extra={"company_id": company_id},
            )
            return result
    except Exception as exc:
        logger.error(
            "webhook_bounce_processing_error error=%s email=%s",
            str(exc)[:200],
            bounce_data.get("email"),
            extra={"company_id": company_id},
        )
        return {
            "status": "error",
            "action": "process_bounce",
            "error": str(exc)[:500],
        }


def _process_brevo_complaint(
    company_id: str,
    complaint_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Process Brevo complaint event (F-124).

    Delegates to BounceComplaintService for full complaint processing:
    mark email as complained, BC-010 permanent suppression.

    Args:
        company_id: Tenant company ID.
        complaint_data: Complaint event data with email, reason.

    Returns:
        Dict with processing result.
    """
    try:
        from database.base import get_db_context
        from app.services.bounce_complaint_service import (
            BounceComplaintService,
        )

        with get_db_context() as db:
            service = BounceComplaintService(db)
            result = service.process_complaint(
                company_id=company_id,
                complaint_data=complaint_data,
            )
            logger.warning(
                "webhook_complaint_processed email=%s status=%s",
                complaint_data.get("email"),
                result.get("status"),
                extra={"company_id": company_id},
            )
            return result
    except Exception as exc:
        logger.error(
            "webhook_complaint_processing_error error=%s email=%s",
            str(exc)[:200],
            complaint_data.get("email"),
            extra={"company_id": company_id},
        )
        return {
            "status": "error",
            "action": "process_complaint",
            "error": str(exc)[:500],
        }


# ═══════════════════════════════════════════════════════════════
# BC-024: SMS Inbound Processing
# ═══════════════════════════════════════════════════════════════

def _process_twilio_inbound_sms(
    company_id: str,
    sms_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Process Twilio inbound SMS by creating a ticket + triggering AI.

    BC-024: Previously this action was logged and dropped — SMS messages
    were silently lost. Now we route to SMSChannelService which creates
    a ticket, then triggers the AI pipeline if bot_enabled for the tenant.

    Args:
        company_id: Tenant company ID.
        sms_data: Extracted SMS data from twilio_handler (from_number, to_number, body, etc.).

    Returns:
        Dict with processing result.
    """
    return _process_sms_inbound(company_id, "twilio", sms_data)


def _process_sms_inbound(
    company_id: str,
    provider: str,
    sms_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Process inbound SMS from any provider — create ticket + trigger AI.

    Used by _process_twilio_inbound_sms (BC-024) and the vonage/generic
    SMS handlers. The SMS data is already in normalized format from the
    provider's webhook handler.

    Args:
        company_id: Tenant company ID.
        provider: SMS provider name (twilio, vonage, generic).
        sms_data: Normalized SMS data with from_number, to_number, body.

    Returns:
        Dict with processing result.
    """
    try:
        from database.base import get_db_context
        from app.services.sms_channel_service import SMSChannelService

        with get_db_context() as db:
            service = SMSChannelService(db)
            # SMSChannelService.process_inbound_sms creates a ticket internally
            # (or links to existing) and stores the message.
            result = service.process_inbound_sms(
                company_id=company_id,
                provider=provider,
                sms_data=sms_data,
            )

            ticket_id = result.get("ticket_id")
            logger.info(
                "webhook_sms_processed provider=%s from=%s ticket=%s",
                provider,
                sms_data.get("from_number"),
                ticket_id,
                extra={"company_id": company_id},
            )

            # BC-024: Trigger AI pipeline for inbound SMS if bot_enabled for tenant
            if ticket_id:
                _maybe_trigger_ai_for_sms(
                    company_id=company_id,
                    ticket_id=ticket_id,
                    sms_data=sms_data,
                    provider=provider,
                )

            return result
    except Exception as exc:
        logger.error(
            "webhook_sms_processing_error error=%s provider=%s from=%s",
            str(exc)[:200],
            provider,
            sms_data.get("from_number"),
            extra={"company_id": company_id},
            exc_info=True,
        )
        return {
            "status": "error",
            "action": "store_sms_notification",
            "error": str(exc)[:500],
        }


def _maybe_trigger_ai_for_sms(
    company_id: str,
    ticket_id: str,
    sms_data: Dict[str, Any],
    provider: str,
) -> None:
    """BC-024: Trigger AI pipeline for an inbound SMS if bot is enabled.

    Checks the chat widget config (bot_enabled field). If true, kicks off
    the PARWA pipeline in a background thread. When the pipeline finishes,
    the AI response is sent back via SMSBridge.send_sms().

    Args:
        company_id: Tenant company ID.
        ticket_id: Ticket ID created from this SMS.
        sms_data: SMS data with from_number, body, etc.
        provider: SMS provider name (for sending reply back).
    """
    import threading

    try:
        from database.base import get_db_context
        from database.models.chat_widget import ChatWidgetConfig

        with get_db_context() as db:
            config = (
                db.query(ChatWidgetConfig)
                .filter(ChatWidgetConfig.company_id == company_id)
                .first()
            )
            if not config or not getattr(config, "bot_enabled", False):
                return  # AI not enabled — leave ticket for human agents
    except Exception as exc:
        logger.warning(
            "sms_ai_enabled_check_failed error=%s",
            str(exc)[:200],
            extra={"company_id": company_id},
        )
        return

    # Fire and forget
    thread = threading.Thread(
        target=_run_sms_ai_pipeline_sync,
        args=(company_id, ticket_id, sms_data, provider),
        daemon=True,
    )
    thread.start()

    logger.info(
        "sms_ai_pipeline_triggered",
        extra={
            "company_id": company_id,
            "ticket_id": ticket_id,
            "provider": provider,
            "from": sms_data.get("from_number"),
        },
    )


def _run_sms_ai_pipeline_sync(
    company_id: str,
    ticket_id: str,
    sms_data: Dict[str, Any],
    provider: str,
) -> None:
    """Run the PARWA pipeline for an inbound SMS, then SMS the reply back.

    Runs in a background thread. Failures are logged but never propagated
    — the ticket remains open for human agents if AI fails.
    """
    import asyncio
    import time
    import uuid

    start = time.time()

    try:
        from app.core.parwa_pipeline.state_v2 import PipelineV2State

        initial_state: PipelineV2State = {
            "ticket_id": f"TKT-SMS-{ticket_id}",
            "tenant_id": company_id,
            "query": sms_data.get("body", ""),
            "channel_type": "sms",
            "customer_context": {
                "customer_id": sms_data.get("from_number", ""),
                "phone": sms_data.get("from_number", ""),
                "account_tier": "parwa",
            },
            "metadata": {
                "source": "inbound_sms",
                "ticket_id": ticket_id,
                "provider": provider,
                "from_number": sms_data.get("from_number", ""),
                "to_number": sms_data.get("to_number", ""),
                "message_id": sms_data.get("message_id", ""),
            },
        }

        from app.core.parwa_pipeline.graph_v2 import build_parwa_pipeline

        graph = build_parwa_pipeline()
        compiled = graph.compile()
        result = asyncio.run(compiled.ainvoke(initial_state))
        result = dict(result)

        ai_response = (
            result.get("final_response")
            or result.get("response")
            or "Thanks for your message. An agent will follow up shortly."
        )

        # Send the AI response back via SMSBridge
        from app.core.sms_bridge.sms_bridge import SMSBridge
        from app.services.integration_service import IntegrationService
        from database.base import get_db_context

        # Look up SMS provider config
        with get_db_context() as db:
            svc = IntegrationService(db)
            # Try the original provider first, then fall back to others
            sms_config = None
            for p in (provider, "twilio", "vonage", "generic"):
                cfg = svc.get_credential_config(company_id, f"sms_{p}")
                if cfg:
                    sms_config = cfg
                    provider = p  # Use the configured provider
                    break

        if sms_config:
            send_result = asyncio.run(SMSBridge.send_sms(
                provider=provider,
                to_number=sms_data.get("from_number", ""),
                body=str(ai_response)[:1600],  # SMS max 1600 chars
                config=sms_config,
            ))

            if send_result.get("success"):
                logger.info(
                    "sms_ai_reply_sent",
                    extra={
                        "company_id": company_id,
                        "ticket_id": ticket_id,
                        "provider": provider,
                    },
                )
            else:
                logger.warning(
                    "sms_ai_reply_failed",
                    extra={
                        "company_id": company_id,
                        "ticket_id": ticket_id,
                        "error": send_result.get("error"),
                    },
                )
        else:
            logger.warning(
                "sms_ai_no_provider_configured",
                extra={"company_id": company_id, "ticket_id": ticket_id},
            )

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "sms_ai_pipeline_completed",
            extra={
                "company_id": company_id,
                "ticket_id": ticket_id,
                "elapsed_ms": elapsed_ms,
                "escalated": result.get("status") == "escalated",
            },
        )

    except Exception as exc:
        logger.error(
            "sms_ai_pipeline_failed error=%s",
            str(exc)[:500],
            extra={
                "company_id": company_id,
                "ticket_id": ticket_id,
                "provider": provider,
            },
            exc_info=True,
        )
