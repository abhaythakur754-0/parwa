"""
PARWA Knowledge Retriever

Retrieves relevant document chunks from the knowledge base.
Tenant-scoped (BC-001).

Currently uses SQL LIKE search on DocumentChunk.content as a
placeholder.  Will be upgraded to pgvector cosine similarity in
Week 9 Day 7-8.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from database.models.onboarding import DocumentChunk, KnowledgeDocument

logger = logging.getLogger("parwa.knowledge_base.retriever")


class KnowledgeRetriever:
    """Retrieve relevant knowledge base chunks for a given tenant.

    BC-001: Every query is filtered by ``company_id`` — no cross-tenant
    data is ever returned.
    """

    def __init__(self, db: Session, company_id: str) -> None:
        self.db = db
        self.company_id = company_id

    # ── Public API ──────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        max_results: int = 5,
        intent_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search knowledge base for chunks matching *query*.

        Placeholder implementation using SQL ``ILIKE``.  Results are
        ordered by most recent chunk creation.  Once pgvector is
        connected, this will switch to cosine similarity ranking.

        Args:
            query: Search query text.
            max_results: Maximum number of results to return.
            intent_type: Optional intent filter (reserved for future use).

        Returns:
            List of dicts with keys:
            chunk_id, content, document_id, document_title,
            relevance_score, source.
        """
        if not query or not query.strip():
            return []

        # Sanitize query for LIKE pattern (escape % and _)
        like_term = _escape_like(query.strip())

        # Build base query: only completed documents, scoped to tenant
        base = (
            self.db.query(
                DocumentChunk,
                KnowledgeDocument.filename,
                KnowledgeDocument.category,
            )
            .join(
                KnowledgeDocument,
                DocumentChunk.document_id == KnowledgeDocument.id,
            )
            .filter(
                DocumentChunk.company_id == self.company_id,
                KnowledgeDocument.company_id == self.company_id,
                KnowledgeDocument.status == "completed",
            )
        )

        # LIKE search on chunk content (split query into words for better
        # coverage)
        words = like_term.split()
        if words:
            conditions = [DocumentChunk.content.ilike(f"%{word}%") for word in words]
            base = base.filter(or_(*conditions))

        # Order by most recent (placeholder — pgvector will use cosine
        # similarity)
        results = base.order_by(desc(DocumentChunk.created_at)).limit(max_results).all()

        # Compute a naive relevance score based on word matches
        out: List[Dict[str, Any]] = []
        for chunk, doc_filename, doc_category in results:
            score = _compute_relevance_score(query, chunk.content)

            out.append(
                {
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "document_id": chunk.document_id,
                    "document_title": doc_filename,
                    "relevance_score": score,
                    "source": doc_filename,
                    "category": doc_category,
                    "chunk_index": chunk.chunk_index,
                }
            )

        # Sort by relevance descending (best first)
        out.sort(key=lambda r: r["relevance_score"], reverse=True)

        return out

    def get_document_chunks(
        self,
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document.

        Filtered by ``company_id`` (BC-001).

        Args:
            document_id: KnowledgeDocument UUID.

        Returns:
            List of dicts with keys: chunk_id, content, chunk_index,
            char_count, has_embedding, created_at.
        """
        chunks = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.company_id == self.company_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        return [
            {
                "chunk_id": c.id,
                "content": c.content,
                "chunk_index": c.chunk_index,
                "char_count": len(c.content) if c.content else 0,
                "has_embedding": c.embedding is not None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in chunks
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics for the current tenant.

        Returns:
            Dict with total_documents, total_chunks,
            documents_by_status.
        """
        # Total documents
        total_documents = (
            self.db.query(func.count(KnowledgeDocument.id))
            .filter(KnowledgeDocument.company_id == self.company_id)
            .scalar()
            or 0
        )

        # Total chunks
        total_chunks = (
            self.db.query(func.count(DocumentChunk.id))
            .filter(DocumentChunk.company_id == self.company_id)
            .scalar()
            or 0
        )

        # Documents with embeddings
        embedded_chunks = (
            self.db.query(func.count(DocumentChunk.id))
            .filter(
                DocumentChunk.company_id == self.company_id,
                DocumentChunk.embedding.isnot(None),
            )
            .scalar()
            or 0
        )

        # Documents by status
        status_rows = (
            self.db.query(
                KnowledgeDocument.status,
                func.count(KnowledgeDocument.id),
            )
            .filter(KnowledgeDocument.company_id == self.company_id)
            .group_by(KnowledgeDocument.status)
            .all()
        )

        documents_by_status = {row.status: row.count for row in status_rows}

        return {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "documents_by_status": documents_by_status,
        }


# ── Module-level Helpers ────────────────────────────────────────────────


def _escape_like(term: str) -> str:
    """Escape SQL LIKE wildcards in *term*."""
    return term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _compute_relevance_score(query: str, content: str) -> float:
    """Compute a naive relevance score (0-1) based on word overlap.

    This is a placeholder.  pgvector cosine similarity will replace this.
    """
    query_words = set(query.lower().split())
    content_lower = content.lower()
    content_words = set(content_lower.split())

    if not query_words:
        return 0.0

    # Exact word overlap
    matches = query_words & content_words
    word_score = len(matches) / len(query_words)

    # Bonus for substring matches
    substring_hits = 0
    for w in query_words:
        if w in content_lower:
            substring_hits += 1
    substring_score = substring_hits / len(query_words)

    return round(min((word_score * 0.7 + substring_score * 0.3), 1.0), 4)
