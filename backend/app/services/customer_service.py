"""
PARWA Customer Service - Customer Management & Channel Linking (Day 30)

Implements F-070: Customer identity management with:
- Customer CRUD operations
- Channel linking/unlinking
- Customer merge functionality
- Customer ticket history
- PS14: Grandfathered tickets (plan snapshot at creation)

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from backend.app.exceptions import (
    NotFoundError,
    AuthorizationError,
    ValidationError,
)
from database.models.tickets import (
    Customer,
    CustomerChannel,
    CustomerMergeAudit,
    Ticket,
    TicketStatus,
)
from backend.app.schemas.customer import ChannelType


class CustomerService:
    """Customer management and channel linking operations."""

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── CUSTOMER CRUD ─────────────────────────────────────────────────────────

    def create_customer(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        external_id: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> Customer:
        """Create a new customer.

        Args:
            email: Customer email (normalized to lowercase)
            phone: Customer phone (normalized)
            name: Customer display name
            external_id: External system identifier
            metadata_json: Additional metadata

        Returns:
            Created Customer object

        Raises:
            ValidationError: If neither email nor phone provided
        """
        if not email and not phone:
            raise ValidationError("At least one of email or phone is required")

        # Normalize email
        if email:
            email = email.strip().lower()

        # Check for existing customer with same email/phone
        existing = self._find_existing_customer(email, phone)
        if existing:
            raise ValidationError(
                f"Customer already exists with matching identifier (ID: {existing.id})"
            )

        customer = Customer(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            email=email,
            phone=phone,
            name=name,
            external_id=external_id,
            metadata_json=json.dumps(metadata_json or {}),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)

        # If email provided, auto-link as email channel
        if email:
            self.link_channel(
                customer_id=customer.id,
                channel_type=ChannelType.EMAIL,
                external_id=email,
                is_verified=False,
            )

        # If phone provided, auto-link as phone channel
        if phone:
            self.link_channel(
                customer_id=customer.id,
                channel_type=ChannelType.PHONE,
                external_id=phone,
                is_verified=False,
            )

        return customer

    def get_customer(self, customer_id: str) -> Customer:
        """Get a customer by ID.

        Args:
            customer_id: Customer ID

        Returns:
            Customer object

        Raises:
            NotFoundError: If customer not found
        """
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.company_id == self.company_id,
        ).first()

        if not customer:
            raise NotFoundError(f"Customer {customer_id} not found")

        return customer

    def get_customer_by_email(self, email: str) -> Optional[Customer]:
        """Get a customer by email.

        Args:
            email: Customer email

        Returns:
            Customer object or None
        """
        return self.db.query(Customer).filter(
            Customer.company_id == self.company_id,
            func.lower(Customer.email) == email.strip().lower(),
        ).first()

    def get_customer_by_phone(self, phone: str) -> Optional[Customer]:
        """Get a customer by phone.

        Args:
            phone: Customer phone

        Returns:
            Customer object or None
        """
        # Normalize phone for comparison
        normalized = self._normalize_phone(phone)
        return self.db.query(Customer).filter(
            Customer.company_id == self.company_id,
            Customer.phone == normalized,
        ).first()

    def list_customers(
        self,
        search: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        external_id: Optional[str] = None,
        has_open_tickets: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Customer], int]:
        """List customers with filters and pagination.

        Args:
            search: Search query (name, email, phone)
            email: Filter by email
            phone: Filter by phone
            external_id: Filter by external ID
            has_open_tickets: Filter customers with open tickets
            page: Page number
            page_size: Items per page
            sort_by: Sort field
            sort_order: Sort direction

        Returns:
            Tuple of (customers list, total count)
        """
        query = self.db.query(Customer).filter(
            Customer.company_id == self.company_id
        )

        # Apply filters
        if email:
            query = query.filter(
                func.lower(Customer.email) == email.strip().lower()
            )

        if phone:
            normalized = self._normalize_phone(phone)
            query = query.filter(Customer.phone == normalized)

        if external_id:
            query = query.filter(Customer.external_id == external_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Customer.name.ilike(search_pattern),
                    Customer.email.ilike(search_pattern),
                    Customer.phone.ilike(search_pattern),
                )
            )

        if has_open_tickets is not None:
            # Subquery for customers with open tickets
            open_ticket_customers = self.db.query(Ticket.customer_id).filter(
                Ticket.company_id == self.company_id,
                Ticket.status.in_([
                    TicketStatus.open.value,
                    TicketStatus.assigned.value,
                    TicketStatus.in_progress.value,
                    TicketStatus.awaiting_client.value,
                    TicketStatus.awaiting_human.value,
                ]),
            ).distinct()

            if has_open_tickets:
                query = query.filter(Customer.id.in_(open_ticket_customers))
            else:
                query = query.filter(~Customer.id.in_(open_ticket_customers))

        # Count total
        total = query.count()

        # Sort
        sort_column = getattr(Customer, sort_by, Customer.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # Paginate
        offset = (page - 1) * page_size
        customers = query.offset(offset).limit(page_size).all()

        return customers, total

    def update_customer(
        self,
        customer_id: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        external_id: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> Customer:
        """Update customer fields.

        Args:
            customer_id: Customer ID
            email: New email
            phone: New phone
            name: New name
            external_id: New external ID
            metadata_json: New metadata

        Returns:
            Updated Customer object

        Raises:
            NotFoundError: If customer not found
            ValidationError: If email/phone already exists for another customer
        """
        customer = self.get_customer(customer_id)

        # Check for conflicts
        if email is not None and email != customer.email:
            existing = self.get_customer_by_email(email)
            if existing and existing.id != customer_id:
                raise ValidationError("Email already in use by another customer")

        if phone is not None and phone != customer.phone:
            existing = self.get_customer_by_phone(phone)
            if existing and existing.id != customer_id:
                raise ValidationError("Phone already in use by another customer")

        # Update fields
        if email is not None:
            customer.email = email.strip().lower()

        if phone is not None:
            customer.phone = self._normalize_phone(phone)

        if name is not None:
            customer.name = name

        if external_id is not None:
            customer.external_id = external_id

        if metadata_json is not None:
            customer.metadata_json = json.dumps(metadata_json)

        customer.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(customer)

        return customer

    def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer (soft delete by anonymizing).

        Args:
            customer_id: Customer ID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If customer not found
            ValidationError: If customer has open tickets
        """
        customer = self.get_customer(customer_id)

        # Check for open tickets
        open_tickets = self.db.query(Ticket).filter(
            Ticket.customer_id == customer_id,
            Ticket.company_id == self.company_id,
            Ticket.status.in_([
                TicketStatus.open.value,
                TicketStatus.assigned.value,
                TicketStatus.in_progress.value,
            ]),
        ).count()

        if open_tickets > 0:
            raise ValidationError(
                f"Cannot delete customer with {open_tickets} open tickets"
            )

        # Anonymize instead of hard delete
        customer.email = None
        customer.phone = None
        customer.name = "[DELETED]"
        customer.metadata_json = json.dumps({"deleted": True})
        customer.updated_at = datetime.utcnow()

        self.db.commit()

        return True

    # ── CHANNEL LINKING ────────────────────────────────────────────────────────

    def link_channel(
        self,
        customer_id: str,
        channel_type: ChannelType,
        external_id: str,
        is_verified: bool = False,
    ) -> CustomerChannel:
        """Link a communication channel to a customer.

        Args:
            customer_id: Customer ID
            channel_type: Type of channel
            external_id: External identifier (email, phone, social handle)
            is_verified: Whether the channel is verified

        Returns:
            Created CustomerChannel object

        Raises:
            NotFoundError: If customer not found
            ValidationError: If channel already linked
        """
        customer = self.get_customer(customer_id)

        # Check if already linked
        existing = self.db.query(CustomerChannel).filter(
            CustomerChannel.company_id == self.company_id,
            CustomerChannel.channel_type == channel_type.value,
            CustomerChannel.external_id == external_id,
        ).first()

        if existing:
            raise ValidationError(
                f"Channel {channel_type.value}:{external_id} already linked"
            )

        channel = CustomerChannel(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            company_id=self.company_id,
            channel_type=channel_type.value,
            external_id=external_id,
            is_verified=is_verified,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)

        return channel

    def unlink_channel(
        self,
        customer_id: str,
        channel_id: str,
    ) -> bool:
        """Unlink a channel from a customer.

        Args:
            customer_id: Customer ID
            channel_id: Channel ID to unlink

        Returns:
            True if unlinked

        Raises:
            NotFoundError: If channel not found
        """
        channel = self.db.query(CustomerChannel).filter(
            CustomerChannel.id == channel_id,
            CustomerChannel.customer_id == customer_id,
            CustomerChannel.company_id == self.company_id,
        ).first()

        if not channel:
            raise NotFoundError(f"Channel {channel_id} not found")

        self.db.delete(channel)
        self.db.commit()

        return True

    def get_customer_channels(self, customer_id: str) -> List[CustomerChannel]:
        """Get all channels linked to a customer.

        Args:
            customer_id: Customer ID

        Returns:
            List of CustomerChannel objects
        """
        return self.db.query(CustomerChannel).filter(
            CustomerChannel.customer_id == customer_id,
            CustomerChannel.company_id == self.company_id,
        ).all()

    def verify_channel(
        self,
        customer_id: str,
        channel_id: str,
    ) -> CustomerChannel:
        """Mark a channel as verified.

        Args:
            customer_id: Customer ID
            channel_id: Channel ID

        Returns:
            Updated CustomerChannel object
        """
        channel = self.db.query(CustomerChannel).filter(
            CustomerChannel.id == channel_id,
            CustomerChannel.customer_id == customer_id,
            CustomerChannel.company_id == self.company_id,
        ).first()

        if not channel:
            raise NotFoundError(f"Channel {channel_id} not found")

        channel.is_verified = True
        channel.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(channel)

        return channel

    # ── CUSTOMER TICKETS ───────────────────────────────────────────────────────

    def get_customer_tickets(
        self,
        customer_id: str,
        status: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Ticket], int]:
        """Get tickets for a customer.

        Args:
            customer_id: Customer ID
            status: Filter by status list
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (tickets list, total count)
        """
        query = self.db.query(Ticket).filter(
            Ticket.customer_id == customer_id,
            Ticket.company_id == self.company_id,
        )

        if status:
            query = query.filter(Ticket.status.in_(status))

        total = query.count()
        tickets = query.order_by(desc(Ticket.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return tickets, total

    # ── CUSTOMER MERGE ─────────────────────────────────────────────────────────

    def merge_customers(
        self,
        primary_customer_id: str,
        merged_customer_ids: List[str],
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Customer:
        """Merge multiple customers into one.

        Args:
            primary_customer_id: ID of the primary (surviving) customer
            merged_customer_ids: IDs of customers to merge
            reason: Reason for merge
            user_id: ID of user performing merge

        Returns:
            Primary Customer object

        Raises:
            NotFoundError: If any customer not found
            ValidationError: If merge is invalid
        """
        # Validate primary exists
        primary = self.get_customer(primary_customer_id)

        # Validate merged customers
        if primary_customer_id in merged_customer_ids:
            raise ValidationError("Primary customer cannot be in merged list")

        if len(merged_customer_ids) != len(set(merged_customer_ids)):
            raise ValidationError("Duplicate customer IDs in merged list")

        merged_customers = []
        for cid in merged_customer_ids:
            customer = self.get_customer(cid)
            merged_customers.append(customer)

        # Collect all data to merge
        merged_emails = [c.email for c in merged_customers if c.email]
        merged_phones = [c.phone for c in merged_customers if c.phone]
        merged_metadata = [json.loads(c.metadata_json or "{}") for c in merged_customers]

        # Update primary with merged data
        primary_metadata = json.loads(primary.metadata_json or "{}")
        primary_metadata["merged"] = {
            "emails": list(set(merged_emails + ([primary.email] if primary.email else []))),
            "phones": list(set(merged_phones + ([primary.phone] if primary.phone else []))),
            "merged_at": datetime.utcnow().isoformat(),
            "merged_customer_ids": merged_customer_ids,
        }
        primary.metadata_json = json.dumps(primary_metadata)
        primary.updated_at = datetime.utcnow()

        # Reassign tickets to primary
        for cid in merged_customer_ids:
            self.db.query(Ticket).filter(
                Ticket.customer_id == cid,
                Ticket.company_id == self.company_id,
            ).update({"customer_id": primary_customer_id})

            # Reassign channels
            self.db.query(CustomerChannel).filter(
                CustomerChannel.customer_id == cid,
                CustomerChannel.company_id == self.company_id,
            ).update({"customer_id": primary_customer_id})

        # Soft delete merged customers
        for customer in merged_customers:
            customer.email = None
            customer.phone = None
            customer.name = f"[MERGED INTO {primary_customer_id}]"
            customer.metadata_json = json.dumps({
                "merged_into": primary_customer_id,
                "merged_at": datetime.utcnow().isoformat(),
            })

        # Create audit record
        audit = CustomerMergeAudit(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            primary_customer_id=primary_customer_id,
            merged_customer_ids=json.dumps(merged_customer_ids),
            merged_by=user_id,
            action_type="merge_reason",
            reason=reason,
            created_at=datetime.utcnow(),
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(primary)

        return primary

    # ── PRIVATE HELPERS ────────────────────────────────────────────────────────

    def _find_existing_customer(
        self,
        email: Optional[str],
        phone: Optional[str],
    ) -> Optional[Customer]:
        """Find existing customer with matching email or phone.

        Args:
            email: Email to check
            phone: Phone to check

        Returns:
            Customer if found, None otherwise
        """
        if email:
            existing = self.get_customer_by_email(email)
            if existing:
                return existing

        if phone:
            existing = self.get_customer_by_phone(phone)
            if existing:
                return existing

        return None

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison.

        Args:
            phone: Phone number

        Returns:
            Normalized phone number
        """
        # Remove common formatting characters
        import re
        return re.sub(r"[\s\-\(\)]", "", phone.strip())
