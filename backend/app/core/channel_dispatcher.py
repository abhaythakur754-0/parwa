"""
Channel Dispatcher — Week 13 Day 2 (F-120)

Routes AI-generated responses to the appropriate channel
(email, chat, sms, voice) based on the ticket's channel field.

When the AI pipeline generates a response, this dispatcher:
1. Reads the ticket's channel field
2. Builds channel-specific payload
3. Dispatches to the correct channel service via Celery

Building Codes:
- BC-001: Multi-tenant (scoped to company_id)
- BC-005: Real-time (Socket.io events on dispatch)
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from database.models.tickets import Ticket

logger = logging.getLogger("parwa.channel_dispatcher")


class ChannelDispatcher:
    """Dispatches AI responses to the correct communication channel.

    Usage:
        dispatcher = ChannelDispatcher(db)
        dispatcher.dispatch(
            company_id="abc",
            ticket_id="ticket-123",
            ai_response_html="<p>Here is your answer</p>",
            ai_response_text="Here is your answer",
            role="ai",
            model_used="gemini-pro",
        )
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
                    ai_response_text=ai_response_text or self._strip_html(ai_response_html),
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
        """Dispatch AI response via chat channel (Socket.io)."""
        try:
            # Create TicketMessage
            from database.models.tickets import TicketMessage

            message = TicketMessage(
                ticket_id=ticket.id,
                company_id=company_id,
                role=role,
                channel="chat",
                content=ai_response_text or self._strip_html(ai_response_html),
                metadata_json=json.dumps({
                    "source": "ai_response",
                    "model_used": model_used,
                }),
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            # Emit via Socket.io
            try:
                from app.core.ticket_events import emit_ticket_event
                emit_ticket_event(
                    company_id=company_id,
                    event_type="message_added",
                    ticket_id=ticket.id,
                    data={
                        "message_id": message.id,
                        "role": role,
                        "channel": "chat",
                        "content": message.content[:200],
                    },
                )
            except Exception:
                pass

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
        """Dispatch AI response via SMS channel (Week 13 Day 5 stub)."""
        # Day 5 will implement full SMS dispatch via Twilio
        logger.info(
            "dispatch_sms_stub",
            extra={
                "company_id": company_id,
                "ticket_id": ticket.id,
            },
        )
        return {
            "status": "stub",
            "channel": "sms",
            "ticket_id": ticket.id,
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
        """Store AI response internally without external channel dispatch."""
        from database.models.tickets import TicketMessage

        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role=role,
            channel=ticket.channel or "internal",
            content=ai_response_text or self._strip_html(ai_response_html),
            metadata_json=json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "confidence": confidence,
            }),
        )
        self.db.add(message)

        if not ticket.first_response_at:
            ticket.first_response_at = __import__("datetime", fromlist=["datetime"]).datetime.now(__import__("datetime", fromlist=["timezone"]).timezone.utc)

        self.db.commit()
        self.db.refresh(message)

        return {
            "status": "stored",
            "channel": ticket.channel or "internal",
            "ticket_id": ticket.id,
            "message_id": message.id,
        }

    @staticmethod
    def _strip_html(html: str) -> str:
        """Strip HTML tags."""
        if not html:
            return ""
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
