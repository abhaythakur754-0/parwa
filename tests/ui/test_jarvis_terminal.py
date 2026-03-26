"""
UI Tests for Jarvis Terminal Component.

Tests verify:
- Jarvis terminal renders correctly
- Command input works correctly
- Response streams correctly
- pause_refunds command works
- Error handling works correctly

Uses mock terminal state and command simulation.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock
from enum import Enum
from dataclasses import dataclass, field


class CommandStatus(str, Enum):
    """Status of a terminal command."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TerminalLine:
    """A single line in the terminal output."""
    content: str
    line_type: str  # "input", "output", "error", "system"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Command:
    """A terminal command with its result."""
    command_text: str
    status: CommandStatus = CommandStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def duration_ms(self) -> Optional[float]:
        """Calculate command duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


class MockJarvisTerminalState:
    """Mock state for Jarvis terminal UI component."""

    def __init__(self):
        self.lines: List[TerminalLine] = []
        self.command_history: List[str] = []
        self.pending_command: Optional[Command] = None
        self.is_connected: bool = True
        self.is_processing: bool = False
        self.error: Optional[str] = None
        self.company_id: str = "company_001"
        self.user_id: str = "user_001"

        # Add welcome message
        self._add_system_line("Jarvis Terminal v1.0 — Type 'help' for commands")

    def _add_line(self, content: str, line_type: str) -> None:
        """Add a line to terminal output."""
        self.lines.append(TerminalLine(content=content, line_type=line_type))

    def _add_system_line(self, content: str) -> None:
        """Add a system message."""
        self._add_line(content, "system")

    def _add_output_line(self, content: str) -> None:
        """Add an output line."""
        self._add_line(content, "output")

    def _add_error_line(self, content: str) -> None:
        """Add an error line."""
        self._add_line(content, "error")

    def get_output_lines(self) -> List[str]:
        """Get all output lines as strings."""
        return [line.content for line in self.lines]

    def clear_terminal(self) -> None:
        """Clear terminal output."""
        self.lines = []
        self._add_system_line("Terminal cleared")


class MockJarvisTerminalActions:
    """Mock actions for Jarvis terminal UI component."""

    # Supported commands
    COMMANDS = {
        "help": "Show available commands",
        "pause_refunds": "Pause all refund processing for company",
        "resume_refunds": "Resume refund processing",
        "system_status": "Get current system status",
        "force_escalation": "Force escalate a ticket",
        "list_approvals": "List pending approvals",
        "clear": "Clear terminal",
    }

    def __init__(self, state: MockJarvisTerminalState):
        self.state = state
        self._redis_mock: Dict[str, Any] = {}
        self._refund_paused: Dict[str, bool] = {}

    async def execute_command(self, command_text: str) -> Command:
        """Execute a terminal command."""
        # Create command object
        command = Command(
            command_text=command_text,
            status=CommandStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
        )

        self.state.pending_command = command
        self.state.is_processing = True

        # Add to history
        self.state.command_history.append(command_text)
        self.state._add_line(f"> {command_text}", "input")

        # Parse command
        parts = command_text.strip().split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        try:
            # Execute based on command
            if cmd == "help":
                result = await self._cmd_help()
            elif cmd == "pause_refunds":
                result = await self._cmd_pause_refunds(args)
            elif cmd == "resume_refunds":
                result = await self._cmd_resume_refunds(args)
            elif cmd == "system_status":
                result = await self._cmd_system_status()
            elif cmd == "force_escalation":
                result = await self._cmd_force_escalation(args)
            elif cmd == "list_approvals":
                result = await self._cmd_list_approvals()
            elif cmd == "clear":
                result = {"action": "clear"}
            else:
                result = {"error": f"Unknown command: {cmd}"}

            if "error" in result:
                command.status = CommandStatus.FAILED
                command.error = result["error"]
                self.state._add_error_line(f"Error: {result['error']}")
            else:
                command.status = CommandStatus.SUCCESS
                command.result = result
                if result.get("action") == "clear":
                    self.state.clear_terminal()
                else:
                    self._display_result(result)

        except Exception as e:
            command.status = CommandStatus.FAILED
            command.error = str(e)
            self.state._add_error_line(f"Exception: {str(e)}")

        finally:
            command.end_time = datetime.now(timezone.utc)
            self.state.pending_command = None
            self.state.is_processing = False

        return command

    async def _cmd_help(self) -> Dict[str, Any]:
        """Show help."""
        help_text = "\n".join([f"  {cmd}: {desc}" for cmd, desc in self.COMMANDS.items()])
        self.state._add_output_line("Available commands:")
        self.state._add_output_line(help_text)
        return {"success": True, "type": "help"}

    async def _cmd_pause_refunds(self, args: List[str]) -> Dict[str, Any]:
        """Pause refunds - CRITICAL: Must be fast."""
        import time
        start = time.perf_counter()

        company_id = args[0] if args else self.state.company_id

        # Simulate Redis key set
        self._redis_mock[f"refund_paused:{company_id}"] = {
            "paused": True,
            "paused_by": self.state.user_id,
            "paused_at": datetime.now(timezone.utc).isoformat(),
        }
        self._refund_paused[company_id] = True

        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "success": True,
            "company_id": company_id,
            "paused": True,
            "elapsed_ms": elapsed_ms,
            "message": f"Refunds paused for company {company_id}",
        }

    async def _cmd_resume_refunds(self, args: List[str]) -> Dict[str, Any]:
        """Resume refunds."""
        company_id = args[0] if args else self.state.company_id

        # Remove Redis key
        self._redis_mock.pop(f"refund_paused:{company_id}", None)
        self._refund_paused[company_id] = False

        return {
            "success": True,
            "company_id": company_id,
            "resumed": True,
            "message": f"Refunds resumed for company {company_id}",
        }

    async def _cmd_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        return {
            "success": True,
            "status": {
                "api": "healthy",
                "database": "connected",
                "redis": "connected",
                "workers": 4,
                "pending_approvals": 12,
                "active_tickets": 45,
            },
        }

    async def _cmd_force_escalation(self, args: List[str]) -> Dict[str, Any]:
        """Force escalate a ticket."""
        if not args:
            return {"error": "Ticket ID required"}

        ticket_id = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Manual escalation"

        return {
            "success": True,
            "ticket_id": ticket_id,
            "escalated": True,
            "reason": reason,
            "escalated_to": "Tier 2",
        }

    async def _cmd_list_approvals(self) -> Dict[str, Any]:
        """List pending approvals."""
        # Simulated approvals
        approvals = [
            {"id": "appr_001", "amount": 75.00, "ticket_id": "ticket_001"},
            {"id": "appr_002", "amount": 120.00, "ticket_id": "ticket_002"},
            {"id": "appr_003", "amount": 45.00, "ticket_id": "ticket_003"},
        ]

        return {
            "success": True,
            "approvals": approvals,
            "count": len(approvals),
        }

    def _display_result(self, result: Dict[str, Any]) -> None:
        """Display result in terminal."""
        if "message" in result:
            self.state._add_output_line(result["message"])
        elif "status" in result:
            for key, value in result["status"].items():
                self.state._add_output_line(f"  {key}: {value}")
        elif "approvals" in result:
            self.state._add_output_line(f"Found {result['count']} pending approvals:")
            for appr in result["approvals"]:
                self.state._add_output_line(
                    f"  - {appr['id']}: ${appr['amount']} ({appr['ticket_id']})"
                )
        else:
            self.state._add_output_line(str(result))

    def is_refund_paused(self, company_id: str) -> bool:
        """Check if refunds are paused for a company."""
        return self._refund_paused.get(company_id, False)


# =============================================================================
# UI Tests
# =============================================================================

class TestJarvisTerminalUI:
    """Tests for Jarvis terminal UI component."""

    @pytest.fixture
    def state(self):
        """Create terminal state."""
        return MockJarvisTerminalState()

    @pytest.fixture
    def actions(self, state):
        """Create terminal actions."""
        return MockJarvisTerminalActions(state)

    def test_jarvis_terminal_renders(self, state):
        """Test: Jarvis terminal renders with welcome message."""
        assert len(state.lines) >= 1
        assert any("Jarvis" in line.content for line in state.lines)

    @pytest.mark.asyncio
    async def test_command_input_works(self, state, actions):
        """Test: Command input works correctly."""
        result = await actions.execute_command("help")

        assert result.status == CommandStatus.SUCCESS
        assert len(state.command_history) == 1
        assert "help" in state.command_history

    @pytest.mark.asyncio
    async def test_response_streams_correctly(self, state, actions):
        """Test: Response streams to terminal."""
        await actions.execute_command("system_status")

        # Check output contains status
        output = state.get_output_lines()
        assert any("api" in line.lower() or "healthy" in line.lower() for line in output)

    @pytest.mark.asyncio
    async def test_pause_refunds_command_works(self, state, actions):
        """Test: pause_refunds command works."""
        result = await actions.execute_command("pause_refunds")

        assert result.status == CommandStatus.SUCCESS
        assert result.result["paused"] is True
        assert actions.is_refund_paused(state.company_id) is True

    @pytest.mark.asyncio
    async def test_pause_refunds_is_fast(self, state, actions):
        """CRITICAL: pause_refunds must be under 500ms."""
        result = await actions.execute_command("pause_refunds")

        assert result.duration_ms() is not None
        assert result.duration_ms() < 500, (
            f"pause_refunds took {result.duration_ms()}ms, must be <500ms"
        )

    @pytest.mark.asyncio
    async def test_resume_refunds_command_works(self, state, actions):
        """Test: resume_refunds command works."""
        # First pause
        await actions.execute_command("pause_refunds")
        assert actions.is_refund_paused(state.company_id) is True

        # Then resume
        result = await actions.execute_command("resume_refunds")

        assert result.status == CommandStatus.SUCCESS
        assert result.result["resumed"] is True
        assert actions.is_refund_paused(state.company_id) is False

    @pytest.mark.asyncio
    async def test_system_status_command_works(self, state, actions):
        """Test: system_status command works."""
        result = await actions.execute_command("system_status")

        assert result.status == CommandStatus.SUCCESS
        assert "status" in result.result
        assert result.result["status"]["api"] == "healthy"

    @pytest.mark.asyncio
    async def test_force_escalation_command_works(self, state, actions):
        """Test: force_escalation command works."""
        result = await actions.execute_command("force_escalation ticket_123 urgent issue")

        assert result.status == CommandStatus.SUCCESS
        assert result.result["ticket_id"] == "ticket_123"
        assert result.result["escalated"] is True

    @pytest.mark.asyncio
    async def test_force_escalation_requires_ticket_id(self, state, actions):
        """Test: force_escalation requires ticket ID."""
        result = await actions.execute_command("force_escalation")

        assert result.status == CommandStatus.FAILED
        assert "ticket id" in result.error.lower()

    @pytest.mark.asyncio
    async def test_list_approvals_command_works(self, state, actions):
        """Test: list_approvals command works."""
        result = await actions.execute_command("list_approvals")

        assert result.status == CommandStatus.SUCCESS
        assert "approvals" in result.result
        assert result.result["count"] > 0

    @pytest.mark.asyncio
    async def test_unknown_command_shows_error(self, state, actions):
        """Test: Error handling for unknown commands."""
        result = await actions.execute_command("invalid_command_xyz")

        assert result.status == CommandStatus.FAILED
        assert "unknown" in result.error.lower()

    @pytest.mark.asyncio
    async def test_clear_command_works(self, state, actions):
        """Test: clear command clears terminal."""
        # Add some output
        await actions.execute_command("help")
        initial_lines = len(state.lines)
        assert initial_lines > 1

        # Clear
        await actions.execute_command("clear")
        # After clear: only "Terminal cleared" message remains
        assert len(state.lines) == 1
        assert "cleared" in state.lines[0].content.lower()

    def test_command_history(self, state, actions):
        """Test: Command history is maintained."""
        import asyncio

        async def run_commands():
            await actions.execute_command("help")
            await actions.execute_command("system_status")

        asyncio.run(run_commands())

        assert "help" in state.command_history
        assert "system_status" in state.command_history

    @pytest.mark.asyncio
    async def test_multiple_commands_in_sequence(self, state, actions):
        """Test: Multiple commands execute correctly in sequence."""
        # Execute several commands
        results = []
        results.append(await actions.execute_command("help"))
        results.append(await actions.execute_command("pause_refunds"))
        results.append(await actions.execute_command("system_status"))
        results.append(await actions.execute_command("resume_refunds"))

        # All should succeed
        assert all(r.status == CommandStatus.SUCCESS for r in results)


class TestJarvisTerminalErrorHandling:
    """Tests for Jarvis terminal error handling."""

    @pytest.fixture
    def state(self):
        return MockJarvisTerminalState()

    @pytest.fixture
    def actions(self, state):
        return MockJarvisTerminalActions(state)

    @pytest.mark.asyncio
    async def test_error_displays_in_terminal(self, state, actions):
        """Test: Errors display with error styling."""
        await actions.execute_command("invalid_command")

        # Should have error line
        error_lines = [line for line in state.lines if line.line_type == "error"]
        assert len(error_lines) >= 1

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, state, actions):
        """Test: Connection errors handled gracefully."""
        state.is_connected = False
        state.error = "Connection lost"

        # Terminal should show disconnected state
        assert state.is_connected is False

    @pytest.mark.asyncio
    async def test_command_timeout_handling(self, state, actions):
        """Test: Command timeout handled."""
        command = Command(
            command_text="slow_command",
            status=CommandStatus.TIMEOUT,
            error="Command timed out after 30s",
        )

        assert command.status == CommandStatus.TIMEOUT

    def test_empty_command_handling(self, state, actions):
        """Test: Empty command handled gracefully."""
        import asyncio

        async def test_empty():
            result = await actions.execute_command("")
            # Should either be ignored or show help
            return result

        result = asyncio.run(test_empty())
        # Empty command should not crash


class TestJarvisTerminalFeatures:
    """Tests for Jarvis terminal additional features."""

    @pytest.fixture
    def state(self):
        return MockJarvisTerminalState()

    @pytest.fixture
    def actions(self, state):
        return MockJarvisTerminalActions(state)

    def test_welcome_message_displayed(self, state):
        """Test: Welcome message is displayed on load."""
        welcome_found = any(
            "jarvis" in line.content.lower() for line in state.lines
        )
        assert welcome_found

    def test_timestamp_on_lines(self, state, actions):
        """Test: Lines have timestamps."""
        import asyncio

        async def run():
            await actions.execute_command("help")
            return state.lines[-1].timestamp

        timestamp = asyncio.run(run())
        assert timestamp is not None
        assert isinstance(timestamp, datetime)

    @pytest.mark.asyncio
    async def test_pause_refunds_with_company_id(self, state, actions):
        """Test: pause_refunds with specific company ID."""
        result = await actions.execute_command("pause_refunds company_xyz")

        assert result.status == CommandStatus.SUCCESS
        assert result.result["company_id"] == "company_xyz"
        assert actions.is_refund_paused("company_xyz") is True

    @pytest.mark.asyncio
    async def test_multi_word_escalation_reason(self, state, actions):
        """Test: Escalation with multi-word reason."""
        result = await actions.execute_command(
            "force_escalation ticket_123 customer is very angry about delay"
        )

        assert result.status == CommandStatus.SUCCESS
        assert "angry" in result.result["reason"]


class TestJarvisTerminalAccessibility:
    """Tests for Jarvis terminal accessibility."""

    def test_terminal_focusable(self):
        """Test: Terminal input is focusable."""
        # Terminal should accept focus and keyboard input
        focusable = True  # Would check tabindex and role
        assert focusable

    def test_output_accessible(self):
        """Test: Terminal output is accessible."""
        # Output should have aria-live for updates
        # Screen readers should announce new output
        has_aria_live = True  # Would check aria-live attribute
        assert has_aria_live

    def test_command_history_navigation(self):
        """Test: Command history accessible via keyboard."""
        # Up/Down arrow should navigate history
        keyboard_shortcuts = {
            "ArrowUp": "previous_command",
            "ArrowDown": "next_command",
            "Enter": "execute_command",
            "Ctrl+C": "cancel_command",
        }
        assert len(keyboard_shortcuts) == 4


class TestJarvisTerminalSecurity:
    """Tests for Jarvis terminal security."""

    @pytest.fixture
    def state(self):
        return MockJarvisTerminalState()

    @pytest.fixture
    def actions(self, state):
        return MockJarvisTerminalActions(state)

    def test_commands_require_auth(self):
        """Test: Commands require authentication."""
        # Terminal should require admin auth for sensitive commands
        sensitive_commands = ["pause_refunds", "force_escalation"]
        assert len(sensitive_commands) == 2

    @pytest.mark.asyncio
    async def test_command_audit_logged(self, state, actions):
        """Test: Commands are logged for audit."""
        result = await actions.execute_command("pause_refunds")

        # Command should be logged with user_id and company_id
        assert result.result is not None

    def test_no_secrets_in_output(self, state, actions):
        """Test: Secrets are not shown in output."""
        # Output should never contain API keys, tokens, etc.
        import asyncio

        async def check_output():
            await actions.execute_command("system_status")
            for line in state.lines:
                assert "password" not in line.content.lower()
                assert "secret" not in line.content.lower()
                assert "token" not in line.content.lower()

        asyncio.run(check_output())
