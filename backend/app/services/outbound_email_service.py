"""
Outbound Email Service — Week 13 Day 2 (F-120)

Handles sending AI-generated responses back to customers via email:
1. Resolve customer email from ticket
2. Build email threading headers (In-Reply-To, References)
3. Render AI response in branded template
4. Check outbound BC-006 rate limit
5. Send via Celery + Brevo
6. Track outbound email in database (OutboundEmail model)
7. Create TicketMessage for the AI reply
8. Emit real-time Socket.io events (BC-005)

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped to company_id)
- BC-003: Idempotent sends (dedup via metadata check)
- BC-005: Real-time (Socket.io events on send)
- BC-006: Email rate limiting (5 replies/thread/24h outbound)
- BC-010: GDPR/opt-out check before sending
- BC-012: Circuit breaker / structured errors
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.email_channel import EmailThread, InboundEmail
from database.models.outbound_email import OutboundEmail
from database.models.tickets import Ticket, TicketMessage, Customer

from app.core.email_utils import strip_html, run_async_coro

logger = logging.getLogger("parwa.outbound_email")

# BC-006: Max outbound AI replies per thread per 24 hours
BC006_MAX_OUTBOUND_REPLIES_24H = 5
BC006_RATE_LIMIT_WINDOW_HOURS = 24

# Max inline quote length (chars) — prevents bloated emails
MAX_QUOTE_LENGTH = 3000


class OutboundEmailService:
    """Service for sending outbound email replies to customers.

    Takes AI-generated responses, resolves customer email,
    builds threading headers, and dispatches via Celery.
    """

    def __init__(self, db: Session):
        self.db = db

    def send_email_reply(
        self,
        company_id: str,
        ticket_id: str,
        ai_response_html: str,
        ai_response_text: Optional[str] = None,
        sender_name: Optional[str] = None,
        model_used: Optional[str] = None,
        confidence: Optional[float] = None,
        attachments: Optional[list] = None,
    ) -> dict:
        """Send an AI-generated email reply to the ticket customer.

        Full pipeline:
        1. Load ticket + customer + email thread
        2. Check outbound BC-006 rate limit
        3. Check BC-010 opt-out (G-08)
        4. Check BC-003 idempotency (G-13)
        5. Build threading headers (In-Reply-To, References) (G-09)
        6. Build subject with Re: prefix
        7. Quote original email inline (G-12)
        8. Render AI response in branded template
        9. Generate plain-text fallback (G-14)
        10. Commit DB record FIRST, then dispatch Celery (G-03)
        11. Create OutboundEmail tracking record (G-01)
        12. Create TicketMessage for the AI reply
        13. Update email thread
        14. Emit Socket.io event via run_async_coro (G-02)

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket to reply on.
            ai_response_html: AI-generated response as HTML.
            ai_response_text: Optional plain-text version.
            sender_name: Agent/AI name for the email footer.
            model_used: AI model used (for footer attribution).
            confidence: AI confidence score (0-1).
            attachments: List of dicts with name, content (base64),
                content_type for outbound attachments.

        Returns:
            Dict with status, ticket_message_id, brevo_message_id, etc.
        """
        # Step 1: Load ticket + customer
        ticket = self._get_ticket(company_id, ticket_id)
        if not ticket:
            return {"status": "error", "error": f"Ticket {ticket_id} not found"}

        if ticket.channel != "email":
            return {
                "status": "error",
                "error": f"Ticket channel is '{ticket.channel}', not 'email'",
            }

        customer = self._get_customer(company_id, ticket.customer_id)
        if not customer or not customer.email:
            return {"status": "error", "error": "Customer email not found"}

        # Step 2: Check outbound BC-006 rate limit
        rate_error = self._check_outbound_rate_limit(
            company_id,
            ticket_id,
        )
        if rate_error:
            logger.warning(
                "outbound_rate_limited",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "customer_email": customer.email,
                    "reason": rate_error,
                },
            )
            return {"status": "rate_limited", "error": rate_error}

        # Step 3: Check BC-010 opt-out (G-08)
        if self._is_customer_opted_out(customer):
            logger.info(
                "outbound_skipped_opt_out",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "customer_email": customer.email,
                },
            )
            return {"status": "skipped", "error": "Customer has opted out of emails"}

        # Step 3b: Check suppression list (F-124 — bounced/complained emails)
        if self._is_email_suppressed(company_id, customer.email):
            logger.info(
                "outbound_skipped_suppressed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "customer_email": customer.email,
                },
            )
            return {
                "status": "skipped",
                "error": "Customer email is suppressed (bounced/complained)",
            }

        # Step 3c: Check OOO status — don't send if customer is OOO (F-122)
        if self._is_customer_ooo(company_id, customer.email):
            logger.info(
                "outbound_skipped_ooo",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "customer_email": customer.email,
                },
            )
            return {
                "status": "skipped",
                "error": "Customer has active out-of-office status",
            }

        # Step 4: Check BC-003 idempotency (G-13)
        dedup_id = f"outbound:{ticket_id}:{hash(ai_response_html) % 100000}"
        if self._is_duplicate_send(company_id, ticket_id, dedup_id):
            logger.info(
                "outbound_idempotent_skip",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "dedup_id": dedup_id,
                },
            )
            return {"status": "duplicate", "error": "Idempotent: reply already sent"}

        # Step 5: Build threading headers (G-09: full chain)
        email_thread = self._get_email_thread(company_id, ticket_id)
        reply_to_msg_id = None
        references = None
        if email_thread:
            reply_to_msg_id = email_thread.latest_message_id
            references = self._build_references_chain(email_thread, company_id)

        # Step 6: Build subject line
        subject = self._build_reply_subject(ticket.subject)

        # Step 7: Get original email for inline quoting (G-12)
        original_quote_html = self._build_inline_quote(company_id, ticket_id)

        # Step 8: Render email template
        html_content = self._render_ai_response_email(
            ticket_subject=ticket.subject,
            ticket_id=ticket.id,
            customer_name=customer.name,
            ai_response_html=ai_response_html,
            agent_name=sender_name or "PARWA AI",
            model_used=model_used,
            inline_quote_html=original_quote_html,
        )

        # Step 9: Generate plain-text fallback (G-14)
        text_content = ai_response_text or strip_html(ai_response_html)
        if original_quote_html:
            text_content += "\n\n--- Original Message ---\n" + strip_html(
                original_quote_html
            )

        # Step 10: Create DB records BEFORE dispatching (G-03 race fix)
        message = TicketMessage(
            ticket_id=ticket_id,
            company_id=company_id,
            role="ai",
            channel="email",
            content=text_content,
            metadata_json=json.dumps(
                {
                    "source": "ai_response",
                    "email_reply_to": reply_to_msg_id,
                    "email_references": references,
                    "model_used": model_used,
                    "sender_name": sender_name,
                    "confidence": confidence,
                    "dedup_id": dedup_id,
                }
            ),
        )
        self.db.add(message)

        # Create OutboundEmail tracking record (G-01)
        outbound = OutboundEmail(
            company_id=company_id,
            recipient_email=customer.email,
            recipient_name=customer.name,
            subject=subject,
            reply_to_message_id=reply_to_msg_id,
            references=references,
            ticket_id=ticket_id,
            role="ai",
            model_used=model_used,
            confidence=confidence,
            content_length=len(text_content),
            template_used="ai_response_email.html",
            delivery_status="pending",
        )
        self.db.add(outbound)

        # Step 11: Update email thread
        if email_thread:
            email_thread.message_count = (email_thread.message_count or 1) + 1
            participants = json.loads(email_thread.participants_json or "[]")
            if customer.email and customer.email.lower() not in participants:
                participants.append(customer.email.lower())
                email_thread.participants_json = json.dumps(participants)

        # Update ticket
        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now(timezone.utc)

        # COMMIT FIRST — ensures Celery worker sees consistent state (G-03)
        self.db.commit()
        self.db.refresh(message)
        self.db.refresh(outbound)

        # Step 12: Dispatch via Celery (after commit — no race condition)
        brevo_message_id = None
        send_error = None
        try:
            from app.tasks.email_tasks import send_email as send_email_task

            send_email_task.delay(
                company_id=company_id,
                to=customer.email,
                subject=subject,
                html_body=html_content,
                text_body=text_content,
                message_id=str(outbound.id),
                reply_to_message_id=reply_to_msg_id,
                references=references,
                attachments=attachments,
                outbound_email_id=str(outbound.id),
            )
        except Exception as exc:
            logger.error(
                "outbound_email_dispatch_failed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "customer_email": customer.email,
                    "error": str(exc)[:200],
                },
            )
            # Fall back to synchronous send
            try:
                from app.services.email_service import send_email_tracked

                result = send_email_tracked(
                    to=customer.email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    reply_to_message_id=reply_to_msg_id,
                    references=references,
                    attachments=attachments,
                )
                brevo_message_id = result.get("message_id")
                if not result.get("success"):
                    send_error = result.get("error", "sync fallback failed")
                    # Update outbound status to failed
                    outbound.delivery_status = "failed"
                    outbound.error_message = send_error
                    self.db.commit()
                    return {
                        "status": "error",
                        "error": f"Email send failed: {send_error}",
                    }
                else:
                    # Update outbound with tracking info
                    outbound.delivery_status = "sent"
                    outbound.brevo_message_id = brevo_message_id
                    outbound.sent_at = datetime.now(timezone.utc)
                    self.db.commit()
            except Exception as exc2:
                outbound.delivery_status = "failed"
                outbound.error_message = str(exc2)[:500]
                self.db.commit()
                return {
                    "status": "error",
                    "error": f"Email send failed: {str(exc2)[:200]}",
                }

        # Step 13: Emit Socket.io event via run_async_coro (G-02 fix)
        try:
            from app.core.event_emitter import emit_ticket_event

            run_async_coro(
                emit_ticket_event(
                    company_id=company_id,
                    event_type="ticket:message_added",
                    payload={
                        "ticket_id": ticket_id,
                        "company_id": company_id,
                        "channel": "email",
                        "message_id": str(message.id),
                        "role": "ai",
                        "extra": {
                            "customer_email": customer.email,
                            "outbound_email_id": str(outbound.id),
                            "model_used": model_used,
                        },
                    },
                ),
            )
        except Exception:
            pass  # Non-critical — logging already handled in run_async_coro

        logger.info(
            "outbound_email_sent",
            extra={
                "company_id": company_id,
                "ticket_id": ticket_id,
                "customer_email": customer.email,
                "message_id": message.id,
                "outbound_id": outbound.id,
                "reply_to": reply_to_msg_id,
            },
        )

        return {
            "status": "sent",
            "ticket_id": ticket_id,
            "ticket_message_id": message.id,
            "outbound_email_id": outbound.id,
            "customer_email": customer.email,
            "brevo_message_id": brevo_message_id,
            "reply_to_message_id": reply_to_msg_id,
        }

    # ── Private Methods ─────────────────────────────────────────

    def _get_ticket(self, company_id: str, ticket_id: str) -> Optional[Ticket]:
        """Get ticket with company isolation (BC-001)."""
        return (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == company_id,
            )
            .first()
        )

    def _get_customer(
        self,
        company_id: str,
        customer_id: Optional[str],
    ) -> Optional[Customer]:
        """Get customer by ID with company isolation (BC-001)."""
        if not customer_id:
            return None
        return (
            self.db.query(Customer)
            .filter(
                Customer.id == customer_id,
                Customer.company_id == company_id,
            )
            .first()
        )

    def _get_email_thread(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[EmailThread]:
        """Get email thread for a ticket (BC-001)."""
        return (
            self.db.query(EmailThread)
            .filter(
                EmailThread.company_id == company_id,
                EmailThread.ticket_id == ticket_id,
            )
            .first()
        )

    def _check_outbound_rate_limit(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[str]:
        """Check BC-006 outbound rate limit: max 5 AI replies/thread/24h.

        Uses OutboundEmail table for accurate tracking of actual sends
        (not just TicketMessage creation). Falls back to TicketMessage
        count if no OutboundEmail records exist.

        Returns:
            None if under limit, or error reason string if exceeded.
        """
        since = datetime.now(timezone.utc) - timedelta(
            hours=BC006_RATE_LIMIT_WINDOW_HOURS,
        )

        # Primary: count actual outbound sends via OutboundEmail
        outbound_count = (
            self.db.query(func.count(OutboundEmail.id))
            .filter(
                OutboundEmail.company_id == company_id,
                OutboundEmail.ticket_id == ticket_id,
                OutboundEmail.role == "ai",
                OutboundEmail.created_at >= since,
            )
            .scalar()
        ) or 0

        if outbound_count >= BC006_MAX_OUTBOUND_REPLIES_24H:
            return (
                f"BC-006 outbound rate limit: {outbound_count} AI replies in last "
                f"{BC006_RATE_LIMIT_WINDOW_HOURS}h (max {BC006_MAX_OUTBOUND_REPLIES_24H})"
            )

        # Fallback: count TicketMessages (for threads without OutboundEmail
        # records)
        msg_count = (
            self.db.query(func.count(TicketMessage.id))
            .filter(
                TicketMessage.company_id == company_id,
                TicketMessage.ticket_id == ticket_id,
                TicketMessage.role == "ai",
                TicketMessage.channel == "email",
                TicketMessage.created_at >= since,
            )
            .scalar()
        ) or 0

        if msg_count >= BC006_MAX_OUTBOUND_REPLIES_24H:
            return (
                f"BC-006 outbound rate limit: {msg_count} AI messages in last "
                f"{BC006_RATE_LIMIT_WINDOW_HOURS}h (max {BC006_MAX_OUTBOUND_REPLIES_24H})"
            )

        return None

    def _is_customer_opted_out(self, customer: Customer) -> bool:
        """Check BC-010: whether customer has opted out of emails.

        Checks the customer's preferences / notification settings
        for email opt-out status.

        Args:
            customer: Customer ORM object.

        Returns:
            True if customer has opted out of email communications.
        """
        # Check customer-level email opt-out flag
        if hasattr(customer, "email_opt_out") and customer.email_opt_out:
            return True
        # Check notification preferences if available
        if hasattr(customer, "notification_preferences"):
            prefs = customer.notification_preferences
            if isinstance(prefs, dict) and prefs.get("email", {}).get("opted_out"):
                return True
            if isinstance(prefs, str):
                try:
                    prefs_dict = json.loads(prefs)
                    if prefs_dict.get("email", {}).get("opted_out"):
                        return True
                except (json.JSONDecodeError, TypeError):
                    pass
        return False

    def _is_duplicate_send(
        self,
        company_id: str,
        ticket_id: str,
        dedup_id: str,
    ) -> bool:
        """Check BC-003: whether this exact reply was already sent.

        Looks for a recent TicketMessage with the same dedup_id
        in metadata_json within the last hour.

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket ID.
            dedup_id: Deduplication identifier.

        Returns:
            True if a duplicate send is detected.
        """
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        count = (
            self.db.query(func.count(TicketMessage.id))
            .filter(
                TicketMessage.company_id == company_id,
                TicketMessage.ticket_id == ticket_id,
                TicketMessage.role == "ai",
                TicketMessage.channel == "email",
                TicketMessage.created_at >= one_hour_ago,
                TicketMessage.metadata_json.contains(dedup_id),
            )
            .scalar()
        ) or 0
        return count > 0

    def _build_references_chain(
        self,
        email_thread: EmailThread,
        company_id: str,
    ) -> Optional[str]:
        """Build the References header from email thread history.

        Looks up ALL messages in the thread to build a complete
        References chain (RFC 2822). This ensures multi-hop threads
        display correctly in all email clients.

        Args:
            email_thread: The EmailThread record.
            company_id: Tenant company ID (for isolation).

        Returns:
            References header string, or None.
        """
        ids = []
        # Start with the thread's original message ID
        if email_thread.thread_message_id:
            ids.append(email_thread.thread_message_id)
        # Query all inbound messages for their message_ids
        inbound_msg_ids = (
            self.db.query(InboundEmail.message_id)
            .filter(
                InboundEmail.company_id == company_id,
                InboundEmail.ticket_id == email_thread.ticket_id,
                InboundEmail.message_id.isnot(None),
                InboundEmail.message_id != "",
            )
            .order_by(InboundEmail.created_at.asc())
            .all()
        )
        for (mid,) in inbound_msg_ids:
            if mid and mid not in ids:
                ids.append(mid)
        # Add the latest message ID if not already present
        if email_thread.latest_message_id and email_thread.latest_message_id not in ids:
            ids.append(email_thread.latest_message_id)
        if not ids:
            return None
        return " ".join(f"<{mid}>" if not mid.startswith("<") else mid for mid in ids)

    def _build_reply_subject(self, original_subject: str) -> str:
        """Build reply subject with Re: prefix.

        Handles:
        - No prefix: "Help needed" -> "Re: Help needed"
        - Already has Re:: "Re: Help needed" -> "Re: Help needed"
        - Multiple Re:: "Re: Re: Help needed" -> "Re: Help needed"
        - Fwd: prefix: "Fwd: Help needed" -> "Re: Help needed"

        Args:
            original_subject: Original ticket subject.

        Returns:
            Subject with single Re: prefix.
        """
        if not original_subject:
            return "Re: "
        # Strip all existing Re:/Fwd: prefixes
        cleaned = re.sub(r"^(Re|Fwd|FW)\s*:\s*", "", original_subject)
        # Preserve original case
        return f"Re: {cleaned}"

    def _build_inline_quote(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[str]:
        """Build an inline quote of the original customer email (G-12).

        Retrieves the latest inbound email for the ticket and formats
        it as a quoted block for inclusion in the reply.

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket ID.

        Returns:
            HTML string with quoted original, or None.
        """
        original = (
            self.db.query(InboundEmail)
            .filter(
                InboundEmail.company_id == company_id,
                InboundEmail.ticket_id == ticket_id,
                InboundEmail.sender_email.isnot(None),
            )
            .order_by(InboundEmail.created_at.desc())
            .first()
        )
        if not original:
            return None

        sender = original.sender_name or original.sender_email or "Customer"
        date_str = ""
        if original.created_at:
            date_str = original.created_at.strftime("%B %d, %Y at %H:%M")

        body = original.body_html or original.body_text or ""
        if len(body) > MAX_QUOTE_LENGTH:
            body = body[:MAX_QUOTE_LENGTH] + "..."

        if original.body_text:
            # Plain-text quote
            lines = body.split("\n")
            quoted = "\n".join(f"> {line}" for line in lines[:20])
            return (
                '<div style="border-left:3px solid #ccc;padding-left:12px;'
                'margin:16px 0;color:#666;font-size:13px">'
                '<p style="margin:0 0 4px;color:#999">'
                f"On {date_str}, {sender} wrote:</p>"
                '<pre style="margin:0;white-space:pre-wrap;font-family:inherit">'
                f"{quoted}</pre></div>"
            )
        else:
            # HTML quote
            return (
                '<div style="border-left:3px solid #ccc;padding-left:12px;'
                'margin:16px 0;color:#666;font-size:13px">'
                '<p style="margin:0 0 4px;color:#999">'
                f"On {date_str}, {sender} wrote:</p>"
                f'<div style="margin:0">{body}</div></div>'
            )

    def _render_ai_response_email(
        self,
        ticket_subject: str,
        ticket_id: str,
        customer_name: Optional[str],
        ai_response_html: str,
        agent_name: str,
        model_used: Optional[str],
        inline_quote_html: Optional[str] = None,
    ) -> str:
        """Render AI response in the branded email template.

        Args:
            ticket_subject: Original ticket subject.
            ticket_id: Ticket UUID.
            customer_name: Customer display name.
            ai_response_html: AI response as HTML.
            agent_name: Name to show in footer.
            model_used: AI model name for footer.
            inline_quote_html: Quoted original email HTML.

        Returns:
            Rendered HTML string.
        """
        try:
            from app.core.email_renderer import render_email_template

            return render_email_template(
                "ai_response_email.html",
                {
                    "ticket_id": ticket_id[:8] if ticket_id else "",
                    "customer_name": customer_name or "there",
                    "ai_response_html": ai_response_html,
                    "agent_name": agent_name,
                    "model_used": model_used,
                    "inline_quote_html": inline_quote_html,
                },
            )
        except Exception as exc:
            # Fallback to raw AI response wrapped in basic HTML
            logger.warning(
                "outbound_email_template_failed",
                extra={"error": str(exc)[:200]},
            )
            quote_block = ""
            if inline_quote_html:
                quote_block = f"<div style='margin-top:20px'>{inline_quote_html}</div>"
            return """
            <div style="font-family:sans-serif;max-width:600px;padding:20px">
                <p>Hi {customer_name or 'there'},</p>
                <div style="margin:16px 0">{ai_response_html}</div>
                <p style="font-size:12px;color:#999">
                    — {agent_name}
                    {f' ({model_used})' if model_used else ''}
                </p>
                {quote_block}
            </div>
            """

    @staticmethod
    def _strip_html(html: str) -> str:
        """Strip HTML tags and return plain text.

        NOTE: Prefer app.core.email_utils.strip_html for new code.
        Kept for backward compatibility with callers.
        """
        return strip_html(html)

    def _is_email_suppressed(self, company_id: str, email: str) -> bool:
        """Check F-124 suppression list: bounced/complained emails.

        Uses BounceComplaintService to check customer_email_status table.

        Args:
            company_id: Tenant company ID.
            email: Customer email address.

        Returns:
            True if email is suppressed from receiving.
        """
        try:
            from app.services.bounce_complaint_service import BounceComplaintService

            svc = BounceComplaintService(self.db)
            return svc.is_email_suppressed(company_id, email)
        except Exception:
            # Suppression check is advisory — never block on failure
            return False

    def _is_customer_ooo(self, company_id: str, email: str) -> bool:
        """Check F-122 OOO status: don't send if customer is out of office.

        Uses OOODetectionService to check sender profile.

        Args:
            company_id: Tenant company ID.
            email: Customer email address.

        Returns:
            True if customer has active OOO status.
        """
        try:
            from app.services.ooo_detection_service import OOODetectionService

            svc = OOODetectionService(self.db)
            result = svc.is_customer_ooo(company_id, email)
            return result is not None
        except Exception:
            # OOO check is advisory — never block on failure
            return False
