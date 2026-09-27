"""
PARWA MCP — Ticketing Server (v2.0.0 — Wired to Real Backend)

Provides support ticket lifecycle tools.
Wired to real backend ticket APIs via httpx.
All placeholder data replaced with live backend calls.

Backend routes: /api/v1/tickets/*
"""

from __future__ import annotations

import os
from typing import Any

import httpx
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

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


class TicketingServer(MCPServerBase):
    """MCP sub-server for support ticket operations — wired to real backend."""

    name = "ticketing_server"
    description = "Support ticket lifecycle management (create, update, search) — wired to backend"
    category = ToolCategory.INTEGRATION
    version = "2.0.0"

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
                        "company_id": {"type": "string", "description": "Tenant company ID"},
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
                        "company_id": {"type": "string"},
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
                        "company_id": {"type": "string"},
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
                        "company_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                        "page": {"type": "integer", "default": 1},
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

    async def _backend_call(
        self, method: str, path: str, json_data: dict | None = None, params: dict | None = None,
    ) -> dict | None:
        """Make an httpx call to the backend ticket API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{BACKEND_URL}{path}"
                resp = await client.request(method, url, json=json_data, params=params)
                if resp.status_code in (200, 201):
                    return resp.json()
                logger.warning(
                    "ticketing_backend_error",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception as exc:
            logger.warning("ticketing_backend_failed", path=path, error=str(exc)[:200])
        return None

    async def _invoke_ticket_create(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_create tool invocation — wired to backend."""
        params = parameters or {}
        subject = params.get("subject", "")
        priority = params.get("priority", "medium")

        logger.info("ticket_create_invoked", subject=subject[:80], priority=priority)

        payload = {
            "subject": subject,
            "description": params.get("description", ""),
            "priority": priority,
            "category": params.get("category", "general"),
            "customer_id": params.get("customer_id"),
            "channel": params.get("channel", "api"),
            "tags": params.get("tags", []),
        }
        if params.get("company_id"):
            payload["company_id"] = params["company_id"]

        data = await self._backend_call("POST", "/api/v1/tickets", json_data=payload)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="ticket_create",
                data=data,
                metadata={"source": "backend"},
            )

        # Fallback: backend unreachable
        return ToolInvokeResponse(
            success=False,
            tool_name="ticket_create",
            error="Ticket creation failed — backend unreachable",
            metadata={"source": "fallback"},
        )

    async def _invoke_ticket_get(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_get tool invocation — wired to backend."""
        params = parameters or {}
        ticket_id = params.get("ticket_id", "")

        logger.info("ticket_get_invoked", ticket_id=ticket_id)

        data = await self._backend_call("GET", f"/api/v1/tickets/{ticket_id}")
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="ticket_get",
                data=data,
                metadata={"source": "backend"},
            )

        return ToolInvokeResponse(
            success=False,
            tool_name="ticket_get",
            error=f"Ticket '{ticket_id}' not found or backend unreachable",
            metadata={"source": "fallback"},
        )

    async def _invoke_ticket_update_status(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_update_status tool invocation — wired to backend."""
        params = parameters or {}
        ticket_id = params.get("ticket_id", "")
        status = params.get("status", "")

        logger.info("ticket_update_status_invoked", ticket_id=ticket_id, new_status=status)

        payload = {"status": status}
        if params.get("reason"):
            payload["reason"] = params["reason"]

        data = await self._backend_call(
            "PATCH", f"/api/v1/tickets/{ticket_id}/status", json_data=payload
        )
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="ticket_update_status",
                data=data,
                metadata={"source": "backend"},
            )

        return ToolInvokeResponse(
            success=False,
            tool_name="ticket_update_status",
            error=f"Failed to update ticket '{ticket_id}' status — backend unreachable",
            metadata={"source": "fallback"},
        )

    async def _invoke_ticket_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle ticket_search tool invocation — wired to backend."""
        params = parameters or {}
        query = params.get("query", "")

        logger.info("ticket_search_invoked", query=query)

        search_params: dict[str, Any] = {}
        for key in ("status", "priority", "customer_id", "company_id"):
            if params.get(key):
                search_params[key] = params[key]
        if query:
            search_params["search"] = query
        search_params["page_size"] = params.get("limit", 20)
        search_params["page"] = params.get("page", 1)

        data = await self._backend_call("GET", "/api/v1/tickets", params=search_params)
        if data:
            return ToolInvokeResponse(
                success=True,
                tool_name="ticket_search",
                data=data,
                metadata={"source": "backend"},
            )

        return ToolInvokeResponse(
            success=True,
            tool_name="ticket_search",
            data={"tickets": [], "total": 0},
            metadata={"source": "fallback", "reason": "backend_unreachable"},
        )


# Singleton instance
ticketing_server = TicketingServer()
