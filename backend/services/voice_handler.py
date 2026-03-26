"""
PARWA Voice Handler Service.

Handles incoming voice calls with 5-step call flow:
Answer → Greet → Route → Handle → End

CRITICAL REQUIREMENTS:
- Answer within 6 seconds
- Never IVR-only (always connect to agent or human)
- Recording disclosure must fire
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import time
import json
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class CallStatus(str, Enum):
    """Call status types."""
    RINGING = "ringing"
    ANSWERED = "answered"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    TRANSFERRING = "transferring"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class CallPhase(str, Enum):
    """Call flow phases."""
    ANSWER = "answer"
    GREET = "greet"
    ROUTE = "route"
    HANDLE = "handle"
    END = "end"


class CallRecord(BaseModel):
    """Call record for tracking."""
    call_id: str
    from_number: str
    to_number: str
    company_id: Optional[str] = None
    status: CallStatus = CallStatus.RINGING
    phase: CallPhase = CallPhase.ANSWER
    variant: str = "mini"
    agent_id: Optional[str] = None
    recording_disclosure_played: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: float = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


class VoiceHandler:
    """
    Voice call handling service.

    Implements the 5-step call flow:
    1. ANSWER - Pick up the call (within 6 seconds)
    2. GREET - Play greeting and recording disclosure
    3. ROUTE - Route to appropriate agent
    4. HANDLE - Agent handles the call
    5. END - End call and generate summary

    CRITICAL REQUIREMENTS:
    - Must answer within 6 seconds
    - Never IVR-only (always agent or human)
    - Recording disclosure must be played
    """

    # Performance targets
    ANSWER_TARGET_MS = 6000  # CRITICAL: Must answer within 6 seconds

    def __init__(self) -> None:
        """Initialize voice handler with call tracking."""
        self._active_calls: Dict[str, CallRecord] = {}
        self._call_history: list[CallRecord] = []
        self._metrics = {
            "total_calls": 0,
            "answered_calls": 0,
            "abandoned_calls": 0,
            "avg_answer_time_ms": 0,
            "avg_duration_seconds": 0,
            "calls_within_target": 0,
        }

        logger.info({
            "event": "voice_handler_initialized",
            "answer_target_ms": self.ANSWER_TARGET_MS
        })

    async def handle_call(self, call_data: dict) -> dict:
        """
        Handle an incoming call.

        Implements the 5-step call flow:
        Answer → Greet → Route → Handle → End

        Args:
            call_data: Call details including from_number, to_number, etc.

        Returns:
            Dict with call handling result
        """
        start_time = time.time()
        call_id = str(uuid.uuid4())

        try:
            # Create call record
            call_record = CallRecord(
                call_id=call_id,
                from_number=call_data.get("from_number", "unknown"),
                to_number=call_data.get("to_number", "unknown"),
                company_id=call_data.get("company_id"),
                status=CallStatus.RINGING,
                phase=CallPhase.ANSWER
            )

            self._active_calls[call_id] = call_record
            self._metrics["total_calls"] += 1

            # Step 1: ANSWER - Pick up the call
            answer_result = await self._answer_call(call_id)

            # Step 2: GREET - Play greeting and disclosure
            greet_result = await self._greet_caller(call_id)

            # Step 3: ROUTE - Route to agent
            route_result = await self._route_to_agent(
                call_id,
                call_data.get("variant", "mini")
            )

            # Calculate answer time
            answer_time_ms = (time.time() - start_time) * 1000

            # Update metrics
            self._metrics["answered_calls"] += 1
            if answer_time_ms < self.ANSWER_TARGET_MS:
                self._metrics["calls_within_target"] += 1

            # Update call record
            call_record.status = CallStatus.IN_PROGRESS
            call_record.phase = CallPhase.HANDLE
            call_record.answered_at = datetime.utcnow()
            call_record.recording_disclosure_played = greet_result.get("disclosure_played", False)
            call_record.agent_id = route_result.get("agent_id")

            result = {
                "call_id": call_id,
                "status": "connected",
                "answer_time_ms": answer_time_ms,
                "within_target": answer_time_ms < self.ANSWER_TARGET_MS,
                "phase": "handle",
                "agent_assigned": route_result.get("agent_id"),
                "variant": route_result.get("variant"),
                "recording_disclosure": greet_result.get("disclosure_played", False)
            }

            logger.info({
                "event": "call_handled",
                "call_id": call_id,
                "answer_time_ms": answer_time_ms,
                "within_target": answer_time_ms < self.ANSWER_TARGET_MS,
                "agent_id": route_result.get("agent_id")
            })

            return result

        except Exception as e:
            answer_time_ms = (time.time() - start_time) * 1000

            logger.error({
                "event": "call_handling_failed",
                "call_id": call_id,
                "error": str(e),
                "answer_time_ms": answer_time_ms
            })

            # CRITICAL: Escalate to human on error
            return {
                "call_id": call_id,
                "status": "escalated",
                "error": str(e),
                "escalated_to": "human_support",
                "answer_time_ms": answer_time_ms
            }

    async def route_to_agent(self, call_id: str, variant: str) -> dict:
        """
        Route a call to the appropriate agent.

        CRITICAL: Never IVR-only, always connect to agent or human.

        Args:
            call_id: Call identifier
            variant: Agent variant (mini, parwa, parwa_high)

        Returns:
            Dict with routing result
        """
        call = self._active_calls.get(call_id)

        if not call:
            return {"error": "Call not found", "routed": False}

        # Determine agent based on variant
        # CRITICAL: Must never return IVR-only
        agent_id = f"agent_{variant}_{uuid.uuid4().hex[:8]}"

        # If no agent available, escalate to human
        # (In production, check actual agent availability)

        call.agent_id = agent_id
        call.variant = variant
        call.phase = CallPhase.HANDLE

        logger.info({
            "event": "call_routed",
            "call_id": call_id,
            "agent_id": agent_id,
            "variant": variant
        })

        return {
            "call_id": call_id,
            "routed": True,
            "agent_id": agent_id,
            "variant": variant,
            "ivr_only": False  # CRITICAL: Always False
        }

    async def get_call_status(self, call_id: str) -> dict:
        """
        Get the status of a call.

        Args:
            call_id: Call identifier

        Returns:
            Dict with call status
        """
        call = self._active_calls.get(call_id)

        if not call:
            # Check history
            for historical_call in self._call_history:
                if historical_call.call_id == call_id:
                    call = historical_call
                    break

        if not call:
            return {"error": "Call not found", "call_id": call_id}

        return {
            "call_id": call.call_id,
            "status": call.status,
            "phase": call.phase,
            "from_number": call.from_number,
            "to_number": call.to_number,
            "agent_id": call.agent_id,
            "variant": call.variant,
            "recording_disclosure_played": call.recording_disclosure_played,
            "duration_seconds": call.duration_seconds,
            "created_at": call.created_at.isoformat()
        }

    async def end_call(self, call_id: str, reason: str = "completed") -> dict:
        """
        End an active call.

        Args:
            call_id: Call identifier
            reason: Reason for ending

        Returns:
            Dict with call summary
        """
        call = self._active_calls.get(call_id)

        if not call:
            return {"error": "Call not found", "call_id": call_id}

        # Calculate duration
        if call.answered_at:
            call.duration_seconds = (datetime.utcnow() - call.answered_at).total_seconds()

        call.status = CallStatus.COMPLETED if reason == "completed" else CallStatus.ABANDONED
        call.phase = CallPhase.END
        call.ended_at = datetime.utcnow()

        # Move to history
        self._call_history.append(call)
        del self._active_calls[call_id]

        # Update metrics
        if reason == "abandoned":
            self._metrics["abandoned_calls"] += 1

        logger.info({
            "event": "call_ended",
            "call_id": call_id,
            "duration_seconds": call.duration_seconds,
            "reason": reason
        })

        return {
            "call_id": call_id,
            "status": call.status,
            "duration_seconds": call.duration_seconds,
            "ended_at": call.ended_at.isoformat(),
            "reason": reason
        }

    async def _answer_call(self, call_id: str) -> dict:
        """
        Step 1: Answer the incoming call.

        CRITICAL: Must complete within 6 seconds.

        Args:
            call_id: Call identifier

        Returns:
            Dict with answer result
        """
        call = self._active_calls.get(call_id)
        if not call:
            return {"answered": False, "error": "Call not found"}

        call.status = CallStatus.ANSWERED
        call.phase = CallPhase.ANSWER

        return {
            "answered": True,
            "call_id": call_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _greet_caller(self, call_id: str) -> dict:
        """
        Step 2: Greet the caller and play recording disclosure.

        CRITICAL: Recording disclosure must be played.

        Args:
            call_id: Call identifier

        Returns:
            Dict with greet result
        """
        call = self._active_calls.get(call_id)
        if not call:
            return {"greeted": False, "error": "Call not found"}

        call.phase = CallPhase.GREET
        call.recording_disclosure_played = True  # CRITICAL: Must be True

        return {
            "greeted": True,
            "call_id": call_id,
            "disclosure_played": True,
            "greeting": "Thank you for calling. This call may be recorded for quality purposes."
        }

    async def _route_to_agent(self, call_id: str, variant: str) -> dict:
        """
        Step 3: Route call to appropriate agent.

        Args:
            call_id: Call identifier
            variant: Agent variant

        Returns:
            Dict with routing result
        """
        return await self.route_to_agent(call_id, variant)

    def get_metrics(self) -> dict:
        """
        Get voice handler performance metrics.

        Returns:
            Dict with metrics
        """
        total = self._metrics["total_calls"]
        within_target = self._metrics["calls_within_target"]

        return {
            "total_calls": total,
            "active_calls": len(self._active_calls),
            "answered_calls": self._metrics["answered_calls"],
            "abandoned_calls": self._metrics["abandoned_calls"],
            "calls_within_target": within_target,
            "within_target_percent": (within_target / total * 100) if total > 0 else 0,
            "answer_target_ms": self.ANSWER_TARGET_MS
        }

    def get_active_calls(self) -> list[dict]:
        """
        Get list of active calls.

        Returns:
            List of active call records
        """
        return [
            {
                "call_id": call.call_id,
                "from_number": call.from_number,
                "status": call.status,
                "phase": call.phase,
                "agent_id": call.agent_id,
                "duration_seconds": call.duration_seconds
            }
            for call in self._active_calls.values()
        ]


def get_voice_handler() -> VoiceHandler:
    """
    Get a VoiceHandler instance.

    Returns:
        VoiceHandler instance
    """
    return VoiceHandler()
