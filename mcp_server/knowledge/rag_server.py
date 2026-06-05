"""
PARWA MCP — RAG Server (v2.0.0)

Provides Retrieval-Augmented Generation query tools backed by the
PARWA backend REST API.  All tool handlers call the real backend
endpoints and fall back to graceful error responses (never mock data)
when the backend is unreachable.

Tools:
  - rag_query        — Retrieve relevant document chunks via RAG pipeline
  - rag_rerank       — Re-rank chunks using BM25-inspired cross-encoder
  - semantic_search  — High-precision semantic search (parwa_high variant)

REST endpoints:
  - POST /knowledge/rag/query
  - POST /knowledge/rag/rerank
  - POST /knowledge/rag/semantic-search
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter

from mcp_server.base_server import MCPServerBase, MCPRegistry, get_logger
from mcp_server.config import get_settings
from mcp_server.models import (
    RAGQueryRequest,
    RAGQueryResult,
    ToolCategory,
    ToolDefinition,
    ToolInvokeResponse,
)

logger = get_logger("mcp.rag_server")


# ═══════════════════════════════════════════════════════════════════
# Backend API Client Helper
# ═══════════════════════════════════════════════════════════════════


class _BackendClient:
    """Helper for calling the PARWA backend API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.BACKEND_URL.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def post(self, path: str, json_data: dict) -> dict:
        client = await self._get_client()
        try:
            response = await client.post(path, json=json_data)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("backend_api_error", path=path, error=str(exc))
            return {"status": "error", "data": {"message": str(exc)}}

    async def get(self, path: str) -> dict:
        client = await self._get_client()
        try:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("backend_api_error", path=path, error=str(exc))
            return {"status": "error", "data": {"message": str(exc)}}

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


# ═══════════════════════════════════════════════════════════════════
# BM25-inspired Reranker (local, mirrors backend rag_reranking logic)
# ═══════════════════════════════════════════════════════════════════

_STOP_WORDS: set[str] = {
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
    "of", "and", "or", "but", "not", "with", "as", "by", "from",
    "this", "that", "these", "those", "be", "are", "was", "were",
    "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can",
    "shall", "must", "i", "you", "he", "she", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "its", "what", "which", "who", "whom",
    "how", "when", "where", "why", "if", "then", "so", "no",
    "yes", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "only", "own", "same",
    "than", "too", "very", "just", "about", "above", "also",
    "into", "over", "after", "before", "between", "through",
    "during", "up", "out", "off", "again", "once", "here",
    "there", "any", "much", "many",
}


def _bm25_rerank(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """Re-rank chunks using a BM25-inspired scoring approach.

    Combines the original retrieval score with keyword overlap,
    exact-phrase matching, and position recency — mirroring the
    backend's CrossEncoderReranker logic.
    """
    if not chunks or not query:
        return chunks[:top_k]

    query_lower = query.lower()
    query_tokens = re.findall(r"\b[a-z0-9]+\b", query_lower)
    query_terms = set(query_tokens) - _STOP_WORDS

    if not query_terms:
        return chunks[:top_k]

    # Build query bigrams
    query_bigrams: set[str] = set()
    for i in range(len(query_tokens) - 1):
        query_bigrams.add(f"{query_tokens[i]} {query_tokens[i + 1]}")

    # Compute IDF across chunk corpus
    total_docs = max(len(chunks), 1)
    df: dict[str, int] = {}
    for chunk in chunks:
        seen: set[str] = set()
        content_lower = chunk.get("content", "").lower()
        tokens = set(re.findall(r"\b[a-z0-9]+\b", content_lower))
        for term in query_terms:
            if term in tokens and term not in seen:
                df[term] = df.get(term, 0) + 1
                seen.add(term)

    idf_scores: dict[str, float] = {}
    for term in query_terms:
        doc_freq = df.get(term, 0)
        idf_val = math.log(
            (total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0
        )
        idf_scores[term] = max(idf_val, 0.0)

    k1, b, avg_dl = 1.5, 0.75, 200.0
    scored_chunks: list[tuple[float, dict]] = []

    for idx, chunk in enumerate(chunks):
        content_lower = chunk.get("content", "").lower()
        content_tokens = re.findall(r"\b[a-z0-9]+\b", content_lower)
        content_terms = set(content_tokens)
        content_term_freq: dict[str, int] = {}
        for t in content_tokens:
            content_term_freq[t] = content_term_freq.get(t, 0) + 1

        # 1. Original score (normalised) — 40%
        original_score = chunk.get("score", 0.0)

        # 2. BM25 keyword density — 30%
        keyword_score = 0.0
        matched_terms = 0
        content_length = max(len(content_tokens), 1)
        for term in query_terms:
            if term not in content_terms:
                continue
            tf = content_term_freq.get(term, 0)
            idf = idf_scores.get(term, 1.0)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (content_length / avg_dl))
            keyword_score += idf * (numerator / denominator)
            matched_terms += 1

        if query_terms:
            normalisation = matched_terms / len(query_terms)
        else:
            normalisation = 0.0
        raw_kw = keyword_score * normalisation
        keyword_score_scaled = raw_kw / (raw_kw + 1.0)

        # 3. Exact phrase bonus — 10%
        phrase_bonus = 0.15 if query_lower in content_lower else 0.0

        # 4. Bigram overlap — 10%
        content_bigrams: set[str] = set()
        for i in range(len(content_tokens) - 1):
            content_bigrams.add(f"{content_tokens[i]} {content_tokens[i + 1]}")
        bigram_overlap = 0.0
        if query_bigrams:
            bg_matches = query_bigrams & content_bigrams
            bigram_overlap = len(bg_matches) / len(query_bigrams) * 0.1

        # 5. Position recency — 10%
        position_bonus = 0.05 * (1.0 - idx / total_docs)

        final_score = (
            original_score * 0.40
            + keyword_score_scaled * 0.30
            + phrase_bonus
            + bigram_overlap
            + position_bonus
        )

        reranked_chunk = {**chunk, "rerank_score": round(min(final_score, 1.0), 6)}
        scored_chunks.append((final_score, reranked_chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:top_k]]


# ═══════════════════════════════════════════════════════════════════
# RAG Server
# ═══════════════════════════════════════════════════════════════════


class RAGServer(MCPServerBase):
    """MCP sub-server for RAG (Retrieval-Augmented Generation) queries."""

    name = "rag_server"
    description = "RAG pipeline queries for contextual document retrieval"
    category = ToolCategory.KNOWLEDGE
    version = "2.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._backend = _BackendClient()

    def register_tools(self, registry: MCPRegistry) -> None:
        """Register RAG tools."""
        registry.register_tool(
            ToolDefinition(
                name="rag_query",
                description="Query the RAG pipeline to retrieve relevant document chunks. "
                            "Returns top-k chunks with relevance scores for AI context enrichment. "
                            "Calls the backend RAG search API for real-time retrieval.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query for retrieval",
                        },
                        "variant_type": {
                            "type": "string",
                            "enum": ["mini_parwa", "parwa", "parwa_high"],
                            "description": "RAG variant tier (default: parwa)",
                            "default": "parwa",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of chunks to retrieve (1-20)",
                            "default": 5,
                        },
                        "filters": {
                            "type": "object",
                            "description": "Metadata filters for retrieval",
                        },
                    },
                    "required": ["query"],
                },
                tags=["rag", "retrieval", "knowledge", "vector"],
                version="2.0.0",
            ),
            handler=self._invoke_rag_query,
        )

        registry.register_tool(
            ToolDefinition(
                name="rag_rerank",
                description="Re-rank a set of retrieved chunks for better relevance ordering. "
                            "Uses BM25-inspired cross-encoder scoring combining original "
                            "vector similarity with keyword overlap and phrase matching.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Original query for re-scoring",
                        },
                        "chunks": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Chunks to re-rank (each must have 'content' and 'score')",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of top chunks to return after reranking",
                            "default": 5,
                        },
                    },
                    "required": ["query", "chunks"],
                },
                tags=["rag", "reranking", "relevance"],
                version="2.0.0",
            ),
            handler=self._invoke_rag_rerank,
        )

        registry.register_tool(
            ToolDefinition(
                name="semantic_search",
                description="High-precision semantic search using the parwa_high variant. "
                            "Returns top-K relevant chunks with source attribution and "
                            "confidence scores. Best for knowledge-intensive queries where "
                            "accuracy matters more than speed.",
                category=self.category,
                server=self.name,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results (1-20)",
                            "default": 10,
                        },
                        "filters": {
                            "type": "object",
                            "description": "Metadata filters",
                        },
                    },
                    "required": ["query"],
                },
                tags=["rag", "semantic", "search", "knowledge"],
                version="2.0.0",
            ),
            handler=self._invoke_semantic_search,
        )

    def get_router(self) -> APIRouter:
        """Return the RAG REST router."""
        router = APIRouter(prefix="/knowledge/rag", tags=["Knowledge — RAG"])

        @router.post("/query", response_model=list[RAGQueryResult])
        async def rag_query(request: RAGQueryRequest) -> list[RAGQueryResult]:
            """Query the RAG pipeline via REST."""
            result = await self._invoke_rag_query(request.model_dump())
            if result.success and result.data:
                return [RAGQueryResult(**r) for r in result.data]
            return []

        @router.post("/rerank")
        async def rag_rerank(body: dict) -> dict:
            """Re-rank chunks via REST."""
            result = await self._invoke_rag_rerank(body)
            if result.success:
                return {"status": "ok", "data": result.data}
            return {"status": "error", "data": {"message": result.error}}

        @router.post("/semantic-search")
        async def semantic_search(body: dict) -> dict:
            """High-precision semantic search via REST."""
            result = await self._invoke_semantic_search(body)
            if result.success:
                return {"status": "ok", "data": result.data}
            return {"status": "error", "data": {"message": result.error}}

        return router

    # ── Tool Handlers ─────────────────────────────────────────────

    async def _invoke_rag_query(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle rag_query tool invocation.

        Calls the backend RAG search endpoint and returns real retrieval
        results.  Falls back to a graceful error if the backend is
        unreachable — never returns mock data.
        """
        start_time = time.monotonic()
        params = parameters or {}
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "")

        query = params.get("query", "")
        variant_type = params.get("variant_type", "parwa")
        top_k = params.get("top_k", 5)
        filters = params.get("filters")

        logger.info(
            "rag_query_invoked",
            query=query[:100],
            variant_type=variant_type,
            top_k=top_k,
            tenant_id=tenant_id,
        )

        if not query.strip():
            return ToolInvokeResponse(
                success=False,
                tool_name="rag_query",
                error="query is required and must not be empty",
            )

        # Build request body for backend API
        request_body: dict[str, Any] = {
            "query": query.strip(),
            "variant_type": variant_type,
            "top_k": top_k,
        }
        if filters:
            request_body["filters"] = filters

        # Call backend API
        backend_response = await self._backend.post("/api/rag/search", request_body)

        if backend_response.get("status") == "error":
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            error_msg = backend_response.get("data", {}).get("message", "Backend unreachable")
            logger.error(
                "rag_query_backend_error",
                error=error_msg,
                elapsed_ms=elapsed_ms,
            )
            return ToolInvokeResponse(
                success=False,
                tool_name="rag_query",
                error=f"RAG backend unavailable: {error_msg}",
                metadata={
                    "query": query,
                    "elapsed_ms": elapsed_ms,
                    "backend_status": "error",
                },
            )

        # Parse backend response
        data = backend_response.get("data", {})
        chunks_raw = data.get("chunks", [])

        results: list[dict] = []
        for chunk in chunks_raw:
            results.append({
                "content": chunk.get("content", ""),
                "source": chunk.get("document_id", ""),
                "score": chunk.get("score", 0.0),
                "metadata": {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "document_id": chunk.get("document_id", ""),
                    "citation": chunk.get("citation", ""),
                    "tenant_id": tenant_id,
                },
            })

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return ToolInvokeResponse(
            success=True,
            tool_name="rag_query",
            data=results,
            metadata={
                "query": query,
                "variant_type": variant_type,
                "top_k": top_k,
                "retrieved_count": len(results),
                "total_found": data.get("total_found", len(results)),
                "elapsed_ms": elapsed_ms,
                "variant_tier_used": data.get("variant_tier_used", variant_type),
                "tenant_id": tenant_id,
            },
        )

    async def _invoke_rag_rerank(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle rag_rerank tool invocation.

        Uses BM25-inspired reranking that mirrors the backend's
        CrossEncoderReranker logic. Operates locally on the provided
        chunks without requiring a backend call.
        """
        start_time = time.monotonic()
        params = parameters or {}
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "")

        query = params.get("query", "")
        chunks = params.get("chunks", [])
        top_k = params.get("top_k", 5)

        logger.info(
            "rag_rerank_invoked",
            query=query[:100],
            chunk_count=len(chunks),
            top_k=top_k,
            tenant_id=tenant_id,
        )

        if not query.strip():
            return ToolInvokeResponse(
                success=False,
                tool_name="rag_rerank",
                error="query is required for reranking",
            )

        if not chunks:
            return ToolInvokeResponse(
                success=True,
                tool_name="rag_rerank",
                data=[],
                metadata={
                    "original_count": 0,
                    "reranked_count": 0,
                    "tenant_id": tenant_id,
                },
            )

        # Apply BM25-inspired reranking
        reranked = _bm25_rerank(query, chunks, top_k=top_k)

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return ToolInvokeResponse(
            success=True,
            tool_name="rag_rerank",
            data=reranked,
            metadata={
                "original_count": len(chunks),
                "reranked_count": len(reranked),
                "top_k": top_k,
                "elapsed_ms": elapsed_ms,
                "method": "bm25_cross_encoder",
                "tenant_id": tenant_id,
            },
        )

    async def _invoke_semantic_search(
        self, parameters: dict | None = None, context: dict | None = None
    ) -> ToolInvokeResponse:
        """Handle semantic_search tool invocation.

        Uses the parwa_high variant for best-quality results, which
        applies the full 3-step pipeline: retrieve → rewrite → rerank.
        """
        start_time = time.monotonic()
        params = parameters or {}
        ctx = context or {}
        tenant_id = ctx.get("tenant_id", "")

        query = params.get("query", "")
        top_k = params.get("top_k", 10)
        filters = params.get("filters")

        logger.info(
            "semantic_search_invoked",
            query=query[:100],
            top_k=top_k,
            tenant_id=tenant_id,
        )

        if not query.strip():
            return ToolInvokeResponse(
                success=False,
                tool_name="semantic_search",
                error="query is required and must not be empty",
            )

        # Call backend with parwa_high for best results
        request_body: dict[str, Any] = {
            "query": query.strip(),
            "variant_type": "parwa_high",
            "top_k": top_k,
        }
        if filters:
            request_body["filters"] = filters

        backend_response = await self._backend.post("/api/rag/search", request_body)

        if backend_response.get("status") == "error":
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            error_msg = backend_response.get("data", {}).get("message", "Backend unreachable")
            logger.error(
                "semantic_search_backend_error",
                error=error_msg,
                elapsed_ms=elapsed_ms,
            )
            return ToolInvokeResponse(
                success=False,
                tool_name="semantic_search",
                error=f"Semantic search backend unavailable: {error_msg}",
                metadata={
                    "query": query,
                    "elapsed_ms": elapsed_ms,
                    "backend_status": "error",
                },
            )

        # Parse and format results with confidence scores
        data = backend_response.get("data", {})
        chunks_raw = data.get("chunks", [])

        results: list[dict] = []
        for chunk in chunks_raw:
            score = chunk.get("score", 0.0)
            # Derive a confidence level from the score
            if score >= 0.85:
                confidence = "high"
            elif score >= 0.60:
                confidence = "medium"
            else:
                confidence = "low"

            results.append({
                "content": chunk.get("content", ""),
                "source": chunk.get("document_id", ""),
                "confidence_score": round(score, 4),
                "confidence_level": confidence,
                "metadata": {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "document_id": chunk.get("document_id", ""),
                    "citation": chunk.get("citation", ""),
                    "tenant_id": tenant_id,
                },
            })

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)

        return ToolInvokeResponse(
            success=True,
            tool_name="semantic_search",
            data=results,
            metadata={
                "query": query,
                "variant_type": "parwa_high",
                "top_k": top_k,
                "retrieved_count": len(results),
                "total_found": data.get("total_found", len(results)),
                "elapsed_ms": elapsed_ms,
                "variant_tier_used": data.get("variant_tier_used", "parwa_high"),
                "tenant_id": tenant_id,
            },
        )


# Singleton instance
rag_server = RAGServer()
