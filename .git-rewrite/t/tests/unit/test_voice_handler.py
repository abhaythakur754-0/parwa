"""
Unit tests for Voice Handler module.

Tests for:
- Answer < 6 seconds
- Never IVR-only
- 5-step call flow
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import asyncio
import time

# Import directly to avoid sqlalchemy dependency in services/__init__.py
import importlib.util
voice_handler_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'backend', 'services', 'voice_handler.py'
)
spec = importlib.util.spec_from_file_location(
    "voice_handler",
    voice_handler_path
)
voice_handler_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice_handler_module)

VoiceHandler = voice_handler_module.VoiceHandler
CallStatus = voice_handler_module.CallStatus
CallPhase = voice_handler_module.CallPhase
CallRecord = voice_handler_module.CallRecord
get_voice_handler = voice_handler_module.get_voice_handler


class TestVoiceHandler:
    """Tests for VoiceHandler class."""

    @pytest.fixture
    def handler(self):
        """Create VoiceHandler fixture."""
        return VoiceHandler()

    @pytest.mark.asyncio
    async def test_handle_call_answer_under_6_seconds(self, handler):
        """CRITICAL: Call must be answered within 6 seconds."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "company_id": "test_company",
            "variant": "mini"
        }

        start_time = time.time()
        result = await handler.handle_call(call_data)
        total_time = (time.time() - start_time) * 1000

        assert result["status"] == "connected"
        assert result["answer_time_ms"] < 6000, \
            f"Answer time {result['answer_time_ms']}ms exceeds 6 second target"
        assert result["within_target"] is True
        assert total_time < 6000

    @pytest.mark.asyncio
    async def test_handle_call_never_ivr_only(self, handler):
        """CRITICAL: Never IVR-only, always connect to agent or human."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "company_id": "test_company"
        }

        result = await handler.handle_call(call_data)

        # Must have an agent assigned
        assert result["agent_assigned"] is not None
        # The result should never indicate IVR-only
        assert "ivr_only" not in result or result.get("ivr_only") is False

    @pytest.mark.asyncio
    async def test_five_step_call_flow(self, handler):
        """Test the 5-step call flow: Answer → Greet → Route → Handle → End."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "variant": "mini"
        }

        # Execute handle_call which should perform Answer, Greet, Route, Handle
        result = await handler.handle_call(call_data)
        call_id = result["call_id"]

        # Verify call went through initial phases
        assert result["status"] == "connected"

        # Get call status to verify phase
        status = await handler.get_call_status(call_id)
        assert status["status"] == "in_progress"
        assert status["phase"] == "handle"

        # End call (step 5)
        end_result = await handler.end_call(call_id)
        assert end_result["status"] == "completed"

        # Verify call ended
        final_status = await handler.get_call_status(call_id)
        assert final_status["status"] == "completed"

    @pytest.mark.asyncio
    async def test_route_to_agent(self, handler):
        """Test routing call to agent."""
        # First handle a call to create it
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        }
        handle_result = await handler.handle_call(call_data)
        call_id = handle_result["call_id"]

        # Route to agent
        result = await handler.route_to_agent(call_id, "parwa")

        assert result["routed"] is True
        assert result["agent_id"] is not None
        assert result["variant"] == "parwa"
        assert result["ivr_only"] is False

    @pytest.mark.asyncio
    async def test_route_to_agent_nonexistent_call(self, handler):
        """Test routing non-existent call."""
        result = await handler.route_to_agent("nonexistent-call-id", "mini")

        assert "error" in result
        assert result["routed"] is False

    @pytest.mark.asyncio
    async def test_get_call_status(self, handler):
        """Test getting call status."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "company_id": "status_test_company"
        }

        result = await handler.handle_call(call_data)
        call_id = result["call_id"]

        status = await handler.get_call_status(call_id)

        assert status["call_id"] == call_id
        assert status["status"] == "in_progress"
        assert status["from_number"] == "+1234567890"
        assert status["to_number"] == "+0987654321"
        assert status["agent_id"] is not None

    @pytest.mark.asyncio
    async def test_get_call_status_nonexistent(self, handler):
        """Test getting status of non-existent call."""
        status = await handler.get_call_status("nonexistent-call-id")

        assert "error" in status

    @pytest.mark.asyncio
    async def test_end_call(self, handler):
        """Test ending a call."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        }

        result = await handler.handle_call(call_data)
        call_id = result["call_id"]

        end_result = await handler.end_call(call_id)

        assert end_result["status"] == "completed"
        assert end_result["call_id"] == call_id
        assert "duration_seconds" in end_result

    @pytest.mark.asyncio
    async def test_end_call_abandoned(self, handler):
        """Test ending a call as abandoned."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        }

        result = await handler.handle_call(call_data)
        call_id = result["call_id"]

        end_result = await handler.end_call(call_id, reason="abandoned")

        assert end_result["status"] == "abandoned"

    @pytest.mark.asyncio
    async def test_end_call_nonexistent(self, handler):
        """Test ending non-existent call."""
        result = await handler.end_call("nonexistent-call-id")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_recording_disclosure_played(self, handler):
        """CRITICAL: Recording disclosure must be played."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        }

        result = await handler.handle_call(call_data)
        call_id = result["call_id"]

        status = await handler.get_call_status(call_id)

        assert status["recording_disclosure_played"] is True

    @pytest.mark.asyncio
    async def test_get_metrics(self, handler):
        """Test getting performance metrics."""
        # Handle a few calls
        for i in range(3):
            await handler.handle_call({
                "from_number": f"+123456789{i}",
                "to_number": "+0987654321"
            })

        metrics = handler.get_metrics()

        assert metrics["total_calls"] >= 3
        assert metrics["answered_calls"] >= 3
        assert metrics["answer_target_ms"] == 6000
        assert "within_target_percent" in metrics

    @pytest.mark.asyncio
    async def test_get_active_calls(self, handler):
        """Test getting active calls list."""
        # Handle calls
        for i in range(2):
            await handler.handle_call({
                "from_number": f"+123456789{i}",
                "to_number": "+0987654321"
            })

        active_calls = handler.get_active_calls()

        assert len(active_calls) >= 2
        for call in active_calls:
            assert "call_id" in call
            assert "status" in call

    @pytest.mark.asyncio
    async def test_different_variants(self, handler):
        """Test routing to different agent variants."""
        variants = ["mini", "parwa", "parwa_high"]

        for variant in variants:
            call_data = {
                "from_number": "+1234567890",
                "to_number": "+0987654321",
                "variant": variant
            }

            result = await handler.handle_call(call_data)

            assert result["status"] == "connected"
            assert result["variant"] == variant

    @pytest.mark.asyncio
    async def test_call_duration_tracking(self, handler):
        """Test call duration is tracked."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        }

        result = await handler.handle_call(call_data)
        call_id = result["call_id"]

        # Wait a bit
        await asyncio.sleep(0.1)

        # End call
        end_result = await handler.end_call(call_id)

        assert end_result["duration_seconds"] >= 0.1

    @pytest.mark.asyncio
    async def test_multiple_concurrent_calls(self, handler):
        """Test handling multiple concurrent calls."""
        call_tasks = [
            handler.handle_call({
                "from_number": f"+123456789{i}",
                "to_number": "+0987654321"
            })
            for i in range(5)
        ]

        results = await asyncio.gather(*call_tasks)

        for result in results:
            assert result["status"] == "connected"
            assert result["answer_time_ms"] < 6000

        # Check all calls are tracked
        active_calls = handler.get_active_calls()
        assert len(active_calls) == 5


class TestCallRecord:
    """Tests for CallRecord model."""

    def test_call_record_creation(self):
        """Test creating a call record."""
        record = CallRecord(
            call_id="test-call-123",
            from_number="+1234567890",
            to_number="+0987654321"
        )

        assert record.call_id == "test-call-123"
        assert record.from_number == "+1234567890"
        assert record.to_number == "+0987654321"
        assert record.status == CallStatus.RINGING
        assert record.phase == CallPhase.ANSWER

    def test_call_record_with_company(self):
        """Test call record with company ID."""
        record = CallRecord(
            call_id="test-call-456",
            from_number="+1234567890",
            to_number="+0987654321",
            company_id="company_123"
        )

        assert record.company_id == "company_123"


class TestCallStatusEnum:
    """Tests for CallStatus enum."""

    def test_call_status_values(self):
        """Test CallStatus enum values."""
        assert CallStatus.RINGING == "ringing"
        assert CallStatus.ANSWERED == "answered"
        assert CallStatus.IN_PROGRESS == "in_progress"
        assert CallStatus.COMPLETED == "completed"
        assert CallStatus.ABANDONED == "abandoned"
        assert CallStatus.FAILED == "failed"


class TestCallPhaseEnum:
    """Tests for CallPhase enum."""

    def test_call_phase_values(self):
        """Test CallPhase enum values (5-step flow)."""
        assert CallPhase.ANSWER == "answer"
        assert CallPhase.GREET == "greet"
        assert CallPhase.ROUTE == "route"
        assert CallPhase.HANDLE == "handle"
        assert CallPhase.END == "end"


class TestGetVoiceHandler:
    """Tests for factory function."""

    def test_get_voice_handler(self):
        """Test factory function returns instance."""
        handler = get_voice_handler()
        assert isinstance(handler, VoiceHandler)


class TestIncomingCallsAPI:
    """Tests for the incoming calls API integration."""

    @pytest.fixture
    def handler(self):
        """Create VoiceHandler fixture."""
        return VoiceHandler()

    @pytest.mark.asyncio
    async def test_call_assignment_includes_recording_disclosure(self, handler):
        """Test that call handling includes recording disclosure."""
        call_data = {
            "from_number": "+1234567890",
            "to_number": "+0987654321"
        }

        result = await handler.handle_call(call_data)

        # Recording disclosure must be True
        assert result["recording_disclosure"] is True
