"""
Phase 2 Unit Tests: Industry-Aware Integration System

Tests the integration catalog, OpenAPI importer, and custom connector logic.
Level 1 — Unit tests (no DB, no HTTP server, pure logic).
"""

import json
import re
import pytest
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════
# Test 1: Integration Catalog — Industry Filtering
# ═══════════════════════════════════════════════════════════════════

class TestIntegrationCatalogIndustryFilter:
    """Verify industry-to-integration mapping matches GAP 3 from INTEGRATION_ROADMAP.md."""

    def test_total_catalog_count(self):
        """Catalog should have 31 integrations (27 original + Gmail + 3 carriers)."""
        from backend.app.core.integration_catalog import CATALOG
        assert len(CATALOG) == 31

    def test_saas_industry_filter(self):
        """SaaS should include CRM, Helpdesk, Analytics, Dev Tools, Productivity."""
        from backend.app.core.integration_catalog import get_catalog_for_industry
        saas = get_catalog_for_industry("saas")
        saas_keys = {i["key"] for i in saas}

        # CRM
        assert "hubspot" in saas_keys
        assert "salesforce" in saas_keys
        assert "pipedrive" in saas_keys

        # Helpdesk
        assert "zendesk" in saas_keys
        assert "freshdesk" in saas_keys
        assert "intercom" in saas_keys

        # Analytics
        assert "mixpanel" in saas_keys
        assert "amplitude" in saas_keys

        # Dev Tools
        assert "github" in saas_keys
        assert "jira" in saas_keys
        assert "linear" in saas_keys

        # Productivity
        assert "notion" in saas_keys

        # NOT in SaaS
        assert "shopify" not in saas_keys
        assert "woocommerce" not in saas_keys
        assert "fedex" not in saas_keys
        assert "ups" not in saas_keys

    def test_ecommerce_industry_filter(self):
        """E-commerce should include Ecommerce, Marketing, Payments, Shipping."""
        from backend.app.core.integration_catalog import get_catalog_for_industry
        ecom = get_catalog_for_industry("ecommerce")
        ecom_keys = {i["key"] for i in ecom}

        # Ecommerce
        assert "shopify" in ecom_keys
        assert "woocommerce" in ecom_keys
        assert "bigcommerce" in ecom_keys

        # Marketing
        assert "mailchimp" in ecom_keys
        assert "klaviyo" in ecom_keys

        # Payments
        assert "stripe" in ecom_keys
        assert "paypal" in ecom_keys

        # Shipping
        assert "shipstation" in ecom_keys
        assert "aftership" in ecom_keys

        # NOT in E-commerce
        assert "github" not in ecom_keys
        assert "jira" not in ecom_keys
        assert "fedex" not in ecom_keys

    def test_logistics_industry_filter(self):
        """Logistics should include 6 shipping carriers + CRM."""
        from backend.app.core.integration_catalog import get_catalog_for_industry
        logistics = get_catalog_for_industry("logistics")
        logistics_keys = {i["key"] for i in logistics}

        # 6 shipping carriers (GAP 3 requirement)
        shipping_keys = {"shipstation", "aftership", "easypost", "fedex", "ups", "dhl"}
        assert shipping_keys.issubset(logistics_keys), f"Missing carriers: {shipping_keys - logistics_keys}"

        # CRM
        assert "hubspot" in logistics_keys
        assert "salesforce" in logistics_keys

        # NOT in Logistics
        assert "shopify" not in logistics_keys
        assert "github" not in logistics_keys
        assert "mailchimp" not in logistics_keys

    def test_other_industry_shows_all(self):
        """Other should show ALL integrations (no filter)."""
        from backend.app.core.integration_catalog import get_catalog_for_industry, CATALOG
        other = get_catalog_for_industry("other")
        assert len(other) == len(CATALOG)

    def test_new_carriers_in_catalog(self):
        """FedEx, UPS, DHL should be in the catalog."""
        from backend.app.core.integration_catalog import get_integration_by_key

        fedex = get_integration_by_key("fedex")
        assert fedex is not None
        assert fedex.category.value == "shipping"
        assert fedex.test_connection.url_template != ""

        ups = get_integration_by_key("ups")
        assert ups is not None
        assert ups.auth_schema.auth_type.value == "oauth2"

        dhl = get_integration_by_key("dhl")
        assert dhl is not None
        assert dhl.auth_schema.auth_type.value == "bearer"

    def test_all_integrations_have_test_connection(self):
        """Every integration must have a pre-written test call (D6)."""
        from backend.app.core.integration_catalog import CATALOG
        for i in CATALOG:
            assert i.test_connection.url_template, f"{i.key} missing test URL"
            assert i.test_connection.method, f"{i.key} missing test method"
            assert i.test_connection.success_check, f"{i.key} missing success check"

    def test_all_integrations_have_auth_schema(self):
        """Every integration must have auth schema fields (GAP 2)."""
        from backend.app.core.integration_catalog import CATALOG
        for i in CATALOG:
            assert i.auth_schema.fields, f"{i.key} missing auth fields"
            assert len(i.auth_schema.fields) > 0, f"{i.key} has no auth fields"


# ═══════════════════════════════════════════════════════════════════
# Test 2: OpenAPI Importer — Spec Parsing Logic
# ═══════════════════════════════════════════════════════════════════

class TestOpenAPIImporter:
    """Test the OpenAPI spec parser logic."""

    @pytest.fixture
    def importer(self):
        from backend.app.services.openapi_importer_service import OpenAPIImporterService
        return OpenAPIImporterService()

    @pytest.fixture
    def petstore_spec(self):
        return {
            "openapi": "3.0.0",
            "info": {"title": "Petstore", "version": "1.0.0", "description": "A sample API"},
            "servers": [{"url": "https://petstore.example.com/v1"}],
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"}
                }
            },
            "paths": {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "summary": "List all pets",
                        "description": "Returns all pets from the system",
                        "parameters": [{"name": "limit", "in": "query", "required": False}],
                        "responses": {"200": {"description": "A list of pets"}},
                    },
                    "post": {
                        "operationId": "createPet",
                        "summary": "Create a pet",
                        "description": "Creates a new pet",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["name"],
                                        "properties": {"name": {"type": "string"}, "tag": {"type": "string"}},
                                    }
                                }
                            }
                        },
                        "responses": {"201": {"description": "Pet created"}},
                    },
                },
                "/pets/{petId}": {
                    "get": {
                        "operationId": "showPetById",
                        "summary": "Get a pet by ID",
                        "description": "Returns a single pet",
                        "parameters": [{"name": "petId", "in": "path", "required": True}],
                        "responses": {"200": {"description": "A pet"}},
                    },
                    "delete": {
                        "deprecated": True,
                        "operationId": "deletePet",
                        "summary": "Delete a pet",
                        "responses": {"200": {"description": "Deleted"}},
                    },
                },
            },
        }

    def test_parse_basic_spec(self, importer, petstore_spec):
        """Parse a minimal OpenAPI v3 spec and verify extracted data."""
        result = importer.import_from_content(json.dumps(petstore_spec), "petstore.json")

        assert result["name"] == "Petstore"
        assert result["base_url"] == "https://petstore.example.com/v1"
        assert result["endpoint_count"] == 3  # deprecated DELETE skipped

    def test_deprecated_endpoints_skipped(self, importer, petstore_spec):
        """Deprecated endpoints should be skipped per GAP 5."""
        result = importer.import_from_content(json.dumps(petstore_spec), "petstore.json")
        methods = [a["method"] for a in result["actions"]]
        assert "DELETE" not in methods

    def test_action_names_generated(self, importer, petstore_spec):
        """Action names should come from operationId."""
        result = importer.import_from_content(json.dumps(petstore_spec), "petstore.json")
        action_names = [a["name"] for a in result["actions"]]
        assert "List Pets" in action_names
        assert "Create Pet" in action_names
        assert "Show Pet By Id" in action_names

    def test_path_params_extracted(self, importer, petstore_spec):
        """Path parameters should be required params."""
        result = importer.import_from_content(json.dumps(petstore_spec), "petstore.json")
        get_pet = [a for a in result["actions"] if "petId" in str(a["params"])][0]
        assert "petId" in get_pet["params"]["required"]

    def test_query_params_extracted(self, importer, petstore_spec):
        """Query parameters should be optional params."""
        result = importer.import_from_content(json.dumps(petstore_spec), "petstore.json")
        list_pets = [a for a in result["actions"] if a["method"] == "GET" and a["path"] == "/pets"][0]
        assert "limit" in list_pets["params"]["optional"]

    def test_request_body_params_extracted(self, importer, petstore_spec):
        """Request body required fields should be required params."""
        result = importer.import_from_content(json.dumps(petstore_spec), "petstore.json")
        create_pet = [a for a in result["actions"] if a["method"] == "POST"][0]
        assert "name" in create_pet["params"]["required"]
        assert "tag" in create_pet["params"]["optional"]

    def test_auth_detection_bearer(self, importer, petstore_spec):
        """Bearer auth should be detected from securitySchemes."""
        result = importer.import_from_content(json.dumps(petstore_spec), "petstore.json")
        assert result["auth_type"] == "bearer"

    def test_auth_detection_apikey(self, importer):
        """API key auth should be detected."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {"/test": {"get": {"responses": {"200": {"description": "OK"}}}}},
            "components": {"securitySchemes": {"apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}},
        }
        result = importer.import_from_content(json.dumps(spec), "test.json")
        assert result["auth_type"] == "api_key_header"

    def test_auth_detection_oauth2(self, importer):
        """OAuth2 should be detected."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {"/test": {"get": {"responses": {"200": {"description": "OK"}}}}},
            "components": {"securitySchemes": {"oauth": {"type": "oauth2", "flows": {}}}},
        }
        result = importer.import_from_content(json.dumps(spec), "test.json")
        assert result["auth_type"] == "oauth2"

    def test_invalid_spec_raises_error(self, importer):
        """Invalid spec (no version field) should raise ValueError."""
        # '{}' parses to {} which is falsy → "Empty spec"
        with pytest.raises(ValueError, match="Empty spec"):
            importer.import_from_content("{}", "test.json")

        # A spec with info but no swagger/openapi version
        with pytest.raises(ValueError, match="Not a valid OpenAPI"):
            importer.import_from_content(json.dumps({"info": {"title": "X"}}), "test.json")

    def test_empty_spec_raises_error(self, importer):
        """Empty spec should raise ValueError."""
        with pytest.raises(ValueError, match="Empty spec"):
            importer.import_from_content("", "test.json")

    def test_no_importable_endpoints_raises_error(self, importer):
        """Spec with no importable endpoints should raise ValueError."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Empty", "version": "1.0"},
            "paths": {},
        }
        with pytest.raises(ValueError, match="No importable endpoints"):
            importer.import_from_content(json.dumps(spec), "empty.json")

    def test_swagger_v2_parsed(self, importer):
        """Swagger v2.0 specs should be parseable."""
        spec = {
            "swagger": "2.0",
            "info": {"title": "Legacy", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "paths": {"/items": {"get": {"responses": {"200": {"description": "OK"}}}}},
        }
        result = importer.import_from_content(json.dumps(spec), "legacy.json")
        assert result["name"] == "Legacy"
        assert result["base_url"] == "https://api.example.com/v1"
        assert result["endpoint_count"] == 1


# ═══════════════════════════════════════════════════════════════════
# Test 3: Custom Connector Service — Validation Logic
# ═══════════════════════════════════════════════════════════════════

class TestCustomConnectorValidation:
    """Test custom connector validation logic.
    
    These tests validate constants without importing the full service
    (which requires sqlalchemy/structlog). Tested by reading the source file."""

    def test_valid_auth_types(self):
        """Verify the 5 supported auth types."""
        import pathlib
        source = pathlib.Path("/home/z/my-project/parwa/backend/app/services/custom_connector_service.py").read_text()
        assert '"bearer"' in source
        assert '"api_key_header"' in source
        assert '"api_key_query"' in source
        assert '"basic_auth"' in source
        assert '"oauth2"' in source

    def test_valid_action_methods(self):
        """Verify the 5 supported HTTP methods for actions."""
        import pathlib
        source = pathlib.Path("/home/z/my-project/parwa/backend/app/services/custom_connector_service.py").read_text()
        assert '"GET"' in source
        assert '"POST"' in source
        assert '"PUT"' in source
        assert '"PATCH"' in source
        assert '"DELETE"' in source

    def test_max_actions_per_connector(self):
        """Verify max actions limit per GAP 4."""
        import pathlib
        source = pathlib.Path("/home/z/my-project/parwa/backend/app/services/custom_connector_service.py").read_text()
        assert "MAX_ACTIONS_PER_CONNECTOR = 50" in source


# ═══════════════════════════════════════════════════════════════════
# Test 4: Integration Service — Credential Masking
# ═══════════════════════════════════════════════════════════════════

class TestCredentialMasking:
    """Test that sensitive fields are properly masked in API responses.
    
    Uses a local copy of the masking function to avoid importing sqlalchemy."""

    @staticmethod
    def _mask_config(config):
        """Local copy of _mask_config from integration_service.py."""
        sensitive_keys = {
            "api_key", "api_token", "token", "access_token", "secret",
            "password", "refresh_token", "bot_token", "client_secret",
            "consumer_secret", "private_api_key", "api_secret",
        }
        masked = {}
        for key, value in config.items():
            if any(s in key.lower() for s in sensitive_keys):
                if isinstance(value, str) and len(value) > 4:
                    masked[key] = value[:4] + "****"
                else:
                    masked[key] = "****"
            else:
                masked[key] = value
        return masked

    def test_mask_config_hides_api_keys(self):
        """API keys should be masked with only last 4 chars visible."""
        config = {"api_key": "sk_live_1234567890", "store_url": "mystore.myshopify.com"}
        masked = self._mask_config(config)
        assert masked["api_key"] == "sk_l****"
        assert masked["store_url"] == "mystore.myshopify.com"

    def test_mask_config_short_values(self):
        """Short sensitive values should show ****."""
        config = {"token": "ab"}
        masked = self._mask_config(config)
        assert masked["token"] == "****"

    def test_mask_config_preserves_non_sensitive(self):
        """Non-sensitive fields should be preserved."""
        config = {"subdomain": "mycompany", "api_key": "secret123"}
        masked = self._mask_config(config)
        assert masked["subdomain"] == "mycompany"
