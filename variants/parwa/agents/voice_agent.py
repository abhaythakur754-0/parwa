"""
PARWA Junior Voice Agent.

PARWA Junior's voice agent handles voice/call processing with
support for up to 5 concurrent calls and medium tier support.
"""
from typing import Dict, Any, Optional
from uuid import UUID

from variants.base_agents.base_voice_agent import BaseVoiceAgent, AgentResponse
from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ParwaVoiceAgent(BaseVoiceAgent):
    """
    PARWA Junior Voice Agent.

    Handles voice/call processing with the following characteristics:
    - Routes to 'medium' tier for sophisticated responses
    - Supports up to 5 concurrent calls (vs 2 for Mini)
    - Escalates when confidence < 60%
    - Supports transcription and synthesis (mocked)
    """

    # PARWA Junior supports 5 concurrent calls
    PARWA_MAX_CONCURRENT_CALLS = 5

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        parwa_config: Optional[ParwaConfig] = None,
    ) -> None:
        """
        Initialize PARWA Junior Voice Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            parwa_config: Optional ParwaConfig instance
        """
        super().__init__(agent_id, config, company_id)
        self._parwa_config = parwa_config or get_parwa_config()
        # Set max concurrent calls to PARWA limit (5)
        self._max_concurrent = self.PARWA_MAX_CONCURRENT_CALLS

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA uses 'medium'."""
        return self._parwa_config.default_tier

    def get_variant(self) -> str:
        """Get the PARWA variant for this agent."""
        return "parwa"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process a voice call.

        Handles call initiation, transcription, and response synthesis.

        Args:
            input_data: Must contain 'action' key ('start_call', 'end_call', 'transcribe')

        Returns:
            AgentResponse with voice processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_voice_process", {
            "action": action,
            "tier": self.get_tier(),
            "max_concurrent": self._max_concurrent,
        })

        if action == "start_call":
            return await self._handle_start_call(input_data)
        elif action == "end_call":
            return await self._handle_end_call(input_data)
        elif action == "transcribe":
            return await self._handle_transcribe(input_data)
        elif action == "synthesize":
            return await self._handle_synthesize(input_data)
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def _handle_start_call(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle call start action."""
        call_id = input_data.get("call_id")
        caller_number = input_data.get("caller_number", "unknown")

        if not call_id:
            return AgentResponse(
                success=False,
                message="Missing required field: call_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Check if we can accept the call (5 concurrent max)
        if not self.can_accept_call():
            self.log_action("parwa_voice_call_rejected", {
                "call_id": call_id,
                "active_calls": self.get_active_call_count(),
                "max_concurrent": self._max_concurrent,
            })
            return AgentResponse(
                success=False,
                message=f"Maximum concurrent calls ({self._max_concurrent}) reached",
                data={
                    "active_calls": self.get_active_call_count(),
                    "max_concurrent": self._max_concurrent,
                },
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        # Start the call
        result = await self.start_call(call_id, caller_number)

        confidence = 0.9 if result["status"] == "started" else 0.3

        return AgentResponse(
            success=result["status"] == "started",
            message=f"Call {call_id} started successfully" if result["status"] == "started" else "Call rejected",
            data={
                "call_id": call_id,
                "active_calls": result.get("active_calls", 0),
                "max_concurrent": self._max_concurrent,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_end_call(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle call end action."""
        call_id = input_data.get("call_id")

        if not call_id:
            return AgentResponse(
                success=False,
                message="Missing required field: call_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.end_call(call_id)

        return AgentResponse(
            success=result["status"] == "ended",
            message=f"Call {call_id} ended" if result["status"] == "ended" else f"Call {call_id} not found",
            data=result,
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_transcribe(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle transcription action."""
        audio_url = input_data.get("audio_url")

        if not audio_url:
            return AgentResponse(
                success=False,
                message="Missing required field: audio_url",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        transcription = await self.transcribe(audio_url)

        confidence = 0.7  # Default confidence for transcription

        return AgentResponse(
            success=True,
            message="Audio transcribed successfully",
            data={
                "audio_url": audio_url,
                "transcription": transcription,
            },
            confidence=confidence,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_synthesize(
        self,
        input_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle synthesis action."""
        text = input_data.get("text")

        if not text:
            return AgentResponse(
                success=False,
                message="Missing required field: text",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        audio_url = await self.synthesize(text)

        return AgentResponse(
            success=True,
            message="Text synthesized successfully",
            data={
                "text": text,
                "audio_url": audio_url,
            },
            confidence=0.9,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def get_voice_stats(self) -> Dict[str, Any]:
        """Get voice agent statistics."""
        stats = self.get_call_stats()
        stats["variant"] = self.get_variant()
        stats["tier"] = self.get_tier()
        stats["parwa_max_concurrent"] = self.PARWA_MAX_CONCURRENT_CALLS
        return stats
