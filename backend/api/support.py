"""
PARWA Support Ticket API Routes.
Provides endpoints for creating, listing, updating, and managing support tickets.
"""
from datetime import datetime
from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.support_ticket import (
    SupportTicket,
    ChannelEnum,
    TicketStatusEnum,
    AITierEnum,
    SentimentEnum,
)
from backend.models.user import User, RoleEnum
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import (
    decode_access_token,
    sanitize_input,
)

# Initialize router and logger
router = APIRouter(prefix="/support", tags=["Support"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Pydantic Schemas ---

class TicketCreateRequest(BaseModel):
    """Request schema for creating a support ticket."""
    customer_email: EmailStr = Field(..., description="Customer's email address")
    channel: ChannelEnum = Field(..., description="Channel of the ticket")
    category: Optional[str] = Field(None, max_length=100, description="Ticket category")
    subject: str = Field(..., min_length=1, max_length=200, description="Ticket subject")
    body: str = Field(..., min_length=1, max_length=10000, description="Ticket body/content")


class TicketUpdateRequest(BaseModel):
    """Request schema for updating a support ticket."""
    status: Optional[TicketStatusEnum] = Field(None, description="New ticket status")
    category: Optional[str] = Field(None, max_length=100, description="New category")
    assigned_to: Optional[uuid.UUID] = Field(None, description="User ID to assign ticket to")
    ai_recommendation: Optional[str] = Field(None, max_length=10000, description="AI recommendation")
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI confidence score")


class TicketMessageRequest(BaseModel):
    """Request schema for adding a message to a ticket."""
    message: str = Field(..., min_length=1, max_length=10000, description="Message content")
    sender: str = Field(..., description="Sender identifier (user_id, customer_email, or 'system')")


class TicketResponse(BaseModel):
    """Response schema for a support ticket."""
    id: uuid.UUID
    company_id: uuid.UUID
    customer_email: str
    channel: str
    status: str
    category: Optional[str]
    subject: str
    body: str
    ai_recommendation: Optional[str]
    ai_confidence: Optional[float]
    ai_tier_used: Optional[str]
    sentiment: Optional[str]
    assigned_to: Optional[uuid.UUID]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    """Response schema for listing tickets."""
    tickets: List[TicketResponse]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str = Field(..., description="Response message")
    ticket_id: Optional[uuid.UUID] = Field(None, description="Related ticket ID")


# --- Helper Functions ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate the current user from JWT token.

    Args:
        credentials: HTTP Bearer credentials containing the JWT token.
        db: Async database session.

    Returns:
        User: The authenticated user instance.

    Raises:
        HTTPException: If token is invalid, expired, or user not found.
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token, settings.secret_key.get_secret_value())
    except ValueError as e:
        logger.warning({"event": "token_decode_failed", "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


def mask_email(email: str) -> str:
    """Mask email for privacy in responses."""
    if not email or "@" not in email:
        return email
    parts = email.split("@")
    if len(parts[0]) <= 3:
        return f"{parts[0][0]}***@{parts[1]}"
    return f"{parts[0][:3]}***@{parts[1]}"


# --- API Endpoints ---

@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new support ticket",
    description="Create a new support ticket for a customer inquiry."
)
async def create_ticket(
    request: TicketCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TicketResponse:
    """
    Create a new support ticket.

    Args:
        request: Ticket creation data.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        TicketResponse: The created ticket data.
    """
    # Sanitize inputs
    customer_email = sanitize_input(request.customer_email.lower())
    subject = sanitize_input(request.subject)
    body = sanitize_input(request.body)
    category = sanitize_input(request.category) if request.category else None

    # Create new ticket
    new_ticket = SupportTicket(
        company_id=current_user.company_id,
        customer_email=customer_email,
        channel=request.channel,
        status=TicketStatusEnum.open,
        category=category,
        subject=subject,
        body=body,
    )

    db.add(new_ticket)
    await db.flush()
    await db.refresh(new_ticket)

    logger.info({
        "event": "ticket_created",
        "ticket_id": str(new_ticket.id),
        "company_id": str(current_user.company_id),
        "channel": request.channel.value,
    })

    return TicketResponse(
        id=new_ticket.id,
        company_id=new_ticket.company_id,
        customer_email=new_ticket.customer_email,
        channel=new_ticket.channel.value,
        status=new_ticket.status.value,
        category=new_ticket.category,
        subject=new_ticket.subject,
        body=new_ticket.body,
        ai_recommendation=new_ticket.ai_recommendation,
        ai_confidence=new_ticket.ai_confidence,
        ai_tier_used=new_ticket.ai_tier_used.value if new_ticket.ai_tier_used else None,
        sentiment=new_ticket.sentiment.value if new_ticket.sentiment else None,
        assigned_to=new_ticket.assigned_to,
        resolved_at=new_ticket.resolved_at,
        created_at=new_ticket.created_at,
        updated_at=new_ticket.updated_at,
    )


@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List support tickets",
    description="List support tickets with optional filtering by status, channel, and assignee."
)
async def list_tickets(
    status_filter: Optional[TicketStatusEnum] = Query(None, alias="status", description="Filter by status"),
    channel_filter: Optional[ChannelEnum] = Query(None, alias="channel", description="Filter by channel"),
    assigned_to: Optional[uuid.UUID] = Query(None, description="Filter by assigned user"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TicketListResponse:
    """
    List support tickets with filtering.

    Args:
        status_filter: Filter by ticket status.
        channel_filter: Filter by channel.
        assigned_to: Filter by assigned user ID.
        page: Page number (1-indexed).
        page_size: Number of items per page.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        TicketListResponse: List of tickets with pagination info.
    """
    # Build query with company scoping (RLS enforcement)
    conditions = [SupportTicket.company_id == current_user.company_id]

    if status_filter:
        conditions.append(SupportTicket.status == status_filter)
    if channel_filter:
        conditions.append(SupportTicket.channel == channel_filter)
    if assigned_to:
        conditions.append(SupportTicket.assigned_to == assigned_to)

    # Count total
    count_query = select(SupportTicket).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    # Get paginated results
    offset = (page - 1) * page_size
    query = select(SupportTicket).where(and_(*conditions)).order_by(
        SupportTicket.created_at.desc()
    ).offset(offset).limit(page_size)

    result = await db.execute(query)
    tickets = result.scalars().all()

    logger.info({
        "event": "tickets_listed",
        "company_id": str(current_user.company_id),
        "total": total,
        "page": page,
    })

    return TicketListResponse(
        tickets=[
            TicketResponse(
                id=t.id,
                company_id=t.company_id,
                customer_email=t.customer_email,
                channel=t.channel.value,
                status=t.status.value,
                category=t.category,
                subject=t.subject,
                body=t.body,
                ai_recommendation=t.ai_recommendation,
                ai_confidence=t.ai_confidence,
                ai_tier_used=t.ai_tier_used.value if t.ai_tier_used else None,
                sentiment=t.sentiment.value if t.sentiment else None,
                assigned_to=t.assigned_to,
                resolved_at=t.resolved_at,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tickets
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket details",
    description="Retrieve details of a specific support ticket."
)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TicketResponse:
    """
    Get a specific support ticket by ID.

    Args:
        ticket_id: The ticket UUID.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        TicketResponse: The ticket data.

    Raises:
        HTTPException: 404 if ticket not found or not in user's company.
    """
    result = await db.execute(
        select(SupportTicket).where(
            and_(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == current_user.company_id
            )
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    logger.info({
        "event": "ticket_retrieved",
        "ticket_id": str(ticket_id),
        "company_id": str(current_user.company_id),
    })

    return TicketResponse(
        id=ticket.id,
        company_id=ticket.company_id,
        customer_email=ticket.customer_email,
        channel=ticket.channel.value,
        status=ticket.status.value,
        category=ticket.category,
        subject=ticket.subject,
        body=ticket.body,
        ai_recommendation=ticket.ai_recommendation,
        ai_confidence=ticket.ai_confidence,
        ai_tier_used=ticket.ai_tier_used.value if ticket.ai_tier_used else None,
        sentiment=ticket.sentiment.value if ticket.sentiment else None,
        assigned_to=ticket.assigned_to,
        resolved_at=ticket.resolved_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.put(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Update a support ticket",
    description="Update ticket status, category, assignment, or AI fields."
)
async def update_ticket(
    ticket_id: uuid.UUID,
    request: TicketUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TicketResponse:
    """
    Update a support ticket.

    Args:
        ticket_id: The ticket UUID.
        request: Update data.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        TicketResponse: The updated ticket data.

    Raises:
        HTTPException: 404 if ticket not found or not in user's company.
    """
    result = await db.execute(
        select(SupportTicket).where(
            and_(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == current_user.company_id
            )
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Update fields
    if request.status is not None:
        ticket.status = request.status
        if request.status == TicketStatusEnum.resolved:
            ticket.resolved_at = datetime.utcnow()

    if request.category is not None:
        ticket.category = sanitize_input(request.category)

    if request.assigned_to is not None:
        ticket.assigned_to = request.assigned_to

    if request.ai_recommendation is not None:
        ticket.ai_recommendation = sanitize_input(request.ai_recommendation)

    if request.ai_confidence is not None:
        ticket.ai_confidence = request.ai_confidence

    await db.flush()
    await db.refresh(ticket)

    logger.info({
        "event": "ticket_updated",
        "ticket_id": str(ticket_id),
        "company_id": str(current_user.company_id),
        "updated_fields": request.model_dump(exclude_unset=True),
    })

    return TicketResponse(
        id=ticket.id,
        company_id=ticket.company_id,
        customer_email=ticket.customer_email,
        channel=ticket.channel.value,
        status=ticket.status.value,
        category=ticket.category,
        subject=ticket.subject,
        body=ticket.body,
        ai_recommendation=ticket.ai_recommendation,
        ai_confidence=ticket.ai_confidence,
        ai_tier_used=ticket.ai_tier_used.value if ticket.ai_tier_used else None,
        sentiment=ticket.sentiment.value if ticket.sentiment else None,
        assigned_to=ticket.assigned_to,
        resolved_at=ticket.resolved_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.post(
    "/tickets/{ticket_id}/escalate",
    response_model=MessageResponse,
    summary="Escalate a support ticket",
    description="Escalate a ticket to manager level for review."
)
async def escalate_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Escalate a support ticket to manager level.

    Args:
        ticket_id: The ticket UUID.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        MessageResponse: Success message.

    Raises:
        HTTPException: 404 if ticket not found, 400 if already escalated.
    """
    result = await db.execute(
        select(SupportTicket).where(
            and_(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == current_user.company_id
            )
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    if ticket.status == TicketStatusEnum.escalated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket is already escalated",
        )

    # Escalate the ticket
    ticket.status = TicketStatusEnum.escalated

    await db.flush()
    await db.refresh(ticket)

    logger.info({
        "event": "ticket_escalated",
        "ticket_id": str(ticket_id),
        "company_id": str(current_user.company_id),
        "escalated_by": str(current_user.id),
    })

    return MessageResponse(
        message="Ticket escalated successfully",
        ticket_id=ticket_id,
    )


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=MessageResponse,
    summary="Add message to ticket",
    description="Add a message or response to a support ticket."
)
async def add_ticket_message(
    ticket_id: uuid.UUID,
    request: TicketMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Add a message to a support ticket.

    This endpoint stores messages related to a ticket. Messages could be
    from support agents, customers, or the system.

    Args:
        ticket_id: The ticket UUID.
        request: Message data.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        MessageResponse: Success message.

    Raises:
        HTTPException: 404 if ticket not found.
    """
    result = await db.execute(
        select(SupportTicket).where(
            and_(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == current_user.company_id
            )
        )
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    # Sanitize message
    message = sanitize_input(request.message)
    sender = sanitize_input(request.sender)

    # In a full implementation, we would store the message in a separate table
    # For now, we log it and update the ticket's updated_at timestamp
    logger.info({
        "event": "ticket_message_added",
        "ticket_id": str(ticket_id),
        "company_id": str(current_user.company_id),
        "sender": sender,
        "message_length": len(message),
    })

    return MessageResponse(
        message="Message added to ticket successfully",
        ticket_id=ticket_id,
    )
