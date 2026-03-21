"""
PARWA Mini Ticket Creation Workflow.

Handles ticket creation with validation and notification.
"""
from typing import Dict, Any, Optional
from variants.mini.tools.ticket_create import TicketCreateTool
from variants.mini.tools.notification import NotificationTool
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TicketCreationWorkflow:
    """
    Workflow for creating support tickets.

    Steps:
    1. Validate ticket data
    2. Create ticket
    3. Send notification
    """

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None
    ) -> None:
        """
        Initialize ticket creation workflow.

        Args:
            mini_config: Mini configuration
        """
        self._config = mini_config or get_mini_config()
        self._ticket_tool = TicketCreateTool()
        self._notification_tool = NotificationTool()

    async def execute(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the ticket creation workflow.

        Args:
            ticket_data: Dict with:
                - subject: Ticket subject
                - description: Ticket description
                - priority: Ticket priority (optional)
                - customer_id: Customer identifier
                - customer_email: Customer email
                - notify_customer: Whether to send notification (optional)

        Returns:
            Dict with workflow result
        """
        subject = ticket_data.get("subject", "")
        description = ticket_data.get("description", "")
        priority = ticket_data.get("priority", "normal")
        customer_id = ticket_data.get("customer_id")
        customer_email = ticket_data.get("customer_email")
        notify_customer = ticket_data.get("notify_customer", True)

        logger.info({
            "event": "ticket_creation_workflow_started",
            "subject": subject,
            "priority": priority,
            "customer_id": customer_id,
        })

        # Step 1: Validate
        validation = self._ticket_tool.validate_ticket_data(
            subject, description, priority
        )

        if not validation.get("valid"):
            return {
                "status": "validation_failed",
                "errors": validation.get("errors", []),
                "message": "Ticket data is invalid.",
            }

        # Step 2: Create ticket
        ticket = await self._ticket_tool.create(
            subject=subject,
            description=description,
            priority=priority,
            customer_id=customer_id,
            customer_email=customer_email,
            metadata=ticket_data.get("metadata"),
        )

        # Step 3: Send notification
        notification_result = None
        if notify_customer and customer_email:
            notification_result = await self._notification_tool.send_email(
                to=customer_email,
                subject=f"Ticket Created: {ticket.get('ticket_id')}",
                body=f"""
Your support ticket has been created.

Ticket ID: {ticket.get('ticket_id')}
Subject: {subject}
Priority: {priority}

We will respond to your inquiry shortly.

Thank you,
Support Team
                """.strip(),
            )

        # Determine if escalation needed based on priority
        escalated = priority.lower() in ["high", "urgent"]

        return {
            "status": "created",
            "ticket": ticket,
            "ticket_id": ticket.get("ticket_id"),
            "notification_sent": notification_result.get("success") if notification_result else False,
            "escalated": escalated,
            "message": f"Ticket {ticket.get('ticket_id')} created successfully.",
        }

    async def execute_with_comment(
        self,
        ticket_data: Dict[str, Any],
        initial_comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute ticket creation with an initial comment.

        Args:
            ticket_data: Ticket creation data
            initial_comment: Optional initial comment to add

        Returns:
            Dict with workflow result
        """
        result = await self.execute(ticket_data)

        if result.get("status") != "created":
            return result

        if initial_comment:
            ticket_id = result.get("ticket_id")
            updated_ticket = await self._ticket_tool.add_comment(
                ticket_id=ticket_id,
                comment=initial_comment,
                author="System",
            )
            result["ticket"] = updated_ticket

        return result

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "TicketCreationWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"
