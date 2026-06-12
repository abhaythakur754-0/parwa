"""
PARWA Cross-Channel Customer Recognition Service (Phase 8)

Implements:
- Customer identity matching by email/phone across channels (Gap C)
- Unified conversation thread view across all channels
- AI context carries across channels (conversation history follows customer)

Gap C: "Sarah emails + chats about same refund → 2 separate conversations"
Fix: Match by email/phone → unified thread → AI sees full context

This service extends the existing IdentityResolutionService with:
1. Unified thread retrieval — all tickets/messages for a customer across channels
2. Cross-channel AI context — conversation summary that follows the customer
3. Channel-aware resolution — recognize same customer across email, chat, SMS, voice

BC-001: All queries scoped by company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from app.logger import get_logger
from app.services.customer_service import CustomerService
from app.services.identity_resolution_service import IdentityResolutionService
from database.models.tickets import (
    Customer,
    CustomerChannel,
    IdentityMatchLog,
    Ticket,
    TicketMessage,
    TicketStatus,
)

logger = get_logger("cross_channel")


class CrossChannelService:
    """Cross-channel customer recognition and unified thread service.

    Provides the "single customer view" across all communication channels.
    When Sarah emails about a refund and then chats about the same refund,
    this service ensures the AI sees both conversations as one thread.

    Usage:
        svc = CrossChannelService(db, company_id="acme")

        # Resolve identity from any channel input
        identity = await svc.resolve_from_channel(
            channel_type="email",
            identifier="sarah@example.com",
            channel_data={"subject": "Refund for order #123"}
        )

        # Get unified thread for a customer
        thread = svc.get_unified_thread(customer_id="...")

        # Get AI context (conversation summary across channels)
        context = svc.get_cross_channel_context(customer_id="...")
    """

    # Channel type to CustomerChannel type mapping
    CHANNEL_TYPE_MAP = {
        "email": "email",
        "chat": "webchat",
        "sms": "phone",
        "voice": "phone",
        "whatsapp": "whatsapp",
        "messenger": "messenger",
        "telegram": "telegram",
        "twitter": "twitter",
        "slack": "slack",
    }

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self.customer_service = CustomerService(db, company_id)
        self.identity_service = IdentityResolutionService(db, company_id)

    # ── CHANNEL-BASED IDENTITY RESOLUTION ────────────────────────────────

    def resolve_from_channel(
        self,
        channel_type: str,
        identifier: str,
        channel_data: Optional[Dict[str, Any]] = None,
        auto_create: bool = True,
    ) -> Dict[str, Any]:
        """Resolve customer identity from a channel-specific identifier.

        This is the PRIMARY entry point when a new message comes in from
        any channel. It:
        1. Checks if the identifier matches an existing customer channel
        2. If not, tries to match by email/phone
        3. If still no match, creates a new customer with the channel linked

        Args:
            channel_type: The channel the message came from (email, chat, sms, etc.)
            identifier: The customer's identifier on that channel
                       (email address, phone number, social handle, etc.)
            channel_data: Optional metadata about the channel interaction
            auto_create: Whether to create a new customer if no match

        Returns:
            Dict with customer_id, match_method, confidence, channels
        """
        normalized_channel = self.CHANNEL_TYPE_MAP.get(
            channel_type.lower(), channel_type.lower()
        )

        # Step 1: Check for existing channel link
        existing_channel = self.db.query(CustomerChannel).filter(
            CustomerChannel.company_id == self.company_id,
            CustomerChannel.channel_type == normalized_channel,
            CustomerChannel.external_id == identifier,
        ).first()

        if existing_channel:
            customer = self.db.query(Customer).filter(
                Customer.id == existing_channel.customer_id,
                Customer.company_id == self.company_id,
            ).first()
            if customer:
                return {
                    "customer_id": customer.id,
                    "match_method": "channel_link",
                    "confidence_score": 1.0,
                    "action_taken": "matched",
                    "channels": self._get_customer_channels(customer.id),
                    "customer_name": customer.name,
                    "customer_email": customer.email,
                }

        # Step 2: Try identity resolution by email/phone
        # Smart detection: if the identifier looks like an email, try email matching
        # regardless of channel type (Gap C: same person on email + chat)
        import re as _re
        _email_pattern = _re.compile(r'^[^@]+@[^@]+\.[^@]+$')
        _looks_like_email = bool(_email_pattern.match(identifier))
        _looks_like_phone = identifier.startswith('+') or identifier.replace('-', '').replace(' ', '').isdigit()

        email = identifier if (channel_type == "email" or _looks_like_email) else None
        phone = identifier if (channel_type in ("sms", "voice") or (_looks_like_phone and not email)) else None
        social_id = identifier if channel_type in (
            "whatsapp", "messenger", "telegram", "twitter", "slack"
        ) else None

        result = self.identity_service.resolve_identity(
            email=email,
            phone=phone,
            social_id=social_id,
            auto_create=auto_create,
        )

        # Step 3: If we found/created a customer, link this channel
        customer_id = result.get("matched_customer_id")
        if customer_id:
            self._ensure_channel_link(
                customer_id, normalized_channel, identifier
            )

            # Get customer info
            customer = self.customer_service.get_customer(customer_id)
            result["channels"] = self._get_customer_channels(customer_id)
            result["customer_name"] = customer.name
            result["customer_email"] = customer.email

        return result

    # ── UNIFIED CONVERSATION THREAD ──────────────────────────────────────

    def get_unified_thread(
        self,
        customer_id: str,
        include_closed: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Get a unified conversation thread for a customer across ALL channels.

        Phase 8 requirement: "Unified conversation thread view"

        Returns all tickets and messages for a customer, organized as a
        single timeline regardless of which channel they came through.

        Args:
            customer_id: The customer ID
            include_closed: Whether to include closed/resolved tickets
            page: Page number
            page_size: Items per page

        Returns:
            Dict with customer info, tickets, and unified message timeline
        """
        customer = self.customer_service.get_customer(customer_id)

        # Get all tickets for this customer
        ticket_query = self.db.query(Ticket).filter(
            Ticket.customer_id == customer_id,
            Ticket.company_id == self.company_id,
        )

        if not include_closed:
            ticket_query = ticket_query.filter(
                Ticket.status.notin_([
                    TicketStatus.closed.value,
                    TicketStatus.resolved.value,
                ])
            )

        total_tickets = ticket_query.count()
        tickets = ticket_query.order_by(
            desc(Ticket.created_at)
        ).offset((page - 1) * page_size).limit(page_size).all()

        # Get all messages for these tickets in a single query
        ticket_ids = [t.id for t in tickets]
        messages = []
        if ticket_ids:
            messages = self.db.query(TicketMessage).filter(
                TicketMessage.ticket_id.in_(ticket_ids),
                TicketMessage.company_id == self.company_id,
            ).order_by(TicketMessage.created_at.desc()).all()

        # Build unified timeline
        timeline = self._build_unified_timeline(tickets, messages)

        # Get customer channels
        channels = self._get_customer_channels(customer_id)

        return {
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
            },
            "channels": channels,
            "total_tickets": total_tickets,
            "tickets": [
                {
                    "id": t.id,
                    "subject": t.subject,
                    "channel": t.channel,
                    "status": t.status,
                    "priority": t.priority,
                    "category": t.category,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tickets
            ],
            "timeline": timeline,
            "page": page,
            "page_size": page_size,
        }

    # ── CROSS-CHANNEL AI CONTEXT ─────────────────────────────────────────

    def get_cross_channel_context(
        self,
        customer_id: str,
        max_recent_messages: int = 20,
    ) -> Dict[str, Any]:
        """Get AI context that carries across channels for a customer.

        Phase 8 requirement: "AI context carries across channels"

        This provides the AI with:
        1. Customer profile and all linked channels
        2. Recent conversation history across ALL channels
        3. Active issues/topics from other channels
        4. Customer sentiment and interaction patterns

        This is what gets injected into the AI's system prompt when
        handling a new ticket from any channel.

        Args:
            customer_id: The customer ID
            max_recent_messages: How many recent messages to include

        Returns:
            Dict with customer context for AI prompt injection
        """
        customer = self.customer_service.get_customer(customer_id)
        channels = self._get_customer_channels(customer_id)

        # Get active tickets across all channels
        active_tickets = self.db.query(Ticket).filter(
            Ticket.customer_id == customer_id,
            Ticket.company_id == self.company_id,
            Ticket.status.notin_([
                TicketStatus.closed.value,
                TicketStatus.resolved.value,
                TicketStatus.frozen.value,
            ]),
        ).order_by(desc(Ticket.created_at)).all()

        # Get recent messages across all active tickets
        active_ticket_ids = [t.id for t in active_tickets]
        recent_messages = []
        if active_ticket_ids:
            recent_messages = self.db.query(TicketMessage).filter(
                TicketMessage.ticket_id.in_(active_ticket_ids),
                TicketMessage.company_id == self.company_id,
                TicketMessage.is_internal == False,
            ).order_by(desc(TicketMessage.created_at)).limit(
                max_recent_messages
            ).all()

        # Build conversation summary per channel
        channel_summaries = {}
        for ticket in active_tickets:
            channel = ticket.channel or "unknown"
            if channel not in channel_summaries:
                channel_summaries[channel] = []
            channel_summaries[channel].append({
                "ticket_id": ticket.id,
                "subject": ticket.subject,
                "status": ticket.status,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            })

        # Build the AI context
        context = {
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
            },
            "channels": channels,
            "active_tickets_count": len(active_tickets),
            "channel_summaries": channel_summaries,
            "recent_conversation": [
                {
                    "ticket_id": msg.ticket_id,
                    "role": msg.role,
                    "channel": msg.channel,
                    "content": msg.content[:500] if msg.content else "",
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in reversed(recent_messages)  # Chronological order
            ],
            # Quick context string for AI prompt injection
            "context_summary": self._build_context_summary(
                customer, channels, active_tickets
            ),
        }

        return context

    # ── CROSS-CHANNEL TICKET LINKING ─────────────────────────────────────

    def find_related_tickets(
        self,
        customer_id: str,
        subject: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Find tickets from other channels that might be related.

        When a new ticket comes in on one channel, this helps find
        existing tickets on other channels about the same issue.

        Args:
            customer_id: Customer ID
            subject: New ticket subject to match against
            keywords: Keywords to search for in existing tickets

        Returns:
            List of potentially related tickets from other channels
        """
        query = self.db.query(Ticket).filter(
            Ticket.customer_id == customer_id,
            Ticket.company_id == self.company_id,
            Ticket.status.notin_([
                TicketStatus.closed.value,
                TicketStatus.resolved.value,
            ]),
        )

        if subject:
            search_pattern = f"%{subject}%"
            query = query.filter(
                or_(
                    Ticket.subject.ilike(search_pattern),
                )
            )

        tickets = query.order_by(desc(Ticket.created_at)).limit(20).all()

        return [
            {
                "id": t.id,
                "subject": t.subject,
                "channel": t.channel,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ]

    # ── PRIVATE HELPERS ──────────────────────────────────────────────────

    def _ensure_channel_link(
        self,
        customer_id: str,
        channel_type: str,
        identifier: str,
    ) -> Optional[CustomerChannel]:
        """Ensure a channel is linked to a customer. Creates link if missing.

        Args:
            customer_id: Customer ID
            channel_type: Channel type (email, chat, sms, etc.)
            identifier: Customer's identifier on that channel

        Returns:
            CustomerChannel object (existing or new)
        """
        # Check if already linked
        existing = self.db.query(CustomerChannel).filter(
            CustomerChannel.customer_id == customer_id,
            CustomerChannel.company_id == self.company_id,
            CustomerChannel.channel_type == channel_type,
            CustomerChannel.external_id == identifier,
        ).first()

        if existing:
            return existing

        # Create new link
        try:
            channel = CustomerChannel(
                id=str(uuid.uuid4()),
                customer_id=customer_id,
                company_id=self.company_id,
                channel_type=channel_type,
                external_id=identifier,
                is_verified=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(channel)
            self.db.commit()
            self.db.refresh(channel)
            logger.info(
                "channel_auto_linked",
                extra={
                    "customer_id": customer_id,
                    "channel_type": channel_type,
                    "identifier": identifier[:50],
                },
            )
            return channel
        except Exception as exc:
            self.db.rollback()
            logger.warning(
                "channel_link_failed",
                extra={
                    "customer_id": customer_id,
                    "channel_type": channel_type,
                    "error": str(exc)[:200],
                },
            )
            return None

    def _get_customer_channels(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all channels linked to a customer."""
        channels = self.db.query(CustomerChannel).filter(
            CustomerChannel.customer_id == customer_id,
            CustomerChannel.company_id == self.company_id,
        ).all()

        return [
            {
                "id": ch.id,
                "channel_type": ch.channel_type,
                "external_id": ch.external_id,
                "is_verified": ch.is_verified,
            }
            for ch in channels
        ]

    def _build_unified_timeline(
        self,
        tickets: List[Ticket],
        messages: List[TicketMessage],
    ) -> List[Dict[str, Any]]:
        """Build a unified chronological timeline from tickets and messages."""
        timeline = []

        # Add tickets as timeline entries
        for ticket in tickets:
            timeline.append({
                "type": "ticket",
                "id": ticket.id,
                "subject": ticket.subject,
                "channel": ticket.channel,
                "status": ticket.status,
                "priority": ticket.priority,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            })

        # Add messages as timeline entries
        for msg in messages:
            timeline.append({
                "type": "message",
                "id": msg.id,
                "ticket_id": msg.ticket_id,
                "role": msg.role,
                "channel": msg.channel,
                "content": msg.content[:1000] if msg.content else "",
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        # Sort by created_at descending
        timeline.sort(
            key=lambda x: x.get("created_at") or "",
            reverse=True,
        )

        return timeline

    def _build_context_summary(
        self,
        customer: Customer,
        channels: List[Dict[str, Any]],
        active_tickets: List[Ticket],
    ) -> str:
        """Build a concise context summary for AI prompt injection.

        This is a natural language summary that gets added to the AI's
        system prompt so it knows the customer's cross-channel history.
        """
        parts = []

        # Customer identity
        name = customer.name or "Unknown"
        parts.append(f"Customer: {name}")

        if customer.email:
            parts.append(f"Email: {customer.email}")
        if customer.phone:
            parts.append(f"Phone: {customer.phone}")

        # Channels
        channel_names = [ch["channel_type"] for ch in channels]
        if channel_names:
            parts.append(f"Channels: {', '.join(channel_names)}")

        # Active issues
        if active_tickets:
            parts.append(f"Active tickets: {len(active_tickets)}")
            for ticket in active_tickets[:3]:  # Top 3 most recent
                ch = ticket.channel or "unknown"
                subj = ticket.subject or "No subject"
                status = ticket.status or "unknown"
                parts.append(f"  - [{ch}] {subj} ({status})")

        return "\n".join(parts)
