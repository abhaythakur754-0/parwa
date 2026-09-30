"""
Provider penalty box + reply-leak strip — tests for the 2026-09-18
live diagnostics (/api/v1/debug/provider-pool):

  - Mistral: 25 calls, 25 failures, ALL 429 — yet every 429 only cooled
    it down 60s, so the water-filling sort (60 RPM > Groq 30 RPM) picked
    it FIRST again after a minute and every ticket call paid a
    dead-provider attempt before reaching Groq. Escalating cooldown now
    benches repeat offenders: 60s → 120s → 240s → 480s → 900s cap.
  - NVIDIA: "[err] unknown" — empty str(httpx.TimeoutException) hid the
    failure cause; llm_call now records the exception TYPE.
  - Live ticket TKT-2B5B2BC3: the AI message was delivered starting with
    "**IMPROVED RESPONSE:**" — the quality node's workflow header.
    strip_meta_headers() removes it at the revision source AND at the
    delivery node.

Run: cd backend && ../venv/bin/python -m pytest tests/test_provider_penalty_and_leak.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ── 1. Escalating cooldown on consecutive 429/5xx ────────────────────


def _fresh_pool():
    from app.core.parwa_pipeline.llm_client import ProviderPool
    return ProviderPool()


def test_first_429_gets_base_cooldown():
    pool = _fresh_pool()
    pool.record_failure("mistral", status_code=429, error_text="rate limited")
    status = pool.get_status()["mistral"]
    # 60s base, allow a small scheduling margin
    assert 55 <= status["cooldown_seconds_left"] <= 60
    assert status["available"] is False


def test_consecutive_429s_escalate_cooldown():
    pool = _fresh_pool()
    streaks = []
    for _ in range(5):
        pool.record_failure("mistral", status_code=429, error_text="rate limited")
        streaks.append(pool.get_status()["mistral"]["cooldown_seconds_left"])
    # 60 → 120 → 240 → 480 → 900 (capped at the auth-error ceiling)
    assert streaks[0] <= 60
    assert streaks[1] <= 120 and streaks[1] > 100
    assert streaks[2] <= 240 and streaks[2] > 220
    assert streaks[3] <= 480 and streaks[3] > 460
    assert streaks[4] <= 900 and streaks[4] > 880


def test_success_resets_the_streak():
    pool = _fresh_pool()
    pool.record_failure("mistral", status_code=429, error_text="rate limited")
    pool.record_failure("mistral", status_code=429, error_text="rate limited")
    # streak=2 → 120s
    assert pool.get_status()["mistral"]["cooldown_seconds_left"] > 100
    pool.record_success("mistral")
    status = pool.get_status()["mistral"]
    assert status["available"] is True
    assert status["cooldown_seconds_left"] == 0
    # next single 429 must be base-level again, not escalated
    pool.record_failure("mistral", status_code=429, error_text="rate limited")
    assert pool.get_status()["mistral"]["cooldown_seconds_left"] <= 60


def test_5xx_also_escalates():
    pool = _fresh_pool()
    pool.record_failure("nvidia", status_code=503, error_text="service unavailable")
    pool.record_failure("nvidia", status_code=500, error_text="server error")
    assert pool.get_status()["nvidia"]["cooldown_seconds_left"] > 100


def test_cooling_provider_is_skipped_by_next_available():
    pool = _fresh_pool()
    pool.record_failure("mistral", status_code=429, error_text="rate limited")

    def _mistral(*a, **k):  # pragma: no cover — must never be picked
        raise AssertionError("cooling-down provider was selected")

    def _groq(*a, **k):
        return "ok"

    picked = pool.next_available([("mistral", _mistral), ("groq", _groq)])
    assert picked is not None and picked[0] == "groq"


# ── 2. Status parsing from provider error text ───────────────────────


def test_status_parsed_from_colon_suffixed_error():
    """Live bug: 'Mistral API error 429: ...' — the isdigit() check never
    matched '429:' (colon), so NO 429 cooldown ever fired. The regex
    parser must read it, with or without the colon."""
    from app.core.parwa_pipeline.llm_client import _status_from_error
    assert _status_from_error("Mistral API error 429: {rate_limited}") == 429
    assert _status_from_error("Groq API error 429:{\"error\":{}}") == 429
    assert _status_from_error("NVIDIA API error 503: upstream") == 503
    assert _status_from_error("no status here") == 0


def test_runtime_error_429_now_triggers_cooldown():
    """End-to-end guard: a provider raising RuntimeError('... 429: ...')
    must land the provider in an escalating cooldown (was: no cooldown
    at all, provider hammered 25/25 times)."""
    from app.core.parwa_pipeline.llm_client import ProviderPool, _status_from_error
    pool = _fresh_pool()
    exc = RuntimeError("Mistral API error 429: Rate limit exceeded")
    pool.record_failure("mistral", status_code=_status_from_error(str(exc)), error_text=str(exc))
    assert pool.get_status()["mistral"]["available"] is False
    assert pool.get_status()["mistral"]["cooldown_seconds_left"] > 50


# ── 3. Reply-leak strip (IMPROVED RESPONSE headers) ──────────────────


@pytest.mark.parametrize(
    "raw,expected_start",
    [
        (
            # 2026-09-19: orphan '---' separators left by header stripping
            # are now cleaned too — the reply starts at the real content.
            "**IMPROVED RESPONSE:**  \n---\n**Subject:** How to Reset Your Password",
            "**Subject:** How to Reset Your Password",
        ),
        (
            "IMPROVED RESPONSE:\nHere is how you reset your password.",
            "Here is how you reset your password.",
        ),
        (
            "## FINAL ANSWER\nThe reset link expires after 24 hours.",
            "The reset link expires after 24 hours.",
        ),
        (
            "*REVISED RESPONSE:* Thank you for reaching out.",
            "Thank you for reaching out.",
        ),
        (
            "__IMPROVED DRAFT__\nStep 1: open Settings.",
            "Step 1: open Settings.",
        ),
    ],
)
def test_strip_meta_headers_removes_leaked_headers(raw, expected_start):
    from app.core.email_utils import strip_meta_headers
    assert strip_meta_headers(raw).startswith(expected_start)


def test_strip_meta_headers_leaves_normal_replies_alone():
    from app.core.email_utils import strip_meta_headers
    reply = "Hi! To reset your password, click **Forgot Password** on the login page."
    assert strip_meta_headers(reply) == reply


def test_strip_meta_headers_keeps_midtext_mentions():
    """A header in the MIDDLE of the reply is content — only the top of
    the message is stripped."""
    from app.core.email_utils import strip_meta_headers
    reply = "This is our FINAL ANSWER policy explained below.\nDetails here."
    assert strip_meta_headers(reply) == reply


def test_strip_meta_headers_handles_empty():
    from app.core.email_utils import strip_meta_headers
    assert strip_meta_headers("") == ""
    assert strip_meta_headers(None) == ""


# ── 3. Delivery node strips before sending ───────────────────────────


def test_deliver_node_imports_the_strip():
    """Guarantees the belt-and-suspenders strip stays wired into Node 6.5.
    Reads the source file directly — conftest mocks can hide the module."""
    src = (
        Path(__file__).resolve().parents[1]
        / "app/core/parwa_pipeline/nodes/node_6_5_deliver.py"
    ).read_text()
    assert "strip_meta_headers" in src
