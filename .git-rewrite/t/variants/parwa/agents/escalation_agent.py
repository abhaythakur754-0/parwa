"""
PARWA Junior Escalation Agent.

PARWA Junior's escalation agent handles human handoff with
enhanced routing and medium tier support.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_escalation_agent import (
    BaseEscalationAgent,
    AgentResponse,
    EscalationReason,
    EscalationChannel,
)
from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ParwaEscalationAgent(BaseEscalationAgent):
    """
    PARWA Junior Escalation Agent.

    Handles human handoff with the following characteristics:
    - Routes to 'medium' tier for sophisticated responses
    - Enhanced escalation routing based on context
    - Lower escalation threshold (60% vs 70% for Mini)
    - Supports all channels including voice and video
    """

    # PARWA Junior uses 60% threshold
    PARWA_ESCALATION_THRESHOLD = 0.60

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        parwa_config: Optional[ParwaConfig] = None,
    ) -> None:
        """
        Initialize PARWA Junior Escalation Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            parwa_config: Optional ParwaConfig instance
        """
        # Set parwa_config BEFORE calling super().__init__ because
        # the parent's __init__ calls get_tier() which needs this attribute
        self._parwa_config = parwa_config or get_parwa_config()
        super().__init__(agent_id, config, company_id)

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA uses 'medium'."""
        return self._parwa_config.default_tier

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "parwa"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process an escalation action.

        Handles escalation checks, triggers, and acknowledgments.

        Args:
            input_data: Must contain 'action' key

        Returns:
            AgentResponse with escalation processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_escalation_process", {
            "action": action,
            "tier": self.get_tier(),
        })

        if action == "check":
            return await self._handle_check_escalation(input_data)
        elif action == "escalate":
            return await self._handle_escalate(input_data)
        elif action == "acknowledge":
            return await self._handle_acknowledge(input_data)
        elif action == "resolve":
            return await self._handle_resolve(input_data)
        elif action == "stats":
            return await self._handle_stats()
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def _handle_check_escalation(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle escalation check."""
        context = input_data.get("context", {})

        needed = await self.check_escalation_needed(context)

        confidence = context.get("confidence", 1.0)

        return AgentResponse(
            success=True,
            message="Escalation check completed",
            data={
                "escalation_needed": needed,
                "confidence": confidence,
                "threshold": self.PARWA_ESCALATION_THRESHOLD,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=needed,
        )

    async def _handle_escalate(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle trigger escalation."""
        ticket_id = input_data.get("ticket_id")
        reason = input_data.get("reason", EscalationReason.LOW_CONFIDENCE.value)
        context = input_data.get("context", {})

        if not ticket_id:
            return AgentResponse(
                success=False,
                message="Missing required field: ticket_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        escalation = await self.escalate(ticket_id, reason, context)

        return AgentResponse(
            success=True,
            message=f"Escalation {escalation['escalation_id']} created",
            data={
                "escalation": escalation,
                "escalation_id": escalation["escalation_id"],
            },
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=True,
        )

    async def _handle_acknowledge(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle acknowledge escalation."""
        escalation_id = input_data.get("escalation_id")
        handler = input_data.get("handler", "unknown")

        if not escalation_id:
            return AgentResponse(
                success=False,
                message="Missing required field: escalation_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.acknowledge_escalation(escalation_id, handler)

        if "error" in result:
            return AgentResponse(
                success=False,
                message=result["message"],
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message=f"Escalation {escalation_id} acknowledged by {handler}",
            data={"escalation": result},
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_resolve(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle resolve escalation."""
        escalation_id = input_data.get("escalation_id")
        resolution = input_data.get("resolution", "")

        if not escalation_id:
            return AgentResponse(
                success=False,
                message="Missing required field: escalation_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.resolve_escalation(escalation_id, resolution)

        if "error" in result:
            return AgentResponse(
                success=False,
                message=result["message"],
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message=f"Escalation {escalation_id} resolved",
            data={"escalation": result},
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_stats(self) -> AgentResponse:
        """Handle get escalation stats."""
        stats = self.get_escalation_stats()
        stats["variant"] = self.get_variant()
        stats["tier"] = self.get_tier()
        stats["threshold"] = self.PARWA_ESCALATION_THRESHOLD

        return AgentResponse(
            success=True,
            message="Escalation statistics retrieved",
            data=stats,
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def check_escalation_needed(
        self,
        context: Dict[str, Any]
    ) -> bool:
        """
        Check if escalation is needed based on context.

        Uses PARWA Junior's 60% threshold.

        Args:
            context: Context dictionary

        Returns:
            True if escalation is needed
        """
        # Check confidence threshold (60% for PARWA)
        confidence = context.get("confidence", 1.0)
        if confidence < self.PARWA_ESCALATION_THRESHOLD:
            self._log_escalation_check(
                EscalationReason.LOW_CONFIDENCE.value,
                confidence,
                True
            )
            return True

        # Check for explicit escalation request
        if context.get("customer_request") in ["human", "agent", "supervisor"]:
            self._log_escalation_check(
                EscalationReason.CUSTOMER_REQUEST.value,
                confidence,
                True
            )
            return True

        # Check for sensitive topics
        sensitive_topics = ["refund", "complaint", "legal", "sue"]
        topic = context.get("topic", "").lower()
        if any(t in topic for t in sensitive_topics):
            self._log_escalation_check(
                EscalationReason.SENSITIVE_TOPIC.value,
                confidence,
                True
            )
            return True

        # Check for repeated failures
        if context.get("retry_count", 0) >= 3:
            self._log_escalation_check(
                EscalationReason.REPEATED_FAILURES.value,
                confidence,
                True
            )
            return True

        # Check for negative sentiment
        sentiment = context.get("customer_sentiment", "")
        if sentiment in ["frustrated", "angry", "upset"]:
            self._log_escalation_check(
                EscalationReason.COMPLAINT.value,
                confidence,
                True
            )
            return True

        self._log_escalation_check("none", confidence, False)
        return False
