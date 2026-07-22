"""
Tests for PARWA Socket.io Event Integration (Day 19)

Integration tests for:
- Event validation + Socket.io emission flow
- Cross-tenant event isolation
- All 5 categories emit correctly
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestEventEmissionIntegration:
    """Test emit_event → emit_to_tenant → buffer flow."""

    @pytest.mark.asyncio
    async def test_full_emit_flow_validates_and_emits(self):
        """Complete flow: validate payload → enrich → emit to room."""
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
                correlation_id="integration-test",
            )

        assert result is True
        mock_emit.assert_called_once()

        # Verify emit_to_tenant got correct kwargs
        kwargs = mock_emit.call_args[1]
        assert kwargs["company_id"] == "acme"
        assert kwargs["event_type"] == "ticket:new"
        enriched = kwargs["payload"]
        assert enriched["ticket_id"] == "t-1"
        assert "_meta" in enriched
        assert enriched["_meta"]["correlation_id"] == "integration-test"

    @pytest.mark.asyncio
    async def test_emit_to_correct_tenant_room(self):
        """Events are emitted only to the correct tenant room."""
        from backend.app.core.event_emitter import emit_ticket_event

        captured_company = None

        async def fake_emit(company_id, event_type, payload):
            nonlocal captured_company
            captured_company = company_id

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            fake_emit,
        ):
            await emit_ticket_event(
                "company-xyz", "ticket:resolved",
                {"ticket_id": "t-999", "company_id": "company-xyz"},
            )

        assert captured_company == "company-xyz"

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self):
        """Events emitted to one tenant do NOT reach another tenant."""
        from backend.app.core.event_emitter import emit_event

        emitted_companies = []

        async def capture_emit(company_id, event_type, payload):
            emitted_companies.append(company_id)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            capture_emit,
        ):
            await emit_event(
                "tenant-a", "ticket:new",
                {"ticket_id": "t-1", "company_id": "tenant-a"},
            )
            await emit_event(
                "tenant-b", "ticket:new",
                {"ticket_id": "t-2", "company_id": "tenant-b"},
            )

        assert emitted_companies == ["tenant-a", "tenant-b"]

    @pytest.mark.asyncio
    async def test_all_categories_emit(self):
        """Verify events from all 5 categories can be emitted."""
        from backend.app.core.event_emitter import (
            emit_ai_event,
            emit_approval_event,
            emit_notification_event,
            emit_system_event,
            emit_ticket_event,
        )

        mock_emit = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            r1 = await emit_ticket_event(
                "acme", "ticket:new",
                {"ticket_id": "t-1", "company_id": "acme"},
            )
            r2 = await emit_ai_event(
                "acme", "ai:classification",
                {"ticket_id": "t-1", "company_id": "acme"},
            )
            r3 = await emit_approval_event(
                "acme", "approval:pending",
                {"approval_id": "a-1", "company_id": "acme"},
            )
            r4 = await emit_notification_event(
                "acme", "notification:new",
                {"company_id": "acme"},
            )
            r5 = await emit_system_event(
                "system:health",
                {"subsystem": "redis", "status": "healthy"},
                company_id="acme",
            )

        assert all([r1, r2, r3, r4, r5])
        assert mock_emit.call_count == 5

    @pytest.mark.asyncio
    async def test_invalid_event_does_not_emit(self):
        """Invalid events never reach emit_to_tenant."""
        from backend.app.core.event_emitter import emit_event

        mock_emit = AsyncMock()

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_event(
                company_id="acme",
                event_type="nonexistent:event",
                payload={"data": "test"},
            )

        assert result is False
        mock_emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_emissions(self):
        """Multiple rapid emissions all succeed."""
        from backend.app.core.event_emitter import emit_event

        mock_emit = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            for i in range(10):
                result = await emit_event(
                    "acme", "ticket:new",
                    {"ticket_id": f"t-{i}", "company_id": "acme"},
                )

        assert result is True
        assert mock_emit.call_count == 10
