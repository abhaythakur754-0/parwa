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

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.integration_catalog import get_catalog, get_catalog_for_industry, get_integration_by_key, ParwaIndustry
from app.services.audit_service import log_audit, AuditAction, ActorType
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
    validate_credentials: bool = Field(default=True, description="Whether to validate credentials before saving")


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
        validate=body.validate_credentials,
    )

    # Phase 9: Audit log for integration connection
    try:
        log_audit(
            company_id=str(user.company_id),
            actor_id=str(user.id),
            actor_type=ActorType.USER.value,
            action=AuditAction.INTEGRATION_CALL.value,
            resource_type="integration",
            resource_id=integration.get("id"),
            new_value=f"Connected {body.integration_type}: {body.name}",
            db=db,
        )
    except Exception:
        pass  # BC-012: Audit logging must not break the main operation

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
async def api_delete_integration(
    integration_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete an integration.

    BC-001: Scoped to user's company_id.
    Phase 7: Cache is invalidated when integration is disconnected.
    """
    # Get integration type before deletion for cache invalidation
    service = IntegrationService(db)
    integration = service.get_integration(
        integration_id=integration_id,
        company_id=user.company_id,
    )
    integration_type = integration.integration_type if integration else None

    service.delete_integration(
        integration_id=integration_id,
        company_id=user.company_id,
    )

    # Phase 7: Invalidate all cached data for this integration
    if integration_type:
        try:
            from app.services.integration_cache_service import IntegrationCacheService
            cache_svc = IntegrationCacheService(company_id=user.company_id)
            await cache_svc.invalidate_on_disconnect(integration_type)
        except Exception:
            pass  # BC-012: Cache invalidation failure must not break deletion

    # Phase 9: Audit log for integration disconnect
    try:
        log_audit(
            company_id=str(user.company_id),
            actor_id=str(user.id),
            actor_type=ActorType.USER.value,
            action=AuditAction.INTEGRATION_DISCONNECT.value,
            resource_type="integration",
            resource_id=integration_id,
            new_value=f"Disconnected {integration_type or 'unknown'}",
            db=db,
        )
    except Exception:
        pass  # BC-012: Audit logging must not break the main operation

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


# ── Phase 10: Integration Health & Disconnect Endpoints ───────────────


@router.get(
    "/health",
    response_model=Dict[str, Any],
)
def api_integration_health(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get health status of all integrations for the company.

    Returns: circuit breaker states, rate limit usage, last test time,
    connected status for each integration.

    BC-001: Scoped to user's company_id.
    """
    result: Dict[str, Any] = {
        "company_id": user.company_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "integrations": {},
    }

    # Get connected integrations
    try:
        service = IntegrationService(db)
        integrations = service.get_integrations(company_id=user.company_id)
    except Exception:
        integrations = []

    # Get circuit breaker states
    cb_states = {}
    try:
        from app.core.parwa_core_bridge import get_parwa_circuit_breaker as get_circuit_breaker_manager
        cb_manager = get_circuit_breaker_manager()
        cb_states = cb_manager.get_all_states()
    except Exception:
        pass

    # Get rate limit status
    rate_limit_status = {}
    try:
        from app.core.integration_rate_limiter import get_integration_rate_limiter
        rate_limiter = get_integration_rate_limiter()
        rate_limit_status = rate_limiter.get_all_status(user.company_id)
    except Exception:
        pass

    # Get provider status from ExternalToolBus
    provider_status = {}
    try:
        from app.core.external_tool_bus import external_tool_bus
        provider_status = external_tool_bus.get_provider_status()
    except Exception:
        pass

    # Get disconnect handler status
    disconnect_handler = None
    try:
        from app.core.integration_disconnect_handler import get_integration_disconnect_handler
        disconnect_handler = get_integration_disconnect_handler()
    except Exception:
        pass

    # Build per-integration health
    for integration in integrations:
        intg_type = integration.get("type", "unknown")
        intg_id = integration.get("id", "")

        health_entry: Dict[str, Any] = {
            "id": intg_id,
            "type": intg_type,
            "name": integration.get("name", ""),
            "status": integration.get("status", "unknown"),
            "connected": True,
            "last_test_at": integration.get("last_test_at"),
            "last_test_result": integration.get("last_test_result"),
        }

        # Circuit breaker state
        if intg_type in cb_states:
            health_entry["circuit_breaker"] = cb_states[intg_type]
        else:
            health_entry["circuit_breaker"] = {"state": "closed", "is_available": True}

        # Rate limit status
        if intg_type in rate_limit_status:
            health_entry["rate_limit"] = rate_limit_status[intg_type]
        else:
            health_entry["rate_limit"] = {"is_limited": False}

        # Disconnect status
        if disconnect_handler:
            health_entry["connected"] = disconnect_handler.is_integration_connected(
                user.company_id, intg_id,
            )
            disconnect_record = disconnect_handler.get_disconnect_status(
                user.company_id, intg_id,
            )
            if disconnect_record:
                health_entry["disconnect_record"] = disconnect_record

        result["integrations"][intg_id] = health_entry

    # Add overall circuit breaker health summary
    try:
        from app.core.parwa_core_bridge import get_parwa_circuit_breaker as get_circuit_breaker_manager
        cb_manager = get_circuit_breaker_manager()
        result["circuit_breaker_health"] = cb_manager.get_health_summary()
    except Exception:
        result["circuit_breaker_health"] = {"status": "unknown"}

    # Add provider statuses
    result["providers"] = provider_status

    return result


class DisconnectIntegrationRequest(BaseModel):
    """Request to disconnect an integration with cleanup."""
    reason: str = Field(default="user_action", description="Disconnect reason: user_action, provider_error, maintenance")


@router.post(
    "/{integration_id}/disconnect",
    response_model=Dict[str, Any],
)
async def api_disconnect_integration(
    integration_id: str,
    body: DisconnectIntegrationRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Properly disconnect an integration with full cleanup.

    Phase 10: Performs instant cleanup including:
    - Stops all pending API calls
    - Invalidates cached data
    - Removes rate limit slots
    - Opens the circuit breaker
    - Notifies AI pipeline

    BC-001: Scoped to user's company_id.
    """
    # Get integration details before disconnect
    service = IntegrationService(db)
    try:
        integration = service.get_integration(
            integration_id=integration_id,
            company_id=user.company_id,
        )
        integration_name = integration.integration_type if integration else ""
    except Exception:
        integration_name = ""

    # Use the disconnect handler for full cleanup
    try:
        from app.core.integration_disconnect_handler import get_integration_disconnect_handler
        handler = get_integration_disconnect_handler()
        result = handler.disconnect_integration(
            company_id=user.company_id,
            integration_id=integration_id,
            integration_name=integration_name,
            reason=body.reason if body else "user_action",
        )
    except Exception as exc:
        result = {
            "company_id": user.company_id,
            "integration_id": integration_id,
            "success": False,
            "error": f"Disconnect handler failed: {str(exc)[:200]}",
            "cleanup_steps": [],
        }

    # Update integration status in DB
    try:
        service.update_integration_status(
            integration_id=integration_id,
            company_id=user.company_id,
            status="disconnected",
        )
    except Exception:
        pass  # BC-008: Status update failure must not break disconnect

    # Phase 7: Invalidate cache
    if integration_name:
        try:
            from app.services.integration_cache_service import IntegrationCacheService
            cache_svc = IntegrationCacheService(company_id=user.company_id)
            await cache_svc.invalidate_on_disconnect(integration_name)
        except Exception:
            pass  # BC-012: Cache invalidation failure must not break disconnect

    # Audit log
    try:
        log_audit(
            company_id=str(user.company_id),
            actor_id=str(user.id),
            actor_type=ActorType.USER.value,
            action=AuditAction.INTEGRATION_DISCONNECT.value,
            resource_type="integration",
            resource_id=integration_id,
            new_value=f"Disconnected {integration_name or 'unknown'}: {body.reason if body else 'user_action'}",
            db=db,
        )
    except Exception:
        pass  # BC-012: Audit logging must not break the main operation

    return result


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


# ── Outbound Webhook Endpoints (Phase 6) ────────────────────────────


class CreateOutboundWebhookRequest(BaseModel):
    """Request to register an outbound webhook endpoint."""
    url: str = Field(..., min_length=1, max_length=2048, description="Webhook URL to receive events")
    events: List[str] = Field(..., min_length=1, description="Event types to subscribe to")
    description: str = Field(default="", max_length=255, description="Optional description")


class UpdateOutboundWebhookRequest(BaseModel):
    """Request to update an outbound webhook."""
    url: str | None = None
    events: List[str] | None = None
    active: bool | None = None
    description: str | None = None


class OutboundWebhookResponse(BaseModel):
    """Response for an outbound webhook."""
    id: str
    url: str
    events: List[str]
    secret: str
    active: bool
    last_triggered_at: str | None = None
    failure_count: int = 0
    description: str | None = None
    created_at: str


@router.get(
    "/webhooks",
    response_model=List[OutboundWebhookResponse],
)
def api_list_outbound_webhooks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[OutboundWebhookResponse]:
    """List all outbound webhooks for the authenticated user's company.

    BC-001: Scoped to user's company_id.
    """
    from database.models.outbound_webhook import OutboundWebhook

    webhooks = (
        db.query(OutboundWebhook)
        .filter(OutboundWebhook.company_id == user.company_id)
        .order_by(OutboundWebhook.created_at.desc())
        .all()
    )

    return [
        OutboundWebhookResponse(
            id=wh.id,
            url=wh.url,
            events=wh.events or [],
            secret=wh.secret,
            active=wh.active,
            last_triggered_at=wh.last_triggered_at.isoformat() if wh.last_triggered_at else None,
            failure_count=wh.failure_count,
            description=wh.description,
            created_at=wh.created_at.isoformat() if wh.created_at else "",
        )
        for wh in webhooks
    ]


@router.post(
    "/webhooks",
    response_model=OutboundWebhookResponse,
    status_code=201,
)
def api_create_outbound_webhook(
    body: CreateOutboundWebhookRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutboundWebhookResponse:
    """Register a new outbound webhook endpoint.

    Per Phase 6: Client configures webhook URL + events.
    The system sends HTTP POST with HMAC signature when events fire.
    BC-001: Scoped to user's company_id.
    BC-003: HMAC signing secret auto-generated.
    """
    from database.models.outbound_webhook import OutboundWebhook

    # Validate event types
    valid_events = set(OutboundWebhook.VALID_EVENTS)
    invalid_events = set(body.events) - valid_events
    if invalid_events:
        from app.exceptions import ValidationError
        raise ValidationError(
            message=f"Invalid event types: {', '.join(invalid_events)}",
            details={"valid_events": OutboundWebhook.VALID_EVENTS},
        )

    webhook = OutboundWebhook(
        company_id=user.company_id,
        url=body.url,
        events=body.events,
        description=body.description,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    # Register webhook with third-party providers if applicable
    _register_webhook_with_providers(webhook, user.company_id, db)

    return OutboundWebhookResponse(
        id=webhook.id,
        url=webhook.url,
        events=webhook.events or [],
        secret=webhook.secret,
        active=webhook.active,
        last_triggered_at=None,
        failure_count=0,
        description=webhook.description,
        created_at=webhook.created_at.isoformat() if webhook.created_at else "",
    )


@router.delete(
    "/webhooks/{webhook_id}",
    response_model=MessageResponse,
)
def api_delete_outbound_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete an outbound webhook.

    BC-001: Scoped to user's company_id.
    """
    from database.models.outbound_webhook import OutboundWebhook

    webhook = (
        db.query(OutboundWebhook)
        .filter(
            OutboundWebhook.id == webhook_id,
            OutboundWebhook.company_id == user.company_id,
        )
        .first()
    )
    if not webhook:
        from app.exceptions import NotFoundError
        raise NotFoundError(message="Webhook not found")

    db.delete(webhook)
    db.commit()
    return MessageResponse(message="Webhook deleted successfully.")


@router.post(
    "/webhooks/{webhook_id}/test",
    response_model=Dict[str, Any],
)
def api_test_outbound_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Send a test event to an outbound webhook endpoint.

    Per Phase 6: Verifies the endpoint is reachable and accepts payloads.
    Sends a ping event with HMAC signature.
    BC-001: Scoped to user's company_id.
    """
    import hmac
    import hashlib
    import json as json_lib
    import httpx

    from database.models.outbound_webhook import OutboundWebhook

    webhook = (
        db.query(OutboundWebhook)
        .filter(
            OutboundWebhook.id == webhook_id,
            OutboundWebhook.company_id == user.company_id,
        )
        .first()
    )
    if not webhook:
        from app.exceptions import NotFoundError
        raise NotFoundError(message="Webhook not found")

    # Build test payload
    test_payload = {
        "event": "webhook.test",
        "webhook_id": webhook.id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "message": "This is a test event from PARWA",
            "company_id": user.company_id,
        },
    }

    payload_str = json_lib.dumps(test_payload, separators=(",", ":"))
    signature = hmac.new(
        webhook.secret.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Parwa-Signature": f"sha256={signature}",
        "X-Parwa-Event": "webhook.test",
        "X-Parwa-Delivery": str(uuid.uuid4()),
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(webhook.url, content=payload_str, headers=headers)
        success = 200 <= resp.status_code < 300
        result = {
            "success": success,
            "status_code": resp.status_code,
            "message": "Test event delivered successfully" if success else f"Endpoint returned {resp.status_code}",
            "webhook_id": webhook.id,
        }
    except Exception as e:
        result = {
            "success": False,
            "status_code": 0,
            "message": f"Failed to reach endpoint: {str(e)[:200]}",
            "webhook_id": webhook.id,
        }

    # Update failure count if needed
    if not result["success"]:
        webhook.failure_count = (webhook.failure_count or 0) + 1
        webhook.last_error = result["message"][:500]
        db.commit()

    return result


def _register_webhook_with_providers(webhook, company_id: str, db: Session) -> None:
    """Register the webhook URL with third-party providers.

    Per Phase 6: When client connects a tool, Parwa registers the webhook
    URL with that provider so Parwa receives real-time events.

    This is a best-effort operation — if registration fails, the webhook
    still works for PARWA-originated events. Provider registration enables
    incoming events from the third party.
    """
    import logging
    logger = logging.getLogger("parwa.webhooks.registration")

    # Get connected integrations for this company
    try:
        service = IntegrationService(db)
        integrations = service.get_integrations(company_id=company_id, active_only=True)
    except Exception:
        integrations = []

    for integration in integrations:
        integration_type = integration.get("type", "")
        try:
            if integration_type == "shopify":
                # Shopify webhook registration
                _register_shopify_webhook(webhook, integration)
            elif integration_type in ("hubspot", "salesforce"):
                # CRM webhook registration (contact.created, deal.updated)
                _register_crm_webhook(webhook, integration)
            # Other providers can be added here
        except Exception as e:
            logger.warning(
                f"Failed to register webhook with {integration_type}: {e}",
                extra={"webhook_id": webhook.id, "integration_type": integration_type},
            )


def _register_shopify_webhook(webhook, integration) -> None:
    """Register webhook URL with Shopify for order events."""
    import httpx
    config = integration.get("config", {})
    shop_domain = config.get("shop_domain", "")
    access_token = config.get("access_token", "")
    if not shop_domain or not access_token:
        return

    # Map PARWA events to Shopify webhook topics
    event_mapping = {
        "ticket.created": "orders/create",
        "ticket.resolved": "orders/fulfilled",
        "integration.error": "app/uninstalled",
    }

    with httpx.Client(timeout=10.0) as client:
        for parwa_event in (webhook.events or []):
            shopify_topic = event_mapping.get(parwa_event)
            if not shopify_topic:
                continue
            try:
                client.post(
                    f"https://{shop_domain}/admin/api/2024-01/webhooks.json",
                    headers={"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"},
                    json={
                        "webhook": {
                            "topic": shopify_topic,
                            "address": webhook.url,
                            "format": "json",
                        }
                    },
                )
            except Exception:
                pass  # Best-effort


def _register_crm_webhook(webhook, integration) -> None:
    """Register webhook URL with CRM providers (HubSpot/Salesforce)."""
    # CRM webhook registration requires OAuth and specific API calls
    # This is a placeholder that logs the registration attempt
    import logging
    logger = logging.getLogger("parwa.webhooks.crm_registration")
    logger.info(
        f"CRM webhook registration requested for {integration.get('type', 'unknown')}",
        extra={"webhook_id": webhook.id, "integration_type": integration.get("type")},
    )


# ── CRM Analysis Endpoint ─────────────────────────────────────────────


class AnalyzeIntegrationsResponse(BaseModel):
    """Response from CRM analysis with recommendations."""

    company_id: str
    analyzed_at: str
    connected_integrations: List[Dict[str, Any]]
    data_profile: Dict[str, Any]
    detected_gaps: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    analysis_summary: str


@router.post(
    "/analyze",
    response_model=AnalyzeIntegrationsResponse,
)
async def api_analyze_integrations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyzeIntegrationsResponse:
    """Analyze connected CRM data and recommend missing integrations.

    This endpoint:
    1. Scans all active integrations for the company
    2. Gathers data profiles (contacts, orders, products, etc.)
    3. Detects gaps in the current setup
    4. Uses LLM to generate personalized recommendations

    Business Impact:
    - Reduces user confusion about which integrations to connect
    - Increases activation rate (more integrations = more value locked in)
    - Personalized suggestions based on actual data patterns

    BC-001: Scoped to authenticated user's company_id.
    """
    # ── EXTERNAL CRM ANALYSER (not local code) ──
    from app.core.crm_analyser_client import (
        analyze_crm_external,
        collect_tenant_tickets,
        get_crm_analyser_url,
    )

    if not get_crm_analyser_url():
        return AnalyzeIntegrationsResponse(
            company_id=str(user.company_id),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            connected_integrations=[],
            data_profile={},
            detected_gaps=[],
            recommendations=[],
            analysis_summary="CRM analyser not configured.",
        )

    # Collect tickets + send to external analyser
    tickets = collect_tenant_tickets(db, str(user.company_id), days=30)
    result = await analyze_crm_external(
        tickets=tickets,
        company_name=getattr(user, "company_name", "Unknown"),
    )

    # Build the response
    recommendations = [
        {"name": name, "priority": "high", "reason": "Recommended by CRM analysis"}
        for name in result.get("integrations", [])
    ]
    data_profile = {"total_tickets": result.get("tickets_scanned", 0)}
    analysis_summary = result.get("error") or f"Analyzed {result.get('tickets_scanned', 0)} tickets. Found {len(result.get('integrations', []))} integrations needed."

    # ── Save to CRMAnalysisResult table (persists across logins) ──
    # Stores the full analysis so the user can see their recommendations
    # on the dashboard later, not just during onboarding.
    try:
        from database.models.crm_analysis import CRMAnalysisResult
        analysis_record = CRMAnalysisResult(
            company_id=str(user.company_id),
            data_profile=data_profile,
            connected_integrations=[],
            detected_gaps=[],
            recommendations=recommendations,
            analysis_summary=analysis_summary,
            is_actioned=False,
            recommendations_accepted=[],
        )
        db.add(analysis_record)
        db.commit()
    except Exception as exc:
        # Don't fail the whole request if DB save fails — the analysis
        # result is still returned to the frontend.
        import logging
        logging.getLogger("parwa.integrations").warning(
            "Failed to save CRMAnalysisResult: %s", str(exc)[:200]
        )

    # Convert to response format
    return AnalyzeIntegrationsResponse(
        company_id=str(user.company_id),
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        connected_integrations=[],
        data_profile=data_profile,
        detected_gaps=[],
        recommendations=recommendations,
        analysis_summary=analysis_summary,
    )


@router.get(
    "/analyze/stored",
)
async def api_get_stored_analysis(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve most recent stored CRM analysis for dashboard display.
    
    Returns the analysis that was saved during onboarding so users can
    see their recommendations in the dashboard without re-running analysis.
    
    BC-001: Scoped to authenticated user's company_id.
    """
    # ── EXTERNAL: get stored analysis from DB (saved by external analyser) ──
    from database.base import SessionLocal
    from database.models.core import CRMAnalysisResult
    _db = SessionLocal()
    try:
        result = _db.query(CRMAnalysisResult).filter(
            CRMAnalysisResult.company_id == str(user.company_id),
        ).order_by(CRMAnalysisResult.created_at.desc()).first()
        if result:
            import json as _json
            result = _json.loads(result.analysis_json) if result.analysis_json else {}
        else:
            result = {}
    finally:
        _db.close()
    
    if not result:
        return {
            "success": False,
            "message": "No stored analysis found. Run analysis first.",
        }
    
    return {
        "success": True,
        **result,
    }
