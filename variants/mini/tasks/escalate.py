"""
PARWA Mini Escalate Task.

Task for triggering human escalation using the Mini Escalation agent.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from variants.mini.agents.escalation_agent import MiniEscalationAgent
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class EscalationLevel(Enum):
    """Escalation level."""
    TIER_1 = "tier_1"  # First-line support
    TIER_2 = "tier_2"  # Senior support
    TIER_3 = "tier_3"  # Expert/specialist
    MANAGER = "manager"  # Manager involvement


class EscalationReason(Enum):
    """Escalation reason types."""
    LOW_CONFIDENCE = "low_confidence"
    COMPLEX_QUERY = "complex_query"
    CUSTOMER_REQUEST = "customer_request"
    COMPLAINT = "complaint"
    REFUND_HIGH_VALUE = "refund_high_value"
    VIP_CUSTOMER = "vip_customer"
    REPEATED_ISSUE = "repeated_issue"
    ANGRY_SENTIMENT = "angry_sentiment"


@dataclass
class EscalationTaskResult:
    """Result from escalation task."""
    success: bool
    escalation_id: Optional[str] = None
    level: EscalationLevel = EscalationLevel.TIER_1
    reason: EscalationReason = EscalationReason.LOW_CONFIDENCE
    assigned_agent: Optional[str] = None
    queue_position: int = 0
    estimated_wait_minutes: int = 0
    customer_message: Optional[str] = None
    handoff_context: Optional[Dict[str, Any]] = None


class EscalateTask:
    """
    Task for triggering human escalation.

    Uses MiniEscalationAgent to:
    1. Determine escalation level
    2. Create escalation record
    3. Route to appropriate queue
    4. Prepare handoff context

    Example:
        task = EscalateTask()
        result = await task.execute({
            "conversation_id": "conv_123",
            "reason": "low_confidence",
            "context": {"query": "...", "attempts": 3},
            "customer_id": "cust_456"
        })
    """

    # Estimated wait times by level (minutes)
    ESTIMATED_WAIT = {
        EscalationLevel.TIER_1: 5,
        EscalationLevel.TIER_2: 15,
        EscalationLevel.TIER_3: 30,
        EscalationLevel.MANAGER: 60,
    }

    # Escalation threshold for confidence
    ESCALATION_CONFIDENCE_THRESHOLD = 0.70

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None,
        agent_id: str = "mini_escalation_task"
    ) -> None:
        """
        Initialize escalation task.

        Args:
            mini_config: Mini configuration
            agent_id: Agent identifier
        """
        self._config = mini_config or get_mini_config()
        self._agent = MiniEscalationAgent(
            agent_id=agent_id,
            mini_config=self._config
        )
        self._escalation_count = 0

    async def execute(self, input_data: Dict[str, Any]) -> EscalationTaskResult:
        """
        Execute the escalation task.

        Args:
            input_data: Must contain:
                - conversation_id: Conversation identifier
                - reason: Reason for escalation
                - context: Context dict with conversation history
                - customer_id: Customer identifier
                - confidence: Optional confidence score
                - is_vip: Optional VIP flag

        Returns:
            EscalationTaskResult with escalation details
        """
        conversation_id = input_data.get("conversation_id", "")
        reason_str = input_data.get("reason", "low_confidence")
        context = input_data.get("context", {})
        customer_id = input_data.get("customer_id", "")
        confidence = input_data.get("confidence", 0.0)
        is_vip = input_data.get("is_vip", False)

        logger.info({
            "event": "escalation_task_started",
            "conversation_id": conversation_id,
            "reason": reason_str,
            "customer_id": customer_id,
            "confidence": confidence,
            "is_vip": is_vip,
        })

        # Determine escalation level
        level = self._determine_level(reason_str, confidence, is_vip, context)

        # Generate escalation ID
        self._escalation_count += 1
        escalation_id = f"esc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{self._escalation_count}"

        # Process through Mini Escalation agent
        response = await self._agent.process({
            "escalation_id": escalation_id,
            "conversation_id": conversation_id,
            "reason": reason_str,
            "level": level.value,
            "context": context,
            "customer_id": customer_id
        })

        # Build result
        try:
            reason_enum = EscalationReason(reason_str)
        except ValueError:
            reason_enum = EscalationReason.LOW_CONFIDENCE

        result = EscalationTaskResult(
            success=response.success,
            escalation_id=escalation_id,
            level=level,
            reason=reason_enum,
            estimated_wait_minutes=self.ESTIMATED_WAIT.get(level, 15),
        )

        if response.success:
            data = response.data or {}
            result.assigned_agent = data.get("assigned_agent")
            result.queue_position = data.get("queue_position", 0)
            result.customer_message = data.get("customer_message", 
                "I'm connecting you with a human agent who can better assist you. Please hold.")
            result.handoff_context = data.get("handoff_context", context)

        logger.info({
            "event": "escalation_task_completed",
            "escalation_id": result.escalation_id,
            "success": result.success,
            "level": level.value,
        })

        return result

    def _determine_level(
        self,
        reason: str,
        confidence: float,
        is_vip: bool,
        context: Dict[str, Any]
    ) -> EscalationLevel:
        """
        Determine appropriate escalation level.

        Args:
            reason: Escalation reason
            confidence: Confidence score
            is_vip: VIP customer flag
            context: Additional context

        Returns:
            Escalation level
        """
        # VIP customers go directly to Tier 2 or Manager
        if is_vip:
            return EscalationLevel.MANAGER if reason == "complaint" else EscalationLevel.TIER_2

        # Complaints go to Tier 2
        if reason in ("complaint", "angry_sentiment"):
            return EscalationLevel.TIER_2

        # High-value refunds go to Tier 2
        if reason == "refund_high_value":
            return EscalationLevel.TIER_2

        # Repeated issues escalate higher
        attempts = context.get("attempts", 0)
        if attempts >= 3:
            return EscalationLevel.TIER_2

        # Default to Tier 1
        return EscalationLevel.TIER_1

    def get_task_name(self) -> str:
        """Get task name."""
        return "escalate"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"

    def get_tier(self) -> str:
        """Get tier used."""
        return "light"
