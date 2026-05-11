"""
CLARA RAG — HyDE (Hypothetical Document Embedding) Generator (F-064)

Uses an LLM to generate a hypothetical answer for a customer query,
then embeds that hypothetical answer and uses it as the primary
retrieval vector.  This bridges the semantic gap between short
conversational queries and the richer knowledge-base documents.

Fallback (BC-008): If the LLM is unavailable, falls back to direct
query embedding — the retrieval still works, just without the
HyDE boost.

BC-001: All operations scoped to company_id.
BC-007: All LLM calls go through Smart Router.
BC-008: Graceful degradation on every async method.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from app.logger import get_logger

logger = get_logger("clara_hyde")

# ── Prompt Template ──────────────────────────────────────────────────

HYDE_SYSTEM_PROMPT: str = (
    "You are a concise knowledge-base article writer for a customer-support "
    "system. Given a customer question, write a brief, factual paragraph "
    "(2-4 sentences, max ~120 words) that directly answers the question as "
    "if it were an entry in a help-center knowledge base. "
    "Do NOT add greetings, disclaimers, or metadata. "
    "Only output the answer text — nothing else."
)

HYDE_USER_TEMPLATE: str = (
    "Customer question:\n"
    "{query}\n\n"
    "Write a concise knowledge-base entry that would answer this question."
)

# ── Cache Settings ───────────────────────────────────────────────────

_HYDE_CACHE_TTL_SECONDS: int = 120  # 2 minutes

# ── Lazy Imports ─────────────────────────────────────────────────────

_smart_router = None  # type: ignore[assignment]


def _get_smart_router() -> Any:
    """Lazily import and return the SmartRouter singleton.

    BC-008: Returns None if the import fails.
    """
    global _smart_router
    if _smart_router is not None:
        return _smart_router
    try:
        from app.core.smart_router import SmartRouter
        _smart_router = SmartRouter()
        return _smart_router
    except Exception as exc:
        logger.warning(
            "hyde_smart_router_import_failed",
            error=str(exc),
        )
        return None


_redis_available: Optional[bool] = None


def _is_redis_available() -> bool:
    """Check if Redis caching is available (BC-012)."""
    global _redis_available
    if _redis_available is not None:
        return _redis_available
    try:
        from app.core.redis import get_redis
        # We only set the flag; we don't call get_redis() here to
        # avoid creating a connection at import time.
        _redis_available = True
        return True
    except Exception:
        _redis_available = False
        return False


# ── Cache Helpers ────────────────────────────────────────────────────


def _build_cache_key(query: str, company_id: str, variant_type: str) -> str:
    """Build a deterministic cache key for HyDE results.

    Format: hyde:{query_hash}:{company_id}:{variant_type}
    """
    query_hash = hashlib.sha256(
        query.strip().lower().encode("utf-8")
    ).hexdigest()[:16]
    return f"hyde:{query_hash}:{company_id}:{variant_type}"


async def _cache_get(
    company_id: str,
    cache_key: str,
) -> Optional[str]:
    """Retrieve a cached HyDE answer from Redis."""
    if not _is_redis_available():
        return None
    try:
        from app.core.redis import cache_get

        cached = await cache_get(company_id, cache_key)
        if cached and isinstance(cached, str):
            logger.debug(
                "hyde_cache_hit",
                company_id=company_id,
                cache_key=cache_key[:40],
            )
            return cached
    except Exception as exc:
        logger.debug(
            "hyde_cache_read_failed",
            error=str(exc),
        )
    return None


async def _cache_set(
    company_id: str,
    cache_key: str,
    value: str,
) -> bool:
    """Store a HyDE answer in Redis with configured TTL."""
    if not _is_redis_available():
        return False
    try:
        from app.core.redis import cache_set

        success = await cache_set(
            company_id,
            cache_key,
            value,
            ttl_seconds=_HYDE_CACHE_TTL_SECONDS,
        )
        if success:
            logger.debug(
                "hyde_cache_stored",
                company_id=company_id,
                cache_key=cache_key[:40],
                ttl_seconds=_HYDE_CACHE_TTL_SECONDS,
            )
        return success
    except Exception as exc:
        logger.debug(
            "hyde_cache_write_failed",
            error=str(exc),
        )
        return False


# ── Embedding Helper ─────────────────────────────────────────────────


async def _generate_embedding(text: str) -> Optional[List[float]]:
    """Generate an embedding vector for the given text.

    Tries the EmbeddingService first, falls back to the vector store's
    own embedding generator (BC-008).
    """
    if not text or not text.strip():
        return None

    # Try real embedding service
    try:
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService(company_id="hyde_query")
        embedding = svc.generate_embedding(text)
        if embedding:
            return embedding
    except Exception as exc:
        logger.debug(
            "hyde_embedding_service_unavailable",
            error=str(exc),
        )

    # BC-008: Fallback to vector store's embedding generator
    try:
        from shared.knowledge_base.vector_search import get_vector_store
        store = get_vector_store()
        if hasattr(store, "_generate_embedding"):
            embedding = store._generate_embedding(text)
            if embedding:
                return embedding
    except Exception as exc:
        logger.warning(
            "hyde_store_embedding_failed",
            error=str(exc),
        )

    return None


# ── HyDE Generator ───────────────────────────────────────────────────


class HyDEGenerator:
    """Hypothetical Document Embedding generator for CLARA RAG.

    Generates a hypothetical answer for a customer query using an LLM,
    then embeds that answer to use as the retrieval vector.  This
    approach improves retrieval quality when the customer query is
    brief, informal, or semantically distant from the KB documents.

    BC-008: Every public async method returns a safe default on error.
    BC-001: All operations are scoped to company_id.
    BC-007: All LLM calls go through the Smart Router.
    """

    def __init__(self) -> None:
        self._router = _get_smart_router()

    # ── Public API ──────────────────────────────────────────────

    async def generate_hypothetical_answer(
        self,
        query: str,
        company_id: str,
        variant_type: str = "parwa",
    ) -> str:
        """Generate a hypothetical answer (a fake KB entry) for the query.

        The hypothetical answer is a concise paragraph that directly
        addresses the customer's question, written as if it were a
        knowledge-base article.

        Args:
            query:        The customer's question.
            company_id:   Tenant identifier (BC-001).
            variant_type: One of mini_parwa, parwa, parwa_high.

        Returns:
            The generated hypothetical answer string.  Returns the
            original query text on LLM failure (BC-008).
        """
        if not query or not query.strip():
            logger.warning(
                "hyde_empty_query_returning_as_is",
                company_id=company_id,
            )
            return query

        # ── Step 1: Check cache ────────────────────────────────
        cache_key = _build_cache_key(query, company_id, variant_type)
        cached_answer = await _cache_get(company_id, cache_key)
        if cached_answer:
            return cached_answer

        # ── Step 2: Generate via LLM ───────────────────────────
        hypothesis = await self._llm_generate(query, company_id, variant_type)

        if hypothesis and hypothesis.strip():
            # ── Step 3: Cache the result ───────────────────────
            await _cache_set(company_id, cache_key, hypothesis.strip())
            return hypothesis.strip()

        # BC-008: LLM unavailable — return the original query
        logger.warning(
            "hyde_generation_failed_returning_original_query",
            company_id=company_id,
            variant_type=variant_type,
            query_preview=query[:80],
        )
        return query

    async def get_hyde_embedding(
        self,
        query: str,
        company_id: str,
        variant_type: str = "parwa",
    ) -> Optional[List[float]]:
        """Generate and embed a hypothetical answer for the query.

        This is the main entry point for the RAG pipeline: it generates
        a hypothetical answer, embeds it, and returns the embedding
        vector for use in similarity search.

        Falls back to embedding the original query directly if the
        LLM is unavailable (BC-008).

        Args:
            query:        The customer's question.
            company_id:   Tenant identifier (BC-001).
            variant_type: One of mini_parwa, parwa, parwa_high.

        Returns:
            Embedding vector (list of floats), or None on complete
            failure.
        """
        if not query or not query.strip():
            return None

        start_time = time.monotonic()

        # Step 1: Generate hypothetical answer
        hypothesis = await self.generate_hypothetical_answer(
            query=query,
            company_id=company_id,
            variant_type=variant_type,
        )

        # Step 2: Embed the hypothetical answer
        if hypothesis and hypothesis.strip():
            embedding = await _generate_embedding(hypothesis)
            if embedding:
                elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
                logger.info(
                    "hyde_embedding_generated",
                    company_id=company_id,
                    variant_type=variant_type,
                    embedding_dim=len(embedding),
                    hypothesis_length=len(hypothesis),
                    elapsed_ms=elapsed_ms,
                )
                return embedding

        # BC-008: Fallback — embed the original query directly
        logger.warning(
            "hyde_embedding_failed_fallback_to_query_embedding",
            company_id=company_id,
            variant_type=variant_type,
        )
        query_embedding = await _generate_embedding(query)
        if query_embedding:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "hyde_fallback_query_embedding_generated",
                company_id=company_id,
                elapsed_ms=elapsed_ms,
            )
        return query_embedding

    # ── Internal: LLM Generation ───────────────────────────────

    async def _llm_generate(
        self,
        query: str,
        company_id: str,
        variant_type: str,
    ) -> Optional[str]:
        """Call the LLM via Smart Router to generate a hypothetical answer.

        Uses the LIGHT tier since HyDE generation is a straightforward
        text-generation task that doesn't need heavy reasoning.

        BC-008: Returns None on any failure.
        """
        router = self._router or _get_smart_router()
        if router is None:
            logger.warning(
                "hyde_router_unavailable_cannot_generate",
                company_id=company_id,
            )
            return None

        try:
            from app.core.smart_router import AtomicStepType

            # Route to LIGHT tier — HyDE generation is not reasoning-intensive
            routing = router.route(
                company_id=company_id,
                variant_type=variant_type,
                atomic_step=AtomicStepType.DRAFT_RESPONSE_SIMPLE,
            )

            messages = [
                {"role": "system", "content": HYDE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": HYDE_USER_TEMPLATE.format(query=query),
                },
            ]

            result = await router.async_execute_llm_call(
                company_id=company_id,
                routing_decision=routing,
                messages=messages,
                temperature=0.3,  # Low temp for factual, consistent output
                max_tokens=300,   # Short hypothetical answer
            )

            content = result.get("content", "")
            if content and content.strip():
                logger.debug(
                    "hyde_llm_generation_success",
                    company_id=company_id,
                    variant_type=variant_type,
                    model=result.get("model", "unknown"),
                    hypothesis_length=len(content.strip()),
                    fallback_used=result.get("fallback_used", False),
                )
                return content.strip()

            if result.get("fallback_used"):
                logger.warning(
                    "hyde_llm_fallback_response_empty",
                    company_id=company_id,
                    error=result.get("error", "unknown"),
                )

        except Exception as exc:
            # BC-008: Never crash — log and return None
            logger.warning(
                "hyde_llm_generation_error",
                company_id=company_id,
                variant_type=variant_type,
                error=str(exc),
            )

        return None
