"""
PARWA Jarvis Integration API

Endpoints for the Jarvis onboarding integration setup flow.
These endpoints allow Jarvis to guide clients through connecting
their integration providers (email, SMS, payment, CRM, etc.).

All endpoints require authentication (get_current_user).

BC-001: All operations scoped to authenticated user's company_id.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.providers import ProviderRegistry, ApiKeyDetector, ProviderFactory
from app.core.providers.base import BaseProvider, ProviderCategory, ConnectionStatus
from app.logger import get_logger
from database.base import get_db
from database.models.core import User
from database.models.integration import Integration

logger = get_logger("jarvis_integrations")

router = APIRouter(prefix="/api/jarvis/integrations", tags=["Jarvis Integrations"])


# ── Request / Response Schemas ──────────────────────────────────────


class DetectKeyRequest(BaseModel):
    """Request to auto-detect a provider from an API key."""

    api_key: str = Field(..., min_length=1, description="API key to detect")


class DetectKeyResponse(BaseModel):
    """Response with detected provider information."""

    provider_type: str
    category: Optional[str] = None
    confidence: float
    name: Optional[str] = None
    matches: List[str] = Field(default_factory=list)


class TestConnectionRequest(BaseModel):
    """Request to test a provider connection."""

    provider_type: str = Field(..., description="Provider key (e.g. 'sendgrid', 'twilio')")
    category: str = Field(..., description="Provider category (e.g. 'email', 'sms')")
    credentials: Dict[str, Any] = Field(
        ..., description="Provider credentials dict"
    )


class TestConnectionResponse(BaseModel):
    """Response with connection test result."""

    success: bool
    message: str
    provider_info: Optional[Dict[str, Any]] = None


class ConnectProviderRequest(BaseModel):
    """Request to connect (save) a provider integration."""

    provider_type: str = Field(..., description="Provider key (e.g. 'sendgrid', 'twilio')")
    category: str = Field(..., description="Provider category (e.g. 'email', 'sms')")
    credentials: Dict[str, Any] = Field(
        ..., description="Provider credentials dict"
    )
    company_id: str = Field(..., description="Company ID to associate with")
    name: Optional[str] = Field(
        default=None, description="Optional display name for this integration"
    )


class ConnectProviderResponse(BaseModel):
    """Response after connecting a provider."""

    success: bool
    connection_id: str
    status: str
    message: Optional[str] = None


class IntegrationStatusItem(BaseModel):
    """Single integration status entry."""

    id: str
    company_id: str
    provider_type: str
    category: str
    name: Optional[str] = None
    status: str
    last_tested_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None


class IntegrationStatusResponse(BaseModel):
    """Response with all integration statuses for a company."""

    company_id: str
    integrations: List[IntegrationStatusItem]
    total: int


class ProviderInfoResponse(BaseModel):
    """Information about a single provider."""

    provider_type: str
    name: str
    description: Optional[str] = None
    setup_difficulty: Optional[str] = None
    setup_time: Optional[str] = None
    required_fields: List[Dict[str, Any]] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    credentials_help: Optional[str] = None


class CategoryProvidersResponse(BaseModel):
    """Response with all providers for a category."""

    category: str
    category_name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    providers: List[ProviderInfoResponse] = Field(default_factory=list)


class DisconnectResponse(BaseModel):
    """Response after disconnecting a provider."""

    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: Dict[str, Any]


# ── Knowledge Base Loader ───────────────────────────────────────────


def _load_knowledge_base() -> Dict[str, Any]:
    """Load the integration providers knowledge base JSON.

    Returns an empty dict if the file is not found or invalid,
    so the API still works (just without rich metadata).
    """
    try:
        import pathlib

        kb_path = (
            pathlib.Path(__file__).resolve().parent.parent
            / "data"
            / "jarvis_knowledge"
            / "11_integration_providers.json"
        )
        if kb_path.exists():
            with open(kb_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        logger.warning("knowledge_base_load_failed", error=str(exc))
    return {}


# Cache the knowledge base at module level (loaded once)
_KB = _load_knowledge_base()


# ── Helper Functions ────────────────────────────────────────────────


def _get_provider_metadata(category: str, provider_type: str) -> Dict[str, Any]:
    """Look up rich metadata from the knowledge base for a provider."""
    categories = _KB.get("categories", {})
    cat_data = categories.get(category, {})
    providers = cat_data.get("providers", {})
    return providers.get(provider_type, {})


def _mask_credentials(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive credential values for safe logging/display."""
    sensitive_keys = {
        "api_key", "api_secret", "secret", "password",
        "auth_token", "access_token", "token", "server_token",
        "client_secret", "secret_access_key",
    }
    masked = {}
    for key, value in credentials.items():
        if any(s in key.lower() for s in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                masked[key] = value[:4] + "****"
            else:
                masked[key] = "****"
        else:
            masked[key] = value
    return masked


def _encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """Encrypt credentials for DB storage.

    Currently stores as JSON (credentials_encrypted column is TEXT).
    Production should use Fernet encryption via shared.utils.token_encryption.
    """
    try:
        from shared.utils.token_encryption import encrypt_token

        return encrypt_token(json.dumps(credentials))
    except (ImportError, Exception):
        # Fallback: base64 encode (not secure, but functional)
        import base64

        return base64.b64encode(json.dumps(credentials).encode()).decode()


def _decrypt_credentials(encrypted: Optional[str]) -> Dict[str, Any]:
    """Decrypt credentials from DB storage."""
    if not encrypted:
        return {}

    try:
        from shared.utils.token_encryption import decrypt_token

        decrypted = decrypt_token(encrypted)
        return json.loads(decrypted)
    except (ImportError, Exception):
        # Fallback: base64 decode
        try:
            import base64

            decoded = base64.b64decode(encrypted.encode()).decode()
            return json.loads(decoded)
        except Exception:
            return {}


def _integration_category(integration_type: str) -> str:
    """Derive the provider category from an integration_type string.

    Maps from the Integration model's integration_type (e.g. 'sendgrid')
    to a provider category (e.g. 'email') using the ProviderRegistry.
    """
    for cat in ProviderRegistry.categories():
        providers = ProviderRegistry.list_by_category(cat)
        if integration_type in providers:
            return cat
    return "custom"


# ── Endpoints ───────────────────────────────────────────────────────


@router.post(
    "/providers/{category}",
    response_model=CategoryProvidersResponse,
    summary="List providers for a category",
)
async def list_providers_by_category(
    category: str,
    user: User = Depends(get_current_user),
):
    """List all available providers for a given category.

    Returns provider info from both the ProviderRegistry (runtime
    adapters) and the knowledge base (rich metadata for Jarvis).

    Args:
        category: Provider category (email, sms, payment, crm,
                  ecommerce, helpdesk, communication).
    """
    category = category.lower().strip()

    # Validate category exists in registry or knowledge base
    registry_providers = ProviderRegistry.list_by_category(category)
    kb_categories = _KB.get("categories", {})
    kb_cat = kb_categories.get(category, {})

    if not registry_providers and not kb_cat:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "CATEGORY_NOT_FOUND",
                "message": f"Category '{category}' not found",
                "available_categories": list(kb_categories.keys())
                or ProviderRegistry.categories(),
            },
        )

    providers_list: List[ProviderInfoResponse] = []

    # Merge registry + knowledge base data
    all_provider_keys = set(list(registry_providers.keys()))
    kb_providers = kb_cat.get("providers", {})
    all_provider_keys.update(kb_providers.keys())

    for ptype in sorted(all_provider_keys):
        kb_meta = kb_providers.get(ptype, {})
        provider_cls = registry_providers.get(ptype)

        # Get required fields from provider class if available
        required_fields: List[Dict[str, Any]] = []
        capabilities: List[str] = []

        if provider_cls:
            try:
                instance = provider_cls()
                required_fields = instance.get_required_fields()
                capabilities = instance.get_capabilities()
            except Exception:
                pass

        # Fallback to KB metadata
        if not required_fields and kb_meta.get("required_fields"):
            required_fields = [
                {"name": f, "type": "password", "label": f.replace("_", " ").title(), "required": True}
                for f in kb_meta["required_fields"]
            ]

        if not capabilities and kb_meta.get("capabilities"):
            capabilities = kb_meta["capabilities"]

        providers_list.append(
            ProviderInfoResponse(
                provider_type=ptype,
                name=kb_meta.get("name", provider_cls.provider_name if provider_cls else ptype),
                description=kb_meta.get("description"),
                setup_difficulty=kb_meta.get("setup_difficulty"),
                setup_time=kb_meta.get("setup_time"),
                required_fields=required_fields,
                capabilities=capabilities,
                credentials_help=kb_meta.get("credentials_help"),
            )
        )

    return CategoryProvidersResponse(
        category=category,
        category_name=kb_cat.get("name", category.title()),
        description=kb_cat.get("description"),
        icon=kb_cat.get("icon"),
        providers=providers_list,
    )


@router.post(
    "/detect-key",
    response_model=DetectKeyResponse,
    summary="Auto-detect provider from API key",
)
async def detect_api_key(
    body: DetectKeyRequest,
    user: User = Depends(get_current_user),
):
    """Auto-detect the provider from an API key string.

    Uses the ApiKeyDetector to match key patterns against known
    provider prefixes, lengths, and regex patterns. Returns the
    best match with a confidence score.

    Example:
        Input:  {"api_key": "SG.xxxxx.yyyyy"}
        Output: {"provider_type": "sendgrid", "category": "email",
                 "confidence": 0.95, "name": "SendGrid"}
    """
    result = ApiKeyDetector.detect(body.api_key)

    # Enrich with provider display name from KB
    provider_type = result["provider_type"]
    category = result.get("category")
    name = None

    if provider_type != "unknown" and category:
        kb_meta = _get_provider_metadata(category, provider_type)
        name = kb_meta.get("name", provider_type)

    return DetectKeyResponse(
        provider_type=provider_type,
        category=category,
        confidence=result["confidence"],
        name=name,
        matches=result.get("matches", []),
    )


@router.post(
    "/test-connection",
    response_model=TestConnectionResponse,
    summary="Test a provider connection",
)
async def test_provider_connection(
    body: TestConnectionRequest,
    user: User = Depends(get_current_user),
):
    """Test connectivity to a provider using supplied credentials.

    Creates a provider instance with the given credentials and
    calls test_connection(). This validates credentials without
    persisting anything to the database.

    Example:
        Input:  {"provider_type": "sendgrid", "category": "email",
                 "credentials": {"api_key": "SG.xxx"}}
        Output: {"success": true, "message": "Connected successfully",
                 "provider_info": {"name": "SendGrid", ...}}
    """
    provider_type = body.provider_type.lower().strip()
    category = body.category.lower().strip()

    # Look up provider class in registry
    try:
        provider_cls = ProviderRegistry.get(category, provider_type)
    except KeyError:
        # Also check knowledge base for providers without runtime adapters
        kb_meta = _get_provider_metadata(category, provider_type)
        if kb_meta:
            return TestConnectionResponse(
                success=False,
                message=(
                    f"Provider '{provider_type}' is known but does not yet "
                    f"have a runtime adapter. Connection testing is not available."
                ),
                provider_info={"name": kb_meta.get("name", provider_type)},
            )
        raise HTTPException(
            status_code=404,
            detail={
                "error": "PROVIDER_NOT_FOUND",
                "message": f"Provider '{provider_type}' not found in category '{category}'",
            },
        )

    try:
        # Create provider instance and test
        provider = await ProviderFactory.create_with_credentials(
            provider_type=provider_type,
            category=category,
            credentials=body.credentials,
        )

        result = await provider.test_connection(body.credentials)

        # Build provider info
        kb_meta = _get_provider_metadata(category, provider_type)
        provider_info = {
            "name": provider.provider_name,
            "type": provider_type,
            "category": category,
            "status": provider.status.value,
            "capabilities": provider.get_capabilities(),
            "setup_difficulty": kb_meta.get("setup_difficulty"),
            "free_tier": kb_meta.get("free_tier"),
        }

        logger.info(
            "provider_connection_tested",
            provider_type=provider_type,
            category=category,
            success=result.success,
            company_id=str(user.company_id),
        )

        return TestConnectionResponse(
            success=result.success,
            message=result.message,
            provider_info=provider_info,
        )

    except Exception as exc:
        logger.error(
            "provider_connection_test_failed",
            provider_type=provider_type,
            category=category,
            error=str(exc),
            company_id=str(user.company_id),
        )
        return TestConnectionResponse(
            success=False,
            message=f"Connection test failed: {str(exc)}",
        )


@router.post(
    "/connect",
    response_model=ConnectProviderResponse,
    status_code=201,
    summary="Connect a provider integration",
)
async def connect_provider(
    body: ConnectProviderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Connect and persist a provider integration.

    Validates the provider exists, tests the connection, and
    saves the (encrypted) credentials to the database. The
    integration is scoped to the user's company_id.

    Steps:
        1. Validate provider_type exists in registry or KB
        2. Test connection with supplied credentials
        3. Encrypt and persist credentials to Integration table
        4. Return connection_id and status

    BC-001: Scoped to user's company_id (not body.company_id).
    """
    provider_type = body.provider_type.lower().strip()
    category = body.category.lower().strip()

    # BC-001: Always use the authenticated user's company_id
    company_id = str(user.company_id)

    # Validate provider exists
    try:
        provider_cls = ProviderRegistry.get(category, provider_type)
    except KeyError:
        kb_meta = _get_provider_metadata(category, provider_type)
        if not kb_meta:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "PROVIDER_NOT_FOUND",
                    "message": f"Provider '{provider_type}' not found in category '{category}'",
                },
            )
        provider_cls = None

    # Test connection first (if we have a runtime adapter)
    connection_ok = False
    test_message = "Provider saved (connection test not available for this provider)"

    if provider_cls:
        try:
            provider = await ProviderFactory.create_with_credentials(
                provider_type=provider_type,
                category=category,
                credentials=body.credentials,
            )
            result = await provider.test_connection(body.credentials)
            connection_ok = result.success
            test_message = result.message

            if not connection_ok:
                logger.warning(
                    "provider_connection_test_failed_on_connect",
                    provider_type=provider_type,
                    category=category,
                    message=test_message,
                    company_id=company_id,
                )
                # Still save, but with 'error' status
        except Exception as exc:
            connection_ok = False
            test_message = f"Connection test error: {str(exc)}"
            logger.warning(
                "provider_connection_test_error_on_connect",
                provider_type=provider_type,
                category=category,
                error=str(exc),
                company_id=company_id,
            )

    # Determine status
    status = "active" if connection_ok else "error"

    # Build integration name
    kb_meta = _get_provider_metadata(category, provider_type)
    display_name = body.name or kb_meta.get("name", provider_type)

    # Check for existing integration of same type for this company
    existing = db.query(Integration).filter(
        Integration.company_id == company_id,
        Integration.integration_type == provider_type,
    ).first()

    if existing:
        # Update existing integration
        existing.credentials_encrypted = _encrypt_credentials(body.credentials)
        existing.status = status
        existing.error_message = None if connection_ok else test_message
        existing.name = display_name
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        connection_id = existing.id
        logger.info(
            "provider_integration_updated",
            connection_id=connection_id,
            provider_type=provider_type,
            category=category,
            company_id=company_id,
            status=status,
        )
    else:
        # Create new integration
        integration = Integration(
            company_id=company_id,
            integration_type=provider_type,
            name=display_name,
            status=status,
            credentials_encrypted=_encrypt_credentials(body.credentials),
            settings=json.dumps({"category": category}),
            error_message=None if connection_ok else test_message,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(integration)
        db.flush()
        connection_id = integration.id
        logger.info(
            "provider_integration_created",
            connection_id=connection_id,
            provider_type=provider_type,
            category=category,
            company_id=company_id,
            status=status,
        )

    return ConnectProviderResponse(
        success=True,
        connection_id=connection_id,
        status=status,
        message=test_message if not connection_ok else "Connected successfully",
    )


@router.get(
    "/status",
    response_model=IntegrationStatusResponse,
    summary="Get all integration statuses for a company",
)
async def get_integration_status(
    company_id: str = Query(..., description="Company ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all integration statuses for a company.

    BC-001: Only returns integrations for the authenticated user's
    company_id (the query param is validated against the user).
    """
    # BC-001: Enforce company scoping
    if str(user.company_id) != company_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FORBIDDEN",
                "message": "You can only view integrations for your own company",
            },
        )

    integrations = (
        db.query(Integration)
        .filter(Integration.company_id == company_id)
        .order_by(Integration.created_at.desc())
        .all()
    )

    items: List[IntegrationStatusItem] = []
    for integ in integrations:
        # Derive category from settings or registry
        settings = {}
        try:
            settings = json.loads(integ.settings) if integ.settings else {}
        except (json.JSONDecodeError, TypeError):
            pass

        category = settings.get("category") or _integration_category(
            integ.integration_type
        )

        items.append(
            IntegrationStatusItem(
                id=integ.id,
                company_id=integ.company_id,
                provider_type=integ.integration_type,
                category=category,
                name=integ.name,
                status=integ.status or "disconnected",
                last_tested_at=(
                    integ.updated_at.isoformat() if integ.updated_at else None
                ),
                error_message=integ.error_message,
                created_at=(
                    integ.created_at.isoformat() if integ.created_at else None
                ),
            )
        )

    return IntegrationStatusResponse(
        company_id=company_id,
        integrations=items,
        total=len(items),
    )


@router.delete(
    "/{connection_id}",
    response_model=DisconnectResponse,
    summary="Disconnect a provider integration",
)
async def disconnect_provider(
    connection_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect and remove a provider integration.

    Deletes the integration record from the database.

    BC-001: Only allows deletion of integrations belonging to
    the authenticated user's company.
    """
    company_id = str(user.company_id)

    integration = db.query(Integration).filter(
        Integration.id == connection_id,
        Integration.company_id == company_id,
    ).first()

    if not integration:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NOT_FOUND",
                "message": f"Integration '{connection_id}' not found for your company",
            },
        )

    provider_type = integration.integration_type
    db.delete(integration)
    db.flush()

    logger.info(
        "provider_integration_disconnected",
        connection_id=connection_id,
        provider_type=provider_type,
        company_id=company_id,
    )

    return DisconnectResponse(
        success=True,
        message=f"Integration '{provider_type}' disconnected successfully",
    )
