"""
PARWA Base Escalation Agent.

Abstract base class for escalation agents. Provides common functionality
for determining when escalation is needed and triggering human handoff.

CRITICAL: Escalation agents handle the handoff to human support,
ensuring complex or sensitive issues are properly routed.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum
import uuid

from variants.base_agents.base_agent import (
    BaseAgent,
    AgentResponse,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EscalationReason(Enum):
    """Reasons for escalation."""
    LOW_CONFIDENCE = "low_confidence"
    COMPLEX_QUERY = "complex_query"
    CUSTOMER_REQUEST = "customer_request"
    SENSITIVE_TOPIC = "sensitive_topic"
    REFUND_REQUEST = "refund_request"
    COMPLAINT = "complaint"
    REPEATED_FAILURES = "repeated_failures"
    TIME_LIMIT = "time_limit"


class EscalationChannel(Enum):
    """Available escalation channels."""
    HUMAN_AGENT = "human_agent"
    SUPERVISOR = "supervisor"
    SPECIALIST = "specialist"
    EMAIL = "email"
    PHONE = "phone"


class BaseEscalationAgent(BaseAgent):
    """
    Abstract base class for escalation agents.

    Provides:
    - Escalation need detection
    - Human handoff triggering
    - Escalation tracking
    - Channel routing

    CRITICAL: Escalation agents are the safety net for AI support.
    They ensure customers can always reach a human when needed.

    Subclasses must implement:
    - get_tier()
    - get_variant()
    - process()
    """

    DEFAULT_ESCALATION_THRESHOLD = 0.70

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Escalation agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy
        """
        super().__init__(agent_id, config, company_id)
        self._escalations: Dict[str, Dict[str, Any]] = {}
        self._escalation_count = 0

    async def check_escalation_needed(
        self,
        context: Dict[str, Any]
    ) -> bool:
        """
        Check if escalation is needed based on context.

        Args:
            context: Context dictionary with:
                - confidence: Current confidence score
                - retry_count: Number of retries
                - customer_sentiment: Detected sentiment
                - topic: Detected topic
                - request: Customer request

        Returns:
            True if escalation is needed
        """
        # Check confidence threshold
        confidence = context.get("confidence", 1.0)
        if confidence < self.DEFAULT_ESCALATION_THRESHOLD:
            self._log_escalation_check(
                EscalationReason.LOW_CONFIDENCE.value,
                confidence,
                True
            )
            return True

        # Check for explicit escalation request
        if context.get("customer_request") in ["human", "agent", "supervisor"]:
            self._log_escalation_check(
                EscalationReason.CUSTOMER_REQUEST.value,
                confidence,
                True
            )
            return True

        # Check for sensitive topics
        sensitive_topics = ["refund", "complaint", "legal", "sue"]
        topic = context.get("topic", "").lower()
        if any(t in topic for t in sensitive_topics):
            self._log_escalation_check(
                EscalationReason.SENSITIVE_TOPIC.value,
                confidence,
                True
            )
            return True

        # Check for repeated failures
        if context.get("retry_count", 0) >= 3:
            self._log_escalation_check(
                EscalationReason.REPEATED_FAILURES.value,
                confidence,
                True
            )
            return True

        # Check for negative sentiment
        sentiment = context.get("customer_sentiment", "")
        if sentiment in ["frustrated", "angry", "upset"]:
            self._log_escalation_check(
                EscalationReason.COMPLAINT.value,
                confidence,
                True
            )
            return True

        self._log_escalation_check("none", confidence, False)
        return False

    async def escalate(
        self,
        ticket_id: str,
        reason: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger escalation to human support.

        CRITICAL: This method initiates the human handoff process.

        Args:
            ticket_id: Associated ticket ID
            reason: Reason for escalation
            context: Full context of the escalation

        Returns:
            Escalation record with:
            - escalation_id: Unique escalation ID
            - status: Escalation status
            - channel: Assigned escalation channel
            - assigned_to: Assigned handler (if known)
        """
        self._escalation_count += 1
        escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"

        # Determine best channel
        channel = self.get_escalation_channel(context)

        escalation = {
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "reason": reason,
            "channel": channel,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "company_id": str(self._company_id) if self._company_id else None,
            "assigned_to": None,
            "acknowledged_at": None,
            "resolved_at": None,
        }

        self._escalations[escalation_id] = escalation

        logger.info({
            "event": "escalation_triggered",
            "agent_id": self._agent_id,
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "reason": reason,
            "channel": channel,
        })

        return escalation

    def get_escalation_channel(
        self,
        context: Dict[str, Any]
    ) -> str:
        """
        Determine the best escalation channel.

        Args:
            context: Context for routing decision

        Returns:
            Channel to use for escalation
        """
        reason = context.get("reason", "")
        confidence = context.get("confidence", 1.0)

        # Very low confidence or complex issues -> specialist
        if confidence < 0.5 or "complex" in reason.lower():
            return EscalationChannel.SPECIALIST.value

        # Refund requests -> supervisor
        if "refund" in reason.lower():
            return EscalationChannel.SUPERVISOR.value

        # Complaints -> supervisor
        if "complaint" in reason.lower():
            return EscalationChannel.SUPERVISOR.value

        # Default to human agent
        return EscalationChannel.HUMAN_AGENT.value

    async def acknowledge_escalation(
        self,
        escalation_id: str,
        handler: str
    ) -> Dict[str, Any]:
        """
        Acknowledge an escalation.

        Args:
            escalation_id: Escalation identifier
            handler: Handler who acknowledged

        Returns:
            Updated escalation record
        """
        escalation = self._escalations.get(escalation_id)

        if not escalation:
            return {
                "status": "error",
                "message": f"Escalation {escalation_id} not found",
            }

        escalation["status"] = "acknowledged"
        escalation["assigned_to"] = handler
        escalation["acknowledged_at"] = datetime.now(timezone.utc).isoformat()

        logger.info({
            "event": "escalation_acknowledged",
            "agent_id": self._agent_id,
            "escalation_id": escalation_id,
            "handler": handler,
        })

        return escalation

    async def resolve_escalation(
        self,
        escalation_id: str,
        resolution: str
    ) -> Dict[str, Any]:
        """
        Resolve an escalation.

        Args:
            escalation_id: Escalation identifier
            resolution: Resolution notes

        Returns:
            Updated escalation record
        """
        escalation = self._escalations.get(escalation_id)

        if not escalation:
            return {
                "status": "error",
                "message": f"Escalation {escalation_id} not found",
            }

        escalation["status"] = "resolved"
        escalation["resolved_at"] = datetime.now(timezone.utc).isoformat()
        escalation["resolution"] = resolution

        logger.info({
            "event": "escalation_resolved",
            "agent_id": self._agent_id,
            "escalation_id": escalation_id,
        })

        return escalation

    def get_escalation_stats(self) -> Dict[str, Any]:
        """Get escalation statistics."""
        pending = sum(1 for e in self._escalations.values() if e["status"] == "pending")
        acknowledged = sum(1 for e in self._escalations.values() if e["status"] == "acknowledged")
        resolved = sum(1 for e in self._escalations.values() if e["status"] == "resolved")

        return {
            "total_escalations": self._escalation_count,
            "pending": pending,
            "acknowledged": acknowledged,
            "resolved": resolved,
        }

    def _log_escalation_check(
        self,
        reason: str,
        confidence: float,
        escalated: bool
    ) -> None:
        """Log an escalation check."""
        logger.debug({
            "event": "escalation_check",
            "agent_id": self._agent_id,
            "reason": reason,
            "confidence": confidence,
            "escalated": escalated,
        })
