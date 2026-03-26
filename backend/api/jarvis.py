"""
PARWA Jarvis API Routes.

Provides AI assistant command and control endpoints.
"""
from datetime import datetime
from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.user import User
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import decode_access_token

# Initialize router and logger
router = APIRouter(prefix="/jarvis", tags=["Jarvis"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Pydantic Schemas ---

class JarvisCommandRequest(BaseModel):
    """Request schema for Jarvis command."""
    command: str = Field(..., min_length=1, max_length=1000, description="Command to execute")
    context: Optional[dict] = Field(None, description="Additional context for command")


class JarvisResponse(BaseModel):
    """Response schema for Jarvis command."""
    command_id: uuid.UUID
    status: str
    message: str
    result: Optional[dict] = None
    created_at: datetime


class JarvisStatusResponse(BaseModel):
    """Response schema for Jarvis status."""
    status: str
    version: str
    uptime_seconds: int
    active_commands: int


class PendingApprovalsResponse(BaseModel):
    """Response schema for pending approvals."""
    approvals: List[dict]
    total: int


# --- Helper Functions ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate current user from JWT token.

    Args:
        credentials: HTTP Bearer credentials containing the JWT token.
        db: Async database session.

    Returns:
        User: The authenticated user instance.

    Raises:
        HTTPException: If token is invalid, expired, or user not found.
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token, settings.secret_key.get_secret_value())
    except ValueError as e:
        logger.warning({"event": "token_decode_failed", "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


# --- API Endpoints ---

@router.post(
    "/command",
    response_model=JarvisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute Jarvis command",
    description="Send a command to Jarvis AI assistant for processing."
)
async def execute_command(
    request: JarvisCommandRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JarvisResponse:
    """
    Execute a Jarvis command.

    Args:
        request: Command request with command string and optional context.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        JarvisResponse with command status and result.
    """
    # TODO: Implement actual command processing
    command_id = uuid.uuid4()

    logger.info({
        "event": "jarvis_command_executed",
        "command_id": str(command_id),
        "user_id": str(current_user.id),
        "company_id": str(current_user.company_id),
        "command": request.command[:100],  # Log first 100 chars
    })

    return JarvisResponse(
        command_id=command_id,
        status="accepted",
        message="Command accepted for processing",
        result=None,
        created_at=datetime.utcnow(),
    )


@router.get(
    "/status",
    response_model=JarvisStatusResponse,
    summary="Get Jarvis status",
    description="Get current status of Jarvis AI assistant."
)
async def get_jarvis_status(
    current_user: User = Depends(get_current_user)
) -> JarvisStatusResponse:
    """
    Get Jarvis status.

    Args:
        current_user: The authenticated user.

    Returns:
        JarvisStatusResponse with current status.
    """
    return JarvisStatusResponse(
        status="operational",
        version="1.0.0",
        uptime_seconds=86400,  # Placeholder
        active_commands=0,
    )


@router.get(
    "/pending-approvals",
    response_model=PendingApprovalsResponse,
    summary="Get pending approvals",
    description="Get list of actions pending human approval."
)
async def get_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> PendingApprovalsResponse:
    """
    Get pending approvals for the company.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        PendingApprovalsResponse with list of pending actions.
    """
    # TODO: Query pending approvals from database
    return PendingApprovalsResponse(
        approvals=[],
        total=0,
    )


@router.post(
    "/pending-approvals/{approval_id}/approve",
    response_model=JarvisResponse,
    summary="Approve pending action",
    description="Approve a pending action that requires human approval."
)
async def approve_pending_action(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JarvisResponse:
    """
    Approve a pending action.

    Args:
        approval_id: UUID of the pending approval.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        JarvisResponse with approval status.
    """
    logger.info({
        "event": "jarvis_approval_approved",
        "approval_id": str(approval_id),
        "user_id": str(current_user.id),
        "company_id": str(current_user.company_id),
    })

    return JarvisResponse(
        command_id=approval_id,
        status="approved",
        message="Action approved successfully",
        result={"approved_by": str(current_user.id)},
        created_at=datetime.utcnow(),
    )


@router.post(
    "/pending-approvals/{approval_id}/reject",
    response_model=JarvisResponse,
    summary="Reject pending action",
    description="Reject a pending action that requires human approval."
)
async def reject_pending_action(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JarvisResponse:
    """
    Reject a pending action.

    Args:
        approval_id: UUID of the pending approval.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        JarvisResponse with rejection status.
    """
    logger.info({
        "event": "jarvis_approval_rejected",
        "approval_id": str(approval_id),
        "user_id": str(current_user.id),
        "company_id": str(current_user.company_id),
    })

    return JarvisResponse(
        command_id=approval_id,
        status="rejected",
        message="Action rejected",
        result={"rejected_by": str(current_user.id)},
        created_at=datetime.utcnow(),
    )
