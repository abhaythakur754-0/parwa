"""
Knowledge Base Indexer Worker.

Handles indexing documents in the knowledge base.

Features:
- Index documents for search
- Reindex all documents
- Verify index integrity
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid
import hashlib

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class IndexStatus(str, Enum):
    """Status of indexing operation."""
    PENDING = "pending"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class IndexRecord:
    """Record of an indexing operation."""
    index_id: str
    doc_id: str
    company_id: str
    status: IndexStatus
    indexed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    chunk_count: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class KBIndexerWorker:
    """
    Worker for indexing knowledge base documents.

    Features:
    - Index documents for search
    - Reindex all documents
    - Verify index integrity

    Example:
        worker = KBIndexerWorker()
        result = await worker.index_document("doc_123")
    """

    def __init__(self) -> None:
        """Initialize KB Indexer Worker."""
        self._indices: Dict[str, IndexRecord] = {}
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._company_docs: Dict[str, List[str]] = {}

        logger.info({
            "event": "kb_indexer_worker_initialized"
        })

    async def index_document(
        self,
        doc_id: str,
        company_id: str = "default",
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Index a document in the knowledge base.

        Args:
            doc_id: Document identifier
            company_id: Company identifier
            content: Document content (optional, for testing)
            metadata: Additional metadata

        Returns:
            Dict with indexing result
        """
        index_id = f"idx_{uuid.uuid4().hex[:8]}"

        logger.info({
            "event": "document_indexing_started",
            "index_id": index_id,
            "doc_id": doc_id,
            "company_id": company_id
        })

        record = IndexRecord(
            index_id=index_id,
            doc_id=doc_id,
            company_id=company_id,
            status=IndexStatus.INDEXING,
            metadata=metadata or {}
        )

        try:
            # Simulate indexing process
            # In production, this would:
            # 1. Chunk the document
            # 2. Generate embeddings
            # 3. Store in vector database

            await asyncio.sleep(0.01)

            # Calculate chunk count based on content
            if content:
                chunk_count = max(1, len(content) // 500)
            else:
                chunk_count = 1

            record.chunk_count = chunk_count
            record.status = IndexStatus.COMPLETED
            record.indexed_at = datetime.now(timezone.utc)

            self._indices[index_id] = record

            # Track company documents
            if company_id not in self._company_docs:
                self._company_docs[company_id] = []
            if doc_id not in self._company_docs[company_id]:
                self._company_docs[company_id].append(doc_id)

            # Store document
            self._documents[doc_id] = {
                "doc_id": doc_id,
                "company_id": company_id,
                "content_hash": hashlib.md5((content or "").encode()).hexdigest()[:16],
                "chunk_count": chunk_count,
                "indexed_at": record.indexed_at.isoformat(),
                "metadata": metadata or {}
            }

            logger.info({
                "event": "document_indexed",
                "index_id": index_id,
                "doc_id": doc_id,
                "chunk_count": chunk_count
            })

            return {
                "success": True,
                "status": IndexStatus.COMPLETED.value,
                "index_id": index_id,
                "doc_id": doc_id,
                "company_id": company_id,
                "chunk_count": chunk_count,
                "indexed_at": record.indexed_at.isoformat()
            }

        except Exception as e:
            record.status = IndexStatus.FAILED
            record.error = str(e)
            self._indices[index_id] = record

            logger.error({
                "event": "document_indexing_failed",
                "index_id": index_id,
                "doc_id": doc_id,
                "error": str(e)
            })

            return {
                "success": False,
                "status": IndexStatus.FAILED.value,
                "error": str(e),
                "index_id": index_id
            }

    async def reindex_all(
        self,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Reindex all documents for a company.

        Args:
            company_id: Company identifier

        Returns:
            Dict with reindex result
        """
        logger.info({
            "event": "reindex_all_started",
            "company_id": company_id
        })

        doc_ids = self._company_docs.get(company_id, [])

        if not doc_ids:
            return {
                "success": True,
                "message": "No documents to reindex",
                "company_id": company_id,
                "documents_processed": 0
            }

        results = []
        success_count = 0
        failure_count = 0

        for doc_id in doc_ids:
            result = await self.index_document(doc_id, company_id)
            results.append(result)

            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1

        logger.info({
            "event": "reindex_all_completed",
            "company_id": company_id,
            "success_count": success_count,
            "failure_count": failure_count
        })

        return {
            "success": failure_count == 0,
            "company_id": company_id,
            "documents_processed": len(doc_ids),
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results
        }

    async def verify_index(
        self,
        doc_id: str
    ) -> bool:
        """
        Verify that a document is properly indexed.

        Args:
            doc_id: Document to verify

        Returns:
            True if document is properly indexed
        """
        doc = self._documents.get(doc_id)

        if not doc:
            logger.warning({
                "event": "verify_index_not_found",
                "doc_id": doc_id
            })
            return False

        # Check if document has required fields
        required_fields = ["doc_id", "company_id", "indexed_at"]
        for field in required_fields:
            if field not in doc:
                logger.warning({
                    "event": "verify_index_missing_field",
                    "doc_id": doc_id,
                    "missing_field": field
                })
                return False

        # Mark as verified
        for record in self._indices.values():
            if record.doc_id == doc_id:
                record.verified_at = datetime.now(timezone.utc)
                record.status = IndexStatus.VERIFIED
                break

        logger.info({
            "event": "index_verified",
            "doc_id": doc_id
        })

        return True

    async def delete_document(
        self,
        doc_id: str,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Delete a document from the index.

        Args:
            doc_id: Document to delete
            company_id: Company identifier

        Returns:
            Dict with deletion result
        """
        logger.info({
            "event": "document_deletion_started",
            "doc_id": doc_id,
            "company_id": company_id
        })

        if doc_id in self._documents:
            del self._documents[doc_id]

        if company_id in self._company_docs:
            if doc_id in self._company_docs[company_id]:
                self._company_docs[company_id].remove(doc_id)

        # Remove index records
        indices_to_remove = [
            idx for idx, rec in self._indices.items()
            if rec.doc_id == doc_id
        ]
        for idx in indices_to_remove:
            del self._indices[idx]

        logger.info({
            "event": "document_deleted",
            "doc_id": doc_id
        })

        return {
            "success": True,
            "doc_id": doc_id,
            "company_id": company_id
        }

    def get_document(
        self,
        doc_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get document by ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document data or None
        """
        return self._documents.get(doc_id)

    def get_company_documents(
        self,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all documents for a company.

        Args:
            company_id: Company identifier

        Returns:
            List of documents
        """
        doc_ids = self._company_docs.get(company_id, [])
        return [
            self._documents[doc_id]
            for doc_id in doc_ids
            if doc_id in self._documents
        ]

    def get_status(self) -> Dict[str, Any]:
        """
        Get worker status.

        Returns:
            Dict with status information
        """
        return {
            "worker_type": "kb_indexer",
            "total_documents": len(self._documents),
            "total_indices": len(self._indices),
            "companies_with_docs": len(self._company_docs)
        }


# ARQ worker function
async def index_document(
    ctx: Dict[str, Any],
    doc_id: str,
    company_id: str = "default"
) -> Dict[str, Any]:
    """
    ARQ worker function for indexing documents.

    Args:
        ctx: ARQ context
        doc_id: Document to index
        company_id: Company identifier

    Returns:
        Indexing result
    """
    worker = KBIndexerWorker()
    return await worker.index_document(doc_id, company_id)


def get_kb_indexer_worker() -> KBIndexerWorker:
    """
    Get a KBIndexerWorker instance.

    Returns:
        KBIndexerWorker instance
    """
    return KBIndexerWorker()
