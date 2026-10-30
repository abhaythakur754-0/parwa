"""
Ghostwriter Draft model (table: ghostwriter_drafts).

One row per drafted help-centre article. A draft is created on demand
("Draft this gap"), is written ONLY from the client's own flagged
conversations and their own knowledge-base documents (BC-001 lock),
and NEVER goes live by itself — approval is an explicit human action.

Honesty rule: this feature drafts for approval. Nothing auto-publishes.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Column, DateTime, String, Text,
    ForeignKey, Index,
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class GhostwriterDraft(Base):
    """A drafted KB article waiting for (or past) human review."""

    __tablename__ = "ghostwriter_drafts"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    gap_topic = Column(String(255), nullable=False)

    # draft | approved | rejected — approval is always a human decision
    status = Column(String(20), default="draft", index=True)

    title = Column(String(255))
    content = Column(Text)                 # article markdown
    sources_json = Column(Text, default="[]")   # [{"document": "..."}]
    based_on_json = Column(Text, default="{}")  # {flagged_count, sample_questions}

    model_used = Column(String(100))

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True,
    )
    reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_ghostwriter_drafts_company_created", "company_id", "created_at"),
        Index("ix_ghostwriter_drafts_company_status", "company_id", "status"),
    )
