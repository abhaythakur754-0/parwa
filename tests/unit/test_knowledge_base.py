"""
Unit tests for Knowledge Base Module.
"""
import os
import uuid
import pytest
import numpy as np
from typing import List

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.knowledge_base.vector_store import (
    VectorStore,
    Document,
    SearchResult,
)
from shared.knowledge_base.kb_manager import (
    KnowledgeBaseManager,
    KnowledgeBaseConfig,
    IngestResult,
)
from shared.knowledge_base.hyde import (
    HyDEGenerator,
    HyDEConfig,
    HyDEResult,
)
from shared.knowledge_base.multi_query import (
    MultiQueryGenerator,
    MultiQueryConfig,
    MultiQueryResult,
    QueryVariation,
)
from shared.knowledge_base.rag_pipeline import (
    RAGPipeline,
    RAGConfig,
    RAGResponse,
)


def mock_embedding_fn(text: str) -> List[float]:
    """Mock embedding function for testing."""
    # Generate deterministic embedding based on text
    np.random.seed(hash(text) % (2**32))
    return list(np.random.randn(1536).astype(float))


class TestVectorStore:
    """Tests for Vector Store."""

    def test_vector_store_creation(self):
        """Test creating a vector store."""
        store = VectorStore()
        assert store.embedding_dimension == 1536
        assert store.count_documents() == 0

    def test_add_document(self):
        """Test adding a document."""
        store = VectorStore()
        doc = store.add_document(
            content="This is a test document about AI.",
            metadata={"source": "test"}
        )

        assert doc.id is not None
        assert doc.content == "This is a test document about AI."
        assert doc.metadata["source"] == "test"
        assert store.count_documents() == 1

    def test_add_document_with_embedding(self):
        """Test adding a document with embedding."""
        store = VectorStore()
        embedding = [0.1] * 1536

        doc = store.add_document(
            content="Test content",
            embedding=embedding
        )

        assert doc.embedding is not None
        assert len(doc.embedding) == 1536

    def test_add_document_empty_content_raises(self):
        """Test that empty content raises error."""
        store = VectorStore()

        with pytest.raises(ValueError, match="cannot be empty"):
            store.add_document(content="")

    def test_add_document_wrong_embedding_dimension(self):
        """Test that wrong embedding dimension raises error."""
        store = VectorStore(embedding_dimension=1536)

        with pytest.raises(ValueError, match="dimension mismatch"):
            store.add_document(
                content="Test",
                embedding=[0.1] * 100  # Wrong dimension
            )

    def test_get_document(self):
        """Test retrieving a document."""
        store = VectorStore()
        added = store.add_document(content="Test document")

        retrieved = store.get_document(added.id)
        assert retrieved is not None
        assert retrieved.content == "Test document"

    def test_get_nonexistent_document(self):
        """Test retrieving non-existent document."""
        store = VectorStore()

        retrieved = store.get_document(uuid.uuid4())
        assert retrieved is None

    def test_search(self):
        """Test similarity search."""
        store = VectorStore()

        # Add documents with known embeddings
        embedding1 = [1.0] * 1536  # All ones
        embedding2 = [-1.0] * 1536  # All negative ones

        store.add_document(content="Document 1", embedding=embedding1)
        store.add_document(content="Document 2", embedding=embedding2)

        # Search with similar embedding to doc 1
        query_embedding = [0.9] * 1536
        results = store.search(query_embedding, top_k=1)

        assert len(results) == 1
        assert results[0].document.content == "Document 1"

    def test_search_with_metadata_filter(self):
        """Test search with metadata filtering."""
        store = VectorStore()

        embedding = [0.5] * 1536
        store.add_document(
            content="Product A",
            embedding=embedding,
            metadata={"category": "electronics"}
        )
        store.add_document(
            content="Product B",
            embedding=embedding,
            metadata={"category": "clothing"}
        )

        results = store.search(
            query_embedding=embedding,
            top_k=10,
            metadata_filter={"category": "electronics"}
        )

        assert len(results) == 1
        assert results[0].document.metadata["category"] == "electronics"

    def test_delete_document(self):
        """Test deleting a document."""
        store = VectorStore()
        doc = store.add_document(content="To be deleted")

        result = store.delete_document(doc.id)
        assert result is True
        assert store.count_documents() == 0

    def test_get_stats(self):
        """Test getting store statistics."""
        store = VectorStore()
        store.add_document(content="Doc 1", embedding=[0.1] * 1536)
        store.add_document(content="Doc 2")  # No embedding

        stats = store.get_stats()
        assert stats["total_documents"] == 2
        assert stats["documents_with_embeddings"] == 1


class TestKnowledgeBaseManager:
    """Tests for Knowledge Base Manager."""

    def test_kb_manager_creation(self):
        """Test creating KB manager."""
        manager = KnowledgeBaseManager()
        assert manager.vector_store is not None
        assert manager.config is not None

    def test_ingest_document(self):
        """Test document ingestion."""
        manager = KnowledgeBaseManager(embedding_fn=mock_embedding_fn)

        result = manager.ingest_document(
            content="This is a comprehensive guide to machine learning.",
            metadata={"topic": "ML"}
        )

        assert result.status == "success"
        assert result.document_id is not None

    def test_ingest_empty_document_raises(self):
        """Test that empty content raises error."""
        manager = KnowledgeBaseManager()

        with pytest.raises(ValueError, match="cannot be empty"):
            manager.ingest_document(content="")

    def test_search_without_embedding_fn_raises(self):
        """Test search without embedding function."""
        manager = KnowledgeBaseManager()

        with pytest.raises(ValueError, match="Embedding function required"):
            manager.search("test query")

    def test_search_with_embedding_fn(self):
        """Test search with embedding function."""
        manager = KnowledgeBaseManager(embedding_fn=mock_embedding_fn)

        # Ingest some documents
        manager.ingest_document(content="Python is a programming language.")
        manager.ingest_document(content="JavaScript is also a programming language.")

        results = manager.search("programming")
        assert isinstance(results, list)

    def test_ingest_batch(self):
        """Test batch ingestion."""
        manager = KnowledgeBaseManager(embedding_fn=mock_embedding_fn)

        documents = [
            {"content": "Document 1 about AI"},
            {"content": "Document 2 about ML"},
            {"content": "Document 3 about DL"},
        ]

        results = manager.ingest_batch(documents)
        assert len(results) == 3
        assert all(r.status == "success" for r in results)

    def test_get_stats(self):
        """Test getting KB statistics."""
        manager = KnowledgeBaseManager(embedding_fn=mock_embedding_fn)
        manager.ingest_document(content="Test document")

        stats = manager.get_stats()
        assert "total_documents" in stats
        assert stats["has_embedding_fn"] is True


class TestHyDEGenerator:
    """Tests for HyDE Generator."""

    def test_hyde_generator_creation(self):
        """Test creating HyDE generator."""
        generator = HyDEGenerator()
        assert generator.config is not None

    def test_generate_without_llm(self):
        """Test generation without LLM (fallback)."""
        generator = HyDEGenerator(embedding_fn=mock_embedding_fn)

        result = generator.generate("What is machine learning?")

        assert result.query == "What is machine learning?"
        assert len(result.hypothetical_document) > 0
        assert result.embedding is not None

    def test_generate_empty_query_raises(self):
        """Test that empty query raises error."""
        generator = HyDEGenerator()

        with pytest.raises(ValueError, match="cannot be empty"):
            generator.generate("")

    def test_generate_different_styles(self):
        """Test generation with different styles."""
        generator = HyDEGenerator()

        detailed = generator.generate("What is AI?", style="detailed")
        concise = generator.generate("What is AI?", style="concise")
        technical = generator.generate("What is AI?", style="technical")

        assert detailed.hypothetical_document is not None
        assert concise.hypothetical_document is not None
        assert technical.hypothetical_document is not None

    def test_generate_batch(self):
        """Test batch generation."""
        generator = HyDEGenerator()

        queries = [
            "What is Python?",
            "What is JavaScript?",
            "What is Rust?"
        ]

        results = generator.generate_batch(queries)
        assert len(results) == 3

    def test_get_stats(self):
        """Test getting generator statistics."""
        generator = HyDEGenerator()
        generator.generate("Test query")

        stats = generator.get_stats()
        assert stats["generation_count"] == 1


class TestMultiQueryGenerator:
    """Tests for Multi-Query Generator."""

    def test_multi_query_generator_creation(self):
        """Test creating multi-query generator."""
        generator = MultiQueryGenerator()
        assert generator.config is not None

    def test_generate_variations(self):
        """Test generating query variations."""
        generator = MultiQueryGenerator()

        result = generator.generate("How do I reset my password?")

        assert result.original_query == "How do I reset my password?"
        assert len(result.variations) > 1
        assert result.total_queries > 1

    def test_generate_empty_query_raises(self):
        """Test that empty query raises error."""
        generator = MultiQueryGenerator()

        with pytest.raises(ValueError, match="cannot be empty"):
            generator.generate("")

    def test_get_all_queries(self):
        """Test extracting all query strings."""
        generator = MultiQueryGenerator()

        result = generator.generate("What is AI?")
        queries = generator.get_all_queries(result)

        assert "What is AI?" in queries
        assert len(queries) == result.total_queries

    def test_num_variations_config(self):
        """Test number of variations configuration."""
        config = MultiQueryConfig(num_variations=5)
        generator = MultiQueryGenerator(config=config)

        result = generator.generate("Test query")
        # +1 for original query if include_original is True
        assert result.total_queries <= 6


class TestRAGPipeline:
    """Tests for RAG Pipeline."""

    def test_rag_pipeline_creation(self):
        """Test creating RAG pipeline."""
        pipeline = RAGPipeline()
        assert pipeline.vector_store is not None
        assert pipeline.kb_manager is not None
        assert pipeline.config is not None

    def test_ingest_and_query(self):
        """Test document ingestion and query."""
        pipeline = RAGPipeline(embedding_fn=mock_embedding_fn)

        # Ingest documents
        pipeline.ingest("Python is a popular programming language.")
        pipeline.ingest("JavaScript is used for web development.")
        pipeline.ingest("Machine learning is a subset of AI.")

        # Query
        response = pipeline.query("What is Python?")

        assert response.query == "What is Python?"
        assert len(response.answer) > 0
        assert response.confidence >= 0.0

    def test_query_empty_raises(self):
        """Test that empty query raises error."""
        pipeline = RAGPipeline()

        with pytest.raises(ValueError, match="cannot be empty"):
            pipeline.query("")

    def test_retrieve_only(self):
        """Test retrieval without generation."""
        pipeline = RAGPipeline(embedding_fn=mock_embedding_fn)

        pipeline.ingest("Document about AI")
        pipeline.ingest("Document about ML")

        results = pipeline.retrieve_only("AI")
        assert isinstance(results, list)

    def test_ingest_batch(self):
        """Test batch ingestion."""
        pipeline = RAGPipeline(embedding_fn=mock_embedding_fn)

        documents = [
            {"content": "Doc 1"},
            {"content": "Doc 2"},
        ]

        ids = pipeline.ingest_batch(documents)
        assert len(ids) == 2

    def test_get_stats(self):
        """Test getting pipeline statistics."""
        pipeline = RAGPipeline(embedding_fn=mock_embedding_fn)

        pipeline.ingest("Test document")
        pipeline.query("Test query")

        stats = pipeline.get_stats()
        assert stats["queries_processed"] == 1
        assert "kb_stats" in stats

    def test_retrieval_strategies(self):
        """Test different retrieval strategies."""
        pipeline = RAGPipeline(embedding_fn=mock_embedding_fn)

        pipeline.ingest("Python programming language guide")

        # Test different strategies
        standard = pipeline.query("Python guide", retrieval_strategy="standard")
        hyde = pipeline.query("Python guide", retrieval_strategy="hyde")
        multi = pipeline.query("Python guide", retrieval_strategy="multi_query")

        assert standard.retrieval_method == "standard"
        assert hyde.retrieval_method == "hyde"
        assert multi.retrieval_method == "multi_query"


class TestIntegration:
    """Integration tests for Knowledge Base."""

    def test_full_rag_workflow(self):
        """Test complete RAG workflow."""
        # Create pipeline
        pipeline = RAGPipeline(
            embedding_fn=mock_embedding_fn,
            config=RAGConfig(
                use_hyde=True,
                use_multi_query=True,
                top_k=3
            )
        )

        # Ingest documents
        documents = [
            {"content": "The company was founded in 2020.", "metadata": {"topic": "history"}},
            {"content": "Our main product is an AI assistant.", "metadata": {"topic": "products"}},
            {"content": "We have offices in New York and London.", "metadata": {"topic": "locations"}},
            {"content": "Customer support is available 24/7.", "metadata": {"topic": "support"}},
        ]

        ids = pipeline.ingest_batch(documents)
        assert len(ids) == 4

        # Query
        response = pipeline.query("What products do you offer?")

        assert response.query == "What products do you offer?"
        assert len(response.answer) > 0
        assert isinstance(response.confidence, float)
        assert response.processing_time_ms > 0

    def test_vector_store_with_company_isolation(self):
        """Test company-scoped data isolation."""
        from uuid import uuid4

        company_a = uuid4()
        company_b = uuid4()

        store_a = VectorStore(company_id=company_a)
        store_b = VectorStore(company_id=company_b)

        # Add documents to each store
        doc_a = store_a.add_document(content="Company A document")
        doc_b = store_b.add_document(content="Company B document")

        # Verify isolation
        assert store_a.get_document(doc_a.id) is not None
        assert store_a.get_document(doc_b.id) is None

        assert store_b.get_document(doc_b.id) is not None
        assert store_b.get_document(doc_a.id) is None
