"""
PARWA Junior Ticket Agent.

PARWA Junior's ticket agent handles support ticket management with
enhanced capabilities and medium tier support.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_ticket_agent import (
    BaseTicketAgent,
    AgentResponse,
    TicketPriority,
    TicketStatus,
)
from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ParwaTicketAgent(BaseTicketAgent):
    """
    PARWA Junior Ticket Agent.

    Handles support ticket management with the following characteristics:
    - Routes to 'medium' tier for sophisticated responses
    - Enhanced ticket categorization and routing
    - Escalates when confidence < 60%
    - Supports all channels including voice and video
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        parwa_config: Optional[ParwaConfig] = None,
    ) -> None:
        """
        Initialize PARWA Junior Ticket Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            parwa_config: Optional ParwaConfig instance
        """
        super().__init__(agent_id, config, company_id)
        self._parwa_config = parwa_config or get_parwa_config()

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA uses 'medium'."""
        return self._parwa_config.default_tier

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "parwa"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a ticket action.

        Handles ticket creation, updates, and status changes.

        Args:
            input_data: Must contain 'action' key

        Returns:
            AgentResponse with ticket processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_ticket_process", {
            "action": action,
            "tier": self.get_tier(),
        })

        if action == "create":
            return await self._handle_create_ticket(input_data)
        elif action == "update":
            return await self._handle_update_ticket(input_data)
        elif action == "get":
            return await self._handle_get_ticket(input_data)
        elif action == "comment":
            return await self._handle_add_comment(input_data)
        elif action == "search":
            return await self._handle_search_tickets(input_data)
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def _handle_create_ticket(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle ticket creation."""
        subject = input_data.get("subject")
        description = input_data.get("description")
        priority = input_data.get("priority", "normal")
        metadata = input_data.get("metadata", {})

        if not subject or not description:
            return AgentResponse(
                success=False,
                message="Missing required fields: subject, description",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Create the ticket
        ticket = await self.create_ticket(
            subject=subject,
            description=description,
            priority=priority,
            metadata=metadata,
        )

        confidence = 0.9

        return AgentResponse(
            success=True,
            message=f"Ticket {ticket['ticket_id']} created successfully",
            data={
                "ticket": ticket,
                "ticket_id": ticket["ticket_id"],
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_update_ticket(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle ticket update."""
        ticket_id = input_data.get("ticket_id")
        updates = input_data.get("updates", {})

        if not ticket_id:
            return AgentResponse(
                success=False,
                message="Missing required field: ticket_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.update_ticket(ticket_id, updates)

        if "error" in result:
            return AgentResponse(
                success=False,
                message=result["message"],
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message=f"Ticket {ticket_id} updated successfully",
            data={"ticket": result},
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_ticket(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle get ticket."""
        ticket_id = input_data.get("ticket_id")

        if not ticket_id:
            return AgentResponse(
                success=False,
                message="Missing required field: ticket_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        ticket = await self.get_ticket(ticket_id)

        if not ticket:
            return AgentResponse(
                success=False,
                message=f"Ticket {ticket_id} not found",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message=f"Ticket {ticket_id} retrieved",
            data={"ticket": ticket},
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_add_comment(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle add comment to ticket."""
        ticket_id = input_data.get("ticket_id")
        comment = input_data.get("comment")
        author = input_data.get("author", "PARWA Junior")

        if not ticket_id or not comment:
            return AgentResponse(
                success=False,
                message="Missing required fields: ticket_id, comment",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.add_comment(ticket_id, comment, author)

        if "error" in result:
            return AgentResponse(
                success=False,
                message=result["message"],
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message=f"Comment added to ticket {ticket_id}",
            data={"ticket": result},
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_search_tickets(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle search tickets."""
        query = input_data.get("query", {})

        results = await self.search_tickets(query)

        return AgentResponse(
            success=True,
            message=f"Found {len(results)} tickets",
            data={
                "tickets": results,
                "count": len(results),
            },
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def get_ticket_stats(self) -> Dict[str, Any]:
        """Get ticket agent statistics."""
        return {
            "total_tickets": self.get_ticket_count(),
            "by_status": self.get_tickets_by_status(),
            "variant": self.get_variant(),
            "tier": self.get_tier(),
        }
