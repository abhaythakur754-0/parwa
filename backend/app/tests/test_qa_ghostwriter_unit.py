"""
Unit tests — AI QA Report Card + Ghostwriter (pure logic + mocked LLM).

Covers:
  - Officer verdict JSON parsing (strict, uncertain never silently passes)
  - Ghostwriter draft JSON parsing, topic keyword extraction
  - Table-name regression guard (qa_report_card, NOT legacy qa_scores)
  - Officer background task: success, daily cap, escalation, unparseable
  - Ghostwriter daily cap

LLM is mocked everywhere here — no network, no keys needed.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.qa_service as qa_service
import app.services.ghostwriter_service as gw_service
from database.models.qa_score import QAReportCard
from database.models.ghostwriter import GhostwriterDraft


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def _llm_reply(content: str):
    return {"choices": [{"message": {"content": content}}]}


def _fake_settings(**overrides):
    s = MagicMock()
    s.QA_ENABLED = True
    s.QA_OFFICER_MODEL = ""
    s.QA_OFFICER_ESCALATION_MODEL = ""
    s.QA_OFFICER_DAILY_CAP = 500
    s.GHOSTWRITER_ENABLED = True
    s.GHOSTWRITER_MODEL = ""
    s.GHOSTWRITER_DAILY_CAP = 50
    s.AI_LIGHT_MODEL = "groq/llama-3.1-8b"
    s.AI_HEAVY_MODEL = "groq/gpt-oss-120b"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


# ══════════════════════════════════════════════════════════════════
# TABLE-NAME REGRESSION GUARDS (the qa_scores collision lesson)
# ══════════════════════════════════════════════════════════════════


class TestTableNameGuards:
    def test_qa_table_is_report_card_not_legacy_scores(self):
        assert QAReportCard.__tablename__ == "qa_report_card"
        assert QAReportCard.__tablename__ != "qa_scores"

    def test_ghostwriter_table_name(self):
        assert GhostwriterDraft.__tablename__ == "ghostwriter_drafts"

    def test_draft_default_status_is_never_approved(self):
        # Column default is the truth (applies at flush); a raw constructor
        # instance shows None before flush — so assert the default itself.
        assert GhostwriterDraft.__table__.c.status.default.arg == "draft"


# ══════════════════════════════════════════════════════════════════
# OFFICER VERDICT PARSING — uncertain must never silently pass
# ══════════════════════════════════════════════════════════════════


class TestOfficerParsing:
    def test_valid_confirm(self):
        parsed = qa_service._parse_officer_json(
            '{"verdict": "confirm", "score": 92, "note": "fine"}'
        )
        assert parsed == {"verdict": "confirm", "score": 92, "note": "fine"}

    def test_valid_with_surrounding_text(self):
        parsed = qa_service._parse_officer_json(
            'Sure! {"verdict": "fail", "score": 40, "note": "invented policy"} thanks'
        )
        assert parsed["verdict"] == "fail"

    def test_score_clamped(self):
        parsed = qa_service._parse_officer_json(
            '{"verdict": "correct", "score": 250, "note": "x"}'
        )
        assert parsed["score"] == 100

    def test_garbage_returns_none(self):
        assert qa_service._parse_officer_json("I cannot review this.") is None

    def test_unknown_verdict_returns_none(self):
        assert qa_service._parse_officer_json(
            '{"verdict": "maybe", "score": 50, "note": "?"}'
        ) is None


# ══════════════════════════════════════════════════════════════════
# OFFICER BACKGROUND TASK — mocked LLM, mocked db context
# ══════════════════════════════════════════════════════════════════


@pytest.fixture()
def fast_officer(monkeypatch):
    monkeypatch.setattr(qa_service, "_OFFICER_START_DELAY_SECONDS", 0)


def _seed_pending_row(db, report_id="rep-1", company_id="co-1"):
    row = QAReportCard(
        id=report_id,
        company_id=company_id,
        conversation_id="conv-1",
        channel="chat",
        score=55,
        flagged=True,
        officer_status="pending",
    )
    db.add(row)
    db.commit()
    return row


class TestOfficerTask:
    def test_officer_reviews_flagged_row(self, fast_officer, in_memory_db):
        db = in_memory_db()
        row = _seed_pending_row(db)
        mock_llm = AsyncMock(return_value=_llm_reply(
            '{"verdict": "confirm", "score": 88, "note": "acceptable"}'
        ))

        @contextmanager
        def fake_ctx():
            yield db

        with patch("database.base.get_db_context", fake_ctx), \
             patch("app.services.qa_service.get_settings",
                   return_value=_fake_settings()), \
             patch("litellm.acompletion", mock_llm):
            asyncio.run(qa_service._officer_review_task(
                row.id, row.company_id, "q", "a", ["tone_check"],
            ))

        db.refresh(row)
        assert row.officer_status == "reviewed"
        assert row.officer_verdict == "confirm"
        assert row.officer_score == 88
        assert mock_llm.await_count == 1

    def test_officer_cap_stops_llm(self, fast_officer, in_memory_db):
        db = in_memory_db()
        row = _seed_pending_row(db)
        db.add(QAReportCard(
            id="already-1", company_id="co-1", officer_status="reviewed",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
        mock_llm = AsyncMock()

        @contextmanager
        def fake_ctx():
            yield db

        with patch("database.base.get_db_context", fake_ctx), \
             patch("app.services.qa_service.get_settings",
                   return_value=_fake_settings(QA_OFFICER_DAILY_CAP=1)), \
             patch("litellm.acompletion", mock_llm):
            asyncio.run(qa_service._officer_review_task(
                row.id, row.company_id, "q", "a", [],
            ))

        db.refresh(row)
        assert row.officer_status == "capped"
        assert "cap" in (row.officer_notes or "")
        mock_llm.assert_not_awaited()

    def test_officer_escalates_on_fail(self, fast_officer, in_memory_db):
        db = in_memory_db()
        row = _seed_pending_row(db)
        mock_llm = AsyncMock(side_effect=[
            _llm_reply('{"verdict": "fail", "score": 30, "note": "wrong"}'),
            _llm_reply('{"verdict": "correct", "score": 65, "note": "partly"}'),
        ])

        @contextmanager
        def fake_ctx():
            yield db

        with patch("database.base.get_db_context", fake_ctx), \
             patch("app.services.qa_service.get_settings",
                   return_value=_fake_settings()), \
             patch("litellm.acompletion", mock_llm):
            asyncio.run(qa_service._officer_review_task(
                row.id, row.company_id, "q", "a", [],
            ))

        db.refresh(row)
        assert mock_llm.await_count == 2  # light failed → heavy double-check
        assert row.officer_verdict == "correct"

    def test_unparseable_verdict_marks_error_not_silent(
        self, fast_officer, in_memory_db,
    ):
        db = in_memory_db()
        row = _seed_pending_row(db)
        mock_llm = AsyncMock(return_value=_llm_reply("no json here"))

        @contextmanager
        def fake_ctx():
            yield db

        with patch("database.base.get_db_context", fake_ctx), \
             patch("app.services.qa_service.get_settings",
                   return_value=_fake_settings()), \
             patch("litellm.acompletion", mock_llm):
            asyncio.run(qa_service._officer_review_task(
                row.id, row.company_id, "q", "a", [],
            ))

        db.refresh(row)
        assert row.officer_status == "error"
        assert "unparseable" in (row.officer_notes or "")

    def test_budget_counter_counts_only_today(self, fast_officer, in_memory_db):
        db = in_memory_db()
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        db.add(QAReportCard(
            id="old-1", company_id="co-1", officer_status="reviewed",
            created_at=yesterday,
        ))
        db.commit()
        with patch("app.services.qa_service.get_settings",
                   return_value=_fake_settings(QA_OFFICER_DAILY_CAP=1)):
            ok, used = qa_service._officer_budget_ok(db)
        assert ok is True   # yesterday's review must not burn today's budget
        assert used == 0


# ══════════════════════════════════════════════════════════════════
# GHOSTWRITER PURE LOGIC
# ══════════════════════════════════════════════════════════════════


class TestGhostwriterParsing:
    def test_valid_draft(self):
        parsed = gw_service._parse_draft_json(
            '{"title": "Warranty", "article_markdown": "# Warranty\\nBody"}'
        )
        assert parsed["title"] == "Warranty"
        assert parsed["article_markdown"].startswith("#")

    def test_garbage_returns_none(self):
        assert gw_service._parse_draft_json("here you go!") is None

    def test_missing_title_rejected(self):
        assert gw_service._parse_draft_json(
            '{"title": "", "article_markdown": "x"}'
        ) is None

    def test_topic_words_skip_short_noise(self):
        assert gw_service._topic_words("How do EU warranty claims work?") == [
            "warranty", "claims", "work",
        ]


class TestGhostwriterCap:
    def test_daily_cap_blocks_before_llm(self, in_memory_db):
        db = in_memory_db()
        db.add(GhostwriterDraft(
            company_id="co-1", gap_topic="t",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
        mock_llm = AsyncMock()
        with patch("app.services.ghostwriter_service.get_settings",
                   return_value=_fake_settings(GHOSTWRITER_DAILY_CAP=1)), \
             patch("litellm.acompletion", mock_llm):
            with pytest.raises(gw_service.DraftCapReached):
                asyncio.run(gw_service.create_draft_from_gap(db, "co-1", "refunds"))
        mock_llm.assert_not_awaited()

    def test_disabled_flag_blocks_before_llm(self, in_memory_db):
        db = in_memory_db()
        mock_llm = AsyncMock()
        with patch("app.services.ghostwriter_service.get_settings",
                   return_value=_fake_settings(GHOSTWRITER_ENABLED=False)), \
             patch("litellm.acompletion", mock_llm):
            with pytest.raises(gw_service.GhostwriterDisabled):
                asyncio.run(gw_service.create_draft_from_gap(db, "co-1", "refunds"))
        mock_llm.assert_not_awaited()
