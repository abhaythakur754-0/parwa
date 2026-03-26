"""
PARWA Mini Process Email Task.

Task for processing incoming emails using the Mini Email agent.
Extracts intent and routes to appropriate handler.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from variants.mini.agents.email_agent import MiniEmailAgent
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EmailIntent(Enum):
    """Email intent classification."""
    INQUIRY = "inquiry"
    COMPLAINT = "complaint"
    REFUND_REQUEST = "refund_request"
    ORDER_STATUS = "order_status"
    FEEDBACK = "feedback"
    OTHER = "other"


@dataclass
class EmailTaskResult:
    """Result from email processing task."""
    success: bool
    intent: Optional[str] = None
    summary: Optional[str] = None
    action_taken: Optional[str] = None
    confidence: float = 0.0
    escalated: bool = False
    escalation_reason: Optional[str] = None
    suggested_response: Optional[str] = None


class ProcessEmailTask:
    """
    Task for processing incoming emails.

    Uses MiniEmailAgent to:
    1. Parse email content
    2. Extract intent and key information
    3. Generate or route response
    4. Escalate if complex or angry sentiment

    Example:
        task = ProcessEmailTask()
        result = await task.execute({
            "email_id": "email_123",
            "subject": "Question about my order",
            "body": "Hi, I ordered last week and haven't received...",
            "sender_email": "customer@example.com"
        })
    """

    # Keywords for intent classification
    INTENT_KEYWORDS = {
        EmailIntent.REFUND_REQUEST: ["refund", "money back", "return", "cancel order"],
        EmailIntent.ORDER_STATUS: ["order status", "where is my", "tracking", "delivery"],
        EmailIntent.COMPLAINT: ["complaint", "unhappy", "disappointed", "terrible", "angry"],
        EmailIntent.FEEDBACK: ["feedback", "suggestion", "review", "rating"],
        EmailIntent.INQUIRY: ["question", "how do i", "what is", "help"],
    }

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None,
        agent_id: str = "mini_email_task"
    ) -> None:
        """
        Initialize email processing task.

        Args:
            mini_config: Mini configuration
            agent_id: Agent identifier
        """
        self._config = mini_config or get_mini_config()
        self._agent = MiniEmailAgent(
            agent_id=agent_id,
            mini_config=self._config
        )

    async def execute(self, input_data: Dict[str, Any]) -> EmailTaskResult:
        """
        Execute the email processing task.

        Args:
            input_data: Must contain:
                - email_id: Email identifier
                - subject: Email subject line
                - body: Email body content
                - sender_email: Sender email address

        Returns:
            EmailTaskResult with processing outcome
        """
        email_id = input_data.get("email_id", "")
        subject = input_data.get("subject", "")
        body = input_data.get("body", "")
        sender_email = input_data.get("sender_email", "")

        logger.info({
            "event": "email_task_started",
            "email_id": email_id,
            "subject": subject[:50],
            "sender": sender_email,
        })

        # Classify intent
        intent = self._classify_intent(subject, body)

        # Combine into email_content for the agent
        email_content = f"Subject: {subject}\n\n{body}"

        # Process through Mini Email agent
        response = await self._agent.process({
            "email_content": email_content,
            "email_id": email_id,
            "sender_email": sender_email,
            "intent": intent
        })

        # Build result
        result = EmailTaskResult(
            success=response.success,
            intent=intent,
            confidence=response.confidence,
            escalated=response.escalated,
            escalation_reason=response.escalation_reason if response.escalated else None,
        )

        if response.success and not response.escalated:
            data = response.data or {}
            result.summary = data.get("summary")
            result.action_taken = data.get("action_taken")
            result.suggested_response = data.get("suggested_response")

        logger.info({
            "event": "email_task_completed",
            "email_id": email_id,
            "intent": intent,
            "success": result.success,
            "escalated": result.escalated,
        })

        return result

    def _classify_intent(self, subject: str, body: str) -> str:
        """
        Classify email intent based on content.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            Intent classification string
        """
        combined = f"{subject} {body}".lower()

        for intent, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return intent.value

        return EmailIntent.OTHER.value

    def get_task_name(self) -> str:
        """Get task name."""
        return "process_email"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"

    def get_tier(self) -> str:
        """Get tier used."""
        return "light"
