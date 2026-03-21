"""
PARWA Mini Chat Agent.

Mini PARWA's chat agent handles real-time chat interactions using
the Light tier for fast responses. Complex conversations are escalated.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_chat_agent import BaseChatAgent, AgentResponse
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniChatAgent(BaseChatAgent):
    """
    Mini PARWA Chat Agent.

    Handles chat interactions with the following characteristics:
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
        """Initialize Mini Chat Agent."""
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
        Process a chat message.

        Args:
            input_data: Must contain 'message' key, optionally 'session_id'

        Returns:
            AgentResponse with chat response
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

        self.log_action("mini_chat_process", {
            "session_id": session_id,
            "message_length": len(message),
            "tier": self.get_tier(),
        })

        # Get conversation context
        context = await self.get_conversation_context(session_id)

        # Handle the message
        result = await self.handle_message(message, {"session_id": session_id})

        # Calculate confidence based on conversation history
        message_count = len(context.get("messages", []))
        confidence = 0.85 if message_count < 5 else 0.75

        # Check escalation
        escalated = confidence < self._mini_config.escalation_threshold

        # Generate response (mocked for now)
        response_message = "Thank you for your message. How can I help you?"

        # Add agent response to conversation
        await self.add_agent_response(session_id, response_message, confidence)

        return AgentResponse(
            success=True,
            message="Chat message processed by Mini PARWA",
            data={
                "response": response_message,
                "session_id": session_id,
                "message_count": result.get("message_count", 0),
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
