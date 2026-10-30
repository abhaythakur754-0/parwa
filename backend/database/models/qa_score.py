"""
AI QA Report Card model (table: qa_report_card).

One row per conversation, written by the fail-open hook in
jarvis_cc_service.send_cc_message (Step 13). Every grade is stamped
with company_id (BC-001) — the locked drawer: a client can never see
another client's conversations.

NOTE: the table is named qa_report_card, NOT qa_scores — the legacy
stub QAScore in analytics.py already owns "qa_scores" and is left
untouched (Ponytail: never delete pre-existing code).

Layer 1 (grading) is pure code + CLARA checklist: $0, no LLM.
Layer 2 (officer) columns stay empty until a flagged row is reviewed.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text,
    ForeignKey, Index,
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class QAReportCard(Base):
    """Quality grade for one conversation (all channels)."""

    __tablename__ = "qa_report_card"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    conversation_id = Column(String(36), index=True)  # jarvis_cc session id
    channel = Column(String(20), default="chat")      # chat / email / sms / voice

    # ── Layer 1: pure-code checklist + hard evidence ($0) ──
    overall_pass = Column(Boolean, default=True)
    score = Column(Integer)                       # 0-100, from CLARA gate
    checklist_json = Column(Text, default="{}")   # per-stage CLARA results
    evidence_json = Column(Text, default="[]")    # repeat question, angry words, ...
    question_excerpt = Column(String(500))       # what the customer asked (truncated)
    flagged = Column(Boolean, default=False, index=True)
    flag_reasons_json = Column(Text, default="[]")

    # ── Layer 2: officer double-check (flagged rows only, capped) ──
    # none | pending | reviewed | capped | error
    officer_status = Column(String(20), default="none")
    # confirm | correct | fail
    officer_verdict = Column(String(20))
    officer_score = Column(Integer)
    officer_notes = Column(Text)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True,
    )

    __table_args__ = (
        Index("ix_qa_report_card_company_created", "company_id", "created_at"),
        Index("ix_qa_report_card_company_flagged", "company_id", "flagged"),
    )
