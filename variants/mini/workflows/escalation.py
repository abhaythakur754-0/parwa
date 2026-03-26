"""
PARWA Mini Escalation Workflow.

Handles escalation to human support with proper logging and notification.
CRITICAL: This workflow triggers human handoff.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
from variants.mini.tools.notification import NotificationTool
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EscalationWorkflow:
    """
    Workflow for handling escalations to human support.

    CRITICAL: This workflow triggers human handoff when
    AI cannot resolve the issue.

    Steps:
    1. Log escalation
    2. Notify human agents
    3. Update ticket status
    """

    ESCALATION_CHANNELS = ["human_agent", "supervisor", "specialist"]

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None
    ) -> None:
        """
        Initialize escalation workflow.

        Args:
            mini_config: Mini configuration
        """
        self._config = mini_config or get_mini_config()
        self._notification_tool = NotificationTool()
        self._escalations: Dict[str, Dict[str, Any]] = {}

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the escalation workflow.

        CRITICAL: This triggers human handoff.

        Args:
            context: Dict with:
                - ticket_id: Associated ticket ID
                - reason: Reason for escalation
                - confidence: Current confidence score
                - customer_id: Customer identifier
                - customer_email: Customer email (optional)
                - channel: Preferred escalation channel (optional)

        Returns:
            Dict with workflow result
        """
        ticket_id = context.get("ticket_id", f"TKT-{uuid.uuid4().hex[:8].upper()}")
        reason = context.get("reason", "escalation_required")
        confidence = context.get("confidence", 0.0)
        customer_id = context.get("customer_id")
        customer_email = context.get("customer_email")

        logger.info({
            "event": "escalation_workflow_started",
            "ticket_id": ticket_id,
            "reason": reason,
            "confidence": confidence,
            "customer_id": customer_id,
        })

        # Step 1: Log escalation
        escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
        escalation = {
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "reason": reason,
            "confidence": confidence,
            "customer_id": customer_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "channel": self._determine_channel(context),
        }
        self._escalations[escalation_id] = escalation

        # Step 2: Notify human agents
        notification_result = await self._notify_human_agents(escalation)

        # Step 3: Update escalation status
        escalation["status"] = "notified"
        escalation["notified_at"] = datetime.now(timezone.utc).isoformat()

        # Optionally notify customer
        customer_notified = False
        if customer_email:
            customer_notify = await self._notification_tool.send_email(
                to=customer_email,
                subject=f"Your request has been escalated - {ticket_id}",
                body=f"""
Your support request has been escalated to our human support team.

Ticket ID: {ticket_id}
Escalation ID: {escalation_id}

A human agent will respond to you shortly.

Thank you for your patience.
                """.strip(),
            )
            customer_notified = customer_notify.get("success", False)

        logger.info({
            "event": "escalation_completed",
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "human_handoff": True,
        })

        return {
            "status": "escalated",
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "human_handoff": True,
            "channel": escalation["channel"],
            "agents_notified": notification_result.get("success", False),
            "customer_notified": customer_notified,
            "message": "Your request has been escalated to a human agent.",
        }

    def _determine_channel(self, context: Dict[str, Any]) -> str:
        """
        Determine the best escalation channel.

        Args:
            context: Escalation context

        Returns:
            Channel name
        """
        reason = context.get("reason", "").lower()
        confidence = context.get("confidence", 1.0)

        # Very low confidence -> specialist
        if confidence < 0.5:
            return "specialist"

        # Refunds and complaints -> supervisor
        if "refund" in reason or "complaint" in reason:
            return "supervisor"

        # Default to human agent
        return "human_agent"

    async def _notify_human_agents(self, escalation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Notify human agents about escalation.

        Args:
            escalation: Escalation details

        Returns:
            Notification result
        """
        # In production, this would notify actual human agents
        # via their preferred channel (Slack, email, dashboard, etc.)

        logger.info({
            "event": "human_agents_notified",
            "escalation_id": escalation.get("escalation_id"),
            "channel": escalation.get("channel"),
        })

        return {
            "success": True,
            "channel": escalation.get("channel"),
            "notified_at": datetime.now(timezone.utc).isoformat(),
        }

    async def acknowledge(
        self,
        escalation_id: str,
        handler: str
    ) -> Dict[str, Any]:
        """
        Acknowledge an escalation.

        Args:
            escalation_id: Escalation identifier
            handler: Handler who acknowledged

        Returns:
            Updated escalation status
        """
        escalation = self._escalations.get(escalation_id)
        if not escalation:
            return {
                "status": "error",
                "message": "Escalation not found",
            }

        escalation["status"] = "acknowledged"
        escalation["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
        escalation["handler"] = handler

        logger.info({
            "event": "escalation_acknowledged",
            "escalation_id": escalation_id,
            "handler": handler,
        })

        return {
            "status": "acknowledged",
            "escalation_id": escalation_id,
            "handler": handler,
        }

    async def resolve(
        self,
        escalation_id: str,
        resolution: str
    ) -> Dict[str, Any]:
        """
        Resolve an escalation.

        Args:
            escalation_id: Escalation identifier
            resolution: Resolution notes

        Returns:
            Updated escalation status
        """
        escalation = self._escalations.get(escalation_id)
        if not escalation:
            return {
                "status": "error",
                "message": "Escalation not found",
            }

        escalation["status"] = "resolved"
        escalation["resolved_at"] = datetime.now(timezone.utc).isoformat()
        escalation["resolution"] = resolution

        logger.info({
            "event": "escalation_resolved",
            "escalation_id": escalation_id,
        })

        return {
            "status": "resolved",
            "escalation_id": escalation_id,
        }

    def get_escalation_stats(self) -> Dict[str, int]:
        """Get escalation statistics."""
        stats = {"pending": 0, "acknowledged": 0, "resolved": 0}
        for escalation in self._escalations.values():
            status = escalation.get("status", "pending")
            stats[status] = stats.get(status, 0) + 1
        return stats

    def get_workflow_name(self) -> str:
        """Get workflow name."""
        return "EscalationWorkflow"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"
