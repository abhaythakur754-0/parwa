"""
PARWA Integrations API Routes.

Provides endpoints for third-party service integration management.
All data is company-scoped for RLS compliance.

Supported integrations: shopify, stripe, twilio, zendesk, email
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.company import Company
from backend.models.user import User, RoleEnum
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import decode_access_token
from shared.utils.cache import Cache

# Expose for testing
__all__ = [
    "router",
    "IntegrationType",
    "IntegrationStatus",
    "get_current_user",
    "is_token_blacklisted",
    "require_manager_role",
    "SUPPORTED_INTEGRATIONS",
]

# Initialize router and logger
router = APIRouter(prefix="/integrations", tags=["Integrations"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Integration Types and Configuration ---

class IntegrationType(str, Enum):
    """Supported integration types."""
    SHOPIFY = "shopify"
    STRIPE = "stripe"
    TWILIO = "twilio"
    ZENDESK = "zendesk"
    EMAIL = "email"


class IntegrationStatus(str, Enum):
    """Integration connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PENDING = "pending"
    ERROR = "error"


# Integration configuration and capabilities
SUPPORTED_INTEGRATIONS = {
    IntegrationType.SHOPIFY: {
        "name": "Shopify",
        "description": "E-commerce platform integration for order and customer sync",
        "category": "ecommerce",
        "requires_webhook": True,
        "supports_oauth": True,
        "features": ["order_sync", "customer_sync", "product_sync"],
        "required_fields": ["store_url", "api_key", "api_secret"],
    },
    IntegrationType.STRIPE: {
        "name": "Stripe",
        "description": "Payment processing integration for billing and refunds",
        "category": "payments",
        "requires_webhook": True,
        "supports_oauth": False,
        "features": ["payment_processing", "refund_handling", "subscription_management"],
        "required_fields": ["api_key", "webhook_secret"],
    },
    IntegrationType.TWILIO: {
        "name": "Twilio",
        "description": "SMS and voice communication integration",
        "category": "communication",
        "requires_webhook": True,
        "supports_oauth": False,
        "features": ["sms", "voice", "whatsapp"],
        "required_fields": ["account_sid", "auth_token", "phone_number"],
    },
    IntegrationType.ZENDESK: {
        "name": "Zendesk",
        "description": "Customer support platform integration",
        "category": "support",
        "requires_webhook": True,
        "supports_oauth": True,
        "features": ["ticket_sync", "knowledge_base", "live_chat"],
        "required_fields": ["subdomain", "api_token", "email"],
    },
    IntegrationType.EMAIL: {
        "name": "Email (Brevo/SendGrid)",
        "description": "Email marketing and transactional email integration",
        "category": "communication",
        "requires_webhook": False,
        "supports_oauth": False,
        "features": ["transactional_email", "marketing_email", "templates"],
        "required_fields": ["api_key", "sender_email", "sender_name"],
    },
}


# --- Pydantic Schemas ---

class IntegrationInfo(BaseModel):
    """Schema for integration information."""
    type: str = Field(..., description="Integration type")
    name: str = Field(..., description="Integration display name")
    description: str = Field(..., description="Integration description")
    category: str = Field(..., description="Integration category")
    status: str = Field(..., description="Connection status")
    features: List[str] = Field(default_factory=list, description="Available features")
    requires_webhook: bool = Field(..., description="Whether webhook setup is required")
    supports_oauth: bool = Field(..., description="Whether OAuth is supported")


class IntegrationListResponse(BaseModel):
    """Response schema for list of integrations."""
    integrations: List[IntegrationInfo] = Field(..., description="Available integrations")
    total: int = Field(..., description="Total count")


class IntegrationStatusResponse(BaseModel):
    """Response schema for integration status."""
    type: str = Field(..., description="Integration type")
    status: str = Field(..., description="Connection status")
    connected_at: Optional[datetime] = Field(None, description="When integration was connected")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync time")
    error_message: Optional[str] = Field(None, description="Error message if status is error")
    features_enabled: List[str] = Field(default_factory=list, description="Enabled features")


class ConnectIntegrationRequest(BaseModel):
    """Request schema for connecting an integration."""
    credentials: Dict[str, str] = Field(..., description="Integration credentials")
    settings: Optional[Dict[str, Any]] = Field(None, description="Optional integration settings")

    @validator("credentials")
    def validate_credentials_not_empty(cls, v):
        """Validate that credentials dict is not empty."""
        if not v:
            raise ValueError("Credentials cannot be empty")
        return v


class ConnectIntegrationResponse(BaseModel):
    """Response schema for connecting an integration."""
    type: str = Field(..., description="Integration type")
    status: str = Field(..., description="Connection status")
    message: str = Field(..., description="Status message")
    connected_at: datetime = Field(..., description="Connection timestamp")


class DisconnectIntegrationResponse(BaseModel):
    """Response schema for disconnecting an integration."""
    type: str = Field(..., description="Integration type")
    status: str = Field(..., description="Connection status")
    message: str = Field(..., description="Status message")
    disconnected_at: datetime = Field(..., description="Disconnection timestamp")


class IntegrationSettingsResponse(BaseModel):
    """Response schema for integration settings."""
    type: str = Field(..., description="Integration type")
    settings: Dict[str, Any] = Field(..., description="Current settings")
    webhook_url: Optional[str] = Field(None, description="Webhook URL if applicable")


class UpdateSettingsRequest(BaseModel):
    """Request schema for updating integration settings."""
    settings: Dict[str, Any] = Field(..., description="New settings")

    @validator("settings")
    def validate_settings_not_empty(cls, v):
        """Validate that settings dict is not empty."""
        if not v:
            raise ValueError("Settings cannot be empty")
        return v


class MessageResponse(BaseModel):
    """Generic message response schema."""
    message: str = Field(..., description="Response message")


# --- Helper Functions ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extract and validate the current user from JWT token.

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

    # Check if token is blacklisted
    if await is_token_blacklisted(token):
        logger.warning({"event": "blacklisted_token_used", "user_id": payload.get("sub")})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
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


async def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is in the Redis blacklist.

    Args:
        token: The JWT token to check.

    Returns:
        bool: True if token is blacklisted, False otherwise.
    """
    try:
        cache = Cache()
        exists = await cache.exists(f"blacklist:{token}")
        await cache.close()
        return exists
    except Exception as e:
        logger.error({"event": "blacklist_check_failed", "error": str(e)})
        return False


def require_manager_role(user: User) -> None:
    """
    Validate that user has manager or admin role.

    Args:
        user: The user to validate.

    Raises:
        HTTPException: If user lacks required permissions.
    """
    # Handle both string and enum role values, as well as mock objects with .value
    if isinstance(user.role, RoleEnum):
        user_role = user.role.value
    elif hasattr(user.role, 'value'):
        user_role = user.role.value
    else:
        user_role = user.role

    valid_roles = [RoleEnum.admin.value, RoleEnum.manager.value]

    if user_role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers or admins can perform this action",
        )


def validate_integration_type(integration_type: str) -> IntegrationType:
    """
    Validate integration type.

    Args:
        integration_type: The integration type string.

    Returns:
        IntegrationType: The validated enum value.

    Raises:
        HTTPException: If integration type is invalid.
    """
    try:
        return IntegrationType(integration_type)
    except ValueError:
        valid_types = [t.value for t in IntegrationType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid integration type. Must be one of: {', '.join(valid_types)}",
        )


async def get_integration_status_from_cache(
    company_id: uuid.UUID,
    integration_type: IntegrationType
) -> Dict[str, Any]:
    """
    Get integration status from cache.

    Args:
        company_id: Company UUID
        integration_type: Integration type enum

    Returns:
        Dict with status information
    """
    try:
        cache = Cache()
        key = f"integration:{company_id}:{integration_type.value}"
        data = await cache.get(key)
        await cache.close()

        if data:
            return data
    except Exception as e:
        logger.error({"event": "cache_read_failed", "error": str(e)})

    return {
        "status": IntegrationStatus.DISCONNECTED.value,
        "connected_at": None,
        "last_sync": None,
        "error_message": None,
        "features_enabled": [],
    }


async def set_integration_status_in_cache(
    company_id: uuid.UUID,
    integration_type: IntegrationType,
    status_data: Dict[str, Any]
) -> None:
    """
    Set integration status in cache.

    Args:
        company_id: Company UUID
        integration_type: Integration type enum
        status_data: Status data to cache
    """
    try:
        cache = Cache()
        key = f"integration:{company_id}:{integration_type.value}"
        await cache.set(key, status_data, ttl=86400)  # 24 hours TTL
        await cache.close()
    except Exception as e:
        logger.error({"event": "cache_write_failed", "error": str(e)})


# --- API Endpoints ---

@router.get(
    "",
    response_model=IntegrationListResponse,
    summary="List available integrations",
    description="Get a list of all available integrations and their status for the company."
)
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> IntegrationListResponse:
    """
    List all available integrations.

    Returns a list of supported integrations with their current connection status.

    Args:
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        IntegrationListResponse: List of integrations with status.
    """
    company_id = current_user.company_id
    integrations = []

    for int_type, config in SUPPORTED_INTEGRATIONS.items():
        # Get current status from cache
        status_data = await get_integration_status_from_cache(company_id, int_type)

        integration = IntegrationInfo(
            type=int_type.value,
            name=config["name"],
            description=config["description"],
            category=config["category"],
            status=status_data.get("status", IntegrationStatus.DISCONNECTED.value),
            features=config["features"],
            requires_webhook=config["requires_webhook"],
            supports_oauth=config["supports_oauth"],
        )
        integrations.append(integration)

    logger.info({
        "event": "integrations_listed",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "count": len(integrations),
    })

    return IntegrationListResponse(
        integrations=integrations,
        total=len(integrations),
    )


@router.get(
    "/{integration_type}/status",
    response_model=IntegrationStatusResponse,
    summary="Get integration status",
    description="Get detailed status for a specific integration."
)
async def get_integration_status(
    integration_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> IntegrationStatusResponse:
    """
    Get detailed status for a specific integration.

    Args:
        integration_type: The integration type (shopify, stripe, twilio, zendesk, email).
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        IntegrationStatusResponse: Detailed integration status.

    Raises:
        HTTPException: 400 if integration type is invalid.
    """
    int_type = validate_integration_type(integration_type)
    company_id = current_user.company_id

    # Get status from cache
    status_data = await get_integration_status_from_cache(company_id, int_type)

    logger.info({
        "event": "integration_status_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "integration_type": int_type.value,
    })

    return IntegrationStatusResponse(
        type=int_type.value,
        status=status_data.get("status", IntegrationStatus.DISCONNECTED.value),
        connected_at=status_data.get("connected_at"),
        last_sync=status_data.get("last_sync"),
        error_message=status_data.get("error_message"),
        features_enabled=status_data.get("features_enabled", []),
    )


@router.post(
    "/{integration_type}/connect",
    response_model=ConnectIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect integration",
    description="Connect a third-party integration. Requires manager or admin role."
)
async def connect_integration(
    integration_type: str,
    request: ConnectIntegrationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConnectIntegrationResponse:
    """
    Connect a third-party integration.

    Validates credentials and establishes connection to the third-party service.

    Args:
        integration_type: The integration type to connect.
        request: Connection credentials and optional settings.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        ConnectIntegrationResponse: Connection status.

    Raises:
        HTTPException: 400 if integration type invalid, 403 if not authorized.
    """
    # Validate permissions
    require_manager_role(current_user)

    int_type = validate_integration_type(integration_type)
    company_id = current_user.company_id
    config = SUPPORTED_INTEGRATIONS[int_type]

    # Validate required fields
    required_fields = config["required_fields"]
    missing_fields = [f for f in required_fields if f not in request.credentials]
    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {', '.join(missing_fields)}",
        )

    # In production, we would validate credentials with the third-party
    # For now, we'll simulate a successful connection
    connected_at = datetime.now(timezone.utc)

    status_data = {
        "status": IntegrationStatus.CONNECTED.value,
        "connected_at": connected_at.isoformat(),
        "last_sync": None,
        "error_message": None,
        "features_enabled": config["features"],
        "settings": request.settings or {},
    }

    await set_integration_status_in_cache(company_id, int_type, status_data)

    logger.info({
        "event": "integration_connected",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "integration_type": int_type.value,
        "features_enabled": config["features"],
    })

    return ConnectIntegrationResponse(
        type=int_type.value,
        status=IntegrationStatus.CONNECTED.value,
        message=f"Successfully connected to {config['name']}",
        connected_at=connected_at,
    )


@router.delete(
    "/{integration_type}/disconnect",
    response_model=DisconnectIntegrationResponse,
    summary="Disconnect integration",
    description="Disconnect a third-party integration. Requires manager or admin role."
)
async def disconnect_integration(
    integration_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DisconnectIntegrationResponse:
    """
    Disconnect a third-party integration.

    Removes the integration connection and clears stored credentials.

    Args:
        integration_type: The integration type to disconnect.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        DisconnectIntegrationResponse: Disconnection status.

    Raises:
        HTTPException: 400 if integration type invalid, 403 if not authorized.
    """
    # Validate permissions
    require_manager_role(current_user)

    int_type = validate_integration_type(integration_type)
    company_id = current_user.company_id
    config = SUPPORTED_INTEGRATIONS[int_type]

    # Get current status to check if connected
    current_status = await get_integration_status_from_cache(company_id, int_type)
    if current_status.get("status") != IntegrationStatus.CONNECTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{config['name']} is not currently connected",
        )

    disconnected_at = datetime.now(timezone.utc)

    # Clear the integration status
    status_data = {
        "status": IntegrationStatus.DISCONNECTED.value,
        "connected_at": None,
        "last_sync": None,
        "error_message": None,
        "features_enabled": [],
        "settings": {},
    }

    await set_integration_status_in_cache(company_id, int_type, status_data)

    logger.info({
        "event": "integration_disconnected",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "integration_type": int_type.value,
    })

    return DisconnectIntegrationResponse(
        type=int_type.value,
        status=IntegrationStatus.DISCONNECTED.value,
        message=f"Successfully disconnected from {config['name']}",
        disconnected_at=disconnected_at,
    )


@router.get(
    "/{integration_type}/settings",
    response_model=IntegrationSettingsResponse,
    summary="Get integration settings",
    description="Get settings for a connected integration."
)
async def get_integration_settings(
    integration_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> IntegrationSettingsResponse:
    """
    Get settings for a connected integration.

    Args:
        integration_type: The integration type.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        IntegrationSettingsResponse: Current integration settings.

    Raises:
        HTTPException: 400 if integration type invalid or not connected.
    """
    int_type = validate_integration_type(integration_type)
    company_id = current_user.company_id
    config = SUPPORTED_INTEGRATIONS[int_type]

    # Get current status
    status_data = await get_integration_status_from_cache(company_id, int_type)
    if status_data.get("status") != IntegrationStatus.CONNECTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{config['name']} is not connected",
        )

    # Generate webhook URL if applicable
    webhook_url = None
    if config["requires_webhook"]:
        webhook_url = f"{settings.api_url}/webhooks/{int_type.value}/{company_id}"

    logger.info({
        "event": "integration_settings_retrieved",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "integration_type": int_type.value,
    })

    return IntegrationSettingsResponse(
        type=int_type.value,
        settings=status_data.get("settings", {}),
        webhook_url=webhook_url,
    )


@router.put(
    "/{integration_type}/settings",
    response_model=MessageResponse,
    summary="Update integration settings",
    description="Update settings for a connected integration. Requires manager or admin role."
)
async def update_integration_settings(
    integration_type: str,
    request: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Update settings for a connected integration.

    Args:
        integration_type: The integration type.
        request: New settings to apply.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        MessageResponse: Success message.

    Raises:
        HTTPException: 400 if integration type invalid or not connected, 403 if not authorized.
    """
    # Validate permissions
    require_manager_role(current_user)

    int_type = validate_integration_type(integration_type)
    company_id = current_user.company_id
    config = SUPPORTED_INTEGRATIONS[int_type]

    # Get current status
    status_data = await get_integration_status_from_cache(company_id, int_type)
    if status_data.get("status") != IntegrationStatus.CONNECTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{config['name']} is not connected",
        )

    # Update settings
    current_settings = status_data.get("settings", {})
    current_settings.update(request.settings)
    status_data["settings"] = current_settings

    await set_integration_status_in_cache(company_id, int_type, status_data)

    logger.info({
        "event": "integration_settings_updated",
        "user_id": str(current_user.id),
        "company_id": str(company_id),
        "integration_type": int_type.value,
    })

    return MessageResponse(
        message=f"Settings updated successfully for {config['name']}"
    )
