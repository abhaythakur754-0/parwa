"""
PARWA Ticketing MCP Server.

MCP server for ticketing operations via Zendesk integration.
Wraps the ZendeskClient and exposes it as MCP tools.
"""
from typing import Dict, Any, List
import asyncio

from mcp_servers.base_server import BaseMCPServer
from shared.integrations.zendesk_client import (
    ZendeskClient,
    TicketStatus,
    TicketPriority,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TicketingServer(BaseMCPServer):
    """
    MCP Server for ticketing operations.

    Tools provided:
    - create_ticket: Create a new support ticket
    - update_ticket: Update an existing ticket
    - get_ticket: Get ticket details
    - add_comment: Add a comment to a ticket
    - search_tickets: Search for tickets

    This server wraps the ZendeskClient and exposes its functionality
    through the MCP protocol.
    """

    def __init__(
        self,
        config: Dict[str, Any] = None,
        zendesk_client: ZendeskClient = None
    ) -> None:
        """
        Initialize Ticketing MCP Server.

        Args:
            config: Server configuration
            zendesk_client: Optional ZendeskClient instance (created if not provided)
        """
        self._zendesk_client = zendesk_client or ZendeskClient()
        super().__init__(name="ticketing_server", config=config)

    def _register_tools(self) -> None:
        """Register all ticketing tools."""
        # Tool: create_ticket
        self.register_tool(
            name="create_ticket",
            description=(
                "Create a new support ticket with subject, description, and priority. "
                "Returns ticket ID for tracking."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Ticket subject line",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed ticket description",
                    },
                    "priority": {
                        "type": "string",
                        "description": "Ticket priority (low, normal, high, urgent)",
                        "enum": ["low", "normal", "high", "urgent"],
                        "default": "normal",
                    },
                    "requester_email": {
                        "type": "string",
                        "description": "Email of the ticket requester",
                    },
                    "requester_name": {
                        "type": "string",
                        "description": "Name of the requester (optional)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to apply to the ticket",
                    },
                },
                "required": ["subject", "description", "requester_email"],
            },
            handler=self._handle_create_ticket,
        )

        # Tool: update_ticket
        self.register_tool(
            name="update_ticket",
            description=(
                "Update an existing ticket with new status, priority, or other fields. "
                "Can also add a comment."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "ID of the ticket to update",
                    },
                    "status": {
                        "type": "string",
                        "description": "New ticket status",
                        "enum": ["new", "open", "pending", "hold", "solved", "closed"],
                    },
                    "priority": {
                        "type": "string",
                        "description": "New ticket priority",
                        "enum": ["low", "normal", "high", "urgent"],
                    },
                    "comment": {
                        "type": "string",
                        "description": "Comment to add to the ticket",
                    },
                    "assignee_id": {
                        "type": "string",
                        "description": "Agent ID to assign ticket to",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New tags (replaces existing)",
                    },
                },
                "required": ["ticket_id"],
            },
            handler=self._handle_update_ticket,
        )

        # Tool: get_ticket
        self.register_tool(
            name="get_ticket",
            description="Get detailed information about a ticket by ID.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "ID of the ticket to retrieve",
                    },
                },
                "required": ["ticket_id"],
            },
            handler=self._handle_get_ticket,
        )

        # Tool: add_comment
        self.register_tool(
            name="add_comment",
            description=(
                "Add a comment to a ticket. Comments can be public (visible to "
                "requester) or internal (agent-only)."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "ID of the ticket",
                    },
                    "comment": {
                        "type": "string",
                        "description": "Comment content",
                    },
                    "author": {
                        "type": "string",
                        "description": "Author identifier (user_id or 'agent')",
                    },
                    "public": {
                        "type": "boolean",
                        "description": "Whether comment is visible to requester",
                        "default": True,
                    },
                },
                "required": ["ticket_id", "comment"],
            },
            handler=self._handle_add_comment,
        )

        # Tool: search_tickets
        self.register_tool(
            name="search_tickets",
            description=(
                "Search for tickets by query string with optional filters. "
                "Returns matching ticket summaries."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status",
                        "enum": ["new", "open", "pending", "hold", "solved", "closed"],
                    },
                    "priority": {
                        "type": "string",
                        "description": "Filter by priority",
                        "enum": ["low", "normal", "high", "urgent"],
                    },
                    "requester_email": {
                        "type": "string",
                        "description": "Filter by requester email",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
            handler=self._handle_search_tickets,
        )

    async def _on_start(self) -> None:
        """Connect to Zendesk service on startup."""
        if not self._zendesk_client.is_connected:
            success = await self._zendesk_client.connect()
            if not success:
                raise RuntimeError("Failed to connect to Zendesk service")

    async def _on_stop(self) -> None:
        """Disconnect from Zendesk service on shutdown."""
        await self._zendesk_client.disconnect()

    async def _handle_create_ticket(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle create_ticket tool call.

        Args:
            params: Tool parameters with subject, description, priority, etc.

        Returns:
            Created ticket details with ticket_id
        """
        subject = params.get("subject")
        description = params.get("description")
        priority = params.get("priority", "normal")
        requester_email = params.get("requester_email")
        requester_name = params.get("requester_name")
        tags = params.get("tags", [])

        try:
            # Map priority string to enum
            priority_enum = TicketPriority(priority.lower())

            result = await self._zendesk_client.create_ticket(
                subject=subject,
                comment=description,
                requester_email=requester_email,
                requester_name=requester_name,
                priority=priority_enum,
                tags=tags,
            )

            logger.info({
                "event": "ticket_created",
                "ticket_id": result.get("id"),
                "subject": subject[:50] if subject else None,
                "priority": priority,
            })

            return {
                "ticket_id": str(result.get("id")),
                "subject": result.get("subject"),
                "status": result.get("status"),
                "priority": result.get("priority"),
                "requester": result.get("requester"),
                "created_at": result.get("created_at"),
            }

        except ValueError as e:
            logger.error({
                "event": "ticket_create_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "ticket_create_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to create ticket"}

    async def _handle_update_ticket(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle update_ticket tool call.

        Args:
            params: Tool parameters with ticket_id and fields to update

        Returns:
            Updated ticket details
        """
        ticket_id = params.get("ticket_id")
        status = params.get("status")
        priority = params.get("priority")
        comment = params.get("comment")
        assignee_id = params.get("assignee_id")
        tags = params.get("tags")

        try:
            # Map status and priority strings to enums if provided
            status_enum = TicketStatus(status.lower()) if status else None
            priority_enum = TicketPriority(priority.lower()) if priority else None

            result = await self._zendesk_client.update_ticket(
                ticket_id=int(ticket_id),
                comment=comment,
                status=status_enum,
                priority=priority_enum,
                assignee_id=int(assignee_id) if assignee_id else None,
                tags=tags,
            )

            logger.info({
                "event": "ticket_updated",
                "ticket_id": ticket_id,
                "updates": {
                    "status": status,
                    "priority": priority,
                    "has_comment": comment is not None,
                },
            })

            return {
                "ticket_id": str(result.get("id")),
                "status": result.get("status"),
                "priority": result.get("priority"),
                "updated_at": result.get("updated_at"),
            }

        except ValueError as e:
            logger.error({
                "event": "ticket_update_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "ticket_update_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to update ticket"}

    async def _handle_get_ticket(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_ticket tool call.

        Args:
            params: Tool parameters with ticket_id

        Returns:
            Ticket details
        """
        ticket_id = params.get("ticket_id")

        try:
            result = await self._zendesk_client.get_ticket(int(ticket_id))

            return {
                "ticket_id": str(result.get("id")),
                "subject": result.get("subject"),
                "description": result.get("description"),
                "status": result.get("status"),
                "priority": result.get("priority"),
                "requester": result.get("requester"),
                "tags": result.get("tags", []),
                "created_at": result.get("created_at"),
                "updated_at": result.get("updated_at"),
            }

        except ValueError as e:
            logger.error({
                "event": "ticket_get_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "ticket_get_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to get ticket"}

    async def _handle_add_comment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle add_comment tool call.

        Args:
            params: Tool parameters with ticket_id, comment, author, public

        Returns:
            Comment details
        """
        ticket_id = params.get("ticket_id")
        comment = params.get("comment")
        author = params.get("author", "agent")
        public = params.get("public", True)

        try:
            result = await self._zendesk_client.add_comment(
                ticket_id=int(ticket_id),
                comment=comment,
                author_id=int(author) if author.isdigit() else None,
                public=public,
            )

            logger.info({
                "event": "comment_added",
                "ticket_id": ticket_id,
                "comment_id": result.get("id"),
                "public": public,
            })

            return {
                "comment_id": str(result.get("id")),
                "ticket_id": str(result.get("ticket_id")),
                "body": result.get("body"),
                "public": result.get("public"),
                "created_at": result.get("created_at"),
            }

        except ValueError as e:
            logger.error({
                "event": "comment_add_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "comment_add_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to add comment"}

    async def _handle_search_tickets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle search_tickets tool call.

        Args:
            params: Tool parameters with query and optional filters

        Returns:
            List of matching tickets
        """
        query = params.get("query")
        status = params.get("status")
        priority = params.get("priority")
        requester_email = params.get("requester_email")
        limit = params.get("limit", 20)

        try:
            # Map status and priority to enums if provided
            status_enum = TicketStatus(status.lower()) if status else None
            priority_enum = TicketPriority(priority.lower()) if priority else None

            results = await self._zendesk_client.search_tickets(
                query=query,
                status=status_enum,
                priority=priority_enum,
                requester_email=requester_email,
                limit=limit,
            )

            # Format results
            formatted_results = [
                {
                    "ticket_id": str(ticket.get("id")),
                    "subject": ticket.get("subject"),
                    "status": ticket.get("status"),
                    "priority": ticket.get("priority"),
                    "created_at": ticket.get("created_at"),
                }
                for ticket in results
            ]

            return {
                "query": query,
                "tickets": formatted_results,
                "count": len(formatted_results),
            }

        except ValueError as e:
            logger.error({
                "event": "ticket_search_validation_error",
                "error": str(e),
            })
            return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error({
                "event": "ticket_search_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to search tickets"}
