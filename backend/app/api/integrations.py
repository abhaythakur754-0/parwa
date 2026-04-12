"""
PARWA Integrations Router (Week 6 — F-030, F-031)

Endpoints for third-party integration management.

- GET  /api/integrations/available  — List available integration types
- POST /api/integrations            — Create a new integration
- GET  /api/integrations            — List company integrations
- POST /api/integrations/{id}/test  — Test an existing integration
- DELETE /api/integrations/{id}     — Delete an integration

F-030: Pre-built Integrations (Zendesk, Shopify, Slack, Gmail)
F-031: Custom Integration Builder (via config fields)

BC-001: All operations scoped to authenticated user's company_id.
GAP 7: Integration validation bypass prevention.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.services.integration_service import (
    INTEGRATION_TYPES,
    create_integration,
    get_integrations,
    test_integration,
    delete_integration,
)
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


# ── Request Schemas ────────────────────────────────────────────────


class CreateIntegrationRequest(BaseModel):
    """Request to create a new integration."""

    integration_type: str = Field(..., description="Type: zendesk, shopify, slack, gmail")
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Integration config with credentials")
    validate: bool = Field(default=True, description="Whether to validate credentials before saving")


class IntegrationResponse(BaseModel):
    """Response with integration details."""

    id: str
    company_id: str
    type: str
    name: str
    status: str
    config: Dict[str, Any]
    last_test_at: str | None = None
    last_test_result: str | None = None
    created_at: str


class TestIntegrationResponse(BaseModel):
    """Response after testing an integration."""

    integration_id: str
    success: bool
    message: str
    status: str
    tested_at: str


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# ── Endpoints ──────────────────────────────────────────────────────


@router.get(
    "/available",
    response_model=List[Dict[str, Any]],
)
def list_available_integrations() -> List[Dict[str, Any]]:
    """List all available integration types and their required fields.

    F-030: Returns integration types with metadata including
    display name, description, required config fields, and icon.

    No authentication required (public info).
    """
    result = []
    for int_type, int_config in INTEGRATION_TYPES.items():
        result.append({
            "type": int_type,
            "required_fields": int_config["required_fields"],
            "test_url_template": int_config["test_url"],
        })
    return result


@router.post(
    "",
    response_model=IntegrationResponse,
    status_code=201,
)
def api_create_integration(
    body: CreateIntegrationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationResponse:
    """Create a new integration.

    F-030/F-031: Creates integration with credential validation.
    GAP 7 FIX: Credentials are validated before saving if validate=True.

    BC-001: Scoped to user's company_id.
    """
    integration = create_integration(
        db=db,
        company_id=user.company_id,
        integration_type=body.integration_type,
        name=body.name,
        config=body.config,
        validate=body.validate,
    )

    return IntegrationResponse(**integration)


@router.get(
    "",
    response_model=List[IntegrationResponse],
)
def api_list_integrations(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[IntegrationResponse]:
    """List integrations for the authenticated user's company.

    BC-001: Scoped to user's company_id.
    Optional status filter: pending, active, error.
    """
    integrations = get_integrations(
        db=db,
        company_id=user.company_id,
        status=status,
    )

    return [IntegrationResponse(**i) for i in integrations]


@router.post(
    "/{integration_id}/test",
    response_model=TestIntegrationResponse,
)
def api_test_integration(
    integration_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TestIntegrationResponse:
    """Test an existing integration's connectivity.

    GAP 7 FIX: Verifies credentials are still valid by making
    a test API call to the integration's service.

    BC-001: Scoped to user's company_id.
    """
    result = test_integration(
        db=db,
        integration_id=integration_id,
        company_id=user.company_id,
    )

    return TestIntegrationResponse(**result)


@router.delete(
    "/{integration_id}",
    response_model=MessageResponse,
)
def api_delete_integration(
    integration_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete an integration.

    BC-001: Scoped to user's company_id.
    """
    delete_integration(
        db=db,
        integration_id=integration_id,
        company_id=user.company_id,
    )
    return MessageResponse(message="Integration deleted successfully.")
