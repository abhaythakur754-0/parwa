"""
Training Advanced API — F-106 Fallback Training + F-107 Cold Start

Provides endpoints for:
- GET /api/training/retraining/schedule — Get retraining schedule
- GET /api/training/retraining/due — Get agents due for retraining
- POST /api/training/retraining/schedule/{agent_id} — Schedule retraining for agent
- POST /api/training/retraining/schedule-all — Schedule all due retraining
- GET /api/training/retraining/effectiveness — Get training effectiveness
- GET /api/training/retraining/stats — Get retraining stats
- GET /api/training/cold-start/status/{agent_id} — Get cold start status
- GET /api/training/cold-start/agents — Get agents needing cold start
- POST /api/training/cold-start/initialize/{agent_id} — Initialize cold start
- POST /api/training/cold-start/initialize-all — Initialize all cold start agents
- GET /api/training/cold-start/templates — List industry templates
- GET /api/training/cold-start/templates/{industry} — Get industry template
- GET /api/training/cold-start/stats — Get cold start stats

BC-001: All endpoints scoped to company_id (via middleware).
BC-012: Structured JSON error responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Path, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import require_roles

logger = logging.getLogger("parwa.training_advanced_api")

router = APIRouter(
    prefix="/api/v1",
    tags=["Training Advanced"],
    dependencies=[Depends(require_roles("owner", "admin", "agent"))],
)


def _get_db(request: Request):
    """Get DB session from request state."""
    from database.session import get_db_session
    return get_db_session()


def _get_company_id(request: Request) -> Optional[str]:
    """Get company_id from request state (injected by middleware)."""
    return getattr(request.state, "company_id", None)


# ═══════════════════════════════════════════════════════════════════════════════
# F-106: Fallback Training Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/training/retraining/schedule",
    summary="Get retraining schedule (F-106)",
)
async def get_retraining_schedule(
    request: Request,
    days_ahead: int = Query(30, ge=1, le=90, description="Days to look ahead"),
):
    """Get the upcoming bi-weekly retraining schedule for the company."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.fallback_training_service import FallbackTrainingService

        service = FallbackTrainingService(db)
        return service.get_retraining_schedule(company_id, days_ahead)

    except Exception as exc:
        logger.error(
            "get_retraining_schedule_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get retraining schedule"}},
        )


@router.get(
    "/training/retraining/due",
    summary="Get agents due for retraining (F-106)",
)
async def get_agents_due_for_retraining(
    request: Request,
    include_force: bool = Query(False, description="Include all agents regardless of timing"),
):
    """Get list of agents that are due for bi-weekly retraining."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.fallback_training_service import FallbackTrainingService

        service = FallbackTrainingService(db)
        agents = service.get_agents_due_for_retraining(company_id, include_force)

        return {
            "company_id": company_id,
            "agents": agents,
            "total": len(agents),
            "due_count": len([a for a in agents if a.get("is_due_for_retraining")]),
            "retraining_interval_days": 14,
        }

    except Exception as exc:
        logger.error(
            "get_agents_due_for_retraining_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get due agents"}},
        )


@router.post(
    "/training/retraining/schedule/{agent_id}",
    summary="Schedule retraining for agent (F-106)",
)
async def schedule_retraining(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
    force: bool = Query(False, description="Force retraining even if not due"),
    priority: str = Query("normal", description="Training priority (low, normal, high)"),
):
    """Schedule bi-weekly retraining for a specific agent."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.fallback_training_service import FallbackTrainingService

        service = FallbackTrainingService(db)
        result = service.schedule_retraining(
            company_id=company_id,
            agent_id=agent_id,
            force=force,
            priority=priority,
        )

        if result.get("status") == "error":
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "SCHEDULE_ERROR", "message": result.get("error")}},
            )

        return result

    except Exception as exc:
        logger.error(
            "schedule_retraining_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to schedule retraining"}},
        )


@router.post(
    "/training/retraining/schedule-all",
    summary="Schedule all due retraining (F-106)",
)
async def schedule_all_retraining(request: Request):
    """Schedule retraining for all agents that are due for bi-weekly retraining."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.fallback_training_service import FallbackTrainingService

        service = FallbackTrainingService(db)
        return service.schedule_all_due_retraining(company_id)

    except Exception as exc:
        logger.error(
            "schedule_all_retraining_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to schedule all retraining"}},
        )


@router.get(
    "/training/retraining/effectiveness",
    summary="Get training effectiveness (F-106)",
)
async def get_training_effectiveness(
    request: Request,
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    runs: int = Query(5, ge=1, le=20, description="Number of runs to analyze"),
):
    """Get effectiveness metrics for recent training runs."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.fallback_training_service import FallbackTrainingService

        service = FallbackTrainingService(db)
        return service.get_training_effectiveness(company_id, agent_id, runs)

    except Exception as exc:
        logger.error(
            "get_training_effectiveness_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get training effectiveness"}},
        )


@router.get(
    "/training/retraining/stats",
    summary="Get retraining stats (F-106)",
)
async def get_retraining_stats(request: Request):
    """Get overall retraining statistics for the company."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.fallback_training_service import FallbackTrainingService

        service = FallbackTrainingService(db)
        return service.get_retraining_stats(company_id)

    except Exception as exc:
        logger.error(
            "get_retraining_stats_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get retraining stats"}},
        )


# ═══════════════════════════════════════════════════════════════════════════════
# F-107: Cold Start Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/training/cold-start/status/{agent_id}",
    summary="Get cold start status (F-107)",
)
async def get_cold_start_status(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
):
    """Check if an agent needs cold start initialization."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.cold_start_service import ColdStartService

        service = ColdStartService(db)
        return service.get_cold_start_status(company_id, agent_id)

    except Exception as exc:
        logger.error(
            "get_cold_start_status_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get cold start status"}},
        )


@router.get(
    "/training/cold-start/agents",
    summary="Get agents needing cold start (F-107)",
)
async def get_agents_needing_cold_start(request: Request):
    """Get all agents that need cold start initialization."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.cold_start_service import ColdStartService

        service = ColdStartService(db)
        agents = service.get_agents_needing_cold_start(company_id)

        return {
            "company_id": company_id,
            "agents": agents,
            "total": len(agents),
        }

    except Exception as exc:
        logger.error(
            "get_agents_needing_cold_start_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get agents needing cold start"}},
        )


@router.post(
    "/training/cold-start/initialize/{agent_id}",
    summary="Initialize cold start for agent (F-107)",
)
async def initialize_cold_start(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
    industry: str = Query("generic", description="Industry template to use"),
    specialty: Optional[str] = Query(None, description="Agent specialty"),
    auto_train: bool = Query(True, description="Automatically start training"),
):
    """Initialize cold start for a new agent with industry template."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.cold_start_service import ColdStartService

        service = ColdStartService(db)
        result = service.initialize_cold_start(
            company_id=company_id,
            agent_id=agent_id,
            industry=industry,
            specialty=specialty,
            auto_train=auto_train,
        )

        if result.get("status") == "error":
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INIT_ERROR", "message": result.get("error")}},
            )

        return result

    except Exception as exc:
        logger.error(
            "initialize_cold_start_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to initialize cold start"}},
        )


@router.post(
    "/training/cold-start/initialize-all",
    summary="Initialize all cold start agents (F-107)",
)
async def initialize_all_cold_start(
    request: Request,
    default_industry: str = Query("generic", description="Default industry template"),
):
    """Initialize cold start for all agents that need it."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.cold_start_service import ColdStartService

        service = ColdStartService(db)
        return service.initialize_all_cold_start_agents(company_id, default_industry)

    except Exception as exc:
        logger.error(
            "initialize_all_cold_start_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to initialize all cold start agents"}},
        )


@router.get(
    "/training/cold-start/templates",
    summary="List industry templates (F-107)",
)
async def list_industry_templates(request: Request):
    """List all available industry templates for cold start."""
    try:
        db = _get_db(request)
        from app.services.cold_start_service import ColdStartService

        service = ColdStartService(db)
        templates = service.list_industry_templates()

        return {
            "templates": templates,
            "total": len(templates),
        }

    except Exception as exc:
        logger.error(
            "list_industry_templates_error",
            extra={"error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to list industry templates"}},
        )


@router.get(
    "/training/cold-start/templates/{industry}",
    summary="Get industry template (F-107)",
)
async def get_industry_template(
    request: Request,
    industry: str = Path(..., description="Industry identifier"),
):
    """Get the template for a specific industry."""
    try:
        db = _get_db(request)
        from app.services.cold_start_service import ColdStartService

        service = ColdStartService(db)
        result = service.get_industry_template(industry)

        if result.get("template") is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": f"Industry template '{industry}' not found"}},
            )

        return result

    except Exception as exc:
        logger.error(
            "get_industry_template_error",
            extra={"industry": industry, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get industry template"}},
        )


@router.get(
    "/training/cold-start/stats",
    summary="Get cold start stats (F-107)",
)
async def get_cold_start_stats(request: Request):
    """Get cold start statistics for the company."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.cold_start_service import ColdStartService

        service = ColdStartService(db)
        return service.get_cold_start_stats(company_id)

    except Exception as exc:
        logger.error(
            "get_cold_start_stats_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get cold start stats"}},
        )
