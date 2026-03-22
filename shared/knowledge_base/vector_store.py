"""
PARWA Vector Store.

Provides vector storage and retrieval using pgvector-compatible storage.
Supports embedding storage, similarity search, and metadata filtering.
"""
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone
import json
import hashlib

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class Document(BaseModel):
    """
    Document model for knowledge base storage.

    Represents a single document with content, embedding, and metadata.
    """
    id: UUID = Field(default_factory=uuid4)
    content: str
    embedding: Optional[List[float]] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    company_id: Optional[UUID] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    model_config = ConfigDict(use_enum_values=True)


class SearchResult(BaseModel):
    """
    Search result from vector similarity query.

    Contains the matched document and relevance score.
    """
    document: Document
    score: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=True)


class VectorStore:
    """
    Vector Store for embedding storage and retrieval.

    Features:
    - Store documents with embeddings
    - Similarity search using cosine distance
    - Company-scoped data isolation
    - Metadata filtering
    - Mock storage for testing (no external DB required)
    """

    DEFAULT_EMBEDDING_DIMENSION = 1536

    def __init__(
        self,
        embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Vector Store.

        Args:
            embedding_dimension: Dimension of embedding vectors (default 1536 for OpenAI)
            company_id: Company UUID for data isolation
        """
        self.embedding_dimension = embedding_dimension
        self.company_id = company_id
        self._documents: Dict[UUID, Document] = {}
        self._embedding_index: Dict[str, UUID] = {}  # Hash -> UUID mapping

        logger.info({
            "event": "vector_store_initialized",
            "embedding_dimension": embedding_dimension,
            "company_id": str(company_id) if company_id else None,
        })

    def add_document(
        self,
        content: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[UUID] = None
    ) -> Document:
        """
        Add a document to the vector store.

        Args:
            content: Document text content
            embedding: Pre-computed embedding vector
            metadata: Additional metadata
            document_id: Optional document ID (auto-generated if not provided)

        Returns:
            Created Document instance

        Raises:
            ValueError: If content is empty or embedding dimension mismatch
        """
        if not content or not content.strip():
            raise ValueError("Document content cannot be empty")

        if embedding and len(embedding) != self.embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dimension}, "
                f"got {len(embedding)}"
            )

        doc_id = document_id or uuid4()

        document = Document(
            id=doc_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            company_id=self.company_id,
        )

        self._documents[doc_id] = document

        # Create hash index for content
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        self._embedding_index[content_hash] = doc_id

        logger.info({
            "event": "document_added",
            "document_id": str(doc_id),
            "company_id": str(self.company_id) if self.company_id else None,
            "has_embedding": embedding is not None,
            "content_length": len(content),
        })

        return document

    def get_document(self, document_id: UUID) -> Optional[Document]:
        """
        Retrieve a document by ID.

        Args:
            document_id: Document UUID

        Returns:
            Document if found, None otherwise
        """
        doc = self._documents.get(document_id)

        # Enforce company isolation
        if doc and self.company_id and doc.company_id != self.company_id:
            logger.warning({
                "event": "document_access_denied",
                "document_id": str(document_id),
                "requested_company": str(self.company_id),
                "document_company": str(doc.company_id) if doc.company_id else None,
            })
            return None

        return doc

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """
        Search for similar documents using embedding.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            metadata_filter: Optional metadata filters
            min_score: Minimum similarity score threshold

        Returns:
            List of SearchResult sorted by score descending

        Raises:
            ValueError: If query embedding dimension mismatch
        """
        if len(query_embedding) != self.embedding_dimension:
            raise ValueError(
                f"Query embedding dimension mismatch: expected "
                f"{self.embedding_dimension}, got {len(query_embedding)}"
            )

        if top_k <= 0:
            raise ValueError("top_k must be positive")

        results: List[SearchResult] = []

        for doc in self._documents.values():
            # Skip documents without embeddings
            if doc.embedding is None:
                continue

            # Enforce company isolation
            if self.company_id and doc.company_id != self.company_id:
                continue

            # Apply metadata filter
            if metadata_filter and not self._matches_filter(
                doc.metadata, metadata_filter
            ):
                continue

            # Calculate cosine similarity
            score = self._cosine_similarity(query_embedding, doc.embedding)

            # Apply minimum score threshold
            if score < min_score:
                continue

            results.append(SearchResult(document=doc, score=score))

        # Sort by score descending and limit to top_k
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:top_k]

        logger.info({
            "event": "search_completed",
            "query_dimension": len(query_embedding),
            "top_k": top_k,
            "results_count": len(results),
            "company_id": str(self.company_id) if self.company_id else None,
        })

        return results

    def search_by_text(
        self,
        query: str,
        embedding_fn: Any,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for similar documents using text query.

        Args:
            query: Text query
            embedding_fn: Function to generate embedding from text
            top_k: Number of results to return
            metadata_filter: Optional metadata filters

        Returns:
            List of SearchResult sorted by score descending
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        try:
            query_embedding = embedding_fn(query)
            return self.search(
                query_embedding=query_embedding,
                top_k=top_k,
                metadata_filter=metadata_filter
            )
        except Exception as e:
            logger.error({
                "event": "embedding_generation_failed",
                "error": str(e),
                "query_length": len(query),
            })
            raise

    def delete_document(self, document_id: UUID) -> bool:
        """
        Delete a document from the store.

        Args:
            document_id: Document UUID

        Returns:
            True if deleted, False if not found
        """
        doc = self._documents.get(document_id)

        if not doc:
            return False

        # Enforce company isolation
        if self.company_id and doc.company_id != self.company_id:
            logger.warning({
                "event": "document_delete_denied",
                "document_id": str(document_id),
            })
            return False

        # Remove from index
        content_hash = hashlib.sha256(doc.content.encode()).hexdigest()
        self._embedding_index.pop(content_hash, None)

        # Remove document
        del self._documents[document_id]

        logger.info({
            "event": "document_deleted",
            "document_id": str(document_id),
        })

        return True

    def count_documents(self) -> int:
        """
        Count total documents in the store.

        Returns:
            Number of documents
        """
        if self.company_id:
            return sum(
                1 for doc in self._documents.values()
                if doc.company_id == self.company_id
            )
        return len(self._documents)

    def clear(self) -> int:
        """
        Clear all documents from the store.

        Returns:
            Number of documents cleared
        """
        count = len(self._documents)
        self._documents.clear()
        self._embedding_index.clear()

        logger.info({
            "event": "vector_store_cleared",
            "documents_cleared": count,
        })

        return count

    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        similarity = dot_product / (magnitude1 * magnitude2)

        # Normalize to 0-1 range (cosine similarity can be -1 to 1)
        # Clamp to [0, 1] to handle floating point precision errors
        normalized = (similarity + 1) / 2
        return max(0.0, min(1.0, normalized))

    def _matches_filter(
        self,
        metadata: Dict[str, Any],
        filter_dict: Dict[str, Any]
    ) -> bool:
        """
        Check if metadata matches filter criteria.

        Args:
            metadata: Document metadata
            filter_dict: Filter criteria

        Returns:
            True if all filters match
        """
        for key, value in filter_dict.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.

        Returns:
            Dict with store statistics
        """
        docs_with_embeddings = sum(
            1 for doc in self._documents.values()
            if doc.embedding is not None
        )

        return {
            "total_documents": len(self._documents),
            "documents_with_embeddings": docs_with_embeddings,
            "embedding_dimension": self.embedding_dimension,
            "company_id": str(self.company_id) if self.company_id else None,
        }
