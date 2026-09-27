"""
PARWA ReAct Tool — CRM Integration  (F-157)

Exposes CRM-related actions to the ReAct agent:
- get_customer             Fetch full customer profile from HubSpot
- search_customers         Search customers by name/email/phone via HubSpot search API
- update_customer          Update customer fields via HubSpot Contacts PATCH
- get_interaction_history  Get recent engagements (notes/emails) for a customer
- add_note                 Attach a note to a customer record via HubSpot Notes API
- get_customer_stats       Aggregate stats: contact + deals + engagement count

All actions are scoped to *company_id* (BC-001) and return structured
ToolResult (BC-008). No mock data — when no HubSpot integration is connected
or the API call fails, the tool returns success=False with an honest error.

Fix history:
  Previously this tool returned _mock_customer() data with random names,
  emails, phones, and tiers. The ReAct agent would confidently reason
  about non-existent customers. Now it calls the real HubSpot API using
  the tenant's stored credentials (IntegrationService.get_credential_config).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── HubSpot API constants ─────────────────────────────────────────
# Same endpoints used by HubSpotAdapter.push_response_to_crm and crm_actions.py.
HUBSPOT_BASE = "https://api.hubapi.com/crm/v3/objects"
HUBSPOT_TIMEOUT = 15.0
HUBSPOT_CONTACT_PROPERTIES = [
    "email", "firstname", "lastname", "phone", "company",
    "lifecyclestage", "city", "state", "country", "createdate", "lastmodifieddate",
]


def _hubspot_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _shape_contact(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize HubSpot contact object to the shape the ReAct agent expects."""
    props = raw.get("properties", {}) or {}
    first = props.get("firstname", "") or ""
    last = props.get("lastname", "") or ""
    full_name = (first + " " + last).strip()
    return {
        "customer_id": str(raw.get("id", "")),
        "name": full_name,
        "first_name": first,
        "last_name": last,
        "email": props.get("email", "") or "",
        "phone": props.get("phone", "") or "",
        "company": props.get("company", "") or "",
        "country": props.get("country", "") or "",
        "lifecycle_stage": props.get("lifecyclestage", "") or "",
        "created_at": props.get("createdate", "") or "",
        "last_active_at": props.get("lastmodifieddate", "") or "",
    }


def _not_connected_result(action: str) -> ToolResult:
    """Honest failure when no HubSpot integration is connected for this tenant."""
    return ToolResult(
        success=False,
        error="HubSpot integration is not connected for this tenant. Connect HubSpot in Settings → Integrations to enable CRM tools.",
        data=None,
        execution_time_ms=0,
    )


def _external_error_result(action: str, error: str) -> ToolResult:
    return ToolResult(
        success=False,
        error=f"HubSpot API error during {action}: {error[:300]}",
        data=None,
        execution_time_ms=0,
    )


def _not_found_result(action: str, customer_id: str) -> ToolResult:
    return ToolResult(
        success=False,
        error=f"Customer '{customer_id}' not found in HubSpot.",
        data=None,
        execution_time_ms=0,
    )


# ── Tool Implementation ────────────────────────────────────────────


class CRMTool(BaseReactTool):
    """ReAct tool for CRM system integration — wired to real HubSpot API."""

    def __init__(self) -> None:
        # No in-memory caches — every call hits HubSpot for fresh data.
        # The IntegrationService credential lookup is cheap (one indexed query).
        pass

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "crm_integration"

    @property
    def description(self) -> str:
        return (
            "Look up customers, update records, get interaction history, "
            "manage contacts, and view customer statistics"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "get_customer",
            "search_customers",
            "update_customer",
            "get_interaction_history",
            "add_note",
            "get_customer_stats",
        ]

    # ── Schema (unchanged — keeps callers compatible) ──────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="get_customer",
                    description="Fetch full customer profile by ID from HubSpot",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "HubSpot contact ID"},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="Full customer object with contact info and lifecycle stage",
                ),
                ActionSchema(
                    name="search_customers",
                    description="Search HubSpot contacts by name, email, or phone",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query (name, email, or phone)"},
                            "limit": {"type": "integer", "description": "Max results (1-100)", "default": 10},
                        },
                        "required": ["query"],
                    },
                    required_params=["query"],
                    returns="List of matching customer summaries",
                ),
                ActionSchema(
                    name="update_customer",
                    description="Update customer fields via HubSpot Contacts PATCH",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "HubSpot contact ID to update"},
                            "name": {"type": "string", "description": "New full name (split into first/last)"},
                            "email": {"type": "string", "description": "New email address"},
                            "phone": {"type": "string", "description": "New phone number"},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="Updated customer object",
                ),
                ActionSchema(
                    name="get_interaction_history",
                    description="Get recent HubSpot engagements (notes/emails) for a customer",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "HubSpot contact ID"},
                            "limit": {"type": "integer", "description": "Max interactions (1-50)", "default": 10},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="List of engagement records with timestamps and types",
                ),
                ActionSchema(
                    name="add_note",
                    description="Attach a note to a HubSpot contact record",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "HubSpot contact ID"},
                            "content": {"type": "string", "description": "Note content"},
                            "author": {"type": "string", "description": "Note author name (prefixed to body)"},
                        },
                        "required": ["customer_id", "content"],
                    },
                    required_params=["customer_id", "content"],
                    returns="Note object with note_id",
                ),
                ActionSchema(
                    name="get_customer_stats",
                    description="Get aggregate stats for a customer (deals + engagement count)",
                    parameters={
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "HubSpot contact ID"},
                        },
                        "required": ["customer_id"],
                    },
                    required_params=["customer_id"],
                    returns="Stats dict with deal count, total deal value, and engagement score",
                ),
            ],
        )

    # ── Credential Resolution ──────────────────────────────────

    def _resolve_creds(self, company_id: str) -> Optional[dict[str, Any]]:
        """Resolve the tenant's active HubSpot credentials via IntegrationService.

        BC-001: scoped by company_id. Returns None when no HubSpot integration
        is connected.
        """
        try:
            from database.base import SessionLocal
            from app.services.integration_service import IntegrationService
            db = SessionLocal()
            try:
                return IntegrationService(db).get_credential_config(company_id, "hubspot")
            finally:
                db.close()
        except Exception as exc:
            logger.exception("crm_tool_credential_resolution_failed", extra={"error": str(exc)[:200]})
            return None

    # ── Execution Router ───────────────────────────────────────

    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """Route action to the appropriate handler."""
        if action == "__health_check__":
            return ToolResult(success=True, error=None, data={"status": "ok"}, execution_time_ms=0)

        handler = {
            "get_customer": self._get_customer,
            "search_customers": self._search_customers,
            "update_customer": self._update_customer,
            "get_interaction_history": self._get_interaction_history,
            "add_note": self._add_note,
            "get_customer_stats": self._get_customer_stats,
        }.get(action)

        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {', '.join(self.actions)}",
                data=None,
                execution_time_ms=0,
            )

        return await handler(company_id, **params)

    # ── Action Handlers ─────────────────────────────────────────

    async def _get_customer(self, company_id: str, **params: Any) -> ToolResult:
        """Fetch a customer profile from HubSpot by contact ID."""
        customer_id: str = params.get("customer_id", "")
        if not customer_id:
            return ToolResult(success=False, error="customer_id is required", data=None, execution_time_ms=0)

        creds = self._resolve_creds(company_id)
        if not creds or not creds.get("access_token"):
            return _not_connected_result("get_customer")

        headers = _hubspot_headers(creds["access_token"])
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
                resp = await client.get(
                    f"{HUBSPOT_BASE}/contacts/{customer_id}",
                    headers=headers,
                    params={"properties": ",".join(HUBSPOT_CONTACT_PROPERTIES)},
                )
        except httpx.HTTPError as exc:
            return _external_error_result("get_customer", f"network_error: {exc}")

        elapsed_ms = int((time.time() - start) * 1000)
        if resp.status_code == 404:
            return _not_found_result("get_customer", customer_id)
        if resp.status_code >= 400:
            return _external_error_result("get_customer", f"hubspot_{resp.status_code}: {resp.text[:200]}")

        contact = _shape_contact(resp.json())
        return ToolResult(success=True, error=None, data=contact, execution_time_ms=elapsed_ms)

    async def _search_customers(self, company_id: str, **params: Any) -> ToolResult:
        """Search HubSpot contacts by name/email/phone using the search API."""
        query: str = params.get("query", "").strip()
        limit: int = min(max(params.get("limit", 10), 1), 100)
        if not query:
            return ToolResult(success=False, error="query is required", data=None, execution_time_ms=0)

        creds = self._resolve_creds(company_id)
        if not creds or not creds.get("access_token"):
            return _not_connected_result("search_customers")

        headers = _hubspot_headers(creds["access_token"])
        # Build filter groups: match query against firstname, lastname, email, or phone.
        search_payload = {
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "email", "operator": "CONTAINS_TOKEN", "value": query},
                    ],
                },
                {
                    "filters": [
                        {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": query},
                    ],
                },
                {
                    "filters": [
                        {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": query},
                    ],
                },
                {
                    "filters": [
                        {"propertyName": "phone", "operator": "CONTAINS_TOKEN", "value": query},
                    ],
                },
            ],
            "properties": HUBSPOT_CONTACT_PROPERTIES,
            "limit": limit,
        }
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
                resp = await client.post(
                    f"{HUBSPOT_BASE}/contacts/search",
                    headers=headers,
                    json=search_payload,
                )
        except httpx.HTTPError as exc:
            return _external_error_result("search_customers", f"network_error: {exc}")

        elapsed_ms = int((time.time() - start) * 1000)
        if resp.status_code >= 400:
            return _external_error_result("search_customers", f"hubspot_{resp.status_code}: {resp.text[:200]}")

        results = resp.json().get("results", []) or []
        customers = [_shape_contact(r) for r in results]
        return ToolResult(
            success=True, error=None,
            data={"customers": customers, "total": len(customers), "query": query},
            execution_time_ms=elapsed_ms,
        )

    async def _update_customer(self, company_id: str, **params: Any) -> ToolResult:
        """Update customer fields via HubSpot Contacts PATCH."""
        customer_id: str = params.get("customer_id", "")
        if not customer_id:
            return ToolResult(success=False, error="customer_id is required", data=None, execution_time_ms=0)

        # Build the properties payload from accepted params.
        properties: dict[str, str] = {}
        if "email" in params and params["email"]:
            properties["email"] = str(params["email"])
        if "phone" in params and params["phone"]:
            properties["phone"] = str(params["phone"])
        if "name" in params and params["name"]:
            # HubSpot stores first/last separately.
            parts = str(params["name"]).split(maxsplit=1)
            properties["firstname"] = parts[0]
            if len(parts) > 1:
                properties["lastname"] = parts[1]

        if not properties:
            return ToolResult(
                success=False,
                error="No fields to update. Provide name, email, or phone.",
                data=None, execution_time_ms=0,
            )

        creds = self._resolve_creds(company_id)
        if not creds or not creds.get("access_token"):
            return _not_connected_result("update_customer")

        headers = _hubspot_headers(creds["access_token"])
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
                resp = await client.patch(
                    f"{HUBSPOT_BASE}/contacts/{customer_id}",
                    headers=headers,
                    json={"properties": properties},
                )
        except httpx.HTTPError as exc:
            return _external_error_result("update_customer", f"network_error: {exc}")

        elapsed_ms = int((time.time() - start) * 1000)
        if resp.status_code == 404:
            return _not_found_result("update_customer", customer_id)
        if resp.status_code >= 400:
            return _external_error_result("update_customer", f"hubspot_{resp.status_code}: {resp.text[:200]}")

        updated = _shape_contact(resp.json())
        updated["updated_fields"] = list(properties.keys())
        return ToolResult(success=True, error=None, data=updated, execution_time_ms=elapsed_ms)

    async def _get_interaction_history(self, company_id: str, **params: Any) -> ToolResult:
        """Get recent HubSpot engagements associated with a contact.

        Uses the v3 associations API: /contacts/{id}/associations/engagements
        Then batch-reads the engagement objects.
        """
        customer_id: str = params.get("customer_id", "")
        limit: int = min(max(params.get("limit", 10), 1), 50)
        if not customer_id:
            return ToolResult(success=False, error="customer_id is required", data=None, execution_time_ms=0)

        creds = self._resolve_creds(company_id)
        if not creds or not creds.get("access_token"):
            return _not_connected_result("get_interaction_history")

        headers = _hubspot_headers(creds["access_token"])
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
                # 1. Get associated engagement IDs.
                assoc = await client.get(
                    f"{HUBSPOT_BASE}/contacts/{customer_id}/associations/engagements",
                    headers=headers,
                )
                if assoc.status_code == 404:
                    return _not_found_result("get_interaction_history", customer_id)
                if assoc.status_code >= 400:
                    return _external_error_result("get_interaction_history", f"hubspot_{assoc.status_code}: {assoc.text[:200]}")

                engagement_ids = [str(r.get("id")) for r in assoc.json().get("results", []) if r.get("id")]
                if not engagement_ids:
                    elapsed = int((time.time() - start) * 1000)
                    return ToolResult(
                        success=True, error=None,
                        data={"customer_id": customer_id, "interactions": [], "total": 0},
                        execution_time_ms=elapsed,
                    )

                # 2. Batch-read engagement objects (max 100 per call).
                batch = await client.post(
                    f"{HUBSPOT_BASE}/engagements/batch/read",
                    headers=headers,
                    json={"inputs": [{"id": eid} for eid in engagement_ids[:limit]]},
                )
        except httpx.HTTPError as exc:
            return _external_error_result("get_interaction_history", f"network_error: {exc}")

        elapsed_ms = int((time.time() - start) * 1000)
        if batch.status_code >= 400:
            return _external_error_result("get_interaction_history", f"hubspot_{batch.status_code}: {batch.text[:200]}")

        interactions: list[dict[str, Any]] = []
        for r in batch.json().get("results", []):
            props = r.get("properties", {}) or {}
            interactions.append({
                "interaction_id": str(r.get("id", "")),
                "customer_id": customer_id,
                "type": props.get("hs_engagement_type", "NOTE"),
                "subject": props.get("hs_engagement_source", "") or props.get("hs_note_body", "")[:80],
                "summary": (props.get("hs_note_body", "") or props.get("hs_email_subject", ""))[:200],
                "created_at": props.get("hs_timestamp", "") or props.get("hs_createdate", ""),
            })
        return ToolResult(
            success=True, error=None,
            data={"customer_id": customer_id, "interactions": interactions, "total": len(interactions)},
            execution_time_ms=elapsed_ms,
        )

    async def _add_note(self, company_id: str, **params: Any) -> ToolResult:
        """Attach a note to a HubSpot contact record.

        Two-step: POST /objects/notes to create the note, then PUT
        /objects/notes/{id}/associations/contact/{contact_id}/note_to_contact
        to associate it.
        """
        customer_id: str = params.get("customer_id", "")
        content: str = params.get("content", "").strip()
        author: Optional[str] = params.get("author")
        if not customer_id:
            return ToolResult(success=False, error="customer_id is required", data=None, execution_time_ms=0)
        if not content:
            return ToolResult(success=False, error="Note content cannot be empty", data=None, execution_time_ms=0)

        creds = self._resolve_creds(company_id)
        if not creds or not creds.get("access_token"):
            return _not_connected_result("add_note")

        headers = _hubspot_headers(creds["access_token"])
        body = f"[{author}] {content}" if author else content
        note_payload = {
            "properties": {
                "hs_note_body": body[:32000],
                "hs_timestamp": str(int(time.time() * 1000)),
            },
        }
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
                resp = await client.post(f"{HUBSPOT_BASE}/notes", headers=headers, json=note_payload)
                if resp.status_code >= 400:
                    return _external_error_result("add_note", f"hubspot_{resp.status_code}: {resp.text[:200]}")
                note_id = resp.json().get("id", "")
                if not note_id:
                    return _external_error_result("add_note", "HubSpot returned no note id")

                # Associate the note with the contact.
                assoc = await client.put(
                    f"{HUBSPOT_BASE}/notes/{note_id}/associations/contact/{customer_id}/note_to_contact",
                    headers=headers,
                )
                associated = assoc.status_code < 400
                if not associated:
                    logger.warning(
                        "crm_tool_note_association_failed",
                        extra={"note_id": note_id, "contact_id": customer_id, "status": assoc.status_code},
                    )
        except httpx.HTTPError as exc:
            return _external_error_result("add_note", f"network_error: {exc}")

        elapsed_ms = int((time.time() - start) * 1000)
        return ToolResult(
            success=True, error=None,
            data={
                "note_id": note_id,
                "customer_id": customer_id,
                "content": body,
                "associated": associated,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=elapsed_ms,
        )

    async def _get_customer_stats(self, company_id: str, **params: Any) -> ToolResult:
        """Aggregate stats: contact info + deal count + total deal value."""
        customer_id: str = params.get("customer_id", "")
        if not customer_id:
            return ToolResult(success=False, error="customer_id is required", data=None, execution_time_ms=0)

        creds = self._resolve_creds(company_id)
        if not creds or not creds.get("access_token"):
            return _not_connected_result("get_customer_stats")

        headers = _hubspot_headers(creds["access_token"])
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=HUBSPOT_TIMEOUT) as client:
                # 1. Fetch contact.
                contact_resp = await client.get(
                    f"{HUBSPOT_BASE}/contacts/{customer_id}",
                    headers=headers,
                    params={"properties": ",".join(HUBSPOT_CONTACT_PROPERTIES)},
                )
                if contact_resp.status_code == 404:
                    return _not_found_result("get_customer_stats", customer_id)
                if contact_resp.status_code >= 400:
                    return _external_error_result("get_customer_stats", f"hubspot_{contact_resp.status_code}: {contact_resp.text[:200]}")
                contact = _shape_contact(contact_resp.json())

                # 2. Fetch associated deals.
                deals_resp = await client.get(
                    f"{HUBSPOT_BASE}/contacts/{customer_id}/associations/deals",
                    headers=headers,
                )
                deal_ids = []
                if deals_resp.status_code < 400:
                    deal_ids = [str(r.get("id")) for r in deals_resp.json().get("results", []) if r.get("id")]

                # 3. Batch-read deal properties for totals.
                total_value = 0.0
                deal_count = len(deal_ids)
                if deal_ids:
                    batch = await client.post(
                        f"{HUBSPOT_BASE}/deals/batch/read",
                        headers=headers,
                        json={"inputs": [{"id": did} for did in deal_ids[:100]]},
                        params={"properties": "amount,dealname,dealstage,closedate"},
                    )
                    if batch.status_code < 400:
                        for r in batch.json().get("results", []):
                            props = r.get("properties", {}) or {}
                            amount_str = props.get("amount", "") or "0"
                            try:
                                total_value += float(amount_str)
                            except (TypeError, ValueError):
                                pass
        except httpx.HTTPError as exc:
            return _external_error_result("get_customer_stats", f"network_error: {exc}")

        elapsed_ms = int((time.time() - start) * 1000)
        return ToolResult(
            success=True, error=None,
            data={
                "customer_id": customer_id,
                "name": contact["name"],
                "email": contact["email"],
                "lifecycle_stage": contact["lifecycle_stage"],
                "deal_count": deal_count,
                "total_deal_value": round(total_value, 2),
                "last_active_at": contact["last_active_at"],
            },
            execution_time_ms=elapsed_ms,
        )
