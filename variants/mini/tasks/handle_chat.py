"""
PARWA Mini Handle Chat Task.

Task for handling chat messages using the Mini Chat agent.
Provides real-time responses and session management.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from variants.mini.agents.chat_agent import MiniChatAgent
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChatTaskResult:
    """Result from chat handling task."""
    success: bool
    response: Optional[str] = None
    session_id: Optional[str] = None
    confidence: float = 0.0
    escalated: bool = False
    escalation_reason: Optional[str] = None
    suggested_actions: list = None
    end_session: bool = False

    def __post_init__(self):
        if self.suggested_actions is None:
            self.suggested_actions = []


class HandleChatTask:
    """
    Task for handling chat messages.

    Uses MiniChatAgent to:
    1. Process incoming chat message
    2. Maintain session context
    3. Provide real-time responses
    4. Escalate when needed

    Example:
        task = HandleChatTask()
        result = await task.execute({
            "message": "I need help with my order",
            "session_id": "sess_123",
            "customer_id": "cust_456"
        })
    """

    # Session limits for Mini variant
    MAX_SESSION_DURATION_MINUTES = 30
    MAX_MESSAGES_PER_SESSION = 50

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None,
        agent_id: str = "mini_chat_task"
    ) -> None:
        """
        Initialize chat handling task.

        Args:
            mini_config: Mini configuration
            agent_id: Agent identifier
        """
        self._config = mini_config or get_mini_config()
        self._agent = MiniChatAgent(
            agent_id=agent_id,
            mini_config=self._config
        )
        self._sessions: Dict[str, Dict[str, Any]] = {}

    async def execute(self, input_data: Dict[str, Any]) -> ChatTaskResult:
        """
        Execute the chat handling task.

        Args:
            input_data: Must contain:
                - message: The chat message
                - session_id: Chat session identifier
                - customer_id: Optional customer identifier
                - message_count: Current message count in session

        Returns:
            ChatTaskResult with response and session info
        """
        message = input_data.get("message", "")
        session_id = input_data.get("session_id", "")
        customer_id = input_data.get("customer_id")
        message_count = input_data.get("message_count", 0)

        logger.info({
            "event": "chat_task_started",
            "session_id": session_id,
            "message": message[:50],
            "message_count": message_count,
        })

        # Check session limits
        if message_count >= self.MAX_MESSAGES_PER_SESSION:
            return ChatTaskResult(
                success=False,
                session_id=session_id,
                escalated=True,
                escalation_reason="max_messages_reached",
                end_session=True,
                response="I've connected you with a human agent who can continue assisting you.",
            )

        # Process through Mini Chat agent
        response = await self._agent.process({
            "message": message,
            "session_id": session_id,
            "customer_id": customer_id,
            "message_count": message_count
        })

        # Build result
        result = ChatTaskResult(
            success=response.success,
            session_id=session_id,
            confidence=response.confidence,
            escalated=response.escalated,
            escalation_reason=response.escalation_reason if response.escalated else None,
        )

        if response.success:
            data = response.data or {}
            result.response = response.message or data.get("response")
            result.suggested_actions = data.get("suggested_actions", [])

        logger.info({
            "event": "chat_task_completed",
            "session_id": session_id,
            "success": result.success,
            "escalated": result.escalated,
        })

        return result

    def get_task_name(self) -> str:
        """Get task name."""
        return "handle_chat"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"

    def get_tier(self) -> str:
        """Get tier used."""
        return "light"
