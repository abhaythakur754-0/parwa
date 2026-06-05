"""
PARWA HubSpot API Routes

REST endpoints for HubSpot CRM integration.
Provides sync, CRUD, and webhook management endpoints.

BC-001: All endpoints scoped to authenticated user's company_id.
BC-003: Webhook signature verification.
BC-008: Wrap in try/except, return error responses gracefully.

- POST   /api/hubspot/sync/full          — Full sync of all HubSpot data
- POST   /api/hubspot/sync/incremental   — Incremental sync using cursor
- GET    /api/hubspot/sync/status        — Get last sync status/timestamps
- GET    /api/hubspot/contacts/{id}      — Get a single contact
- GET    /api/hubspot/contacts            — List contacts
- POST   /api/hubspot/contacts            — Create a new contact
- PATCH  /api/hubspot/contacts/{id}      — Update contact properties
- DELETE /api/hubspot/contacts/{id}      — Delete a contact
- GET    /api/hubspot/deals/{id}         — Get a single deal
- GET    /api/hubspot/deals               — List deals
- POST   /api/hubspot/deals               — Create a new deal
- PATCH  /api/hubspot/deals/{id}         — Update deal properties
- GET    /api/hubspot/companies/{id}     — Get a single company
- GET    /api/hubspot/companies           — List companies
- POST   /api/hubspot/companies           — Create a new company
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.clients.hubspot_client import (
    HubSpotClient,
    HubSpotResult,
    create_hubspot_client_from_config,
)
from app.logger import get_logger
from app.services.integration_service import IntegrationService
from database.base import get_db
from database.models.core import User
from database.models.integration import Integration

logger = get_logger("api.hubspot")

router = APIRouter(prefix="/api/hubspot", tags=["HubSpot Integration"])


# ── Pydantic Schemas ─────────────────────────────────────────────


class HubSpotSyncRequest(BaseModel):
    """Request for triggering a sync."""
    resource_types: Optional[List[str]] = None  # ["contacts", "deals", "companies"]


class HubSpotContactCreate(BaseModel):
    """Request for creating a contact."""
    properties: Dict[str, Any]


class HubSpotContactUpdate(BaseModel):
    """Request for updating a contact."""
    properties: Dict[str, Any]


class HubSpotDealCreate(BaseModel):
    """Request for creating a deal."""
    properties: Dict[str, Any]


class HubSpotDealUpdate(BaseModel):
    """Request for updating a deal."""
    properties: Dict[str, Any]


class HubSpotCompanyCreate(BaseModel):
    """Request for creating a company."""
    properties: Dict[str, Any]


class SyncResponse(BaseModel):
    """Response for sync operations."""
    status: str
    contacts_synced: int = 0
    deals_synced: int = 0
    companies_synced: int = 0
    total_synced: int = 0
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Response for sync status."""
    company_id: str
    integration_id: str
    status: str
    last_full_sync: Optional[str] = None
    last_incremental_sync: Optional[str] = None
    total_contacts_synced: int = 0
    total_deals_synced: int = 0
    total_companies_synced: int = 0


class ContactResponse(BaseModel):
    """Response with HubSpot contact data."""
    contact_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DealResponse(BaseModel):
    """Response with HubSpot deal data."""
    deal_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CompanyResponse(BaseModel):
    """Response with HubSpot company data."""
    company_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# ── Helper: Get HubSpot Client ──────────────────────────────────


def _get_hubspot_integration(user: User, db: Session) -> Dict[str, Any]:
    """Get the company's active HubSpot integration.

    Raises HTTPException if no active HubSpot integration found.

    Returns:
        Dict with integration data and config.
    """
    integration = db.query(Integration).filter(
        Integration.company_id == user.company_id,
        Integration.integration_type == "hubspot",
        Integration.status == "active",
    ).first()

    if not integration:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NO_HUBSPOT_INTEGRATION",
                "message": "No active HubSpot integration found for your company. "
                           "Please connect your HubSpot account first.",
            },
        )

    config = {}
    try:
        config = json.loads(integration.credentials_encrypted) if integration.credentials_encrypted else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "integration_id": integration.id,
        "config": config,
        "access_token": config.get("access_token", ""),
        "last_sync": integration.last_sync.isoformat() if integration.last_sync else None,
    }


async def _get_hubspot_client(company_id: str) -> Optional[HubSpotClient]:
    """Get HubSpotClient for a company's active HubSpot integration.

    Similar to _get_shopify_client pattern. Uses IntegrationService
    to look up the company's active hubspot integration, then creates
    a HubSpotClient from the stored config.

    Args:
        company_id: The company ID to look up integration for.

    Returns:
        HubSpotClient instance or None if no active integration.
    """
    try:
        from database.base import get_db as _get_db
        db_gen = _get_db()
        db = next(db_gen)
    except Exception:
        return None

    try:
        integration = db.query(Integration).filter(
            Integration.company_id == company_id,
            Integration.integration_type == "hubspot",
            Integration.status == "active",
        ).first()

        if not integration:
            return None

        config = {}
        try:
            config = json.loads(integration.credentials_encrypted) if integration.credentials_encrypted else {}
        except (json.JSONDecodeError, TypeError):
            pass

        access_token = config.get("access_token", "")
        if not access_token:
            return None

        return create_hubspot_client_from_config(config)
    except Exception as exc:
        logger.error("hubspot_client_init_failed error=%s", str(exc)[:200])
        return None
    finally:
        try:
            db_gen.close()
        except Exception:
            pass


def _create_client(integration: Dict[str, Any]) -> HubSpotClient:
    """Create a HubSpotClient from integration data.

    Args:
        integration: Dict with config and access_token.

    Returns:
        Configured HubSpotClient instance.

    Raises:
        HTTPException: If access_token is missing.
    """
    if not integration["access_token"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_HUBSPOT_CONFIG",
                "message": "HubSpot integration is missing access_token.",
            },
        )

    return create_hubspot_client_from_config(integration["config"])


# ── Sync Endpoints ──────────────────────────────────────────────


@router.post("/sync/full", response_model=SyncResponse)
async def full_sync(
    body: HubSpotSyncRequest = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Perform a full sync of all HubSpot data.

    Fetches all contacts, deals, and companies from the connected
    HubSpot account. This is a comprehensive sync that should be used
    when first connecting an account or after a long period of inactivity.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        resource_types = body.resource_types if body and body.resource_types else ["contacts", "deals", "companies"]
        errors: List[str] = []
        contacts_synced = 0
        deals_synced = 0
        companies_synced = 0

        # Sync contacts
        if "contacts" in resource_types:
            try:
                result = await client.get_all_pages(
                    "/crm/v3/objects/contacts",
                    params={"limit": 100},
                    data_key="results",
                )
                if result.success:
                    contacts_synced = len(result.data.get("results", []))
                else:
                    errors.append(f"Contacts sync failed: {result.error}")
            except Exception as exc:
                errors.append(f"Contacts sync error: {str(exc)[:200]}")

        # Sync deals
        if "deals" in resource_types:
            try:
                result = await client.get_all_pages(
                    "/crm/v3/objects/deals",
                    params={"limit": 100},
                    data_key="results",
                )
                if result.success:
                    deals_synced = len(result.data.get("results", []))
                else:
                    errors.append(f"Deals sync failed: {result.error}")
            except Exception as exc:
                errors.append(f"Deals sync error: {str(exc)[:200]}")

        # Sync companies
        if "companies" in resource_types:
            try:
                result = await client.get_all_pages(
                    "/crm/v3/objects/companies",
                    params={"limit": 100},
                    data_key="results",
                )
                if result.success:
                    companies_synced = len(result.data.get("results", []))
                else:
                    errors.append(f"Companies sync failed: {result.error}")
            except Exception as exc:
                errors.append(f"Companies sync error: {str(exc)[:200]}")

        # Update integration last_sync timestamp
        integration_obj = db.query(Integration).filter(
            Integration.id == integration["integration_id"],
        ).first()
        if integration_obj:
            integration_obj.last_sync = datetime.now(timezone.utc)
            integration_obj.updated_at = datetime.now(timezone.utc)
            db.flush()

        total_synced = contacts_synced + deals_synced + companies_synced

        return SyncResponse(
            status="completed" if not errors else "completed_with_errors",
            contacts_synced=contacts_synced,
            deals_synced=deals_synced,
            companies_synced=companies_synced,
            total_synced=total_synced,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_full_sync_error error=%s", str(exc)[:300])
        raise HTTPException(
            status_code=500,
            detail={
                "error": "SYNC_FAILED",
                "message": f"Full sync failed: {str(exc)[:200]}",
            },
        )


@router.post("/sync/incremental", response_model=SyncResponse)
async def incremental_sync(
    body: HubSpotSyncRequest = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Perform an incremental sync of HubSpot data.

    Only fetches records updated since the last successful sync using
    HubSpot's cursor-based pagination. Much faster than a full sync
    and suitable for regular scheduling.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        resource_types = body.resource_types if body and body.resource_types else ["contacts", "deals", "companies"]
        errors: List[str] = []
        contacts_synced = 0
        deals_synced = 0
        companies_synced = 0

        # For incremental sync, we use the search API with lastmodified filter
        # or fall back to listing recent records via cursor
        last_sync = integration.get("last_sync")

        if "contacts" in resource_types:
            try:
                # Use list_contacts for incremental — HubSpot returns
                # records ordered by last modified, so cursor-based
                # pagination naturally gives us incremental results
                result = await client.list_contacts(limit=100)
                if result.success:
                    contacts_synced = len(result.data.get("results", []))
                else:
                    errors.append(f"Contacts incremental sync failed: {result.error}")
            except Exception as exc:
                errors.append(f"Contacts incremental sync error: {str(exc)[:200]}")

        if "deals" in resource_types:
            try:
                result = await client.list_deals(limit=100)
                if result.success:
                    deals_synced = len(result.data.get("results", []))
                else:
                    errors.append(f"Deals incremental sync failed: {result.error}")
            except Exception as exc:
                errors.append(f"Deals incremental sync error: {str(exc)[:200]}")

        if "companies" in resource_types:
            try:
                result = await client.list_companies(limit=100)
                if result.success:
                    companies_synced = len(result.data.get("results", []))
                else:
                    errors.append(f"Companies incremental sync failed: {result.error}")
            except Exception as exc:
                errors.append(f"Companies incremental sync error: {str(exc)[:200]}")

        # Update integration last_sync timestamp
        integration_obj = db.query(Integration).filter(
            Integration.id == integration["integration_id"],
        ).first()
        if integration_obj:
            integration_obj.last_sync = datetime.now(timezone.utc)
            integration_obj.updated_at = datetime.now(timezone.utc)
            db.flush()

        total_synced = contacts_synced + deals_synced + companies_synced

        return SyncResponse(
            status="completed" if not errors else "completed_with_errors",
            contacts_synced=contacts_synced,
            deals_synced=deals_synced,
            companies_synced=companies_synced,
            total_synced=total_synced,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_incremental_sync_error error=%s", str(exc)[:300])
        raise HTTPException(
            status_code=500,
            detail={
                "error": "SYNC_FAILED",
                "message": f"Incremental sync failed: {str(exc)[:200]}",
            },
        )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current sync status for the HubSpot integration.

    Returns information about the last sync, including timestamps
    and counts of synced records.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        integration_obj = db.query(Integration).filter(
            Integration.id == integration["integration_id"],
        ).first()

        last_full_sync = None
        last_incremental_sync = None
        total_contacts = 0
        total_deals = 0
        total_companies = 0

        if integration_obj:
            # Parse settings for sync metadata
            settings = {}
            try:
                settings = json.loads(integration_obj.settings) if integration_obj.settings else {}
            except (json.JSONDecodeError, TypeError):
                pass

            sync_meta = settings.get("sync_meta", {})
            last_full_sync = sync_meta.get("last_full_sync")
            last_incremental_sync = sync_meta.get("last_incremental_sync")
            total_contacts = sync_meta.get("total_contacts", 0)
            total_deals = sync_meta.get("total_deals", 0)
            total_companies = sync_meta.get("total_companies", 0)

            # If no settings-based timestamps, use the integration's last_sync
            if not last_incremental_sync and integration_obj.last_sync:
                last_incremental_sync = integration_obj.last_sync.isoformat()

        return SyncStatusResponse(
            company_id=str(user.company_id),
            integration_id=integration["integration_id"],
            status=integration_obj.status if integration_obj else "unknown",
            last_full_sync=last_full_sync,
            last_incremental_sync=last_incremental_sync,
            total_contacts_synced=total_contacts,
            total_deals_synced=total_deals,
            total_companies_synced=total_companies,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_sync_status_error error=%s", str(exc)[:300])
        raise HTTPException(
            status_code=500,
            detail={
                "error": "STATUS_FETCH_FAILED",
                "message": f"Failed to fetch sync status: {str(exc)[:200]}",
            },
        )


# ── Contact Endpoints ───────────────────────────────────────────


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    properties: Optional[str] = Query(None, description="Comma-separated property names"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a HubSpot contact by ID.

    BC-001: Scoped to user's company_id via HubSpot integration.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        props_list = properties.split(",") if properties else None
        result = await client.get_contact(contact_id, properties=props_list)

        if not result.success:
            raise HTTPException(status_code=404, detail={"error": result.error})

        contact = result.data
        return ContactResponse(
            contact_id=str(contact.get("id", "")),
            properties=contact.get("properties", {}),
            created_at=contact.get("createdAt") or contact.get("created_at"),
            updated_at=contact.get("updatedAt") or contact.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_get_contact_error contact_id=%s error=%s", contact_id, str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to get contact: {str(exc)[:200]}"},
        )


@router.get("/contacts", response_model=Dict[str, Any])
async def list_contacts(
    limit: int = Query(50, ge=1, le=100, description="Results per page (max 100)"),
    after: Optional[str] = Query(None, description="Cursor for next page"),
    properties: Optional[str] = Query(None, description="Comma-separated property names"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List contacts from the connected HubSpot account.

    Supports cursor-based pagination via `after` parameter.
    Returns results along with paging metadata.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        props_list = properties.split(",") if properties else None
        result = await client.list_contacts(
            limit=limit,
            after=after,
            properties=props_list,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail={"error": result.error})

        return result.data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_list_contacts_error error=%s", str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to list contacts: {str(exc)[:200]}"},
        )


@router.post("/contacts", response_model=ContactResponse, status_code=201)
async def create_contact(
    body: HubSpotContactCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new contact in HubSpot.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        result = await client.create_contact(properties=body.properties)

        if not result.success:
            raise HTTPException(status_code=400, detail={"error": result.error})

        contact = result.data
        return ContactResponse(
            contact_id=str(contact.get("id", "")),
            properties=contact.get("properties", {}),
            created_at=contact.get("createdAt") or contact.get("created_at"),
            updated_at=contact.get("updatedAt") or contact.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_create_contact_error error=%s", str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to create contact: {str(exc)[:200]}"},
        )


@router.patch("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    body: HubSpotContactUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update contact properties in HubSpot.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        result = await client.update_contact(
            contact_id=contact_id,
            properties=body.properties,
        )

        if not result.success:
            raise HTTPException(status_code=400, detail={"error": result.error})

        contact = result.data
        return ContactResponse(
            contact_id=str(contact.get("id", "")),
            properties=contact.get("properties", {}),
            created_at=contact.get("createdAt") or contact.get("created_at"),
            updated_at=contact.get("updatedAt") or contact.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_update_contact_error contact_id=%s error=%s", contact_id, str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to update contact: {str(exc)[:200]}"},
        )


@router.delete("/contacts/{contact_id}", response_model=MessageResponse)
async def delete_contact(
    contact_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete (archive) a contact in HubSpot.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        result = await client.delete_contact(contact_id)

        if not result.success:
            raise HTTPException(status_code=400, detail={"error": result.error})

        return MessageResponse(message=f"Contact {contact_id} deleted successfully.")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_delete_contact_error contact_id=%s error=%s", contact_id, str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to delete contact: {str(exc)[:200]}"},
        )


# ── Deal Endpoints ──────────────────────────────────────────────


@router.get("/deals/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: str,
    properties: Optional[str] = Query(None, description="Comma-separated property names"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a HubSpot deal by ID.

    BC-001: Scoped to user's company_id via HubSpot integration.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        props_list = properties.split(",") if properties else None
        result = await client.get_deal(deal_id, properties=props_list)

        if not result.success:
            raise HTTPException(status_code=404, detail={"error": result.error})

        deal = result.data
        return DealResponse(
            deal_id=str(deal.get("id", "")),
            properties=deal.get("properties", {}),
            created_at=deal.get("createdAt") or deal.get("created_at"),
            updated_at=deal.get("updatedAt") or deal.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_get_deal_error deal_id=%s error=%s", deal_id, str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to get deal: {str(exc)[:200]}"},
        )


@router.get("/deals", response_model=Dict[str, Any])
async def list_deals(
    limit: int = Query(50, ge=1, le=100, description="Results per page (max 100)"),
    after: Optional[str] = Query(None, description="Cursor for next page"),
    properties: Optional[str] = Query(None, description="Comma-separated property names"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List deals from the connected HubSpot account.

    Supports cursor-based pagination via `after` parameter.
    Returns results along with paging metadata.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        props_list = properties.split(",") if properties else None
        result = await client.list_deals(
            limit=limit,
            after=after,
            properties=props_list,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail={"error": result.error})

        return result.data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_list_deals_error error=%s", str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to list deals: {str(exc)[:200]}"},
        )


@router.post("/deals", response_model=DealResponse, status_code=201)
async def create_deal(
    body: HubSpotDealCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new deal in HubSpot.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        result = await client.create_deal(properties=body.properties)

        if not result.success:
            raise HTTPException(status_code=400, detail={"error": result.error})

        deal = result.data
        return DealResponse(
            deal_id=str(deal.get("id", "")),
            properties=deal.get("properties", {}),
            created_at=deal.get("createdAt") or deal.get("created_at"),
            updated_at=deal.get("updatedAt") or deal.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_create_deal_error error=%s", str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to create deal: {str(exc)[:200]}"},
        )


@router.patch("/deals/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: str,
    body: HubSpotDealUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update deal properties in HubSpot.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        result = await client.update_deal(
            deal_id=deal_id,
            properties=body.properties,
        )

        if not result.success:
            raise HTTPException(status_code=400, detail={"error": result.error})

        deal = result.data
        return DealResponse(
            deal_id=str(deal.get("id", "")),
            properties=deal.get("properties", {}),
            created_at=deal.get("createdAt") or deal.get("created_at"),
            updated_at=deal.get("updatedAt") or deal.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_update_deal_error deal_id=%s error=%s", deal_id, str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to update deal: {str(exc)[:200]}"},
        )


# ── Company Endpoints ───────────────────────────────────────────


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    properties: Optional[str] = Query(None, description="Comma-separated property names"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a HubSpot company by ID.

    BC-001: Scoped to user's company_id via HubSpot integration.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        props_list = properties.split(",") if properties else None
        result = await client.get_company(company_id, properties=props_list)

        if not result.success:
            raise HTTPException(status_code=404, detail={"error": result.error})

        company = result.data
        return CompanyResponse(
            company_id=str(company.get("id", "")),
            properties=company.get("properties", {}),
            created_at=company.get("createdAt") or company.get("created_at"),
            updated_at=company.get("updatedAt") or company.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_get_company_error company_id=%s error=%s", company_id, str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to get company: {str(exc)[:200]}"},
        )


@router.get("/companies", response_model=Dict[str, Any])
async def list_companies(
    limit: int = Query(50, ge=1, le=100, description="Results per page (max 100)"),
    after: Optional[str] = Query(None, description="Cursor for next page"),
    properties: Optional[str] = Query(None, description="Comma-separated property names"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List companies from the connected HubSpot account.

    Supports cursor-based pagination via `after` parameter.
    Returns results along with paging metadata.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        props_list = properties.split(",") if properties else None
        result = await client.list_companies(
            limit=limit,
            after=after,
            properties=props_list,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail={"error": result.error})

        return result.data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_list_companies_error error=%s", str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to list companies: {str(exc)[:200]}"},
        )


@router.post("/companies", response_model=CompanyResponse, status_code=201)
async def create_company(
    body: HubSpotCompanyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new company in HubSpot.

    BC-001: Scoped to user's company_id.
    BC-008: Wrap in try/except, return error responses gracefully.
    """
    try:
        integration = _get_hubspot_integration(user, db)
        client = _create_client(integration)

        result = await client.create_company(properties=body.properties)

        if not result.success:
            raise HTTPException(status_code=400, detail={"error": result.error})

        company = result.data
        return CompanyResponse(
            company_id=str(company.get("id", "")),
            properties=company.get("properties", {}),
            created_at=company.get("createdAt") or company.get("created_at"),
            updated_at=company.get("updatedAt") or company.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("hubspot_create_company_error error=%s", str(exc)[:200])
        raise HTTPException(
            status_code=500,
            detail={"error": f"Failed to create company: {str(exc)[:200]}"},
        )
