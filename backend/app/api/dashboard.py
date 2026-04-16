"""
PARWA Dashboard API Routes (Week 15 — Dashboard + Analytics)

FastAPI router endpoints for the dashboard and analytics features.

Endpoints:
- GET  /api/dashboard/home — Unified dashboard data (F-036)
- GET  /api/dashboard/layout — Dashboard widget layout
- GET  /api/dashboard/activity-feed — Global activity feed (F-037)
- GET  /api/dashboard/metrics — Key KPI metrics (F-038)

Building Codes: BC-001 (tenant isolation), BC-011 (auth),
               BC-012 (error handling, structured responses)
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_company_id,
)
from app.exceptions import ValidationError
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("dashboard_api")

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ══════════════════════════════════════════════════════════════════
# F-036: DASHBOARD HOME — Unified Widget Data
# ══════════════════════════════════════════════════════════════════


@router.get("/home")
async def dashboard_home(
    period_days: int = Query(
        30, ge=1, le=365,
        description="Number of days for dashboard data",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get unified dashboard home data.

    Returns all widget data in a single API call:
    ticket summary, KPIs, SLA metrics, volume trend, category
    distribution, activity feed, savings, workforce allocation,
    CSAT, and anomaly alerts.

    F-036: Dashboard Home
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.dashboard_service import get_dashboard_home

        data = get_dashboard_home(company_id, db, period_days=period_days)

        logger.info(
            "dashboard_home_loaded",
            company_id=company_id,
            user_id=str(user.id),
            period_days=period_days,
        )

        return data

    except Exception as exc:
        logger.error(
            "dashboard_home_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/layout")
async def dashboard_layout(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get dashboard widget layout configuration.

    Returns the widget layout for the dashboard, including
    widget positions, sizes, types, and refresh intervals.

    F-036: Dashboard Home (layout config)
    BC-011: Requires authentication.
    """
    try:
        from app.services.dashboard_service import DEFAULT_WIDGETS

        return {
            "layout_id": "default",
            "widgets": DEFAULT_WIDGETS,
            "is_default": True,
        }

    except Exception as exc:
        logger.error(
            "dashboard_layout_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-037: ACTIVITY FEED — Real-Time Event Stream
# ══════════════════════════════════════════════════════════════════


@router.get("/activity-feed")
async def activity_feed(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        25, ge=1, le=100,
        description="Events per page",
    ),
    event_type: Optional[str] = Query(
        None,
        description="Filter by event type (comma-separated)",
    ),
    ticket_id: Optional[str] = Query(
        None,
        description="Filter by ticket ID",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get global activity feed.

    Returns a paginated stream of activity events across all
    tickets: status changes, assignments, new tickets, and messages.
    Sorted by most recent first.

    F-037: Activity Feed
    BC-001: Scoped by company_id.
    BC-005: Designed for real-time push via Socket.io.
    BC-011: Requires authentication.
    """
    try:
        from app.services.dashboard_service import get_activity_feed

        # Parse event type filter
        event_types = None
        if event_type:
            event_types = [t.strip() for t in event_type.split(",") if t.strip()]

        result = get_activity_feed(
            company_id, db,
            page=page,
            page_size=page_size,
            event_types=event_types,
            ticket_id=ticket_id,
        )

        logger.info(
            "activity_feed_loaded",
            company_id=company_id,
            user_id=str(user.id),
            page=page,
            total_events=result.get("total", 0),
        )

        return result

    except Exception as exc:
        logger.error(
            "activity_feed_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-038: KEY METRICS AGGREGATION — KPIs
# ══════════════════════════════════════════════════════════════════


@router.get("/metrics")
async def key_metrics(
    period: str = Query(
        "last_30d",
        description="Time period: last_7d, last_30d, last_90d",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get key performance indicator metrics.

    Returns KPI cards with current values, previous period comparison,
    change percentages, and sparkline arrays for mini-chart rendering.
    Includes anomaly detection flags for unusual patterns.

    F-038: Key Metrics Aggregation
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    # Validate period
    valid_periods = {"last_7d", "last_30d", "last_90d"}
    if period not in valid_periods:
        raise ValidationError(
            message=f"Invalid period '{period}'. Must be one of: {', '.join(sorted(valid_periods))}",
            details={"field": "period", "allowed": sorted(valid_periods)},
        )

    try:
        from app.services.dashboard_service import get_key_metrics

        data = get_key_metrics(company_id, db, period=period)

        logger.info(
            "key_metrics_loaded",
            company_id=company_id,
            user_id=str(user.id),
            period=period,
            kpi_count=len(data.get("kpis", [])),
        )

        return data

    except Exception as exc:
        logger.error(
            "key_metrics_error",
            company_id=company_id,
            error=str(exc),
        )
        raise
