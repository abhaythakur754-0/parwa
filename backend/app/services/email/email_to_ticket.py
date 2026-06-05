"""
PARWA Email-to-Ticket Converter — Day 5 (Email Deep + Email MCP Server)

Converts inbound emails into helpdesk tickets or adds messages to
existing ticket threads.  Uses EmailParser for HTML parsing, thread
tracking, and attachment extraction.

Building Codes:
- BC-001: All queries scoped to company_id (multi-tenant isolation)
- BC-008: Never crash — all exceptions caught, returns error dicts
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services.email.email_parser import EmailParser
from database.models.email_channel import EmailThread
from database.models.tickets import Ticket, TicketMessage

logger = logging.getLogger("parwa.email_to_ticket")


class EmailToTicketConverter:
    """Convert inbound emails into tickets or add to existing threads.

    Orchestrates the full email-to-ticket pipeline:
    1. Parse HTML body into clean text
    2. Track / find conversation thread
    3. Create new ticket or add message to existing ticket
    4. Extract and link attachments

    All database queries are scoped by ``company_id`` (BC-001).
    All exceptions are caught and returned as error dicts (BC-008).
    """

    def __init__(self, db_session: Session) -> None:
        self.db = db_session
        self.parser = EmailParser()

    # ── Main Conversion Pipeline ─────────────────────────────────

    def convert_inbound_email(
        self,
        email_data: dict,
        company_id: str,
        db_session: Optional[Session] = None,
    ) -> dict:
        """Parse an inbound email and create or update a ticket.

        Full pipeline:
        1. Parse HTML body into clean text (via EmailParser)
        2. Strip quoted replies and detect signature
        3. Track conversation thread via In-Reply-To / References
        4. Look up existing ticket by thread_id or subject match
        5. Create new Ticket + TicketMessage if no existing ticket
        6. Add TicketMessage to existing ticket if thread match found
        7. Extract and link attachments

        Args:
            email_data: Dict with keys:
                from_email, to_email, subject, body (plain),
                html_body, message_id, in_reply_to, references,
                attachments, received_at
            company_id: Tenant company ID (BC-001).
            db_session: Optional override for the DB session.

        Returns:
            Dict with keys:
            - status: ``"ok"`` or ``"error"``
            - ticket_id: ID of the created or updated ticket
            - message_id: ID of the created TicketMessage
            - thread_id: Thread identifier for the email conversation
            - is_new_ticket: Whether a new ticket was created
            - attachments_linked: Count of attachments linked to ticket
            - error: Error message if status is ``"error"``
        """
        db = db_session or self.db

        try:
            # Step 1: Parse HTML body
            body_text = email_data.get("body", "")
            html_body = email_data.get("html_body", "")

            parsed_html: dict = {}
            if html_body:
                parsed_html = self.parser.parse_html_email(html_body)
                if parsed_html.get("status") == "ok" and parsed_html.get("text"):
                    # Prefer parsed HTML if it yields content
                    body_text = parsed_html["text"]

            # Step 2: Strip quoted replies and detect signature
            clean_body = self.parser.strip_quoted_reply(body_text)
            body_content, _signature = self.parser.detect_email_signature(clean_body)

            # Fall back to full clean body if signature detection
            # removes too much (body would be empty)
            if not body_content.strip():
                body_content = clean_body

            # Step 3: Track conversation thread
            message_id = email_data.get("message_id", "")
            in_reply_to = email_data.get("in_reply_to")
            references = email_data.get("references")

            thread_result = self.parser.track_thread(
                message_id=message_id,
                in_reply_to=in_reply_to,
                references=references,
                company_id=company_id,
            )

            if thread_result.get("status") == "error":
                logger.warning(
                    "email_thread_tracking_failed",
                    extra={
                        "company_id": company_id,
                        "message_id": message_id,
                        "error": thread_result.get("error"),
                    },
                )
                # Continue with new thread instead of failing
                thread_result = {
                    "status": "ok",
                    "thread_id": str(uuid.uuid4()),
                    "message_ids": [message_id],
                    "is_new_thread": True,
                }

            thread_id = thread_result["thread_id"]

            # Step 4: Look up existing ticket by thread or subject
            existing_ticket: Optional[Ticket] = None
            email_thread: Optional[EmailThread] = None

            if in_reply_to or references:
                email_thread = self._find_email_thread(
                    company_id=company_id,
                    db=db,
                    in_reply_to=in_reply_to,
                    references=references,
                )
                if email_thread:
                    existing_ticket = (
                        db.query(Ticket)
                        .filter(
                            Ticket.id == email_thread.ticket_id,
                            Ticket.company_id == company_id,
                        )
                        .first()
                    )

            # Fallback: try subject match for emails without thread headers
            if not existing_ticket:
                existing_ticket = self._find_ticket_by_subject(
                    company_id=company_id,
                    db=db,
                    subject=email_data.get("subject", ""),
                )

            # Step 5/6: Create or update ticket
            if existing_ticket:
                result = self._add_message_to_ticket(
                    company_id=company_id,
                    db=db,
                    ticket=existing_ticket,
                    email_data=email_data,
                    body_content=body_content,
                    email_thread=email_thread,
                    thread_id=thread_id,
                )
            else:
                result = self._create_new_ticket(
                    company_id=company_id,
                    db=db,
                    email_data=email_data,
                    body_content=body_content,
                    thread_id=thread_id,
                )

            # Step 7: Extract and link attachments
            attachments_linked = 0
            raw_attachments = email_data.get("attachments", [])
            if raw_attachments:
                att_result = self.parser.extract_attachments(
                    email_data=email_data,
                    company_id=company_id,
                )
                if att_result.get("status") == "ok":
                    attachments_linked = len(att_result.get("attachments", []))
                    # Store attachment metadata in ticket metadata
                    self._link_attachments_to_ticket(
                        company_id=company_id,
                        db=db,
                        ticket_id=result.get("ticket_id"),
                        attachments=att_result.get("attachments", []),
                    )

            return {
                "status": "ok",
                "ticket_id": result.get("ticket_id"),
                "message_id": result.get("message_id"),
                "thread_id": thread_id,
                "is_new_ticket": result.get("is_new_ticket", False),
                "attachments_linked": attachments_linked,
            }

        except Exception as exc:
            logger.error(
                "email_to_ticket_conversion_failed",
                extra={
                    "company_id": company_id,
                    "message_id": email_data.get("message_id", ""),
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "ticket_id": None,
                "message_id": None,
                "thread_id": None,
                "is_new_ticket": False,
                "attachments_linked": 0,
                "error": str(exc)[:500],
            }

    # ── Private: Ticket Creation ─────────────────────────────────

    def _create_new_ticket(
        self,
        company_id: str,
        db: Session,
        email_data: dict,
        body_content: str,
        thread_id: str,
    ) -> dict:
        """Create a new Ticket and TicketMessage from an inbound email.

        Also creates an EmailThread record to link future replies.

        Args:
            company_id: Tenant company ID (BC-001).
            db: SQLAlchemy session.
            email_data: Inbound email data dict.
            body_content: Cleaned body text.
            thread_id: Thread identifier.

        Returns:
            Dict with ticket_id, message_id, is_new_ticket=True.
        """
        # Find or create customer
        customer_id = self._find_or_create_customer(
            company_id=company_id,
            db=db,
            email_data=email_data,
        )

        subject = (email_data.get("subject") or "(No Subject)")[:255]

        # Create ticket
        ticket = Ticket(
            company_id=company_id,
            customer_id=customer_id,
            channel="email",
            subject=subject,
            status="open",
            metadata_json=json.dumps({
                "email_message_id": email_data.get("message_id", ""),
                "email_from": email_data.get("from_email", ""),
                "email_to": email_data.get("to_email", ""),
                "email_received_at": email_data.get("received_at", ""),
                "thread_id": thread_id,
                "source": "inbound_email",
            }),
        )
        db.add(ticket)
        db.flush()  # Get ticket.id

        # Create first ticket message
        msg = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role="customer",
            content=body_content or email_data.get("body", ""),
            channel="email",
            metadata_json=json.dumps({
                "email_message_id": email_data.get("message_id", ""),
                "email_in_reply_to": email_data.get("in_reply_to", ""),
                "email_from": email_data.get("from_email", ""),
                "email_sender_name": email_data.get("sender_name", ""),
                "attachments": email_data.get("attachments", []),
            }),
        )
        db.add(msg)

        # Create EmailThread record for future reply matching
        email_thread = EmailThread(
            company_id=company_id,
            ticket_id=ticket.id,
            thread_message_id=email_data.get("message_id", ""),
            latest_message_id=email_data.get("message_id", ""),
            message_count=1,
            participants_json=json.dumps(
                [email_data.get("from_email", "").lower().strip()]
            ),
        )
        db.add(email_thread)

        db.commit()
        db.refresh(ticket)
        db.refresh(msg)

        logger.info(
            "email_created_new_ticket",
            extra={
                "company_id": company_id,
                "ticket_id": ticket.id,
                "thread_id": thread_id,
                "subject": subject[:80],
            },
        )

        return {
            "ticket_id": ticket.id,
            "message_id": msg.id,
            "is_new_ticket": True,
        }

    def _add_message_to_ticket(
        self,
        company_id: str,
        db: Session,
        ticket: Ticket,
        email_data: dict,
        body_content: str,
        email_thread: Optional[EmailThread],
        thread_id: str,
    ) -> dict:
        """Add a new message to an existing ticket.

        Updates the EmailThread record with the new message.

        Args:
            company_id: Tenant company ID (BC-001).
            db: SQLAlchemy session.
            ticket: Existing Ticket ORM object.
            email_data: Inbound email data dict.
            body_content: Cleaned body text.
            email_thread: Optional EmailThread ORM object.
            thread_id: Thread identifier.

        Returns:
            Dict with ticket_id, message_id, is_new_ticket=False.
        """
        # Create ticket message
        msg = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role="customer",
            content=body_content or email_data.get("body", ""),
            channel="email",
            metadata_json=json.dumps({
                "email_message_id": email_data.get("message_id", ""),
                "email_in_reply_to": email_data.get("in_reply_to", ""),
                "email_from": email_data.get("from_email", ""),
                "email_sender_name": email_data.get("sender_name", ""),
                "attachments": email_data.get("attachments", []),
            }),
        )
        db.add(msg)

        # Update email thread
        if email_thread:
            email_thread.latest_message_id = email_data.get("message_id", "")
            email_thread.message_count = (email_thread.message_count or 1) + 1

            # Update participants
            participants: list[str] = []
            try:
                participants = json.loads(email_thread.participants_json or "[]")
            except (json.JSONDecodeError, TypeError):
                participants = []

            sender_email = email_data.get("from_email", "").lower().strip()
            if sender_email and sender_email not in participants:
                participants.append(sender_email)
                email_thread.participants_json = json.dumps(participants)
        else:
            # Create EmailThread if it doesn't exist yet
            new_thread = EmailThread(
                company_id=company_id,
                ticket_id=ticket.id,
                thread_message_id=email_data.get("message_id", ""),
                latest_message_id=email_data.get("message_id", ""),
                message_count=1,
                participants_json=json.dumps(
                    [email_data.get("from_email", "").lower().strip()]
                ),
            )
            db.add(new_thread)

        db.commit()
        db.refresh(msg)

        logger.info(
            "email_added_to_existing_ticket",
            extra={
                "company_id": company_id,
                "ticket_id": ticket.id,
                "thread_id": thread_id,
            },
        )

        return {
            "ticket_id": ticket.id,
            "message_id": msg.id,
            "is_new_ticket": False,
        }

    # ── Private: Lookup Helpers ──────────────────────────────────

    @staticmethod
    def _find_email_thread(
        company_id: str,
        db: Session,
        in_reply_to: Optional[str],
        references: Optional[str],
    ) -> Optional[EmailThread]:
        """Find an existing EmailThread by In-Reply-To or References.

        Search order:
        1. Match thread_message_id or latest_message_id against
           in_reply_to (most specific)
        2. Parse references header into Message-ID list, search for
           any matching thread_message_id

        All queries scoped to company_id (BC-001).

        Args:
            company_id: Tenant company ID.
            db: SQLAlchemy session.
            in_reply_to: The In-Reply-To header value.
            references: The References header (space-separated Message-IDs).

        Returns:
            EmailThread if found, None otherwise.
        """
        if not in_reply_to and not references:
            return None

        # Search 1: Direct match by in_reply_to
        if in_reply_to:
            clean_irt = in_reply_to.strip().strip("<>")
            thread = (
                db.query(EmailThread)
                .filter(
                    EmailThread.company_id == company_id,
                    or_(
                        EmailThread.thread_message_id == clean_irt,
                        EmailThread.latest_message_id == clean_irt,
                    ),
                )
                .first()
            )
            if thread:
                return thread

        # Search 2: Match any Message-ID from references chain
        if references:
            ref_ids = re.findall(r"<([^>]+)>", references)
            if not ref_ids:
                ref_ids = [r.strip() for r in references.split() if r.strip()]

            for ref_id in ref_ids:
                ref_id = ref_id.strip().strip("<>")
                if not ref_id:
                    continue
                thread = (
                    db.query(EmailThread)
                    .filter(
                        EmailThread.company_id == company_id,
                        or_(
                            EmailThread.thread_message_id == ref_id,
                            EmailThread.latest_message_id == ref_id,
                        ),
                    )
                    .first()
                )
                if thread:
                    return thread

        return None

    @staticmethod
    def _find_ticket_by_subject(
        company_id: str,
        db: Session,
        subject: str,
    ) -> Optional[Ticket]:
        """Find an existing ticket by subject match within the same tenant.

        Strips common prefixes (Re:, Fwd:) and searches for an
        open/assigned/in_progress ticket with the same subject.

        BC-001: Scoped to company_id.

        Args:
            company_id: Tenant company ID.
            db: SQLAlchemy session.
            subject: Email subject line.

        Returns:
            Ticket if found, None otherwise.
        """
        if not subject:
            return None

        # Strip Re:/Fwd: prefixes for matching
        clean_subject = re.sub(
            r"^(Re|Fwd|FW)\s*:\s*", "", subject.strip()
        ).strip()

        if not clean_subject:
            return None

        # Look for an open-ish ticket with a matching subject
        return (
            db.query(Ticket)
            .filter(
                Ticket.company_id == company_id,
                Ticket.channel == "email",
                Ticket.status.in_(["open", "assigned", "in_progress", "awaiting_client"]),
                or_(
                    Ticket.subject == clean_subject,
                    Ticket.subject == subject,
                ),
            )
            .order_by(Ticket.created_at.desc())
            .first()
        )

    @staticmethod
    def _find_or_create_customer(
        company_id: str,
        db: Session,
        email_data: dict,
    ) -> Optional[str]:
        """Find or create a Customer from the email sender.

        Uses simple email lookup within the tenant scope (BC-001).

        Args:
            company_id: Tenant company ID.
            db: SQLAlchemy session.
            email_data: Email data with from_email.

        Returns:
            Customer ID if found/created, None otherwise.
        """
        sender_email = email_data.get("from_email", "").strip().lower()
        if not sender_email:
            return None

        try:
            from database.models.tickets import Customer

            # Find existing customer
            customer = (
                db.query(Customer)
                .filter(
                    Customer.company_id == company_id,
                    Customer.email == sender_email,
                )
                .first()
            )
            if customer:
                return customer.id

            # Create new customer
            name = email_data.get("sender_name", "") or sender_email.split("@")[0]
            new_customer = Customer(
                company_id=company_id,
                email=sender_email,
                name=name,
            )
            db.add(new_customer)
            db.flush()

            return new_customer.id

        except Exception as exc:
            logger.warning(
                "email_customer_lookup_failed",
                extra={
                    "company_id": company_id,
                    "sender_email": sender_email,
                    "error": str(exc)[:200],
                },
            )
            return None

    @staticmethod
    def _link_attachments_to_ticket(
        company_id: str,
        db: Session,
        ticket_id: Optional[str],
        attachments: list[dict],
    ) -> None:
        """Link extracted attachments to a ticket via TicketAttachment.

        Stores attachment metadata in the ticket's metadata_json for
        quick reference.  BC-001: scoped to company_id.

        Args:
            company_id: Tenant company ID.
            db: SQLAlchemy session.
            ticket_id: Ticket to link attachments to.
            attachments: List of attachment dicts from EmailParser.
        """
        if not ticket_id or not attachments:
            return

        try:
            ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == company_id,
                )
                .first()
            )
            if not ticket:
                return

            # Append attachment info to ticket metadata
            try:
                metadata = json.loads(ticket.metadata_json or "{}")
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            existing_attachments = metadata.get("attachments", [])
            for att in attachments:
                existing_attachments.append({
                    "filename": att.get("filename", ""),
                    "content_type": att.get("content_type", ""),
                    "size": att.get("size", 0),
                    "storage_path": att.get("storage_path", ""),
                })

            metadata["attachments"] = existing_attachments
            ticket.metadata_json = json.dumps(metadata)
            db.commit()

        except Exception as exc:
            logger.warning(
                "email_link_attachments_failed",
                extra={
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "error": str(exc)[:200],
                },
            )

