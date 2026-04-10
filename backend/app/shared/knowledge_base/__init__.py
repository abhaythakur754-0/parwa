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

__all__ = ["KnowledgeBaseManager", "DocumentChunker", "KnowledgeRetriever"]
