"""
CLARA RAG — Multi-Query Retrieval Module (F-064)

Generates multiple alternative phrasings of a customer query using an LLM,
retrieves results for each phrasing independently, then merges and
deduplicates results by chunk_id.  Chunks are ranked by their aggregate
relevance score (average across all queries where the chunk appeared).

This approach significantly improves recall by catching chunks that would
be missed by a single query phrasing, especially when the customer's
question is ambiguous or uses non-standard terminology.

Fallback (BC-008): If the LLM is unavailable, falls back to retrieving
with just the original query — retrieval still works, just without the
multi-query recall boost.

BC-001: All operations scoped to company_id.
BC-007: All LLM calls go through Smart Router.
BC-008: Graceful degradation on every async method.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from app.logger import get_logger
from app.core.rag_retrieval import RAGChunk, RAGResult, RAGRetriever

logger = get_logger("clara_multi_query")

# ── Prompt Template ──────────────────────────────────────────────────

MQ_SYSTEM_PROMPT: str = (
    "You are a search-query rephraser for a customer-support knowledge base. "
    "Given a customer's question, generate {num_alternatives} alternative "
    "phrasings that a different customer might use to ask the same thing. "
    "Each alternative should vary the vocabulary, sentence structure, or "
    "level of detail.  Output ONLY a JSON array of strings — no explanation, "
    "no markdown, no extra text."
)

MQ_USER_TEMPLATE: str = (
    "Original customer question:\n"
    "{query}\n\n"
    "Generate {num_alternatives} alternative phrasings as a JSON array of strings."
)

# ── Configuration ────────────────────────────────────────────────────

_DEFAULT_NUM_ALTERNATIVES: int = 3
_DEFAULT_TOP_K: int = 10

# Cache TTL for generated alternative queries
_MQ_CACHE_TTL_SECONDS: int = 120

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
            "multi_query_smart_router_import_failed",
            error=str(exc),
        )
        return None


# ── Cache Helpers ────────────────────────────────────────────────────


def _build_query_cache_key(
    query: str,
    company_id: str,
    variant_type: str,
    num_alternatives: int,
) -> str:
    """Build a deterministic cache key for alternative queries."""
    query_hash = hashlib.sha256(
        query.strip().lower().encode("utf-8")
    ).hexdigest()[:16]
    return f"mq:{query_hash}:{company_id}:{variant_type}:{num_alternatives}"


async def _cache_get_alternatives(
    company_id: str,
    cache_key: str,
) -> Optional[List[str]]:
    """Retrieve cached alternative queries."""
    try:
        from app.core.redis import cache_get

        cached = await cache_get(company_id, cache_key)
        if cached and isinstance(cached, list):
            # Validate all items are strings
            if all(isinstance(q, str) for q in cached):
                logger.debug(
                    "multi_query_cache_hit",
                    company_id=company_id,
                    cache_key=cache_key[:40],
                    alternatives_count=len(cached),
                )
                return cached
    except Exception as exc:
        logger.debug(
            "multi_query_cache_read_failed",
            error=str(exc),
        )
    return None


async def _cache_set_alternatives(
    company_id: str,
    cache_key: str,
    alternatives: List[str],
) -> bool:
    """Store alternative queries in Redis cache."""
    try:
        from app.core.redis import cache_set

        success = await cache_set(
            company_id,
            cache_key,
            alternatives,
            ttl_seconds=_MQ_CACHE_TTL_SECONDS,
        )
        if success:
            logger.debug(
                "multi_query_cache_stored",
                company_id=company_id,
                cache_key=cache_key[:40],
                alternatives_count=len(alternatives),
            )
        return success
    except Exception as exc:
        logger.debug(
            "multi_query_cache_write_failed",
            error=str(exc),
        )
        return False


# ── JSON Extraction Helper ───────────────────────────────────────────


def _extract_json_array(text: str) -> Optional[List[str]]:
    """Extract a JSON array of strings from LLM output.

    The LLM may wrap the array in markdown code fences or add
    extra text.  This function robustly extracts the first
    JSON array found in the response.

    Args:
        text: Raw LLM response text.

    Returns:
        List of strings, or None if parsing fails.
    """
    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown code fences
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language tag)
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        # Remove closing fence
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # Try to find a JSON array in the text
    # Look for the outermost [ ... ]
    bracket_start = cleaned.find("[")
    bracket_end = cleaned.rfind("]")
    if bracket_start != -1 and bracket_end > bracket_start:
        json_str = cleaned[bracket_start: bracket_end + 1]
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                # Validate all items are strings
                validated = []
                for item in parsed:
                    if isinstance(item, str) and item.strip():
                        validated.append(item.strip())
                if validated:
                    return validated
        except json.JSONDecodeError:
            pass

    # Fallback: try parsing the entire text
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            validated = []
            for item in parsed:
                if isinstance(item, str) and item.strip():
                    validated.append(item.strip())
            if validated:
                return validated
    except json.JSONDecodeError:
        pass

    # Last resort: try splitting by newlines if it looks like a list
    lines = [l.strip().strip('"').strip("'") for l in cleaned.split("\n") if l.strip()]
    if len(lines) >= 2:
        validated = [l for l in lines if l and not l.startswith("[") and not l.startswith("]")]
        if validated:
            return validated

    return None


# ── Multi-Query Retriever ────────────────────────────────────────────


class MultiQueryRetriever:
    """Multi-query retrieval engine for CLARA RAG.

    Generates alternative phrasings of the customer query, retrieves
    results for each phrasing, then merges and ranks by aggregate score.

    BC-008: Every public async method returns a safe default on error.
    BC-001: All operations scoped to company_id.
    BC-007: All LLM calls go through Smart Router.
    """

    def __init__(self, retriever: Optional[RAGRetriever] = None) -> None:
        """Initialize with an optional RAGRetriever instance.

        Args:
            retriever: RAGRetriever to use for actual retrieval.
                       If None, a new instance is created lazily.
        """
        self._retriever = retriever
        self._router = _get_smart_router()

    def _get_retriever(self) -> RAGRetriever:
        """Get or create the RAGRetriever."""
        if self._retriever is None:
            self._retriever = RAGRetriever()
        return self._retriever

    # ── Public API ──────────────────────────────────────────────

    async def generate_alternative_queries(
        self,
        query: str,
        company_id: str,
        variant_type: str = "parwa",
        num_alternatives: int = _DEFAULT_NUM_ALTERNATIVES,
    ) -> List[str]:
        """Generate alternative query phrasings using the LLM.

        Args:
            query:            The original customer query.
            company_id:       Tenant identifier (BC-001).
            variant_type:     One of mini_parwa, parwa, parwa_high.
            num_alternatives: Number of alternative phrasings to generate.

        Returns:
            List of alternative query strings.  Returns an empty list
            on LLM failure (BC-008).
        """
        if not query or not query.strip():
            return []

        # Clamp num_alternatives to reasonable range
        num_alternatives = max(1, min(num_alternatives, 5))

        # ── Step 1: Check cache ────────────────────────────────
        cache_key = _build_query_cache_key(
            query, company_id, variant_type, num_alternatives,
        )
        cached = await _cache_get_alternatives(company_id, cache_key)
        if cached is not None:
            return cached

        # ── Step 2: Generate via LLM ───────────────────────────
        alternatives = await self._llm_generate_queries(
            query=query,
            company_id=company_id,
            variant_type=variant_type,
            num_alternatives=num_alternatives,
        )

        if alternatives:
            # ── Step 3: Cache the results ───────────────────────
            await _cache_set_alternatives(company_id, cache_key, alternatives)
            return alternatives

        # BC-008: LLM unavailable — return empty list (caller uses original)
        logger.warning(
            "multi_query_generation_failed_returning_empty",
            company_id=company_id,
            variant_type=variant_type,
            query_preview=query[:80],
        )
        return []

    async def retrieve_with_multi_query(
        self,
        query: str,
        company_id: str,
        variant_type: str = "parwa",
        top_k: int = _DEFAULT_TOP_K,
    ) -> RAGResult:
        """Retrieve using multiple query phrasings, merge, and rank.

        Executes retrieval for the original query plus all generated
        alternative phrasings, then merges the results by chunk_id
        and ranks by aggregate score.

        Args:
            query:        The original customer query.
            company_id:   Tenant identifier (BC-001).
            variant_type: One of mini_parwa, parwa, parwa_high.
            top_k:        Maximum number of final results.

        Returns:
            RAGResult with merged, deduplicated, and ranked chunks.
        """
        start_time = time.monotonic()

        if not query or not query.strip():
            return RAGResult(
                variant_tier_used=variant_type,
                retrieval_time_ms=0.0,
            )

        # Step 1: Generate alternative queries
        alternatives = await self.generate_alternative_queries(
            query=query,
            company_id=company_id,
            variant_type=variant_type,
        )

        # Step 2: Build the list of all queries to execute
        all_queries = [query]  # Always include the original
        if alternatives:
            all_queries.extend(alternatives)

        logger.debug(
            "multi_query_retrieval_starting",
            company_id=company_id,
            variant_type=variant_type,
            total_queries=len(all_queries),
            has_alternatives=bool(alternatives),
        )

        # Step 3: Execute retrieval for all queries concurrently
        retriever = self._get_retriever()
        results: List[RAGResult] = []

        tasks = [
            retriever.retrieve(
                query=q,
                company_id=company_id,
                variant_type=variant_type,
                top_k=top_k,
            )
            for q in all_queries
        ]

        try:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    # BC-008: Log but continue with other results
                    logger.warning(
                        "multi_query_retrieval_error_for_query",
                        company_id=company_id,
                        query_index=i,
                        query_preview=all_queries[i][:60],
                        error=str(result),
                    )
                elif isinstance(result, RAGResult):
                    results.append(result)
        except Exception as exc:
            logger.warning(
                "multi_query_gather_error",
                company_id=company_id,
                error=str(exc),
            )

        # Step 4: If we have results, merge and rank
        if results:
            merged_chunks = self._merge_and_deduplicate(results)
            if merged_chunks:
                retrieval_time_ms = round(
                    (time.monotonic() - start_time) * 1000, 2
                )

                logger.info(
                    "multi_query_retrieval_complete",
                    company_id=company_id,
                    variant_type=variant_type,
                    queries_executed=len(results),
                    chunks_before_dedupe=sum(len(r.chunks) for r in results),
                    chunks_after_dedupe=len(merged_chunks),
                    top_k_requested=top_k,
                    retrieval_time_ms=retrieval_time_ms,
                )

                return RAGResult(
                    chunks=merged_chunks[:top_k],
                    total_found=len(merged_chunks),
                    retrieval_time_ms=retrieval_time_ms,
                    variant_tier_used=variant_type,
                )

        # BC-008: Fallback — retrieve with just the original query
        logger.warning(
            "multi_query_retrieval_fallback_to_single_query",
            company_id=company_id,
            variant_type=variant_type,
        )
        fallback_result = await retriever.retrieve(
            query=query,
            company_id=company_id,
            variant_type=variant_type,
            top_k=top_k,
        )
        retrieval_time_ms = round(
            (time.monotonic() - start_time) * 1000, 2
        )
        fallback_result.retrieval_time_ms = retrieval_time_ms
        fallback_result.degradation_used = True
        return fallback_result

    # ── Merge & Deduplication ──────────────────────────────────

    def _merge_and_deduplicate(
        self,
        results: List[RAGResult],
    ) -> List[RAGChunk]:
        """Merge results from multiple queries, deduplicate by chunk_id,
        and re-rank by aggregate score.

        For each unique chunk, the aggregate score is computed as the
        average of its scores across all queries where it appeared.
        Chunks that appear in more queries get a small frequency boost.

        Args:
            results: List of RAGResult objects from different queries.

        Returns:
            Deduplicated and re-ranked list of RAGChunk objects.
        """
        if not results:
            return []

        # Collect all scores per chunk_id
        chunks_with_scores: Dict[str, List[float]] = {}

        for result in results:
            for chunk in result.chunks:
                cid = chunk.chunk_id
                if cid not in chunks_with_scores:
                    chunks_with_scores[cid] = []
                chunks_with_scores[cid].append(chunk.score)

        # Build a lookup for chunk data (use first occurrence)
        chunk_data: Dict[str, RAGChunk] = {}
        for result in results:
            for chunk in result.chunks:
                if chunk.chunk_id not in chunk_data:
                    chunk_data[chunk.chunk_id] = chunk

        # Rank by aggregate score
        ranked = self._rank_by_aggregate_score(chunks_with_scores)

        # Build final list with updated scores
        merged: List[RAGChunk] = []
        for chunk_id, aggregate_score in ranked:
            original = chunk_data.get(chunk_id)
            if original is None:
                continue

            merged.append(RAGChunk(
                chunk_id=original.chunk_id,
                document_id=original.document_id,
                content=original.content,
                score=round(aggregate_score, 6),
                metadata=original.metadata,
                citation=original.citation,
            ))

        return merged

    def _rank_by_aggregate_score(
        self,
        chunks_with_scores: Dict[str, List[float]],
    ) -> List[Tuple[str, float]]:
        """Rank chunks by aggregate relevance score.

        The aggregate score is computed as:
            aggregate = avg_score * (1 + 0.1 * (num_appearances - 1))

        Where:
            - avg_score = mean of all individual scores for this chunk
            - num_appearances = number of queries where this chunk appeared
            - The frequency bonus rewards chunks found across multiple queries,
              capped at +30% for appearing in all queries.

        Args:
            chunks_with_scores: Dict mapping chunk_id to list of scores.

        Returns:
            List of (chunk_id, aggregate_score) tuples, sorted descending.
        """
        if not chunks_with_scores:
            return []

        max_appearances = max(len(scores) for scores in chunks_with_scores.values())
        ranked: List[Tuple[str, float]] = []

        for chunk_id, scores in chunks_with_scores.items():
            avg_score = sum(scores) / len(scores)
            num_appearances = len(scores)

            # Frequency bonus: up to +30% for appearing in all queries
            frequency_bonus = 0.1 * (num_appearances - 1) if max_appearances > 1 else 0.0
            aggregate = avg_score * (1.0 + min(frequency_bonus, 0.3))

            ranked.append((chunk_id, aggregate))

        # Sort by aggregate score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        logger.debug(
            "multi_query_ranking_complete",
            unique_chunks=len(ranked),
            max_appearances=max_appearances,
            top_score=ranked[0][1] if ranked else 0.0,
        )

        return ranked

    # ── Internal: LLM Query Generation ─────────────────────────

    async def _llm_generate_queries(
        self,
        query: str,
        company_id: str,
        variant_type: str,
        num_alternatives: int,
    ) -> Optional[List[str]]:
        """Call the LLM via Smart Router to generate alternative queries.

        Uses the LIGHT tier since query reformulation is straightforward.
        Parses the JSON array from the LLM response.

        BC-008: Returns None on any failure.
        """
        router = self._router or _get_smart_router()
        if router is None:
            logger.warning(
                "multi_query_router_unavailable_cannot_generate",
                company_id=company_id,
            )
            return None

        try:
            from app.core.smart_router import AtomicStepType

            routing = router.route(
                company_id=company_id,
                variant_type=variant_type,
                atomic_step=AtomicStepType.DRAFT_RESPONSE_SIMPLE,
            )

            messages = [
                {
                    "role": "system",
                    "content": MQ_SYSTEM_PROMPT.format(
                        num_alternatives=num_alternatives,
                    ),
                },
                {
                    "role": "user",
                    "content": MQ_USER_TEMPLATE.format(
                        query=query,
                        num_alternatives=num_alternatives,
                    ),
                },
            ]

            result = await router.async_execute_llm_call(
                company_id=company_id,
                routing_decision=routing,
                messages=messages,
                temperature=0.7,  # Moderate temp for diverse phrasings
                max_tokens=500,   # Enough for 3-5 alternative queries
            )

            content = result.get("content", "")
            if not content or not content.strip():
                if result.get("fallback_used"):
                    logger.warning(
                        "multi_query_llm_fallback_response_empty",
                        company_id=company_id,
                        error=result.get("error", "unknown"),
                    )
                return None

            # Parse the JSON array from the response
            alternatives = _extract_json_array(content)
            if alternatives:
                # Clamp to requested number
                alternatives = alternatives[:num_alternatives]
                logger.debug(
                    "multi_query_llm_generation_success",
                    company_id=company_id,
                    variant_type=variant_type,
                    model=result.get("model", "unknown"),
                    alternatives_generated=len(alternatives),
                    fallback_used=result.get("fallback_used", False),
                )
                return alternatives

            logger.warning(
                "multi_query_llm_response_parse_failed",
                company_id=company_id,
                response_preview=content[:200],
            )

        except Exception as exc:
            logger.warning(
                "multi_query_llm_generation_error",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )

        return None
