"""
PARWA High Video Support Agent.

Handles video support sessions for PARWA High customers.
Provides video call management, screen sharing, and session recording.

PARWA High video features:
- Start/end video sessions
- Screen sharing capabilities
- Session recording (optional)
- Encrypted video streams
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class VideoSessionStatus(Enum):
    """Video session status types."""
    INITIATED = "initiated"
    ACTIVE = "active"
    SCREEN_SHARING = "screen_sharing"
    ENDED = "ended"
    FAILED = "failed"


@dataclass
class VideoSession:
    """Video session data."""
    session_id: str
    customer_id: str
    status: VideoSessionStatus = VideoSessionStatus.INITIATED
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: int = 0
    screen_share_enabled: bool = False
    recording_enabled: bool = False
    recording_url: Optional[str] = None


class ParwaHighVideoAgent(BaseAgent):
    """
    Video support agent for PARWA High variant.

    Provides video support capabilities including:
    - Starting video calls with customers
    - Screen sharing during sessions
    - Ending video sessions
    - Session recording management

    Example:
        agent = ParwaHighVideoAgent()
        result = await agent.start_video("sess_123", "cust_456")
    """

    # Maximum video duration in minutes
    MAX_VIDEO_DURATION_MINUTES = 60

    def __init__(
        self,
        agent_id: str = "parwa_high_video",
        parwa_high_config: Optional[ParwaHighConfig] = None
    ) -> None:
        """
        Initialize PARWA High video agent.

        Args:
            agent_id: Unique agent identifier
            parwa_high_config: PARWA High configuration
        """
        super().__init__(agent_id=agent_id)
        self._config = parwa_high_config or get_parwa_high_config()
        self._active_sessions: Dict[str, VideoSession] = {}

    async def start_video(
        self,
        session_id: str,
        customer_id: str,
        enable_recording: bool = False
    ) -> AgentResponse:
        """
        Start a video support session.

        Args:
            session_id: Unique session identifier
            customer_id: Customer identifier
            enable_recording: Whether to record the session

        Returns:
            AgentResponse with session details
        """
        logger.info({
            "event": "video_session_starting",
            "session_id": session_id,
            "customer_id": customer_id,
            "enable_recording": enable_recording,
            "variant": "parwa_high",
        })

        # Check if session already exists
        if session_id in self._active_sessions:
            existing = self._active_sessions[session_id]
            if existing.status == VideoSessionStatus.ACTIVE:
                return AgentResponse(
                    success=False,
                    message=f"Video session {session_id} is already active",
                    data={"session_id": session_id, "status": "already_active"},
                )

        # Create new session
        session = VideoSession(
            session_id=session_id,
            customer_id=customer_id,
            status=VideoSessionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            recording_enabled=enable_recording,
        )

        self._active_sessions[session_id] = session

        logger.info({
            "event": "video_session_started",
            "session_id": session_id,
            "customer_id": customer_id,
            "status": "active",
            "recording": enable_recording,
        })

        return AgentResponse(
            success=True,
            message=f"Video session {session_id} started successfully",
            confidence=0.95,
            data={
                "session_id": session_id,
                "customer_id": customer_id,
                "status": VideoSessionStatus.ACTIVE.value,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "recording_enabled": enable_recording,
                "max_duration_minutes": self.MAX_VIDEO_DURATION_MINUTES,
            },
        )

    async def share_screen(
        self,
        session_id: str,
        enabled: bool = True
    ) -> AgentResponse:
        """
        Enable or disable screen sharing for a session.

        Args:
            session_id: Session identifier
            enabled: True to enable, False to disable

        Returns:
            AgentResponse with screen share status
        """
        session = self._active_sessions.get(session_id)

        if not session:
            return AgentResponse(
                success=False,
                message=f"Video session {session_id} not found",
                data={"session_id": session_id, "error": "not_found"},
            )

        if session.status != VideoSessionStatus.ACTIVE:
            return AgentResponse(
                success=False,
                message=f"Video session {session_id} is not active",
                data={"session_id": session_id, "status": session.status.value},
            )

        # Update session
        session.screen_share_enabled = enabled
        session.status = VideoSessionStatus.SCREEN_SHARING if enabled else VideoSessionStatus.ACTIVE

        logger.info({
            "event": "screen_share_toggled",
            "session_id": session_id,
            "enabled": enabled,
        })

        return AgentResponse(
            success=True,
            message=f"Screen sharing {'enabled' if enabled else 'disabled'}",
            confidence=0.95,
            data={
                "session_id": session_id,
                "screen_share_enabled": enabled,
                "status": session.status.value,
            },
        )

    async def end_video(self, session_id: str) -> AgentResponse:
        """
        End a video support session.

        Args:
            session_id: Session identifier

        Returns:
            AgentResponse with session summary
        """
        session = self._active_sessions.get(session_id)

        if not session:
            return AgentResponse(
                success=False,
                message=f"Video session {session_id} not found",
                data={"session_id": session_id, "error": "not_found"},
            )

        # Calculate duration
        ended_at = datetime.now(timezone.utc)
        if session.started_at:
            duration = (ended_at - session.started_at).total_seconds()
            session.duration_seconds = int(duration)
        session.ended_at = ended_at
        session.status = VideoSessionStatus.ENDED

        logger.info({
            "event": "video_session_ended",
            "session_id": session_id,
            "duration_seconds": session.duration_seconds,
            "screen_share_enabled": session.screen_share_enabled,
            "recording_enabled": session.recording_enabled,
        })

        # Generate recording URL if recording was enabled
        recording_url = None
        if session.recording_enabled:
            recording_url = f"https://recordings.parwa.high/{session_id}.mp4"

        return AgentResponse(
            success=True,
            message=f"Video session {session_id} ended successfully",
            confidence=0.95,
            data={
                "session_id": session_id,
                "status": VideoSessionStatus.ENDED.value,
                "duration_seconds": session.duration_seconds,
                "duration_minutes": round(session.duration_seconds / 60, 2),
                "screen_share_enabled": session.screen_share_enabled,
                "recording_enabled": session.recording_enabled,
                "recording_url": recording_url,
                "ended_at": ended_at.isoformat(),
            },
        )

    def get_active_session_count(self) -> int:
        """Get count of active video sessions."""
        return sum(
            1 for s in self._active_sessions.values()
            if s.status in (VideoSessionStatus.ACTIVE, VideoSessionStatus.SCREEN_SHARING)
        )

    def get_session(self, session_id: str) -> Optional[VideoSession]:
        """Get a video session by ID."""
        return self._active_sessions.get(session_id)

    def get_tier(self) -> str:
        """Get the tier for this agent."""
        return "heavy"

    def get_variant(self) -> str:
        """Get the variant for this agent."""
        return "parwa_high"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process video-related request.

        Args:
            input_data: Must contain 'action' key with value:
                - 'start': Start video session
                - 'screen_share': Toggle screen sharing
                - 'end': End video session

        Returns:
            AgentResponse with result
        """
        action = input_data.get("action", "")

        if action == "start":
            return await self.start_video(
                session_id=input_data.get("session_id", ""),
                customer_id=input_data.get("customer_id", ""),
                enable_recording=input_data.get("enable_recording", False),
            )
        elif action == "screen_share":
            return await self.share_screen(
                session_id=input_data.get("session_id", ""),
                enabled=input_data.get("enabled", True),
            )
        elif action == "end":
            return await self.end_video(
                session_id=input_data.get("session_id", ""),
            )
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown video action: {action}",
                data={"action": action, "valid_actions": ["start", "screen_share", "end"]},
            )
