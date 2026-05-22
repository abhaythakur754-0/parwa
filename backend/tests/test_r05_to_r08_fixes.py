"""
Comprehensive unit and integration tests for R-05 through R-08 fixes.

R-05: Version Single Source of Truth
R-06: Response Model Validation
R-07: Configurable Settings
R-08: Pydantic Schemas for Integration, Approval, Technique
"""

import os
from typing import Optional, get_type_hints
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError


# ════════════════════════════════════════════════════════════════════════
# R-05: Version Single Source of Truth
# ════════════════════════════════════════════════════════════════════════


class TestR05VersionSingleSourceOfTruth:
    """Verify that APP_VERSION is defined once in Settings and used everywhere."""

    def test_r05_app_version_in_config(self):
        """Verify Settings().APP_VERSION == "0.3.0".

        The version must be a single constant in app.config.Settings
        rather than duplicated across modules.
        """
        from app.config import Settings

        settings = Settings()
        assert settings.APP_VERSION == "0.3.0", (
            f"Expected APP_VERSION='0.3.0', got '{settings.APP_VERSION}'"
        )

    def test_r05_health_endpoint_uses_config_version(self):
        """Verify that health.py's APP_VERSION comes from settings.

        R-05 FIX: health.py should import and use get_settings().APP_VERSION
        instead of a hardcoded version string.
        """
        from app.api.health import APP_VERSION
        from app.config import Settings

        expected = Settings().APP_VERSION
        assert APP_VERSION == expected, (
            f"health.py APP_VERSION='{APP_VERSION}' does not match "
            f"Settings.APP_VERSION='{expected}'"
        )

    def test_r05_main_fastapi_version_matches_config(self):
        """Verify that the FastAPI app's version comes from config.APP_VERSION.

        R-05 FIX: The FastAPI constructor should use get_settings().APP_VERSION
        for the version parameter instead of a hardcoded string.
        """
        from app.config import Settings

        # Import the app — it's already constructed at module level
        from app.main import app

        expected = Settings().APP_VERSION
        assert app.version == expected, (
            f"FastAPI app.version='{app.version}' does not match "
            f"Settings.APP_VERSION='{expected}'"
        )

    def test_r05_version_env_override(self, monkeypatch):
        """Verify APP_VERSION can be overridden via env var APP_VERSION=1.0.0.

        R-05 FIX: Since APP_VERSION is a pydantic-settings field, it should
        be overridable via the APP_VERSION environment variable.
        """
        from app.config import Settings, get_settings

        # Clear the lru_cache so we get a fresh instance
        get_settings.cache_clear()

        monkeypatch.setenv("APP_VERSION", "1.0.0")

        try:
            settings = Settings()
            assert settings.APP_VERSION == "1.0.0", (
                f"Expected APP_VERSION='1.0.0' after env override, "
                f"got '{settings.APP_VERSION}'"
            )
        finally:
            # Restore original state
            get_settings.cache_clear()
            monkeypatch.delenv("APP_VERSION", raising=False)


# ════════════════════════════════════════════════════════════════════════
# R-06: Response Model Validation
# ════════════════════════════════════════════════════════════════════════


class TestR06ResponseModelValidation:
    """Verify that all API endpoints have explicit response_model declarations.

    R-06 FIX: Every endpoint should have a response_model for OpenAPI docs
    and runtime validation.
    """

    def _get_route_response_model(self, router, path: str, method: str = "GET"):
        """Helper to find a route's response_model by path and method."""
        for route in router.routes:
            if not hasattr(route, "path"):
                continue
            if route.path == path:
                if hasattr(route, "methods"):
                    if method.upper() in route.methods:
                        return getattr(route, "response_model", None)
        return None

    # ── Health endpoints ──────────────────────────────────────────────

    def test_r06_health_endpoint_has_response_model(self):
        """Verify /health endpoint has response_model=HealthResponse."""
        from app.api.health import router as health_router, HealthResponse

        model = self._get_route_response_model(health_router, "/health", "GET")
        assert model is not None, "/health endpoint has no response_model"
        assert model == HealthResponse, (
            f"/health response_model is {model}, expected HealthResponse"
        )

    def test_r06_health_detail_has_response_model(self):
        """Verify /health/detail endpoint has response_model=HealthDetailResponse."""
        from app.api.health import router as health_router, HealthDetailResponse

        model = self._get_route_response_model(
            health_router, "/health/detail", "GET"
        )
        assert model is not None, "/health/detail endpoint has no response_model"
        assert model == HealthDetailResponse, (
            f"/health/detail response_model is {model}, expected HealthDetailResponse"
        )

    def test_r06_readiness_has_response_model(self):
        """Verify /ready endpoint has response_model=ReadinessResponse."""
        from app.api.health import router as health_router, ReadinessResponse

        model = self._get_route_response_model(health_router, "/ready", "GET")
        assert model is not None, "/ready endpoint has no response_model"
        assert model == ReadinessResponse, (
            f"/ready response_model is {model}, expected ReadinessResponse"
        )

    # ── MFA endpoints ─────────────────────────────────────────────────

    def test_r06_mfa_login_verify_has_response_model(self):
        """Verify MFA verify login endpoint has response_model."""
        from app.api.mfa import router as mfa_router, MFALoginVerifyResponse

        model = self._get_route_response_model(
            mfa_router, "/api/auth/mfa/verify", "POST"
        )
        assert model is not None, (
            "/api/auth/mfa/verify endpoint has no response_model"
        )
        assert model == MFALoginVerifyResponse, (
            f"MFA verify response_model is {model}, "
            f"expected MFALoginVerifyResponse"
        )

    def test_r06_mfa_backup_codes_count_has_response_model(self):
        """Verify backup codes count endpoint has response_model."""
        from app.api.mfa import router as mfa_router, BackupCodesCountResponse

        model = self._get_route_response_model(
            mfa_router, "/api/auth/mfa/backup-codes", "GET"
        )
        assert model is not None, (
            "/api/auth/mfa/backup-codes GET endpoint has no response_model"
        )
        assert model == BackupCodesCountResponse, (
            f"Backup codes count response_model is {model}, "
            f"expected BackupCodesCountResponse"
        )

    def test_r06_mfa_backup_code_use_has_response_model(self):
        """Verify backup code use endpoint has response_model."""
        from app.api.mfa import router as mfa_router, BackupCodeUseResponse

        model = self._get_route_response_model(
            mfa_router, "/api/auth/mfa/backup-codes/use", "POST"
        )
        assert model is not None, (
            "/api/auth/mfa/backup-codes/use endpoint has no response_model"
        )
        assert model == BackupCodeUseResponse, (
            f"Backup code use response_model is {model}, "
            f"expected BackupCodeUseResponse"
        )

    # ── Webhook endpoints ─────────────────────────────────────────────

    def test_r06_webhook_status_has_response_model(self):
        """Verify webhook status endpoint has response_model."""
        from app.api.webhooks import router as webhook_router, WebhookStatusResponse

        model = self._get_route_response_model(
            webhook_router, "/api/webhooks/status/{event_db_id}", "GET"
        )
        assert model is not None, (
            "/api/webhooks/status/{event_db_id} endpoint has no response_model"
        )
        assert model == WebhookStatusResponse, (
            f"Webhook status response_model is {model}, "
            f"expected WebhookStatusResponse"
        )


# ════════════════════════════════════════════════════════════════════════
# R-07: Configurable Settings
# ════════════════════════════════════════════════════════════════════════


class TestR07ConfigurableSettings:
    """Verify that previously hardcoded values are now configurable via Settings.

    R-07 FIX: Operational tuning parameters should be configurable through
    environment variables so ops teams can adjust them without code changes.
    """

    # ── Default value tests ───────────────────────────────────────────

    def test_r07_pricing_token_ttl_in_config(self):
        """Verify PRICING_TOKEN_TTL_SECONDS defaults to 3600."""
        from app.config import Settings

        settings = Settings()
        assert settings.PRICING_TOKEN_TTL_SECONDS == 3600, (
            f"Expected PRICING_TOKEN_TTL_SECONDS=3600, "
            f"got {settings.PRICING_TOKEN_TTL_SECONDS}"
        )

    def test_r07_pricing_max_quantity_in_config(self):
        """Verify PRICING_MAX_VARIANT_QUANTITY defaults to 10."""
        from app.config import Settings

        settings = Settings()
        assert settings.PRICING_MAX_VARIANT_QUANTITY == 10, (
            f"Expected PRICING_MAX_VARIANT_QUANTITY=10, "
            f"got {settings.PRICING_MAX_VARIANT_QUANTITY}"
        )

    def test_r07_pricing_input_max_length_in_config(self):
        """Verify PRICING_INPUT_MAX_LENGTH defaults to 100."""
        from app.config import Settings

        settings = Settings()
        assert settings.PRICING_INPUT_MAX_LENGTH == 100, (
            f"Expected PRICING_INPUT_MAX_LENGTH=100, "
            f"got {settings.PRICING_INPUT_MAX_LENGTH}"
        )

    def test_r07_mfa_session_ttl_in_config(self):
        """Verify MFA_SESSION_TTL_SECONDS defaults to 300."""
        from app.config import Settings

        settings = Settings()
        assert settings.MFA_SESSION_TTL_SECONDS == 300, (
            f"Expected MFA_SESSION_TTL_SECONDS=300, "
            f"got {settings.MFA_SESSION_TTL_SECONDS}"
        )

    def test_r07_kb_max_file_size_in_config(self):
        """Verify KB_MAX_FILE_SIZE defaults to 52428800 (50 MB)."""
        from app.config import Settings

        settings = Settings()
        assert settings.KB_MAX_FILE_SIZE == 52428800, (
            f"Expected KB_MAX_FILE_SIZE=52428800, "
            f"got {settings.KB_MAX_FILE_SIZE}"
        )

    def test_r07_kb_max_retry_in_config(self):
        """Verify KB_MAX_RETRY_COUNT defaults to 3."""
        from app.config import Settings

        settings = Settings()
        assert settings.KB_MAX_RETRY_COUNT == 3, (
            f"Expected KB_MAX_RETRY_COUNT=3, "
            f"got {settings.KB_MAX_RETRY_COUNT}"
        )

    def test_r07_webhook_max_payload_in_config(self):
        """Verify WEBHOOK_MAX_PAYLOAD_SIZE defaults to 1048576 (1 MB)."""
        from app.config import Settings

        settings = Settings()
        assert settings.WEBHOOK_MAX_PAYLOAD_SIZE == 1048576, (
            f"Expected WEBHOOK_MAX_PAYLOAD_SIZE=1048576, "
            f"got {settings.WEBHOOK_MAX_PAYLOAD_SIZE}"
        )

    def test_r07_webhook_max_age_in_config(self):
        """Verify WEBHOOK_MAX_AGE_SECONDS defaults to 300 (5 minutes)."""
        from app.config import Settings

        settings = Settings()
        assert settings.WEBHOOK_MAX_AGE_SECONDS == 300, (
            f"Expected WEBHOOK_MAX_AGE_SECONDS=300, "
            f"got {settings.WEBHOOK_MAX_AGE_SECONDS}"
        )

    # ── Environment variable override tests ───────────────────────────

    def test_r07_pricing_token_ttl_env_override(self, monkeypatch):
        """Verify env var override works for PRICING_TOKEN_TTL_SECONDS."""
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("PRICING_TOKEN_TTL_SECONDS", "7200")

        try:
            settings = Settings()
            assert settings.PRICING_TOKEN_TTL_SECONDS == 7200, (
                f"Expected PRICING_TOKEN_TTL_SECONDS=7200 after env override, "
                f"got {settings.PRICING_TOKEN_TTL_SECONDS}"
            )
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("PRICING_TOKEN_TTL_SECONDS", raising=False)

    def test_r07_mfa_session_ttl_env_override(self, monkeypatch):
        """Verify env var override works for MFA_SESSION_TTL_SECONDS."""
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("MFA_SESSION_TTL_SECONDS", "600")

        try:
            settings = Settings()
            assert settings.MFA_SESSION_TTL_SECONDS == 600, (
                f"Expected MFA_SESSION_TTL_SECONDS=600 after env override, "
                f"got {settings.MFA_SESSION_TTL_SECONDS}"
            )
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("MFA_SESSION_TTL_SECONDS", raising=False)

    def test_r07_kb_max_file_size_env_override(self, monkeypatch):
        """Verify env var override works for KB_MAX_FILE_SIZE."""
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("KB_MAX_FILE_SIZE", "104857600")

        try:
            settings = Settings()
            assert settings.KB_MAX_FILE_SIZE == 104857600, (
                f"Expected KB_MAX_FILE_SIZE=104857600 after env override, "
                f"got {settings.KB_MAX_FILE_SIZE}"
            )
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("KB_MAX_FILE_SIZE", raising=False)


# ════════════════════════════════════════════════════════════════════════
# R-08: Pydantic Schemas for Integration, Approval, Technique
# ════════════════════════════════════════════════════════════════════════


class TestR08IntegrationSchemas:
    """Verify Integration domain Pydantic schemas (R-08).

    Security rule: encrypted fields are NEVER exposed in Response schemas.
    """

    def test_r08_integration_create_schema_validates(self):
        """Create IntegrationCreate with valid data."""
        from app.schemas.integration import IntegrationCreate

        schema = IntegrationCreate(
            integration_type="slack",
            name="Slack Workspace",
            status="connected",
            settings='{"channel": "#general"}',
        )
        assert schema.integration_type == "slack"
        assert schema.name == "Slack Workspace"
        assert schema.status == "connected"

    def test_r08_integration_response_excludes_encrypted(self):
        """Verify IntegrationResponse has no `credentials_encrypted` field.

        R-08 FIX: Encrypted fields must never appear in response schemas
        to prevent credential leakage.
        """
        from app.schemas.integration import IntegrationResponse

        field_names = set(IntegrationResponse.model_fields.keys())
        assert "credentials_encrypted" not in field_names, (
            "IntegrationResponse must not include 'credentials_encrypted' field"
        )
        # Verify expected fields ARE present
        assert "id" in field_names
        assert "company_id" in field_names
        assert "integration_type" in field_names

    def test_r08_rest_connector_create_schema(self):
        """Create RESTConnectorCreate with valid data."""
        from app.schemas.integration import RESTConnectorCreate

        schema = RESTConnectorCreate(
            integration_id="int-123",
            base_url="https://api.example.com/v1",
            auth_type="bearer",
        )
        assert schema.integration_id == "int-123"
        assert schema.base_url == "https://api.example.com/v1"
        assert schema.auth_type == "bearer"

    def test_r08_rest_connector_response_excludes_encrypted(self):
        """Verify no `auth_config_encrypted` field in RESTConnectorResponse."""
        from app.schemas.integration import RESTConnectorResponse

        field_names = set(RESTConnectorResponse.model_fields.keys())
        assert "auth_config_encrypted" not in field_names, (
            "RESTConnectorResponse must not include 'auth_config_encrypted' field"
        )

    def test_r08_webhook_integration_create_schema(self):
        """Create WebhookIntegrationCreate with valid data."""
        from app.schemas.integration import WebhookIntegrationCreate

        schema = WebhookIntegrationCreate(
            integration_id="int-456",
            webhook_url="https://hooks.example.com/trigger",
            secret="whsec_abc123",
        )
        assert schema.integration_id == "int-456"
        assert schema.webhook_url == "https://hooks.example.com/trigger"
        assert schema.secret == "whsec_abc123"

    def test_r08_mcp_connection_create_schema(self):
        """Create MCPConnectionCreate with valid data."""
        from app.schemas.integration import MCPConnectionCreate

        schema = MCPConnectionCreate(
            name="Production MCP",
            server_url="https://mcp.example.com",
        )
        assert schema.name == "Production MCP"
        assert schema.server_url == "https://mcp.example.com"

    def test_r08_mcp_response_excludes_encrypted(self):
        """Verify no `auth_token_encrypted` in MCPConnectionResponse."""
        from app.schemas.integration import MCPConnectionResponse

        field_names = set(MCPConnectionResponse.model_fields.keys())
        assert "auth_token_encrypted" not in field_names, (
            "MCPConnectionResponse must not include 'auth_token_encrypted' field"
        )

    def test_r08_db_connection_create_schema(self):
        """Create DBConnectionCreate with valid data."""
        from app.schemas.integration import DBConnectionCreate

        schema = DBConnectionCreate(
            name="Analytics DB",
            db_type="postgresql",
            is_readonly=True,
        )
        assert schema.name == "Analytics DB"
        assert schema.db_type == "postgresql"
        assert schema.is_readonly is True

    def test_r08_db_response_excludes_encrypted(self):
        """Verify no `connection_string_encrypted` in DBConnectionResponse."""
        from app.schemas.integration import DBConnectionResponse

        field_names = set(DBConnectionResponse.model_fields.keys())
        assert "connection_string_encrypted" not in field_names, (
            "DBConnectionResponse must not include 'connection_string_encrypted' field"
        )


class TestR08ApprovalSchemas:
    """Verify Approval domain Pydantic schemas (R-08)."""

    def test_r08_approval_queue_create_schema(self):
        """Create ApprovalQueueCreate with valid data."""
        from app.schemas.approval import ApprovalQueueCreate

        schema = ApprovalQueueCreate(
            company_id="comp-1",
            action_type="refund",
            confidence_score="85.50",
            risk_level="medium",
            amount="99.99",
        )
        assert schema.company_id == "comp-1"
        assert schema.action_type == "refund"

    def test_r08_approval_queue_status_validation(self):
        """Test that invalid status raises validation error.

        ApprovalStatus is an Enum with: pending, approved, rejected, expired.
        An invalid status string should fail validation.
        """
        from app.schemas.approval import ApprovalQueueCreate

        with pytest.raises(ValidationError) as exc_info:
            ApprovalQueueCreate(
                company_id="comp-1",
                action_type="refund",
                status="invalid_status",
            )
        # Verify the error mentions the invalid value
        error_str = str(exc_info.value).lower()
        assert "invalid_status" in error_str or "validation" in error_str

    def test_r08_auto_approve_rule_create_schema(self):
        """Create AutoApproveRuleCreate with valid data."""
        from app.schemas.approval import AutoApproveRuleCreate

        schema = AutoApproveRuleCreate(
            company_id="comp-1",
            action_type="refund",
            min_confidence="90.00",
            created_by="user-1",
        )
        assert schema.company_id == "comp-1"
        assert schema.action_type == "refund"
        assert schema.is_active is False  # default

    def test_r08_executed_action_create_schema(self):
        """Create ExecutedActionCreate with valid data."""
        from app.schemas.approval import ExecutedActionCreate

        schema = ExecutedActionCreate(
            company_id="comp-1",
            action_type="email_send",
            action_data='{"to": "customer@example.com"}',
        )
        assert schema.company_id == "comp-1"
        assert schema.action_type == "email_send"

    def test_r08_undo_log_create_schema(self):
        """Create UndoLogCreate with valid data."""
        from app.schemas.approval import UndoLogCreate

        schema = UndoLogCreate(
            company_id="comp-1",
            executed_action_id="action-1",
            undo_type="reversal",
            undo_reason="Customer requested cancellation",
        )
        assert schema.company_id == "comp-1"
        assert schema.executed_action_id == "action-1"
        assert schema.undo_type.value == "reversal"

    def test_r08_undo_type_validation(self):
        """Test that invalid undo_type raises validation error.

        UndoType is an Enum with: reversal, email_recall.
        An invalid undo_type string should fail validation.
        """
        from app.schemas.approval import UndoLogCreate

        with pytest.raises(ValidationError) as exc_info:
            UndoLogCreate(
                company_id="comp-1",
                executed_action_id="action-1",
                undo_type="invalid_type",
            )
        error_str = str(exc_info.value).lower()
        assert "invalid_type" in error_str or "validation" in error_str

    def test_r08_approval_update_all_optional(self):
        """Verify ApprovalQueueUpdate fields are all Optional.

        R-08 FIX: Update schemas should allow partial updates, so
        every field must be Optional.
        """
        from app.schemas.approval import ApprovalQueueUpdate

        for field_name, field_info in ApprovalQueueUpdate.model_fields.items():
            is_optional = field_info.is_required() is False
            assert is_optional, (
                f"ApprovalQueueUpdate.{field_name} must be Optional "
                f"(required=True found)"
            )


class TestR08TechniqueSchemas:
    """Verify Technique domain Pydantic schemas (R-08)."""

    def test_r08_technique_config_create_schema(self):
        """Create TechniqueConfigurationCreate with tier_2."""
        from app.schemas.technique import TechniqueConfigurationCreate

        schema = TechniqueConfigurationCreate(
            company_id="comp-1",
            technique_id="reverse_thinking",
            tier="tier_2",
            is_enabled=True,
        )
        assert schema.company_id == "comp-1"
        assert schema.technique_id == "reverse_thinking"
        assert schema.tier == "tier_2"
        assert schema.is_enabled is True

    def test_r08_technique_config_tier_validation(self):
        """Test that invalid tier raises validation error.

        TechniqueConfigurationCreate.tier is Literal["tier_2", "tier_3"].
        Only tier_2 and tier_3 are valid values.
        """
        from app.schemas.technique import TechniqueConfigurationCreate

        with pytest.raises(ValidationError) as exc_info:
            TechniqueConfigurationCreate(
                company_id="comp-1",
                technique_id="cot",
                tier="tier_1",  # Invalid — only tier_2 and tier_3 allowed
            )
        error_str = str(exc_info.value).lower()
        assert "tier_1" in error_str or "validation" in error_str or "literal" in error_str

    def test_r08_technique_execution_create_schema(self):
        """Create TechniqueExecutionCreate with valid data."""
        from app.schemas.technique import TechniqueExecutionCreate

        schema = TechniqueExecutionCreate(
            company_id="comp-1",
            technique_id="step_back",
            tier="tier_2",
            tokens_input=500,
            tokens_output=200,
            latency_ms=1200,
            result_status="success",
        )
        assert schema.company_id == "comp-1"
        assert schema.technique_id == "step_back"
        assert schema.result_status == "success"
        assert schema.tokens_input == 500

    def test_r08_technique_execution_result_status_validation(self):
        """Test invalid result_status raises validation error.

        TechniqueExecutionCreate.result_status is a Literal with specific values:
        success, fallback, timeout, error, skipped_budget.
        """
        from app.schemas.technique import TechniqueExecutionCreate

        with pytest.raises(ValidationError) as exc_info:
            TechniqueExecutionCreate(
                company_id="comp-1",
                technique_id="cot",
                tier="tier_2",
                result_status="invalid_status",
            )
        error_str = str(exc_info.value).lower()
        assert (
            "invalid_status" in error_str
            or "validation" in error_str
            or "literal" in error_str
        )

    def test_r08_technique_version_create_schema(self):
        """Create TechniqueVersionCreate with valid data."""
        from app.schemas.technique import TechniqueVersionCreate

        schema = TechniqueVersionCreate(
            company_id="comp-1",
            technique_id="cot",
            version="v2",
            label="Chain of Thought v2 (compressed prompts)",
            is_active=True,
            is_default=False,
        )
        assert schema.technique_id == "cot"
        assert schema.version == "v2"
        assert schema.label == "Chain of Thought v2 (compressed prompts)"
        assert schema.ab_test_traffic_pct == 50  # default


class TestR08SchemaExportAndOptional:
    """Verify that all new schemas are importable and update schemas are all Optional."""

    def test_r08_schemas_exported_from_init(self):
        """Verify all new schemas are importable from app.schemas.

        R-08 FIX: All schemas must be re-exported from the package __init__
        so they can be imported with `from app.schemas import SchemaName`.
        """
        from app.schemas import (
            # Integration schemas
            IntegrationCreate,
            IntegrationUpdate,
            IntegrationResponse,
            RESTConnectorCreate,
            RESTConnectorResponse,
            WebhookIntegrationCreate,
            MCPConnectionCreate,
            MCPConnectionResponse,
            DBConnectionCreate,
            DBConnectionResponse,
            # Approval schemas
            ApprovalQueueCreate,
            ApprovalQueueUpdate,
            ApprovalQueueResponse,
            AutoApproveRuleCreate,
            ExecutedActionCreate,
            UndoLogCreate,
            # Technique schemas
            TechniqueConfigurationCreate,
            TechniqueConfigurationResponse,
            TechniqueExecutionCreate,
            TechniqueExecutionResponse,
            TechniqueVersionCreate,
            TechniqueVersionResponse,
        )

        # Verify they are actually classes (not None or mock objects)
        assert IntegrationCreate is not None
        assert ApprovalQueueCreate is not None
        assert TechniqueConfigurationCreate is not None

    def test_r08_integration_update_all_optional(self):
        """Verify IntegrationUpdate fields are all Optional.

        R-08 FIX: Update schemas should allow partial updates, so
        every field must be Optional (not required).
        """
        from app.schemas.integration import IntegrationUpdate

        for field_name, field_info in IntegrationUpdate.model_fields.items():
            is_optional = field_info.is_required() is False
            assert is_optional, (
                f"IntegrationUpdate.{field_name} must be Optional "
                f"(required=True found)"
            )

    def test_r08_approval_update_all_optional(self):
        """Verify ApprovalQueueUpdate fields are all Optional.

        R-08 FIX: Update schemas should allow partial updates.
        Already tested in TestR08ApprovalSchemas but also tested here
        for completeness of the R-08 verification suite.
        """
        from app.schemas.approval import ApprovalQueueUpdate

        for field_name, field_info in ApprovalQueueUpdate.model_fields.items():
            is_optional = field_info.is_required() is False
            assert is_optional, (
                f"ApprovalQueueUpdate.{field_name} must be Optional "
                f"(required=True found)"
            )
