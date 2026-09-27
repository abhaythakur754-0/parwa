"""
PARWA Shared Knowledge Base Module

Centralized knowledge base functionality:
- Document ingestion and chunking
- Embedding generation (via EmbeddingService)
- Retrieval and search
- Re-indexing management

All operations are tenant-scoped via company_id (BC-001).
"""

from app.shared.knowledge_base.manager import KnowledgeBaseManager
from app.shared.knowledge_base.chunker import DocumentChunker
from app.shared.knowledge_base.retriever import KnowledgeRetriever

# G1 FIX: These modules were missing, causing ImportError in rag_retrieval.py
from shared.knowledge_base.vector_search import (
    EMBEDDING_DIMENSION,
    VectorStore,
    MockVectorStore,
    get_vector_store,
)
from shared.knowledge_base.reindexing import (
    ReindexJob,
    ReindexingManager,
    ReindexStatus,
)

__all__ = [
    "KnowledgeBaseManager",
    "DocumentChunker",
    "KnowledgeRetriever",
    "EMBEDDING_DIMENSION",
    "VectorStore",
    "MockVectorStore",
    "get_vector_store",
    "ReindexJob",
    "ReindexingManager",
    "ReindexStatus",
]
