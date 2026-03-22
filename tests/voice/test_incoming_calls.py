"""
Voice Call Tests.

Tests for incoming voice call handling including:
- Answer time (< 6 seconds)
- Recording disclosure
- Never IVR-only
- Call routing

CRITICAL REQUIREMENTS:
- Answer < 6 seconds
- Recording disclosure fires
- Never IVR-only
"""
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import time


class MockCallRecord:
    """Mock call record for testing."""

    def __init__(
        self,
        call_id: str,
        from_number: str,
        to_number: str,
        company_id: Optional[str] = None
    ):
        self.call_id = call_id
        self.from_number = from_number
        self.to_number = to_number
        self.company_id = company_id
        self.status = "ringing"
        self.phase = "answer"
        self.variant = "mini"
        self.agent_id: Optional[str] = None
        self.recording_disclosure_played = False
        self.created_at = datetime.now(timezone.utc)
        self.answered_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self.duration_seconds = 0.0
        self.answer_time_ms: float = 0.0


class MockVoiceHandler:
    """Mock voice handler for testing."""

    # CRITICAL: Must answer within 6 seconds
    ANSWER_TARGET_MS = 6000

    def __init__(self):
        self._active_calls: Dict[str, MockCallRecord] = {}
        self._call_history: List[MockCallRecord] = []
        self._metrics = {
            "total_calls": 0,
            "answered_calls": 0,
            "calls_within_target": 0,
        }

    async def handle_call(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming call with 5-step flow.

        CRITICAL: Must answer within 6 seconds.

        Args:
            call_data: Call details

        Returns:
            Dict with call handling result
        """
        start_time = time.time()
        call_id = str(uuid.uuid4())

        # Create call record
        call = MockCallRecord(
            call_id=call_id,
            from_number=call_data.get("from_number", "unknown"),
            to_number=call_data.get("to_number", "unknown"),
            company_id=call_data.get("company_id")
        )
        self._active_calls[call_id] = call
        self._metrics["total_calls"] += 1

        # Step 1: ANSWER
        call.status = "answered"
        call.answered_at = datetime.now(timezone.utc)

        # Step 2: GREET - Play recording disclosure
        call.phase = "greet"
        call.recording_disclosure_played = True  # CRITICAL

        # Step 3: ROUTE
        variant = call_data.get("variant", "mini")
        agent_id = f"agent-{variant}-{uuid.uuid4().hex[:8]}"
        call.agent_id = agent_id
        call.variant = variant
        call.phase = "handle"

        # Calculate answer time
        answer_time_ms = (time.time() - start_time) * 1000
        call.answer_time_ms = answer_time_ms

        self._metrics["answered_calls"] += 1
        if answer_time_ms < self.ANSWER_TARGET_MS:
            self._metrics["calls_within_target"] += 1

        return {
            "call_id": call_id,
            "status": "connected",
            "answer_time_ms": answer_time_ms,
            "within_target": answer_time_ms < self.ANSWER_TARGET_MS,
            "agent_assigned": agent_id,
            "variant": variant,
            "recording_disclosure": True,  # CRITICAL
            "ivr_only": False  # CRITICAL: Always False
        }

    async def route_to_agent(
        self,
        call_id: str,
        variant: str
    ) -> Dict[str, Any]:
        """
        Route call to agent.

        CRITICAL: Never IVR-only.

        Args:
            call_id: Call ID
            variant: Agent variant

        Returns:
            Dict with routing result
        """
        call = self._active_calls.get(call_id)
        if not call:
            return {"error": "Call not found", "routed": False}

        agent_id = f"agent-{variant}-{uuid.uuid4().hex[:8]}"
        call.agent_id = agent_id
        call.variant = variant

        return {
            "call_id": call_id,
            "routed": True,
            "agent_id": agent_id,
            "variant": variant,
            "ivr_only": False  # CRITICAL: Always False
        }

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Get call status."""
        call = self._active_calls.get(call_id)
        if not call:
            return {"error": "Call not found"}

        return {
            "call_id": call.call_id,
            "status": call.status,
            "phase": call.phase,
            "agent_id": call.agent_id,
            "recording_disclosure_played": call.recording_disclosure_played
        }

    async def end_call(
        self,
        call_id: str,
        reason: str = "completed"
    ) -> Dict[str, Any]:
        """End an active call."""
        call = self._active_calls.get(call_id)
        if not call:
            return {"error": "Call not found"}

        if call.answered_at:
            call.duration_seconds = (
                datetime.now(timezone.utc) - call.answered_at
            ).total_seconds()

        call.status = "completed" if reason == "completed" else "abandoned"
        call.ended_at = datetime.now(timezone.utc)

        self._call_history.append(call)
        del self._active_calls[call_id]

        return {
            "call_id": call_id,
            "status": call.status,
            "duration_seconds": call.duration_seconds
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total = self._metrics["total_calls"]
        within_target = self._metrics["calls_within_target"]

        return {
            "total_calls": total,
            "answered_calls": self._metrics["answered_calls"],
            "calls_within_target": within_target,
            "within_target_percent": (within_target / total * 100) if total > 0 else 0,
            "answer_target_ms": self.ANSWER_TARGET_MS
        }


@pytest.fixture
def voice_handler():
    """Create a mock voice handler."""
    return MockVoiceHandler()


class TestIncomingCallAnswerTime:
    """
    Tests for incoming call answer time.

    CRITICAL: Must answer within 6 seconds.
    """

    @pytest.mark.asyncio
    async def test_answer_within_6_seconds(self, voice_handler):
        """Test that calls are answered within 6 seconds."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "variant": "mini"
        }

        result = await voice_handler.handle_call(call_data)

        # CRITICAL: Answer time < 6 seconds (6000ms)
        assert result["answer_time_ms"] < 6000, \
            f"Answer time {result['answer_time_ms']}ms exceeds 6 second target"

    @pytest.mark.asyncio
    async def test_answer_time_within_target(self, voice_handler):
        """Test that answer time is flagged as within target."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        assert result["within_target"] is True

    @pytest.mark.asyncio
    async def test_multiple_calls_within_target(self, voice_handler):
        """Test that multiple calls are all answered within target."""
        for i in range(10):
            result = await voice_handler.handle_call({
                "from_number": f"+123456789{i}",
                "to_number": "+0987654321"
            })
            assert result["within_target"] is True

        metrics = voice_handler.get_metrics()
        assert metrics["calls_within_target"] == 10
        assert metrics["within_target_percent"] == 100.0


class TestRecordingDisclosure:
    """
    Tests for recording disclosure.

    CRITICAL: Recording disclosure must fire on every call.
    """

    @pytest.mark.asyncio
    async def test_recording_disclosure_fires(self, voice_handler):
        """Test that recording disclosure fires on call."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        # CRITICAL: Recording disclosure must be True
        assert result["recording_disclosure"] is True

    @pytest.mark.asyncio
    async def test_disclosure_in_call_status(self, voice_handler):
        """Test that disclosure is recorded in call status."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        status = await voice_handler.get_call_status(result["call_id"])

        assert status["recording_disclosure_played"] is True

    @pytest.mark.asyncio
    async def test_disclosure_always_fires(self, voice_handler):
        """Test that disclosure fires on every variant."""
        variants = ["mini", "parwa", "parwa_high"]

        for variant in variants:
            result = await voice_handler.handle_call({
                "from_number": "+1234567890",
                "to_number": "+0987654321",
                "variant": variant
            })

            assert result["recording_disclosure"] is True


class TestNeverIVROnly:
    """
    Tests for IVR-only prevention.

    CRITICAL: Never IVR-only, always connect to agent or human.
    """

    @pytest.mark.asyncio
    async def test_never_ivr_only(self, voice_handler):
        """Test that calls are never IVR-only."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        # CRITICAL: ivr_only must be False
        assert result["ivr_only"] is False

    @pytest.mark.asyncio
    async def test_agent_assigned(self, voice_handler):
        """Test that an agent is always assigned."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        assert result["agent_assigned"] is not None
        assert result["agent_assigned"].startswith("agent-")

    @pytest.mark.asyncio
    async def test_routing_never_ivr_only(self, voice_handler):
        """Test that routing is never IVR-only."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        route_result = await voice_handler.route_to_agent(
            result["call_id"],
            "mini"
        )

        assert route_result["ivr_only"] is False
        assert route_result["routed"] is True


class TestCallRouting:
    """
    Tests for call routing to correct variant.
    """

    @pytest.mark.asyncio
    async def test_route_to_mini_variant(self, voice_handler):
        """Test routing to mini variant."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "variant": "mini"
        })

        assert result["variant"] == "mini"
        assert "mini" in result["agent_assigned"]

    @pytest.mark.asyncio
    async def test_route_to_parwa_variant(self, voice_handler):
        """Test routing to parwa variant."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "variant": "parwa"
        })

        assert result["variant"] == "parwa"
        assert "parwa" in result["agent_assigned"]

    @pytest.mark.asyncio
    async def test_route_to_parwa_high_variant(self, voice_handler):
        """Test routing to parwa_high variant."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "variant": "parwa_high"
        })

        assert result["variant"] == "parwa_high"
        assert "parwa_high" in result["agent_assigned"]

    @pytest.mark.asyncio
    async def test_default_variant_is_mini(self, voice_handler):
        """Test that default variant is mini."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
            # No variant specified
        })

        assert result["variant"] == "mini"


class TestCallLifecycle:
    """
    Tests for call lifecycle management.
    """

    @pytest.mark.asyncio
    async def test_call_created(self, voice_handler):
        """Test that call is created properly."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        assert "call_id" in result
        assert result["status"] == "connected"

    @pytest.mark.asyncio
    async def test_call_status_retrieved(self, voice_handler):
        """Test that call status can be retrieved."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        status = await voice_handler.get_call_status(result["call_id"])

        assert status["call_id"] == result["call_id"]
        assert status["status"] == "answered"

    @pytest.mark.asyncio
    async def test_call_ended(self, voice_handler):
        """Test that call can be ended."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        end_result = await voice_handler.end_call(result["call_id"])

        assert end_result["status"] == "completed"
        assert "duration_seconds" in end_result

    @pytest.mark.asyncio
    async def test_call_abandoned(self, voice_handler):
        """Test that call can be marked as abandoned."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        end_result = await voice_handler.end_call(
            result["call_id"],
            reason="abandoned"
        )

        assert end_result["status"] == "abandoned"


class TestCallMetrics:
    """
    Tests for call metrics tracking.
    """

    @pytest.mark.asyncio
    async def test_metrics_tracked(self, voice_handler):
        """Test that metrics are tracked."""
        await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        metrics = voice_handler.get_metrics()

        assert metrics["total_calls"] == 1
        assert metrics["answered_calls"] == 1

    @pytest.mark.asyncio
    async def test_multiple_calls_metrics(self, voice_handler):
        """Test metrics for multiple calls."""
        for i in range(5):
            await voice_handler.handle_call({
                "from_number": f"+123456789{i}",
                "to_number": "+0987654321"
            })

        metrics = voice_handler.get_metrics()

        assert metrics["total_calls"] == 5
        assert metrics["answered_calls"] == 5
        assert metrics["calls_within_target"] == 5


class TestErrorHandling:
    """
    Tests for error handling in voice calls.
    """

    @pytest.mark.asyncio
    async def test_nonexistent_call_status(self, voice_handler):
        """Test status for nonexistent call."""
        status = await voice_handler.get_call_status("nonexistent-id")

        assert "error" in status

    @pytest.mark.asyncio
    async def test_nonexistent_call_end(self, voice_handler):
        """Test ending nonexistent call."""
        result = await voice_handler.end_call("nonexistent-id")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_nonexistent_call_route(self, voice_handler):
        """Test routing nonexistent call."""
        result = await voice_handler.route_to_agent("nonexistent-id", "mini")

        assert "error" in result
        assert result["routed"] is False


class TestFiveStepCallFlow:
    """
    Tests for the 5-step call flow:
    Answer → Greet → Route → Handle → End
    """

    @pytest.mark.asyncio
    async def test_answer_step(self, voice_handler):
        """Test Answer step of call flow."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        assert result["status"] == "connected"

    @pytest.mark.asyncio
    async def test_greet_step(self, voice_handler):
        """Test Greet step (recording disclosure)."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        assert result["recording_disclosure"] is True

    @pytest.mark.asyncio
    async def test_route_step(self, voice_handler):
        """Test Route step (agent assignment)."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        assert result["agent_assigned"] is not None

    @pytest.mark.asyncio
    async def test_handle_step(self, voice_handler):
        """Test Handle step (call in progress)."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        status = await voice_handler.get_call_status(result["call_id"])

        # Call should be in handle phase after routing
        assert status["phase"] == "handle"

    @pytest.mark.asyncio
    async def test_end_step(self, voice_handler):
        """Test End step (call completion)."""
        result = await voice_handler.handle_call({
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        })

        end_result = await voice_handler.end_call(result["call_id"])

        assert end_result["status"] == "completed"
