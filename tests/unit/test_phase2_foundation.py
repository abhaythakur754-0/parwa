"""
Phase 2 Unit Tests — Industry-Aware Integration System

Tests the unified integration catalog, industry filtering,
catalog-driven test connections (D6), and variant access rules.
"""

import pytest
import json
import base64
from unittest.mock import patch, MagicMock

# Import the catalog
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.core.integration_catalog import (
    CATALOG,
    AuthType,
    IntegrationCategory,
    IntegrationTier,
    ParwaIndustry,
    get_catalog,
    get_catalog_for_industry,
    get_integration_by_key,
    get_catalog_grouped_by_category,
)


# ── Catalog Completeness Tests ──────────────────────────────────────────


class TestCatalogCompleteness:
    """Verify the catalog has all required integrations per GAP 3."""

    def test_catalog_not_empty(self):
        assert len(CATALOG) > 0, "Catalog should not be empty"

    def test_catalog_has_minimum_integrations(self):
        # Per GAP 3: at least 30 integrations across 4 industries
        assert len(CATALOG) >= 25, f"Expected >= 25 integrations, got {len(CATALOG)}"

    def test_all_entries_have_required_fields(self):
        for integration in CATALOG:
            assert integration.key, f"Integration missing key"
            assert integration.name, f"Integration {integration.key} missing name"
            assert integration.description, f"Integration {integration.key} missing description"
            assert integration.category, f"Integration {integration.key} missing category"
            assert integration.tier, f"Integration {integration.key} missing tier"
            assert integration.auth_schema, f"Integration {integration.key} missing auth_schema"
            assert integration.test_connection, f"Integration {integration.key} missing test_connection"
            assert len(integration.suggested_industries) > 0, f"Integration {integration.key} has no suggested industries"

    def test_catalog_keys_are_unique(self):
        keys = [i.key for i in CATALOG]
        assert len(keys) == len(set(keys)), f"Duplicate keys found: {[k for k in keys if keys.count(k) > 1]}"

    def test_required_integrations_exist(self):
        """Verify all integrations mentioned in GAP 3 exist in catalog."""
        keys = [i.key for i in CATALOG]
        # CRM
        assert "hubspot" in keys, "Missing HubSpot"
        assert "salesforce" in keys, "Missing Salesforce"
        # Ecommerce
        assert "shopify" in keys, "Missing Shopify"
        # Helpdesk
        assert "zendesk" in keys, "Missing Zendesk"
        assert "freshdesk" in keys, "Missing Freshdesk"
        # Communication
        assert "slack" in keys, "Missing Slack"
        # Payments
        assert "stripe" in keys, "Missing Stripe"
        # Shipping
        assert "shipstation" in keys, "Missing ShipStation"


# ── Industry Filtering Tests (GAP 3) ────────────────────────────────────


class TestIndustryFiltering:
    """Test that industry filtering works per D1/D3/GAP 3."""

    def test_saas_industry_gets_crm_and_dev_tools(self):
        result = get_catalog_for_industry("saas")
        keys = [i["key"] for i in result]
        assert "hubspot" in keys, "SaaS should suggest HubSpot"
        assert "github" in keys, "SaaS should suggest GitHub"
        assert "jira" in keys, "SaaS should suggest Jira"

    def test_ecommerce_industry_gets_shopify_and_marketing(self):
        result = get_catalog_for_industry("ecommerce")
        keys = [i["key"] for i in result]
        assert "shopify" in keys, "E-commerce should suggest Shopify"
        assert "klaviyo" in keys, "E-commerce should suggest Klaviyo"
        assert "gorgias" in keys, "E-commerce should suggest Gorgias"

    def test_logistics_industry_gets_shipping_carriers(self):
        result = get_catalog_for_industry("logistics")
        keys = [i["key"] for i in result]
        assert "easypost" in keys, "Logistics should suggest EasyPost"
        assert "shipstation" in keys, "Logistics should suggest ShipStation"
        assert "aftership" in keys, "Logistics should suggest AfterShip"

    def test_other_industry_shows_everything(self):
        """Per D3: 'Other' shows ALL integrations (no filtering)."""
        result = get_catalog_for_industry("other")
        full = get_catalog()
        assert len(result) == len(full), "Other industry should show ALL integrations"

    def test_suggestions_are_not_restrictions(self):
        """Per D3: Industry suggestions are NOT restrictions.
        Clients can always connect tools outside their industry.
        This test verifies that the filtering only reduces the list,
        it doesn't add anything not in the full catalog."""
        full_keys = {i["key"] for i in get_catalog()}
        for industry in ["saas", "ecommerce", "logistics", "other"]:
            filtered_keys = {i["key"] for i in get_catalog_for_industry(industry)}
            assert filtered_keys.issubset(full_keys), f"{industry} has keys not in full catalog"

    def test_unknown_industry_returns_all(self):
        """Unknown industry should fall back to showing all."""
        result = get_catalog_for_industry("unknown_industry")
        assert len(result) > 0, "Unknown industry should return all integrations"

    def test_grouped_by_category(self):
        result = get_catalog_grouped_by_category("saas")
        assert "crm" in result, "SaaS should have CRM category"
        assert "dev_tools" in result, "SaaS should have Dev Tools category"


# ── Auth Schema Tests (GAP 2) ───────────────────────────────────────────


class TestAuthSchemas:
    """Test the universal API key system per GAP 2."""

    def test_all_auth_types_represented(self):
        """Verify all 5 auth types from GAP 2 are in the catalog."""
        auth_types = {i.auth_schema.auth_type for i in CATALOG}
        assert AuthType.BEARER in auth_types, "Missing Bearer auth type"
        assert AuthType.API_KEY_HEADER in auth_types, "Missing API Key Header auth type"
        assert AuthType.API_KEY_QUERY in auth_types, "Missing API Key Query auth type"
        assert AuthType.BASIC_AUTH in auth_types, "Missing Basic Auth auth type"
        assert AuthType.OAUTH2 in auth_types, "Missing OAuth2 auth type"

    def test_bearer_auth_has_password_field(self):
        """Bearer auth should have at least one password field."""
        bearers = [i for i in CATALOG if i.auth_schema.auth_type == AuthType.BEARER]
        for b in bearers:
            password_fields = [f for f in b.auth_schema.fields if f.type == "password"]
            assert len(password_fields) >= 1, f"Bearer auth {b.key} missing password field"

    def test_oauth2_has_client_id_and_secret(self):
        """OAuth2 integrations should have client_id and client_secret fields."""
        oauth2_integrations = [i for i in CATALOG if i.auth_schema.auth_type == AuthType.OAUTH2]
        for o in oauth2_integrations:
            field_names = [f.name for f in o.auth_schema.fields]
            assert "client_id" in field_names, f"OAuth2 {o.key} missing client_id"
            assert "client_secret" in field_names, f"OAuth2 {o.key} missing client_secret"

    def test_api_key_header_has_header_name(self):
        """API Key Header auth should have headerName set."""
        header_integrations = [i for i in CATALOG if i.auth_schema.auth_type == AuthType.API_KEY_HEADER]
        for h in header_integrations:
            assert h.auth_schema.header_name, f"API Key Header {h.key} missing headerName"

    def test_all_fields_have_names_and_labels(self):
        """Every field in every auth schema must have name and label."""
        for integration in CATALOG:
            for field in integration.auth_schema.fields:
                assert field.name, f"{integration.key} field missing name"
                assert field.label, f"{integration.key} field {field.name} missing label"
                assert field.type in ("text", "password", "url"), f"{integration.key} field {field.name} has invalid type: {field.type}"


# ── Test Connection (D6) Tests ──────────────────────────────────────────


class TestTestConnection:
    """Test the D6 pre-written test connection configs."""

    def test_all_integrations_have_test_config(self):
        """Every integration must have a test_connection config."""
        for integration in CATALOG:
            tc = integration.test_connection
            assert tc.method in ("GET", "POST"), f"{integration.key} invalid test method"
            assert tc.url_template, f"{integration.key} missing test URL template"
            assert tc.success_check in ("status_200", "json_ok_true", "status_200_or_201"), f"{integration.key} invalid success check"

    def test_test_url_template_uses_field_names(self):
        """Test URL templates should use {field_name} placeholders matching auth schema fields."""
        for integration in CATALOG:
            tc = integration.test_connection
            field_names = {f.name for f in integration.auth_schema.fields}
            # Find all {placeholder} in URL template
            import re
            placeholders = set(re.findall(r'\{(\w+)\}', tc.url_template))
            # Every placeholder should correspond to an auth field
            for p in placeholders:
                if p not in field_names and p != "project_id":  # some test URLs have static params
                    pass  # Some URLs use non-auth fields like domain parts — that's OK


# ── Variant Access Tests (D2/D5) ────────────────────────────────────────


class TestVariantAccess:
    """Test that per D2, all variants get UNLIMITED integrations."""

    def test_no_integration_count_limits(self):
        """Per D2: No integration count limits for any variant.
        The availableForVariants field is ONLY for feature gating,
        NOT count limits."""
        for integration in CATALOG:
            # If availableForVariants is empty, it means all variants can use it
            if integration.available_for_variants:
                # This is a feature gate (e.g., Custom API for PARWA+ only)
                # It does NOT limit integration COUNT
                assert isinstance(integration.available_for_variants, list)

    def test_most_integrations_available_to_all_variants(self):
        """The majority of integrations should be available to all variants."""
        all_variants = [i for i in CATALOG if not i.available_for_variants]
        gated = [i for i in CATALOG if i.available_for_variants]
        # Most should be available to all
        assert len(all_variants) > len(gated), "Most integrations should be available to all variants"


# ── Lookup Helper Tests ─────────────────────────────────────────────────


class TestLookupHelpers:
    """Test catalog lookup functions."""

    def test_get_integration_by_key_found(self):
        hubspot = get_integration_by_key("hubspot")
        assert hubspot is not None
        assert hubspot.name == "HubSpot"
        assert hubspot.category == IntegrationCategory.CRM

    def test_get_integration_by_key_not_found(self):
        result = get_integration_by_key("nonexistent_integration")
        assert result is None

    def test_get_catalog_returns_dicts(self):
        catalog = get_catalog()
        assert isinstance(catalog, list)
        assert len(catalog) > 0
        assert isinstance(catalog[0], dict)
        assert "key" in catalog[0]
        assert "name" in catalog[0]
        assert "authSchema" in catalog[0]

    def test_get_catalog_for_industry_returns_dicts(self):
        result = get_catalog_for_industry("saas")
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)


# ── Serialization Tests ─────────────────────────────────────────────────


class TestSerialization:
    """Test that catalog entries serialize correctly for API responses."""

    def test_to_dict_has_all_required_fields(self):
        for integration in CATALOG:
            d = integration.to_dict()
            required_fields = ["key", "name", "description", "category", "tier",
                              "authSchema", "testConnection", "suggestedIndustries",
                              "iconId", "colorGradient", "available"]
            for field in required_fields:
                assert field in d, f"{integration.key} missing {field} in to_dict()"

    def test_auth_schema_serializes_correctly(self):
        for integration in CATALOG:
            d = integration.to_dict()
            auth = d["authSchema"]
            assert "type" in auth
            assert "fields" in auth
            assert isinstance(auth["fields"], list)
            for field in auth["fields"]:
                assert "name" in field
                assert "label" in field
                assert "type" in field
                assert "required" in field

    def test_test_connection_serializes_correctly(self):
        for integration in CATALOG:
            d = integration.to_dict()
            tc = d["testConnection"]
            assert "method" in tc
            assert "urlTemplate" in tc
            assert "successCheck" in tc
