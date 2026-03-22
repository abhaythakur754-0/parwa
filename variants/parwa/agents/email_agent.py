"""
PARWA Junior Email Agent.

PARWA Junior's email agent handles email processing with enhanced
intent extraction and the medium tier for more sophisticated responses.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_email_agent import BaseEmailAgent, AgentResponse
from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ParwaEmailAgent(BaseEmailAgent):
    """
    PARWA Junior Email Agent.

    Handles email processing with the following characteristics:
    - Routes to 'medium' tier for more sophisticated responses
    - Enhanced intent extraction with more patterns
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
        Initialize PARWA Junior Email Agent.

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
        Process an email.

        Parses email content, extracts intent, and routes appropriately.

        Args:
            input_data: Must contain 'email_content' key

        Returns:
            AgentResponse with email processing result
        """
        # Validate input
        validation_error = self.validate_input(input_data, {
            "required": ["email_content"],
            "properties": {"email_content": {"type": "string"}}
        })
        if validation_error:
            return AgentResponse(
                success=False,
                message=validation_error,
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        email_content = input_data["email_content"]
        self.log_action("parwa_email_process", {
            "email_length": len(email_content),
            "tier": self.get_tier(),
        })

        # Parse the email
        parsed_email = await self.parse_email(email_content)

        # Extract intent
        intent = await self.extract_intent(parsed_email)

        # Calculate confidence
        confidence = self.get_intent_confidence(parsed_email, intent)

        # Check escalation based on PARWA config threshold (60%)
        escalated = confidence < self._parwa_config.escalation_threshold

        if escalated:
            self.log_action("parwa_email_escalate", {
                "intent": intent,
                "confidence": confidence,
                "threshold": self._parwa_config.escalation_threshold,
            })

        # Format response
        response_data = {
            "parsed": parsed_email,
            "intent": intent,
            "order_references": parsed_email.get("order_references", []),
            "urgency": parsed_email.get("urgency", "normal"),
        }

        formatted = self.format_email_response(intent, response_data, confidence)

        message = f"Email processed - Intent: {intent}"
        if escalated:
            message = f"Email escalated due to low confidence - Intent: {intent}"

        return AgentResponse(
            success=True,
            message=message,
            data=formatted,
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation is needed.

        Uses PARWA config's escalation threshold (default 60%).

        Args:
            confidence: Confidence score (0.0-1.0)
            context: Optional additional context

        Returns:
            True if confidence < escalation threshold
        """
        return confidence < self._parwa_config.escalation_threshold
