"""
PARWA Analytics API Routes.

Provides metrics, reporting, and analytics endpoints.
All data is company-scoped for RLS compliance.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.user import User
from backend.services.analytics_service import AnalyticsService
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import decode_access_token

# Initialize router and logger
router = APIRouter(prefix="/analytics", tags=["Analytics"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Pydantic Schemas ---

class CompanyStatsResponse(BaseModel):
    """Response schema for company statistics."""
    total_tickets: int = Field(..., description="Total number of tickets")
    open_tickets: int = Field(..., description="Number of open tickets")
    resolved_tickets: int = Field(..., description="Number of resolved tickets")
    avg_response_time: float = Field(..., description="Average response time in hours")
    sla_compliance_rate: float = Field(..., description="SLA compliance percentage")


class TicketMetricItem(BaseModel):
    """Schema for a single ticket metric item."""
    date: Optional[str] = Field(None, description="Date of the metric")
    tickets_created: int = Field(..., description="Tickets created")
    tickets_resolved: int = Field(..., description="Tickets resolved")
    avg_resolution_time: float = Field(..., description="Average resolution time")


class TicketMetricsResponse(BaseModel):
    """Response schema for ticket metrics over time."""
    metrics: List[TicketMetricItem] = Field(..., description="List of ticket metrics")
    group_by: str = Field(..., description="Grouping interval (day, week, month)")


class ResponseTimeMetricsResponse(BaseModel):
    """Response schema for response time metrics."""
    first_response_avg: float = Field(..., description="Average first response time in hours")
    resolution_time_avg: float = Field(..., description="Average resolution time in hours")
    by_priority: Dict[str, float] = Field(..., description="Response times by priority")


class AgentPerformanceItem(BaseModel):
    """Schema for a single agent performance item."""
    agent_id: str = Field(..., description="Agent UUID")
    agent_name: str = Field(..., description="Agent name/email")
    tickets_assigned: int = Field(..., description="Tickets assigned to agent")
    tickets_resolved: int = Field(..., description="Tickets resolved by agent")
    avg_resolution_time: float = Field(..., description="Average resolution time in hours")
    customer_satisfaction: float = Field(..., description="Customer satisfaction score")


class AgentPerformanceResponse(BaseModel):
    """Response schema for agent performance metrics."""
    agents: List[AgentPerformanceItem] = Field(..., description="List of agent performance items")


class ActivityFeedItem(BaseModel):
    """Schema for a single activity feed item."""
    id: str = Field(..., description="Activity item ID")
    type: str = Field(..., description="Type of activity")
    description: str = Field(..., description="Activity description")
    timestamp: Optional[str] = Field(None, description="When activity occurred")
    user_id: Optional[str] = Field(None, description="User ID who performed action")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ActivityFeedResponse(BaseModel):
    """Response schema for activity feed."""
    activities: List[ActivityFeedItem] = Field(..., description="List of activity items")
    total: int = Field(..., description="Total number of activities")
    limit: int = Field(..., description="Max results returned")
    offset: int = Field(..., description="Pagination offset")


class SLAComplianceResponse(BaseModel):
    """Response schema for SLA compliance metrics."""
    compliance_rate: float = Field(..., description="SLA compliance percentage")
    total_tickets: int = Field(..., description="Total tickets monitored")
    breached_tickets: int = Field(..., description="Tickets that breached SLA")
    avg_time_to_breach: float = Field(..., description="Average hours to breach")


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


# --- API Endpoints ---

@router.get(
    "/stats",
    response_model=CompanyStatsResponse,
    summary="Get company statistics",
    description="Retrieve aggregated company statistics including tickets and SLA compliance."
)
async def get_company_stats(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> CompanyStatsResponse:
    """
    Get aggregated company statistics.

    Returns statistics including total tickets, open tickets, resolved tickets,
    average response time, and SLA compliance rate. All data is scoped to
    the user's company for RLS compliance.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        CompanyStatsResponse: Aggregated company statistics.
    """
    company_id = current_user.company_id
    service = AnalyticsService(db, company_id)

    stats = await service.get_company_stats(start_date, end_date)

    logger.info({
        "event": "company_stats_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
    })

    return CompanyStatsResponse(
        total_tickets=stats["total_tickets"],
        open_tickets=stats["open_tickets"],
        resolved_tickets=stats["resolved_tickets"],
        avg_response_time=stats["avg_response_time"],
        sla_compliance_rate=stats["sla_compliance_rate"],
    )


@router.get(
    "/metrics/tickets",
    response_model=TicketMetricsResponse,
    summary="Get ticket metrics",
    description="Retrieve ticket volume and resolution metrics over time."
)
async def get_ticket_metrics(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    group_by: str = Query("day", description="Grouping interval (day, week, month)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TicketMetricsResponse:
    """
    Get ticket volume and resolution metrics over time.

    Returns metrics grouped by day, week, or month including tickets created,
    tickets resolved, and average resolution time.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        group_by: Grouping interval (day, week, month).
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        TicketMetricsResponse: Ticket metrics over time.
    """
    company_id = current_user.company_id
    service = AnalyticsService(db, company_id)

    # Validate group_by parameter
    if group_by not in ("day", "week", "month"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="group_by must be one of: day, week, month"
        )

    metrics = await service.get_ticket_metrics(start_date, end_date, group_by)

    logger.info({
        "event": "ticket_metrics_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "group_by": group_by,
    })

    return TicketMetricsResponse(
        metrics=[
            TicketMetricItem(
                date=m["date"],
                tickets_created=m["tickets_created"],
                tickets_resolved=m["tickets_resolved"],
                avg_resolution_time=m["avg_resolution_time"],
            )
            for m in metrics
        ],
        group_by=group_by,
    )


@router.get(
    "/metrics/response-time",
    response_model=ResponseTimeMetricsResponse,
    summary="Get response time metrics",
    description="Retrieve average response times and resolution times."
)
async def get_response_time_metrics(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ResponseTimeMetricsResponse:
    """
    Get average response times.

    Returns first response time averages, resolution time averages,
    and breakdowns by priority level.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        ResponseTimeMetricsResponse: Response time metrics.
    """
    company_id = current_user.company_id
    service = AnalyticsService(db, company_id)

    metrics = await service.get_response_time_metrics(start_date, end_date)

    logger.info({
        "event": "response_time_metrics_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
    })

    return ResponseTimeMetricsResponse(
        first_response_avg=metrics["first_response_avg"],
        resolution_time_avg=metrics["resolution_time_avg"],
        by_priority=metrics["by_priority"],
    )


@router.get(
    "/metrics/agent-performance",
    response_model=AgentPerformanceResponse,
    summary="Get agent performance",
    description="Retrieve performance metrics for agents."
)
async def get_agent_performance(
    agent_id: Optional[uuid.UUID] = Query(None, description="Filter by specific agent"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AgentPerformanceResponse:
    """
    Get individual agent performance metrics.

    Returns metrics for each agent including tickets assigned, tickets resolved,
    average resolution time, and customer satisfaction scores.

    Args:
        agent_id: Optional specific agent UUID filter.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        AgentPerformanceResponse: Agent performance metrics.
    """
    company_id = current_user.company_id
    service = AnalyticsService(db, company_id)

    performance = await service.get_agent_performance(agent_id, start_date, end_date)

    logger.info({
        "event": "agent_performance_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "agent_filter": str(agent_id) if agent_id else None,
    })

    return AgentPerformanceResponse(
        agents=[
            AgentPerformanceItem(
                agent_id=p["agent_id"],
                agent_name=p["agent_name"],
                tickets_assigned=p["tickets_assigned"],
                tickets_resolved=p["tickets_resolved"],
                avg_resolution_time=p["avg_resolution_time"],
                customer_satisfaction=p["customer_satisfaction"],
            )
            for p in performance
        ]
    )


@router.get(
    "/activity-feed",
    response_model=ActivityFeedResponse,
    summary="Get activity feed",
    description="Retrieve recent activity feed for the company."
)
async def get_activity_feed(
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    activity_types: Optional[str] = Query(None, description="Filter by activity types (comma-separated)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ActivityFeedResponse:
    """
    Get recent activity feed.

    Returns a paginated list of recent activities including ticket creation,
    resolution, and escalation events.

    Args:
        limit: Max results to return (1-100).
        offset: Pagination offset.
        activity_types: Optional comma-separated list of activity types to filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        ActivityFeedResponse: Activity feed items.
    """
    company_id = current_user.company_id
    service = AnalyticsService(db, company_id)

    # Parse activity types if provided
    types_list = None
    if activity_types:
        types_list = [t.strip() for t in activity_types.split(",") if t.strip()]

    activities = await service.get_activity_feed(limit, offset, types_list)

    logger.info({
        "event": "activity_feed_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "limit": limit,
        "offset": offset,
    })

    return ActivityFeedResponse(
        activities=[
            ActivityFeedItem(
                id=a["id"],
                type=a["type"],
                description=a["description"],
                timestamp=a["timestamp"],
                user_id=a["user_id"],
                metadata=a["metadata"],
            )
            for a in activities
        ],
        total=len(activities),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/sla-compliance",
    response_model=SLAComplianceResponse,
    summary="Get SLA compliance",
    description="Retrieve SLA compliance metrics for the company."
)
async def get_sla_compliance(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SLAComplianceResponse:
    """
    Get SLA compliance metrics.

    Returns SLA compliance percentage, total tickets monitored,
    breached tickets count, and average time to breach.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        SLAComplianceResponse: SLA compliance metrics.
    """
    company_id = current_user.company_id
    service = AnalyticsService(db, company_id)

    compliance = await service.calculate_sla_compliance(start_date, end_date)

    logger.info({
        "event": "sla_compliance_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "compliance_rate": compliance["compliance_rate"],
    })

    return SLAComplianceResponse(
        compliance_rate=compliance["compliance_rate"],
        total_tickets=compliance["total_tickets"],
        breached_tickets=compliance["breached_tickets"],
        avg_time_to_breach=compliance["avg_time_to_breach"],
    )
