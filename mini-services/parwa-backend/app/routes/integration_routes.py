"""Integration routes for PARWA backend.

Phase 15: Integration test endpoint now uses ExternalToolBus for
retry, circuit breaker, and cache support.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, IntegrationCredential, AuditLog
from app.auth import get_current_user
from app.encryption import encrypt_data, decrypt_data, mask_key
from app.services.external_tool_bus import get_tool_bus

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# --- Integration Catalog ---

INTEGRATION_CATALOG = [
    # ===== CRM =====
    {
        "id": "hubspot",
        "name": "HubSpot",
        "category": "crm",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "HubSpot API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.hubapi.com/crm/v3/contacts?limit=1",
            "headers": {"Authorization": "Bearer {api_key}"},
        },
        "tier": 1,
        "description": "CRM platform for managing contacts, deals, and customer relationships",
        "industries": ["saas", "ecommerce", "logistics", "other"],
    },
    {
        "id": "salesforce",
        "name": "Salesforce",
        "category": "crm",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [
                {"name": "access_token", "label": "Salesforce Access Token", "type": "password", "required": True},
                {"name": "instance_url", "label": "Instance URL", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "{instance_url}/services/data/v58.0/query?q=SELECT+Id+FROM+Account+LIMIT+1",
            "headers": {"Authorization": "Bearer {access_token}"},
        },
        "tier": 1,
        "description": "Enterprise CRM for sales, service, and marketing automation",
        "industries": ["saas", "logistics", "other"],
    },
    {
        "id": "pipedrive",
        "name": "Pipedrive",
        "category": "crm",
        "auth_type": "query",
        "auth_schema": {
            "fields": [{"name": "api_token", "label": "Pipedrive API Token", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.pipedrive.com/v1/users/me?api_token={api_token}",
        },
        "tier": 1,
        "description": "Sales CRM for managing pipelines and deals",
        "industries": ["saas", "other"],
    },
    # ===== E-commerce =====
    {
        "id": "shopify",
        "name": "Shopify",
        "category": "ecommerce",
        "auth_type": "header",
        "auth_schema": {
            "fields": [
                {"name": "access_token", "label": "Shopify Access Token", "type": "password", "required": True},
                {"name": "shop_domain", "label": "Shop Domain (e.g. mystore.myshopify.com)", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://{shop_domain}/admin/api/2024-01/shop.json",
            "headers": {"X-Shopify-Access-Token": "{access_token}"},
        },
        "tier": 1,
        "description": "E-commerce platform for online stores and retail",
        "industries": ["ecommerce", "other"],
    },
    {
        "id": "woocommerce",
        "name": "WooCommerce",
        "category": "ecommerce",
        "auth_type": "basic",
        "auth_schema": {
            "fields": [
                {"name": "consumer_key", "label": "Consumer Key", "type": "password", "required": True},
                {"name": "consumer_secret", "label": "Consumer Secret", "type": "password", "required": True},
                {"name": "store_url", "label": "Store URL", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "{store_url}/wp-json/wc/v3/system_status",
            "auth": {"username": "{consumer_key}", "password": "{consumer_secret}"},
        },
        "tier": 1,
        "description": "WordPress-based e-commerce platform",
        "industries": ["ecommerce", "other"],
    },
    {
        "id": "bigcommerce",
        "name": "BigCommerce",
        "category": "ecommerce",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [
                {"name": "access_token", "label": "BigCommerce Access Token", "type": "password", "required": True},
                {"name": "store_hash", "label": "Store Hash", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.bigcommerce.com/stores/{store_hash}/v2/store",
            "headers": {
                "X-Auth-Token": "{access_token}",
                "Accept": "application/json",
            },
        },
        "tier": 1,
        "description": "Enterprise e-commerce platform for growing businesses",
        "industries": ["ecommerce", "other"],
    },
    # ===== Helpdesk =====
    {
        "id": "zendesk",
        "name": "Zendesk",
        "category": "helpdesk",
        "auth_type": "basic",
        "auth_schema": {
            "fields": [
                {"name": "email", "label": "Zendesk Email", "type": "email", "required": True},
                {"name": "api_token", "label": "API Token", "type": "password", "required": True},
                {"name": "subdomain", "label": "Subdomain", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://{subdomain}.zendesk.com/api/v2/tickets/count",
            "auth": {"username": "{email}/token", "password": "{api_token}"},
        },
        "tier": 1,
        "description": "Customer support and ticketing platform",
        "industries": ["saas", "ecommerce", "logistics", "other"],
    },
    {
        "id": "freshdesk",
        "name": "Freshdesk",
        "category": "helpdesk",
        "auth_type": "basic",
        "auth_schema": {
            "fields": [
                {"name": "api_key", "label": "Freshdesk API Key", "type": "password", "required": True},
                {"name": "domain", "label": "Domain (e.g. mycompany.freshdesk.com)", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://{domain}/api/v2/tickets?per_page=1",
            "auth": {"username": "{api_key}", "password": "X"},
        },
        "tier": 1,
        "description": "Freshworks customer support platform",
        "industries": ["saas", "logistics", "other"],
    },
    {
        "id": "intercom",
        "name": "Intercom",
        "category": "helpdesk",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "access_token", "label": "Intercom Access Token", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.intercom.io/admins",
            "headers": {
                "Authorization": "Bearer {access_token}",
                "Accept": "application/json",
            },
        },
        "tier": 1,
        "description": "Customer messaging and engagement platform",
        "industries": ["saas", "other"],
    },
    {
        "id": "gorgias",
        "name": "Gorgias",
        "category": "helpdesk",
        "auth_type": "basic",
        "auth_schema": {
            "fields": [
                {"name": "email", "label": "Gorgias Email", "type": "email", "required": True},
                {"name": "api_key", "label": "API Key", "type": "password", "required": True},
                {"name": "domain", "label": "Domain (e.g. mycompany.gorgias.com)", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://{domain}/api/tickets/?limit=1",
            "auth": {"username": "{email}", "password": "{api_key}"},
        },
        "tier": 1,
        "description": "E-commerce helpdesk with automation",
        "industries": ["ecommerce", "other"],
    },
    # ===== Analytics =====
    {
        "id": "mixpanel",
        "name": "Mixpanel",
        "category": "analytics",
        "auth_type": "basic",
        "auth_schema": {
            "fields": [
                {"name": "api_secret", "label": "Mixpanel API Secret", "type": "password", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://mixpanel.com/api/2.0/engage?project_id=test",
            "auth": {"username": "{api_secret}", "password": ""},
        },
        "tier": 2,
        "description": "Product analytics for user behavior tracking",
        "industries": ["saas", "other"],
    },
    {
        "id": "amplitude",
        "name": "Amplitude",
        "category": "analytics",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Amplitude API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "POST",
            "url": "https://amplitude.com/api/2/userprivacy/deletion",
            "headers": {"Authorization": "Bearer {api_key}"},
        },
        "tier": 2,
        "description": "Digital analytics and product intelligence platform",
        "industries": ["saas", "other"],
    },
    {
        "id": "google_analytics",
        "name": "Google Analytics",
        "category": "analytics",
        "auth_type": "oauth2",
        "auth_schema": {
            "fields": [
                {"name": "access_token", "label": "Google OAuth Access Token", "type": "password", "required": True},
                {"name": "refresh_token", "label": "Google OAuth Refresh Token", "type": "password", "required": True},
                {"name": "property_id", "label": "GA4 Property ID", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}/metadata",
            "headers": {"Authorization": "Bearer {access_token}"},
        },
        "tier": 2,
        "description": "Web analytics and reporting platform",
        "industries": ["ecommerce", "other"],
    },
    # ===== Email Marketing =====
    {
        "id": "klaviyo",
        "name": "Klaviyo",
        "category": "email_marketing",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Klaviyo Private API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://a.klaviyo.com/api/profiles/?page[size]=1",
            "headers": {
                "Authorization": "Klaviyo-API-Key {api_key}",
                "accept": "application/json",
                "revision": "2024-02-15",
            },
        },
        "tier": 2,
        "description": "Email marketing and SMS platform for e-commerce",
        "industries": ["ecommerce", "other"],
    },
    {
        "id": "mailchimp",
        "name": "Mailchimp",
        "category": "email_marketing",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Mailchimp API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://us1.api.mailchimp.com/3.0/ping",
            "headers": {"Authorization": "Bearer {api_key}"},
        },
        "tier": 2,
        "description": "Email marketing and automation platform",
        "industries": ["saas", "ecommerce", "other"],
    },
    {
        "id": "brevo",
        "name": "Brevo",
        "category": "email_marketing",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Brevo API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.brevo.com/v3/account",
            "headers": {"api-key": "{api_key}"},
        },
        "tier": 2,
        "description": "Email marketing, SMS, and CRM platform",
        "industries": ["saas", "other"],
    },
    # ===== Payments =====
    {
        "id": "stripe",
        "name": "Stripe",
        "category": "payments",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Stripe Secret Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.stripe.com/v1/balance",
            "headers": {"Authorization": "Bearer {api_key}"},
        },
        "tier": 1,
        "description": "Online payment processing platform",
        "industries": ["saas", "ecommerce", "logistics", "other"],
    },
    {
        "id": "paddle",
        "name": "Paddle",
        "category": "payments",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Paddle API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://sandbox-api.paddle.com/transactions",
            "headers": {"Authorization": "Bearer {api_key}"},
        },
        "tier": 1,
        "description": "SaaS billing and payment platform",
        "industries": ["saas", "other"],
    },
    {
        "id": "paypal",
        "name": "PayPal",
        "category": "payments",
        "auth_type": "oauth2",
        "auth_schema": {
            "fields": [
                {"name": "client_id", "label": "PayPal Client ID", "type": "text", "required": True},
                {"name": "client_secret", "label": "PayPal Client Secret", "type": "password", "required": True},
            ]
        },
        "test_config": {
            "method": "POST",
            "url": "https://api-m.sandbox.paypal.com/v1/oauth2/token",
            "auth": {"username": "{client_id}", "password": "{client_secret}"},
        },
        "tier": 1,
        "description": "Global online payment platform",
        "industries": ["ecommerce", "other"],
    },
    # ===== Dev Tools =====
    {
        "id": "github",
        "name": "GitHub",
        "category": "dev_tools",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "GitHub Personal Access Token", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.github.com/user",
            "headers": {"Authorization": "Bearer {api_key}"},
        },
        "tier": 2,
        "description": "Code hosting and collaboration platform",
        "industries": ["saas", "other"],
    },
    {
        "id": "jira",
        "name": "Jira",
        "category": "dev_tools",
        "auth_type": "basic",
        "auth_schema": {
            "fields": [
                {"name": "email", "label": "Atlassian Email", "type": "email", "required": True},
                {"name": "api_token", "label": "API Token", "type": "password", "required": True},
                {"name": "domain", "label": "Domain (e.g. mycompany.atlassian.net)", "type": "text", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://{domain}/rest/api/3/myself",
            "auth": {"username": "{email}", "password": "{api_token}"},
        },
        "tier": 2,
        "description": "Project management and issue tracking",
        "industries": ["saas", "other"],
    },
    {
        "id": "linear",
        "name": "Linear",
        "category": "dev_tools",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Linear API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "POST",
            "url": "https://api.linear.app/graphql",
            "headers": {"Authorization": "{api_key}"},
            "body": '{"query": "{ viewer { id } }"}',
        },
        "tier": 2,
        "description": "Modern project management for software teams",
        "industries": ["saas", "other"],
    },
    # ===== Shipping =====
    {
        "id": "shipstation",
        "name": "ShipStation",
        "category": "shipping",
        "auth_type": "basic",
        "auth_schema": {
            "fields": [
                {"name": "api_key", "label": "ShipStation API Key", "type": "password", "required": True},
                {"name": "api_secret", "label": "ShipStation API Secret", "type": "password", "required": True},
            ]
        },
        "test_config": {
            "method": "GET",
            "url": "https://ssapi.shipstation.com/orders?pageSize=1",
            "auth": {"username": "{api_key}", "password": "{api_secret}"},
        },
        "tier": 1,
        "description": "Shipping and order fulfillment platform",
        "industries": ["ecommerce", "logistics", "other"],
    },
    {
        "id": "aftership",
        "name": "AfterShip",
        "category": "shipping",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "AfterShip API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.aftership.com/v4/couriers",
            "headers": {"aftership-api-key": "{api_key}"},
        },
        "tier": 1,
        "description": "Shipment tracking and notification platform",
        "industries": ["ecommerce", "logistics", "other"],
    },
    {
        "id": "easypost",
        "name": "EasyPost",
        "category": "shipping",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "EasyPost API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.easypost.com/v2/users",
            "auth": {"username": "{api_key}", "password": ""},
        },
        "tier": 1,
        "description": "Shipping API and logistics platform",
        "industries": ["logistics", "other"],
    },
    {
        "id": "fedex",
        "name": "FedEx",
        "category": "shipping",
        "auth_type": "oauth2",
        "auth_schema": {
            "fields": [
                {"name": "client_id", "label": "FedEx Client ID", "type": "text", "required": True},
                {"name": "client_secret", "label": "FedEx Client Secret", "type": "password", "required": True},
            ]
        },
        "test_config": {
            "method": "POST",
            "url": "https://apis-sandbox.fedex.com/oauth/token",
            "body": "grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}",
        },
        "tier": 1,
        "description": "FedEx shipping and logistics services",
        "industries": ["logistics", "other"],
    },
    {
        "id": "ups",
        "name": "UPS",
        "category": "shipping",
        "auth_type": "oauth2",
        "auth_schema": {
            "fields": [
                {"name": "client_id", "label": "UPS Client ID", "type": "text", "required": True},
                {"name": "client_secret", "label": "UPS Client Secret", "type": "password", "required": True},
            ]
        },
        "test_config": {
            "method": "POST",
            "url": "https://wwwcie.ups.com/security/v1/oauth/token",
            "body": "grant_type=client_credentials",
            "headers": {
                "Authorization": "Basic {base64(client_id:client_secret)}",
            },
        },
        "tier": 1,
        "description": "UPS shipping and logistics services",
        "industries": ["logistics", "other"],
    },
    {
        "id": "dhl",
        "name": "DHL",
        "category": "shipping",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "DHL API Key", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.dhl.com/location-finder/v1/find-by-address?countryCode=US",
            "headers": {"DHL-API-Key": "{api_key}"},
        },
        "tier": 1,
        "description": "DHL shipping and logistics services",
        "industries": ["logistics", "other"],
    },
    # ===== Communication =====
    {
        "id": "slack",
        "name": "Slack",
        "category": "communication",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "bot_token", "label": "Slack Bot Token (xoxb-...)", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://slack.com/api/auth.test",
            "headers": {"Authorization": "Bearer {bot_token}"},
        },
        "tier": 1,
        "description": "Team communication and collaboration platform",
        "industries": ["saas", "ecommerce", "logistics", "other"],
    },
    {
        "id": "notion",
        "name": "Notion",
        "category": "communication",
        "auth_type": "bearer",
        "auth_schema": {
            "fields": [{"name": "api_key", "label": "Notion Integration Token", "type": "password", "required": True}]
        },
        "test_config": {
            "method": "GET",
            "url": "https://api.notion.com/v1/users/me",
            "headers": {
                "Authorization": "Bearer {api_key}",
                "Notion-Version": "2022-06-28",
            },
        },
        "tier": 2,
        "description": "All-in-one workspace for notes, docs, and collaboration",
        "industries": ["saas", "other"],
    },
]


# --- Pydantic Models ---

class ConnectRequest(BaseModel):
    integration_id: str
    auth_type: str
    credentials: dict


class DisconnectRequest(BaseModel):
    integration_id: str


class TestIntegrationRequest(BaseModel):
    integration_id: str


# --- Routes ---

@router.get("/catalog")
def get_catalog(industry: str = None):
    """Get integration catalog, optionally filtered by industry."""
    if industry and industry != "other":
        filtered = [i for i in INTEGRATION_CATALOG if industry in i["industries"]]
        return {"integrations": filtered, "total": len(filtered)}
    return {"integrations": INTEGRATION_CATALOG, "total": len(INTEGRATION_CATALOG)}


@router.post("/connect")
def connect_integration(
    req: ConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Connect an integration by storing encrypted credentials."""
    # Find the integration in the catalog
    integration = next((i for i in INTEGRATION_CATALOG if i["id"] == req.integration_id), None)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{req.integration_id}' not found in catalog",
        )

    # Encrypt credentials
    creds_json = json.dumps(req.credentials)
    encrypted = encrypt_data(creds_json)

    # Determine last 4 chars from the first credential value
    first_value = next(iter(req.credentials.values()), "")
    last_4 = first_value[-4:] if len(first_value) >= 4 else first_value

    # Check if already connected
    existing = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.integration_id == req.integration_id,
        )
        .first()
    )

    if existing:
        # Update existing
        existing.encrypted_data = encrypted
        existing.auth_type = req.auth_type
        existing.last_4_chars = last_4
        existing.status = "active"
        existing.last_tested_at = datetime.utcnow()
        existing.integration_name = integration["name"]
        db.commit()
        db.refresh(existing)
        credential_id = existing.id
    else:
        # Create new
        cred = IntegrationCredential(
            tenant_id=current_user.tenant_id,
            integration_id=req.integration_id,
            integration_name=integration["name"],
            auth_type=req.auth_type,
            encrypted_data=encrypted,
            status="active",
            last_tested_at=datetime.utcnow(),
            last_4_chars=last_4,
        )
        db.add(cred)
        db.commit()
        db.refresh(cred)
        credential_id = cred.id

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="integration.connected",
        actor=current_user.email,
        resource_type="integration",
        resource_id=req.integration_id,
        details=json.dumps({"integration_name": integration["name"]}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Integration '{integration['name']}' connected successfully",
        "integration_id": req.integration_id,
        "credential_id": credential_id,
        "masked_key": mask_key(first_value),
        "status": "active",
    }


@router.post("/disconnect")
def disconnect_integration(
    req: DisconnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect an integration."""
    cred = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.integration_id == req.integration_id,
        )
        .first()
    )

    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )

    cred.status = "disconnected"

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="integration.disconnected",
        actor=current_user.email,
        resource_type="integration",
        resource_id=req.integration_id,
        details=json.dumps({"integration_name": cred.integration_name}),
        severity="warning",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Integration '{cred.integration_name}' disconnected",
        "integration_id": req.integration_id,
        "status": "disconnected",
    }


@router.post("/test")
async def test_integration(
    req: TestIntegrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test an integration connection using the ExternalToolBus.

    Phase 15: Now uses ExternalToolBus with:
    - 3x exponential backoff retry
    - Circuit breaker (auto-open after 5 failures)
    - Response caching
    - Structured error propagation with degraded data fallback
    """
    cred = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.integration_id == req.integration_id,
        )
        .first()
    )

    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not connected",
        )

    # Find integration config
    integration = next((i for i in INTEGRATION_CATALOG if i["id"] == req.integration_id), None)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not in catalog")

    # Decrypt credentials
    try:
        creds_json = decrypt_data(cred.encrypted_data)
        credentials = json.loads(creds_json)
    except Exception as e:
        return {"success": False, "error": f"Failed to decrypt credentials: {str(e)}"}

    # Build test request
    test_config = integration.get("test_config", {})
    method = test_config.get("method", "GET")
    url_template = test_config.get("url", "")
    headers_template = test_config.get("headers", {})

    # Replace placeholders in URL
    url = url_template
    for key, value in credentials.items():
        url = url.replace(f"{{{key}}}", str(value))

    # Replace placeholders in headers
    headers = {}
    for h_key, h_val in headers_template.items():
        val = h_val
        for c_key, c_value in credentials.items():
            val = val.replace(f"{{{c_key}}}", str(c_value))
        headers[h_key] = val

    # Handle basic auth
    auth = None
    auth_config = test_config.get("auth")
    if auth_config:
        auth_user = auth_config.get("username", "")
        auth_pass = auth_config.get("password", "")
        for c_key, c_value in credentials.items():
            auth_user = auth_user.replace(f"{{{c_key}}}", str(c_value))
            auth_pass = auth_pass.replace(f"{{{c_key}}}", str(c_value))
        auth = (auth_user, auth_pass) if auth_user else None

    # Handle POST body
    body = None
    if method.upper() == "POST":
        body = test_config.get("body", "")
        for c_key, c_value in credentials.items():
            body = body.replace(f"{{{c_key}}}", str(c_value))

    # Use ExternalToolBus for the call (Phase 15)
    bus = get_tool_bus()
    result = await bus.call(
        integration_id=req.integration_id,
        method=method,
        url=url,
        headers=headers,
        auth=auth,
        body=body,
        data_type="realtime",
        use_cache=False,  # Don't cache test calls
        tenant_id=current_user.tenant_id,
        actor=current_user.email,
        db=db,
    )

    # Update credential status based on result
    if result.get("success"):
        cred.last_tested_at = datetime.utcnow()
        cred.status = "active"
        db.commit()

        return {
            "success": True,
            "status_code": result.get("status_code"),
            "message": "Connection successful",
            "from_cache": result.get("from_cache", False),
        }
    else:
        cred.last_tested_at = datetime.utcnow()
        # Only set error status if it's not a retriable/circuit issue
        error_code = result.get("error", "unknown")
        if error_code not in ["circuit_open", "all_retries_failed"]:
            cred.status = "error"
        db.commit()

        response = {
            "success": False,
            "error": error_code,
            "message": result.get("message", "Connection test failed"),
            "is_retriable": result.get("is_retriable", False),
        }
        if result.get("degraded"):
            response["degraded"] = True
            response["data_age"] = result.get("data_age")
        if result.get("retry_attempts"):
            response["retry_attempts"] = result.get("retry_attempts")
        return response


@router.get("/health")
def get_integration_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get integration health status including circuit breaker states.

    Phase 15: Now includes actual circuit breaker state from ExternalToolBus.
    """
    from app.services.external_tool_bus import get_tool_bus

    creds = (
        db.query(IntegrationCredential)
        .filter(IntegrationCredential.tenant_id == current_user.tenant_id)
        .all()
    )

    bus = get_tool_bus()
    circuit_states = bus.get_circuit_states()
    cache_stats = bus.get_cache_stats()

    health_data = []
    for cred in creds:
        circuit_info = circuit_states.get(cred.integration_id, {})
        health_data.append({
            "integration_id": cred.integration_id,
            "integration_name": cred.integration_name,
            "status": cred.status,
            "last_tested_at": cred.last_tested_at.isoformat() if cred.last_tested_at else None,
            "circuit_breaker": circuit_info.get("state", "closed" if cred.status == "active" else "open"),
            "circuit_breaker_failures": circuit_info.get("failure_count", 0),
            "rate_limit": "normal",
        })

    return {
        "integrations": health_data,
        "total": len(health_data),
        "healthy": sum(1 for h in health_data if h["status"] == "active"),
        "unhealthy": sum(1 for h in health_data if h["status"] != "active"),
        "circuit_breaker_summary": {
            "total_tracked": len(circuit_states),
            "open": sum(1 for c in circuit_states.values() if c.get("state") == "open"),
            "half_open": sum(1 for c in circuit_states.values() if c.get("state") == "half_open"),
            "closed": sum(1 for c in circuit_states.values() if c.get("state") == "closed"),
        },
        "cache_summary": cache_stats,
    }


@router.get("/list")
def list_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List connected integrations for the tenant."""
    creds = (
        db.query(IntegrationCredential)
        .filter(IntegrationCredential.tenant_id == current_user.tenant_id)
        .all()
    )

    integrations = []
    for cred in creds:
        integrations.append({
            "id": cred.id,
            "integration_id": cred.integration_id,
            "integration_name": cred.integration_name,
            "auth_type": cred.auth_type,
            "status": cred.status,
            "last_4_chars": cred.last_4_chars,
            "last_tested_at": cred.last_tested_at.isoformat() if cred.last_tested_at else None,
        })

    return {"integrations": integrations, "total": len(integrations)}
