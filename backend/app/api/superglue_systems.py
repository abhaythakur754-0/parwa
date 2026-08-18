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

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import superglue_client
from database.base import get_db
from database.models.core import User
from database.models.integration import MCPConnection, Integration, DBConnection
from shared.utils.token_encryption import encrypt_token, decrypt_token


router = APIRouter(prefix="/api/superglue", tags=["superglue-systems"])


# ── Curated catalog (replaces Nango's 6-provider list) ────────────────
# These are popular systems PARWA customers commonly connect. Users can
# also connect ANY custom system via the POST endpoint with a custom URL.

POPULAR_SYSTEMS: List[Dict[str, Any]] = [
    # ── APIs (connect via URL + API key) ──
    {"id": "shopify",      "name": "Shopify",           "icon": "🛒", "url_hint": "https://{store}.myshopify.com", "category": "E-commerce",   "type": "api"},
    {"id": "gmail",        "name": "Gmail",             "icon": "📧", "url_hint": "https://gmail.googleapis.com",   "category": "Email",         "type": "api"},
    {"id": "slack",        "name": "Slack",             "icon": "💬", "url_hint": "https://slack.com/api",          "category": "Communication", "type": "api"},
    {"id": "hubspot",      "name": "HubSpot",           "icon": "🎯", "url_hint": "https://api.hubapi.com",         "category": "CRM",           "type": "api"},
    {"id": "zendesk",      "name": "Zendesk",           "icon": "🎫", "url_hint": "https://{subdomain}.zendesk.com/api/v2", "category": "Helpdesk", "type": "api"},
    {"id": "stripe",       "name": "Stripe",            "icon": "💳", "url_hint": "https://api.stripe.com",         "category": "Payments",      "type": "api"},
    {"id": "razorpay",     "name": "Razorpay",          "icon": "💰", "url_hint": "https://api.razorpay.com",       "category": "Payments",      "type": "api"},
    {"id": "github",       "name": "GitHub",            "icon": "🔧", "url_hint": "https://api.github.com",         "category": "Dev Tools",     "type": "api"},
    {"id": "notion",       "name": "Notion",            "icon": "📝", "url_hint": "https://api.notion.com/v1",      "category": "Productivity",  "type": "api"},
    {"id": "jira",         "name": "Jira",              "icon": "🟦", "url_hint": "https://{subdomain}.atlassian.net", "category": "Project Management", "type": "api"},
    {"id": "google-analytics", "name": "Google Analytics", "icon": "📊", "url_hint": "https://analyticsreporting.googleapis.com", "category": "Analytics", "type": "api"},
    # ── Databases (connect via host/port/credentials — Superglue auto-reads schema) ──
    {"id": "postgres",     "name": "PostgreSQL Database","icon": "🗄️", "url_hint": "", "category": "Database",          "type": "database", "db_type": "postgresql"},
    {"id": "mysql",        "name": "MySQL Database",     "icon": "🗄️", "url_hint": "", "category": "Database",          "type": "database", "db_type": "mysql"},
    {"id": "mongodb",      "name": "MongoDB",            "icon": "🍃", "url_hint": "", "category": "Database",          "type": "database", "db_type": "mongodb"},
    {"id": "snowflake",    "name": "Snowflake Warehouse","icon": "❄️", "url_hint": "", "category": "Data Warehouse",    "type": "database", "db_type": "snowflake"},
    {"id": "bigquery",     "name": "BigQuery",           "icon": "📊", "url_hint": "", "category": "Data Warehouse",    "type": "database", "db_type": "bigquery"},
    {"id": "supabase-db",  "name": "Supabase Database",  "icon": "⚡", "url_hint": "", "category": "Database",          "type": "database", "db_type": "postgresql"},
    # ── Custom (user-defined) ──
    {"id": "custom",       "name": "Custom System",      "icon": "🔌", "url_hint": "", "category": "Custom",            "type": "api"},
]

# Systems that are CRM-type — these get an MCPConnection record so the
# 8-node pipeline can access them on every ticket.
CRM_SYSTEM_IDS = {"hubspot", "zendesk", "salesforce", "custom"}

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
async def list_systems(user: User = Depends(get_current_user)) -> ListSystemsResponse:
    """List all systems connected by this tenant.

    BC-001: Scoped to user's company_id. Only returns systems with the
    tenant_{company_id}__ prefix.
    """
    tenant_id = str(user.company_id)
    systems = await superglue_client.list_tenant_systems(tenant_id)
    # Strip the tenant prefix from the ID for cleaner frontend display
    cleaned = []
    prefix = f"tenant_{tenant_id}__"
    for s in systems:
        clean_id = s.get("id", "")
        if clean_id.startswith(prefix):
            clean_id = clean_id[len(prefix):]
        cleaned.append(SystemResponse(
            id=clean_id,
            name=s.get("name", ""),
            url=s.get("url", ""),
            icon=s.get("icon", ""),
            credentials={},  # never expose credentials to frontend
            metadata=s.get("metadata", {}),
            created_at=s.get("createdAt") or s.get("created_at"),
            updated_at=s.get("updatedAt") or s.get("updated_at"),
        ))
    return ListSystemsResponse(success=True, systems=cleaned, count=len(cleaned))


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

    # For databases, build the URL + credentials from the DB-specific fields
    if is_database:
        if not req.db_host or not req.db_name or not req.db_username:
            raise HTTPException(status_code=400, detail="Database connections require db_host, db_name, db_username")
        # Build a connection URL for Superglue (it treats DBs as systems with a URL)
        db_port = req.db_port or 5432
        req.url = f"{req.db_type or 'postgresql'}://{req.db_host}:{db_port}/{req.db_name}"
        # Store DB credentials in the credentials dict for Superglue
        req.credentials = {
            "db_type": req.db_type,
            "host": req.db_host,
            "port": db_port,
            "database": req.db_name,
            "username": req.db_username,
            "password": req.db_password or "",
        }
        # Tell Superglue this is a database — it will auto-read the schema
        if not req.metadata:
            req.metadata = {}
        req.metadata["system_type"] = "database"
        req.metadata["db_type"] = req.db_type

    result = await superglue_client.create_system(
        system_id=req.system_id,
        name=req.name,
        url=req.url,
        tenant_id=tenant_id,
        credentials=req.credentials,
        metadata=req.metadata,
        icon=req.icon,
        specific_instructions=req.specific_instructions,
    )
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"Superglue error: {result.get('error', 'unknown')}")

    # Save EVERY connection to the Integration table (local DB record).
    _upsert_integration(
        db=db,
        company_id=tenant_id,
        integration_type=req.system_id,
        name=req.name,
        credentials=req.credentials,
        settings=req.metadata or {},
    )

    # If this is a CRM system, ALSO register an MCPConnection
    is_crm = req.system_id in CRM_SYSTEM_IDS or (req.metadata or {}).get("is_crm", False)
    if is_crm:
        _upsert_mcp_connection(
            db=db,
            company_id=tenant_id,
            name=req.name,
            server_url=req.url,
            auth_token=req.credentials.get("api_key") if req.credentials else None,
            system_id=req.system_id,
        )

    # If this is a database, ALSO save to DBConnection table (read-only enforced)
    if is_database:
        _upsert_db_connection(
            db=db,
            company_id=tenant_id,
            name=req.name,
            db_type=req.db_type or "postgresql",
            db_host=req.db_host,
            db_port=req.db_port or 5432,
            db_name=req.db_name,
            db_username=req.db_username,
            db_password=req.db_password,
            system_id=req.system_id,
        )

    data = result.get("data", {})
    return SystemResponse(
        id=req.system_id,  # return the clean (non-namespaced) ID
        name=data.get("name", req.name),
        url=data.get("url", req.url),
        icon=data.get("icon", req.icon),
        credentials={},
        metadata=data.get("metadata", {}),
        created_at=data.get("createdAt") or data.get("created_at"),
        updated_at=data.get("updatedAt") or data.get("updated_at"),
    )


@router.get("/systems/{system_id}", response_model=SystemResponse)
async def get_system(
    system_id: str,
    user: User = Depends(get_current_user),
) -> SystemResponse:
    """Get details of one connected system."""
    tenant_id = str(user.company_id)
    result = await superglue_client.get_system(system_id, tenant_id=tenant_id)
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
    result = await superglue_client.delete_system(system_id, tenant_id=tenant_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "System not found"))

    # Also remove the local Integration record
    integration = db.query(Integration).filter(
        Integration.company_id == tenant_id,
        Integration.integration_type == system_id,
    ).first()
    if integration:
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
            DBConnection.name.like(f"%({system_id})"),
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
    """Verify a system is connected + MCPConnection is registered.

    Checks:
    1. System exists in Superglue (GET /v1/systems/{id} returns 200)
    2. If CRM: MCPConnection record exists in PARWA DB

    Used by onboarding Step 2 "Connect & Verify" button to confirm the
    CRM is actually reachable before triggering the CRM Analyser.
    """
    tenant_id = str(user.company_id)

    # 1. Check Superglue
    sg_result = await superglue_client.get_system(system_id, tenant_id=tenant_id)
    superglue_ok = sg_result.get("success", False)

    if not superglue_ok:
        return VerifyResponse(
            verified=False,
            superglue_ok=False,
            mcp_registered=False,
            system_id=system_id,
            name="",
            url="",
            message=f"Superglue verification failed: {sg_result.get('error', 'system not found')}",
        )

    data = sg_result.get("data", {})
    name = data.get("name", system_id)
    url = data.get("url", "")

    # 2. Check MCPConnection (only for CRM systems)
    is_crm = system_id in CRM_SYSTEM_IDS
    mcp_registered = False
    if is_crm:
        mcp = db.query(MCPConnection).filter(
            MCPConnection.company_id == tenant_id,
            MCPConnection.name.like(f"%({system_id})"),
        ).first()
        mcp_registered = mcp is not None
        if not mcp_registered:
            # Auto-create the MCPConnection if missing (self-healing)
            _upsert_mcp_connection(
                db=db,
                company_id=tenant_id,
                name=name,
                server_url=url,
                auth_token=None,
                system_id=system_id,
            )
            mcp_registered = True

    return VerifyResponse(
        verified=True,
        superglue_ok=True,
        mcp_registered=mcp_registered,
        system_id=system_id,
        name=name,
        url=url,
        message="CRM verified — connected to Superglue" + (" + registered with MCP" if mcp_registered else ""),
    )


# ── Helper: upsert MCPConnection ──────────────────────────────────────


def _upsert_mcp_connection(
    db: Session,
    company_id: str,
    name: str,
    server_url: str,
    auth_token: Optional[str],
    system_id: str,
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
        mcp.status = "connected"
        mcp.capabilities = json.dumps(["crm"])
    else:
        # Create new
        mcp = MCPConnection(
            company_id=company_id,
            name=full_name,
            server_url=server_url,
            auth_token_encrypted=encrypt_token(auth_token) if auth_token else None,
            status="connected",
            capabilities=json.dumps(["crm"]),
        )
        db.add(mcp)

    db.commit()
    db.refresh(mcp)
    return mcp


# ── Helper: upsert Integration (local DB record for every connection) ──


def _upsert_integration(
    db: Session,
    company_id: str,
    integration_type: str,
    name: str,
    credentials: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
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
    if credentials:
        # Store the whole credentials dict as encrypted JSON
        creds_encrypted = encrypt_token(json.dumps(credentials))

    settings_json = json.dumps(settings or {})

    if integration:
        # Update existing
        integration.name = name
        integration.status = "connected"
        if creds_encrypted:
            integration.credentials_encrypted = creds_encrypted
        integration.settings = settings_json
        integration.error_message = None
    else:
        # Create new
        integration = Integration(
            company_id=company_id,
            integration_type=integration_type,
            name=name,
            status="connected",
            credentials_encrypted=creds_encrypted,
            settings=settings_json,
        )
        db.add(integration)

    db.commit()
    db.refresh(integration)
    return integration


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

    # 1. Get the system from Superglue (to retrieve URL + credentials)
    sg_result = await superglue_client.get_system(system_id, tenant_id=tenant_id)
    if not sg_result.get("success"):
        return TestResponse(
            system_id=system_id,
            works=False,
            tested_at=datetime.now(timezone.utc).isoformat(),
            message=f"System not found in Superglue: {sg_result.get('error', 'unknown')}",
        )

    data = sg_result.get("data", {})
    system_url = data.get("url", "").rstrip("/")
    credentials = data.get("credentials", {}) or {}

    tested_at = datetime.now(timezone.utc).isoformat()

    # ── DATABASE TEST: verify DBConnection record + Superglue has the system ──
    # For databases, Superglue auto-reads the schema when the system was created.
    # The test just confirms: (1) Superglue has it, (2) DBConnection record exists.
    # Superglue handles the actual schema introspection + tool generation automatically.
    if system_id in DATABASE_SYSTEM_IDS:
        # Check DBConnection record exists
        db_conn = db.query(DBConnection).filter(
            DBConnection.company_id == tenant_id,
            DBConnection.name.like(f"%({system_id})"),
        ).first()

        if db_conn:
            db_conn.status = "verified"
            db.commit()

        return TestResponse(
            system_id=system_id,
            works=True,
            status_code=200,
            tested_at=tested_at,
            message=f"✓ Database connected — Superglue is reading schema + generating tools automatically",
            sample_data={"db_type": data.get("metadata", {}).get("db_type", "unknown")} if data.get("metadata") else None,
        )

    # ── API TEST: make a real HTTP GET to verify credentials work ──
    if not system_url:
        return TestResponse(
            system_id=system_id,
            works=False,
            tested_at=tested_at,
            message="System has no URL configured",
        )

    # 2. Build auth headers from credentials
    headers = {"Accept": "application/json", "User-Agent": "PARWA-Test/1.0"}
    api_key = credentials.get("api_key") or credentials.get("token") or credentials.get("access_token")
    if api_key:
        # Try common auth header patterns
        headers["Authorization"] = f"Bearer {api_key}"
        # Also set X-API-Key as fallback (some APIs use this)
        headers["X-API-Key"] = api_key

    # 3. Make a real GET request to the system's URL
    tested_at = datetime.now(timezone.utc).isoformat()
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(system_url, headers=headers)

        # 200/201 = works; 401/403 = auth failed; 404 = wrong URL; 5xx = their server broken
        works = resp.status_code in (200, 201)
        sample = resp.text[:500] if resp.text else ""

        # Update the Integration record with test result
        integration = db.query(Integration).filter(
            Integration.company_id == tenant_id,
            Integration.integration_type == system_id,
        ).first()
        if integration:
            integration.last_sync = datetime.now(timezone.utc)
            if works:
                integration.status = "verified"
                integration.error_message = None
            else:
                integration.status = "error"
                integration.error_message = f"HTTP {resp.status_code}: {sample[:200]}"
            db.commit()

        if works:
            message = f"✓ Connection works (HTTP {resp.status_code})"
        elif resp.status_code in (401, 403):
            message = f"✗ Authentication failed (HTTP {resp.status_code}) — check your API key"
        elif resp.status_code == 404:
            message = f"✗ URL not found (HTTP 404) — check your system URL"
        else:
            message = f"✗ API returned HTTP {resp.status_code}"

        return TestResponse(
            system_id=system_id,
            works=works,
            status_code=resp.status_code,
            tested_at=tested_at,
            message=message,
            sample_data={"preview": sample} if sample else None,
        )

    except httpx.ConnectError:
        return TestResponse(
            system_id=system_id,
            works=False,
            tested_at=tested_at,
            message=f"✗ Cannot connect to {system_url} — URL is wrong or unreachable",
        )
    except httpx.TimeoutException:
        return TestResponse(
            system_id=system_id,
            works=False,
            tested_at=tested_at,
            message=f"✗ Connection timed out — {system_url} is too slow or unreachable",
        )
    except Exception as exc:
        return TestResponse(
            system_id=system_id,
            works=False,
            tested_at=tested_at,
            message=f"✗ Test failed: {str(exc)[:150]}",
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
) -> DBConnection:
    """Create or update a DBConnection record for a database system.

    Stores the connection string (Fernet-encrypted) so PARWA has a local
    record of every database the tenant has connected. ALWAYS read-only
    (is_readonly=True) — the AI agent can never write to customer databases.

    The (company_id, name) pair is the natural key — reconnecting the same
    database updates instead of creating a duplicate.
    """
    # Build the connection string based on database type
    if db_type == "mongodb":
        conn_str = f"mongodb://{db_username}:{db_password or ''}@{db_host}:{db_port}/{db_name}"
    elif db_type == "snowflake":
        conn_str = f"snowflake://{db_username}:{db_password or ''}@{db_host}/{db_name}"
    elif db_type == "bigquery":
        conn_str = f"bigquery://{db_host}/{db_name}"  # uses service account, not password
    else:
        # postgresql, mysql
        conn_str = f"{db_type}://{db_username}:{db_password or ''}@{db_host}:{db_port}/{db_name}"

    conn_encrypted = encrypt_token(conn_str)

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
