"""
Outbound Email Service — Week 13 Day 2 (F-120)

Handles sending AI-generated responses back to customers via email:
1. Resolve customer email from ticket
2. Build email threading headers (In-Reply-To, References)
3. Render AI response in branded template
4. Check outbound BC-006 rate limit
5. Send via Celery + Brevo
6. Track outbound email in database
7. Create TicketMessage for the AI reply

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped to company_id)
- BC-006: Email rate limiting (5 replies/thread/24h outbound)
- BC-012: Circuit breaker / structured errors
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_
from sqlalchemy.orm import Session

from database.models.email_channel import EmailThread
from database.models.tickets import Ticket, TicketMessage, Customer

logger = logging.getLogger("parwa.outbound_email")

# BC-006: Max outbound AI replies per thread per 24 hours
BC006_MAX_OUTBOUND_REPLIES_24H = 5
BC006_RATE_LIMIT_WINDOW_HOURS = 24


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
    ) -> dict:
        """Send an AI-generated email reply to the ticket customer.

        Full pipeline:
        1. Load ticket + customer + email thread
        2. Check outbound BC-006 rate limit
        3. Build threading headers (In-Reply-To, References)
        4. Render AI response in branded template
        5. Send via Celery task
        6. Create TicketMessage for the AI reply
        7. Update email thread tracking

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket to reply on.
            ai_response_html: AI-generated response as HTML.
            ai_response_text: Optional plain-text version.
            sender_name: Agent/AI name for the email footer.
            model_used: AI model used (for footer attribution).

        Returns:
            Dict with status, ticket_message_id, etc.
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
            company_id, ticket_id,
        )
        if rate_error:
            return {"status": "rate_limited", "error": rate_error}

        # Step 3: Build threading headers
        email_thread = self._get_email_thread(company_id, ticket_id)
        reply_to_msg_id = None
        references = None
        if email_thread:
            reply_to_msg_id = email_thread.latest_message_id
            references = self._build_references_chain(email_thread)

        # Step 4: Build subject line
        subject = self._build_reply_subject(ticket.subject)

        # Step 5: Render email template
        html_content = self._render_ai_response_email(
            ticket_subject=ticket.subject,
            ticket_id=ticket.id,
            customer_name=customer.name,
            ai_response_html=ai_response_html,
            agent_name=sender_name or "PARWA AI",
            model_used=model_used,
        )

        # Step 6: Send via Celery
        try:
            from app.tasks.email_tasks import send_email as send_email_task
            send_email_task.delay(
                company_id=company_id,
                to=customer.email,
                subject=subject,
                html_body=html_content,
                reply_to_message_id=reply_to_msg_id,
                references=references,
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
                sent = self._send_sync(
                    to=customer.email,
                    subject=subject,
                    html_content=html_content,
                    reply_to_message_id=reply_to_msg_id,
                    references=references,
                )
                if not sent:
                    return {"status": "error", "error": "Email send failed (sync fallback)"}
            except Exception as exc2:
                return {
                    "status": "error",
                    "error": f"Email send failed: {str(exc2)[:200]}",
                }

        # Step 7: Create TicketMessage for the AI reply
        message = TicketMessage(
            ticket_id=ticket_id,
            company_id=company_id,
            role="ai",
            channel="email",
            content=ai_response_text or self._strip_html(ai_response_html),
            metadata_json=json.dumps({
                "source": "ai_response",
                "email_reply_to": reply_to_msg_id,
                "email_references": references,
                "model_used": model_used,
                "sender_name": sender_name,
            }),
        )
        self.db.add(message)

        # Step 8: Update email thread
        if email_thread:
            email_thread.message_count = (email_thread.message_count or 1) + 1
            participants = json.loads(email_thread.participants_json or "[]")
            if customer.email and customer.email.lower() not in participants:
                participants.append(customer.email.lower())
                email_thread.participants_json = json.dumps(participants)

        # Update ticket
        if not ticket.first_response_at:
            ticket.first_response_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(message)

        # Step 9: Emit Socket.io event
        try:
            from app.core.ticket_events import emit_ticket_event
            emit_ticket_event(
                company_id=company_id,
                event_type="message_added",
                ticket_id=ticket_id,
                data={
                    "message_id": message.id,
                    "role": "ai",
                    "channel": "email",
                    "customer_email": customer.email,
                },
            )
        except Exception:
            pass  # Non-critical

        logger.info(
            "outbound_email_sent",
            extra={
                "company_id": company_id,
                "ticket_id": ticket_id,
                "customer_email": customer.email,
                "message_id": message.id,
                "reply_to": reply_to_msg_id,
            },
        )

        return {
            "status": "sent",
            "ticket_id": ticket_id,
            "ticket_message_id": message.id,
            "customer_email": customer.email,
            "reply_to_message_id": reply_to_msg_id,
        }

    # ── Private Methods ─────────────────────────────────────────

    def _get_ticket(self, company_id: str, ticket_id: str) -> Optional[Ticket]:
        """Get ticket with company isolation."""
        return (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == company_id,
            )
            .first()
        )

    def _get_customer(
        self, company_id: str, customer_id: Optional[str],
    ) -> Optional[Customer]:
        """Get customer by ID with company isolation."""
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
        self, company_id: str, ticket_id: str,
    ) -> Optional[EmailThread]:
        """Get email thread for a ticket."""
        return (
            self.db.query(EmailThread)
            .filter(
                EmailThread.company_id == company_id,
                EmailThread.ticket_id == ticket_id,
            )
            .first()
        )

    def _check_outbound_rate_limit(
        self, company_id: str, ticket_id: str,
    ) -> Optional[str]:
        """Check BC-006 outbound rate limit: max 5 AI replies/thread/24h.

        Returns:
            None if under limit, or error reason string if exceeded.
        """
        since = datetime.now(timezone.utc) - timedelta(
            hours=BC006_RATE_LIMIT_WINDOW_HOURS,
        )
        count = (
            self.db.query(TicketMessage)
            .filter(
                TicketMessage.company_id == company_id,
                TicketMessage.ticket_id == ticket_id,
                TicketMessage.role == "ai",
                TicketMessage.channel == "email",
                TicketMessage.created_at >= since,
            )
            .count()
        )
        if count >= BC006_MAX_OUTBOUND_REPLIES_24H:
            return (
                f"BC-006 outbound rate limit: {count} AI replies in last "
                f"{BC006_RATE_LIMIT_WINDOW_HOURS}h (max {BC006_MAX_OUTBOUND_REPLIES_24H})"
            )
        return None

    def _build_references_chain(
        self, email_thread: EmailThread,
    ) -> Optional[str]:
        """Build the References header from email thread.

        The References header is a space-separated list of all
        Message-IDs in the thread, ordered oldest to newest.

        Args:
            email_thread: The EmailThread record.

        Returns:
            References header string, or None.
        """
        ids = []
        if email_thread.thread_message_id:
            ids.append(email_thread.thread_message_id)
        if (
            email_thread.latest_message_id
            and email_thread.latest_message_id != email_thread.thread_message_id
        ):
            ids.append(email_thread.latest_message_id)
        if not ids:
            return None
        return " ".join(f"<{mid}>" if not mid.startswith("<") else mid for mid in ids)

    def _build_reply_subject(self, original_subject: str) -> str:
        """Build reply subject with Re: prefix.

        Handles:
        - No prefix: "Help needed" → "Re: Help needed"
        - Already has Re:: "Re: Help needed" → "Re: Help needed"
        - Multiple Re:: "Re: Re: Help needed" → "Re: Help needed"

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

    def _render_ai_response_email(
        self,
        ticket_subject: str,
        ticket_id: str,
        customer_name: Optional[str],
        ai_response_html: str,
        agent_name: str,
        model_used: Optional[str],
    ) -> str:
        """Render AI response in the branded email template.

        Args:
            ticket_subject: Original ticket subject.
            ticket_id: Ticket UUID.
            customer_name: Customer display name.
            ai_response_html: AI response as HTML.
            agent_name: Name to show in footer.
            model_used: AI model name for footer.

        Returns:
            Rendered HTML string.
        """
        try:
            from app.core.email_renderer import render_email_template
            return render_email_template(
                "ai_response_email.html",
                {
                    "ticket_subject": ticket_subject or "",
                    "ticket_id": ticket_id[:8] if ticket_id else "",
                    "customer_name": customer_name or "there",
                    "ai_response_html": ai_response_html,
                    "agent_name": agent_name,
                    "model_used": model_used,
                    "subject_prefix": "Re: ",
                },
            )
        except Exception as exc:
            # Fallback to raw AI response wrapped in basic HTML
            logger.warning(
                "outbound_email_template_failed",
                extra={"error": str(exc)[:200]},
            )
            return f"""
            <div style="font-family:sans-serif;max-width:600px;padding:20px">
                <p>Hi {customer_name or 'there'},</p>
                <div style="margin:16px 0">{ai_response_html}</div>
                <p style="font-size:12px;color:#999">
                    — {agent_name}
                    {f' ({model_used})' if model_used else ''}
                </p>
            </div>
            """

    def _send_sync(
        self,
        to: str,
        subject: str,
        html_content: str,
        reply_to_message_id: Optional[str] = None,
        references: Optional[str] = None,
    ) -> bool:
        """Synchronous fallback for email sending.

        Used when Celery dispatch fails.
        """
        from app.services.email_service import send_email
        return send_email(
            to=to,
            subject=subject,
            html_content=html_content,
            reply_to_message_id=reply_to_msg_id,
            references=references,
        )

    @staticmethod
    def _strip_html(html: str) -> str:
        """Strip HTML tags and return plain text."""
        if not html:
            return ""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text
