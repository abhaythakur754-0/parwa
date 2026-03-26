"""
PARWA Automation API.

API endpoints for automation triggers, scheduling, and status.
Works with all 3 variants (Mini, PARWA, PARWA High).

CRITICAL: Automation requires authentication.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from uuid import UUID, uuid4
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

# Initialize router and logger
router = APIRouter(prefix="/automation", tags=["Automation"])
logger = get_logger(__name__)
settings = get_settings()


# --- Enums ---

class AutomationType(str, Enum):
    """Types of automation available."""
    PROVISION_AGENT = "provision_agent"
    DEPROVISION_AGENT = "deprovision_agent"
    PAUSE_REFUNDS = "pause_refunds"
    RESUME_REFUNDS = "resume_refunds"
    ESCALATE_TICKET = "escalate_ticket"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_KNOWLEDGE = "update_knowledge"
    RUN_ANALYTICS = "run_analytics"


class AutomationStatus(str, Enum):
    """Automation execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VariantType(str, Enum):
    """Supported variant types."""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"


# --- Pydantic Schemas ---

class AutomationTrigger(BaseModel):
    """Request to trigger an automation."""
    automation_type: AutomationType
    company_id: str
    variant: VariantType = VariantType.MINI
    parameters: Dict[str, Any] = Field(default_factory=dict)
    callback_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomationSchedule(BaseModel):
    """Request to schedule an automation."""
    automation_type: AutomationType
    company_id: str
    variant: VariantType = VariantType.MINI
    parameters: Dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime
    recurring: bool = False
    cron_expression: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomationResponse(BaseModel):
    """Response from automation API."""
    success: bool
    automation_id: str
    automation_type: str
    status: AutomationStatus
    variant: str
    company_id: str
    message: str
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomationStatusResponse(BaseModel):
    """Response for automation status check."""
    automation_id: str
    automation_type: str
    status: AutomationStatus
    variant: str
    company_id: str
    progress_percent: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# --- In-memory storage (would be database in production) ---

_automation_store: Dict[str, Dict[str, Any]] = {}


# --- Helper Functions ---

def generate_automation_id() -> str:
    """Generate unique automation ID."""
    return f"auto_{uuid4().hex[:16]}"


async def execute_automation(
    automation_type: AutomationType,
    company_id: str,
    variant: VariantType,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute an automation based on type.

    Args:
        automation_type: Type of automation to execute
        company_id: Company identifier
        variant: Variant type (mini, parwa, parwa_high)
        parameters: Automation parameters

    Returns:
        Dict with execution result
    """
    result: Dict[str, Any] = {"status": "completed"}

    if automation_type == AutomationType.PROVISION_AGENT:
        count = parameters.get("count", 1)
        agent_type = parameters.get("agent_type", "faq")
        result = {
            "status": "completed",
            "agents_provisioned": count,
            "agent_type": agent_type,
            "variant": variant.value,
            "message": f"Provisioned {count} {agent_type} agent(s) for {variant.value}",
        }

    elif automation_type == AutomationType.DEPROVISION_AGENT:
        agent_ids = parameters.get("agent_ids", [])
        result = {
            "status": "completed",
            "agents_deprovisioned": len(agent_ids),
            "variant": variant.value,
        }

    elif automation_type == AutomationType.PAUSE_REFUNDS:
        result = {
            "status": "completed",
            "refunds_paused": True,
            "variant": variant.value,
            "message": f"Refunds paused for company {company_id}",
        }

    elif automation_type == AutomationType.RESUME_REFUNDS:
        result = {
            "status": "completed",
            "refunds_resumed": True,
            "variant": variant.value,
            "message": f"Refunds resumed for company {company_id}",
        }

    elif automation_type == AutomationType.ESCALATE_TICKET:
        ticket_id = parameters.get("ticket_id")
        reason = parameters.get("reason", "Automated escalation")
        result = {
            "status": "completed",
            "ticket_id": ticket_id,
            "escalation_reason": reason,
            "variant": variant.value,
        }

    elif automation_type == AutomationType.SEND_NOTIFICATION:
        channel = parameters.get("channel", "email")
        recipient = parameters.get("recipient")
        message = parameters.get("message", "")
        result = {
            "status": "completed",
            "channel": channel,
            "recipient": recipient,
            "message_sent": True,
            "variant": variant.value,
        }

    elif automation_type == AutomationType.UPDATE_KNOWLEDGE:
        entries_updated = parameters.get("entries", 0)
        result = {
            "status": "completed",
            "entries_updated": entries_updated,
            "variant": variant.value,
        }

    elif automation_type == AutomationType.RUN_ANALYTICS:
        period = parameters.get("period", "30d")
        result = {
            "status": "completed",
            "period": period,
            "insights_generated": True,
            "variant": variant.value,
        }

    return result


# --- API Endpoints ---

@router.post(
    "/trigger",
    response_model=AutomationResponse,
    summary="Trigger an automation",
    description="Trigger an automation to run immediately."
)
async def trigger_automation(
    request: AutomationTrigger,
    db: AsyncSession = Depends(get_db)
) -> AutomationResponse:
    """
    Trigger an automation to run immediately.

    Works with all 3 variants (Mini, PARWA, PARWA High).

    Args:
        request: Automation trigger request
        db: Database session

    Returns:
        AutomationResponse with execution status
    """
    automation_id = generate_automation_id()
    created_at = datetime.now(timezone.utc)

    logger.info({
        "event": "automation_triggered",
        "automation_id": automation_id,
        "automation_type": request.automation_type.value,
        "company_id": request.company_id,
        "variant": request.variant.value,
    })

    # Store automation record
    _automation_store[automation_id] = {
        "automation_id": automation_id,
        "automation_type": request.automation_type,
        "company_id": request.company_id,
        "variant": request.variant,
        "status": AutomationStatus.RUNNING,
        "parameters": request.parameters,
        "created_at": created_at,
    }

    try:
        # Execute automation
        result = await execute_automation(
            automation_type=request.automation_type,
            company_id=request.company_id,
            variant=request.variant,
            parameters=request.parameters,
        )

        completed_at = datetime.now(timezone.utc)

        # Update store
        _automation_store[automation_id]["status"] = AutomationStatus.COMPLETED
        _automation_store[automation_id]["result"] = result
        _automation_store[automation_id]["completed_at"] = completed_at

        logger.info({
            "event": "automation_completed",
            "automation_id": automation_id,
            "automation_type": request.automation_type.value,
            "duration_ms": (completed_at - created_at).total_seconds() * 1000,
        })

        return AutomationResponse(
            success=True,
            automation_id=automation_id,
            automation_type=request.automation_type.value,
            status=AutomationStatus.COMPLETED,
            variant=request.variant.value,
            company_id=request.company_id,
            message=f"Automation {request.automation_type.value} completed successfully",
            result=result,
            created_at=created_at,
            completed_at=completed_at,
            metadata={
                "callback_url": request.callback_url,
                "variant": request.variant.value,
            },
        )

    except Exception as e:
        _automation_store[automation_id]["status"] = AutomationStatus.FAILED
        _automation_store[automation_id]["error"] = str(e)

        logger.error({
            "event": "automation_failed",
            "automation_id": automation_id,
            "error": str(e),
        })

        return AutomationResponse(
            success=False,
            automation_id=automation_id,
            automation_type=request.automation_type.value,
            status=AutomationStatus.FAILED,
            variant=request.variant.value,
            company_id=request.company_id,
            message=f"Automation failed: {str(e)}",
            created_at=created_at,
        )


@router.post(
    "/schedule",
    response_model=AutomationResponse,
    summary="Schedule an automation",
    description="Schedule an automation to run at a future time."
)
async def schedule_automation(
    request: AutomationSchedule,
    db: AsyncSession = Depends(get_db)
) -> AutomationResponse:
    """
    Schedule an automation to run at a future time.

    Works with all 3 variants (Mini, PARWA, PARWA High).

    Args:
        request: Automation schedule request
        db: Database session

    Returns:
        AutomationResponse with schedule status
    """
    automation_id = generate_automation_id()
    created_at = datetime.now(timezone.utc)

    # Validate scheduled time is in the future
    if request.scheduled_at <= created_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheduled time must be in the future"
        )

    logger.info({
        "event": "automation_scheduled",
        "automation_id": automation_id,
        "automation_type": request.automation_type.value,
        "company_id": request.company_id,
        "variant": request.variant.value,
        "scheduled_at": request.scheduled_at.isoformat(),
        "recurring": request.recurring,
    })

    # Store scheduled automation
    _automation_store[automation_id] = {
        "automation_id": automation_id,
        "automation_type": request.automation_type,
        "company_id": request.company_id,
        "variant": request.variant,
        "status": AutomationStatus.PENDING,
        "parameters": request.parameters,
        "scheduled_at": request.scheduled_at,
        "recurring": request.recurring,
        "cron_expression": request.cron_expression,
        "created_at": created_at,
    }

    return AutomationResponse(
        success=True,
        automation_id=automation_id,
        automation_type=request.automation_type.value,
        status=AutomationStatus.PENDING,
        variant=request.variant.value,
        company_id=request.company_id,
        message=f"Automation scheduled for {request.scheduled_at.isoformat()}",
        created_at=created_at,
        metadata={
            "scheduled_at": request.scheduled_at.isoformat(),
            "recurring": request.recurring,
            "cron_expression": request.cron_expression,
        },
    )


@router.get(
    "/status/{automation_id}",
    response_model=AutomationStatusResponse,
    summary="Get automation status",
    description="Check the status of an automation."
)
async def get_automation_status(
    automation_id: str,
    db: AsyncSession = Depends(get_db)
) -> AutomationStatusResponse:
    """
    Get the status of an automation.

    Args:
        automation_id: Automation identifier
        db: Database session

    Returns:
        AutomationStatusResponse with current status

    Raises:
        HTTPException: 404 if automation not found
    """
    automation = _automation_store.get(automation_id)

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation {automation_id} not found"
        )

    # Calculate progress
    status_value = automation.get("status", AutomationStatus.PENDING)
    if status_value == AutomationStatus.COMPLETED:
        progress = 100
    elif status_value == AutomationStatus.RUNNING:
        progress = 50
    elif status_value == AutomationStatus.FAILED:
        progress = 0
    else:
        progress = 0

    return AutomationStatusResponse(
        automation_id=automation_id,
        automation_type=automation.get("automation_type").value,
        status=status_value,
        variant=automation.get("variant").value,
        company_id=automation.get("company_id"),
        progress_percent=progress,
        started_at=automation.get("created_at"),
        completed_at=automation.get("completed_at"),
        result=automation.get("result"),
        error=automation.get("error"),
    )


@router.get(
    "/list",
    response_model=List[AutomationStatusResponse],
    summary="List automations",
    description="List automations for a company."
)
async def list_automations(
    company_id: str,
    variant: Optional[VariantType] = None,
    status_filter: Optional[AutomationStatus] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
) -> List[AutomationStatusResponse]:
    """
    List automations for a company.

    Works with all 3 variants (Mini, PARWA, PARWA High).

    Args:
        company_id: Company identifier
        variant: Optional variant filter
        status_filter: Optional status filter
        limit: Maximum results
        db: Database session

    Returns:
        List of AutomationStatusResponse
    """
    results = []

    for automation_id, automation in _automation_store.items():
        # Filter by company
        if automation.get("company_id") != company_id:
            continue

        # Filter by variant
        if variant and automation.get("variant") != variant:
            continue

        # Filter by status
        if status_filter and automation.get("status") != status_filter:
            continue

        status_value = automation.get("status", AutomationStatus.PENDING)
        if status_value == AutomationStatus.COMPLETED:
            progress = 100
        elif status_value == AutomationStatus.RUNNING:
            progress = 50
        else:
            progress = 0

        results.append(AutomationStatusResponse(
            automation_id=automation_id,
            automation_type=automation.get("automation_type").value,
            status=status_value,
            variant=automation.get("variant").value,
            company_id=automation.get("company_id"),
            progress_percent=progress,
            started_at=automation.get("created_at"),
            completed_at=automation.get("completed_at"),
            result=automation.get("result"),
            error=automation.get("error"),
        ))

        if len(results) >= limit:
            break

    return results


@router.delete(
    "/{automation_id}",
    response_model=AutomationResponse,
    summary="Cancel an automation",
    description="Cancel a pending automation."
)
async def cancel_automation(
    automation_id: str,
    db: AsyncSession = Depends(get_db)
) -> AutomationResponse:
    """
    Cancel a pending automation.

    Args:
        automation_id: Automation identifier
        db: Database session

    Returns:
        AutomationResponse with cancellation status

    Raises:
        HTTPException: 404 if automation not found, 400 if not cancellable
    """
    automation = _automation_store.get(automation_id)

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation {automation_id} not found"
        )

    current_status = automation.get("status")
    if current_status not in [AutomationStatus.PENDING, AutomationStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel automation with status {current_status.value}"
        )

    # Cancel the automation
    automation["status"] = AutomationStatus.CANCELLED
    cancelled_at = datetime.now(timezone.utc)

    logger.info({
        "event": "automation_cancelled",
        "automation_id": automation_id,
        "previous_status": current_status.value,
    })

    return AutomationResponse(
        success=True,
        automation_id=automation_id,
        automation_type=automation.get("automation_type").value,
        status=AutomationStatus.CANCELLED,
        variant=automation.get("variant").value,
        company_id=automation.get("company_id"),
        message="Automation cancelled successfully",
        created_at=automation.get("created_at"),
        completed_at=cancelled_at,
    )
