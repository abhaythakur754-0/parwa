"""
PARWA Burst Mode API Routes.

Provides endpoints for managing burst mode operations.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.services.burst_mode import BurstModeService
from shared.core_functions.logger import get_logger

# Initialize router and logger
router = APIRouter(prefix="/burst", tags=["Burst Mode"])
logger = get_logger(__name__)

# Service instance
_burst_mode_service = BurstModeService()


# --- Pydantic Schemas ---

class StatusResponse(BaseModel):
    """Response schema for burst mode status."""
    state: str
    is_active: bool
    current_session: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any]
    activation_count: int
    cooldown_remaining_seconds: Optional[float] = None


class ActivateRequest(BaseModel):
    """Request schema for activating burst mode."""
    trigger_type: str = Field(
        default="manual",
        description="Trigger type (manual, auto_load, auto_queue, auto_latency, scheduled)"
    )
    options: Optional[Dict[str, Any]] = Field(None, description="Additional options")


class ActivateResponse(BaseModel):
    """Response schema for activation."""
    success: bool
    session_id: Optional[str] = None
    state: str
    trigger_type: Optional[str] = None
    activated_at: Optional[str] = None
    message: str
    error: Optional[str] = None
    cooldown_remaining_seconds: Optional[float] = None


class DeactivateResponse(BaseModel):
    """Response schema for deactivation."""
    success: bool
    state: str
    cooldown_duration_seconds: Optional[int] = None
    session_summary: Optional[Dict[str, Any]] = None
    message: str
    error: Optional[str] = None


class MetricsResponse(BaseModel):
    """Response schema for burst mode metrics."""
    current_metrics: Dict[str, Any]
    current_state: str
    statistics: Dict[str, Any]
    triggers_breakdown: Dict[str, int]
    thresholds: Dict[str, Any]
    recent_sessions: list


# --- API Endpoints ---

@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Get burst mode status",
    description="Get the current burst mode status and metrics."
)
async def get_burst_status() -> StatusResponse:
    """
    Get current burst mode status.

    Returns the current state, active session (if any), and current metrics.

    Returns:
        StatusResponse with current status details.
    """
    status_data = _burst_mode_service.get_status()

    logger.info({
        "event": "burst_status_endpoint_called",
        "state": status_data["state"],
        "is_active": status_data["is_active"],
    })

    return StatusResponse(
        state=status_data["state"],
        is_active=status_data["is_active"],
        current_session=status_data["current_session"],
        metrics=status_data["metrics"],
        activation_count=status_data["activation_count"],
        cooldown_remaining_seconds=status_data.get("cooldown_remaining_seconds"),
    )


@router.post(
    "/activate",
    response_model=ActivateResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate burst mode",
    description="Manually activate burst mode."
)
async def activate_burst_mode(
    request: ActivateRequest
) -> ActivateResponse:
    """
    Manually activate burst mode.

    Args:
        request: Activation request with trigger type and options.

    Returns:
        ActivateResponse with activation result.

    Raises:
        HTTPException: 400 if already active or in cooldown.
    """
    result = await _burst_mode_service.activate(
        trigger_type=request.trigger_type,
        options=request.options or {}
    )

    logger.info({
        "event": "burst_activate_endpoint_called",
        "success": result["success"],
        "state": result["state"],
        "trigger_type": request.trigger_type,
    })

    if not result["success"]:
        # Don't raise exception for expected failures, return response
        return ActivateResponse(
            success=False,
            state=result["state"],
            message=result.get("error", "Failed to activate burst mode"),
            error=result.get("error"),
            cooldown_remaining_seconds=result.get("cooldown_remaining_seconds"),
        )

    return ActivateResponse(
        success=True,
        session_id=result["session_id"],
        state=result["state"],
        trigger_type=result["trigger_type"],
        activated_at=result["activated_at"],
        message=result["message"],
    )


@router.post(
    "/deactivate",
    response_model=DeactivateResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate burst mode",
    description="Deactivate burst mode and enter cooldown."
)
async def deactivate_burst_mode(
    reason: Optional[str] = None
) -> DeactivateResponse:
    """
    Deactivate burst mode.

    Ends the current burst session and enters cooldown period.

    Args:
        reason: Optional reason for deactivation.

    Returns:
        DeactivateResponse with deactivation result.

    Raises:
        HTTPException: 400 if not currently active.
    """
    result = await _burst_mode_service.deactivate(reason=reason)

    logger.info({
        "event": "burst_deactivate_endpoint_called",
        "success": result["success"],
        "state": result["state"],
        "reason": reason,
    })

    if not result["success"]:
        return DeactivateResponse(
            success=False,
            state=result["state"],
            message=result.get("error", "Failed to deactivate burst mode"),
            error=result.get("error"),
        )

    return DeactivateResponse(
        success=True,
        state=result["state"],
        cooldown_duration_seconds=result["cooldown_duration_seconds"],
        session_summary=result["session_summary"],
        message=result["message"],
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Get burst mode metrics",
    description="Get detailed metrics and statistics for burst mode."
)
async def get_burst_metrics() -> MetricsResponse:
    """
    Get detailed burst mode metrics.

    Returns current metrics, historical statistics, and configuration thresholds.

    Returns:
        MetricsResponse with comprehensive metrics data.
    """
    metrics_data = _burst_mode_service.get_metrics()

    logger.info({
        "event": "burst_metrics_endpoint_called",
        "current_state": metrics_data["current_state"],
        "total_activations": metrics_data["statistics"]["total_activations"],
    })

    return MetricsResponse(
        current_metrics=metrics_data["current_metrics"],
        current_state=metrics_data["current_state"],
        statistics=metrics_data["statistics"],
        triggers_breakdown=metrics_data["triggers_breakdown"],
        thresholds=metrics_data["thresholds"],
        recent_sessions=metrics_data["recent_sessions"],
    )
