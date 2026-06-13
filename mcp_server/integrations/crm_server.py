"""
PARWA MCP — CRM Server (v2.0.0 — Wired to Real Backend)

Provides CRM platform integration tools.
Wired to real backend CRM integration via httpx passthrough.

When an integration is connected (HubSpot/Salesforce/Pipedrive credentials stored),
this server proxies requests through the backend ExternalToolBus.

When no integration is connected, returns honest "not connected" status instead of fake data.
"""

from __future__ import annotations

import os

import httpx
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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5100")


class CRMServer(MCPServerBase):
    """MCP sub-server for CRM platform integrations — wired to real backend."""

    name = "crm_server"
    description = "CRM platform integration (HubSpot, Salesforce, Pipedrive) — wired to backend"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register CRM tools."""
        registry.register_tool(
            ToolDefinition(
                name="crm_get_contact",
                description="Look up a CRM contact by ID, email, or phone number. "
                            "Returns contact details including notes and activity history.",
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
                        "company_id": {"type": "string"},
                    },
                },
                tags=["crm", "contact", "hubspot", "salesforce"],
            ),
            handler=self._invoke_get_contact,
        )

        registry.register_tool(
            ToolDefinition(
                name="crm_create_note",
                description="Add a note to a CRM contact record.",
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
                        "company_id": {"type": "string"},
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
                description="Get deals/opportunities associated with a contact.",
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
                        "company_id": {"type": "string"},
                    },
                    "required": ["contact_id"],
                },
                tags=["crm", "deals", "opportunities"],
            ),
            handler=self._invoke_get_deals,
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

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend CRM integration API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "crm_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("crm_backend_failed", path=path, error=str(exc)[:200])
        return None

    def _not_connected_response(self, tool_name: str, platform: str) -> ToolInvokeResponse:
        """Return an honest 'not connected' response instead of fake data."""
        return ToolInvokeResponse(
            success=False,
            tool_name=tool_name,
            error=f"CRM platform '{platform}' is not connected. Connect your {platform} account in Settings → Integrations to enable CRM lookups.",
            metadata={"platform": platform, "status": "not_connected"},
        )

    async def _invoke_get_contact(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_get_contact tool invocation — wired to backend."""
        params = parameters or {}
        platform = params.get("platform", "hubspot")

        logger.info("crm_get_contact_invoked", platform=platform)

        # Try backend integration endpoint
        payload = {
            "action": "get_contact",
            "platform": platform,
            "contact_id": params.get("contact_id"),
            "email": params.get("email"),
            "phone": params.get("phone"),
        }
        if params.get("company_id"):
            payload["company_id"] = params["company_id"]

        data = await self._backend_call("POST", "/api/v1/integrations/crm/contact", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="crm_get_contact",
                data=data,
                metadata={"platform": platform, "source": "backend"},
            )

        # No integration connected — honest response
        return self._not_connected_response("crm_get_contact", platform)

    async def _invoke_create_note(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_create_note tool invocation — wired to backend."""
        params = parameters or {}
        contact_id = params.get("contact_id", "")
        platform = params.get("platform", "hubspot")

        logger.info("crm_create_note_invoked", contact_id=contact_id, platform=platform)

        payload = {
            "action": "create_note",
            "platform": platform,
            "contact_id": contact_id,
            "note": params.get("note", ""),
        }
        if params.get("company_id"):
            payload["company_id"] = params["company_id"]

        data = await self._backend_call("POST", "/api/v1/integrations/crm/note", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="crm_create_note",
                data=data,
                metadata={"platform": platform, "source": "backend"},
            )

        return self._not_connected_response("crm_create_note", platform)

    async def _invoke_get_deals(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_get_deals tool invocation — wired to backend."""
        params = parameters or {}
        contact_id = params.get("contact_id", "")
        platform = params.get("platform", "hubspot")

        logger.info("crm_get_deals_invoked", contact_id=contact_id, platform=platform)

        payload = {
            "action": "get_deals",
            "platform": platform,
            "contact_id": contact_id,
        }
        if params.get("company_id"):
            payload["company_id"] = params["company_id"]

        data = await self._backend_call("POST", "/api/v1/integrations/crm/deals", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="crm_get_deals",
                data=data,
                metadata={"platform": platform, "source": "backend"},
            )

        return self._not_connected_response("crm_get_deals", platform)


# Singleton instance
crm_server = CRMServer()
