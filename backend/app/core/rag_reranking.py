"""
RAG Reranking Module (F-064) — Knowledge Base Search (Part 2)

Post-retrieval reranking, context assembly, citation tracking, and
query rewriting for the PARWA RAG pipeline.  Operates on the output of
`rag_retrieval.RAGRetriever.retrieve()`.

Variant-specific behaviour
--------------------------
  mini_parwa   — SKIP reranking, return chunks sorted by original score.
  parwa        — Cross-encoder reranking (cosine + keyword overlap).
  high_parwa   — Retrieve → Rewrite query → Rerank (3-step pipeline).

BC-001: Tenant isolation — every operation is scoped to company_id.
BC-008: Graceful degradation — failures produce partial/empty results,
        never raise to callers.
GAP-004: All `execute()` calls are guarded by `asyncio.wait_for()` with
         a configurable timeout, max_retries=1, and concurrency-limited
         via `asyncio.Semaphore(5)`.

Parent: Week 9 Day 8 (Monday)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.logger import get_logger
from app.core.rag_retrieval import (
    RAGChunk,
    RAGResult,
)

logger = get_logger("rag_reranking")

# ── Constants & Enums ──────────────────────────────────────────────


class RerankStrategy(Enum):
    """Strategy selector for reranking behaviour per variant."""

    SKIP = "skip"                      # mini_parwa — no reranking
    CROSS_ENCODER = "cross_encoder"    # parwa    — cosine + keyword
    REWRITE_RERANK = "rewrite_rerank"  # high_parwa — rewrite then rerank


VARIANT_RERANK_CONFIG: Dict[str, Dict[str, Any]] = {
    "mini_parwa": {
        "strategy": RerankStrategy.SKIP,
        "max_context_tokens": 4096,
        "timeout_seconds": 5,
        "default_top_k": 3,
    },
    "parwa": {
        "strategy": RerankStrategy.CROSS_ENCODER,
        "max_context_tokens": 8192,
        "timeout_seconds": 10,
        "default_top_k": 5,
    },
    "high_parwa": {
        "strategy": RerankStrategy.REWRITE_RERANK,
        "max_context_tokens": 16384,
        "timeout_seconds": 15,
        "default_top_k": 10,
    },
}

# GAP-004: Concurrency limit for reranking operations
_RERANK_CONCURRENCY_LIMIT = 5

# GAP-004: Default timeout in seconds for execute() calls
_EXECUTE_TIMEOUT_SECONDS = 10.0

# GAP-004: Maximum retries on timeout
_MAX_RETRIES = 1

# Cache TTL for reranked results (seconds)
_RERANK_CACHE_TTL = 120

# Sentence-end pattern for smart truncation
_SENTENCE_END_RE = re.compile(r"[.!?]\s+")

# Approximate token-to-character ratio (safe lower-bound for English)
_CHARS_PER_TOKEN = 4

# ── Stop-word set for TF-IDF style keyword scoring ────────────────

_STOP_WORDS: Set[str] = {
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


# ── Data Classes ───────────────────────────────────────────────────


@dataclass
class AssembledContext:
    """Result of assembling retrieved chunks into a single context string.

    Attributes:
        context_string:   The concatenated, optionally truncated context.
        total_tokens:     Approximate token count of ``context_string``.
        chunks_used:      Which chunks were included (in order).
        citations:        Citation objects for each included chunk.
        truncated:        Whether the context was truncated to fit
                          ``max_tokens``.
    """

    context_string: str = ""
    total_tokens: int = 0
    chunks_used: List[RAGChunk] = field(default_factory=list)
    citations: List[Citation] = field(
        default_factory=list)  # type: ignore[assignment]
    truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_string": self.context_string,
            "total_tokens": self.total_tokens,
            "chunks_used_count": len(self.chunks_used),
            "citations_count": len(self.citations),
            "truncated": self.truncated,
            "chunk_ids": [c.chunk_id for c in self.chunks_used],
        }


@dataclass
class Citation:
    """A citation tracking which chunk contributed to the context.

    Attributes:
        chunk_id:            Unique chunk identifier.
        document_id:         Parent document identifier.
        relevance_score:     Final reranking score for this chunk.
        position_in_context: Character offset where this chunk starts
                             in the assembled context string.
        excerpt:             A short excerpt from the chunk (first ~200 chars).
    """

    chunk_id: str
    document_id: str
    relevance_score: float
    position_in_context: int
    excerpt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "relevance_score": round(self.relevance_score, 6),
            "position_in_context": self.position_in_context,
            "excerpt": self.excerpt,
        }


# ── MetadataFilter ────────────────────────────────────────────────


class MetadataFilter:
    """Filter a list of ``RAGChunk`` objects using AND-combined metadata rules.

    Supported filter keys:
        source_type  — exact string match on ``metadata["source_type"]``.
        date_from    — inclusive lower bound on ``metadata["date"]`` (ISO str).
        date_to      — inclusive upper bound on ``metadata["date"]`` (ISO str).
        category     — exact string match on ``metadata["category"]``.
        tags         — list of tags; chunk must contain **all** tags
                       (subset of ``metadata.get("tags", [])``).
        min_score    — float; chunks with ``score < min_score`` are dropped.
    """

    # Known metadata keys — unknown keys are silently ignored.
    _SUPPORTED_KEYS: Set[str] = {
        "source_type", "date_from", "date_to", "category", "tags", "min_score",
    }

    @classmethod
    def filter_chunks(
        cls,
        chunks: List[RAGChunk],
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RAGChunk]:
        """Apply metadata filters to a chunk list.

        Args:
            chunks:  Chunks to filter.
            filters: Dict of filter rules (AND-combined).

        Returns:
            Filtered list of chunks that match **all** active rules.
        """
        if not filters or not chunks:
            return list(chunks)

        # Normalise: only keep supported keys
        active_filters: Dict[str, Any] = {
            k: v for k, v in filters.items() if k in cls._SUPPORTED_KEYS
        }

        if not active_filters:
            return list(chunks)

        passed: List[RAGChunk] = []
        for chunk in chunks:
            if cls._chunk_matches(chunk, active_filters):
                passed.append(chunk)

        logger.debug(
            "metadata_filter_applied",
            input_count=len(chunks),
            output_count=len(passed),
            filter_keys=list(active_filters.keys()),
        )
        return passed

    @classmethod
    def _chunk_matches(cls, chunk: RAGChunk, filters: Dict[str, Any]) -> bool:
        """Return True if *chunk* satisfies every active filter rule."""
        meta = chunk.metadata or {}

        # source_type — exact match
        if "source_type" in filters:
            if meta.get("source_type") != filters["source_type"]:
                return False

        # category — exact match
        if "category" in filters:
            if meta.get("category") != filters["category"]:
                return False

        # date_from / date_to — inclusive range on metadata["date"]
        chunk_date = meta.get("date")
        if chunk_date:
            try:
                from datetime import datetime

                if isinstance(chunk_date, str):
                    chunk_dt = datetime.fromisoformat(chunk_date)
                elif isinstance(chunk_date, datetime):
                    chunk_dt = chunk_date
                else:
                    chunk_dt = None

                if chunk_dt is not None:
                    if "date_from" in filters:
                        from_val = filters["date_from"]
                        if isinstance(from_val, str):
                            from_dt = datetime.fromisoformat(from_val)
                        elif isinstance(from_val, datetime):
                            from_dt = from_val
                        else:
                            from_dt = None
                        if from_dt is not None and chunk_dt < from_dt:
                            return False

                    if "date_to" in filters:
                        to_val = filters["date_to"]
                        if isinstance(to_val, str):
                            to_dt = datetime.fromisoformat(to_val)
                        elif isinstance(to_val, datetime):
                            to_dt = to_val
                        else:
                            to_dt = None
                        if to_dt is not None and chunk_dt > to_dt:
                            return False
            except (ValueError, TypeError):
                # Malformed date — don't filter out; be lenient
                pass

        # tags — all requested tags must be present
        if "tags" in filters:
            required_tags: List[str] = filters["tags"]
            if isinstance(required_tags, str):
                required_tags = [required_tags]
            chunk_tags: List[str] = meta.get("tags", [])
            if not isinstance(chunk_tags, list):
                chunk_tags = []
            required_set = set(required_tags)
            chunk_tag_set = set(chunk_tags)
            if not required_set.issubset(chunk_tag_set):
                return False

        # min_score
        if "min_score" in filters:
            min_score_val = filters["min_score"]
            if isinstance(min_score_val, (int, float)):
                if chunk.score < float(min_score_val):
                    return False

        return True


# ── QueryRewriter ─────────────────────────────────────────────────


class QueryRewriter:
    """Expand and refine a user query using retrieved chunk content.

    Used exclusively by the ``high_parwa`` variant.  The rewriter reads the
    top retrieved chunks, extracts high-value terms, and produces a richer
    query that can improve reranking precision.

    BC-008: Always returns *something* — even on error, the original query
    is returned unchanged.
    """

    # Maximum number of expansion terms to add
    _MAX_EXPANSION_TERMS: int = 8

    # Minimum TF-IDF score a term must have to be considered "high-value"
    _MIN_TERM_SCORE: float = 0.15

    # Stop words to exclude from expansion
    _EXTRA_STOP_WORDS: Set[str] = _STOP_WORDS | {
        "also", "like", "get", "use", "using", "used", "make", "made",
        "know", "need", "want", "think", "thing", "things", "way",
    }

    @classmethod
    async def rewrite(
        cls,
        query: str,
        original_chunks: List[RAGChunk],
        company_id: str,
    ) -> str:
        """Rewrite *query* using content from *original_chunks*.

        The algorithm:
        1. Tokenise the original query.
        2. Build a TF-IDF-inspired vocabulary from the top chunks.
        3. Pick the highest-scoring terms that don't already appear in
           the query.
        4. Append the top expansion terms to produce a richer query.

        Args:
            query:           Original user query.
            original_chunks: Chunks retrieved for this query (pre-rerank).
            company_id:      Tenant identifier (BC-001).

        Returns:
            Rewritten query string (or the original on error/empty input).
        """
        if not query or not query.strip() or not original_chunks:
            return query

        try:
            query_terms: Set[str] = cls._tokenise(query)

            # Build corpus from top chunks (limit to first 5 for speed)
            corpus_chunks = original_chunks[:5]
            term_scores: Dict[str, float] = cls._build_term_scores(
                query_terms, corpus_chunks
            )

            # Pick top expansion terms not already in the query
            expansions: List[Tuple[str, float]] = sorted(
                term_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            added_terms: List[str] = []
            for term, score in expansions:
                if (
                    term not in query_terms
                    and score >= cls._MIN_TERM_SCORE
                    and len(added_terms) < cls._MAX_EXPANSION_TERMS
                ):
                    added_terms.append(term)

            if not added_terms:
                return query

            rewritten = f"{query} {' '.join(added_terms)}"

            logger.debug(
                "query_rewritten",
                company_id=company_id,
                original_query=query[:80],
                added_terms=added_terms,
                rewritten_length=len(rewritten),
            )

            return rewritten

        except Exception as exc:
            # BC-008: Never crash — return the original query
            logger.warning(
                "query_rewrite_failed_fallback_to_original",
                company_id=company_id,
                error=str(exc),
            )
            return query

    # ── Internal helpers ───────────────────────────────────────

    @classmethod
    def _tokenise(cls, text: str) -> Set[str]:
        """Lowercase tokeniser that strips punctuation and stop-words."""
        words = set(re.findall(r"\b[a-z0-9]+\b", text.lower()))
        return words - cls._EXTRA_STOP_WORDS

    @classmethod
    def _build_term_scores(
        cls,
        query_terms: Set[str],
        chunks: List[RAGChunk],
    ) -> Dict[str, float]:
        """Compute a TF-IDF-inspired score for every term in *chunks*.

        Terms already present in *query_terms* are deprioritised.
        """
        # Term frequency across all chunk contents
        tf: Dict[str, int] = {}
        # Number of chunks containing the term (for IDF)
        df: Dict[str, int] = {}
        total_chunks = max(len(chunks), 1)

        for chunk in chunks:
            seen_in_chunk: Set[str] = set()
            content_words = re.findall(r"\b[a-z0-9]+\b", chunk.content.lower())
            for word in content_words:
                if word not in cls._EXTRA_STOP_WORDS:
                    tf[word] = tf.get(word, 0) + 1
                    if word not in seen_in_chunk:
                        df[word] = df.get(word, 0) + 1
                        seen_in_chunk.add(word)

        scores: Dict[str, float] = {}
        for term, freq in tf.items():
            # IDF component
            idf = math.log(total_chunks / max(df.get(term, 1), 1)) + 1.0
            # Raw TF-IDF
            raw_score = (freq / max(total_chunks, 1)) * idf
            # Boost terms that partially match query terms
            boost = 0.0
            for qt in query_terms:
                if qt in term or term in qt:
                    boost = 0.3
                    break
            scores[term] = raw_score + boost

        return scores


# ── ContextWindowAssembler ────────────────────────────────────────


class ContextWindowAssembler:
    """Assemble retrieved chunks into a single context string that fits
    within a token budget.

    Features:
    - Approximate token counting (character-based heuristic).
    - Citation tracking: records which chunk contributed which part.
    - Smart truncation: never cuts mid-sentence when possible.

    BC-008: Always returns a valid ``AssembledContext``, even with empty
    input.
    """

    # Maximum excerpt length for citation excerpts
    _MAX_EXCERPT_LENGTH: int = 200

    # Separator between chunks
    _CHUNK_SEPARATOR: str = "\n\n---\n\n"

    @classmethod
    def assemble(
        cls,
        chunks: List[RAGChunk],
        max_tokens: int,
        query: str = "",
    ) -> AssembledContext:
        """Combine chunks into a context string respecting *max_tokens*.

        Args:
            chunks:     Ordered list of chunks (highest relevance first).
            max_tokens: Approximate token budget.
            query:      Original query (for logging only).

        Returns:
            ``AssembledContext`` with the assembled string, token count,
            included chunks, citations, and truncation flag.
        """
        result = AssembledContext()

        if not chunks or max_tokens <= 0:
            return result

        max_chars = max_tokens * _CHARS_PER_TOKEN
        # Reserve space for separators
        separator_len = len(cls._CHUNK_SEPARATOR)
        # Reserve a margin for rounding errors
        effective_max_chars = max_chars - (separator_len * 2)

        accumulated_parts: List[str] = []
        used_chunks: List[RAGChunk] = []
        current_length = 0
        # for CitationTracker
        positions: List[Tuple[str, str, float, int]] = []

        for chunk in chunks:
            content = chunk.content.strip()
            if not content:
                continue

            # Calculate length of this chunk with separator
            part_len = len(content) + \
                (separator_len if accumulated_parts else 0)

            if current_length + part_len > effective_max_chars:
                # We need to truncate this last chunk to fit
                remaining_chars = effective_max_chars - current_length
                if remaining_chars > 100:  # Only add if meaningful content fits
                    truncated_content = cls._smart_truncate(
                        content, remaining_chars)
                    if truncated_content:
                        pos_offset = current_length
                        accumulated_parts.append(truncated_content)
                        used_chunks.append(chunk)
                        positions.append((
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.score,
                            pos_offset,
                        ))
                        current_length += len(truncated_content)
                        result.truncated = True
                else:
                    result.truncated = True
                break

            pos_offset = current_length
            accumulated_parts.append(content)
            used_chunks.append(chunk)
            positions.append((
                chunk.chunk_id,
                chunk.document_id,
                chunk.score,
                pos_offset,
            ))
            current_length += part_len

        # Build context string
        context_string = cls._CHUNK_SEPARATOR.join(accumulated_parts)
        total_tokens = max(1, len(context_string) // _CHARS_PER_TOKEN)

        # Build citations from positions
        citations: List[Citation] = []
        for chunk_id, doc_id, score, pos in positions:
            excerpt = ""
            for ch in used_chunks:
                if ch.chunk_id == chunk_id:
                    excerpt = ch.content[: cls._MAX_EXCERPT_LENGTH]
                    if len(ch.content) > cls._MAX_EXCERPT_LENGTH:
                        excerpt += "..."
                    break
            citations.append(Citation(
                chunk_id=chunk_id,
                document_id=doc_id,
                relevance_score=score,
                position_in_context=pos,
                excerpt=excerpt,
            ))

        result.context_string = context_string
        result.total_tokens = total_tokens
        result.chunks_used = used_chunks
        result.citations = citations

        logger.debug(
            "context_assembled",
            chunks_input=len(chunks),
            chunks_used=len(used_chunks),
            total_tokens=total_tokens,
            max_tokens=max_tokens,
            truncated=result.truncated,
            query_length=len(query),
        )

        return result

    @classmethod
    def _smart_truncate(cls, text: str, max_chars: int) -> str:
        """Truncate *text* to approximately *max_chars* without cutting
        mid-sentence when possible.

        Strategy:
        1. If the text fits entirely, return it.
        2. Find the last sentence-ending punctuation within the limit.
        3. If no sentence boundary is found, fall back to the last
           whitespace within the limit.
        4. If still no good boundary, hard-truncate.
        """
        if len(text) <= max_chars:
            return text

        # Look for a sentence boundary within the limit
        truncated = text[:max_chars]
        last_sentence_end = -1
        for match in _SENTENCE_END_RE.finditer(truncated):
            if match.end() <= max_chars:
                last_sentence_end = match.end()

        if last_sentence_end > max_chars // 2:
            # Only use sentence boundary if it doesn't cut too much content
            return text[:last_sentence_end].rstrip()

        # Fallback: last whitespace
        last_space = truncated.rfind(" ")
        if last_space > max_chars // 2:
            return text[:last_space].rstrip()

        # Hard truncate
        return truncated.rstrip()


# ── CitationTracker ───────────────────────────────────────────────


class CitationTracker:
    """Track which chunks contributed to an assembled context.

    Produces structured ``Citation`` objects that can be attached to AI
    responses for transparency and traceability.
    """

    @classmethod
    def track_citations(
        cls,
        chunks: List[RAGChunk],
        assembled_context: AssembledContext,
    ) -> List[Citation]:
        """Build citation list from chunks and assembled context.

        Args:
            chunks:            All candidate chunks (pre-truncation).
            assembled_context: The assembled context (may be truncated).

        Returns:
            List of ``Citation`` objects for chunks that were included
            in the assembled context, ordered by position.
        """
        if not assembled_context.chunks_used:
            return []

        # Build a quick lookup: chunk_id -> chunk
        chunk_lookup: Dict[str, RAGChunk] = {
            c.chunk_id: c for c in chunks
        }

        # The assembler already built citations — use them but enrich
        # with metadata from the full chunk list
        enriched: List[Citation] = []
        seen_ids: Set[str] = set()

        for citation in assembled_context.citations:
            if citation.chunk_id in seen_ids:
                continue
            seen_ids.add(citation.chunk_id)

            full_chunk = chunk_lookup.get(citation.chunk_id)
            if full_chunk is not None:
                # Build a richer excerpt from the full chunk metadata
                source = full_chunk.metadata.get("source", "Knowledge Base")
                page = full_chunk.metadata.get("page")
                section = full_chunk.metadata.get("section")

                enriched_excerpt = citation.excerpt
                if source != "Knowledge Base" or page or section:
                    meta_str = f"[Source: {source}]"
                    if page:
                        meta_str += f" (p. {page})"
                    if section:
                        meta_str += f" — {section}"
                    enriched_excerpt = f"{meta_str} {citation.excerpt}"

                enriched_citation = Citation(
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    relevance_score=citation.relevance_score,
                    position_in_context=citation.position_in_context,
                    excerpt=enriched_excerpt,
                )
            else:
                enriched_citation = citation

            enriched.append(enriched_citation)

        logger.debug(
            "citations_tracked",
            citation_count=len(enriched),
            context_length=len(assembled_context.context_string),
        )

        return enriched


# ── CrossEncoderReranker ──────────────────────────────────────────


class CrossEncoderReranker:
    """Post-retrieval reranker for RAG chunks.

    Implements a lightweight cross-encoder scoring approach that combines:
    - Cosine similarity (from the original retrieval score)
    - BM25-inspired TF-IDF keyword overlap scoring
    - Exact-phrase matching bonus
    - Position recency bonus

    Variant behaviour:
      mini_parwa   — Skips reranking entirely; returns chunks sorted by
                     original vector similarity score.
      parwa        — Cross-encoder reranking (cosine + keyword overlap).
      high_parwa   — Full 3-step pipeline: retrieve → rewrite query → rerank.

    BC-001: All operations scoped to company_id.
    BC-008: Failures produce best-effort results, never exceptions.
    GAP-004: execute() guarded by asyncio.wait_for() with timeout,
             max_retries=1, and semaphore(5) concurrency limit.
    """

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(_RERANK_CONCURRENCY_LIMIT)
        self._metadata_filter = MetadataFilter()
        self._assembler = ContextWindowAssembler()
        self._citation_tracker = CitationTracker()
        self._query_rewriter = QueryRewriter()

    # ── Public API ─────────────────────────────────────────────

    async def rerank(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        variant_type: str = "parwa",
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RAGResult:
        """Rerank and optionally rewrite, filter, and assemble context.

        This is the main entry point.  It delegates to the appropriate
        variant strategy and returns a ``RAGResult`` containing the
        reranked (and possibly assembled) chunks.

        Args:
            chunks:       Retrieved chunks from ``RAGRetriever``.
            query:        User query.
            company_id:   Tenant identifier (BC-001).
            variant_type: One of ``mini_parwa``, ``parwa``, ``high_parwa``.
            top_k:        Maximum number of chunks to return.
            filters:      Optional metadata filters.

        Returns:
            ``RAGResult`` with reranked/filtered chunks and timing info.
        """
        start_time = time.monotonic()

        # BC-008: Guard against invalid inputs
        if not chunks:
            return RAGResult(
                variant_tier_used=variant_type,
                retrieval_time_ms=0.0,
            )

        # Resolve config with fallback
        if variant_type not in VARIANT_RERANK_CONFIG:
            logger.warning(
                "rerank_unknown_variant_type_defaulting",
                variant_type=variant_type,
                company_id=company_id,
            )
            variant_type = "parwa"

        config = VARIANT_RERANK_CONFIG[variant_type]
        strategy: RerankStrategy = config["strategy"]
        timeout_seconds: float = config["timeout_seconds"]

        # Resolve top_k from config if not explicitly provided
        if top_k is None:
            top_k = config.get("default_top_k", 5)

        try:
            # GAP-004: Execute with timeout, retry, and concurrency guard
            result = await self._execute_with_guard(
                chunks=chunks,
                query=query,
                company_id=company_id,
                variant_type=variant_type,
                top_k=top_k,
                strategy=strategy,
                filters=filters,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            # BC-008: On complete failure, return chunks sorted by original
            # score
            logger.warning(
                "rerank_execution_failed_fallback_to_original_order",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )
            sorted_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)
            retrieval_time_ms = round(
                (time.monotonic() - start_time) * 1000, 2)
            result = RAGResult(
                chunks=sorted_chunks[:top_k],
                total_found=len(sorted_chunks),
                retrieval_time_ms=retrieval_time_ms,
                variant_tier_used=variant_type,
                degradation_used=True,
            )

        return result

    # ── Full Pipeline (high_parwa) ─────────────────────────────

    async def _execute_rewrite_rerank(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
    ) -> RAGResult:
        """Execute the 3-step pipeline for high_parwa.

        Steps:
        1. Rewrite the query using chunk content.
        2. Rerank chunks against the rewritten query.
        3. Apply metadata filters.
        """
        start_time = time.monotonic()

        # Step 1: Query rewriting
        rewritten_query = await self._query_rewriter.rewrite(
            query=query,
            original_chunks=chunks,
            company_id=company_id,
        )

        # Step 2: Cross-encoder reranking with rewritten query
        reranked = self._cross_encoder_score(
            chunks=chunks,
            query=rewritten_query,
            company_id=company_id,
        )

        # Step 3: Metadata filtering
        if filters:
            reranked = MetadataFilter.filter_chunks(reranked, filters)

        # Sort by new score and limit
        reranked.sort(key=lambda c: c.score, reverse=True)
        final_chunks = reranked[:top_k]

        retrieval_time_ms = round((time.monotonic() - start_time) * 1000, 2)

        logger.info(
            "rerank_rewrite_rerank_complete",
            company_id=company_id,
            variant_type="high_parwa",
            original_query=query[:80],
            rewritten_query=rewritten_query[:80],
            chunks_input=len(chunks),
            chunks_output=len(final_chunks),
            retrieval_time_ms=retrieval_time_ms,
        )

        return RAGResult(
            chunks=final_chunks,
            total_found=len(reranked),
            retrieval_time_ms=retrieval_time_ms,
            variant_tier_used="high_parwa",
        )

    # ── Cross-Encoder Scoring ──────────────────────────────────

    def _cross_encoder_score(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
    ) -> List[RAGChunk]:
        """Score each chunk using a BM25-inspired cross-encoder approach.

        Scoring components:
        1. **Original score weight (40%)** — the vector similarity from
           the initial retrieval.
        2. **Keyword density (30%)** — TF-IDF-weighted overlap between
           query terms and chunk content.
        3. **Exact phrase bonus (10%)** — the full query appears in the
           chunk.
        4. **Bigram overlap (10%)** — consecutive query word pairs found
           in the chunk.
        5. **Position recency (10%)** — earlier chunks get a small boost,
           reflecting their original ranking quality.

        Returns a new list of ``RAGChunk`` with updated scores.
        """
        if not chunks or not query or not query.strip():
            return list(chunks)

        query_lower = query.lower()
        query_tokens: List[str] = re.findall(r"\b[a-z0-9]+\b", query_lower)
        query_terms: Set[str] = set(query_tokens) - _STOP_WORDS

        if not query_terms:
            return list(chunks)

        # Build query bigrams for bigram matching
        query_bigrams: Set[str] = set()
        for i in range(len(query_tokens) - 1):
            bigram = f"{query_tokens[i]} {query_tokens[i + 1]}"
            query_bigrams.add(bigram)

        # Compute IDF for query terms across all chunks (corpus-level)
        idf_scores: Dict[str, float] = self._compute_idf(query_terms, chunks)

        reranked: List[RAGChunk] = []
        total_chunks = max(len(chunks), 1)

        for idx, chunk in enumerate(chunks):
            content_lower = chunk.content.lower()
            content_tokens: List[str] = re.findall(
                r"\b[a-z0-9]+\b", content_lower
            )
            content_terms: Set[str] = set(content_tokens)
            content_term_freq: Dict[str, int] = {}
            for t in content_tokens:
                content_term_freq[t] = content_term_freq.get(t, 0) + 1

            # 1. Original score (normalised)
            original_score = chunk.score

            # 2. TF-IDF keyword density
            keyword_score = self._compute_bm25_score(
                query_terms=query_terms,
                content_terms=content_terms,
                content_term_freq=content_term_freq,
                idf_scores=idf_scores,
                content_length=len(content_tokens),
            )

            # 3. Exact phrase bonus
            phrase_bonus = 0.15 if query_lower in content_lower else 0.0

            # 4. Bigram overlap
            content_bigrams: Set[str] = set()
            for i in range(len(content_tokens) - 1):
                bg = f"{content_tokens[i]} {content_tokens[i + 1]}"
                content_bigrams.add(bg)
            bigram_overlap = 0.0
            if query_bigrams:
                bg_matches = query_bigrams & content_bigrams
                bigram_overlap = len(bg_matches) / len(query_bigrams) * 0.1

            # 5. Position recency bonus
            position_bonus = 0.05 * (1.0 - idx / total_chunks)

            # Weighted combination
            final_score = (
                original_score * 0.40
                + keyword_score * 0.30
                + phrase_bonus
                + bigram_overlap
                + position_bonus
            )

            reranked.append(RAGChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=round(min(final_score, 1.0), 6),
                metadata=chunk.metadata,
                citation=chunk.citation,
            ))

        # Sort by new score
        reranked.sort(key=lambda c: c.score, reverse=True)

        logger.debug(
            "cross_encoder_scoring_complete",
            company_id=company_id,
            chunks_scored=len(reranked),
            top_score=reranked[0].score if reranked else 0.0,
        )

        return reranked

    def _compute_bm25_score(
        self,
        query_terms: Set[str],
        content_terms: Set[str],
        content_term_freq: Dict[str, int],
        idf_scores: Dict[str, float],
        content_length: int,
    ) -> float:
        """Compute a BM25-inspired score for query-content overlap.

        Uses standard BM25 formula with k1=1.5, b=0.75.
        """
        k1 = 1.5
        b = 0.75
        avg_dl = 200.0  # Assume average document length of 200 tokens

        if content_length == 0:
            return 0.0

        total_score = 0.0
        matched_terms = 0

        for term in query_terms:
            if term not in content_terms:
                continue

            tf = content_term_freq.get(term, 0)
            idf = idf_scores.get(term, 1.0)

            # BM25 TF component
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (
                1 - b + b * (content_length / avg_dl)
            )

            total_score += idf * (numerator / denominator)
            matched_terms += 1

        # Normalise to [0, 1] range — approximate using matched fraction
        if query_terms:
            normalisation = matched_terms / len(query_terms)
        else:
            normalisation = 0.0

        # Scale to reasonable [0, 1] range using sigmoid-like transform
        raw = total_score * normalisation
        scaled = raw / (raw + 1.0)  # soft-clamp to [0, 1)

        return min(scaled, 1.0)

    def _compute_idf(
        self,
        query_terms: Set[str],
        chunks: List[RAGChunk],
    ) -> Dict[str, float]:
        """Compute IDF for query terms across the chunk corpus."""
        df: Dict[str, int] = {}
        total_docs = max(len(chunks), 1)

        for chunk in chunks:
            seen: Set[str] = set()
            tokens = set(re.findall(r"\b[a-z0-9]+\b", chunk.content.lower()))
            for term in query_terms:
                if term in tokens and term not in seen:
                    df[term] = df.get(term, 0) + 1
                    seen.add(term)

        idf: Dict[str, float] = {}
        for term in query_terms:
            doc_freq = df.get(term, 0)
            # Smooth IDF: log((N - df + 0.5) / (df + 0.5) + 1)
            idf_val = math.log(
                (total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0
            )
            idf[term] = max(idf_val, 0.0)

        return idf

    # ── GAP-004: Execution Guard ──────────────────────────────

    async def _execute_with_guard(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        variant_type: str,
        top_k: int,
        strategy: RerankStrategy,
        filters: Optional[Dict[str, Any]],
        timeout_seconds: float,
    ) -> RAGResult:
        """Execute the reranking pipeline with GAP-004 protections.

        Applies:
        - ``asyncio.Semaphore(5)`` for concurrency limiting.
        - ``asyncio.wait_for()`` with configurable timeout.
        - max_retries=1 on ``asyncio.TimeoutError``.
        """
        last_error: Optional[Exception] = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with self._semaphore:
                    result = await asyncio.wait_for(
                        self._execute_strategy(
                            chunks=chunks,
                            query=query,
                            company_id=company_id,
                            variant_type=variant_type,
                            top_k=top_k,
                            strategy=strategy,
                            filters=filters,
                        ),
                        timeout=timeout_seconds,
                    )
                    return result

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Reranking timed out after {timeout_seconds}s "
                    f"(attempt {attempt + 1}/{_MAX_RETRIES + 1})"
                )
                logger.warning(
                    "rerank_timeout_retrying",
                    company_id=company_id,
                    variant_type=variant_type,
                    attempt=attempt + 1,
                    max_retries=_MAX_RETRIES,
                    timeout_seconds=timeout_seconds,
                )

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "rerank_execution_error_retrying",
                    company_id=company_id,
                    variant_type=variant_type,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                break  # Non-timeout errors are not retried

        # All retries exhausted — raise so the caller's BC-008 guard
        # can catch and fall back
        raise last_error or RuntimeError(
            "rerank_execute_with_guard: unexpected state")

    async def _execute_strategy(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        variant_type: str,
        top_k: int,
        strategy: RerankStrategy,
        filters: Optional[Dict[str, Any]],
    ) -> RAGResult:
        """Dispatch to the appropriate strategy handler."""
        start_time = time.monotonic()

        if strategy == RerankStrategy.SKIP:
            result = self._strategy_skip(chunks, variant_type, top_k)
        elif strategy == RerankStrategy.CROSS_ENCODER:
            result = self._strategy_cross_encoder(
                chunks, query, company_id, variant_type, top_k, filters
            )
        elif strategy == RerankStrategy.REWRITE_RERANK:
            result = await self._strategy_rewrite_rerank(
                chunks, query, company_id, variant_type, top_k, filters
            )
        else:
            # Unknown strategy — fall back to skip
            logger.warning(
                "rerank_unknown_strategy_fallback_to_skip",
                strategy=str(strategy),
                company_id=company_id,
            )
            result = self._strategy_skip(chunks, variant_type, top_k)

        # Record retrieval time
        retrieval_time_ms = round((time.monotonic() - start_time) * 1000, 2)
        result.retrieval_time_ms = retrieval_time_ms

        return result

    # ── Strategy: SKIP (mini_parwa) ───────────────────────────

    def _strategy_skip(
        self,
        chunks: List[RAGChunk],
        variant_type: str,
        top_k: int,
    ) -> RAGResult:
        """mini_parwa strategy: return chunks sorted by original score.

        No cross-encoder, no rewriting — just sort and truncate.
        """
        sorted_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)
        final_chunks = sorted_chunks[:top_k]

        logger.debug(
            "rerank_strategy_skip",
            variant_type=variant_type,
            chunks_input=len(chunks),
            chunks_output=len(final_chunks),
        )

        return RAGResult(
            chunks=final_chunks,
            total_found=len(sorted_chunks),
            variant_tier_used=variant_type,
        )

    # ── Strategy: CROSS_ENCODER (parwa) ───────────────────────

    def _strategy_cross_encoder(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        variant_type: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
    ) -> RAGResult:
        """parwa strategy: cross-encoder reranking with metadata filtering."""
        # Apply metadata filters first (reduce the corpus)
        if filters:
            filtered = MetadataFilter.filter_chunks(chunks, filters)
        else:
            filtered = list(chunks)

        # Cross-encoder scoring
        reranked = self._cross_encoder_score(
            chunks=filtered,
            query=query,
            company_id=company_id,
        )

        final_chunks = reranked[:top_k]

        logger.debug(
            "rerank_strategy_cross_encoder",
            company_id=company_id,
            variant_type=variant_type,
            chunks_input=len(chunks),
            chunks_after_filter=len(filtered),
            chunks_output=len(final_chunks),
        )

        return RAGResult(
            chunks=final_chunks,
            total_found=len(reranked),
            variant_tier_used=variant_type,
        )

    # ── Strategy: REWRITE_RERANK (high_parwa) ─────────────────

    async def _strategy_rewrite_rerank(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        variant_type: str,
        top_k: int,
        filters: Optional[Dict[str, Any]],
    ) -> RAGResult:
        """high_parwa strategy: rewrite → rerank → filter."""
        return await self._execute_rewrite_rerank(
            chunks=chunks,
            query=query,
            company_id=company_id,
            top_k=top_k,
            filters=filters,
        )

    # ── Context Assembly (convenience method) ──────────────────

    def assemble_context(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        variant_type: str = "parwa",
    ) -> AssembledContext:
        """Assemble reranked chunks into a context window.

        This is a convenience method that selects the appropriate token
        budget based on the variant and delegates to
        ``ContextWindowAssembler``.

        Args:
            chunks:       Reranked chunks (already scored and ordered).
            query:        Original user query.
            company_id:   Tenant identifier (BC-001).
            variant_type: Determines the max token budget.

        Returns:
            ``AssembledContext`` with the combined context string.
        """
        config = VARIANT_RERANK_CONFIG.get(
            variant_type, VARIANT_RERANK_CONFIG["parwa"]
        )
        max_tokens: int = config["max_context_tokens"]

        assembled = ContextWindowAssembler.assemble(
            chunks=chunks,
            max_tokens=max_tokens,
            query=query,
        )

        logger.debug(
            "context_assembly_complete",
            company_id=company_id,
            variant_type=variant_type,
            total_tokens=assembled.total_tokens,
            max_tokens=max_tokens,
            truncated=assembled.truncated,
        )

        return assembled

    # ── Citation Tracking (convenience method) ─────────────────

    def track_citations(
        self,
        chunks: List[RAGChunk],
        assembled_context: AssembledContext,
    ) -> List[Citation]:
        """Track citations for the assembled context.

        Delegates to ``CitationTracker.track_citations()``.
        """
        return CitationTracker.track_citations(chunks, assembled_context)

    # ── End-to-End Pipeline (convenience) ─────────────────────

    async def rerank_and_assemble(
        self,
        chunks: List[RAGChunk],
        query: str,
        company_id: str,
        variant_type: str = "parwa",
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[RAGResult, AssembledContext, List[Citation]]:
        """Full pipeline: rerank → assemble context → track citations.

        Convenience method that combines ``rerank()``, ``assemble_context()``,
        and ``track_citations()`` into a single call.

        Args:
            chunks:       Retrieved chunks from ``RAGRetriever``.
            query:        User query.
            company_id:   Tenant identifier (BC-001).
            variant_type: One of ``mini_parwa``, ``parwa``, ``high_parwa``.
            top_k:        Maximum chunks to return.
            filters:      Optional metadata filters.

        Returns:
            Tuple of ``(RAGResult, AssembledContext, List[Citation])``.
        """
        # Step 1: Rerank
        result = await self.rerank(
            chunks=chunks,
            query=query,
            company_id=company_id,
            variant_type=variant_type,
            top_k=top_k,
            filters=filters,
        )

        # Step 2: Assemble context
        assembled = self.assemble_context(
            chunks=result.chunks,
            query=query,
            company_id=company_id,
            variant_type=variant_type,
        )

        # Step 3: Track citations
        citations = self.track_citations(chunks, assembled)

        return result, assembled, citations


# ── Redis Cache Helpers ───────────────────────────────────────────


def _build_rerank_cache_key(
    query: str,
    company_id: str,
    variant_type: str,
    top_k: int,
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a deterministic Redis cache key for reranked results.

    Format: ``rerank:{company_id}:{query_hash}``
    where ``query_hash`` is the first 16 hex chars of SHA-256 of the
    normalised query + variant + top_k + filters.
    """
    query_hash = hashlib.sha256(
        query.lower().strip().encode("utf-8")
    ).hexdigest()[:16]

    # Include variant, top_k, and filters in the hash for uniqueness
    meta = json.dumps(
        {"variant": variant_type, "top_k": top_k, "filters": filters or {}},
        sort_keys=True,
    )
    meta_hash = hashlib.sha256(meta.encode("utf-8")).hexdigest()[:8]

    return f"rerank:{company_id}:{query_hash}:{meta_hash}"


async def get_cached_rerank(
    company_id: str,
    query: str,
    variant_type: str,
    top_k: int,
    filters: Optional[Dict[str, Any]] = None,
) -> Optional[RAGResult]:
    """Look up a cached reranking result from Redis.

    BC-012: Fail-open — returns ``None`` on any Redis error.

    Args:
        company_id:   Tenant identifier (BC-001).
        query:        User query.
        variant_type: RAG variant tier.
        top_k:        Maximum chunks.
        filters:      Metadata filters used.

    Returns:
        Cached ``RAGResult`` or ``None`` if not found / error.
    """
    try:
        from app.core.redis import cache_get

        cache_key = _build_rerank_cache_key(
            query, company_id, variant_type, top_k, filters
        )
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
                chunks=chunks,
                total_found=cached.get("total_found", 0),
                retrieval_time_ms=cached.get("retrieval_time_ms", 0.0),
                query_embedding_time_ms=cached.get(
                    "query_embedding_time_ms", 0.0
                ),
                filters_applied=cached.get("filters_applied", {}),
                variant_tier_used=cached.get("variant_tier_used", "parwa"),
                cached=True,
            )
    except Exception as exc:
        # BC-008 / BC-012: Fail open
        logger.debug(
            "rerank_cache_get_failed",
            company_id=company_id,
            error=str(exc),
        )
    return None


async def set_cached_rerank(
    company_id: str,
    query: str,
    variant_type: str,
    top_k: int,
    result: RAGResult,
    filters: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = _RERANK_CACHE_TTL,
) -> bool:
    """Store a reranking result in Redis.

    BC-012: Fail-open — returns ``False`` on any Redis error.

    Args:
        company_id:   Tenant identifier (BC-001).
        query:        User query.
        variant_type: RAG variant tier.
        top_k:        Maximum chunks.
        result:       ``RAGResult`` to cache.
        filters:      Metadata filters used.
        ttl_seconds:  Cache TTL.

    Returns:
        ``True`` if caching succeeded, ``False`` otherwise.
    """
    try:
        from app.core.redis import cache_set

        cache_key = _build_rerank_cache_key(
            query, company_id, variant_type, top_k, filters
        )
        return await cache_set(
            company_id,
            cache_key,
            result.to_dict(),
            ttl_seconds=ttl_seconds,
        )
    except Exception as exc:
        # BC-008 / BC-012: Fail open
        logger.debug(
            "rerank_cache_set_failed",
            company_id=company_id,
            error=str(exc),
        )
    return False


async def invalidate_rerank_cache(
    company_id: str,
    query: Optional[str] = None,
) -> bool:
    """Invalidate cached rerank results for a tenant.

    If *query* is provided, only that specific query's cache entry is
    removed.  Otherwise, all rerank cache entries for the tenant are
    cleared (pattern-based deletion).

    BC-001: Scoped to company_id.
    BC-012: Fail-open.

    Args:
        company_id: Tenant identifier.
        query:      Optional query to narrow the invalidation.

    Returns:
        ``True`` if invalidation succeeded, ``False`` otherwise.
    """
    try:
        from app.core.redis import cache_delete

        if query:
            # Delete specific cache entry
            # Build key with all variants
            deleted = True
            for variant_type in VARIANT_RERANK_CONFIG:
                for top_k in [3, 5, 10]:
                    key = _build_rerank_cache_key(
                        query, company_id, variant_type, top_k
                    )
                    await cache_delete(company_id, key)
            return deleted
        else:
            # Pattern-based deletion for all rerank keys
            try:
                from app.core.redis import get_redis, make_key

                redis = await get_redis()
                pattern = make_key(company_id, "cache", "rerank:*")
                keys = []
                async for key in redis.scan_iter(match=pattern, count=100):
                    keys.append(key)
                if keys:
                    await redis.delete(*keys)
                return True
            except Exception:
                return False
    except Exception:
        return False


# ── Convenience Factory ───────────────────────────────────────────


def get_reranker() -> CrossEncoderReranker:
    """Factory function to obtain a ``CrossEncoderReranker`` instance.

    Returns a module-level singleton for efficiency.
    """
    if not hasattr(get_reranker, "_instance"):
        # type: ignore[attr-defined]
        get_reranker._instance = CrossEncoderReranker()
    return get_reranker._instance  # type: ignore[attr-defined]
