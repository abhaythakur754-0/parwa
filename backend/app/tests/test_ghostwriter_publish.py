"""
Integration tests — Ghostwriter publish (the self-extending loop's wire).

The closed circuit: gap → draft → HUMAN approve → approved article lands
in knowledge_documents + document_chunks (company-stamped, status=
"completed") → Node 3 of the live pipeline reads exactly those tables.

Real in-memory database (house conftest fixture), no LLM needed — the
draft here is seeded directly; publishing involves no model call.
Tests target the SERVICE layer (house pattern — app.api imports pull the
whole auth chain, which the minimal venv cannot carry).
"""

from __future__ import annotations

import pytest

import app.services.ghostwriter_service as gw_service
from database.models.ghostwriter import GhostwriterDraft
from database.models.onboarding import DocumentChunk, KnowledgeDocument


COMPANY_A = "company-aaa"
COMPANY_B = "company-bbb"

ARTICLE = (
    "UK payouts go out every Friday and arrive within 3 business days. "
    "Late payouts: contact support after 5 business days."
)


def _seed_draft(db, draft_id: str = "d-pub", company_id: str = COMPANY_A,
                status: str = "approved", content: str = ARTICLE) -> GhostwriterDraft:
    draft = GhostwriterDraft(
        id=draft_id, company_id=company_id, gap_topic="UK payout timing",
        status=status, title="Payout timing explained",
        content=content,
    )
    db.add(draft)
    db.commit()
    return draft


class TestPublishService:
    def test_approved_draft_publishes_completed_company_stamped_doc(
        self, in_memory_db,
    ):
        db = in_memory_db()
        _seed_draft(db)

        doc = gw_service.publish_draft_to_knowledge(db, COMPANY_A, "d-pub")

        assert doc is not None
        assert doc.company_id == COMPANY_A            # BC-001: the stamp
        assert doc.status == "completed"              # Node 3 only reads completed
        assert doc.category == "ghostwriter"          # provenance is visible
        assert doc.filename.endswith(".md")
        chunk = (
            db.query(DocumentChunk)
            .filter_by(document_id=doc.id, company_id=COMPANY_A)
            .one()
        )
        assert chunk.content == ARTICLE
        assert chunk.chunk_index == 0

    def test_publish_is_idempotent(self, in_memory_db):
        db = in_memory_db()
        _seed_draft(db)

        first = gw_service.publish_draft_to_knowledge(db, COMPANY_A, "d-pub")
        second = gw_service.publish_draft_to_knowledge(db, COMPANY_A, "d-pub")

        assert first.id == second.id
        assert db.query(KnowledgeDocument).filter_by(
            company_id=COMPANY_A, category="ghostwriter",
        ).count() == 1
        assert db.query(DocumentChunk).filter_by(
            company_id=COMPANY_A,
        ).count() == 1

    def test_unapproved_draft_is_never_published(self, in_memory_db):
        db = in_memory_db()
        _seed_draft(db, draft_id="d-wip", status="draft")

        assert gw_service.publish_draft_to_knowledge(
            db, COMPANY_A, "d-wip",
        ) is None
        assert db.query(KnowledgeDocument).count() == 0

    def test_rejected_draft_is_never_published(self, in_memory_db):
        db = in_memory_db()
        _seed_draft(db, draft_id="d-rej", status="rejected")

        assert gw_service.publish_draft_to_knowledge(
            db, COMPANY_A, "d-rej",
        ) is None
        assert db.query(KnowledgeDocument).count() == 0

    def test_company_lock_other_clients_draft_is_invisible(self, in_memory_db):
        db = in_memory_db()
        _seed_draft(db, draft_id="d-b", company_id=COMPANY_B)

        assert gw_service.publish_draft_to_knowledge(
            db, COMPANY_A, "d-b",
        ) is None                                   # A cannot touch B's draft
        assert db.query(KnowledgeDocument).count() == 0

    def test_empty_article_is_skipped_honestly(self, in_memory_db):
        db = in_memory_db()
        _seed_draft(db, draft_id="d-empty", content="   ")

        assert gw_service.publish_draft_to_knowledge(
            db, COMPANY_A, "d-empty",
        ) is None
        assert db.query(KnowledgeDocument).count() == 0

    def test_missing_draft_returns_none(self, in_memory_db):
        db = in_memory_db()
        assert gw_service.publish_draft_to_knowledge(
            db, COMPANY_A, "does-not-exist",
        ) is None


class TestNode3Visibility:
    def test_published_article_matches_node3_query_shape(self, in_memory_db):
        """The live pipeline's tier-2 KB fetch queries:
        KnowledgeDocument(company_id == tenant, status == "completed")
        → DocumentChunk(company_id == tenant, document_id.in_(doc_ids)).
        This test runs THAT exact shape and expects the article back."""
        db = in_memory_db()
        _seed_draft(db)
        doc = gw_service.publish_draft_to_knowledge(db, COMPANY_A, "d-pub")
        assert doc is not None

        docs = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id == COMPANY_A,
                KnowledgeDocument.status == "completed",
            )
            .all()
        )
        doc_ids = [d.id for d in docs]
        chunks = (
            db.query(DocumentChunk)
            .filter(
                DocumentChunk.company_id == COMPANY_A,
                DocumentChunk.document_id.in_(doc_ids),
            )
            .all()
        )

        assert len(chunks) == 1
        assert "every Friday" in chunks[0].content

    def test_other_company_cannot_see_published_article(self, in_memory_db):
        db = in_memory_db()
        _seed_draft(db)
        doc = gw_service.publish_draft_to_knowledge(db, COMPANY_A, "d-pub")
        assert doc is not None

        leaks = (
            db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.company_id == COMPANY_B,
                KnowledgeDocument.status == "completed",
            )
            .all()
        )
        assert leaks == []


class TestApproveAndPublish:
    def test_approve_publishes_and_reports_honestly(self, in_memory_db):
        db = in_memory_db()
        _seed_draft(db, draft_id="d-api", status="draft")

        result = gw_service.approve_and_publish(db, COMPANY_A, "d-api")

        assert result["status"] == "approved"
        assert result["published"] is True
        assert result["publish_error"] is None

    def test_missing_draft_reports_not_found(self, in_memory_db):
        db = in_memory_db()
        result = gw_service.approve_and_publish(db, COMPANY_A, "nope")
        assert result["id"] is None
        assert result["published"] is False

    def test_publish_failure_does_not_undo_approval(self, in_memory_db, monkeypatch):
        db = in_memory_db()
        _seed_draft(db, draft_id="d-boom", status="draft")

        def _boom(*args, **kwargs):
            raise RuntimeError("knowledge store down")

        monkeypatch.setattr(gw_service, "publish_draft_to_knowledge", _boom)
        result = gw_service.approve_and_publish(db, COMPANY_A, "d-boom")

        assert result["status"] == "approved"        # human decision stands
        assert result["published"] is False          # reported honestly
        assert "knowledge store down" in result["publish_error"]
