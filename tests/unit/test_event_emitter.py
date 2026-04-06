"""
Tests for PARWA Event Emitter (Day 19)

Tests:
- emit_event validates event type and payload
- Payload size enforcement
- Metadata enrichment (correlation_id, timestamp)
- Category-scoped helpers
- Graceful error handling (never crashes)
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestEstimateBytes:
    """Test byte estimation utility."""

    def test_dict_estimate(self):
        """Estimates bytes for a simple dict."""
        from backend.app.core.event_emitter import _estimate_bytes
        result = _estimate_bytes({"key": "value"})
        assert result > 0

    def test_string_estimate(self):
        """Estimates bytes for a string."""
        from backend.app.core.event_emitter import _estimate_bytes
        result = _estimate_bytes("hello world")
        assert result > 0

    def test_large_payload_estimate(self):
        """Large payload returns large byte estimate."""
        from backend.app.core.event_emitter import _estimate_bytes
        large = {"data": "x" * 10000}
        result = _estimate_bytes(large)
        assert result > 10000

    def test_empty_dict(self):
        """Empty dict still has byte overhead."""
        from backend.app.core.event_emitter import _estimate_bytes
        result = _estimate_bytes({})
        assert result >= 2  # '{}'


class TestEnrichPayload:
    """Test payload enrichment."""

    def test_adds_meta_with_correlation_id(self):
        """Enrichment adds _meta with provided correlation_id."""
        from backend.app.core.event_emitter import _enrich_payload
        result = _enrich_payload(
            {"key": "val"}, "acme", correlation_id="corr-123"
        )
        assert result["key"] == "val"
        assert result["_meta"]["correlation_id"] == "corr-123"
        assert result["_meta"]["company_id"] == "acme"
        assert "timestamp" in result["_meta"]

    def test_generates_uuid_if_no_correlation_id(self):
        """Auto-generates UUID correlation_id if not provided."""
        from backend.app.core.event_emitter import _enrich_payload
        result = _enrich_payload({"key": "val"}, "acme")
        assert len(result["_meta"]["correlation_id"]) == 36  # UUID format

    def test_preserves_original_payload(self):
        """Original payload fields are preserved."""
        from backend.app.core.event_emitter import _enrich_payload
        result = _enrich_payload(
            {"ticket_id": "t-1", "status": "open"}, "acme"
        )
        assert result["ticket_id"] == "t-1"
        assert result["status"] == "open"


class TestEmitEvent:
    """Test core emit_event function."""

    @pytest.mark.asyncio
    async def test_unknown_event_type_returns_false(self):
        """Unknown event type returns False without crashing."""
        from backend.app.core.event_emitter import emit_event
        result = await emit_event(
            company_id="acme",
            event_type="unknown:event",
            payload={},
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_payload_returns_false(self):
        """Invalid payload (missing required fields) returns False."""
        from backend.app.core.event_emitter import emit_event
        result = await emit_event(
            company_id="acme",
            event_type="ticket:new",
            payload={"company_id": "acme"},  # missing ticket_id
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_oversized_payload_returns_false(self):
        """Payload exceeding max bytes returns False."""
        from backend.app.core.event_emitter import emit_event
        large_payload = {
            "ticket_id": "t-1",
            "company_id": "acme",
            "message": "x" * 15000,
        }
        result = await emit_event(
            company_id="acme",
            event_type="ticket:new",
            payload=large_payload,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_emit_failure_returns_false(self):
        """emit_to_tenant failure returns False (never crashes)."""
        from backend.app.core.event_emitter import emit_event
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            AsyncMock(side_effect=RuntimeError("Socket down")),
        ):
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "t-1", "company_id": "acme"},
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_valid_event_emits_and_enriches(self):
        """Valid event emits with enriched metadata."""
        from backend.app.core.event_emitter import emit_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "t-1", "company_id": "acme"},
                correlation_id="test-corr-xyz",
            )
        assert result is True
        mock_emit.assert_called_once()
        # Keyword args used by emit_to_tenant
        kwargs = mock_emit.call_args[1]
        assert kwargs["company_id"] == "acme"
        assert kwargs["event_type"] == "ticket:new"
        enriched = kwargs["payload"]
        assert "_meta" in enriched
        assert enriched["_meta"]["correlation_id"] == "test-corr-xyz"


class TestEmitTicketEvent:
    """Test ticket event helper."""

    @pytest.mark.asyncio
    async def test_valid_ticket_event(self):
        """Valid ticket event emits successfully."""
        from backend.app.core.event_emitter import emit_ticket_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_ticket_event(
                "acme", "ticket:new",
                {"ticket_id": "t-1", "company_id": "acme"},
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_non_ticket_event_rejected(self):
        """Non-ticket:* event type is rejected."""
        from backend.app.core.event_emitter import emit_ticket_event
        result = await emit_ticket_event(
            "acme", "ai:draft_ready",
            {"ticket_id": "t-1", "company_id": "acme"},
        )
        assert result is False


class TestEmitAIEvent:
    """Test AI event helper."""

    @pytest.mark.asyncio
    async def test_valid_ai_event(self):
        """Valid AI event emits successfully."""
        from backend.app.core.event_emitter import emit_ai_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_ai_event(
                "acme", "ai:classification",
                {"ticket_id": "t-1", "company_id": "acme"},
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_non_ai_event_rejected(self):
        """Non-ai:* event type is rejected."""
        from backend.app.core.event_emitter import emit_ai_event
        result = await emit_ai_event(
            "acme", "ticket:new",
            {"ticket_id": "t-1", "company_id": "acme"},
        )
        assert result is False


class TestEmitApprovalEvent:
    """Test approval event helper."""

    @pytest.mark.asyncio
    async def test_valid_approval_event(self):
        """Valid approval event emits successfully."""
        from backend.app.core.event_emitter import emit_approval_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_approval_event(
                "acme", "approval:pending",
                {"approval_id": "a-1", "company_id": "acme"},
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_non_approval_event_rejected(self):
        """Non-approval:* event type is rejected."""
        from backend.app.core.event_emitter import emit_approval_event
        result = await emit_approval_event(
            "acme", "ticket:new",
            {"ticket_id": "t-1", "company_id": "acme"},
        )
        assert result is False


class TestEmitNotificationEvent:
    """Test notification event helper."""

    @pytest.mark.asyncio
    async def test_valid_notification_event(self):
        """Valid notification event emits successfully."""
        from backend.app.core.event_emitter import emit_notification_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_notification_event(
                "acme", "notification:new",
                {"company_id": "acme", "title": "Test"},
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_non_notification_event_rejected(self):
        """Non-notification:* event type is rejected."""
        from backend.app.core.event_emitter import emit_notification_event
        result = await emit_notification_event(
            "acme", "ticket:new",
            {"ticket_id": "t-1", "company_id": "acme"},
        )
        assert result is False


class TestEmitSystemEvent:
    """Test system event helper."""

    @pytest.mark.asyncio
    async def test_system_event_with_company_id(self):
        """System event with explicit company_id."""
        from backend.app.core.event_emitter import emit_system_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_system_event(
                "system:health",
                {"subsystem": "redis", "status": "healthy"},
                company_id="acme",
            )
        assert result is True
        assert mock_emit.call_args[1]["company_id"] == "acme"

    @pytest.mark.asyncio
    async def test_system_event_global(self):
        """System event without company_id uses 'system'."""
        from backend.app.core.event_emitter import emit_system_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_system_event(
                "system:health",
                {"subsystem": "redis", "status": "healthy"},
            )
        assert result is True
        assert mock_emit.call_args[1]["company_id"] == "system"

    @pytest.mark.asyncio
    async def test_system_event_uses_payload_company_id(self):
        """System event uses company_id from payload if not provided."""
        from backend.app.core.event_emitter import emit_system_event
        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_system_event(
                "system:error",
                {"company_id": "acme", "message": "fail"},
            )
        assert result is True
        assert mock_emit.call_args[1]["company_id"] == "acme"

    @pytest.mark.asyncio
    async def test_non_system_event_rejected(self):
        """Non-system:* event type is rejected."""
        from backend.app.core.event_emitter import emit_system_event
        result = await emit_system_event(
            "ticket:new",
            {"ticket_id": "t-1", "company_id": "acme"},
        )
        assert result is False
