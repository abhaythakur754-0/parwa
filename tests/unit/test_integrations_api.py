"""
Unit tests for Integrations API.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set environment variables before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.company_id = uuid.uuid4()
    user.role = MagicMock()
    user.role.value = "admin"
    user.is_active = True
    return user


@pytest.fixture
def mock_manager_user():
    """Create a mock manager user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "manager@example.com"
    user.company_id = uuid.uuid4()
    user.role = MagicMock()
    user.role.value = "manager"
    user.is_active = True
    return user


@pytest.fixture
def mock_viewer_user():
    """Create a mock viewer user (no manager/admin permissions)."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "viewer@example.com"
    user.company_id = uuid.uuid4()
    user.role = MagicMock()
    user.role.value = "viewer"
    user.is_active = True
    return user


def create_test_app():
    """Create a FastAPI test app with integrations router."""
    app = FastAPI()

    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    from backend.api.integrations import router
    app.include_router(router)

    return app


class TestIntegrationsRouter:
    """Tests for integrations router configuration."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.integrations import router
        assert router.prefix == "/integrations"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.integrations import router
        assert "Integrations" in router.tags


class TestIntegrationTypeEnum:
    """Tests for IntegrationType enum."""

    def test_integration_type_values(self):
        """Test IntegrationType enum values."""
        from backend.api.integrations import IntegrationType
        assert IntegrationType.SHOPIFY.value == "shopify"
        assert IntegrationType.STRIPE.value == "stripe"
        assert IntegrationType.TWILIO.value == "twilio"
        assert IntegrationType.ZENDESK.value == "zendesk"
        assert IntegrationType.EMAIL.value == "email"

    def test_integration_type_from_string(self):
        """Test creating IntegrationType from string."""
        from backend.api.integrations import IntegrationType
        assert IntegrationType("stripe") == IntegrationType.STRIPE


class TestIntegrationStatusEnum:
    """Tests for IntegrationStatus enum."""

    def test_status_values(self):
        """Test IntegrationStatus enum values."""
        from backend.api.integrations import IntegrationStatus
        assert IntegrationStatus.CONNECTED.value == "connected"
        assert IntegrationStatus.DISCONNECTED.value == "disconnected"
        assert IntegrationStatus.PENDING.value == "pending"
        assert IntegrationStatus.ERROR.value == "error"


class TestSupportedIntegrations:
    """Tests for SUPPORTED_INTEGRATIONS configuration."""

    def test_all_integrations_have_config(self):
        """Test that all integration types have configuration."""
        from backend.api.integrations import SUPPORTED_INTEGRATIONS, IntegrationType

        for int_type in IntegrationType:
            assert int_type in SUPPORTED_INTEGRATIONS
            config = SUPPORTED_INTEGRATIONS[int_type]
            assert "name" in config
            assert "description" in config
            assert "category" in config
            assert "features" in config
            assert "required_fields" in config

    def test_shopify_config(self):
        """Test Shopify integration configuration."""
        from backend.api.integrations import SUPPORTED_INTEGRATIONS, IntegrationType

        config = SUPPORTED_INTEGRATIONS[IntegrationType.SHOPIFY]
        assert config["name"] == "Shopify"
        assert config["category"] == "ecommerce"
        assert "order_sync" in config["features"]
        assert "store_url" in config["required_fields"]

    def test_stripe_config(self):
        """Test Stripe integration configuration."""
        from backend.api.integrations import SUPPORTED_INTEGRATIONS, IntegrationType

        config = SUPPORTED_INTEGRATIONS[IntegrationType.STRIPE]
        assert config["name"] == "Stripe"
        assert config["category"] == "payments"
        assert "api_key" in config["required_fields"]

    def test_twilio_config(self):
        """Test Twilio integration configuration."""
        from backend.api.integrations import SUPPORTED_INTEGRATIONS, IntegrationType

        config = SUPPORTED_INTEGRATIONS[IntegrationType.TWILIO]
        assert config["name"] == "Twilio"
        assert config["category"] == "communication"
        assert "sms" in config["features"]


class TestConnectIntegrationRequest:
    """Tests for ConnectIntegrationRequest schema."""

    def test_valid_request(self):
        """Test valid connect request."""
        from backend.api.integrations import ConnectIntegrationRequest

        request = ConnectIntegrationRequest(
            credentials={"api_key": "test_key", "api_secret": "test_secret"}
        )
        assert request.credentials["api_key"] == "test_key"

    def test_request_with_settings(self):
        """Test connect request with settings."""
        from backend.api.integrations import ConnectIntegrationRequest

        request = ConnectIntegrationRequest(
            credentials={"api_key": "test_key"},
            settings={"sync_interval": 60, "enabled": True}
        )
        assert request.settings["sync_interval"] == 60

    def test_empty_credentials_raises_error(self):
        """Test that empty credentials raises validation error."""
        from backend.api.integrations import ConnectIntegrationRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ConnectIntegrationRequest(credentials={})


class TestUpdateSettingsRequest:
    """Tests for UpdateSettingsRequest schema."""

    def test_valid_request(self):
        """Test valid update settings request."""
        from backend.api.integrations import UpdateSettingsRequest

        request = UpdateSettingsRequest(settings={"enabled": True, "frequency": "daily"})
        assert request.settings["enabled"] is True

    def test_empty_settings_raises_error(self):
        """Test that empty settings raises validation error."""
        from backend.api.integrations import UpdateSettingsRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UpdateSettingsRequest(settings={})


class TestIntegrationListResponse:
    """Tests for IntegrationListResponse schema."""

    def test_valid_response(self):
        """Test valid list response."""
        from backend.api.integrations import IntegrationListResponse, IntegrationInfo

        integrations = [
            IntegrationInfo(
                type="shopify",
                name="Shopify",
                description="E-commerce",
                category="ecommerce",
                status="connected",
                features=["order_sync"],
                requires_webhook=True,
                supports_oauth=True,
            )
        ]

        response = IntegrationListResponse(integrations=integrations, total=1)
        assert response.total == 1
        assert len(response.integrations) == 1


class TestIntegrationStatusResponse:
    """Tests for IntegrationStatusResponse schema."""

    def test_valid_response(self):
        """Test valid status response."""
        from backend.api.integrations import IntegrationStatusResponse

        response = IntegrationStatusResponse(
            type="stripe",
            status="connected",
            connected_at=datetime.now(timezone.utc),
            features_enabled=["payment_processing"]
        )
        assert response.status == "connected"

    def test_error_response(self):
        """Test status response with error."""
        from backend.api.integrations import IntegrationStatusResponse

        response = IntegrationStatusResponse(
            type="stripe",
            status="error",
            error_message="API key invalid"
        )
        assert response.error_message == "API key invalid"


class TestEndpointsWithoutAuth:
    """Tests for endpoints without authentication."""

    def test_list_integrations_requires_auth(self):
        """Test that list integrations requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/integrations")

        assert response.status_code in [401, 403]

    def test_get_status_requires_auth(self):
        """Test that get status requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/integrations/shopify/status")

        assert response.status_code in [401, 403]

    def test_connect_requires_auth(self):
        """Test that connect requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/integrations/shopify/connect",
                json={"credentials": {"api_key": "test"}}
            )

        assert response.status_code in [401, 403]

    def test_disconnect_requires_auth(self):
        """Test that disconnect requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.delete("/integrations/shopify/disconnect")

        assert response.status_code in [401, 403]

    def test_get_settings_requires_auth(self):
        """Test that get settings requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/integrations/shopify/settings")

        assert response.status_code in [401, 403]

    def test_update_settings_requires_auth(self):
        """Test that update settings requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.put(
                "/integrations/shopify/settings",
                json={"settings": {"enabled": True}}
            )

        assert response.status_code in [401, 403]


class TestInvalidIntegrationType:
    """Tests for invalid integration type handling."""

    def test_status_invalid_type(self):
        """Test get status with invalid integration type."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/integrations/invalid_type/status")

        assert response.status_code in [401, 403, 400, 422]

    def test_connect_invalid_type(self):
        """Test connect with invalid integration type."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/integrations/invalid_type/connect",
                json={"credentials": {"api_key": "test"}}
            )

        assert response.status_code in [401, 403, 400, 422]


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_validate_integration_type_valid(self):
        """Test validate_integration_type with valid type."""
        from backend.api.integrations import validate_integration_type, IntegrationType

        result = validate_integration_type("stripe")
        assert result == IntegrationType.STRIPE

    def test_validate_integration_type_invalid(self):
        """Test validate_integration_type with invalid type."""
        from backend.api.integrations import validate_integration_type
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_integration_type("invalid")

        assert exc_info.value.status_code == 400

    def test_require_manager_role_admin(self, mock_user):
        """Test require_manager_role with admin user."""
        from backend.api.integrations import require_manager_role

        # Set up the mock to return a string for role.value
        class MockRole:
            value = "admin"

        mock_user.role = MockRole()

        # Should not raise
        require_manager_role(mock_user)

    def test_require_manager_role_manager(self, mock_manager_user):
        """Test require_manager_role with manager user."""
        from backend.api.integrations import require_manager_role

        # Set up the mock to return a string for role.value
        class MockRole:
            value = "manager"

        mock_manager_user.role = MockRole()

        # Should not raise
        require_manager_role(mock_manager_user)

    def test_require_manager_role_viewer_denied(self, mock_viewer_user):
        """Test require_manager_role with viewer user."""
        from backend.api.integrations import require_manager_role
        from fastapi import HTTPException

        # Set up the mock to return a string for role.value
        class MockRole:
            value = "viewer"

        mock_viewer_user.role = MockRole()

        with pytest.raises(HTTPException) as exc_info:
            require_manager_role(mock_viewer_user)

        assert exc_info.value.status_code == 403


class TestCacheIntegrationStatus:
    """Tests for cache integration status functions."""

    @pytest.mark.asyncio
    async def test_get_integration_status_from_cache_empty(self):
        """Test getting status when not in cache."""
        from backend.api.integrations import (
            get_integration_status_from_cache,
            IntegrationType
        )
        from unittest.mock import AsyncMock, patch

        company_id = uuid.uuid4()

        with patch("backend.api.integrations.Cache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None
            mock_cache.close = AsyncMock()
            mock_cache_class.return_value = mock_cache

            result = await get_integration_status_from_cache(company_id, IntegrationType.STRIPE)

            assert result["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_set_integration_status_in_cache(self):
        """Test setting status in cache."""
        from backend.api.integrations import (
            set_integration_status_in_cache,
            IntegrationType
        )
        from unittest.mock import AsyncMock, patch

        company_id = uuid.uuid4()
        status_data = {"status": "connected", "features_enabled": ["sms"]}

        with patch("backend.api.integrations.Cache") as mock_cache_class:
            mock_cache = AsyncMock()
            mock_cache.set = AsyncMock()
            mock_cache.close = AsyncMock()
            mock_cache_class.return_value = mock_cache

            await set_integration_status_in_cache(company_id, IntegrationType.TWILIO, status_data)

            mock_cache.set.assert_called_once()


class TestConnectIntegrationResponse:
    """Tests for ConnectIntegrationResponse schema."""

    def test_valid_response(self):
        """Test valid connect response."""
        from backend.api.integrations import ConnectIntegrationResponse

        response = ConnectIntegrationResponse(
            type="shopify",
            status="connected",
            message="Successfully connected",
            connected_at=datetime.now(timezone.utc)
        )
        assert response.status == "connected"
        assert response.message == "Successfully connected"


class TestDisconnectIntegrationResponse:
    """Tests for DisconnectIntegrationResponse schema."""

    def test_valid_response(self):
        """Test valid disconnect response."""
        from backend.api.integrations import DisconnectIntegrationResponse

        response = DisconnectIntegrationResponse(
            type="shopify",
            status="disconnected",
            message="Successfully disconnected",
            disconnected_at=datetime.now(timezone.utc)
        )
        assert response.status == "disconnected"


class TestIntegrationSettingsResponse:
    """Tests for IntegrationSettingsResponse schema."""

    def test_valid_response(self):
        """Test valid settings response."""
        from backend.api.integrations import IntegrationSettingsResponse

        response = IntegrationSettingsResponse(
            type="stripe",
            settings={"webhook_enabled": True, "sync_frequency": 60},
            webhook_url="https://api.example.com/webhooks/stripe/123"
        )
        assert response.settings["webhook_enabled"] is True
        assert response.webhook_url is not None

    def test_response_without_webhook(self):
        """Test settings response without webhook URL."""
        from backend.api.integrations import IntegrationSettingsResponse

        response = IntegrationSettingsResponse(
            type="email",
            settings={"sender_email": "noreply@example.com"}
        )
        assert response.webhook_url is None
