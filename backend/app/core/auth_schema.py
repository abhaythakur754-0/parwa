"""
PARWA Phase 3 — Auth Schema & Integration Catalog Module

CRITICAL RULES:
- Paddle is ONLY for PARWA's own subscription billing — it must NOT appear in the client integration catalog
- 35 integration entries with correct industry mappings per the roadmap
- 5 auth types: bearer, api_key_header, api_key_query_param, basic_auth, oauth2
- BC-001: All operations scoped to company_id
- BC-008: Never crash — all methods wrapped in try/except

Architecture:
    AuthSchemaClass.validate(credentials) -> (bool, str)
    AuthSchemaClass.apply_to_request(request_config, credentials) -> dict
    AuthSchemaClass.mask_credentials(credentials) -> dict
    AuthSchemaClass.test_connection_url: str

    AUTH_SCHEMA_REGISTRY: dict mapping integration_type -> catalog entry
    IntegrationCatalogService: service class for catalog queries and connection testing
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _mask_value(value: str, visible_tail: int = 4) -> str:
    """Mask a sensitive string, showing only the last *visible_tail* characters.

    BC-008: Never crash — returns ``"****"`` on any error.
    """
    try:
        if not value:
            return "****"
        if len(value) <= visible_tail:
            return "****"
        return "*" * (len(value) - visible_tail) + value[-visible_tail:]
    except Exception:
        return "****"


# ---------------------------------------------------------------------------
# Auth Schema Classes — one per auth type
# ---------------------------------------------------------------------------

class BearerTokenAuth:
    """Authorization: Bearer {token}"""

    auth_type: str = "bearer"
    required_fields: List[str] = ["token"]
    test_connection_url: str = ""  # overridden per integration

    @classmethod
    def validate(cls, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate that all required fields are present and non-empty."""
        try:
            if not credentials or not isinstance(credentials, dict):
                return False, "Credentials must be a non-empty dictionary"
            missing = [
                f for f in cls.required_fields
                if f not in credentials or not credentials[f]
            ]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            return True, "Bearer token credentials validated"
        except Exception as exc:
            logger.error("BearerTokenAuth.validate error: %s", exc)
            return False, f"Validation error: {exc}"

    @classmethod
    def apply_to_request(
        cls,
        request_config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add Authorization header to the HTTP request config."""
        try:
            config = dict(request_config)
            headers = dict(config.get("headers", {}))
            headers["Authorization"] = f"Bearer {credentials.get('token', '')}"
            config["headers"] = headers
            return config
        except Exception as exc:
            logger.error("BearerTokenAuth.apply_to_request error: %s", exc)
            return dict(request_config)

    @classmethod
    def mask_credentials(cls, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy with sensitive values masked (show last 4 chars)."""
        try:
            return {
                "token": _mask_value(credentials.get("token", "")),
            }
        except Exception as exc:
            logger.error("BearerTokenAuth.mask_credentials error: %s", exc)
            return {"token": "****"}


class APIKeyHeaderAuth:
    """Custom header name + value  (e.g. X-API-Key: abc123)"""

    auth_type: str = "api_key_header"
    required_fields: List[str] = ["header_name", "api_key"]
    test_connection_url: str = ""

    @classmethod
    def validate(cls, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            if not credentials or not isinstance(credentials, dict):
                return False, "Credentials must be a non-empty dictionary"
            missing = [
                f for f in cls.required_fields
                if f not in credentials or not credentials[f]
            ]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            return True, "API key header credentials validated"
        except Exception as exc:
            logger.error("APIKeyHeaderAuth.validate error: %s", exc)
            return False, f"Validation error: {exc}"

    @classmethod
    def apply_to_request(
        cls,
        request_config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            config = dict(request_config)
            headers = dict(config.get("headers", {}))
            header_name = credentials.get("header_name", "X-API-Key")
            headers[header_name] = credentials.get("api_key", "")
            config["headers"] = headers
            return config
        except Exception as exc:
            logger.error("APIKeyHeaderAuth.apply_to_request error: %s", exc)
            return dict(request_config)

    @classmethod
    def mask_credentials(cls, credentials: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {
                "header_name": credentials.get("header_name", ""),
                "api_key": _mask_value(credentials.get("api_key", "")),
            }
        except Exception as exc:
            logger.error("APIKeyHeaderAuth.mask_credentials error: %s", exc)
            return {"header_name": "", "api_key": "****"}


class APIKeyQueryAuth:
    """Query parameter name + value  (e.g. ?api_key=abc123)"""

    auth_type: str = "api_key_query_param"
    required_fields: List[str] = ["param_name", "api_key"]
    test_connection_url: str = ""

    @classmethod
    def validate(cls, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            if not credentials or not isinstance(credentials, dict):
                return False, "Credentials must be a non-empty dictionary"
            missing = [
                f for f in cls.required_fields
                if f not in credentials or not credentials[f]
            ]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            return True, "API key query-param credentials validated"
        except Exception as exc:
            logger.error("APIKeyQueryAuth.validate error: %s", exc)
            return False, f"Validation error: {exc}"

    @classmethod
    def apply_to_request(
        cls,
        request_config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            config = dict(request_config)
            params = dict(config.get("params", {}))
            param_name = credentials.get("param_name", "api_key")
            params[param_name] = credentials.get("api_key", "")
            config["params"] = params
            return config
        except Exception as exc:
            logger.error("APIKeyQueryAuth.apply_to_request error: %s", exc)
            return dict(request_config)

    @classmethod
    def mask_credentials(cls, credentials: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {
                "param_name": credentials.get("param_name", ""),
                "api_key": _mask_value(credentials.get("api_key", "")),
            }
        except Exception as exc:
            logger.error("APIKeyQueryAuth.mask_credentials error: %s", exc)
            return {"param_name": "", "api_key": "****"}


class BasicAuth:
    """Username + password → base64-encoded Authorization header."""

    auth_type: str = "basic_auth"
    required_fields: List[str] = ["username", "password"]
    test_connection_url: str = ""

    @classmethod
    def validate(cls, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            if not credentials or not isinstance(credentials, dict):
                return False, "Credentials must be a non-empty dictionary"
            missing = [
                f for f in cls.required_fields
                if f not in credentials or not credentials[f]
            ]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            return True, "Basic auth credentials validated"
        except Exception as exc:
            logger.error("BasicAuth.validate error: %s", exc)
            return False, f"Validation error: {exc}"

    @classmethod
    def apply_to_request(
        cls,
        request_config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            config = dict(request_config)
            headers = dict(config.get("headers", {}))
            username = credentials.get("username", "")
            password = credentials.get("password", "")
            encoded = base64.b64encode(
                f"{username}:{password}".encode("utf-8")
            ).decode("utf-8")
            headers["Authorization"] = f"Basic {encoded}"
            config["headers"] = headers
            return config
        except Exception as exc:
            logger.error("BasicAuth.apply_to_request error: %s", exc)
            return dict(request_config)

    @classmethod
    def mask_credentials(cls, credentials: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {
                "username": credentials.get("username", ""),
                "password": _mask_value(credentials.get("password", "")),
            }
        except Exception as exc:
            logger.error("BasicAuth.mask_credentials error: %s", exc)
            return {"username": "", "password": "****"}


class OAuth2Auth:
    """client_id + client_secret + redirect_uri + refresh_token"""

    auth_type: str = "oauth2"
    required_fields: List[str] = [
        "client_id",
        "client_secret",
        "redirect_uri",
        "refresh_token",
    ]
    test_connection_url: str = ""

    @classmethod
    def validate(cls, credentials: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            if not credentials or not isinstance(credentials, dict):
                return False, "Credentials must be a non-empty dictionary"
            missing = [
                f for f in cls.required_fields
                if f not in credentials or not credentials[f]
            ]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            return True, "OAuth2 credentials validated"
        except Exception as exc:
            logger.error("OAuth2Auth.validate error: %s", exc)
            return False, f"Validation error: {exc}"

    @classmethod
    def apply_to_request(
        cls,
        request_config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add OAuth2 Bearer token to request (assumes token exchange already done).

        If an ``access_token`` key is present in credentials it is used directly.
        Otherwise the refresh-token exchange parameters are attached so a
        downstream token-exchange step can be performed.
        """
        try:
            config = dict(request_config)
            headers = dict(config.get("headers", {}))

            access_token = credentials.get("access_token")
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            else:
                # Attach refresh-token exchange payload for downstream use
                config["oauth2_refresh"] = {
                    "client_id": credentials.get("client_id", ""),
                    "client_secret": credentials.get("client_secret", ""),
                    "redirect_uri": credentials.get("redirect_uri", ""),
                    "refresh_token": credentials.get("refresh_token", ""),
                    "grant_type": "refresh_token",
                }

            config["headers"] = headers
            return config
        except Exception as exc:
            logger.error("OAuth2Auth.apply_to_request error: %s", exc)
            return dict(request_config)

    @classmethod
    def mask_credentials(cls, credentials: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return {
                "client_id": credentials.get("client_id", ""),
                "client_secret": _mask_value(
                    credentials.get("client_secret", "")
                ),
                "redirect_uri": credentials.get("redirect_uri", ""),
                "refresh_token": _mask_value(
                    credentials.get("refresh_token", "")
                ),
            }
        except Exception as exc:
            logger.error("OAuth2Auth.mask_credentials error: %s", exc)
            return {
                "client_id": "",
                "client_secret": "****",
                "redirect_uri": "",
                "refresh_token": "****",
            }


# ---------------------------------------------------------------------------
# Auth schema lookup
# ---------------------------------------------------------------------------

AUTH_TYPE_MAP: Dict[str, type] = {
    "bearer": BearerTokenAuth,
    "api_key_header": APIKeyHeaderAuth,
    "api_key_query_param": APIKeyQueryAuth,
    "basic_auth": BasicAuth,
    "oauth2": OAuth2Auth,
}


# ---------------------------------------------------------------------------
# Integration Catalog — 35 entries (NO PADDLE)
# ---------------------------------------------------------------------------

AUTH_SCHEMA_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ── CRM ──────────────────────────────────────────────────────────────
    "hubspot": {
        "name": "HubSpot",
        "category": "crm",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.hubapi.com/crm/v3/objects/contacts?limit=1",
        "industries": ["saas", "ecommerce", "logistics", "other"],
        "description": "HubSpot CRM — contacts, deals, companies, and tickets management.",
    },
    "salesforce": {
        "name": "Salesforce",
        "category": "crm",
        "auth_type": "oauth2",
        "auth_schema": ["client_id", "client_secret", "redirect_uri", "refresh_token"],
        "test_connection_url": "https://login.salesforce.com/services/oauth2/userinfo",
        "industries": ["saas", "logistics", "other"],
        "description": "Salesforce CRM — enterprise customer relationship management with lead and opportunity tracking.",
    },
    "pipedrive": {
        "name": "Pipedrive",
        "category": "crm",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.pipedrive.com/v1/users/me",
        "industries": ["saas", "other"],
        "description": "Pipedrive CRM — visual sales pipeline and deal management.",
    },
    # ── Ecommerce ────────────────────────────────────────────────────────
    "shopify": {
        "name": "Shopify",
        "category": "ecommerce",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://{shop}.myshopify.com/admin/api/2024-01/shop.json",
        "industries": ["ecommerce", "other"],
        "description": "Shopify — e-commerce platform for online stores, products, orders, and fulfillment.",
    },
    "woocommerce": {
        "name": "WooCommerce",
        "category": "ecommerce",
        "auth_type": "basic_auth",
        "auth_schema": ["username", "password"],
        "test_connection_url": "https://{shop}/wp-json/wc/v3/system_status",
        "industries": ["ecommerce", "other"],
        "description": "WooCommerce — WordPress-based e-commerce with product, order, and customer management.",
    },
    "bigcommerce": {
        "name": "BigCommerce",
        "category": "ecommerce",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://api.bigcommerce.com/stores/{store_hash}/v2/store",
        "industries": ["ecommerce", "other"],
        "description": "BigCommerce — enterprise e-commerce platform with catalog, orders, and storefront APIs.",
    },
    # ── Helpdesk ─────────────────────────────────────────────────────────
    "zendesk": {
        "name": "Zendesk",
        "category": "helpdesk",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://{subdomain}.zendesk.com/api/v2/users/me.json",
        "industries": ["saas", "ecommerce", "logistics", "other"],
        "description": "Zendesk — customer support ticketing, help center, and messaging platform.",
    },
    "freshdesk": {
        "name": "Freshdesk",
        "category": "helpdesk",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://{domain}.freshdesk.com/api/v2/settings/helpdesk",
        "industries": ["saas", "logistics", "other"],
        "description": "Freshdesk — helpdesk ticketing with automation, knowledge base, and multichannel support.",
    },
    "intercom": {
        "name": "Intercom",
        "category": "helpdesk",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.intercom.io/me",
        "industries": ["saas", "other"],
        "description": "Intercom — conversational support, engagement, and customer messaging platform.",
    },
    "gorgias": {
        "name": "Gorgias",
        "category": "helpdesk",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://{domain}.gorgias.com/api/users/me",
        "industries": ["ecommerce", "other"],
        "description": "Gorgias — ecommerce helpdesk with auto-replies, ticketing, and social media integration.",
    },
    # ── Payment ──────────────────────────────────────────────────────────
    "stripe": {
        "name": "Stripe",
        "category": "payment",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.stripe.com/v1/balance",
        "industries": ["saas", "ecommerce", "logistics", "other"],
        "description": "Stripe — online payment processing for subscriptions, invoices, and refunds.",
    },
    "paypal": {
        "name": "PayPal",
        "category": "payment",
        "auth_type": "oauth2",
        "auth_schema": ["client_id", "client_secret", "redirect_uri", "refresh_token"],
        "test_connection_url": "https://api-m.paypal.com/v1/identity/oauth2/userinfo",
        "industries": ["ecommerce", "other"],
        "description": "PayPal — global payment platform with checkout, subscriptions, and payout APIs.",
    },
    "razorpay": {
        "name": "Razorpay",
        "category": "payment",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://api.razorpay.com/v1/items",
        "industries": ["other"],
        "description": "Razorpay — Indian payment gateway with payment links, settlements, and refunds.",
    },
    # ── Analytics ────────────────────────────────────────────────────────
    "mixpanel": {
        "name": "Mixpanel",
        "category": "analytics",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.mixpanel.com/query/engage?project_id={project_id}",
        "industries": ["saas", "other"],
        "description": "Mixpanel — product analytics with event tracking, funnels, and retention reports.",
    },
    "amplitude": {
        "name": "Amplitude",
        "category": "analytics",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://amplitude.com/api/2/userprofile",
        "industries": ["saas", "other"],
        "description": "Amplitude — digital analytics platform for user behavior, cohorts, and A/B testing.",
    },
    "google_analytics": {
        "name": "Google Analytics",
        "category": "analytics",
        "auth_type": "oauth2",
        "auth_schema": ["client_id", "client_secret", "redirect_uri", "refresh_token"],
        "test_connection_url": "https://analyticsreporting.googleapis.com/v4/userActivity:search",
        "industries": ["ecommerce", "other"],
        "description": "Google Analytics — web and app analytics with audience, acquisition, and conversion data.",
    },
    # ── Email ────────────────────────────────────────────────────────────
    "mailchimp": {
        "name": "Mailchimp",
        "category": "email",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://{dc}.api.mailchimp.com/3.0/ping",
        "industries": ["saas", "ecommerce", "other"],
        "description": "Mailchimp — email marketing, automation, audience management, and campaign analytics.",
    },
    "klaviyo": {
        "name": "Klaviyo",
        "category": "email",
        "auth_type": "api_key_query_param",
        "auth_schema": ["param_name", "api_key"],
        "test_connection_url": "https://a.klaviyo.com/api/accounts",
        "industries": ["ecommerce", "other"],
        "description": "Klaviyo — ecommerce email and SMS marketing with flows, segments, and predictive analytics.",
    },
    "brevo": {
        "name": "Brevo",
        "category": "email",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://api.brevo.com/v3/account",
        "industries": ["saas", "ecommerce", "other"],
        "description": "Brevo (formerly Sendinblue) — email, SMS, and chat marketing with transactional email support.",
    },
    "sendgrid": {
        "name": "SendGrid",
        "category": "email",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.sendgrid.com/v3/user/account",
        "industries": ["saas", "ecommerce", "other"],
        "description": "SendGrid — transactional and marketing email delivery with templates and analytics.",
    },
    "mailgun": {
        "name": "Mailgun",
        "category": "email",
        "auth_type": "basic_auth",
        "auth_schema": ["username", "password"],
        "test_connection_url": "https://api.mailgun.net/v3/domains",
        "industries": ["saas", "ecommerce", "other"],
        "description": "Mailgun — transactional email service with routing, validation, and analytics APIs.",
    },
    "postmark": {
        "name": "Postmark",
        "category": "email",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.postmarkapp.com/server",
        "industries": ["saas", "ecommerce", "other"],
        "description": "Postmark — fast transactional email delivery with bounce handling and open tracking.",
    },
    # ── Productivity ─────────────────────────────────────────────────────
    "slack": {
        "name": "Slack",
        "category": "productivity",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://slack.com/api/auth.test",
        "industries": ["saas", "ecommerce", "logistics", "other"],
        "description": "Slack — team messaging, channels, threads, and workflow automation platform.",
    },
    "notion": {
        "name": "Notion",
        "category": "productivity",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.notion.com/v1/users/me",
        "industries": ["saas", "other"],
        "description": "Notion — workspace for docs, wikis, databases, and project management.",
    },
    # ── Dev Tools ────────────────────────────────────────────────────────
    "github": {
        "name": "GitHub",
        "category": "dev_tools",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.github.com/user",
        "industries": ["saas", "other"],
        "description": "GitHub — code hosting, pull requests, issues, and CI/CD integrations.",
    },
    "jira": {
        "name": "Jira",
        "category": "dev_tools",
        "auth_type": "basic_auth",
        "auth_schema": ["username", "password"],
        "test_connection_url": "https://{domain}.atlassian.net/rest/api/3/myself",
        "industries": ["saas", "other"],
        "description": "Jira — issue tracking, agile boards, sprint management, and project workflows.",
    },
    "linear": {
        "name": "Linear",
        "category": "dev_tools",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.linear.app/graphql",
        "industries": ["saas", "other"],
        "description": "Linear — modern issue tracking with cycles, projects, and keyboard-first workflow.",
    },
    # ── SMS ──────────────────────────────────────────────────────────────
    "twilio": {
        "name": "Twilio",
        "category": "sms",
        "auth_type": "basic_auth",
        "auth_schema": ["username", "password"],
        "test_connection_url": "https://api.twilio.com/2010-04-01/Accounts.json",
        "industries": ["saas", "ecommerce", "logistics", "other"],
        "description": "Twilio — SMS, voice, and WhatsApp messaging with phone number management.",
    },
    "vonage": {
        "name": "Vonage",
        "category": "sms",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://api.nexmo.com/v1/methods/getBalance",
        "industries": ["saas", "ecommerce", "logistics", "other"],
        "description": "Vonage (Nexmo) — SMS, voice, and verify APIs with global carrier reach.",
    },
    # ── Shipping ─────────────────────────────────────────────────────────
    "shipstation": {
        "name": "ShipStation",
        "category": "shipping",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://ssapi.shipstation.com/users",
        "industries": ["ecommerce", "logistics", "other"],
        "description": "ShipStation — multi-carrier shipping, order fulfillment, and label management.",
    },
    "aftership": {
        "name": "AfterShip",
        "category": "shipping",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://api.aftership.com/v4/trackings",
        "industries": ["ecommerce", "logistics", "other"],
        "description": "AfterShip — shipment tracking, notifications, and post-purchase analytics.",
    },
    "easypost": {
        "name": "EasyPost",
        "category": "shipping",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://api.easypost.com/v2/users",
        "industries": ["logistics", "other"],
        "description": "EasyPost — shipping API for rates, labels, tracking, and insurance across carriers.",
    },
    "fedex": {
        "name": "FedEx",
        "category": "shipping",
        "auth_type": "bearer",
        "auth_schema": ["token"],
        "test_connection_url": "https://apis.fedex.com/track/v2/shipments",
        "industries": ["logistics", "other"],
        "description": "FedEx — shipping, tracking, rating, and pickup APIs for FedEx carrier services.",
    },
    "ups": {
        "name": "UPS",
        "category": "shipping",
        "auth_type": "oauth2",
        "auth_schema": ["client_id", "client_secret", "redirect_uri", "refresh_token"],
        "test_connection_url": "https://onlinetools.ups.com/api/track/v1/details/{tracking_number}",
        "industries": ["logistics", "other"],
        "description": "UPS — shipping, tracking, rating, and time-in-transit APIs for UPS services.",
    },
    "dhl": {
        "name": "DHL",
        "category": "shipping",
        "auth_type": "api_key_header",
        "auth_schema": ["header_name", "api_key"],
        "test_connection_url": "https://api.dhl.com/track/shipments",
        "industries": ["logistics", "other"],
        "description": "DHL — shipment tracking, pickup, and rating APIs for DHL Express and DHL eCommerce.",
    },
}


# ---------------------------------------------------------------------------
# Integration Catalog Service
# ---------------------------------------------------------------------------

class IntegrationCatalogService:
    """Service for querying the integration catalog and testing connections.

    BC-001: Every public method accepts ``company_id`` so that operations are
    scoped to a single tenant.

    BC-008: Every public method is wrapped in try/except so the service never
    crashes the caller.
    """

    def __init__(self, company_id: str) -> None:
        self.company_id = company_id

    # ── catalog queries ──────────────────────────────────────────────────

    def get_catalog(self, industry: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return the full catalog or filter by industry.

        When *industry* is ``None``, ``"other"`` or ``"general"``, all
        integrations are returned (BC-001: still scoped to company_id in
        metadata).
        """
        try:
            all_entries = []
            for key, entry in AUTH_SCHEMA_REGISTRY.items():
                item = dict(entry)
                item["integration_type"] = key
                item["company_id"] = self.company_id
                all_entries.append(item)

            if not industry or industry.lower() in ("other", "general"):
                return all_entries

            industry_lower = industry.lower()
            filtered = [
                e for e in all_entries
                if industry_lower in [i.lower() for i in e.get("industries", [])]
            ]
            return filtered
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.get_catalog error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return []

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Return all integrations matching *category*."""
        try:
            if not category:
                return []
            category_lower = category.lower()
            results = []
            for key, entry in AUTH_SCHEMA_REGISTRY.items():
                if entry.get("category", "").lower() == category_lower:
                    item = dict(entry)
                    item["integration_type"] = key
                    item["company_id"] = self.company_id
                    results.append(item)
            return results
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.get_by_category error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return []

    def get_integration(self, integration_type: str) -> Dict[str, Any]:
        """Return a single integration entry or an empty dict if not found."""
        try:
            entry = AUTH_SCHEMA_REGISTRY.get(integration_type)
            if not entry:
                return {
                    "error": f"Integration type '{integration_type}' not found in catalog",
                    "company_id": self.company_id,
                }
            item = dict(entry)
            item["integration_type"] = integration_type
            item["company_id"] = self.company_id
            return item
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.get_integration error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return {
                "error": f"Failed to retrieve integration: {exc}",
                "company_id": self.company_id,
            }

    # ── connection testing ───────────────────────────────────────────────

    def test_connection(
        self,
        integration_type: str,
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate credentials and simulate a connection test.

        Returns a result dict with ``success``, ``message``, and
        ``masked_credentials`` keys.  The actual HTTP call is not performed
        here — the returned ``test_url`` and ``request_config`` give the
        caller everything needed to execute the real request.
        """
        try:
            entry = AUTH_SCHEMA_REGISTRY.get(integration_type)
            if not entry:
                return {
                    "success": False,
                    "message": f"Integration type '{integration_type}' not found in catalog",
                    "company_id": self.company_id,
                    "integration_type": integration_type,
                }

            auth_type_str = entry.get("auth_type", "")
            auth_cls = AUTH_TYPE_MAP.get(auth_type_str)
            if not auth_cls:
                return {
                    "success": False,
                    "message": f"Unsupported auth type '{auth_type_str}'",
                    "company_id": self.company_id,
                    "integration_type": integration_type,
                }

            # Validate
            is_valid, validation_msg = auth_cls.validate(credentials)
            if not is_valid:
                return {
                    "success": False,
                    "message": validation_msg,
                    "company_id": self.company_id,
                    "integration_type": integration_type,
                }

            # Build request config for test call
            test_url = entry.get("test_connection_url", "")
            request_config: Dict[str, Any] = {
                "method": "GET",
                "url": test_url,
                "headers": {},
                "params": {},
            }
            request_config = auth_cls.apply_to_request(request_config, credentials)

            # Mask credentials for safe return
            masked = auth_cls.mask_credentials(credentials)

            return {
                "success": True,
                "message": f"Credentials validated for {entry.get('name', integration_type)}. Test URL prepared.",
                "company_id": self.company_id,
                "integration_type": integration_type,
                "test_url": test_url,
                "request_config": request_config,
                "masked_credentials": masked,
            }
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.test_connection error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return {
                "success": False,
                "message": f"Connection test failed: {exc}",
                "company_id": self.company_id,
                "integration_type": integration_type,
            }

    # ── convenience helpers ──────────────────────────────────────────────

    def list_categories(self) -> List[str]:
        """Return unique categories across all integrations."""
        try:
            categories = sorted({
                entry.get("category", "")
                for entry in AUTH_SCHEMA_REGISTRY.values()
                if entry.get("category")
            })
            return categories
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.list_categories error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return []

    def list_industries(self) -> List[str]:
        """Return unique industries across all integrations."""
        try:
            industries: set = set()
            for entry in AUTH_SCHEMA_REGISTRY.values():
                for ind in entry.get("industries", []):
                    industries.add(ind)
            return sorted(industries)
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.list_industries error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return []

    def get_auth_schema_for(self, integration_type: str) -> Dict[str, Any]:
        """Return the auth schema class and fields for an integration type."""
        try:
            entry = AUTH_SCHEMA_REGISTRY.get(integration_type)
            if not entry:
                return {
                    "error": f"Integration type '{integration_type}' not found",
                    "company_id": self.company_id,
                }
            auth_type_str = entry.get("auth_type", "")
            auth_cls = AUTH_TYPE_MAP.get(auth_type_str)
            return {
                "integration_type": integration_type,
                "name": entry.get("name", ""),
                "auth_type": auth_type_str,
                "auth_schema": entry.get("auth_schema", []),
                "auth_class": auth_cls.__name__ if auth_cls else None,
                "required_fields": auth_cls.required_fields if auth_cls else [],
                "test_connection_url": entry.get("test_connection_url", ""),
                "company_id": self.company_id,
            }
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.get_auth_schema_for error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return {
                "error": f"Failed to get auth schema: {exc}",
                "company_id": self.company_id,
            }

    def mask_credentials(
        self,
        integration_type: str,
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Mask sensitive credential values for an integration type."""
        try:
            auth_type_str = AUTH_SCHEMA_REGISTRY.get(
                integration_type, {}
            ).get("auth_type", "")
            auth_cls = AUTH_TYPE_MAP.get(auth_type_str)
            if not auth_cls:
                return {k: "****" for k in credentials}
            return auth_cls.mask_credentials(credentials)
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.mask_credentials error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return {k: "****" for k in credentials}

    def apply_auth_to_request(
        self,
        integration_type: str,
        request_config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply authentication to an HTTP request config for a given integration."""
        try:
            auth_type_str = AUTH_SCHEMA_REGISTRY.get(
                integration_type, {}
            ).get("auth_type", "")
            auth_cls = AUTH_TYPE_MAP.get(auth_type_str)
            if not auth_cls:
                return dict(request_config)
            return auth_cls.apply_to_request(request_config, credentials)
        except Exception as exc:
            logger.error(
                "IntegrationCatalogService.apply_auth_to_request error (company_id=%s): %s",
                self.company_id,
                exc,
            )
            return dict(request_config)
