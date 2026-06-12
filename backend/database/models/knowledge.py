"""
PARWA Phase 3 — Knowledge Models

KnowledgeDocument and FAQ for RAG-powered customer support and
self-service knowledge management.

BC-001: Every table carries ``company_id`` for strict tenant boundaries.
All timestamps are UTC. Primary keys are UUID strings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, _uuid, _utcnow


# ---------------------------------------------------------------------------
# KnowledgeDocument
# ---------------------------------------------------------------------------

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="E.g. pdf, docx, txt, md, csv, html",
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="processing",
        comment="One of: processing, ready, failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Populated when status is 'failed'",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", lazy="selectin")

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_knowledge_documents_company_id", "company_id"),
        Index("ix_knowledge_documents_company_status", "company_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeDocument id={self.id!r} filename={self.filename!r} "
            f"status={self.status!r}>"
        )


# ---------------------------------------------------------------------------
# FAQ
# ---------------------------------------------------------------------------

class FAQ(Base):
    __tablename__ = "faqs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="E.g. billing, shipping, returns, technical, general",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # -- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship("Company", lazy="selectin")

    # -- indexes -------------------------------------------------------------
    __table_args__ = (
        Index("ix_faqs_company_id", "company_id"),
        Index("ix_faqs_company_category", "company_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<FAQ id={self.id!r} category={self.category!r}>"
