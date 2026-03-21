"""
PARWA Mini Ticket Agent.

Mini PARWA's ticket agent handles support ticket creation and management.
Routes to Light tier and escalates complex issues.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_ticket_agent import (
    BaseTicketAgent,
    AgentResponse,
    TicketPriority,
    TicketStatus,
)
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniTicketAgent(BaseTicketAgent):
    """
    Mini PARWA Ticket Agent.

    Handles support tickets with the following characteristics:
    - Always routes to 'light' tier
    - Escalates when confidence < 70%
    - Creates tickets with proper categorization
    - Limited to basic ticket operations
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        mini_config: Optional[MiniConfig] = None,
    ) -> None:
        """
        Initialize Mini Ticket Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            mini_config: Optional MiniConfig instance
        """
        super().__init__(agent_id, config, company_id)
        self._mini_config = mini_config or get_mini_config()

    def get_tier(self) -> str:
        """Get the AI tier for this agent. Mini always uses 'light'."""
        return "light"

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "mini"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a ticket request.

        Args:
            input_data: Must contain 'action' key:
                - 'create': Create a new ticket
                - 'update': Update an existing ticket
                - 'get': Get ticket details
                - 'comment': Add a comment

        Returns:
            AgentResponse with ticket operation result
        """
        action = input_data.get("action", "create")

        if action == "create":
            return await self._handle_create(input_data)
        elif action == "update":
            return await self._handle_update(input_data)
        elif action == "get":
            return await self._handle_get(input_data)
        elif action == "comment":
            return await self._handle_comment(input_data)
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def _handle_create(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle ticket creation."""
        subject = input_data.get("subject")
        description = input_data.get("description")
        priority = input_data.get("priority", "normal")

        if not subject:
            return AgentResponse(
                success=False,
                message="Missing required field: subject",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        if not description:
            return AgentResponse(
                success=False,
                message="Missing required field: description",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Validate priority
        valid_priorities = ["low", "normal", "high", "urgent"]
        if priority.lower() not in valid_priorities:
            priority = "normal"

        self.log_action("mini_ticket_create", {
            "subject": subject,
            "priority": priority,
            "tier": self.get_tier(),
        })

        # Create ticket
        ticket = await self.create_ticket(
            subject=subject,
            description=description,
            priority=priority,
            metadata=input_data.get("metadata"),
        )

        # Calculate confidence based on completeness
        confidence = self._calculate_creation_confidence(input_data)

        # Check if should escalate based on priority
        escalated = priority.lower() in ["high", "urgent"]

        return AgentResponse(
            success=True,
            message="Ticket created successfully",
            data={
                "ticket": ticket,
                "ticket_id": ticket["ticket_id"],
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    async def _handle_update(self, input_data: Dict[str, Any]) -> AgentResponse:
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

        if not updates:
            return AgentResponse(
                success=False,
                message="No updates provided",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("mini_ticket_update", {
            "ticket_id": ticket_id,
            "updates": list(updates.keys()),
        })

        ticket = await self.update_ticket(ticket_id, updates)

        if "error" in ticket.get("status", ""):
            return AgentResponse(
                success=False,
                message=ticket.get("message", "Ticket not found"),
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message="Ticket updated successfully",
            data={"ticket": ticket},
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle get ticket request."""
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
            message="Ticket retrieved successfully",
            data={"ticket": ticket},
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_comment(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle add comment request."""
        ticket_id = input_data.get("ticket_id")
        comment = input_data.get("comment")
        author = input_data.get("author", "Mini Agent")

        if not ticket_id:
            return AgentResponse(
                success=False,
                message="Missing required field: ticket_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        if not comment:
            return AgentResponse(
                success=False,
                message="Missing required field: comment",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("mini_ticket_comment", {
            "ticket_id": ticket_id,
            "author": author,
        })

        ticket = await self.add_comment(ticket_id, comment, author)

        if "error" in ticket.get("status", ""):
            return AgentResponse(
                success=False,
                message=ticket.get("message", "Ticket not found"),
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message="Comment added successfully",
            data={"ticket": ticket},
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def _calculate_creation_confidence(self, input_data: Dict[str, Any]) -> float:
        """Calculate confidence based on input completeness."""
        confidence = 0.7  # Base confidence

        # More complete information = higher confidence
        if input_data.get("priority"):
            confidence += 0.1
        if input_data.get("metadata"):
            confidence += 0.1
        if len(input_data.get("description", "")) > 50:
            confidence += 0.1

        return min(confidence, 1.0)

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation is needed.

        Uses Mini config's escalation threshold (default 70%).

        Args:
            confidence: Confidence score (0.0-1.0)
            context: Optional additional context

        Returns:
            True if confidence < escalation threshold
        """
        return confidence < self._mini_config.escalation_threshold

    def get_ticket_stats(self) -> Dict[str, Any]:
        """Get ticket agent statistics."""
        return {
            "total_tickets": self.get_ticket_count(),
            "by_status": self.get_tickets_by_status(),
            "variant": self.get_variant(),
            "tier": self.get_tier(),
        }
