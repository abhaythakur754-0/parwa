"""
PARWA Mini SMS Agent.

Mini PARWA's SMS agent handles SMS communications using
the Light tier. Simple messages are handled directly,
complex ones are escalated.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_sms_agent import BaseSMSAgent, AgentResponse
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniSMSAgent(BaseSMSAgent):
    """
    Mini PARWA SMS Agent.

    Handles SMS communications with the following characteristics:
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
        """Initialize Mini SMS Agent."""
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
        Process an SMS message.

        Args:
            input_data: Must contain 'sms_content' key, optionally 'from_number'

        Returns:
            AgentResponse with SMS processing result
        """
        # Validate input
        validation_error = self.validate_input(input_data, {
            "required": ["sms_content"],
            "properties": {"sms_content": {"type": "string"}}
        })
        if validation_error:
            return AgentResponse(
                success=False,
                message=validation_error,
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        sms_content = input_data["sms_content"]
        from_number = input_data.get("from_number", "unknown")

        self.log_action("mini_sms_process", {
            "from_number": from_number,
            "content_length": len(sms_content),
            "tier": self.get_tier(),
        })

        # Parse the SMS
        parsed = await self.parse_sms(sms_content)

        # Add to conversation history
        await self.add_to_conversation(from_number, sms_content, is_incoming=True)

        # Calculate confidence based on parsed content
        confidence = self._calculate_sms_confidence(parsed)

        # Check escalation
        escalated = confidence < self._mini_config.escalation_threshold

        # Generate response based on keywords
        response_message = self._generate_sms_response(parsed)

        # Send response if not escalated
        if not escalated and from_number != "unknown":
            await self.send_response(from_number, response_message)
            await self.add_to_conversation(from_number, response_message, is_incoming=False)

        return AgentResponse(
            success=True,
            message="SMS processed by Mini PARWA",
            data={
                "parsed": parsed,
                "response": response_message,
                "from_number": from_number,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    def _calculate_sms_confidence(self, parsed: Dict[str, Any]) -> float:
        """
        Calculate confidence based on parsed SMS content.

        Args:
            parsed: Parsed SMS data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.5  # Base confidence

        # Increase confidence for short, clear messages
        if parsed.get("is_short"):
            confidence += 0.15

        # Increase confidence for messages with order references
        if parsed.get("order_references"):
            confidence += 0.2

        # Increase confidence for messages with recognized keywords
        if parsed.get("keywords"):
            confidence += 0.1

        return min(1.0, confidence)

    def _generate_sms_response(self, parsed: Dict[str, Any]) -> str:
        """
        Generate an SMS response based on parsed content.

        Args:
            parsed: Parsed SMS data

        Returns:
            Response message string
        """
        keywords = parsed.get("keywords", [])

        if "help" in keywords:
            return "Thanks for reaching out! Reply with ORDER for order status, or SUPPORT for help."
        elif "order" in keywords or "status" in keywords:
            return "For order status, please provide your order number (e.g., ORD-12345)."
        elif "refund" in keywords:
            return "For refund requests, please provide your order number and reason."
        elif "cancel" in keywords:
            return "To cancel, please provide your order number. Cancellations within 24hrs are free."
        else:
            return "Thanks for your message. A support agent will respond shortly."

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if escalation is needed based on Mini threshold."""
        return confidence < self._mini_config.escalation_threshold
