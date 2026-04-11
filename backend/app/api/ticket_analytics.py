"""
PARWA Ticket Analytics API (MF10)

Analytics API endpoints for ticket reporting:
- GET /api/v1/analytics/tickets/summary
- GET /api/v1/analytics/tickets/trends
- GET /api/v1/analytics/tickets/category
- GET /api/v1/analytics/tickets/sla
- GET /api/v1/analytics/tickets/agents

BC-001: All endpoints are tenant-scoped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.services.ticket_analytics_service import (
    TicketAnalyticsService,
    DateRange,
    IntervalType,
    TicketSummary,
    TrendPoint,
    CategoryDistribution,
    SLAMetrics,
    AgentMetrics,
)


router = APIRouter(prefix="/analytics/tickets", tags=["analytics", "tickets"])


# ── Request/Response Schemas ─────────────────────────────────────────────────

class DateRangeParams(BaseModel):
    """Date range parameters."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TicketSummaryResponse(BaseModel):
    """Response schema for ticket summary."""
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    awaiting_client_tickets: int
    awaiting_human_tickets: int
    critical_tickets: int
    high_tickets: int
    medium_tickets: int
    low_tickets: int
    resolution_rate: float
    avg_resolution_time_hours: Optional[float] = None
    avg_first_response_time_hours: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TrendPointResponse(BaseModel):
    """Response schema for a single trend point."""
    timestamp: datetime
    count: int
    label: str


class CategoryDistributionResponse(BaseModel):
    """Response schema for category distribution."""
    category: str
    count: int
    percentage: float


class SLAMetricsResponse(BaseModel):
    """Response schema for SLA metrics."""
    total_tickets_with_sla: int
    breached_count: int
    approaching_count: int
    compliant_count: int
    compliance_rate: float
    avg_first_response_minutes: Optional[float] = None
    avg_resolution_minutes: Optional[float] = None


class AgentMetricsResponse(BaseModel):
    """Response schema for agent metrics."""
    agent_id: str
    agent_name: Optional[str] = None
    tickets_assigned: int
    tickets_resolved: int
    tickets_open: int
    avg_resolution_time_hours: Optional[float] = None
    avg_first_response_time_hours: Optional[float] = None
    csat_avg: Optional[float] = None
    csat_count: int
    resolution_rate: float


# ── Helper Functions ─────────────────────────────────────────────────────────

def parse_date_range(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    default_days: int = 30,
) -> DateRange:
    """Parse date range parameters or create default."""
    if start_date and end_date:
        return DateRange(start_date=start_date, end_date=end_date)
    elif start_date:
        return DateRange(start_date=start_date, end_date=datetime.now(timezone.utc))
    elif end_date:
        return DateRange(
            start_date=end_date - __import__('datetime').timedelta(days=default_days),
            end_date=end_date,
        )
    else:
        return DateRange.last_n_days(default_days)


def get_company_id_from_user(current_user) -> str:
    """Extract company_id from current user."""
    if isinstance(current_user, dict):
        return current_user.get("company_id")
    return getattr(current_user, "company_id", None)


# ── API Endpoints ────────────────────────────────────────────────────────────

@router.get(
    "/summary",
    response_model=TicketSummaryResponse,
    summary="Get ticket summary statistics",
)
async def get_ticket_summary(
    start_date: Optional[datetime] = Query(None, description="Start date for range"),
    end_date: Optional[datetime] = Query(None, description="End date for range"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get summary statistics for tickets.

    Returns:
        - Total tickets count
        - Tickets by status (open, in_progress, resolved, closed, etc.)
        - Tickets by priority (critical, high, medium, low)
        - Resolution rate
        - Average resolution and first response times
    """
    company_id = get_company_id_from_user(current_user)
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found",
        )

    service = TicketAnalyticsService(db, company_id)
    date_range = parse_date_range(start_date, end_date)

    summary = service.get_summary(date_range)

    return TicketSummaryResponse(
        total_tickets=summary.total_tickets,
        open_tickets=summary.open_tickets,
        in_progress_tickets=summary.in_progress_tickets,
        resolved_tickets=summary.resolved_tickets,
        closed_tickets=summary.closed_tickets,
        awaiting_client_tickets=summary.awaiting_client_tickets,
        awaiting_human_tickets=summary.awaiting_human_tickets,
        critical_tickets=summary.critical_tickets,
        high_tickets=summary.high_tickets,
        medium_tickets=summary.medium_tickets,
        low_tickets=summary.low_tickets,
        resolution_rate=round(summary.resolution_rate, 3),
        avg_resolution_time_hours=(
            round(summary.avg_resolution_time_hours, 2)
            if summary.avg_resolution_time_hours else None
        ),
        avg_first_response_time_hours=(
            round(summary.avg_first_response_time_hours, 2)
            if summary.avg_first_response_time_hours else None
        ),
        start_date=summary.start_date,
        end_date=summary.end_date,
    )


@router.get(
    "/trends",
    response_model=List[TrendPointResponse],
    summary="Get ticket volume trends",
)
async def get_ticket_trends(
    interval: str = Query("day", description="Interval: hour, day, week, month"),
    start_date: Optional[datetime] = Query(None, description="Start date for range"),
    end_date: Optional[datetime] = Query(None, description="End date for range"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get ticket volume trends over time.

    Returns ticket counts grouped by the specified interval.
    """
    company_id = get_company_id_from_user(current_user)
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found",
        )

    # Validate interval
    try:
        interval_type = IntervalType(interval.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid interval: {interval}. Must be one of: hour, day, week, month",
        )

    service = TicketAnalyticsService(db, company_id)
    date_range = parse_date_range(start_date, end_date)

    trends = service.get_trends(interval_type, date_range)

    return [
        TrendPointResponse(
            timestamp=trend.timestamp,
            count=trend.count,
            label=trend.label,
        )
        for trend in trends
    ]


@router.get(
    "/category",
    response_model=List[CategoryDistributionResponse],
    summary="Get ticket distribution by category",
)
async def get_category_distribution(
    start_date: Optional[datetime] = Query(None, description="Start date for range"),
    end_date: Optional[datetime] = Query(None, description="End date for range"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get distribution of tickets by category.

    Returns:
        - Category name
        - Ticket count
        - Percentage of total
    """
    company_id = get_company_id_from_user(current_user)
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found",
        )

    service = TicketAnalyticsService(db, company_id)
    date_range = parse_date_range(start_date, end_date)

    distribution = service.get_category_distribution(date_range)

    return [
        CategoryDistributionResponse(
            category=dist.category,
            count=dist.count,
            percentage=dist.percentage,
        )
        for dist in distribution
    ]


@router.get(
    "/sla",
    response_model=SLAMetricsResponse,
    summary="Get SLA performance metrics",
)
async def get_sla_metrics(
    start_date: Optional[datetime] = Query(None, description="Start date for range"),
    end_date: Optional[datetime] = Query(None, description="End date for range"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get SLA performance metrics.

    Returns:
        - Total tickets with SLA tracking
        - Breached count
        - Approaching breach count
        - Compliant count
        - Compliance rate
        - Average first response time (minutes)
        - Average resolution time (minutes)
    """
    company_id = get_company_id_from_user(current_user)
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found",
        )

    service = TicketAnalyticsService(db, company_id)
    date_range = parse_date_range(start_date, end_date)

    metrics = service.get_sla_metrics(date_range)

    return SLAMetricsResponse(
        total_tickets_with_sla=metrics.total_tickets_with_sla,
        breached_count=metrics.breached_count,
        approaching_count=metrics.approaching_count,
        compliant_count=metrics.compliant_count,
        compliance_rate=round(metrics.compliance_rate, 3),
        avg_first_response_minutes=(
            round(metrics.avg_first_response_minutes, 1)
            if metrics.avg_first_response_minutes else None
        ),
        avg_resolution_minutes=(
            round(metrics.avg_resolution_minutes, 1)
            if metrics.avg_resolution_minutes else None
        ),
    )


@router.get(
    "/agents",
    response_model=List[AgentMetricsResponse],
    summary="Get per-agent performance metrics",
)
async def get_agent_metrics(
    start_date: Optional[datetime] = Query(None, description="Start date for range"),
    end_date: Optional[datetime] = Query(None, description="End date for range"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get per-agent performance metrics.

    Returns:
        - Agent ID and name
        - Tickets assigned, resolved, open
        - Resolution rate
        - CSAT average and count
    """
    company_id = get_company_id_from_user(current_user)
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found",
        )

    service = TicketAnalyticsService(db, company_id)
    date_range = parse_date_range(start_date, end_date)

    metrics = service.get_agent_metrics(date_range)

    return [
        AgentMetricsResponse(
            agent_id=m.agent_id,
            agent_name=m.agent_name,
            tickets_assigned=m.tickets_assigned,
            tickets_resolved=m.tickets_resolved,
            tickets_open=m.tickets_open,
            avg_resolution_time_hours=(
                round(m.avg_resolution_time_hours, 2)
                if m.avg_resolution_time_hours else None
            ),
            avg_first_response_time_hours=(
                round(m.avg_first_response_time_hours, 2)
                if m.avg_first_response_time_hours else None
            ),
            csat_avg=m.csat_avg,
            csat_count=m.csat_count,
            resolution_rate=round(m.resolution_rate, 3),
        )
        for m in metrics[:limit]
    ]


# ── Dashboard Endpoint (Combined) ────────────────────────────────────────────

@router.get(
    "/dashboard",
    summary="Get combined analytics dashboard data",
)
async def get_analytics_dashboard(
    start_date: Optional[datetime] = Query(None, description="Start date for range"),
    end_date: Optional[datetime] = Query(None, description="End date for range"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """
    Get combined analytics data for dashboard display.

    Returns summary, SLA metrics, and category distribution in a single call.
    """
    company_id = get_company_id_from_user(current_user)
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company ID not found",
        )

    service = TicketAnalyticsService(db, company_id)
    date_range = parse_date_range(start_date, end_date)

    summary = service.get_summary(date_range)
    sla = service.get_sla_metrics(date_range)
    categories = service.get_category_distribution(date_range)
    trends = service.get_trends(IntervalType.DAY, date_range)

    return {
        "summary": {
            "total_tickets": summary.total_tickets,
            "open_tickets": summary.open_tickets,
            "resolved_tickets": summary.resolved_tickets,
            "closed_tickets": summary.closed_tickets,
            "resolution_rate": round(summary.resolution_rate, 3),
            "avg_resolution_time_hours": summary.avg_resolution_time_hours,
        },
        "sla": {
            "compliance_rate": round(sla.compliance_rate, 3),
            "breached_count": sla.breached_count,
            "avg_first_response_minutes": sla.avg_first_response_minutes,
        },
        "by_category": [
            {
                "category": c.category,
                "count": c.count,
                "percentage": c.percentage,
            }
            for c in categories[:5]  # Top 5 categories
        ],
        "trend": [
            {
                "date": t.label,
                "count": t.count,
            }
            for t in trends[-7:]  # Last 7 data points
        ],
    }
