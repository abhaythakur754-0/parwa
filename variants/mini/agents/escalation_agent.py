"""
PARWA Mini Escalation Agent.

Mini PARWA's escalation agent handles human handoff triggers.
CRITICAL: This agent triggers the human handoff process when
confidence is low or customer requests a human.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_escalation_agent import (
    BaseEscalationAgent,
    AgentResponse,
    EscalationReason,
    EscalationChannel,
)
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniEscalationAgent(BaseEscalationAgent):
    """
    Mini PARWA Escalation Agent.

    Handles escalation to human support with the following characteristics:
    - Always routes to 'light' tier
    - Triggers human handoff on escalation
    - Escalation threshold: 70% confidence
    - Routes to appropriate channel based on context

    CRITICAL: This agent is the safety net for AI support.
    It ensures customers can always reach a human when needed.
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        mini_config: Optional[MiniConfig] = None,
    ) -> None:
        """
        Initialize Mini Escalation Agent.

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
        Process an escalation check request.

        CRITICAL: This method may trigger human handoff.

        Args:
            input_data: Must contain:
                - context: Context dict with confidence, sentiment, etc.
                - ticket_id: Associated ticket ID (optional)

        Returns:
            AgentResponse with escalation status
        """
        context = input_data.get("context", {})
        ticket_id = input_data.get("ticket_id", f"TKT-{self._agent_id}")

        self.log_action("mini_escalation_check", {
            "ticket_id": ticket_id,
            "confidence": context.get("confidence", 1.0),
            "tier": self.get_tier(),
        })

        # Check if escalation is needed
        needs_escalation = await self.check_escalation_needed(context)

        if needs_escalation:
            # Determine reason
            reason = self._determine_reason(context)

            # CRITICAL: Trigger human handoff
            escalation = await self.escalate(ticket_id, reason, context)

            self.log_action("mini_escalation_triggered", {
                "ticket_id": ticket_id,
                "escalation_id": escalation["escalation_id"],
                "reason": reason,
                "channel": escalation["channel"],
            })

            return AgentResponse(
                success=True,
                message="Escalation triggered - human handoff initiated",
                data={
                    "escalated": True,
                    "escalation": escalation,
                    "human_handoff": True,
                    "channel": escalation["channel"],
                },
                confidence=0.0,  # Confidence is low, that's why we escalated
                tier_used=self.get_tier(),
                variant=self.get_variant(),
                escalated=True,
            )

        # No escalation needed
        return AgentResponse(
            success=True,
            message="No escalation needed",
            data={
                "escalated": False,
                "confidence": context.get("confidence", 1.0),
            },
            confidence=context.get("confidence", 1.0),
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=False,
        )

    def _determine_reason(self, context: Dict[str, Any]) -> str:
        """Determine the primary reason for escalation."""
        confidence = context.get("confidence", 1.0)

        if confidence < 0.5:
            return EscalationReason.LOW_CONFIDENCE.value

        if context.get("customer_request") in ["human", "agent", "supervisor"]:
            return EscalationReason.CUSTOMER_REQUEST.value

        if context.get("retry_count", 0) >= 3:
            return EscalationReason.REPEATED_FAILURES.value

        sentiment = context.get("customer_sentiment", "")
        if sentiment in ["frustrated", "angry", "upset"]:
            return EscalationReason.COMPLAINT.value

        topic = context.get("topic", "").lower()
        if "refund" in topic:
            return EscalationReason.REFUND_REQUEST.value
        if "complaint" in topic:
            return EscalationReason.COMPLAINT.value

        return EscalationReason.COMPLEX_QUERY.value

    async def check_escalation_needed(self, context: Dict[str, Any]) -> bool:
        """
        Check if escalation is needed based on context.

        Uses Mini config's escalation threshold (default 70%).

        Args:
            context: Context dictionary

        Returns:
            True if escalation is needed
        """
        # Check confidence against Mini threshold
        confidence = context.get("confidence", 1.0)
        if confidence < self._mini_config.escalation_threshold:
            return True

        # Check for explicit human request
        if context.get("customer_request") in ["human", "agent", "supervisor"]:
            return True

        # Check for sensitive topics
        sensitive_topics = ["refund", "complaint", "legal", "sue"]
        topic = context.get("topic", "").lower()
        if any(t in topic for t in sensitive_topics):
            return True

        # Check for repeated failures
        if context.get("retry_count", 0) >= 3:
            return True

        # Check for negative sentiment
        sentiment = context.get("customer_sentiment", "")
        if sentiment in ["frustrated", "angry", "upset"]:
            return True

        return False

    def get_escalation_channel(self, context: Dict[str, Any]) -> str:
        """
        Determine the best escalation channel for Mini.

        Mini routes escalations to:
        - Specialist for very low confidence
        - Supervisor for refunds/complaints
        - Human agent for everything else

        Args:
            context: Context for routing decision

        Returns:
            Channel to use for escalation
        """
        reason = context.get("reason", "")
        confidence = context.get("confidence", 1.0)

        # Very low confidence -> specialist
        if confidence < 0.5:
            return EscalationChannel.SPECIALIST.value

        # Refunds and complaints -> supervisor
        reason_lower = reason.lower() if isinstance(reason, str) else ""
        if "refund" in reason_lower or "complaint" in reason_lower:
            return EscalationChannel.SUPERVISOR.value

        # Default to human agent
        return EscalationChannel.HUMAN_AGENT.value

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation is needed.

        Args:
            confidence: Confidence score (0.0-1.0)
            context: Optional additional context

        Returns:
            True if confidence < escalation threshold
        """
        return confidence < self._mini_config.escalation_threshold

    def get_escalation_stats_summary(self) -> Dict[str, Any]:
        """Get escalation statistics summary."""
        stats = self.get_escalation_stats()
        stats["variant"] = self.get_variant()
        stats["tier"] = self.get_tier()
        stats["escalation_threshold"] = self._mini_config.escalation_threshold
        return stats
