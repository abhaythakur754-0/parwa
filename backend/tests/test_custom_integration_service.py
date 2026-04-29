"""
PARWA Tests — F-031: Custom Integration Builder

Tests the CustomIntegrationService covering:
- CRUD operations (create, get, list, update, delete, activate)
- Config validation per integration type
- Credential masking (BC-011)
- Plan limit enforcement
- Test connectivity for each type
- Error tracking and auto-disable at 3 consecutive errors
- Record success/failure methods
- Webhook ID lookup for incoming webhooks

Building Codes: BC-001, BC-003, BC-004, BC-011, BC-012
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.exceptions import ValidationError
from app.services.custom_integration_service import (
    CustomIntegrationService,
    VALID_INTEGRATION_TYPES,
    VALID_AUTH_TYPES,
    VALID_HTTP_METHODS,
    PLAN_LIMITS,
    MAX_CONSECUTIVE_ERRORS,
    REST_TIMEOUT_SECONDS,
    DB_TIMEOUT_SECONDS,
    REQUIRED_CONFIG_FIELDS,
    _encrypt_config,
    _decrypt_config,
    _mask_config,
    _parse_json,
)


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def company_id():
    return "comp-abc-123"


@pytest.fixture
def service(mock_db):
    return CustomIntegrationService(mock_db)


def _make_mock_integration(
    integration_id="int-123",
    company_id="comp-abc-123",
    name="Test Integration",
    integration_type="rest",
    status="draft",
    config_encrypted=None,
    webhook_id=None,
    webhook_secret=None,
    consecutive_error_count=0,
    last_error_message=None,
    last_tested_at=None,
    last_test_result=None,
):
    """Create a mock CustomIntegration ORM object."""
    integration = MagicMock()
    integration.id = integration_id
    integration.company_id = company_id
    integration.name = name
    integration.integration_type = integration_type
    integration.status = status
    integration.config_encrypted = config_encrypted or _encrypt_config({
        "url": "https://api.example.com",
        "method": "GET",
        "auth_type": "bearer",
        "token": "secret-token-12345",
    })
    integration.settings = "{}"
    integration.webhook_id = webhook_id
    integration.webhook_secret = webhook_secret
    integration.consecutive_error_count = consecutive_error_count
    integration.last_error_message = last_error_message
    integration.last_tested_at = last_tested_at
    integration.last_test_result = last_test_result
    integration.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    integration.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
    return integration


# ══════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ══════════════════════════════════════════════════════════════════

class TestConstants:
    """Verify that service constants match the spec."""

    def test_valid_integration_types(self):
        expected = {"rest", "graphql", "webhook_in", "webhook_out", "database"}
        assert VALID_INTEGRATION_TYPES == expected

    def test_valid_auth_types(self):
        expected = {"bearer", "basic", "api_key", "oauth2", "none"}
        assert VALID_AUTH_TYPES == expected

    def test_valid_http_methods(self):
        assert "GET" in VALID_HTTP_METHODS
        assert "POST" in VALID_HTTP_METHODS
        assert "PUT" in VALID_HTTP_METHODS
        assert "DELETE" in VALID_HTTP_METHODS

    def test_plan_limits_exist(self):
        assert "free" in PLAN_LIMITS
        assert "mini_parwa" in PLAN_LIMITS
        assert "parwa" in PLAN_LIMITS
        assert "pro" in PLAN_LIMITS
        assert "enterprise" in PLAN_LIMITS

    def test_plan_limits_growth(self):
        assert PLAN_LIMITS["parwa"] == 5

    def test_max_consecutive_errors(self):
        assert MAX_CONSECUTIVE_ERRORS == 3

    def test_rest_timeout(self):
        assert REST_TIMEOUT_SECONDS == 10

    def test_db_timeout(self):
        assert DB_TIMEOUT_SECONDS == 5

    def test_required_config_fields_rest(self):
        assert REQUIRED_CONFIG_FIELDS["rest"] == ["url", "method"]

    def test_required_config_fields_graphql(self):
        assert REQUIRED_CONFIG_FIELDS["graphql"] == ["url"]

    def test_required_config_fields_webhook_out(self):
        assert "url" in REQUIRED_CONFIG_FIELDS["webhook_out"]
        assert "method" in REQUIRED_CONFIG_FIELDS["webhook_out"]
        assert "trigger_events" in REQUIRED_CONFIG_FIELDS["webhook_out"]

    def test_required_config_fields_database(self):
        assert REQUIRED_CONFIG_FIELDS["database"] == [
            "connection_string", "db_type"]


# ══════════════════════════════════════════════════════════════════
# CREDENTIAL HELPERS TESTS
# ══════════════════════════════════════════════════════════════════

class TestCredentialHelpers:
    """Test encryption, decryption, and masking."""

    def test_encrypt_decrypt_roundtrip(self):
        config = {"api_key": "sk-12345", "url": "https://api.example.com"}
        encrypted = _encrypt_config(config)
        decrypted = _decrypt_config(encrypted)
        assert decrypted["api_key"] == "sk-12345"
        assert decrypted["url"] == "https://api.example.com"

    def test_encrypt_decrypt_empty_config(self):
        encrypted = _encrypt_config({})
        decrypted = _decrypt_config(encrypted)
        assert decrypted == {}

    def test_decrypt_empty_string(self):
        assert _decrypt_config("") == {}

    def test_decrypt_none(self):
        assert _decrypt_config(None) == {}

    def test_mask_config_api_key(self):
        config = {
            "api_key": "sk-1234567890abcdef",
            "url": "https://api.example.com"}
        masked = _mask_config(config)
        assert masked["api_key"] == "sk-1****"
        assert masked["url"] == "https://api.example.com"

    def test_mask_config_access_token(self):
        config = {"access_token": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
        masked = _mask_config(config)
        assert masked["access_token"] == "ghp_****"

    def test_mask_config_short_secret(self):
        config = {"secret": "ab"}
        masked = _mask_config(config)
        assert masked["secret"] == "****"

    def test_mask_config_connection_string(self):
        config = {
            "connection_string": "postgresql://user:password123@host:5432/db"}
        masked = _mask_config(config)
        assert "password" not in masked["connection_string"]
        assert "****" in masked["connection_string"]

    def test_mask_config_non_sensitive(self):
        config = {"url": "https://api.example.com", "method": "GET"}
        masked = _mask_config(config)
        assert masked == config

    def test_mask_config_nested_dict(self):
        config = {"auth": {"client_secret": "super-secret-value-12345"}}
        masked = _mask_config(config)
        # Fixed: _mask_config now recurses into nested dicts, masking sensitive
        # inner keys
        assert masked["auth"]["client_secret"] == "supe****"

    def test_parse_json_valid(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_parse_json_invalid(self):
        assert _parse_json("not json") is None

    def test_parse_json_none(self):
        assert _parse_json(None) is None

    def test_parse_json_empty(self):
        assert _parse_json("") is None


# ══════════════════════════════════════════════════════════════════
# CREATE TESTS
# ══════════════════════════════════════════════════════════════════

class TestCreate:
    """Test custom integration creation."""

    def test_create_rest_integration(self, service, mock_db, company_id):
        config = {
            "url": "https://api.example.com/v1",
            "method": "POST",
            "auth_type": "bearer",
            "token": "sk-test-token",
        }
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.create(
            company_id=company_id,
            integration_type="rest",
            name="My REST API",
            config=config,
        )

        assert result["type"] == "rest"
        assert result["name"] == "My REST API"
        assert result["status"] == "draft"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_create_graphql_integration(self, service, mock_db, company_id):
        config = {
            "url": "https://api.example.com/graphql",
            "auth_type": "bearer",
            "token": "ghp_123"}
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.create(
            company_id=company_id,
            integration_type="graphql",
            name="My GraphQL API",
            config=config,
        )

        assert result["type"] == "graphql"
        assert result["status"] == "draft"

    def test_create_webhook_in_generates_ids(
            self, service, mock_db, company_id):
        config = {"expected_payload_schema": {"type": "object"}}
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.create(
            company_id=company_id,
            integration_type="webhook_in",
            name="Incoming Webhook",
            config=config,
        )

        assert result["type"] == "webhook_in"
        assert result["webhook_id"] is not None
        assert len(result["webhook_id"]) > 16
        # Secret should be masked in response
        assert result["config"].get("secret") is not None

    def test_create_webhook_out(self, service, mock_db, company_id):
        config = {
            "url": "https://hooks.example.com/parwa",
            "method": "POST",
            "trigger_events": ["ticket.created", "ticket.resolved"],
            "payload_template": {"event": "{{event_type}}"},
        }
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.create(
            company_id=company_id,
            integration_type="webhook_out",
            name="Outgoing Webhook",
            config=config,
        )

        assert result["type"] == "webhook_out"
        assert result["status"] == "draft"

    def test_create_database_integration(self, service, mock_db, company_id):
        config = {
            "connection_string": "postgresql://user:pass@host:5432/mydb",
            "db_type": "postgresql",
            "query_template": "SELECT * FROM customers WHERE id = :id",
        }
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        result = service.create(
            company_id=company_id,
            integration_type="database",
            name="Customer DB",
            config=config,
        )

        assert result["type"] == "database"
        assert result["status"] == "draft"
        # Connection string should be masked
        assert "pass" not in result["config"]["connection_string"]
        assert "****" in result["config"]["connection_string"]

    def test_create_invalid_type_raises(self, service, company_id):
        with pytest.raises(ValidationError) as exc_info:
            service.create(
                company_id=company_id,
                integration_type="invalid_type",
                name="Bad Type",
                config={},
            )
        assert "Invalid integration type" in str(exc_info.value.message)

    def test_create_missing_required_fields(self, service, company_id):
        # REST requires url and method — validation fails before plan limit
        # check
        with pytest.raises(ValidationError) as exc_info:
            service.create(
                company_id=company_id,
                integration_type="rest",
                name="Missing Fields",
                config={"auth_type": "bearer"},
            )
        assert "Missing required config fields" in str(exc_info.value.message)

    def test_create_invalid_auth_type(self, service, company_id):
        with pytest.raises(ValidationError) as exc_info:
            service.create(
                company_id=company_id,
                integration_type="rest",
                name="Bad Auth",
                config={
                    "url": "https://example.com",
                    "method": "GET",
                    "auth_type": "ntlm"},
            )
        assert "Invalid auth_type" in str(exc_info.value.message)

    def test_create_invalid_http_method(self, service, company_id):
        with pytest.raises(ValidationError) as exc_info:
            service.create(
                company_id=company_id,
                integration_type="rest",
                name="Bad Method",
                config={"url": "https://example.com", "method": "INVALID"},
            )
        assert "Invalid HTTP method" in str(exc_info.value.message)

    def test_create_plan_limit_enforced(self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        with pytest.raises(ValidationError) as exc_info:
            service.create(
                company_id=company_id,
                integration_type="rest",
                name="Over Limit",
                config={"url": "https://example.com", "method": "GET"},
            )
        assert "limit" in str(exc_info.value.message).lower()

    def test_create_method_uppercases_http_method(
            self, service, mock_db, company_id):
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        config = {"url": "https://example.com", "method": "post"}
        service.create(
            company_id=company_id,
            integration_type="rest",
            name="Lowercase Method",
            config=config,
        )
        # Verify the config stored has uppercase method
        call_args = mock_db.add.call_args[0][0]
        stored_config = _decrypt_config(call_args.config_encrypted)
        assert stored_config["method"] == "POST"


# ══════════════════════════════════════════════════════════════════
# GET / LIST TESTS
# ══════════════════════════════════════════════════════════════════

class TestGetAndList:
    """Test retrieval operations."""

    def test_get_returns_masked_integration(self, service, mock_db):
        integration = _make_mock_integration()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.get("int-123", "comp-abc-123")
        assert result is not None
        assert result["id"] == "int-123"
        assert result["type"] == "rest"
        # Token should be masked
        assert "secret-token-12345" not in result["config"]["token"]
        assert "****" in result["config"]["token"]

    def test_get_not_found_returns_none(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = service.get("nonexistent", "comp-abc-123")
        assert result is None

    def test_list_returns_all_for_company(self, service, mock_db):
        integration = _make_mock_integration()
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            integration]
        mock_db.query.return_value = mock_query

        results = service.list("comp-abc-123")
        assert len(results) == 1
        assert results[0]["id"] == "int-123"

    def test_list_filters_by_type(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        service.list("comp-abc-123", integration_type="rest")
        # Should have called filter multiple times (once for company_id, once
        # for type)
        assert mock_query.filter.call_count >= 1

    def test_list_invalid_type_raises(self, service, mock_db):
        with pytest.raises(ValidationError):
            service.list("comp-abc-123", integration_type="invalid")

    def test_list_filters_by_status(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        service.list("comp-abc-123", status="active")

    def test_list_invalid_status_raises(self, service, mock_db):
        with pytest.raises(ValidationError):
            service.list("comp-abc-123", status="invalid_status")


# ══════════════════════════════════════════════════════════════════
# UPDATE / DELETE / ACTIVATE TESTS
# ══════════════════════════════════════════════════════════════════

class TestUpdateDeleteActivate:
    """Test update, delete, and activate operations."""

    def test_update_name(self, service, mock_db):
        integration = _make_mock_integration(status="draft")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.update("int-123", "comp-abc-123", name="New Name")
        assert result["name"] == "New Name"

    def test_update_config_resets_error_count(self, service, mock_db):
        integration = _make_mock_integration(
            status="active",
            consecutive_error_count=2,
            last_error_message="Connection failed",
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.update(
            "int-123", "comp-abc-123",
            config={"url": "https://new-url.example.com"},
        )
        assert integration.consecutive_error_count == 0
        assert integration.last_error_message is None

    def test_update_disabled_integration_raises(self, service, mock_db):
        integration = _make_mock_integration(status="disabled")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError) as exc_info:
            service.update("int-123", "comp-abc-123", name="New Name")
        assert "Cannot update" in str(exc_info.value.message)

    def test_update_not_found_raises(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError):
            service.update("nonexistent", "comp-abc-123", name="New Name")

    def test_delete_success(self, service, mock_db):
        integration = _make_mock_integration()
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.delete("int-123", "comp-abc-123")
        assert result is True
        mock_db.delete.assert_called_once_with(integration)

    def test_delete_not_found_raises(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError):
            service.delete("nonexistent", "comp-abc-123")

    def test_activate_draft_to_active(self, service, mock_db):
        integration = _make_mock_integration(status="draft")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.activate("int-123", "comp-abc-123")
        assert result["status"] == "active"
        assert integration.status == "active"

    def test_activate_non_draft_raises(self, service, mock_db):
        integration = _make_mock_integration(status="active")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError) as exc_info:
            service.activate("int-123", "comp-abc-123")
        assert "Cannot activate" in str(exc_info.value.message)

    def test_activate_not_found_raises(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError):
            service.activate("nonexistent", "comp-abc-123")


# ══════════════════════════════════════════════════════════════════
# TEST CONNECTIVITY TESTS
# ══════════════════════════════════════════════════════════════════

class TestConnectivity:
    """Test connectivity testing for each integration type."""

    def test_test_rest_success(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="rest",
            config_encrypted=_encrypt_config({
                "url": "https://httpbin.org/get",
                "method": "GET",
                "auth_type": "none",
            }),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        with patch("app.services.custom_integration_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__ = MagicMock(
                return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.request.return_value = mock_response

            result = service.test_connectivity("int-123", "comp-abc-123")

        assert result["success"] is True
        assert result["type"] == "rest"
        assert result["latency_ms"] is not None

    def test_test_rest_server_error(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="rest",
            config_encrypted=_encrypt_config({
                "url": "https://httpbin.org/status/500",
                "method": "GET",
                "auth_type": "none",
            }),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        with patch("app.services.custom_integration_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__enter__ = MagicMock(
                return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.request.return_value = mock_response

            result = service.test_connectivity("int-123", "comp-abc-123")

        assert result["success"] is False
        assert "500" in result["message"]

    def test_test_rest_timeout(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="rest",
            config_encrypted=_encrypt_config({
                "url": "https://slow.example.com",
                "method": "GET",
                "auth_type": "none",
            }),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        import httpx
        with patch("app.services.custom_integration_service.httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(
                return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.request.side_effect = httpx.TimeoutException(
                "timeout")

            result = service.test_connectivity("int-123", "comp-abc-123")

        assert result["success"] is False
        assert "timed out" in result["message"].lower()

    def test_test_webhook_in_success(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="webhook_in",
            webhook_id="wh-abc-123",
            config_encrypted=_encrypt_config({
                "expected_payload_schema": {"type": "object"},
                "secret": "whsec-test-secret",
            }),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.test_connectivity("int-123", "comp-abc-123")
        assert result["success"] is True
        assert "valid" in result["message"].lower()

    def test_test_webhook_in_missing_schema(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="webhook_in",
            webhook_id="wh-abc-123",
            config_encrypted=_encrypt_config({"secret": "whsec-test-secret"}),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.test_connectivity("int-123", "comp-abc-123")
        assert result["success"] is False
        assert "schema" in result["message"].lower()

    def test_test_webhook_out_success(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="webhook_out",
            config_encrypted=_encrypt_config({
                "url": "https://hooks.example.com/parwa",
                "method": "POST",
                "trigger_events": ["ticket.created"],
            }),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        with patch("app.services.custom_integration_service.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__ = MagicMock(
                return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.request.return_value = mock_response

            result = service.test_connectivity("int-123", "comp-abc-123")

        assert result["success"] is True

    def test_test_database_unsupported_type(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="database",
            config_encrypted=_encrypt_config({
                "connection_string": "some-connection",
                "db_type": "oracle",
            }),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.test_connectivity("int-123", "comp-abc-123")
        assert result["success"] is False
        assert "Unsupported" in result["message"]

    def test_test_not_found_raises(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValidationError):
            service.test_connectivity("nonexistent", "comp-abc-123")


# ══════════════════════════════════════════════════════════════════
# ERROR TRACKING & AUTO-DISABLE TESTS
# ══════════════════════════════════════════════════════════════════

class TestErrorTracking:
    """Test error recording and auto-disable at 3 consecutive errors."""

    def test_record_success_resets_count(self, service, mock_db):
        integration = _make_mock_integration(consecutive_error_count=2)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        service.record_success("int-123", "comp-abc-123")
        assert integration.consecutive_error_count == 0
        assert integration.last_error_message is None

    def test_record_failure_increments_count(self, service, mock_db):
        integration = _make_mock_integration(consecutive_error_count=0)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        auto_disabled = service.record_failure(
            "int-123", "comp-abc-123", "Connection refused")
        assert integration.consecutive_error_count == 1
        assert auto_disabled is False

    def test_record_failure_auto_disables_at_3(self, service, mock_db):
        integration = _make_mock_integration(
            status="active",
            consecutive_error_count=2,
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        auto_disabled = service.record_failure(
            "int-123", "comp-abc-123", "Connection refused")
        assert integration.consecutive_error_count == 3
        assert integration.status == "disabled"
        assert auto_disabled is True

    def test_record_failure_not_found_returns_false(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        auto_disabled = service.record_failure(
            "nonexistent", "comp-abc-123", "Error")
        assert auto_disabled is False

    def test_test_connectivity_auto_disables_at_3(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="rest",
            status="active",
            consecutive_error_count=2,
            config_encrypted=_encrypt_config({
                "url": "https://failing.example.com",
                "method": "GET",
                "auth_type": "none",
            }),
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        import httpx
        with patch("app.services.custom_integration_service.httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(
                return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.request.side_effect = httpx.ConnectError(
                "refused")

            result = service.test_connectivity("int-123", "comp-abc-123")

        assert result["success"] is False
        assert result["auto_disabled"] is True
        assert integration.status == "disabled"


# ══════════════════════════════════════════════════════════════════
# WEBHOOK ID LOOKUP TESTS
# ══════════════════════════════════════════════════════════════════

class TestWebhookIdLookup:
    """Test get_by_webhook_id for incoming webhooks."""

    def test_get_by_webhook_id_found(self, service, mock_db):
        integration = _make_mock_integration(
            integration_type="webhook_in",
            webhook_id="wh-abc-123",
            status="active",
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = integration
        mock_db.query.return_value = mock_query

        result = service.get_by_webhook_id("wh-abc-123")
        assert result is not None
        assert result.webhook_id == "wh-abc-123"

    def test_get_by_webhook_id_not_found(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = service.get_by_webhook_id("nonexistent")
        assert result is None


# ══════════════════════════════════════════════════════════════════
# TO_DICT TESTS
# ══════════════════════════════════════════════════════════════════

class TestToDict:
    """Test _to_dict serialization."""

    def test_to_dict_masked(self, service):
        integration = _make_mock_integration()
        result = service._to_dict(integration, mask_credentials=True)
        assert result["id"] == "int-123"
        assert result["company_id"] == "comp-abc-123"
        assert result["type"] == "rest"
        assert result["status"] == "draft"
        assert "secret-token-12345" not in str(result["config"])

    def test_to_dict_webhook_url(self, service):
        integration = _make_mock_integration(
            integration_type="webhook_in",
            webhook_id="wh-abc-123",
            config_encrypted=_encrypt_config({"secret": "test"}),
        )
        result = service._to_dict(integration, mask_credentials=True)
        assert result["webhook_url"] == "/api/integrations/webhooks/incoming/wh-abc-123"

    def test_to_dict_non_webhook_no_webhook_url(self, service):
        integration = _make_mock_integration(integration_type="rest")
        result = service._to_dict(integration, mask_credentials=True)
        assert result["webhook_url"] is None

    def test_to_dict_timestamps(self, service):
        integration = _make_mock_integration()
        result = service._to_dict(integration, mask_credentials=True)
        assert result["created_at"] is not None
        assert result["updated_at"] is not None


# ══════════════════════════════════════════════════════════════════
# AUTH HEADER BUILDER TESTS
# ══════════════════════════════════════════════════════════════════

class TestAuthHeaders:
    """Test _build_auth_headers."""

    def test_bearer_auth(self, service):
        headers = service._build_auth_headers(
            {"auth_type": "bearer", "token": "test-token"})
        assert headers["Authorization"] == "Bearer test-token"

    def test_bearer_auth_uses_access_token(self, service):
        headers = service._build_auth_headers(
            {"auth_type": "bearer", "access_token": "ghp_123"})
        assert headers["Authorization"] == "Bearer ghp_123"

    def test_basic_auth(self, service):
        headers = service._build_auth_headers(
            {"auth_type": "basic", "username": "user", "password": "pass"})
        assert headers["Authorization"].startswith("Basic ")

    def test_api_key_auth(self, service):
        headers = service._build_auth_headers(
            {"auth_type": "api_key", "api_key": "sk-123"})
        assert headers["X-API-Key"] == "sk-123"

    def test_api_key_custom_header(self, service):
        headers = service._build_auth_headers({
            "auth_type": "api_key",
            "api_key_header": "X-Custom-Key",
            "api_key": "custom-val",
        })
        assert headers["X-Custom-Key"] == "custom-val"

    def test_oauth2_auth(self, service):
        headers = service._build_auth_headers(
            {"auth_type": "oauth2", "access_token": "ya29.abc"})
        assert headers["Authorization"] == "Bearer ya29.abc"

    def test_none_auth(self, service):
        headers = service._build_auth_headers({"auth_type": "none"})
        assert headers == {}

    def test_no_auth_type(self, service):
        headers = service._build_auth_headers({})
        assert headers == {}


# ══════════════════════════════════════════════════════════════════
# CONNECTION STRING MASKING TESTS
# ══════════════════════════════════════════════════════════════════

class TestConnectionMasking:
    """Test _mask_connection_string."""

    def test_mask_postgres_connection_string(self):
        conn = "postgresql://user:mysecretpassword@localhost:5432/mydb"
        masked = CustomIntegrationService._mask_connection_string(conn)
        assert "mysecretpassword" not in masked
        assert "****" in masked
        assert "postgresql://" in masked

    def test_mask_mysql_connection_string(self):
        conn = "mysql://admin:supersecret@db-host:3306/production"
        masked = CustomIntegrationService._mask_connection_string(conn)
        assert "supersecret" not in masked
        assert "****" in masked

    def test_mask_no_password(self):
        conn = "postgresql://localhost:5432/mydb"
        masked = CustomIntegrationService._mask_connection_string(conn)
        assert "****" not in masked
