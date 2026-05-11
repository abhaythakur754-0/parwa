"""
PARWA MCP — Ticketing Server

Provides support ticket lifecycle tools.
Supports ticket creation, updates, transitions, and search.
"""

from __future__ import annotations

from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.models import (
    TicketCreateRequest,
    TicketResponse,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.ticketing_server")


class TicketingServer(MCPServerBase):
    """MCP sub-server for support ticket operations."""

    name = "ticketing_server"
    description = "Support ticket lifecycle management (create, update, search)"
    category = ToolCategory.INTEGRATION
    version = "1.0.0"

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register ticketing tools."""
        registry.register_tool(
            ToolDefinition(
                name="ticket_create",
                description="Create a new support ticket with priority, category, and tags.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "urgent"],
                            "default": "medium",
                        },
                        "category": {"type": "string"},
                        "customer_id": {"type": "string"},
                        "channel": {"type": "string", "default": "api"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["subject", "description"],
                },
                tags=["ticket", "create", "support"],
            ),
            handler=self._invoke_ticket_create,
        )

        registry.register_tool(
            ToolDefinition(
                name="ticket_get",
                description="Retrieve ticket details by ticket ID.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                    },
                    "required": ["ticket_id"],
                },
                tags=["ticket", "get", "details"],
            ),
            handler=self._invoke_ticket_get,
        )

        registry.register_tool(
            ToolDefinition(
                name="ticket_update_status",
                description="Update a ticket's status (open, in_progress, pending, resolved, closed).",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["open", "in_progress", "pending", "resolved", "closed"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["ticket_id", "status"],
                },
                tags=["ticket", "update", "status", "transition"],
            ),
            handler=self._invoke_ticket_update_status,
        )

        registry.register_tool(
            ToolDefinition(
                name="ticket_search",
                description="Search tickets by query, filters, and sorting.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "status": {"type": "string"},
                        "priority": {"type": "string"},
                        "customer_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                    },
                },
                tags=["ticket", "search", "query"],
            ),
            handler=self._invoke_ticket_search,
        )

    def get_router(self) -> APIRouter:
        """Return the ticketing REST router."""
        router = APIRouter(prefix="/integrations/ticketing", tags=["Integration — Ticketing"])

        @router.post("/create", response_model=TicketResponse)
        async def create_ticket(request: TicketCreateRequest) -> TicketResponse:
            """Create a ticket via REST."""
            result = await self._invoke_ticket_create(request.model_dump())
            if result.success and result.data:
                return TicketResponse(**result.data)
            return TicketResponse(message="Failed to create ticket")

        return router

    async def _invoke_ticket_create(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_create tool invocation."""
        params = parameters or {}
        subject = params.get("subject", "")
        priority = params.get("priority", "medium")

        logger.info(
            "ticket_created",
            subject=subject[:80],
            priority=priority,
        )

        return ToolInvokeResponse(
            success=True,
            tool_name="ticket_create",
            data={
                "ticket_id": f"TKT_placeholder_{id(parameters) % 100000}",
                "status": "open",
                "subject": subject,
                "priority": priority,
                "message": "Ticket created successfully",
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_ticket_get(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_get tool invocation."""
        params = parameters or {}
        ticket_id = params.get("ticket_id", "")

        logger.info("ticket_retrieved", ticket_id=ticket_id)

        return ToolInvokeResponse(
            success=True,
            tool_name="ticket_get",
            data={
                "ticket_id": ticket_id,
                "status": "open",
                "subject": "Sample ticket subject",
                "priority": "medium",
                "created_at": "2025-01-15T10:00:00Z",
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_ticket_update_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_update_status tool invocation."""
        params = parameters or {}
        ticket_id = params.get("ticket_id", "")
        status = params.get("status", "")

        logger.info("ticket_status_updated", ticket_id=ticket_id, new_status=status)

        return ToolInvokeResponse(
            success=True,
            tool_name="ticket_update_status",
            data={
                "ticket_id": ticket_id,
                "status": status,
                "message": f"Ticket status updated to '{status}'",
            },
            metadata={"status": "placeholder"},
        )

    async def _invoke_ticket_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_search tool invocation."""
        params = parameters or {}
        query = params.get("query", "")

        logger.info("ticket_search", query=query)

        return ToolInvokeResponse(
            success=True,
            tool_name="ticket_search",
            data={
                "tickets": [],
                "total": 0,
            },
            metadata={"status": "placeholder"},
        )


# Singleton instance
ticketing_server = TicketingServer()
