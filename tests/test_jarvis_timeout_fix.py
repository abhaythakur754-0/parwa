"""
Tests for Jarvis chat timeout fix (30s → 90s frontend, 30s → 60s backend).

Verifies:
  1. Frontend axios timeout is 90000ms (90s)
  2. Backend LLM gateway timeout is 60s
  3. Backend Jarvis chat timeout is 60s
  4. Vercel maxDuration for Jarvis route is 90s
  5. No 30s (30000ms) timeout remaining in the chat path

Run:  cd backend && python3 -m pytest ../tests/test_jarvis_timeout_fix.py -v --noconftest
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Frontend axios timeout ───────────────────────────────────────────

def test_frontend_axios_timeout_90s():
    """axios client timeout must be 90000ms (90s), not 30000ms."""
    source = (_REPO_ROOT / "src" / "lib" / "api.ts").read_text()
    assert "90000" in source, "axios timeout must be 90000 (90s)"
    assert "timeout: 30000" not in source, "Old 30000ms timeout still present"


# ── 2. Backend LLM gateway timeout ─────────────────────────────────────

def test_backend_llm_timeout_60s():
    """LLM gateway READ_TIMEOUT must be 60s, not 30s."""
    source = (_BACKEND / "app" / "core" / "llm_gateway.py").read_text()
    assert "READ_TIMEOUT_SECONDS = 60.0" in source, "LLM timeout must be 60s"
    assert "READ_TIMEOUT_SECONDS = 30.0" not in source, "Old 30s timeout still present"


# ── 3. Backend Jarvis chat timeout ─────────────────────────────────────

def test_backend_jarvis_chat_timeout_60s():
    """Jarvis chat.py future.result timeout must be 60s, not 30s."""
    source = (_BACKEND / "app" / "services" / "jarvis" / "chat.py").read_text()
    assert "timeout=60" in source, "Jarvis chat timeout must be 60s"
    # The old 30s timeout should be gone from the orchestrator call
    assert "_future.result(timeout=30)" not in source, "Old 30s timeout still present"


# ── 4. Vercel maxDuration ────────────────────────────────────────────────

def test_vercel_jarvis_max_duration_90():
    """Vercel maxDuration for Jarvis route must be 90s."""
    source = (_REPO_ROOT / "vercel.json").read_text()
    assert '"maxDuration": 90' in source, "Vercel Jarvis maxDuration must be 90s"


# ── 5. No 30s timeout in the critical path ──────────────────────────────

def test_no_30s_timeout_in_jarvis_path():
    """No remaining 30s (30000ms) timeout in the Jarvis chat path."""
    # Frontend
    api_source = (_REPO_ROOT / "src" / "lib" / "api.ts").read_text()
    assert "timeout: 30000" not in api_source, "api.ts still has 30000ms timeout"

    # Backend LLM gateway
    llm_source = (_BACKEND / "app" / "core" / "llm_gateway.py").read_text()
    assert "READ_TIMEOUT_SECONDS = 30.0" not in llm_source, "LLM still has 30s timeout"


# ── 6. Backend fallback message exists ──────────────────────────────────

def test_friendly_error_message_exists():
    """The friendly error fallback message must exist in jarvis_cc_service.py."""
    source = (_BACKEND / "app" / "services" / "jarvis_cc_service.py").read_text()
    assert "_get_friendly_error_message" in source, "Missing fallback function"
    assert "temporary issue" in source.lower() or "follow up" in source.lower(), \
           "Missing user-friendly fallback message"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--noconftest"]))
