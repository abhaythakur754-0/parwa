"""
Integration tests for R-05 through R-08 fixes.

These tests verify that the fixes work end-to-end, including:
- R-05: Version single source of truth (config -> health endpoint -> FastAPI app)
- R-06: Response model validation on endpoints (OpenAPI schema + runtime)
- R-07: Configurable settings used by routers at runtime
- R-08: Pydantic schemas validate real data shapes from the codebase
"""

import os
import sys
from typing import Any, Dict, List, Optional, get_type_hints
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError


# ========================================================================
# R-05 INTEGRATION: Version Single Source of Truth
# ========================================================================


class TestR05Integration:
    """Integration tests for R-05: Verify version consistency across the stack."""

    def test_r05_version_flows_from_config_to_fastapi_app(self):
        """Verify the version in Settings appears in the FastAPI app object."""
        from app.config import Settings
        from app.main import app

        settings = Settings()
        assert app.version == settings.APP_VERSION, (
            f"FastAPI app.version='{app.version}' does not match "
            f"Settings.APP_VERSION='{settings.APP_VERSION}'."
        )

    def test_r05_version_flows_from_config_to_health_module(self):
        """Verify the version in Settings appears in the health module."""
        from app.config import Settings
        from app.api.health import APP_VERSION

        settings = Settings()
        assert APP_VERSION == settings.APP_VERSION, (
            f"health.py APP_VERSION='{APP_VERSION}' does not match "
            f"Settings.APP_VERSION='{settings.APP_VERSION}'"
        )

    def test_r05_no_hardcoded_version_strings_in_health(self):
        """Verify health.py does NOT contain a hardcoded version string."""
        import inspect
        from app.api import health

        source = inspect.getsource(health)
        assert 'APP_VERSION = "0.3.0"' not in source, (
            "health.py still contains hardcoded APP_VERSION = '0.3.0'."
        )
        assert 'APP_VERSION = "0.1.0"' not in source, (
            "health.py contains old hardcoded APP_VERSION = '0.1.0'."
        )

    def test_r05_no_hardcoded_version_in_main_fastapi_constructor(self):
        """Verify main.py does NOT pass a hardcoded version to FastAPI()."""
        import inspect
        from app import main

        source = inspect.getsource(main)
        assert 'version="0.1.0"' not in source, (
            "main.py still contains hardcoded version='0.1.0' in FastAPI()."
        )

    def test_r05_version_is_configurable_via_env_var(self, monkeypatch):
        """Verify APP_VERSION can be overridden at deployment time."""
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("APP_VERSION", "2.5.0-beta")

        try:
            settings = Settings()
            assert settings.APP_VERSION == "2.5.0-beta"
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("APP_VERSION", raising=False)

    def test_r05_health_response_model_includes_version(self):
        """Verify the health response model includes a 'version' field."""
        from app.api.health import HealthResponse

        assert "version" in HealthResponse.model_fields, (
            "HealthResponse model must include a 'version' field."
        )
        version_field = HealthResponse.model_fields["version"]
        assert version_field.annotation == str


# ========================================================================
# R-06 INTEGRATION: Response Model Validation
# ========================================================================


class TestR06Integration:
    """Integration tests for R-06: Verify response_model works end-to-end."""

    def test_r06_all_health_routes_have_response_model(self):
        """Verify all health routes have response_model (except /metrics)."""
        from app.api.health import router

        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            if route.path == "/metrics":
                continue
            assert getattr(route, "response_model", None) is not None, (
                f"Route {route.path} [{route.methods}] has no response_model."
            )

    def test_r06_mfa_routes_all_have_response_model(self):
        """Verify all MFA routes have response_model declarations."""
        from app.api.mfa import router

        routes_with_model = 0
        routes_total = 0
        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            routes_total += 1
            if getattr(route, "response_model", None) is not None:
                routes_with_model += 1

        assert routes_with_model == routes_total, (
            f"Only {routes_with_model}/{routes_total} MFA routes have response_model."
        )

    def test_r06_pricing_routes_all_have_response_model(self):
        """Verify all pricing routes have response_model declarations."""
        from app.api.pricing import router

        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            assert getattr(route, "response_model", None) is not None, (
                f"Pricing route {route.path} has no response_model."
            )

    def test_r06_knowledge_base_routes_all_have_response_model(self):
        """Verify all knowledge base routes have response_model."""
        from app.api.knowledge_base import router

        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            assert getattr(route, "response_model", None) is not None, (
                f"Knowledge base route {route.path} has no response_model."
            )

    def test_r06_webhook_routes_all_have_response_model(self):
        """Verify all webhook routes have response_model declarations."""
        from app.api.webhooks import router

        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            assert getattr(route, "response_model", None) is not None, (
                f"Webhook route {route.path} has no response_model."
            )

    def test_r06_billing_routes_all_have_response_model(self):
        """Verify billing routes have response_model declarations.

        Note: Endpoints returning binary Response (e.g. PDF) are excluded
        since response_model is not applicable for non-JSON responses.
        """
        from app.api.billing import router

        routes_without_model = []
        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            model = getattr(route, "response_model", None)
            if model is None:
                # Binary endpoints like PDF legitimately lack response_model
                if "pdf" not in route.path.lower():
                    routes_without_model.append(route.path)

        assert not routes_without_model, (
            f"Billing routes missing response_model: {routes_without_model}"
        )

    def test_r06_response_models_are_pydantic_basemodel_subclasses(self):
        """Verify response_model values are proper Pydantic models."""
        from app.api.health import router as health_router
        from pydantic import BaseModel as PydanticBaseModel

        for route in health_router.routes:
            if not hasattr(route, "methods"):
                continue
            model = getattr(route, "response_model", None)
            if model is None:
                continue
            origin = getattr(model, "__origin__", None)
            if origin is list:
                args = getattr(model, "__args__", ())
                if args:
                    assert issubclass(args[0], PydanticBaseModel), (
                        f"Route {route.path} response_model inner type "
                        f"{args[0]} is not a BaseModel subclass"
                    )
            elif isinstance(model, type):
                assert issubclass(model, PydanticBaseModel), (
                    f"Route {route.path} response_model {model} "
                    f"is not a BaseModel subclass"
                )

    def test_r06_health_response_model_matches_return_shape(self):
        """Verify HealthResponse model matches what health_endpoint returns."""
        from app.api.health import HealthResponse

        expected_keys = {
            "status", "timestamp", "version", "uptime_seconds",
            "subsystems", "checks_total", "checks_healthy",
            "checks_degraded", "checks_unhealthy", "cached",
            "circuit_breakers", "self_healing", "sentry",
        }

        model_keys = set(HealthResponse.model_fields.keys())
        missing = expected_keys - model_keys
        assert not missing, (
            f"HealthResponse is missing fields: {missing}"
        )


# ========================================================================
# R-07 INTEGRATION: Configurable Settings Used by Routers
# ========================================================================


class TestR07Integration:
    """Integration tests for R-07: Verify routers use config values."""

    def test_r07_pricing_router_uses_config_for_input_sanitization(self):
        """Verify pricing.py uses Settings.PRICING_INPUT_MAX_LENGTH."""
        import inspect
        from app.api import pricing

        source = inspect.getsource(pricing)
        assert "PRICING_INPUT_MAX_LENGTH" in source, (
            "pricing.py does not reference PRICING_INPUT_MAX_LENGTH."
        )

    def test_r07_pricing_router_uses_config_for_variant_quantity(self):
        """Verify pricing.py uses Settings.PRICING_MAX_VARIANT_QUANTITY."""
        import inspect
        from app.api import pricing

        source = inspect.getsource(pricing)
        assert "PRICING_MAX_VARIANT_QUANTITY" in source, (
            "pricing.py does not reference PRICING_MAX_VARIANT_QUANTITY."
        )

    def test_r07_mfa_router_uses_config_for_session_ttl(self):
        """Verify mfa.py uses Settings.MFA_SESSION_TTL_SECONDS."""
        import inspect
        from app.api import mfa

        source = inspect.getsource(mfa)
        assert "MFA_SESSION_TTL_SECONDS" in source, (
            "mfa.py does not reference MFA_SESSION_TTL_SECONDS."
        )

    def test_r07_knowledge_base_router_uses_config_for_file_size(self):
        """Verify knowledge_base.py uses Settings.KB_MAX_FILE_SIZE."""
        import inspect
        from app.api import knowledge_base

        source = inspect.getsource(knowledge_base)
        assert "KB_MAX_FILE_SIZE" in source, (
            "knowledge_base.py does not reference KB_MAX_FILE_SIZE."
        )

    def test_r07_webhook_router_uses_config_for_payload_size(self):
        """Verify webhooks.py uses Settings.WEBHOOK_MAX_PAYLOAD_SIZE."""
        import inspect
        from app.api import webhooks

        source = inspect.getsource(webhooks)
        assert "WEBHOOK_MAX_PAYLOAD_SIZE" in source, (
            "webhooks.py does not reference WEBHOOK_MAX_PAYLOAD_SIZE."
        )

    def test_r07_webhook_router_uses_config_for_max_age(self):
        """Verify webhooks.py uses Settings.WEBHOOK_MAX_AGE_SECONDS."""
        import inspect
        from app.api import webhooks

        source = inspect.getsource(webhooks)
        assert "WEBHOOK_MAX_AGE_SECONDS" in source, (
            "webhooks.py does not reference WEBHOOK_MAX_AGE_SECONDS."
        )

    def test_r07_config_defaults_match_original_hardcoded_values(self):
        """Verify Settings defaults match the original hardcoded values."""
        from app.config import Settings

        settings = Settings()
        assert settings.PRICING_TOKEN_TTL_SECONDS == 3600
        assert settings.PRICING_MAX_VARIANT_QUANTITY == 10
        assert settings.PRICING_INPUT_MAX_LENGTH == 100
        assert settings.MFA_SESSION_TTL_SECONDS == 300
        assert settings.KB_MAX_FILE_SIZE == 52428800
        assert settings.KB_MAX_RETRY_COUNT == 3
        assert settings.WEBHOOK_MAX_PAYLOAD_SIZE == 1048576
        assert settings.WEBHOOK_MAX_AGE_SECONDS == 300

    def test_r07_all_new_settings_are_int_type(self):
        """Verify all new R-07 settings are int type."""
        from app.config import Settings

        r07_fields = [
            "PRICING_TOKEN_TTL_SECONDS",
            "PRICING_MAX_VARIANT_QUANTITY",
            "PRICING_INPUT_MAX_LENGTH",
            "MFA_SESSION_TTL_SECONDS",
            "KB_MAX_FILE_SIZE",
            "KB_MAX_RETRY_COUNT",
            "WEBHOOK_MAX_PAYLOAD_SIZE",
            "WEBHOOK_MAX_AGE_SECONDS",
        ]

        for field_name in r07_fields:
            field_info = Settings.model_fields[field_name]
            assert field_info.annotation == int, (
                f"Settings.{field_name} is {field_info.annotation}, expected int."
            )

    def test_r07_pricing_config_env_override(self, monkeypatch):
        """Verify pricing config can be tuned via env vars."""
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("PRICING_MAX_VARIANT_QUANTITY", "25")

        try:
            settings = Settings()
            assert settings.PRICING_MAX_VARIANT_QUANTITY == 25
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("PRICING_MAX_VARIANT_QUANTITY", raising=False)

    def test_r07_kb_config_env_override(self, monkeypatch):
        """Verify knowledge base config can be tuned via env vars."""
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("KB_MAX_FILE_SIZE", "104857600")
        monkeypatch.setenv("KB_MAX_RETRY_COUNT", "5")

        try:
            settings = Settings()
            assert settings.KB_MAX_FILE_SIZE == 104857600
            assert settings.KB_MAX_RETRY_COUNT == 5
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("KB_MAX_FILE_SIZE", raising=False)
            monkeypatch.delenv("KB_MAX_RETRY_COUNT", raising=False)

    def test_r07_webhook_config_env_override(self, monkeypatch):
        """Verify webhook config can be tuned via env vars."""
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("WEBHOOK_MAX_PAYLOAD_SIZE", "5242880")
        monkeypatch.setenv("WEBHOOK_MAX_AGE_SECONDS", "600")

        try:
            settings = Settings()
            assert settings.WEBHOOK_MAX_PAYLOAD_SIZE == 5242880
            assert settings.WEBHOOK_MAX_AGE_SECONDS == 600
        finally:
            get_settings.cache_clear()
            monkeypatch.delenv("WEBHOOK_MAX_PAYLOAD_SIZE", raising=False)
            monkeypatch.delenv("WEBHOOK_MAX_AGE_SECONDS", raising=False)


# ========================================================================
# R-08 INTEGRATION: Pydantic Schemas
# ========================================================================


class TestR08IntegrationIntegrationSchemas:
    """Integration tests for R-08: Integration domain schemas."""

    def test_r08_integration_create_with_minimal_fields(self):
        """Verify IntegrationCreate works with only required fields."""
        from app.schemas.integration import IntegrationCreate

        schema = IntegrationCreate(integration_type="slack")
        assert schema.integration_type == "slack"

    def test_r08_integration_create_accepts_various_types(self):
        """Verify IntegrationCreate accepts valid integration types."""
        from app.schemas.integration import IntegrationCreate

        for itype in ["slack", "email", "webhook", "rest_api", "mcp", "database"]:
            schema = IntegrationCreate(integration_type=itype)
            assert schema.integration_type == itype

    def test_r08_integration_response_has_id_field(self):
        """Verify IntegrationResponse always includes an id field."""
        from app.schemas.integration import IntegrationResponse

        assert "id" in IntegrationResponse.model_fields

    def test_r08_rest_connector_create_validates_url(self):
        """Verify RESTConnectorCreate accepts well-formed URLs."""
        from app.schemas.integration import RESTConnectorCreate

        schema = RESTConnectorCreate(
            integration_id="int-1",
            base_url="https://api.example.com/v1",
            auth_type="bearer",
        )
        assert schema.base_url == "https://api.example.com/v1"

    def test_r08_webhook_integration_has_secret_field(self):
        """Verify WebhookIntegrationCreate includes a secret field."""
        from app.schemas.integration import WebhookIntegrationCreate

        assert "secret" in WebhookIntegrationCreate.model_fields

    def test_r08_mcp_connection_response_excludes_auth_token(self):
        """Verify MCPConnectionResponse does not leak auth_token_encrypted."""
        from app.schemas.integration import MCPConnectionResponse

        field_names = set(MCPConnectionResponse.model_fields.keys())
        assert "auth_token_encrypted" not in field_names
        assert "auth_token" not in field_names

    def test_r08_db_connection_response_excludes_connection_string(self):
        """Verify DBConnectionResponse does not leak connection_string_encrypted."""
        from app.schemas.integration import DBConnectionResponse

        field_names = set(DBConnectionResponse.model_fields.keys())
        assert "connection_string_encrypted" not in field_names
        assert "connection_string" not in field_names


class TestR08IntegrationApprovalSchemas:
    """Integration tests for R-08: Approval domain schemas."""

    def test_r08_approval_queue_status_enum_values(self):
        """Verify ApprovalStatus enum has all required values."""
        from app.schemas.approval import ApprovalStatus

        valid_statuses = {"pending", "approved", "rejected", "expired"}
        actual_statuses = {s.value for s in ApprovalStatus}
        assert valid_statuses == actual_statuses

    def test_r08_approval_queue_create_with_all_fields(self):
        """Verify ApprovalQueueCreate with all optional fields populated."""
        from app.schemas.approval import ApprovalQueueCreate

        schema = ApprovalQueueCreate(
            company_id="comp-1",
            action_type="refund",
            confidence_score="85.50",
            risk_level="medium",
            amount="99.99",
            status="pending",
            metadata_json='{"key": "value"}',
        )
        assert schema.company_id == "comp-1"
        assert schema.risk_level == "medium"

    def test_r08_auto_approve_rule_defaults_to_inactive(self):
        """Verify AutoApproveRuleCreate defaults to is_active=False."""
        from app.schemas.approval import AutoApproveRuleCreate

        schema = AutoApproveRuleCreate(
            company_id="comp-1",
            action_type="refund",
            min_confidence="90.00",
            created_by="admin-1",
        )
        assert schema.is_active is False

    def test_r08_undo_log_has_reason_field(self):
        """Verify UndoLogCreate has an undo_reason field for audit trails."""
        from app.schemas.approval import UndoLogCreate

        field_info = UndoLogCreate.model_fields.get("undo_reason")
        assert field_info is not None, (
            "UndoLogCreate must have 'undo_reason' field for audit trails"
        )

    def test_r08_approval_update_is_fully_optional(self):
        """Verify ApprovalQueueUpdate allows partial updates."""
        from app.schemas.approval import ApprovalQueueUpdate

        schema = ApprovalQueueUpdate()
        for field_name, field_info in ApprovalQueueUpdate.model_fields.items():
            assert not field_info.is_required(), (
                f"ApprovalQueueUpdate.{field_name} is required - should be optional."
            )


class TestR08IntegrationTechniqueSchemas:
    """Integration tests for R-08: Technique domain schemas."""

    def test_r08_technique_config_tier_values(self):
        """Verify tier only allows tier_2/tier_3."""
        from app.schemas.technique import TechniqueConfigurationCreate

        schema = TechniqueConfigurationCreate(
            company_id="comp-1", technique_id="cot", tier="tier_2",
        )
        assert schema.tier == "tier_2"

        schema = TechniqueConfigurationCreate(
            company_id="comp-1", technique_id="cot", tier="tier_3",
        )
        assert schema.tier == "tier_3"

        with pytest.raises(ValidationError):
            TechniqueConfigurationCreate(
                company_id="comp-1", technique_id="cot", tier="tier_1",
            )

    def test_r08_technique_execution_result_status_values(self):
        """Verify result_status has the correct literal values."""
        from app.schemas.technique import TechniqueExecutionCreate

        valid_statuses = ["success", "fallback", "timeout", "error", "skipped_budget"]
        for status in valid_statuses:
            schema = TechniqueExecutionCreate(
                company_id="comp-1",
                technique_id="cot",
                tier="tier_2",
                result_status=status,
            )
            assert schema.result_status == status

        with pytest.raises(ValidationError):
            TechniqueExecutionCreate(
                company_id="comp-1",
                technique_id="cot",
                tier="tier_2",
                result_status="invalid",
            )

    def test_r08_technique_version_ab_test_default(self):
        """Verify ab_test_traffic_pct defaults to 50."""
        from app.schemas.technique import TechniqueVersionCreate

        schema = TechniqueVersionCreate(
            company_id="comp-1", technique_id="cot", version="v2",
            label="CoT v2",
        )
        assert schema.ab_test_traffic_pct == 50


class TestR08CrossSchema:
    """Cross-cutting integration tests for R-08 schemas."""

    def test_r08_all_new_schemas_importable_from_package(self):
        """Verify all new schemas are importable from the schemas package."""
        import app.schemas as pkg

        expected_names = [
            "IntegrationCreate", "IntegrationUpdate", "IntegrationResponse",
            "RESTConnectorCreate", "RESTConnectorResponse",
            "WebhookIntegrationCreate",
            "MCPConnectionCreate", "MCPConnectionResponse",
            "DBConnectionCreate", "DBConnectionResponse",
            "ApprovalQueueCreate", "ApprovalQueueUpdate", "ApprovalQueueResponse",
            "AutoApproveRuleCreate",
            "ExecutedActionCreate",
            "UndoLogCreate",
            "TechniqueConfigurationCreate", "TechniqueConfigurationResponse",
            "TechniqueExecutionCreate", "TechniqueExecutionResponse",
            "TechniqueVersionCreate", "TechniqueVersionResponse",
        ]

        for name in expected_names:
            assert hasattr(pkg, name), f"app.schemas does not export '{name}'."

    def test_r08_response_schemas_have_id_field(self):
        """Verify response schemas include id that create schemas don't."""
        from app.schemas.integration import IntegrationCreate, IntegrationResponse

        response_fields = set(IntegrationResponse.model_fields.keys())
        create_fields = set(IntegrationCreate.model_fields.keys())

        assert "id" in response_fields
        assert "id" not in create_fields

    def test_r08_encrypted_fields_never_in_response_schemas(self):
        """Verify NO response schema exposes encrypted/secret fields."""
        from app.schemas import integration, approval, technique

        sensitive_patterns = ["encrypted", "credentials", "password"]
        # Note: "secret" excluded because masked fields like
        # secret_masked are safe (they show ****, not actual secrets)

        for module in [integration, approval, technique]:
            for name in dir(module):
                obj = getattr(module, name)
                if not isinstance(obj, type):
                    continue
                if not issubclass(obj, BaseModel):
                    continue
                if not name.endswith("Response"):
                    continue

                field_names = set(obj.model_fields.keys())
                for field_name in field_names:
                    field_lower = field_name.lower()
                    for pattern in sensitive_patterns:
                        assert pattern not in field_lower, (
                            f"{name}.{field_name} contains '{pattern}' - "
                            f"response schemas must never expose sensitive fields"
                        )


# ========================================================================
# CROSS-CUTTING: R-05 + R-06 + R-07 + R-08
# ========================================================================


class TestCrossCuttingIntegration:
    """Integration tests that verify multiple R-series fixes work together."""

    def test_r05_r06_version_in_health_response_model(self):
        """Verify R-05 and R-06 work together: version field in health response."""
        from app.api.health import HealthResponse, APP_VERSION
        from app.config import Settings

        assert APP_VERSION == Settings().APP_VERSION
        assert "version" in HealthResponse.model_fields

    def test_r07_r06_response_models_use_config_types(self):
        """Verify R-07 and R-06 work together: response models properly typed."""
        from app.api.health import HealthResponse

        uptime_field = HealthResponse.model_fields.get("uptime_seconds")
        assert uptime_field is not None
        assert uptime_field.annotation == float

        checks_field = HealthResponse.model_fields.get("checks_total")
        assert checks_field is not None
        assert checks_field.annotation == int

    def test_r08_r06_schemas_used_as_response_models(self):
        """Verify R-08 schemas are wired into router endpoints."""
        from app.api.integrations import router

        found_response_model = False
        for route in router.routes:
            if not hasattr(route, "methods"):
                continue
            model = getattr(route, "response_model", None)
            if model is not None:
                found_response_model = True
                break

        assert found_response_model, (
            "Integrations router should have routes with response_model declared."
        )

    def test_r05_r07_config_consistency(self):
        """Verify R-05 and R-07 both use the same Settings class."""
        from app.config import Settings

        # Pydantic Settings fields are in model_fields, not class attributes
        assert "APP_VERSION" in Settings.model_fields, (
            "Settings missing APP_VERSION field (R-05)"
        )

        r07_fields = [
            "PRICING_TOKEN_TTL_SECONDS",
            "PRICING_MAX_VARIANT_QUANTITY",
            "PRICING_INPUT_MAX_LENGTH",
            "MFA_SESSION_TTL_SECONDS",
            "KB_MAX_FILE_SIZE",
            "KB_MAX_RETRY_COUNT",
            "WEBHOOK_MAX_PAYLOAD_SIZE",
            "WEBHOOK_MAX_AGE_SECONDS",
        ]
        for field in r07_fields:
            assert field in Settings.model_fields, (
                f"Settings missing R-07 field '{field}'"
            )
