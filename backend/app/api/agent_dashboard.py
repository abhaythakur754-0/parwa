"""
PARWA Agent Dashboard API Routes (F-097)

FastAPI router endpoints for the Agent Dashboard — card-based views
of all AI agents with real-time status, performance metrics, sparkline
data, and quick-action affordances.

Endpoints:
- GET  /api/agents/dashboard              — List all agent cards + status counts
- GET  /api/agents/dashboard/{agent_id}   — Single agent card detail
- GET  /api/agents/dashboard/status-counts — Agent counts by status
- POST /api/agents/dashboard/{agent_id}/pause  — Pause an agent
- POST /api/agents/dashboard/{agent_id}/resume — Resume a paused agent

Building Codes: BC-001 (tenant isolation), BC-005 (real-time Socket.io),
               BC-007 (AI model availability), BC-011 (auth), BC-012 (errors)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_company_id,
)
from app.exceptions import ValidationError
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("agent_dashboard_api")

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# F-097: Agent Dashboard Endpoints
# ══════════════════════════════════════════════════════════════════


@router.get("/api/agents/dashboard")
async def list_agent_cards(
    status: Optional[str] = Query(
        None,
        description="Filter by status (active, training, paused, error, cold_start)",
    ),
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all agent cards with status counts.

    Returns all AI agent cards for the current tenant with performance
    metrics, sparkline data, and quick-action affordances. Includes
    aggregate status counts for filter chips.

    F-097: Agent Dashboard
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if status:
        valid = ("active", "training", "paused", "error", "cold_start")
        if status not in valid:
            raise ValidationError(
                message=f"Invalid status filter: {status}",
                details={"field": "status", "valid_values": list(valid)},
            )

    try:
        from app.services.agent_dashboard_service import (
            get_agent_dashboard_service,
        )

        svc = get_agent_dashboard_service(company_id)
        result = svc.get_agent_cards(db=db, status_filter=status)

        return result

    except Exception as exc:
        logger.error(
            "agent_dashboard_list_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents/dashboard/{agent_id}")
async def get_agent_card_detail(
    agent_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single agent card detail.

    Returns detailed information for a single agent including setup
    status, active instruction set, channels, and permissions.

    F-097: Agent Dashboard
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_dashboard_service import (
            get_agent_dashboard_service,
        )

        svc = get_agent_dashboard_service(company_id)
        result = svc.get_agent_card(
            agent_id=agent_id.strip(),
            db=db,
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_dashboard_detail_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents/dashboard/status-counts")
async def get_status_counts(
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get agent counts grouped by status.

    Returns counts for active, training, paused, error, and cold_start
    statuses. Used to render status filter chips on the dashboard.

    F-097: Agent Dashboard
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.agent_dashboard_service import (
            get_agent_dashboard_service,
        )

        svc = get_agent_dashboard_service(company_id)
        result = svc.get_agent_status_counts(db=db)

        return result

    except Exception as exc:
        logger.error(
            "agent_dashboard_status_counts_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.post("/api/agents/dashboard/{agent_id}/pause")
async def pause_agent(
    agent_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pause an active agent.

    Only agents in 'active' status can be paused. Paused agents
    stop handling new tickets. Emits a Socket.io event
    (agent:status_changed) for real-time dashboard updates.

    F-097: Agent Dashboard
    BC-001: Scoped by company_id.
    BC-005: Real-time via Socket.io.
    BC-007: Agent status tied to model availability.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_dashboard_service import (
            get_agent_dashboard_service,
        )

        svc = get_agent_dashboard_service(company_id)
        result = svc.pause_agent(
            agent_id=agent_id.strip(),
            db=db,
            user_id=str(user.id),
        )

        logger.info(
            "agent_paused_api",
            company_id=company_id,
            agent_id=agent_id,
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_pause_api_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.post("/api/agents/dashboard/{agent_id}/resume")
async def resume_agent(
    agent_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resume a paused agent.

    Only agents in 'paused' status can be resumed. Resumed agents
    begin handling new tickets again. Emits a Socket.io event
    (agent:status_changed) for real-time dashboard updates.

    F-097: Agent Dashboard
    BC-001: Scoped by company_id.
    BC-005: Real-time via Socket.io.
    BC-007: Agent status tied to model availability.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_dashboard_service import (
            get_agent_dashboard_service,
        )

        svc = get_agent_dashboard_service(company_id)
        result = svc.resume_agent(
            agent_id=agent_id.strip(),
            db=db,
            user_id=str(user.id),
        )

        logger.info(
            "agent_resumed_api",
            company_id=company_id,
            agent_id=agent_id,
            user_id=str(user.id),
        )

        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_resume_api_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


@router.get("/api/agents/dashboard/{agent_id}/metrics")
async def get_agent_realtime_metrics(
    agent_id: str,
    company_id: str = Depends(get_company_id),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get realtime metrics for a single agent.

    Returns the latest performance metrics for dashboard display
    or polling. Also emitted via Socket.io agent:metrics_updated.

    F-097: Agent Dashboard
    BC-001: Scoped by company_id.
    BC-011: Requires authentication.
    """
    if not agent_id or not agent_id.strip():
        raise ValidationError(
            message="agent_id is required",
            details={"field": "agent_id"},
        )

    try:
        from app.services.agent_dashboard_service import (
            get_agent_dashboard_service,
        )

        svc = get_agent_dashboard_service(company_id)
        result = svc.get_agent_realtime_metrics(
            agent_id=agent_id.strip(),
            db=db,
        )
        return result

    except (ValidationError, Exception) as exc:
        from app.exceptions import NotFoundError
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        logger.error(
            "agent_realtime_metrics_error",
            company_id=company_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise
