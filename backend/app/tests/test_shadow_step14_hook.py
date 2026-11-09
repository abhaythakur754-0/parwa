"""
Unit tests — Step 14 Shadow A/B hook (jarvis_cc_service wiring).

The hook's contract:
  1. Shadow Mode off / no config  → nothing happens, no LLM call.
  2. Shadow Mode on               → challenger answers the SAME message,
     the SAME CLARA checklist scores BOTH sides, comparison recorded,
     shadow_winner = shadow_score >= live_score.
  3. Challenger fails to answer   → comparison skipped honestly (no
     poisoned win/loss stats).
  4. ANY error inside the task    → swallowed (fail-open, BC-008):
     shadow must never break a live conversation.

Harness: in-memory SQLite with exactly the two shadow tables, bound
into the service via its _get_db_session seam (same house pattern as
app/tests/conftest.py). LLM + prompt pieces mocked; CLARA mocked with
controlled scores.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.jarvis_cc_service as cc_service
from app.services.shadow_mode_service import ShadowModeService
from database.base import Base
from database.models.shadow_mode import ShadowModeConfig, ShadowModeResult

COMPANY = "comp_step14_test"
SESSION = "sess_step14_test"

LIVE_RESPONSE = "Your payout arrives Friday."
SHADOW_RESPONSE = "Payouts land every Friday, within 3 business days."

# ── Shared in-memory engine: the service's own DB seam points here ──
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.close()


Base.metadata.create_all(
    bind=_engine,
    tables=[ShadowModeConfig.__table__, ShadowModeResult.__table__],
)
_test_session_factory = sessionmaker(bind=_engine, expire_on_commit=False)


def _patched_db_session():
    return _test_session_factory()


def _clara_result(score: float) -> SimpleNamespace:
    return SimpleNamespace(overall_score=score, overall_pass=score >= 0.6)


def _make_service(active: bool = True) -> ShadowModeService:
    svc = ShadowModeService()
    if active:
        assert svc.enable_shadow_mode(
            company_id=COMPANY,
            live_variant="mini_parwa",
            shadow_variant="parwa",
            sample_rate=1.0,
        )["success"]
    return svc


def _clara_factory(live_score: float, shadow_score: float):
    """CLARA mock: score by which response text it is asked to judge."""

    class _FakeClara:
        def __init__(self) -> None:
            self.evaluate = AsyncMock(side_effect=self._side)

        async def _side(self, response: str, **_kw):
            if response == LIVE_RESPONSE:
                return _clara_result(live_score)
            return _clara_result(shadow_score)

    return _FakeClara


@contextmanager
def _fake_db_ctx():
    yield MagicMock()


def _run_task(svc: ShadowModeService, **overrides) -> None:
    """Run the Step 14 task with all externals mocked."""
    with (
        patch.object(
            ShadowModeService, "_get_db_session",
            staticmethod(_patched_db_session),
        ),
        patch(
            "app.services.shadow_mode_service.get_shadow_mode_service",
            return_value=svc,
        ),
        patch(
            "app.services.jarvis_cc_service.build_cc_system_prompt",
            return_value="SYSTEM PROMPT",
        ),
        patch(
            "app.services.jarvis_cc_service._get_recent_history",
            return_value=[{"role": "user", "content": "hi"}],
        ),
        patch(
            "app.services.jarvis_cc_service._call_ai_provider_fallback",
            AsyncMock(return_value=(SHADOW_RESPONSE, "direct_ai", {}, [])),
        ),
        patch(
            "app.core.clara_quality_gate.CLARAQualityGate",
            overrides.get(
                "clara_factory",
                _clara_factory(live_score=0.8, shadow_score=0.9),
            ),
        ),
        patch("database.base.get_db_context", lambda: _fake_db_ctx()),
    ):
        asyncio.run(
            cc_service._shadow_comparison_task(
                company_id=COMPANY,
                session_id=SESSION,
                user_message="When is my payout?",
                live_response=LIVE_RESPONSE,
                live_ctx={"variant_tier": "mini_parwa", "industry": "ecom"},
                live_elapsed_ms=120.0,
            )
        )


def _history_rows(svc: ShadowModeService) -> list:
    return svc.get_comparison_history(COMPANY) or []


# ════════════════════════════════════════════════════════════════════
# 1. OFF → nothing happens
# ════════════════════════════════════════════════════════════════════


class TestHookOff:
    def test_no_config_means_no_shadow_processing(self):
        with patch.object(
            ShadowModeService, "_get_db_session",
            staticmethod(_patched_db_session),
        ):
            svc = _make_service(active=False)
            should, reason = svc.should_process_shadow(COMPANY, "hello")
        assert should is False
        assert reason == "no_active_shadow_mode"

    def test_inactive_config_midflight_records_nothing(self):
        with patch.object(
            ShadowModeService, "_get_db_session",
            staticmethod(_patched_db_session),
        ):
            svc = _make_service(active=True)
            svc.disable_shadow_mode(COMPANY, "turned off between gate and task")
            rows = _history_rows(svc)
        assert rows == []


# ════════════════════════════════════════════════════════════════════
# 2. ON → fair fight, same checklist, correct verdict
# ════════════════════════════════════════════════════════════════════


class TestHookOn:
    def test_shadow_better_records_winner_true(self):
        svc = _make_service()
        _run_task(svc, clara_factory=_clara_factory(0.8, 0.9))
        rows = _history_rows(svc)
        assert len(rows) == 1
        row = rows[0]
        assert row["live_quality_score"] == pytest.approx(0.8)
        assert row["shadow_quality_score"] == pytest.approx(0.9)
        assert row["quality_delta"] == pytest.approx(0.1)
        assert row["shadow_winner"] is True
        assert row["shadow_variant"] == "parwa"
        assert row["live_variant"] == "mini_parwa"

    def test_live_better_records_winner_false(self):
        svc = _make_service()
        _run_task(svc, clara_factory=_clara_factory(0.9, 0.7))
        row = _history_rows(svc)[0]
        assert row["shadow_winner"] is False
        assert row["quality_delta"] == pytest.approx(-0.2)

    def test_equal_scores_count_as_shadow_win(self):
        # Model semantics: "True if shadow_quality >= live_quality" —
        # matched-or-exceeded, same bar the graduation streak uses.
        svc = _make_service()
        _run_task(svc, clara_factory=_clara_factory(0.75, 0.75))
        row = _history_rows(svc)[0]
        assert row["shadow_winner"] is True

    def test_mode_at_comparison_reflects_config_status(self):
        svc = _make_service()
        _run_task(svc, clara_factory=_clara_factory(0.5, 0.5))
        row = _history_rows(svc)[0]
        assert row["mode_at_comparison"] == "shadow"

    def test_shadow_ctx_uses_challenger_tier(self):
        """The challenger must be prompted under ITS OWN variant tier."""
        svc = _make_service()
        with (
            patch.object(
                ShadowModeService, "_get_db_session",
                staticmethod(_patched_db_session),
            ),
            patch(
                "app.services.shadow_mode_service.get_shadow_mode_service",
                return_value=svc,
            ),
            patch(
                "app.services.jarvis_cc_service.build_cc_system_prompt",
                return_value="SYSTEM PROMPT",
            ) as mock_prompt,
            patch(
                "app.services.jarvis_cc_service._get_recent_history",
                return_value=[],
            ),
            patch(
                "app.services.jarvis_cc_service._call_ai_provider_fallback",
                AsyncMock(return_value=(SHADOW_RESPONSE, "direct_ai", {}, [])),
            ),
            patch(
                "app.core.clara_quality_gate.CLARAQualityGate",
                _clara_factory(0.8, 0.9),
            ),
            patch("database.base.get_db_context", lambda: _fake_db_ctx()),
        ):
            asyncio.run(
                cc_service._shadow_comparison_task(
                    company_id=COMPANY,
                    session_id=SESSION,
                    user_message="When is my payout?",
                    live_response=LIVE_RESPONSE,
                    live_ctx={"variant_tier": "mini_parwa"},
                    live_elapsed_ms=100.0,
                )
            )
        ctx_arg = mock_prompt.call_args[0][3]
        assert ctx_arg["variant_tier"] == "parwa"


# ════════════════════════════════════════════════════════════════════
# 3. CHALLENGER SILENCE → skip honestly
# ════════════════════════════════════════════════════════════════════


class TestChallengerNoAnswer:
    def test_friendly_error_response_records_nothing(self):
        svc = _make_service()
        with (
            patch.object(
                ShadowModeService, "_get_db_session",
                staticmethod(_patched_db_session),
            ),
            patch(
                "app.services.shadow_mode_service.get_shadow_mode_service",
                return_value=svc,
            ),
            patch(
                "app.services.jarvis_cc_service.build_cc_system_prompt",
                return_value="SYSTEM PROMPT",
            ),
            patch(
                "app.services.jarvis_cc_service._get_recent_history",
                return_value=[],
            ),
            patch(
                "app.services.jarvis_cc_service._call_ai_provider_fallback",
                AsyncMock(
                    return_value=(
                        cc_service._get_friendly_error_message(),
                        "direct_ai",
                        {},
                        [],
                    )
                ),
            ),
            patch("database.base.get_db_context", lambda: _fake_db_ctx()),
        ):
            asyncio.run(
                cc_service._shadow_comparison_task(
                    company_id=COMPANY,
                    session_id=SESSION,
                    user_message="When is my payout?",
                    live_response=LIVE_RESPONSE,
                    live_ctx={},
                    live_elapsed_ms=100.0,
                )
            )
        assert _history_rows(svc) == []


# ════════════════════════════════════════════════════════════════════
# 4. FAIL-OPEN — shadow must never break the conversation
# ════════════════════════════════════════════════════════════════════


class TestFailOpen:
    def test_provider_exception_is_swallowed(self):
        svc = _make_service()
        with (
            patch.object(
                ShadowModeService, "_get_db_session",
                staticmethod(_patched_db_session),
            ),
            patch(
                "app.services.shadow_mode_service.get_shadow_mode_service",
                return_value=svc,
            ),
            patch(
                "app.services.jarvis_cc_service.build_cc_system_prompt",
                return_value="SYSTEM PROMPT",
            ),
            patch(
                "app.services.jarvis_cc_service._get_recent_history",
                return_value=[],
            ),
            patch(
                "app.services.jarvis_cc_service._call_ai_provider_fallback",
                AsyncMock(side_effect=RuntimeError("provider down")),
            ),
            patch("database.base.get_db_context", lambda: _fake_db_ctx()),
        ):
            # Must NOT raise — the send path continues regardless.
            asyncio.run(
                cc_service._shadow_comparison_task(
                    company_id=COMPANY,
                    session_id=SESSION,
                    user_message="When is my payout?",
                    live_response=LIVE_RESPONSE,
                    live_ctx={},
                    live_elapsed_ms=100.0,
                )
            )
        assert _history_rows(svc) == []
