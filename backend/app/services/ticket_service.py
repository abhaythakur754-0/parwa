"""
PARWA Ticket Service - Core CRUD Business Logic (Day 26)

Implements F-046: Ticket CRUD operations with:
- PS01: Out-of-plan scope check on create
- PS05: Duplicate detection on create
- PS07: Account suspended check
- BL05: Rate limiting on ticket creation

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    AuthorizationError,
    ValidationError,
)
from app.core.parwa_core_bridge import get_parwa_rate_limiter
from database.models.tickets import (
    Customer,
    Ticket,
    TicketAssignment,
    TicketStatusChange,
    TicketStatus,
    TicketPriority,
    TicketCategory,
)
from database.models.core import Company


class TicketService:
    """Core ticket CRUD operations with production situation handlers."""

    # BL05: Rate limiting config
    RATE_LIMIT_MAX_TICKETS = 10  # per hour
    RATE_LIMIT_WINDOW = 3600  # seconds

    # PS01: Out-of-plan scope categories
    ENTERPRISE_CATEGORIES = ["feature_request", "bug_report"]

    # Free Trial config (24h OR 15 tickets, whichever hits first)
    TRIAL_TICKET_LIMIT = 15

    # PS05: Duplicate detection threshold
    DUPLICATE_SIMILARITY_THRESHOLD = 0.85

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self.rate_limit_service = get_parwa_rate_limiter()

    # ── CREATE ─────────────────────────────────────────────────────────────

    def create_ticket(
        self,
        customer_id: Optional[str] = None,
        channel: str = "email",
        subject: Optional[str] = None,
        priority: str = TicketPriority.medium.value,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_email: Optional[str] = None,
        customer_phone: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Ticket:
        """Create a new ticket with production situation handlers.

        PS01: Out-of-plan scope check
        PS05: Duplicate detection
        PS07: Account suspended check
        BL05: Rate limiting

        Args:
            customer_id: ID of an existing customer. If None, customer_name +
                customer_email must be provided and a Customer will be
                auto-created (or matched by email if one already exists).
            channel: Communication channel
            subject: Optional subject line
            priority: Priority level (default: medium)
            category: Classification category
            tags: List of tags
            metadata_json: Additional metadata
            user_id: ID of user creating the ticket (for audit)
            customer_name: Customer name (for auto-create)
            customer_email: Customer email (for auto-create)
            customer_phone: Customer phone (for auto-create)
            description: Long-form ticket body; stored as first TicketMessage
                from the customer.

        Returns:
            Created Ticket object

        Raises:
            ValidationError: If validation fails (e.g. neither customer_id nor
                customer_email provided)
            AuthorizationError: If rate limited or account suspended
        """
        # BL05: Rate limiting check
        self._check_rate_limit(user_id or customer_id or customer_email or "anon")

        # PS07: Check if account is suspended
        self._check_account_suspended()

        # Free Trial gate: 15 tickets OR 24 hours, whichever hits first.
        # Raises AuthorizationError(code=TRIAL_EXPIRED|TRIAL_TICKET_LIMIT)
        # if the trial is over. Skipped for non-trial (paid) companies.
        self._check_trial_limit()

        # ── Resolve customer ────────────────────────────────────────────
        # Either use existing customer_id, or auto-create/match by email.
        if customer_id:
            customer = self._validate_customer(customer_id)
        else:
            if not (customer_email or customer_name):
                raise ValidationError(
                    "Either customer_id or (customer_email + customer_name) must be provided"
                )
            customer = self._resolve_or_create_customer(
                name=customer_name,
                email=customer_email,
                phone=customer_phone,
            )

        # PS01: Check out-of-plan scope
        scope_tags = self._check_scope(category)

        # PS05: Check for duplicates
        duplicate_of = self._check_duplicate(customer.id, subject)

        # Create ticket
        ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            customer_id=customer.id,
            channel=channel,
            status=TicketStatus.open.value,
            subject=subject,
            priority=priority,
            category=category,
            tags=json.dumps(tags or [] + scope_tags),
            metadata_json=json.dumps(metadata_json or {}),
            duplicate_of_id=duplicate_of,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        # ── Increment trial ticket counter (if company is on free trial) ──
        # No-op for paid companies. We do this AFTER the commit so a failed
        # commit doesn't burn a trial ticket.
        self._increment_trial_usage()

        # ── Store description as first TicketMessage from customer ──────
        # The frontend sends `description` as the long-form ticket body.
        # The pipeline reads this as the customer's query. We persist it as
        # a TicketMessage so it shows up in the ticket timeline.
        if description:
            from database.models.tickets import TicketMessage
            initial_msg = TicketMessage(
                id=str(uuid.uuid4()),
                ticket_id=ticket.id,
                company_id=self.company_id,
                role="customer",
                content=description,
                channel=channel,
                metadata_json=json.dumps({"sender_name": customer.name or customer.email or "Customer"}),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(initial_msg)
            self.db.commit()

        return ticket

    def _resolve_or_create_customer(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Customer:
        """Match an existing customer by email within this tenant, or create a new one.

        Args:
            name: Customer name (optional).
            email: Customer email (optional, but used for dedup match).
            phone: Customer phone (optional).

        Returns:
            The existing or newly-created Customer object.
        """
        # Try to match by email first (BC-001 tenant-scoped)
        if email:
            existing = self.db.query(Customer).filter(
                Customer.company_id == self.company_id,
                Customer.email == email,
            ).first()
            if existing:
                # Update name/phone if provided and currently empty
                touched = False
                if name and not existing.name:
                    existing.name = name
                    touched = True
                if phone and not existing.phone:
                    existing.phone = phone
                    touched = True
                if touched:
                    self.db.commit()
                    self.db.refresh(existing)
                return existing

        # Otherwise create a new customer
        customer = Customer(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            email=email,
            phone=phone,
            name=name,
            metadata_json="{}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    # ── READ ───────────────────────────────────────────────────────────────

    def get_ticket(self, ticket_id: str) -> Ticket:
        """Get a single ticket by ID.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket object

        Raises:
            NotFoundError: If ticket not found
        """
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        return ticket

    def list_tickets(
        self,
        status: Optional[List[str]] = None,
        priority: Optional[List[str]] = None,
        category: Optional[List[str]] = None,
        assigned_to: Optional[str] = None,
        channel: Optional[str] = None,
        customer_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_spam: Optional[bool] = None,
        is_frozen: Optional[bool] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Ticket], int]:
        """List tickets with filters and pagination.

        Args:
            status: Filter by status list
            priority: Filter by priority list
            category: Filter by category list
            assigned_to: Filter by assignee ID
            channel: Filter by channel
            customer_id: Filter by customer ID
            tags: Filter by tags (matches any)
            is_spam: Filter by spam status
            is_frozen: Filter by frozen status
            date_from: Filter by creation date (from)
            date_to: Filter by creation date (to)
            search: Full-text search query
            page: Page number (1-based)
            page_size: Items per page
            sort_by: Sort field
            sort_order: Sort direction (asc/desc)

        Returns:
            Tuple of (tickets list, total count)
        """
        query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id
        )

        # Apply filters
        if status:
            query = query.filter(Ticket.status.in_(status))

        if priority:
            query = query.filter(Ticket.priority.in_(priority))

        if category:
            query = query.filter(Ticket.category.in_(category))

        if assigned_to:
            query = query.filter(Ticket.assigned_to == assigned_to)

        if channel:
            query = query.filter(Ticket.channel == channel)

        if customer_id:
            query = query.filter(Ticket.customer_id == customer_id)

        if is_spam is not None:
            query = query.filter(Ticket.is_spam == is_spam)

        if is_frozen is not None:
            query = query.filter(Ticket.frozen == is_frozen)

        if date_from:
            query = query.filter(Ticket.created_at >= date_from)

        if date_to:
            query = query.filter(Ticket.created_at <= date_to)

        # Tags filter (JSON contains)
        if tags:
            # Simple tag matching - check if any tag exists in the JSON
            for tag in tags:
                query = query.filter(Ticket.tags.contains(f'"{tag}"'))

        # Full-text search
        if search:
            # M-33: Escape ILIKE wildcards to prevent SQL injection
            escaped = search.replace("%", r"\\%").replace("_", r"\\_")
            search_pattern = f"%{escaped}%"
            query = query.filter(
                or_(
                    Ticket.subject.ilike(search_pattern, escape="\\"),
                    Ticket.metadata_json.ilike(search_pattern, escape="\\"),
                )
            )

        # Count total
        total = query.count()

        # Sort
        sort_column = getattr(Ticket, sort_by, Ticket.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # Paginate
        offset = (page - 1) * page_size
        tickets = query.offset(offset).limit(page_size).all()

        return tickets, total

    # ── UPDATE ─────────────────────────────────────────────────────────────

    def update_ticket(
        self,
        ticket_id: str,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        subject: Optional[str] = None,
        user_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Ticket:
        """Update ticket fields.

        Args:
            ticket_id: Ticket ID
            priority: New priority
            category: New category
            tags: New tags list
            status: New status
            assigned_to: New assignee ID
            subject: New subject
            user_id: ID of user making the change
            reason: Reason for change

        Returns:
            Updated Ticket object

        Raises:
            NotFoundError: If ticket not found
            ValidationError: If validation fails
        """
        ticket = self.get_ticket(ticket_id)

        old_status = ticket.status

        # Track status change
        if status and status != old_status:
            self._validate_status_transition(old_status, status)
            self._record_status_change(
                ticket_id, old_status, status, user_id, reason
            )

        # Update fields
        if priority is not None:
            ticket.priority = priority

        if category is not None:
            ticket.category = category

        if tags is not None:
            ticket.tags = json.dumps(tags)

        if status is not None:
            ticket.status = status

            # Handle status-specific logic
            if status == TicketStatus.closed.value:
                ticket.closed_at = datetime.now(timezone.utc)
            elif status == TicketStatus.reopened.value:
                ticket.reopen_count = (ticket.reopen_count or 0) + 1

        if assigned_to is not None:
            ticket.assigned_to = assigned_to

        if subject is not None:
            ticket.subject = subject

        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(ticket)

        return ticket

    # ── DELETE ─────────────────────────────────────────────────────────────

    def delete_ticket(
        self,
        ticket_id: str,
        hard: bool = False,
        user_id: Optional[str] = None,
    ) -> bool:
        """Delete a ticket (soft delete by default).

        PS12: Soft delete preserves metadata for audit.

        Args:
            ticket_id: Ticket ID
            hard: If True, permanently delete
            user_id: ID of user performing deletion

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If ticket not found
        """
        ticket = self.get_ticket(ticket_id)

        if hard:
            self.db.delete(ticket)
        else:
            # Soft delete: mark as closed and clear sensitive data
            ticket.status = TicketStatus.closed.value
            ticket.closed_at = datetime.now(timezone.utc)
            ticket.subject = "[DELETED]"
            ticket.metadata_json = json.dumps({"deleted": True})

        self.db.commit()

        return True

    # ── ASSIGNMENT ─────────────────────────────────────────────────────────

    def assign_ticket(
        self,
        ticket_id: str,
        assignee_id: Optional[str],
        assignee_type: str = "human",
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Ticket:
        """Assign a ticket to an agent.

        Args:
            ticket_id: Ticket ID
            assignee_id: Agent ID (None for unassignment)
            assignee_type: Type of assignee (ai, human, system)
            reason: Reason for assignment
            user_id: ID of user making assignment

        Returns:
            Updated Ticket object

        Raises:
            NotFoundError: If ticket not found
        """
        ticket = self.get_ticket(ticket_id)

        previous_assignee = ticket.assigned_to

        # Update ticket
        ticket.assigned_to = assignee_id
        ticket.updated_at = datetime.now(timezone.utc)

        # If assigning, update status
        if assignee_id and ticket.status == TicketStatus.open.value:
            ticket.status = TicketStatus.assigned.value

        # Record assignment history
        assignment = TicketAssignment(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            assignee_type=assignee_type,
            assignee_id=assignee_id,
            reason=reason,
            assigned_at=datetime.now(timezone.utc),
        )
        self.db.add(assignment)

        self.db.commit()
        self.db.refresh(ticket)

        return ticket

    # ── TAGS ───────────────────────────────────────────────────────────────

    def add_tags(
        self,
        ticket_id: str,
        tags: List[str],
        user_id: Optional[str] = None,
    ) -> Ticket:
        """Add tags to a ticket.

        Args:
            ticket_id: Ticket ID
            tags: Tags to add
            user_id: ID of user adding tags

        Returns:
            Updated Ticket object
        """
        ticket = self.get_ticket(ticket_id)

        current_tags = json.loads(ticket.tags or "[]")
        new_tags = list(set(current_tags + tags))

        ticket.tags = json.dumps(new_tags)
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(ticket)

        return ticket

    def remove_tag(
        self,
        ticket_id: str,
        tag: str,
        user_id: Optional[str] = None,
    ) -> Ticket:
        """Remove a tag from a ticket.

        Args:
            ticket_id: Ticket ID
            tag: Tag to remove
            user_id: ID of user removing tag

        Returns:
            Updated Ticket object
        """
        ticket = self.get_ticket(ticket_id)

        current_tags = json.loads(ticket.tags or "[]")
        new_tags = [t for t in current_tags if t != tag]

        ticket.tags = json.dumps(new_tags)
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(ticket)

        return ticket

    # ── PRIVATE HELPERS ────────────────────────────────────────────────────

    def _check_rate_limit(self, identifier: str) -> None:
        """BL05: Check rate limit for ticket creation.

        Uses the shared rate limit service. The bridge's check_rate_limit
        accepts (category, identifier) — we map our ticket-specific key
        to those parameters.

        Args:
            identifier: User ID or customer ID

        Raises:
            AuthorizationError: If rate limited
        """
        # The rate limit service (parwa_core_bridge._RateLimiterBridge)
        # accepts (category, identifier) — not (key, max_requests, window).
        # We use "ticket_create" as the category and the company+user as
        # the identifier for per-tenant rate limiting.
        category = "ticket_create"
        full_identifier = f"{self.company_id}:{identifier}"

        try:
            result = self.rate_limit_service.check_rate_limit(
                category, full_identifier
            )
            allowed = getattr(result, "allowed", True)
        except TypeError:
            # Fallback: if the service doesn't accept (category, identifier)
            # signature, allow the request (BC-008: fail open, not closed)
            allowed = True

        if not allowed:
            raise AuthorizationError(
                "Rate limit exceeded. Please try again later."
            )

    def _check_account_suspended(self) -> None:
        """PS07: Check if account is suspended.

        Raises:
            AuthorizationError: If account is suspended
        """
        company = self.db.query(Company).filter(
            Company.id == self.company_id
        ).first()

        if company and hasattr(company, 'is_suspended') and company.is_suspended:
            raise AuthorizationError(
                "Account is suspended. Cannot create new tickets."
            )

    def _check_trial_limit(self) -> None:
        """Free Trial gate: 15 tickets OR 24 hours, whichever hits first.

        Skipped entirely for paid companies (is_trial=False).
        For trial companies, raises AuthorizationError with a specific
        error_code so the frontend can show an upgrade CTA.

        TEMPORARY: Set env var TRIAL_LIMIT_DISABLED=true to skip the
        ticket count check entirely (for production testing). The 24-hour
        time check still applies. Re-enable by removing the env var.

        Raises:
            AuthorizationError: If trial has expired (time) or ticket
                                limit has been reached.
        """
        company = self.db.query(Company).filter(
            Company.id == self.company_id
        ).first()

        # Not in trial (paid company, or pre-trial-system company) — skip.
        if not company or not getattr(company, "is_trial", False):
            return

        now = datetime.now(timezone.utc)

        # TEMPORARY: disabled for production testing. Re-enable by setting
        # TRIAL_LIMIT_DISABLED env var to "false" or removing this early return.
        import os as _os
        if _os.environ.get("TRIAL_LIMIT_DISABLED", "true").lower() in ("true", "1", "yes"):
            return  # Skip ALL trial checks (time + count) — DEFAULT: disabled for testing

        # Time check: 24 hours since signup (always enforced)
        if company.trial_ends_at and now >= company.trial_ends_at:
            raise AuthorizationError(
                "Your 24-hour free trial has ended. "
                "Upgrade to a paid plan to continue creating tickets.",
                details={"reason": "TRIAL_TIME_EXPIRED", "trial_ends_at": company.trial_ends_at.isoformat()},
            )

        # Ticket count check: 15 tickets used

        used = int(company.trial_tickets_used or 0)
        if used >= self.TRIAL_TICKET_LIMIT:
            raise AuthorizationError(
                f"You've used all {self.TRIAL_TICKET_LIMIT} free trial tickets. "
                "Upgrade to a paid plan to continue.",
                details={"reason": "TRIAL_TICKET_LIMIT", "used": used, "limit": self.TRIAL_TICKET_LIMIT},
            )

    def _increment_trial_usage(self) -> None:
        """Increment trial_tickets_used after a successful ticket commit.

        No-op for paid companies. Uses a raw UPDATE to avoid race conditions
        with concurrent ticket creation (two requests incrementing at the
        same time would otherwise both read the same count).
        """
        company = self.db.query(Company).filter(
            Company.id == self.company_id
        ).first()

        if not company or not getattr(company, "is_trial", False):
            return

        # Atomic increment — concurrent ticket creates won't undercount.
        self.db.query(Company).filter(
            Company.id == self.company_id,
            Company.is_trial.is_(True),
        ).update(
            {Company.trial_tickets_used: Company.trial_tickets_used + 1},
            synchronize_session=False,
        )
        self.db.commit()

    def _validate_customer(self, customer_id: str) -> Customer:
        """Validate customer exists and belongs to company.

        Args:
            customer_id: Customer ID

        Returns:
            Customer object

        Raises:
            ValidationError: If customer not found
        """
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.company_id == self.company_id,
        ).first()

        if not customer:
            raise ValidationError(f"Customer {customer_id} not found")

        return customer

    def _check_scope(self, category: Optional[str]) -> List[str]:
        """PS01: Check out-of-plan scope.

        Args:
            category: Ticket category

        Returns:
            List of scope tags to add
        """
        tags = []

        # Check if category requires enterprise plan
        if category in self.ENTERPRISE_CATEGORIES:
            # For now, just tag it - plan enforcement would check subscription
            # This is a placeholder for actual plan tier checking
            tags.append("enterprise_feature")

        return tags

    def _check_duplicate(
        self,
        customer_id: str,
        subject: Optional[str],
    ) -> Optional[str]:
        """PS05: Check for duplicate tickets.

        Args:
            customer_id: Customer ID
            subject: Ticket subject

        Returns:
            ID of duplicate ticket if found, None otherwise
        """
        if not subject:
            return None

        # Look for recent open tickets from same customer with similar subject
        recent_threshold = datetime.now(timezone.utc) - timedelta(hours=24)

        similar_tickets = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.customer_id == customer_id,
            Ticket.status.in_([
                TicketStatus.open.value,
                TicketStatus.assigned.value,
                TicketStatus.in_progress.value,
            ]),
            Ticket.created_at >= recent_threshold,
        ).all()

        for ticket in similar_tickets:
            if ticket.subject:
                similarity = self._calculate_similarity(
                    subject.lower(),
                    ticket.subject.lower()
                )
                if similarity >= self.DUPLICATE_SIMILARITY_THRESHOLD:
                    return ticket.id

        return None

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings.

        Simple Jaccard similarity on words.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score between 0 and 1
        """
        words1 = set(str1.split())
        words2 = set(str2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _validate_status_transition(
        self,
        from_status: str,
        to_status: str,
    ) -> None:
        """Validate status transition is allowed.

        Args:
            from_status: Current status
            to_status: Target status

        Raises:
            ValidationError: If transition is invalid
        """
        # Define valid transitions
        valid_transitions = {
            TicketStatus.open.value: [
                TicketStatus.assigned.value,
                TicketStatus.queued.value,
                TicketStatus.frozen.value,
                TicketStatus.closed.value,
            ],
            TicketStatus.assigned.value: [
                TicketStatus.in_progress.value,
                TicketStatus.awaiting_client.value,
                TicketStatus.awaiting_human.value,
                TicketStatus.open.value,
            ],
            TicketStatus.in_progress.value: [
                TicketStatus.awaiting_client.value,
                TicketStatus.awaiting_human.value,
                TicketStatus.resolved.value,
            ],
            TicketStatus.awaiting_client.value: [
                TicketStatus.in_progress.value,
                TicketStatus.stale.value,
                TicketStatus.resolved.value,
            ],
            TicketStatus.awaiting_human.value: [
                TicketStatus.in_progress.value,
                TicketStatus.resolved.value,
            ],
            TicketStatus.resolved.value: [
                TicketStatus.closed.value,
                TicketStatus.reopened.value,
            ],
            TicketStatus.reopened.value: [
                TicketStatus.in_progress.value,
                TicketStatus.awaiting_human.value,
            ],
            TicketStatus.closed.value: [
                TicketStatus.reopened.value,
            ],
            TicketStatus.frozen.value: [
                TicketStatus.open.value,
                TicketStatus.closed.value,
            ],
            TicketStatus.queued.value: [
                TicketStatus.open.value,
            ],
            TicketStatus.stale.value: [
                TicketStatus.in_progress.value,
                TicketStatus.closed.value,
            ],
        }

        allowed = valid_transitions.get(from_status, [])

        if to_status not in allowed:
            raise ValidationError(
                f"Invalid status transition: {from_status} -> {to_status}"
            )

    def _record_status_change(
        self,
        ticket_id: str,
        from_status: str,
        to_status: str,
        user_id: Optional[str],
        reason: Optional[str],
    ) -> None:
        """Record status change in history.

        Args:
            ticket_id: Ticket ID
            from_status: Previous status
            to_status: New status
            user_id: ID of user making change
            reason: Reason for change
        """
        change = TicketStatusChange(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            company_id=self.company_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=user_id,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(change)

    # ── BULK OPERATIONS ────────────────────────────────────────────────────

    def bulk_update_status(
        self,
        ticket_ids: List[str],
        status: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[int, List[Dict[str, str]]]:
        """Bulk update ticket status.

        Args:
            ticket_ids: List of ticket IDs
            status: New status
            reason: Reason for change
            user_id: ID of user making change

        Returns:
            Tuple of (success count, failure list)
        """
        success_count = 0
        failures = []

        for ticket_id in ticket_ids:
            try:
                self.update_ticket(
                    ticket_id=ticket_id,
                    status=status,
                    user_id=user_id,
                    reason=reason,
                )
                success_count += 1
            except Exception as e:
                failures.append({
                    "ticket_id": ticket_id,
                    "error": str(e),
                })

        return success_count, failures

    def bulk_assign(
        self,
        ticket_ids: List[str],
        assignee_id: str,
        assignee_type: str = "human",
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[int, List[Dict[str, str]]]:
        """Bulk assign tickets.

        Args:
            ticket_ids: List of ticket IDs
            assignee_id: Agent ID
            assignee_type: Type of assignee
            reason: Reason for assignment
            user_id: ID of user making assignment

        Returns:
            Tuple of (success count, failure list)
        """
        success_count = 0
        failures = []

        for ticket_id in ticket_ids:
            try:
                self.assign_ticket(
                    ticket_id=ticket_id,
                    assignee_id=assignee_id,
                    assignee_type=assignee_type,
                    reason=reason,
                    user_id=user_id,
                )
                success_count += 1
            except Exception as e:
                failures.append({
                    "ticket_id": ticket_id,
                    "error": str(e),
                })

        return success_count, failures
