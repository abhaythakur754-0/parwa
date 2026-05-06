"""
PARWA Junior SMS Agent.

PARWA Junior's SMS agent handles SMS processing with enhanced
parsing and medium tier support.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_sms_agent import BaseSMSAgent, AgentResponse
from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ParwaSMSAgent(BaseSMSAgent):
    """
    PARWA Junior SMS Agent.

    Handles SMS processing with the following characteristics:
    - Routes to 'medium' tier for sophisticated responses
    - Enhanced SMS parsing with keyword detection
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
        Initialize PARWA Junior SMS Agent.

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
        Process an SMS message.

        Parses SMS content, detects keywords, and routes appropriately.

        Args:
            input_data: Must contain 'message' key, optionally 'phone_number'

        Returns:
            AgentResponse with SMS processing result
        """
        # Validate input
        validation_error = self.validate_input(input_data, {
            "required": ["message"],
            "properties": {"message": {"type": "string"}}
        })
        if validation_error:
            return AgentResponse(
                success=False,
                message=validation_error,
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        message = input_data["message"]
        phone_number = input_data.get("phone_number", "unknown")

        self.log_action("parwa_sms_process", {
            "message_length": len(message),
            "phone_number": phone_number,
            "tier": self.get_tier(),
        })

        # Parse the SMS
        parsed_sms = await self.parse_sms(message)

        # Add to conversation history
        await self.add_to_conversation(phone_number, message, is_incoming=True)

        # Calculate confidence based on parsed content
        confidence = self._calculate_sms_confidence(parsed_sms)

        # Check escalation based on PARWA config threshold (60%)
        escalated = confidence < self._parwa_config.escalation_threshold

        if escalated:
            self.log_action("parwa_sms_escalate", {
                "phone_number": phone_number,
                "confidence": confidence,
                "threshold": self._parwa_config.escalation_threshold,
            })

        # Format response
        response_message = "SMS processed successfully"
        if escalated:
            response_message = "SMS escalated due to low confidence"

        # Send response if not escalated
        if not escalated and phone_number != "unknown":
            await self.send_response(phone_number, response_message)
            await self.add_to_conversation(phone_number, response_message, is_incoming=False)

        return AgentResponse(
            success=True,
            message=response_message,
            data={
                "parsed": parsed_sms,
                "phone_number": phone_number,
                "keywords": parsed_sms.get("keywords", []),
                "order_references": parsed_sms.get("order_references", []),
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    def _calculate_sms_confidence(
        self,
        parsed_sms: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence for SMS processing.

        Args:
            parsed_sms: Parsed SMS data

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.6  # Base confidence for PARWA

        # Higher confidence for clear keywords
        keywords = parsed_sms.get("keywords", [])
        if keywords:
            confidence += min(0.2, len(keywords) * 0.05)

        # Higher confidence if order references found
        if parsed_sms.get("order_references"):
            confidence += 0.15

        # Lower confidence for very short messages
        if parsed_sms.get("is_short", False):
            confidence -= 0.1

        # Lower confidence for very short word count
        word_count = parsed_sms.get("word_count", 0)
        if word_count < 3:
            confidence -= 0.15

        return max(0.0, min(1.0, confidence))

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
