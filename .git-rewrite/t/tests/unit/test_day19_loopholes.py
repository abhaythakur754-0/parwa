"""
Day 19 Loophole Tests — Socket.io Business Event System

Tests for 4 loophole checks from WEEK3_ROADMAP.md Day 19:
- L59: Rate limit on event emission per tenant (max 100 events/sec)
- L60: Socket.io auth is verified on every handler, not just connect
- Cross-tenant event leakage (deep verification)
- Large payloads truncated/rejected (max 10KB per event)
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.events import reset_event_registry


@pytest.fixture(autouse=True)
def _reset():
    """Reset singletons before each test."""
    reset_event_registry()
    yield
    reset_event_registry()
    from backend.app.core.event_emitter import reset_rate_tracker
    reset_rate_tracker()


# ── L59: Rate Limiting ─────────────────────────────────────


class TestRateLimiting:
    """L59: Rate limit enforced on emit_event (BC-005)."""

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_after_threshold(self):
        """After 100 emits in 1 second, subsequent emits are blocked."""
        from backend.app.core.event_emitter import (
            emit_event,
            reset_rate_tracker,
        )

        reset_rate_tracker()
        mock_emit = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            # Emit 100 events (at the limit)
            success_count = 0
            for i in range(100):
                result = await emit_event(
                    company_id="acme",
                    event_type="ticket:new",
                    payload={"ticket_id": f"t-{i}", "company_id": "acme"},
                )
                if result:
                    success_count += 1

            assert success_count == 100

            # 101st should be rate-limited
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "t-blocked", "company_id": "acme"},
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_is_per_tenant(self):
        """Rate limit is independent per tenant."""
        from backend.app.core.event_emitter import (
            emit_event,
            reset_rate_tracker,
        )

        reset_rate_tracker()
        mock_emit = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            # Exhaust tenant-a's rate limit
            for i in range(100):
                await emit_event(
                    company_id="tenant-a",
                    event_type="ticket:new",
                    payload={"ticket_id": f"t-{i}", "company_id": "tenant-a"},
                )

            # tenant-a is blocked
            result_a = await emit_event(
                company_id="tenant-a",
                event_type="ticket:new",
                payload={"ticket_id": "blocked", "company_id": "tenant-a"},
            )
            assert result_a is False

            # tenant-b can still emit
            result_b = await emit_event(
                company_id="tenant-b",
                event_type="ticket:new",
                payload={"ticket_id": "ok", "company_id": "tenant-b"},
            )
            assert result_b is True

    @pytest.mark.asyncio
    async def test_rate_limit_is_per_event_type(self):
        """Rate limit is independent per event type for the same tenant."""
        from backend.app.core.event_emitter import (
            emit_event,
            reset_rate_tracker,
        )

        reset_rate_tracker()
        mock_emit = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            # Exhaust ticket:new limit for acme
            for i in range(100):
                await emit_event(
                    company_id="acme",
                    event_type="ticket:new",
                    payload={"ticket_id": f"t-{i}", "company_id": "acme"},
                )

            # ticket:new is blocked
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "blocked", "company_id": "acme"},
            )
            assert result is False

            # ai:classification for same tenant still works
            result = await emit_event(
                company_id="acme",
                event_type="ai:classification",
                payload={"ticket_id": "ai-ok", "company_id": "acme"},
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window(self):
        """Rate limit window resets after 1 second."""
        from backend.app.core.event_emitter import (
            emit_event,
            reset_rate_tracker,
        )

        reset_rate_tracker()
        mock_emit = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            # Exhaust limit
            for i in range(100):
                await emit_event(
                    company_id="acme",
                    event_type="ticket:new",
                    payload={"ticket_id": f"t-{i}", "company_id": "acme"},
                )

            # Blocked
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "blocked", "company_id": "acme"},
            )
            assert result is False

            # Fast-forward time past the window
            with patch("backend.app.core.event_emitter.time") as mock_time:
                mock_time.time.return_value = time.time() + 1.1
                mock_time.__name__ = "time"

                # Now should work again (old timestamps evicted)
                result = await emit_event(
                    company_id="acme",
                    event_type="ticket:new",
                    payload={"ticket_id": "recovered", "company_id": "acme"},
                )
                assert result is True


class TestRateLimitInternal:
    """Unit tests for _check_rate_limit function."""

    def test_allows_under_limit(self):
        """Allows emit when under limit."""
        from backend.app.core.event_emitter import _check_rate_limit
        _check_rate_limit("acme", "ticket:new", 100)
        assert _check_rate_limit("acme", "ticket:new", 100) is True

    def test_blocks_at_limit(self):
        """Blocks emit exactly at limit."""
        from backend.app.core.event_emitter import _check_rate_limit
        for _ in range(100):
            assert _check_rate_limit("acme", "ticket:new", 100) is True
        assert _check_rate_limit("acme", "ticket:new", 100) is False

    def test_custom_limit(self):
        """Respects custom rate limit value."""
        from backend.app.core.event_emitter import _check_rate_limit
        # Limit of 2
        assert _check_rate_limit("acme", "test", 2) is True
        assert _check_rate_limit("acme", "test", 2) is True
        assert _check_rate_limit("acme", "test", 2) is False

    def test_reset_clears_tracker(self):
        """reset_rate_tracker clears all entries."""
        from backend.app.core.event_emitter import (
            _check_rate_limit,
            reset_rate_tracker,
            _rate_tracker,
        )
        for _ in range(50):
            _check_rate_limit("acme", "test", 100)
        assert len(_rate_tracker["acme:test"]) == 50
        reset_rate_tracker()
        assert len(_rate_tracker) == 0


# ── L60: Auth on Every Handler ─────────────────────────────


class TestPingHandlerAuth:
    """L60: ping handler rejects unauthenticated sessions."""

    @pytest.mark.asyncio
    async def test_ping_without_company_id_rejected(self):
        """Ping without company_id in session returns error."""
        from backend.app.core.socketio import sio

        # Mock session without company_id
        mock_get_session = AsyncMock(return_value={"user_id": "u-123"})
        with patch.object(sio, "get_session", mock_get_session):
            result = await sio._trigger_event(
                "ping", "/", "test-sid-ping-noauth",
            )
        assert result["error"] == "unauthenticated"

    @pytest.mark.asyncio
    async def test_ping_with_company_id_succeeds(self):
        """Ping with valid company_id returns pong."""
        from backend.app.core.socketio import sio

        mock_get_session = AsyncMock(
            return_value={"company_id": "acme", "user_id": "u-1"}
        )
        with patch.object(sio, "get_session", mock_get_session):
            result = await sio._trigger_event(
                "ping", "/", "test-sid-ping-auth",
            )
        assert result.get("pong") is True
        assert "server_time" in result

    @pytest.mark.asyncio
    async def test_ping_session_exception_rejected(self):
        """Ping with session exception returns unauthenticated."""
        from backend.app.core.socketio import sio

        mock_get_session = AsyncMock(side_effect=KeyError("no session"))
        with patch.object(sio, "get_session", mock_get_session):
            result = await sio._trigger_event(
                "ping", "/", "test-sid-ping-err",
            )
        assert result["error"] == "unauthenticated"


class TestUnsubscribeHandlerAuth:
    """L60: event:unsubscribe handler rejects unauthenticated sessions."""

    @pytest.mark.asyncio
    async def test_unsubscribe_without_company_id_rejected(self):
        """Unsubscribe without company_id returns error."""
        from backend.app.core.socketio import sio

        mock_get_session = AsyncMock(return_value={"user_id": "u-123"})
        mock_save_session = AsyncMock()
        with patch.object(sio, "get_session", mock_get_session):
            with patch.object(sio, "save_session", mock_save_session):
                result = await sio._trigger_event(
                    "event:unsubscribe", "/",
                    "test-sid-unsub-noauth",
                    {"event_types": ["ticket:new"]},
                )
        assert result["error"] == "unauthenticated"


class TestSubscribeHandlerAuth:
    """L60: event:subscribe handler rejects unauthenticated sessions."""

    @pytest.mark.asyncio
    async def test_subscribe_without_company_id_rejected(self):
        """Subscribe without company_id returns error."""
        from backend.app.core.socketio import sio

        mock_get_session = AsyncMock(return_value={"user_id": "u-123"})
        mock_save_session = AsyncMock()
        with patch.object(sio, "get_session", mock_get_session):
            with patch.object(sio, "save_session", mock_save_session):
                result = await sio._trigger_event(
                    "event:subscribe", "/",
                    "test-sid-sub-noauth",
                    {"event_types": ["ticket:new"]},
                )
        assert result["error"] == "unauthenticated"


# ── Cross-Tenant Isolation (Deep) ─────────────────────────


class TestCrossTenantIsolationDeep:
    """Verify events NEVER leak across tenants."""

    @pytest.mark.asyncio
    async def test_emit_never_calls_another_tenant_room(self):
        """emit_to_tenant is called ONLY with the correct company_id."""
        from backend.app.core.event_emitter import emit_event

        call_log = []

        async def spy_emit(company_id, event_type, payload):
            call_log.append(company_id)

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            spy_emit,
        ):
            # Emit to 5 different tenants
            tenants = ["acme", "globex", "initech", "umbrella", "stark"]
            for tenant in tenants:
                await emit_event(
                    company_id=tenant,
                    event_type="ticket:new",
                    payload={"ticket_id": f"t-{tenant}", "company_id": tenant},
                )

        # Each emit should have called only its own tenant
        assert call_log == tenants
        assert len(call_log) == 5

    @pytest.mark.asyncio
    async def test_payload_cannot_override_company_id(self):
        """Even if payload has a different company_id, emit uses the arg."""
        from backend.app.core.event_emitter import emit_event

        captured = {}

        async def spy_emit(company_id, event_type, payload):
            captured["emit_company"] = company_id
            captured["payload_company"] = payload.get("company_id")

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            spy_emit,
        ):
            await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "t-1", "company_id": "HACKED-tenant"},
            )

        # The emit goes to the correct tenant (from arg), not from payload
        assert captured["emit_company"] == "acme"
        # But payload still has original company_id (from payload validation)
        assert captured["payload_company"] == "HACKED-tenant"

    @pytest.mark.asyncio
    async def test_enriched_meta_has_correct_company_id(self):
        """The _meta.company_id matches the emit arg, not payload."""
        from backend.app.core.event_emitter import emit_event

        captured_payload = None

        async def spy_emit(company_id, event_type, payload):
            nonlocal captured_payload
            captured_payload = payload

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            spy_emit,
        ):
            await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "t-1", "company_id": "acme"},
            )

        # _meta.company_id comes from emit arg, not payload
        assert captured_payload["_meta"]["company_id"] == "acme"

    @pytest.mark.asyncio
    async def test_system_event_to_system_tenant(self):
        """System events without company_id go to 'system' tenant."""
        from backend.app.core.event_emitter import emit_system_event

        captured = {}

        async def spy_emit(company_id, event_type, payload):
            captured["company_id"] = company_id

        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            spy_emit,
        ):
            await emit_system_event(
                "system:health",
                {"subsystem": "redis", "status": "healthy"},
            )

        assert captured["company_id"] == "system"


# ── Large Payload (10KB) ───────────────────────────────────


class TestPayloadSizeEnforcement:
    """Verify payloads exceeding max size are rejected."""

    @pytest.mark.asyncio
    async def test_just_under_10kb_accepted(self):
        """Payload just under 10KB is accepted."""
        from backend.app.core.event_emitter import emit_event

        # Build payload that's ~9.5KB
        payload = {
            "ticket_id": "t-1",
            "company_id": "acme",
            "message": "x" * 9500,
        }

        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload=payload,
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_exactly_10kb_accepted(self):
        """Payload at exactly 10KB limit is accepted."""
        from backend.app.core.event_emitter import emit_event
        import json

        payload = {"ticket_id": "t-1", "company_id": "acme", "message": "x"}
        # Grow until just at 10240
        while len(json.dumps(payload).encode()) < 10240:
            payload["message"] += "x"

        mock_emit = AsyncMock(return_value=1)
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload=payload,
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_over_10kb_rejected(self):
        """Payload over 10KB is rejected."""
        from backend.app.core.event_emitter import emit_event

        payload = {
            "ticket_id": "t-1",
            "company_id": "acme",
            "message": "x" * 12000,
        }

        mock_emit = AsyncMock()
        with patch(
            "backend.app.core.socketio.emit_to_tenant",
            mock_emit,
        ):
            result = await emit_event(
                company_id="acme",
                event_type="ticket:new",
                payload=payload,
            )
        assert result is False
        mock_emit.assert_not_called()
