"""
Email Channel Service: Inbound email processing pipeline.

Week 13 Day 1 (F-121: Email Inbound).

Handles the complete inbound email lifecycle:
1. Store raw email in inbound_emails table (audit trail)
2. Detect email loops (BC-003)
3. Detect auto-replies / OOO
4. Find or create customer via identity resolution
5. Find existing email thread via In-Reply-To/References
6. Create new ticket or add message to existing thread
7. Track email thread state

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped to company_id)
- BC-003: Idempotent webhook processing (same Message-ID → skip)
- BC-006: Email communication
- BC-010: Data lifecycle (raw emails retained for audit)
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.schemas.email_channel import AutoReplyDetection, EmailLoopDetection
from database.models.email_channel import EmailThread, InboundEmail
from database.models.tickets import Ticket, TicketMessage

logger = logging.getLogger("parwa.email_channel")

# ── Loop Detection Constants ────────────────────────────────────

# Maximum allowed In-Reply-To chain depth to prevent infinite loops
MAX_REPLY_DEPTH = 20

# BC-006: Maximum email replies per thread per 24 hours
BC006_MAX_REPLIES_PER_THREAD_24H = 5

# BC-006: Time window for rate limiting (24 hours)
BC006_RATE_LIMIT_WINDOW_HOURS = 24

# Known PARWA system email addresses (will never be from real customers)
PARWA_SYSTEM_DOMAINS = [
    "parwa.ai",
    "getparwa.com",
    "parwasupport.com",
]

# Headers that indicate auto-reply / out-of-office
AUTO_REPLY_HEADERS = {
    "x-auto-response-suppress",
    "auto-submitted",
    "x-auto-reply",
    "x-noriday",
    "precedence",
    "x-precedence",
}

# Auto-reply header values that indicate auto-response
AUTO_REPLY_HEADER_VALUES = [
    "auto-replied",
    "yes",
    "auto_reply",
    "autoreply",
    "list",
    "bulk",
]

# Body patterns for OOO / auto-reply detection (case-insensitive)
OOO_BODY_PATTERNS = [
    re.compile(r"out\s+of\s+(?:the\s+)?office", re.IGNORECASE),
    re.compile(r"auto(?:-)?reply", re.IGNORECASE),
    re.compile(r"autoreply", re.IGNORECASE),
    re.compile(r"vacation\s+(?:notice|auto|response|mode)", re.IGNORECASE),
    re.compile(r"i(?:'m| am)\s+(?:currently\s+)?(?:away|out|on vacation|on leave)", re.IGNORECASE),
    re.compile(r"thank\s+you\s+for\s+your\s+email", re.IGNORECASE),
    re.compile(r"i\s+will\s+(?:be\s+)?(?:back|return|respond)\s+(?:on|from|after|by)", re.IGNORECASE),
    re.compile(r"no\s+(?:longer\s+)?(?:monitoring|checking|reading)\s+(?:this\s+)?(?:inbox|email|account)", re.IGNORECASE),
    re.compile(r"please\s+contact\s+(?:someone\s+else|my\s+colleague)", re.IGNORECASE),
    re.compile(r"this\s+is\s+an\s+automated", re.IGNORECASE),
]


class EmailChannelService:
    """Service for processing inbound emails and managing email threads.

    All methods are scoped to company_id (BC-001) and are idempotent
    where applicable (BC-003).
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Main Processing Pipeline ────────────────────────────────

    def process_inbound_email(
        self,
        company_id: str,
        email_data: dict,
    ) -> dict:
        """Process an inbound email from Brevo webhook.

        Full pipeline:
        1. Check for duplicate Message-ID (idempotency — BC-003)
        2. Store raw email
        3. Detect email loops
        4. Detect auto-replies / OOO
        5. Find/create customer
        6. Find existing thread or create new ticket
        7. Create ticket message
        8. Update email thread tracking

        Args:
            company_id: Tenant company ID.
            email_data: Dict from brevo_handler with keys:
                sender_email, sender_name, recipient_email, subject,
                body_html, body_text, message_id, in_reply_to,
                references, attachments.

        Returns:
            Dict with status, ticket_id, thread_id, inbound_email_id, etc.
        """
        # Step 1: Idempotency check — same Message-ID?
        message_id = email_data.get("message_id", "")
        if message_id:
            existing = self._get_by_message_id(message_id)
            if existing:
                logger.info(
                    "email_duplicate_skip",
                    extra={
                        "company_id": company_id,
                        "message_id": message_id,
                        "existing_id": existing.id,
                    },
                )
                return {
                    "status": "skipped_duplicate",
                    "ticket_id": existing.ticket_id,
                    "inbound_email_id": existing.id,
                    "error": None,
                }

        # Step 2: Store raw email
        inbound_email = self._store_raw_email(company_id, email_data)

        # Step 3: Loop detection
        loop_result = self.detect_email_loop(company_id, email_data)
        if loop_result.is_loop:
            inbound_email.is_loop = True
            self.db.commit()
            logger.warning(
                "email_loop_detected",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "loop_type": loop_result.loop_type,
                    "sender": email_data.get("sender_email"),
                },
            )
            return {
                "status": "skipped_loop",
                "ticket_id": None,
                "inbound_email_id": inbound_email.id,
                "loop_detection": loop_result.model_dump(),
            }

        # Step 4: Auto-reply detection
        auto_reply_result = self.detect_auto_reply(email_data)
        if auto_reply_result.is_auto_reply:
            inbound_email.is_auto_reply = True
            self.db.commit()
            logger.info(
                "email_auto_reply_skip",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "source": auto_reply_result.detection_source,
                    "sender": email_data.get("sender_email"),
                },
            )
            return {
                "status": "skipped_auto_reply",
                "ticket_id": None,
                "inbound_email_id": inbound_email.id,
                "auto_reply_detection": auto_reply_result.model_dump(),
            }

        # Step 4b: Spam detection (PS15 + MF21)
        spam_result = self._check_spam(company_id, email_data)
        if spam_result and spam_result.get("should_auto_flag"):
            inbound_email.processing_error = f"Auto-flagged as spam: {spam_result.get('spam_score', 0)}"
            self.db.commit()
            logger.warning(
                "email_spam_flagged",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "spam_score": spam_result.get("spam_score"),
                    "sender": email_data.get("sender_email"),
                },
            )
            return {
                "status": "skipped_spam",
                "ticket_id": None,
                "inbound_email_id": inbound_email.id,
                "spam_detection": spam_result,
            }

        # Step 5: Find or create customer
        customer_id = self._find_or_create_customer(company_id, email_data)

        # Step 6: Find existing thread
        in_reply_to = email_data.get("in_reply_to")
        references = email_data.get("references", "")
        email_thread = self.find_email_thread(company_id, in_reply_to, references)

        try:
            if email_thread:
                # Add message to existing ticket
                ticket_id = self._add_to_existing_thread(
                    company_id=company_id,
                    email_thread=email_thread,
                    email_data=email_data,
                    inbound_email=inbound_email,
                    customer_id=customer_id,
                )
                return {
                    "status": "added_to_thread",
                    "ticket_id": ticket_id,
                    "thread_id": email_thread.id,
                    "inbound_email_id": inbound_email.id,
                }
            else:
                # Create new ticket + thread
                result = self._create_new_ticket(
                    company_id=company_id,
                    email_data=email_data,
                    inbound_email=inbound_email,
                    customer_id=customer_id,
                )
                return {
                    "status": "created_ticket",
                    "ticket_id": result["ticket_id"],
                    "thread_id": result["thread_id"],
                    "inbound_email_id": inbound_email.id,
                }
        except ValueError as exc:
            # BC-006 rate limit or other validation errors
            error_str = str(exc)
            is_rate_limit = "BC-006" in error_str
            inbound_email.processing_error = error_str[:1000]
            self.db.commit()
            logger.warning(
                "email_validation_error" if not is_rate_limit else "email_bc006_blocked",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "error": error_str[:200],
                    "is_rate_limit": is_rate_limit,
                },
            )
            return {
                "status": "rate_limited" if is_rate_limit else "validation_error",
                "ticket_id": None,
                "inbound_email_id": inbound_email.id,
                "error": error_str[:500],
            }
        except Exception as exc:
            inbound_email.processing_error = str(exc)[:1000]
            self.db.commit()
            logger.error(
                "email_processing_error",
                extra={
                    "company_id": company_id,
                    "message_id": message_id,
                    "error": str(exc)[:200],
                },
            )
            return {
                "status": "error",
                "ticket_id": None,
                "inbound_email_id": inbound_email.id,
                "error": str(exc)[:500],
            }

    # ── Loop Detection ──────────────────────────────────────────

    def detect_email_loop(
        self,
        company_id: str,
        email_data: dict,
    ) -> EmailLoopDetection:
        """Detect if an inbound email is part of a mail loop.

        Checks:
        1. Self-sent: sender domain matches PARWA system domains
        2. X-Loop header present
        3. Message-ID already processed (duplicate)
        4. Excessive In-Reply-To chain depth

        Args:
            company_id: Tenant company ID.
            email_data: Email data dict with sender_email, message_id,
                in_reply_to, headers_json.

        Returns:
            EmailLoopDetection with is_loop and reason.
        """
        sender_email = email_data.get("sender_email", "").lower().strip()
        message_id = email_data.get("message_id", "")
        in_reply_to = email_data.get("in_reply_to", "")
        headers_json = email_data.get("headers_json", "{}")

        # Parse headers if dict string
        headers = {}
        if isinstance(headers_json, str):
            try:
                headers = json.loads(headers_json)
            except (json.JSONDecodeError, TypeError):
                headers = {}
        elif isinstance(headers_json, dict):
            headers = headers_json

        # Check 1: Self-sent (sender domain matches PARWA domains)
        sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
        if sender_domain in PARWA_SYSTEM_DOMAINS:
            return EmailLoopDetection(
                is_loop=True,
                reason=f"Sender domain '{sender_domain}' matches PARWA system domain",
                loop_type="self_sent",
            )

        # Check 2: X-Loop header
        x_loop = headers.get("x-loop", "")
        if x_loop and "parwa" in x_loop.lower():
            return EmailLoopDetection(
                is_loop=True,
                reason="X-Loop header detected with PARWA domain",
                loop_type="x_loop_header",
            )

        # Check 3: Already processed (BC-003)
        if message_id:
            existing = self._get_by_message_id(message_id)
            if existing and existing.is_processed:
                return EmailLoopDetection(
                    is_loop=True,
                    reason=f"Message-ID '{message_id}' already processed",
                    loop_type="already_processed",
                )

        # Check 4: Excessive reply depth
        if in_reply_to:
            depth = self._count_reply_depth(company_id, in_reply_to)
            if depth >= MAX_REPLY_DEPTH:
                return EmailLoopDetection(
                    is_loop=True,
                    reason=f"Reply chain depth ({depth}) exceeds max ({MAX_REPLY_DEPTH})",
                    loop_type="depth_exceeded",
                )

        return EmailLoopDetection(is_loop=False)

    # ── Auto-Reply / OOO Detection ──────────────────────────────

    def detect_auto_reply(
        self,
        email_data: dict,
    ) -> AutoReplyDetection:
        """Detect if an inbound email is an auto-reply or out-of-office.

        Checks:
        1. Auto-reply headers (Auto-Submitted, X-Auto-Response-Suppress, etc.)
        2. Body content patterns (OOO phrases, vacation notices, etc.)

        Args:
            email_data: Email data dict with headers_json, body_text, body_html.

        Returns:
            AutoReplyDetection with is_auto_reply and reason.
        """
        headers_json = email_data.get("headers_json", "{}")
        body_text = email_data.get("body_text", "")
        body_html = email_data.get("body_html", "")

        # Parse headers
        headers = {}
        if isinstance(headers_json, str):
            try:
                headers = json.loads(headers_json)
            except (json.JSONDecodeError, TypeError):
                headers = {}
        elif isinstance(headers_json, dict):
            headers = headers_json

        # Check 1: Auto-reply headers
        for header_name in AUTO_REPLY_HEADERS:
            header_value = str(headers.get(header_name, "")).lower().strip()
            if not header_value:
                continue

            # Match specific auto-reply header values
            if header_value in AUTO_REPLY_HEADER_VALUES:
                return AutoReplyDetection(
                    is_auto_reply=True,
                    reason=f"Auto-reply header '{header_name}' = '{header_value}'",
                    detection_source="header",
                )

            # Match Precedence: auto_reply specifically
            if header_name == "precedence" and "auto" in header_value:
                return AutoReplyDetection(
                    is_auto_reply=True,
                    reason=f"Precedence header = '{header_value}'",
                    detection_source="header",
                )

            # Match Auto-Submitted: any non-empty value means auto
            if header_name == "auto-submitted" and header_value != "no":
                return AutoReplyDetection(
                    is_auto_reply=True,
                    reason=f"Auto-Submitted header = '{header_value}'",
                    detection_source="header",
                )

        # Check 2: Body patterns (use text first, fall back to HTML-stripped)
        body_to_check = body_text or ""
        if not body_to_check and body_html:
            # Strip HTML tags for pattern matching
            body_to_check = re.sub(r"<[^>]+>", " ", body_html)
            body_to_check = re.sub(r"\s+", " ", body_to_check).strip()

        if body_to_check:
            # Only check first 2000 chars for performance
            check_text = body_to_check[:2000]
            for pattern in OOO_BODY_PATTERNS:
                if pattern.search(check_text):
                    matched = pattern.search(check_text).group(0)
                    return AutoReplyDetection(
                        is_auto_reply=True,
                        reason=f"Body pattern matched: '{matched}'",
                        detection_source="body",
                    )

        return AutoReplyDetection(is_auto_reply=False)

    # ── Email Thread Management ─────────────────────────────────

    def find_email_thread(
        self,
        company_id: str,
        in_reply_to: Optional[str],
        references: Optional[str],
    ) -> Optional[EmailThread]:
        """Find an existing email thread by In-Reply-To or References.

        Search order:
        1. Match email_threads.thread_message_id or latest_message_id
           against in_reply_to (most specific)
        2. Parse references header into Message-ID list, search for
           any matching thread_message_id

        Args:
            company_id: Tenant company ID.
            in_reply_to: The In-Reply-To header value.
            references: The References header (space-separated Message-IDs).

        Returns:
            EmailThread if found, None otherwise.
        """
        if not in_reply_to and not references:
            return None

        # Search 1: Direct match by in_reply_to
        if in_reply_to:
            thread = (
                self.db.query(EmailThread)
                .filter(
                    EmailThread.company_id == company_id,
                    or_(
                        EmailThread.thread_message_id == in_reply_to.strip(),
                        EmailThread.latest_message_id == in_reply_to.strip(),
                    ),
                )
                .first()
            )
            if thread:
                return thread

        # Search 2: Match any Message-ID from references chain
        if references:
            ref_ids = self._parse_references(references)
            for ref_id in ref_ids:
                ref_id = ref_id.strip()
                if not ref_id:
                    continue
                thread = (
                    self.db.query(EmailThread)
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

    # ── Query Methods ───────────────────────────────────────────

    def get_inbound_email(
        self,
        inbound_email_id: str,
        company_id: str,
    ) -> Optional[InboundEmail]:
        """Get a single inbound email with company_id isolation.

        Args:
            inbound_email_id: The inbound email UUID.
            company_id: Tenant company ID.

        Returns:
            InboundEmail if found, None otherwise.
        """
        return (
            self.db.query(InboundEmail)
            .filter(
                InboundEmail.id == inbound_email_id,
                InboundEmail.company_id == company_id,
            )
            .first()
        )

    def list_inbound_emails(
        self,
        company_id: str,
        page: int = 1,
        page_size: int = 50,
        is_processed: Optional[bool] = None,
        sender_email: Optional[str] = None,
    ) -> dict:
        """List inbound emails with pagination and filters.

        Args:
            company_id: Tenant company ID.
            page: Page number (1-based).
            page_size: Items per page.
            is_processed: Filter by processing status.
            sender_email: Filter by sender email.

        Returns:
            Dict with items, total, page, page_size, total_pages.
        """
        query = self.db.query(InboundEmail).filter(
            InboundEmail.company_id == company_id,
        )

        if is_processed is not None:
            query = query.filter(InboundEmail.is_processed == is_processed)
        if sender_email:
            query = query.filter(InboundEmail.sender_email == sender_email)

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = query.order_by(InboundEmail.created_at.desc()).offset(offset).limit(page_size).all()

        return {
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ── Private Methods ─────────────────────────────────────────

    def _store_raw_email(self, company_id: str, email_data: dict) -> InboundEmail:
        """Store raw inbound email in the database.

        Args:
            company_id: Tenant company ID.
            email_data: Email data from brevo_handler.

        Returns:
            Created InboundEmail record.
        """
        inbound = InboundEmail(
            company_id=company_id,
            message_id=email_data.get("message_id"),
            in_reply_to=email_data.get("in_reply_to"),
            references=email_data.get("references"),
            sender_email=email_data.get("sender_email", "").strip(),
            sender_name=email_data.get("sender_name", ""),
            recipient_email=email_data.get("recipient_email", "").strip(),
            subject=email_data.get("subject", ""),
            body_html=email_data.get("body_html", ""),
            body_text=email_data.get("body_text", ""),
            headers_json=email_data.get("headers_json", "{}"),
            raw_size_bytes=len(email_data.get("body_html", "")) + len(email_data.get("body_text", "")),
        )
        self.db.add(inbound)
        self.db.commit()
        self.db.refresh(inbound)
        return inbound

    def _get_by_message_id(self, message_id: str) -> Optional[InboundEmail]:
        """Look up an inbound email by Message-ID.

        Args:
            message_id: RFC 2822 Message-ID header value.

        Returns:
            InboundEmail if found, None otherwise.
        """
        if not message_id:
            return None
        return (
            self.db.query(InboundEmail)
            .filter(InboundEmail.message_id == message_id.strip())
            .first()
        )

    def _count_reply_depth(self, company_id: str, in_reply_to: str) -> int:
        """Count how deep the reply chain is.

        Traverses the email thread chain to count depth.

        Args:
            company_id: Tenant company ID.
            in_reply_to: The In-Reply-To Message-ID to start from.

        Returns:
            Integer depth count.
        """
        depth = 0
        current_id = in_reply_to.strip()
        visited = set()

        while current_id and current_id not in visited and depth < MAX_REPLY_DEPTH + 5:
            visited.add(current_id)
            thread = (
                self.db.query(EmailThread)
                .filter(
                    EmailThread.company_id == company_id,
                    or_(
                        EmailThread.thread_message_id == current_id,
                        EmailThread.latest_message_id == current_id,
                    ),
                )
                .first()
            )
            if thread:
                depth += 1
                # Move to the previous message in the chain
                current_id = thread.thread_message_id
                if current_id == thread.latest_message_id:
                    break
            else:
                break

        return depth

    def _parse_references(self, references: str) -> list:
        """Parse the References header into a list of Message-IDs.

        The References header is a space-separated list of Message-IDs,
        typically enclosed in angle brackets.

        Args:
            references: The References header value.

        Returns:
            List of Message-ID strings (without angle brackets).
        """
        if not references:
            return []

        # Extract Message-IDs from angle brackets
        ids = re.findall(r"<([^>]+)>", references)
        if ids:
            return ids

        # Fallback: split by whitespace
        return [r.strip() for r in references.split() if r.strip()]

    def _find_or_create_customer(self, company_id: str, email_data: dict) -> Optional[str]:
        """Find or create a customer based on email address.

        Uses the identity resolution service if available,
        falls back to simple email lookup.

        Args:
            company_id: Tenant company ID.
            email_data: Email data with sender_email.

        Returns:
            Customer ID if found/created, None otherwise.
        """
        sender_email = email_data.get("sender_email", "").strip()
        if not sender_email:
            return None

        try:
            from database.models.tickets import Customer

            # Try to find existing customer by email within this company
            customer = (
                self.db.query(Customer)
                .filter(
                    Customer.company_id == company_id,
                    Customer.email == sender_email.lower(),
                )
                .first()
            )
            if customer:
                return customer.id

            # Create new customer
            new_customer = Customer(
                company_id=company_id,
                email=sender_email.lower(),
                name=email_data.get("sender_name", sender_email.split("@")[0]),
            )
            self.db.add(new_customer)
            self.db.commit()
            self.db.refresh(new_customer)
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

    def _check_spam(self, company_id: str, email_data: dict) -> Optional[dict]:
        """Run spam detection on inbound email (PS15 + MF21).

        Uses SpamDetectionService.analyze_ticket() to score the email.
        If the score exceeds the auto-flag threshold, the email is
        rejected before ticket creation.

        Args:
            company_id: Tenant company ID.
            email_data: Email data with subject, body_text, sender_email.

        Returns:
            Spam analysis result dict, or None if scoring fails.
        """
        try:
            from app.services.spam_detection_service import SpamDetectionService
            spam_svc = SpamDetectionService(self.db, company_id)
            subject = email_data.get("subject", "")
            content = email_data.get("body_text") or email_data.get("body_html", "")
            return spam_svc.analyze_ticket(
                subject=subject,
                content=content[:2000],  # Limit for performance
            )
        except Exception as exc:
            # Spam detection is advisory — never block on failure
            logger.warning(
                "email_spam_check_failed",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:200],
                },
            )
            return None

    def _classify_email(self, company_id: str, email_data: dict) -> Optional[dict]:
        """Run AI intent classification on inbound email (F-062).

        Uses ClassificationEngine to determine the primary intent,
        which sets the ticket category. This enables automatic
        routing and prioritization.

        Args:
            company_id: Tenant company ID.
            email_data: Email data with subject and body.

        Returns:
            Classification result dict with primary_intent, primary_confidence,
            classification_method. Returns None if classification fails.
        """
        try:
            from app.core.classification_engine import (
                ClassificationEngine,
                INTENT_TO_CATEGORY_MAP,
            )
            engine = ClassificationEngine()
            text = email_data.get("body_text") or ""
            if not text:
                # Fall back to HTML-stripped body
                html = email_data.get("body_html", "")
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text).strip()
            subject = email_data.get("subject", "")
            full_text = f"{subject} {text}".strip()
            if len(full_text) < 5:
                return None
            result = engine.classify(full_text[:3000])
            return {
                "primary_intent": result.primary_intent,
                "primary_confidence": result.primary_confidence,
                "secondary_intents": result.secondary_intents,
                "classification_method": result.classification_method,
                "processing_time_ms": result.processing_time_ms,
            }
        except Exception as exc:
            # Classification is advisory — never block on failure
            logger.warning(
                "email_classification_failed",
                extra={
                    "company_id": company_id,
                    "error": str(exc)[:200],
                },
            )
            return None

    def _check_bc006_rate_limit(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[str]:
        """Check BC-006 rate limit: max 5 replies per thread per 24h.

        Counts customer messages (role='customer', channel='email')
        created in the last 24 hours for this ticket.

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket to check.

        Returns:
            None if under limit, or error reason string if exceeded.
        """
        since = datetime.now(timezone.utc) - timedelta(
            hours=BC006_RATE_LIMIT_WINDOW_HOURS
        )
        count = (
            self.db.query(TicketMessage)
            .filter(
                TicketMessage.company_id == company_id,
                TicketMessage.ticket_id == ticket_id,
                TicketMessage.role == "customer",
                TicketMessage.channel == "email",
                TicketMessage.created_at >= since,
            )
            .count()
        )
        if count >= BC006_MAX_REPLIES_PER_THREAD_24H:
            return (
                f"BC-006 rate limit exceeded: {count} emails in last "
                f"{BC006_RATE_LIMIT_WINDOW_HOURS}h (max {BC006_MAX_REPLIES_PER_THREAD_24H})"
            )
        return None

    def _add_to_existing_thread(
        self,
        company_id: str,
        email_thread: EmailThread,
        email_data: dict,
        inbound_email: InboundEmail,
        customer_id: Optional[str],
    ) -> str:
        """Add an email reply to an existing ticket thread.

        Args:
            company_id: Tenant company ID.
            email_thread: The existing EmailThread record.
            email_data: Email data from brevo_handler.
            inbound_email: The stored InboundEmail record.
            customer_id: Customer ID.

        Returns:
            The ticket_id of the existing ticket.

        Raises:
            ValueError: If BC-006 rate limit is exceeded.
        """
        # BC-006: Rate limit check — 5 replies/thread/24h
        rate_limit_error = self._check_bc006_rate_limit(
            company_id, email_thread.ticket_id,
        )
        if rate_limit_error:
            logger.warning(
                "email_bc006_rate_limit_exceeded",
                extra={
                    "company_id": company_id,
                    "ticket_id": email_thread.ticket_id,
                    "sender": email_data.get("sender_email"),
                    "reason": rate_limit_error,
                },
            )
            raise ValueError(rate_limit_error)

        # Create ticket message
        message = TicketMessage(
            ticket_id=email_thread.ticket_id,
            company_id=company_id,
            role="customer",
            content=email_data.get("body_text") or email_data.get("body_html", ""),
            channel="email",
            metadata_json=json.dumps({
                "email_message_id": email_data.get("message_id", ""),
                "email_in_reply_to": email_data.get("in_reply_to", ""),
                "email_sender": email_data.get("sender_email", ""),
                "email_sender_name": email_data.get("sender_name", ""),
                "attachments": email_data.get("attachments", []),
            }),
        )
        if customer_id:
            # Update ticket customer_id if not set
            ticket = self.db.query(Ticket).filter(
                Ticket.id == email_thread.ticket_id,
                Ticket.company_id == company_id,
            ).first()
            if ticket and not ticket.customer_id and customer_id:
                ticket.customer_id = customer_id
        self.db.add(message)

        # Update email thread
        email_thread.latest_message_id = email_data.get("message_id", "")
        email_thread.message_count = (email_thread.message_count or 1) + 1

        # Update participants list
        participants = json.loads(email_thread.participants_json or "[]")
        sender_email = email_data.get("sender_email", "").lower().strip()
        if sender_email and sender_email not in participants:
            participants.append(sender_email)
            email_thread.participants_json = json.dumps(participants)

        # Mark inbound email as processed
        inbound_email.is_processed = True
        inbound_email.ticket_id = email_thread.ticket_id

        self.db.commit()

        logger.info(
            "email_added_to_thread",
            extra={
                "company_id": company_id,
                "ticket_id": email_thread.ticket_id,
                "thread_id": email_thread.id,
                "message_count": email_thread.message_count,
                "sender": sender_email,
            },
        )

        return email_thread.ticket_id

    def _create_new_ticket(
        self,
        company_id: str,
        email_data: dict,
        inbound_email: InboundEmail,
        customer_id: Optional[str],
    ) -> dict:
        """Create a new ticket from an inbound email.

        Args:
            company_id: Tenant company ID.
            email_data: Email data from brevo_handler.
            inbound_email: The stored InboundEmail record.
            customer_id: Customer ID.

        Returns:
            Dict with ticket_id and thread_id.
        """
        # AI classification — set category/intent from email content
        category = None
        priority = "medium"
        classification_result = self._classify_email(company_id, email_data)
        if classification_result:
            category = classification_result.get("primary_intent")
            # Map high-confidence complaint/escalation to high priority
            if classification_result.get("primary_confidence", 0) > 0.8:
                intent = category or ""
                if intent in ("complaint", "escalation", "cancellation"):
                    priority = "high"

        # Create ticket
        ticket = Ticket(
            company_id=company_id,
            customer_id=customer_id,
            channel="email",
            subject=email_data.get("subject", "(No Subject)")[:255],
            status="open",
            category=category,
            priority=priority,
            metadata_json=json.dumps({
                "email_message_id": email_data.get("message_id", ""),
                "email_sender": email_data.get("sender_email", ""),
                "email_sender_name": email_data.get("sender_name", ""),
                "source": "inbound_email",
                "classification": classification_result,
            }),
        )
        self.db.add(ticket)
        self.db.flush()  # Get ticket.id

        # Create first ticket message
        message = TicketMessage(
            ticket_id=ticket.id,
            company_id=company_id,
            role="customer",
            content=email_data.get("body_text") or email_data.get("body_html", ""),
            channel="email",
            metadata_json=json.dumps({
                "email_message_id": email_data.get("message_id", ""),
                "email_sender": email_data.get("sender_email", ""),
                "email_sender_name": email_data.get("sender_name", ""),
                "attachments": email_data.get("attachments", []),
                "is_first_message": True,
            }),
        )
        self.db.add(message)

        # Create email thread
        email_thread = EmailThread(
            company_id=company_id,
            ticket_id=ticket.id,
            thread_message_id=email_data.get("message_id", ""),
            latest_message_id=email_data.get("message_id", ""),
            message_count=1,
            participants_json=json.dumps([email_data.get("sender_email", "").lower().strip()]),
        )
        self.db.add(email_thread)

        # Mark inbound email as processed
        inbound_email.is_processed = True
        inbound_email.ticket_id = ticket.id

        self.db.commit()

        logger.info(
            "email_new_ticket_created",
            extra={
                "company_id": company_id,
                "ticket_id": ticket.id,
                "thread_id": email_thread.id,
                "sender": email_data.get("sender_email"),
                "subject": email_data.get("subject", ""),
            },
        )

        return {
            "ticket_id": ticket.id,
            "thread_id": email_thread.id,
        }
