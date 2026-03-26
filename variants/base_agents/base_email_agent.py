"""
PARWA Base Email Agent.

Abstract base class for email-processing agents. Provides common
functionality for email parsing, intent extraction, and response handling.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
import re

from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class BaseEmailAgent(BaseAgent):
    """
    Abstract base class for email-processing agents.

    Provides:
    - Email parsing and structure extraction
    - Intent classification
    - Response formatting

    Subclasses must implement:
    - get_tier()
    - get_variant()
    - process()
    """

    # Common intent patterns
    INTENT_PATTERNS = {
        "refund": [r"refund", r"money back", r"return.*order"],
        "order_status": [r"where.*order", r"track.*order", r"order status"],
        "cancel": [r"cancel.*order", r"stop.*order"],
        "support": [r"help", r"support", r"issue", r"problem"],
        "inquiry": [r"question", r"inquiry", r"ask"],
        "complaint": [r"complaint", r"unhappy", r"disappointed"],
    }

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Email agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy
        """
        super().__init__(agent_id, config, company_id)

    async def parse_email(self, email_content: str) -> Dict[str, Any]:
        """
        Parse email content into structured data.

        Args:
            email_content: Raw email content

        Returns:
            Parsed email structure with:
            - subject: Email subject
            - body: Main body text
            - sender: Sender info if detected
            - order_references: Any order numbers found
            - urgency: Estimated urgency level
        """
        result = {
            "subject": "",
            "body": "",
            "sender": None,
            "order_references": [],
            "urgency": "normal",
            "has_attachments": False,
        }

        lines = email_content.strip().split("\n")
        body_lines = []
        in_body = False

        for line in lines:
            line_lower = line.lower().strip()

            # Extract subject
            if line_lower.startswith("subject:") or line_lower.startswith("subject :"):
                result["subject"] = line.split(":", 1)[1].strip()
                continue

            # Detect sender
            if line_lower.startswith("from:") or line_lower.startswith("from :"):
                result["sender"] = line.split(":", 1)[1].strip()
                continue

            # Detect attachments indicator
            if "attachment" in line_lower or "attached" in line_lower:
                result["has_attachments"] = True

            # Rest is body
            in_body = True
            if in_body:
                body_lines.append(line)

        result["body"] = "\n".join(body_lines).strip()

        # Extract order references (patterns like ORD-123, #12345, etc.)
        order_patterns = [
            r"ORD-\d+",
            r"ORDER[-\s]?\d+",
            r"#\d{4,}",
        ]
        for pattern in order_patterns:
            matches = re.findall(pattern, email_content, re.IGNORECASE)
            result["order_references"].extend(matches)

        # Detect urgency
        urgency_keywords = ["urgent", "asap", "immediately", "emergency", "critical"]
        if any(kw in email_content.lower() for kw in urgency_keywords):
            result["urgency"] = "high"
        elif any(kw in email_content.lower() for kw in ["whenever", "no rush"]):
            result["urgency"] = "low"

        return result

    async def extract_intent(self, parsed_email: Dict[str, Any]) -> str:
        """
        Extract the primary intent from parsed email.

        Args:
            parsed_email: Parsed email structure

        Returns:
            Primary intent string (refund, order_status, cancel, support, etc.)
        """
        # Combine subject and body for intent detection
        text = f"{parsed_email.get('subject', '')} {parsed_email.get('body', '')}".lower()

        # Check each intent pattern
        intent_scores = {}
        for intent, patterns in self.INTENT_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, text)
                score += len(matches)
            if score > 0:
                intent_scores[intent] = score

        if not intent_scores:
            return "inquiry"

        # Return highest scoring intent
        return max(intent_scores, key=intent_scores.get)

    def get_intent_confidence(
        self,
        parsed_email: Dict[str, Any],
        detected_intent: str
    ) -> float:
        """
        Calculate confidence for detected intent.

        Args:
            parsed_email: Parsed email structure
            detected_intent: The detected intent

        Returns:
            Confidence score between 0.0 and 1.0
        """
        text = f"{parsed_email.get('subject', '')} {parsed_email.get('body', '')}".lower()

        patterns = self.INTENT_PATTERNS.get(detected_intent, [])
        matches = 0
        for pattern in patterns:
            matches += len(re.findall(pattern, text))

        # More matches = higher confidence
        return min(1.0, 0.3 + (matches * 0.2))

    def format_email_response(
        self,
        intent: str,
        response_data: Dict[str, Any],
        confidence: float
    ) -> Dict[str, Any]:
        """
        Format an email response.

        Args:
            intent: Detected intent
            response_data: Response data
            confidence: Confidence score

        Returns:
            Formatted response dictionary
        """
        return {
            "intent": intent,
            "response": response_data,
            "confidence": confidence,
            "channel": "email",
            "requires_followup": confidence < 0.7,
        }
