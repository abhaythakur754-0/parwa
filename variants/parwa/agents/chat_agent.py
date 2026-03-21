"""
PARWA Junior Chat Agent.

PARWA Junior's chat agent handles real-time chat conversations with
enhanced context management and medium tier support.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_chat_agent import BaseChatAgent, AgentResponse
from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ParwaChatAgent(BaseChatAgent):
    """
    PARWA Junior Chat Agent.

    Handles chat conversations with the following characteristics:
    - Routes to 'medium' tier for sophisticated responses
    - Enhanced conversation context management
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
        Initialize PARWA Junior Chat Agent.

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
        Process a chat message.

        Maintains conversation context and routes appropriately.

        Args:
            input_data: Must contain 'message' key, optionally 'session_id'

        Returns:
            AgentResponse with chat processing result
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
        session_id = input_data.get("session_id", "default")
        context = input_data.get("context", {})

        self.log_action("parwa_chat_process", {
            "message_length": len(message),
            "session_id": session_id,
            "tier": self.get_tier(),
        })

        # Handle the message
        handle_result = await self.handle_message(message, {
            "session_id": session_id,
            **context
        })

        # Get conversation context
        session = await self.get_conversation_context(session_id)
        message_count = len(session.get("messages", []))

        # Calculate confidence based on context quality
        confidence = self._calculate_chat_confidence(message, session)

        # Check escalation based on PARWA config threshold (60%)
        escalated = confidence < self._parwa_config.escalation_threshold

        if escalated:
            self.log_action("parwa_chat_escalate", {
                "session_id": session_id,
                "confidence": confidence,
                "threshold": self._parwa_config.escalation_threshold,
            })

        # Generate response
        response_message = "Chat message processed"
        if escalated:
            response_message = "Chat escalated due to low confidence"

        # Add agent response to session
        await self.add_agent_response(session_id, response_message, confidence)

        return AgentResponse(
            success=True,
            message=response_message,
            data={
                "session_id": session_id,
                "message_count": message_count,
                "handle_result": handle_result,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    def _calculate_chat_confidence(
        self,
        message: str,
        session: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence for chat processing.

        Args:
            message: Current message
            session: Session context

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.6  # Base confidence for PARWA

        # Higher confidence for clear, direct messages
        if len(message.split()) <= 10:
            confidence += 0.15

        # Higher confidence if we have conversation history
        message_history = session.get("messages", [])
        if len(message_history) > 2:
            confidence += 0.1

        # Lower confidence for very long messages
        if len(message) > 500:
            confidence -= 0.1

        # Lower confidence for messages with questions
        if "?" in message:
            confidence -= 0.05

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
