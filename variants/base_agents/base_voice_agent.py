"""
PARWA Base Voice Agent.

Abstract base class for voice/call agents. Provides common functionality
for transcription, synthesis, and call management.
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


class BaseVoiceAgent(BaseAgent):
    """
    Abstract base class for voice/call agents.

    Provides:
    - Transcription (mocked)
    - Synthesis (mocked)
    - Call state management
    - Concurrent call tracking

    Subclasses must implement:
    - get_tier()
    - get_variant()
    - process()
    """

    DEFAULT_MAX_CONCURRENT_CALLS = 5

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Voice agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Optional configuration dictionary
            company_id: Company UUID for multi-tenancy
        """
        super().__init__(agent_id, config, company_id)
        self._active_calls: Dict[str, Dict[str, Any]] = {}
        self._call_count = 0
        self._max_concurrent = self.DEFAULT_MAX_CONCURRENT_CALLS

    @property
    def max_concurrent_calls(self) -> int:
        """Get maximum concurrent calls."""
        return self._max_concurrent

    @max_concurrent_calls.setter
    def max_concurrent_calls(self, value: int) -> None:
        """Set maximum concurrent calls."""
        self._max_concurrent = value

    async def transcribe(self, audio_url: str) -> str:
        """
        Transcribe audio to text.

        Note: This is mocked for testing. In production,
        this would use a speech-to-text service.

        Args:
            audio_url: URL to audio file

        Returns:
            Transcribed text
        """
        # Mock transcription
        logger.info({
            "event": "transcription_started",
            "agent_id": self._agent_id,
            "audio_url": audio_url,
        })

        # Return mock transcription
        return "This is a mock transcription of the audio content."

    async def synthesize(self, text: str) -> str:
        """
        Synthesize text to speech.

        Note: This is mocked for testing. In production,
        this would use a text-to-speech service.

        Args:
            text: Text to synthesize

        Returns:
            URL to synthesized audio
        """
        # Mock synthesis
        audio_id = f"AUDIO-{len(text)}-{datetime.now().timestamp():.0f}"

        logger.info({
            "event": "synthesis_completed",
            "agent_id": self._agent_id,
            "text_length": len(text),
            "audio_id": audio_id,
        })

        return f"https://mock-audio.example.com/{audio_id}.mp3"

    def can_accept_call(self) -> bool:
        """
        Check if agent can accept a new call.

        Returns:
            True if under concurrent call limit
        """
        return len(self._active_calls) < self._max_concurrent

    async def start_call(
        self,
        call_id: str,
        caller_number: str
    ) -> Dict[str, Any]:
        """
        Start a new call session.

        Args:
            call_id: Unique call identifier
            caller_number: Caller's phone number

        Returns:
            Call session data
        """
        if not self.can_accept_call():
            return {
                "status": "rejected",
                "reason": "max_concurrent_calls_reached",
                "active_calls": len(self._active_calls),
            }

        self._call_count += 1
        self._active_calls[call_id] = {
            "call_id": call_id,
            "caller_number": caller_number,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "messages": [],
        }

        logger.info({
            "event": "call_started",
            "agent_id": self._agent_id,
            "call_id": call_id,
            "active_calls": len(self._active_calls),
        })

        return {
            "status": "started",
            "call_id": call_id,
            "active_calls": len(self._active_calls),
        }

    async def end_call(self, call_id: str) -> Dict[str, Any]:
        """
        End a call session.

        Args:
            call_id: Call identifier

        Returns:
            Call summary
        """
        call = self._active_calls.pop(call_id, None)

        if not call:
            return {
                "status": "error",
                "message": f"Call {call_id} not found",
            }

        # Calculate duration
        started = datetime.fromisoformat(call["started_at"].replace("Z", "+00:00"))
        duration = (datetime.now(timezone.utc) - started).total_seconds()

        call["ended_at"] = datetime.now(timezone.utc).isoformat()
        call["duration_seconds"] = duration
        call["status"] = "ended"

        logger.info({
            "event": "call_ended",
            "agent_id": self._agent_id,
            "call_id": call_id,
            "duration_seconds": duration,
        })

        return call

    def get_active_call_count(self) -> int:
        """Get number of active calls."""
        return len(self._active_calls)

    def get_call_stats(self) -> Dict[str, Any]:
        """Get voice agent statistics."""
        return {
            "total_calls": self._call_count,
            "active_calls": len(self._active_calls),
            "max_concurrent": self._max_concurrent,
            "available_slots": self._max_concurrent - len(self._active_calls),
        }
