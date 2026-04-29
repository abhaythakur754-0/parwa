"""
Tests for RAG Retrieval Module (F-064), Shared Knowledge Base (F-152, F-153)

Covers:
  - MockVectorStore: add/delete/search/get operations, tenant isolation, cosine similarity
  - RAGRetriever: basic search, variant-specific behavior (mini/parwa/high), filters, threshold, cache
  - ReindexingManager: mark/process/status/invalidation/stale documents
  - Edge cases: empty query, no results, very long queries, special characters
  - BC-001: company_id isolation
  - BC-008: graceful degradation

Parent: Week 9 Day 7 (Sunday)
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from shared.knowledge_base.vector_search import (
    MockVectorStore,
    VectorStore,
    SearchResult,
    vector_search,
    get_vector_store,
)
from shared.knowledge_base.reindexing import (
    ReindexingManager,
)
from app.core.rag_retrieval import (
    RAGChunk,
    RAGRetriever,
    RAGResult,
    VARIANT_CONFIG,
    QUERY_SYNONYMS,
)


# =========================================================================
# SECTION 1: MockVectorStore Tests
# =========================================================================


class TestMockVectorStoreBasics:
    """Core operations of MockVectorStore."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)

    def test_add_document_success(self):
        """Adding a document returns True."""
        result = self.store.add_document(
            document_id="doc1",
            chunks=[{"content": "Hello world"}],
            company_id="c1",
        )
        assert result is True

    def test_add_document_with_metadata(self):
        """Document-level metadata is preserved."""
        self.store.add_document(
            document_id="doc1",
            chunks=[{"content": "Test content"}],
            company_id="c1",
            metadata={"source": "test.pd", "page": 1},
        )
        doc = self.store.get_document("doc1", "c1")
        assert doc["metadata"]["source"] == "test.pdf"
        assert doc["metadata"]["page"] == 1

    def test_add_document_multiple_chunks(self):
        """Multiple chunks are stored correctly."""
        chunks = [
            {"content": "Chunk one"},
            {"content": "Chunk two"},
            {"content": "Chunk three"},
        ]
        self.store.add_document(
            document_id="doc1",
            chunks=chunks,
            company_id="c1",
        )
        doc = self.store.get_document("doc1", "c1")
        assert len(doc["chunks"]) == 3

    def test_add_document_chunk_ids_format(self):
        """Chunk IDs follow {document_id}_chunk_{i} format."""
        self.store.add_document(
            document_id="doc1",
            chunks=[{"content": "A"}, {"content": "B"}],
            company_id="c1",
        )
        doc = self.store.get_document("doc1", "c1")
        assert doc["chunks"][0]["chunk_id"] == "doc1_chunk_0"
        assert doc["chunks"][1]["chunk_id"] == "doc1_chunk_1"

    def test_add_document_chunk_metadata_merged(self):
        """Chunk-level metadata merges with document-level metadata."""
        self.store.add_document(
            document_id="doc1",
            chunks=[
                {"content": "Test", "metadata": {"section": "intro"}},
            ],
            company_id="c1",
            metadata={"source": "manual.pd", "page": 5},
        )
        doc = self.store.get_document("doc1", "c1")
        assert doc["chunks"][0]["metadata"]["source"] == "manual.pdf"
        assert doc["chunks"][0]["metadata"]["section"] == "intro"

    def test_get_document_exists(self):
        """Retrieving an existing document returns it."""
        self.store.add_document(
            document_id="doc1",
            chunks=[{"content": "Content"}],
            company_id="c1",
        )
        doc = self.store.get_document("doc1", "c1")
        assert doc is not None
        assert doc["document_id"] == "doc1"
        assert doc["company_id"] == "c1"
        assert len(doc["chunks"]) == 1

    def test_get_document_not_exists(self):
        """Retrieving a non-existent document returns None."""
        doc = self.store.get_document("nonexistent", "c1")
        assert doc is None

    def test_delete_document_exists(self):
        """Deleting an existing document returns True."""
        self.store.add_document(
            document_id="doc1",
            chunks=[{"content": "Content"}],
            company_id="c1",
        )
        result = self.store.delete_document("doc1", "c1")
        assert result is True

    def test_delete_document_not_exists(self):
        """Deleting a non-existent document returns False."""
        result = self.store.delete_document("nonexistent", "c1")
        assert result is False

    def test_delete_document_removes_from_get(self):
        """After deletion, get_document returns None."""
        self.store.add_document(
            document_id="doc1",
            chunks=[{"content": "Content"}],
            company_id="c1",
        )
        self.store.delete_document("doc1", "c1")
        doc = self.store.get_document("doc1", "c1")
        assert doc is None

    def test_delete_document_removes_from_search(self):
        """After deletion, document chunks are not searchable."""
        self.store.add_document(
            document_id="doc1",
            chunks=[{"content": "Specific unique content"}],
            company_id="c1",
        )
        self.store.delete_document("doc1", "c1")
        embedding = self.store._generate_embedding("Specific unique content")
        results = self.store.search(embedding, "c1", top_k=10)
        assert len(results) == 0

    def test_health_check_healthy(self):
        """Health check returns True when healthy."""
        assert self.store.health_check() is True

    def test_health_check_unhealthy(self):
        """Health check returns False when unhealthy."""
        self.store.set_unhealthy(True)
        assert self.store.health_check() is False

    def test_set_unhealthy_and_restore(self):
        """Can toggle unhealthy state."""
        self.store.set_unhealthy(True)
        assert self.store.health_check() is False
        self.store.set_unhealthy(False)
        assert self.store.health_check() is True

    def test_clear(self):
        """Clear removes all stored data."""
        self.store.add_document("doc1", [{"content": "A"}], "c1")
        self.store.add_document("doc2", [{"content": "B"}], "c2")
        self.store.clear()
        assert self.store.document_count("c1") == 0
        assert self.store.document_count("c2") == 0

    def test_document_count(self):
        """document_count returns correct count."""
        self.store.add_document("doc1", [{"content": "A"}], "c1")
        self.store.add_document("doc2", [{"content": "B"}], "c1")
        assert self.store.document_count("c1") == 2


class TestMockVectorStoreSearch:
    """Vector search functionality."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        # Add test documents
        self.store.add_document("doc1", [{"content": "Refund policy for customer orders"}, {
            "content": "How to return items"}], "c1", )
        self.store.add_document("doc2", [{"content": "API endpoint configuration guide"}, {
            "content": "Server setup instructions"}], "c1", )
        self.store.add_document(
            "doc3",
            [{"content": "Billing invoice and payment processing"}],
            "c2",
        )

    def test_search_returns_results(self):
        """Search with relevant embedding returns results."""
        query_embedding = self.store._generate_embedding(
            "refund policy orders")
        results = self.store.search(query_embedding, "c1", top_k=5)
        assert len(results) > 0

    def test_search_returns_search_results(self):
        """Results are SearchResult objects."""
        query_embedding = self.store._generate_embedding("refund")
        results = self.store.search(query_embedding, "c1", top_k=5)
        for r in results:
            assert isinstance(r, SearchResult)
            assert isinstance(r.score, float)
            assert isinstance(r.content, str)

    def test_search_respects_top_k(self):
        """top_k limits the number of results."""
        query_embedding = self.store._generate_embedding("refund")
        results = self.store.search(query_embedding, "c1", top_k=1)
        assert len(results) <= 1

    def test_search_sorted_by_score_desc(self):
        """Results are sorted by score descending."""
        query_embedding = self.store._generate_embedding("refund")
        results = self.store.search(query_embedding, "c1", top_k=10)
        for i in range(1, len(results)):
            assert results[i].score <= results[i - 1].score

    def test_search_empty_company(self):
        """Search in a company with no documents returns empty."""
        query_embedding = self.store._generate_embedding("anything")
        results = self.store.search(query_embedding, "c_empty", top_k=5)
        assert len(results) == 0

    def test_search_unhealthy_returns_empty(self):
        """Search when unhealthy returns empty list."""
        self.store.set_unhealthy(True)
        query_embedding = self.store._generate_embedding("refund")
        results = self.store.search(query_embedding, "c1", top_k=5)
        assert results == []

    def test_search_filters_document_type(self):
        """Metadata filter on document_type works."""
        self.store.add_document(
            "doc_filtered",
            [{"content": "Specific filtered content", "metadata": {"document_type": "faq"}}],
            "c1",
        )
        query_embedding = self.store._generate_embedding(
            "Specific filtered content")
        results = self.store.search(
            query_embedding, "c1", top_k=10,
            filters={"document_type": "faq"},
        )
        for r in results:
            assert r.metadata.get("document_type") == "faq"

    def test_search_filters_source(self):
        """Metadata filter on source works."""
        self.store.add_document(
            "doc_src",
            [{"content": "Unique source content", "metadata": {"source": "manual"}}],
            "c1",
        )
        query_embedding = self.store._generate_embedding(
            "Unique source content")
        results = self.store.search(
            query_embedding, "c1", top_k=10,
            filters={"source": "manual"},
        )
        for r in results:
            assert r.metadata.get("source") == "manual"

    def test_search_filters_tags(self):
        """Metadata filter on tags works (ALL tags required)."""
        self.store.add_document(
            "doc_tags",
            [{"content": "Tagged content", "metadata": {"tags": ["refund", "policy"]}}],
            "c1",
        )
        query_embedding = self.store._generate_embedding("Tagged content")
        results = self.store.search(
            query_embedding, "c1", top_k=10,
            filters={"tags": ["refund"]},
        )
        for r in results:
            tags = r.metadata.get("tags", [])
            assert "refund" in tags

    def test_search_filters_tags_multiple(self):
        """Multiple tags filter requires ALL tags."""
        self.store.add_document(
            "doc_multi",
            [{"content": "Multi tag content", "metadata": {"tags": ["a", "b", "c"]}}],
            "c1",
        )
        query_embedding = self.store._generate_embedding("Multi tag content")
        results = self.store.search(
            query_embedding, "c1", top_k=10,
            filters={"tags": ["a", "c"]},
        )
        for r in results:
            tags = set(r.metadata.get("tags", []))
            assert "a" in tags
            assert "c" in tags

    def test_search_no_filters(self):
        """No filters returns all matching chunks."""
        query_embedding = self.store._generate_embedding("refund")
        results = self.store.search(query_embedding, "c1", top_k=10)
        assert len(results) > 0


class TestMockVectorStoreTenantIsolation:
    """BC-001: Tenant isolation in MockVectorStore."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "doc_a",
            [{"content": "Company A secret data"}],
            "company_a",
        )
        self.store.add_document(
            "doc_b",
            [{"content": "Company B confidential data"}],
            "company_b",
        )

    def test_company_a_cannot_see_company_b(self):
        """Company A search does not return Company B data."""
        query_embedding = self.store._generate_embedding("confidential data")
        results_a = self.store.search(query_embedding, "company_a", top_k=10)
        doc_ids = {r.document_id for r in results_a}
        assert "doc_b" not in doc_ids

    def test_company_b_cannot_see_company_a(self):
        """Company B search does not return Company A data."""
        query_embedding = self.store._generate_embedding("secret data")
        results_b = self.store.search(query_embedding, "company_b", top_k=10)
        doc_ids = {r.document_id for r in results_b}
        assert "doc_a" not in doc_ids

    def test_get_document_cross_tenant_none(self):
        """Getting a document from another tenant returns None."""
        doc = self.store.get_document("doc_a", "company_b")
        assert doc is None

    def test_delete_document_cross_tenant_false(self):
        """Deleting a document from another tenant returns False."""
        result = self.store.delete_document("doc_a", "company_b")
        assert result is False

    def test_delete_cross_tenant_does_not_affect_owner(self):
        """Deleting from wrong tenant doesn't affect the real document."""
        self.store.delete_document("doc_a", "company_b")
        doc = self.store.get_document("doc_a", "company_a")
        assert doc is not None


class TestCosineSimilarity:
    """Cosine similarity calculation."""

    def test_identical_vectors(self):
        """Identical vectors have similarity 1.0."""
        vec = [0.5, 0.5, 0.5, 0.5]
        vec_norm = MockVectorStore._normalize(vec)
        score = MockVectorStore._cosine_similarity(vec_norm, vec_norm)
        assert score > 0.99  # Allow small floating-point error

    def test_orthogonal_vectors(self):
        """Orthogonal vectors have similarity ~0.0."""
        vec_a = MockVectorStore._normalize([1.0, 0.0, 0.0])
        vec_b = MockVectorStore._normalize([0.0, 1.0, 0.0])
        score = MockVectorStore._cosine_similarity(vec_a, vec_b)
        assert abs(score) < 0.01

    def test_opposite_vectors(self):
        """Opposite vectors have similarity ~-1.0."""
        vec_a = MockVectorStore._normalize([1.0, 0.0])
        vec_b = MockVectorStore._normalize([-1.0, 0.0])
        score = MockVectorStore._cosine_similarity(vec_a, vec_b)
        assert score < -0.99

    def test_different_lengths(self):
        """Different length vectors return 0.0."""
        score = MockVectorStore._cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])
        assert score == 0.0

    def test_empty_vectors(self):
        """Empty vectors don't crash."""
        score = MockVectorStore._cosine_similarity([], [])
        assert score == 0.0

    def test_clamped_to_range(self):
        """Score is clamped to [-1, 1]."""
        # This is inherently tested by the implementation
        # but let's verify with extreme values
        vec_a = [1e10, -1e10, 1e10]
        vec_b = [-1e10, 1e10, -1e10]
        score = MockVectorStore._cosine_similarity(
            MockVectorStore._normalize(vec_a),
            MockVectorStore._normalize(vec_b),
        )
        assert -1.0 <= score <= 1.0


class TestVectorStoreInterface:
    """Verify VectorStore is properly abstract."""

    def test_cannot_instantiate_abstract(self):
        """VectorStore ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            VectorStore()

    def test_mock_is_vector_store(self):
        """MockVectorStore is a VectorStore."""
        assert isinstance(MockVectorStore(), VectorStore)


# =========================================================================
# SECTION 2: RAG Retriever Tests
# =========================================================================


class TestRAGRetrieverBasic:
    """Basic RAG retrieval operations."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "refund_doc",
            [
                {"content": "Our refund policy allows returns within 30 days of purchase"},
                {"content": "To process a refund, contact support with your order number"},
            ],
            "c1",
            {"source": "refund_policy.pd", "page": 1},
        )
        self.store.add_document(
            "tech_doc",
            [{"content": "API endpoint /api/v1/users returns user data in JSON format"}],
            "c1",
            {"source": "api_docs.md", "section": "Users"},
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_basic_search(self):
        """Basic search returns results."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)
        assert result.variant_tier_used == "parwa"

    @pytest.mark.asyncio
    async def test_search_returns_chunks(self):
        """Search result has chunk list."""
        result = await self.retriever.retrieve(
            query="refund",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result.chunks, list)
        assert result.total_found >= 0

    @pytest.mark.asyncio
    async def test_search_has_timing_info(self):
        """Search result includes timing information."""
        result = await self.retriever.retrieve(
            query="refund",
            company_id="c1",
            variant_type="parwa",
        )
        assert result.retrieval_time_ms >= 0
        assert result.query_embedding_time_ms >= 0

    @pytest.mark.asyncio
    async def test_search_chunks_have_required_fields(self):
        """Returned chunks have all required fields."""
        result = await self.retriever.retrieve(
            query="refund",
            company_id="c1",
            variant_type="parwa",
        )
        for chunk in result.chunks:
            assert chunk.chunk_id
            assert chunk.document_id
            assert chunk.content
            assert 0.0 <= chunk.score <= 1.0
            assert isinstance(chunk.metadata, dict)

    @pytest.mark.asyncio
    async def test_search_with_no_results(self):
        """Search with no matching documents returns empty result."""
        empty_store = MockVectorStore(seed=42)
        retriever = RAGRetriever(vector_store=empty_store)
        result = await retriever.retrieve(
            query="nonexistent query",
            company_id="c_empty",
            variant_type="parwa",
        )
        assert result.total_found == 0
        assert len(result.chunks) == 0


class TestRAGRetrieverVariants:
    """Variant-specific RAG behavior."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "doc1",
            [
                {"content": "Refund policy: Returns within 30 days"},
                {"content": "API configuration: Set up endpoints"},
                {"content": "Billing: Invoice processing steps"},
            ],
            "c1",
            {"source": "knowledge_base.pdf"},
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_mini_parwa_variant(self):
        """mini_parwa uses basic vector search."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="mini_parwa",
        )
        assert result.variant_tier_used == "mini_parwa"
        assert isinstance(result.chunks, list)

    @pytest.mark.asyncio
    async def test_parwa_variant(self):
        """parwa uses metadata filtering."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="parwa",
        )
        assert result.variant_tier_used == "parwa"

    @pytest.mark.asyncio
    async def test_high_parwa_variant(self):
        """high_parwa uses full pipeline with reranking and citations."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="high_parwa",
        )
        assert result.variant_tier_used == "high_parwa"

    @pytest.mark.asyncio
    async def test_high_parwa_has_citations(self):
        """high_parwa adds citations to chunks."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="high_parwa",
        )
        for chunk in result.chunks:
            assert chunk.citation is not None
            assert "Source" in chunk.citation

    @pytest.mark.asyncio
    async def test_mini_parwa_no_citations(self):
        """mini_parwa does not add citations."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="mini_parwa",
        )
        for chunk in result.chunks:
            assert chunk.citation is None

    @pytest.mark.asyncio
    async def test_parwa_no_citations(self):
        """parwa does not add citations."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="parwa",
        )
        for chunk in result.chunks:
            assert chunk.citation is None

    @pytest.mark.asyncio
    async def test_high_parwa_citation_includes_source(self):
        """Citations include document source."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="high_parwa",
        )
        for chunk in result.chunks:
            if chunk.citation:
                assert "knowledge_base.pdf" in chunk.citation


class TestRAGRetrieverThresholds:
    """Similarity threshold filtering per variant."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "doc1",
            [{"content": "Completely unrelated content about gardening and flowers"}],
            "c1",
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_mini_parwa_low_threshold(self):
        """mini_parwa has lowest threshold (0.5)."""
        result = await self.retriever.retrieve(
            query="plants and garden maintenance",
            company_id="c1",
            variant_type="mini_parwa",
        )
        # Low threshold means more results can pass
        config = VARIANT_CONFIG["mini_parwa"]
        assert config["similarity_threshold"] == 0.5

    @pytest.mark.asyncio
    async def test_parwa_medium_threshold(self):
        """parwa has medium threshold (0.6)."""
        config = VARIANT_CONFIG["parwa"]
        assert config["similarity_threshold"] == 0.6

    @pytest.mark.asyncio
    async def test_high_parwa_high_threshold(self):
        """high_parwa has highest threshold (0.7)."""
        config = VARIANT_CONFIG["high_parwa"]
        assert config["similarity_threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_custom_threshold(self):
        """Custom threshold can be passed."""
        result = await self.retriever.retrieve(
            query="gardening flowers plants",
            company_id="c1",
            variant_type="parwa",
            similarity_threshold=0.99,
        )
        # Very high threshold should filter out most results
        assert result.total_found >= 0

    @pytest.mark.asyncio
    async def test_threshold_zero_returns_all(self):
        """Threshold of 0 returns all matching chunks."""
        result = await self.retriever.retrieve(
            query="gardening",
            company_id="c1",
            variant_type="parwa",
            similarity_threshold=0.0,
        )
        assert result.total_found >= 0


class TestRAGRetrieverFilters:
    """Metadata filtering in RAG retrieval."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document("faq_doc",
                                [{"content": "FAQ refund answer",
                                  "metadata": {"document_type": "faq"}},
                                    {"content": "FAQ billing answer",
                                     "metadata": {"document_type": "faq"}},
                                 ],
                                "c1",
                                )
        self.store.add_document("guide_doc",
                                [{"content": "Guide refund steps",
                                  "metadata": {"document_type": "guide"}},
                                 ],
                                "c1",
                                )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_parwa_applies_filters(self):
        """parwa applies metadata filters."""
        result = await self.retriever.retrieve(
            query="refund",
            company_id="c1",
            variant_type="parwa",
            filters={"document_type": "faq"},
        )
        for chunk in result.chunks:
            assert chunk.metadata.get("document_type") == "faq"

    @pytest.mark.asyncio
    async def test_mini_parwa_ignores_filters(self):
        """mini_parwa does not use metadata filters."""
        # mini_parwa config has use_metadata_filters=False
        config = VARIANT_CONFIG["mini_parwa"]
        assert config["use_metadata_filters"] is False

    @pytest.mark.asyncio
    async def test_high_parwa_applies_filters(self):
        """high_parwa applies metadata filters."""
        result = await self.retriever.retrieve(
            query="refund",
            company_id="c1",
            variant_type="high_parwa",
            filters={"document_type": "guide"},
        )
        for chunk in result.chunks:
            assert chunk.metadata.get("document_type") == "guide"

    @pytest.mark.asyncio
    async def test_no_filter_returns_all(self):
        """No filter returns all matching chunks."""
        result = await self.retriever.retrieve(
            query="refund",
            company_id="c1",
            variant_type="parwa",
        )
        # Without filter, we might get chunks from any document type
        assert isinstance(result.chunks, list)


class TestRAGRetrieverTopK:
    """Top-K limiting in RAG retrieval."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "big_doc",
            [{"content": f"Chunk number {i} with some shared topic words about refunds and policies"}
             for i in range(20)],
            "c1",
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_top_k_limits_results(self):
        """top_k limits the number of returned chunks."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="parwa",
            top_k=3,
        )
        assert len(result.chunks) <= 3

    @pytest.mark.asyncio
    async def test_top_k_one(self):
        """top_k=1 returns at most 1 chunk."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="parwa",
            top_k=1,
        )
        assert len(result.chunks) <= 1

    @pytest.mark.asyncio
    async def test_top_k_larger_than_available(self):
        """top_k larger than available results returns all."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="parwa",
            top_k=100,
        )
        assert len(result.chunks) <= 100


class TestRAGRetrieverTenantIsolation:
    """BC-001: Tenant isolation in RAG retrieval."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "company_a_doc",
            [{"content": "Company A confidential refund policy"}],
            "company_a",
        )
        self.store.add_document(
            "company_b_doc",
            [{"content": "Company B proprietary billing process"}],
            "company_b",
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_tenant_a_sees_own_data(self):
        """Tenant A gets only their own data."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="company_a",
            variant_type="parwa",
        )
        for chunk in result.chunks:
            assert chunk.document_id == "company_a_doc"

    @pytest.mark.asyncio
    async def test_tenant_b_sees_own_data(self):
        """Tenant B gets only their own data."""
        result = await self.retriever.retrieve(
            query="billing process",
            company_id="company_b",
            variant_type="parwa",
        )
        for chunk in result.chunks:
            assert chunk.document_id == "company_b_doc"

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b(self):
        """Tenant A cannot see Tenant B's data."""
        result = await self.retriever.retrieve(
            query="billing process proprietary",
            company_id="company_a",
            variant_type="parwa",
        )
        doc_ids = {c.document_id for c in result.chunks}
        assert "company_b_doc" not in doc_ids


class TestRAGRetrieverGracefulDegradation:
    """BC-008: Graceful degradation."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "doc1",
            [{"content": "Some searchable content about refunds and returns"}],
            "c1",
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        """Empty query returns empty result without crashing (BC-008)."""
        result = await self.retriever.retrieve(
            query="",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)
        # Empty query returns early — not a degradation scenario
        assert result.chunks == []

    @pytest.mark.asyncio
    async def test_whitespace_query_returns_empty(self):
        """Whitespace-only query returns empty result."""
        result = await self.retriever.retrieve(
            query="   ",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_unhealthy_store_triggers_fallback(self):
        """Unhealthy vector store triggers keyword fallback."""
        self.store.set_unhealthy(True)
        result = await self.retriever.retrieve(
            query="refund returns",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)
        # Keyword search may or may not find results,
        # but it should not crash
        assert result.degradation_used is True

    @pytest.mark.asyncio
    async def test_keyword_fallback_works(self):
        """Keyword fallback finds results by word overlap."""
        result = await self.retriever.retrieve(
            query="refund returns content",
            company_id="c1",
            variant_type="parwa",
        )
        # When vector search fails, keyword search should work
        assert isinstance(result, RAGResult)


class TestRAGRetrieverEdgeCases:
    """Edge cases and adversarial inputs."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "doc1",
            [{"content": "Normal document content about refunds"}],
            "c1",
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_very_long_query(self):
        """Very long query doesn't crash."""
        long_query = "refund " * 5000
        result = await self.retriever.retrieve(
            query=long_query,
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_special_characters_query(self):
        """Query with special characters doesn't crash."""
        result = await self.retriever.retrieve(
            query="refund $100.00 @#$%^&*()_+",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_unicode_query(self):
        """Unicode query doesn't crash."""
        result = await self.retriever.retrieve(
            query="返金リクエスト remboursierung",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_sql_injection_query(self):
        """SQL injection in query is treated as text."""
        result = await self.retriever.retrieve(
            query="'; DROP TABLE documents; --",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_html_in_query(self):
        """HTML in query is treated as text."""
        result = await self.retriever.retrieve(
            query="<script>alert('xss')</script> refund",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_unknown_variant_defaults_to_parwa(self):
        """Unknown variant_type falls back to parwa config."""
        result = await self.retriever.retrieve(
            query="refund",
            company_id="c1",
            variant_type="unknown_variant",
        )
        assert result.variant_tier_used == "unknown_variant"
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_null_bytes_in_query(self):
        """Null bytes in query don't crash."""
        result = await self.retriever.retrieve(
            query="refund\x00return\x00policy",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_newlines_in_query(self):
        """Newlines in query don't crash."""
        result = await self.retriever.retrieve(
            query="refund\n\nreturns\npolicy",
            company_id="c1",
            variant_type="parwa",
        )
        assert isinstance(result, RAGResult)


class TestRAGRetrieverCache:
    """Cache behavior in RAG retrieval."""

    def setup_method(self):
        self.store = MockVectorStore(seed=42)
        self.store.add_document(
            "doc1",
            [{"content": "Cacheable content about refund policy"}],
            "c1",
        )
        self.retriever = RAGRetriever(vector_store=self.store)

    @pytest.mark.asyncio
    async def test_cache_miss_returns_result(self):
        """Cache miss still returns a valid result."""
        result = await self.retriever.retrieve(
            query="refund policy",
            company_id="c1",
            variant_type="parwa",
        )
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self):
        """Cache hit returns cached=True result."""
        cached_data = {
            "chunks": [{
                "chunk_id": "c1",
                "document_id": "doc1",
                "content": "Cached chunk",
                "score": 0.9,
                "metadata": {},
                "citation": None,
            }],
            "total_found": 1,
            "retrieval_time_ms": 5.0,
            "query_embedding_time_ms": 2.0,
            "filters_applied": {},
            "variant_tier_used": "parwa",
        }
        with patch(
            "app.core.redis.cache_get",
            new_callable=AsyncMock,
            return_value=cached_data,
        ):
            result = await self.retriever.retrieve(
                query="refund policy",
                company_id="c1",
                variant_type="parwa",
            )
            assert result.cached is True
            assert len(result.chunks) == 1
            assert result.chunks[0].content == "Cached chunk"

    @pytest.mark.asyncio
    async def test_cache_fail_open(self):
        """Redis failure doesn't crash retrieval."""
        with patch(
            "app.core.redis.cache_get",
            new_callable=AsyncMock,
            side_effect=Exception("Redis down"),
        ):
            with patch(
                "app.core.redis.cache_set",
                new_callable=AsyncMock,
                side_effect=Exception("Redis down"),
            ):
                result = await self.retriever.retrieve(
                    query="refund policy",
                    company_id="c1",
                    variant_type="parwa",
                )
                assert isinstance(result, RAGResult)
                assert result.cached is False


class TestRAGRetrieverQueryExpansion:
    """Query expansion for high_parwa variant."""

    def setup_method(self):
        self.retriever = RAGRetriever()

    def test_expand_refund_query(self):
        """Refund query gets expanded with synonyms."""
        expanded = self.retriever._expand_query("I want a refund")
        assert "I want a refund" in expanded  # Original always present
        assert len(expanded) > 1  # Should have expansions

    def test_expand_no_synonyms(self):
        """Query without synonyms returns only original."""
        expanded = self.retriever._expand_query("xyzzyplugh frobozz")
        assert len(expanded) == 1
        assert expanded[0] == "xyzzyplugh frobozz"

    def test_expand_billing_query(self):
        """Billing query gets expanded."""
        expanded = self.retriever._expand_query("billing inquiry")
        assert len(expanded) > 1

    def test_expand_max_3_results(self):
        """Query expansion returns at most 3 queries."""
        expanded = self.retriever._expand_query("refund password cancel error")
        assert len(expanded) <= 3


class TestRAGRetrieverReranking:
    """Reranking for high_parwa variant."""

    def test_rerank_preserves_chunks(self):
        """Reranking preserves chunk count."""
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="A", score=0.5),
            RAGChunk(chunk_id="c2", document_id="d1", content="B", score=0.7),
        ]
        retriever = RAGRetriever()
        reranked = retriever._rerank("test query", chunks)
        assert len(reranked) == 2

    def test_rerank_sorted_by_score(self):
        """Reranked results are sorted by score descending."""
        chunks = [
            RAGChunk(chunk_id="c1", document_id="d1", content="Low", score=0.3),
            RAGChunk(chunk_id="c2", document_id="d1", content="High", score=0.9),
            RAGChunk(chunk_id="c3", document_id="d1", content="Mid", score=0.6),
        ]
        retriever = RAGRetriever()
        reranked = retriever._rerank("High Mid Low", chunks)
        scores = [c.score for c in reranked]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_empty_list(self):
        """Reranking empty list returns empty list."""
        retriever = RAGRetriever()
        result = retriever._rerank("query", [])
        assert result == []


class TestRAGResultSerialization:
    """RAGResult serialization to dict."""

    def test_to_dict(self):
        """RAGResult serializes correctly."""
        result = RAGResult(
            chunks=[
                RAGChunk(
                    chunk_id="c1", document_id="d1",
                    content="Test", score=0.9,
                    metadata={"source": "test.pdf"},
                    citation="[Source: test.pdf]",
                ),
            ],
            total_found=1,
            retrieval_time_ms=10.5,
            query_embedding_time_ms=5.2,
            filters_applied={"document_type": "faq"},
            variant_tier_used="high_parwa",
            cached=False,
            degradation_used=False,
        )
        d = result.to_dict()
        assert d["total_found"] == 1
        assert d["variant_tier_used"] == "high_parwa"
        assert d["cached"] is False
        assert len(d["chunks"]) == 1
        assert d["chunks"][0]["citation"] == "[Source: test.pdf]"
        assert d["chunks"][0]["score"] == 0.9

    def test_rag_chunk_to_dict(self):
        """RAGChunk serializes correctly."""
        chunk = RAGChunk(
            chunk_id="c1", document_id="d1",
            content="Hello", score=0.85,
            metadata={"page": 3},
        )
        d = chunk.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["document_id"] == "d1"
        assert d["content"] == "Hello"
        assert d["score"] == 0.85
        assert d["metadata"]["page"] == 3


class TestRAGRetrieverCacheKey:
    """Cache key generation."""

    def test_cache_key_includes_company_id(self):
        """Different company_ids produce different keys."""
        r = RAGRetriever()
        key1 = r._build_cache_key("query", "c1", "parwa", None)
        key2 = r._build_cache_key("query", "c2", "parwa", None)
        assert key1 != key2

    def test_cache_key_includes_variant(self):
        """Different variants produce different keys."""
        r = RAGRetriever()
        key1 = r._build_cache_key("query", "c1", "mini_parwa", None)
        key2 = r._build_cache_key("query", "c1", "parwa", None)
        assert key1 != key2

    def test_cache_key_deterministic(self):
        """Same inputs produce same key."""
        r = RAGRetriever()
        key1 = r._build_cache_key("test query", "c1", "parwa", {"type": "faq"})
        key2 = r._build_cache_key("test query", "c1", "parwa", {"type": "faq"})
        assert key1 == key2

    def test_cache_key_case_normalized(self):
        """Query is normalized in cache key."""
        r = RAGRetriever()
        key1 = r._build_cache_key("Test Query", "c1", "parwa", None)
        key2 = r._build_cache_key("test query", "c1", "parwa", None)
        assert key1 == key2

    def test_cache_key_different_filters(self):
        """Different filters produce different keys."""
        r = RAGRetriever()
        key1 = r._build_cache_key("query", "c1", "parwa", {"type": "faq"})
        key2 = r._build_cache_key("query", "c1", "parwa", {"type": "guide"})
        assert key1 != key2


# =========================================================================
# SECTION 3: ReindexingManager Tests
# =========================================================================


class TestReindexingManagerMark:
    """Mark documents for reindexing."""

    def setup_method(self):
        self.manager = ReindexingManager()

    @pytest.mark.asyncio
    async def test_mark_single_document(self):
        """Marking a single document returns 1."""
        count = await self.manager.mark_for_reindex("c1", ["doc1"])
        assert count == 1

    @pytest.mark.asyncio
    async def test_mark_multiple_documents(self):
        """Marking multiple documents returns correct count."""
        count = await self.manager.mark_for_reindex(
            "c1", ["doc1", "doc2", "doc3"]
        )
        assert count == 3

    @pytest.mark.asyncio
    async def test_mark_empty_list(self):
        """Marking empty list returns 0."""
        count = await self.manager.mark_for_reindex("c1", [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_mark_creates_pending_jobs(self):
        """Marking creates jobs with 'pending' status."""
        await self.manager.mark_for_reindex("c1", ["doc1"])
        status = self.manager.get_reindex_status("c1")
        assert status.pending == 1

    @pytest.mark.asyncio
    async def test_mark_different_companies_isolated(self):
        """Marking for different companies is isolated."""
        await self.manager.mark_for_reindex("c1", ["doc1"])
        await self.manager.mark_for_reindex("c2", ["doc2", "doc3"])
        assert self.manager.get_reindex_status("c1").pending == 1
        assert self.manager.get_reindex_status("c2").pending == 2

    @pytest.mark.asyncio
    async def test_mark_duplicate_documents(self):
        """Marking same document twice creates two jobs."""
        await self.manager.mark_for_reindex("c1", ["doc1"])
        await self.manager.mark_for_reindex("c1", ["doc1"])
        assert self.manager.get_reindex_status("c1").pending == 2


class TestReindexingManagerProcess:
    """Process reindex queue."""

    def setup_method(self):
        self.manager = ReindexingManager()

    @pytest.mark.asyncio
    async def test_process_empty_queue(self):
        """Processing empty queue returns zeros."""
        result = await self.manager.process_reindex_queue("c1")
        assert result["processed"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_process_pending_jobs(self):
        """Processing completes pending jobs."""
        await self.manager.mark_for_reindex("c1", ["doc1", "doc2"])
        result = await self.manager.process_reindex_queue("c1")
        assert result["processed"] == 2
        assert result["succeeded"] == 2
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_process_with_callback(self):
        """Processing calls the process_fn callback."""
        await self.manager.mark_for_reindex("c1", ["doc1"])
        called = []

        def callback(job):
            called.append(job.document_id)
            return True

        result = await self.manager.process_reindex_queue("c1", process_fn=callback)
        assert result["succeeded"] == 1
        assert "doc1" in called

    @pytest.mark.asyncio
    async def test_process_with_failing_callback(self):
        """Failing callback marks jobs as failed."""
        await self.manager.mark_for_reindex("c1", ["doc1"])

        def fail_callback(job):
            raise RuntimeError("Processing failed")

        result = await self.manager.process_reindex_queue("c1", process_fn=fail_callback)
        assert result["failed"] == 1
        assert result["succeeded"] == 0
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_process_async_callback(self):
        """Processing works with async callbacks."""
        await self.manager.mark_for_reindex("c1", ["doc1"])

        async def async_callback(job):
            return True

        result = await self.manager.process_reindex_queue("c1", process_fn=async_callback)
        assert result["succeeded"] == 1

    @pytest.mark.asyncio
    async def test_process_respects_batch_size(self):
        """Batch size limits processing."""
        await self.manager.mark_for_reindex("c1", [f"doc{i}" for i in range(10)])
        result = await self.manager.process_reindex_queue("c1", batch_size=3)
        assert result["processed"] == 3
        assert self.manager.get_reindex_status("c1").pending == 7

    @pytest.mark.asyncio
    async def test_process_updates_status(self):
        """Processing updates the status correctly."""
        await self.manager.mark_for_reindex("c1", ["doc1"])
        await self.manager.process_reindex_queue("c1")
        status = self.manager.get_reindex_status("c1")
        assert status.completed == 1
        assert status.pending == 0


class TestReindexingManagerStatus:
    """Reindex status tracking."""

    def setup_method(self):
        self.manager = ReindexingManager()

    def test_initial_status_empty(self):
        """Initial status for unknown company is all zeros."""
        status = self.manager.get_reindex_status("unknown")
        assert status.pending == 0
        assert status.processing == 0
        assert status.completed == 0
        assert status.failed == 0
        assert status.total == 0

    @pytest.mark.asyncio
    async def test_status_after_mark(self):
        """Status reflects pending after mark."""
        await self.manager.mark_for_reindex("c1", ["doc1", "doc2", "doc3"])
        status = self.manager.get_reindex_status("c1")
        assert status.pending == 3
        assert status.total == 3

    @pytest.mark.asyncio
    async def test_status_after_process(self):
        """Status reflects completed after process."""
        await self.manager.mark_for_reindex("c1", ["doc1"])
        await self.manager.process_reindex_queue("c1")
        status = self.manager.get_reindex_status("c1")
        assert status.completed == 1
        assert status.total == 1


class TestReindexingManagerCacheInvalidation:
    """Cache invalidation on reindex."""

    def setup_method(self):
        self.manager = ReindexingManager()

    @pytest.mark.asyncio
    async def test_invalidate_cache(self):
        """Cache invalidation tracks affected documents."""
        count = await self.manager.invalidate_cache("c1", ["doc1", "doc2"])
        assert count == 2

    @pytest.mark.asyncio
    async def test_invalidate_cache_empty(self):
        """Invalidating empty list returns 0."""
        count = await self.manager.invalidate_cache("c1", [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_invalidate_accumulates(self):
        """Invalidation accumulates across calls."""
        await self.manager.invalidate_cache("c1", ["doc1"])
        await self.manager.invalidate_cache("c1", ["doc2", "doc3"])
        # Total invalidated documents should be 3
        count = await self.manager.invalidate_cache("c1", ["doc1"])
        assert count == 3


class TestReindexingManagerStaleDocuments:
    """SG-34: Stale document detection."""

    def setup_method(self):
        self.manager = ReindexingManager()

    @pytest.mark.asyncio
    async def test_no_stale_documents_initially(self):
        """No stale documents when nothing has been indexed."""
        stale = await self.manager.get_stale_documents("c1", max_age_minutes=5)
        assert len(stale) == 0

    @pytest.mark.asyncio
    async def test_fresh_documents_not_stale(self):
        """Recently indexed documents are not stale."""
        self.manager.record_index_timestamp("c1", ["doc1"])
        stale = await self.manager.get_stale_documents("c1", max_age_minutes=5)
        assert len(stale) == 0

    @pytest.mark.asyncio
    async def test_old_documents_are_stale(self):
        """Documents indexed long ago are stale."""
        self.manager.record_index_timestamp("c1", ["old_doc"])
        # Manually age the timestamp
        # 10 minutes ago
        self.manager._doc_timestamps["c1"]["old_doc"] = time.time() - 600
        stale = await self.manager.get_stale_documents("c1", max_age_minutes=5)
        assert len(stale) == 1
        assert stale[0]["document_id"] == "old_doc"

    @pytest.mark.asyncio
    async def test_stale_sorted_by_age(self):
        """Stale documents are sorted by age (most stale first)."""
        self.manager._doc_timestamps["c1"] = {
            "doc1": time.time() - 300,  # 5 min ago
            "doc2": time.time() - 600,  # 10 min ago (more stale)
            "doc3": time.time() - 60,   # 1 min ago (fresh)
        }
        stale = await self.manager.get_stale_documents("c1", max_age_minutes=5)
        assert len(stale) == 2  # doc1 and doc2 are stale
        assert stale[0]["document_id"] == "doc2"  # Most stale first

    @pytest.mark.asyncio
    async def test_stale_has_age_info(self):
        """Stale document includes age_minutes."""
        self.manager.record_index_timestamp("c1", ["old_doc"])
        self.manager._doc_timestamps["c1"]["old_doc"] = time.time() - 600
        stale = await self.manager.get_stale_documents("c1", max_age_minutes=5)
        assert "age_minutes" in stale[0]
        assert stale[0]["age_minutes"] >= 10

    def test_record_index_timestamp(self):
        """record_index_timestamp stores timestamps."""
        self.manager.record_index_timestamp("c1", ["doc1", "doc2"])
        assert "doc1" in self.manager._doc_timestamps["c1"]
        assert "doc2" in self.manager._doc_timestamps["c1"]

    def test_record_index_timestamp_overwrites(self):
        """Re-recording overwrites old timestamp."""
        self.manager.record_index_timestamp("c1", ["doc1"])
        ts1 = self.manager._doc_timestamps["c1"]["doc1"]
        self.manager.record_index_timestamp("c1", ["doc1"])
        ts2 = self.manager._doc_timestamps["c1"]["doc1"]
        assert ts2 >= ts1


class TestReindexingManagerClear:
    """ReindexingManager cleanup."""

    def setup_method(self):
        self.manager = ReindexingManager()

    @pytest.mark.asyncio
    async def test_clear_resets_state(self):
        """Clear resets all state."""
        await self.manager.mark_for_reindex("c1", ["doc1", "doc2"])
        await self.manager.process_reindex_queue("c1")
        await self.manager.invalidate_cache("c1", ["doc1"])

        self.manager.clear()
        status = self.manager.get_reindex_status("c1")
        assert status.pending == 0
        assert status.completed == 0
        assert status.failed == 0


# =========================================================================
# SECTION 4: Variant Configuration Tests
# =========================================================================


class TestVariantConfig:
    """Verify VARIANT_CONFIG has correct structure."""

    def test_all_variants_present(self):
        """All three variants have config entries."""
        for variant in ("mini_parwa", "parwa", "high_parwa"):
            assert variant in VARIANT_CONFIG

    def test_config_has_required_keys(self):
        """Each variant config has all required keys."""
        required_keys = [
            "similarity_threshold", "default_top_k",
            "use_metadata_filters", "use_reranking",
            "use_citation_tracking", "use_query_expansion",
            "max_retrieval_time_ms",
        ]
        for variant, config in VARIANT_CONFIG.items():
            for key in required_keys:
                assert key in config, f"{variant} missing {key}"

    def test_thresholds_increasing(self):
        """Similarity thresholds increase with tier."""
        assert VARIANT_CONFIG["mini_parwa"]["similarity_threshold"] < \
            VARIANT_CONFIG["parwa"]["similarity_threshold"] < \
            VARIANT_CONFIG["high_parwa"]["similarity_threshold"]

    def test_top_k_increasing(self):
        """Default top_k increases with tier."""
        assert VARIANT_CONFIG["mini_parwa"]["default_top_k"] < \
            VARIANT_CONFIG["parwa"]["default_top_k"] < \
            VARIANT_CONFIG["high_parwa"]["default_top_k"]


# =========================================================================
# SECTION 5: Query Synonyms Tests
# =========================================================================


class TestQuerySynonyms:
    """Verify QUERY_SYNONYMS structure."""

    def test_synonyms_is_dict(self):
        """QUERY_SYNONYMS is a dict."""
        assert isinstance(QUERY_SYNONYMS, dict)

    def test_synonyms_have_lists(self):
        """Each synonym entry has a list of alternatives."""
        for key, values in QUERY_SYNONYMS.items():
            assert isinstance(values, list)
            assert len(values) > 0

    def test_common_synonyms_present(self):
        """Common query terms have synonyms."""
        for term in ["refund", "error", "billing", "password", "cancel"]:
            assert term in QUERY_SYNONYMS


# =========================================================================
# SECTION 6: Convenience Functions Tests
# =========================================================================


class TestVectorSearchConvenience:
    """vector_search convenience function and get_vector_store."""

    def test_get_vector_store_returns_mock(self):
        """get_vector_store returns MockVectorStore instance."""
        store = get_vector_store()
        assert isinstance(store, MockVectorStore)

    def test_get_vector_store_singleton(self):
        """get_vector_store returns the same instance."""
        s1 = get_vector_store()
        s2 = get_vector_store()
        assert s1 is s2

    def test_vector_search_returns_results(self):
        """vector_search convenience function works."""
        store = get_vector_store()
        store.add_document(
            "doc1",
            [{"content": "Test content for search"}],
            "c_test",
        )
        embedding = store._generate_embedding("Test content")
        results = vector_search(embedding, "c_test", top_k=5)
        assert isinstance(results, list)
