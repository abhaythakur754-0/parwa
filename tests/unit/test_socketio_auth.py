"""
Tests for PARWA Socket.io JWT Auth (S02)

Tests:
- Connect with valid JWT (200 OK, joins room)
- Connect with expired JWT (rejected)
- Connect with invalid JWT (rejected)
- Connect with no token (rejected)
- Connect extracts user_id from JWT
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from backend.app.core.auth import (  # noqa: E402
    create_access_token,
)
from backend.app.core.socketio import (  # noqa: E402
    _extract_token_from_qs,
    _register_handlers,
    sio,
)

# Register handlers so connect/disconnect events are available
_register_handlers()


class TestExtractTokenFromQS:
    """Tests for _extract_token_from_qs helper."""

    def test_token_present(self):
        qs = "token=abc123&other=value"
        assert _extract_token_from_qs(qs) == "abc123"

    def test_token_only_param(self):
        qs = "token=mytoken"
        assert _extract_token_from_qs(qs) == "mytoken"

    def test_token_in_middle(self):
        qs = "a=1&token=mytok&b=2"
        assert _extract_token_from_qs(qs) == "mytok"

    def test_no_token(self):
        qs = "other=value&foo=bar"
        assert _extract_token_from_qs(qs) == ""

    def test_empty_qs(self):
        assert _extract_token_from_qs("") == ""

    def test_none_qs(self):
        assert _extract_token_from_qs(None) == ""


class TestSocketIOJWTAuth:
    """Tests for Socket.io JWT authentication (S02)."""

    @pytest.mark.asyncio
    async def test_connect_with_valid_jwt(self):
        """Valid JWT token allows connection and joins room."""
        token = create_access_token(
            user_id="user-001",
            company_id="acme",
            email="test@example.com",
            role="owner",
        )
        environ = {"QUERY_STRING": f"token={token}"}

        mock_enter = AsyncMock()
        mock_save = AsyncMock()

        with patch.object(sio, "enter_room", mock_enter):
            with patch.object(sio, "save_session", mock_save):
                result = await sio._trigger_event(
                    "connect", "/", "test-sid", environ,
                )
                assert result is not False

        mock_enter.assert_called_once()
        call_args = mock_enter.call_args
        assert call_args[0][0] == "test-sid"
        assert call_args[0][1] == "tenant_acme"

        mock_save.assert_called_once()
        session_data = mock_save.call_args[0][1]
        assert session_data["company_id"] == "acme"
        assert session_data["user_id"] == "user-001"

    @pytest.mark.asyncio
    async def test_connect_with_expired_jwt(self):
        """Expired JWT token rejects connection."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt

        settings_secret = os.environ["JWT_SECRET_KEY"]
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": "user-001",
            "company_id": "acme",
            "email": "test@example.com",
            "role": "owner",
            "plan": "starter",
            "type": "access",
            "exp": now - timedelta(hours=1),
            "iat": now - timedelta(hours=2),
            "nbf": now - timedelta(hours=2),
        }
        expired_token = jwt.encode(
            expired_payload, settings_secret,
            algorithm="HS256",
        )
        environ = {"QUERY_STRING": f"token={expired_token}"}

        mock_enter = AsyncMock()
        with patch.object(sio, "enter_room", mock_enter):
            result = await sio._trigger_event(
                "connect", "/", "test-sid", environ,
            )
            assert result is False

        mock_enter.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_with_invalid_jwt(self):
        """Invalid JWT token rejects connection."""
        environ = {
            "QUERY_STRING": "token=invalid.jwt.token"
        }

        mock_enter = AsyncMock()
        with patch.object(sio, "enter_room", mock_enter):
            result = await sio._trigger_event(
                "connect", "/", "test-sid", environ,
            )
            assert result is False

        mock_enter.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_with_no_token(self):
        """No token at all rejects connection."""
        environ = {"QUERY_STRING": "other=value"}

        mock_enter = AsyncMock()
        with patch.object(sio, "enter_room", mock_enter):
            result = await sio._trigger_event(
                "connect", "/", "test-sid", environ,
            )
            assert result is False

        mock_enter.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_extracts_user_id_from_jwt(self):
        """JWT payload sub claim stored as user_id in session."""
        token = create_access_token(
            user_id="user-xyz-999",
            company_id="acme",
            email="test@example.com",
            role="admin",
        )
        environ = {"QUERY_STRING": f"token={token}"}

        mock_enter = AsyncMock()
        mock_save = AsyncMock()

        with patch.object(sio, "enter_room", mock_enter):
            with patch.object(sio, "save_session", mock_save):
                await sio._trigger_event(
                    "connect", "/", "test-sid", environ,
                )

        session_data = mock_save.call_args[0][1]
        assert session_data["user_id"] == "user-xyz-999"
        assert session_data["company_id"] == "acme"

    @pytest.mark.asyncio
    async def test_connect_backward_compat_socketio_auth(self):
        """socketio_auth dict still works for backward compat."""
        environ = {
            "socketio_auth": {"company_id": "acme"},
            "QUERY_STRING": "",
        }

        mock_enter = AsyncMock()
        mock_save = AsyncMock()

        with patch.object(sio, "enter_room", mock_enter):
            with patch.object(sio, "save_session", mock_save):
                await sio._trigger_event(
                    "connect", "/", "test-sid", environ,
                )

        mock_enter.assert_called_once()
        session_data = mock_save.call_args[0][1]
        assert session_data["company_id"] == "acme"
