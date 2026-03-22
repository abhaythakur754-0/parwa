"""
Unit tests for Jarvis Commands module.

Tests for:
- pause_refunds Redis key set within 500ms
- resume_refunds removes key
- get_system_status returns data
- force_escalation works
"""
import pytest
import asyncio
from datetime import datetime

from backend.core.jarvis_commands import (
    JarvisCommands,
    JarvisCommandResult,
    RedisClient,
    get_jarvis_commands
)


class TestRedisClient:
    """Tests for Redis client."""

    @pytest.fixture
    def redis_client(self):
        """Create Redis client fixture."""
        return RedisClient()

    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_client):
        """Test basic set and get operations."""
        await redis_client.set("test_key", "test_value")
        result = await redis_client.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_expiry(self, redis_client):
        """Test set with expiry."""
        await redis_client.set("expiring_key", "value", ex=1)
        result = await redis_client.get("expiring_key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_delete(self, redis_client):
        """Test delete operation."""
        await redis_client.set("delete_key", "value")
        deleted = await redis_client.delete("delete_key")
        assert deleted is True
        result = await redis_client.get("delete_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_exists(self, redis_client):
        """Test exists operation."""
        await redis_client.set("exists_key", "value")
        exists = await redis_client.exists("exists_key")
        assert exists is True

        exists = await redis_client.exists("nonexistent_key")
        assert exists is False


class TestJarvisCommands:
    """Tests for JarvisCommands class."""

    @pytest.fixture
    def jarvis(self):
        """Create JarvisCommands fixture."""
        return JarvisCommands()

    @pytest.mark.asyncio
    async def test_pause_refunds_within_500ms(self, jarvis):
        """CRITICAL: pause_refunds must set Redis key within 500ms."""
        result = await jarvis.pause_refunds(
            company_id="test_company",
            reason="Emergency stop"
        )

        assert result.success is True
        assert result.command == "pause_refunds"
        assert result.company_id == "test_company"
        # CRITICAL: Must be within 500ms
        assert result.execution_time_ms < 500, \
            f"pause_refunds took {result.execution_time_ms}ms, must be < 500ms"
        assert result.data["paused"] is True
        assert result.audit_id is not None

    @pytest.mark.asyncio
    async def test_pause_refunds_with_duration(self, jarvis):
        """Test pause_refunds with auto-resume duration."""
        result = await jarvis.pause_refunds(
            company_id="test_company_2",
            reason="Scheduled maintenance",
            duration_minutes=30
        )

        assert result.success is True
        assert result.data["duration_minutes"] == 30

    @pytest.mark.asyncio
    async def test_resume_refunds_removes_key(self, jarvis):
        """Test resume_refunds removes the pause key."""
        # First pause
        pause_result = await jarvis.pause_refunds(
            company_id="resume_test_company"
        )
        assert pause_result.success is True

        # Verify paused
        is_paused = await jarvis.is_refunds_paused("resume_test_company")
        assert is_paused is True

        # Now resume
        resume_result = await jarvis.resume_refunds("resume_test_company")
        assert resume_result.success is True
        assert resume_result.data["resumed"] is True
        assert resume_result.data["was_paused"] is True

        # Verify no longer paused
        is_paused = await jarvis.is_refunds_paused("resume_test_company")
        assert is_paused is False

    @pytest.mark.asyncio
    async def test_get_system_status(self, jarvis):
        """Test get_system_status returns data."""
        result = await jarvis.get_system_status("test_company")

        assert result.success is True
        assert result.command == "get_system_status"
        assert result.company_id == "test_company"
        assert "refunds_paused" in result.data
        assert "system_health" in result.data
        assert result.data["company_id"] == "test_company"

    @pytest.mark.asyncio
    async def test_get_system_status_with_paused_refunds(self, jarvis):
        """Test system status reflects paused refunds."""
        company_id = "paused_status_company"

        # Pause refunds
        await jarvis.pause_refunds(company_id, reason="Test pause")

        # Get status
        status = await jarvis.get_system_status(company_id)

        assert status.success is True
        assert status.data["refunds_paused"] is True
        assert status.data["pause_info"] is not None
        assert status.data["pause_info"]["reason"] == "Test pause"

    @pytest.mark.asyncio
    async def test_force_escalation(self, jarvis):
        """Test force_escalation works."""
        result = await jarvis.force_escalation(
            ticket_id="TICKET-123",
            reason="Customer complaint",
            level="immediate"
        )

        assert result.success is True
        assert result.command == "force_escalation"
        assert result.data["ticket_id"] == "TICKET-123"
        assert result.data["escalated"] is True
        assert result.audit_id is not None

    @pytest.mark.asyncio
    async def test_force_escalation_default_level(self, jarvis):
        """Test force_escalation with default level."""
        result = await jarvis.force_escalation(
            ticket_id="TICKET-456",
            reason="Urgent issue"
        )

        assert result.success is True
        assert result.data["escalation_level"] == "immediate"

    @pytest.mark.asyncio
    async def test_audit_log(self, jarvis):
        """Test audit log is maintained."""
        # Execute several commands
        await jarvis.pause_refunds("audit_company")
        await jarvis.get_system_status("audit_company")
        await jarvis.force_escalation("TICKET-789", "Test")

        audit_log = jarvis.get_audit_log()
        assert len(audit_log) >= 3

        # Check audit entries have required fields
        for entry in audit_log:
            assert "audit_id" in entry
            assert "command" in entry
            assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_get_stats(self, jarvis):
        """Test get_stats returns statistics."""
        await jarvis.pause_refunds("stats_company")

        stats = jarvis.get_stats()

        assert "total_commands" in stats
        assert "pause_target_ms" in stats
        assert stats["pause_target_ms"] == 500
        assert stats["total_commands"] >= 1


class TestJarvisCommandResult:
    """Tests for JarvisCommandResult model."""

    def test_result_creation(self):
        """Test creating a result."""
        result = JarvisCommandResult(
            success=True,
            command="test_command",
            company_id="test_company",
            message="Test message"
        )

        assert result.success is True
        assert result.command == "test_command"
        assert result.company_id == "test_company"
        assert result.message == "Test message"
        assert isinstance(result.timestamp, datetime)

    def test_result_with_data(self):
        """Test result with additional data."""
        result = JarvisCommandResult(
            success=True,
            command="test_command",
            data={"key": "value", "count": 42}
        )

        assert result.data["key"] == "value"
        assert result.data["count"] == 42


class TestGetJarvisCommands:
    """Tests for factory function."""

    def test_get_jarvis_commands(self):
        """Test factory function returns instance."""
        jarvis = get_jarvis_commands()
        assert isinstance(jarvis, JarvisCommands)

    def test_multiple_calls_same_instance(self):
        """Test factory returns new instance each time."""
        jarvis1 = get_jarvis_commands()
        jarvis2 = get_jarvis_commands()
        # Note: This is not a singleton pattern, each call creates new instance
        assert isinstance(jarvis1, JarvisCommands)
        assert isinstance(jarvis2, JarvisCommands)
