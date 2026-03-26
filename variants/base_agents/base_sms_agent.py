"""
PARWA Base SMS Agent.

Abstract base class for SMS agents. Provides common functionality
for SMS parsing, response sending, and conversation tracking.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
import re

from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class BaseSMSAgent(BaseAgent):
    """
    Abstract base class for SMS agents.

    Provides:
    - SMS parsing
    - Response sending (mocked)
    - Conversation tracking

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
        Initialize SMS agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy
        """
        super().__init__(agent_id, config, company_id)
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}
        self._message_count = 0

    async def parse_sms(self, sms_content: str) -> Dict[str, Any]:
        """
        Parse SMS content into structured data.

        Args:
            sms_content: Raw SMS content

        Returns:
            Parsed SMS structure with:
            - message: Clean message text
            - keywords: Detected keywords
            - order_references: Any order numbers found
            - phone_number: Detected phone numbers
            - is_short: Whether this is a short message
        """
        result = {
            "message": sms_content.strip(),
            "keywords": [],
            "order_references": [],
            "phone_numbers": [],
            "is_short": len(sms_content) < 50,
            "word_count": len(sms_content.split()),
        }

        # Extract order references
        order_patterns = [r"ORD-\d+", r"ORDER[-\s]?\d+", r"#\d{4,}"]
        for pattern in order_patterns:
            matches = re.findall(pattern, sms_content, re.IGNORECASE)
            result["order_references"].extend(matches)

        # Extract phone numbers
        phone_pattern = r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        result["phone_numbers"] = re.findall(phone_pattern, sms_content)

        # Detect common keywords
        keyword_list = [
            "help", "order", "status", "cancel", "refund",
            "track", "support", "urgent", "issue", "problem"
        ]
        sms_lower = sms_content.lower()
        for keyword in keyword_list:
            if keyword in sms_lower:
                result["keywords"].append(keyword)

        return result

    async def send_response(
        self,
        to: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Send an SMS response.

        Note: This is mocked for testing. In production,
        this would use Twilio or similar service.

        Args:
            to: Recipient phone number
            message: Message to send

        Returns:
            Send result with message ID
        """
        self._message_count += 1

        # Mock response
        result = {
            "status": "sent",
            "message_id": f"SMS-{self._message_count:06d}",
            "to": to,
            "message_length": len(message),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "segments": (len(message) // 160) + 1,
        }

        logger.info({
            "event": "sms_sent",
            "agent_id": self._agent_id,
            "to": to,
            "message_id": result["message_id"],
        })

        return result

    async def get_conversation(
        self,
        phone_number: str
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a phone number.

        Args:
            phone_number: Phone number

        Returns:
            List of messages in conversation
        """
        return self._conversations.get(phone_number, [])

    async def add_to_conversation(
        self,
        phone_number: str,
        message: str,
        is_incoming: bool
    ) -> None:
        """
        Add a message to conversation history.

        Args:
            phone_number: Phone number
            message: Message content
            is_incoming: True if incoming, False if outgoing
        """
        if phone_number not in self._conversations:
            self._conversations[phone_number] = []

        self._conversations[phone_number].append({
            "message": message,
            "is_incoming": is_incoming,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_stats(self) -> Dict[str, Any]:
        """Get SMS agent statistics."""
        return {
            "total_messages_sent": self._message_count,
            "active_conversations": len(self._conversations),
        }
