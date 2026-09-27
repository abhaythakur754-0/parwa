"""
Phase 2 Integration Tests — BFF Route Verification

Level 2 integration tests that verify:
- BFF catalog route returns proper data
- BFF industry-change-impact route works
- BFF custom connector routes exist
- Backend catalog endpoints match BFF expectations
- Frontend integration-catalog mirrors backend catalog

These tests validate the wiring between:
  Frontend BFF routes (src/app/api/integrations/*)
  → Backend API (backend/app/api/integrations.py)
  → Backend catalog (backend/app/core/integration_catalog.py)

Run with:
  PYTHONPATH=/home/z/my-project/parwa:/home/z/my-project/parwa/backend \
    python -m pytest tests/integration/test_phase2_bff.py -v --noconftest
"""

import sys
import os
import json
import importlib
from typing import Any, Dict, List

import pytest


# ── Backend Catalog Verification ──────────────────────────────────────────


def _import_backend_catalog():
    """Import the backend integration catalog module."""
    # Ensure backend is on the path
    backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
    backend_path = os.path.abspath(backend_path)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    from app.core import integration_catalog
    return integration_catalog


class TestBackendIntegrationCatalog:
    """Test the backend integration_catalog module returns proper data."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.catalog_mod = _import_backend_catalog()

    def test_catalog_returns_list(self):
        """get_catalog() must return a non-empty list."""
        result = self.catalog_mod.get_catalog()
        assert isinstance(result, list), "get_catalog() should return a list"
        assert len(result) > 0, "Catalog should not be empty"

    def test_catalog_entry_has_required_fields(self):
        """Each catalog entry must have required Phase 2 fields."""
        catalog = self.catalog_mod.get_catalog()
        required_fields = [
            "key", "name", "description", "category", "tier",
            "authSchema", "testConnection", "suggestedIndustries",
            "available",
        ]
        for entry in catalog:
            for field in required_fields:
                assert field in entry, f"Entry '{entry.get('key', '?')}' missing field '{field}'"

    def test_catalog_entry_key_is_unique(self):
        """All catalog keys must be unique."""
        catalog = self.catalog_mod.get_catalog()
        keys = [e["key"] for e in catalog]
        assert len(keys) == len(set(keys)), f"Duplicate keys found: {[k for k in keys if keys.count(k) > 1]}"

    def test_catalog_has_expected_integrations(self):
        """Catalog must include key Phase 2 integrations."""
        catalog = self.catalog_mod.get_catalog()
        keys = {e["key"] for e in catalog}
        expected_keys = {
            "hubspot", "salesforce", "shopify", "zendesk",
            "slack", "gmail", "stripe", "notion",
        }
        missing = expected_keys - keys
        assert not missing, f"Missing expected integrations: {missing}"

    def test_catalog_saas_filter(self):
        """get_catalog_for_industry('saas') must return SaaS-suggested integrations."""
        result = self.catalog_mod.get_catalog_for_industry("saas")
        assert isinstance(result, list)
        keys = {e["key"] for e in result}
        # SaaS should include Slack, Zendesk, HubSpot
        assert "slack" in keys, "Slack should be suggested for SaaS"
        assert "zendesk" in keys, "Zendesk should be suggested for SaaS"
        assert "hubspot" in keys, "HubSpot should be suggested for SaaS"

    def test_catalog_ecommerce_filter(self):
        """get_catalog_for_industry('ecommerce') must return E-Commerce integrations."""
        result = self.catalog_mod.get_catalog_for_industry("ecommerce")
        assert isinstance(result, list)
        keys = {e["key"] for e in result}
        # E-Commerce should include Shopify, WooCommerce
        assert "shopify" in keys, "Shopify should be suggested for ecommerce"
        assert "woocommerce" in keys, "WooCommerce should be suggested for ecommerce"
        # SaaS-only integrations should NOT appear in ecommerce
        assert "pipedrive" not in keys, "Pipedrive is SaaS-only, not for ecommerce"

    def test_catalog_other_shows_all(self):
        """get_catalog_for_industry('other') must show ALL integrations."""
        full_catalog = self.catalog_mod.get_catalog()
        other_result = self.catalog_mod.get_catalog_for_industry("other")
        assert len(other_result) == len(full_catalog), (
            f"'other' industry should show all integrations: "
            f"got {len(other_result)}, expected {len(full_catalog)}"
        )

    def test_catalog_logistics_filter(self):
        """get_catalog_for_industry('logistics') must return logistics integrations."""
        result = self.catalog_mod.get_catalog_for_industry("logistics")
        assert isinstance(result, list)
        keys = {e["key"] for e in result}
        # Logistics should include FedEx, UPS, DHL
        assert "fedex" in keys, "FedEx should be suggested for logistics"
        assert "ups" in keys, "UPS should be suggested for logistics"
        assert "dhl" in keys, "DHL should be suggested for logistics"

    def test_saas_shows_different_than_ecommerce(self):
        """SaaS and E-Commerce must produce different integration lists (Phase 2 core feature)."""
        saas_keys = {e["key"] for e in self.catalog_mod.get_catalog_for_industry("saas")}
        ecommerce_keys = {e["key"] for e in self.catalog_mod.get_catalog_for_industry("ecommerce")}
        assert saas_keys != ecommerce_keys, (
            "SaaS and E-Commerce should have different suggested integrations"
        )
        # Some overlap is expected (e.g., Slack is in both)
        overlap = saas_keys & ecommerce_keys
        assert len(overlap) > 0, "Some integrations should overlap between SaaS and E-Commerce"
        # But there should also be unique ones
        saas_only = saas_keys - ecommerce_keys
        ecommerce_only = ecommerce_keys - saas_keys
        assert len(saas_only) > 0, "SaaS should have some unique suggestions"
        assert len(ecommerce_only) > 0, "E-Commerce should have some unique suggestions"

    def test_get_integration_by_key(self):
        """get_integration_by_key must return the correct integration."""
        result = self.catalog_mod.get_integration_by_key("shopify")
        assert result is not None, "Shopify should be found in catalog"
        assert result.key == "shopify"
        assert result.category.value == "ecommerce"

    def test_auth_schema_types(self):
        """Catalog must include all 5 auth types per GAP 2."""
        catalog = self.catalog_mod.get_catalog()
        auth_types = {e["authSchema"]["type"] for e in catalog}
        expected_types = {"bearer", "api_key_header", "api_key_query", "basic_auth", "oauth2"}
        missing = expected_types - auth_types
        assert not missing, f"Missing auth types in catalog: {missing}"

    def test_test_connection_config_present(self):
        """Every integration must have a testConnection config (D6 — NO AI)."""
        catalog = self.catalog_mod.get_catalog()
        for entry in catalog:
            tc = entry.get("testConnection")
            assert tc is not None, f"Entry '{entry['key']}' missing testConnection"
            assert "method" in tc, f"Entry '{entry['key']}' testConnection missing method"
            assert "urlTemplate" in tc, f"Entry '{entry['key']}' testConnection missing urlTemplate"
            assert "successCheck" in tc, f"Entry '{entry['key']}' testConnection missing successCheck"


class TestBackendIntegrationsRouter:
    """Test the backend integrations router structure matches BFF expectations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        backend_path = os.path.abspath(backend_path)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

    def test_industry_change_impact_schema(self):
        """IndustryChangeImpactRequest/Response schemas must exist in integrations.py."""
        from app.api.integrations import (
            IndustryChangeImpactRequest,
            IndustryChangeImpactResponse,
        )
        # Verify request schema fields
        req_fields = set(IndustryChangeImpactRequest.model_fields.keys())
        assert "new_industry" in req_fields
        assert "current_industry" in req_fields

        # Verify response schema fields
        resp_fields = set(IndustryChangeImpactResponse.model_fields.keys())
        expected_resp = {
            "new_industry", "current_industry", "connected_integrations",
            "still_recommended", "no_longer_suggested", "newly_suggested",
            "message",
        }
        assert expected_resp.issubset(resp_fields), f"Missing response fields: {expected_resp - resp_fields}"

    def test_create_integration_schema(self):
        """CreateIntegrationRequest must accept integration_type, name, config."""
        from app.api.integrations import CreateIntegrationRequest
        fields = set(CreateIntegrationRequest.model_fields.keys())
        assert "integration_type" in fields
        assert "name" in fields
        assert "config" in fields

    def test_custom_connector_endpoints_exist(self):
        """Backend must have custom connector routes registered."""
        from app.api.integrations import router
        # Router has prefix="/api/integrations" so paths include the prefix
        routes = [(r.path, r.methods) for r in router.routes if hasattr(r, 'methods')]
        paths = [r[0] for r in routes]

        # Check with the prefix since the router defines prefix="/api/integrations"
        assert "/api/integrations/catalog" in paths, "Missing /catalog endpoint"
        assert "/api/integrations/available" in paths, "Missing /available endpoint"
        assert "/api/integrations/industry-change-impact" in paths, "Missing /industry-change-impact endpoint"
        assert "/api/integrations/custom/connector" in paths, "Missing /custom/connector endpoint"
        assert "/api/integrations/custom/connectors" in paths, "Missing /custom/connectors endpoint"
        assert "/api/integrations/openapi-import" in paths, "Missing /openapi-import endpoint"
        assert "/api/integrations/openapi-import/save" in paths, "Missing /openapi-import/save endpoint"


class TestBFFRouteFiles:
    """Verify BFF route files exist and import the correct backend URL helper."""

    def test_bff_catalog_route_exists(self):
        """BFF catalog route file must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "api", "integrations", "catalog", "route.ts"
        )
        assert os.path.exists(path), f"BFF catalog route missing at {path}"

    def test_bff_industry_change_impact_route_exists(self):
        """BFF industry-change-impact route file must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "api", "integrations", "industry-change-impact", "route.ts"
        )
        assert os.path.exists(path), f"BFF industry-change-impact route missing at {path}"

    def test_bff_custom_connector_route_exists(self):
        """BFF custom connector catch-all route must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "api", "integrations", "custom", "[...path]", "route.ts"
        )
        assert os.path.exists(path), f"BFF custom connector route missing at {path}"

    def test_bff_integrations_base_route_exists(self):
        """BFF integrations base route must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "api", "integrations", "route.ts"
        )
        assert os.path.exists(path), f"BFF integrations base route missing at {path}"

    def test_bff_available_route_exists(self):
        """BFF integrations/available route must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "api", "integrations", "available", "route.ts"
        )
        assert os.path.exists(path), f"BFF available route missing at {path}"

    def test_bff_id_route_exists(self):
        """BFF integrations/[id] route must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "api", "integrations", "[id]", "route.ts"
        )
        assert os.path.exists(path), f"BFF [id] route missing at {path}"

    def test_bff_routes_import_backend_url(self):
        """All BFF route files must import getBackendUrl."""
        bff_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "api", "integrations"
        )
        route_files = []
        for root, dirs, files in os.walk(bff_dir):
            for f in files:
                if f == "route.ts":
                    route_files.append(os.path.join(root, f))

        for rf in route_files:
            with open(rf, "r") as fh:
                content = fh.read()
            assert "getBackendUrl" in content, (
                f"BFF route {rf} does not import getBackendUrl"
            )
            assert "/api/integrations" in content, (
                f"BFF route {rf} does not proxy to /api/integrations"
            )


class TestFrontendAPIClient:
    """Verify the frontend API client has all Phase 2 integration methods."""

    def test_integrations_api_has_catalog(self):
        """integrationsApi must have getCatalog method."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "api.ts"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "getCatalog" in content, "Missing integrationsApi.getCatalog"

    def test_integrations_api_has_industry_change_impact(self):
        """integrationsApi must have industryChangeImpact method."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "api.ts"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "industryChangeImpact" in content, "Missing integrationsApi.industryChangeImpact"

    def test_integrations_api_has_custom_connector_methods(self):
        """integrationsApi must have custom connector CRUD methods."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "api.ts"
        )
        with open(path, "r") as f:
            content = f.read()
        expected_methods = [
            "createCustomConnector",
            "listCustomConnectors",
            "getCustomConnector",
            "updateCustomConnector",
            "deleteCustomConnector",
            "testCustomConnector",
        ]
        for method in expected_methods:
            assert method in content, f"Missing integrationsApi.{method}"

    def test_integrations_api_has_openapi_import(self):
        """integrationsApi must have importOpenAPI and saveOpenAPIImport methods."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "api.ts"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "importOpenAPI" in content, "Missing integrationsApi.importOpenAPI"
        assert "saveOpenAPIImport" in content, "Missing integrationsApi.saveOpenAPIImport"


class TestFrontendIntegrationCatalog:
    """Verify the frontend integration catalog mirrors the backend."""

    def test_catalog_file_exists(self):
        """Frontend integration-catalog.ts must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "integration-catalog.ts"
        )
        assert os.path.exists(path), f"Frontend catalog missing at {path}"

    def test_catalog_has_industry_filtering(self):
        """Frontend catalog must have getIntegrationsForIndustry function."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "integration-catalog.ts"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "getIntegrationsForIndustry" in content, "Missing getIntegrationsForIndustry"
        assert "mapIndustryToParwaIndustry" in content, "Missing mapIndustryToParwaIndustry"

    def test_catalog_has_all_key_integrations(self):
        """Frontend catalog must list all key integrations from backend."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "integration-catalog.ts"
        )
        with open(path, "r") as f:
            content = f.read()

        expected_keys = [
            "hubspot", "salesforce", "shopify", "woocommerce",
            "zendesk", "slack", "gmail", "stripe", "notion",
            "fedex", "ups", "dhl", "github", "jira",
        ]
        for key in expected_keys:
            assert f"key: '{key}'" in content, f"Frontend catalog missing integration: {key}"

    def test_catalog_has_parwa_industry_enum(self):
        """Frontend must define ParwaIndustry = saas | ecommerce | logistics | other."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "lib", "integration-catalog.ts"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "'saas'" in content or '"saas"' in content, "Missing saas industry"
        assert "'ecommerce'" in content or '"ecommerce"' in content, "Missing ecommerce industry"
        assert "'logistics'" in content or '"logistics"' in content, "Missing logistics industry"


class TestFrontendComponents:
    """Verify Phase 2 frontend components exist and use correct APIs."""

    def test_integration_step_exists(self):
        """IntegrationStep component must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "components", "onboarding", "IntegrationStep.tsx"
        )
        assert os.path.exists(path), f"IntegrationStep component missing at {path}"

    def test_integration_step_uses_catalog(self):
        """IntegrationStep must import from integration-catalog."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "components", "onboarding", "IntegrationStep.tsx"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "integration-catalog" in content, "IntegrationStep must import from integration-catalog"
        assert "getIntegrationsForIndustry" in content, "IntegrationStep must use getIntegrationsForIndustry"

    def test_integration_step_has_industry_prop(self):
        """IntegrationStep must accept an industry prop."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "components", "onboarding", "IntegrationStep.tsx"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "industry?" in content, "IntegrationStep must accept industry prop"

    def test_custom_connector_form_exists(self):
        """CustomConnectorForm component must exist."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "components", "onboarding", "CustomConnectorForm.tsx"
        )
        assert os.path.exists(path), f"CustomConnectorForm component missing at {path}"

    def test_custom_connector_form_uses_api(self):
        """CustomConnectorForm must use integrationsApi."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "components", "onboarding", "CustomConnectorForm.tsx"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "integrationsApi" in content, "CustomConnectorForm must use integrationsApi"
        assert "createCustomConnector" in content or "importOpenAPI" in content, (
            "CustomConnectorForm must call createCustomConnector or importOpenAPI"
        )

    def test_settings_page_has_plan_industry_tab(self):
        """Settings page must have 'Plan & Industry' tab."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "app", "dashboard", "settings", "page.tsx"
        )
        with open(path, "r") as f:
            content = f.read()
        assert 'plan-industry' in content, "Settings page must have plan-industry tab"
        assert 'Plan & Industry' in content, "Settings page must display 'Plan & Industry' label"

    def test_onboarding_wizard_passes_industry(self):
        """OnboardingWizard must pass industry to IntegrationStep."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "src", "components", "onboarding", "OnboardingWizard.tsx"
        )
        with open(path, "r") as f:
            content = f.read()
        assert "IntegrationStep" in content, "OnboardingWizard must use IntegrationStep"
        assert "industry" in content, "OnboardingWizard must reference industry"
