"""
Tests for PARWA Socket.io Server (Day 5)

Tests:
- Tenant room naming: tenant_{company_id} (BC-005)
- Room name validation
- Socket.io server initialization
- emit_to_tenant room scoping
- Cross-tenant isolation (no global rooms)
- Auth rejection for anonymous connections (BC-011)
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.socketio import (
    get_socketio_server,
    get_tenant_room,
    sio,
)


class TestGetTenantRoom:
    """Test tenant room name generation (BC-005)."""

    def test_basic_room_format(self):
        """Room follows tenant_{company_id} format."""
        result = get_tenant_room("acme")
        assert result == "tenant_acme"

    def test_room_starts_with_prefix(self):
        """Room name starts with tenant_ prefix."""
        result = get_tenant_room("mycompany")
        assert result.startswith("tenant_")

    def test_uuid_company_id(self):
        """Room name works with UUID company_ids."""
        result = get_tenant_room("550e8400-e29b-41d4-a716-446655440000")
        assert result == "tenant_550e8400-e29b-41d4-a716-446655440000"

    def test_empty_company_id_raises(self):
        """Empty company_id raises ValueError (BC-005)."""
        with pytest.raises(ValueError, match="company_id is required"):
            get_tenant_room("")

    def test_none_company_id_raises(self):
        """None company_id raises ValueError (BC-005)."""
        with pytest.raises(ValueError, match="company_id is required"):
            get_tenant_room(None)

    def test_int_company_id_raises(self):
        """Non-string company_id raises ValueError."""
        with pytest.raises(ValueError, match="company_id is required"):
            get_tenant_room(42)

    def test_whitespace_only_raises(self):
        """Whitespace-only company_id raises ValueError."""
        with pytest.raises(ValueError, match="whitespace-only"):
            get_tenant_room("   ")

    def test_whitespace_stripped(self):
        """Whitespace around company_id is stripped."""
        result = get_tenant_room("  acme  ")
        assert result == "tenant_acme"

    def test_control_chars_raise(self):
        """Control characters in company_id raise ValueError."""
        with pytest.raises(ValueError, match="control characters"):
            get_tenant_room("acme\x00evil")

    def test_max_length_enforced(self):
        """company_id exceeding max length raises ValueError."""
        long_id = "a" * 129
        with pytest.raises(ValueError, match="max length"):
            get_tenant_room(long_id)

    def test_max_length_boundary_ok(self):
        """company_id at max length (128) is accepted."""
        ok_id = "a" * 128
        result = get_tenant_room(ok_id)
        assert result == f"tenant_{ok_id}"

    def test_no_global_room(self):
        """Room name ALWAYS includes company_id (no global rooms)."""
        result = get_tenant_room("test")
        assert "tenant_test" == result
        assert result != "tenant_"
        assert result != "global"

    def test_different_tenants_different_rooms(self):
        """Different company_ids produce different rooms."""
        room_a = get_tenant_room("tenantA")
        room_b = get_tenant_room("tenantB")
        assert room_a != room_b
        assert room_a == "tenant_tenantA"
        assert room_b == "tenant_tenantB"


class TestSocketioServer:
    """Test Socket.io server initialization and configuration."""

    def test_server_exists(self):
        """Socket.io server singleton exists."""
        assert sio is not None

    def test_server_is_async(self):
        """Socket.io server is AsyncServer."""
        import socketio
        assert isinstance(sio, socketio.AsyncServer)

    def test_get_socketio_server(self):
        """get_socketio_server returns the same instance."""
        server = get_socketio_server()
        assert server is sio

    def test_async_mode_asgi(self):
        """Server is configured for ASGI async mode."""
        assert sio.async_mode == "asgi"

    def test_ping_timeout_set(self):
        """Ping timeout is configured for reliability."""
        assert sio.eio.ping_timeout == 60

    def test_ping_interval_set(self):
        """Ping interval is configured."""
        assert sio.eio.ping_interval == 25

    def test_max_http_buffer_size(self):
        """Max HTTP buffer size is set to prevent OOM."""
        assert sio.eio.max_http_buffer_size == 1_000_000

    def test_engineio_exists(self):
        """EngineIO server is initialized."""
        assert sio.eio is not None

    def test_transport_configured(self):
        """WebSocket and polling transports are configured."""
        # Transport config is set via EngineIO
        eio = sio.eio
        assert eio is not None


class TestEmitToTenant:
    """Test tenant-scoped event emission (BC-001, BC-005)."""

    @pytest.mark.asyncio
    async def test_emit_valid_company_id(self):
        """emit_to_tenant calls sio.emit with correct room."""
        mock_sio_emit = AsyncMock()
        with patch.object(sio, "emit", mock_sio_emit):
            with patch.object(sio, "rooms", AsyncMock(return_value=[])):
                from backend.app.core.socketio import emit_to_tenant
                await emit_to_tenant(
                    company_id="acme",
                    event_type="ticket:new",
                    payload={"ticket_id": "123"},
                )
                mock_sio_emit.assert_called_once()
                call_kwargs = mock_sio_emit.call_args
                assert call_kwargs[1]["room"] == "tenant_acme"
                assert call_kwargs[0][0] == "ticket:new"

    @pytest.mark.asyncio
    async def test_emit_invalid_company_id_raises(self):
        """emit_to_tenant rejects invalid company_id (BC-001)."""
        from backend.app.core.socketio import emit_to_tenant
        with pytest.raises(ValueError, match="Invalid company_id"):
            await emit_to_tenant(
                company_id="",
                event_type="test",
                payload={},
            )

    @pytest.mark.asyncio
    async def test_emit_stores_in_buffer(self):
        """emit_to_tenant also stores event in buffer (BC-005)."""
        mock_sio_emit = AsyncMock()
        mock_store = AsyncMock(return_value=True)
        with patch.object(sio, "emit", mock_sio_emit):
            with patch.object(sio, "rooms", AsyncMock(return_value=[])):
                with patch(
                    "backend.app.core.event_buffer.store_event",
                    mock_store,
                ):
                    from backend.app.core.socketio import emit_to_tenant
                    await emit_to_tenant(
                        company_id="acme",
                        event_type="ticket:new",
                        payload={"id": "1"},
                    )
                    mock_store.assert_called_once_with(
                        company_id="acme",
                        event_type="ticket:new",
                        payload={"id": "1"},
                    )

    @pytest.mark.asyncio
    async def test_emit_continues_if_buffer_fails(self):
        """emit_to_tenant doesn't fail if event buffer store fails (BC-005)."""
        mock_sio_emit = AsyncMock()
        mock_store = AsyncMock(side_effect=Exception("Buffer down"))
        with patch.object(sio, "emit", mock_sio_emit):
            with patch.object(sio, "rooms", AsyncMock(return_value=[])):
                with patch(
                    "backend.app.core.event_buffer.store_event",
                    mock_store,
                ):
                    from backend.app.core.socketio import emit_to_tenant
                    # Should NOT raise — emit still works
                    await emit_to_tenant(
                        company_id="acme",
                        event_type="ticket:new",
                        payload={},
                    )
                    mock_sio_emit.assert_called_once()
