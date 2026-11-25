"""
PARWA Superglue Systems Router — Onboarding integration connections.

Replaces the removed Nango OAuth layer. Lets users connect their external
apps (Shopify, Gmail, Slack, HubSpot, etc.) via Superglue during onboarding
Step 2 and from the /dashboard/integrations page.

For CRM systems, also registers an MCPConnection record so PARWA's 8-node
pipeline can access the CRM on every ticket.

Endpoints:
- GET    /api/superglue/systems/catalog   — Curated list of popular systems to connect
- GET    /api/superglue/systems           — List tenant's connected systems
- POST   /api/superglue/systems           — Connect a new system (+ MCPConnection if CRM)
- GET    /api/superglue/systems/{id}      — Get one connected system
- POST   /api/superglue/systems/{id}/verify — Verify connection + MCP registration
- DELETE /api/superglue/systems/{id}      — Disconnect a system (+ remove MCPConnection)

BC-001: All operations scoped to authenticated user's company_id (tenant isolation).
        System IDs are namespaced as tenant_{company_id}__{system_id} in Superglue.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import superglue_client
from app.logger import get_logger
from database.base import get_db
from database.models.core import User
from database.models.integration import MCPConnection, Integration, DBConnection
from shared.utils.token_encryption import encrypt_token, decrypt_token


router = APIRouter(prefix="/api/superglue", tags=["superglue-systems"])

logger = get_logger("superglue_systems_api")


# ── Curated catalog (replaces Nango's 6-provider list) ────────────────
# These are popular systems PARWA customers commonly connect. Users can
# also connect ANY custom system via the POST endpoint with a custom URL.
#
# Auth types:
#   "oauth"    → Require a provider-issued access token until the OAuth callback is implemented.
#   "api_key"  → Show URL + API Key form (+ optional extra_fields per system)
#   "database" → Show host/port/db/user/pass form (+ optional extra_fields for Snowflake/BigQuery)
#   "smtp"     → Show SMTP form (host + port + user + pass for custom email)
#
# auth_schema: list of extra fields to show BEFORE the standard API Key field.
#   Each field: {"key": "field_name", "label": "Label", "type": "text|email|password", "required": bool, "placeholder": "..."}

POPULAR_SYSTEMS: List[Dict[str, Any]] = [
    # ── CRM (OAuth + API key mix) ──
    {"id": "hubspot",      "name": "HubSpot",           "icon": "🎯", "url_hint": "https://api.hubapi.com",         "category": "CRM",           "auth_type": "oauth"},
    {"id": "salesforce",   "name": "Salesforce",        "icon": "☁️", "url_hint": "https://login.salesforce.com",   "category": "CRM",           "auth_type": "oauth"},
    {"id": "zendesk",      "name": "Zendesk",           "icon": "🎫", "url_hint": "https://{subdomain}.zendesk.com/api/v2", "category": "Helpdesk", "auth_type": "api_key",
     "auth_schema": [
         {"key": "subdomain", "label": "Subdomain", "type": "text", "required": True, "placeholder": "mycompany"},
         {"key": "email", "label": "Email", "type": "email", "required": True, "placeholder": "admin@company.com"},
     ]},
    {"id": "freshdesk",    "name": "Freshdesk",         "icon": "🎫", "url_hint": "https://{domain}.freshdesk.com/api/v2", "category": "Helpdesk", "auth_type": "api_key",
     "auth_schema": [
         {"key": "domain", "label": "Domain", "type": "text", "required": True, "placeholder": "mycompany.freshdesk.com"},
     ]},
    {"id": "zoho",         "name": "Zoho CRM",          "icon": "🏢", "url_hint": "https://www.zohoapis.com/crm/v2", "category": "CRM",        "auth_type": "oauth"},
    {"id": "pipedrive",    "name": "Pipedrive",         "icon": "🔄", "url_hint": "https://api.pipedrive.com",      "category": "CRM",           "auth_type": "api_key"},

    # ── E-commerce ──
    {"id": "shopify",      "name": "Shopify",           "icon": "🛒", "url_hint": "https://{store}.myshopify.com", "category": "E-commerce",    "auth_type": "oauth",
     "auth_schema": [
         {"key": "store", "label": "Store subdomain", "type": "text", "required": True, "placeholder": "mystore"},
     ]},

    # ── Email (OAuth + API key + SMTP mix) ──
    {"id": "gmail",        "name": "Gmail",             "icon": "📧", "url_hint": "https://gmail.googleapis.com",   "category": "Email",         "auth_type": "oauth"},
    {"id": "brevo",        "name": "Brevo",             "icon": "📧", "url_hint": "https://api.brevo.com",          "category": "Email",         "auth_type": "api_key"},
    {"id": "sendgrid",     "name": "SendGrid",          "icon": "📧", "url_hint": "https://api.sendgrid.com",       "category": "Email",         "auth_type": "api_key"},
    {"id": "custom-smtp",  "name": "Custom SMTP",       "icon": "✉️", "url_hint": "",                               "category": "Email",         "auth_type": "smtp"},

    # ── Payments ──
    {"id": "stripe",       "name": "Stripe",            "icon": "💳", "url_hint": "https://api.stripe.com",         "category": "Payments",      "auth_type": "api_key"},
    {"id": "razorpay",     "name": "Razorpay",          "icon": "💰", "url_hint": "https://api.razorpay.com",       "category": "Payments",      "auth_type": "api_key",
     "auth_schema": [
         {"key": "key_id", "label": "Key ID", "type": "text", "required": True, "placeholder": "rzp_live_xxx"},
     ]},
    {"id": "paypal",       "name": "PayPal",            "icon": "💳", "url_hint": "https://api.paypal.com",         "category": "Payments",      "auth_type": "oauth"},

    # ── Communication ──
    {"id": "slack",        "name": "Slack",             "icon": "💬", "url_hint": "https://slack.com/api",          "category": "Communication", "auth_type": "oauth"},
    {"id": "twilio",       "name": "Twilio",            "icon": "📱", "url_hint": "https://api.twilio.com",         "category": "Communication", "auth_type": "api_key",
     "auth_schema": [
         {"key": "account_sid", "label": "Account SID", "type": "text", "required": True, "placeholder": "ACxxx"},
     ]},

    # ── Dev Tools / Productivity ──
    {"id": "github",       "name": "GitHub",            "icon": "🐙", "url_hint": "https://api.github.com",         "category": "Dev Tools",     "auth_type": "oauth"},
    {"id": "notion",       "name": "Notion",            "icon": "📝", "url_hint": "https://api.notion.com/v1",      "category": "Productivity",  "auth_type": "oauth"},
    {"id": "jira",         "name": "Jira",              "icon": "🟦", "url_hint": "https://{subdomain}.atlassian.net", "category": "Project Management", "auth_type": "oauth",
     "auth_schema": [
         {"key": "subdomain", "label": "Atlassian site", "type": "text", "required": True, "placeholder": "mycompany"},
     ]},
    {"id": "google-analytics", "name": "Google Analytics", "icon": "📊", "url_hint": "https://analyticsreporting.googleapis.com", "category": "Analytics", "auth_type": "oauth"},

    # ── Databases (standard host/port form) ──
    {"id": "postgres",     "name": "PostgreSQL",        "icon": "🗄️", "url_hint": "", "category": "Database",       "auth_type": "database", "db_type": "postgresql"},
    {"id": "mysql",        "name": "MySQL",             "icon": "🗄️", "url_hint": "", "category": "Database",       "auth_type": "database", "db_type": "mysql"},
    {"id": "mongodb",      "name": "MongoDB",           "icon": "🍃", "url_hint": "", "category": "Database",       "auth_type": "database", "db_type": "mongodb"},
    {"id": "supabase-db",  "name": "Supabase Database", "icon": "⚡", "url_hint": "", "category": "Database",       "auth_type": "database", "db_type": "postgresql"},

    # ── Data Warehouses (database form + extra fields) ──
    {"id": "snowflake",    "name": "Snowflake",         "icon": "❄️", "url_hint": "", "category": "Data Warehouse", "auth_type": "database", "db_type": "snowflake",
     "auth_schema": [
         {"key": "account", "label": "Account", "type": "text", "required": True, "placeholder": "xy12345.us-east-1"},
         {"key": "warehouse", "label": "Warehouse", "type": "text", "required": True, "placeholder": "COMPUTE_WH"},
         {"key": "schema", "label": "Schema", "type": "text", "required": False, "placeholder": "PUBLIC"},
     ]},
    {"id": "bigquery",     "name": "BigQuery",          "icon": "📊", "url_hint": "", "category": "Data Warehouse", "auth_type": "database", "db_type": "bigquery",
     "auth_schema": [
         {"key": "project_id", "label": "Project ID", "type": "text", "required": True, "placeholder": "my-gcp-project"},
         {"key": "credentials_json", "label": "Service Account JSON", "type": "textarea", "required": True, "placeholder": "{...}"},
     ]},

    # ── Custom (user-defined — works for ANY system) ──
    {"id": "custom",       "name": "Custom System",      "icon": "🔌", "url_hint": "", "category": "Custom",        "auth_type": "api_key"},
]

# Systems that are CRM-type — these get an MCPConnection record so the
# 8-node pipeline can access them on every ticket.
CRM_SYSTEM_IDS = {"hubspot", "zendesk", "salesforce", "freshdesk", "zoho", "pipedrive", "custom"}

# Systems that are database-type — these get a DBConnection record +
# Superglue auto-reads the schema + generates query tools.
DATABASE_SYSTEM_IDS = {"postgres", "mysql", "mongodb", "snowflake", "bigquery", "supabase-db"}


# ── Pydantic models ───────────────────────────────────────────────────

class CreateSystemRequest(BaseModel):
    system_id: str = Field(..., description="System type ID (e.g. 'shopify', 'postgres') or custom slug")
    name: str = Field(..., description="Human-readable name (e.g. 'My Shopify Store', 'Payment Database')")
    url: str = Field(default="", description="Base URL of the external system (empty for databases)")
    credentials: Optional[Dict[str, Any]] = Field(default=None, description="Auth credentials (api_key, token, etc.)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Freeform metadata")
    icon: str = Field(default="", description="Emoji icon")
    specific_instructions: str = Field(default="", description="Notes for Superglue's LLM")
    # Database-specific fields (only used when system_id is in DATABASE_SYSTEM_IDS)
    db_type: Optional[str] = Field(default=None, description="Database type: postgresql, mysql, mongodb, snowflake, bigquery")
    db_host: Optional[str] = Field(default=None, description="Database host (e.g. mydb.company.com)")
    db_port: Optional[int] = Field(default=None, description="Database port (e.g. 5432)")
    db_name: Optional[str] = Field(default=None, description="Database name")
    db_username: Optional[str] = Field(default=None, description="Database username (should be read-only)")
    db_password: Optional[str] = Field(default=None, description="Database password")


class SystemResponse(BaseModel):
    id: str
    name: str
    url: str
    icon: str = ""
    credentials: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ListSystemsResponse(BaseModel):
    success: bool
    systems: List[SystemResponse]
    count: int


class CatalogResponse(BaseModel):
    success: bool
    systems: List[Dict[str, Any]]


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/systems/catalog", response_model=CatalogResponse)
async def get_catalog() -> CatalogResponse:
    """List popular systems users can connect (curated catalog).

    No auth required — this is just a static catalog for the UI.
    """
    return CatalogResponse(success=True, systems=POPULAR_SYSTEMS)


@router.get("/systems", response_model=ListSystemsResponse)
async def list_systems(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ListSystemsResponse:
    """List this tenant's locally registered integrations without leaking other tenants."""
    tenant_id = str(user.company_id)
    shared_ids = {item["id"] for item in POPULAR_SYSTEMS if item["id"] != "custom"}
    rows = db.query(Integration).filter(
        Integration.company_id == tenant_id,
    ).order_by(Integration.created_at.asc()).all()

    systems = []
    for row in rows:
        is_shared = row.integration_type in shared_ids
        result = await superglue_client.get_system(
            row.integration_type,
            tenant_id=tenant_id,
        )
        data = result.get("data", {}) if result.get("success") else {}
        metadata = dict(data.get("metadata") or {})
        metadata["local_status"] = row.status
        systems.append(SystemResponse(
            id=row.integration_type,
            name=data.get("name") or row.name or row.integration_type,
            url=data.get("url") or "",
            icon=data.get("icon") or "",
            credentials={},
            metadata=metadata,
            created_at=data.get("createdAt") or row.created_at,
            updated_at=data.get("updatedAt") or row.updated_at,
        ))
    return ListSystemsResponse(success=True, systems=systems, count=len(systems))


@router.post("/systems", response_model=SystemResponse, status_code=201)
async def create_system(
    req: CreateSystemRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemResponse:
    """Connect a new system via Superglue.

    For CRM-type systems: also creates an MCPConnection record.
    For database-type systems: also creates a DBConnection record (read-only enforced).
    For ALL systems: creates an Integration record (local tracking).

    BC-001: Scoped to user's company_id. System ID is namespaced as
    tenant_{company_id}__{system_id} to prevent cross-tenant access.
    """
    if not superglue_client.is_configured():
        raise HTTPException(status_code=503, detail="Superglue is not configured on the server")

    tenant_id = str(user.company_id)
    is_database = req.system_id in DATABASE_SYSTEM_IDS

    system_definition = next(
        (item for item in POPULAR_SYSTEMS if item["id"] == req.system_id),
        {},
    )
    auth_type = system_definition.get("auth_type", "api_key")
    if req.metadata is None:
        req.metadata = {}
    # The server-side catalog is authoritative; callers cannot downgrade an
    # OAuth provider into an API-key integration by changing request metadata.
    req.metadata["auth_type"] = auth_type
    has_provider_credentials = any(
        str(value).strip() for value in (req.credentials or {}).values() if value is not None
    )
    if not is_database and auth_type != "oauth" and not has_provider_credentials:
        raise HTTPException(
            status_code=422,
            detail="Provider credentials are required for this integration.",
        )

    # For databases, build the URL + credentials from the DB-specific fields
    if is_database:
        db_type = req.db_type or "postgresql"
        missing_database_fields = (
            not req.db_host
            or not req.db_name
            or (db_type != "bigquery" and not req.db_username)
        )
        if missing_database_fields:
            raise HTTPException(
                status_code=400,
                detail="Database connections require host and database name; username is also required except for BigQuery service accounts.",
            )
        # Superglue resolves <<systemId_secretName>> placeholders from the
        # tenant-owned encrypted connection. Never embed DB passwords in URLs.
        db_port = req.db_port or (443 if db_type in {"snowflake", "bigquery"} else 5432)
        db_credentials = dict(req.credentials or {})
        db_credentials.update({
            "db_type": db_type,
            "host": req.db_host,
            "port": db_port,
            "database": req.db_name,
            "username": req.db_username or "",
            "password": req.db_password or "",
            "readonly": True,
        })
        if db_type in {"postgres", "postgresql"}:
            req.url = (
                f"postgresql://<<{req.system_id}_username>>:<<{req.system_id}_password>>"
                f"@{req.db_host}:{db_port}/{req.db_name}"
            )
        elif db_type == "mysql":
            req.url = (
                f"mysql://<<{req.system_id}_username>>:<<{req.system_id}_password>>"
                f"@{req.db_host}:{db_port}/{req.db_name}"
            )
        elif db_type == "mongodb":
            req.url = (
                f"mongodb://<<{req.system_id}_username>>:<<{req.system_id}_password>>"
                f"@{req.db_host}:{db_port}/{req.db_name}?authSource=admin"
            )
        elif db_type == "snowflake":
            db_credentials["account"] = req.db_host
            db_credentials["warehouse"] = db_credentials.get("warehouse", "")
            db_credentials["schema"] = db_credentials.get("schema", "")
            req.url = (
                f"snowflake://<<{req.system_id}_username>>:<<{req.system_id}_password>>"
                f"@<<{req.system_id}_account>>/?warehouse=<<{req.system_id}_warehouse>>"
                f"&database={req.db_name}&schema=<<{req.system_id}_schema>>"
            )
        elif db_type == "bigquery":
            req.url = f"bigquery://<<{req.system_id}_project_id>>"
        else:
            raise HTTPException(status_code=422, detail="Unsupported database connector type")
        req.credentials = db_credentials
        # Tell Superglue this is a database — it will auto-read the schema
        if not req.metadata:
            req.metadata = {}
        req.metadata["system_type"] = "database"
        req.metadata["db_type"] = db_type

    # Provision a separate Superglue service account for each tenant. The
    # global admin token must never own customer credentials or OAuth tokens.
    from app.core.superglue_tenant_accounts import get_or_create_tenant_account
    tenant_account = await get_or_create_tenant_account(db, tenant_id)
    if not tenant_account.get("success"):
        raise HTTPException(
            status_code=503,
            detail=tenant_account.get("error", "Could not provision integration credentials"),
        )

    if not req.metadata:
        req.metadata = {}
    req.metadata["auth_type"] = auth_type

    shared_system_ids = {item["id"] for item in POPULAR_SYSTEMS if item["id"] != "custom"}
    is_shared_system = req.system_id in shared_system_ids
    if is_database:
        # The shared system definition is generic; the tenant-specific URL
        # and credentials are stored on that tenant's service-account connection.
        definition_url = f"{req.db_type or 'postgresql'}://localhost:{req.db_port or 5432}/{req.db_name}"
    else:
        definition_url = system_definition.get("url_hint") or req.url

    result = await superglue_client.create_system(
        system_id=req.system_id,
        name=system_definition.get("name") or req.name,
        url=definition_url,
        tenant_id=tenant_id,
        credentials=req.credentials,
        metadata=req.metadata,
        icon=req.icon or system_definition.get("icon", ""),
        specific_instructions=req.specific_instructions,
        customer_api_key=tenant_account["api_key"],
        credential_url=req.url,
        template_id=req.system_id if is_shared_system and auth_type in {"oauth", "api_key"} else None,
    )
    if not result.get("success"):
        raw_error = str(result.get("error", "unknown"))
        logger.error(
            "superglue_create_failed system=%s tenant=%s error=%.300s",
            req.system_id, tenant_id, raw_error,
        )
        # Upstream failures can be entire HTML error pages — never show those
        # to users. Log the full detail, return one clean readable line.
        if "<" in raw_error and ">" in raw_error:
            detail = "The integration service is temporarily unavailable. Please try again in a few minutes."
        else:
            detail = f"Could not connect {req.name}: {raw_error[:200]}"
        raise HTTPException(status_code=502, detail=detail)

    # Save EVERY connection to the Integration table (local DB record).
    _upsert_integration(
        db=db,
        company_id=tenant_id,
        integration_type=req.system_id,
        name=req.name,
        credentials=req.credentials,
        settings=req.metadata or {},
        status="pending_oauth" if auth_type == "oauth" else "pending",
    )

    # If this is a CRM system, ALSO register an MCPConnection
    is_crm = req.system_id in CRM_SYSTEM_IDS or (req.metadata or {}).get("is_crm", False)
    if is_crm:
        _upsert_mcp_connection(
            db=db,
            company_id=tenant_id,
            name=req.name,
            server_url=req.url,
            auth_token=(req.credentials.get("api_key") or req.credentials.get("access_token") or req.credentials.get("token")) if req.credentials else None,
            system_id=req.system_id,
            # MCP must not expose an API-key integration until the provider
            # health check has succeeded.
            status="pending_oauth" if auth_type == "oauth" else "pending",
        )

    # If this is a database, ALSO save to DBConnection table (read-only enforced)
    if is_database:
        db_conn = _upsert_db_connection(
            db=db,
            company_id=tenant_id,
            name=req.name,
            db_type=req.db_type or "postgresql",
            db_host=req.db_host,
            db_port=db_port,
            db_name=req.db_name,
            db_username=req.db_username,
            db_password=req.db_password,
            system_id=req.system_id,
            connection_config=req.credentials,
        )
        # Schema discovery is part of connection setup, not a later manual step.
        schema_discovery = await _discover_db_schema_for_connection(
            db=db,
            db_conn=db_conn,
            tenant_id=tenant_id,
            connection_config=req.credentials,
        )

    data = result.get("data", {})
    response_metadata = dict(data.get("metadata") or req.metadata or {})
    if is_database:
        response_metadata["schema_discovery"] = {
            "status": "verified" if schema_discovery.get("success") else "pending",
            "table_count": len((schema_discovery.get("schema") or {}).get("tables", [])),
            "error": schema_discovery.get("error"),
        }
    return SystemResponse(
        id=req.system_id,  # return the clean (non-namespaced) ID
        name=data.get("name", req.name),
        url=data.get("url", req.url),
        icon=data.get("icon", req.icon),
        credentials={},
        metadata=response_metadata,
        created_at=data.get("createdAt") or data.get("created_at"),
        updated_at=data.get("updatedAt") or data.get("updated_at"),
    )


@router.get("/systems/{system_id}", response_model=SystemResponse)
async def get_system(
    system_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemResponse:
    """Get details of one connected system after tenant ownership validation."""
    tenant_id = str(user.company_id)
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    is_shared = system_id in {item["id"] for item in POPULAR_SYSTEMS if item["id"] != "custom"}
    result = await superglue_client.get_system(
        system_id,
        tenant_id=tenant_id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "System not found"))

    data = result.get("data", {})
    return SystemResponse(
        id=system_id,
        name=data.get("name", ""),
        url=data.get("url", ""),
        icon=data.get("icon", ""),
        credentials={},
        metadata=data.get("metadata", {}),
        created_at=data.get("createdAt") or data.get("created_at"),
        updated_at=data.get("updatedAt") or data.get("updated_at"),
    )


@router.delete("/systems/{system_id}")
async def delete_system(
    system_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Disconnect a system (delete from Superglue + remove MCPConnection if CRM)."""
    tenant_id = str(user.company_id)
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    is_shared = system_id in {item["id"] for item in POPULAR_SYSTEMS if item["id"] != "custom"}
    result = (
        await superglue_client.delete_tenant_credentials(system_id, tenant_id)
        if is_shared
        else await superglue_client.delete_system(system_id, tenant_id=tenant_id)
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error", "Could not revoke integration credentials"),
        )

    integration_name = integration.name
    db.delete(integration)
    db.commit()

    # Also remove the MCPConnection record if this was a CRM
    if system_id in CRM_SYSTEM_IDS:
        mcp = db.query(MCPConnection).filter(
            MCPConnection.company_id == tenant_id,
            MCPConnection.name.like(f"%({system_id})"),
        ).first()
        if mcp:
            db.delete(mcp)
            db.commit()

    # Also remove the DBConnection record if this was a database
    if system_id in DATABASE_SYSTEM_IDS:
        db_conn = db.query(DBConnection).filter(
            DBConnection.company_id == tenant_id,
            DBConnection.name == integration_name,
        ).first()
        if db_conn:
            db.delete(db_conn)
            db.commit()

    return {"success": True}


# ── Verify endpoint ────────────────────────────────────────────────────


class VerifyResponse(BaseModel):
    verified: bool
    superglue_ok: bool
    mcp_registered: bool
    system_id: str
    name: str
    url: str
    message: str


@router.post("/systems/{system_id}/verify", response_model=VerifyResponse)
async def verify_system(
    system_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerifyResponse:
    """Check Superglue registration AND previously verified provider access.

    A Superglue system record alone is not proof that provider credentials work.
    The /test endpoint performs the real provider/database check and marks the
    local Integration/DBConnection record verified.
    """
    tenant_id = str(user.company_id)
    sg_result = await superglue_client.get_system(system_id, tenant_id=tenant_id)
    if not sg_result.get("success"):
        return VerifyResponse(
            verified=False,
            superglue_ok=False,
            mcp_registered=False,
            system_id=system_id,
            name="",
            url="",
            message=f"System not found in Superglue: {sg_result.get('error', 'unknown')}",
        )

    data = sg_result.get("data", {})
    name = data.get("name", system_id)
    url = data.get("url", "")
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()

    if system_id in DATABASE_SYSTEM_IDS:
        db_conn = db.query(DBConnection).filter(
            DBConnection.company_id == tenant_id,
            DBConnection.name == (integration.name if integration else ""),
        ).first()
        provider_verified = bool(db_conn and db_conn.status == "verified" and db_conn.schema_analysis)
    else:
        provider_verified = bool(
            integration and integration.status in ("active", "verified")
        )

    is_crm = system_id in CRM_SYSTEM_IDS
    mcp_registered = False
    if is_crm and provider_verified:
        mcp = db.query(MCPConnection).filter(
            MCPConnection.company_id == tenant_id,
            MCPConnection.name.like(f"%({system_id})"),
        ).first()
        if not mcp:
            credentials = IntegrationService._parse_json(
                integration.credentials_encrypted if integration else None
            ) or {}
            auth_token = (
                credentials.get("api_key")
                or credentials.get("access_token")
                or credentials.get("token")
            )
            _upsert_mcp_connection(
                db=db,
                company_id=tenant_id,
                name=name,
                server_url=url,
                auth_token=auth_token,
                system_id=system_id,
            )
            mcp = db.query(MCPConnection).filter(
                MCPConnection.company_id == tenant_id,
                MCPConnection.name.like(f"%({system_id})"),
            ).first()
        mcp_registered = mcp is not None

    verified = bool(provider_verified and (not is_crm or mcp_registered))
    message = (
        "Provider credentials and local connection records are verified."
        if verified else
        "System exists in Superglue, but provider credentials or database schema have not been verified. Run the connection test first."
    )
    return VerifyResponse(
        verified=verified,
        superglue_ok=True,
        mcp_registered=mcp_registered,
        system_id=system_id,
        name=name,
        url=url,
        message=message,
    )


# ── Helper: upsert MCPConnection ──────────────────────────────────────


def _upsert_mcp_connection(
    db: Session,
    company_id: str,
    name: str,
    server_url: str,
    auth_token: Optional[str],
    system_id: str,
    status: str = "connected",
) -> MCPConnection:
    """Create or update an MCPConnection record for a CRM system.

    The name is stored as "{display_name} ({system_id})" so we can find
    it later by system_id suffix.
    """
    full_name = f"{name} ({system_id})"
    # Find existing by company + name suffix
    mcp = db.query(MCPConnection).filter(
        MCPConnection.company_id == company_id,
        MCPConnection.name == full_name,
    ).first()

    if mcp:
        # Update existing
        mcp.server_url = server_url
        if auth_token:
            mcp.auth_token_encrypted = encrypt_token(auth_token)
        mcp.status = status
        mcp.capabilities = json.dumps(["crm"])
    else:
        # Create new
        mcp = MCPConnection(
            company_id=company_id,
            name=full_name,
            server_url=server_url,
            auth_token_encrypted=encrypt_token(auth_token) if auth_token else None,
            status=status,
            capabilities=json.dumps(["crm"]),
        )
        db.add(mcp)

    db.commit()
    db.refresh(mcp)
    return mcp


def _set_mcp_connection_status(
    db: Session,
    integration: Optional[Integration],
    system_id: str,
    status: str,
) -> None:
    if not integration:
        return
    connection = db.query(MCPConnection).filter(
        MCPConnection.company_id == str(integration.company_id),
        MCPConnection.name == f"{integration.name} ({system_id})",
    ).first()
    if connection:
        connection.status = status
        db.commit()


# ── Helper: upsert Integration (local DB record for every connection) ──


def _upsert_integration(
    db: Session,
    company_id: str,
    integration_type: str,
    name: str,
    credentials: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
    status: str = "connected",
) -> Integration:
    """Create or update an Integration record.

    Every Superglue connection (CRM and non-CRM) is recorded here so PARWA
    can query a tenant's integrations locally without calling Superglue.
    This persists across logins — when the user comes back, their
    integrations are still listed.

    The (company_id, integration_type) pair is the natural key — if a
    tenant reconnects the same integration type, we update instead of
    creating a duplicate.
    """
    integration = db.query(Integration).filter(
        Integration.company_id == company_id,
        Integration.integration_type == integration_type,
    ).first()

    # Encrypt credentials if provided
    creds_encrypted = None
    if credentials is not None:
        # Store the whole credentials dict as encrypted JSON. An empty OAuth
        # dict intentionally clears any stale API-key credentials on reconnect.
        creds_encrypted = encrypt_token(json.dumps(credentials))

    settings_json = json.dumps(settings or {})

    if integration:
        # Update existing
        integration.name = name
        integration.status = status
        if credentials is not None:
            integration.credentials_encrypted = creds_encrypted
        integration.settings = settings_json
        integration.error_message = None
    else:
        # Create new
        integration = Integration(
            company_id=company_id,
            integration_type=integration_type,
            name=name,
            status=status,
            credentials_encrypted=creds_encrypted,
            settings=settings_json,
        )
        db.add(integration)

    db.commit()
    db.refresh(integration)
    return integration


# ── Managed OAuth: explicit customer consent, tenant-scoped credentials ──


class OAuthStartResponse(BaseModel):
    authorization_url: str


class OAuthStatusResponse(BaseModel):
    system_id: str
    connected: bool
    status: str
    message: str


@router.post("/systems/{system_id}/oauth/start", response_model=OAuthStartResponse)
async def start_system_oauth(
    system_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OAuthStartResponse:
    """Start a Superglue-managed OAuth exchange for the authenticated tenant."""
    tenant_id = str(user.company_id)
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration has not been created")

    definition = next((item for item in POPULAR_SYSTEMS if item["id"] == system_id), None)
    if not definition or definition.get("auth_type") != "oauth":
        raise HTTPException(status_code=400, detail="This integration does not use OAuth")

    result = await superglue_client.start_oauth_exchange(
        system_id=system_id,
        tenant_id=tenant_id,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error", "Could not start provider authorization"),
        )
    integration.status = "pending_oauth"
    integration.error_message = None
    db.commit()
    return OAuthStartResponse(authorization_url=result["authorization_url"])


@router.get("/systems/{system_id}/oauth/status", response_model=OAuthStatusResponse)
async def get_system_oauth_status(
    system_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OAuthStatusResponse:
    """Poll Superglue's tenant credential store; never expose OAuth tokens."""
    tenant_id = str(user.company_id)
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    result = await superglue_client.check_oauth_credentials(
        system_id=system_id,
        tenant_id=tenant_id,
    )
    connected = result.get("success") is True and result.get("connected") is True
    if connected:
        integration.status = "verified"
        integration.error_message = None
        integration.last_sync = datetime.now(timezone.utc)
        mcp_connection = db.query(MCPConnection).filter(
            MCPConnection.company_id == tenant_id,
            MCPConnection.name == f"{integration.name} ({system_id})",
        ).first()
        if mcp_connection:
            mcp_connection.status = "connected"
    elif integration.status != "verified":
        integration.status = "pending_oauth"
        integration.error_message = result.get("error")
    db.commit()

    return OAuthStatusResponse(
        system_id=system_id,
        connected=connected,
        status=integration.status,
        message=(
            "Provider account authorized and credentials stored securely"
            if connected else result.get("error") or "Waiting for provider authorization"
        ),
    )


# ── Test endpoint: real credential verification ───────────────────────


class TestResponse(BaseModel):
    system_id: str
    works: bool
    status_code: Optional[int] = None
    tested_at: str
    message: str
    sample_data: Optional[Dict[str, Any]] = None


@router.post("/systems/{system_id}/test", response_model=TestResponse)
async def test_system(
    system_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TestResponse:
    """Test that a connected system's credentials actually work.

    Makes a REAL HTTP GET request to the system's URL with the stored
    credentials. This is NOT a fake check — it confirms the API key/token
    actually authenticates against the real external API.

    Used by onboarding Step 2 to prevent users proceeding with broken
    integrations (wrong API key, wrong URL, expired token).

    Returns:
        works: True if the API responded successfully (200/201)
        status_code: the HTTP status code returned by the external API
        message: human-readable result
        sample_data: first 500 chars of the response (for debugging)
    """
    import httpx
    from datetime import datetime, timezone

    tenant_id = str(user.company_id)
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()
    if not integration:
        return TestResponse(
            system_id=system_id,
            works=False,
            tested_at=datetime.now(timezone.utc).isoformat(),
            message="Integration is not connected for this tenant",
        )
    is_shared = system_id in {item["id"] for item in POPULAR_SYSTEMS if item["id"] != "custom"}

    # 1. Get the shared provider definition or tenant-namespaced custom system.
    sg_result = await superglue_client.get_system(
        system_id,
        tenant_id=tenant_id,
    )
    if not sg_result.get("success"):
        return TestResponse(
            system_id=system_id,
            works=False,
            tested_at=datetime.now(timezone.utc).isoformat(),
            message=f"System not found in Superglue: {sg_result.get('error', 'unknown')}",
        )

    data = sg_result.get("data", {})
    system_url = data.get("url", "").rstrip("/")
    definition = next((item for item in POPULAR_SYSTEMS if item["id"] == system_id), {})
    if definition.get("auth_type") == "oauth":
        oauth_status = await superglue_client.check_oauth_credentials(
            system_id=system_id,
            tenant_id=tenant_id,
        )
        works = oauth_status.get("success") is True and oauth_status.get("connected") is True
        if integration:
            integration.status = "verified" if works else "pending_oauth"
            integration.error_message = None if works else oauth_status.get("error")
        if works:
            mcp_connection = db.query(MCPConnection).filter(
                MCPConnection.company_id == tenant_id,
                MCPConnection.name == f"{integration.name} ({system_id})",
            ).first() if integration else None
            if mcp_connection:
                mcp_connection.status = "connected"
        db.commit()
        return TestResponse(
            system_id=system_id,
            works=works,
            status_code=200 if works else None,
            tested_at=datetime.now(timezone.utc).isoformat(),
            message=(
                "OAuth account authorized and securely connected"
                if works else oauth_status.get("error") or "Complete provider authorization to verify this integration"
            ),
        )

    # Prefer the locally encrypted credentials; Superglue may redact secrets
    # when returning a system object.
    from app.services.integration_service import IntegrationService
    credentials = IntegrationService._parse_json(
        integration.credentials_encrypted if integration else None
    ) or {}

    tested_at = datetime.now(timezone.utc).isoformat()

    # ── DATABASE TEST: require real schema discovery ──
    if system_id in DATABASE_SYSTEM_IDS:
        db_conn = db.query(DBConnection).filter(
            DBConnection.company_id == tenant_id,
            DBConnection.name == integration.name,
        ).first() if integration else None

        if not db_conn:
            return TestResponse(
                system_id=system_id,
                works=False,
                tested_at=tested_at,
                message="Database connection record not found for this tenant",
            )

        discovery = await _discover_db_schema_for_connection(
            db=db, db_conn=db_conn, tenant_id=tenant_id
        )
        schema = discovery.get("schema") or {}
        works = bool(discovery.get("success"))
        return TestResponse(
            system_id=system_id,
            works=works,
            status_code=200 if works else None,
            tested_at=tested_at,
            message=(
                f"Database reachable; discovered {len(schema.get('tables', []))} tables"
                if works else f"Database schema discovery failed: {discovery.get('error', 'unknown error')}"
            ),
            sample_data={"db_type": db_conn.db_type, "schema_ready": works},
        )

    # ── Provider-specific credential test ──────────────────────────
    # A GET to an API root can return 200 without authenticating. Use the
    # integration catalog's real test endpoint for known providers.
    from app.core.integration_catalog import get_integration_by_key
    catalog_entry = get_integration_by_key(system_id)

    if catalog_entry:
        normalized = dict(credentials)
        token = (
            normalized.get("access_token")
            or normalized.get("api_key")
            or normalized.get("token")
            or normalized.get("api_token")
        )
        if system_id == "hubspot" and token:
            normalized["api_key"] = token
        elif system_id == "salesforce" and token:
            normalized["refresh_token"] = token
            normalized.setdefault("instance_url", system_url)
        elif system_id == "gmail" and token:
            normalized["refresh_token"] = token
        elif system_id == "shopify" and token:
            from urllib.parse import urlparse
            normalized["access_token"] = token
            normalized.setdefault("store_url", urlparse(system_url).netloc)
        elif system_id == "slack" and token:
            normalized["bot_token"] = token
        elif system_id in ("github", "notion") and token:
            normalized["api_key"] = token
        elif system_id == "zendesk":
            normalized["api_token"] = token or normalized.get("api_token", "")
            if not normalized.get("subdomain") and system_url:
                from urllib.parse import urlparse
                normalized["subdomain"] = urlparse(system_url).hostname.split(".")[0]
        elif system_id == "freshdesk":
            if not normalized.get("domain") and system_url:
                from urllib.parse import urlparse
                normalized["domain"] = urlparse(system_url).hostname.split(".")[0]
        elif system_id == "pipedrive" and token:
            normalized["api_token"] = token
            if not normalized.get("company_domain") and system_url:
                from urllib.parse import urlparse
                normalized["company_domain"] = urlparse(system_url).hostname.split(".")[0]
        elif system_id == "twilio" and token:
            normalized["auth_token"] = token

        test_result = await asyncio.to_thread(
            IntegrationService(db)._test_credentials, system_id, normalized
        )
        works = bool(test_result.get("success"))
        if integration:
            integration.last_sync = datetime.now(timezone.utc)
            integration.status = "verified" if works else "error"
            integration.error_message = None if works else str(test_result.get("message", "Provider test failed"))[:500]
            db.commit()
            if system_id in CRM_SYSTEM_IDS or (integration.settings or {}).get("is_crm"):
                _set_mcp_connection_status(db, integration, system_id, "connected" if works else "error")
        return TestResponse(
            system_id=system_id,
            works=works,
            status_code=200 if works else None,
            tested_at=tested_at,
            message=test_result.get("message", "Provider credential test failed"),
        )

    # Zoho uses a provider-specific authorization scheme and is not in the
    # shared catalog yet; do not fall back to an unauthenticated API-root GET.
    if system_id == "zoho":
        token = credentials.get("access_token") or credentials.get("api_key")
        if not token:
            return TestResponse(system_id=system_id, works=False, tested_at=tested_at, message="Zoho access token is missing")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://www.zohoapis.com/crm/v2/users?type=CurrentUser",
                    headers={"Authorization": f"Zoho-oauthtoken {token}", "Accept": "application/json"},
                )
            works = resp.status_code == 200
            if integration:
                integration.status = "verified" if works else "error"
                integration.error_message = None if works else f"Zoho returned HTTP {resp.status_code}"
                db.commit()
                _set_mcp_connection_status(db, integration, system_id, "connected" if works else "error")
            return TestResponse(
                system_id=system_id, works=works, status_code=resp.status_code,
                tested_at=tested_at,
                message="Connected to Zoho CRM" if works else f"Zoho authentication failed (HTTP {resp.status_code})",
            )
        except Exception as exc:
            return TestResponse(system_id=system_id, works=False, tested_at=tested_at, message=f"Zoho test failed: {str(exc)[:150]}")

    # Unknown/custom providers must not be marked verified by a root URL
    # returning HTTP 200. Require a provider-specific health-check definition
    # before enabling an agent to use this integration.
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()
    if integration:
        integration.status = "error"
        integration.error_message = "No provider-specific authenticated health check is configured"
        db.commit()
        if system_id in CRM_SYSTEM_IDS or (integration.settings or {}).get("is_crm"):
            _set_mcp_connection_status(db, integration, system_id, "error")

    return TestResponse(
        system_id=system_id,
        works=False,
        tested_at=tested_at,
        message="This provider has no authenticated connection test configured. It cannot be marked verified yet.",
    )


# ── Helper: upsert DBConnection (for database-type systems) ──────────


def _upsert_db_connection(
    db: Session,
    company_id: str,
    name: str,
    db_type: str,
    db_host: str,
    db_port: int,
    db_name: str,
    db_username: str,
    db_password: Optional[str],
    system_id: str,
    connection_config: Optional[Dict[str, Any]] = None,
) -> DBConnection:
    """Create or update a DBConnection record for a database system.

    Stores the connection string (Fernet-encrypted) so PARWA has a local
    record of every database the tenant has connected. ALWAYS read-only
    (is_readonly=True) — the AI agent can never write to customer databases.

    The (company_id, name) pair is the natural key — reconnecting the same
    database updates instead of creating a duplicate.
    """
    # Store the complete structured config encrypted. This preserves provider-
    # specific fields (e.g. BigQuery service accounts, Snowflake warehouse/role)
    # required by schema discovery and later agent tool generation.
    config = dict(connection_config or {})
    config.update({
        "db_type": db_type,
        "host": db_host,
        "port": db_port,
        "database": db_name,
        "username": db_username,
        "password": db_password or "",
        "readonly": True,
    })
    conn_encrypted = encrypt_token(json.dumps(config))

    # Find existing by (company_id, name)
    db_conn = db.query(DBConnection).filter(
        DBConnection.company_id == company_id,
        DBConnection.name == name,
    ).first()

    if db_conn:
        # Update existing
        db_conn.db_type = db_type
        db_conn.connection_string_encrypted = conn_encrypted
        db_conn.is_readonly = True  # ALWAYS read-only
        db_conn.status = "connected"
    else:
        # Create new
        db_conn = DBConnection(
            company_id=company_id,
            name=name,
            db_type=db_type,
            connection_string_encrypted=conn_encrypted,
            is_readonly=True,  # ALWAYS read-only — AI agent can never write
            status="connected",
        )
        db.add(db_conn)

    db.commit()
    db.refresh(db_conn)
    return db_conn


def _sanitize_schema_metadata(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Delegate to the shared allowlist sanitizer; sample values are excluded."""
    from app.core.schema_metadata import sanitize_schema_metadata
    return sanitize_schema_metadata(schema)


async def _discover_db_schema_for_connection(
    db: Session,
    db_conn: DBConnection,
    tenant_id: str,
    connection_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Discover and persist a tenant database schema through Superglue.

    A generic fallback schema is not success. Only a real schema response
    marks the connection verified and exposes it to ticket-solving agents.
    """
    config = dict(connection_config or {})
    if not config and db_conn.connection_string_encrypted:
        try:
            from shared.utils.token_encryption import decrypt_token
            from urllib.parse import unquote, urlsplit

            decrypted = decrypt_token(db_conn.connection_string_encrypted)
            if decrypted:
                try:
                    parsed_config = json.loads(decrypted)
                    config = parsed_config if isinstance(parsed_config, dict) else {}
                except (json.JSONDecodeError, TypeError):
                    # Backward compatibility for older rows that encrypted a
                    # URI rather than the structured config used by new rows.
                    parsed = urlsplit(decrypted)
                    config = {
                        "db_type": parsed.scheme or db_conn.db_type,
                        "host": parsed.hostname or "",
                        "port": parsed.port,
                        "database": parsed.path.lstrip("/"),
                        "username": unquote(parsed.username or ""),
                        "password": unquote(parsed.password or ""),
                        "readonly": True,
                    }
        except Exception as exc:
            logger.warning("db_schema_config_decrypt_failed: %s", str(exc)[:160])
            config = {}

    if not config:
        db_conn.status = "schema_pending"
        db.commit()
        return {"success": False, "schema": None, "error": "Database connection config is unavailable"}

    # Superglue's connection namespace is the integration system ID, not
    # PARWA's local DBConnection row UUID.
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.name == db_conn.name,
    ).first()
    superglue_system_id = integration.integration_type if integration else db_conn.name

    result = await superglue_client.analyze_db_schema(
        db_connection_id=superglue_system_id,
        tenant_id=tenant_id,
        db_type=db_conn.db_type,
        connection_config=config,
    )
    schema = result.get("schema")
    has_discovered_objects = isinstance(schema, dict) and any(
        isinstance(schema.get(key), list) and len(schema[key]) > 0
        for key in ("tables", "collections", "schemas")
    )
    if result.get("success") and has_discovered_objects and schema.get("source") != "fallback":
        # Store structural metadata only. Sample rows and values belong in
        # live Superglue tool results, not a long-lived schema cache.
        safe_schema = _sanitize_schema_metadata(schema)
        db_conn.schema_analysis = json.dumps(safe_schema)
        db_conn.status = "verified"
        db_conn.updated_at = datetime.now(timezone.utc)
        if integration:
            integration.status = "verified"
            integration.error_message = None
            integration.last_sync = datetime.now(timezone.utc)
        db.commit()
        return {"success": True, "schema": safe_schema}

    db_conn.status = "schema_pending"
    db.commit()
    return {
        "success": False,
        "schema": None,
        "error": result.get("error") or "Superglue did not return a verified schema",
    }


# ── Custom Integration/DB Discovery Endpoints ──────────────────────────
# These are called by the frontend when a user wants to connect a Custom
# platform (not in our curated catalog). We ask Superglue for the auth
# schema and return it so the frontend can render the right form.

class DiscoverAuthRequest(BaseModel):
    platform_name: str = Field(..., description="Platform name (e.g. 'Zoho Inventory', 'Paddle', 'CockroachDB')")
    platform_type: str = Field(default="integration", description="'integration' or 'database'")


@router.post("/discover-auth")
async def discover_auth(req: DiscoverAuthRequest, user: User = Depends(get_current_user)):
    """Ask Superglue for the auth schema of a custom platform.

    When a user types a platform name that's NOT in our curated catalog,
    we ask Superglue: "What auth does this platform need?" and return
    the auth type + required fields so the frontend can render the form.

    If Superglue doesn't know the platform, we return a fallback schema.
    """
    result = await superglue_client.discover_auth_schema(
        platform_name=req.platform_name,
        platform_type=req.platform_type,
    )
    return result


class AnalyzeDBSchemaRequest(BaseModel):
    db_connection_id: str = Field(..., description="DBConnection record ID")
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID (uses auth user if not provided)")


@router.post("/db/analyze-schema")
async def analyze_db_schema(
    req: AnalyzeDBSchemaRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze a connected database's schema via Superglue auto.read.

    After a database is connected, Superglue discovers the tables, columns,
    types, and relationships. The schema is saved to DBConnection.schema_analysis
    and used by the 8-node pipeline for ticket solving context.

    Example: Node 3 (Knowledge Fetch) reads schema_analysis to understand
    what data is available. Node 4 (Reasoning) uses this to decide which
    Superglue query tools to call.
    """
    tenant_id = str(user.company_id)
    if req.tenant_id and req.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Cannot access another tenant's database")

    # Find the DB connection
    db_conn = db.query(DBConnection).filter(
        DBConnection.id == req.db_connection_id,
        DBConnection.company_id == tenant_id,
    ).first()

    if not db_conn:
        raise HTTPException(status_code=404, detail="Database connection not found")

    result = await _discover_db_schema_for_connection(
        db=db,
        db_conn=db_conn,
        tenant_id=tenant_id,
    )

    return {
        "success": result.get("success", False),
        "schema": result.get("schema"),
        "error": result.get("error"),
    }
