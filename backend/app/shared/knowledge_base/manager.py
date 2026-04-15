"""
PARWA Knowledge Base Manager

Orchestrates the full knowledge base pipeline:
1. Document ingestion (chunking)
2. Embedding generation
3. Storage
4. Retrieval
5. Re-indexing

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — embedding failures do not block ingestion.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import NotFoundError, ValidationError
from app.shared.knowledge_base.chunker import DocumentChunker
from app.shared.knowledge_base.retriever import KnowledgeRetriever
from database.models.onboarding import DocumentChunk, KnowledgeDocument

logger = logging.getLogger("parwa.knowledge_base.manager")

# ── Embedding API Constants ─────────────────────────────────────────────

# Google AI Studio embedding model
_EMBEDDING_MODEL = "text-embedding-004"
_EMBEDDING_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_EMBEDDING_TASK_TYPE = "RETRIEVAL_DOCUMENT"
_EMBEDDING_TIMEOUT_SEC = 30


class KnowledgeBaseManager:
    """High-level manager for the knowledge base pipeline.

    Usage::

        manager = KnowledgeBaseManager(db, company_id="abc-123")
        result = manager.ingest_document(doc_id, content, filename="faq.md")
        results = manager.search("how do I reset my password?")
    """

    def __init__(self, db: Session, company_id: str) -> None:
        self.db = db
        self.company_id = company_id
        self._chunker = DocumentChunker()
        self._retriever = KnowledgeRetriever(db, company_id)

    # ── Public API ──────────────────────────────────────────────────────

    def ingest_document(
        self,
        document_id: str,
        content: str,
        filename: str = "",
    ) -> Dict[str, Any]:
        """Ingest a document: chunk, embed, and store.

        Args:
            document_id: KnowledgeDocument UUID.
            content: Full text content of the document.
            filename: Original filename for metadata.

        Returns:
            Dict with keys: chunk_count, document_id, status.

        Raises:
            NotFoundError: If document not found for this tenant.
            ValidationError: If document status is invalid.
        """
        # Verify document exists and belongs to this tenant (BC-001)
        doc = self._get_document(document_id)

        # Update status to processing
        doc.status = "processing"
        doc.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        try:
            # Step 1: Chunk the content
            chunks = self._chunker.chunk_text(content, filename=filename)

            if not chunks:
                # Empty document — mark completed with 0 chunks
                doc.status = "completed"
                doc.chunk_count = 0
                doc.error_message = None
                doc.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                logger.info(
                    "ingest_empty_document",
                    document_id=document_id,
                    company_id=self.company_id,
                )
                return {
                    "chunk_count": 0,
                    "document_id": document_id,
                    "status": "completed",
                }

            # Step 2: Generate embeddings and store chunks
            stored_count = 0
            embedding_failures = 0

            for chunk_data in chunks:
                embedding: Optional[List[float]] = None

                # BC-008: Graceful degradation — embedding failure is
                # non-fatal.  Chunk is still stored for text-based search.
                try:
                    embedding = self._generate_embedding(chunk_data["content"])
                except Exception as exc:
                    logger.warning(
                        "embedding_generation_failed",
                        document_id=document_id,
                        chunk_index=chunk_data["chunk_index"],
                        error=str(exc),
                    )
                    embedding_failures += 1

                chunk = DocumentChunk(
                    document_id=document_id,
                    company_id=self.company_id,  # BC-001
                    content=chunk_data["content"],
                    chunk_index=chunk_data["chunk_index"],
                    embedding=(
                        json.dumps(embedding) if embedding else None
                    ),
                )
                self.db.add(chunk)
                stored_count += 1

            # Step 3: Update document status
            doc.status = "completed"
            doc.chunk_count = stored_count
            doc.error_message = None
            doc.updated_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(
                "ingest_document_completed",
                document_id=document_id,
                company_id=self.company_id,
                chunk_count=stored_count,
                embedding_failures=embedding_failures,
            )

            return {
                "chunk_count": stored_count,
                "document_id": document_id,
                "status": "completed",
                "embedding_failures": embedding_failures,
            }

        except Exception as exc:
            # Mark document as failed
            doc.status = "failed"
            doc.error_message = str(exc)[:500]
            doc.failed_at = datetime.now(timezone.utc)
            doc.updated_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.error(
                "ingest_document_failed",
                document_id=document_id,
                company_id=self.company_id,
                error=str(exc),
            )
            raise

    def reindex_document(self, document_id: str) -> Dict[str, Any]:
        """Delete existing chunks, re-chunk, and re-embed a document.

        Args:
            document_id: KnowledgeDocument UUID.

        Returns:
            Dict with keys: chunk_count, status.

        Raises:
            NotFoundError: If document not found for this tenant.
        """
        doc = self._get_document(document_id)

        # Get original content for re-chunking.
        # Content lives in existing chunks; extract from first chunk
        # or use the original content if available.
        existing_chunks = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.company_id == self.company_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        # Reconstruct content from existing chunks
        content = "\n\n".join(
            c.content for c in existing_chunks if c.content
        )

        # Delete existing chunks
        deleted_count = self.delete_document_chunks(document_id)

        logger.info(
            "reindex_document_started",
            document_id=document_id,
            company_id=self.company_id,
            chunks_deleted=deleted_count,
        )

        # Re-ingest
        result = self.ingest_document(
            document_id=document_id,
            content=content,
            filename=doc.filename,
        )

        result["chunks_deleted"] = deleted_count
        return result

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search the knowledge base.

        Delegates to :class:`KnowledgeRetriever`.

        Args:
            query: Search query text.
            max_results: Maximum number of results.

        Returns:
            List of relevance-ranked chunk dicts.
        """
        return self._retriever.search(query, max_results=max_results)

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics.

        Delegates to :class:`KnowledgeRetriever`.

        Returns:
            Dict with total_documents, total_chunks, documents_by_status.
        """
        return self._retriever.get_stats()

    def delete_document_chunks(self, document_id: str) -> int:
        """Soft-delete all chunks for a document.

        Removes chunks from the database (hard delete since they can
        be re-created via re-indexing).

        Args:
            document_id: KnowledgeDocument UUID.

        Returns:
            Number of chunks deleted.
        """
        count = (
            self.db.query(DocumentChunk)
            .filter(
                DocumentChunk.document_id == document_id,
                DocumentChunk.company_id == self.company_id,  # BC-001
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()

        logger.info(
            "delete_document_chunks",
            document_id=document_id,
            company_id=self.company_id,
            deleted_count=count,
        )

        return count

    # ── Private Helpers ─────────────────────────────────────────────────

    def _get_document(self, document_id: str) -> KnowledgeDocument:
        """Fetch a document owned by the current tenant.

        Args:
            document_id: KnowledgeDocument UUID.

        Returns:
            The KnowledgeDocument ORM instance.

        Raises:
            NotFoundError: If document not found or company_id mismatch.
        """
        doc = (
            self.db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.company_id == self.company_id,  # BC-001
            )
            .first()
        )

        if not doc:
            raise NotFoundError(
                f"KnowledgeDocument {document_id} not found",
                details={"document_id": document_id, "company_id": self.company_id},
            )

        return doc

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate a vector embedding using Google AI text-embedding-004.

        Uses a synchronous ``httpx`` call.  Returns ``None`` on any
        failure (BC-008 graceful degradation).

        Args:
            text: Text to embed (should fit within model context window).

        Returns:
            List[float] embedding vector, or ``None`` on failure.
        """
        # Truncate text to avoid exceeding API limits (~20k characters safe)
        truncated = text[:20000] if len(text) > 20000 else text

        if not truncated.strip():
            return None

        try:
            settings = get_settings()
            api_key = settings.GOOGLE_AI_API_KEY

            if not api_key:
                logger.warning("embedding_skipped_no_api_key")
                return None

            url = (
                f"{_EMBEDDING_API_BASE}/{_EMBEDDING_MODEL}:embedContent"
            )

            payload = {
                "model": f"models/{_EMBEDDING_MODEL}",
                "content": {
                    "parts": [{"text": truncated}],
                },
                "taskType": _EMBEDDING_TASK_TYPE,
            }

            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            }

            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=_EMBEDDING_TIMEOUT_SEC,
            )
            response.raise_for_status()

            data = response.json()
            embedding = (
                data.get("embedding", {})
                .get("values")
            )

            if not embedding or not isinstance(embedding, list):
                logger.warning(
                    "embedding_response_missing_values",
                    response_keys=list(data.keys()) if isinstance(data, dict) else "non-dict",
                )
                return None

            return embedding

        except httpx.TimeoutException:
            logger.warning("embedding_request_timeout")
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "embedding_http_error",
                status_code=exc.response.status_code,
                detail=exc.response.text[:200] if exc.response.text else "",
            )
            return None
        except Exception as exc:
            logger.warning(
                "embedding_generation_error",
                error=str(exc),
            )
            return None
