"""
CLARA RAG — LLM-Based Reranker (F-064)

Uses an LLM to score each retrieved chunk's relevance to the query
on a 1-10 scale, replacing the traditional BM25 cross-encoder reranking
with semantically-aware scoring.  This produces significantly better
rankings, especially for nuanced or complex queries.

The reranker is a drop-in replacement for the existing BM25 reranking
in ``rag_retrieval.RAGRetriever._rerank()`` and
``rag_reranking.CrossEncoderReranker._cross_encoder_score()``.

Batch scoring: up to 5 chunks per LLM call to reduce API usage while
maintaining quality.  Structured output parsing extracts scores from
the LLM response.

Fallback (BC-008): If the LLM is unavailable, falls back to the existing
BM25-inspired reranking — the pipeline still works, just without the
semantic scoring boost.

BC-001: All operations scoped to company_id.
BC-007: All LLM calls go through Smart Router.
BC-008: Graceful degradation on every async method.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.logger import get_logger
from app.core.rag_retrieval import RAGChunk, RAGResult

logger = get_logger("clara_llm_reranker")

# ── Prompt Templates ─────────────────────────────────────────────────

RERANK_SYSTEM_PROMPT: str = (
    "You are a relevance-scoring engine for a customer-support "
    "knowledge base.  Given a customer query and a list of knowledge-base "
    "chunks, score each chunk's relevance on a scale of 1 to 10, where:\n"
    "  10 = The chunk directly and completely answers the question.\n"
    "   7-9 = The chunk is highly relevant and provides most of the answer.\n"
    "   4-6 = The chunk is partially relevant (tangentially related).\n"
    "   1-3 = The chunk is not relevant to the question.\n\n"
    "Output ONLY a JSON object mapping chunk index to score. "
    "Example: {\"0\": 9, \"1\": 3, \"2\": 7}\n"
    "Do NOT add any explanation or extra text."
)

RERANK_USER_TEMPLATE: str = (
    "Customer query:\n{query}\n\n"
    "Score each chunk's relevance:\n\n"
    "{chunks_text}"
)

# ── Configuration ────────────────────────────────────────────────────

# Maximum chunks to send per LLM call (batching)
_BATCH_SIZE: int = 5

# Default maximum tokens for LLM response
_DEFAULT_MAX_TOKENS: int = 300

# Temperature for scoring (low = consistent, deterministic)
_SCORING_TEMPERATURE: float = 0.1

# ── Lazy Imports ─────────────────────────────────────────────────────

_smart_router = None  # type: ignore[assignment]


def _get_smart_router() -> Any:
    """Lazily import and return the SmartRouter singleton."""
    global _smart_router
    if _smart_router is not None:
        return _smart_router
    try:
        from app.core.smart_router import SmartRouter
        _smart_router = SmartRouter()
        return _smart_router
    except Exception as exc:
        logger.warning(
            "llm_reranker_smart_router_import_failed",
            error=str(exc),
        )
        return None


# ── Score Extraction ─────────────────────────────────────────────────


def _extract_scores_from_response(
    text: str,
    num_chunks: int,
) -> Optional[Dict[int, float]]:
    """Extract a dict of {chunk_index: score} from LLM response.

    Handles various output formats:
    - Clean JSON: {"0": 8, "1": 3}
    - Markdown-wrapped: ```json\n{"0": 8}\n```
    - Numbered lines: "0: 8\n1: 3"
    - List: [[0, 8], [1, 3]]

    Args:
        text:       Raw LLM response text.
        num_chunks: Expected number of chunks (for validation).

    Returns:
        Dict mapping chunk index (int) to score (float), or None.
    """
    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown code fences
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # Strategy 1: Parse as JSON object
    try:
        import json

        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            scores: Dict[int, float] = {}
            for key, value in parsed.items():
                try:
                    idx = int(key)
                    score = float(value)
                    if 1 <= score <= 10:
                        scores[idx] = score
                except (ValueError, TypeError):
                    continue
            if scores:
                return scores
    except Exception:
        pass

    # Strategy 2: Match "index": score or "index":score patterns
    pattern = r'["\']?(\d+)["\']?\s*[:\s]+(\d+(?:\.\d+)?)'
    matches = re.findall(pattern, cleaned)
    if matches:
        scores = {}
        for idx_str, score_str in matches:
            try:
                idx = int(idx_str)
                score = float(score_str)
                if 1 <= score <= 10:
                    scores[idx] = score
            except (ValueError, TypeError):
                continue
        if scores:
            return scores

    # Strategy 3: Try parsing as JSON array of [index, score] pairs
    try:
        import json

        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            scores = {}
            for item in parsed:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    try:
                        idx = int(item[0])
                        score = float(item[1])
                        if 1 <= score <= 10:
                            scores[idx] = score
                    except (ValueError, TypeError):
                        continue
            if scores:
                return scores
    except Exception:
        pass

    return None


# ── BM25 Fallback Reranker ──────────────────────────────────────────


def _bm25_rerank(query: str, chunks: List[RAGChunk]) -> List[RAGChunk]:
    """BM25-inspired reranking as fallback when LLM is unavailable.

    This mirrors the logic in ``RAGRetriever._rerank()`` to provide
    a consistent fallback experience.

    Scoring components:
    - Word overlap density (30%)
    - Exact phrase match bonus (10%)
    - Original vector score (60%)

    Args:
        query:  The customer query.
        chunks: Chunks to rerank.

    Returns:
        Re-scored list of RAGChunk, sorted by score descending.
    """
    if not chunks or not query or not query.strip():
        return list(chunks)

    query_lower = query.lower()
    query_words = set(re.findall(r"\b\w+\b", query_lower))
    if not query_words:
        return list(chunks)

    reranked: List[RAGChunk] = []
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
        rerank_score = (
            chunk.score * 0.6
            + word_density * 0.3
            + phrase_bonus
            + position_bonus
        )

        reranked.append(RAGChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            content=chunk.content,
            score=round(min(rerank_score, 1.0), 6),
            metadata=chunk.metadata,
            citation=chunk.citation,
        ))

    reranked.sort(key=lambda c: c.score, reverse=True)
    return reranked


# ── LLM Reranker ─────────────────────────────────────────────────────


class LLMReranker:
    """LLM-based reranker for CLARA RAG.

    Scores each chunk's relevance to the query using an LLM, providing
    semantically-aware reranking that outperforms traditional BM25
    cross-encoder approaches.

    This is a drop-in replacement for the existing BM25 reranking:
    it can be used anywhere ``_rerank(query, chunks)`` is called.

    Features:
    - Batch scoring: up to 5 chunks per LLM call.
    - Structured output parsing with multiple fallback strategies.
    - BM25 fallback when LLM is unavailable (BC-008).
    - Score normalisation to [0, 1] range for pipeline compatibility.

    BC-008: Every public async method returns a safe default on error.
    BC-001: All operations scoped to company_id.
    BC-007: All LLM calls go through Smart Router.
    """

    def __init__(self) -> None:
        self._router = _get_smart_router()

    # ── Public API ──────────────────────────────────────────────

    async def rerank(
        self,
        query: str,
        chunks: List[RAGChunk],
        company_id: str,
        variant_type: str = "parwa",
        top_k: int = 10,
    ) -> List[RAGChunk]:
        """Rerank chunks using LLM relevance scoring.

        Processes chunks in batches of up to 5, sending each batch to
        the LLM for relevance scoring on a 1-10 scale.  Scores are
        then normalised to [0, 1] and the chunks are re-sorted.

        Falls back to BM25 reranking if the LLM is unavailable (BC-008).

        Args:
            query:        The customer query.
            chunks:       Retrieved chunks to rerank.
            company_id:   Tenant identifier (BC-001).
            variant_type: One of mini_parwa, parwa, parwa_high.
            top_k:        Maximum number of chunks to return.

        Returns:
            Re-ranked list of RAGChunk, sorted by relevance score
            descending, limited to top_k.
        """
        start_time = time.monotonic()

        # Guard against invalid inputs
        if not chunks:
            return []
        if not query or not query.strip():
            # No query to score against — return sorted by original score
            sorted_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)
            return sorted_chunks[:top_k]

        # Check if LLM is available
        router = self._router or _get_smart_router()
        if router is None:
            logger.warning(
                "llm_reranker_unavailable_fallback_to_bm25",
                company_id=company_id,
            )
            bm25_result = _bm25_rerank(query, chunks)
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "llm_reranker_bm25_fallback_complete",
                company_id=company_id,
                variant_type=variant_type,
                chunks_reranked=len(bm25_result),
                elapsed_ms=elapsed_ms,
            )
            return bm25_result[:top_k]

        # Process chunks in batches
        all_scored_chunks: List[RAGChunk] = []

        for batch_start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[batch_start: batch_start + _BATCH_SIZE]
            scored_batch = await self._score_batch(
                query=query,
                chunks=batch,
                batch_offset=batch_start,
                company_id=company_id,
                variant_type=variant_type,
                router=router,
            )
            all_scored_chunks.extend(scored_batch)

        # If LLM scoring produced no results, fall back to BM25
        if not all_scored_chunks:
            logger.warning(
                "llm_reranker_no_scores_produced_fallback_to_bm25",
                company_id=company_id,
            )
            bm25_result = _bm25_rerank(query, chunks)
            return bm25_result[:top_k]

        # Sort by LLM score descending
        all_scored_chunks.sort(key=lambda c: c.score, reverse=True)
        final_chunks = all_scored_chunks[:top_k]

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "llm_reranker_complete",
            company_id=company_id,
            variant_type=variant_type,
            chunks_input=len(chunks),
            chunks_output=len(final_chunks),
            top_k=top_k,
            batches_processed=(len(chunks) + _BATCH_SIZE - 1) // _BATCH_SIZE,
            elapsed_ms=elapsed_ms,
            top_score=final_chunks[0].score if final_chunks else 0.0,
        )

        return final_chunks

    # ── Batch Scoring ───────────────────────────────────────────

    async def _score_batch(
        self,
        query: str,
        chunks: List[RAGChunk],
        batch_offset: int,
        company_id: str,
        variant_type: str,
        router: Any,
    ) -> List[RAGChunk]:
        """Score a batch of chunks using the LLM.

        Sends up to 5 chunks in a single LLM call and extracts
        relevance scores from the response.

        Args:
            query:        The customer query.
            chunks:       Chunks in this batch.
            batch_offset: Starting index of this batch in the full list.
            company_id:   Tenant identifier.
            variant_type: PARWA variant.
            router:       SmartRouter instance.

        Returns:
            List of RAGChunk with updated scores, or the original
            chunks with BM25 scores if LLM scoring fails.
        """
        if not chunks:
            return []

        # Build the chunks text for the prompt
        chunks_text_parts: List[str] = []
        for i, chunk in enumerate(chunks):
            content_preview = chunk.content[:300]
            if len(chunk.content) > 300:
                content_preview += "..."
            chunks_text_parts.append(
                f"Chunk {i}:\n{content_preview}"
            )

        chunks_text = "\n\n".join(chunks_text_parts)

        try:
            from app.core.smart_router import AtomicStepType

            routing = router.route(
                company_id=company_id,
                variant_type=variant_type,
                atomic_step=AtomicStepType.SENTIMENT_ANALYSIS,
            )

            messages = [
                {"role": "system", "content": RERANK_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": RERANK_USER_TEMPLATE.format(
                        query=query,
                        chunks_text=chunks_text,
                    ),
                },
            ]

            result = await router.async_execute_llm_call(
                company_id=company_id,
                routing_decision=routing,
                messages=messages,
                temperature=_SCORING_TEMPERATURE,
                max_tokens=_DEFAULT_MAX_TOKENS,
            )

            content = result.get("content", "")
            if not content or not content.strip():
                if result.get("fallback_used"):
                    logger.warning(
                        "llm_reranker_batch_fallback_response_empty",
                        company_id=company_id,
                        batch_offset=batch_offset,
                        error=result.get("error", "unknown"),
                    )
                return _bm25_rerank(query, chunks)

            # Extract scores from response
            scores = _extract_scores_from_response(
                text=content,
                num_chunks=len(chunks),
            )

            if scores is None:
                logger.warning(
                    "llm_reranker_batch_score_parse_failed",
                    company_id=company_id,
                    batch_offset=batch_offset,
                    response_preview=content[:200],
                )
                return _bm25_rerank(query, chunks)

            # Apply scores to chunks and normalise to [0, 1]
            scored_chunks: List[RAGChunk] = []
            for i, chunk in enumerate(chunks):
                if i in scores:
                    # Normalise 1-10 scale to 0-1
                    normalised_score = (scores[i] - 1) / 9.0
                    scored_chunks.append(RAGChunk(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        score=round(normalised_score, 6),
                        metadata=chunk.metadata,
                        citation=chunk.citation,
                    ))
                else:
                    # Score not found for this chunk — use original
                    scored_chunks.append(RAGChunk(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        score=chunk.score,
                        metadata=chunk.metadata,
                        citation=chunk.citation,
                    ))

            logger.debug(
                "llm_reranker_batch_scored",
                company_id=company_id,
                batch_offset=batch_offset,
                batch_size=len(chunks),
                scores_found=len(scores),
                model=result.get("model", "unknown"),
                fallback_used=result.get("fallback_used", False),
            )

            return scored_chunks

        except Exception as exc:
            # BC-008: Fall back to BM25 on any error
            logger.warning(
                "llm_reranker_batch_scoring_error_fallback_to_bm25",
                company_id=company_id,
                batch_offset=batch_offset,
                error=str(exc),
            )
            return _bm25_rerank(query, chunks)
