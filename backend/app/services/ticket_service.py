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
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.services.rate_limit_service import RateLimitService
from app.services.shadow_mode_service import ShadowModeService
from sqlalchemy import desc, or_
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from database.models.core import Company
from database.models.shadow_mode import ShadowLog
from database.models.tickets import (
    Customer,
    Ticket,
    TicketAssignment,
    TicketPriority,
    TicketStatus,
    TicketStatusChange,
)


class TicketService:
    """Core ticket CRUD operations with production situation handlers."""

    # BL05: Rate limiting config
    RATE_LIMIT_MAX_TICKETS = 10  # per hour
    RATE_LIMIT_WINDOW = 3600  # seconds

    # PS01: Out-of-plan scope categories
    ENTERPRISE_CATEGORIES = ["feature_request", "bug_report"]

    # PS05: Duplicate detection threshold
    DUPLICATE_SIMILARITY_THRESHOLD = 0.85

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self.rate_limit_service = RateLimitService()

    # ── CREATE ─────────────────────────────────────────────────────────────

    def create_ticket(
        self,
        customer_id: str,
        channel: str,
        subject: Optional[str] = None,
        priority: str = TicketPriority.medium.value,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Ticket:
        """Create a new ticket with production situation handlers.

        PS01: Out-of-plan scope check
        PS05: Duplicate detection
        PS07: Account suspended check
        BL05: Rate limiting

        Args:
            customer_id: ID of the customer
            channel: Communication channel
            subject: Optional subject line
            priority: Priority level (default: medium)
            category: Classification category
            tags: List of tags
            metadata_json: Additional metadata
            user_id: ID of user creating the ticket (for audit)

        Returns:
            Created Ticket object

        Raises:
            ValidationError: If validation fails
            AuthorizationError: If rate limited or account suspended
        """
        # BL05: Rate limiting check
        self._check_rate_limit(user_id or customer_id)

        # PS07: Check if account is suspended
        self._check_account_suspended()

        # Validate customer exists and belongs to company
        customer = self._validate_customer(customer_id)

        # PS01: Check out-of-plan scope
        scope_tags = self._check_scope(category)

        # PS05: Check for duplicates
        duplicate_of = self._check_duplicate(customer_id, subject)

        # Create ticket
        ticket = Ticket(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            customer_id=customer_id,
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

        return ticket

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
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

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
        query = self.db.query(Ticket).filter(Ticket.company_id == self.company_id)

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
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Ticket.subject.ilike(search_pattern),
                    Ticket.metadata_json.ilike(search_pattern),
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
        retry_count: int = 3,
    ) -> Ticket:
        """Update ticket fields with optimistic locking.

        Uses a ``version`` column to detect concurrent modifications.
        On version mismatch, retries with exponential backoff up to
        ``retry_count`` times (max 3).

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
            retry_count: Max retries on version conflict (default 3).

        Returns:
            Updated Ticket object

        Raises:
            NotFoundError: If ticket not found
            ValidationError: If validation fails
            ConflictError: If version mismatch persists after retries
        """
        retry_count = min(max(retry_count, 0), 3)
        last_error: Optional[Exception] = None

        for attempt in range(retry_count + 1):
            # 1. Read current ticket and its version
            ticket = (
                self.db.query(Ticket)
                .filter(
                    Ticket.id == ticket_id,
                    Ticket.company_id == self.company_id,
                )
                .with_for_update(skip_locked=True)
                .first()
            )

            if not ticket:
                raise NotFoundError(f"Ticket {ticket_id} not found")

            read_version = ticket.version or 1
            old_status = ticket.status

            # Track status change
            if status and status != old_status:
                self._validate_status_transition(old_status, status)
                self._record_status_change(
                    ticket_id, old_status, status, user_id, reason
                )

            # 2. Build update values
            update_values: Dict[str, Any] = {
                "version": read_version + 1,
                "updated_at": datetime.now(timezone.utc),
            }

            if priority is not None:
                update_values["priority"] = priority

            if category is not None:
                update_values["category"] = category

            if tags is not None:
                update_values["tags"] = json.dumps(tags)

            if status is not None:
                update_values["status"] = status
                if status == TicketStatus.closed.value:
                    update_values["closed_at"] = datetime.now(timezone.utc)
                elif status == TicketStatus.reopened.value:
                    update_values["reopen_count"] = (ticket.reopen_count or 0) + 1

            if assigned_to is not None:
                update_values["assigned_to"] = assigned_to

            if subject is not None:
                update_values["subject"] = subject

            # 3. Optimistic locking: UPDATE WHERE version = read_version
            result = self.db.execute(
                sa_update(Ticket.__table__)
                .where(
                    Ticket.id == ticket_id,
                    Ticket.company_id == self.company_id,
                    Ticket.version == read_version,
                )
                .values(**update_values)
            )

            if result.rowcount == 0:
                # Version mismatch — another process updated the row
                last_error = ConflictError(
                    message=(
                        f"Ticket {ticket_id} was modified by another process "
                        f"(expected version {read_version}). "
                        f"Attempt {attempt + 1}/{retry_count + 1}."
                    ),
                    details={
                        "ticket_id": ticket_id,
                        "expected_version": read_version,
                        "attempt": attempt + 1,
                        "max_retries": retry_count,
                    },
                )
                self.db.rollback()
                if attempt < retry_count:
                    backoff = 0.05 * (2**attempt)  # 50ms, 100ms, 200ms
                    time.sleep(backoff)
                continue

            # Success — commit and refresh
            self.db.commit()
            self.db.refresh(ticket)
            return ticket

        # All retries exhausted
        raise last_error  # type: ignore[misc]

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

        Uses optimistic locking to prevent race conditions.

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
            ConflictError: If version mismatch after retries
        """
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        read_version = ticket.version or 1
        previous_assignee = ticket.assigned_to

        # Update ticket
        update_values: Dict[str, Any] = {
            "assigned_to": assignee_id,
            "updated_at": datetime.now(timezone.utc),
            "version": read_version + 1,
        }

        # If assigning, update status
        if assignee_id and ticket.status == TicketStatus.open.value:
            update_values["status"] = TicketStatus.assigned.value

        # Optimistic locking: UPDATE WHERE version = read_version
        result = self.db.execute(
            sa_update(Ticket.__table__)
            .where(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
                Ticket.version == read_version,
            )
            .values(**update_values)
        )

        if result.rowcount == 0:
            self.db.rollback()
            raise ConflictError(
                message=(
                    f"Ticket {ticket_id} was modified by another process "
                    f"during assignment (expected version {read_version})."
                ),
                details={
                    "ticket_id": ticket_id,
                    "expected_version": read_version,
                },
            )

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

        .. note::
            This currently uses an **in-memory** counter because
            ``RateLimitService()`` is instantiated without a Redis
            client.  In multi-worker deployments this means the limit
            is per-process and can be bypassed.  When Redis is
            available, inject a Redis client into the service so that
            ``_check_redis`` is used instead of ``_check_in_memory``.

        TODO(M2): Inject Redis client — e.g. use the shared
        ``get_rate_limit_service()`` singleton which is configured
        centrally, or pass a Redis connection via ``TicketService.__init__``.

        Args:
            identifier: User ID or customer ID

        Raises:
            AuthorizationError: If rate limited
        """
        key = f"ticket_create:{self.company_id}:{identifier}"

        # Use existing rate limit service
        allowed = self.rate_limit_service.check_rate_limit(
            key=key,
            max_requests=self.RATE_LIMIT_MAX_TICKETS,
            window_seconds=self.RATE_LIMIT_WINDOW,
        )

        if not allowed:
            raise AuthorizationError("Rate limit exceeded. Please try again later.")

    def _check_account_suspended(self) -> None:
        """PS07: Check if account is suspended.

        Raises:
            AuthorizationError: If account is suspended
        """
        company = self.db.query(Company).filter(Company.id == self.company_id).first()

        if company and hasattr(company, "is_suspended") and company.is_suspended:
            raise AuthorizationError("Account is suspended. Cannot create new tickets.")

    def _validate_customer(self, customer_id: str) -> Customer:
        """Validate customer exists and belongs to company.

        Args:
            customer_id: Customer ID

        Returns:
            Customer object

        Raises:
            ValidationError: If customer not found
        """
        customer = (
            self.db.query(Customer)
            .filter(
                Customer.id == customer_id,
                Customer.company_id == self.company_id,
            )
            .first()
        )

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

        similar_tickets = (
            self.db.query(Ticket)
            .filter(
                Ticket.company_id == self.company_id,
                Ticket.customer_id == customer_id,
                Ticket.status.in_(
                    [
                        TicketStatus.open.value,
                        TicketStatus.assigned.value,
                        TicketStatus.in_progress.value,
                    ]
                ),
                Ticket.created_at >= recent_threshold,
            )
            .all()
        )

        for ticket in similar_tickets:
            if ticket.subject:
                similarity = self._calculate_similarity(
                    subject.lower(), ticket.subject.lower()
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
                failures.append(
                    {
                        "ticket_id": ticket_id,
                        "error": str(e),
                    }
                )

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
                failures.append(
                    {
                        "ticket_id": ticket_id,
                        "error": str(e),
                    }
                )

        return success_count, failures

    # ── SHADOW MODE TICKET METHODS ──────────────────────────────────────────

    def evaluate_ticket_shadow(
        self,
        ticket_id: str,
        action_type: str,
    ) -> Dict[str, Any]:
        """Evaluate if a ticket action should go through shadow mode.

        Uses ShadowModeService to evaluate risk based on action type and
        ticket metadata. Returns evaluation result with risk score and
        decision.

        BC-001: Scoped by company_id from instance.
        BC-008: Never crashes caller - defensive error handling.

        Args:
            ticket_id: Ticket ID to evaluate.
            action_type: Type of action (e.g., 'ticket_close', 'ticket_escalate').

        Returns:
            Dict with keys:
                - requires_approval: bool
                - risk_score: float (0.0-1.0)
                - mode: str ('shadow', 'supervised', 'graduated')
                - shadow_log_id: Optional[str] if logged
                - reason: str
                - error: Optional[str] if something went wrong
        """
        try:
            # Get ticket to extract context
            ticket = self.get_ticket(ticket_id)

            # Build action payload with ticket context
            action_payload = {
                "ticket_id": ticket_id,
                "ticket_status": ticket.status,
                "ticket_priority": ticket.priority,
                "ticket_category": ticket.category,
                "reopen_count": ticket.reopen_count,
                "escalation_level": ticket.escalation_level,
                "sla_breached": ticket.sla_breached,
            }

            # Use ShadowModeService to evaluate
            shadow_service = ShadowModeService()
            result = shadow_service.evaluate_action_risk(
                company_id=self.company_id,
                action_type=action_type,
                action_payload=action_payload,
            )

            return {
                "requires_approval": result.get("requires_approval", True),
                "risk_score": result.get("risk_score", 0.5),
                "mode": result.get("mode", "supervised"),
                "shadow_log_id": None,  # Not logged yet
                "reason": result.get("reason", ""),
                "layers": result.get("layers", {}),
                "auto_execute": result.get("auto_execute", False),
            }

        except NotFoundError:
            return {
                "requires_approval": True,
                "risk_score": 0.5,
                "mode": "supervised",
                "shadow_log_id": None,
                "reason": "Ticket not found - defaulting to supervised",
                "error": "Ticket not found",
                "auto_execute": False,
            }
        except Exception as e:
            # BC-008: Never crash the caller
            return {
                "requires_approval": True,
                "risk_score": 0.5,
                "mode": "supervised",
                "shadow_log_id": None,
                "reason": "Evaluation error - defaulting to supervised",
                "error": str(e),
                "auto_execute": False,
            }

    def resolve_ticket_with_shadow(
        self,
        ticket_id: str,
        manager_id: Optional[str] = None,
        resolution_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve a ticket, checking shadow mode first.

        If shadow mode requires approval:
            - Log action to shadow_log
            - Set ticket.shadow_status = 'pending_approval'
            - Return pending state

        If auto-execute (graduated mode, low risk):
            - Resolve ticket immediately
            - Log to shadow_log with auto_approved flag
            - Add to undo queue

        BC-001: Scoped by company_id.
        BC-008: Never crashes caller.

        Args:
            ticket_id: Ticket ID to resolve.
            manager_id: Optional manager ID for audit.
            resolution_note: Optional note for the resolution.

        Returns:
            Dict with resolution status and shadow details.
        """
        try:
            # Evaluate shadow mode
            evaluation = self.evaluate_ticket_shadow(
                ticket_id=ticket_id,
                action_type="ticket_close",
            )

            ticket = self.get_ticket(ticket_id)

            # Check if ticket can be resolved
            if ticket.status not in [
                TicketStatus.in_progress.value,
                TicketStatus.resolved.value,
                TicketStatus.awaiting_client.value,
                TicketStatus.awaiting_human.value,
            ]:
                return {
                    "success": False,
                    "error": f"Cannot resolve ticket in status: {
                        ticket.status}",
                    "ticket_id": ticket_id,
                }

            shadow_service = ShadowModeService()

            if evaluation["requires_approval"] and not evaluation.get("auto_execute"):
                # Log to shadow_log and set pending
                log_result = shadow_service.log_shadow_action(
                    company_id=self.company_id,
                    action_type="ticket_close",
                    action_payload={
                        "ticket_id": ticket_id,
                        "resolution_note": resolution_note,
                        "manager_id": manager_id,
                    },
                    risk_score=evaluation["risk_score"],
                    mode=evaluation["mode"],
                )

                # Update ticket shadow status
                ticket.shadow_status = "pending_approval"
                ticket.shadow_log_id = log_result.get("id")
                ticket.risk_score = evaluation["risk_score"]
                ticket.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(ticket)

                return {
                    "success": True,
                    "resolved": False,
                    "pending_approval": True,
                    "ticket_id": ticket_id,
                    "shadow_log_id": log_result.get("id"),
                    "risk_score": evaluation["risk_score"],
                    "mode": evaluation["mode"],
                    "message": "Resolution pending manager approval",
                }

            else:
                # Auto-execute: resolve immediately
                old_status = ticket.status
                ticket.status = TicketStatus.resolved.value
                ticket.shadow_status = "auto_approved"
                ticket.risk_score = evaluation["risk_score"]
                ticket.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(ticket)

                # Record status change
                self._record_status_change(
                    ticket_id=ticket_id,
                    from_status=old_status,
                    to_status=TicketStatus.resolved.value,
                    user_id=manager_id,
                    reason=f"Auto-approved resolution: {resolution_note or 'No note'}",
                )

                # Log auto-approval
                log_result = shadow_service.log_shadow_action(
                    company_id=self.company_id,
                    action_type="ticket_close",
                    action_payload={
                        "ticket_id": ticket_id,
                        "resolution_note": resolution_note,
                        "auto_approved": True,
                    },
                    risk_score=evaluation["risk_score"],
                    mode="graduated",
                )

                # Approve the logged action automatically
                shadow_service.approve_shadow_action(
                    shadow_log_id=log_result.get("id"),
                    manager_id=manager_id or "system",
                    note="Auto-approved in graduated mode",
                )

                return {
                    "success": True,
                    "resolved": True,
                    "pending_approval": False,
                    "ticket_id": ticket_id,
                    "shadow_log_id": log_result.get("id"),
                    "risk_score": evaluation["risk_score"],
                    "mode": evaluation["mode"],
                    "message": "Ticket resolved (auto-approved)",
                }

        except NotFoundError:
            return {
                "success": False,
                "error": "Ticket not found",
                "ticket_id": ticket_id,
            }
        except Exception as e:
            # BC-008: Never crash caller
            return {
                "success": False,
                "error": str(e),
                "ticket_id": ticket_id,
            }

    def approve_ticket_resolution(
        self,
        ticket_id: str,
        manager_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a pending shadow ticket resolution.

        Updates ticket.shadow_status to 'approved', sets approved_by and
        approved_at, executes the actual resolution, and calls
        ShadowModeService.approve_shadow_action().

        BC-001: Scoped by company_id.
        BC-008: Never crashes caller.

        Args:
            ticket_id: Ticket ID to approve.
            manager_id: Manager ID approving the resolution.
            note: Optional approval note.

        Returns:
            Dict with approval status and ticket details.
        """
        try:
            ticket = self.get_ticket(ticket_id)

            # Verify ticket is pending approval
            if ticket.shadow_status != "pending_approval":
                return {
                    "success": False,
                    "error": f"Ticket is not pending approval. Current status: {
                        ticket.shadow_status}",
                    "ticket_id": ticket_id,
                }

            if not ticket.shadow_log_id:
                return {
                    "success": False,
                    "error": "No shadow log entry found for this ticket",
                    "ticket_id": ticket_id,
                }

            # Update ticket
            old_status = ticket.status
            ticket.shadow_status = "approved"
            ticket.approved_by = manager_id
            ticket.approved_at = datetime.now(timezone.utc)
            ticket.status = TicketStatus.resolved.value
            ticket.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(ticket)

            # Record status change
            self._record_status_change(
                ticket_id=ticket_id,
                from_status=old_status,
                to_status=TicketStatus.resolved.value,
                user_id=manager_id,
                reason=f"Manager approved: {note or 'No note'}",
            )

            # Approve in ShadowModeService
            shadow_service = ShadowModeService()
            shadow_result = shadow_service.approve_shadow_action(
                shadow_log_id=ticket.shadow_log_id,
                manager_id=manager_id,
                note=note,
            )

            return {
                "success": True,
                "ticket_id": ticket_id,
                "shadow_status": "approved",
                "approved_by": manager_id,
                "approved_at": (
                    ticket.approved_at.isoformat() if ticket.approved_at else None
                ),
                "shadow_log": shadow_result,
                "message": "Ticket resolution approved",
            }

        except NotFoundError:
            return {
                "success": False,
                "error": "Ticket not found",
                "ticket_id": ticket_id,
            }
        except Exception as e:
            # BC-008: Never crash caller
            return {
                "success": False,
                "error": str(e),
                "ticket_id": ticket_id,
            }

    def undo_ticket_resolution(
        self,
        ticket_id: str,
        reason: str,
        manager_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Undo a previously approved ticket resolution.

        Sets ticket.shadow_status to 'undone', reopens the ticket, and
        calls ShadowModeService.undo_auto_approved_action().

        BC-001: Scoped by company_id.
        BC-008: Never crashes caller.

        Args:
            ticket_id: Ticket ID to undo.
            reason: Reason for the undo.
            manager_id: Optional manager ID requesting undo.

        Returns:
            Dict with undo status and ticket details.
        """
        try:
            ticket = self.get_ticket(ticket_id)

            # Verify ticket was resolved (approved or auto_approved)
            if ticket.shadow_status not in ["approved", "auto_approved"]:
                return {
                    "success": False,
                    "error": f"Ticket is not in an approved state. Current status: {
                        ticket.shadow_status}",
                    "ticket_id": ticket_id,
                }

            if not ticket.shadow_log_id:
                return {
                    "success": False,
                    "error": "No shadow log entry found for this ticket",
                    "ticket_id": ticket_id,
                }

            # Update ticket
            old_status = ticket.status
            ticket.shadow_status = "undone"
            ticket.status = TicketStatus.reopened.value
            ticket.reopen_count = (ticket.reopen_count or 0) + 1
            ticket.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(ticket)

            # Record status change
            self._record_status_change(
                ticket_id=ticket_id,
                from_status=old_status,
                to_status=TicketStatus.reopened.value,
                user_id=manager_id,
                reason=f"Undo resolution: {reason}",
            )

            # Undo in ShadowModeService
            shadow_service = ShadowModeService()
            undo_result = shadow_service.undo_auto_approved_action(
                shadow_log_id=ticket.shadow_log_id,
                reason=reason,
                manager_id=manager_id,
            )

            return {
                "success": True,
                "ticket_id": ticket_id,
                "shadow_status": "undone",
                "ticket_status": TicketStatus.reopened.value,
                "undo_log": undo_result,
                "message": "Ticket resolution undone",
            }

        except NotFoundError:
            return {
                "success": False,
                "error": "Ticket not found",
                "ticket_id": ticket_id,
            }
        except Exception as e:
            # BC-008: Never crash caller
            return {
                "success": False,
                "error": str(e),
                "ticket_id": ticket_id,
            }

    def get_ticket_shadow_details(
        self,
        ticket_id: str,
    ) -> Dict[str, Any]:
        """Get shadow mode details for a ticket.

        Returns ticket's shadow status, risk score, approval info, and
        related shadow log entry.

        BC-001: Scoped by company_id.
        BC-008: Never crashes caller.

        Args:
            ticket_id: Ticket ID to get details for.

        Returns:
            Dict with shadow mode details.
        """
        try:
            ticket = self.get_ticket(ticket_id)

            result = {
                "ticket_id": ticket_id,
                "shadow_status": ticket.shadow_status or "none",
                "risk_score": float(ticket.risk_score) if ticket.risk_score else None,
                "approved_by": ticket.approved_by,
                "approved_at": (
                    ticket.approved_at.isoformat() if ticket.approved_at else None
                ),
                "shadow_log_id": ticket.shadow_log_id,
            }

            # Fetch shadow log entry if exists
            if ticket.shadow_log_id:
                shadow_log = (
                    self.db.query(ShadowLog)
                    .filter(
                        ShadowLog.id == ticket.shadow_log_id,
                    )
                    .first()
                )

                if shadow_log:
                    result["shadow_log"] = {
                        "id": shadow_log.id,
                        "action_type": shadow_log.action_type,
                        "mode": shadow_log.mode,
                        "risk_score": shadow_log.jarvis_risk_score,
                        "manager_decision": shadow_log.manager_decision,
                        "manager_note": shadow_log.manager_note,
                        "resolved_at": (
                            shadow_log.resolved_at.isoformat()
                            if shadow_log.resolved_at
                            else None
                        ),
                        "created_at": (
                            shadow_log.created_at.isoformat()
                            if shadow_log.created_at
                            else None
                        ),
                    }

            return result

        except NotFoundError:
            return {
                "ticket_id": ticket_id,
                "error": "Ticket not found",
            }
        except Exception as e:
            # BC-008: Never crash caller
            return {
                "ticket_id": ticket_id,
                "error": str(e),
            }
