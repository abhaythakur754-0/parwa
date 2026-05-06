"""
E2E Test: Jarvis Commands.

Tests Jarvis admin command operations with CRITICAL verification:
- pause_refunds Redis key set within 500ms
- Resume refunds removes key
- System status returns correctly
- Force escalation works
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import time
import json

from tests.e2e import E2ETestHelper, MockRedisClient


class MockJarvisCommands:
    """Mock Jarvis commands service for E2E testing."""

    # Performance targets
    PAUSE_REFUNDS_TARGET_MS = 500  # CRITICAL: Must be under 500ms

    def __init__(self, redis_client: MockRedisClient) -> None:
        """
        Initialize mock Jarvis commands.

        Args:
            redis_client: Mock Redis client
        """
        self._redis = redis_client
        self._audit_log: list[Dict[str, Any]] = []
        self._command_count = 0

    async def pause_refunds(
        self,
        company_id: str,
        reason: Optional[str] = None,
        duration_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Pause all refund processing.

        CRITICAL: Must set Redis key within 500ms.

        Args:
            company_id: Company ID
            reason: Pause reason
            duration_minutes: Auto-resume duration

        Returns:
            Pause result with timing
        """
        start_time = time.time()
        command_id = f"pause_{company_id}_{int(time.time() * 1000)}"

        try:
            # Set Redis key
            redis_key = f"jarvis:refund_pause:{company_id}"
            pause_data = json.dumps({
                "paused_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason or "Admin pause",
                "duration_minutes": duration_minutes
            })

            expiry = duration_minutes * 60 if duration_minutes else None
            await self._redis.set(redis_key, pause_data, ex=expiry)

            execution_time_ms = (time.time() - start_time) * 1000

            # Audit
            self._audit_log.append({
                "command_id": command_id,
                "command": "pause_refunds",
                "company_id": company_id,
                "execution_time_ms": execution_time_ms,
                "within_target": execution_time_ms < self.PAUSE_REFUNDS_TARGET_MS
            })
            self._command_count += 1

            return {
                "success": True,
                "command": "pause_refunds",
                "company_id": company_id,
                "execution_time_ms": execution_time_ms,
                "within_target_ms": execution_time_ms < self.PAUSE_REFUNDS_TARGET_MS,
                "redis_key": redis_key,
                "paused": True
            }

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "command": "pause_refunds",
                "error": str(e),
                "execution_time_ms": execution_time_ms
            }

    async def resume_refunds(self, company_id: str) -> Dict[str, Any]:
        """
        Resume refund processing.

        Args:
            company_id: Company ID

        Returns:
            Resume result
        """
        start_time = time.time()
        command_id = f"resume_{company_id}_{int(time.time() * 1000)}"

        try:
            redis_key = f"jarvis:refund_pause:{company_id}"
            was_paused = await self._redis.exists(redis_key)
            await self._redis.delete(redis_key)

            execution_time_ms = (time.time() - start_time) * 1000

            self._audit_log.append({
                "command_id": command_id,
                "command": "resume_refunds",
                "company_id": company_id,
                "was_paused": was_paused,
                "execution_time_ms": execution_time_ms
            })
            self._command_count += 1

            return {
                "success": True,
                "command": "resume_refunds",
                "company_id": company_id,
                "was_paused": was_paused,
                "resumed": True,
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "command": "resume_refunds",
                "error": str(e),
                "execution_time_ms": execution_time_ms
            }

    async def get_system_status(self, company_id: str) -> Dict[str, Any]:
        """
        Get system status for a company.

        Args:
            company_id: Company ID

        Returns:
            System status
        """
        start_time = time.time()

        try:
            pause_key = f"jarvis:refund_pause:{company_id}"
            is_paused = await self._redis.exists(pause_key)

            pause_data = None
            if is_paused:
                raw_data = await self._redis.get(pause_key)
                if raw_data:
                    pause_data = json.loads(raw_data)

            execution_time_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "company_id": company_id,
                "refunds_paused": is_paused,
                "pause_info": pause_data,
                "system_health": "operational",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def force_escalation(
        self,
        ticket_id: str,
        reason: str,
        level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Force escalate a ticket.

        Args:
            ticket_id: Ticket ID
            reason: Escalation reason
            level: Escalation level

        Returns:
            Escalation result
        """
        start_time = time.time()
        command_id = f"escalate_{ticket_id}_{int(time.time() * 1000)}"

        try:
            escalation_key = f"jarvis:escalation:{ticket_id}"
            escalation_data = json.dumps({
                "ticket_id": ticket_id,
                "reason": reason,
                "level": level or "immediate",
                "escalated_at": datetime.now(timezone.utc).isoformat(),
                "forced": True
            })

            await self._redis.set(escalation_key, escalation_data, ex=86400)

            execution_time_ms = (time.time() - start_time) * 1000

            self._audit_log.append({
                "command_id": command_id,
                "command": "force_escalation",
                "ticket_id": ticket_id,
                "reason": reason,
                "level": level,
                "execution_time_ms": execution_time_ms
            })
            self._command_count += 1

            return {
                "success": True,
                "command": "force_escalation",
                "ticket_id": ticket_id,
                "escalation_level": level or "immediate",
                "escalated": True,
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "command": "force_escalation",
                "error": str(e),
                "execution_time_ms": execution_time_ms
            }

    async def is_refunds_paused(self, company_id: str) -> bool:
        """
        Check if refunds are paused.

        Args:
            company_id: Company ID

        Returns:
            True if paused
        """
        redis_key = f"jarvis:refund_pause:{company_id}"
        return await self._redis.exists(redis_key)

    def get_audit_log(self, limit: int = 100) -> list[Dict[str, Any]]:
        """Get recent audit log."""
        return self._audit_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get command statistics."""
        return {
            "total_commands": self._command_count,
            "pause_target_ms": self.PAUSE_REFUNDS_TARGET_MS
        }


@pytest.fixture
def redis_client():
    """Create mock Redis client fixture."""
    return MockRedisClient()


@pytest.fixture
def jarvis(redis_client):
    """Create Jarvis commands fixture."""
    return MockJarvisCommands(redis_client)


class TestE2EJarvisPauseRefunds:
    """E2E tests for Jarvis pause_refunds command - CRITICAL."""

    @pytest.mark.asyncio
    async def test_pause_refunds_within_500ms(self, jarvis):
        """CRITICAL: pause_refunds must set Redis key within 500ms."""
        result = await jarvis.pause_refunds(
            company_id="test-company-001",
            reason="Emergency stop"
        )

        assert result["success"] is True
        assert result["paused"] is True
        assert result["execution_time_ms"] < 500, \
            f"CRITICAL: pause_refunds took {result['execution_time_ms']:.2f}ms, must be < 500ms"
        assert result["within_target_ms"] is True

    @pytest.mark.asyncio
    async def test_pause_refunds_sets_redis_key(self, jarvis, redis_client):
        """Test that pause_refunds sets the Redis key."""
        company_id = "redis-key-test"

        result = await jarvis.pause_refunds(company_id=company_id)

        assert result["success"] is True

        # Verify Redis key exists
        is_paused = await jarvis.is_refunds_paused(company_id)
        assert is_paused is True

        # Verify key content
        redis_key = f"jarvis:refund_pause:{company_id}"
        raw_data = await redis_client.get(redis_key)
        assert raw_data is not None

        data = json.loads(raw_data)
        assert "paused_at" in data
        assert data["reason"] == "Admin pause"

    @pytest.mark.asyncio
    async def test_pause_refunds_with_duration(self, jarvis, redis_client):
        """Test pause_refunds with auto-resume duration."""
        result = await jarvis.pause_refunds(
            company_id="duration-test",
            reason="Scheduled maintenance",
            duration_minutes=30
        )

        assert result["success"] is True
        assert result["execution_time_ms"] < 500

        # Verify duration stored
        redis_key = f"jarvis:refund_pause:duration-test"
        raw_data = await redis_client.get(redis_key)
        data = json.loads(raw_data)

        assert data["duration_minutes"] == 30


class TestE2EJarvisResumeRefunds:
    """E2E tests for Jarvis resume_refunds command."""

    @pytest.mark.asyncio
    async def test_resume_refunds_removes_redis_key(self, jarvis):
        """CRITICAL: resume_refunds must remove the pause key."""
        company_id = "resume-test-company"

        # First pause
        await jarvis.pause_refunds(company_id=company_id)
        assert await jarvis.is_refunds_paused(company_id) is True

        # Now resume
        result = await jarvis.resume_refunds(company_id)

        assert result["success"] is True
        assert result["was_paused"] is True
        assert result["resumed"] is True

        # Verify key removed
        assert await jarvis.is_refunds_paused(company_id) is False

    @pytest.mark.asyncio
    async def test_resume_refunds_twice_safe(self, jarvis):
        """Test that resuming twice is safe."""
        company_id = "double-resume-test"

        # Pause
        await jarvis.pause_refunds(company_id=company_id)

        # Resume once
        result1 = await jarvis.resume_refunds(company_id)
        assert result1["was_paused"] is True

        # Resume again (should still succeed)
        result2 = await jarvis.resume_refunds(company_id)
        assert result2["success"] is True
        assert result2["was_paused"] is False


class TestE2EJarvisSystemStatus:
    """E2E tests for Jarvis get_system_status command."""

    @pytest.mark.asyncio
    async def test_system_status_returns_data(self, jarvis):
        """Test that system status returns correct data."""
        result = await jarvis.get_system_status("status-test-company")

        assert result["success"] is True
        assert result["company_id"] == "status-test-company"
        assert "refunds_paused" in result
        assert "system_health" in result

    @pytest.mark.asyncio
    async def test_system_status_reflects_paused_state(self, jarvis):
        """Test that system status reflects paused refunds."""
        company_id = "paused-status-test"

        # Check initial status
        status1 = await jarvis.get_system_status(company_id)
        assert status1["refunds_paused"] is False

        # Pause refunds
        await jarvis.pause_refunds(
            company_id=company_id,
            reason="Testing pause"
        )

        # Check status now
        status2 = await jarvis.get_system_status(company_id)
        assert status2["refunds_paused"] is True
        assert status2["pause_info"] is not None
        assert status2["pause_info"]["reason"] == "Testing pause"


class TestE2EJarvisForceEscalation:
    """E2E tests for Jarvis force_escalation command."""

    @pytest.mark.asyncio
    async def test_force_escalation_works(self, jarvis):
        """Test that force_escalation works correctly."""
        result = await jarvis.force_escalation(
            ticket_id="TKT-12345",
            reason="Customer complaint",
            level="immediate"
        )

        assert result["success"] is True
        assert result["escalated"] is True
        assert result["escalation_level"] == "immediate"

    @pytest.mark.asyncio
    async def test_force_escalation_default_level(self, jarvis):
        """Test force_escalation with default level."""
        result = await jarvis.force_escalation(
            ticket_id="TKT-67890",
            reason="Urgent issue"
        )

        assert result["success"] is True
        assert result["escalation_level"] == "immediate"


class TestE2EJarvisAuditLog:
    """E2E tests for Jarvis audit logging."""

    @pytest.mark.asyncio
    async def test_audit_log_tracks_commands(self, jarvis):
        """Test that audit log tracks all commands."""
        # Execute multiple commands
        await jarvis.pause_refunds("audit-test-1")
        await jarvis.get_system_status("audit-test-1")
        await jarvis.force_escalation("TKT-AUDIT", "Test")
        await jarvis.resume_refunds("audit-test-1")

        audit_log = jarvis.get_audit_log()

        assert len(audit_log) >= 3

        # Verify audit entries
        commands = [e["command"] for e in audit_log]
        assert "pause_refunds" in commands
        assert "force_escalation" in commands
        assert "resume_refunds" in commands

    @pytest.mark.asyncio
    async def test_audit_log_includes_timing(self, jarvis):
        """Test that audit log includes execution timing."""
        await jarvis.pause_refunds("timing-test")

        audit_log = jarvis.get_audit_log()
        pause_entry = next(
            (e for e in audit_log if e["command"] == "pause_refunds"),
            None
        )

        assert pause_entry is not None
        assert "execution_time_ms" in pause_entry
        assert pause_entry["execution_time_ms"] < 500


class TestE2EJarvisCompleteWorkflow:
    """E2E tests for complete Jarvis workflows."""

    @pytest.mark.asyncio
    async def test_complete_pause_resume_workflow(self, jarvis):
        """
        Complete workflow: Pause → Verify → Resume → Verify.

        CRITICAL: Each operation must be fast.
        """
        company_id = "complete-workflow-test"

        # Step 1: Pause refunds
        pause_result = await jarvis.pause_refunds(
            company_id=company_id,
            reason="Complete workflow test"
        )

        assert pause_result["success"] is True
        assert pause_result["execution_time_ms"] < 500
        assert pause_result["within_target_ms"] is True

        # Step 2: Verify paused
        assert await jarvis.is_refunds_paused(company_id) is True

        # Step 3: Get status
        status = await jarvis.get_system_status(company_id)
        assert status["refunds_paused"] is True

        # Step 4: Resume refunds
        resume_result = await jarvis.resume_refunds(company_id)
        assert resume_result["success"] is True

        # Step 5: Verify resumed
        assert await jarvis.is_refunds_paused(company_id) is False

        # Verify final status
        final_status = await jarvis.get_system_status(company_id)
        assert final_status["refunds_paused"] is False

    @pytest.mark.asyncio
    async def test_multiple_companies_independent(self, jarvis):
        """Test that pause/resume works independently per company."""
        companies = ["company-a", "company-b", "company-c"]

        # Pause all companies
        for company_id in companies:
            result = await jarvis.pause_refunds(company_id=company_id)
            assert result["success"] is True
            assert result["execution_time_ms"] < 500

        # Verify all paused
        for company_id in companies:
            assert await jarvis.is_refunds_paused(company_id) is True

        # Resume only one
        await jarvis.resume_refunds("company-b")

        # Verify only that one resumed
        assert await jarvis.is_refunds_paused("company-a") is True
        assert await jarvis.is_refunds_paused("company-b") is False
        assert await jarvis.is_refunds_paused("company-c") is True

    @pytest.mark.asyncio
    async def test_performance_under_load(self, jarvis):
        """Test performance with rapid sequential commands."""
        import asyncio

        # Execute 20 pause commands rapidly
        tasks = [
            jarvis.pause_refunds(company_id=f"load-test-{i}")
            for i in range(20)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed within target
        for result in results:
            assert result["success"] is True
            assert result["execution_time_ms"] < 500, \
                f"CRITICAL: Command exceeded 500ms target: {result['execution_time_ms']:.2f}ms"
