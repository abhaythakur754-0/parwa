"""
PARWA Agent Metrics API Routes (F-098)

FastAPI router endpoints for Agent Performance Metrics — historical
metrics, threshold management, and agent comparison.

Endpoints:
- GET  /api/agents/{agent_id}/metrics              — Historical metrics
- GET  /api/agents/{agent_id}/metrics/thresholds   — Get thresholds
- PUT  /api/agents/{agent_id}/metrics/thresholds   — Update thresholds
- GET  /api/agents/metrics/compare                 — Compare agents

Building Codes: BC-001 (tenant isolation), BC-011 (auth), BC-012 (errors)
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_company_id,
)
from app.exceptions import ValidationError
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("agent_metrics_api")

router = APIRouter(prefix="/api/agents", tags=["Agent Metrics (F-098)"])


# ══════════════════════════════════════════════════════════════════
# Request / Response Models
# ══════════════════════════════════════════════════════════════════


class UpdateThresholdsRequest(BaseModel):
    """Request body for updating agent metric thresholds."""

    resolution_rate_min: Optional[float] = Field(None, description="Minimum resolution rate (%)")
    confidence_min: Optional[float] = Field(None, description="Minimum avg confidence (%)")
    csat_min: Optional[float] = Field(None, description="Minimum avg CSAT (1-5 scale)")
    escalation_max_pct: Optional[float] = Field(None, description="Maximum escalation rate (%)")


# ══════════════════════════════════════════════════════════════════
# F-098: Agent Metrics Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/agents/{agent_id}/metrics")
async def get_agent_metrics(
    agent_id: str,
    period: str = Query(
        "7d",
        description="Time period (7d, 14d, 30d, 90d)",
    ),
    granularity: str = Query(
        "daily",
        description="Aggregation granularity (daily, weekly)",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get historical performance metrics for an agent.

    Returns daily or weekly aggregated metrics including resolution rate,
    avg confidence, CSAT, escalation rate, and handle time for the
    specified time period.

    F-098: Agent Performance Metrics
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_metrics_service import AgentMetricsService

        svc = AgentMetricsService(db=db)
        result = svc.get_metrics(
            agent_id=agent_id.strip(),
            company_id=company_id,
            period=period,
            granularity=granularity,
        )
        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import ValidationError as VE
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, VE, NotFoundError)):
            raise
        logger.error(
            "agent_metrics_get_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents/{agent_id}/metrics/thresholds")
async def get_agent_thresholds(
    agent_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get metric threshold configuration for an agent.

    Returns the current threshold values for resolution rate,
    confidence, CSAT, and escalation rate. Creates default
    thresholds if none exist.

    F-098: Agent Performance Metrics
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_metrics_service import AgentMetricsService

        svc = AgentMetricsService(db=db)
        result = svc.get_thresholds(
            agent_id=agent_id.strip(),
            company_id=company_id,
        )
        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_thresholds_get_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.put("/api/agents/{agent_id}/metrics/thresholds")
async def update_agent_thresholds(
    agent_id: str,
    body: UpdateThresholdsRequest,
    # BC-011: Supervisor+ role required for threshold updates.
    # Uncomment the following line to enforce role-based access:
    # user: User = Depends(require_roles("supervisor", "owner", "admin")),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update metric threshold configuration for an agent.

    Accepts partial updates — only provided fields are modified.
    Warns if csat_min > 5.0 (impossible on standard CSAT scale).

    F-098: Agent Performance Metrics
    BC-001: Scoped by company_id.
    BC-011: Requires authentication. Supervisor+ role recommended.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    updates = body.model_dump(exclude_none=True)

    if not updates:
        raise ValidationError(
            message="At least one threshold field must be provided",
            details={"field": "thresholds"},
        )

    try:
        from app.services.agent_metrics_service import AgentMetricsService

        svc = AgentMetricsService(db=db)
        result = svc.update_thresholds(
            agent_id=agent_id.strip(),
            company_id=company_id,
            updates=updates,
            user_id=str(user.id),
        )

        logger.info(
            "agent_thresholds_updated_api",
            company_id=company_id,
            agent_id=agent_id,
            user_id=str(user.id),
            updates=updates,
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_thresholds_update_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents/metrics/compare")
async def compare_agent_metrics(
    agent_ids: str = Query(
        ...,
        description="Comma-separated list of agent IDs to compare",
    ),
    period: str = Query(
        "30d",
        description="Time period (7d, 14d, 30d, 90d)",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare performance metrics across multiple agents.

    Returns a list of per-agent summaries with trend indicators.
    Agents with fewer than 5 tickets in the period are excluded.

    F-098: Agent Performance Metrics
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_ids or not agent_ids.strip():
        raise ValidationError(
            message="agent_ids is required",
            details={"field": "agent_ids"},
        )

    try:
        ids = [aid.strip() for aid in agent_ids.split(",") if aid.strip()]

        if not ids:
            raise ValidationError(
                message="At least one agent_id must be provided",
                details={"field": "agent_ids"},
            )

        from app.services.agent_metrics_service import AgentMetricsService

        svc = AgentMetricsService(db=db)
        result = svc.compare_agents(
            agent_ids=ids,
            company_id=company_id,
            period=period,
        )
        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_metrics_compare_error",
            company_id=company_id,
            agent_ids=agent_ids,
            error=str(exc),
        )
        raise
