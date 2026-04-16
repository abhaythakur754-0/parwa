"""
PARWA Analytics Intelligence API Routes (Week 15 — Dashboard + Analytics)

FastAPI router endpoints for intelligent analytics features.

Endpoints:
- GET  /api/analytics/growth-nudges — Usage pattern alerts (F-042)
- GET  /api/analytics/forecast — Ticket volume forecast (F-043)
- GET  /api/analytics/csat-trends — CSAT trend analytics (F-044)

Building Codes: BC-001 (tenant isolation), BC-007 (AI model),
               BC-011 (auth), BC-012 (error handling)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_company_id,
)
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("analytics_intelligence_api")

router = APIRouter(prefix="/api/analytics", tags=["analytics", "intelligence"])


# ══════════════════════════════════════════════════════════════════
# F-042: GROWTH NUDGE ALERT
# ══════════════════════════════════════════════════════════════════


@router.get("/growth-nudges")
async def growth_nudges(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get growth nudge alerts based on usage pattern analysis.

    Analyzes ticket volume, AI utilization, CSAT trends, channel
    usage, and SLA patterns to generate actionable recommendations.

    F-042: Growth Nudge Alert
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_intelligence_service import get_growth_nudges

        data = get_growth_nudges(company_id, db)

        logger.info(
            "growth_nudges_loaded",
            company_id=company_id,
            user_id=str(user.id),
            nudge_count=data.get("total", 0),
        )

        return data

    except Exception as exc:
        logger.error(
            "growth_nudges_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-043: TICKET VOLUME FORECAST
# ══════════════════════════════════════════════════════════════════


@router.get("/forecast")
async def ticket_forecast(
    forecast_days: int = Query(
        14, ge=1, le=60,
        description="Number of days to predict",
    ),
    historical_days: int = Query(
        30, ge=7, le=90,
        description="Number of historical days for model training",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get ticket volume forecast using predictive analytics.

    Uses linear regression and moving average to predict future
    ticket volume. Includes confidence bounds and seasonality detection.

    F-043: Ticket Volume Forecast
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_intelligence_service import get_ticket_forecast

        data = get_ticket_forecast(
            company_id, db,
            forecast_days=forecast_days,
            historical_days=historical_days,
        )

        logger.info(
            "ticket_forecast_loaded",
            company_id=company_id,
            user_id=str(user.id),
            forecast_days=forecast_days,
            trend=data.get("trend_direction", "stable"),
        )

        return data

    except Exception as exc:
        logger.error(
            "ticket_forecast_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-044: CSAT TRENDS
# ══════════════════════════════════════════════════════════════════


@router.get("/csat-trends")
async def csat_trends(
    days: int = Query(
        30, ge=1, le=90,
        description="Number of days for CSAT analysis",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get customer satisfaction trend analytics.

    Returns daily CSAT averages, rating distributions, and
    breakdowns by agent, category, and channel.

    F-044: CSAT Trends
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_intelligence_service import get_csat_trends

        data = get_csat_trends(company_id, db, days=days)

        logger.info(
            "csat_trends_loaded",
            company_id=company_id,
            user_id=str(user.id),
            days=days,
            overall_avg=data.get("overall_avg", 0),
        )

        return data

    except Exception as exc:
        logger.error(
            "csat_trends_error",
            company_id=company_id,
            error=str(exc),
        )
        raise
