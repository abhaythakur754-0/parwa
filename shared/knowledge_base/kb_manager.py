"""
PARWA Knowledge Base Manager.

Manages knowledge base operations including document ingestion,
retrieval, and maintenance. Coordinates with VectorStore for
embedding-based operations.
"""
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID, uuid4
from datetime import datetime, timezone
import json

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.knowledge_base.vector_store import (
    VectorStore,
    Document,
    SearchResult,
)

logger = get_logger(__name__)


class KnowledgeBaseConfig(BaseModel):
    """
    Configuration for Knowledge Base Manager.
    """
    embedding_dimension: int = Field(default=1536)
    default_top_k: int = Field(default=5, ge=1, le=100)
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0)
    max_chunk_size: int = Field(default=1000, ge=100)
    chunk_overlap: int = Field(default=100, ge=0)
    enable_deduplication: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class IngestResult(BaseModel):
    """
    Result of document ingestion.
    """
    document_id: UUID
    content: str
    chunk_count: int = Field(default=1)
    status: str = "success"
    message: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class KnowledgeBaseManager:
    """
    Knowledge Base Manager for document operations.

    Features:
    - Document ingestion with chunking
    - Semantic search with configurable top-k
    - Company-scoped knowledge isolation
    - Document deduplication
    - Batch operations support
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        config: Optional[KnowledgeBaseConfig] = None,
        company_id: Optional[UUID] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None
    ) -> None:
        """
        Initialize Knowledge Base Manager.

        Args:
            vector_store: VectorStore instance (created if not provided)
            config: KB configuration
            company_id: Company UUID for data isolation
            embedding_fn: Function to generate embeddings from text
        """
        self.config = config or KnowledgeBaseConfig()
        self.company_id = company_id
        self.embedding_fn = embedding_fn

        self.vector_store = vector_store or VectorStore(
            embedding_dimension=self.config.embedding_dimension,
            company_id=company_id
        )

        logger.info({
            "event": "kb_manager_initialized",
            "company_id": str(company_id) if company_id else None,
            "config": self.config.model_dump(),
        })

    def ingest_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        auto_chunk: bool = True
    ) -> IngestResult:
        """
        Ingest a document into the knowledge base.

        Args:
            content: Document text content
            metadata: Additional metadata
            auto_chunk: Whether to chunk large documents

        Returns:
            IngestResult with document ID and status

        Raises:
            ValueError: If content is empty
        """
        if not content or not content.strip():
            raise ValueError("Document content cannot be empty")

        # Clean content
        content = content.strip()
        metadata = metadata or {}
        metadata["company_id"] = str(self.company_id) if self.company_id else None
        metadata["ingested_at"] = datetime.now(timezone.utc).isoformat()

        # Check for deduplication
        if self.config.enable_deduplication:
            existing = self._find_duplicate(content)
            if existing:
                logger.info({
                    "event": "document_duplicate_skipped",
                    "existing_id": str(existing.id),
                })
                return IngestResult(
                    document_id=existing.id,
                    content=content,
                    status="skipped",
                    message="Duplicate document detected"
                )

        # Chunk if necessary
        chunks = [content]
        if auto_chunk and len(content) > self.config.max_chunk_size:
            chunks = self._chunk_text(content)

        # Generate embeddings for each chunk
        document_id = uuid4()
        chunk_count = len(chunks)

        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **metadata,
                "chunk_index": i,
                "total_chunks": chunk_count,
                "parent_document_id": str(document_id),
            }

            embedding = None
            if self.embedding_fn:
                try:
                    embedding = self.embedding_fn(chunk)
                except Exception as e:
                    logger.error({
                        "event": "embedding_generation_failed",
                        "error": str(e),
                        "chunk_index": i,
                    })

            self.vector_store.add_document(
                content=chunk,
                embedding=embedding,
                metadata=chunk_metadata
            )

        logger.info({
            "event": "document_ingested",
            "document_id": str(document_id),
            "content_length": len(content),
            "chunk_count": chunk_count,
        })

        return IngestResult(
            document_id=document_id,
            content=content,
            chunk_count=chunk_count,
            status="success"
        )

    def ingest_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[IngestResult]:
        """
        Ingest multiple documents.

        Args:
            documents: List of dicts with 'content' and optional 'metadata'

        Returns:
            List of IngestResult for each document
        """
        results: List[IngestResult] = []

        for doc in documents:
            try:
                result = self.ingest_document(
                    content=doc.get("content", ""),
                    metadata=doc.get("metadata"),
                    auto_chunk=doc.get("auto_chunk", True)
                )
                results.append(result)
            except Exception as e:
                logger.error({
                    "event": "batch_ingest_error",
                    "error": str(e),
                })
                results.append(IngestResult(
                    document_id=uuid4(),
                    content=doc.get("content", "")[:100],
                    status="error",
                    message=str(e)
                ))

        success_count = sum(1 for r in results if r.status == "success")
        logger.info({
            "event": "batch_ingest_complete",
            "total_documents": len(documents),
            "successful": success_count,
            "failed": len(documents) - success_count,
        })

        return results

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        min_score: Optional[float] = None
    ) -> List[SearchResult]:
        """
        Search the knowledge base.

        Args:
            query: Search query text
            top_k: Number of results (uses config default if not provided)
            metadata_filter: Metadata filters to apply
            min_score: Minimum relevance score

        Returns:
            List of SearchResult sorted by relevance

        Raises:
            ValueError: If query is empty or embedding function not set
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        if not self.embedding_fn:
            raise ValueError(
                "Embedding function required for search. "
                "Initialize KnowledgeBaseManager with embedding_fn parameter."
            )

        top_k = top_k or self.config.default_top_k
        min_score = min_score or self.config.min_relevance_score

        try:
            query_embedding = self.embedding_fn(query)
        except Exception as e:
            logger.error({
                "event": "search_embedding_failed",
                "error": str(e),
            })
            raise

        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            metadata_filter=metadata_filter,
            min_score=min_score
        )

        logger.info({
            "event": "search_completed",
            "query_length": len(query),
            "results_count": len(results),
            "top_k": top_k,
        })

        return results

    def get_document(self, document_id: UUID) -> Optional[Document]:
        """
        Retrieve a document by ID.

        Args:
            document_id: Document UUID

        Returns:
            Document if found, None otherwise
        """
        return self.vector_store.get_document(document_id)

    def delete_document(self, document_id: UUID) -> bool:
        """
        Delete a document from the knowledge base.

        Args:
            document_id: Document UUID

        Returns:
            True if deleted, False if not found
        """
        return self.vector_store.delete_document(document_id)

    def update_document(
        self,
        document_id: UUID,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Document]:
        """
        Update a document's content or metadata.

        Args:
            document_id: Document UUID
            content: New content (optional)
            metadata: New metadata (optional, merged with existing)

        Returns:
            Updated Document if found, None otherwise
        """
        doc = self.vector_store.get_document(document_id)
        if not doc:
            return None

        # Update content
        if content:
            doc.content = content
            doc.updated_at = datetime.now(timezone.utc)

            # Regenerate embedding
            if self.embedding_fn:
                try:
                    doc.embedding = self.embedding_fn(content)
                except Exception as e:
                    logger.error({
                        "event": "update_embedding_failed",
                        "error": str(e),
                    })

        # Update metadata
        if metadata:
            doc.metadata = {**doc.metadata, **metadata}
            doc.updated_at = datetime.now(timezone.utc)

        logger.info({
            "event": "document_updated",
            "document_id": str(document_id),
            "content_updated": content is not None,
            "metadata_updated": metadata is not None,
        })

        return doc

    def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.

        Returns:
            Dict with KB statistics
        """
        store_stats = self.vector_store.get_stats()

        return {
            **store_stats,
            "company_id": str(self.company_id) if self.company_id else None,
            "config": self.config.model_dump(),
            "has_embedding_fn": self.embedding_fn is not None,
        }

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        chunks: List[str] = []
        start = 0
        chunk_size = self.config.max_chunk_size
        overlap = self.config.chunk_overlap

        while start < len(text):
            end = start + chunk_size

            # Try to find a good break point
            if end < len(text):
                # Look for paragraph break
                break_point = text.rfind("\n\n", start, end)
                if break_point > start:
                    end = break_point
                else:
                    # Look for sentence break
                    break_point = text.rfind(". ", start, end)
                    if break_point > start:
                        end = break_point + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - overlap if end < len(text) else end

        return chunks

    def _find_duplicate(self, content: str) -> Optional[Document]:
        """
        Find a duplicate document by content hash.

        Args:
            content: Content to check

        Returns:
            Existing Document if duplicate found, None otherwise
        """
        import hashlib

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        for doc in self.vector_store._documents.values():
            if self.company_id and doc.company_id != self.company_id:
                continue

            doc_hash = hashlib.sha256(doc.content.encode()).hexdigest()
            if doc_hash == content_hash:
                return doc

        return None
