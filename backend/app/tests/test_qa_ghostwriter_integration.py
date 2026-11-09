"""
Integration tests — AI QA Report Card + Ghostwriter.

Real in-memory database, REAL CLARA checklist (Layer 1 is pure code —
no LLM, no keys), mocked LLM only for Layer 2 / Ghostwriter.

The golden paths verified here:
  1. Every conversation gets a grade, stamped with its company_id.
  2. Hard evidence (angry words, repeat question) flags — never silent.
  3. The locked drawer: company A can never read or touch company B.
  4. Ghostwriter drafts only from the client's own data, always lands
     as status="draft", approval is human-only.
  5. API routers are company-scoped at the dependency level.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import app.services.qa_service as qa_service
import app.services.ghostwriter_service as gw_service
from database.models.jarvis import JarvisMessage
from database.models.qa_score import QAReportCard
from database.models.ghostwriter import GhostwriterDraft
from database.models.onboarding import DocumentChunk, KnowledgeDocument


COMPANY_A = "company-aaa"
COMPANY_B = "company-bbb"


def _llm_reply(content: str):
    return {"choices": [{"message": {"content": content}}]}


def _fake_settings(**overrides):
    from unittest.mock import MagicMock
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
# 1. LAYER 1 — GRADING (real CLARA, $0, no LLM)
# ══════════════════════════════════════════════════════════════════


class TestGradingIntegration:
    def test_clean_conversation_graded_and_not_flagged(self, in_memory_db, monkeypatch):
        db = in_memory_db()
        monkeypatch.setattr(qa_service, "_OFFICER_START_DELAY_SECONDS", 0)

        row = asyncio.run(qa_service.grade_and_schedule_review(
            db=db,
            company_id=COMPANY_A,
            conversation_id="conv-clean",
            channel="chat",
            user_message="Where is my order #12345?",
            ai_response=(
                "Your order #12345 shipped on Monday and arrives Thursday. "
                "Track it here: https://example.com/track/12345."
            ),
        ))

        assert row is not None
        assert row.company_id == COMPANY_A          # BC-001: the stamp
        assert row.channel == "chat"
        assert row.score is not None and row.score > 0
        assert row.flagged is False
        assert row.officer_status == "none"

    def test_angry_wording_flags_with_reason(self, in_memory_db, monkeypatch):
        db = in_memory_db()
        monkeypatch.setattr(qa_service, "_OFFICER_START_DELAY_SECONDS", 0)

        row = asyncio.run(qa_service.grade_and_schedule_review(
            db=db, company_id=COMPANY_A, conversation_id="conv-angry",
            channel="email",
            user_message="This is unacceptable, your service is a joke.",
            ai_response="I am sorry you feel that way.",
        ))

        assert row.flagged is True
        assert "angry_wording" in row.flag_reasons_json
        assert row.officer_status == "pending"

    def test_repeat_question_flags(self, in_memory_db, monkeypatch):
        db = in_memory_db()
        monkeypatch.setattr(qa_service, "_OFFICER_START_DELAY_SECONDS", 0)
        # production semantics: the current ask is already saved (Step 7)
        # plus one identical prior ask → count 2 → repeat evidence
        for _ in range(2):
            db.add(JarvisMessage(
                session_id="conv-repeat", role="user",
                content="Where is my refund?", message_type="text",
            ))
        db.commit()

        row = asyncio.run(qa_service.grade_and_schedule_review(
            db=db, company_id=COMPANY_A, conversation_id="conv-repeat",
            channel="chat",
            user_message="Where is my refund?",
            ai_response="Refunds take 5 business days.",
        ))

        reasons = row.flag_reasons_json
        assert "repeat_question" in reasons

    def test_every_grade_stamps_company_even_when_flagged(
        self, in_memory_db, monkeypatch,
    ):
        db = in_memory_db()
        monkeypatch.setattr(qa_service, "_OFFICER_START_DELAY_SECONDS", 0)
        for company in (COMPANY_A, COMPANY_B):
            row = asyncio.run(qa_service.grade_and_schedule_review(
                db=db, company_id=company, conversation_id=f"conv-{company}",
                channel="sms",
                user_message="I am furious, no one answered me!",
                ai_response="Hello.",
            ))
            assert row.company_id == company

    def test_disabled_qa_writes_nothing(self, in_memory_db, monkeypatch):
        db = in_memory_db()
        with patch("app.services.qa_service.get_settings",
                   return_value=_fake_settings(QA_ENABLED=False)):
            row = asyncio.run(qa_service.grade_and_schedule_review(
                db=db, company_id=COMPANY_A, conversation_id="c",
                channel="chat", user_message="q", ai_response="a",
            ))
        assert row is None
        assert db.query(QAReportCard).count() == 0


# ══════════════════════════════════════════════════════════════════
# 2. THE LOCKED DRAWER — tenant isolation at service level
# ══════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    def _seed_two_companies(self, db):
        now = datetime.now(timezone.utc)
        db.add(QAReportCard(
            id="row-a1", company_id=COMPANY_A, conversation_id="ca1",
            channel="chat", score=90, flagged=False, officer_status="none",
            created_at=now,
        ))
        db.add(QAReportCard(
            id="row-a2", company_id=COMPANY_A, conversation_id="ca2",
            channel="chat", score=40, flagged=True,
            flag_reasons_json='["tone_check"]', officer_status="pending",
            question_excerpt="Company A question about payouts",
            created_at=now,
        ))
        db.add(QAReportCard(
            id="row-b1", company_id=COMPANY_B, conversation_id="cb1",
            channel="email", score=10, flagged=True,
            flag_reasons_json='["structure_check"]', officer_status="pending",
            question_excerpt="Company B secret question",
            created_at=now,
        ))
        db.commit()

    def test_summary_never_leaks_other_company(self, in_memory_db):
        db = in_memory_db()
        self._seed_two_companies(db)

        summary_a = qa_service.get_qa_summary(db, COMPANY_A)
        assert summary_a["graded_total"] == 2          # only A's rows
        assert summary_a["flagged_count"] == 1

        summary_b = qa_service.get_qa_summary(db, COMPANY_B)
        assert summary_b["graded_total"] == 1
        assert summary_b["flagged_count"] == 1

    def test_flagged_list_is_company_locked(self, in_memory_db):
        db = in_memory_db()
        self._seed_two_companies(db)

        rows_a, total_a = qa_service.get_flagged_conversations(db, COMPANY_A)
        assert total_a == 1
        assert all("Company B" not in (r["question_excerpt"] or "") for r in rows_a)

        rows_b, total_b = qa_service.get_flagged_conversations(db, COMPANY_B)
        assert total_b == 1
        assert rows_b[0]["question_excerpt"] == "Company B secret question"
        assert rows_b[0]["conversation_id"] == "cb1"

    def test_draft_approval_cannot_cross_companies(self, in_memory_db):
        db = in_memory_db()
        db.add(GhostwriterDraft(
            id="draft-b1", company_id=COMPANY_B, gap_topic="payouts",
            status="draft",
        ))
        db.commit()

        # Company A tries to approve B's draft → physically not found
        result = gw_service.set_draft_status(db, COMPANY_A, "draft-b1", "approved")
        assert result is None
        db.rollback()

        # Company B approves its own → works
        result = gw_service.set_draft_status(db, COMPANY_B, "draft-b1", "approved")
        assert result is not None
        assert result.status == "approved"
        assert result.reviewed_at is not None

    def test_api_routers_cannot_be_called_without_company_scope(self):
        """Source-level guard: every endpoint takes company_id from the
        authenticated dependency, never from the request body."""
        qa_src = (
            Path(__file__).resolve().parents[2]
            / "app" / "api" / "qa_metrics.py"
        ).read_text()
        gw_src = (
            Path(__file__).resolve().parents[2]
            / "app" / "api" / "ghostwriter.py"
        ).read_text()
        assert qa_src.count("Depends(get_company_id)") >= 2
        assert gw_src.count("Depends(get_company_id)") >= 4
        assert "approve_draft" in gw_src and "reject_draft" in gw_src


# ══════════════════════════════════════════════════════════════════
# 3. GHOSTWRITER — gap → draft (mocked LLM, real DB)
# ══════════════════════════════════════════════════════════════════


def _seed_gap_material(db):
    """Company A has flagged payout questions + one matching KB doc.
    Company B has its own doc — must never appear in A's draft."""
    now = datetime.now(timezone.utc)
    db.add(QAReportCard(
        id="flag-a1", company_id=COMPANY_A, conversation_id="ca1",
        channel="chat", score=35, flagged=True,
        flag_reasons_json='["logic_check"]', officer_status="pending",
        question_excerpt="When will my UK payout arrive?",
        created_at=now,
    ))
    db.add(KnowledgeDocument(
        id="doc-a1", company_id=COMPANY_A, filename="payouts.pdf",
        status="completed",
    ))
    db.add(DocumentChunk(
        document_id="doc-a1", company_id=COMPANY_A, chunk_index=0,
        content="Payout policy: UK payouts are processed every Friday "
                "and arrive within 3 business days.",
    ))
    db.add(KnowledgeDocument(
        id="doc-b1", company_id=COMPANY_B, filename="secret-b.pdf",
        status="completed",
    ))
    db.add(DocumentChunk(
        document_id="doc-b1", company_id=COMPANY_B, chunk_index=0,
        content="Company B confidential payout rules.",
    ))
    db.commit()


class TestGhostwriterFlow:
    def test_draft_created_from_gap_with_own_sources_only(
        self, in_memory_db,
    ):
        db = in_memory_db()
        _seed_gap_material(db)
        mock_llm = AsyncMock(return_value=_llm_reply(
            '{"title": "Payout timing explained", '
            '"article_markdown": "UK payouts go out every Friday and '
            'arrive within 3 business days."}'
        ))

        with patch("litellm.acompletion", mock_llm):
            draft = asyncio.run(
                gw_service.create_draft_from_gap(db, COMPANY_A, "UK payout timing")
            )

        assert draft.company_id == COMPANY_A
        assert draft.status == "draft"                    # never auto-approved
        assert "payouts.pdf" in draft.sources_json
        assert "secret-b.pdf" not in draft.sources_json   # B's doc never leaks
        assert "When will my UK payout arrive?" in draft.based_on_json
        assert draft.model_used == "groq/llama-3.1-8b"    # light tier default
        assert mock_llm.await_count == 1                  # ONE cheap call

    def test_approve_then_reject_lifecycle(self, in_memory_db):
        db = in_memory_db()
        draft = GhostwriterDraft(
            id="d-1", company_id=COMPANY_A, gap_topic="t", status="draft",
        )
        db.add(draft)
        db.commit()

        approved = gw_service.set_draft_status(db, COMPANY_A, "d-1", "approved")
        assert approved.status == "approved"
        assert approved.reviewed_at is not None

        rejected = gw_service.set_draft_status(db, COMPANY_A, "d-1", "rejected")
        assert rejected.status == "rejected"

    def test_invalid_status_rejected(self, in_memory_db):
        db = in_memory_db()
        with pytest.raises(ValueError):
            gw_service.set_draft_status(db, COMPANY_A, "x", "auto_publish")

    def test_draft_lists_are_company_locked(self, in_memory_db):
        db = in_memory_db()
        db.add(GhostwriterDraft(
            id="da", company_id=COMPANY_A, gap_topic="a", status="draft",
        ))
        db.add(GhostwriterDraft(
            id="db2", company_id=COMPANY_B, gap_topic="b", status="draft",
        ))
        db.commit()

        rows_a, total_a = gw_service.list_drafts(db, COMPANY_A)
        assert total_a == 1 and rows_a[0]["id"] == "da"
        rows_b, total_b = gw_service.list_drafts(db, COMPANY_B)
        assert total_b == 1 and rows_b[0]["id"] == "db2"

    def test_no_matching_kb_still_drafts_honestly(self, in_memory_db):
        """No sources → prompt tells the model to state unknowns.
        The draft is still created (the gap is real, the honesty is kept)."""
        db = in_memory_db()
        mock_llm = AsyncMock(return_value=_llm_reply(
            '{"title": "Quantum refunds", '
            '"article_markdown": "Policy details need confirmation."}'
        ))
        with patch("litellm.acompletion", mock_llm):
            draft = asyncio.run(
                gw_service.create_draft_from_gap(db, COMPANY_A, "quantum refunds")
            )
        assert draft.status == "draft"
        assert draft.sources_json == "[]"
