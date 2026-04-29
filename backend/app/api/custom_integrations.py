"""
PARWA Custom Integration API (F-031)

Endpoints for custom integration management:

- POST   /api/integrations/custom           — Create custom integration
- POST   /api/integrations/custom/{id}/test — Test connectivity
- POST   /api/integrations/custom/{id}/activate — Activate (draft → active)
- PUT    /api/integrations/custom/{id}      — Update config
- DELETE /api/integrations/custom/{id}      — Delete
- GET    /api/integrations/custom           — List company's custom integrations
- GET    /api/integrations/custom/{id}      — Get single custom integration

Building Codes:
- BC-001: All operations scoped to company_id
- BC-011: JWT authentication required
- BC-012: Structured JSON error responses
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.services.custom_integration_service import CustomIntegrationService
from app.services.outgoing_webhook_service import OutgoingWebhookService
from database.base import get_db
from database.models.core import User

router = APIRouter(
    prefix="/api/integrations/custom",
    tags=["Custom Integrations (F-031)"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


# ── Request/Response Schemas ───────────────────────────────────────


class CreateCustomIntegrationRequest(BaseModel):
    """Request to create a custom integration."""

    type: str = Field(
        ...,
        description="Integration type: rest, graphql, webhook_in, webhook_out, database",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name for the integration",
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific configuration (see docs for schema per type)",
    )


class UpdateCustomIntegrationRequest(BaseModel):
    """Request to update a custom integration."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[Dict[str, Any]] = Field(None)
    settings: Optional[Dict[str, Any]] = Field(None)


class TestCustomIntegrationRequest(BaseModel):
    """Request body for testing a custom integration."""

    test_payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional test payload (for webhook_out type)",
    )


class CustomIntegrationResponse(BaseModel):
    """Response with custom integration details."""

    id: str
    company_id: str
    name: str
    type: str
    status: str
    config: Dict[str, Any]
    settings: Dict[str, Any]
    webhook_id: Optional[str] = None
    webhook_url: Optional[str] = None
    consecutive_error_count: int = 0
    last_error_message: Optional[str] = None
    last_tested_at: Optional[str] = None
    last_test_result: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TestResponse(BaseModel):
    """Response after testing connectivity."""

    integration_id: str
    type: str
    name: str
    success: bool
    message: str
    latency_ms: Optional[int] = None
    tested_at: str
    auto_disabled: bool = False


class ActivateResponse(BaseModel):
    """Response after activating an integration."""

    id: str
    name: str
    type: str
    status: str
    message: str


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


class DeliveryLogResponse(BaseModel):
    """Outgoing webhook delivery log entry."""

    id: str
    company_id: str
    custom_integration_id: str
    trigger_event: str
    trigger_event_id: Optional[str] = None
    attempt: int
    status: str
    response_status_code: Optional[int] = None
    error_message: Optional[str] = None
    scheduled_at: Optional[str] = None
    delivered_at: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────


@router.post(
    "",
    response_model=CustomIntegrationResponse,
    status_code=201,
)
def create_custom_integration(
    body: CreateCustomIntegrationRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomIntegrationResponse:
    """Create a new custom integration in draft status.

    The integration will remain in 'draft' status until explicitly activated.
    Config schema depends on the integration type:

    - **rest**: url, method, headers, auth_type, auth credentials,
      request_template, response_mapping
    - **graphql**: url, headers, auth_type, auth credentials,
      query_template, response_mapping
    - **webhook_in**: expected_payload_schema, field_mapping
      (webhook_id and secret are auto-generated)
    - **webhook_out**: url, method, headers, trigger_events, payload_template
    - **database**: connection_string, db_type, query_template, field_mapping

    BC-001: Scoped to user's company_id.
    BC-011: JWT authentication required.
    """
    service = CustomIntegrationService(db)
    integration = service.create(
        company_id=user.company_id,
        integration_type=body.type,
        name=body.name,
        config=body.config,
    )
    return CustomIntegrationResponse(**integration)


@router.get(
    "",
    response_model=List[CustomIntegrationResponse],
)
def list_custom_integrations(
    type: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[CustomIntegrationResponse]:
    """List custom integrations for the authenticated user's company.

    Optional query params:
    - type: Filter by integration type
    - status: Filter by status (draft, active, disabled, error)

    BC-001: Scoped to user's company_id.
    """
    service = CustomIntegrationService(db)
    integrations = service.list(
        company_id=user.company_id,
        integration_type=type,
        status=status,
    )
    return [CustomIntegrationResponse(**i) for i in integrations]


@router.get(
    "/{integration_id}",
    response_model=CustomIntegrationResponse,
)
def get_custom_integration(
    integration_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomIntegrationResponse:
    """Get a single custom integration by ID.

    BC-001: Scoped to user's company_id.
    """
    service = CustomIntegrationService(db)
    integration = service.get(integration_id, user.company_id)

    if not integration:
        from app.exceptions import NotFoundError

        raise NotFoundError(
            message="Custom integration not found",
            details={"integration_id": integration_id},
        )

    return CustomIntegrationResponse(**integration)


@router.put(
    "/{integration_id}",
    response_model=CustomIntegrationResponse,
)
def update_custom_integration(
    integration_id: str,
    body: UpdateCustomIntegrationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomIntegrationResponse:
    """Update a custom integration's config, name, or settings.

    Only draft or active integrations can be updated.
    Changing config resets the consecutive error count.

    BC-001: Scoped to user's company_id.
    """
    service = CustomIntegrationService(db)
    integration = service.update(
        integration_id=integration_id,
        company_id=user.company_id,
        config=body.config,
        name=body.name,
        settings=body.settings,
    )
    return CustomIntegrationResponse(**integration)


@router.delete(
    "/{integration_id}",
    response_model=MessageResponse,
)
def delete_custom_integration(
    integration_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete a custom integration.

    BC-001: Scoped to user's company_id.
    """
    service = CustomIntegrationService(db)
    service.delete(integration_id, user.company_id)
    return MessageResponse(message="Custom integration deleted successfully.")


@router.post(
    "/{integration_id}/test",
    response_model=TestResponse,
)
def test_custom_integration(
    integration_id: str,
    body: TestCustomIntegrationRequest = TestCustomIntegrationRequest(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TestResponse:
    """Test a custom integration's connectivity.

    For REST/GraphQL: Makes a test HTTP request (10s timeout).
    For webhook_in: Validates configuration.
    For webhook_out: Sends a test payload to the configured URL.
    For database: Pings the database (5s timeout).

    If the test fails and the integration has 3+ consecutive failures,
    it will be automatically disabled.

    BC-001: Scoped to user's company_id.
    """
    service = CustomIntegrationService(db)
    result = service.test_connectivity(
        integration_id=integration_id,
        company_id=user.company_id,
        test_payload=body.test_payload,
        is_manual_test=True,  # D12-P5: User-initiated tests should not trigger auto-disable
    )
    return TestResponse(**result)


@router.post(
    "/{integration_id}/activate",
    response_model=ActivateResponse,
)
def activate_custom_integration(
    integration_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActivateResponse:
    """Activate a custom integration (draft → active).

    Only draft integrations can be activated. Consider testing
    the integration before activating it.

    BC-001: Scoped to user's company_id.
    """
    service = CustomIntegrationService(db)
    integration = service.activate(integration_id, user.company_id)
    return ActivateResponse(
        id=integration["id"],
        name=integration["name"],
        type=integration["type"],
        status=integration["status"],
        message="Integration activated successfully.",
    )


@router.post(
    "/{integration_id}/reactivate",
    response_model=CustomIntegrationResponse,
)
def reactivate_custom_integration(
    integration_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomIntegrationResponse:
    """Reactivate a disabled integration (resets to draft).

    Clears the error count and sets status back to draft so the
    integration can be re-tested and re-activated.

    BC-001: Scoped to user's company_id.
    """
    service = CustomIntegrationService(db)
    integration = service.reactivate(integration_id, user.company_id)
    return CustomIntegrationResponse(**integration)


# ── Outgoing Webhook Delivery Logs ─────────────────────────────────


@router.get(
    "/{integration_id}/deliveries",
    response_model=List[DeliveryLogResponse],
)
def get_delivery_logs(
    integration_id: str,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[DeliveryLogResponse]:
    """Get delivery logs for a specific outgoing webhook integration.

    Optional query params:
    - status: Filter by delivery status (pending/success/failed)

    BC-001: Scoped to user's company_id.
    """
    webhook_service = OutgoingWebhookService()
    logs = webhook_service.get_delivery_logs(
        company_id=user.company_id,
        integration_id=integration_id,
        status=status,
    )
    return [DeliveryLogResponse(**log) for log in logs]
