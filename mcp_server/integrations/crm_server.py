"""
PARWA MCP — CRM Server

Provides CRM platform integration tools.
Supports HubSpot (primary), Salesforce, and Pipedrive
for contact lookup, deal tracking, company management,
note creation, and activity logging.

Connected to real HubSpot CRM API via HubSpotClient when a
HubSpot integration is configured. Falls back to placeholder
data when no integration is available.

Day 6 Upgrades (v2.0.0):
  - Live HubSpot API integration for all CRM tools
  - New tools: crm_create_contact, crm_update_contact,
    crm_get_company, crm_list_deals, crm_search_contacts
  - HubSpotClient integration via _get_hubspot_client helper
  - Real API calls when company_id + active HubSpot integration present
  - Fallback to placeholder when no integration configured
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    CRMContactRequest,
    CRMContactResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.crm_server")

# Backend URL for fetching integration credentials
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


def _get_hubspot_client(company_id: str) -> Optional[Any]:
    """Get a HubSpotClient for a company's active HubSpot integration.

    Fetches the integration credentials from the backend API
    and creates a configured HubSpotClient instance.

    Args:
        company_id: PARWA company ID.

    Returns:
        HubSpotClient instance or None if no integration found.
    """
    try:
        import httpx
        from app.clients.hubspot_client import HubSpotClient

        # Try to get HubSpot integration from backend
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{BACKEND_URL}/api/integrations",
                params={"status": "active"},
                headers={"X-Company-Id": company_id},
            )

            if resp.status_code != 200:
                return None

            integrations = resp.json()
            for integration in integrations:
                if integration.get("type") == "hubspot" and integration.get("status") == "active":
                    config = integration.get("config", {})
                    access_token = config.get("access_token", "")

                    if access_token:
                        return HubSpotClient(access_token=access_token)

    except ImportError:
        logger.warning("hubspot_client_not_available")
    except Exception as exc:
        logger.warning("hubspot_client_fetch_failed error=%s", str(exc)[:200])

    return None


def _get_hubspot_client_from_config(config: Dict[str, Any]) -> Optional[Any]:
    """Create a HubSpotClient directly from a config dict.

    Used when integration config is already available (e.g., from
    the MCP context) and we don't need to fetch from the backend.

    Args:
        config: Dict with access_token.

    Returns:
        HubSpotClient instance or None.
    """
    try:
        from app.clients.hubspot_client import HubSpotClient

        access_token = config.get("access_token", "")

        if access_token:
            return HubSpotClient(access_token=access_token)
    except ImportError:
        logger.warning("hubspot_client_not_available")
    except Exception as exc:
        logger.warning("hubspot_client_creation_failed error=%s", str(exc)[:200])

    return None


class CRMServer(MCPServerBase):
    """MCP sub-server for CRM platform integrations.

    Connects to real HubSpot API when integration is available.
    Provides tools for contact management, deal tracking,
    company lookup, note creation, and contact search.
    """

    name = "crm_server"
    description = "CRM platform integration (HubSpot, Salesforce, Pipedrive)"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register CRM tools."""
        # ── Existing tools (upgraded with live API) ────────────

        registry.register_tool(
            ToolDefinition(
                name="crm_get_contact",
                description="Look up a CRM contact by ID, email, or phone number. "
                            "Returns contact details including notes and activity history. "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                        "platform": {
                            "type": "string",
                            "enum": ["hubspot", "salesforce", "pipedrive"],
                            "default": "hubspot",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                        "properties": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "HubSpot contact properties to include",
                        },
                    },
                },
                tags=["crm", "contact", "hubspot", "salesforce"],
            ),
            handler=self._invoke_get_contact,
        )

        registry.register_tool(
            ToolDefinition(
                name="crm_create_note",
                description="Add a note to a CRM contact record. "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "string"},
                        "note": {"type": "string"},
                        "platform": {
                            "type": "string",
                            "default": "hubspot",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                    },
                    "required": ["contact_id", "note"],
                },
                tags=["crm", "note", "activity"],
            ),
            handler=self._invoke_create_note,
        )

        registry.register_tool(
            ToolDefinition(
                name="crm_get_deals",
                description="Get deals/opportunities associated with a contact. "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "string"},
                        "platform": {
                            "type": "string",
                            "default": "hubspot",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": ["contact_id"],
                },
                tags=["crm", "deals", "opportunities"],
            ),
            handler=self._invoke_get_deals,
        )

        # ── Day 6: New CRM Tools ──────────────────────────────

        registry.register_tool(
            ToolDefinition(
                name="crm_create_contact",
                description="Create a new CRM contact. "
                            "Input: contact properties (email, firstname, lastname, phone, company, jobtitle). "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "description": "Contact email address"},
                        "firstname": {"type": "string", "description": "First name"},
                        "lastname": {"type": "string", "description": "Last name"},
                        "phone": {"type": "string", "description": "Phone number"},
                        "company": {"type": "string", "description": "Company name"},
                        "jobtitle": {"type": "string", "description": "Job title"},
                        "platform": {
                            "type": "string",
                            "default": "hubspot",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                    },
                    "required": ["email", "company_id"],
                },
                tags=["crm", "contact", "create", "hubspot"],
            ),
            handler=self._invoke_create_contact,
        )

        registry.register_tool(
            ToolDefinition(
                name="crm_update_contact",
                description="Update an existing CRM contact's properties. "
                            "Input: contact_id + properties to update. "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "contact_id": {"type": "string", "description": "HubSpot contact ID"},
                        "properties": {
                            "type": "object",
                            "description": "Properties to update (key-value pairs)",
                        },
                        "platform": {
                            "type": "string",
                            "default": "hubspot",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                    },
                    "required": ["contact_id", "properties", "company_id"],
                },
                tags=["crm", "contact", "update", "hubspot"],
            ),
            handler=self._invoke_update_contact,
        )

        registry.register_tool(
            ToolDefinition(
                name="crm_get_company",
                description="Get a company record from CRM by company ID. "
                            "Returns company details including industry, website, and address. "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "company_id": {"type": "string", "description": "HubSpot company ID"},
                        "platform": {
                            "type": "string",
                            "default": "hubspot",
                        },
                        "company_id_param": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                        "properties": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "HubSpot company properties to include",
                        },
                    },
                    "required": ["company_id"],
                },
                tags=["crm", "company", "hubspot"],
            ),
            handler=self._invoke_get_company,
        )

        registry.register_tool(
            ToolDefinition(
                name="crm_list_deals",
                description="List deals from CRM with optional filters. "
                            "Returns deal pipeline information, stages, and amounts. "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 50},
                        "after": {"type": "string", "description": "Pagination cursor from previous response"},
                        "platform": {
                            "type": "string",
                            "default": "hubspot",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                        "properties": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Deal properties to include",
                        },
                    },
                },
                tags=["crm", "deals", "list", "pipeline"],
            ),
            handler=self._invoke_list_deals,
        )

        registry.register_tool(
            ToolDefinition(
                name="crm_search_contacts",
                description="Search CRM contacts by query string. "
                            "Matches against email, name, phone, and other contact fields. "
                            "Uses real HubSpot API when integration is configured.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (email, name, phone, etc.)"},
                        "limit": {"type": "integer", "default": 50},
                        "platform": {
                            "type": "string",
                            "default": "hubspot",
                        },
                        "company_id": {
                            "type": "string",
                            "description": "PARWA company ID for HubSpot integration lookup",
                        },
                        "properties": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Contact properties to include in results",
                        },
                    },
                    "required": ["query"],
                },
                tags=["crm", "contact", "search", "hubspot"],
            ),
            handler=self._invoke_search_contacts,
        )

    def get_router(self) -> APIRouter:
        """Return the CRM REST router."""
        router = APIRouter(prefix="/integrations/crm", tags=["Integration — CRM"])

        @router.post("/contact", response_model=CRMContactResponse)
        async def get_contact(request: CRMContactRequest) -> CRMContactResponse:
            """Look up a CRM contact via REST."""
            result = await self._invoke_get_contact(request.model_dump())
            if result.success and result.data:
                return CRMContactResponse(**result.data)
            return CRMContactResponse(contact_id="", name="Not found")

        return router

    # ── Helper ──────────────────────────────────────────────────

    @staticmethod
    def _extract_contact_properties(hubspot_contact: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized contact data from HubSpot contact object."""
        props = hubspot_contact.get("properties", {})
        return {
            "contact_id": str(hubspot_contact.get("id", "")),
            "email": props.get("email", ""),
            "first_name": props.get("firstname", ""),
            "last_name": props.get("lastname", ""),
            "phone": props.get("phone", ""),
            "company": props.get("company", ""),
            "job_title": props.get("jobtitle", ""),
            "lifecycle_stage": props.get("lifecyclestage", ""),
            "created_at": props.get("createdate", ""),
            "updated_at": props.get("lastmodifieddate", ""),
        }

    @staticmethod
    def _extract_deal_properties(hubspot_deal: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized deal data from HubSpot deal object."""
        props = hubspot_deal.get("properties", {})
        return {
            "deal_id": str(hubspot_deal.get("id", "")),
            "name": props.get("dealname", ""),
            "stage": props.get("dealstage", ""),
            "amount": props.get("amount", "0"),
            "pipeline": props.get("pipeline", ""),
            "close_date": props.get("closedate", ""),
            "deal_type": props.get("dealtype", ""),
            "created_at": props.get("createdate", ""),
        }

    @staticmethod
    def _extract_company_properties(hubspot_company: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized company data from HubSpot company object."""
        props = hubspot_company.get("properties", {})
        return {
            "company_id": str(hubspot_company.get("id", "")),
            "name": props.get("name", ""),
            "website": props.get("domain", ""),
            "industry": props.get("industry", ""),
            "city": props.get("city", ""),
            "state": props.get("state", ""),
            "country": props.get("country", ""),
            "phone": props.get("phone", ""),
            "created_at": props.get("createdate", ""),
        }

    # ── Tool Handlers ───────────────────────────────────────────

    async def _invoke_get_contact(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_get_contact tool invocation."""
        params = parameters or {}
        contact_id = params.get("contact_id")
        email = params.get("email")
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id", "")
        requested_properties = params.get("properties")

        logger.info(
            "crm_contact_lookup contact_id=%s email=%s platform=%s",
            contact_id, email, platform,
        )

        # Try real HubSpot API
        if platform == "hubspot" and company_id:
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                # If email provided but no contact_id, search first
                if email and not contact_id:
                    search_result = await hubspot_client.search_contacts(
                        query=email,
                        limit=1,
                        properties=requested_properties or ["email", "firstname", "lastname", "phone", "company", "jobtitle", "lifecyclestage"],
                    )
                    if search_result.success and search_result.data:
                        results = search_result.data.get("results", [])
                        if results:
                            contact_data = self._extract_contact_properties(results[0])
                            return ToolInvokeResponse(
                                success=True,
                                tool_name="crm_get_contact",
                                data=contact_data,
                                metadata={"platform": "hubspot", "source": "live_api"},
                            )

                # Direct lookup by contact_id
                if contact_id:
                    result = await hubspot_client.get_contact(
                        contact_id,
                        properties=requested_properties or ["email", "firstname", "lastname", "phone", "company", "jobtitle", "lifecyclestage"],
                    )
                    if result.success:
                        contact_data = self._extract_contact_properties(result.data)
                        return ToolInvokeResponse(
                            success=True,
                            tool_name="crm_get_contact",
                            data=contact_data,
                            metadata={"platform": "hubspot", "source": "live_api"},
                        )
                    else:
                        return ToolInvokeResponse(
                            success=False,
                            tool_name="crm_get_contact",
                            error=f"HubSpot contact lookup failed: {result.error}",
                        )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_get_contact",
            data={
                "contact_id": contact_id or f"crm_placeholder_{id(parameters) % 100000}",
                "name": "Sample Contact",
                "email": email or "contact@example.com",
                "phone": "",
                "company": "Sample Company",
                "notes": [],
                "metadata": {"platform": platform},
            },
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_create_note(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_create_note tool invocation."""
        params = parameters or {}
        contact_id = params.get("contact_id", "")
        note = params.get("note", "")
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id", "")

        logger.info("crm_note_created contact_id=%s note_len=%d", contact_id, len(note))

        # Try real HubSpot API
        if platform == "hubspot" and company_id and contact_id:
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                result = await hubspot_client.create_note(
                    contact_id=contact_id,
                    body=note,
                )
                if result.success:
                    note_data = result.data
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="crm_create_note",
                        data={
                            "note_id": str(note_data.get("id", "")),
                            "contact_id": contact_id,
                            "body": note,
                            "created_at": note_data.get("properties", {}).get("hs_created_date", ""),
                        },
                        metadata={"platform": "hubspot", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="crm_create_note",
                        error=f"HubSpot note creation failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_create_note",
            data={
                "note_id": f"note_placeholder_{id(parameters) % 100000}",
                "contact_id": contact_id,
                "message": "Note created successfully",
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_get_deals(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_get_deals tool invocation."""
        params = parameters or {}
        contact_id = params.get("contact_id", "")
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id", "")
        limit = params.get("limit", 50)

        logger.info("crm_deals_retrieved contact_id=%s", contact_id)

        # Try real HubSpot API — get deals associated with contact
        if platform == "hubspot" and company_id and contact_id:
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                # Get deal associations for this contact
                assoc_result = await hubspot_client.get_deal_associations(
                    deal_id=contact_id,
                    to_object_type="deals",
                )
                if assoc_result.success:
                    deal_ids = [
                        r.get("id", "")
                        for r in assoc_result.data.get("results", [])
                    ]

                    # Fetch each deal's details
                    deal_list = []
                    for did in deal_ids[:limit]:
                        deal_result = await hubspot_client.get_deal(did)
                        if deal_result.success:
                            deal_list.append(self._extract_deal_properties(deal_result.data))

                    return ToolInvokeResponse(
                        success=True,
                        tool_name="crm_get_deals",
                        data={
                            "deals": deal_list,
                            "total": len(deal_list),
                            "contact_id": contact_id,
                        },
                        metadata={"platform": "hubspot", "source": "live_api"},
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_get_deals",
            data={"deals": [], "total": 0},
            metadata={"status": "placeholder"},
        )

    # ── Day 6: New Tool Handlers ────────────────────────────────

    async def _invoke_create_contact(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_create_contact tool invocation."""
        params = parameters or {}
        email = params.get("email", "")
        firstname = params.get("firstname", "")
        lastname = params.get("lastname", "")
        phone = params.get("phone", "")
        company = params.get("company", "")
        jobtitle = params.get("jobtitle", "")
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id", "")

        logger.info("crm_create_contact email=%s company_id=%s", email, company_id)

        if not email:
            return ToolInvokeResponse(
                success=False,
                tool_name="crm_create_contact",
                error="email is required",
            )

        if not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="crm_create_contact",
                error="company_id is required",
            )

        # Build HubSpot properties
        contact_properties = {"email": email}
        if firstname:
            contact_properties["firstname"] = firstname
        if lastname:
            contact_properties["lastname"] = lastname
        if phone:
            contact_properties["phone"] = phone
        if company:
            contact_properties["company"] = company
        if jobtitle:
            contact_properties["jobtitle"] = jobtitle

        # Try real HubSpot API
        if platform == "hubspot":
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                result = await hubspot_client.create_contact(
                    properties=contact_properties,
                )
                if result.success:
                    contact_data = self._extract_contact_properties(result.data)
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="crm_create_contact",
                        data=contact_data,
                        metadata={"platform": "hubspot", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="crm_create_contact",
                        error=f"HubSpot contact creation failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_create_contact",
            data={
                "contact_id": f"crm_new_{id(parameters) % 100000}",
                "email": email,
                "first_name": firstname,
                "last_name": lastname,
                "phone": phone,
                "company": company,
                "job_title": jobtitle,
                "message": "Contact created (placeholder — no HubSpot integration)",
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_update_contact(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_update_contact tool invocation."""
        params = parameters or {}
        contact_id = params.get("contact_id", "")
        properties = params.get("properties", {})
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id", "")

        logger.info("crm_update_contact contact_id=%s company_id=%s", contact_id, company_id)

        if not contact_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="crm_update_contact",
                error="contact_id is required",
            )

        if not company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="crm_update_contact",
                error="company_id is required",
            )

        if not properties:
            return ToolInvokeResponse(
                success=False,
                tool_name="crm_update_contact",
                error="properties dict is required (cannot be empty)",
            )

        # Try real HubSpot API
        if platform == "hubspot":
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                result = await hubspot_client.update_contact(
                    contact_id=contact_id,
                    properties=properties,
                )
                if result.success:
                    contact_data = self._extract_contact_properties(result.data)
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="crm_update_contact",
                        data=contact_data,
                        metadata={"platform": "hubspot", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="crm_update_contact",
                        error=f"HubSpot contact update failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_update_contact",
            data={
                "contact_id": contact_id,
                "updated_properties": list(properties.keys()),
                "message": "Contact updated (placeholder — no HubSpot integration)",
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_get_company(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_get_company tool invocation."""
        params = parameters or {}
        hs_company_id = params.get("company_id", "")
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id_param", "")
        requested_properties = params.get("properties")

        logger.info("crm_get_company hubspot_company_id=%s", hs_company_id)

        if not hs_company_id:
            return ToolInvokeResponse(
                success=False,
                tool_name="crm_get_company",
                error="company_id is required",
            )

        # Try real HubSpot API
        if platform == "hubspot" and company_id:
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                result = await hubspot_client.get_company(
                    hs_company_id,
                    properties=requested_properties or ["name", "domain", "industry", "city", "state", "country", "phone"],
                )
                if result.success:
                    company_data = self._extract_company_properties(result.data)
                    return ToolInvokeResponse(
                        success=True,
                        tool_name="crm_get_company",
                        data=company_data,
                        metadata={"platform": "hubspot", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="crm_get_company",
                        error=f"HubSpot company lookup failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_get_company",
            data={
                "company_id": hs_company_id,
                "name": "Sample Company",
                "website": "example.com",
                "industry": "Technology",
                "phone": "",
            },
            metadata={"platform": platform, "status": "placeholder"},
        )

    async def _invoke_list_deals(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_list_deals tool invocation."""
        params = parameters or {}
        limit = params.get("limit", 50)
        after = params.get("after")
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id", "")
        requested_properties = params.get("properties")

        logger.info("crm_list_deals company_id=%s limit=%d", company_id, limit)

        # Try real HubSpot API
        if platform == "hubspot" and company_id:
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                result = await hubspot_client.list_deals(
                    limit=limit,
                    after=after,
                    properties=requested_properties or ["dealname", "dealstage", "amount", "pipeline", "closedate", "dealtype"],
                )
                if result.success:
                    raw_deals = result.data.get("results", [])
                    deal_list = [self._extract_deal_properties(d) for d in raw_deals]
                    paging = result.data.get("paging", {})
                    next_cursor = ""
                    if paging.get("next"):
                        next_cursor = paging["next"].get("after", "")

                    return ToolInvokeResponse(
                        success=True,
                        tool_name="crm_list_deals",
                        data={
                            "deals": deal_list,
                            "total": len(deal_list),
                            "after": next_cursor,
                            "has_more": bool(next_cursor),
                        },
                        metadata={"platform": "hubspot", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="crm_list_deals",
                        error=f"HubSpot deals list failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_list_deals",
            data={"deals": [], "total": 0, "after": "", "has_more": False},
            metadata={"status": "placeholder"},
        )

    async def _invoke_search_contacts(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_search_contacts tool invocation."""
        params = parameters or {}
        query = params.get("query", "")
        limit = params.get("limit", 50)
        platform = params.get("platform", "hubspot")
        company_id = params.get("company_id", "")
        requested_properties = params.get("properties")

        logger.info("crm_search_contacts query=%s company_id=%s", query, company_id)

        if not query:
            return ToolInvokeResponse(
                success=False,
                tool_name="crm_search_contacts",
                error="query is required",
            )

        # Try real HubSpot API
        if platform == "hubspot" and company_id:
            hubspot_client = _get_hubspot_client(company_id)
            if hubspot_client:
                result = await hubspot_client.search_contacts(
                    query=query,
                    limit=limit,
                    properties=requested_properties or ["email", "firstname", "lastname", "phone", "company", "jobtitle", "lifecyclestage"],
                )
                if result.success:
                    raw_contacts = result.data.get("results", [])
                    contact_list = [self._extract_contact_properties(c) for c in raw_contacts]

                    return ToolInvokeResponse(
                        success=True,
                        tool_name="crm_search_contacts",
                        data={
                            "contacts": contact_list,
                            "total": len(contact_list),
                            "query": query,
                        },
                        metadata={"platform": "hubspot", "source": "live_api"},
                    )
                else:
                    return ToolInvokeResponse(
                        success=False,
                        tool_name="crm_search_contacts",
                        error=f"HubSpot contact search failed: {result.error}",
                    )

        # Fallback: placeholder response
        return ToolInvokeResponse(
            success=True,
            tool_name="crm_search_contacts",
            data={"contacts": [], "total": 0, "query": query},
            metadata={"status": "placeholder"},
        )


# Singleton instance
crm_server = CRMServer()
