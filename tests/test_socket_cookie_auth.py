"""
Tests for socket.io cookie-based authentication (C-03 security fix).

Verifies that:
  1. The backend can extract the JWT from the httpOnly `parwa_at` cookie.
  2. The backend connect handler tries the cookie when the query-string token is missing.
  3. The frontend socket-client sets withCredentials: true (sends cookies).

Run:  cd backend && python3 -m pytest ../tests/test_socket_cookie_auth.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Cookie extraction helper ────────────────────────────────────────────

def test_extract_token_from_cookie_finds_parwa_at():
    from app.core.socketio import _extract_token_from_cookie

    cookie = "parwa_user=some_data; parwa_at=eyJ.abc.def; parwa_rt=xyz"
    assert _extract_token_from_cookie(cookie) == "eyJ.abc.def"


def test_extract_token_from_cookie_returns_empty_when_missing():
    from app.core.socketio import _extract_token_from_cookie

    assert _extract_token_from_cookie("parwa_user=data; other=val") == ""
    assert _extract_token_from_cookie("") == ""
    assert _extract_token_from_cookie(None) == ""  # type: ignore[arg-type]


def test_extract_token_from_cookie_handles_single_cookie():
    from app.core.socketio import _extract_token_from_cookie

    assert _extract_token_from_cookie("parwa_at=token123") == "token123"


def test_extract_token_from_cookie_strips_whitespace():
    from app.core.socketio import _extract_token_from_cookie

    cookie = "parwa_user=data; parwa_at=tok; other=val"
    # The extractor should handle semicolon-separated cookies with whitespace
    assert _extract_token_from_cookie(cookie) == "tok"


# ── 2. Query-string extraction still works (backward compat) ──────────────

def test_extract_token_from_qs_still_works():
    from app.core.socketio import _extract_token_from_qs

    assert _extract_token_from_qs("token=abc123") == "abc123"
    assert _extract_token_from_qs("foo=bar&token=abc&baz=qux") == "abc"
    assert _extract_token_from_qs("no_token_here") == ""
    assert _extract_token_from_qs("") == ""


# ── 3. Frontend socket-client sets withCredentials ─────────────────────────

def test_frontend_socket_client_has_with_credentials():
    """The frontend socket-client.ts must set withCredentials: true
    so the httpOnly cookie is sent on the WebSocket handshake."""
    source = (_REPO_ROOT / "src" / "lib" / "socket-client.ts").read_text()
    assert "withCredentials: true" in source, (
        "socket-client.ts missing `withCredentials: true` — "
        "httpOnly cookie is not sent on WebSocket handshake (C-03 risk)"
    )


# ── 4. Backend connect handler tries cookie fallback ───────────────────────

def test_backend_connect_handler_has_cookie_fallback():
    """The backend socketio.py connect handler must try the httpOnly cookie
    when the query-string token is missing."""
    source = (_REPO_ROOT / "backend" / "app" / "core" / "socketio.py").read_text()
    assert "_extract_token_from_cookie" in source
    assert "HTTP_COOKIE" in source
    # The cookie fallback must be tried when query-string token is empty
    assert "if not token:" in source


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
