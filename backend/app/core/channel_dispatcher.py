"""
Channel Dispatcher — Week 13 Day 2 (F-120)

Routes AI-generated responses to the appropriate channel
(email, chat, sms, voice) based on the ticket's channel field.

When the AI pipeline generates a response, this dispatcher:
1. Reads the ticket's channel field
2. Builds channel-specific payload
3. Dispatches to the correct channel service via Celery

Integration Points:
- Called from AI pipeline after response generation (Stage 12+)
- Called from agent reply endpoints (manual agent sends)
- Called from webhook handlers (e.g., email_channel_tasks after AI processing)

Building Codes:
- BC-001: Multi-tenant (scoped to company_id)
- BC-005: Real-time (Socket.io events on dispatch)

Usage:
    dispatcher = ChannelDispatcher(db)
    result = dispatcher.dispatch(
        company_id="abc",
        ticket_id="ticket-123",
        ai_response_html="<p>Here is your answer</p>",
        ai_response_text="Here is your answer",
        role="ai",
        model_used="gemini-pro",
    )
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from database.models.tickets import Ticket, TicketMessage
from app.core.email_utils import strip_html, run_async_coro

logger = logging.getLogger("parwa.channel_dispatcher")


class ChannelDispatcher:
    """Dispatches AI responses to the correct communication channel.

    This is the central routing layer between the AI pipeline and
    channel-specific senders. Every AI-generated response flows
    through this dispatcher.

    Channels supported:
    - email: Via OutboundEmailService + Brevo (F-120)
    - chat: Via Socket.io real-time push
    - sms: Via Twilio (Week 13 Day 5 — stub for now)
    - internal: TicketMessage only, no external send
    """

    def __init__(self, db: Session):
        self.db = db

    def dispatch(
        self,
        company_id: str,
        ticket_id: str,
        ai_response_html: str,
        ai_response_text: Optional[str] = None,
        role: str = "ai",
        model_used: Optional[str] = None,
        confidence: Optional[float] = None,
        attachments: Optional[list] = None,
    ) -> dict:
        """Dispatch an AI response to the ticket's channel.

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket to respond on.
            ai_response_html: AI response as HTML.
            ai_response_text: Plain-text version (fallback).
            role: Who is sending — "ai", "agent", or "system".
            model_used: AI model name for attribution.
            confidence: AI confidence score (0-1).
            attachments: Optional list of attachment dicts for email.

        Returns:
            Dict with status, channel used, and channel-specific data.
        """
        # Load ticket to determine channel
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == company_id,
            )
            .first()
        )

        if not ticket:
            logger.error(
                "dispatch_ticket_not_found",
                extra={"company_id": company_id, "ticket_id": ticket_id},
            )
            return {"status": "error", "error": f"Ticket {ticket_id} not found"}

        channel = ticket.channel or "email"

        # Route to channel-specific handler
        try:
            if channel == "email":
                return self._dispatch_email(
                    company_id=company_id,
                    ticket=ticket,
                    ai_response_html=ai_response_html,
                    ai_response_text=ai_response_text,
                    role=role,
                    model_used=model_used,
                    confidence=confidence,
                    attachments=attachments,
                )
            elif channel == "chat":
                return self._dispatch_chat(
                    company_id=company_id,
                    ticket=ticket,
                    ai_response_html=ai_response_html,
                    ai_response_text=ai_response_text,
                    role=role,
                    model_used=model_used,
                )
            elif channel == "sms":
                return self._dispatch_sms(
                    company_id=company_id,
                    ticket=ticket,
                    ai_response_text=ai_response_text or strip_html(ai_response_html),
                    role=role,
                    model_used=model_used,
                )
            else:
                # Default: create TicketMessage only (no external send)
                return self._dispatch_internal(
                    company_id=company_id,
                    ticket=ticket,
                    ai_response_html=ai_response_html,
                    ai_response_text=ai_response_text,
                    role=role,
                    model_used=model_used,
                    confidence=confidence,
                )
        except Exception as exc:
            logger.error(
                "dispatch_error",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "channel": channel,
                    "error": str(exc)[:200],
                },
            )
            return {"status": "error", "error": str(exc)[:200]}

    def _dispatch_email(
        self,
        company_id: str,
        ticket: Ticket,
        ai_response_html: str,
        ai_response_text: Optional[str],
        role: str,
        model_used: Optional[str],
        confidence: Optional[float],
        attachments: Optional[list] = None,
    ) -> dict:
        """Dispatch AI response via email channel."""
        try:
            from app.tasks.email_tasks import send_outbound_reply

            send_outbound_reply.delay(
                company_id=company_id,
                ticket_id=ticket.id,
                ai_response_html=ai_response_html,
                ai_response_text=ai_response_text,
                sender_name=model_used or "PARWA AI",
                model_used=model_used,
                confidence=confidence,
                attachments=attachments,
            )

            logger.info(
                "dispatched_to_email",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket.id,
                    "role": role,
                },
            )
            return {
                "status": "dispatched",
                "channel": "email",
                "ticket_id": ticket.id,
            }
        except Exception as exc:
            # Fallback: direct service call
            logger.warning(
                "dispatch_email_celery_failed_fallback",
                extra={"error": str(exc)[:200]},
            )
            from app.services.outbound_email_service import OutboundEmailService
            service = OutboundEmailService(self.db)
            return service.send_email_reply(
                company_id=company_id,
                ticket_id=ticket.id,
                ai_response_html=ai_response_html,
                ai_response_text=ai_response_text,
                sender_name=model_used or "PARWA AI",
                model_used=model_used,
                confidence=confidence,
                attachments=attachments,
            )

    def _dispatch_chat(
        self,
        company_id: str,
        ticket: Ticket,
        ai_response_html: str,
        ai_response_text: Optional[str],
        role: str,
        model_used: Optional[str],
    ) -> dict:
        """Dispatch AI response via chat channel (Socket.io).

        Creates a TicketMessage and emits via Socket.io for
        real-time delivery to the customer's chat widget.
        """
        try:
            message = TicketMessage(
                ticket_id=ticket.id,
                company_id=company_id,
                role=role,
                channel="chat",
                content=ai_response_text or strip_html(ai_response_html),
                metadata_json=json.dumps({
                    "source": "ai_response",
                    "model_used": model_used,
                }),
            )
            self.db.add(message)

            if not ticket.first_response_at:
                ticket.first_response_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(message)

            # Emit via Socket.io using run_async_coro (G-02 fix)
            try:
                from app.core.event_emitter import emit_ticket_event
                run_async_coro(
                    emit_ticket_event(
                        company_id=company_id,
                        event_type="ticket:message_added",
                        payload={
                            "ticket_id": ticket.id,
                            "company_id": company_id,
                            "channel": "chat",
                            "message_id": str(message.id),
                            "role": role,
                            "extra": {
                                "content": message.content[:200],
                                "model_used": model_used,
                            },
                        },
                    ),
                )
            except Exception:
                pass  # Non-critical

            return {
                "status": "sent",
                "channel": "chat",
                "ticket_id": ticket.id,
                "message_id": message.id,
            }
        except Exception as exc:
            logger.error(
                "dispatch_chat_error",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket.id,
                    "error": str(exc)[:200],
                },
            )
            return {"status": "error", "channel": "chat", "error": str(exc)[:200]}

    def _dispatch_sms(
        self,
        company_id: str,
        ticket: Ticket,
        ai_response_text: str,
        role: str,
        model_used: Optional[str],
    ) -> dict:
        """Dispatch AI response via SMS channel (Week 13 Day 5 stub).

        Day 5 will implement full SMS dispatch via Twilio.
        Currently stores a TicketMessage and returns a stub status.
        """
        # Create TicketMessage for audit trail even in stub mode
        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role=role,
            channel="sms",
            content=ai_response_text[:160],  # SMS length limit
            metadata_json=json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "stub_pending_day5",
            }),
        )
        self.db.add(message)
        self.db.commit()

        logger.info(
            "dispatch_sms_stub",
            extra={
                "company_id": company_id,
                "ticket_id": ticket.id,
                "message_id": str(message.id),
            },
        )
        return {
            "status": "stub",
            "channel": "sms",
            "ticket_id": ticket.id,
            "message_id": str(message.id),
            "message": "SMS dispatch not yet implemented (Week 13 Day 5)",
        }

    def _dispatch_internal(
        self,
        company_id: str,
        ticket: Ticket,
        ai_response_html: str,
        ai_response_text: Optional[str],
        role: str,
        model_used: Optional[str],
        confidence: Optional[float],
    ) -> dict:
        """Store AI response internally without external channel dispatch.

        Used for channels that don't have an external delivery mechanism
        (e.g., internal notes, API-only channels).
        """
        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role=role,
            channel=ticket.channel or "internal",
            content=ai_response_text or strip_html(ai_response_html),
            metadata_json=json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "confidence": confidence,
            }),
        )
        self.db.add(message)

        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(message)

        return {
            "status": "stored",
            "channel": ticket.channel or "internal",
            "ticket_id": ticket.id,
            "message_id": message.id,
        }
