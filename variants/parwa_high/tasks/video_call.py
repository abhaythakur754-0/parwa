"""
PARWA High Video Call Task.

Task for managing video support sessions in PARWA High.
Provides video call management including start, screen share, and end actions.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from variants.parwa_high.agents.video_agent import ParwaHighVideoAgent
from variants.parwa_high.config import ParwaHighConfig, get_parwa_high_config
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class VideoCallStatus(Enum):
    """Video call status types."""
    STARTED = "started"
    SCREEN_SHARING = "screen_sharing"
    ENDED = "ended"
    FAILED = "failed"


@dataclass
class VideoCallResult:
    """Result from video call task execution."""
    success: bool
    session_id: Optional[str] = None
    status: VideoCallStatus = VideoCallStatus.FAILED
    duration_seconds: int = 0
    message: str = ""
    recording_url: Optional[str] = None


class VideoCallTask:
    """
    Task for managing video support sessions.

    Uses ParwaHighVideoAgent to handle video call operations:
    - start: Start a new video session
    - share_screen: Enable/disable screen sharing
    - end: End video session and get summary

    Example:
        task = VideoCallTask()
        result = await task.execute({
            "action": "start",
            "session_id": "sess_123",
            "customer_id": "cust_456"
        })
    """

    def __init__(
        self,
        parwa_high_config: Optional[ParwaHighConfig] = None,
        agent_id: str = "video_call_task"
    ) -> None:
        """
        Initialize video call task.

        Args:
            parwa_high_config: PARWA High configuration
            agent_id: Agent identifier
        """
        self._config = parwa_high_config or get_parwa_high_config()
        self._agent = ParwaHighVideoAgent(agent_id=agent_id)

    async def execute(
        self,
        session_id: str,
        customer_id: str,
        action: str,
        **kwargs
    ) -> VideoCallResult:
        """
        Execute video call action.

        Args:
            session_id: Video session identifier
            customer_id: Customer identifier
            action: Action to perform (start, share_screen, end)
            **kwargs: Additional parameters

        Returns:
            VideoCallResult with action result
        """
        logger.info({
            "event": "video_call_task_started",
            "session_id": session_id,
            "customer_id": customer_id,
            "action": action,
            "variant": "parwa_high",
        })

        if action == "start":
            enable_recording = kwargs.get("enable_recording", False)
            response = await self._agent.start_video(
                session_id=session_id,
                customer_id=customer_id,
                enable_recording=enable_recording,
            )

            if response.success:
                return VideoCallResult(
                    success=True,
                    session_id=session_id,
                    status=VideoCallStatus.STARTED,
                    message=response.message,
                )
            return VideoCallResult(
                success=False,
                session_id=session_id,
                status=VideoCallStatus.FAILED,
                message=response.message,
            )

        elif action == "share_screen":
            enabled = kwargs.get("enabled", True)
            response = await self._agent.share_screen(
                session_id=session_id,
                enabled=enabled,
            )

            if response.success:
                return VideoCallResult(
                    success=True,
                    session_id=session_id,
                    status=VideoCallStatus.SCREEN_SHARING,
                    message=response.message,
                )
            return VideoCallResult(
                success=False,
                session_id=session_id,
                status=VideoCallStatus.FAILED,
                message=response.message,
            )

        elif action == "end":
            response = await self._agent.end_video(session_id=session_id)

            if response.success:
                data = response.data or {}
                return VideoCallResult(
                    success=True,
                    session_id=session_id,
                    status=VideoCallStatus.ENDED,
                    duration_seconds=data.get("duration_seconds", 0),
                    message=response.message,
                    recording_url=data.get("recording_url"),
                )
            return VideoCallResult(
                success=False,
                session_id=session_id,
                status=VideoCallStatus.FAILED,
                message=response.message,
            )

        else:
            return VideoCallResult(
                success=False,
                session_id=session_id,
                status=VideoCallStatus.FAILED,
                message=f"Unknown action: {action}",
            )

    def get_task_name(self) -> str:
        """Get task name."""
        return "video_call"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa_high"

    def get_tier(self) -> str:
        """Get tier used."""
        return "heavy"
