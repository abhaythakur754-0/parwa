"""
PARWA Integrations Router

Endpoints for third-party integration management.

- GET  /api/integrations/catalog          — List catalog (with optional industry filter)
- GET  /api/integrations/available         — List available integration types (legacy)
- POST /api/integrations                   — Create a new integration
- GET  /api/integrations                   — List company integrations
- POST /api/integrations/{id}/test         — Test an existing integration
- DELETE /api/integrations/{id}            — Delete an integration

BC-001: All operations scoped to authenticated user's company_id.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.integration_catalog import get_catalog, get_catalog_for_industry, get_integration_by_key, ParwaIndustry
from app.services.integration_service import IntegrationService
from database.base import get_db
from database.models.core import User

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


# ── Request Schemas ────────────────────────────────────────────────


class CreateIntegrationRequest(BaseModel):
    """Request to create a new integration."""

    integration_type: str = Field(..., description="Integration key from catalog, e.g. hubspot, shopify, slack")
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Integration config with credentials")
    validate: bool = Field(default=True, description="Whether to validate credentials before saving")


class IndustryChangeImpactRequest(BaseModel):
    """Request to check industry change impact."""
    new_industry: str = Field(..., description="New industry: saas, ecommerce, logistics, other")
    current_industry: str = Field(..., description="Current industry")


class IndustryChangeImpactResponse(BaseModel):
    """Response showing impact of industry change on integrations."""
    new_industry: str
    current_industry: str
    connected_integrations: List[Dict[str, Any]]
    still_recommended: List[str]
    no_longer_suggested: List[str]
    newly_suggested: List[str]
    message: str


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
    "/catalog",
    response_model=List[Dict[str, Any]],
)
def get_integration_catalog(
    industry: Optional[str] = Query(None, description="Filter by industry: saas, ecommerce, logistics, other"),
) -> List[Dict[str, Any]]:
    """Return the unified integration catalog with optional industry filtering.

    Per GAP 3: Industry is a SUGGESTION filter, not a restriction.
    Per D3: 'other' shows ALL integrations.
    If no industry specified, returns the full catalog.
    """
    if industry:
        return get_catalog_for_industry(industry)
    return get_catalog()


@router.get(
    "/available",
    response_model=List[Dict[str, Any]],
)
def list_available_integrations() -> List[Dict[str, Any]]:
    """List all available integration types and their required fields.

    Legacy endpoint — prefer /catalog for full metadata.
    No authentication required (public info).
    """
    return get_catalog()


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
    service = IntegrationService(db)
    integration = service.create_integration(
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
    Optional status filter: pending, active, error, disconnected.
    """
    service = IntegrationService(db)
    integrations = service.get_integrations(
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
    service = IntegrationService(db)
    result = service.test_integration(
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
    service = IntegrationService(db)
    service.delete_integration(
        integration_id=integration_id,
        company_id=user.company_id,
    )
    return MessageResponse(message="Integration deleted successfully.")


@router.post(
    "/industry-change-impact",
    response_model=IndustryChangeImpactResponse,
)
def api_industry_change_impact(
    body: IndustryChangeImpactRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndustryChangeImpactResponse:
    """Check the impact of changing industry on existing integrations.

    Per GAP 10: Industry change NEVER disconnects integrations.
    Existing connections STAY connected. Only the suggestion filter changes.
    Clients can always connect tools outside their industry.

    Returns:
    - still_recommended: integrations that are suggested in BOTH industries
    - no_longer_suggested: connected integrations not in new industry's suggestions
    - newly_suggested: integrations newly suggested for the new industry
    """
    # Get suggested integration keys for both industries
    current_suggested = {i["key"] for i in get_catalog_for_industry(body.current_industry)}
    new_suggested = {i["key"] for i in get_catalog_for_industry(body.new_industry)}

    # Get currently connected integrations
    service = IntegrationService(db)
    connected = service.get_integrations(company_id=user.company_id, active_only=True)
    connected_keys = {i["type"] for i in connected}

    # Categorize
    still_recommended = sorted(connected_keys & new_suggested)
    no_longer_suggested = sorted(connected_keys - new_suggested)
    newly_suggested = sorted((new_suggested - current_suggested) - connected_keys)

    # Build connected integration details
    connected_details = []
    for i in connected:
        catalog_entry = get_integration_by_key(i["type"])
        in_new_industry = i["type"] in new_suggested
        connected_details.append({
            "key": i["type"],
            "name": i["name"],
            "status": i["status"],
            "category": catalog_entry.category.value if catalog_entry else "custom",
            "in_new_industry_suggestions": in_new_industry,
        })

    # Build message
    if no_longer_suggested:
        msg = (
            f"You're changing from {body.current_industry} to {body.new_industry}. "
            f"{len(no_longer_suggested)} integration(s) will still work but are no longer suggested for {body.new_industry}. "
            f"Your tickets, knowledge base, and billing are NOT affected."
        )
    else:
        msg = (
            f"Changing from {body.current_industry} to {body.new_industry} will not affect any of your "
            f"connected integrations. {len(newly_suggested)} new integrations are suggested for {body.new_industry}."
        )

    return IndustryChangeImpactResponse(
        new_industry=body.new_industry,
        current_industry=body.current_industry,
        connected_integrations=connected_details,
        still_recommended=still_recommended,
        no_longer_suggested=no_longer_suggested,
        newly_suggested=newly_suggested,
        message=msg,
    )


# ── Custom Connector Endpoints (Tier 3 + Tier 2) ────────────────────


class CreateCustomConnectorRequest(BaseModel):
    """Request to create a custom REST connector (Tier 3)."""
    name: str = Field(..., min_length=1, max_length=100, description="Connector display name")
    base_url: str = Field(..., description="Base URL for API calls")
    auth_type: str = Field(..., description="Auth type: bearer, api_key_header, api_key_query, basic_auth, oauth2")
    auth_config: Dict[str, Any] = Field(default_factory=dict, description="Auth credentials")
    actions: List[Dict[str, Any]] = Field(..., min_length=1, description="Action definitions")
    description: str = Field(default="", description="Connector description")
    test_endpoint: str = Field(default="", description="Override test endpoint")


class UpdateCustomConnectorRequest(BaseModel):
    """Request to update a custom REST connector."""
    name: str | None = None
    base_url: str | None = None
    auth_type: str | None = None
    auth_config: Dict[str, Any] | None = None
    actions: List[Dict[str, Any]] | None = None


class ImportOpenAPIRequest(BaseModel):
    """Request to import an OpenAPI spec (Tier 2)."""
    url: str | None = Field(None, description="URL to the OpenAPI spec")
    file_content: str | None = Field(None, description="Raw file content (JSON or YAML)")
    filename: str = Field(default="", description="Original filename for context")
    name: str | None = Field(None, description="Override integration name")
    base_url: str | None = Field(None, description="Override base URL")
    auth_type: str | None = Field(None, description="Override auth type")
    auth_config: Dict[str, Any] = Field(default_factory=dict, description="Auth credentials")
    actions: List[Dict[str, Any]] | None = Field(None, description="Override actions (edit after import)")


@router.post(
    "/custom/connector",
    response_model=Dict[str, Any],
    status_code=201,
)
def api_create_custom_connector(
    body: CreateCustomConnectorRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a custom REST connector (Tier 3).

    Per D4: PARWA and PARWA High only.
    Per GAP 4: Custom API add-on = $49/month.
    Per D13: No per-action or per-call charges.

    BC-001: Scoped to user's company_id.
    """
    from app.services.custom_connector_service import CustomConnectorService

    service = CustomConnectorService(db)
    result = service.create_connector(
        company_id=user.company_id,
        name=body.name,
        base_url=body.base_url,
        auth_type=body.auth_type,
        auth_config=body.auth_config,
        actions=body.actions,
        description=body.description,
        source="custom",
        test_endpoint=body.test_endpoint,
    )
    return result


@router.get(
    "/custom/connectors",
    response_model=List[Dict[str, Any]],
)
def api_list_custom_connectors(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all custom connectors for the authenticated user's company.

    BC-001: Scoped to user's company_id.
    """
    from app.services.custom_connector_service import CustomConnectorService

    service = CustomConnectorService(db)
    return service.get_connectors(company_id=user.company_id)


@router.get(
    "/custom/connectors/{connector_id}",
    response_model=Dict[str, Any],
)
def api_get_custom_connector(
    connector_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a single custom connector by ID.

    BC-001: Scoped to user's company_id.
    """
    from app.services.custom_connector_service import CustomConnectorService

    service = CustomConnectorService(db)
    result = service.get_connector(connector_id=connector_id, company_id=user.company_id)
    if not result:
        from app.exceptions import NotFoundError
        raise NotFoundError(message="Connector not found")
    return result


@router.put(
    "/custom/connectors/{connector_id}",
    response_model=Dict[str, Any],
)
def api_update_custom_connector(
    connector_id: str,
    body: UpdateCustomConnectorRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a custom connector's configuration.

    BC-001: Scoped to user's company_id.
    """
    from app.services.custom_connector_service import CustomConnectorService

    service = CustomConnectorService(db)
    updates = {k: v for k, v in body.dict().items() if v is not None}
    return service.update_connector(
        connector_id=connector_id,
        company_id=user.company_id,
        updates=updates,
    )


@router.delete(
    "/custom/connectors/{connector_id}",
    response_model=MessageResponse,
)
def api_delete_custom_connector(
    connector_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete a custom connector.

    BC-001: Scoped to user's company_id.
    """
    from app.services.custom_connector_service import CustomConnectorService

    service = CustomConnectorService(db)
    service.delete_connector(connector_id=connector_id, company_id=user.company_id)
    return MessageResponse(message="Custom connector deleted successfully.")


@router.post(
    "/custom/connectors/{connector_id}/test",
    response_model=Dict[str, Any],
)
def api_test_custom_connector(
    connector_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Test a custom connector's connectivity.

    BC-001: Scoped to user's company_id.
    """
    from app.services.custom_connector_service import CustomConnectorService

    service = CustomConnectorService(db)
    return service.test_connector(connector_id=connector_id, company_id=user.company_id)


@router.post(
    "/openapi-import",
    response_model=Dict[str, Any],
)
def api_import_openapi(
    body: ImportOpenAPIRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Import an OpenAPI/Swagger spec and auto-generate a connector (Tier 2).

    Per D4: PARWA High only.
    Per GAP 5: Max 100 endpoints per spec. Skip deprecated endpoints.

    BC-001: Scoped to user's company_id.

    Two modes:
    1. Provide URL → backend fetches and parses spec
    2. Provide file_content → backend parses directly

    Returns the parsed spec with auto-generated actions.
    Client reviews, then saves via /custom/connector with source=openapi_import.
    """
    from app.services.openapi_importer_service import OpenAPIImporterService

    importer = OpenAPIImporterService()

    # Parse the spec
    if body.url:
        parsed = importer.import_from_url(body.url)
    elif body.file_content:
        parsed = importer.import_from_content(body.file_content, body.filename)
    else:
        raise ValidationError(
            message="Either 'url' or 'file_content' must be provided",
            details={},
        )

    # Apply overrides from client
    if body.name:
        parsed["name"] = body.name
    if body.base_url:
        parsed["base_url"] = body.base_url
    if body.auth_type:
        parsed["auth_type"] = body.auth_type
    if body.actions is not None:
        parsed["actions"] = body.actions

    # If auth_config provided, include it for the save step
    if body.auth_config:
        parsed["auth_config"] = body.auth_config
    else:
        parsed["auth_config"] = {}

    return parsed


@router.post(
    "/openapi-import/save",
    response_model=Dict[str, Any],
    status_code=201,
)
def api_save_openapi_import(
    body: Dict[str, Any],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Save an OpenAPI import as a custom connector.

    After the client reviews and edits the parsed spec from /openapi-import,
    they send the final version here to create the connector.

    BC-001: Scoped to user's company_id.
    """
    from app.services.custom_connector_service import CustomConnectorService

    service = CustomConnectorService(db)
    return service.create_connector(
        company_id=user.company_id,
        name=body.get("name", "Imported API"),
        base_url=body.get("base_url", ""),
        auth_type=body.get("auth_type", "bearer"),
        auth_config=body.get("auth_config", {}),
        actions=body.get("actions", []),
        description=body.get("description", ""),
        source="openapi_import",
        test_endpoint=body.get("test_endpoint", ""),
    )
