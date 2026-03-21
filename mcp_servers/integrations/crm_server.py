"""
PARWA CRM MCP Server.

MCP server for CRM (Customer Relationship Management) operations.
Provides tools for contact management, interaction history, and
customer data operations.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


# Mock data for testing
MOCK_CONTACTS = {
    "CONT-001": {
        "contact_id": "CONT-001",
        "email": "john.doe@example.com",
        "name": "John Doe",
        "phone": "+1-555-0100",
        "company": "Tech Corp",
        "title": "Engineering Manager",
        "status": "active",
        "source": "website",
        "tags": ["enterprise", "tech"],
        "created_at": "2025-06-15T00:00:00Z",
        "updated_at": "2026-03-10T12:00:00Z"
    },
    "CONT-002": {
        "contact_id": "CONT-002",
        "email": "jane.smith@example.com",
        "name": "Jane Smith",
        "phone": "+1-555-0200",
        "company": "Design Studio",
        "title": "Creative Director",
        "status": "active",
        "source": "referral",
        "tags": ["creative", "design"],
        "created_at": "2026-01-10T00:00:00Z",
        "updated_at": "2026-03-15T09:30:00Z"
    },
    "CONT-003": {
        "contact_id": "CONT-003",
        "email": "mike.johnson@example.com",
        "name": "Mike Johnson",
        "phone": "+1-555-0300",
        "company": "Startup Inc",
        "title": "CEO",
        "status": "lead",
        "source": "linkedin",
        "tags": ["startup", "founder"],
        "created_at": "2026-02-20T00:00:00Z",
        "updated_at": "2026-03-18T14:00:00Z"
    }
}

MOCK_INTERACTIONS = {
    "CONT-001": [
        {
            "interaction_id": "INT-001",
            "contact_id": "CONT-001",
            "type": "email",
            "subject": "Product inquiry",
            "summary": "Customer asked about enterprise pricing",
            "timestamp": "2026-03-10T12:00:00Z",
            "agent": "support-agent-1"
        },
        {
            "interaction_id": "INT-002",
            "contact_id": "CONT-001",
            "type": "call",
            "subject": "Follow-up call",
            "summary": "Discussed implementation timeline",
            "timestamp": "2026-03-12T15:30:00Z",
            "agent": "sales-agent-2"
        }
    ],
    "CONT-002": [
        {
            "interaction_id": "INT-003",
            "contact_id": "CONT-002",
            "type": "chat",
            "subject": "Support request",
            "summary": "Helped with account setup",
            "timestamp": "2026-03-15T09:30:00Z",
            "agent": "support-agent-3"
        }
    ],
    "CONT-003": [
        {
            "interaction_id": "INT-004",
            "contact_id": "CONT-003",
            "type": "email",
            "subject": "Demo request",
            "summary": "Scheduled product demo for next week",
            "timestamp": "2026-03-18T14:00:00Z",
            "agent": "sales-agent-1"
        }
    ]
}


class CRMServer(BaseMCPServer):
    """
    MCP server for CRM operations.

    Provides tools for:
    - Contact lookup and management
    - Contact search
    - Contact creation and updates
    - Interaction history retrieval
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize CRM server.

        Args:
            config: Optional server configuration
        """
        super().__init__("crm-server", config)
        self._contacts = dict(MOCK_CONTACTS)
        self._interactions = {k: list(v) for k, v in MOCK_INTERACTIONS.items()}

    def _register_tools(self) -> None:
        """Register all CRM tools."""
        self.register_tool(
            name="get_contact",
            description="Retrieve contact details by contact ID",
            parameters_schema={
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "The contact ID to look up"
                    }
                },
                "required": ["contact_id"]
            },
            handler=self._handle_get_contact
        )

        self.register_tool(
            name="search_contacts",
            description="Search contacts by query string",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for contacts"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10
                    }
                },
                "required": ["query"]
            },
            handler=self._handle_search_contacts
        )

        self.register_tool(
            name="create_contact",
            description="Create a new contact",
            parameters_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "Contact data including email, name, etc.",
                        "properties": {
                            "email": {"type": "string"},
                            "name": {"type": "string"},
                            "phone": {"type": "string"},
                            "company": {"type": "string"},
                            "title": {"type": "string"},
                            "source": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["email", "name"]
                    }
                },
                "required": ["data"]
            },
            handler=self._handle_create_contact
        )

        self.register_tool(
            name="update_contact",
            description="Update an existing contact",
            parameters_schema={
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "The contact ID to update"
                    },
                    "data": {
                        "type": "object",
                        "description": "Fields to update"
                    }
                },
                "required": ["contact_id", "data"]
            },
            handler=self._handle_update_contact
        )

        self.register_tool(
            name="get_interaction_history",
            description="Get interaction history for a contact",
            parameters_schema={
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "The contact ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of interactions",
                        "default": 20
                    }
                },
                "required": ["contact_id"]
            },
            handler=self._handle_get_interaction_history
        )

    async def _handle_get_contact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_contact tool call.

        Args:
            params: Tool parameters containing contact_id

        Returns:
            Contact details or error
        """
        contact_id = params["contact_id"]
        contact = self._contacts.get(contact_id)

        if not contact:
            logger.warning({
                "event": "contact_not_found",
                "contact_id": contact_id
            })
            return {
                "status": "error",
                "message": f"Contact '{contact_id}' not found"
            }

        logger.info({
            "event": "contact_retrieved",
            "contact_id": contact_id
        })

        return {
            "status": "success",
            "contact": contact
        }

    async def _handle_search_contacts(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle search_contacts tool call.

        Args:
            params: Tool parameters containing query and optional limit

        Returns:
            List of matching contacts
        """
        query = params["query"].lower()
        limit = params.get("limit", 10)

        matching_contacts = []
        for contact in self._contacts.values():
            # Search in name, email, company, title, and tags
            search_text = " ".join([
                contact["name"].lower(),
                contact["email"].lower(),
                contact.get("company", "").lower(),
                contact.get("title", "").lower(),
                " ".join(contact.get("tags", []))
            ])

            if query in search_text:
                matching_contacts.append(contact)

        results = matching_contacts[:limit]

        logger.info({
            "event": "contacts_searched",
            "query": query,
            "results_count": len(results)
        })

        return {
            "status": "success",
            "contacts": results,
            "total_found": len(matching_contacts),
            "returned": len(results)
        }

    async def _handle_create_contact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle create_contact tool call.

        Args:
            params: Tool parameters containing contact data

        Returns:
            Created contact details
        """
        data = params["data"]

        # Validate required fields
        if "email" not in data or "name" not in data:
            return {
                "status": "error",
                "message": "Email and name are required"
            }

        # Check for duplicate email
        existing = next(
            (c for c in self._contacts.values() if c["email"] == data["email"]),
            None
        )
        if existing:
            return {
                "status": "error",
                "message": f"Contact with email '{data['email']}' already exists"
            }

        # Generate contact ID
        contact_id = f"CONT-{uuid.uuid4().hex[:8].upper()}"

        # Create contact
        now = datetime.now(timezone.utc).isoformat()
        contact = {
            "contact_id": contact_id,
            "email": data["email"],
            "name": data["name"],
            "phone": data.get("phone", ""),
            "company": data.get("company", ""),
            "title": data.get("title", ""),
            "status": data.get("status", "lead"),
            "source": data.get("source", "api"),
            "tags": data.get("tags", []),
            "created_at": now,
            "updated_at": now
        }

        self._contacts[contact_id] = contact
        self._interactions[contact_id] = []

        logger.info({
            "event": "contact_created",
            "contact_id": contact_id,
            "email": data["email"]
        })

        return {
            "status": "success",
            "contact": contact
        }

    async def _handle_update_contact(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle update_contact tool call.

        Args:
            params: Tool parameters containing contact_id and data

        Returns:
            Updated contact details
        """
        contact_id = params["contact_id"]
        data = params["data"]

        contact = self._contacts.get(contact_id)
        if not contact:
            return {
                "status": "error",
                "message": f"Contact '{contact_id}' not found"
            }

        # Update allowed fields
        updatable_fields = [
            "name", "phone", "company", "title", "status", "tags"
        ]
        for field in updatable_fields:
            if field in data:
                contact[field] = data[field]

        contact["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info({
            "event": "contact_updated",
            "contact_id": contact_id,
            "updated_fields": list(data.keys())
        })

        return {
            "status": "success",
            "contact": contact
        }

    async def _handle_get_interaction_history(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle get_interaction_history tool call.

        Args:
            params: Tool parameters containing contact_id and optional limit

        Returns:
            List of interactions for the contact
        """
        contact_id = params["contact_id"]
        limit = params.get("limit", 20)

        # Check contact exists
        if contact_id not in self._contacts:
            return {
                "status": "error",
                "message": f"Contact '{contact_id}' not found"
            }

        interactions = self._interactions.get(contact_id, [])
        results = interactions[:limit]

        logger.info({
            "event": "interactions_retrieved",
            "contact_id": contact_id,
            "count": len(results)
        })

        return {
            "status": "success",
            "interactions": results,
            "total_count": len(interactions),
            "returned": len(results)
        }
