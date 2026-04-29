"""
PARWA Shared Knowledge Base Module

Centralized knowledge base functionality:
- Document ingestion and chunking
- Embedding generation (via EmbeddingService)
- Retrieval and search
- Re-indexing management

All operations are tenant-scoped via company_id (BC-001).

Bug Fix Day 4: Fixed imports to use ``app.shared`` instead of bare ``shared``
to avoid PYTHONPATH dependency issues.
"""

from app.shared.knowledge_base.chunker import DocumentChunker
from app.shared.knowledge_base.manager import KnowledgeBaseManager
from app.shared.knowledge_base.reindexing import (
    ReindexingManager,
    ReindexJob,
    ReindexStatus,
)
from app.shared.knowledge_base.retriever import KnowledgeRetriever

# G1 FIX + Bug Fix Day 4: Use app.shared path instead of bare shared path
from app.shared.knowledge_base.vector_search import (
    MockVectorStore,  # backwards-compat alias for InMemoryVectorStore
)
from app.shared.knowledge_base.vector_search import (
    EMBEDDING_DIMENSION,
    InMemoryVectorStore,
    PgVectorStore,
    VectorStore,
    get_vector_store,
)

__all__ = [
    "KnowledgeBaseManager",
    "DocumentChunker",
    "KnowledgeRetriever",
    "EMBEDDING_DIMENSION",
    "VectorStore",
    "InMemoryVectorStore",
    "MockVectorStore",  # backwards-compat alias
    "PgVectorStore",
    "get_vector_store",
    "ReindexJob",
    "ReindexingManager",
    "ReindexStatus",
]
