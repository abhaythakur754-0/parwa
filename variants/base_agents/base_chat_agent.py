"""
PARWA Base Chat Agent.

Abstract base class for chat agents. Provides common functionality
for message handling, conversation context management, and response generation.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class BaseChatAgent(BaseAgent):
    """
    Abstract base class for chat agents.

    Provides:
    - Message handling
    - Conversation context management
    - Session tracking

    Subclasses must implement:
    - get_tier()
    - get_variant()
    - process()
    """

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Chat agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy
        """
        super().__init__(agent_id, config, company_id)
        self._sessions: Dict[str, Dict[str, Any]] = {}

    async def handle_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle a chat message.

        Args:
            message: Chat message text
            context: Optional conversation context

        Returns:
            Response dictionary with message and metadata
        """
        context = context or {}
        session_id = context.get("session_id", "default")

        # Get or create session
        session = await self.get_conversation_context(session_id)

        # Add message to history
        session["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "message": message,
            "session_id": session_id,
            "message_count": len(session["messages"]),
            "context": context,
        }

    async def get_conversation_context(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get conversation context for a session.

        Args:
            session_id: Session identifier

        Returns:
            Conversation context with:
            - session_id: Session identifier
            - messages: List of messages
            - created_at: Session creation time
            - metadata: Additional session metadata
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "messages": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {},
            }

        return self._sessions[session_id]

    async def update_conversation_context(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """
        Update conversation context.

        Args:
            session_id: Session identifier
            updates: Updates to apply to context
        """
        if session_id in self._sessions:
            self._sessions[session_id]["metadata"].update(updates)

    async def add_agent_response(
        self,
        session_id: str,
        message: str,
        confidence: float
    ) -> None:
        """
        Add an agent response to the conversation.

        Args:
            session_id: Session identifier
            message: Agent response message
            confidence: Confidence score
        """
        if session_id in self._sessions:
            self._sessions[session_id]["messages"].append({
                "role": "agent",
                "content": message,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def clear_session(self, session_id: str) -> bool:
        """
        Clear a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was cleared, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_message_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get message history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        session = self._sessions.get(session_id, {})
        messages = session.get("messages", [])
        return messages[-limit:]
