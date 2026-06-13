"""
PARWA Custom Connector Router

API endpoints for Tier 3 (Custom REST Connector) and Tier 2 (OpenAPI Import).

Per GAP 4: Custom REST Connector — PARWA and PARWA High only.
Per GAP 5: OpenAPI Import — PARWA High only.
Per D13: Custom API = $49/month add-on, no per-action charges.

BC-001: All operations scoped to company_id.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.services.custom_connector_service import CustomConnectorService
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/integrations/custom", tags=["Custom Connectors"])


# ── Request Schemas ────────────────────────────────────────────────


class ActionDefinition(BaseModel):
    """A single action in a custom connector."""
    name: str = Field(..., min_length=1, max_length=100)
    method: str = Field(..., pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    path: str = Field(..., min_length=1, description="API path, e.g. /invoices")
    description: str = Field(..., min_length=5, max_length=1000, description="Natural language description for AI tool selection")
    required_params: List[str] = Field(default_factory=list)
    optional_params: List[str] = Field(default_factory=list)
    response_key: str = Field(default="", description="JSON path to key data, e.g. data.balance")


class CreateCustomConnectorRequest(BaseModel):
    """Request to create a Tier 3 Custom REST Connector."""
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., description="Base URL, e.g. https://billing.internal.company.com/api/v1")
    auth_type: str = Field(..., pattern="^(bearer|api_key_header|api_key_query|basic_auth|oauth2)$")
    auth_credentials: Dict[str, Any] = Field(default_factory=dict)
    actions: List[ActionDefinition] = Field(..., min_length=1, max_length=100)
    test_endpoint: Optional[str] = Field(None, description="Override default GET {base_url}/health")
    variant: str = Field(default="parwa", pattern="^(parwa|parwa_high)$")


class ImportOpenAPIRequest(BaseModel):
    """Request to import an OpenAPI spec (Tier 2)."""
    name: Optional[str] = Field(None, description="Override spec title")
    spec_url: Optional[str] = Field(None, description="URL to OpenAPI JSON/YAML spec")
    spec_content: Optional[Dict[str, Any]] = Field(None, description="Raw OpenAPI spec object")
    base_url_override: Optional[str] = Field(None, description="Override base URL from spec")
    auth_type: str = Field(default="bearer")
    auth_credentials: Optional[Dict[str, Any]] = Field(None)
    variant: str = Field(default="parwa_high", pattern="^parwa_high$")


class ConnectorResponse(BaseModel):
    """Response with connector details."""
    id: str
    company_id: str
    type: str
    name: str
    status: str
    config: Dict[str, Any]
    settings: Dict[str, Any]
    error_message: Optional[str] = None
    created_at: str


# ── Endpoints ──────────────────────────────────────────────────────


@router.post(
    "/connector",
    response_model=ConnectorResponse,
    status_code=201,
)
def create_custom_connector(
    body: CreateCustomConnectorRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectorResponse:
    """Create a Tier 3 Custom REST Connector.

    Per GAP 4: Client defines base_url, auth, and actions manually.
    Per D4: Available for PARWA and PARWA High only.
    Per D13: Custom API add-on = $49/month, no per-action charges.
    """
    service = CustomConnectorService(db)
    result = service.create_custom_connector(
        company_id=user.company_id,
        name=body.name,
        base_url=body.base_url,
        auth_type=body.auth_type,
        auth_credentials=body.auth_credentials,
        actions=[a.model_dump() for a in body.actions],
        test_endpoint=body.test_endpoint,
        variant=body.variant,
    )
    return ConnectorResponse(**result)


@router.post(
    "/openapi-import",
    response_model=ConnectorResponse,
    status_code=201,
)
def import_openapi_spec(
    body: ImportOpenAPIRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConnectorResponse:
    """Import an OpenAPI specification and auto-generate a connector (Tier 2).

    Per GAP 5: Client provides OpenAPI/Swagger spec URL or file.
    Per D4: Available for PARWA High only.
    """
    service = CustomConnectorService(db)
    result = service.import_openapi_spec(
        company_id=user.company_id,
        name=body.name,
        spec_url=body.spec_url,
        spec_content=body.spec_content,
        base_url_override=body.base_url_override,
        auth_type=body.auth_type,
        auth_credentials=body.auth_credentials,
        variant=body.variant,
    )
    return ConnectorResponse(**result)
