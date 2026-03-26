"""
PARWA Mini Voice Agent.

Mini PARWA's voice agent handles voice calls with limited concurrency.
Maximum 2 concurrent calls enforced for the entry-level variant.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_voice_agent import BaseVoiceAgent, AgentResponse
from variants.mini.config import MiniConfig, get_mini_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class MiniVoiceAgent(BaseVoiceAgent):
    """
    Mini PARWA Voice Agent.

    Handles voice calls with the following characteristics:
    - Maximum 2 concurrent calls (Mini limit)
    - Always routes to 'light' tier
    - Escalates when confidence < 70%
    - Rejects calls when at capacity
    """

    # Mini supports max 2 concurrent calls
    MINI_MAX_CONCURRENT_CALLS = 2

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        mini_config: Optional[MiniConfig] = None,
    ) -> None:
        """
        Initialize Mini Voice Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            mini_config: Optional MiniConfig instance
        """
        super().__init__(agent_id, config, company_id)
        self._mini_config = mini_config or get_mini_config()
        # Override base class default with Mini limit
        self._max_concurrent = self.MINI_MAX_CONCURRENT_CALLS

    def get_tier(self) -> str:
        """Get the AI tier for this agent. Mini always uses 'light'."""
        return "light"

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "mini"

    def can_accept_call(self) -> bool:
        """
        Check if agent can accept a new call.

        Mini is limited to 2 concurrent calls maximum.

        Returns:
            True if under concurrent call limit (2 for Mini)
        """
        return len(self._active_calls) < self.MINI_MAX_CONCURRENT_CALLS

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a voice call request.

        Args:
            input_data: Must contain 'audio_url' or 'call_id'

        Returns:
            AgentResponse with call handling result
        """
        # Check for call management
        call_id = input_data.get("call_id")
        action = input_data.get("action", "process")

        # Handle call start/end actions
        if action == "start_call":
            return await self._handle_start_call(input_data)
        elif action == "end_call":
            return await self._handle_end_call(input_data)

        # Validate input for processing
        audio_url = input_data.get("audio_url")
        if not audio_url:
            return AgentResponse(
                success=False,
                message="Missing required field: audio_url",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("mini_voice_process", {
            "audio_url": audio_url,
            "tier": self.get_tier(),
            "active_calls": len(self._active_calls),
        })

        # Transcribe audio (mocked)
        transcription = await self.transcribe(audio_url)

        # Calculate confidence based on transcription quality
        confidence = self._calculate_confidence(transcription)

        # Check if should escalate
        escalated = self.should_escalate(confidence, input_data)

        # Synthesize response (mocked)
        response_text = self._generate_response(transcription, escalated)
        audio_response = await self.synthesize(response_text)

        return AgentResponse(
            success=True,
            message="Voice call processed successfully",
            data={
                "transcription": transcription,
                "response_text": response_text,
                "audio_response_url": audio_response,
                "active_calls": len(self._active_calls),
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
            escalated=escalated,
        )

    async def _handle_start_call(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle call start request."""
        call_id = input_data.get("call_id")
        caller_number = input_data.get("caller_number", "unknown")

        if not call_id:
            return AgentResponse(
                success=False,
                message="Missing required field: call_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        if not self.can_accept_call():
            self.log_action("mini_voice_rejected", {
                "reason": "max_concurrent_calls_reached",
                "active_calls": len(self._active_calls),
                "max_allowed": self.MINI_MAX_CONCURRENT_CALLS,
            })
            return AgentResponse(
                success=False,
                message="Maximum concurrent calls reached (Mini limit: 2)",
                data={
                    "active_calls": len(self._active_calls),
                    "max_allowed": self.MINI_MAX_CONCURRENT_CALLS,
                },
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.start_call(call_id, caller_number)

        return AgentResponse(
            success=True,
            message="Call started",
            data=result,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_end_call(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle call end request."""
        call_id = input_data.get("call_id")

        if not call_id:
            return AgentResponse(
                success=False,
                message="Missing required field: call_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.end_call(call_id)

        if "error" in result.get("status", ""):
            return AgentResponse(
                success=False,
                message=result.get("message", "Call not found"),
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        return AgentResponse(
            success=True,
            message="Call ended",
            data=result,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def _calculate_confidence(self, transcription: str) -> float:
        """Calculate confidence based on transcription."""
        # Mock confidence calculation
        if not transcription or len(transcription) < 10:
            return 0.4
        elif "unclear" in transcription.lower():
            return 0.5
        else:
            return 0.85

    def _generate_response(self, transcription: str, escalated: bool) -> str:
        """Generate response text based on transcription."""
        if escalated:
            return ("I'm having difficulty understanding your request. "
                    "Let me connect you with a human agent who can better assist you.")
        return f"Thank you for your message. I've noted: {transcription[:50]}..."

    def should_escalate(
        self,
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if escalation is needed.

        Uses Mini config's escalation threshold (default 70%).

        Args:
            confidence: Confidence score (0.0-1.0)
            context: Optional additional context

        Returns:
            True if confidence < escalation threshold
        """
        return confidence < self._mini_config.escalation_threshold

    def get_voice_stats(self) -> Dict[str, Any]:
        """Get voice agent statistics including Mini-specific limits."""
        stats = self.get_call_stats()
        stats["mini_limit"] = self.MINI_MAX_CONCURRENT_CALLS
        stats["variant"] = self.get_variant()
        return stats
