"""
PARWA Dashboard API Routes.
Provides endpoints for statistics, metrics, activity feed, and team performance.
All data is company-scoped for RLS compliance.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.support_ticket import SupportTicket, TicketStatusEnum, SentimentEnum
from backend.models.user import User, RoleEnum
from backend.models.company import Company
from backend.models.sla_breach import SLABreach
from backend.models.usage_log import UsageLog
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import decode_access_token

# Initialize router and logger
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Pydantic Schemas ---

class DateRangeRequest(BaseModel):
    """Request schema for date range filtering."""
    start_date: Optional[datetime] = Field(None, description="Start date for filtering")
    end_date: Optional[datetime] = Field(None, description="End date for filtering")


class TicketStatsResponse(BaseModel):
    """Response schema for ticket statistics."""
    total_tickets: int = Field(..., description="Total number of tickets")
    open_tickets: int = Field(..., description="Number of open tickets")
    pending_tickets: int = Field(..., description="Number of pending approval tickets")
    resolved_tickets: int = Field(..., description="Number of resolved tickets")
    escalated_tickets: int = Field(..., description="Number of escalated tickets")


class SLAStatsResponse(BaseModel):
    """Response schema for SLA statistics."""
    total_breaches: int = Field(..., description="Total SLA breaches")
    resolved_breaches: int = Field(..., description="Resolved SLA breaches")
    avg_resolution_hours: Optional[float] = Field(None, description="Average resolution time in hours")


class DashboardStatsResponse(BaseModel):
    """Response schema for dashboard statistics."""
    company_id: uuid.UUID = Field(..., description="Company ID")
    company_name: str = Field(..., description="Company name")
    ticket_stats: TicketStatsResponse = Field(..., description="Ticket statistics")
    sla_stats: SLAStatsResponse = Field(..., description="SLA statistics")
    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")


class ActivityItemResponse(BaseModel):
    """Response schema for a single activity item."""
    id: uuid.UUID = Field(..., description="Activity item ID")
    type: str = Field(..., description="Type of activity (ticket_created, ticket_resolved, etc.)")
    description: str = Field(..., description="Activity description")
    timestamp: datetime = Field(..., description="When the activity occurred")
    user_email: Optional[str] = Field(None, description="User who performed the action")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ActivityFeedResponse(BaseModel):
    """Response schema for activity feed."""
    items: List[ActivityItemResponse] = Field(..., description="List of activity items")
    total_count: int = Field(..., description="Total number of items available")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")


class KPIMetricsResponse(BaseModel):
    """Response schema for KPI metrics."""
    avg_response_time_hours: Optional[float] = Field(None, description="Average first response time")
    resolution_rate: float = Field(..., description="Percentage of tickets resolved")
    avg_resolution_time_hours: Optional[float] = Field(None, description="Average resolution time")
    customer_satisfaction_score: Optional[float] = Field(None, description="CSAT score (0-100)")
    ai_accuracy_rate: Optional[float] = Field(None, description="AI response accuracy rate")


class TicketSummaryResponse(BaseModel):
    """Response schema for ticket summary by status/priority."""
    by_status: Dict[str, int] = Field(..., description="Tickets grouped by status")
    by_sentiment: Dict[str, int] = Field(..., description="Tickets grouped by sentiment")
    by_channel: Dict[str, int] = Field(..., description="Tickets grouped by channel")


class TeamMemberPerformance(BaseModel):
    """Response schema for individual team member performance."""
    user_id: uuid.UUID = Field(..., description="User ID")
    user_email: str = Field(..., description="User email")
    tickets_assigned: int = Field(..., description="Number of tickets assigned")
    tickets_resolved: int = Field(..., description="Number of tickets resolved")
    avg_resolution_time_hours: Optional[float] = Field(None, description="Average resolution time")
    resolution_rate: float = Field(..., description="Resolution rate percentage")


class TeamPerformanceResponse(BaseModel):
    """Response schema for team performance metrics."""
    team_members: List[TeamMemberPerformance] = Field(..., description="Individual member performance")
    team_avg_resolution_time: Optional[float] = Field(None, description="Team average resolution time")
    team_resolution_rate: float = Field(..., description="Team resolution rate percentage")


class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str = Field(..., description="Response message")


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


async def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is in the Redis blacklist.

    Args:
        token: The JWT token to check.

    Returns:
        bool: True if token is blacklisted, False otherwise.
    """
    from shared.utils.cache import Cache

    try:
        cache = Cache()
        exists = await cache.exists(f"blacklist:{token}")
        await cache.close()
        return exists
    except Exception as e:
        logger.error({"event": "blacklist_check_failed", "error": str(e)})
        return False


# --- API Endpoints ---

@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get dashboard statistics",
    description="Retrieve company statistics including tickets, users, and SLA metrics."
)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DashboardStatsResponse:
    """
    Get dashboard statistics for the current user's company.

    Returns aggregated statistics including ticket counts, SLA breaches,
    and user counts. All data is scoped to the user's company for RLS compliance.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        DashboardStatsResponse: Aggregated dashboard statistics.
    """
    company_id = current_user.company_id

    # Get company info
    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    # Get ticket counts by status
    ticket_counts_result = await db.execute(
        select(
            SupportTicket.status,
            func.count(SupportTicket.id).label("count")
        )
        .where(SupportTicket.company_id == company_id)
        .group_by(SupportTicket.status)
    )
    ticket_counts = {row.status: row.count for row in ticket_counts_result}

    ticket_stats = TicketStatsResponse(
        total_tickets=sum(ticket_counts.values()),
        open_tickets=ticket_counts.get(TicketStatusEnum.open, 0),
        pending_tickets=ticket_counts.get(TicketStatusEnum.pending_approval, 0),
        resolved_tickets=ticket_counts.get(TicketStatusEnum.resolved, 0),
        escalated_tickets=ticket_counts.get(TicketStatusEnum.escalated, 0),
    )

    # Get SLA breach stats
    sla_breaches_result = await db.execute(
        select(
            func.count(SLABreach.id).label("total"),
            func.sum(func.cast(SLABreach.resolved_at.isnot(None), type_=None)).label("resolved"),
            func.avg(SLABreach.hours_overdue).label("avg_hours")
        )
        .where(SLABreach.company_id == company_id)
    )
    sla_row = sla_breaches_result.first()

    sla_stats = SLAStatsResponse(
        total_breaches=sla_row.total or 0,
        resolved_breaches=sla_row.resolved or 0,
        avg_resolution_hours=sla_row.avg_hours,
    )

    # Get user counts
    user_counts_result = await db.execute(
        select(
            func.count(User.id).label("total"),
            func.sum(func.cast(User.is_active == True, type_=None)).label("active")
        )
        .where(User.company_id == company_id)
    )
    user_row = user_counts_result.first()

    logger.info({
        "event": "dashboard_stats_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
    })

    return DashboardStatsResponse(
        company_id=company_id,
        company_name=company.name,
        ticket_stats=ticket_stats,
        sla_stats=sla_stats,
        total_users=user_row.total or 0,
        active_users=int(user_row.active or 0),
    )


@router.get(
    "/activity",
    response_model=ActivityFeedResponse,
    summary="Get activity feed",
    description="Retrieve recent activity feed for the company."
)
async def get_activity_feed(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ActivityFeedResponse:
    """
    Get recent activity feed for the company.

    Returns a paginated list of recent ticket activities including
    creation, resolution, and escalation events.

    Args:
        page: Page number for pagination.
        page_size: Number of items per page.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        ActivityFeedResponse: Paginated activity feed.
    """
    company_id = current_user.company_id
    offset = (page - 1) * page_size

    # Build date filter conditions
    date_conditions = [SupportTicket.company_id == company_id]
    if start_date:
        date_conditions.append(SupportTicket.created_at >= start_date)
    if end_date:
        date_conditions.append(SupportTicket.created_at <= end_date)

    # Get tickets as activity items (simplified approach)
    query = (
        select(SupportTicket)
        .where(and_(*date_conditions))
        .order_by(SupportTicket.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    tickets = result.scalars().all()

    # Convert tickets to activity items
    activity_items = []
    for ticket in tickets:
        # Determine activity type based on status
        if ticket.status == TicketStatusEnum.resolved:
            activity_type = "ticket_resolved"
            description = f"Ticket '{ticket.subject}' was resolved"
        elif ticket.status == TicketStatusEnum.escalated:
            activity_type = "ticket_escalated"
            description = f"Ticket '{ticket.subject}' was escalated"
        elif ticket.status == TicketStatusEnum.pending_approval:
            activity_type = "ticket_pending"
            description = f"Ticket '{ticket.subject}' is pending approval"
        else:
            activity_type = "ticket_created"
            description = f"Ticket '{ticket.subject}' was created"

        activity_items.append(ActivityItemResponse(
            id=ticket.id,
            type=activity_type,
            description=description,
            timestamp=ticket.updated_at,
            user_email=None,  # Would need to join with user for actual email
            metadata={
                "status": ticket.status.value if ticket.status else None,
                "channel": ticket.channel.value if ticket.channel else None,
                "sentiment": ticket.sentiment.value if ticket.sentiment else None,
            }
        ))

    # Get total count
    count_query = select(func.count(SupportTicket.id)).where(and_(*date_conditions))
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    logger.info({
        "event": "activity_feed_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "page": page,
        "total_count": total_count,
    })

    return ActivityFeedResponse(
        items=activity_items,
        total_count=total_count,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/metrics",
    response_model=KPIMetricsResponse,
    summary="Get KPI metrics",
    description="Retrieve key performance indicators for the company."
)
async def get_kpi_metrics(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> KPIMetricsResponse:
    """
    Get KPI metrics for the company.

    Returns key performance indicators including response times,
    resolution rates, and customer satisfaction metrics.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        KPIMetricsResponse: KPI metrics for the company.
    """
    company_id = current_user.company_id

    # Build date filter conditions
    date_conditions = [SupportTicket.company_id == company_id]
    if start_date:
        date_conditions.append(SupportTicket.created_at >= start_date)
    if end_date:
        date_conditions.append(SupportTicket.created_at <= end_date)

    # Get total and resolved counts for resolution rate
    counts_result = await db.execute(
        select(
            func.count(SupportTicket.id).label("total"),
            func.sum(
                func.cast(SupportTicket.status == TicketStatusEnum.resolved, type_=None)
            ).label("resolved")
        )
        .where(and_(*date_conditions))
    )
    counts_row = counts_result.first()

    total_tickets = counts_row.total or 0
    resolved_tickets = counts_row.resolved or 0
    resolution_rate = (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0.0

    # Get average resolution time (for resolved tickets)
    resolution_time_result = await db.execute(
        select(
            func.avg(
                func.extract('epoch', SupportTicket.resolved_at - SupportTicket.created_at) / 3600
            ).label("avg_hours")
        )
        .where(and_(
            SupportTicket.company_id == company_id,
            SupportTicket.resolved_at.isnot(None),
            SupportTicket.status == TicketStatusEnum.resolved
        ))
    )
    resolution_row = resolution_time_result.first()
    avg_resolution_time = resolution_row.avg_hours

    # Calculate sentiment-based satisfaction score
    sentiment_result = await db.execute(
        select(
            SupportTicket.sentiment,
            func.count(SupportTicket.id).label("count")
        )
        .where(and_(
            SupportTicket.company_id == company_id,
            SupportTicket.sentiment.isnot(None)
        ))
        .group_by(SupportTicket.sentiment)
    )
    sentiment_counts = {row.sentiment: row.count for row in sentiment_result}

    total_sentiment = sum(sentiment_counts.values())
    positive_count = sentiment_counts.get(SentimentEnum.positive, 0)
    csat_score = (positive_count / total_sentiment * 100) if total_sentiment > 0 else None

    # Get AI confidence average (as proxy for accuracy)
    ai_confidence_result = await db.execute(
        select(func.avg(SupportTicket.ai_confidence))
        .where(and_(
            SupportTicket.company_id == company_id,
            SupportTicket.ai_confidence.isnot(None)
        ))
    )
    ai_accuracy = ai_confidence_result.scalar()

    logger.info({
        "event": "kpi_metrics_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "resolution_rate": resolution_rate,
    })

    return KPIMetricsResponse(
        avg_response_time_hours=None,  # Would need first_response_at field
        resolution_rate=round(resolution_rate, 2),
        avg_resolution_time_hours=round(avg_resolution_time, 2) if avg_resolution_time else None,
        customer_satisfaction_score=round(csat_score, 2) if csat_score else None,
        ai_accuracy_rate=round(ai_accuracy * 100, 2) if ai_accuracy else None,
    )


@router.get(
    "/tickets/summary",
    response_model=TicketSummaryResponse,
    summary="Get ticket summary",
    description="Retrieve ticket summary grouped by status, sentiment, and channel."
)
async def get_ticket_summary(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TicketSummaryResponse:
    """
    Get ticket summary grouped by various dimensions.

    Returns ticket counts grouped by status, sentiment, and channel.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        TicketSummaryResponse: Ticket summary by different groupings.
    """
    company_id = current_user.company_id

    # Build date filter conditions
    date_conditions = [SupportTicket.company_id == company_id]
    if start_date:
        date_conditions.append(SupportTicket.created_at >= start_date)
    if end_date:
        date_conditions.append(SupportTicket.created_at <= end_date)

    # Get counts by status
    status_result = await db.execute(
        select(
            SupportTicket.status,
            func.count(SupportTicket.id).label("count")
        )
        .where(and_(*date_conditions))
        .group_by(SupportTicket.status)
    )
    by_status = {row.status.value: row.count for row in status_result}

    # Get counts by sentiment
    sentiment_result = await db.execute(
        select(
            SupportTicket.sentiment,
            func.count(SupportTicket.id).label("count")
        )
        .where(and_(*date_conditions))
        .group_by(SupportTicket.sentiment)
    )
    by_sentiment = {
        row.sentiment.value if row.sentiment else "unknown": row.count
        for row in sentiment_result
    }

    # Get counts by channel
    channel_result = await db.execute(
        select(
            SupportTicket.channel,
            func.count(SupportTicket.id).label("count")
        )
        .where(and_(*date_conditions))
        .group_by(SupportTicket.channel)
    )
    by_channel = {row.channel.value: row.count for row in channel_result}

    logger.info({
        "event": "ticket_summary_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
    })

    return TicketSummaryResponse(
        by_status=by_status,
        by_sentiment=by_sentiment,
        by_channel=by_channel,
    )


@router.get(
    "/team/performance",
    response_model=TeamPerformanceResponse,
    summary="Get team performance",
    description="Retrieve team performance metrics for the company."
)
async def get_team_performance(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TeamPerformanceResponse:
    """
    Get team performance metrics.

    Returns performance metrics for team members including
    tickets assigned, resolved, and average resolution times.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        TeamPerformanceResponse: Team performance metrics.
    """
    company_id = current_user.company_id

    # Get all users for the company
    users_result = await db.execute(
        select(User).where(User.company_id == company_id)
    )
    users = users_result.scalars().all()
    user_map = {user.id: user for user in users}

    # Build date filter conditions
    date_conditions = [SupportTicket.company_id == company_id]
    if start_date:
        date_conditions.append(SupportTicket.created_at >= start_date)
    if end_date:
        date_conditions.append(SupportTicket.created_at <= end_date)

    # Get assigned ticket counts
    assigned_result = await db.execute(
        select(
            SupportTicket.assigned_to,
            func.count(SupportTicket.id).label("count")
        )
        .where(and_(*date_conditions, SupportTicket.assigned_to.isnot(None)))
        .group_by(SupportTicket.assigned_to)
    )
    assigned_counts = {row.assigned_to: row.count for row in assigned_result}

    # Get resolved ticket counts
    resolved_result = await db.execute(
        select(
            SupportTicket.assigned_to,
            func.count(SupportTicket.id).label("count")
        )
        .where(and_(
            *date_conditions,
            SupportTicket.assigned_to.isnot(None),
            SupportTicket.status == TicketStatusEnum.resolved
        ))
        .group_by(SupportTicket.assigned_to)
    )
    resolved_counts = {row.assigned_to: row.count for row in resolved_result}

    # Get average resolution time per user
    resolution_time_result = await db.execute(
        select(
            SupportTicket.assigned_to,
            func.avg(
                func.extract('epoch', SupportTicket.resolved_at - SupportTicket.created_at) / 3600
            ).label("avg_hours")
        )
        .where(and_(
            SupportTicket.company_id == company_id,
            SupportTicket.assigned_to.isnot(None),
            SupportTicket.resolved_at.isnot(None),
            SupportTicket.status == TicketStatusEnum.resolved
        ))
        .group_by(SupportTicket.assigned_to)
    )
    resolution_times = {row.assigned_to: row.avg_hours for row in resolution_time_result}

    # Build team member performance list
    team_members = []
    total_assigned = 0
    total_resolved = 0
    total_resolution_time = 0.0
    members_with_time = 0

    for user_id, user in user_map.items():
        assigned = assigned_counts.get(user_id, 0)
        resolved = resolved_counts.get(user_id, 0)
        avg_time = resolution_times.get(user_id)

        resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0.0

        team_members.append(TeamMemberPerformance(
            user_id=user_id,
            user_email=user.email,
            tickets_assigned=assigned,
            tickets_resolved=resolved,
            avg_resolution_time_hours=round(avg_time, 2) if avg_time else None,
            resolution_rate=round(resolution_rate, 2),
        ))

        total_assigned += assigned
        total_resolved += resolved
        if avg_time:
            total_resolution_time += avg_time
            members_with_time += 1

    # Calculate team averages
    team_resolution_rate = (total_resolved / total_assigned * 100) if total_assigned > 0 else 0.0
    team_avg_resolution = (total_resolution_time / members_with_time) if members_with_time > 0 else None

    logger.info({
        "event": "team_performance_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "team_size": len(team_members),
    })

    return TeamPerformanceResponse(
        team_members=team_members,
        team_avg_resolution_time=round(team_avg_resolution, 2) if team_avg_resolution else None,
        team_resolution_rate=round(team_resolution_rate, 2),
    )
