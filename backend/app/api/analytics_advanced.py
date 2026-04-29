"""
PARWA Analytics Advanced API Routes (Week 15 — Dashboard + Analytics)

FastAPI router endpoints for advanced analytics features.

Endpoints:
- GET  /api/analytics/adaptation — AI adaptation tracker (F-039)
- GET  /api/analytics/savings — Running savings counter (F-040)
- GET  /api/analytics/workforce — AI vs human allocation (F-041)
- GET  /api/analytics/confidence-trend — AI confidence trend (F-115)
- GET  /api/analytics/drift-reports — Drift detection reports (F-116)
- GET  /api/analytics/qa-scores — QA scores (F-119)

Building Codes: BC-001 (tenant isolation), BC-002 (financial),
               BC-007 (AI model), BC-011 (auth), BC-012 (error handling)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_company_id,
)
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("analytics_advanced_api")

router = APIRouter(prefix="/api/analytics", tags=["analytics", "advanced"])


# ══════════════════════════════════════════════════════════════════
# F-039: ADAPTATION TRACKER
# ══════════════════════════════════════════════════════════════════


@router.get("/adaptation")
async def adaptation_tracker(
    days: int = Query(
        30,
        ge=1,
        le=90,
        description="Number of days to track",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get AI adaptation/learning progress over time.

    Returns daily AI accuracy vs human accuracy, mistake rates,
    training runs, and drift reports for the specified period.

    F-039: Adaptation Tracker
    BC-001: Scoped by company_id.
    BC-007: AI model learning metrics.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_advanced_service import get_adaptation_tracker

        data = get_adaptation_tracker(company_id, db, days=days)

        logger.info(
            "adaptation_tracker_loaded",
            company_id=company_id,
            user_id=str(user.id),
            days=days,
        )

        return data

    except Exception as exc:
        logger.error(
            "adaptation_tracker_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-040: RUNNING SAVINGS COUNTER
# ══════════════════════════════════════════════════════════════════


@router.get("/savings")
async def savings_counter(
    months: int = Query(
        12,
        ge=1,
        le=24,
        description="Number of months to include in trend",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get running savings counter — AI vs human cost comparison.

    Returns cumulative savings from AI-resolved tickets vs
    what they would have cost with human agents. Includes
    monthly trend, average costs, and savings percentage.

    F-040: Running Savings Counter
    BC-001: Scoped by company_id.
    BC-002: Financial metrics.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_advanced_service import get_savings_counter

        data = get_savings_counter(company_id, db, months=months)

        logger.info(
            "savings_counter_loaded",
            company_id=company_id,
            user_id=str(user.id),
            all_time_savings=data.get("all_time_savings", 0),
        )

        return data

    except Exception as exc:
        logger.error(
            "savings_counter_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-041: WORKFORCE ALLOCATION
# ══════════════════════════════════════════════════════════════════


@router.get("/workforce")
async def workforce_allocation(
    days: int = Query(
        30,
        ge=1,
        le=90,
        description="Number of days for allocation data",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get AI vs human workforce allocation distribution.

    Shows ticket distribution between AI and human agents,
    broken down by time period, channel, and category.

    F-041: Workforce Allocation
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_advanced_service import get_workforce_allocation

        data = get_workforce_allocation(company_id, db, days=days)

        logger.info(
            "workforce_allocation_loaded",
            company_id=company_id,
            user_id=str(user.id),
            days=days,
        )

        return data

    except Exception as exc:
        logger.error(
            "workforce_allocation_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-115: CONFIDENCE TREND
# ══════════════════════════════════════════════════════════════════


@router.get("/confidence-trend")
async def confidence_trend(
    days: int = Query(
        30,
        ge=1,
        le=90,
        description="Number of days to track",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get AI confidence trend over time.

    Returns daily average confidence scores, distribution buckets,
    low-confidence alerts, and trend direction for AI-generated
    message confidence.

    F-115: Confidence Trend
    BC-001: Scoped by company_id.
    BC-007: AI model confidence metrics.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_dashboard_service import get_confidence_trend

        data = get_confidence_trend(company_id, db, days=days)

        logger.info(
            "confidence_trend_loaded",
            company_id=company_id,
            user_id=str(user.id),
            days=days,
        )

        return data

    except Exception as exc:
        logger.error(
            "confidence_trend_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-116: DRIFT REPORTS
# ══════════════════════════════════════════════════════════════════


@router.get("/drift-reports")
async def drift_reports(
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum number of reports to return",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get drift detection reports for model performance monitoring.

    Returns recent drift reports with severity, metric details,
    and active/resolved status tracking.

    F-116: Drift Reports
    BC-001: Scoped by company_id.
    BC-007: AI model drift detection.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_dashboard_service import get_drift_reports

        data = get_drift_reports(company_id, db, limit=limit)

        logger.info(
            "drift_reports_loaded",
            company_id=company_id,
            user_id=str(user.id),
            report_count=data.get("total", 0),
        )

        return data

    except Exception as exc:
        logger.error(
            "drift_reports_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


# ══════════════════════════════════════════════════════════════════
# F-119: QA SCORES
# ══════════════════════════════════════════════════════════════════


@router.get("/qa-scores")
async def qa_scores(
    days: int = Query(
        30,
        ge=1,
        le=90,
        description="Number of days to track",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get QA scores — response quality assessment over time.

    Returns daily quality scores across dimensions (accuracy,
    completeness, tone), pass rates, and trend direction.

    F-119: QA Scores
    BC-001: Scoped by company_id.
    BC-007: AI quality metrics.
    BC-011: Requires authentication.
    """
    try:
        from app.services.analytics_dashboard_service import get_qa_scores

        data = get_qa_scores(company_id, db, days=days)

        logger.info(
            "qa_scores_loaded",
            company_id=company_id,
            user_id=str(user.id),
            days=days,
        )

        return data

    except Exception as exc:
        logger.error(
            "qa_scores_error",
            company_id=company_id,
            error=str(exc),
        )
        raise
