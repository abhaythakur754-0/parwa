"""
PARWA Mini Create Ticket Task.

Task for creating support tickets using the Mini Ticket agent.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from variants.mini.agents.ticket_agent import MiniTicketAgent
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class TicketPriority(Enum):
    """Ticket priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(Enum):
    """Ticket status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class TicketTaskResult:
    """Result from create ticket task."""
    success: bool
    ticket_id: Optional[str] = None
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.NORMAL
    confidence: float = 0.0
    escalated: bool = False
    escalation_reason: Optional[str] = None
    assigned_to: Optional[str] = None
    estimated_resolution_hours: Optional[int] = None


class CreateTicketTask:
    """
    Task for creating support tickets.

    Uses MiniTicketAgent to:
    1. Create new support ticket
    2. Classify priority
    3. Assign to appropriate queue
    4. Escalate high priority tickets

    Example:
        task = CreateTicketTask()
        result = await task.execute({
            "subject": "Order not received",
            "description": "I ordered 5 days ago...",
            "customer_id": "cust_123",
            "category": "shipping"
        })
    """

    # Priority based on category
    CATEGORY_PRIORITY = {
        "refund": TicketPriority.HIGH,
        "complaint": TicketPriority.HIGH,
        "shipping": TicketPriority.NORMAL,
        "billing": TicketPriority.NORMAL,
        "inquiry": TicketPriority.LOW,
        "feedback": TicketPriority.LOW,
    }

    # SLA hours by priority
    SLA_HOURS = {
        TicketPriority.URGENT: 1,
        TicketPriority.HIGH: 4,
        TicketPriority.NORMAL: 24,
        TicketPriority.LOW: 72,
    }

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None,
        agent_id: str = "mini_ticket_task"
    ) -> None:
        """
        Initialize create ticket task.

        Args:
            mini_config: Mini configuration
            agent_id: Agent identifier
        """
        self._config = mini_config or get_mini_config()
        self._agent = MiniTicketAgent(
            agent_id=agent_id,
            mini_config=self._config
        )

    async def execute(self, input_data: Dict[str, Any]) -> TicketTaskResult:
        """
        Execute the create ticket task.

        Args:
            input_data: Must contain:
                - subject: Ticket subject
                - description: Ticket description
                - customer_id: Customer identifier
                - category: Optional ticket category

        Returns:
            TicketTaskResult with ticket details
        """
        subject = input_data.get("subject", "")
        description = input_data.get("description", "")
        customer_id = input_data.get("customer_id", "")
        category = input_data.get("category", "inquiry")

        logger.info({
            "event": "ticket_task_started",
            "subject": subject[:50],
            "customer_id": customer_id,
            "category": category,
        })

        # Determine priority from category
        priority = self._determine_priority(category, subject, description)

        # Process through Mini Ticket agent
        response = await self._agent.process({
            "subject": subject,
            "description": description,
            "customer_id": customer_id,
            "category": category,
            "priority": priority.value
        })

        # Build result
        result = TicketTaskResult(
            success=response.success,
            priority=priority,
            confidence=response.confidence,
            escalated=response.escalated,
            escalation_reason=response.escalation_reason if response.escalated else None,
            estimated_resolution_hours=self.SLA_HOURS.get(priority),
        )

        if response.success:
            data = response.data or {}
            result.ticket_id = data.get("ticket_id")
            result.status = TicketStatus(data.get("status", "open"))
            result.assigned_to = data.get("assigned_to")

            # Auto-escalate high/urgent priority
            if priority in (TicketPriority.HIGH, TicketPriority.URGENT):
                result.escalated = True
                result.escalation_reason = f"Auto-escalated due to {priority.value} priority"

        logger.info({
            "event": "ticket_task_completed",
            "ticket_id": result.ticket_id,
            "success": result.success,
            "priority": priority.value,
            "escalated": result.escalated,
        })

        return result

    def _determine_priority(
        self,
        category: str,
        subject: str,
        description: str
    ) -> TicketPriority:
        """
        Determine ticket priority.

        Args:
            category: Ticket category
            subject: Ticket subject
            description: Ticket description

        Returns:
            Determined priority level
        """
        # Start with category-based priority
        priority = self.CATEGORY_PRIORITY.get(category, TicketPriority.NORMAL)

        # Check for urgent keywords
        combined = f"{subject} {description}".lower()
        urgent_keywords = ["urgent", "emergency", "immediately", "asap", "critical"]
        if any(kw in combined for kw in urgent_keywords):
            priority = TicketPriority.URGENT

        return priority

    def get_task_name(self) -> str:
        """Get task name."""
        return "create_ticket"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"

    def get_tier(self) -> str:
        """Get tier used."""
        return "light"
