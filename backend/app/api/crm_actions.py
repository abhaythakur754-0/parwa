"""
PARWA CRM Actions Router — Real CRM tool invocations.

Fixes the fake-wired MCP `crm_server` problem:
  mcp_server/integrations/crm_server.py claimed to be "v2.0.0 — Wired to Real Backend"
  but called three backend endpoints that DON'T EXIST:
    POST /api/v1/integrations/crm/contact
    POST /api/v1/integrations/crm/note
    POST /api/v1/integrations/crm/deals

  The result: even when a real HubSpot integration was connected with valid
  credentials, the backend returned 404, the MCP's `_backend_call` returned None,
  and the user saw the misleading "not connected" response.

  This router provides the three missing endpoints. They:
    1. Resolve the tenant's active CRM integration via IntegrationService
       (BC-001: scoped by company_id, returns None if no active integration).
    2. Call the real HubSpot Contacts/Deals/Notes API using the stored
       access_token (same pattern as HubSpotAdapter.push_response_to_crm).
    3. Return honest results: real data on success, structured "not_connected"
       status when no integration exists, "external_error" on provider failure.

  Endpoint inventory:
    POST /api/integrations/crm/contact  — look up contact by id/email/phone
    POST /api/integrations/crm/note     — add a note to a contact
    POST /api/integrations/crm/deals    — list deals for a contact

BC-001: All operations scoped to authenticated user's company_id.
BC-012: No stack traces leak to clients; structured error responses.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.services.integration_service import IntegrationService
from database.base import get_db
from database.models.core import User

logger = logging.getLogger("parwa.api.crm_actions")

router = APIRouter(prefix="/api/integrations/crm", tags=["Integrations — CRM Actions"])


# ── Request / Response Schemas ────────────────────────────────────


class CRMContactRequest(BaseModel):
    """Look up a CRM contact by id, email, or phone."""

    action: str = Field(default="get_contact", description="Action key (kept for MCP compatibility)")
    platform: str = Field(default="hubspot", description="CRM platform: hubspot | salesforce | pipedrive")
    contact_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_id: Optional[str] = Field(
        default=None,
        description="Optional override; defaults to authenticated user's company_id (BC-001)",
    )


class CRMNoteRequest(BaseModel):
    """Add a note to a CRM contact record."""

    action: str = Field(default="create_note")
    platform: str = Field(default="hubspot")
    contact_id: str = Field(..., min_length=1, description="HubSpot contact ID")
    note: str = Field(..., min_length=1, max_length=10000, description="Note body")
    company_id: Optional[str] = None


class CRMDealsRequest(BaseModel):
    """List deals associated with a CRM contact."""

    action: str = Field(default="get_deals")
    platform: str = Field(default="hubspot")
    contact_id: str = Field(..., min_length=1)
    company_id: Optional[str] = None


class CRMActionResponse(BaseModel):
    """Standard response for all CRM action endpoints.

    `status` is one of:
      - "ok"             — call succeeded, data populated
      - "not_connected"  — no active CRM integration for this tenant
      - "not_found"      — integration connected, but the requested object doesn't exist
      - "external_error" — provider returned an error (auth, rate limit, etc.)
    """

    status: str
    platform: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


# ── HubSpot API helpers ───────────────────────────────────────────
# HubSpot CRM v3 endpoints — same pattern as HubSpotAdapter.push_response_to_crm.

HUBSPOT_BASE = "https://api.hubapi.com/crm/v3/objects"
HUBSPOT_TIMEOUT = 15.0


def _hubspot_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


async def _hubspot_get_contact(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    *,
    contact_id: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch a HubSpot contact by id, email, or phone.

    Returns {"status": "ok"|"not_found"|"external_error", "data": {...}, "error": str|None}.
    """
    # 1. Direct lookup by contact ID.
    if contact_id:
        try:
            resp = await client.get(
                f"{HUBSPOT_BASE}/contacts/{contact_id}",
                headers=headers,
                params={"properties": "email,firstname,lastname,phone,company,lifecyclestage"},
            )
        except httpx.HTTPError as exc:
            return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
        if resp.status_code == 404:
            return {"status": "not_found", "data": {}, "error": None}
        if resp.status_code >= 400:
            return {"status": "external_error", "data": {}, "error": f"hubspot_{resp.status_code}: {resp.text[:200]}"}
        return {"status": "ok", "data": _shape_hubspot_contact(resp.json()), "error": None}

    # 2. Lookup by email or phone via the search API.
    property_name = "email" if email else "phone"
    property_value = email or phone
    if not property_value:
        return {"status": "external_error", "data": {}, "error": "missing contact_id, email, or phone"}

    search_payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": property_name,
                        "operator": "EQ",
                        "value": property_value,
                    }
                ]
            }
        ],
        "properties": ["email", "firstname", "lastname", "phone", "company", "lifecyclestage"],
        "limit": 1,
    }
    try:
        resp = await client.post(
            f"{HUBSPOT_BASE}/contacts/search",
            headers=headers,
            json=search_payload,
        )
    except httpx.HTTPError as exc:
        return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
    if resp.status_code >= 400:
        return {"status": "external_error", "data": {}, "error": f"hubspot_{resp.status_code}: {resp.text[:200]}"}

    results = resp.json().get("results", [])
    if not results:
        return {"status": "not_found", "data": {}, "error": None}
    return {"status": "ok", "data": _shape_hubspot_contact(results[0]), "error": None}


def _shape_hubspot_contact(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize HubSpot contact object to a stable response shape."""
    props = raw.get("properties", {}) or {}
    return {
        "contact_id": str(raw.get("id", "")),
        "email": props.get("email", ""),
        "first_name": props.get("firstname", ""),
        "last_name": props.get("lastname", ""),
        "phone": props.get("phone", ""),
        "company": props.get("company", ""),
        "lifecycle_stage": props.get("lifecyclestage", ""),
        "raw": raw,  # Full object for callers that want every field.
    }


async def _hubspot_create_note(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    *,
    contact_id: str,
    note_body: str,
) -> Dict[str, Any]:
    """Create a HubSpot note and associate it with the contact.

    HubSpot v3 flow:
      1. POST /objects/notes  → create the note object
      2. PUT  /objects/notes/{note_id}/associations/contact/{contact_id}/note_to_contact
    """
    note_payload = {
        "properties": {
            "hs_note_body": note_body[:32000],  # HubSpot note body limit.
            "hs_timestamp": str(int(time.time() * 1000)),
        },
    }
    try:
        resp = await client.post(
            f"{HUBSPOT_BASE}/notes",
            headers=headers,
            json=note_payload,
        )
    except httpx.HTTPError as exc:
        return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
    if resp.status_code >= 400:
        return {"status": "external_error", "data": {}, "error": f"hubspot_{resp.status_code}: {resp.text[:200]}"}

    note_id = resp.json().get("id", "")
    if not note_id:
        return {"status": "external_error", "data": {}, "error": "hubspot returned no note id"}

    # Associate the note with the contact.
    try:
        assoc = await client.put(
            f"{HUBSPOT_BASE}/notes/{note_id}/associations/contact/{contact_id}/note_to_contact",
            headers=headers,
        )
        if assoc.status_code >= 400:
            # Note was created but association failed — still return the note id,
            # the caller can retry the association separately.
            return {
                "status": "ok",
                "data": {"note_id": note_id, "contact_id": contact_id, "associated": False},
                "error": f"association_failed: hubspot_{assoc.status_code}",
            }
    except httpx.HTTPError as exc:
        return {
            "status": "ok",
            "data": {"note_id": note_id, "contact_id": contact_id, "associated": False},
            "error": f"association_network_error: {exc}",
        }

    return {
        "status": "ok",
        "data": {"note_id": note_id, "contact_id": contact_id, "associated": True},
        "error": None,
    }


async def _hubspot_get_deals(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    *,
    contact_id: str,
) -> Dict[str, Any]:
    """List deals associated with a HubSpot contact.

    Uses the batch-read associations API to find deal IDs, then fetches deal properties.
    """
    # 1. Get associated deal IDs.
    try:
        resp = await client.get(
            f"{HUBSPOT_BASE}/contacts/{contact_id}/associations/deals",
            headers=headers,
        )
    except httpx.HTTPError as exc:
        return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
    if resp.status_code == 404:
        return {"status": "not_found", "data": {}, "error": None}
    if resp.status_code >= 400:
        return {"status": "external_error", "data": {}, "error": f"hubspot_{resp.status_code}: {resp.text[:200]}"}

    deal_ids = [str(r.get("id")) for r in resp.json().get("results", []) if r.get("id")]
    if not deal_ids:
        return {"status": "ok", "data": {"deals": [], "count": 0}, "error": None}

    # 2. Batch-read deal properties.
    batch_payload = {"inputs": [{"id": did} for did in deal_ids[:100]]}  # HubSpot batch limit 100.
    try:
        batch = await client.post(
            f"{HUBSPOT_BASE}/deals/batch/read",
            headers=headers,
            json=batch_payload,
            params={"properties": "dealname,amount,dealstage,closedate,pipeline"},
        )
    except httpx.HTTPError as exc:
        return {"status": "external_error", "data": {}, "error": f"network_error: {exc}"}
    if batch.status_code >= 400:
        return {"status": "external_error", "data": {}, "error": f"hubspot_{batch.status_code}: {batch.text[:200]}"}

    deals: List[Dict[str, Any]] = []
    for r in batch.json().get("results", []):
        props = r.get("properties", {}) or {}
        deals.append(
            {
                "deal_id": str(r.get("id", "")),
                "name": props.get("dealname", ""),
                "amount": props.get("amount", ""),
                "stage": props.get("dealstage", ""),
                "close_date": props.get("closedate", ""),
                "pipeline": props.get("pipeline", ""),
            }
        )
    return {"status": "ok", "data": {"deals": deals, "count": len(deals)}, "error": None}


# ── Credential resolution ─────────────────────────────────────────


def _resolve_crm_credentials(
    db: Session,
    user: User,
    platform: str,
) -> Optional[Dict[str, Any]]:
    """Resolve the tenant's active CRM integration credentials.

    BC-001: ALWAYS scoped to the authenticated user's company_id.
            The request body's `company_id` field is accepted for MCP payload
            compatibility but is NEVER trusted — only the authed user's
            company_id is used. (Platform-admin override is out of scope
            for this fix; would require a separate role check.)
    Returns the decrypted credential dict (IntegrationService.get_credential_config),
    or None if no active integration of that platform is connected.
    """
    company_id = str(user.company_id)
    service = IntegrationService(db)
    platform_key = (platform or "hubspot").lower().strip()
    return service.get_credential_config(company_id, platform_key)


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/contact", response_model=CRMActionResponse)
async def crm_get_contact(
    body: CRMContactRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CRMActionResponse:
    """Look up a CRM contact by id, email, or phone."""
    creds = _resolve_crm_credentials(db, user, body.platform)
    if not creds or not creds.get("access_token"):
        return CRMActionResponse(
            status="not_connected",
            platform=body.platform,
            data={},
            error=f"CRM platform '{body.platform}' is not connected for this tenant.",
        )

    headers = _hubspot_headers(creds["access_token"])
    async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
        result = await _hubspot_get_contact(
            client,
            headers,
            contact_id=body.contact_id,
            email=body.email,
            phone=body.phone,
        )
    return CRMActionResponse(
        status=result["status"],
        platform=body.platform,
        data=result["data"],
        error=result["error"],
    )


@router.post("/note", response_model=CRMActionResponse)
async def crm_create_note(
    body: CRMNoteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CRMActionResponse:
    """Add a note to a CRM contact record."""
    creds = _resolve_crm_credentials(db, user, body.platform)
    if not creds or not creds.get("access_token"):
        return CRMActionResponse(
            status="not_connected",
            platform=body.platform,
            data={},
            error=f"CRM platform '{body.platform}' is not connected for this tenant.",
        )

    headers = _hubspot_headers(creds["access_token"])
    async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
        result = await _hubspot_create_note(
            client,
            headers,
            contact_id=body.contact_id,
            note_body=body.note,
        )
    return CRMActionResponse(
        status=result["status"],
        platform=body.platform,
        data=result["data"],
        error=result["error"],
    )


@router.post("/deals", response_model=CRMActionResponse)
async def crm_get_deals(
    body: CRMDealsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CRMActionResponse:
    """List deals associated with a CRM contact."""
    creds = _resolve_crm_credentials(db, user, body.platform)
    if not creds or not creds.get("access_token"):
        return CRMActionResponse(
            status="not_connected",
            platform=body.platform,
            data={},
            error=f"CRM platform '{body.platform}' is not connected for this tenant.",
        )

    headers = _hubspot_headers(creds["access_token"])
    async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
        result = await _hubspot_get_deals(
            client,
            headers,
            contact_id=body.contact_id,
        )
    return CRMActionResponse(
        status=result["status"],
        platform=body.platform,
        data=result["data"],
        error=result["error"],
    )
