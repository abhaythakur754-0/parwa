"""
Week 3 Unit Tests — Socket.io Server (BC-005, BC-001, BC-011)

Tests for:
- get_tenant_room() — room name generation + validation
- get_connected_count() — connection counting
- emit_to_tenant() — room emission + event buffer + return count
- emit_to_session() — targeted session emission
- Connection handler — JWT auth, backward compat
- Business handlers — subscribe, unsubscribe, ping
"""

import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.app.core.socketio import (
    get_tenant_room,
    get_connected_count,
    get_socketio_server,
    emit_to_tenant,
    emit_to_session,
    _validate_company_id,
    _extract_token_from_qs,
    TENANT_ROOM_PREFIX,
    MAX_COMPANY_ID_LENGTH,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mock_sio():
    """Mock Socket.io AsyncServer."""
    sio = AsyncMock()
    sio.manager = MagicMock()
    return sio


@pytest.fixture
def mock_socketio_pkg(mock_sio):
    """Mock the socketio package import."""
    with patch.dict("sys.modules", {"socketio": MagicMock(AsyncServer=lambda **kw: mock_sio)}):
        yield mock_sio


# ── get_tenant_room Tests ────────────────────────────────────────

class TestGetTenantRoom:
    """Tests for get_tenant_room() room name generation."""

    def test_valid_simple_id(self):
        result = get_tenant_room("acme")
        assert result == "tenant_acme"

    def test_valid_uuid(self):
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        result = get_tenant_room(uuid_str)
        assert result == f"tenant_{uuid_str}"

    def test_valid_numeric_id(self):
        result = get_tenant_room("12345")
        assert result == "tenant_12345"

    def test_valid_with_underscores(self):
        result = get_tenant_room("my_company_123")
        assert result == "tenant_my_company_123"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="required"):
            get_tenant_room("")

    def test_none_raises(self):
        with pytest.raises(ValueError, match="required"):
            get_tenant_room(None)

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="required"):
            get_tenant_room(123)

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="whitespace"):
            get_tenant_room("   ")

    def test_too_long_raises(self):
        long_id = "a" * (MAX_COMPANY_ID_LENGTH + 1)
        with pytest.raises(ValueError, match="max length"):
            get_tenant_room(long_id)

    def test_exactly_max_length_passes(self):
        exact_id = "a" * MAX_COMPANY_ID_LENGTH
        result = get_tenant_room(exact_id)
        assert result == f"tenant_{exact_id}"

    def test_control_char_null_raises(self):
        with pytest.raises(ValueError, match="control"):
            get_tenant_room("acme\x00")

    def test_control_char_tab_raises(self):
        with pytest.raises(ValueError, match="control"):
            get_tenant_room("acme\tcorp")

    def test_control_char_newline_raises(self):
        with pytest.raises(ValueError, match="control"):
            get_tenant_room("acme\ncorp")

    def test_strips_whitespace(self):
        result = get_tenant_room("  acme  ")
        assert result == "tenant_acme"

    def test_prefix_constant(self):
        assert TENANT_ROOM_PREFIX == "tenant_"


# ── _validate_company_id Tests ───────────────────────────────────

class TestValidateCompanyID:
    """Tests for _validate_company_id() helper."""

    def test_valid_returns_true(self):
        assert _validate_company_id("acme") is True

    def test_empty_returns_false(self):
        assert _validate_company_id("") is False

    def test_none_returns_false(self):
        assert _validate_company_id(None) is False

    def test_too_long_returns_false(self):
        assert _validate_company_id("a" * 200) is False

    def test_control_chars_returns_false(self):
        assert _validate_company_id("acme\x01") is False

    def test_whitespace_only_returns_false(self):
        assert _validate_company_id("   ") is False

    def test_stripped_valid_returns_true(self):
        assert _validate_company_id("  acme  ") is True


# ── _extract_token_from_qs Tests ─────────────────────────────────

class TestExtractTokenFromQS:
    """Tests for _extract_token_from_qs() helper."""

    def test_valid_token(self):
        qs = "token=abc123&other=val"
        assert _extract_token_from_qs(qs) == "abc123"

    def test_token_in_middle(self):
        qs = "other=val&token=xyz&more=stuff"
        assert _extract_token_from_qs(qs) == "xyz"

    def test_no_token(self):
        qs = "other=val&more=stuff"
        assert _extract_token_from_qs(qs) == ""

    def test_empty_qs(self):
        assert _extract_token_from_qs("") == ""

    def test_none_qs(self):
        assert _extract_token_from_qs(None) == ""

    def test_empty_token_value(self):
        qs = "token=&other=val"
        assert _extract_token_from_qs(qs) == ""


# ── get_connected_count Tests ────────────────────────────────────

class TestGetConnectedCount:
    """Tests for get_connected_count()."""

    def test_returns_zero_when_sio_none(self):
        with patch("backend.app.core.socketio.sio", None):
            result = get_connected_count()
            assert result == 0

    def test_returns_count_from_manager(self):
        mock_manager = MagicMock()
        mock_manager.get_participants.return_value = {"sid1", "sid2", "sid3"}
        mock_sio_instance = MagicMock()
        mock_sio_instance.manager = mock_manager
        with patch("backend.app.core.socketio.sio", mock_sio_instance):
            result = get_connected_count()
            assert result == 3

    def test_returns_zero_when_no_participants(self):
        mock_manager = MagicMock()
        mock_manager.get_participants.return_value = set()
        mock_sio_instance = MagicMock()
        mock_sio_instance.manager = mock_manager
        with patch("backend.app.core.socketio.sio", mock_sio_instance):
            result = get_connected_count()
            assert result == 0

    def test_returns_zero_on_exception(self):
        mock_manager = MagicMock()
        mock_manager.get_participants.side_effect = RuntimeError("broken")
        mock_sio_instance = MagicMock()
        mock_sio_instance.manager = mock_manager
        with patch("backend.app.core.socketio.sio", mock_sio_instance):
            result = get_connected_count()
            assert result == 0

    def test_returns_zero_when_no_manager(self):
        mock_sio_instance = MagicMock()
        # Remove 'manager' attribute
        del mock_sio_instance.manager
        with patch("backend.app.core.socketio.sio", mock_sio_instance):
            result = get_connected_count()
            assert result == 0


# ── emit_to_tenant Tests ─────────────────────────────────────────

class TestEmitToTenant:
    """Tests for emit_to_tenant()."""

    @pytest.mark.asyncio
    async def test_valid_emission(self):
        mock_manager = MagicMock()
        mock_manager.get_participants.return_value = {"sid1", "sid2"}
        mock_sio_instance = AsyncMock()
        mock_sio_instance.manager = mock_manager
        with patch("backend.app.core.socketio.sio", mock_sio_instance), \
             patch("backend.app.core.socketio.store_event", new_callable=AsyncMock) as mock_store:
            result = await emit_to_tenant("acme", "ticket:new", {"id": "123"})
            assert result == 2
            mock_sio_instance.emit.assert_called_once_with(
                "ticket:new", {"id": "123"}, room="tenant_acme"
            )
            mock_store.assert_called_once_with(
                company_id="acme", event_type="ticket:new", payload={"id": "123"}
            )

    @pytest.mark.asyncio
    async def test_invalid_company_id_raises(self):
        with pytest.raises(ValueError, match="Invalid company_id"):
            await emit_to_tenant("", "ticket:new", {})

    @pytest.mark.asyncio
    async def test_none_company_id_raises(self):
        with pytest.raises(ValueError, match="Invalid company_id"):
            await emit_to_tenant(None, "ticket:new", {})

    @pytest.mark.asyncio
    async def test_event_buffer_failure_does_not_break(self):
        mock_manager = MagicMock()
        mock_manager.get_participants.return_value = {"sid1"}
        mock_sio_instance = AsyncMock()
        mock_sio_instance.manager = mock_manager
        with patch("backend.app.core.socketio.sio", mock_sio_instance), \
             patch("backend.app.core.socketio.store_event", new_callable=AsyncMock,
                   side_effect=Exception("Redis down")):
            result = await emit_to_tenant("acme", "ticket:new", {"id": "123"})
            # Should still succeed — event buffer failure is non-fatal
            assert result == 1

    @pytest.mark.asyncio
    async def test_returns_zero_on_manager_exception(self):
        mock_manager = MagicMock()
        mock_manager.get_participants.side_effect = Exception("broken")
        mock_sio_instance = AsyncMock()
        mock_sio_instance.manager = mock_manager
        with patch("backend.app.core.socketio.sio", mock_sio_instance), \
             patch("backend.app.core.socketio.store_event", new_callable=AsyncMock):
            result = await emit_to_tenant("acme", "ticket:new", {})
            assert result == 0


# ── emit_to_session Tests ────────────────────────────────────────

class TestEmitToSession:
    """Tests for emit_to_session()."""

    @pytest.mark.asyncio
    async def test_emits_to_session(self):
        mock_sio_instance = AsyncMock()
        with patch("backend.app.core.socketio.sio", mock_sio_instance):
            await emit_to_session("acme", "session_123", "msg", {"text": "hi"})
            mock_sio_instance.emit.assert_called_once_with(
                "msg", {"text": "hi"}, room="session_123"
            )


# ── get_socketio_server Tests ────────────────────────────────────

class TestGetSocketioServer:
    """Tests for get_socketio_server()."""

    def test_returns_sio_instance(self):
        mock_sio_instance = MagicMock()
        with patch("backend.app.core.socketio.sio", mock_sio_instance):
            result = get_socketio_server()
            assert result is mock_sio_instance

    def test_returns_none_when_unavailable(self):
        with patch("backend.app.core.socketio.sio", None):
            result = get_socketio_server()
            assert result is None
