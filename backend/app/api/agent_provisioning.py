"""
PARWA Agent Provisioning API (F-099)

FastAPI router endpoints for Paddle-triggered agent provisioning:

- POST /api/agents/provision/checkout          — Initiate agent checkout
- GET  /api/agents/provision/{id}/status       — Check provisioning status
- GET  /api/agents/provision/limit             — Check agent limit for tier

Building Codes: BC-001 (tenant isolation), BC-002 (financial),
               BC-011 (auth / supervisor+ required), BC-012 (errors).
"""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_company_id,
)
from app.exceptions import NotFoundError
from app.logger import get_logger
from database.base import get_db
from database.models.core import User

logger = get_logger("agent_provisioning_api")

router = APIRouter(
    prefix="/api/agents/provision",
    tags=["Agent Provisioning (F-099)"],
)


# ── Request/Response Schemas ─────────────────────────────────────


class CreateCheckoutRequest(BaseModel):
    """Request to initiate agent checkout via Paddle."""

    agent_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name for the new agent",
    )
    specialty: str = Field(
        ...,
        description="Agent specialty (billing, returns, technical, etc.)",
    )
    channels: List[str] = Field(
        ...,
        description="List of channels (chat, email, sms, voice, slack, webchat)",
    )


class CheckoutResponse(BaseModel):
    """Response after creating a Paddle checkout."""

    pending_agent_id: str
    paddle_checkout_url: str
    payment_status: str
    expires_at: str


class ProvisioningStatusResponse(BaseModel):
    """Response with provisioning status details."""

    id: str
    agent_name: str
    specialty: str
    channels: str
    payment_status: str
    provisioning_status: str
    created_at: str | None = None
    provisioned_at: str | None = None
    error_message: str | None = None


class AgentLimitResponse(BaseModel):
    """Response with agent limit information."""

    tier: str
    current_agents: int
    max_agents: int
    can_add: bool


# ── Endpoints ────────────────────────────────────────────────────


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=201,
)
def create_checkout(
    body: CreateCheckoutRequest,
    # BC-011: Requires supervisor+ role for agent provisioning
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    """Initiate Paddle checkout for a new AI agent.

    Validates the agent configuration, checks subscription tier limits,
    and returns a Paddle checkout URL for payment.

    The user is redirected to the Paddle checkout URL to complete
    payment. On successful payment, a Paddle webhook triggers
    agent provisioning automatically.

    BC-001: Scoped to user's company_id.
    BC-011: Requires authentication. Supervisor+ role recommended
            for agent provisioning (financial action).
    BC-002: Financial operation — creates Paddle checkout.
    """
    try:
        from app.services.agent_provisioning_service import (
            AgentProvisioningService,
        )

        svc = AgentProvisioningService(db)

        paddle_customer_id = None
        # Try to get paddle_customer_id from company record
        from database.models.core import Company

        company = (
            db.query(Company)
            .filter(
                Company.id == company_id,
            )
            .first()
        )
        if company:
            paddle_customer_id = getattr(
                company,
                "paddle_customer_id",
                None,
            )

        result = svc.create_checkout(
            company_id=company_id,
            agent_name=body.agent_name,
            specialty=body.specialty,
            channels=body.channels,
            paddle_customer_id=paddle_customer_id,
        )

        logger.info(
            "checkout_created_api",
            company_id=company_id,
            pending_agent_id=result["pending_agent_id"],
            user_id=str(user.id),
        )

        return CheckoutResponse(**result)

    except (NotFoundError, Exception) as exc:
        from app.exceptions import (
            ValidationError,
            InternalError,
        )

        if isinstance(exc, (ValidationError, NotFoundError, InternalError)):
            raise
        logger.error(
            "checkout_creation_api_error",
            company_id=company_id,
            error=str(exc),
        )
        raise


@router.get(
    "/{pending_agent_id}/status",
    response_model=ProvisioningStatusResponse,
)
def get_provisioning_status(
    pending_agent_id: str,
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> ProvisioningStatusResponse:
    """Get the provisioning status of a pending agent.

    Returns the current payment and provisioning status of a
    pending agent, including any error messages if provisioning
    failed.

    BC-001: Scoped to user's company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.agent_provisioning_service import (
            AgentProvisioningService,
        )

        svc = AgentProvisioningService(db)
        result = svc.get_provisioning_status(
            pending_agent_id=pending_agent_id,
            company_id=company_id,
        )

        return ProvisioningStatusResponse(**result)

    except (NotFoundError, Exception) as exc:
        from app.exceptions import (
            ValidationError,
        )

        if isinstance(exc, (NotFoundError, ValidationError)):
            raise
        logger.error(
            "provisioning_status_api_error",
            company_id=company_id,
            pending_agent_id=pending_agent_id,
            error=str(exc),
        )
        raise


@router.get(
    "/limit",
    response_model=AgentLimitResponse,
)
def get_agent_limit(
    user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id),
    db: Session = Depends(get_db),
) -> AgentLimitResponse:
    """Get agent limit information for the company's subscription tier.

    Returns the current number of active agents, the maximum allowed
    for the subscription tier, and whether more agents can be added.

    BC-001: Scoped to user's company_id.
    BC-011: Requires authentication.
    """
    try:
        from app.services.agent_provisioning_service import (
            AgentProvisioningService,
        )

        svc = AgentProvisioningService(db)
        result = svc.get_agent_limit(company_id=company_id)

        return AgentLimitResponse(**result)

    except Exception as exc:
        logger.error(
            "agent_limit_api_error",
            company_id=company_id,
            error=str(exc),
        )
        raise
