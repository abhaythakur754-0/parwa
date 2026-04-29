"""
RAG Retrieval Module (F-064) — Knowledge Base Search (Part 1)

Handles knowledge base search/retrieval for generating AI responses.
Variant-specific complexity tiers:
  - mini_parwa: basic vector search only (cosine similarity, top-k)
  - parwa: + metadata filtering (document_type, date range, tags)
  - high_parwa: full pipeline (vector search + metadata + reranking + citations)

BC-001: Tenant isolation — all queries scoped to company_id.
BC-008: Graceful degradation — fallback to keyword search on vector failure.

Parent: Week 9 Day 7 (Sunday)
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from shared.knowledge_base.vector_search import (
    VectorStore,
    get_vector_store,
)

logger = get_logger("rag_retrieval")

# ── Per-variant configuration ─────────────────────────────────────────

VARIANT_CONFIG = {
    "mini_parwa": {
        "similarity_threshold": 0.5,
        "default_top_k": 3,
        "use_metadata_filters": False,
        "use_reranking": False,
        "use_citation_tracking": False,
        "use_query_expansion": False,
        "max_retrieval_time_ms": 2000,
    },
    "parwa": {
        "similarity_threshold": 0.6,
        "default_top_k": 5,
        "use_metadata_filters": True,
        "use_reranking": False,
        "use_citation_tracking": False,
        "use_query_expansion": False,
        "max_retrieval_time_ms": 3000,
    },
    "high_parwa": {
        "similarity_threshold": 0.7,
        "default_top_k": 10,
        "use_metadata_filters": True,
        "use_reranking": True,
        "use_citation_tracking": True,
        "use_query_expansion": True,
        "max_retrieval_time_ms": 5000,
    },
}

# ── Query expansion synonyms for high_parwa ──────────────────────────

QUERY_SYNONYMS: Dict[str, List[str]] = {
    "refund": ["reimburse", "return", "money back", "credit"],
    "error": ["bug", "crash", "issue", "problem", "failure"],
    "billing": ["invoice", "charge", "payment", "subscription"],
    "password": ["login", "credentials", "authentication", "sign in"],
    "cancel": ["terminate", "unsubscribe", "deactivate", "end"],
    "shipping": ["delivery", "track", "package", "parcel", "order"],
    "account": ["profile", "settings", "user", "membership"],
    "help": ["support", "assist", "guide", "how to"],
    "slow": ["lag", "delay", "timeout", "unresponsive", "performance"],
    "price": ["cost", "fee", "rate", "amount", "pricing"],
}

CACHE_TTL_SECONDS = 120


# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class RAGChunk:
    """A retrieved chunk from the knowledge base."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    citation: Optional[str] = None  # high_parwa only

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "score": round(self.score, 6),
            "metadata": self.metadata,
            "citation": self.citation,
        }


@dataclass
class RAGResult:
    """Result of a RAG retrieval operation."""

    chunks: List[RAGChunk] = field(default_factory=list)
    total_found: int = 0
    retrieval_time_ms: float = 0.0
    query_embedding_time_ms: float = 0.0
    filters_applied: Dict[str, Any] = field(default_factory=dict)
    variant_tier_used: str = "parwa"
    cached: bool = False
    degradation_used: bool = False  # BC-008

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunks": [c.to_dict() for c in self.chunks],
            "total_found": self.total_found,
            "retrieval_time_ms": round(self.retrieval_time_ms, 2),
            "query_embedding_time_ms": round(self.query_embedding_time_ms, 2),
            "filters_applied": self.filters_applied,
            "variant_tier_used": self.variant_tier_used,
            "cached": self.cached,
            "degradation_used": self.degradation_used,
        }


# ── RAG Retriever ────────────────────────────────────────────────────


class RAGRetriever:
    """Knowledge base RAG retrieval engine.

    Supports three variant tiers with increasing complexity:
    - mini_parwa: Basic vector search
    - parwa: + metadata filtering
    - high_parwa: + reranking + citation tracking + query expansion

    BC-001: All queries scoped to company_id.
    BC-008: Falls back to keyword search if vector search fails.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self._store = vector_store or get_vector_store()

    async def retrieve(
        self,
        query: str,
        company_id: str,
        variant_type: str = "parwa",
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RAGResult:
        """Retrieve relevant chunks from the knowledge base.

        Args:
            query: User query to search for.
            company_id: Tenant identifier (BC-001).
            variant_type: One of mini_parwa, parwa, high_parwa.
            top_k: Maximum results (defaults to variant config).
            similarity_threshold: Minimum similarity score.
            filters: Metadata filters (document_type, tags, date range).

        Returns:
            RAGResult with chunks and metadata.
        """
        # BC-008: Input validation — empty query
        if not query or not isinstance(query, str) or not query.strip():
            return RAGResult(
                variant_tier_used=variant_type,
                retrieval_time_ms=0.0,
            )

        start_time = time.monotonic()

        # G9-GAP-12 FIX: Log warning for unknown variant_type
        if variant_type not in VARIANT_CONFIG:
            logger.warning(
                "rag_unknown_variant_type_defaulting_to_parwa",
                variant_type=variant_type,
                company_id=company_id,
            )
        config = VARIANT_CONFIG.get(variant_type, VARIANT_CONFIG["parwa"])
        if top_k is None:
            top_k = config["default_top_k"]
        if similarity_threshold is None:
            similarity_threshold = config["similarity_threshold"]

        # ── Step 1: Check cache ──────────────────────────────────
        cache_key = self._build_cache_key(
            query, company_id, variant_type, filters)
        cached_result = await self._check_cache(company_id, cache_key)
        if cached_result is not None:
            cached_result.retrieval_time_ms = round(
                (time.monotonic() - start_time) * 1000, 2
            )
            logger.debug("rag_cache_hit", key=cache_key)
            return cached_result

        # ── Step 2: Generate query embedding ─────────────────────
        embed_start = time.monotonic()
        query_embedding = await self._generate_embedding(query)
        embedding_time_ms = round((time.monotonic() - embed_start) * 1000, 2)

        if query_embedding is None:
            # BC-008: Fallback to keyword search
            logger.warning(
                "rag_embedding_failed_keyword_fallback",
                company_id=company_id,
                variant_type=variant_type,
            )
            return await self._keyword_search(
                query=query,
                company_id=company_id,
                variant_type=variant_type,
                top_k=top_k,
                filters=filters,
                start_time=start_time,
            )

        # ── Step 3: Query expansion (high_parwa only) ───────────
        expanded_queries = [query]
        if config.get("use_query_expansion"):
            expanded_queries = self._expand_query(query)

        # ── Step 4: Vector search ────────────────────────────────
        all_chunks: List[RAGChunk] = []

        # BC-008: Check store health before searching
        if hasattr(
                self._store,
                "health_check") and not self._store.health_check():
            logger.warning(
                "rag_vector_store_unhealthy_keyword_fallback",
                company_id=company_id,
            )
            return await self._keyword_search(
                query=query,
                company_id=company_id,
                variant_type=variant_type,
                top_k=top_k,
                filters=filters,
                start_time=start_time,
            )

        for exp_query in expanded_queries:
            exp_embedding = query_embedding
            if exp_query != query:
                exp_embedding = await self._generate_embedding(exp_query) or query_embedding

            try:
                search_results = self._store.search(
                    query_embedding=exp_embedding,
                    company_id=company_id,
                    top_k=top_k,
                    filters=filters if config.get("use_metadata_filters") else None,
                )
            except Exception as exc:
                # BC-008: Fallback to keyword search
                logger.warning(
                    "rag_vector_search_failed_keyword_fallback",
                    company_id=company_id,
                    error=str(exc),
                )
                return await self._keyword_search(
                    query=query,
                    company_id=company_id,
                    variant_type=variant_type,
                    top_k=top_k,
                    filters=filters,
                    start_time=start_time,
                )

            for sr in search_results:
                if sr.score >= similarity_threshold:
                    chunk = RAGChunk(
                        chunk_id=sr.chunk_id,
                        document_id=sr.document_id,
                        content=sr.content,
                        score=sr.score,
                        metadata=sr.metadata,
                    )
                    all_chunks.append(chunk)

        # ── Step 5: Reranking (high_parwa only) ──────────────────
        if config.get("use_reranking") and all_chunks:
            all_chunks = self._rerank(query, all_chunks)

        # ── Step 6: Citation tracking (high_parwa only) ──────────
        if config.get("use_citation_tracking") and all_chunks:
            all_chunks = self._add_citations(all_chunks)

        # ── Step 7: Deduplicate and limit ────────────────────────
        seen = set()
        unique_chunks = []
        for chunk in all_chunks:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                unique_chunks.append(chunk)

        final_chunks = unique_chunks[:top_k]
        retrieval_time_ms = round((time.monotonic() - start_time) * 1000, 2)

        result = RAGResult(
            chunks=final_chunks,
            total_found=len(unique_chunks),
            retrieval_time_ms=retrieval_time_ms,
            query_embedding_time_ms=embedding_time_ms,
            filters_applied=filters if config.get("use_metadata_filters") else {},
            variant_tier_used=variant_type,
        )

        # ── Step 8: Cache result ─────────────────────────────────
        await self._store_cache(company_id, cache_key, result)

        logger.info(
            "rag_retrieval_complete",
            company_id=company_id,
            variant_type=variant_type,
            chunks_found=result.total_found,
            chunks_returned=len(result.chunks),
            retrieval_time_ms=retrieval_time_ms,
        )

        return result

    # ── Embedding Generation ──────────────────────────────────────

    async def _generate_embedding(
        self, text: str
    ) -> Optional[List[float]]:
        """Generate query embedding using EmbeddingService.

        Falls back to the store's own embedding generator if the service
        is unavailable (BC-008).
        """
        if not text or not text.strip():
            return None

        # Try real embedding service first
        try:
            from app.services.embedding_service import EmbeddingService
            svc = EmbeddingService(company_id="rag_query")
            embedding = svc.generate_embedding(text)
            if embedding:
                return embedding
        except Exception as exc:
            logger.debug(
                "rag_embedding_service_unavailable",
                error=str(exc),
            )

        # BC-008: Fallback to store's own generator (e.g. MockVectorStore)
        if hasattr(self._store, '_generate_embedding'):
            try:
                return self._store._generate_embedding(text)
            except Exception as exc:
                logger.warning(
                    "rag_store_embedding_failed",
                    error=str(exc),
                )

        return None

    # ── Keyword Search Fallback (BC-008) ──────────────────────────

    async def _keyword_search(
        self,
        query: str,
        company_id: str,
        variant_type: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
        start_time: float,
    ) -> RAGResult:
        """Fallback keyword-based search when vector search fails.

        BC-008: Graceful degradation — never returns an error.
        """
        query_lower = query.lower()
        query_words = set(re.findall(r"\b\w+\b", query_lower))

        config = VARIANT_CONFIG.get(variant_type, VARIANT_CONFIG["parwa"])
        # G9-GAP-12 FIX: Log warning for unknown variant_type in keyword
        # fallback
        if variant_type not in VARIANT_CONFIG:
            logger.warning(
                "rag_unknown_variant_type_keyword_fallback",
                variant_type=variant_type,
                company_id=company_id,
            )
        chunks: List[RAGChunk] = []

        try:
            # Get all documents for this company
            # G9-GAP-07 FIX: Use public get_all_documents() method instead of
            # accessing private _store._store attribute directly
            company_docs: Dict[str, Any] = {}
            if hasattr(self._store, 'get_all_documents'):
                company_docs = self._store.get_all_documents(company_id)
            elif hasattr(self._store, '_store'):
                company_docs = self._store._store.get(company_id, {})
            for doc_id, doc_data in company_docs.items():
                for chunk in doc_data.get("chunks", []):
                    # Score based on word overlap — handle both dict and
                    # StoredChunk
                    if isinstance(chunk, dict):
                        content_lower = chunk.get("content", "").lower()
                        chunk_id = chunk.get("chunk_id", "")
                        document_id = doc_id
                        chunk_metadata = chunk.get("metadata", {})
                    else:
                        content_lower = chunk.content.lower()
                        chunk_id = chunk.chunk_id
                        document_id = chunk.document_id
                        chunk_metadata = chunk.metadata
                    content_words = set(re.findall(r"\b\w+\b", content_lower))
                    overlap = query_words & content_words
                    if overlap:
                        score = len(overlap) / max(len(query_words), 1)
                        chunks.append(
                            RAGChunk(
                                chunk_id=chunk_id,
                                document_id=document_id,
                                content=content_lower,
                                score=round(score, 4),
                                metadata=chunk_metadata,
                            )
                        )
        except Exception as exc:
            logger.warning(
                "rag_keyword_search_failed",
                error=str(exc),
            )

        # Sort by score descending
        chunks.sort(key=lambda c: c.score, reverse=True)
        final_chunks = chunks[:top_k]

        retrieval_time_ms = round((time.monotonic() - start_time) * 1000, 2)

        return RAGResult(
            chunks=final_chunks,
            total_found=len(chunks),
            retrieval_time_ms=retrieval_time_ms,
            query_embedding_time_ms=0.0,
            filters_applied=filters or {},
            variant_tier_used=variant_type,
            degradation_used=True,
        )

    # ── Query Expansion (high_parwa) ──────────────────────────────

    def _expand_query(self, query: str) -> List[str]:
        """Expand query with synonyms for better recall.

        Returns original query + expanded queries (max 3 total).
        """
        query_lower = query.lower()
        words = set(re.findall(r"\b\w+\b", query_lower))

        expansions: List[str] = []
        for word, synonyms in QUERY_SYNONYMS.items():
            if word in words:
                for synonym in synonyms[:1]:  # Add at most 1 synonym per word
                    expanded = re.sub(
                        r"\b" + re.escape(word) + r"\b",
                        synonym,
                        query_lower,
                        count=1,
                    )
                    if expanded != query_lower:
                        expansions.append(expanded)

        # Return original + up to 2 expansions
        return [query] + expansions[:2]

    # ── Reranking (high_parwa) ────────────────────────────────────

    def _rerank(self, query: str, chunks: List[RAGChunk]) -> List[RAGChunk]:
        """Rerank chunks based on query-chunk similarity.

        Uses a simple BM25-inspired scoring:
        - Boost for exact phrase match
        - Boost for query word density in chunk
        - Boost for chunk position (earlier chunks are preferred)
        """
        query_lower = query.lower()
        query_words = set(re.findall(r"\b\w+\b", query_lower))
        if not query_words:
            return chunks

        reranked = []
        for i, chunk in enumerate(chunks):
            content_lower = chunk.content.lower()
            content_words = set(re.findall(r"\b\w+\b", content_lower))

            # Word overlap ratio
            overlap = query_words & content_words
            word_density = len(overlap) / max(len(query_words), 1)

            # Exact phrase bonus
            phrase_bonus = 0.1 if query_lower in content_lower else 0.0

            # Position bonus (earlier chunks get small boost)
            position_bonus = 0.01 * (1 - i / max(len(chunks), 1))

            # Combine original score with reranking signals
            rerank_score = chunk.score * 0.6 + word_density * \
                0.3 + phrase_bonus + position_bonus

            reranked.append(RAGChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=round(min(rerank_score, 1.0), 6),
                metadata=chunk.metadata,
            ))

        reranked.sort(key=lambda c: c.score, reverse=True)
        return reranked

    # ── Citation Tracking (high_parwa) ────────────────────────────

    def _add_citations(self, chunks: List[RAGChunk]) -> List[RAGChunk]:
        """Add citation references to chunks.

        Format: [Source: {source}] at the beginning of citation field.
        """
        for chunk in chunks:
            source = chunk.metadata.get("source", "Knowledge Base")
            page = chunk.metadata.get("page")
            section = chunk.metadata.get("section")

            citation = f"[Source: {source}]"
            if page:
                citation += f" (p. {page})"
            if section:
                citation += f" — {section}"

            chunk.citation = citation

        return chunks

    # ── Cache Methods ─────────────────────────────────────────────

    @staticmethod
    def _build_cache_key(
        query: str,
        company_id: str,
        variant_type: str,
        filters: Optional[Dict[str, Any]],
    ) -> str:
        """Build a deterministic cache key."""
        query_hash = hashlib.sha256(
            query.lower().strip().encode("utf-8")).hexdigest()[:16]
        filter_hash = ""
        if filters:
            import json
            filter_hash = hashlib.sha256(
                json.dumps(filters, sort_keys=True).encode("utf-8")
            ).hexdigest()[:8]
        return f"rag:{company_id}:{variant_type}:{query_hash}:{filter_hash}"

    async def _check_cache(
        self, company_id: str, cache_key: str
    ) -> Optional[RAGResult]:
        """Check cache for a previous result."""
        try:
            from app.core.redis import cache_get

            cached = await cache_get(company_id, cache_key)
            if cached and isinstance(cached, dict):
                chunks = [
                    RAGChunk(
                        chunk_id=c["chunk_id"],
                        document_id=c["document_id"],
                        content=c["content"],
                        score=c["score"],
                        metadata=c.get("metadata", {}),
                        citation=c.get("citation"),
                    )
                    for c in cached.get("chunks", [])
                ]
                return RAGResult(
                    chunks=chunks, total_found=cached.get(
                        "total_found", 0), retrieval_time_ms=cached.get(
                        "retrieval_time_ms", 0.0), query_embedding_time_ms=cached.get(
                        "query_embedding_time_ms", 0.0), filters_applied=cached.get(
                        "filters_applied", {}), variant_tier_used=cached.get(
                        "variant_tier_used", "parwa"), cached=True, )
        except Exception as exc:
            logger.warning(
                "rag_cache_read_failed",
                error=str(exc),
                cache_key=cache_key)
        return None

    async def _store_cache(
        self, company_id: str, cache_key: str, result: RAGResult
    ) -> None:
        """Store a result in cache."""
        try:
            from app.core.redis import cache_set

            await cache_set(
                company_id,
                cache_key,
                result.to_dict(),
                ttl_seconds=CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.debug(
                "rag_cache_write_failed",
                error=str(exc),
                cache_key=cache_key)
