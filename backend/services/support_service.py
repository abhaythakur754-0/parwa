"""
Support Service Layer

Business logic for support ticket operations.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload

from backend.models.support_ticket import (
    SupportTicket,
    ChannelEnum,
    TicketStatusEnum,
    AITierEnum,
    SentimentEnum,
)
from backend.models.user import User
from backend.models.company import Company
from backend.models.audit_trail import AuditTrail
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

# SLA thresholds by channel (in hours)
SLA_THRESHOLDS = {
    ChannelEnum.chat: 1,
    ChannelEnum.email: 24,
    ChannelEnum.sms: 4,
    ChannelEnum.voice: 2,
}


class SupportService:
    """
    Service class for support ticket business logic.
    
    All methods enforce company-scoped data access (RLS).
    Provides ticket CRUD, escalation, messaging, and SLA tracking.
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize support service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def create_ticket(
        self,
        subject: str,
        description: str,
        customer_email: str,
        channel: ChannelEnum = ChannelEnum.email,
        category: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SupportTicket:
        """
        Create a new support ticket.
        
        Args:
            subject: Ticket subject line
            description: Initial ticket description/body
            customer_email: Customer email address
            channel: Communication channel (email, chat, sms, voice)
            category: Optional ticket category
            customer_id: Optional customer user UUID
            metadata: Optional additional metadata
            
        Returns:
            Created SupportTicket instance
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        if not subject or not subject.strip():
            raise ValueError("Subject is required")
        if not description or not description.strip():
            raise ValueError("Description is required")
        if not customer_email or not self._validate_email(customer_email):
            raise ValueError("Valid customer email is required")
        
        # Sanitize inputs
        subject = subject.strip()
        description = description.strip()
        customer_email = customer_email.lower().strip()
        
        # Create ticket
        ticket = SupportTicket(
            company_id=self.company_id,
            customer_email=customer_email,
            channel=channel,
            status=TicketStatusEnum.open,
            category=category.strip() if category else None,
            subject=subject,
            body=description,
        )
        
        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)
        
        # Log audit trail
        await self._log_audit(
            action="create",
            entity_type="ticket",
            entity_id=ticket.id,
            changes={
                "subject": subject,
                "channel": channel.value,
                "customer_email": customer_email,
            }
        )
        
        logger.info({
            "event": "ticket_created",
            "ticket_id": str(ticket.id),
            "company_id": str(self.company_id),
            "channel": channel.value,
        })
        
        return ticket
    
    async def get_ticket_by_id(self, ticket_id) -> Optional[SupportTicket]:
        """
        Get a ticket by ID with company scoping.
        
        Args:
            ticket_id: Ticket UUID (can be UUID or string)
            
        Returns:
            SupportTicket if found and belongs to company, None otherwise
        """
        # Handle invalid UUID strings
        if isinstance(ticket_id, str):
            try:
                ticket_id = UUID(ticket_id)
            except (ValueError, TypeError):
                return None
        
        if not isinstance(ticket_id, UUID):
            return None
        
        result = await self.db.execute(
            select(SupportTicket).where(
                and_(
                    SupportTicket.id == ticket_id,
                    SupportTicket.company_id == self.company_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_tickets(
        self,
        status: Optional[TicketStatusEnum] = None,
        channel: Optional[ChannelEnum] = None,
        assignee_id: Optional[UUID] = None,
        sentiment: Optional[SentimentEnum] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SupportTicket]:
        """
        List tickets with filtering and pagination.
        
        Args:
            status: Filter by status
            channel: Filter by channel
            assignee_id: Filter by assigned agent
            sentiment: Filter by sentiment
            limit: Max results to return (default 50, max 100)
            offset: Pagination offset
            
        Returns:
            List of SupportTicket instances
        """
        # Enforce limit
        limit = min(limit, 100)
        
        # Build query conditions
        conditions = [SupportTicket.company_id == self.company_id]
        
        if status:
            conditions.append(SupportTicket.status == status)
        if channel:
            conditions.append(SupportTicket.channel == channel)
        if assignee_id:
            conditions.append(SupportTicket.assigned_to == assignee_id)
        if sentiment:
            conditions.append(SupportTicket.sentiment == sentiment)
        
        query = select(SupportTicket).where(
            and_(*conditions)
        ).order_by(
            desc(SupportTicket.created_at)
        ).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_ticket(
        self,
        ticket_id: UUID,
        status: Optional[TicketStatusEnum] = None,
        category: Optional[str] = None,
        assignee_id: Optional[UUID] = None,
        ai_recommendation: Optional[str] = None,
        ai_confidence: Optional[float] = None,
        ai_tier: Optional[AITierEnum] = None,
        sentiment: Optional[SentimentEnum] = None
    ) -> Optional[SupportTicket]:
        """
        Update ticket fields.
        
        Args:
            ticket_id: Ticket UUID
            status: New status
            category: New category
            assignee_id: New assignee UUID
            ai_recommendation: AI-generated recommendation
            ai_confidence: AI confidence score (0.0-1.0)
            ai_tier: AI tier used for processing
            sentiment: Detected sentiment
            
        Returns:
            Updated SupportTicket if found, None otherwise
            
        Raises:
            ValueError: If ai_confidence is out of range
        """
        ticket = await self.get_ticket_by_id(ticket_id)
        if not ticket:
            return None
        
        changes: Dict[str, Any] = {}
        
        if status is not None and status != ticket.status:
            changes["status"] = {"old": ticket.status.value, "new": status.value}
            ticket.status = status
            
            # Set resolved_at if resolving
            if status == TicketStatusEnum.resolved:
                ticket.resolved_at = datetime.now(timezone.utc)
                changes["resolved_at"] = ticket.resolved_at.isoformat()
        
        if category is not None:
            changes["category"] = {"old": ticket.category, "new": category}
            ticket.category = category
        
        if assignee_id is not None:
            changes["assigned_to"] = {"old": str(ticket.assigned_to), "new": str(assignee_id)}
            ticket.assigned_to = assignee_id
        
        if ai_recommendation is not None:
            ticket.ai_recommendation = ai_recommendation
            changes["ai_recommendation"] = True
        
        if ai_confidence is not None:
            if not 0.0 <= ai_confidence <= 1.0:
                raise ValueError("ai_confidence must be between 0.0 and 1.0")
            ticket.ai_confidence = ai_confidence
            changes["ai_confidence"] = ai_confidence
        
        if ai_tier is not None:
            ticket.ai_tier_used = ai_tier
            changes["ai_tier"] = ai_tier.value
        
        if sentiment is not None:
            ticket.sentiment = sentiment
            changes["sentiment"] = sentiment.value
        
        await self.db.flush()
        await self.db.refresh(ticket)
        
        # Log audit trail
        if changes:
            await self._log_audit(
                action="update",
                entity_type="ticket",
                entity_id=ticket.id,
                changes=changes
            )
        
        logger.info({
            "event": "ticket_updated",
            "ticket_id": str(ticket_id),
            "company_id": str(self.company_id),
            "changes": list(changes.keys()),
        })
        
        return ticket
    
    async def escalate_ticket(
        self,
        ticket_id: UUID,
        reason: str,
        escalated_to_id: UUID
    ) -> Optional[SupportTicket]:
        """
        Escalate ticket to higher support tier.
        
        Args:
            ticket_id: Ticket UUID
            reason: Escalation reason
            escalated_to_id: User UUID to escalate to
            
        Returns:
            Updated SupportTicket with escalation info
            
        Raises:
            ValueError: If reason is empty or ticket not found
        """
        if not reason or not reason.strip():
            raise ValueError("Escalation reason is required")
        
        ticket = await self.get_ticket_by_id(ticket_id)
        if not ticket:
            return None
        
        old_status = ticket.status
        old_assignee = ticket.assigned_to
        
        # Update ticket
        ticket.status = TicketStatusEnum.escalated
        ticket.assigned_to = escalated_to_id
        
        await self.db.flush()
        await self.db.refresh(ticket)
        
        # Log audit trail
        await self._log_audit(
            action="escalate",
            entity_type="ticket",
            entity_id=ticket.id,
            changes={
                "reason": reason,
                "old_status": old_status.value,
                "new_status": TicketStatusEnum.escalated.value,
                "old_assignee": str(old_assignee) if old_assignee else None,
                "new_assignee": str(escalated_to_id),
            }
        )
        
        logger.info({
            "event": "ticket_escalated",
            "ticket_id": str(ticket_id),
            "company_id": str(self.company_id),
            "escalated_to": str(escalated_to_id),
            "reason": reason,
        })
        
        return ticket
    
    async def add_message(
        self,
        ticket_id: UUID,
        sender_id: UUID,
        message: str,
        is_internal: bool = False
    ) -> Dict[str, Any]:
        """
        Add a message to ticket conversation.
        
        Args:
            ticket_id: Ticket UUID
            sender_id: User UUID sending message
            message: Message content
            is_internal: Whether this is an internal note
            
        Returns:
            Dict with message details
            
        Raises:
            ValueError: If message is empty or ticket not found
        """
        if not message or not message.strip():
            raise ValueError("Message content is required")
        
        ticket = await self.get_ticket_by_id(ticket_id)
        if not ticket:
            raise ValueError("Ticket not found")
        
        message_id = uuid4()
        message_data = {
            "id": str(message_id),
            "ticket_id": str(ticket_id),
            "sender_id": str(sender_id),
            "message": message.strip(),
            "is_internal": is_internal,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Log audit trail
        await self._log_audit(
            action="add_message",
            entity_type="ticket_message",
            entity_id=message_id,
            changes={
                "ticket_id": str(ticket_id),
                "sender_id": str(sender_id),
                "is_internal": is_internal,
                "message_length": len(message),
            }
        )
        
        logger.info({
            "event": "ticket_message_added",
            "ticket_id": str(ticket_id),
            "company_id": str(self.company_id),
            "sender_id": str(sender_id),
            "is_internal": is_internal,
        })
        
        return message_data
    
    async def calculate_sla_status(
        self,
        ticket_id
    ) -> Dict[str, Any]:
        """
        Calculate SLA status for a ticket.
        
        Args:
            ticket_id: Ticket UUID
            
        Returns:
            Dict with SLA status info:
            - is_breached: bool
            - time_remaining_seconds: int
            - sla_deadline: str
            - sla_threshold_hours: int
        """
        ticket = await self.get_ticket_by_id(ticket_id)
        if not ticket:
            return {
                "is_breached": False,
                "time_remaining_seconds": 0,
                "sla_deadline": None,
                "sla_threshold_hours": 0,
                "error": "Ticket not found"
            }
        
        # Get SLA threshold based on channel
        threshold_hours = SLA_THRESHOLDS.get(ticket.channel, 24)
        
        # Calculate deadline
        sla_deadline = ticket.created_at + timedelta(hours=threshold_hours)
        
        # Check if breached
        now = datetime.now(timezone.utc)
        is_breached = now > sla_deadline
        
        # Calculate time remaining
        if is_breached:
            time_remaining = timedelta(0)
        else:
            time_remaining = sla_deadline - now
        
        return {
            "is_breached": is_breached,
            "time_remaining_seconds": int(time_remaining.total_seconds()),
            "sla_deadline": sla_deadline.isoformat(),
            "sla_threshold_hours": threshold_hours,
            "ticket_status": ticket.status.value,
        }
    
    async def get_ticket_count_by_status(self) -> Dict[str, int]:
        """
        Get count of tickets grouped by status.
        
        Returns:
            Dict mapping status string to count
        """
        result = await self.db.execute(
            select(
                SupportTicket.status,
                func.count(SupportTicket.id)
            ).where(
                SupportTicket.company_id == self.company_id
            ).group_by(
                SupportTicket.status
            )
        )
        
        counts = {status.value: 0 for status in TicketStatusEnum}
        for row in result:
            counts[row[0].value] = row[1]
        
        return counts
    
    async def assign_ticket(
        self,
        ticket_id: UUID,
        assignee_id: UUID
    ) -> Optional[SupportTicket]:
        """
        Assign a ticket to a user.
        
        Args:
            ticket_id: Ticket UUID
            assignee_id: User UUID to assign
            
        Returns:
            Updated SupportTicket if found, None otherwise
        """
        return await self.update_ticket(ticket_id, assignee_id=assignee_id)
    
    async def _log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        changes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log audit trail entry.
        
        Args:
            action: Action performed (create, update, escalate, etc.)
            entity_type: Entity type (ticket, message, etc.)
            entity_id: Entity UUID
            changes: Optional dict of changes
        """
        try:
            audit = AuditTrail(
                company_id=self.company_id,
                ticket_id=entity_id if entity_type == "ticket" else None,
                actor="support_service",
                action=action,
                details=changes or {},
            )
            audit.entry_hash = audit.compute_hash()
            
            self.db.add(audit)
            await self.db.flush()
        except Exception as e:
            # Don't fail the main operation if audit fails
            logger.error({
                "event": "audit_log_failed",
                "error": str(e),
                "action": action,
                "entity_id": str(entity_id),
            })
    
    def _validate_email(self, email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email string to validate
            
        Returns:
            True if valid, False otherwise
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
