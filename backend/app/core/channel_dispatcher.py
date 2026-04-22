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
    - sms: Via Twilio with TCPA compliance (BC-010) and rate limiting (BC-006)
    - voice: Audit trail only (TTS pipeline integration pending)
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
            elif channel == "voice":
                return self._dispatch_voice(
                    company_id=company_id,
                    ticket=ticket,
                    ai_response_text=(
                        ai_response_text or strip_html(ai_response_html)
                    ),
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
        """Dispatch AI response via SMS channel (Twilio).

        Creates a TicketMessage for audit trail, retrieves the
        customer's phone number, and sends via Twilio async.

        Handles TwilioTCPAError (BC-010) and TwilioRateLimitError
        (BC-006) gracefully, updating dispatch_status in metadata.
        """
        # ── Resolve customer phone number ───────────────────────
        to_number = self._get_customer_phone(ticket)
        if not to_number:
            logger.error(
                "dispatch_sms_no_phone",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket.id,
                },
            )
            # Create TicketMessage so the audit trail is preserved
            message = TicketMessage(
                ticket_id=ticket.id,
                company_id=company_id,
                role=role,
                channel="sms",
                content=(ai_response_text or "")[:1600],
                metadata_json=json.dumps({
                    "source": "ai_response",
                    "model_used": model_used,
                    "dispatch_status": "failed",
                    "error": "No customer phone number found on ticket",
                }),
            )
            self.db.add(message)
            self.db.commit()
            return {
                "status": "error",
                "channel": "sms",
                "ticket_id": ticket.id,
                "message_id": str(message.id),
                "error": "No customer phone number found",
            }

        # ── Truncate body to Twilio limit (1600 chars) ──────────
        sms_body = (ai_response_text or "")[:1600]

        # ── Create TicketMessage for audit trail ────────────────
        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role=role,
            channel="sms",
            content=sms_body[:200],  # Preview for ticket view
            metadata_json=json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "dispatching",
                "to_number": to_number,
                "body_length": len(sms_body),
            }),
        )
        self.db.add(message)

        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(message)

        # ── Send via Twilio (async, fire-and-forget) ────────────
        run_async_coro(
            self._send_sms_async(
                message_id=message.id,
                company_id=company_id,
                to_number=to_number,
                body=sms_body,
            )
        )

        logger.info(
            "dispatched_to_sms",
            extra={
                "company_id": company_id,
                "ticket_id": ticket.id,
                "message_id": str(message.id),
                "to_number": to_number,
                "role": role,
            },
        )
        return {
            "status": "dispatched",
            "channel": "sms",
            "ticket_id": ticket.id,
            "message_id": str(message.id),
        }

    # ── SMS Helpers ─────────────────────────────────────────────

    async def _send_sms_async(
        self,
        message_id: str,
        company_id: str,
        to_number: str,
        body: str,
    ) -> None:
        """Async helper: send SMS via Twilio and update TicketMessage.

        Called via ``run_async_coro`` from the sync ``_dispatch_sms``.
        Handles Twilio-specific exceptions and updates the
        TicketMessage metadata_json with the final dispatch status.
        """
        from app.core.channels.twilio_client import (
            TwilioClientError,
            TwilioRateLimitError,
            TwilioTCPAError,
            get_twilio_client,
        )

        try:
            client = get_twilio_client(company_id, self.db)
            result = await client.send_sms(
                to=to_number,
                body=body,
                company_id=company_id,
                db=self.db,
            )

            if result.get("success"):
                self._update_message_dispatch_status(
                    message_id=message_id,
                    status="sent",
                    twilio_sid=result.get("message_sid"),
                    twilio_status=result.get("status"),
                )
                logger.info(
                    "dispatch_sms_sent",
                    extra={
                        "company_id": company_id,
                        "message_id": message_id,
                        "twilio_sid": result.get("message_sid"),
                        "to_number": to_number,
                    },
                )
            else:
                self._update_message_dispatch_status(
                    message_id=message_id,
                    status="failed",
                    error=result.get("error_message", "Twilio send failed"),
                    error_code=result.get("error_code"),
                )
                logger.warning(
                    "dispatch_sms_twilio_rejected",
                    extra={
                        "company_id": company_id,
                        "message_id": message_id,
                        "error_code": result.get("error_code"),
                        "to_number": to_number,
                    },
                )

        except TwilioTCPAError as exc:
            logger.warning(
                "dispatch_sms_tcpa_blocked",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "to_number": to_number,
                    "error": str(exc)[:200],
                },
            )
            self._update_message_dispatch_status(
                message_id=message_id,
                status="failed",
                error=f"TCPA compliance: {exc}",
            )

        except TwilioRateLimitError as exc:
            logger.warning(
                "dispatch_sms_rate_limited",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "to_number": to_number,
                    "error": str(exc)[:200],
                },
            )
            self._update_message_dispatch_status(
                message_id=message_id,
                status="failed",
                error=f"Rate limited (BC-006): {exc}",
            )

        except TwilioClientError as exc:
            logger.error(
                "dispatch_sms_client_error",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "to_number": to_number,
                    "error": str(exc)[:200],
                },
            )
            self._update_message_dispatch_status(
                message_id=message_id,
                status="failed",
                error=str(exc)[:200],
            )

        except Exception as exc:
            logger.error(
                "dispatch_sms_unexpected_error",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "to_number": to_number,
                    "error": str(exc)[:200],
                },
            )
            self._update_message_dispatch_status(
                message_id=message_id,
                status="failed",
                error=str(exc)[:200],
            )

    def _get_customer_phone(self, ticket: Ticket) -> Optional[str]:
        """Extract customer phone number from ticket metadata or customer.

        Resolution order:
        1. ``ticket.metadata_json["customer_number"]`` (set by SMS inbound)
        2. ``ticket.metadata_json["from_number"]`` (Twilio webhook)
        3. Customer record linked via ``ticket.customer_id``

        Returns:
            Phone number string or None.
        """
        # 1 & 2: Check ticket metadata (populated by SMS inbound pipeline)
        if ticket.metadata_json:
            try:
                meta = (json.loads(ticket.metadata_json)
                        if isinstance(ticket.metadata_json, str)
                        else ticket.metadata_json)
                phone = meta.get("customer_number") or meta.get("from_number")
                if phone:
                    return str(phone)
            except (json.JSONDecodeError, TypeError):
                pass

        # 3: Look up customer record
        if hasattr(ticket, "customer_id") and ticket.customer_id:
            try:
                from database.models.customers import Customer
                customer = self.db.query(Customer).filter(
                    Customer.id == ticket.customer_id,
                    Customer.company_id == ticket.company_id,
                ).first()
                if customer:
                    phone = (getattr(customer, "phone", None)
                             or getattr(customer, "phone_number", None))
                    if phone:
                        return str(phone)
            except Exception as exc:
                logger.warning(
                    "dispatch_sms_customer_lookup_failed",
                    extra={
                        "ticket_id": ticket.id,
                        "customer_id": str(ticket.customer_id),
                        "error": str(exc)[:100],
                    },
                )

        return None

    def _update_message_dispatch_status(
        self,
        message_id: str,
        status: str,
        twilio_sid: Optional[str] = None,
        twilio_status: Optional[str] = None,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """Update a TicketMessage's metadata_json dispatch status.

        Merges the new status fields into the existing metadata.
        Handles session issues gracefully (e.g., closed session
        after fire-and-forget async execution).
        """
        try:
            message = self.db.query(TicketMessage).filter(
                TicketMessage.id == message_id,
            ).first()
            if not message:
                return

            # Parse existing metadata and merge
            try:
                meta = (json.loads(message.metadata_json)
                        if message.metadata_json else {})
            except (json.JSONDecodeError, TypeError):
                meta = {}

            meta["dispatch_status"] = status
            if twilio_sid:
                meta["twilio_message_sid"] = twilio_sid
            if twilio_status:
                meta["twilio_status"] = twilio_status
            if error:
                meta["error"] = error
            if error_code:
                meta["error_code"] = error_code

            message.metadata_json = json.dumps(meta)
            self.db.commit()
        except Exception as exc:
            # Non-critical: the message was already created with
            # dispatch_status="dispatching" — don't raise.
            logger.warning(
                "dispatch_sms_metadata_update_failed",
                extra={
                    "message_id": message_id,
                    "error": str(exc)[:100],
                },
            )

    # ── Voice Channel ───────────────────────────────────────────

    def _dispatch_voice(
        self,
        company_id: str,
        ticket: Ticket,
        ai_response_text: str,
        role: str,
        model_used: Optional[str],
    ) -> dict:
        """Dispatch AI response via voice channel.

        Currently stores a TicketMessage for audit trail and logs
        a warning that the TTS (text-to-speech) pipeline is required
        for actual voice delivery.

        Future: integrate TTS → Twilio <Say>/<Play> TwiML →
        ``TwilioClient.make_call()`` for outbound voice responses.
        """
        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role=role,
            channel="voice",
            content=ai_response_text,
            metadata_json=json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "stored",
                "note": "Voice delivery requires TTS pipeline integration",
            }),
        )
        self.db.add(message)

        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(message)

        logger.warning(
            "dispatch_voice_tts_pending",
            extra={
                "company_id": company_id,
                "ticket_id": ticket.id,
                "message_id": str(message.id),
                "detail": (
                    "Voice AI response stored but not delivered — "
                    "TTS pipeline + Twilio make_call() integration needed"
                ),
            },
        )
        return {
            "status": "stored",
            "channel": "voice",
            "ticket_id": ticket.id,
            "message_id": str(message.id),
            "note": "Voice delivery requires TTS pipeline",
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
