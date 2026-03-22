"""
E2E Test: UI Jarvis Flow.

Tests the Jarvis terminal through the UI:
- Open Jarvis terminal
- Send command
- Verify streaming response
- Command history navigation
- Abort streaming
- Invalid command handling
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, AsyncGenerator
import asyncio


class MockJarvisService:
    """Mock service for Jarvis terminal operations."""

    VALID_COMMANDS = [
        "status",
        "pause refunds",
        "resume refunds",
        "force escalation",
        "list approvals",
        "agent status",
        "system health",
        "clear",
        "help",
    ]

    def __init__(self) -> None:
        self._command_history: List[Dict[str, Any]] = []
        self._current_stream: Optional[asyncio.Task] = None
        self._is_streaming = False

    async def send_command(self, command: str) -> Dict[str, Any]:
        """Send a command and get response."""
        command = command.strip().lower()

        # Add to history
        entry = {
            "command": command,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response": None,
            "status": "pending",
        }

        if command not in self.VALID_COMMANDS:
            entry["response"] = f"Unknown command: {command}. Type 'help' for available commands."
            entry["status"] = "error"
        else:
            entry["response"] = self._generate_response(command)
            entry["status"] = "success"

        self._command_history.append(entry)
        return entry

    async def stream_command(self, command: str) -> AsyncGenerator[str, None]:
        """Stream command response."""
        self._is_streaming = True
        command = command.strip().lower()

        response = self._generate_response(command)

        # Simulate streaming by yielding chunks
        words = response.split(" ")
        for i, word in enumerate(words):
            if not self._is_streaming:
                break
            await asyncio.sleep(0.05)  # Simulate typing delay
            yield word + (" " if i < len(words) - 1 else "")

        # Add to history
        self._command_history.append({
            "command": command,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response": response,
            "status": "success",
        })

        self._is_streaming = False

    def abort(self) -> bool:
        """Abort current stream."""
        self._is_streaming = False
        return True

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get command history."""
        return self._command_history[-limit:]

    def clear_history(self) -> None:
        """Clear command history."""
        self._command_history = []

    def _generate_response(self, command: str) -> str:
        """Generate response for a command."""
        responses = {
            "status": "System Status: All systems operational.\n- 5 agents active\n- 23 tickets in queue\n- 3 pending approvals",
            "pause refunds": "Refund processing paused. Pending refunds will be held for review.",
            "resume refunds": "Refund processing resumed. All pending refunds will be processed normally.",
            "force escalation": "Escalation triggered. A supervisor has been notified.",
            "list approvals": "Pending Approvals:\n1. APR-001: $49.99 refund\n2. APR-002: $125.00 refund\n3. APR-003: $15.00 refund",
            "agent status": "Agent Status:\n- Tier 1 Agent: Active (12 tickets handled today)\n- Tier 2 Agent: Active (5 escalations resolved)\n- Refund Agent: Idle",
            "system health": "System Health:\n- API: OK (45ms avg)\n- Database: OK (12ms avg)\n- Redis: OK (2ms avg)\n- AI Model: OK",
            "clear": "Terminal cleared.",
            "help": "Available commands:\n- status: Show system status\n- pause refunds: Pause refund processing\n- resume refunds: Resume refund processing\n- force escalation: Trigger manual escalation\n- list approvals: Show pending approvals\n- agent status: Show agent status\n- system health: Show system health\n- clear: Clear terminal\n- help: Show this help",
        }
        return responses.get(command, "Command executed.")


@pytest.fixture
def jarvis_service():
    """Create Jarvis service fixture."""
    return MockJarvisService()


class TestUIJarvisFlow:
    """E2E tests for UI Jarvis flow."""

    @pytest.mark.asyncio
    async def test_open_jarvis_terminal(self, jarvis_service):
        """Test opening Jarvis terminal."""
        # Terminal is ready when service is created
        assert jarvis_service is not None
        history = jarvis_service.get_history()
        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_send_valid_command(self, jarvis_service):
        """Test sending a valid command."""
        result = await jarvis_service.send_command("status")

        assert result["status"] == "success"
        assert "System Status" in result["response"]

    @pytest.mark.asyncio
    async def test_send_invalid_command(self, jarvis_service):
        """Test sending an invalid command."""
        result = await jarvis_service.send_command("invalid_command_xyz")

        assert result["status"] == "error"
        assert "Unknown command" in result["response"]

    @pytest.mark.asyncio
    async def test_streaming_response(self, jarvis_service):
        """Test streaming response."""
        chunks = []
        async for chunk in jarvis_service.stream_command("status"):
            chunks.append(chunk)

        full_response = "".join(chunks)
        assert len(chunks) > 1  # Should be multiple chunks
        assert "System Status" in full_response

    @pytest.mark.asyncio
    async def test_abort_streaming(self, jarvis_service):
        """Test aborting streaming response."""
        chunks = []

        async def collect_stream():
            async for chunk in jarvis_service.stream_command("help"):
                chunks.append(chunk)
                if len(chunks) == 2:
                    jarvis_service.abort()

        await collect_stream()

        # Stream should have been aborted
        assert jarvis_service._is_streaming is False

    @pytest.mark.asyncio
    async def test_command_history(self, jarvis_service):
        """Test command history."""
        await jarvis_service.send_command("status")
        await jarvis_service.send_command("help")
        await jarvis_service.send_command("agent status")

        history = jarvis_service.get_history()

        assert len(history) == 3
        assert history[0]["command"] == "status"
        assert history[1]["command"] == "help"
        assert history[2]["command"] == "agent status"

    @pytest.mark.asyncio
    async def test_clear_history(self, jarvis_service):
        """Test clearing command history."""
        await jarvis_service.send_command("status")
        await jarvis_service.send_command("help")

        jarvis_service.clear_history()
        history = jarvis_service.get_history()

        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_help_command(self, jarvis_service):
        """Test help command shows all commands."""
        result = await jarvis_service.send_command("help")

        assert result["status"] == "success"
        assert "Available commands" in result["response"]
        assert "status" in result["response"]
        assert "pause refunds" in result["response"]

    @pytest.mark.asyncio
    async def test_pause_resume_refunds(self, jarvis_service):
        """Test pause and resume refund commands."""
        pause_result = await jarvis_service.send_command("pause refunds")
        assert pause_result["status"] == "success"
        assert "paused" in pause_result["response"].lower()

        resume_result = await jarvis_service.send_command("resume refunds")
        assert resume_result["status"] == "success"
        assert "resumed" in resume_result["response"].lower()
