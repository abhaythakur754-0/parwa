"""
PARWA Integration Catalog — Backend Mirror

Single source of truth for the backend. Mirrors the frontend catalog
in src/lib/integration-catalog.ts. When adding an integration, update
BOTH files.

Per D2: All variants get UNLIMITED integrations.
Per D4: Three tiers — Pre-built (Tier 1), OpenAPI Import (Tier 2), Custom REST (Tier 3).
Per D6: Pre-written HTTP test calls — NO AI tokens spent.
Per GAP 2: Universal API key system with 5 auth types.
Per GAP 3: Full catalog per industry (suggestions, not restrictions).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ────────────────────────────────────────────────────────────────


class AuthType(str, Enum):
    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    API_KEY_QUERY = "api_key_query"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"


class IntegrationCategory(str, Enum):
    CRM = "crm"
    ECOMMERCE = "ecommerce"
    HELPDESK = "helpdesk"
    COMMUNICATION = "communication"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    PAYMENTS = "payments"
    SHIPPING = "shipping"
    DEV_TOOLS = "dev_tools"
    PRODUCTIVITY = "productivity"
    CUSTOM = "custom"


class IntegrationTier(str, Enum):
    TIER1_PREBUILT = "tier1_prebuilt"
    TIER2_OPENAPI = "tier2_openapi"
    TIER3_CUSTOM = "tier3_custom"


class ParwaIndustry(str, Enum):
    SAAS = "saas"
    ECOMMERCE = "ecommerce"
    LOGISTICS = "logistics"
    OTHER = "other"


# ── Data Classes ─────────────────────────────────────────────────────────


class AuthField:
    """A single field in an auth schema."""

    def __init__(self, name: str, label: str, type: str = "text",
                 required: bool = True, placeholder: str = ""):
        self.name = name
        self.label = label
        self.type = type
        self.required = required
        self.placeholder = placeholder

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "placeholder": self.placeholder,
        }


class AuthSchema:
    """Defines how an integration authenticates."""

    def __init__(self, auth_type: AuthType, fields: List[AuthField],
                 header_name: str = "", query_param_name: str = "",
                 redirect_uri: str = ""):
        self.auth_type = auth_type
        self.fields = fields
        self.header_name = header_name
        self.query_param_name = query_param_name
        self.redirect_uri = redirect_uri

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": self.auth_type.value,
            "fields": [f.to_dict() for f in self.fields],
        }
        if self.header_name:
            d["headerName"] = self.header_name
        if self.query_param_name:
            d["queryParamName"] = self.query_param_name
        if self.redirect_uri:
            d["redirectUri"] = self.redirect_uri
        return d


class TestConnectionConfig:
    """Pre-written HTTP test call per D6 — NO AI."""

    def __init__(self, method: str, url_template: str,
                 headers_template: Optional[Dict[str, str]] = None,
                 success_check: str = "status_200",
                 success_message: str = "Connected"):
        self.method = method.upper()
        self.url_template = url_template
        self.headers_template = headers_template or {}
        self.success_check = success_check
        self.success_message = success_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "urlTemplate": self.url_template,
            "headersTemplate": self.headers_template,
            "successCheck": self.success_check,
            "successMessage": self.success_message,
        }


class IntegrationDefinition:
    """Complete definition of an integration in the catalog."""

    def __init__(
        self,
        key: str,
        name: str,
        description: str,
        category: IntegrationCategory,
        tier: IntegrationTier,
        auth_schema: AuthSchema,
        test_connection: TestConnectionConfig,
        suggested_industries: List[ParwaIndustry],
        icon_id: str = "",
        color_gradient: str = "",
        available: bool = True,
        available_for_variants: Optional[List[str]] = None,
    ):
        self.key = key
        self.name = name
        self.description = description
        self.category = category
        self.tier = tier
        self.auth_schema = auth_schema
        self.test_connection = test_connection
        self.suggested_industries = suggested_industries
        self.icon_id = icon_id
        self.color_gradient = color_gradient
        self.available = available
        self.available_for_variants = available_for_variants or []

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "tier": self.tier.value,
            "authSchema": self.auth_schema.to_dict(),
            "testConnection": self.test_connection.to_dict(),
            "suggestedIndustries": [i.value for i in self.suggested_industries],
            "iconId": self.icon_id,
            "colorGradient": self.color_gradient,
            "available": self.available,
        }
        if self.available_for_variants:
            d["availableForVariants"] = self.available_for_variants
        return d


# ── The Unified Catalog ──────────────────────────────────────────────────

CATALOG: List[IntegrationDefinition] = [
    # CRM
    IntegrationDefinition(
        key="hubspot", name="HubSpot",
        description="Look up customers, deals, and contact info from HubSpot CRM.",
        category=IntegrationCategory.CRM, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "HubSpot API Key", "password", True, "pat-xxx-xxx")]),
        test_connection=TestConnectionConfig("GET", "https://api.hubapi.com/crm/v3/contacts?limit=1", {"Authorization": "Bearer {api_key}"}, "status_200", "Connected to HubSpot CRM"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.ECOMMERCE, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="hubspot", color_gradient="from-orange-500 to-orange-400",
    ),
    IntegrationDefinition(
        key="salesforce", name="Salesforce",
        description="Access customer records, opportunities, and cases from Salesforce.",
        category=IntegrationCategory.CRM, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.OAUTH2, [
            AuthField("client_id", "Consumer Key", "text", True, "3MVG9..."),
            AuthField("client_secret", "Consumer Secret", "password", True),
            AuthField("instance_url", "Instance URL", "url", True, "https://na1.salesforce.com"),
            AuthField("refresh_token", "Refresh Token", "password", True),
        ]),
        test_connection=TestConnectionConfig("GET", "{instance_url}/services/data/v60.0/", {"Authorization": "Bearer {refresh_token}"}, "status_200", "Connected to Salesforce"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="salesforce", color_gradient="from-blue-500 to-blue-400",
    ),
    IntegrationDefinition(
        key="pipedrive", name="Pipedrive",
        description="Manage deals, contacts, and pipelines from Pipedrive CRM.",
        category=IntegrationCategory.CRM, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.API_KEY_QUERY, [
            AuthField("api_token", "API Token", "password", True, "xxx123abc"),
            AuthField("company_domain", "Company Domain", "text", True, "yourcompany"),
        ], query_param_name="api_token"),
        test_connection=TestConnectionConfig("GET", "https://{company_domain}.pipedrive.com/api/v1/users/me?api_token={api_token}", success_check="json_ok_true", success_message="Connected to Pipedrive"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        icon_id="pipedrive", color_gradient="from-green-500 to-green-400",
    ),
    # ECOMMERCE
    IntegrationDefinition(
        key="shopify", name="Shopify",
        description="Look up orders, products, and inventory from your Shopify store.",
        category=IntegrationCategory.ECOMMERCE, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.API_KEY_HEADER, [
            AuthField("store_url", "Store URL", "url", True, "your-store.myshopify.com"),
            AuthField("access_token", "Access Token", "password", True, "shpat_xxx"),
        ], header_name="X-Shopify-Access-Token"),
        test_connection=TestConnectionConfig("GET", "https://{store_url}/admin/api/2024-01/shop.json", {"X-Shopify-Access-Token": "{access_token}"}, "status_200", "Connected to Shopify store"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="shopify", color_gradient="from-green-500 to-emerald-400",
    ),
    IntegrationDefinition(
        key="woocommerce", name="WooCommerce",
        description="Access orders, products, and customers from your WooCommerce store.",
        category=IntegrationCategory.ECOMMERCE, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BASIC_AUTH, [
            AuthField("store_url", "Store URL", "url", True, "https://yourstore.com"),
            AuthField("consumer_key", "Consumer Key", "text", True, "ck_xxx"),
            AuthField("consumer_secret", "Consumer Secret", "password", True, "cs_xxx"),
        ]),
        test_connection=TestConnectionConfig("GET", "{store_url}/wp-json/wc/v3/system_status", success_check="status_200", success_message="Connected to WooCommerce"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="woocommerce", color_gradient="from-purple-500 to-purple-400",
    ),
    IntegrationDefinition(
        key="bigcommerce", name="BigCommerce",
        description="Manage products, orders, and customers from your BigCommerce store.",
        category=IntegrationCategory.ECOMMERCE, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.API_KEY_HEADER, [
            AuthField("store_hash", "Store Hash", "text", True, "abc123"),
            AuthField("access_token", "Access Token", "password", True, "xxx"),
        ], header_name="X-Auth-Token"),
        test_connection=TestConnectionConfig("GET", "https://api.bigcommerce.com/stores/{store_hash}/v2/store", {"X-Auth-Token": "{access_token}", "Accept": "application/json"}, "status_200", "Connected to BigCommerce"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="bigcommerce", color_gradient="from-indigo-500 to-indigo-400",
    ),
    # HELPDESK
    IntegrationDefinition(
        key="zendesk", name="Zendesk",
        description="Manage tickets, contacts, and knowledge base from Zendesk.",
        category=IntegrationCategory.HELPDESK, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BASIC_AUTH, [
            AuthField("subdomain", "Subdomain", "text", True, "your-company"),
            AuthField("email", "Email", "text", True, "admin@company.com"),
            AuthField("api_token", "API Token", "password", True, "zendesk_api_token"),
        ]),
        test_connection=TestConnectionConfig("GET", "https://{subdomain}.zendesk.com/api/v2/users/me.json", success_check="status_200", success_message="Connected to Zendesk"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.ECOMMERCE, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="zendesk", color_gradient="from-green-500 to-green-400",
    ),
    IntegrationDefinition(
        key="freshdesk", name="Freshdesk",
        description="Access tickets, contacts, and solutions from Freshdesk.",
        category=IntegrationCategory.HELPDESK, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BASIC_AUTH, [
            AuthField("domain", "Domain", "text", True, "yourcompany"),
            AuthField("api_key", "API Key", "password", True, "freshdesk_api_key"),
        ]),
        test_connection=TestConnectionConfig("GET", "https://{domain}.freshdesk.com/api/v2/agents/me", success_check="status_200", success_message="Connected to Freshdesk"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="freshdesk", color_gradient="from-blue-500 to-blue-400",
    ),
    IntegrationDefinition(
        key="intercom", name="Intercom",
        description="Access conversations, contacts, and help center from Intercom.",
        category=IntegrationCategory.HELPDESK, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("access_token", "Access Token", "password", True, "dG9rZW4...")]),
        test_connection=TestConnectionConfig("GET", "https://api.intercom.io/me", {"Authorization": "Bearer {access_token}", "Accept": "application/json"}, "status_200", "Connected to Intercom"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        icon_id="intercom", color_gradient="from-blue-600 to-blue-500",
    ),
    IntegrationDefinition(
        key="gorgias", name="Gorgias",
        description="Manage e-commerce support tickets from Gorgias.",
        category=IntegrationCategory.HELPDESK, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BASIC_AUTH, [
            AuthField("domain", "Domain", "text", True, "yourcompany"),
            AuthField("email", "Email", "text", True, "admin@company.com"),
            AuthField("api_key", "API Key", "password", True),
        ]),
        test_connection=TestConnectionConfig("GET", "https://{domain}.gorgias.com/api/users/me", success_check="status_200", success_message="Connected to Gorgias"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="gorgias", color_gradient="from-teal-500 to-teal-400",
    ),
    # COMMUNICATION
    IntegrationDefinition(
        key="slack", name="Slack",
        description="Receive alerts, manage tickets, and respond from Slack.",
        category=IntegrationCategory.COMMUNICATION, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("bot_token", "Bot Token", "password", True, "xoxb-xxx")]),
        test_connection=TestConnectionConfig("POST", "https://slack.com/api/auth.test", {"Authorization": "Bearer {bot_token}"}, "json_ok_true", "Connected to Slack workspace"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.ECOMMERCE, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="slack", color_gradient="from-purple-500 to-purple-400",
    ),
    IntegrationDefinition(
        key="gmail", name="Gmail",
        description="Sync email conversations and auto-respond via AI.",
        category=IntegrationCategory.COMMUNICATION, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.OAUTH2, [
            AuthField("client_id", "Client ID", "text", True, "xxx.apps.googleusercontent.com"),
            AuthField("client_secret", "Client Secret", "password", True),
            AuthField("refresh_token", "Refresh Token", "password", True),
        ]),
        test_connection=TestConnectionConfig("GET", "https://www.googleapis.com/gmail/v1/users/me/profile", {"Authorization": "Bearer {refresh_token}"}, "status_200", "Connected to Gmail"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.ECOMMERCE, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="gmail", color_gradient="from-red-500 to-red-400",
    ),
    # ANALYTICS
    IntegrationDefinition(
        key="mixpanel", name="Mixpanel",
        description="Query user events and analytics data from Mixpanel.",
        category=IntegrationCategory.ANALYTICS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BASIC_AUTH, [AuthField("api_secret", "API Secret", "password", True)]),
        test_connection=TestConnectionConfig("GET", "https://mixpanel.com/api/2.0/engage?project_id=0", success_check="status_200_or_201", success_message="Connected to Mixpanel"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        icon_id="mixpanel", color_gradient="from-blue-500 to-indigo-400",
    ),
    IntegrationDefinition(
        key="amplitude", name="Amplitude",
        description="Access product analytics and user behavior data from Amplitude.",
        category=IntegrationCategory.ANALYTICS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.API_KEY_HEADER, [
            AuthField("api_key", "API Key", "text", True),
            AuthField("secret_key", "Secret Key", "password", True),
        ], header_name="Authorization"),
        test_connection=TestConnectionConfig("GET", "https://amplitude.com/api/2/usersearch?user=test", success_check="status_200", success_message="Connected to Amplitude"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        icon_id="amplitude", color_gradient="from-blue-600 to-blue-500",
    ),
    IntegrationDefinition(
        key="google_analytics", name="Google Analytics",
        description="Access traffic, conversion, and user data from Google Analytics.",
        category=IntegrationCategory.ANALYTICS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.OAUTH2, [
            AuthField("client_id", "Client ID", "text", True),
            AuthField("client_secret", "Client Secret", "password", True),
            AuthField("refresh_token", "Refresh Token", "password", True),
        ]),
        test_connection=TestConnectionConfig("GET", "https://analyticsreporting.googleapis.com/v4/userActivity:search", {"Authorization": "Bearer {refresh_token}"}, "status_200", "Connected to Google Analytics"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="google-analytics", color_gradient="from-orange-500 to-yellow-400",
    ),
    # MARKETING
    IntegrationDefinition(
        key="mailchimp", name="Mailchimp",
        description="Access subscribers, campaigns, and automation data.",
        category=IntegrationCategory.MARKETING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "API Key", "password", True, "xxx-us1")]),
        test_connection=TestConnectionConfig("GET", "https://us1.api.mailchimp.com/3.0/", {"Authorization": "Bearer {api_key}"}, "status_200", "Connected to Mailchimp"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="mailchimp", color_gradient="from-yellow-500 to-yellow-400",
    ),
    IntegrationDefinition(
        key="klaviyo", name="Klaviyo",
        description="Access email marketing, flows, and customer data from Klaviyo.",
        category=IntegrationCategory.MARKETING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.API_KEY_QUERY, [AuthField("private_api_key", "Private API Key", "password", True)], query_param_name="api_key"),
        test_connection=TestConnectionConfig("GET", "https://a.klaviyo.com/api/accounts/?api_key={private_api_key}", {"Accept": "application/json"}, "status_200", "Connected to Klaviyo"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="klaviyo", color_gradient="from-green-600 to-green-500",
    ),
    IntegrationDefinition(
        key="brevo", name="Brevo",
        description="Send transactional emails and manage contacts via Brevo.",
        category=IntegrationCategory.MARKETING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "API Key", "password", True, "xkeysib-xxx")]),
        test_connection=TestConnectionConfig("GET", "https://api.brevo.com/v3/account", {"api-key": "{api_key}"}, "status_200", "Connected to Brevo"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        icon_id="brevo", color_gradient="from-blue-500 to-blue-400",
    ),
    # PAYMENTS
    IntegrationDefinition(
        key="stripe", name="Stripe",
        description="Access payments, subscriptions, and customer billing data.",
        category=IntegrationCategory.PAYMENTS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "Secret Key", "password", True, "sk_live_xxx")]),
        test_connection=TestConnectionConfig("GET", "https://api.stripe.com/v1/balance", {"Authorization": "Bearer {api_key}"}, "status_200", "Connected to Stripe"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="stripe", color_gradient="from-indigo-500 to-indigo-400",
    ),
    IntegrationDefinition(
        key="paddle", name="Paddle",
        description="Access subscriptions, transactions, and pricing data from Paddle.",
        category=IntegrationCategory.PAYMENTS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "API Key", "password", True, "pd_live_xxx")]),
        test_connection=TestConnectionConfig("GET", "https://sandbox-api.paddle.com/transactions", {"Authorization": "Bearer {api_key}"}, "status_200", "Connected to Paddle"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        icon_id="paddle", color_gradient="from-cyan-500 to-cyan-400",
    ),
    IntegrationDefinition(
        key="paypal", name="PayPal",
        description="Access transactions, refunds, and dispute data from PayPal.",
        category=IntegrationCategory.PAYMENTS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.OAUTH2, [
            AuthField("client_id", "Client ID", "text", True),
            AuthField("client_secret", "Client Secret", "password", True),
            AuthField("base_url", "Base URL", "url", True, "https://api-m.paypal.com"),
        ]),
        test_connection=TestConnectionConfig("GET", "{base_url}/v1/identity/oauth2/userinfo?schema=paypalv1.1", success_check="status_200", success_message="Connected to PayPal"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.OTHER],
        icon_id="paypal", color_gradient="from-blue-600 to-blue-500",
    ),
    # SHIPPING
    IntegrationDefinition(
        key="shipstation", name="ShipStation",
        description="Access shipments, orders, and fulfillment data from ShipStation.",
        category=IntegrationCategory.SHIPPING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BASIC_AUTH, [
            AuthField("api_key", "API Key", "text", True),
            AuthField("api_secret", "API Secret", "password", True),
        ]),
        test_connection=TestConnectionConfig("GET", "https://ssapi.shipstation.com/stores", success_check="status_200", success_message="Connected to ShipStation"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="shipstation", color_gradient="from-blue-500 to-blue-400",
    ),
    IntegrationDefinition(
        key="aftership", name="AfterShip",
        description="Track shipments and delivery status across carriers via AfterShip.",
        category=IntegrationCategory.SHIPPING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "API Key", "password", True, "as_xxx")]),
        test_connection=TestConnectionConfig("GET", "https://api.aftership.com/v4/couriers", {"aftership-api-key": "{api_key}"}, "status_200", "Connected to AfterShip"),
        suggested_industries=[ParwaIndustry.ECOMMERCE, ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="aftership", color_gradient="from-teal-500 to-teal-400",
    ),
    IntegrationDefinition(
        key="easypost", name="EasyPost",
        description="Generate labels, verify addresses, and track packages via EasyPost.",
        category=IntegrationCategory.SHIPPING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "API Key", "password", True, "EZAK_xxx")]),
        test_connection=TestConnectionConfig("GET", "https://api.easypost.com/v2/users", {"Authorization": "Bearer {api_key}"}, "status_200", "Connected to EasyPost"),
        suggested_industries=[ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="easypost", color_gradient="from-green-500 to-green-400",
    ),
    IntegrationDefinition(
        key="fedex", name="FedEx",
        description="Track shipments, get rates, and manage deliveries via FedEx API.",
        category=IntegrationCategory.SHIPPING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [
            AuthField("api_key", "API Key", "text", True, "l7xx..."),
            AuthField("secret_key", "Secret Key", "password", True),
        ]),
        test_connection=TestConnectionConfig("POST", "https://apis.fedex.com/oauth/token", {"Content-Type": "application/x-www-form-urlencoded"}, "status_200", "Connected to FedEx"),
        suggested_industries=[ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="fedex", color_gradient="from-purple-600 to-purple-500",
    ),
    IntegrationDefinition(
        key="ups", name="UPS",
        description="Track packages, get shipping rates, and validate addresses via UPS API.",
        category=IntegrationCategory.SHIPPING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.OAUTH2, [
            AuthField("client_id", "Client ID", "text", True, "xxx"),
            AuthField("client_secret", "Client Secret", "password", True),
        ]),
        test_connection=TestConnectionConfig("POST", "https://onlinetools.ups.com/security/v1/oauth/token", success_check="status_200", success_message="Connected to UPS"),
        suggested_industries=[ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="ups", color_gradient="from-amber-600 to-amber-500",
    ),
    IntegrationDefinition(
        key="dhl", name="DHL",
        description="Track shipments and get delivery updates via DHL API.",
        category=IntegrationCategory.SHIPPING, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "DHL API Key", "password", True, "demo-key")]),
        test_connection=TestConnectionConfig("GET", "https://api-eu.dhl.com/track/shipments?trackingNumber=0", {"DHL-API-Key": "{api_key}"}, "status_200", "Connected to DHL"),
        suggested_industries=[ParwaIndustry.LOGISTICS, ParwaIndustry.OTHER],
        icon_id="dhl", color_gradient="from-yellow-500 to-yellow-400",
    ),
    # DEV TOOLS
    IntegrationDefinition(
        key="github", name="GitHub",
        description="Access issues, pull requests, and repository data from GitHub.",
        category=IntegrationCategory.DEV_TOOLS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "Personal Access Token", "password", True, "ghp_xxx")]),
        test_connection=TestConnectionConfig("GET", "https://api.github.com/user", {"Authorization": "Bearer {api_key}"}, "status_200", "Connected to GitHub"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        available_for_variants=["parwa", "parwa_high"],
        icon_id="github", color_gradient="from-gray-600 to-gray-500",
    ),
    IntegrationDefinition(
        key="jira", name="Jira",
        description="Access issues, projects, and sprint data from Jira.",
        category=IntegrationCategory.DEV_TOOLS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BASIC_AUTH, [
            AuthField("domain", "Domain", "text", True, "yourcompany"),
            AuthField("email", "Email", "text", True),
            AuthField("api_token", "API Token", "password", True),
        ]),
        test_connection=TestConnectionConfig("GET", "https://{domain}.atlassian.net/rest/api/3/myself", success_check="status_200", success_message="Connected to Jira"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        available_for_variants=["parwa", "parwa_high"],
        icon_id="jira", color_gradient="from-blue-500 to-blue-400",
    ),
    IntegrationDefinition(
        key="linear", name="Linear",
        description="Access issues, projects, and cycles from Linear.",
        category=IntegrationCategory.DEV_TOOLS, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "API Key", "password", True, "lin_api_xxx")]),
        test_connection=TestConnectionConfig("POST", "https://api.linear.app/graphql", {"Authorization": "{api_key}", "Content-Type": "application/json"}, "status_200", "Connected to Linear"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        available_for_variants=["parwa", "parwa_high"],
        icon_id="linear", color_gradient="from-violet-500 to-violet-400",
    ),
    # PRODUCTIVITY
    IntegrationDefinition(
        key="notion", name="Notion",
        description="Access pages, databases, and content from Notion workspace.",
        category=IntegrationCategory.PRODUCTIVITY, tier=IntegrationTier.TIER1_PREBUILT,
        auth_schema=AuthSchema(AuthType.BEARER, [AuthField("api_key", "Internal Integration Token", "password", True, "ntn_xxx")]),
        test_connection=TestConnectionConfig("GET", "https://api.notion.com/v1/users/me", {"Authorization": "Bearer {api_key}", "Notion-Version": "2022-06-28"}, "status_200", "Connected to Notion"),
        suggested_industries=[ParwaIndustry.SAAS, ParwaIndustry.OTHER],
        available_for_variants=["parwa", "parwa_high"],
        icon_id="notion", color_gradient="from-gray-500 to-gray-400",
    ),
]


# ── Lookup Helpers ───────────────────────────────────────────────────────

# Build a lookup dict for O(1) access
_CATALOG_BY_KEY: Dict[str, IntegrationDefinition] = {i.key: i for i in CATALOG}


def get_catalog() -> List[Dict[str, Any]]:
    """Return the full catalog as a list of dicts."""
    return [i.to_dict() for i in CATALOG]


def get_catalog_for_industry(industry: str) -> List[Dict[str, Any]]:
    """Return integrations suggested for an industry.

    Per D3: 'other' shows ALL integrations (no filtering).
    Suggestions are NOT restrictions — clients can always connect outside their industry.
    """
    if industry == "other":
        return [i.to_dict() for i in CATALOG if i.available]

    try:
        parwa_industry = ParwaIndustry(industry.lower())
    except ValueError:
        return [i.to_dict() for i in CATALOG if i.available]

    return [
        i.to_dict() for i in CATALOG
        if i.available and parwa_industry in i.suggested_industries
    ]


def get_integration_by_key(key: str) -> Optional[IntegrationDefinition]:
    """Look up an integration definition by its key."""
    return _CATALOG_BY_KEY.get(key)


def get_catalog_grouped_by_category(industry: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return integrations grouped by category for an industry."""
    items = get_catalog_for_industry(industry)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        cat = item["category"]
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(item)
    return grouped
