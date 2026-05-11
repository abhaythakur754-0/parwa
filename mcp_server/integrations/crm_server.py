"""
PARWA MCP — CRM Server

Provides CRM platform integration tools.
Supports HubSpot, Salesforce, and Pipedrive
for contact lookup, deal tracking, and activity logging.
"""

from __future__ import annotations

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


class CRMServer(MCPServerBase):
    """MCP sub-server for CRM platform integrations."""

    name = "crm_server"
    description = "CRM platform integration (HubSpot, Salesforce, Pipedrive)"
    category = ToolCategory.INTEGRATION
    version = "1.0.0"

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

    async def _invoke_get_contact(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle crm_get_contact tool invocation."""
        params = parameters or {}
        contact_id = params.get("contact_id")
        email = params.get("email")
        platform = params.get("platform", "hubspot")

        logger.info(
            "crm_contact_lookup",
            contact_id=contact_id,
            email=email,
            platform=platform,
        )

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

        logger.info("crm_note_created", contact_id=contact_id, note_len=len(note))

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

        logger.info("crm_deals_retrieved", contact_id=contact_id)

        return ToolInvokeResponse(
            success=True,
            tool_name="crm_get_deals",
            data={"deals": [], "total": 0},
            metadata={"status": "placeholder"},
        )


# Singleton instance
crm_server = CRMServer()
