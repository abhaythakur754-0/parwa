"""
PARWA Mini Make Call Task.

Task for making voice calls using the Mini Voice agent.
Enforces 2 concurrent call limit for Mini variant.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime, timezone

from variants.mini.agents.voice_agent import MiniVoiceAgent
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class CallStatus(Enum):
    """Call status enumeration."""
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED = "queued"


@dataclass
class CallTaskResult:
    """Result from make call task."""
    success: bool
    call_id: Optional[str] = None
    status: CallStatus = CallStatus.QUEUED
    duration_seconds: float = 0.0
    confidence: float = 0.0
    escalated: bool = False
    escalation_reason: Optional[str] = None
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    queued_reason: Optional[str] = None


class MakeCallTask:
    """
    Task for making voice calls.

    Uses MiniVoiceAgent to:
    1. Initiate outbound call
    2. Handle call flow
    3. Process responses
    4. Enforce 2 concurrent call limit

    CRITICAL: Mini variant limits to 2 concurrent calls.

    Example:
        task = MakeCallTask()
        result = await task.execute({
            "phone_number": "+1234567890",
            "reason": "order_confirmation",
            "customer_id": "cust_123"
        })
    """

    # Mini variant limits
    MAX_CONCURRENT_CALLS = 2

    def __init__(
        self,
        mini_config: Optional[MiniConfig] = None,
        agent_id: str = "mini_voice_task"
    ) -> None:
        """
        Initialize make call task.

        Args:
            mini_config: Mini configuration
            agent_id: Agent identifier
        """
        self._config = mini_config or get_mini_config()
        self._agent = MiniVoiceAgent(
            agent_id=agent_id,
            mini_config=self._config
        )
        self._active_calls: Dict[str, datetime] = {}

    async def execute(self, input_data: Dict[str, Any]) -> CallTaskResult:
        """
        Execute the make call task.

        Args:
            input_data: Must contain:
                - phone_number: Destination phone number
                - reason: Call reason (order_confirmation, support_followup, etc.)
                - customer_id: Optional customer identifier
                - priority: Optional priority (normal, high)

        Returns:
            CallTaskResult with call status
        """
        phone_number = input_data.get("phone_number", "")
        reason = input_data.get("reason", "general")
        customer_id = input_data.get("customer_id")
        priority = input_data.get("priority", "normal")

        logger.info({
            "event": "call_task_started",
            "phone_number": phone_number[-4:] if phone_number else None,  # Mask for privacy
            "reason": reason,
            "customer_id": customer_id,
            "priority": priority,
            "active_calls": len(self._active_calls),
        })

        # Check concurrent call limit (CRITICAL for Mini)
        if len(self._active_calls) >= self.MAX_CONCURRENT_CALLS:
            logger.warning({
                "event": "call_limited",
                "reason": "max_concurrent_reached",
                "active_calls": len(self._active_calls),
                "limit": self.MAX_CONCURRENT_CALLS,
            })
            return CallTaskResult(
                success=False,
                status=CallStatus.QUEUED,
                queued_reason=f"Max concurrent calls ({self.MAX_CONCURRENT_CALLS}) reached. Call queued.",
            )

        # Generate call ID
        call_id = f"call_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{phone_number[-4:]}"

        # Track active call
        self._active_calls[call_id] = datetime.now(timezone.utc)

        try:
            # Process through Mini Voice agent
            response = await self._agent.process({
                "call_id": call_id,
                "phone_number": phone_number,
                "reason": reason,
                "customer_id": customer_id,
                "priority": priority
            })

            # Build result
            result = CallTaskResult(
                success=response.success,
                call_id=call_id,
                status=CallStatus.COMPLETED if response.success else CallStatus.FAILED,
                confidence=response.confidence,
                escalated=response.escalated,
                escalation_reason=response.escalation_reason if response.escalated else None,
            )

            if response.success:
                data = response.data or {}
                result.duration_seconds = data.get("duration_seconds", 0.0)
                result.recording_url = data.get("recording_url")
                result.transcript = data.get("transcript")

            logger.info({
                "event": "call_task_completed",
                "call_id": call_id,
                "success": result.success,
                "duration": result.duration_seconds,
            })

            return result

        finally:
            # Remove from active calls
            if call_id in self._active_calls:
                del self._active_calls[call_id]

    def get_active_call_count(self) -> int:
        """Get current number of active calls."""
        return len(self._active_calls)

    def can_make_call(self) -> bool:
        """Check if a new call can be made."""
        return len(self._active_calls) < self.MAX_CONCURRENT_CALLS

    def get_task_name(self) -> str:
        """Get task name."""
        return "make_call"

    def get_variant(self) -> str:
        """Get variant name."""
        return "mini"

    def get_tier(self) -> str:
        """Get tier used."""
        return "light"
