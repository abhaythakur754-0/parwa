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
import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional, Any, Coroutine

from sqlalchemy.orm import Session

from database.models.tickets import Ticket, TicketMessage
from app.core.email_utils import strip_html, run_async_coro

logger = logging.getLogger("parwa.channel_dispatcher")


def _run_async_safely(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from sync code AND return its result.

    Handles two cases:
    1. No running event loop in current thread → use ``asyncio.run``.
    2. Running event loop in current thread (e.g. FastAPI/uvicorn) →
       dispatch to a fresh worker thread that has no loop, run there,
       and return the result. This avoids the
       ``RuntimeError: asyncio.run() cannot be called from a running event loop``
       crash.

    Args:
        coro: An awaitable coroutine (e.g. ``SMSBridge.send_sms(...)``).

    Returns:
        The coroutine's return value.
    """
    try:
        asyncio.get_running_loop()
        # We're inside a running loop — run the coroutine in a worker
        # thread with its own fresh loop, then return the result.
        result_holder: dict = {}

        def _worker() -> None:
            try:
                result_holder["value"] = asyncio.run(coro)
            except Exception as exc:  # noqa: BLE001
                result_holder["error"] = exc

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()
        if "error" in result_holder:
            raise result_holder["error"]
        return result_holder.get("value")
    except RuntimeError:
        # No running loop — safe to use asyncio.run directly.
        return asyncio.run(coro)


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
            elif channel == "voice":
                return self._dispatch_voice(
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
        """Dispatch AI response via SMS channel (BC-024: provider-agnostic).

        Uses SMSBridge to send via the tenant's configured SMS provider
        (Twilio, Vonage, or generic SMS gateway). Falls back to storing
        the message as a TicketMessage if no SMS provider is configured.
        """
        # Create TicketMessage for audit trail
        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role=role,
            channel="sms",
            content=ai_response_text[:1600],  # SMS max 1600 chars
            metadata_json=json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "pending",
            }),
        )
        self.db.add(message)
        self.db.commit()

        # BC-024: Use SMSBridge to actually send the SMS via configured provider
        import asyncio
        try:
            from app.core.sms_bridge.sms_bridge import SMSBridge
            from app.services.integration_service import IntegrationService

            svc = IntegrationService(self.db)
            sms_provider = None
            sms_config = None
            # Catalog keys are "twilio", "vonage", "plivo", "telnyx", "messagebird"
            # (NOT "sms_twilio" — that was a bug that prevented finding credentials)
            for p in ("twilio", "vonage", "plivo", "telnyx", "messagebird"):
                cfg = svc.get_credential_config(company_id, p)
                if cfg:
                    sms_provider = p
                    sms_config = cfg
                    break

            if not sms_provider:
                logger.warning(
                    "dispatch_sms_no_provider",
                    extra={"company_id": company_id, "ticket_id": ticket.id},
                )
                message.metadata_json = json.dumps({
                    "source": "ai_response",
                    "model_used": model_used,
                    "dispatch_status": "no_provider_configured",
                })
                self.db.commit()
                return {
                    "status": "no_provider",
                    "channel": "sms",
                    "ticket_id": ticket.id,
                    "message_id": str(message.id),
                    "message": "No SMS provider configured for tenant",
                }

            # Get customer phone from ticket metadata
            customer_phone = ""
            if ticket.metadata_json:
                try:
                    meta = json.loads(ticket.metadata_json)
                    customer_phone = meta.get("from_number") or meta.get("phone") or meta.get("customer_phone", "")
                except Exception:
                    pass

            if not customer_phone:
                logger.warning(
                    "dispatch_sms_no_recipient",
                    extra={"company_id": company_id, "ticket_id": ticket.id},
                )
                return {
                    "status": "no_recipient",
                    "channel": "sms",
                    "ticket_id": ticket.id,
                    "message_id": str(message.id),
                    "message": "No customer phone number on ticket",
                }

            # Send via SMSBridge
            # CRITICAL: SMSBridge.send_sms is async. We may be called from
            # an async context (pipeline node) or sync context. asyncio.run()
            # crashes if a loop is already running in this thread. So we
            # detect and dispatch to a worker thread with its own loop.
            send_result = _run_async_safely(SMSBridge.send_sms(
                provider=sms_provider,
                to_number=customer_phone,
                body=ai_response_text[:1600],
                config=sms_config,
            ))

            dispatch_status = "sent" if send_result.get("success") else "failed"
            message.metadata_json = json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": dispatch_status,
                "sms_provider": sms_provider,
                "sms_message_id": send_result.get("message_id", ""),
                "error": send_result.get("error", ""),
            })
            self.db.commit()

            logger.info(
                "dispatch_sms_sent" if dispatch_status == "sent" else "dispatch_sms_failed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket.id,
                    "message_id": str(message.id),
                    "provider": sms_provider,
                },
            )
            return {
                "status": dispatch_status,
                "channel": "sms",
                "ticket_id": ticket.id,
                "message_id": str(message.id),
                "provider": sms_provider,
                "provider_message_id": send_result.get("message_id", ""),
                "error": send_result.get("error", ""),
            }
        except Exception as exc:
            logger.error(
                "dispatch_sms_error error=%s",
                str(exc)[:200],
                extra={"company_id": company_id, "ticket_id": ticket.id},
                exc_info=True,
            )
            message.metadata_json = json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "error",
                "error": str(exc)[:200],
            })
            self.db.commit()
            return {
                "status": "error",
                "channel": "sms",
                "ticket_id": ticket.id,
                "message_id": str(message.id),
                "error": str(exc)[:200],
            }

    def _dispatch_voice(
        self,
        company_id: str,
        ticket: Ticket,
        ai_response_text: str,
        role: str,
        model_used: Optional[str],
    ) -> dict:
        """Dispatch AI response via voice channel (BC-025: provider-agnostic).

        Uses VoiceChannelService to initiate an outbound call that reads the
        AI response aloud via TTS (Text-to-Speech). Stores the response as a
        TicketMessage for audit trail. Falls back to internal storage if voice
        is not configured for the tenant.

        Fix context: previously, voice tickets fell through to _dispatch_internal
        because there was no 'voice' branch in dispatch(). The AI response was
        stored but NO phone call was made. Now we call VoiceChannelService.
        """
        # Create TicketMessage for audit trail
        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role=role,
            channel="voice",
            content=ai_response_text[:4000],  # Voice TTS limit
            metadata_json=json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "pending",
            }),
        )
        self.db.add(message)
        self.db.commit()

        try:
            from app.services.voice_channel_service import VoiceChannelService

            service = VoiceChannelService(self.db)

            # Get customer phone from ticket metadata
            customer_phone = ""
            if ticket.metadata_json:
                try:
                    meta = json.loads(ticket.metadata_json)
                    customer_phone = (
                        meta.get("from_number")
                        or meta.get("phone")
                        or meta.get("customer_phone", "")
                    )
                except Exception:
                    pass

            if not customer_phone:
                logger.warning(
                    "dispatch_voice_no_recipient",
                    extra={"company_id": company_id, "ticket_id": ticket.id},
                )
                message.metadata_json = json.dumps({
                    "source": "ai_response",
                    "model_used": model_used,
                    "dispatch_status": "no_recipient",
                })
                self.db.commit()
                return {
                    "status": "no_recipient",
                    "channel": "voice",
                    "ticket_id": ticket.id,
                    "message_id": str(message.id),
                    "message": "No customer phone number on ticket",
                }

            # Initiate the outbound call (handles Twilio, rate limits, opt-out)
            # Truncate to ~500 chars for TTS — a 30-second call at natural pace.
            tts_message = ai_response_text[:500]
            variant_tier = "parwa"  # Default; could be read from ticket if stored
            call_result = service.initiate_outbound_call(
                company_id=company_id,
                to_number=customer_phone,
                variant_tier=variant_tier,
                message=tts_message,
                sender_role="ai_agent",
                ticket_id=ticket.id,
            )

            if call_result.get("status") == "error":
                message.metadata_json = json.dumps({
                    "source": "ai_response",
                    "model_used": model_used,
                    "dispatch_status": "failed",
                    "error": call_result.get("error", "unknown"),
                })
                self.db.commit()
                return {
                    "status": "failed",
                    "channel": "voice",
                    "ticket_id": ticket.id,
                    "message_id": str(message.id),
                    "error": call_result.get("error", "Voice call failed"),
                }

            # Success — record call SID
            message.metadata_json = json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "dispatched",
                "call_id": call_result.get("call_id", ""),
                "twilio_call_sid": call_result.get("twilio_call_sid", ""),
            })
            self.db.commit()

            logger.info(
                "dispatch_voice_call_initiated",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket.id,
                    "call_id": call_result.get("call_id"),
                },
            )
            return {
                "status": "dispatched",
                "channel": "voice",
                "ticket_id": ticket.id,
                "message_id": str(message.id),
                "call_id": call_result.get("call_id"),
                "twilio_call_sid": call_result.get("twilio_call_sid"),
            }
        except Exception as exc:
            logger.error(
                "dispatch_voice_error error=%s",
                str(exc)[:200],
                extra={"company_id": company_id, "ticket_id": ticket.id},
                exc_info=True,
            )
            message.metadata_json = json.dumps({
                "source": "ai_response",
                "model_used": model_used,
                "dispatch_status": "error",
                "error": str(exc)[:200],
            })
            self.db.commit()
            return {
                "status": "error",
                "channel": "voice",
                "ticket_id": ticket.id,
                "message_id": str(message.id),
                "error": str(exc)[:200],
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
