"""
Training API Endpoints — F-100 Agent Lightning Training Loop + F-101 50-Mistake Threshold

Provides endpoints for:
- POST /api/agents/{agent_id}/train — Start training for an agent
- GET /api/training/runs — List training runs
- GET /api/training/runs/{run_id} — Get training run details
- POST /api/training/runs/{run_id}/cancel — Cancel a training run
- GET /api/training/stats — Get training statistics
- POST /api/agents/{agent_id}/mistakes — Report a mistake (F-101)
- GET /api/agents/{agent_id}/mistakes/threshold — Get threshold status (F-101)
- GET /api/agents/{agent_id}/mistakes/history — Get mistake history

BC-001: All endpoints scoped to company_id (via middleware).
BC-007: Training threshold is LOCKED at 50 (immutable).
BC-012: Structured JSON error responses.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, Request, Path, HTTPException
from fastapi.responses import JSONResponse

from app.schemas.training import (
    MistakeReportRequest,
    MistakeReportResponse,
    ThresholdStatusResponse,
    MistakeHistoryResponse,
    MistakeStatsResponse,
    TrainingRunCreateRequest,
    TrainingRunCreateResponse,
    TrainingRunResponse,
    TrainingRunListResponse,
    TrainingRunCancelResponse,
    TrainingStatsResponse,
    CheckpointCreateRequest,
    CheckpointCreateResponse,
    CheckpointResponse,
)

logger = logging.getLogger("parwa.training_api")

router = APIRouter(prefix="/api/v1", tags=["Training"])


def _get_db(request: Request):
    """Get DB session from request state."""
    from database.session import get_db_session
    return get_db_session()


def _get_company_id(request: Request) -> Optional[str]:
    """Get company_id from request state (injected by middleware)."""
    return getattr(request.state, "company_id", None)


# ═══════════════════════════════════════════════════════════════════════════════
# F-101: Mistake Threshold Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/agents/{agent_id}/mistakes",
    response_model=MistakeReportResponse,
    summary="Report an agent mistake (F-101)",
)
async def report_mistake(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
    body: MistakeReportRequest = None,
):
    """Report a mistake made by an agent.

    When the agent reaches 50 mistakes (LOCKED threshold per BC-007 rule 10),
    training is automatically triggered.
    """
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.mistake_threshold_service import MistakeThresholdService

        service = MistakeThresholdService(db)
        result = service.report_mistake(
            company_id=company_id,
            agent_id=agent_id,
            ticket_id=body.ticket_id if body else None,
            mistake_type=body.mistake_type if body else "incorrect_response",
            original_response=body.original_response if body else None,
            expected_response=body.expected_response if body else None,
            correction=body.correction if body else None,
            severity=body.severity if body else "medium",
        )
        return result

    except Exception as exc:
        logger.error(
            "report_mistake_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to report mistake"}},
        )


@router.get(
    "/agents/{agent_id}/mistakes/threshold",
    response_model=ThresholdStatusResponse,
    summary="Get threshold status (F-101)",
)
async def get_threshold_status(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
):
    """Get the current mistake threshold status for an agent.

    The threshold is LOCKED at 50 per BC-007 rule 10 and cannot be changed.
    """
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.mistake_threshold_service import MistakeThresholdService

        service = MistakeThresholdService(db)
        return service.get_threshold_status(company_id, agent_id)

    except Exception as exc:
        logger.error(
            "get_threshold_status_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get threshold status"}},
        )


@router.get(
    "/agents/{agent_id}/mistakes/history",
    response_model=MistakeHistoryResponse,
    summary="Get mistake history (F-101)",
)
async def get_mistake_history(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    mistake_type: Optional[str] = Query(None, description="Filter by mistake type"),
):
    """Get mistake history for an agent."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.mistake_threshold_service import MistakeThresholdService

        service = MistakeThresholdService(db)
        return service.get_mistake_history(
            company_id=company_id,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
            severity=severity,
            mistake_type=mistake_type,
        )

    except Exception as exc:
        logger.error(
            "get_mistake_history_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get mistake history"}},
        )


@router.get(
    "/agents/{agent_id}/mistakes/stats",
    response_model=MistakeStatsResponse,
    summary="Get mistake statistics (F-101)",
)
async def get_mistake_stats(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
):
    """Get mistake statistics for an agent."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.mistake_threshold_service import MistakeThresholdService

        service = MistakeThresholdService(db)
        return service.get_mistake_stats(company_id, agent_id)

    except Exception as exc:
        logger.error(
            "get_mistake_stats_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get mistake stats"}},
        )


# ═══════════════════════════════════════════════════════════════════════════════
# F-100: Training Run Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/agents/{agent_id}/train",
    response_model=TrainingRunCreateResponse,
    summary="Start training for an agent (F-100)",
)
async def start_training(
    request: Request,
    agent_id: str = Path(..., description="Agent ID"),
    body: TrainingRunCreateRequest = None,
):
    """Start a training run for an agent.

    Initiates the Lightning Training Loop with the specified configuration.
    """
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(db)
        result = service.create_training_run(
            company_id=company_id,
            agent_id=agent_id,
            dataset_id=body.dataset_id if body else "",
            name=body.name if body else None,
            trigger=body.trigger if body else "manual",
            base_model=body.base_model if body else None,
            epochs=body.epochs if body else 3,
            learning_rate=body.learning_rate if body else 0.0001,
            batch_size=body.batch_size if body else 16,
        )
        return result

    except Exception as exc:
        logger.error(
            "start_training_error",
            extra={"company_id": company_id, "agent_id": agent_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to start training"}},
        )


@router.get(
    "/training/runs",
    response_model=TrainingRunListResponse,
    summary="List training runs (F-100)",
)
async def list_training_runs(
    request: Request,
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List training runs for the tenant."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(db)
        return service.list_training_runs(
            company_id=company_id,
            agent_id=agent_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    except Exception as exc:
        logger.error(
            "list_training_runs_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to list training runs"}},
        )


@router.get(
    "/training/runs/{run_id}",
    response_model=TrainingRunResponse,
    summary="Get training run details (F-100)",
)
async def get_training_run(
    request: Request,
    run_id: str = Path(..., description="Training run ID"),
):
    """Get details of a specific training run."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(db)
        result = service.get_training_run(company_id, run_id)

        if not result:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": f"Training run {run_id} not found"}},
            )

        return result

    except Exception as exc:
        logger.error(
            "get_training_run_error",
            extra={"company_id": company_id, "run_id": run_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get training run"}},
        )


@router.post(
    "/training/runs/{run_id}/cancel",
    response_model=TrainingRunCancelResponse,
    summary="Cancel a training run (F-100)",
)
async def cancel_training_run(
    request: Request,
    run_id: str = Path(..., description="Training run ID"),
):
    """Cancel an active training run."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(db)
        result = service.cancel_training_run(company_id, run_id)

        if result.get("status") == "error":
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "CANNOT_CANCEL", "message": result.get("error")}},
            )

        return result

    except Exception as exc:
        logger.error(
            "cancel_training_run_error",
            extra={"company_id": company_id, "run_id": run_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to cancel training run"}},
        )


@router.get(
    "/training/stats",
    response_model=TrainingStatsResponse,
    summary="Get training statistics (F-100)",
)
async def get_training_stats(
    request: Request,
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
):
    """Get training statistics for the tenant or a specific agent."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(db)
        return service.get_training_stats(company_id, agent_id)

    except Exception as exc:
        logger.error(
            "get_training_stats_error",
            extra={"company_id": company_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get training stats"}},
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoint Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/training/runs/{run_id}/checkpoints/best",
    response_model=CheckpointResponse,
    summary="Get best checkpoint (F-100)",
)
async def get_best_checkpoint(
    request: Request,
    run_id: str = Path(..., description="Training run ID"),
):
    """Get the best checkpoint for a training run."""
    company_id = _get_company_id(request)
    if not company_id:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "AUTHORIZATION_ERROR", "message": "Tenant identification required"}},
        )

    try:
        db = _get_db(request)
        from app.services.agent_training_service import AgentTrainingService

        service = AgentTrainingService(db)
        result = service.get_best_checkpoint(company_id, run_id)

        if not result:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": "No best checkpoint found"}},
            )

        return result

    except Exception as exc:
        logger.error(
            "get_best_checkpoint_error",
            extra={"company_id": company_id, "run_id": run_id, "error": str(exc)[:200]},
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Failed to get best checkpoint"}},
        )
