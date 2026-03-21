"""
PARWA Mini Email Agent.

Mini PARWA's email agent processes email communications using
the Light tier. It parses emails, extracts intent, and
escalates complex cases.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_email_agent import BaseEmailAgent, AgentResponse
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniEmailAgent(BaseEmailAgent):
    """
    Mini PARWA Email Agent.

    Handles email processing with the following characteristics:
    - Always routes to 'light' tier
    - Escalates when confidence < 70%
    - Uses MiniConfig for configuration
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        mini_config: Optional[MiniConfig] = None,
    ) -> None:
        """Initialize Mini Email Agent."""
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
        Process an email.

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
        self.log_action("mini_email_process", {
            "content_length": len(email_content),
            "tier": self.get_tier(),
        })

        # Parse the email
        parsed = await self.parse_email(email_content)

        # Extract intent
        intent = await self.extract_intent(parsed)

        # Calculate confidence
        confidence = 0.85 if intent != "unknown" else 0.5

        # Check escalation
        escalated = confidence < self._mini_config.escalation_threshold

        return AgentResponse(
            success=True,
            message="Email processed by Mini PARWA",
            data={
                "parsed": parsed,
                "intent": intent,
            },
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
        """Check if escalation is needed based on Mini threshold."""
        return confidence < self._mini_config.escalation_threshold
